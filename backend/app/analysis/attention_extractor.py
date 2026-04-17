"""
Attention Weight Extractor for Transformer Models

Extracts and aggregates attention weights from transformer models (DeBERTa, RoBERTa)
to provide interpretable token-level importance scores.

Features:
- Multi-head attention aggregation
- CLS token attention extraction
- Layer-specific attention weights
- Normalized importance scores
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports
_torch = None
_transformers = None


def _import_dependencies():
    """Lazy import heavy dependencies"""
    global _torch, _transformers
    if _torch is None:
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            _torch = torch
            _transformers = (AutoTokenizer, AutoModelForSequenceClassification)
            logger.info("Torch and transformers loaded successfully")
        except ImportError:
            logger.warning("torch/transformers not installed")
            _torch = False
            _transformers = False
    return (_torch, _transformers) if _torch is not False else (None, None)


class AttentionExtractor:
    """
    Extract attention weights from transformer models
    
    Supports DeBERTa, RoBERTa, BERT, and similar architectures.
    """
    
    def __init__(self, model_name_or_path: str):
        """
        Initialize attention extractor
        
        Args:
            model_name_or_path: HuggingFace model ID or local path
        """
        self.model_name_or_path = model_name_or_path
        self.model = None
        self.tokenizer = None
        
        self._load_model()
    
    def _load_model(self):
        """Load model and tokenizer"""
        torch, transformers = _import_dependencies()
        if torch is None or transformers is None:
            logger.warning("Cannot load model: dependencies not available")
            return
        
        AutoTokenizer, AutoModelForSequenceClassification = transformers
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name_or_path,
                output_attentions=True  # Enable attention output
            )
            self.model.eval()  # Set to evaluation mode
            logger.info(f"Attention extractor loaded: {self.model_name_or_path}")
        except Exception as e:
            logger.error(f"Failed to load model for attention extraction: {e}")
            self.model = None
            self.tokenizer = None
    
    def is_available(self) -> bool:
        """Check if extractor is ready"""
        return self.model is not None and self.tokenizer is not None
    
    def extract_attention(self, text: str, layer: int = -1) -> Optional[Dict]:
        """
        Extract attention weights from specified layer
        
        Args:
            text: Input text
            layer: Layer index (-1 for last layer, 0 for first)
        
        Returns:
            {
                "tokens": [str],
                "attention_matrix": [[float]],  # shape: [seq_len, seq_len]
                "cls_attention": [float],  # attention from [CLS] token
                "aggregated_scores": [float],  # per-token importance
                "layer": int
            }
            
            Returns None if extraction fails
        """
        if not self.is_available():
            logger.warning("Attention extractor not available")
            return None
        
        torch, _ = _import_dependencies()
        if torch is None:
            return None
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=False
            )
            
            # Get tokens for display
            tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
            
            # Forward pass with attention output
            with torch.no_grad():
                outputs = self.model(**inputs, output_attentions=True)
                attentions = outputs.attentions  # Tuple of attention tensors
            
            # Validate layer index
            num_layers = len(attentions)
            if layer < 0:
                layer = num_layers + layer
            if layer < 0 or layer >= num_layers:
                logger.warning(f"Invalid layer {layer}, using last layer")
                layer = num_layers - 1
            
            # Extract target layer attention
            # Shape: [batch_size, num_heads, seq_len, seq_len]
            layer_attention = attentions[layer][0]  # Remove batch dimension
            
            # Aggregate multi-head attention (average across heads)
            # Shape: [seq_len, seq_len]
            aggregated_attention = layer_attention.mean(dim=0).cpu().numpy()
            
            # Extract CLS token attention (first token)
            # This shows which tokens the [CLS] token attends to
            cls_attention = aggregated_attention[0, :].tolist()
            
            # Compute per-token importance scores
            # Use attention TO each token (column-wise sum)
            token_scores = aggregated_attention.sum(axis=0)
            
            # Normalize scores to [0, 1]
            if token_scores.max() > 0:
                token_scores = token_scores / token_scores.max()
            
            # Skip special tokens ([CLS], [SEP], [PAD]) in scores
            aggregated_scores = []
            for i, token in enumerate(tokens):
                if token in ['[CLS]', '[SEP]', '[PAD]', '<s>', '</s>', '<pad>']:
                    aggregated_scores.append(0.0)
                else:
                    aggregated_scores.append(float(token_scores[i]))
            
            return {
                "tokens": tokens,
                "attention_matrix": aggregated_attention.tolist(),
                "cls_attention": cls_attention,
                "aggregated_scores": aggregated_scores,
                "layer": layer,
                "num_layers": num_layers
            }
            
        except Exception as e:
            logger.error(f"Attention extraction failed: {e}")
            return None
    
    def visualize_attention(self, text: str, layer: int = -1) -> Optional[Dict]:
        """
        Generate attention visualization data for UI
        
        Args:
            text: Input text
            layer: Layer index
        
        Returns:
            {
                "tokens": [str],
                "importance_scores": [float],
                "top_tokens": [{"token": str, "score": float, "position": int}]
            }
        """
        attention_data = self.extract_attention(text, layer)
        if attention_data is None:
            return None
        
        tokens = attention_data["tokens"]
        scores = attention_data["aggregated_scores"]
        
        # Get top important tokens (excluding special tokens)
        token_importance = []
        for i, (token, score) in enumerate(zip(tokens, scores)):
            if score > 0:  # Skip special tokens (score = 0)
                token_importance.append({
                    "token": token,
                    "score": round(score, 3),
                    "position": i
                })
        
        # Sort by importance
        token_importance.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "tokens": tokens,
            "importance_scores": [round(s, 3) for s in scores],
            "top_tokens": token_importance[:10]  # Top 10 tokens
        }


# Singleton instance
_attention_extractor = None


def get_attention_extractor(model_name_or_path: str = None) -> Optional[AttentionExtractor]:
    """
    Get or create attention extractor (cached)
    
    Args:
        model_name_or_path: Model ID or path (uses default if None)
    
    Returns:
        AttentionExtractor instance or None
    """
    global _attention_extractor
    
    if model_name_or_path is None:
        model_name_or_path = "Bharat2004/deberta-fakenews-detector"
    
    if _attention_extractor is None:
        try:
            _attention_extractor = AttentionExtractor(model_name_or_path)
            if _attention_extractor.is_available():
                logger.info("Attention extractor created and cached")
            else:
                _attention_extractor = None
        except Exception as e:
            logger.error(f"Failed to create attention extractor: {e}")
            _attention_extractor = None
    
    return _attention_extractor


def extract_attention_weights(text: str, model_name_or_path: str = None, 
                              layer: int = -1) -> Optional[Dict]:
    """
    Convenience function to extract attention weights
    
    Args:
        text: Input text
        model_name_or_path: Model ID or path
        layer: Layer index (-1 for last)
    
    Returns:
        Attention data dict or None
    """
    extractor = get_attention_extractor(model_name_or_path)
    if extractor is None:
        return None
    
    return extractor.extract_attention(text, layer)


# Example usage
if __name__ == "__main__":
    print("Attention Weight Extractor")
    print("=" * 60)
    print("\nThis module extracts attention weights from transformer models.")
    print("\nUsage:")
    print("  from app.analysis.attention_extractor import extract_attention_weights")
    print("  attention = extract_attention_weights(text)")
    print("\nRequires: pip install transformers torch")

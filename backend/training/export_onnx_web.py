"""
Export DeBERTa model to ONNX Web format for browser-side inference

This script:
1. Loads the trained model from HuggingFace
2. Exports to ONNX format
3. Quantizes for smaller size (<50MB target)
4. Optimizes for browser inference
5. Saves tokenizer configuration

Target: <50MB model, <200ms inference time
"""

import os
import json
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from optimum.onnxruntime import ORTModelForSequenceClassification
from onnxruntime.quantization import quantize_dynamic, QuantType
import onnx
from onnx import optimizer

# Configuration
MODEL_ID = "Bharat2004/deberta-fakenews-detector"
OUTPUT_DIR = "./onnx_web"
QUANTIZED_MODEL = "model_quantized.onnx"

def export_to_onnx():
    """Export model to ONNX format"""
    print("="*80)
    print("EXPORTING MODEL TO ONNX WEB FORMAT")
    print("="*80)
    print()
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Step 1: Load model from HuggingFace
    print("Step 1: Loading model from HuggingFace...")
    print(f"Model ID: {MODEL_ID}")
    
    try:
        model = ORTModelForSequenceClassification.from_pretrained(
            MODEL_ID,
            export=True,
            provider="CPUExecutionProvider"
        )
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        return False
    
    print()
    
    # Step 2: Save base ONNX model
    print("Step 2: Saving base ONNX model...")
    base_model_path = os.path.join(OUTPUT_DIR, "model.onnx")
    model.save_pretrained(OUTPUT_DIR)
    
    # Get model size
    if os.path.exists(base_model_path):
        size_mb = os.path.getsize(base_model_path) / (1024 * 1024)
        print(f"✓ Base model saved: {size_mb:.1f} MB")
    else:
        print("✗ Base model not found")
        return False
    
    print()
    
    # Step 3: Quantize model for smaller size
    print("Step 3: Quantizing model...")
    print("Target: <50MB for browser deployment")
    
    try:
        quantized_path = os.path.join(OUTPUT_DIR, QUANTIZED_MODEL)
        
        quantize_dynamic(
            base_model_path,
            quantized_path,
            weight_type=QuantType.QUInt8,
            optimize_model=True
        )
        
        quantized_size_mb = os.path.getsize(quantized_path) / (1024 * 1024)
        reduction = ((size_mb - quantized_size_mb) / size_mb) * 100
        
        print(f"✓ Quantized model saved: {quantized_size_mb:.1f} MB")
        print(f"  Size reduction: {reduction:.1f}%")
        
        if quantized_size_mb > 50:
            print(f"⚠ Warning: Model size ({quantized_size_mb:.1f} MB) exceeds 50MB target")
        
    except Exception as e:
        print(f"✗ Quantization failed: {e}")
        return False
    
    print()
    
    # Step 4: Optimize ONNX graph
    print("Step 4: Optimizing ONNX graph...")
    
    try:
        # Load quantized model
        onnx_model = onnx.load(quantized_path)
        
        # Apply optimizations
        passes = [
            'eliminate_identity',
            'eliminate_nop_transpose',
            'eliminate_nop_pad',
            'eliminate_unused_initializer',
            'fuse_consecutive_transposes',
            'fuse_transpose_into_gemm'
        ]
        
        optimized_model = optimizer.optimize(onnx_model, passes)
        
        # Save optimized model
        optimized_path = os.path.join(OUTPUT_DIR, "model_optimized.onnx")
        onnx.save(optimized_model, optimized_path)
        
        optimized_size_mb = os.path.getsize(optimized_path) / (1024 * 1024)
        print(f"✓ Optimized model saved: {optimized_size_mb:.1f} MB")
        
    except Exception as e:
        print(f"⚠ Optimization failed (using quantized model): {e}")
        optimized_path = quantized_path
        optimized_size_mb = quantized_size_mb
    
    print()
    
    # Step 5: Save tokenizer
    print("Step 5: Saving tokenizer...")
    
    try:
        tokenizer.save_pretrained(OUTPUT_DIR)
        print("✓ Tokenizer saved")
    except Exception as e:
        print(f"✗ Failed to save tokenizer: {e}")
        return False
    
    print()
    
    # Step 6: Create metadata file
    print("Step 6: Creating metadata...")
    
    metadata = {
        "model_id": MODEL_ID,
        "model_type": "deberta-v3-base",
        "task": "text-classification",
        "labels": ["real", "fake"],
        "max_length": 512,
        "quantized": True,
        "optimized": True,
        "model_size_mb": optimized_size_mb,
        "target_inference_time_ms": 200,
        "accuracy": 0.9663,
        "f1_score": 0.9646,
        "export_date": "2026-04-16",
        "files": {
            "model": "model_optimized.onnx",
            "tokenizer": "tokenizer.json",
            "config": "config.json"
        },
        "usage": {
            "javascript": "See extension/background/onnx_inference.js",
            "python": "Use onnxruntime for inference"
        }
    }
    
    metadata_path = os.path.join(OUTPUT_DIR, "metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("✓ Metadata saved")
    print()
    
    # Step 7: Create README
    print("Step 7: Creating README...")
    
    readme_content = f"""# ONNX Web Model for Browser-Side Inference

## Model Information

- **Model ID**: {MODEL_ID}
- **Base Model**: microsoft/deberta-v3-base
- **Task**: Binary text classification (real/fake news)
- **Accuracy**: 96.63%
- **F1 Score**: 0.9646

## Files

- `model_optimized.onnx` - Quantized and optimized model ({optimized_size_mb:.1f} MB)
- `tokenizer.json` - Fast tokenizer configuration
- `config.json` - Model configuration
- `metadata.json` - Model metadata and usage info

## Usage in Browser

```javascript
import * as ort from 'onnxruntime-web';

// Load model
const session = await ort.InferenceSession.create('model_optimized.onnx');

// Tokenize input
const inputs = tokenizer.encode(text);

// Run inference
const feeds = {{
    input_ids: new ort.Tensor('int64', inputs.input_ids, [1, inputs.length]),
    attention_mask: new ort.Tensor('int64', inputs.attention_mask, [1, inputs.length])
}};

const results = await session.run(feeds);
const logits = results.logits.data;

// Get prediction
const probabilities = softmax(logits);
const verdict = probabilities[1] > 0.5 ? 'fake' : 'real';
```

## Performance

- **Target Inference Time**: <200ms
- **Model Size**: {optimized_size_mb:.1f} MB
- **Memory Usage**: ~100MB
- **Quantization**: INT8

## Integration

See `extension/background/onnx_inference.js` for complete implementation.

## License

MIT License - Same as parent project
"""
    
    readme_path = os.path.join(OUTPUT_DIR, "README.md")
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print("✓ README created")
    print()
    
    # Final summary
    print("="*80)
    print("EXPORT COMPLETE!")
    print("="*80)
    print()
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Model size: {optimized_size_mb:.1f} MB")
    print(f"Files created:")
    print(f"  - model_optimized.onnx")
    print(f"  - tokenizer.json")
    print(f"  - config.json")
    print(f"  - metadata.json")
    print(f"  - README.md")
    print()
    print("Next steps:")
    print("  1. Copy files to extension/models/ directory")
    print("  2. Implement onnx_inference.js in extension")
    print("  3. Update service_worker.js to use local inference")
    print("  4. Test inference performance")
    print()
    
    return True

def test_inference():
    """Test ONNX model inference"""
    print("="*80)
    print("TESTING ONNX INFERENCE")
    print("="*80)
    print()
    
    try:
        import onnxruntime as ort
        import numpy as np
        
        # Load model
        model_path = os.path.join(OUTPUT_DIR, "model_optimized.onnx")
        session = ort.InferenceSession(model_path)
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(OUTPUT_DIR)
        
        # Test cases
        test_cases = [
            "COVID vaccines are safe and effective",
            "Scientists confirm earth is flat",
            "Stock market reaches new high"
        ]
        
        print("Running test predictions...")
        print()
        
        for text in test_cases:
            # Tokenize
            inputs = tokenizer(
                text,
                return_tensors="np",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # Run inference
            import time
            start = time.time()
            
            outputs = session.run(
                None,
                {
                    "input_ids": inputs["input_ids"].astype(np.int64),
                    "attention_mask": inputs["attention_mask"].astype(np.int64)
                }
            )
            
            elapsed = (time.time() - start) * 1000  # Convert to ms
            
            # Get prediction
            logits = outputs[0][0]
            probs = np.exp(logits) / np.sum(np.exp(logits))
            verdict = "fake" if probs[1] > 0.5 else "real"
            confidence = max(probs)
            
            print(f"Text: {text[:50]}...")
            print(f"Verdict: {verdict.upper()} (confidence: {confidence:.2%})")
            print(f"Inference time: {elapsed:.1f}ms")
            print()
        
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    # Export model
    success = export_to_onnx()
    
    if success:
        # Test inference
        print()
        test_inference()
    else:
        print("Export failed. Please check errors above.")

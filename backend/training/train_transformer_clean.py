"""
Clean Transformer Training Pipeline for Fake News Detection

This script trains a DeBERTa-v3-base model on fake news datasets.
Designed to run on Kaggle/Colab with GPU.

Usage:
    python train_transformer_clean.py

Outputs:
    - deberta_factcheck/ (model + tokenizer)
    - training_results.json (metrics)
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding
)
from datasets import Dataset

# ── Configuration ──────────────────────────────────────────────
CONFIG = {
    'model_name': 'microsoft/deberta-v3-base',  # 184M params
    'max_length': 512,
    'batch_size': 16,
    'learning_rate': 2e-5,
    'epochs': 3,
    'warmup_ratio': 0.1,
    'weight_decay': 0.01,
    'fp16': True,  # Mixed precision
    'output_dir': './deberta_factcheck',
    'save_steps': 500,
    'eval_steps': 500,
    'logging_steps': 100,
}

print("="*60)
print("FAKE NEWS DETECTION - TRANSFORMER TRAINING")
print("="*60)
print(f"Model: {CONFIG['model_name']}")
print(f"Device: {'GPU' if torch.cuda.is_available() else 'CPU'}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
print("="*60)

# ── Load Data ──────────────────────────────────────────────────
def load_datasets():
    """Load and merge all available datasets"""
    frames = []
    
    # Dataset 1: Fake.csv + True.csv
    if os.path.exists("Fake.csv") and os.path.exists("True.csv"):
        fake_df = pd.read_csv("Fake.csv")
        true_df = pd.read_csv("True.csv")
        
        fake_df['text'] = (fake_df.get('title', '') + ' ' + fake_df.get('text', '')).str.strip()
        true_df['text'] = (true_df.get('title', '') + ' ' + true_df.get('text', '')).str.strip()
        
        fake_df['label'] = 1
        true_df['label'] = 0
        
        frames.append(fake_df[['text', 'label']])
        frames.append(true_df[['text', 'label']])
        print(f"✓ Loaded Fake.csv + True.csv: {len(fake_df) + len(true_df)} samples")
    
    # Dataset 2: fake_news_dataset_44k.csv
    if os.path.exists("fake_news_dataset_44k.csv"):
        df = pd.read_csv("fake_news_dataset_44k.csv")
        if 'text' in df.columns and 'label' in df.columns:
            df = df[['text', 'label']].dropna()
            df['label'] = df['label'].astype(int)
            frames.append(df)
            print(f"✓ Loaded fake_news_dataset_44k.csv: {len(df)} samples")
    
    # Dataset 3: fake_news_dataset_20k.csv
    if os.path.exists("fake_news_dataset_20k.csv"):
        df = pd.read_csv("fake_news_dataset_20k.csv")
        if 'text' in df.columns and 'label' in df.columns:
            df['text'] = (df.get('title', '') + ' ' + df['text']).str.strip()
            df['label'] = df['label'].str.lower().map({'fake': 1, 'real': 0})
            df = df[['text', 'label']].dropna()
            df['label'] = df['label'].astype(int)
            frames.append(df)
            print(f"✓ Loaded fake_news_dataset_20k.csv: {len(df)} samples")
    
    if not frames:
        raise ValueError("No datasets found! Add CSV files to current directory.")
    
    # Merge and clean
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=['text', 'label'])
    
    # Quality filters
    df = df[df['text'].str.len() >= 30]  # Min 30 chars
    df = df[df['text'].str.len() <= 5000]  # Max 5000 chars
    df = df[df['text'].str.contains(r'[a-zA-Z]', regex=True)]  # Must have letters
    df = df.drop_duplicates(subset=['text'])
    
    print(f"\n📊 Total samples: {len(df)}")
    print(f"   Fake: {df['label'].sum()} ({df['label'].mean()*100:.1f}%)")
    print(f"   Real: {(df['label']==0).sum()} ({(1-df['label'].mean())*100:.1f}%)")
    
    return df

# ── Prepare Dataset ────────────────────────────────────────────
def prepare_dataset(df, tokenizer):
    """Convert DataFrame to HuggingFace Dataset"""
    
    # Split: 80% train, 10% val, 10% test
    train_df, temp_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df['label']
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, random_state=42, stratify=temp_df['label']
    )
    
    print(f"\n📂 Split:")
    print(f"   Train: {len(train_df)} samples")
    print(f"   Val:   {len(val_df)} samples")
    print(f"   Test:  {len(test_df)} samples")
    
    # Convert to HuggingFace Dataset
    train_dataset = Dataset.from_pandas(train_df[['text', 'label']])
    val_dataset = Dataset.from_pandas(val_df[['text', 'label']])
    test_dataset = Dataset.from_pandas(test_df[['text', 'label']])
    
    # Tokenize
    def tokenize_function(examples):
        return tokenizer(
            examples['text'],
            truncation=True,
            max_length=CONFIG['max_length'],
            padding=False  # Dynamic padding in collator
        )
    
    print("\n🔄 Tokenizing...")
    train_dataset = train_dataset.map(tokenize_function, batched=True, remove_columns=['text'])
    val_dataset = val_dataset.map(tokenize_function, batched=True, remove_columns=['text'])
    test_dataset = test_dataset.map(tokenize_function, batched=True, remove_columns=['text'])
    
    return train_dataset, val_dataset, test_dataset

# ── Training ───────────────────────────────────────────────────
def compute_metrics(eval_pred):
    """Compute accuracy and F1"""
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    
    acc = accuracy_score(labels, predictions)
    f1 = f1_score(labels, predictions, average='macro')
    
    return {'accuracy': acc, 'f1': f1}

def train_model(train_dataset, val_dataset, tokenizer):
    """Train DeBERTa model"""
    
    print("\n🚀 Loading model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        CONFIG['model_name'],
        num_labels=2,
        problem_type="single_label_classification"
    )
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=CONFIG['output_dir'],
        num_train_epochs=CONFIG['epochs'],
        per_device_train_batch_size=CONFIG['batch_size'],
        per_device_eval_batch_size=CONFIG['batch_size'] * 2,
        learning_rate=CONFIG['learning_rate'],
        warmup_ratio=CONFIG['warmup_ratio'],
        weight_decay=CONFIG['weight_decay'],
        fp16=CONFIG['fp16'] and torch.cuda.is_available(),
        logging_steps=CONFIG['logging_steps'],
        eval_strategy='steps',
        eval_steps=CONFIG['eval_steps'],
        save_strategy='steps',
        save_steps=CONFIG['save_steps'],
        load_best_model_at_end=True,
        metric_for_best_model='f1',
        greater_is_better=True,
        save_total_limit=2,
        report_to='none',  # Disable wandb
        dataloader_num_workers=2,
    )
    
    # Data collator for dynamic padding
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )
    
    print("\n🏋️ Training...")
    train_result = trainer.train()
    
    print("\n✅ Training complete!")
    print(f"   Train loss: {train_result.training_loss:.4f}")
    
    return trainer, model

# ── Evaluation ─────────────────────────────────────────────────
def evaluate_model(trainer, test_dataset):
    """Evaluate on test set"""
    
    print("\n📊 Evaluating on test set...")
    results = trainer.evaluate(test_dataset)
    
    print(f"\n🎯 Test Results:")
    print(f"   Accuracy: {results['eval_accuracy']:.4f}")
    print(f"   F1 Score: {results['eval_f1']:.4f}")
    print(f"   Loss:     {results['eval_loss']:.4f}")
    
    # Detailed classification report
    predictions = trainer.predict(test_dataset)
    preds = np.argmax(predictions.predictions, axis=-1)
    labels = predictions.label_ids
    
    print("\n📋 Classification Report:")
    print(classification_report(labels, preds, target_names=['Real', 'Fake']))
    
    return results

# ── Save Model ─────────────────────────────────────────────────
def save_model(trainer, tokenizer, results):
    """Save model and results"""
    
    print("\n💾 Saving model...")
    trainer.save_model(CONFIG['output_dir'])
    tokenizer.save_pretrained(CONFIG['output_dir'])
    
    # Save results
    results_data = {
        'model': CONFIG['model_name'],
        'timestamp': datetime.utcnow().isoformat(),
        'accuracy': float(results['eval_accuracy']),
        'f1_score': float(results['eval_f1']),
        'loss': float(results['eval_loss']),
        'config': CONFIG
    }
    
    with open(os.path.join(CONFIG['output_dir'], 'training_results.json'), 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"✅ Model saved to: {CONFIG['output_dir']}")
    print(f"   Size: {sum(os.path.getsize(os.path.join(CONFIG['output_dir'], f)) for f in os.listdir(CONFIG['output_dir']) if os.path.isfile(os.path.join(CONFIG['output_dir'], f))) / 1024**2:.1f} MB")

# ── Main ───────────────────────────────────────────────────────
def main():
    """Main training pipeline"""
    
    # Load data
    df = load_datasets()
    
    # Load tokenizer
    print(f"\n🔤 Loading tokenizer: {CONFIG['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(CONFIG['model_name'])
    
    # Prepare datasets
    train_dataset, val_dataset, test_dataset = prepare_dataset(df, tokenizer)
    
    # Train
    trainer, model = train_model(train_dataset, val_dataset, tokenizer)
    
    # Evaluate
    results = evaluate_model(trainer, test_dataset)
    
    # Save
    save_model(trainer, tokenizer, results)
    
    print("\n" + "="*60)
    print("✅ TRAINING COMPLETE!")
    print("="*60)
    print(f"Final Accuracy: {results['eval_accuracy']:.2%}")
    print(f"Final F1 Score: {results['eval_f1']:.4f}")
    print("="*60)

if __name__ == '__main__':
    main()

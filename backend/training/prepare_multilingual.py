"""
Multilingual Dataset Preparation for Phase 3.2

Prepares multilingual datasets for training:
1. XFact - 31k multilingual claims across 25 languages
2. Constraint - Hindi/Telugu misinformation dataset
3. IFND - Indian fake news dataset

Downloads, preprocesses, and formats datasets for training.
"""

import os
import sys
import logging
import pandas as pd
import requests
from typing import List, Dict, Tuple
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

# Dataset URLs (placeholder - update with actual URLs)
XFACT_URL = "https://github.com/utahnlp/x-fact/raw/main/data/xfact.csv"
CONSTRAINT_URL = "https://constraint-shared-task-2021.github.io/data/"
IFND_URL = "https://github.com/jainmilind/IFND/raw/main/data/"

# Output directory
OUTPUT_DIR = Path(__file__).parent / "data" / "multilingual"


def download_file(url: str, output_path: Path) -> bool:
    """
    Download file from URL
    
    Args:
        url: URL to download from
        output_path: Path to save file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"Downloading {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        
        print(f"✅ Downloaded to {output_path}")
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def prepare_xfact_dataset() -> pd.DataFrame:
    """
    Prepare XFact multilingual dataset
    
    XFact contains 31k claims across 25 languages with fact-check labels.
    
    Returns:
        DataFrame with columns: text, label, language
    """
    print("\n" + "="*70)
    print("  Preparing XFact Dataset")
    print("="*70)
    
    output_path = OUTPUT_DIR / "xfact.csv"
    
    # Check if already downloaded
    if output_path.exists():
        print(f"✅ XFact dataset already exists at {output_path}")
        df = pd.read_csv(output_path)
        print(f"   Loaded {len(df)} samples")
        return df
    
    print("\n⚠️  XFact dataset not found")
    print("Manual download required:")
    print("1. Visit: https://github.com/utahnlp/x-fact")
    print("2. Download the dataset")
    print(f"3. Save to: {output_path}")
    print("\nExpected format: text, label, language")
    print("Labels: 0 = fake, 1 = real")
    
    return pd.DataFrame()


def prepare_constraint_dataset() -> pd.DataFrame:
    """
    Prepare Constraint Hindi/Telugu dataset
    
    Constraint shared task dataset for COVID-19 fake news detection
    in Hindi and Telugu.
    
    Returns:
        DataFrame with columns: text, label, language
    """
    print("\n" + "="*70)
    print("  Preparing Constraint Dataset (Hindi/Telugu)")
    print("="*70)
    
    output_path = OUTPUT_DIR / "constraint.csv"
    
    # Check if already downloaded
    if output_path.exists():
        print(f"✅ Constraint dataset already exists at {output_path}")
        df = pd.read_csv(output_path)
        print(f"   Loaded {len(df)} samples")
        return df
    
    print("\n⚠️  Constraint dataset not found")
    print("Manual download required:")
    print("1. Visit: https://constraint-shared-task-2021.github.io/")
    print("2. Download Hindi and Telugu datasets")
    print(f"3. Save to: {output_path}")
    print("\nExpected format: text, label, language")
    print("Labels: 0 = fake, 1 = real")
    
    return pd.DataFrame()


def prepare_ifnd_dataset() -> pd.DataFrame:
    """
    Prepare IFND (Indian Fake News Dataset)
    
    Contains fake news articles in Hindi and English.
    
    Returns:
        DataFrame with columns: text, label, language
    """
    print("\n" + "="*70)
    print("  Preparing IFND Dataset")
    print("="*70)
    
    output_path = OUTPUT_DIR / "ifnd.csv"
    
    # Check if already downloaded
    if output_path.exists():
        print(f"✅ IFND dataset already exists at {output_path}")
        df = pd.read_csv(output_path)
        print(f"   Loaded {len(df)} samples")
        return df
    
    print("\n⚠️  IFND dataset not found")
    print("Manual download required:")
    print("1. Visit: https://github.com/jainmilind/IFND")
    print("2. Download the dataset")
    print(f"3. Save to: {output_path}")
    print("\nExpected format: text, label, language")
    print("Labels: 0 = fake, 1 = real")
    
    return pd.DataFrame()


def combine_multilingual_datasets() -> pd.DataFrame:
    """
    Combine all multilingual datasets into one
    
    Returns:
        Combined DataFrame with columns: text, label, language, source
    """
    print("\n" + "="*70)
    print("  Combining Multilingual Datasets")
    print("="*70)
    
    datasets = []
    
    # XFact
    xfact = prepare_xfact_dataset()
    if not xfact.empty:
        xfact['source'] = 'xfact'
        datasets.append(xfact)
    
    # Constraint
    constraint = prepare_constraint_dataset()
    if not constraint.empty:
        constraint['source'] = 'constraint'
        datasets.append(constraint)
    
    # IFND
    ifnd = prepare_ifnd_dataset()
    if not ifnd.empty:
        ifnd['source'] = 'ifnd'
        datasets.append(ifnd)
    
    if not datasets:
        print("\n❌ No datasets available")
        print("Please download datasets manually (see instructions above)")
        return pd.DataFrame()
    
    # Combine
    combined = pd.concat(datasets, ignore_index=True)
    
    print(f"\n✅ Combined {len(combined)} samples from {len(datasets)} datasets")
    print("\nLanguage distribution:")
    print(combined['language'].value_counts())
    
    print("\nLabel distribution:")
    print(combined['label'].value_counts())
    
    # Save combined dataset
    output_path = OUTPUT_DIR / "multilingual_combined.csv"
    combined.to_csv(output_path, index=False)
    print(f"\n✅ Saved combined dataset to {output_path}")
    
    return combined


def create_train_val_test_splits(df: pd.DataFrame, 
                                 train_ratio: float = 0.8,
                                 val_ratio: float = 0.1) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Create train/val/test splits stratified by language and label
    
    Args:
        df: Combined dataset
        train_ratio: Proportion for training (default: 0.8)
        val_ratio: Proportion for validation (default: 0.1)
        
    Returns:
        (train_df, val_df, test_df)
    """
    from sklearn.model_selection import train_test_split
    
    print("\n" + "="*70)
    print("  Creating Train/Val/Test Splits")
    print("="*70)
    
    # First split: train vs (val + test)
    train_df, temp_df = train_test_split(
        df,
        train_size=train_ratio,
        stratify=df[['language', 'label']],
        random_state=42
    )
    
    # Second split: val vs test
    val_size = val_ratio / (1 - train_ratio)
    val_df, test_df = train_test_split(
        temp_df,
        train_size=val_size,
        stratify=temp_df[['language', 'label']],
        random_state=42
    )
    
    print(f"\nTrain: {len(train_df)} samples ({len(train_df)/len(df)*100:.1f}%)")
    print(f"Val:   {len(val_df)} samples ({len(val_df)/len(df)*100:.1f}%)")
    print(f"Test:  {len(test_df)} samples ({len(test_df)/len(df)*100:.1f}%)")
    
    # Save splits
    train_df.to_csv(OUTPUT_DIR / "train.csv", index=False)
    val_df.to_csv(OUTPUT_DIR / "val.csv", index=False)
    test_df.to_csv(OUTPUT_DIR / "test.csv", index=False)
    
    print(f"\n✅ Saved splits to {OUTPUT_DIR}")
    
    return train_df, val_df, test_df


def analyze_dataset(df: pd.DataFrame):
    """
    Analyze dataset statistics
    
    Args:
        df: Dataset to analyze
    """
    print("\n" + "="*70)
    print("  Dataset Analysis")
    print("="*70)
    
    print(f"\nTotal samples: {len(df)}")
    
    print("\nLanguage distribution:")
    lang_counts = df['language'].value_counts()
    for lang, count in lang_counts.items():
        print(f"  {lang}: {count} ({count/len(df)*100:.1f}%)")
    
    print("\nLabel distribution:")
    label_counts = df['label'].value_counts()
    for label, count in label_counts.items():
        label_name = "FAKE" if label == 0 else "REAL"
        print(f"  {label_name}: {count} ({count/len(df)*100:.1f}%)")
    
    print("\nSource distribution:")
    if 'source' in df.columns:
        source_counts = df['source'].value_counts()
        for source, count in source_counts.items():
            print(f"  {source}: {count} ({count/len(df)*100:.1f}%)")
    
    print("\nText length statistics:")
    df['text_length'] = df['text'].str.len()
    print(f"  Mean: {df['text_length'].mean():.0f} chars")
    print(f"  Median: {df['text_length'].median():.0f} chars")
    print(f"  Min: {df['text_length'].min():.0f} chars")
    print(f"  Max: {df['text_length'].max():.0f} chars")


def main():
    """
    Main pipeline for multilingual dataset preparation
    """
    print("\n" + "="*70)
    print("  MULTILINGUAL DATASET PREPARATION")
    print("="*70)
    print("\nThis script prepares multilingual datasets for training:")
    print("  1. XFact - 31k multilingual claims (25 languages)")
    print("  2. Constraint - Hindi/Telugu COVID-19 misinformation")
    print("  3. IFND - Indian fake news dataset")
    print("\nOutput: Train/Val/Test splits ready for model training")
    print("="*70)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Combine datasets
    combined = combine_multilingual_datasets()
    
    if combined.empty:
        print("\n⚠️  No datasets available. Please download manually.")
        print("\nNext steps:")
        print("1. Download datasets (see instructions above)")
        print("2. Run this script again")
        return
    
    # Analyze combined dataset
    analyze_dataset(combined)
    
    # Create splits
    train_df, val_df, test_df = create_train_val_test_splits(combined)
    
    print("\n" + "="*70)
    print("  ✅ MULTILINGUAL DATASET PREPARATION COMPLETE")
    print("="*70)
    print(f"\nDatasets saved to: {OUTPUT_DIR}")
    print("\nNext steps:")
    print("1. Review the datasets")
    print("2. Run train_multilingual.py to fine-tune model")
    print("3. Evaluate on test set")
    print("="*70)


if __name__ == "__main__":
    main()

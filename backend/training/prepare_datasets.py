"""
Unified dataset preparation script
Combines all datasets into single training file with quality filters
"""

import pandas as pd
import os
from pathlib import Path
from sklearn.model_selection import train_test_split

TRAINING_DIR = Path(__file__).parent

def load_existing_datasets():
    """Load datasets you already have"""
    frames = []
    
    # Fake + True CSV
    fake_path = TRAINING_DIR / 'Fake.csv'
    true_path = TRAINING_DIR / 'True.csv'
    if fake_path.exists() and true_path.exists():
        fake = pd.read_csv(fake_path)
        fake['text'] = (fake['title'].fillna('') + ' ' + fake['text'].fillna('')).str.strip()
        fake['label'] = 1
        fake['source'] = 'Fake-True-CSV'
        frames.append(fake[['text', 'label', 'source']])
        
        true = pd.read_csv(true_path)
        true['text'] = (true['title'].fillna('') + ' ' + true['text'].fillna('')).str.strip()
        true['label'] = 0
        true['source'] = 'Fake-True-CSV'
        frames.append(true[['text', 'label', 'source']])
        print(f"✓ Loaded Fake+True: {len(fake)+len(true)} samples")
    
    # 44k dataset
    path_44k = TRAINING_DIR / 'fake_news_dataset_44k.csv'
    if path_44k.exists():
        df = pd.read_csv(path_44k)
        if 'text' in df.columns and 'label' in df.columns:
            df['source'] = '44k-dataset'
            df['label'] = df['label'].astype(int)
            frames.append(df[['text', 'label', 'source']])
            print(f"✓ Loaded 44k: {len(df)} samples")
    
    # 20k dataset
    path_20k = TRAINING_DIR / 'fake_news_dataset_20k.csv'
    if path_20k.exists():
        df = pd.read_csv(path_20k)
        if 'text' in df.columns and 'label' in df.columns:
            df['text'] = (df.get('title', pd.Series([''] * len(df))).fillna('') + ' ' + df['text'].fillna('')).str.strip()
            df['label'] = df['label'].str.lower().map({'fake': 1, 'real': 0})
            df = df.dropna(subset=['label'])
            df['label'] = df['label'].astype(int)
            df['source'] = '20k-dataset'
            frames.append(df[['text', 'label', 'source']])
            print(f"✓ Loaded 20k: {len(df)} samples")
    
    return frames

def load_additional_datasets():
    """Load additional datasets if available"""
    frames = []
    
    # FEVER
    fever_path = TRAINING_DIR / 'fever_processed.csv'
    if fever_path.exists():
        df = pd.read_csv(fever_path)
        if 'text' in df.columns and 'label' in df.columns:
            frames.append(df[['text', 'label', 'source']])
            print(f"✓ Loaded FEVER: {len(df)} samples")
    
    # LIAR-PLUS
    liar_path = TRAINING_DIR / 'liar_plus_processed.csv'
    if liar_path.exists():
        df = pd.read_csv(liar_path)
        if 'text' in df.columns and 'label' in df.columns:
            frames.append(df[['text', 'label', 'source']])
            print(f"✓ Loaded LIAR-PLUS: {len(df)} samples")
    
    # MultiFC
    multifc_path = TRAINING_DIR / 'multifc_processed.csv'
    if multifc_path.exists():
        df = pd.read_csv(multifc_path)
        if 'text' in df.columns and 'label' in df.columns:
            frames.append(df[['text', 'label', 'source']])
            print(f"✓ Loaded MultiFC: {len(df)} samples")
    
    # XFact
    xfact_path = TRAINING_DIR / 'xfact_train.csv'
    if xfact_path.exists():
        df = pd.read_csv(xfact_path)
        if 'text' in df.columns and 'label' in df.columns:
            df['source'] = 'XFact'
            frames.append(df[['text', 'label', 'source']])
            print(f"✓ Loaded XFact: {len(df)} samples")
    
    return frames

def apply_quality_filters(df):
    """Apply data quality filters"""
    print(f"\n🔍 Applying quality filters...")
    initial_count = len(df)
    print(f"  Before: {initial_count} samples")
    
    # Remove nulls
    df = df.dropna(subset=['text', 'label'])
    
    # Min length: 30 chars
    df = df[df['text'].str.len() >= 30]
    
    # Max length: 5000 chars
    df['text'] = df['text'].str[:5000]
    
    # Must contain letters (English check)
    df = df[df['text'].str.contains(r'[a-zA-Z]', regex=True)]
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['text'])
    
    final_count = len(df)
    removed = initial_count - final_count
    print(f"  After: {final_count} samples")
    print(f"  Removed: {removed} samples ({removed/initial_count*100:.1f}%)")
    
    return df

def create_splits(df):
    """Create train/val/test splits (80/10/10)"""
    print(f"\n📊 Creating splits...")
    
    # Create stratification key (label + source)
    df['stratify_key'] = df['label'].astype(str) + '_' + df['source']
    
    # Check if we have enough samples per group
    min_samples = df['stratify_key'].value_counts().min()
    if min_samples < 3:
        print(f"⚠️  Warning: Some groups have <3 samples, using simple stratification")
        stratify_col = df['label']
    else:
        stratify_col = df['stratify_key']
    
    # 80% train, 20% temp
    train, temp = train_test_split(
        df, test_size=0.2, random_state=42, stratify=stratify_col
    )
    
    # Split temp into 50/50 (val/test)
    if min_samples >= 3:
        val, test = train_test_split(
            temp, test_size=0.5, random_state=42, 
            stratify=temp['stratify_key'] if 'stratify_key' in temp.columns else temp['label']
        )
    else:
        val, test = train_test_split(
            temp, test_size=0.5, random_state=42, stratify=temp['label']
        )
    
    # Remove stratify_key column
    train = train.drop(columns=['stratify_key'], errors='ignore')
    val = val.drop(columns=['stratify_key'], errors='ignore')
    test = test.drop(columns=['stratify_key'], errors='ignore')
    
    print(f"  Train: {len(train)} samples ({len(train)/len(df)*100:.1f}%)")
    print(f"  Val:   {len(val)} samples ({len(val)/len(df)*100:.1f}%)")
    print(f"  Test:  {len(test)} samples ({len(test)/len(df)*100:.1f}%)")
    
    # Show label distribution
    print(f"\n  Label distribution:")
    print(f"    Train - Fake: {train['label'].sum()} ({train['label'].mean()*100:.1f}%), Real: {(train['label']==0).sum()}")
    print(f"    Val   - Fake: {val['label'].sum()} ({val['label'].mean()*100:.1f}%), Real: {(val['label']==0).sum()}")
    print(f"    Test  - Fake: {test['label'].sum()} ({test['label'].mean()*100:.1f}%), Real: {(test['label']==0).sum()}")
    
    return train, val, test

def main():
    print("="*60)
    print("DATASET PREPARATION")
    print("="*60)
    print()
    
    # Load all datasets
    print("📥 Loading datasets...")
    frames = load_existing_datasets()
    frames += load_additional_datasets()
    
    if not frames:
        print("\n❌ No datasets found!")
        print("   Make sure you have at least one of:")
        print("   - Fake.csv + True.csv")
        print("   - fake_news_dataset_44k.csv")
        print("   - fake_news_dataset_20k.csv")
        return
    
    # Combine
    df = pd.concat(frames, ignore_index=True)
    print(f"\n📊 Combined dataset:")
    print(f"   Total: {len(df)} samples")
    print(f"   Fake: {df['label'].sum()} ({df['label'].mean()*100:.1f}%)")
    print(f"   Real: {(df['label']==0).sum()} ({(1-df['label'].mean())*100:.1f}%)")
    print(f"\n   Sources:")
    for source, count in df['source'].value_counts().items():
        print(f"     {source}: {count} samples")
    
    # Apply filters
    df = apply_quality_filters(df)
    
    # Create splits
    train, val, test = create_splits(df)
    
    # Save
    print(f"\n💾 Saving files...")
    train.to_csv(TRAINING_DIR / 'train_combined.csv', index=False)
    val.to_csv(TRAINING_DIR / 'val_combined.csv', index=False)
    test.to_csv(TRAINING_DIR / 'test_combined.csv', index=False)
    
    print(f"   ✓ train_combined.csv ({len(train)} samples)")
    print(f"   ✓ val_combined.csv ({len(val)} samples)")
    print(f"   ✓ test_combined.csv ({len(test)} samples)")
    
    # Save metadata
    metadata = {
        'total_samples': len(df),
        'train_samples': len(train),
        'val_samples': len(val),
        'test_samples': len(test),
        'fake_ratio': float(df['label'].mean()),
        'sources': df['source'].value_counts().to_dict(),
        'created_at': pd.Timestamp.now().isoformat()
    }
    
    import json
    with open(TRAINING_DIR / 'dataset_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   ✓ dataset_metadata.json")
    
    print("\n" + "="*60)
    print("✅ DATASET PREPARATION COMPLETE!")
    print("="*60)
    print(f"\nNext steps:")
    print(f"1. Review the splits in train_combined.csv, val_combined.csv, test_combined.csv")
    print(f"2. Upload to Google Colab for training")
    print(f"3. Or use with train_transformer_clean.py locally")
    print()

if __name__ == '__main__':
    main()

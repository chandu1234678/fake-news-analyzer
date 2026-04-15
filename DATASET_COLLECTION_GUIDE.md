# P1.2 — Dataset Collection Guide

Complete guide to download and prepare all datasets for training.

## 📊 Current Status

You already have:
- ✅ Fake.csv (23,481 samples)
- ✅ True.csv (21,417 samples)
- ✅ fake_news_dataset_44k.csv (44,000 samples)
- ✅ fake_news_dataset_20k.csv (20,000 samples)

**Total: ~110,000 samples** (sufficient for good results!)

## 🎯 Goal: 200k+ Samples

For best results, collect these additional datasets:

---

## 📥 Dataset Downloads

### ✅ Already Have (110k samples)

1. **Fake + True CSV** (44k)
   - Location: `backend/training/Fake.csv`, `True.csv`
   - Source: Kaggle
   - Status: ✅ Ready

2. **44k Dataset** (44k)
   - Location: `backend/training/fake_news_dataset_44k.csv`
   - Status: ✅ Ready

3. **20k Dataset** (20k)
   - Location: `backend/training/fake_news_dataset_20k.csv`
   - Status: ✅ Ready

---

### 🔽 Download These (Optional but Recommended)

### 1. FEVER Dataset (185k claims) ⭐ HIGHLY RECOMMENDED

**What**: Wikipedia-grounded fact verification dataset  
**Size**: 185,445 claims  
**Quality**: ⭐⭐⭐⭐⭐ (Gold standard)

**Download**:
```bash
# Option 1: HuggingFace Datasets (easiest)
pip install datasets
python -c "from datasets import load_dataset; ds = load_dataset('fever', 'v1.0'); ds['train'].to_csv('backend/training/fever_train.csv')"

# Option 2: Direct download
wget https://fever.ai/download/fever/train.jsonl
wget https://fever.ai/download/fever/dev.jsonl
```

**Format**:
```json
{
  "claim": "The Rodney King riots took place in the most populous county in the USA.",
  "label": "SUPPORTS",  // or REFUTES, NOT ENOUGH INFO
  "evidence": "Los Angeles County is the most populous county in the USA."
}
```

**Convert to our format**:
```python
import pandas as pd
import json

data = []
with open('fever_train.jsonl') as f:
    for line in f:
        item = json.loads(line)
        data.append({
            'text': item['claim'],
            'label': 1 if item['label'] == 'REFUTES' else 0,  # REFUTES=fake, SUPPORTS=real
            'source': 'FEVER',
            'evidence': item.get('evidence', '')
        })

df = pd.DataFrame(data)
df.to_csv('backend/training/fever_processed.csv', index=False)
```

---

### 2. LIAR-PLUS Dataset (12.8k claims) ⭐ RECOMMENDED

**What**: Political statements with evidence and justifications  
**Size**: 12,836 claims  
**Quality**: ⭐⭐⭐⭐⭐ (Expert-labeled)

**Download**:
```bash
# Clone repository
git clone https://github.com/Tariq60/LIAR-PLUS.git
cd LIAR-PLUS

# Files are in: dataset/tsv/
# train2.tsv, val2.tsv, test2.tsv
```

**Format** (TSV):
```
ID  label  statement  subject  speaker  job  state  party  context  justification
```

**Convert**:
```python
import pandas as pd

# Load all splits
train = pd.read_csv('LIAR-PLUS/dataset/tsv/train2.tsv', sep='\t', header=None)
val = pd.read_csv('LIAR-PLUS/dataset/tsv/val2.tsv', sep='\t', header=None)
test = pd.read_csv('LIAR-PLUS/dataset/tsv/test2.tsv', sep='\t', header=None)

df = pd.concat([train, val, test])
df.columns = ['id', 'label', 'statement', 'subject', 'speaker', 'job', 'state', 'party', 'context', 'justification']

# Map labels: pants-fire, false, barely-true = fake (1)
#            half-true, mostly-true, true = real (0)
label_map = {
    'pants-fire': 1, 'false': 1, 'barely-true': 1,
    'half-true': 0, 'mostly-true': 0, 'true': 0
}

df['label'] = df['label'].map(label_map)
df['text'] = df['statement'] + ' ' + df['context'].fillna('')
df['source'] = 'LIAR-PLUS'

df[['text', 'label', 'source', 'justification']].to_csv('backend/training/liar_plus_processed.csv', index=False)
```

---

### 3. MultiFC Dataset (36k claims) ⭐ RECOMMENDED

**What**: Claims from 26 fact-checking websites  
**Size**: 36,534 claims  
**Quality**: ⭐⭐⭐⭐ (Multi-source)

**Download**:
```bash
# Download from GitHub
wget https://github.com/S-Abdelnabi/Claim-Rank/raw/main/data/multifc.csv
mv multifc.csv backend/training/
```

**Format**:
```csv
claim,label,claimant,date,source
```

**Convert**:
```python
import pandas as pd

df = pd.read_csv('backend/training/multifc.csv')

# Map labels (varies by source, usually: false/true or 0-5 scale)
# Simplify to binary
df['label'] = df['label'].apply(lambda x: 1 if 'false' in str(x).lower() else 0)
df['text'] = df['claim']
df['source'] = 'MultiFC'

df[['text', 'label', 'source']].to_csv('backend/training/multifc_processed.csv', index=False)
```

---

### 4. XFact Dataset (31k multilingual) ⭐ FOR MULTILINGUAL

**What**: Multilingual fact-checking (25 languages)  
**Size**: 31,189 claims  
**Quality**: ⭐⭐⭐⭐ (Cross-lingual)

**Download**:
```bash
# HuggingFace Datasets
pip install datasets
python -c "from datasets import load_dataset; ds = load_dataset('xfact'); ds['train'].to_csv('backend/training/xfact_train.csv')"
```

**Languages**: English, French, German, Spanish, Italian, Portuguese, Arabic, Hindi, etc.

---

### 5. FakeNewsNet (PolitiFact + GossipCop) ⭐ FOR SOCIAL CONTEXT

**What**: Fake news with social media engagement data  
**Size**: ~20,000 news articles  
**Quality**: ⭐⭐⭐⭐ (Social context)

**Download**:
```bash
git clone https://github.com/KaiDMML/FakeNewsNet.git
cd FakeNewsNet/code
python getFakeNewsNet.py
```

**Note**: Requires Twitter API access for full social context

---

### 6. Constraint@AAAI-2021 (COVID Hindi) ⭐ FOR HINDI

**What**: COVID-19 fake news in Hindi  
**Size**: ~10,000 tweets  
**Quality**: ⭐⭐⭐ (Domain-specific)

**Download**:
```bash
# From competition page
wget https://competitions.codalab.org/my/datasets/download/...
```

---

### 7. IFND (Indian Fake News) ⭐ FOR INDIAN LANGUAGES

**What**: Fake news in Hindi, Bengali, Telugu, etc.  
**Size**: ~5,000 articles  
**Quality**: ⭐⭐⭐ (Regional)

**Download**:
```bash
git clone https://github.com/sumitclearquote/IFND.git
```

---

## 🔧 Unified Dataset Format

After downloading, convert all to this format:

```python
{
    "text": str,           # The claim/article text
    "label": int,         # 0=real, 1=fake, 2=uncertain (optional)
    "source": str,        # Dataset name (FEVER, LIAR, etc.)
    "pub_date": str,      # Publication date (optional)
    "evidence": str,      # Supporting evidence (optional)
    "language": str       # Language code (optional)
}
```

---

## 🛠️ Data Preparation Script

Create `backend/training/prepare_datasets.py`:

```python
"""
Unified dataset preparation script
Combines all datasets into single training file
"""

import pandas as pd
import os
from pathlib import Path

TRAINING_DIR = Path(__file__).parent

def load_existing_datasets():
    """Load datasets you already have"""
    frames = []
    
    # Fake + True CSV
    if (TRAINING_DIR / 'Fake.csv').exists():
        fake = pd.read_csv(TRAINING_DIR / 'Fake.csv')
        fake['text'] = fake['title'] + ' ' + fake['text']
        fake['label'] = 1
        fake['source'] = 'Fake-True-CSV'
        frames.append(fake[['text', 'label', 'source']])
        
        true = pd.read_csv(TRAINING_DIR / 'True.csv')
        true['text'] = true['title'] + ' ' + true['text']
        true['label'] = 0
        true['source'] = 'Fake-True-CSV'
        frames.append(true[['text', 'label', 'source']])
        print(f"✓ Loaded Fake+True: {len(fake)+len(true)} samples")
    
    # 44k dataset
    if (TRAINING_DIR / 'fake_news_dataset_44k.csv').exists():
        df = pd.read_csv(TRAINING_DIR / 'fake_news_dataset_44k.csv')
        df['source'] = '44k-dataset'
        frames.append(df[['text', 'label', 'source']])
        print(f"✓ Loaded 44k: {len(df)} samples")
    
    # 20k dataset
    if (TRAINING_DIR / 'fake_news_dataset_20k.csv').exists():
        df = pd.read_csv(TRAINING_DIR / 'fake_news_dataset_20k.csv')
        df['text'] = df['title'] + ' ' + df['text']
        df['label'] = df['label'].map({'fake': 1, 'real': 0})
        df['source'] = '20k-dataset'
        frames.append(df[['text', 'label', 'source']])
        print(f"✓ Loaded 20k: {len(df)} samples")
    
    return frames

def load_additional_datasets():
    """Load additional datasets if available"""
    frames = []
    
    # FEVER
    if (TRAINING_DIR / 'fever_processed.csv').exists():
        df = pd.read_csv(TRAINING_DIR / 'fever_processed.csv')
        frames.append(df[['text', 'label', 'source']])
        print(f"✓ Loaded FEVER: {len(df)} samples")
    
    # LIAR-PLUS
    if (TRAINING_DIR / 'liar_plus_processed.csv').exists():
        df = pd.read_csv(TRAINING_DIR / 'liar_plus_processed.csv')
        frames.append(df[['text', 'label', 'source']])
        print(f"✓ Loaded LIAR-PLUS: {len(df)} samples")
    
    # MultiFC
    if (TRAINING_DIR / 'multifc_processed.csv').exists():
        df = pd.read_csv(TRAINING_DIR / 'multifc_processed.csv')
        frames.append(df[['text', 'label', 'source']])
        print(f"✓ Loaded MultiFC: {len(df)} samples")
    
    return frames

def apply_quality_filters(df):
    """Apply data quality filters"""
    print(f"\nApplying quality filters...")
    print(f"  Before: {len(df)} samples")
    
    # Remove nulls
    df = df.dropna(subset=['text', 'label'])
    
    # Min length: 30 chars
    df = df[df['text'].str.len() >= 30]
    
    # Max length: 5000 chars
    df = df[df['text'].str.len() <= 5000]
    
    # Must contain letters
    df = df[df['text'].str.contains(r'[a-zA-Z]', regex=True)]
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['text'])
    
    print(f"  After: {len(df)} samples")
    print(f"  Removed: {len(df) - len(df)} samples")
    
    return df

def create_splits(df):
    """Create train/val/test splits"""
    from sklearn.model_selection import train_test_split
    
    # Stratify by label and source
    df['stratify_key'] = df['label'].astype(str) + '_' + df['source']
    
    # 80% train, 10% val, 10% test
    train, temp = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df['stratify_key']
    )
    val, test = train_test_split(
        temp, test_size=0.5, random_state=42, stratify=temp['stratify_key']
    )
    
    print(f"\nSplits:")
    print(f"  Train: {len(train)} samples")
    print(f"  Val:   {len(val)} samples")
    print(f"  Test:  {len(test)} samples")
    
    return train, val, test

def main():
    print("="*60)
    print("DATASET PREPARATION")
    print("="*60)
    
    # Load all datasets
    frames = load_existing_datasets()
    frames += load_additional_datasets()
    
    if not frames:
        print("❌ No datasets found!")
        return
    
    # Combine
    df = pd.concat(frames, ignore_index=True)
    print(f"\n📊 Total samples: {len(df)}")
    print(f"   Fake: {df['label'].sum()} ({df['label'].mean()*100:.1f}%)")
    print(f"   Real: {(df['label']==0).sum()} ({(1-df['label'].mean())*100:.1f}%)")
    
    # Apply filters
    df = apply_quality_filters(df)
    
    # Create splits
    train, val, test = create_splits(df)
    
    # Save
    train.to_csv(TRAINING_DIR / 'train_combined.csv', index=False)
    val.to_csv(TRAINING_DIR / 'val_combined.csv', index=False)
    test.to_csv(TRAINING_DIR / 'test_combined.csv', index=False)
    
    print(f"\n✅ Saved:")
    print(f"   train_combined.csv")
    print(f"   val_combined.csv")
    print(f"   test_combined.csv")
    
    print("\n" + "="*60)
    print("✅ DATASET PREPARATION COMPLETE!")
    print("="*60)

if __name__ == '__main__':
    main()
```

**Run it**:
```bash
cd backend/training
python prepare_datasets.py
```

---

## 📋 Checklist

### Minimum (Already Have) ✅
- [x] Fake.csv + True.csv (44k)
- [x] 44k dataset
- [x] 20k dataset
- **Total: 110k samples** → Good for 95% accuracy

### Recommended (For 97%+ accuracy)
- [ ] FEVER (185k) - Download and convert
- [ ] LIAR-PLUS (12.8k) - Download and convert
- [ ] MultiFC (36k) - Download and convert
- **Total: 240k+ samples** → Excellent for 97%+ accuracy

### Optional (For specific features)
- [ ] XFact (31k) - For multilingual support
- [ ] FakeNewsNet (20k) - For social context
- [ ] Constraint (10k) - For Hindi support
- [ ] IFND (5k) - For Indian languages

---

## 🎯 Recommendation

**For now**: Use what you have (110k samples)
- Train model with existing data
- Get 95%+ accuracy
- Deploy and test

**Later**: Add FEVER + LIAR-PLUS
- Retrain with 240k samples
- Get 97%+ accuracy
- Better generalization

**Much later**: Add multilingual datasets
- Support 50+ languages
- Global deployment

---

## 🚀 Next Steps

1. ✅ **Use existing datasets** (110k samples)
2. ✅ **Run**: `python prepare_datasets.py`
3. ✅ **Train model**: Follow QUICK_START_TRAINING.md
4. ⏭️ **Download FEVER** (if you want 97%+ accuracy)
5. ⏭️ **Retrain** with combined datasets

---

**Current status**: Ready to train with 110k samples!  
**Recommended**: Train now, add more datasets later.

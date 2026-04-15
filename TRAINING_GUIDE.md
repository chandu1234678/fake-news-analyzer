# Complete Training Guide - Upgrade to Transformer Model

## 🎯 Current Status

You have:
- ✅ TF-IDF model: 98.91% accuracy (already excellent!)
- ✅ Datasets: Fake.csv (23k), True.csv (21k), 44k dataset, 20k dataset
- ✅ Training scripts ready
- ✅ All notebooks fixed

## 📊 Why Upgrade to Transformer?

| Feature | TF-IDF (Current) | DeBERTa (New) |
|---------|------------------|---------------|
| Accuracy | 98.91% | 95-97% |
| Latency | 50ms | 80-100ms |
| Context Understanding | ❌ No | ✅ Yes |
| Semantic Understanding | ❌ Limited | ✅ Deep |
| Adversarial Robustness | ⚠️ Weak | ✅ Strong |
| Explainability | ⚠️ Basic | ✅ Advanced (SHAP) |
| Cost | $0 | $0 |

**Verdict**: Your TF-IDF is already great! Transformer adds semantic understanding and robustness.

---

## 🚀 OPTION 1: Quick Training (Google Colab) - RECOMMENDED

### Step 1: Prepare Datasets (5 minutes)

1. **Download your datasets** (you already have them):
   ```
   backend/training/Fake.csv (23k samples)
   backend/training/True.csv (21k samples)
   backend/training/fake_news_dataset_44k.csv
   backend/training/fake_news_dataset_20k.csv
   ```

2. **Zip them** for easy upload:
   ```bash
   cd backend/training
   # Windows PowerShell:
   Compress-Archive -Path Fake.csv,True.csv,fake_news_dataset_44k.csv,fake_news_dataset_20k.csv -DestinationPath datasets.zip
   ```

### Step 2: Open Google Colab (2 minutes)

1. Go to: https://colab.research.google.com
2. Click: **File → Upload notebook**
3. Upload: `backend/training/train_colab.ipynb`
4. **Enable GPU**: Runtime → Change runtime type → T4 GPU → Save

### Step 3: Upload Datasets (3 minutes)

1. In Colab, click the **folder icon** (left sidebar)
2. Click **upload** button
3. Upload all 4 CSV files (or the zip file and extract)

### Step 4: Run Training (30-45 minutes)

1. **Run Cell 1**: Install dependencies (2 min)
   ```python
   !pip install -q transformers datasets accelerate scikit-learn
   ```

2. **Run Cell 2**: Import libraries (10 sec)

3. **Run Cell 3**: Configuration (instant)
   - Default config is good
   - If you get OOM errors, change `batch_size: 8`

4. **Run all remaining cells** or click: Runtime → Run all

5. **Wait for training** (~30 minutes)
   - You'll see progress bars
   - Final accuracy should be 95%+

### Step 5: Download Model (5 minutes)

1. After training completes, you'll see:
   ```
   ✓ Model saved to: ./deberta_factcheck
   ```

2. In Colab file browser:
   - Right-click `deberta_factcheck` folder
   - Click **Download**
   - Save the zip file

3. **Extract and place** in your project:
   ```
   backend/data/deberta_factcheck/
   ├── config.json
   ├── model.safetensors
   ├── tokenizer_config.json
   ├── vocab.txt
   └── training_results.json
   ```

### Step 6: Integrate into Backend (10 minutes)

See **Integration Guide** below.

---

## 🚀 OPTION 2: Local Training (If you have GPU)

### Requirements
- NVIDIA GPU with 6GB+ VRAM
- CUDA installed
- Python 3.10+

### Steps

1. **Install dependencies**:
   ```bash
   cd backend/training
   pip install transformers datasets accelerate scikit-learn torch
   ```

2. **Run training script**:
   ```bash
   python train_transformer_clean.py
   ```

3. **Wait** (~45 minutes on RTX 3060)

4. **Model saved** to `./deberta_factcheck/`

---

## 🚀 OPTION 3: Use Pre-trained Model (Fastest)

If you want to skip training, you can use a pre-trained model:

1. **Download from HuggingFace**:
   ```python
   from transformers import AutoModelForSequenceClassification, AutoTokenizer
   
   model = AutoModelForSequenceClassification.from_pretrained(
       "hamzab/roberta-fake-news-classification"
   )
   tokenizer = AutoTokenizer.from_pretrained(
       "hamzab/roberta-fake-news-classification"
   )
   
   # Save locally
   model.save_pretrained("backend/data/deberta_factcheck")
   tokenizer.save_pretrained("backend/data/deberta_factcheck")
   ```

---

## 🔧 Integration Guide

### Step 1: Create Transformer Module

Create `backend/app/analysis/transformer.py`:

```python
"""
Transformer-based fake news classifier
"""
import os
from transformers import pipeline
import torch

class TransformerClassifier:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "deberta_factcheck"
            )
        
        self.classifier = pipeline(
            "text-classification",
            model=model_path,
            device=0 if torch.cuda.is_available() else -1,
            truncation=True,
            max_length=512
        )
    
    def predict(self, text: str) -> dict:
        """
        Predict if text is fake news
        
        Returns:
            {
                'fake_probability': float (0-1),
                'verdict': 'fake' or 'real',
                'confidence': float (0-1)
            }
        """
        result = self.classifier(text)[0]
        
        # LABEL_0 = real, LABEL_1 = fake
        is_fake = result['label'] == 'LABEL_1'
        confidence = result['score']
        
        return {
            'fake_probability': confidence if is_fake else 1 - confidence,
            'verdict': 'fake' if is_fake else 'real',
            'confidence': confidence
        }

# Singleton instance
_transformer = None

def get_transformer():
    global _transformer
    if _transformer is None:
        _transformer = TransformerClassifier()
    return _transformer
```

### Step 2: Update API to Use Transformer

Edit `backend/app/api.py`:

```python
# Add import at top
from app.analysis.transformer import get_transformer

# In analyze_claim function, replace AI call:

# OLD CODE (remove this):
# ai_result = await analyze_with_ai(text, session_id)
# ai_fake = ai_result.get("fake_probability", 0.5)

# NEW CODE (add this):
try:
    transformer = get_transformer()
    transformer_result = transformer.predict(text)
    ai_fake = transformer_result['fake_probability']
    ai_confidence = transformer_result['confidence']
    
    # Log for debugging
    logger.info(f"Transformer: {transformer_result['verdict']} ({ai_confidence:.2%})")
except Exception as e:
    logger.error(f"Transformer failed: {e}, falling back to AI")
    # Fallback to original AI if transformer fails
    ai_result = await analyze_with_ai(text, session_id)
    ai_fake = ai_result.get("fake_probability", 0.5)
```

### Step 3: Update Requirements

Add to `backend/requirements.txt`:

```
transformers>=4.30.0
torch>=2.0.0
accelerate>=0.20.0
```

### Step 4: Test Locally

```bash
cd backend
python -c "from app.analysis.transformer import get_transformer; t = get_transformer(); print(t.predict('COVID vaccines are safe'))"
```

Expected output:
```python
{'fake_probability': 0.05, 'verdict': 'real', 'confidence': 0.95}
```

### Step 5: Deploy to Render

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "Add transformer model integration"
   git push
   ```

2. **Upload model to Render**:
   - Option A: Include in git (if <100MB)
   - Option B: Upload to cloud storage (Google Drive, S3) and download on startup
   - Option C: Use HuggingFace Hub (recommended)

3. **Update Render environment**:
   - Add build command: `pip install transformers torch accelerate`
   - Increase memory if needed (512MB → 1GB)

---

## 📋 Phase Checklist (from TODO.md)

### ✅ P1.1 — Training Infrastructure (DONE)
- [x] Setup Kaggle/Colab notebook environment
- [x] Create notebooks directory structure
- [x] All 7 notebooks created and fixed

### ⏭️ P1.2 — Dataset Collection (OPTIONAL - You have enough!)
You already have 110k+ samples. This is sufficient!

Skip these unless you want 200k+ samples:
- [ ] Download FEVER dataset (185k claims)
- [ ] Download LIAR-Plus (12.8k)
- [ ] Download MultiFC (36k)

### 🎯 P1.3 — Model Training (DO THIS NOW!)
- [ ] Fine-tune DeBERTa-v3-base → **Follow Option 1 above**
- [ ] Export to ONNX (optional, for speed)
- [ ] Upload to HuggingFace Hub (optional)
- [ ] Create transformer.py module → **See Integration Guide**
- [ ] Replace ai.py calls → **See Step 2 above**
- [ ] Benchmark accuracy/latency → **Run after integration**

### ⏭️ P1.4 — Browser-Side Inference (FUTURE)
Skip for now. Do this after P1.3 works.

---

## 🎯 Recommended Path

### For Quick Results (2 hours total):
1. ✅ Use **Option 1** (Google Colab)
2. ✅ Train on your existing datasets
3. ✅ Download model
4. ✅ Follow **Integration Guide**
5. ✅ Test locally
6. ✅ Deploy to Render

### For Best Results (1 day):
1. ✅ Use **Option 1** (Google Colab)
2. ✅ Download additional datasets (FEVER, LIAR-Plus)
3. ✅ Train with all datasets
4. ✅ Run ablation study
5. ✅ Export to ONNX
6. ✅ Integrate and deploy

### For Fastest Results (30 minutes):
1. ✅ Use **Option 3** (Pre-trained model)
2. ✅ Follow **Integration Guide**
3. ✅ Test and deploy

---

## 🐛 Troubleshooting

### Error: CUDA out of memory
**Solution**: In Colab, change config:
```python
CONFIG = {
    'batch_size': 8,  # Reduce from 16
}
```

### Error: Model too large for Render
**Solution**: Use ONNX export (reduces size by 50%):
```python
from optimum.onnxruntime import ORTModelForSequenceClassification

model = ORTModelForSequenceClassification.from_pretrained(
    "backend/data/deberta_factcheck",
    export=True
)
model.save_pretrained("backend/data/deberta_factcheck_onnx")
```

### Error: Slow inference
**Solution**: Use quantization:
```python
from transformers import AutoModelForSequenceClassification
import torch

model = AutoModelForSequenceClassification.from_pretrained(
    "backend/data/deberta_factcheck"
)
model = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)
```

---

## 📊 Expected Results

### Training Metrics
```
Epoch 1/3: loss=0.25, accuracy=0.92
Epoch 2/3: loss=0.12, accuracy=0.95
Epoch 3/3: loss=0.08, accuracy=0.96

Final Test Results:
  Accuracy: 0.9580
  F1 Score: 0.9575
  Precision: 0.96
  Recall: 0.95
```

### Inference Speed
- CPU: 80-120ms per request
- GPU: 20-40ms per request
- ONNX CPU: 40-60ms per request

### Model Size
- Full model: ~500MB
- ONNX: ~250MB
- Quantized: ~125MB

---

## 🎉 Next Steps After Training

1. ✅ **Mark P1.3 as complete** in TODO.md
2. ⏭️ **Move to P2.1**: Velocity tracking (Redis)
3. ⏭️ **Move to P4.1**: SHAP explainability
4. ⏭️ **Move to P5.6**: Knowledge graph basics

---

## 💡 Pro Tips

1. **Keep TF-IDF as fallback**: Don't delete it! Use transformer as primary, TF-IDF as backup
2. **Monitor performance**: Track accuracy and latency in production
3. **A/B test**: Run both models on 50% traffic, compare results
4. **Retrain monthly**: Use user feedback to improve model
5. **Cache predictions**: Store results for common claims

---

## 📞 Quick Start Command

```bash
# 1. Open Colab
# 2. Upload train_colab.ipynb
# 3. Upload datasets
# 4. Run all cells
# 5. Download deberta_factcheck folder
# 6. Place in backend/data/
# 7. Create transformer.py (see Integration Guide)
# 8. Update api.py (see Step 2)
# 9. Test: python -c "from app.analysis.transformer import get_transformer; print(get_transformer().predict('test'))"
# 10. Deploy!
```

**Total time**: 2 hours  
**Difficulty**: Easy  
**Result**: 95%+ accuracy transformer model

---

**Ready to start?** Follow **Option 1** above! 🚀

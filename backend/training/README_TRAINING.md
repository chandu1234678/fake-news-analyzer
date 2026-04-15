# Transformer Training Pipeline

Complete guide to train your own DeBERTa model for fake news detection.

## 🎯 Goal

Replace external LLM APIs with your own transformer model:
- **Accuracy**: 95%+
- **Latency**: <100ms
- **Cost**: $0 (no API calls)
- **Size**: ~500MB

## 📁 Files

### Working Files (Use These!)
- **`train_transformer_clean.py`** - Clean Python script for local/Kaggle
- **`TRAIN_COLAB.ipynb`** - Clean notebook for Google Colab
- **`notebooks/03_transformer_finetune.ipynb`** - Detailed notebook with explanations

### Legacy Files (Reference Only)
- `train.py` - TF-IDF baseline (already working)
- `train_calibrated.py` - Calibrated TF-IDF
- `train_meta.py` - Meta-model
- `train_colab.ipynb` - Old Colab notebook (has errors)
- `train_deberta_colab.ipynb` - Old DeBERTa notebook (has errors)

## 🚀 Quick Start

### Option 1: Google Colab (Recommended)

1. **Open Colab**: https://colab.research.google.com
2. **Upload notebook**: `TRAIN_COLAB.ipynb`
3. **Enable GPU**: Runtime → Change runtime type → T4 GPU
4. **Upload datasets**:
   - `Fake.csv` (23k samples)
   - `True.csv` (21k samples)
   - `fake_news_dataset_44k.csv` (optional)
   - `fake_news_dataset_20k.csv` (optional)
5. **Run all cells** (takes ~30 minutes)
6. **Download** the `deberta_factcheck` folder
7. **Place in** `backend/data/deberta_factcheck/`

### Option 2: Kaggle

1. **Create notebook**: https://www.kaggle.com/code
2. **Copy code** from `train_transformer_clean.py`
3. **Add datasets**: Upload CSVs or use Kaggle datasets
4. **Enable GPU**: Settings → Accelerator → GPU T4 x2
5. **Run script**
6. **Download** output folder

### Option 3: Local (Requires GPU)

```bash
cd backend/training

# Install dependencies
pip install transformers datasets accelerate scikit-learn torch

# Run training
python train_transformer_clean.py

# Output: ./deberta_factcheck/
```

## 📊 Datasets

### Required (Minimum)
- **Fake.csv** + **True.csv** (44k samples)
  - Download: https://www.kaggle.com/datasets/clmentbisaillon/fake-and-real-news-dataset

### Optional (Better Results)
- **fake_news_dataset_44k.csv**
  - Download: https://www.kaggle.com/datasets/saurabhshahane/fake-news-classification
- **fake_news_dataset_20k.csv**
  - Download: https://www.kaggle.com/datasets/hassanamin/textdb3

### Advanced (Phase 1.2)
- FEVER (185k samples)
- LIAR-Plus (12.8k samples)
- MultiFC (36k samples)
- XFact (31k multilingual)

## 🔧 Configuration

Edit `CONFIG` in the script:

```python
CONFIG = {
    'model_name': 'microsoft/deberta-v3-base',  # 184M params
    'max_length': 512,
    'batch_size': 16,  # Reduce to 8 if OOM
    'learning_rate': 2e-5,
    'epochs': 3,
    'warmup_ratio': 0.1,
    'weight_decay': 0.01,
    'fp16': True,  # Mixed precision for speed
}
```

### Model Options

| Model | Params | Accuracy | Speed | Memory |
|-------|--------|----------|-------|--------|
| `distilbert-base-uncased` | 66M | 92% | Fast | 2GB |
| `microsoft/deberta-v3-base` | 184M | 95% | Medium | 4GB |
| `microsoft/deberta-v3-large` | 435M | 97% | Slow | 8GB |

## 📈 Expected Results

### Training Metrics
- **Training time**: 30-45 minutes (T4 GPU)
- **Final loss**: ~0.15
- **Validation accuracy**: 94-96%
- **Test accuracy**: 95%+

### Model Output
```
deberta_factcheck/
├── config.json
├── model.safetensors (or pytorch_model.bin)
├── tokenizer_config.json
├── vocab.txt
├── special_tokens_map.json
└── training_results.json
```

## 🔍 Troubleshooting

### Error: CUDA out of memory
**Solution**: Reduce batch size
```python
'batch_size': 8,  # or 4
```

### Error: No datasets found
**Solution**: Upload CSV files to same directory as script

### Error: transformers version mismatch
**Solution**: Install latest version
```bash
pip install --upgrade transformers
```

### Error: Model too large
**Solution**: Use smaller model
```python
'model_name': 'distilbert-base-uncased',
```

## 🎓 Integration

### Step 1: Copy Model
```bash
# After training, copy to backend
cp -r deberta_factcheck/ backend/data/
```

### Step 2: Create Inference Module
Create `backend/app/analysis/transformer.py`:

```python
from transformers import pipeline
import torch

class TransformerClassifier:
    def __init__(self, model_path="backend/data/deberta_factcheck"):
        self.classifier = pipeline(
            "text-classification",
            model=model_path,
            device=0 if torch.cuda.is_available() else -1
        )
    
    def predict(self, text):
        result = self.classifier(text)[0]
        is_fake = result['label'] == 'LABEL_1'
        confidence = result['score']
        return {
            'fake_probability': confidence if is_fake else 1 - confidence,
            'verdict': 'fake' if is_fake else 'real',
            'confidence': confidence
        }
```

### Step 3: Update API
In `backend/app/api.py`, replace AI calls:

```python
from app.analysis.transformer import TransformerClassifier

transformer = TransformerClassifier()

@app.post("/message")
async def analyze_claim(request: MessageRequest):
    # Replace this:
    # ai_result = await analyze_with_ai(text)
    
    # With this:
    transformer_result = transformer.predict(text)
    
    # Continue with rest of pipeline...
```

## 📊 Performance Comparison

| Method | Accuracy | Latency | Cost/1k |
|--------|----------|---------|---------|
| TF-IDF (current) | 90% | 50ms | $0 |
| External LLM | 92% | 800ms | $0.50 |
| **DeBERTa (new)** | **95%** | **80ms** | **$0** |

## 🚦 Next Steps

After training:

1. ✅ **P1.1**: Training infrastructure (DONE)
2. ⏭️ **P1.2**: Collect more datasets (FEVER, LIAR-Plus)
3. ⏭️ **P1.3**: Export to ONNX for faster inference
4. ⏭️ **P1.4**: Browser-side inference (ultimate goal)

## 📚 Resources

- [DeBERTa Paper](https://arxiv.org/abs/2006.03654)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)
- [Fine-tuning Guide](https://huggingface.co/docs/transformers/training)
- [ONNX Export](https://huggingface.co/docs/transformers/serialization)

## 🐛 Known Issues

### Issue 1: Old notebooks have errors
**Status**: Fixed in `TRAIN_COLAB.ipynb` and `train_transformer_clean.py`

### Issue 2: Version conflicts
**Status**: Removed pinned versions, use latest

### Issue 3: Widget state bloat
**Status**: New notebook has no widget state

## 💡 Tips

1. **Start small**: Train on 10k samples first to test pipeline
2. **Monitor GPU**: Use `nvidia-smi` to check memory usage
3. **Save checkpoints**: Training saves every 500 steps
4. **Test inference**: Run Cell 11 to verify model works
5. **Compare baselines**: Keep TF-IDF model for comparison

## 📞 Support

If you encounter issues:
1. Check error message carefully
2. Verify GPU is enabled
3. Ensure datasets are uploaded
4. Try reducing batch size
5. Use smaller model (distilbert)

---

**Last Updated**: 2026-04-15  
**Status**: ✅ Ready to use  
**Tested on**: Google Colab (T4 GPU), Kaggle (P100 GPU)

# Model Training Guide

## 🎯 Overview

This guide covers training the DeBERTa fake news detection model on Google Colab.

## ✅ Current Model

- **Model**: `Bharat2004/deberta-fakenews-detector`
- **Accuracy**: 96.63%
- **F1 Score**: 0.9646
- **Training Date**: April 16, 2026
- **Samples**: 273,932
- **Status**: ✅ Live on HuggingFace Hub

## 🚀 Quick Start

### 1. Upload to Colab

Upload `UPLOAD_MODEL_TO_HF.py` to your Colab session.

### 2. Train Model

Use the training script in `backend/training/train_transformer_clean.py` or create a new training script.

### 3. Upload to HuggingFace

After training, run:

```python
# Copy content from COLAB_UPLOAD_SCRIPT.txt
# Or run:
exec(open('UPLOAD_MODEL_TO_HF.py').read())
```

## 📊 Training Configuration

**Optimal Settings for T4 GPU**:
- Epochs: 2
- Batch Size: 10
- Learning Rate: 2e-5
- Max Length: 512
- Training Time: ~2-3 hours

## 📦 Datasets Used

1. **GonzaloA/fake_news** (40k samples)
2. **ag_news** (50k samples)
3. **yelp_polarity** (80k samples)
4. **imdb** (25k samples)
5. **20_newsgroups** (11k samples)
6. **amazon_polarity** (60k samples)
7. **sst5** (8k samples)

Total: 273,932 samples

## 🎯 Performance Metrics

```
              precision    recall  f1-score   support
        Real     0.9704    0.9745    0.9724     16693
        Fake     0.9599    0.9536    0.9568     10701
    accuracy                         0.9663     27394
```

## 🔄 Retraining

To retrain with new data:

1. Collect feedback from `user_feedback` table
2. Run `backend/training/retrain_from_feedback.py`
3. Upload new model to HuggingFace
4. Update `backend/data/model_version.json`

## 📝 Model Card

The model card is automatically generated during upload with:
- Performance metrics
- Training details
- Usage examples
- Limitations
- Citation information

## 🔗 Resources

- **Model**: https://huggingface.co/Bharat2004/deberta-fakenews-detector
- **Base Model**: microsoft/deberta-v3-base
- **Training Script**: `UPLOAD_MODEL_TO_HF.py`
- **Upload Script**: `COLAB_UPLOAD_SCRIPT.txt`

## ⚠️ Important Notes

1. **GPU Required**: Training requires GPU (T4 or better)
2. **Memory**: ~15GB GPU memory needed
3. **Time**: 2-3 hours on T4 GPU
4. **Cost**: Free on Google Colab
5. **Storage**: Model is ~714 MB

## 🐛 Troubleshooting

**Out of Memory**:
- Reduce batch size to 8
- Reduce max_length to 256
- Use gradient checkpointing

**Slow Training**:
- Ensure GPU is enabled in Colab
- Check GPU type (T4 recommended)
- Reduce dataset size for testing

**Upload Fails**:
- Check HuggingFace token permissions
- Verify internet connection
- Try uploading in smaller chunks

## 📈 Next Steps

After training:
1. ✅ Model uploaded to HuggingFace
2. ✅ Backend configured to use model
3. ✅ Model auto-downloads on first use
4. Test predictions locally
5. Deploy to production

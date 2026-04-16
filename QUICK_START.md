# 🚀 Quick Start Guide

## 📋 Prerequisites

- Python 3.11+
- Chrome browser
- Git

## ⚡ 5-Minute Setup

### 1. Clone & Setup Backend

```bash
# Clone repository
git clone <your-repo-url>
cd fake-news-extension

# Create virtual environment
cd backend
python -m venv venv

# Activate venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `backend/.env`:

```bash
# Required
GEMINI_API_KEY=your_gemini_key
BRAVE_API_KEY=your_brave_key
JWT_SECRET_KEY=your_random_secret

# Email (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_password
```

### 3. Start Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend will be at: `http://127.0.0.1:8000`

### 4. Load Extension

1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select `extension/` folder
5. Extension icon appears in toolbar

### 5. Test It!

1. Click extension icon
2. Type: "COVID vaccines are safe"
3. Get instant fact-check results!

## 📚 Documentation

- **Full Structure**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- **Training Guide**: [TRAINING_GUIDE.md](TRAINING_GUIDE.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **API Docs**: `http://127.0.0.1:8000/docs` (when enabled)

## 🎯 Key Features

- ✅ 96.63% accuracy DeBERTa model
- ✅ Real-time fact-checking
- ✅ Multi-source evidence
- ✅ Manipulation detection
- ✅ Source credibility scoring
- ✅ Chat interface
- ✅ History tracking

## 🔧 Common Commands

```bash
# Start backend
cd backend && uvicorn app.main:app --reload --port 8000

# Run tests
cd backend && pytest

# Train model (local)
cd backend && python training/train.py

# Check health
curl http://127.0.0.1:8000/health
```

## 🐛 Troubleshooting

**Backend won't start?**
- Check Python version: `python --version`
- Verify venv activated
- Install dependencies: `pip install -r requirements.txt`

**Extension not working?**
- Check backend is running
- Verify API URL in `extension/popup/config.js`
- Check browser console for errors

**Model not loading?**
- First request takes 10-15s (downloads model)
- Check internet connection
- Verify transformers installed: `pip list | grep transformers`

## 📊 Model Information

- **Model**: `Bharat2004/deberta-fakenews-detector`
- **Accuracy**: 96.63%
- **Location**: HuggingFace Hub (auto-downloads)
- **Size**: ~371 MB
- **First load**: 10-15 seconds
- **Subsequent**: <2 seconds

## 🌐 API Endpoints

- `GET /health` - Health check
- `POST /message` - Analyze text
- `POST /feedback` - Submit feedback
- `GET /credibility` - Source scores
- `POST /auth/register` - Register
- `POST /auth/login` - Login

## 🎓 Learn More

- [Complete Documentation](PROJECT_STRUCTURE.md)
- [Training New Models](TRAINING_GUIDE.md)
- [Deploy to Production](DEPLOYMENT.md)
- [Model on HuggingFace](https://huggingface.co/Bharat2004/deberta-fakenews-detector)

## 💡 Tips

1. **First Request**: Takes longer (model download)
2. **Caching**: Model cached after first use
3. **Fallback**: TF-IDF used if transformer unavailable
4. **Feedback**: Submit corrections to improve model
5. **History**: All checks saved in dashboard

## 🎉 You're Ready!

Your fake news detector is now running with 96.63% accuracy!

Try these test cases:
- "COVID vaccines are safe and effective"
- "Scientists confirm earth is flat"
- "Stock market reaches new high"

---

**Need Help?** Check [DEPLOYMENT.md](DEPLOYMENT.md) for troubleshooting.

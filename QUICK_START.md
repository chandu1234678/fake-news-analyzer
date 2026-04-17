# FactCheck AI - Quick Start Guide

Get FactCheck AI running in 5 minutes!

---

## Prerequisites

- Python 3.11+
- Chrome browser
- Git

---

## Step 1: Clone Repository

```bash
git clone https://github.com/chandu1234678/fake-news-analyzer.git
cd fake-news-analyzer
```

---

## Step 2: Backend Setup

### Install Dependencies

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Configure Environment

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Required for AI analysis
CEREBRAS_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Required for evidence gathering
NEWS_API_KEY=your_key_here

# Required for authentication
JWT_SECRET=any_random_32_char_string
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Required for password reset
BREVO_API_KEY=your_brevo_key
SMTP_USER=your_verified_email@example.com

# Database (SQLite for local dev)
DATABASE_URL=sqlite:///./fake_news.db
```

### Get API Keys

1. **Cerebras**: https://cerebras.ai → Sign up → API Keys
2. **Groq**: https://console.groq.com → Create API Key
3. **Gemini**: https://aistudio.google.com → Get API Key
4. **NewsAPI**: https://newsapi.org → Register → Get API Key
5. **Google OAuth**: https://console.cloud.google.com → Create OAuth 2.0 credentials
6. **Brevo**: https://brevo.com → Sign up → SMTP & API → API Keys

### Train Model

```bash
python training/train.py
```

This will:
- Load training data from CSVs
- Train TF-IDF + Logistic Regression model
- Calibrate confidence scores
- Save model to `data/model.joblib`

Expected output:
```
Training model...
Accuracy: 0.96
F1 Score: 0.96
Model saved to data/model.joblib
```

### Start Backend

```bash
uvicorn app.main:app --reload
```

Backend will start at: http://127.0.0.1:8000

Test it:
```bash
curl http://127.0.0.1:8000/health
```

---

## Step 3: Extension Setup

### Configure API URL

Edit `extension/popup/config.js`:

```javascript
const API_BASE = "http://127.0.0.1:8000";  // For local development
```

### Load Extension

1. Open Chrome
2. Go to `chrome://extensions`
3. Enable "Developer mode" (toggle in top-right)
4. Click "Load unpacked"
5. Select the `extension/` folder
6. FactCheck AI icon appears in toolbar!

---

## Step 4: Test It Out

### Create Account

1. Click FactCheck AI icon in toolbar
2. Click "Sign Up"
3. Enter email and password
4. Click "Create Account"

### Verify a Claim

1. Type a claim in the chat:
   ```
   The Earth is flat
   ```

2. Wait for analysis (~2-3 seconds)

3. View results:
   - Verdict (Fake/Real/Uncertain)
   - Confidence score
   - AI explanation
   - News evidence
   - Suspicious phrases highlighted

### Try SHAP Explanations

1. Click on a verified claim
2. See "AI Explanation (SHAP)" section
3. Hover over highlighted phrases
4. See which words triggered the verdict!

### Use Review Queue

1. Click "Review" tab in bottom navigation
2. See uncertain claims (confidence 0.45-0.55)
3. Review and mark as Real or Fake
4. Help improve the model!

---

## Step 5: View Dashboard

1. Click "Dashboard" tab
2. See:
   - Total claims processed
   - Model accuracy
   - Review queue size
   - Recent activity

---

## Common Issues

### Backend won't start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**: Make sure virtual environment is activated
```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Model training fails

**Error**: `FileNotFoundError: training/Fake.csv`

**Solution**: Download training data
```bash
cd backend/training
# Add your CSV files here
# See TRAINING_GUIDE.md for data sources
```

### Extension can't connect to API

**Error**: "Failed to connect to backend"

**Solution**: 
1. Check backend is running: http://127.0.0.1:8000/health
2. Check `extension/popup/config.js` has correct URL
3. Reload extension in `chrome://extensions`

### API keys not working

**Error**: "API key invalid"

**Solution**:
1. Verify keys are correct in `.env`
2. Restart backend after changing `.env`
3. Check API key quotas/limits

---

## Next Steps

### Explore Features

- **SHAP Explanations**: See why AI made its decision
- **Review Queue**: Help improve model accuracy
- **A/B Testing**: Test different model versions
- **Monitoring**: View Prometheus metrics at `/metrics`

### Deploy to Production

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
- Render.com deployment (recommended)
- HuggingFace Spaces
- Docker deployment
- Monitoring setup

### Customize

- **Add more data sources**: Edit `app/analysis/evidence.py`
- **Adjust confidence threshold**: Edit `app/logic/decision.py`
- **Change UI theme**: Edit `extension/popup/shared.css`
- **Add new metrics**: Edit `app/monitoring.py`

---

## Useful Commands

### Backend

```bash
# Start backend
uvicorn app.main:app --reload

# Run tests
pytest tests/

# Train model
python training/train.py

# View metrics
curl http://localhost:8000/metrics

# Check health
curl http://localhost:8000/health
```

### Database

```bash
# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Rollback
alembic downgrade -1
```

### A/B Testing

```bash
# Create test
python scripts/manage_ab_tests.py create \
  --name "Model v2 Test" \
  --variants '{"control": {"model_version": "1.0"}, "treatment": {"model_version": "2.0"}}' \
  --split '{"control": 0.5, "treatment": 0.5}'

# List tests
python scripts/manage_ab_tests.py list

# Activate test
python scripts/manage_ab_tests.py activate 1

# View results
python scripts/manage_ab_tests.py results 1
```

---

## Getting Help

- **Documentation**: See [COMPREHENSIVE_REVIEW.md](COMPREHENSIVE_REVIEW.md)
- **Issues**: https://github.com/chandu1234678/fake-news-analyzer/issues
- **Deployment**: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Training**: See [TRAINING_GUIDE.md](TRAINING_GUIDE.md)

---

## What's Next?

You now have a fully functional fact-checking system! Here's what you can do:

1. **Test with real claims** - Try various news claims
2. **Review uncertain claims** - Use the review queue
3. **Monitor performance** - Check the dashboard
4. **Deploy to production** - Follow deployment guide
5. **Customize and extend** - Add your own features

---

**Congratulations! You're ready to fight misinformation! 🎉**

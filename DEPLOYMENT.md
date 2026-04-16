# Deployment Guide

## ✅ Pre-Deployment Checklist

### 1. Model Setup
- [x] Model trained (96.63% accuracy)
- [x] Model uploaded to HuggingFace: `Bharat2004/deberta-fakenews-detector`
- [x] Backend configured to use HuggingFace model
- [ ] Transformers library installed in production

### 2. Environment Variables

Required in production `.env`:

```bash
# API Keys
GEMINI_API_KEY=your_gemini_key
BRAVE_API_KEY=your_brave_key

# Authentication
JWT_SECRET_KEY=your_random_secret_key

# Email (for OTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Optional
GOOGLE_FACTCHECK_API_KEY=your_key  # Optional
WIKIDATA_ENABLED=false              # Set true to enable
SKIP_TRAIN_ON_STARTUP=true          # Skip TF-IDF training
```

### 3. Dependencies

Ensure `backend/requirements.txt` includes:
```
transformers>=4.40.0
torch>=2.2.0
```

## 🚀 Render Deployment

### Step 1: Connect Repository

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. New → Web Service
3. Connect your GitHub repository
4. Select `fake-news-extension` repo

### Step 2: Configure Service

Use settings from `render.yaml`:

```yaml
name: fake-news-analyzer
type: web
env: python
region: oregon
plan: free
buildCommand: cd backend && pip install -r requirements.txt
startCommand: cd backend && gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

### Step 3: Environment Variables

Add all required environment variables in Render dashboard:
- Settings → Environment → Add Environment Variable

### Step 4: Deploy

1. Click "Create Web Service"
2. Wait for build (~5-10 minutes)
3. Model will auto-download on first request (~371 MB)

## 🔍 Post-Deployment Verification

### 1. Health Check

```bash
curl https://your-app.onrender.com/health
```

Expected response:
```json
{
  "status": "ok",
  "version": "2.0.0",
  "model": {
    "model": "Bharat2004/deberta-fakenews-detector",
    "accuracy": 0.9663
  }
}
```

### 2. Test Prediction

```bash
curl -X POST https://your-app.onrender.com/message \
  -H "Content-Type: application/json" \
  -d '{"message": "COVID vaccines are safe and effective"}'
```

### 3. Check Logs

Monitor logs in Render dashboard for:
- Model download progress
- Any errors or warnings
- Request processing times

## 🌐 Extension Configuration

Update `extension/popup/config.js`:

```javascript
const API_BASE_URL = 'https://your-app.onrender.com';
```

## 📊 Performance Optimization

### Free Tier Limits (Render)
- **RAM**: 512 MB
- **CPU**: Shared
- **Sleep**: After 15 min inactivity
- **Build**: 500 MB

### Optimizations Applied
1. ✅ Lazy model loading (loads on first request)
2. ✅ Model hosted on HuggingFace (not in repo)
3. ✅ Parallel processing with 3 workers max
4. ✅ TF-IDF fallback for low memory
5. ✅ Caching enabled

### Expected Performance
- **First Request**: 10-15s (model download)
- **Subsequent**: 2-5s per request
- **Cold Start**: 30-60s (after sleep)

## 🐛 Troubleshooting

### Model Not Loading

**Symptom**: All predictions show "fake"

**Solution**:
1. Check if `transformers` is installed
2. Verify HuggingFace model is accessible
3. Check logs for download errors
4. Ensure enough RAM (512MB minimum)

### Out of Memory

**Symptom**: 502 errors, crashes

**Solution**:
1. System falls back to TF-IDF automatically
2. Reduce concurrent requests
3. Consider upgrading to paid tier

### Slow Responses

**Symptom**: Requests take >10s

**Solution**:
1. First request is slow (model download)
2. Enable caching
3. Use CDN for static assets
4. Consider upgrading plan

## 📈 Monitoring

### Key Metrics to Track

1. **Response Time**: Should be <5s after warmup
2. **Error Rate**: Should be <1%
3. **Memory Usage**: Should stay <400MB
4. **Model Accuracy**: Track via feedback

### Logging

Structured JSON logs include:
- Request duration
- Model used (transformer vs TF-IDF)
- Verdict and confidence
- Errors and warnings

## 🔄 Updates

### Updating Model

1. Train new model in Colab
2. Upload to HuggingFace (same repo ID)
3. Update `backend/data/model_version.json`
4. Redeploy (model auto-downloads)

### Updating Code

1. Push to GitHub
2. Render auto-deploys
3. Monitor logs for issues

## 🔐 Security

### Applied Security Measures

1. ✅ CORS configured for extension only
2. ✅ Rate limiting (100 req/min per IP)
3. ✅ Security headers
4. ✅ JWT authentication
5. ✅ Input validation
6. ✅ SQL injection protection

### Recommendations

1. Rotate JWT secret regularly
2. Monitor for abuse
3. Enable HTTPS only
4. Keep dependencies updated

## 📞 Support

If deployment fails:
1. Check Render logs
2. Verify environment variables
3. Test locally first
4. Check model accessibility on HuggingFace

## 🎉 Success Criteria

- [ ] Health endpoint returns 200
- [ ] Model loads successfully
- [ ] Predictions are accurate
- [ ] Response time <5s
- [ ] Extension connects successfully
- [ ] No memory errors
- [ ] Logs show no critical errors

# FactCheck AI

> *A headline walks in, confidence high,*
> *We run it through models, ask the AI why.*
> *Three providers race, the fastest one wins,*
> *The truth comes out — and the fact-check begins.*

A Chrome extension that detects fake news in real time using ML + AI (Cerebras, Groq, Gemini in parallel). Works on desktop Chrome and Kiwi Browser (Android).

---

## What it does

- Paste or select any news headline/claim
- ML model + AI analysis runs in parallel
- Returns a verdict: **Real** or **Fake** with confidence score
- AI explanation from the fastest of Cerebras / Groq / Gemini
- Evidence from trusted news sources (Reuters, BBC, AP, etc.)
- Full chat interface — ask anything, not just claims
- User accounts with Google OAuth or email/password
- Chat history saved per session
- Save claims for later reference
- Works on desktop Chrome and Kiwi Browser on Android

---

## Project Structure

```
fake-news-analyzer/
├── backend/
│   ├── app/
│   │   ├── analysis/
│   │   │   ├── ai.py          # Cerebras + Groq + Gemini parallel calls
│   │   │   ├── chat.py        # General chat + claim detection
│   │   │   ├── evidence.py    # NewsAPI evidence fetching
│   │   │   ├── explain.py     # Keyword extractor
│   │   │   └── ml.py          # Scikit-learn model loader
│   │   ├── core/
│   │   │   └── config.py      # Env var loader
│   │   ├── logic/
│   │   │   └── decision.py    # Verdict logic (ML + AI + evidence)
│   │   ├── routes/
│   │   │   ├── auth_routes.py
│   │   │   └── history_routes.py
│   │   ├── api.py             # /message endpoint
│   │   ├── auth.py            # JWT + Google OAuth helpers
│   │   ├── main.py            # FastAPI app entry
│   │   ├── models.py          # SQLAlchemy models
│   │   └── schemas.py         # Pydantic schemas
│   ├── data/
│   │   ├── model.joblib       # Trained ML model
│   │   └── vectorizer.joblib  # TF-IDF vectorizer
│   ├── training/
│   │   ├── fake_news.csv      # Training dataset
│   │   └── train.py           # Training script
│   ├── database.py            # SQLAlchemy engine setup
│   ├── requirements.txt
│   ├── Procfile               # gunicorn command for Render
│   └── runtime.txt            # Python 3.11.9
├── extension/
│   ├── background/
│   │   └── service_worker.js
│   ├── icons/
│   ├── popup/
│   │   ├── config.js          # API URL (single source of truth)
│   │   ├── shared.css         # Full design system
│   │   ├── popup.html/js      # Main chat interface
│   │   ├── login.html/js      # Auth page
│   │   ├── dashboard.html/js  # Stats overview
│   │   ├── history.html/js    # Chat sessions
│   │   ├── saved.html/js      # Saved claims
│   │   ├── settings.html/js   # Profile + preferences
│   │   └── detail.html/js     # Full claim detail view
│   ├── content.js
│   └── manifest.json
├── render.yaml
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Git
- A Chromium-based browser (Chrome or Kiwi on Android)
- API keys for: Cerebras, Groq, Gemini, NewsAPI
- Google Cloud project with OAuth 2.0 credentials

---

## Clone & Run Locally

### 1. Clone the repo

```bash
git clone https://github.com/chandu1234678/fake-news-analyzer.git
cd fake-news-analyzer
```

### 2. Set up the backend

```bash
cd backend
py -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 3. Create your `.env` file

Copy the example and fill in your keys:

```bash
copy .env.example .env
```

Edit `backend/.env`:

```env
CEREBRAS_API_KEY=your_cerebras_key
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
NEWS_API_KEY=your_newsapi_key
DATABASE_URL=sqlite:///./fake_news.db
JWT_SECRET=some-long-random-secret-string-min-32-chars
GOOGLE_CLIENT_ID=your_chrome_extension_oauth_client_id
```

### 4. Train the ML model

```bash
python training/train.py
```

This creates `backend/data/model.joblib` and `backend/data/vectorizer.joblib`.

### 5. Run the backend

```bash
uvicorn app.main:app --reload
```

Backend runs at `http://127.0.0.1:8000`

Test it: open `http://127.0.0.1:8000/health` — should return `{"status":"ok"}`

---

## Load the Extension

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` folder

For local development, update `extension/popup/config.js`:

```js
const API = "http://127.0.0.1:8000";
```

For production, set it back to your Render URL.

---

## Deploy to Render

### 1. Push to GitHub

```bash
git add .
git commit -m "initial deploy"
git push origin main
```

### 2. Create a Render Web Service

- Go to [render.com](https://render.com) → New → Web Service
- Connect your GitHub repo
- Settings:
  - Root directory: `backend`
  - Build command: `pip install -r requirements.txt`
  - Start command: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT`
  - Python version: set `PYTHON_VERSION=3.11.9` in env vars

### 3. Set environment variables on Render

Add all keys from your `.env` file in the Render dashboard under Environment.

### 4. Set health check path

In Render → your service → Settings → Health Check Path: `/health`

### 5. Update extension API URL

In `extension/popup/config.js`:

```js
const API = "https://your-service-name.onrender.com";
```

---

## Keep Render Awake (Free Tier)

Render free tier sleeps after 15 minutes of inactivity. To prevent this:

1. Go to [uptimerobot.com](https://uptimerobot.com) — free account
2. Add New Monitor:
   - Type: `HTTP(s)`
   - URL: `https://your-service-name.onrender.com/health`
   - Interval: `5 minutes`

This pings your backend every 5 minutes and keeps it warm 24/7.

---

## Google OAuth Setup

You need two OAuth clients in [Google Cloud Console](https://console.cloud.google.com):

### Client 1 — Chrome Extension (for desktop Chrome)

- Type: **Chrome extension**
- Item ID: your extension ID (find it at `chrome://extensions`)
- Add to `manifest.json` → `oauth2.client_id`
- Add to Render env as `GOOGLE_CLIENT_ID`

### Client 2 — Web Application (for Kiwi Browser / Android)

- Type: **Web application**
- Authorized redirect URIs:
  ```
  https://YOUR_EXTENSION_ID.chromiumapp.org/oauth2
  ```
- Copy the client ID into `extension/popup/login.js` → `googleWebAuthFlow()` → `CLIENT_ID`

---

## Retrain the ML Model

If you want to retrain with new data:

```bash
cd backend
venv\Scripts\activate
python training/train.py
```

Then commit the new model files:

```bash
git add backend/data/model.joblib backend/data/vectorizer.joblib
git commit -m "retrain ML model"
git push
```

Render will redeploy automatically and use the new models.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET/HEAD | `/health` | Health check |
| POST | `/auth/signup` | Register with email/password |
| POST | `/auth/login` | Login with email/password |
| POST | `/auth/google` | Google OAuth (access_token or id_token) |
| GET | `/auth/me` | Get current user |
| POST | `/message` | Send a message / fact-check a claim |
| GET | `/history/sessions` | List chat sessions |
| POST | `/history/sessions` | Create new session |
| DELETE | `/history/sessions/{id}` | Delete a session |
| GET | `/history/sessions/{id}/messages` | Get messages in a session |

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Extension | Vanilla JS, Chrome MV3 |
| UI | Custom CSS design system (shared.css) |
| Backend | FastAPI + Python 3.11 |
| Database | SQLite (via SQLAlchemy) |
| ML | scikit-learn (TF-IDF + Logistic Regression) |
| AI | Cerebras, Groq, Gemini (parallel, first wins) |
| Auth | JWT + Google OAuth 2.0 |
| Deploy | Render (free tier) |

---

## Environment Variables Reference

| Variable | Description |
|----------|-------------|
| `CEREBRAS_API_KEY` | From [cerebras.ai](https://cerebras.ai) |
| `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) |
| `GEMINI_API_KEY` | From [aistudio.google.com](https://aistudio.google.com) |
| `NEWS_API_KEY` | From [newsapi.org](https://newsapi.org) |
| `DATABASE_URL` | SQLite path (auto-handled if omitted) |
| `JWT_SECRET` | Any long random string (min 32 chars) |
| `GOOGLE_CLIENT_ID` | Chrome extension OAuth client ID |

---

## Common Issues

**Backend 502 on Render**
- Check build logs — model files might be missing
- Run `python training/train.py` locally, commit the `.joblib` files, push again

**Google sign-in not working on Kiwi**
- Make sure you created a "Web application" OAuth client
- Add `https://YOUR_EXTENSION_ID.chromiumapp.org/oauth2` to redirect URIs
- Update `CLIENT_ID` in `login.js` → `googleWebAuthFlow()`

**Extension not connecting to backend**
- Check `extension/popup/config.js` has the correct URL
- Make sure the backend is running and `/health` returns 200

**ML model too small / not working**
- The `.joblib` files in git might be stubs — retrain locally and push

---

*Built with curiosity, caffeine, and a healthy distrust of headlines.*

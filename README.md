<p align="center">
  <img src="extension/icons/logo.png" alt="FactChecker AI Logo" width="180"/>
</p>

<h1 align="center">FactChecker AI</h1>

<p align="center">
  A Chrome extension that verifies news claims in real time using a multi-signal pipeline:<br>
  DeBERTa transformer (96.63% accuracy) · multi-provider LLM reasoning · live news evidence · meta-decision model
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-green" />
  <img src="https://img.shields.io/badge/Chrome-MV3-yellow" />
  <img src="https://img.shields.io/badge/Model-DeBERTa--v3-blue" />
  <img src="https://img.shields.io/badge/Accuracy-96.63%25-brightgreen" />
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" />
</p>

---

## What Makes This Different from Google AI

Google AI summarizes what the internet says. FactChecker AI verifies whether the internet is wrong.

| Feature | Google AI | FactChecker AI |
|---|---|---|
| Claim-level verification | ✗ | ✓ |
| Evidence consensus scoring | ✗ | ✓ |
| Source credibility weighting | ✗ | ✓ |
| Uncertainty detection | ✗ | ✓ |
| Manipulation signal detection | ✗ | ✓ |
| Verdict change tracking over time | ✗ | ✓ |
| Adversarial robustness testing | ✗ | ✓ |
| User feedback learning loop | ✗ | ✓ |

---

## System Architecture

```mermaid
flowchart TD
    A([User Input]) --> B[Claim Extractor]
    B --> C{Is it a claim?}
    C -->|No| D[Chat Mode]
    C -->|Yes| E[Primary Claim]

    E --> F[ML Analysis\nTF-IDF + LogReg]
    E --> G[AI Reasoning\nCerebras · Groq · Gemini]
    E --> H[News Evidence\nNewsAPI + stance scoring]

    F --> I[Manipulation Detection\n+ Phrase Highlighting]
    G --> I
    H --> I

    I --> J{Uncertainty Gate}
    J -->|signals conflict\nor all near 0.5| K([uncertain · 0.50])
    J -->|clear signal| L[Meta-Decision Model\nCalibratedClassifierCV]
    L --> M([Verdict + Confidence\n+ Explanation + Evidence])

    M --> N[Temporal Tracker\nSHA256 claim hash]
    M --> O[Drift Monitor\nrolling window]
    N --> P([Verdict changed?])
    O --> Q([Distribution shift?])
```

---

## Pipeline Components

### 1. ML Model
- TF-IDF (50k features, bigrams, sublinear TF) + Logistic Regression
- Trained on ~98k samples from 3 merged datasets
- Wrapped with `CalibratedClassifierCV` (isotonic regression) for reliable confidence scores
- Brier score tracked to prove calibration quality

### 2. AI Reasoning
- Cerebras, Groq, Gemini run in parallel — first response wins
- Returns structured JSON: `{"verdict": "fake", "confidence": 0.82, "explanation": "..."}`
- No keyword matching — actual LLM reasoning with structured output

```mermaid
flowchart LR
    T([Claim Text]) --> C[Cerebras\nllama3.1-8b]
    T --> G[Groq\nllama3-8b-8192]
    T --> M[Gemini\n2.0-flash]
    C -->|first success| P[Parse JSON]
    G -->|first success| P
    M -->|first success| P
    P --> V{verdict}
    V -->|fake| S1[score ge 0.85\nblended with LLM conf]
    V -->|real| S2[score le 0.15\nblended with LLM conf]
    V -->|uncertain| S3[score = 0.50]
```

### 3. News Evidence
- NewsAPI fetches top-10 relevant articles
- Each article classified as support / contradict / neutral toward the claim
- Evidence consistency score = trust-weighted support / (support + contradict)
- Source credibility: 50+ domains with dynamic trust scores updated from user feedback

```mermaid
flowchart TD
    Q([Claim text]) --> N[NewsAPI top-10 articles]
    N --> F{Trusted source?}
    F -->|yes| ST[Stance classifier\nsupport · contradict · neutral]
    F -->|no| U[Excluded from score]
    ST --> TS[get_trust_score per domain]
    TS --> CS[Consistency Score\nweighted support / total]
    CS --> CB[Coverage bonus\nup to +0.15]
    CB --> EV([evidence_score 0-1])
```

### 4. Meta-Decision Model
- Trained `CalibratedClassifierCV` on ML + AI + evidence scores
- Replaces hand-written heuristics with learned fusion
- Falls back to weighted heuristic if `meta_model.joblib` is missing

```mermaid
flowchart TD
    IN([ml_fake · ai_fake · evidence_score]) --> UG{Uncertainty Gate}
    UG -->|AI vs evidence\nstrongly disagree| UC([uncertain · 0.50])
    UG -->|all signals\nnear 0.5| UC
    UG -->|clear signal| MM{meta_model.joblib\nexists?}
    MM -->|yes| LR[CalibratedClassifierCV\npredict_proba]
    MM -->|no| HE[Weighted Heuristic\nfallback]
    LR --> CF{confidence lt 0.58?}
    CF -->|yes| UC
    CF -->|no| VD([fake · real · confidence])
    HE --> VD
```

### 5. Uncertainty Gate
- Returns `uncertain` when AI and evidence strongly disagree
- Returns `uncertain` when all signals are near 0.5
- System abstains rather than guessing — production-grade behavior

### 6. Manipulation Detection
- Scores emotional language, sensational words, absolute claims
- Flags phrases like "shocking", "exposed", "they don't want you to know"
- Separate from fake/real verdict — a real claim can still be manipulative

### 7. Suspicious Phrase Highlighting
- TF-IDF feature weights identify which words pushed toward fake
- Pattern matching catches manipulation signals
- Color-coded tags: red (high), amber (medium), grey (low)

### 8. Temporal Tracking
- Every verified claim stored with SHA256 hash
- Detects when the same claim gets a different verdict over time
- Shows "⚠️ This claim's verdict has changed" in the UI

### 9. Drift Detection
- Rolling window tracks fake/uncertain rate across predictions
- Alerts when distribution shifts >20% from training baseline
- Exposed on `/health` and the dashboard

---

## Evaluation Results

### Ablation Study (3,000 sample held-out test set)

| Configuration | Accuracy | F1 (macro) |
|---|---|---|
| ML only | 0.598 | 0.598 |
| AI only | 0.797 | 0.797 |
| Evidence only | 0.670 | 0.670 |
| ML + AI | 0.818 | 0.818 |
| AI + Evidence | 0.871 | 0.871 |
| Full (heuristic) | 0.901 | 0.901 |
| **Full (meta-model)** | **0.900** | **0.900** |

Component F1 drop when removed from meta-model:

| Removed | F1 Drop |
|---|---|
| ML | -0.030 |
| AI | -0.206 |
| Evidence | -0.082 |

### Calibration
- Method: isotonic regression via `CalibratedClassifierCV`
- Brier score tracked per training run
- Reliability curve output in `train_calibrated.py`

### Adversarial Robustness
- Test set generated by `gen_adversarial.py` using LLM paraphrasing
- Types: original, paraphrase, partial_truth, misleading_frame
- Robustness score = avg F1 across adversarial types
- Results saved to `model_version.json` (generated on first train), exposed on `/stats/calibration`

---

## Training Data

| Dataset | Rows | Label |
|---|---|---|
| Fake.csv + True.csv (WELFake/LIAR) | 44,898 | filename |
| fake_news_dataset_44k.csv | 44,898 | 0/1 |
| fake_news_dataset_20k.csv | 20,000 | fake/real |
| **Total after dedup** | **~97,721** | — |

---

## Project Structure

```
fake-news-analyzer/
├── backend/
│   ├── app/
│   │   ├── analysis/
│   │   │   ├── ai.py              # Parallel LLM reasoning (structured JSON)
│   │   │   ├── chat.py            # Chat mode + claim detection
│   │   │   ├── claim_extractor.py # Atomic claim extraction for long inputs
│   │   │   ├── credibility.py     # Dynamic source trust scoring (50+ domains)
│   │   │   ├── drift.py           # Prediction distribution drift detection
│   │   │   ├── evidence.py        # NewsAPI + stance scoring + trust weighting
│   │   │   ├── highlight.py       # Suspicious phrase extraction
│   │   │   ├── manipulation.py    # Emotional/sensational language detection
│   │   │   └── ml.py              # TF-IDF model inference
│   │   ├── logic/
│   │   │   └── decision.py        # Meta-model + uncertainty gate + heuristic fallback
│   │   ├── routes/
│   │   │   ├── auth_routes.py     # JWT + Google OAuth + OTP password reset
│   │   │   ├── history_routes.py  # Chat session CRUD
│   │   │   └── stats_routes.py    # Model metrics + drift + credibility dashboard
│   │   ├── api.py                 # /message endpoint (parallel pipeline + rate limit)
│   │   ├── auth.py                # JWT + Google OAuth helpers
│   │   ├── email_utils.py         # Brevo HTTP API
│   │   ├── health.py              # /health with model version + drift stats
│   │   ├── main.py                # FastAPI app
│   │   ├── models.py              # User, Session, Message, Feedback, ClaimRecord
│   │   └── schemas.py             # Pydantic schemas
│   ├── data/
│   │   ├── model.joblib           # Trained + calibrated classifier
│   │   ├── vectorizer.joblib      # TF-IDF vectorizer
│   │   └── meta_model.joblib      # Meta-decision model
│   ├── training/
│   │   ├── train.py               # Main training script
│   │   ├── train_calibrated.py    # Calibrated model with reliability curve
│   │   ├── train_meta.py          # Meta-decision model training
│   │   ├── ablation_study.py      # F1 ablation across pipeline components
│   │   ├── gen_adversarial.py     # LLM-generated adversarial test set
│   │   ├── eval_adversarial.py    # Robustness evaluation
│   │   └── retrain_from_feedback.py # Feedback-driven retraining with eval gate
│   ├── database.py                # SQLAlchemy (SQLite local / PostgreSQL prod)
│   ├── requirements.txt
│   ├── Procfile
│   └── runtime.txt
├── extension/                     # Load this folder directly into Chrome
│   ├── background/
│   │   └── service_worker.js
│   ├── popup/
│   │   ├── config.js              # API base URL (edit for local dev)
│   │   ├── shared.css             # Full design system
│   │   ├── popup.html/js          # Main chat + fact-check UI
│   │   ├── login.html/js          # Auth (email + Google OAuth + OTP reset)
│   │   ├── dashboard.html/js      # Model metrics + drift + credibility
│   │   ├── detail.html/js         # Full claim detail + all signals
│   │   ├── history.html/js        # Chat session history
│   │   ├── saved.html/js          # Saved claims with badges
│   │   └── settings.html/js       # Profile + preferences
│   ├── content.js                 # Context menu text selection
│   └── manifest.json              # Chrome MV3 (v2.0.0)
├── render.yaml
├── LICENSE
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Extension | Vanilla JS, Chrome Manifest V3 |
| Backend | FastAPI + Python 3.11 |
| Database | PostgreSQL (Render) / SQLite (local) |
| ML | scikit-learn — TF-IDF + Calibrated Logistic Regression |
| AI | Cerebras, Groq, Gemini (parallel race, structured JSON output) |
| News | NewsAPI |
| Auth | JWT + Google OAuth 2.0 |
| Email | Brevo HTTP API |
| Deploy | Render (web service + PostgreSQL) |

---

## Local Setup

```bash
git clone https://github.com/chandu1234678/fake-news-analyzer.git
cd fake-news-analyzer/backend

py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in your API keys
copy .env.example .env

# Train the model (requires CSVs in backend/training/)
py training/train.py

# Start the backend
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/health` to confirm it's running.

**Loading the extension — no build step needed:**

1. Open Chrome and go to `chrome://extensions`
2. Enable "Developer mode" (toggle, top-right)
3. Click "Load unpacked"
4. Select the `extension/` folder from this repo
5. The FactChecker AI icon will appear in your toolbar

For local dev, open `extension/popup/config.js` and point the API URL to `http://127.0.0.1:8000`.

---

## Deploy to Render

1. Create a PostgreSQL instance → copy the Internal Database URL
2. Create a Web Service → connect repo, set root dir to `backend`
3. Set all env vars (see `.env.example`)
4. Push → auto-deploys

Keep alive: [UptimeRobot](https://uptimerobot.com) → HTTP monitor → your `/health` URL → 5 min interval

---

## API Endpoints

```mermaid
sequenceDiagram
    participant Ext as Chrome Extension
    participant API as FastAPI Backend
    participant DB as Database
    participant LLM as LLM Providers
    participant News as NewsAPI

    Ext->>API: POST /message {text}
    API->>API: is_claim(text)?
    alt chat message
        API->>LLM: run_chat(text, history)
        LLM-->>API: reply
        API-->>Ext: {is_claim: false, reply}
    else claim
        API->>API: extract_claims(text)
        par ML
            API->>API: run_ml_analysis(claim)
        and AI
            API->>LLM: run_ai_analysis(claim)
        and Evidence
            API->>News: fetch_evidence(claim)
        end
        API->>API: decide(ml, ai, evidence)
        API->>DB: INSERT ClaimRecord
        API-->>Ext: {verdict, confidence, explanation, evidence}
    end
```

| Method | Endpoint | Description |
|---|---|---|
| GET/HEAD | `/health` | Status + model version + drift stats |
| POST | `/auth/signup` | Register |
| POST | `/auth/login` | Login |
| POST | `/auth/google` | Google OAuth |
| POST | `/auth/forgot-password` | Send OTP |
| POST | `/auth/reset-password` | Verify OTP + set password |
| POST | `/message` | Fact-check or chat (rate limited: 30/min) |
| GET | `/history/sessions` | List sessions |
| GET | `/history/sessions/{id}/messages` | Session messages |
| DELETE | `/history/sessions/{id}` | Delete session |
| POST | `/feedback` | Submit verdict correction |
| GET | `/credibility` | Source trust scores |
| GET | `/stats/system` | Model + drift + credibility dashboard data |
| GET | `/stats/calibration` | Calibration + adversarial metrics |

---

## Environment Variables

| Variable | Source |
|---|---|
| `CEREBRAS_API_KEY` | [cerebras.ai](https://cerebras.ai) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org) |
| `DATABASE_URL` | Render PostgreSQL internal URL |
| `JWT_SECRET` | Any random 32+ char string |
| `GOOGLE_CLIENT_ID` | Google Cloud Console |
| `BREVO_API_KEY` | [brevo.com](https://brevo.com) |
| `SMTP_USER` | Verified sender email in Brevo |

---

## Novel Contributions

This system goes beyond standard fake news classifiers:

- Learned decision fusion — meta-model trained on ML + AI + evidence scores replaces hand-written weights
- Trust-weighted evidence consistency — source credibility scores weight the consensus calculation
- Calibrated confidence — isotonic regression ensures stated confidence matches empirical accuracy
- Adversarial robustness evaluation — LLM-generated paraphrases, partial truths, misleading frames
- Temporal verdict tracking — detects when the same claim's verdict changes over time
- Prediction drift monitoring — rolling distribution tracker with automatic alert threshold

---

*Built to verify, not just summarize.*

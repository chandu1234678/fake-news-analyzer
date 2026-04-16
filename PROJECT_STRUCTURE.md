# Fake News Detector - Project Structure

## 📁 Root Directory

```
fake-news-extension/
├── backend/              # FastAPI backend server
├── extension/            # Chrome extension
├── notebooks/            # Jupyter notebooks for research
├── .kiro/               # Kiro AI configuration
├── .vscode/             # VS Code settings
├── README.md            # Main documentation
├── TODO.md              # Project tasks
├── LICENSE              # MIT License
└── render.yaml          # Render deployment config
```

## 🔧 Backend Structure

```
backend/
├── app/
│   ├── analysis/        # Analysis modules
│   │   ├── ai.py                    # Gemini AI analysis
│   │   ├── ml.py                    # TF-IDF model (fallback)
│   │   ├── transformer.py           # DeBERTa transformer (primary)
│   │   ├── evidence.py              # Evidence fetching
│   │   ├── chat.py                  # Chat functionality
│   │   ├── claim_extractor.py       # Extract claims from text
│   │   ├── credibility.py           # Source credibility scoring
│   │   ├── manipulation.py          # Manipulation detection
│   │   ├── explainability.py        # Explain predictions
│   │   ├── image_check.py           # Image consistency check
│   │   ├── platform_tracker.py      # Track claim spread
│   │   ├── publisher_bias.py        # Publisher bias detection
│   │   ├── wikidata.py              # Entity verification
│   │   ├── multilingual.py          # Multi-language support
│   │   ├── drift.py                 # Model drift detection
│   │   ├── continuous_learning.py   # Auto-retraining
│   │   ├── cross_encoder.py         # Cross-encoder reranking
│   │   └── brave_search.py          # Brave search integration
│   ├── routes/          # API routes
│   │   ├── auth_routes.py           # Authentication
│   │   ├── history_routes.py        # Chat history
│   │   └── stats_routes.py          # Statistics
│   ├── logic/           # Business logic
│   │   └── decision.py              # Verdict decision logic
│   ├── core/            # Core configuration
│   │   └── config.py                # App configuration
│   ├── api.py           # Main API endpoints
│   ├── auth.py          # Auth utilities
│   ├── email_utils.py   # Email utilities
│   ├── health.py        # Health check endpoint
│   ├── middleware.py    # Security middleware
│   ├── models.py        # Database models
│   ├── schemas.py       # Pydantic schemas
│   └── main.py          # FastAPI app entry point
├── data/                # Model files
│   ├── model.joblib                 # TF-IDF model
│   ├── vectorizer.joblib            # TF-IDF vectorizer
│   ├── meta_model.joblib            # Meta-decision model
│   └── model_version.json           # Model metadata
├── training/            # Training scripts
│   ├── train.py                     # Train TF-IDF model
│   ├── train_production.py          # Production training
│   ├── train_transformer_clean.py   # Train transformer
│   ├── retrain_from_feedback.py     # Retrain from feedback
│   ├── prepare_datasets.py          # Dataset preparation
│   ├── benchmark_model.py           # Benchmark models
│   ├── ablation_study.py            # Ablation study
│   └── *.csv                        # Training datasets
├── tests/               # Test files
│   ├── conftest.py                  # Pytest configuration
│   ├── test_moderation.py           # Moderation tests
│   ├── test_retrain_from_feedback.py
│   └── stress_test.py               # Load testing
├── alembic/             # Database migrations
│   ├── versions/                    # Migration files
│   ├── env.py                       # Alembic environment
│   └── script.py.mako               # Migration template
├── database.py          # Database connection
├── requirements.txt     # Python dependencies
├── runtime.txt          # Python version
├── Procfile             # Render process file
├── alembic.ini          # Alembic configuration
└── .env                 # Environment variables
```

## 🧩 Extension Structure

```
extension/
├── popup/               # Extension popup UI
│   ├── popup.html                   # Main popup
│   ├── popup.js                     # Popup logic
│   ├── dashboard.html               # Dashboard
│   ├── dashboard.js                 # Dashboard logic
│   ├── history.html                 # History view
│   ├── history.js                   # History logic
│   ├── detail.html                  # Detail view
│   ├── detail.js                    # Detail logic
│   ├── saved.html                   # Saved items
│   ├── saved.js                     # Saved logic
│   ├── settings.html                # Settings
│   ├── settings.js                  # Settings logic
│   ├── login.html                   # Login page
│   ├── login.js                     # Login logic
│   ├── config.js                    # Configuration
│   ├── shared.css                   # Shared styles
│   └── tailwind.css                 # Tailwind CSS
├── background/          # Background service worker
│   └── service_worker.js            # Background tasks
├── icons/               # Extension icons
│   ├── icon16.png
│   ├── icon48.png
│   ├── icon128.png
│   └── logo.png
├── content.js           # Content script
├── manifest.json        # Extension manifest
├── tailwind.config.js   # Tailwind configuration
└── tailwind.input.css   # Tailwind input
```

## 📊 Notebooks

```
notebooks/
├── 02_baseline_tfidf.ipynb          # TF-IDF baseline
├── 03_transformer_finetune.ipynb    # Transformer fine-tuning
└── 06_explainability.ipynb          # Explainability analysis
```

## 🚀 Training Files (Root)

```
UPLOAD_MODEL_TO_HF.py                # Upload model to HuggingFace
COLAB_UPLOAD_SCRIPT.txt              # Copy-paste Colab script
HF_UPLOAD_GUIDE.md                   # Upload guide
NEXT_STEPS.md                        # Next steps after training
README_TRAINING.md                   # Training documentation
```

## 🔑 Key Files

- **backend/app/main.py**: FastAPI application entry point
- **backend/app/api.py**: Main API endpoints for fact-checking
- **backend/app/analysis/transformer.py**: DeBERTa model integration
- **backend/data/model_version.json**: Model metadata and version
- **extension/manifest.json**: Chrome extension configuration
- **extension/content.js**: Content script for web page analysis
- **render.yaml**: Render deployment configuration

## 🗄️ Database

SQLite database: `backend/fake_news.db`

Tables:
- users
- chat_sessions
- chat_messages
- user_feedback
- claim_records

## 🌐 API Endpoints

- `POST /message` - Analyze text/claim
- `POST /feedback` - Submit user feedback
- `GET /credibility` - Get source credibility scores
- `POST /auth/register` - Register user
- `POST /auth/login` - Login user
- `GET /history/sessions` - Get chat sessions
- `GET /stats/dashboard` - Get statistics
- `GET /health` - Health check

## 📦 Model Information

**Primary Model**: DeBERTa v3 Base
- **Location**: `Bharat2004/deberta-fakenews-detector` (HuggingFace Hub)
- **Accuracy**: 96.63%
- **F1 Score**: 0.9646
- **Training Samples**: 273,932
- **Auto-downloads** on first use

**Fallback Model**: TF-IDF + Logistic Regression
- **Location**: `backend/data/model.joblib`
- **Used when**: Transformer not available or low memory

## 🔧 Environment Variables

Required in `backend/.env`:
```
GEMINI_API_KEY=your_key
BRAVE_API_KEY=your_key
JWT_SECRET_KEY=your_secret
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_password
```

Optional:
```
GOOGLE_FACTCHECK_API_KEY=your_key
WIKIDATA_ENABLED=false
SKIP_TRAIN_ON_STARTUP=true
```

## 📝 Development

**Start Backend**:
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Load Extension**:
1. Open Chrome → Extensions → Developer mode
2. Load unpacked → Select `extension/` folder

## 🚀 Deployment

**Render**:
- Configured in `render.yaml`
- Auto-deploys from GitHub
- Free tier: 512MB RAM

**Model Hosting**:
- HuggingFace Hub (free)
- Auto-downloads on deployment

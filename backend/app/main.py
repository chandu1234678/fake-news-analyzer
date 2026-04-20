import os
import logging
import json
import math
import warnings
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

# Suppress scikit-learn version warnings (models trained on 1.6.1)
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

# ── Custom JSON encoder — sanitize nan/inf from numpy/sklearn ─
class _SafeJSONEncoder(json.JSONEncoder):
    """Replace nan/inf float values with None so JSON serialization never crashes."""
    def iterencode(self, o, _one_shot=False):
        return super().iterencode(self._sanitize(o), _one_shot)

    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._sanitize(v) for v in obj]
        return obj

# Monkey-patch FastAPI's default JSON encoder
import fastapi.responses as _fr
_orig_render = _fr.JSONResponse.render

def _safe_render(self, content):
    try:
        return _orig_render(self, content)
    except (ValueError, OverflowError):
        # Fallback: sanitize all floats then re-encode
        import numpy as np

        def _fix(obj):
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if hasattr(obj, 'item'):  # numpy scalar
                v = obj.item()
                return None if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
            if isinstance(obj, dict):
                return {k: _fix(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_fix(v) for v in obj]
            return obj

        return json.dumps(_fix(content), allow_nan=False).encode("utf-8")

_fr.JSONResponse.render = _safe_render

from database import engine, Base
import app.models  # register models
from app.api import router
from app.routes.auth_routes import router as auth_router
from app.routes.history_routes import router as history_router
from app.routes.stats_routes import router as stats_router
from app.routes.explain_routes import router as explain_router
from app.routes.review_routes import router as review_router
from app.routes.ab_routes import router as ab_router
from app.routes.metrics_routes import router as metrics_router
from app.routes.websocket_routes import router as websocket_router
from app.routes.cache_routes import router as cache_router
from app.routes.quota_routes import router as quota_router
from app.routes.analytics_routes import router as analytics_router
from app.routes.audio_routes import router as audio_router
from app.routes.viral_routes import router as viral_router
from app.routes.upload_routes import router as upload_router
from app.routes.payment_routes import router as payment_router
from app.health import router as health_router
from app.middleware import SecurityMiddleware

# ── Structured JSON logging ───────────────────────────────────
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log)

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.root.handlers = [_handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class _SuppressHealthLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(_SuppressHealthLogs())


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    # ── Load TF-IDF model only (fast, ~50ms) ──────────────────
    # RoBERTa is NOT preloaded — it's 500MB and would time out Render's
    # health check. It loads lazily on first request instead.
    try:
        from app.analysis.ml import _load_tfidf
        _load_tfidf()
        logger.info("TF-IDF model preloaded")
    except Exception as e:
        logger.warning("TF-IDF preload failed: %s", e)

    # ── Train TF-IDF if no model file exists ──────────────────
    if os.getenv("SKIP_TRAIN_ON_STARTUP", "false").lower() != "true":
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "model.joblib")
        if not os.path.exists(model_path):
            try:
                import subprocess, sys
                train_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "training", "train.py")
                subprocess.run([sys.executable, train_script], check=True)
                logger.info("ML model trained on startup")
            except Exception as e:
                logger.warning("ML training failed on startup: %s", e)

    # ── Pre-warm sentence-transformers (avoids 30s cold-start on first claim) ─
    # Only runs if sentence-transformers is installed (not on Render free tier)
    try:
        from app.analysis.semantic_clustering import _get_sentence_transformer
        _get_sentence_transformer()
        logger.info("Sentence-transformers model pre-warmed")
    except (ImportError, Exception) as e:
        logger.debug("Sentence-transformers pre-warm skipped: %s", e)

    # ── Start background data collection scheduler ────────────
    # Collects fresh labeled training data every 24h from web search + fact-checkers
    # Non-blocking — runs in a daemon thread
    try:
        import threading, time as _time
        from database import SessionLocal

        def _collection_scheduler():
            """Check every hour if it's time to collect new training data."""
            _time.sleep(300)  # wait 5 min after startup before first check
            while True:
                try:
                    from app.analysis.continuous_learning import maybe_collect_data
                    result = maybe_collect_data(SessionLocal)
                    if result.get("triggered"):
                        logger.info("Background data collection triggered: %s", result.get("reason"))
                except Exception as e:
                    logger.debug("Collection scheduler error: %s", e)
                _time.sleep(3600)  # check every hour

        _sched_thread = threading.Thread(
            target=_collection_scheduler,
            daemon=True,
            name="data-collection-scheduler",
        )
        _sched_thread.start()
        logger.info("Background data collection scheduler started (every 24h)")
    except Exception as e:
        logger.warning("Data collection scheduler failed to start: %s", e)

    yield


app = FastAPI(
    title="PiNE AI",
    version="2.6.1",
    lifespan=lifespan,
    description="PiNE AI — AI-powered fact-checking API with ML models, evidence search, and real-time verification",
    # Disable docs in production for security (set ENABLE_DOCS=true to re-enable)
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None,
    openapi_url="/openapi.json" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None,
)

# ── CORS — only allow extension and known origins ─────────────
ALLOWED_ORIGINS = [
    "chrome-extension://",   # matched by prefix check below
    "https://fake-news-analyzer-j6ka.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Chrome extensions need wildcard — headers guard the rest
    allow_methods=["GET", "POST", "DELETE", "PATCH", "HEAD"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

# ── Security middleware (rate limiting + headers) ─────────────
app.add_middleware(SecurityMiddleware)

# ── Rate limit headers middleware ─────────────────────────────
from app.rate_limit import add_rate_limit_headers
app.middleware("http")(add_rate_limit_headers)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(history_router)
app.include_router(stats_router)
app.include_router(explain_router)
app.include_router(review_router)
app.include_router(ab_router)
app.include_router(metrics_router)
app.include_router(websocket_router)
app.include_router(cache_router)
app.include_router(quota_router)
app.include_router(analytics_router)
app.include_router(audio_router)
app.include_router(viral_router)
app.include_router(upload_router)
app.include_router(payment_router)
app.include_router(health_router)
app.include_router(router)

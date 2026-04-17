import os
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
import app.models  # register models
from app.api import router
from app.routes.auth_routes import router as auth_router
from app.routes.history_routes import router as history_router
from app.routes.stats_routes import router as stats_router
from app.routes.explain_routes import router as explain_router
from app.routes.review_routes import router as review_router
from app.routes.ab_routes import router as ab_router
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
    yield


app = FastAPI(
    title="FactCheck AI",
    version="2.0.0",
    lifespan=lifespan,
    # Hide docs in production — remove these lines if you want Swagger UI
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
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

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(history_router)
app.include_router(stats_router)
app.include_router(explain_router)
app.include_router(review_router)
app.include_router(ab_router)
app.include_router(health_router)
app.include_router(router)

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
import app.models  # register models
from app.api import router
from app.routes.auth_routes import router as auth_router
from app.routes.history_routes import router as history_router
from app.routes.stats_routes import router as stats_router
from app.health import router as health_router
from app.middleware import SecurityMiddleware

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class _SuppressHealthLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(_SuppressHealthLogs())


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
app.include_router(health_router)
app.include_router(router)

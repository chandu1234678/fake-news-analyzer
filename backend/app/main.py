import os
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
import app.models  # register models
from app.api import router
from app.routes.auth_routes import router as auth_router
from app.routes.history_routes import router as history_router
from app.routes.stats_routes import router as stats_router
from app.health import router as health_router

# ── Logging setup ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Suppress /health spam from logs ──────────────────────────
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
            print("ML model trained successfully")
        except Exception as e:
            print(f"Warning: ML training failed: {e}")
    yield


app = FastAPI(title="FactCheck AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(history_router)
app.include_router(stats_router)
app.include_router(health_router)
app.include_router(router)

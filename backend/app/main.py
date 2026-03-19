import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
import app.models  # register models
from app.api import router
from app.routes.auth_routes import router as auth_router
from app.routes.history_routes import router as history_router

app = FastAPI(title="FactCheck AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(history_router)
app.include_router(router)


@app.on_event("startup")
def on_startup():
    # Create DB tables
    Base.metadata.create_all(bind=engine)
    # Train ML model if artifacts are missing (first deploy)
    model_path = os.path.join(os.path.dirname(__file__), "..", "data", "model.joblib")
    if not os.path.exists(model_path):
        try:
            import subprocess, sys
            train_script = os.path.join(os.path.dirname(__file__), "..", "training", "train.py")
            subprocess.run([sys.executable, train_script], check=True)
            print("ML model trained successfully")
        except Exception as e:
            print(f"Warning: ML training failed: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

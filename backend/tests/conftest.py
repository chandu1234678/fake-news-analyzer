import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import app.models
from database import Base, get_db
from app.main import app
from app.auth import get_current_user_optional
import app.api as api_module


@pytest.fixture()
def client(monkeypatch):
    os.environ["SKIP_TRAIN_ON_STARTUP"] = "true"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_optional] = lambda: None

    monkeypatch.setattr(api_module, "run_ml_analysis", lambda text: {"fake": 0.9})
    monkeypatch.setattr(api_module, "run_ai_analysis", lambda text: (0.9, "AI says fake"))
    monkeypatch.setattr(api_module, "fetch_evidence", lambda text: (0.1, ["http://example.com"], []))
    monkeypatch.setattr(api_module, "analyze_manipulation", lambda text: (0.8, ["sensational"]))
    monkeypatch.setattr(api_module, "extract_claims", lambda text: [text])
    monkeypatch.setattr(api_module, "normalize_claim", lambda text: (text, "English", False))
    monkeypatch.setattr(api_module, "build_explanation", lambda **kwargs: {"summary": "ok"})
    monkeypatch.setattr(api_module, "get_highlights", lambda text: [])
    monkeypatch.setattr(api_module, "record_drift", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_module, "decide", lambda **kwargs: ("fake", 0.9))

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

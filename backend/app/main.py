from fastapi import FastAPI
from app.api import router
from app.health import router as health_router

app = FastAPI(title="Fake News Analyzer")

app.include_router(router)
app.include_router(health_router)

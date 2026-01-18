from fastapi import FastAPI
from app.api import router

app = FastAPI(title="Fake News Analyzer")
app.include_router(router)

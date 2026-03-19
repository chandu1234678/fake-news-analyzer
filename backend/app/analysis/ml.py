import os
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

_model = None
_vectorizer = None

def _load():
    global _model, _vectorizer
    if _model is None:
        _model = joblib.load(os.path.join(DATA_DIR, "model.joblib"))
        _vectorizer = joblib.load(os.path.join(DATA_DIR, "vectorizer.joblib"))

def run_ml_analysis(text: str):
    _load()
    vec = _vectorizer.transform([text])
    prob = _model.predict_proba(vec)[0][1]
    return {"fake": round(float(prob), 2)}

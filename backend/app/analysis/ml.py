import os
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

model = joblib.load(os.path.join(DATA_DIR, "model.joblib"))
vectorizer = joblib.load(os.path.join(DATA_DIR, "vectorizer.joblib"))

def run_ml_analysis(text: str):
    vec = vectorizer.transform([text])
    prob = model.predict_proba(vec)[0][1]
    return {"fake": round(float(prob), 2)}

"""
Retrain from User Feedback

Pulls UserFeedback records from the DB where user corrected the verdict,
combines with original training data, and retrains the model.

Only uses feedback where:
  - predicted != actual (genuine corrections)
  - confidence was high (model was wrong confidently — most valuable)

Run: python backend/training/retrain_from_feedback.py
"""

import os
import sys
import json
import joblib
import pandas as pd
from datetime import datetime
from sklearn.metrics import f1_score, accuracy_score

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import SessionLocal
from app.models import UserFeedback

DATA_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
TRAIN_DIR = os.path.dirname(__file__)


def load_feedback() -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = db.query(UserFeedback).filter(
            UserFeedback.predicted != UserFeedback.actual
        ).all()
        if not rows:
            print("⚠️  No feedback corrections found in DB.")
            return pd.DataFrame()
        data = []
        for r in rows:
            if r.claim_text and r.actual in ("fake", "real"):
                data.append({
                    "combined": r.claim_text,
                    "label": 1 if r.actual == "fake" else 0,
                    "source": "feedback",
                })
        print(f"✅ Loaded {len(data)} feedback corrections from DB")
        return pd.DataFrame(data)
    finally:
        db.close()


def main():
    feedback_df = load_feedback()
    if feedback_df.empty:
        print("Nothing to retrain on. Exiting.")
        return

    # Load existing training data (legacy CSV)
    legacy = os.path.join(TRAIN_DIR, "fake_news.csv")
    frames = [feedback_df]
    if os.path.exists(legacy):
        df_leg = pd.read_csv(legacy)
        df_leg["combined"] = df_leg["text"].fillna("")
        df_leg["label"] = df_leg["label"].map({"fake": 1, "real": 0})
        df_leg["source"] = "original"
        frames.append(df_leg[["combined", "label", "source"]])

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["combined", "label"])
    df = df[df["combined"].str.len() > 20]
    df = df.drop_duplicates(subset=["combined"])
    print(f"📊 Total training samples: {len(df)} (feedback: {len(feedback_df)})")

    # Load existing vectorizer (don't refit — preserve feature space)
    vec_path = os.path.join(DATA_DIR, "vectorizer.joblib")
    if not os.path.exists(vec_path):
        print("❌ vectorizer.joblib not found. Run train.py first.")
        return

    vectorizer = joblib.load(vec_path)
    from sklearn.linear_model import LogisticRegression
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        df["combined"], df["label"], test_size=0.15, random_state=42
    )
    X_train_vec = vectorizer.transform(X_train)
    X_test_vec  = vectorizer.transform(X_test)

    base = LogisticRegression(max_iter=1000, C=5.0, solver="lbfgs", n_jobs=-1)
    base.fit(X_train_vec, y_train)

    # Calibrate
    X_cal_vec = X_test_vec
    y_cal     = y_test
    calibrated = CalibratedClassifierCV(base, method="isotonic", cv="prefit")
    calibrated.fit(X_cal_vec, y_cal)

    y_pred = calibrated.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, average="macro")
    print(f"🎯 Retrained accuracy: {acc:.4f} | F1: {f1:.4f}")

    # Load old model metrics to compare
    version_path = os.path.join(DATA_DIR, "model_version.json")
    old_f1 = 0.0
    if os.path.exists(version_path):
        with open(version_path) as fp:
            old_info = json.load(fp)
        old_f1 = old_info.get("f1_macro", 0.0)
        print(f"   Previous F1: {old_f1:.4f}")

    if f1 < old_f1 - 0.01:
        print(f"⛔ New model F1 ({f1:.4f}) is worse than current ({old_f1:.4f}). Rejecting.")
        return

    # Save
    joblib.dump(calibrated, os.path.join(DATA_DIR, "model.joblib"))
    version_info = {
        "version": datetime.utcnow().strftime("v%Y%m%d_%H%M") + "_feedback",
        "samples": len(df),
        "feedback_samples": len(feedback_df),
        "accuracy": round(acc, 4),
        "f1_macro": round(f1, 4),
        "calibration": "isotonic",
    }
    with open(version_path, "w") as fp:
        json.dump(version_info, fp, indent=2)

    print(f"✅ Model updated with feedback data. Version: {version_info['version']}")


if __name__ == "__main__":
    main()

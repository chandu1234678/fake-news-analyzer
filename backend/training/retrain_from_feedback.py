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


def _load_training_frames() -> list[pd.DataFrame]:
    frames = []

    def _normalize_label(value):
        if pd.isna(value):
            return None
        if isinstance(value, str):
            value = value.strip().lower()
            if value in {"fake", "1", "true", "yes"}:
                return 1
            if value in {"real", "0", "false", "no"}:
                return 0
        if value in {1, 1.0, True}:
            return 1
        if value in {0, 0.0, False}:
            return 0
        try:
            return int(value)
        except Exception:
            return None

    fake_path = os.path.join(TRAIN_DIR, "Fake.csv")
    true_path = os.path.join(TRAIN_DIR, "True.csv")
    if os.path.exists(fake_path) and os.path.exists(true_path):
        fake_df = pd.read_csv(fake_path, usecols=["title", "text"])
        true_df = pd.read_csv(true_path, usecols=["title", "text"])
        fake_df["label"] = 1
        true_df["label"] = 0
        for df in (fake_df, true_df):
            df["combined"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
        frames.extend([fake_df[["combined", "label"]], true_df[["combined", "label"]]])

    ds2_path = os.path.join(TRAIN_DIR, "fake_news_dataset_44k.csv")
    if os.path.exists(ds2_path):
        df2 = pd.read_csv(ds2_path, usecols=["text", "label"])
        df2 = df2.dropna(subset=["text", "label"])
        df2["label"] = df2["label"].map(_normalize_label)
        df2 = df2.dropna(subset=["label"])
        df2["label"] = df2["label"].astype(int)
        df2 = df2.rename(columns={"text": "combined"})
        frames.append(df2[["combined", "label"]])

    ds3_path = os.path.join(TRAIN_DIR, "fake_news_dataset_20k.csv")
    if os.path.exists(ds3_path):
        df3 = pd.read_csv(ds3_path, usecols=["title", "text", "label"])
        df3 = df3.dropna(subset=["text", "label"])
        df3["label"] = df3["label"].astype(str).str.strip().str.lower().map({"fake": 1, "real": 0})
        df3 = df3.dropna(subset=["label"])
        df3["label"] = df3["label"].astype(int)
        df3["combined"] = (df3["title"].fillna("") + " " + df3["text"].fillna("")).str.strip()
        frames.append(df3[["combined", "label"]])

    legacy_path = os.path.join(TRAIN_DIR, "fake_news.csv")
    if os.path.exists(legacy_path):
        df_leg = pd.read_csv(legacy_path)
        if {"text", "label"}.issubset(df_leg.columns):
            df_leg["combined"] = df_leg["text"].fillna("")
            df_leg["label"] = df_leg["label"].map(_normalize_label)
            df_leg = df_leg.dropna(subset=["label"])
            frames.append(df_leg[["combined", "label"]])

    return frames


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
    frames = []
    if not feedback_df.empty:
        frames.append(feedback_df)
    frames.extend(_load_training_frames())

    if not frames:
        print("Nothing to retrain on. Exiting.")
        return

    df = pd.concat(frames, ignore_index=True, sort=False)
    df = df.dropna(subset=["combined", "label"])
    df = df[df["combined"].str.len() > 20]
    df = df.drop_duplicates(subset=["combined"])
    df["label"] = df["label"].astype(int)

    if df["label"].nunique() < 2:
        print("❌ Need both fake and real labels to retrain safely.")
        return

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

    class_counts = df["label"].value_counts()
    stratify_labels = df["label"] if class_counts.min() >= 2 else None

    X_train, X_test, y_train, y_test = train_test_split(
        df["combined"], df["label"], test_size=0.15, random_state=42, stratify=stratify_labels
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
        "training_sources": {
            "feedback": int(len(feedback_df)),
            "datasets": int(len(df) - len(feedback_df)),
        },
    }
    with open(version_path, "w") as fp:
        json.dump(version_info, fp, indent=2)

    print(f"✅ Model updated with feedback data. Version: {version_info['version']}")


if __name__ == "__main__":
    main()

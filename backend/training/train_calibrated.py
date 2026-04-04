"""
Calibrated ML Model Training

Wraps the TF-IDF + Logistic Regression model with CalibratedClassifierCV
(isotonic regression) so that confidence scores are reliable:
  - "90% confidence" should be correct ~90% of the time
  - Plots reliability curve to prove calibration

Run: python backend/training/train_calibrated.py
Outputs: backend/data/model.joblib (calibrated), backend/data/vectorizer.joblib
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib
import json
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, accuracy_score, f1_score,
    brier_score_loss
)

BASE_DIR  = os.path.dirname(os.path.dirname(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
TRAIN_DIR = os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)

# ── Load data (same logic as train.py) ────────────────────────
frames = []

for fname, label_col, label_map in [
    ("Fake.csv",  None, 1),
    ("True.csv",  None, 0),
]:
    path = os.path.join(TRAIN_DIR, fname)
    if os.path.exists(path):
        df = pd.read_csv(path, usecols=["title", "text"])
        df["combined"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
        df["label"] = label_map
        frames.append(df[["combined", "label"]])

for fname, text_col, label_col in [
    ("fake_news_dataset_44k.csv", "text",  "label"),
    ("fake_news_dataset_20k.csv", "title", "label"),
]:
    path = os.path.join(TRAIN_DIR, fname)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if "text" in df.columns:
                df["combined"] = (df.get("title", pd.Series([""] * len(df))).fillna("") + " " + df["text"].fillna("")).str.strip()
            else:
                continue
            if df["label"].dtype == object:
                df["label"] = df["label"].str.strip().str.lower().map({"fake": 1, "real": 0})
            df["label"] = df["label"].astype(int)
            frames.append(df[["combined", "label"]])
        except Exception as e:
            print(f"⚠️  {fname}: {e}")

legacy = os.path.join(TRAIN_DIR, "fake_news.csv")
if os.path.exists(legacy) and not frames:
    df = pd.read_csv(legacy)
    df["combined"] = df["text"].fillna("")
    df["label"] = df["label"].map({"fake": 1, "real": 0})
    frames.append(df[["combined", "label"]])

if not frames:
    print("❌ No training data found.")
    sys.exit(1)

df = pd.concat(frames, ignore_index=True)
df = df.dropna(subset=["combined", "label"])
df = df[df["combined"].str.len() > 20]
df = df.drop_duplicates(subset=["combined"])
print(f"📊 Total samples: {len(df)} | Fake: {df['label'].sum()} | Real: {(df['label']==0).sum()}")

# ── Split: 80% train, 10% calibration, 10% test ───────────────
X_temp, X_test, y_temp, y_test = train_test_split(
    df["combined"], df["label"], test_size=0.10, random_state=42, stratify=df["label"]
)
X_train, X_cal, y_train, y_cal = train_test_split(
    X_temp, y_temp, test_size=0.111, random_state=42, stratify=y_temp
)
print(f"   Train: {len(X_train)} | Cal: {len(X_cal)} | Test: {len(X_test)}")

# ── Vectorize ─────────────────────────────────────────────────
vectorizer = TfidfVectorizer(
    stop_words="english", max_features=50000,
    ngram_range=(1, 2), sublinear_tf=True, min_df=2,
)
X_train_vec = vectorizer.fit_transform(X_train)
X_cal_vec   = vectorizer.transform(X_cal)
X_test_vec  = vectorizer.transform(X_test)

# ── Base model ────────────────────────────────────────────────
base = LogisticRegression(max_iter=1000, C=5.0, solver="lbfgs", n_jobs=-1)
base.fit(X_train_vec, y_train)

# ── Calibrate with isotonic regression ───────────────────────
calibrated = CalibratedClassifierCV(base, method="isotonic", cv="prefit")
calibrated.fit(X_cal_vec, y_cal)

# ── Evaluate ──────────────────────────────────────────────────
y_pred      = calibrated.predict(X_test_vec)
y_proba     = calibrated.predict_proba(X_test_vec)[:, 1]
acc         = accuracy_score(y_test, y_pred)
f1          = f1_score(y_test, y_pred, average="macro")
brier       = brier_score_loss(y_test, y_proba)

print(f"\n🎯 Test accuracy : {acc:.4f}")
print(f"   F1 (macro)    : {f1:.4f}")
print(f"   Brier score   : {brier:.4f}  (lower = better calibrated, 0 = perfect)")
print(classification_report(y_test, y_pred, target_names=["Real", "Fake"]))

# ── Calibration curve ─────────────────────────────────────────
try:
    frac_pos, mean_pred = calibration_curve(y_test, y_proba, n_bins=10)
    print("\n📈 Reliability curve (mean predicted prob → fraction positive):")
    print(f"   {'Predicted':>10}  {'Actual':>8}")
    for mp, fp in zip(mean_pred, frac_pos):
        bar = "█" * int(fp * 20)
        print(f"   {mp:>10.3f}  {fp:>8.3f}  {bar}")
    print("   (Ideal: predicted ≈ actual — diagonal line)")
except Exception as e:
    print(f"⚠️  Calibration curve failed: {e}")

# ── Save model + metadata ─────────────────────────────────────
joblib.dump(calibrated, os.path.join(DATA_DIR, "model.joblib"))
joblib.dump(vectorizer, os.path.join(DATA_DIR, "vectorizer.joblib"))

# Save version metadata
version_info = {
    "version": datetime.utcnow().strftime("v%Y%m%d_%H%M"),
    "samples": len(df),
    "accuracy": round(acc, 4),
    "f1_macro": round(f1, 4),
    "brier_score": round(brier, 4),
    "calibration": "isotonic",
    "features": 50000,
    "ngram_range": [1, 2],
}
with open(os.path.join(DATA_DIR, "model_version.json"), "w") as f:
    json.dump(version_info, f, indent=2)

print(f"\n✅ Calibrated model saved → backend/data/model.joblib")
print(f"   Version: {version_info['version']}")

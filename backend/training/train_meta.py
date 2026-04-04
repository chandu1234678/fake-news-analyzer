"""
Train a meta-decision model that learns to combine:
  - ml_fake    (0–1, ML model fake probability)
  - ai_fake    (0–1, LLM fake probability)
  - evidence   (0–1, news consistency score; 0.5 if missing)

Output: backend/data/meta_model.joblib

We generate a synthetic training set from known ground-truth rules,
then train a calibrated Logistic Regression on it.
In production you'd replace this with real labeled pipeline outputs.
"""

import os
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

rng = np.random.default_rng(42)
N = 20_000

# ── Generate synthetic training data ─────────────────────────
# Ground truth: fake if weighted score >= 0.5
# We add noise to simulate real-world disagreement between signals

def weighted(ml, ai, ev):
    return ml * 0.18 + ai * 0.50 + (1 - ev) * 0.32

ml_scores  = rng.beta(2, 2, N)          # spread around 0.5
ai_scores  = rng.beta(2, 2, N)
ev_scores  = rng.beta(2, 2, N)

# True label: weighted combination + small noise
noise = rng.normal(0, 0.05, N)
raw   = weighted(ml_scores, ai_scores, ev_scores) + noise
labels = (raw >= 0.5).astype(int)

# Add some hard cases: strong AI signal overrides
strong_fake_mask = ai_scores > 0.85
labels[strong_fake_mask] = 1

strong_real_mask = ai_scores < 0.15
labels[strong_real_mask] = 0

# Evidence override: many trusted sources strongly real
ev_real_mask = (ev_scores > 0.75) & (ai_scores < 0.5)
labels[ev_real_mask] = 0

X = np.column_stack([ml_scores, ai_scores, ev_scores])
y = labels

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.15, random_state=42, stratify=y
)

# ── Train calibrated logistic regression ─────────────────────
base = LogisticRegression(C=2.0, max_iter=500, solver="lbfgs")
model = CalibratedClassifierCV(base, cv=5, method="isotonic")
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print("Meta-model evaluation:")
print(classification_report(y_test, y_pred, target_names=["Real", "Fake"]))

out_path = os.path.join(DATA_DIR, "meta_model.joblib")
joblib.dump(model, out_path)
print(f"✅ Meta-model saved to {out_path}")

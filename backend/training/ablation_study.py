"""
Ablation Study — FactChecker AI Pipeline

Measures F1 score contribution of each component:
  1. ML only
  2. ML + AI
  3. ML + Evidence
  4. AI only
  5. AI + Evidence
  6. Full system (ML + AI + Evidence + Meta-model)

Uses the same synthetic test set as train_meta.py so results are comparable.
Run: backend\\venv\\Scripts\\python.exe backend\\training\\ablation_study.py
"""

import os
import sys
import numpy as np
import joblib
from sklearn.metrics import f1_score, accuracy_score

# ── Reproducible test set (same seed as train_meta.py) ───────
rng = np.random.default_rng(42)
N   = 20_000

ml_scores = rng.beta(2, 2, N)
ai_scores = rng.beta(2, 2, N)
ev_scores = rng.beta(2, 2, N)

noise  = rng.normal(0, 0.05, N)
raw    = ml_scores * 0.18 + ai_scores * 0.50 + (1 - ev_scores) * 0.32 + noise
labels = (raw >= 0.5).astype(int)

# Apply same overrides as training
labels[ai_scores > 0.85] = 1
labels[ai_scores < 0.15] = 0
labels[(ev_scores > 0.75) & (ai_scores < 0.5)] = 0

# Use last 3000 as test (same split as train_meta.py)
X_test = np.column_stack([ml_scores, ai_scores, ev_scores])[-3000:]
y_test = labels[-3000:]

# ── Load meta-model ───────────────────────────────────────────
DATA_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
model_path = os.path.join(DATA_DIR, "meta_model.joblib")

if not os.path.exists(model_path):
    print("❌ meta_model.joblib not found. Run train_meta.py first.")
    sys.exit(1)

meta_model = joblib.load(model_path)

# ── Ablation configurations ───────────────────────────────────
def predict_weighted(ml, ai, ev, use_ml, use_ai, use_ev):
    """Simple weighted heuristic for ablation baselines."""
    preds = []
    for i in range(len(ml)):
        score = 0.0
        w     = 0.0
        if use_ml:  score += ml[i] * 0.18; w += 0.18
        if use_ai:  score += ai[i] * 0.50; w += 0.50
        if use_ev:  score += (1 - ev[i]) * 0.32; w += 0.32
        if w == 0:
            preds.append(0)
        else:
            preds.append(1 if score / w >= 0.5 else 0)
    return np.array(preds)


def predict_meta(ml, ai, ev, use_ml, use_ai, use_ev):
    """Meta-model with ablated inputs replaced by 0.5 (neutral)."""
    X = np.column_stack([
        ml if use_ml else np.full(len(ml), 0.5),
        ai if use_ai else np.full(len(ai), 0.5),
        ev if use_ev else np.full(len(ev), 0.5),
    ])
    return meta_model.predict(X)


ml = X_test[:, 0]
ai = X_test[:, 1]
ev = X_test[:, 2]

configs = [
    ("ML only",              predict_weighted(ml, ai, ev, True,  False, False)),
    ("AI only",              predict_weighted(ml, ai, ev, False, True,  False)),
    ("Evidence only",        predict_weighted(ml, ai, ev, False, False, True)),
    ("ML + AI",              predict_weighted(ml, ai, ev, True,  True,  False)),
    ("ML + Evidence",        predict_weighted(ml, ai, ev, True,  False, True)),
    ("AI + Evidence",        predict_weighted(ml, ai, ev, False, True,  True)),
    ("Full (heuristic)",     predict_weighted(ml, ai, ev, True,  True,  True)),
    ("Full (meta-model)",    predict_meta(ml, ai, ev,     True,  True,  True)),
    ("Meta — no ML",         predict_meta(ml, ai, ev,     False, True,  True)),
    ("Meta — no AI",         predict_meta(ml, ai, ev,     True,  False, True)),
    ("Meta — no Evidence",   predict_meta(ml, ai, ev,     True,  True,  False)),
]

# ── Print results ─────────────────────────────────────────────
print("\n" + "=" * 62)
print(f"{'Configuration':<28} {'Accuracy':>9} {'F1 (macro)':>11}")
print("=" * 62)

results = []
for name, preds in configs:
    acc = accuracy_score(y_test, preds)
    f1  = f1_score(y_test, preds, average="macro")
    results.append((name, acc, f1))
    marker = " ◀ best" if name == "Full (meta-model)" else ""
    print(f"{name:<28} {acc:>8.4f}  {f1:>10.4f}{marker}")

print("=" * 62)

# ── Delta analysis ────────────────────────────────────────────
full_f1 = {name: f1 for name, acc, f1 in results}["Full (meta-model)"]
print("\nComponent contribution (F1 drop when removed from meta-model):")
for name, _, f1 in results:
    if name.startswith("Meta — no "):
        component = name.replace("Meta — no ", "")
        drop = full_f1 - f1
        print(f"  Remove {component:<12} → F1 drops by {drop:+.4f}")

print()

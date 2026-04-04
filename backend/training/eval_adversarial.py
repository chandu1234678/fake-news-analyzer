"""
Adversarial Evaluation

Runs the full pipeline on the generated adversarial test set
and reports F1, accuracy, and robustness score vs baseline.

Run: python backend/training/eval_adversarial.py
Requires: adversarial_test.csv (run gen_adversarial.py first)
          model.joblib + vectorizer.joblib in backend/data/
"""

import os
import sys
import csv
import json
import joblib
import numpy as np
from sklearn.metrics import f1_score, accuracy_score, classification_report

BASE_DIR  = os.path.dirname(os.path.dirname(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
TRAIN_DIR = os.path.dirname(__file__)

ADV_CSV   = os.path.join(TRAIN_DIR, "adversarial_test.csv")
VER_PATH  = os.path.join(DATA_DIR, "model_version.json")


def load_adversarial():
    if not os.path.exists(ADV_CSV):
        print("❌ adversarial_test.csv not found. Run gen_adversarial.py first.")
        sys.exit(1)
    rows = []
    with open(ADV_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("text") and r.get("label") in ("fake", "real"):
                rows.append(r)
    return rows


def predict_ml(texts):
    model_path = os.path.join(DATA_DIR, "model.joblib")
    vec_path   = os.path.join(DATA_DIR, "vectorizer.joblib")
    if not (os.path.exists(model_path) and os.path.exists(vec_path)):
        print("❌ model.joblib / vectorizer.joblib not found.")
        sys.exit(1)
    model      = joblib.load(model_path)
    vectorizer = joblib.load(vec_path)
    X = vectorizer.transform(texts)
    return model.predict(X)


def main():
    rows  = load_adversarial()
    texts = [r["text"] for r in rows]
    y_true = np.array([1 if r["label"] == "fake" else 0 for r in rows])
    types  = [r.get("type", "original") for r in rows]

    print(f"\n📊 Adversarial test set: {len(rows)} samples")
    type_counts = {}
    for t in types:
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in type_counts.items():
        print(f"   {t:<20} {c}")

    y_pred = predict_ml(texts)

    # Overall metrics
    acc = accuracy_score(y_true, y_pred)
    f1  = f1_score(y_true, y_pred, average="macro", zero_division=0)
    print(f"\n🎯 Overall — Accuracy: {acc:.4f} | F1 (macro): {f1:.4f}")
    print(classification_report(y_true, y_pred, target_names=["Real", "Fake"], zero_division=0))

    # Per-type breakdown
    print("Per-type breakdown:")
    print(f"  {'Type':<22} {'N':>4}  {'Acc':>7}  {'F1':>7}")
    print("  " + "-" * 44)
    results_by_type = {}
    for t in set(types):
        idx = [i for i, tp in enumerate(types) if tp == t]
        if not idx:
            continue
        yt = y_true[idx]
        yp = y_pred[idx]
        a  = accuracy_score(yt, yp)
        f  = f1_score(yt, yp, average="macro", zero_division=0)
        results_by_type[t] = {"acc": a, "f1": f, "n": len(idx)}
        print(f"  {t:<22} {len(idx):>4}  {a:>7.4f}  {f:>7.4f}")

    # Robustness score: avg F1 across adversarial types (excluding original)
    adv_types = [t for t in results_by_type if t != "original"]
    if adv_types:
        rob_f1 = np.mean([results_by_type[t]["f1"] for t in adv_types])
        orig_f1 = results_by_type.get("original", {}).get("f1", f1)
        drop = orig_f1 - rob_f1
        print(f"\n🛡️  Robustness score (avg adversarial F1): {rob_f1:.4f}")
        print(f"   F1 drop vs original: {drop:+.4f}")
        if drop < 0.05:
            print("   ✅ System is robust — minimal degradation under adversarial conditions")
        elif drop < 0.15:
            print("   ⚠️  Moderate degradation — consider adversarial training")
        else:
            print("   ❌ High degradation — model is brittle to rephrasing")

    # Save results to model_version.json
    if os.path.exists(VER_PATH):
        with open(VER_PATH) as fp:
            mv = json.load(fp)
        mv["adversarial_f1"]         = round(f1, 4)
        mv["adversarial_accuracy"]   = round(acc, 4)
        mv["robustness_score"]       = round(rob_f1, 4) if adv_types else None
        mv["adversarial_samples"]    = len(rows)
        with open(VER_PATH, "w") as fp:
            json.dump(mv, fp, indent=2)
        print(f"\n✅ Results saved to model_version.json")


if __name__ == "__main__":
    main()

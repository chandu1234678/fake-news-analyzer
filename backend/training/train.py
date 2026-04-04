"""
Train fake news classifier on merged datasets.

Sources used:
  1. Fake.csv / True.csv  — title+text, label from filename (0=real, 1=fake)
  2. fake_news_dataset_44k.csv — text + label (0/1)
  3. fake_news_dataset_20k.csv — title+text + label (real/fake)

Combined: ~110k samples → TF-IDF + Logistic Regression
"""

import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

BASE_DIR  = os.path.dirname(os.path.dirname(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
TRAIN_DIR = os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)

frames = []

# ── Dataset 1: Fake.csv + True.csv (title + text, label from filename) ────────
fake_path = os.path.join(TRAIN_DIR, "Fake.csv")
true_path = os.path.join(TRAIN_DIR, "True.csv")
if os.path.exists(fake_path) and os.path.exists(true_path):
    fake_df = pd.read_csv(fake_path, usecols=["title", "text"])
    true_df = pd.read_csv(true_path, usecols=["title", "text"])
    fake_df["label"] = 1
    true_df["label"] = 0
    for df in [fake_df, true_df]:
        df["combined"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
    frames.append(fake_df[["combined", "label"]])
    frames.append(true_df[["combined", "label"]])
    print(f"✅ Dataset 1 (Fake+True): {len(fake_df)+len(true_df)} rows")
else:
    print("⚠️  Fake.csv / True.csv not found, skipping")

# ── Dataset 2: fake_news_dataset_44k.csv (text, label 0/1) ───────────────────
ds2_path = os.path.join(TRAIN_DIR, "fake_news_dataset_44k.csv")
if os.path.exists(ds2_path):
    df2 = pd.read_csv(ds2_path, usecols=["text", "label"])
    df2 = df2.dropna(subset=["text", "label"])
    df2["label"] = df2["label"].astype(int)
    df2 = df2.rename(columns={"text": "combined"})
    frames.append(df2[["combined", "label"]])
    print(f"✅ Dataset 2 (44k): {len(df2)} rows")
else:
    print("⚠️  fake_news_dataset_44k.csv not found, skipping")

# ── Dataset 3: fake_news_dataset_20k.csv (title+text, label real/fake) ────────
ds3_path = os.path.join(TRAIN_DIR, "fake_news_dataset_20k.csv")
if os.path.exists(ds3_path):
    df3 = pd.read_csv(ds3_path, usecols=["title", "text", "label"])
    df3 = df3.dropna(subset=["text", "label"])
    df3["label"] = df3["label"].str.strip().str.lower().map({"fake": 1, "real": 0})
    df3 = df3.dropna(subset=["label"])
    df3["label"] = df3["label"].astype(int)
    df3["combined"] = (df3["title"].fillna("") + " " + df3["text"].fillna("")).str.strip()
    frames.append(df3[["combined", "label"]])
    print(f"✅ Dataset 3 (20k): {len(df3)} rows")
else:
    print("⚠️  fake_news_dataset_20k.csv not found, skipping")

# ── Also support legacy fake_news.csv (text + label fake/real) ────────────────
legacy_path = os.path.join(TRAIN_DIR, "fake_news.csv")
if os.path.exists(legacy_path) and not frames:
    df_leg = pd.read_csv(legacy_path)
    df_leg["combined"] = df_leg["text"].fillna("")
    df_leg["label"] = df_leg["label"].map({"fake": 1, "real": 0})
    frames.append(df_leg[["combined", "label"]])
    print(f"✅ Legacy dataset: {len(df_leg)} rows")

if not frames:
    raise RuntimeError("No training data found. Add CSV files to backend/training/")

# ── Merge & clean ──────────────────────────────────────────────────────────────
df = pd.concat(frames, ignore_index=True)
df = df.dropna(subset=["combined", "label"])
df = df[df["combined"].str.len() > 20]   # drop near-empty rows
df = df.drop_duplicates(subset=["combined"])

# ── Data quality filter ────────────────────────────────────────
# Minimum length: drop anything under 30 chars (noise)
df = df[df["combined"].str.len() >= 30]
# Drop rows with non-English or garbage content (basic heuristic)
df = df[df["combined"].str.contains(r"[a-zA-Z]", regex=True)]
# Cap max length to avoid memory issues with very long articles
df["combined"] = df["combined"].str[:5000]

print(f"\n📊 Total samples after merge+dedup+quality: {len(df)}")
print(f"   Fake: {df['label'].sum()} | Real: {(df['label']==0).sum()}")

# ── Train / test split ─────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    df["combined"], df["label"], test_size=0.1, random_state=42, stratify=df["label"]
)

# ── Vectorize ─────────────────────────────────────────────────────────────────
vectorizer = TfidfVectorizer(
    stop_words="english",
    max_features=50000,      # 50k features vs old 3k — much richer
    ngram_range=(1, 2),      # unigrams + bigrams
    sublinear_tf=True,       # log-scale TF
    min_df=2,
)
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec  = vectorizer.transform(X_test)

# ── Model ──────────────────────────────────────────────────────────────────────
model = LogisticRegression(max_iter=1000, C=5.0, solver="lbfgs", n_jobs=-1)
model.fit(X_train_vec, y_train)

# ── Evaluate ───────────────────────────────────────────────────────────────────
y_pred = model.predict(X_test_vec)
acc = accuracy_score(y_test, y_pred)
print(f"\n🎯 Test accuracy: {acc:.4f}")
print(classification_report(y_test, y_pred, target_names=["Real", "Fake"]))

# ── Save ───────────────────────────────────────────────────────────────────────
joblib.dump(model,      os.path.join(DATA_DIR, "model.joblib"))
joblib.dump(vectorizer, os.path.join(DATA_DIR, "vectorizer.joblib"))
print("✅ Model & vectorizer saved to backend/data/")

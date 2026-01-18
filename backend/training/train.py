import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

df = pd.read_csv(os.path.join(os.path.dirname(__file__), "fake_news.csv"))

X = df["text"]
y = df["label"].map({"fake": 1, "real": 0})

vectorizer = TfidfVectorizer(stop_words="english", max_features=3000)
X_vec = vectorizer.fit_transform(X)

model = LogisticRegression()
model.fit(X_vec, y)

joblib.dump(model, os.path.join(DATA_DIR, "model.joblib"))
joblib.dump(vectorizer, os.path.join(DATA_DIR, "vectorizer.joblib"))

print("✅ Model trained & saved")

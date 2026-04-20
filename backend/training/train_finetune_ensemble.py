"""
Fine-Tune Ensemble Training
============================
Fine-tunes TWO pre-trained fake news models on your local datasets,
then combines them into a weighted ensemble for inference.

Base models:
  1. jy46604790/Fake-News-Bert-Detect  — existing RoBERTa-base (already in prod)
  2. Arko007/fact-check1-v3-final      — DeBERTa-v3-large, 99.98% acc, calibrated

Your local training data:
  - Fake.csv + True.csv  (~44k ISOT articles)
  - fake_news_dataset_44k.csv
  - fake_news_dataset_20k.csv

Outputs:
  - ./finetuned_roberta/          (fine-tuned model 1)
  - ./finetuned_deberta/          (fine-tuned model 2)
  - ./ensemble_results.json       (per-model + ensemble metrics)
  - HuggingFace Hub push (optional, set HF_TOKEN + HF_USERNAME)

Run on Colab (recommended — needs GPU):
  !python train_finetune_ensemble.py --push-to-hub --hf-username YOUR_USERNAME

Run locally (CPU, slow but works):
  python backend/training/train_finetune_ensemble.py
"""

import os
import sys
import json
import argparse
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

import torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score,
    recall_score, classification_report
)
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    pipeline,
)
from datasets import Dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Model definitions ─────────────────────────────────────────
MODELS = {
    "roberta": {
        "hf_id":       "jy46604790/Fake-News-Bert-Detect",
        "output_dir":  "./finetuned_roberta",
        "max_length":  512,
        "batch_size":  16,
        "lr":          2e-5,
        "epochs":      4,
        # Label mapping for this model: LABEL_0=Fake, LABEL_1=Real
        "fake_label":  "LABEL_0",
        "weight":      1.0,   # ensemble weight (updated after eval)
        "description": "RoBERTa-base fine-tuned on fake news — fast, production-ready",
    },
    "deberta": {
        "hf_id":       "Arko007/fact-check1-v3-final",
        "output_dir":  "./finetuned_deberta",
        "max_length":  512,
        "batch_size":  8,    # DeBERTa-v3-large needs more memory
        "lr":          1e-5,  # lower LR for large model to avoid catastrophic forgetting
        "epochs":      2,     # fewer epochs — already well-calibrated
        # Label mapping: FAKE=1, REAL=0
        "fake_label":  "FAKE",
        "weight":      1.5,   # higher weight — larger, more accurate model
        "description": "DeBERTa-v3-large, 99.98% acc, calibrated on 51K samples",
    },
}

# ── Data loading ──────────────────────────────────────────────

def load_local_data(data_dir: str) -> pd.DataFrame:
    """Load all local CSV datasets and merge them."""
    frames = []

    # Fake.csv + True.csv (ISOT dataset)
    fake_path = os.path.join(data_dir, "Fake.csv")
    true_path = os.path.join(data_dir, "True.csv")
    if os.path.exists(fake_path) and os.path.exists(true_path):
        fake_df = pd.read_csv(fake_path, usecols=["title", "text"])
        true_df = pd.read_csv(true_path, usecols=["title", "text"])
        fake_df["label"] = 1
        true_df["label"] = 0
        for df in (fake_df, true_df):
            df["text"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
        frames.append(fake_df[["text", "label"]])
        frames.append(true_df[["text", "label"]])
        log.info("✓ Fake.csv + True.csv: %d samples", len(fake_df) + len(true_df))

    # fake_news_dataset_44k.csv
    ds44_path = os.path.join(data_dir, "fake_news_dataset_44k.csv")
    if os.path.exists(ds44_path):
        df = pd.read_csv(ds44_path, usecols=["text", "label"]).dropna()
        df["label"] = df["label"].astype(int)
        frames.append(df[["text", "label"]])
        log.info("✓ fake_news_dataset_44k.csv: %d samples", len(df))

    # fake_news_dataset_20k.csv
    ds20_path = os.path.join(data_dir, "fake_news_dataset_20k.csv")
    if os.path.exists(ds20_path):
        df = pd.read_csv(ds20_path, usecols=["title", "text", "label"]).dropna()
        df["label"] = df["label"].str.strip().str.lower().map({"fake": 1, "real": 0})
        df = df.dropna(subset=["label"])
        df["label"] = df["label"].astype(int)
        df["text"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
        frames.append(df[["text", "label"]])
        log.info("✓ fake_news_dataset_20k.csv: %d samples", len(df))

    if not frames:
        raise RuntimeError(
            "No training data found. Expected Fake.csv, True.csv, "
            "fake_news_dataset_44k.csv, or fake_news_dataset_20k.csv "
            f"in {data_dir}"
        )

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["text", "label"])
    df = df[df["text"].str.len() >= 30]
    df = df[df["text"].str.contains(r"[a-zA-Z]", regex=True)]
    df["text"] = df["text"].str[:5000]
    df = df.drop_duplicates(subset=["text"])
    df["label"] = df["label"].astype(int)

    log.info(
        "📊 Total after merge+dedup: %d | Fake: %d | Real: %d",
        len(df), df["label"].sum(), (df["label"] == 0).sum()
    )
    return df


def make_splits(df: pd.DataFrame):
    """80/10/10 stratified split."""
    train_df, temp_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["label"]
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, random_state=42, stratify=temp_df["label"]
    )
    log.info(
        "Split → train: %d | val: %d | test: %d",
        len(train_df), len(val_df), len(test_df)
    )
    return train_df, val_df, test_df


# ── Tokenization ──────────────────────────────────────────────

def tokenize_df(df: pd.DataFrame, tokenizer, max_length: int) -> Dataset:
    ds = Dataset.from_pandas(df[["text", "label"]].reset_index(drop=True))

    def _tok(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )

    return ds.map(_tok, batched=True, remove_columns=["text"])


# ── Metrics ───────────────────────────────────────────────────

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy":     accuracy_score(labels, preds),
        "f1_macro":     f1_score(labels, preds, average="macro"),
        "f1_weighted":  f1_score(labels, preds, average="weighted"),
        "precision":    precision_score(labels, preds, average="macro", zero_division=0),
        "recall":       recall_score(labels, preds, average="macro", zero_division=0),
    }


# ── Fine-tune one model ───────────────────────────────────────

def finetune_model(
    name: str,
    cfg: dict,
    train_ds: Dataset,
    val_ds: Dataset,
    test_ds: Dataset,
    hf_token: str = None,
    push_to_hub: bool = False,
    hf_username: str = None,
) -> dict:
    """Fine-tune a single model and return its test metrics."""

    log.info("")
    log.info("=" * 60)
    log.info("Fine-tuning: %s  (%s)", name.upper(), cfg["hf_id"])
    log.info("=" * 60)

    output_dir = cfg["output_dir"]
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Load tokenizer + model
    log.info("Loading tokenizer from %s ...", cfg["hf_id"])
    tokenizer = AutoTokenizer.from_pretrained(cfg["hf_id"], token=hf_token)

    log.info("Loading model from %s ...", cfg["hf_id"])
    model = AutoModelForSequenceClassification.from_pretrained(
        cfg["hf_id"],
        num_labels=2,
        ignore_mismatched_sizes=True,  # safe when head size differs
        token=hf_token,
    )

    # Tokenize splits
    log.info("Tokenizing ...")
    tok_train = tokenize_df(train_ds, tokenizer, cfg["max_length"])
    tok_val   = tokenize_df(val_ds,   tokenizer, cfg["max_length"])
    tok_test  = tokenize_df(test_ds,  tokenizer, cfg["max_length"])

    # Training args
    hub_model_id = f"{hf_username}/factchecker-{name}" if push_to_hub and hf_username else None

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=cfg["epochs"],
        per_device_train_batch_size=cfg["batch_size"],
        per_device_eval_batch_size=cfg["batch_size"] * 2,
        learning_rate=cfg["lr"],
        warmup_ratio=0.06,
        weight_decay=0.01,
        fp16=torch.cuda.is_available(),
        bf16=False,
        logging_steps=100,
        eval_strategy="steps",
        eval_steps=500,
        save_strategy="steps",
        save_steps=500,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        save_total_limit=2,
        report_to="none",
        push_to_hub=push_to_hub and hub_model_id is not None,
        hub_model_id=hub_model_id,
        hub_token=hf_token,
        dataloader_num_workers=2,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tok_train,
        eval_dataset=tok_val,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    log.info("Training on %s ...", "GPU" if torch.cuda.is_available() else "CPU")
    trainer.train()

    # Evaluate on test set
    log.info("Evaluating on test set ...")
    test_results = trainer.evaluate(tok_test)

    preds_out = trainer.predict(tok_test)
    pred_labels = np.argmax(preds_out.predictions, axis=-1)
    true_labels = preds_out.label_ids

    report = classification_report(
        true_labels, pred_labels,
        target_names=["Real", "Fake"],
        digits=4,
    )
    log.info("\n%s", report)

    metrics = {
        "model":     cfg["hf_id"],
        "name":      name,
        "accuracy":  round(test_results["eval_accuracy"], 4),
        "f1_macro":  round(test_results["eval_f1_macro"], 4),
        "precision": round(test_results["eval_precision"], 4),
        "recall":    round(test_results["eval_recall"], 4),
        "output_dir": output_dir,
        "hub_model_id": hub_model_id,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Save model
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    if push_to_hub and hub_model_id:
        log.info("Pushing to HuggingFace Hub: %s ...", hub_model_id)
        try:
            trainer.push_to_hub(commit_message=f"Fine-tuned on local fake news datasets — {metrics['f1_macro']:.4f} F1")
            log.info("✓ Pushed to https://huggingface.co/%s", hub_model_id)
        except Exception as e:
            log.warning("Hub push failed: %s", e)

    log.info(
        "✓ %s done — accuracy=%.4f  f1=%.4f",
        name.upper(), metrics["accuracy"], metrics["f1_macro"]
    )
    return metrics


# ── Ensemble inference ────────────────────────────────────────

class FinetuneEnsemble:
    """
    Loads both fine-tuned models and combines their predictions.

    Weights are set proportional to their test F1 scores so the
    better model automatically gets more say.
    """

    def __init__(self, results: dict, hf_token: str = None):
        self.pipes = {}
        self.weights = {}

        for name, cfg in MODELS.items():
            output_dir = cfg["output_dir"]
            if not os.path.exists(output_dir):
                log.warning("Model dir not found: %s — skipping", output_dir)
                continue
            try:
                device = 0 if torch.cuda.is_available() else -1
                self.pipes[name] = pipeline(
                    "text-classification",
                    model=output_dir,
                    device=device,
                    truncation=True,
                    max_length=cfg["max_length"],
                )
                # Weight = F1 score from fine-tuning (better model → more weight)
                f1 = results.get(name, {}).get("f1_macro", cfg["weight"])
                self.weights[name] = f1
                log.info("✓ Loaded %s (weight=%.4f)", name, f1)
            except Exception as e:
                log.warning("Failed to load %s: %s", name, e)

        if not self.pipes:
            raise RuntimeError("No fine-tuned models loaded. Run training first.")

        # Normalize weights to sum to 1
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}
        log.info("Ensemble weights: %s", self.weights)

    def predict(self, text: str) -> dict:
        """
        Returns:
          {
            "fake_probability": float,
            "verdict": "fake" | "real",
            "confidence": float,
            "model": "ensemble",
            "breakdown": { "roberta": float, "deberta": float }
          }
        """
        fake_probs = {}

        for name, pipe in self.pipes.items():
            try:
                result = pipe(text[:5000])[0]
                label = result["label"].upper()
                score = float(result["score"])

                # Normalize to fake probability
                cfg = MODELS[name]
                fake_label = cfg["fake_label"].upper()
                if label == fake_label:
                    fake_prob = score
                else:
                    fake_prob = 1.0 - score

                fake_probs[name] = fake_prob
            except Exception as e:
                log.warning("Inference failed for %s: %s", name, e)

        if not fake_probs:
            return {"fake_probability": 0.5, "verdict": "uncertain", "confidence": 0.0, "model": "ensemble"}

        # Weighted average
        weighted_fake = sum(
            fake_probs[n] * self.weights.get(n, 1.0)
            for n in fake_probs
        )
        # Re-normalize if some models failed
        active_weight = sum(self.weights.get(n, 1.0) for n in fake_probs)
        fake_probability = weighted_fake / active_weight if active_weight > 0 else 0.5

        verdict = "fake" if fake_probability >= 0.5 else "real"
        confidence = abs(fake_probability - 0.5) * 2  # 0 = uncertain, 1 = certain

        return {
            "fake_probability": round(fake_probability, 4),
            "verdict": verdict,
            "confidence": round(confidence, 4),
            "model": "ensemble",
            "breakdown": {k: round(v, 4) for k, v in fake_probs.items()},
        }

    def predict_batch(self, texts: list) -> list:
        return [self.predict(t) for t in texts]


# ── Update ml.py to use ensemble ─────────────────────────────

def update_ml_config(results: dict, data_dir: str):
    """
    Write ensemble_config.json so ml.py can load both fine-tuned models.
    """
    config = {
        "ensemble_models": [],
        "updated_at": datetime.utcnow().isoformat(),
    }

    for name, cfg in MODELS.items():
        output_dir = cfg["output_dir"]
        hub_id = results.get(name, {}).get("hub_model_id")
        f1 = results.get(name, {}).get("f1_macro", cfg["weight"])

        # Prefer HF Hub ID if pushed, else local path
        model_ref = hub_id if hub_id else output_dir

        config["ensemble_models"].append({
            "name": name,
            "model_id": model_ref,
            "fake_label": cfg["fake_label"],
            "weight": round(f1, 4),
            "max_length": cfg["max_length"],
            "description": cfg["description"],
        })

    out_path = os.path.join(data_dir, "ensemble_config.json")
    with open(out_path, "w") as f:
        json.dump(config, f, indent=2)
    log.info("✓ Ensemble config saved → %s", out_path)
    return config


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune RoBERTa + DeBERTa ensemble on local fake news data"
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.dirname(__file__),
        help="Directory containing Fake.csv, True.csv, etc. (default: script dir)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.dirname(__file__),
        help="Where to write finetuned_roberta/ and finetuned_deberta/",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["roberta", "deberta", "both"],
        default=["both"],
        help="Which models to fine-tune (default: both)",
    )
    parser.add_argument(
        "--push-to-hub",
        action="store_true",
        help="Push fine-tuned models to HuggingFace Hub after training",
    )
    parser.add_argument(
        "--hf-username",
        default=os.getenv("HF_USERNAME", ""),
        help="Your HuggingFace username (or set HF_USERNAME env var)",
    )
    parser.add_argument(
        "--hf-token",
        default=os.getenv("HF_TOKEN", ""),
        help="HuggingFace write token (or set HF_TOKEN env var)",
    )
    parser.add_argument(
        "--skip-roberta",
        action="store_true",
        help="Skip RoBERTa fine-tuning (use existing finetuned_roberta/ if present)",
    )
    parser.add_argument(
        "--skip-deberta",
        action="store_true",
        help="Skip DeBERTa fine-tuning (use existing finetuned_deberta/ if present)",
    )
    args = parser.parse_args()

    # Resolve model output dirs relative to --output-dir
    for name, cfg in MODELS.items():
        cfg["output_dir"] = os.path.join(args.output_dir, f"finetuned_{name}")

    data_dir = args.data_dir
    hf_token = args.hf_token or None
    push = args.push_to_hub and bool(args.hf_username) and bool(hf_token)

    if args.push_to_hub and not push:
        log.warning(
            "--push-to-hub requires both --hf-username and --hf-token (or HF_USERNAME/HF_TOKEN env vars)"
        )

    log.info("")
    log.info("=" * 60)
    log.info("FINE-TUNE ENSEMBLE TRAINING")
    log.info("=" * 60)
    log.info("Device: %s", "GPU ✓" if torch.cuda.is_available() else "CPU (slow)")
    if torch.cuda.is_available():
        log.info("GPU: %s", torch.cuda.get_device_name(0))
    log.info("Data dir: %s", data_dir)
    log.info("Push to Hub: %s", push)
    log.info("")

    # Load data once, share splits across both models
    df = load_local_data(data_dir)
    train_df, val_df, test_df = make_splits(df)

    results = {}
    models_to_train = set()
    if "both" in args.models:
        models_to_train = {"roberta", "deberta"}
    else:
        models_to_train = set(args.models)

    if args.skip_roberta:
        models_to_train.discard("roberta")
    if args.skip_deberta:
        models_to_train.discard("deberta")

    # Fine-tune selected models
    for name in ["roberta", "deberta"]:  # fixed order
        cfg = MODELS[name]
        if name not in models_to_train:
            # Try to load existing metrics
            metrics_path = os.path.join(cfg["output_dir"], "metrics.json")
            if os.path.exists(metrics_path):
                with open(metrics_path) as f:
                    results[name] = json.load(f)
                log.info("Skipping %s — loaded existing metrics (f1=%.4f)", name, results[name]["f1_macro"])
            else:
                log.info("Skipping %s — no existing metrics found", name)
            continue

        results[name] = finetune_model(
            name=name,
            cfg=cfg,
            train_ds=train_df,
            val_ds=val_df,
            test_ds=test_df,
            hf_token=hf_token,
            push_to_hub=push,
            hf_username=args.hf_username,
        )

    # Save ensemble results
    results_path = os.path.join(args.output_dir, "ensemble_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    log.info("✓ Results saved → %s", results_path)

    # Update ensemble config for ml.py
    data_dir_backend = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data"
    )
    os.makedirs(data_dir_backend, exist_ok=True)
    config = update_ml_config(results, data_dir_backend)

    # Print summary
    log.info("")
    log.info("=" * 60)
    log.info("RESULTS SUMMARY")
    log.info("=" * 60)
    for name, m in results.items():
        log.info(
            "  %-10s  accuracy=%.4f  f1=%.4f  %s",
            name.upper(),
            m.get("accuracy", 0),
            m.get("f1_macro", 0),
            f"→ {m.get('hub_model_id', m.get('output_dir', ''))}"
        )

    log.info("")
    log.info("Ensemble config written to backend/data/ensemble_config.json")
    log.info("")
    log.info("Next steps:")
    log.info("  1. Set ENABLE_ENSEMBLE=true in backend/.env")
    if push:
        for name, m in results.items():
            if m.get("hub_model_id"):
                log.info("  2. Set DEBERTA_MODEL=%s in backend/.env", m["hub_model_id"])
    else:
        log.info("  2. Models saved locally — run with --push-to-hub to upload to HuggingFace")
    log.info("=" * 60)


if __name__ == "__main__":
    main()

import os
import pandas as pd

from training import retrain_from_feedback as rff


def test_load_training_frames_normalizes_labels(tmp_path, monkeypatch):
    ds2 = tmp_path / "fake_news_dataset_44k.csv"
    pd.DataFrame({"text": ["alpha", "beta"], "label": ["fake", "real"]}).to_csv(ds2, index=False)

    legacy = tmp_path / "fake_news.csv"
    pd.DataFrame({"text": ["one", "two"], "label": [1, 0]}).to_csv(legacy, index=False)

    monkeypatch.setattr(rff, "TRAIN_DIR", str(tmp_path))

    frames = rff._load_training_frames()
    assert frames
    combined = pd.concat(frames, ignore_index=True)

    assert set(combined["label"]) == {0, 1}
    assert combined["combined"].notna().all()

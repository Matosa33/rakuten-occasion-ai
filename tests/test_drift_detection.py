"""Test de la détection de drift Evidently (Cycle 12.3, D-024)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl


def test_drift_detection_synthetique(tmp_path, monkeypatch):
    """Pipeline drift end-to-end sur petites données : sortie attendue + rapport HTML."""
    rng = np.random.default_rng(0)
    n = 400

    # Reference : titres courts, catégories Electronics/Video_Games
    ref = pl.DataFrame(
        {
            "title": ["short"] * n,
            "description": ["a" * 20] * n,
            "_source_category": rng.choice(["Electronics", "Video_Games"], n).tolist(),
        }
    )
    # Current : titres bien plus longs + autres catégories → drift fort attendu
    cur = pl.DataFrame(
        {
            "title": ["a much longer product title here"] * n,
            "description": ["b" * 200] * n,
            "_source_category": rng.choice(
                ["Tools_and_Home_Improvement", "Cell_Phones_and_Accessories"], n
            ).tolist(),
        }
    )
    ref.write_parquet(tmp_path / "train.parquet")
    cur.write_parquet(tmp_path / "test.parquet")

    from src.monitoring import drift_detection

    monkeypatch.setattr(drift_detection, "DATA_PROCESSED_PRODUCTS", tmp_path)
    monkeypatch.setattr(drift_detection, "REFERENCE_SAMPLE", n)
    monkeypatch.setattr(drift_detection, "CURRENT_SAMPLE", n)
    monkeypatch.setattr(drift_detection, "REPORT_DIR", tmp_path / "reports")

    result = drift_detection.detect_drift()

    assert result["n_reference"] == n
    assert result["n_current"] == n
    assert 0.0 <= result["drift_share"] <= 1.0
    # Distributions volontairement très différentes → drift détecté
    assert result["drift_detected"] is True
    assert Path(result["report_html"]).exists()

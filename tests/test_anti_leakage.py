"""Tests anti-leakage CI (sous-todo 1.3) — vérifie P1, P3, P5 rapidement.

Ces tests sont **conditionnels** : ils s'exécutent si les parquets
`data/processed/products/*.parquet` existent (run après sous-todo 1.2),
sinon ils sont skipped (garde la CI rapide pour les développeurs qui
n'ont pas le full dataset local).

Patterns testés en CI :
- P1 : Doublons parent_asin train/test (0 overlap exigé) — ~5 sec
- P3 : Fuite temporelle (spread médianes < 1 an) — ~5 sec
- P5 : Feature engineering stateless (grep static) — ~ms

P2 (metadata contient label) et P4 (overlap user_id) sont **lourds**
(scan tous reviews_index, ~1 min) → exclus de la CI mais vérifiés en
batch via `python -m src.data.validate.01_anti_leakage_check`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_DIR = REPO_ROOT / "data" / "processed" / "products"
FE_SOURCE = REPO_ROOT / "src" / "data" / "clean" / "05_feature_engineering.py"
METRICS_JSON = REPO_ROOT / "reports" / "02_cleaning" / "anti_leakage_metrics.json"

# Skipper si les parquets ne sont pas générés (cas CI sans données)
SKIP_REASON = "data/processed/products/ vide — lance d'abord sous-todo 1.2"


def _products_available() -> bool:
    if not PRODUCTS_DIR.exists():
        return False
    return all(
        (PRODUCTS_DIR / f"{split}.parquet").exists() for split in ("train", "val", "test")
    )


@pytest.mark.skipif(not _products_available(), reason=SKIP_REASON)
def test_p1_no_parent_asin_overlap_train_test():
    """P1 — 0 overlap parent_asin train/test (group split strict)."""
    import polars as pl

    train = pl.scan_parquet(PRODUCTS_DIR / "train.parquet").select("parent_asin").collect(
        engine="streaming"
    )
    test = pl.scan_parquet(PRODUCTS_DIR / "test.parquet").select("parent_asin").collect(
        engine="streaming"
    )
    overlap = set(train["parent_asin"].to_list()) & set(test["parent_asin"].to_list())
    assert len(overlap) == 0, (
        f"P1 cassé : {len(overlap)} parent_asin présents dans train ET test. "
        "Le split product-level doit être strict (anti-L1 variantes)."
    )


@pytest.mark.skipif(not _products_available(), reason=SKIP_REASON)
def test_p1_no_parent_asin_overlap_train_val():
    """P1 — 0 overlap parent_asin train/val."""
    import polars as pl

    train = pl.scan_parquet(PRODUCTS_DIR / "train.parquet").select("parent_asin").collect(
        engine="streaming"
    )
    val = pl.scan_parquet(PRODUCTS_DIR / "val.parquet").select("parent_asin").collect(
        engine="streaming"
    )
    overlap = set(train["parent_asin"].to_list()) & set(val["parent_asin"].to_list())
    assert len(overlap) == 0, f"P1 cassé : {len(overlap)} parent_asin train ∩ val"


@pytest.mark.skipif(not _products_available(), reason=SKIP_REASON)
def test_p3_temporal_distribution_aligned():
    """P3 — Médianes year_last_review proches entre splits (< 1 an d'écart)."""
    import polars as pl

    medians = []
    for split in ("train", "val", "test"):
        m = (
            pl.scan_parquet(PRODUCTS_DIR / f"{split}.parquet")
            .filter(pl.col("year_last_review").is_not_null())
            .select(pl.col("year_last_review").median())
            .collect(engine="streaming")
            .item()
        )
        medians.append(m)
    spread = max(medians) - min(medians)
    assert spread < 1, (
        f"P3 cassé : spread médianes year_last_review = {spread} ans entre splits. "
        f"Médianes = {medians}. Acceptable < 1 an."
    )


def test_p5_feature_engineering_stateless():
    """P5 — Aucun stateful global (mean/std/quantile) dans 05_feature_engineering.py."""
    if not FE_SOURCE.exists():
        pytest.skip("05_feature_engineering.py absent")
    source = FE_SOURCE.read_text(encoding="utf-8")
    statefuls = [".mean()", ".std()", ".quantile(", ".min()", ".max()", ".median()"]
    found = [pat for pat in statefuls if pat in source]
    assert not found, (
        f"P5 cassé : statefuls trouvés dans 05_feature_engineering.py : {found}. "
        "Si volontaires, vérifier qu'ils sont calculés sur le **train uniquement** "
        "(R3 anti-leakage)."
    )


@pytest.mark.skipif(not METRICS_JSON.exists(), reason="anti_leakage_metrics.json absent")
def test_metrics_json_has_5_patterns():
    """Le JSON anti_leakage_metrics.json doit avoir les 5 patterns P1-P5."""
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    expected = {"P1", "P2", "P3", "P4", "P5"}
    assert set(metrics.keys()) == expected, (
        f"JSON anti_leakage_metrics.json incomplet : keys = {set(metrics.keys())} "
        f"vs attendu {expected}"
    )

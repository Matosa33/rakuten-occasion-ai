"""Tests des stats appariées (Cycle 34.6) — fonctions pures sur données synthétiques."""

from __future__ import annotations

from src.retrieval.listing_quality_stats import (
    clustered_bootstrap_ci,
    page_trend,
    product_family,
    tost_equivalence,
    wilcoxon_pair,
)


def test_product_family_retire_index():
    assert product_family("11_apple_iphone_14_128go") == "apple_iphone_14_128go"
    assert (
        product_family("12_apple_iphone_14_128go") == "apple_iphone_14_128go"
    )  # doublon → même famille


def test_page_trend_detecte_monotonie():
    # 12 sujets strictement croissants C0<C1<C2<C3
    matrix = {
        "C0": [0.1 + i * 0.01 for i in range(12)],
        "C1": [0.3 + i * 0.01 for i in range(12)],
        "C2": [0.6 + i * 0.01 for i in range(12)],
        "C3": [0.8 + i * 0.01 for i in range(12)],
    }
    res = page_trend(matrix, ["C0", "C1", "C2", "C3"])
    assert res["p"] < 0.01  # tendance croissante très significative


def test_wilcoxon_detecte_difference():
    a = [0.5 + i * 0.02 for i in range(15)]
    b = [0.3 + i * 0.02 for i in range(15)]  # a systématiquement > b
    res = wilcoxon_pair(a, b)
    assert res["p"] < 0.01 and res["median_diff"] > 0


def test_tost_equivalence_quand_proche():
    a = [0.50, 0.51, 0.49, 0.50, 0.52, 0.48, 0.50, 0.51]
    b = [0.50, 0.50, 0.50, 0.51, 0.49, 0.50, 0.51, 0.49]  # ~identiques
    res = tost_equivalence(a, b, sesoi=0.05)
    assert res["equivalent"] is True


def test_clustered_bootstrap_compte_familles():
    values = [1.0, 1.0, 0.0, 0.0, 1.0]
    families = ["a", "a", "b", "b", "c"]  # 3 familles, 5 obs
    res = clustered_bootstrap_ci(values, families, n_boot=500)
    assert res["n_families"] == 3 and res["n_obs"] == 5
    assert res["ci_low"] <= res["mean"] <= res["ci_high"]

"""Tests pour le pricing M8 cascade L1-L4 (src/pricing/01_algorithmique.py)."""

from __future__ import annotations

import importlib

import pytest

_pricing = importlib.import_module("src.pricing.01_algorithmique")
suggest_price = _pricing.suggest_price
PricingResult = _pricing.PricingResult
CONDITION_MULTIPLIER = _pricing.CONDITION_MULTIPLIER
CATEGORY_DEPRECIATION_RATE = _pricing.CATEGORY_DEPRECIATION_RATE


class TestL1CatalogMeta:
    def test_l1_returns_high_confidence(self):
        result = suggest_price(
            catalog_price=100.0,
            knn_neighbors_prices=None,
            category_median_price=None,
            condition="bon_etat",
            age_years=0.0,
            category="Electronics",
        )
        assert result.confidence_level == "L1"
        assert result.confidence_score == 0.90
        assert result.method == "catalog_meta"

    def test_l1_applies_condition_multiplier(self):
        result_neuf = suggest_price(100.0, None, None, "neuf", 0.0, "Electronics")
        result_correct = suggest_price(100.0, None, None, "correct", 0.0, "Electronics")
        assert result_neuf.suggested_price_eur > result_correct.suggested_price_eur
        # Avec dépréciation 0 an + Electronics, prix neuf = 100 * 1.0
        assert abs(result_neuf.suggested_price_eur - 100.0) < 0.01

    def test_l1_applies_depreciation(self):
        # Electronics : -15 %/an
        result = suggest_price(100.0, None, None, "neuf", 2.0, "Electronics")
        # 100 * (1 - 0.15*2) * 1.0 = 70
        assert abs(result.suggested_price_eur - 70.0) < 0.01


class TestL2KNNMedian:
    def test_l2_falls_back_to_knn(self):
        result = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=[80.0, 90.0, 100.0, 110.0],
            category_median_price=None,
            condition="bon_etat",
            age_years=0.0,
            category="Electronics",
        )
        assert result.confidence_level == "L2"
        assert result.method == "knn_median"

    def test_l2_filters_invalid_prices(self):
        # Prix < 0.01 (parasite Amazon) sont filtrés
        result = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=[0.0, 0.0, 80.0, 90.0, 100.0],
            category_median_price=None,
            condition="bon_etat",
            category="Electronics",
        )
        # Median(80, 90, 100) = 90, * 0.55 (bon_etat) = 49.5
        assert abs(result.suggested_price_eur - 49.5) < 0.01

    def test_l2_requires_min_3_valid_prices(self):
        # Avec seulement 2 prix valides, doit passer en L3
        result = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=[0.0, 80.0, 90.0],  # 2 valides seulement
            category_median_price=50.0,
            condition="bon_etat",
            category="Electronics",
        )
        assert result.confidence_level == "L3"


class TestL3CategoryMedian:
    def test_l3_uses_category_median(self):
        result = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=None,
            category_median_price=50.0,
            condition="bon_etat",
            category="Electronics",
        )
        assert result.confidence_level == "L3"
        assert result.method == "category_median"
        # 50 * 0.55 (bon_etat) = 27.5
        assert abs(result.suggested_price_eur - 27.5) < 0.01


class TestL4Fallback:
    def test_l4_when_all_inputs_missing(self):
        result = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=None,
            category_median_price=None,
            condition="bon_etat",
            category="",
        )
        assert result.confidence_level == "L4"
        assert result.suggested_price_eur == 0.0
        assert result.method == "fallback"
        assert "manuelle" in result.explanation.lower()


class TestConditionAndDepreciationConfig:
    def test_all_conditions_have_multipliers(self):
        for cond in ("neuf", "tres_bon_etat", "bon_etat", "correct"):
            assert cond in CONDITION_MULTIPLIER

    def test_condition_multipliers_descending(self):
        assert (
            CONDITION_MULTIPLIER["neuf"]
            > CONDITION_MULTIPLIER["tres_bon_etat"]
            > CONDITION_MULTIPLIER["bon_etat"]
            > CONDITION_MULTIPLIER["correct"]
        )

    def test_4_categories_have_depreciation(self):
        for cat in (
            "Electronics",
            "Cell_Phones_and_Accessories",
            "Video_Games",
            "Tools_and_Home_Improvement",
        ):
            assert cat in CATEGORY_DEPRECIATION_RATE


@pytest.mark.parametrize(
    "category,age,catalog,expected_min",
    [
        ("Cell_Phones_and_Accessories", 1.0, 1000.0, 700),  # -20%/an
        ("Tools_and_Home_Improvement", 5.0, 1000.0, 700),  # -5%/an = 0.75
        ("Electronics", 3.0, 1000.0, 500),  # -15%/an = 0.55
    ],
)
def test_depreciation_per_category(category, age, catalog, expected_min):
    result = suggest_price(catalog, None, None, "neuf", age, category)
    assert result.suggested_price_eur >= expected_min - 50  # tolerance

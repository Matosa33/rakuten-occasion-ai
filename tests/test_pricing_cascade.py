"""Tests pour le pricing M8 cascade L1-L4 (src/pricing/01_algorithmique.py)."""

from __future__ import annotations

import importlib

import pytest

_pricing = importlib.import_module("src.pricing.01_algorithmique")
suggest_price = _pricing.suggest_price
PricingResult = _pricing.PricingResult
CONDITION_MULTIPLIER = _pricing.CONDITION_MULTIPLIER
CATEGORY_DEPRECIATION_RATE = _pricing.CATEGORY_DEPRECIATION_RATE
# 17.4b (D-036) : entrées USD, sorties EUR - les assertions de valeur
# référencent la constante du module (robustes à un changement de taux).
USD_TO_EUR = _pricing.USD_TO_EUR


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
        # Avec dépréciation 0 an + Electronics, prix neuf = 100 $ * 1.0 → EUR
        assert abs(result_neuf.suggested_price_eur - 100.0 * USD_TO_EUR) < 0.01

    def test_l1_applies_depreciation(self):
        # Electronics : -15 %/an
        result = suggest_price(100.0, None, None, "neuf", 2.0, "Electronics")
        # 100 $ * (1 - 0.15*2) * 1.0 = 70 $ → EUR
        assert abs(result.suggested_price_eur - 70.0 * USD_TO_EUR) < 0.01


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
        # Median(80, 90, 100) = 90 $, * 0.55 (bon_etat) = 49.5 $ → EUR
        assert abs(result.suggested_price_eur - 49.5 * USD_TO_EUR) < 0.01

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
        # 50 $ * 0.55 (bon_etat) = 27.5 $ → EUR
        assert abs(result.suggested_price_eur - 27.5 * USD_TO_EUR) < 0.01


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


class TestL15LLMAnchor:
    """Cycle 36 - niveau L1.5 : prix neuf de référence estimé par IA → décote déterministe."""

    def test_l15_used_when_anchor_present_and_no_catalog(self):
        r = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=[5.0, 6.0, 7.0],  # voisins pollués ignorés grâce à l'ancre
            category_median_price=10.0,
            condition="bon_etat",
            age_years=0.0,
            category="Electronics",
            llm_anchor_price=200.0,
            llm_anchor_confidence=0.8,
        )
        assert r.confidence_level == "L1.5"
        assert r.method == "llm_anchor"
        # 200 $ * 0.55 (bon état) * USD_TO_EUR, dépréciation 0 an
        assert abs(r.suggested_price_eur - 200.0 * 0.55 * USD_TO_EUR) < 0.01

    def test_l1_beats_l15(self):
        # Prix catalogue RÉEL présent → L1 prioritaire sur l'ancre IA.
        r = suggest_price(
            catalog_price=300.0,
            knn_neighbors_prices=None,
            category_median_price=None,
            condition="bon_etat",
            age_years=0.0,
            category="Electronics",
            llm_anchor_price=200.0,
            llm_anchor_confidence=0.9,
        )
        assert r.confidence_level == "L1"
        assert r.method == "catalog_meta"

    def test_l15_applies_condition_and_depreciation(self):
        neuf = suggest_price(None, None, None, "neuf", 0.0, "Electronics", llm_anchor_price=200.0)
        correct = suggest_price(
            None, None, None, "correct", 2.0, "Electronics", llm_anchor_price=200.0
        )
        assert neuf.suggested_price_eur > correct.suggested_price_eur
        assert abs(neuf.suggested_price_eur - 200.0 * 1.0 * USD_TO_EUR) < 0.01
        # correct 2 ans Electronics : 200 * (1-0.30) * 0.35 * taux
        assert abs(correct.suggested_price_eur - 200.0 * 0.70 * 0.35 * USD_TO_EUR) < 0.01

    def test_l15_skipped_when_anchor_none(self):
        # Sans ancre → comportement IDENTIQUE à l'actuel (garde de non-régression).
        r = suggest_price(None, [50.0, 60.0, 70.0], 40.0, "bon_etat", 0.0, "Electronics")
        assert r.confidence_level == "L2"
        assert r.method == "knn_median"

    def test_l15_ignored_if_anchor_zero_or_negative(self):
        r = suggest_price(None, None, 40.0, "bon_etat", 0.0, "Electronics", llm_anchor_price=0.0)
        assert r.confidence_level == "L3"  # ancre invalide → on saute L1.5


class TestUnderpricingGuard:
    """Cycle 36 - garde-fou : une médiane de voisins polluée (6 € pour 150 €) est relevée."""

    def test_floor_lifts_absurd_knn_median(self):
        # Montre ~150 $ neuf, voisins pollués par bracelets/coques à 5-7 $.
        r = suggest_price(
            catalog_price=None,
            knn_neighbors_prices=[5.0, 6.0, 7.0, 6.0, 5.0],
            category_median_price=None,
            condition="bon_etat",
            age_years=2.0,
            category="Electronics",
            expected_order_of_magnitude=150.0,
        )
        assert r.method == "knn_median"
        # plancher = 0.25 * (150 * 0.70 * 0.55 * taux)
        floor = 0.25 * (150.0 * 0.70 * 0.55 * USD_TO_EUR)
        assert r.suggested_price_eur >= floor - 0.01
        assert "relevé" in r.explanation.lower()

    def test_floor_inactive_without_expected(self):
        # Sans ordre de grandeur attendu → pas de relevage (rétro-compat).
        r = suggest_price(None, [5.0, 6.0, 7.0], None, "bon_etat", 2.0, "Electronics")
        assert "relevé" not in r.explanation.lower()
        assert r.suggested_price_eur < 5.0  # reste bas (non corrigé)

    def test_floor_does_not_lower_reasonable_price(self):
        # Voisins cohérents avec le neuf → pas modifié.
        r = suggest_price(
            None,
            [90.0, 100.0, 110.0],
            None,
            "bon_etat",
            1.0,
            "Electronics",
            expected_order_of_magnitude=120.0,
        )
        assert "relevé" not in r.explanation.lower()


class TestL1AnchorConsistency:
    """Cycle 36 - garde-fou : un prix catalogue d'accessoire (top-1 mal apparié) ne pollue pas L1."""

    def test_l1_skipped_when_catalog_polluted_by_accessory(self):
        # top-1 = coque à 43.6 $ mais l'ancre IA estime l'iPhone à 598 $ → on ignore L1, on prend L1.5.
        r = suggest_price(
            catalog_price=43.6,
            knn_neighbors_prices=None,
            category_median_price=None,
            condition="bon_etat",
            age_years=2.0,
            category="Electronics",
            llm_anchor_price=598.0,
            llm_anchor_confidence=0.9,
        )
        assert r.confidence_level == "L1.5"
        assert r.method == "llm_anchor"

    def test_l1_kept_when_catalog_consistent_with_anchor(self):
        # catalogue cohérent avec l'ancre (même ordre de grandeur) → L1 (prix réel) prioritaire.
        r = suggest_price(
            catalog_price=900.0,
            knn_neighbors_prices=None,
            category_median_price=None,
            condition="bon_etat",
            age_years=2.0,
            category="Electronics",
            llm_anchor_price=1000.0,
            llm_anchor_confidence=0.9,
        )
        assert r.confidence_level == "L1"
        assert r.method == "catalog_meta"

    def test_l1_kept_when_no_anchor(self):
        # pas d'ancre → comportement historique (L1 dès qu'un prix catalogue existe).
        r = suggest_price(43.6, None, None, "bon_etat", 2.0, "Electronics")
        assert r.confidence_level == "L1"


class TestCatalogOutlierGuard:
    """Cycle 36 - un prix catalogue ABERRANT (donnée polluée) ne doit pas être gobé par L1."""

    def test_absurd_catalog_price_ignored_for_neighbors(self):
        # catalogue 9755 $ (faute de saisie) vs voisins ~240 → on écarte L1, on prend L2.
        r = suggest_price(
            catalog_price=9755.0,
            knn_neighbors_prices=[230.0, 240.0, 250.0, 235.0],
            category_median_price=None,
            condition="bon_etat",
            age_years=2.0,
            category="Electronics",
        )
        assert r.method == "knn_median"
        assert r.suggested_price_eur < 300

    def test_normal_catalog_price_kept(self):
        r = suggest_price(250.0, [230.0, 240.0, 260.0], None, "bon_etat", 2.0, "Electronics")
        assert r.confidence_level == "L1"

    def test_no_neighbors_no_outlier_guard(self):
        # sans assez de voisins → pas de garde-fou (rétro-compat)
        r = suggest_price(9755.0, None, None, "bon_etat", 2.0, "Electronics")
        assert r.confidence_level == "L1"

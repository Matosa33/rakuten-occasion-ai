"""Tests des métriques dures de qualité de fiche (Cycle 34.5) - fonctions pures."""

from __future__ import annotations

from src.retrieval.listing_quality_metrics import (
    brand_correct,
    completeness_fixed,
    entity_match,
    leaf_exact,
    leaf_overlap,
    typical_field_rate,
)


def test_leaf_exact():
    assert leaf_exact("A > B > Smartwatches", "X > Y > Smartwatches") == 1
    assert leaf_exact("A > B > Tablets", "X > Y > Smartwatches") == 0
    assert leaf_exact("", "X > Smartwatches") == 0


def test_leaf_overlap_retire_stopwords():
    ov = leaf_overlap("Electronics > Graphics Cards", "Electronics > Computers > Graphics Cards")
    assert ov > 0  # 'graphics','cards' communs ; 'electronics' (stopword) ignoré
    assert leaf_overlap("Tablets", "Smartwatches") == 0.0


def test_entity_match():
    assert entity_match("Apple iPhone 13", "Apple iPhone 13 128GB Black") == 1  # tous présents
    assert entity_match("Apple iPhone 13", "Samsung Galaxy A50 Black") == 0


def test_brand_correct():
    fields = [{"name": "Marque", "value": "Apple", "source": "observé"}]
    assert brand_correct(fields, "Apple iPhone 13") == 1
    assert brand_correct(fields, "Samsung Galaxy") == 0
    assert brand_correct([], "Apple") == 0


def test_completeness_fixed():
    assert completeness_fixed(
        ["Type de produit", "État"], ["Type de produit", "État", "Marque"]
    ) == round(2 / 3, 4)
    assert completeness_fixed([], ["A"]) == 0.0


def test_typical_field_rate():
    assert typical_field_rate([{"source": "observé"}, {"source": "typique-à-vérifier"}]) == 0.5
    assert typical_field_rate([]) == 0.0

"""Tests de la cascade de remplissage catalog-miss (Cycle 33.8, D-041).

Vérifie : le bon niveau de cascade (N1/N2/N3), la provenance par champ (observé / catalogue /
typique-à-vérifier), et le calcul de complétude. Anti-hallucination : une valeur issue d'un
candidat NON fiable est marquée « typique-à-vérifier », jamais affirmée comme catalogue.
"""

from __future__ import annotations

from src.serving.listing_fill import (
    SRC_CATALOG,
    SRC_OBSERVED,
    SRC_TYPICAL,
    assemble_listing,
)


def _src(res, field_name: str) -> str | None:
    for f in res.fields:
        if f.name == field_name:
            return f.source
    return None


def test_n1_match_fiable_specs_catalogue():
    """Match fiable → niveau N1, les facettes du candidat sont sourcées 'catalogue'."""
    res = assemble_listing(
        category_leaf="Smartwatches",
        category_confidence=0.9,
        condition_label="Bon état",
        photo_attributes={},  # rien lu sur la photo
        match_brand="Apple",
        match_attributes={"color": "Noir", "capacity": "32 Go"},
        match_reliable=True,
        expected_facets=["color", "capacity"],
    )
    assert res.level == "N1_catalog"
    assert _src(res, "Marque") == SRC_CATALOG
    assert _src(res, "Couleur") == SRC_CATALOG
    assert res.completeness == 1.0  # Type, État, Marque, Couleur, Capacité tous remplis


def test_n2_pas_de_match_photo_prioritaire_et_typique_marque():
    """Pas de match fiable mais catégorie sûre → N2 ; photo = 'observé', candidat = 'typique'."""
    res = assemble_listing(
        category_leaf="Graphics Cards",
        category_confidence=0.5,
        condition_label="Très bon état",
        photo_attributes={"brand": "NVIDIA", "color": "Noir"},  # lus sur la photo
        match_brand="MSI",
        match_attributes={"capacity": "24 Go"},  # candidat non fiable → typique
        match_reliable=False,
        expected_facets=["color", "capacity"],
    )
    assert res.level == "N2_category_photo"
    assert _src(res, "Marque") == SRC_OBSERVED  # la photo prime
    assert _src(res, "Couleur") == SRC_OBSERVED
    assert _src(res, "Capacité") == SRC_TYPICAL  # imputé du candidat non fiable → à vérifier


def test_n3_sans_categorie_observe_seul():
    """Sans catégorie → niveau N3 (observé seul), complétude partielle."""
    res = assemble_listing(
        category_leaf="",
        category_confidence=0.0,
        condition_label="Bon état",
        photo_attributes={"brand": "Bosch"},
        match_reliable=False,
        expected_facets=["color"],
    )
    assert res.level == "N3_observed"
    assert _src(res, "Marque") == SRC_OBSERVED
    assert "Couleur" in res.missing  # facette attendue non remplie
    assert 0.0 < res.completeness < 1.0


def test_completude_compte_les_manquants():
    """La complétude = champs remplis / attendus ; les manquants sont listés."""
    res = assemble_listing(
        category_leaf="Pressure Washers",
        category_confidence=0.7,
        condition_label="Bon état",
        photo_attributes={},  # rien d'observé
        match_reliable=False,
        expected_facets=["color", "capacity"],
    )
    # attendus : Type, État, Marque, Couleur, Capacité (5) ; remplis : Type + État (2)
    assert "Marque" in res.missing and "Couleur" in res.missing
    assert res.completeness == round(2 / 5, 4)

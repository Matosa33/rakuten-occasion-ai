"""Le rangement a facettes explicites est bien cable dans l'API (P0, D-041/D-044).

Garde-fou : (1) le schema fixe de facettes couvre toutes les macros, (2) l'assemblage
produit des champs avec provenance et une completude sur dénominateur fixe.
"""

from __future__ import annotations

from src.api.main import _load_expected_facets
from src.config import CATEGORIES
from src.serving.listing_fill import SRC_CATALOG, SRC_OBSERVED, assemble_listing


def test_expected_facets_config_couvre_les_macros() -> None:
    fac = _load_expected_facets()
    assert set(fac) == set(CATEGORIES), "le schema de facettes doit couvrir exactement les macros"
    for keys in fac.values():
        assert keys and all(isinstance(k, str) for k in keys)


def test_assemble_listing_provenance_et_completude() -> None:
    fac = _load_expected_facets()
    a = assemble_listing(
        category_leaf="Power Supplies",
        category_confidence=0.8,
        condition_label="Bon état",
        photo_attributes={"brand": "EVGA", "capacity": "1000W"},
        match_attributes={"color": "Black", "model": "1000 GQ"},
        match_reliable=True,
        expected_facets=fac["Electronics"],
    )
    sources = {f.name: f.source for f in a.fields}
    assert sources["Capacité"] == SRC_OBSERVED  # la photo est prioritaire
    assert sources["Couleur"] == SRC_CATALOG  # catalogue si absent de la photo
    assert a.level == "N1_catalog"
    assert 0.0 < a.completeness <= 1.0

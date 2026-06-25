"""Statut OOD 3 niveaux + garde-longueur titre (Cycle 35.5/35.6, audit pre-prod).

Le seuil intermediaire (to_confirm) n'etait jamais couvert ; le titre genere pouvait deborder.
"""

from __future__ import annotations

from src.api.pipeline import TITLE_MAX_LEN, _clamp_title, status_from_score


def test_status_les_trois_niveaux_et_bornes() -> None:
    assert status_from_score(0.80) == "identified"
    assert status_from_score(0.60) == "identified"  # borne incluse
    assert status_from_score(0.59) == "to_confirm"
    assert status_from_score(0.45) == "to_confirm"  # borne incluse
    assert status_from_score(0.44) == "uncertain"
    assert status_from_score(0.0) == "uncertain"


def test_clamp_title_vide_repli_sur_catalogue() -> None:
    assert _clamp_title("", "Apple iPhone 13") == "Apple iPhone 13"
    assert _clamp_title("   ", "Repli") == "Repli"


def test_clamp_title_tronque_proprement() -> None:
    out = _clamp_title("X" * 200, "fb")
    assert len(out) <= TITLE_MAX_LEN
    assert out.endswith("…")


def test_clamp_title_normal_inchange() -> None:
    assert _clamp_title("iPhone 13 128GB Noir", "fb") == "iPhone 13 128GB Noir"

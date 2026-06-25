"""Test du vote k-NN fin (bras A2, champion du benchmark Cycle 33).

Garantit que la catégorie fine retournée par le pipeline vient bien d'un vote pondéré
des voisins (plus robuste que la catégorie du seul top-1), avec confiance et breadcrumb.
"""

from __future__ import annotations

from src.api.pipeline import Candidate, weighted_fine_vote


def _cand(asin: str, fine: str, score: float, path: str = "") -> Candidate:
    return Candidate(
        parent_asin=asin,
        title="",
        store="",
        category="Electronics",
        score=score,
        category_fine=fine,
        category_path=path,
    )


def test_vote_pondere_peut_battre_le_top1():
    """Le top-1 dit 'Tablets', mais le poids cumulé des voisins penche pour 'Graphics Cards'."""
    cands = [
        _cand("a", "Tablets", 0.61, "Electronics > Tablets"),
        _cand("b", "Graphics Cards", 0.60, "Electronics > Computers > Graphics Cards"),
        _cand("c", "Graphics Cards", 0.59, "Electronics > Computers > Graphics Cards"),
    ]
    fine, conf, path = weighted_fine_vote(cands)
    assert fine == "Graphics Cards"  # le vote (0.60+0.59) bat le top-1 seul (0.61)
    assert 0.0 < conf <= 1.0
    assert "Graphics Cards" in path


def test_confiance_est_part_du_vote():
    """Unanimité → confiance = 1.0."""
    cands = [_cand("a", "Consoles", 0.9, "X"), _cand("b", "Consoles", 0.7, "X")]
    fine, conf, _ = weighted_fine_vote(cands)
    assert fine == "Consoles"
    assert conf == 1.0


def test_vote_vide_si_aucune_categorie_fine():
    """Aucun candidat avec catégorie fine → triple vide (pas de crash)."""
    assert weighted_fine_vote([_cand("a", "", 0.5)]) == ("", 0.0, "")
    assert weighted_fine_vote([]) == ("", 0.0, "")

"""Tests du vote k-NN pondere sur la categorie fine (bras champion knn-vote, D-040/D-044).

Cette fonction est le coeur de la classification fine (mesure +2,4 pts leaf-acc vs top-1) et
n'etait pas testee (audit pre-prod). On verifie consensus, cas singleton, et cas degeneres.
"""

from __future__ import annotations

from src.api.pipeline import Candidate, weighted_fine_vote


def _c(fine: str, score: float, path: str = "") -> Candidate:
    return Candidate(
        "asin", "titre", "store", "Electronics", score, category_fine=fine, category_path=path
    )


def test_vote_consensus_pondere_par_similarite() -> None:
    cands = [
        _c("Graphics Cards", 0.9, "Electronics > Graphics Cards"),
        _c("Graphics Cards", 0.8),
        _c("Monitors", 0.5),
    ]
    fine, conf, path = weighted_fine_vote(cands)
    assert fine == "Graphics Cards"  # la majorite ponderee gagne
    assert 0.5 < conf <= 1.0  # confiance = part du vote remporte
    assert path == "Electronics > Graphics Cards"  # breadcrumb du meilleur candidat gagnant


def test_vote_singleton_confiance_pleine() -> None:
    fine, conf, path = weighted_fine_vote([_c("Smartwatches", 0.7, "P > Q")])
    assert (fine, conf, path) == ("Smartwatches", 1.0, "P > Q")


def test_vote_aucun_candidat() -> None:
    assert weighted_fine_vote([]) == ("", 0.0, "")


def test_vote_candidats_sans_categorie_fine() -> None:
    assert weighted_fine_vote([_c("", 0.9), _c("", 0.5)]) == ("", 0.0, "")


def test_vote_ignore_scores_negatifs() -> None:
    # un voisin a score negatif (OOD) ne doit pas peser negativement
    fine, conf, _ = weighted_fine_vote([_c("Laptops", 0.8), _c("Laptops", -0.3)])
    assert fine == "Laptops" and 0.0 < conf <= 1.0

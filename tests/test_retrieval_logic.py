"""Tests de la logique retrieval pure (Cycle 15.3, D-034 - modules aveugles audit 15.0).

Données synthétiques uniquement (aucun artefact lourd) : OOD guardrails 3 niveaux
(D-012/D-017), fusion RRF (Cormack 2009), Akinator backend (entropie discriminante).
Modules à préfixe numéroté → import via importlib.
"""

from __future__ import annotations

import importlib

import numpy as np
import pytest

_ood = importlib.import_module("src.retrieval.03_ood_guardrails")
_akinator = importlib.import_module("src.retrieval.04_akinator_backend")
_rrf = importlib.import_module("src.retrieval.02_multiview_rrf")


# ─────────────────────────────────────────────────────────────────────────────
# OOD guardrails (D-012 : seuil 0.600 calibré F0.5)
# ─────────────────────────────────────────────────────────────────────────────


def test_ood_top1_sous_le_seuil():
    """Score top1 < seuil → OOD (anti-hallucination R19)."""
    assert _ood.is_ood_top1(0.55, threshold=0.600) is True
    assert _ood.is_ood_top1(0.65, threshold=0.600) is False


def test_ood_exactement_au_seuil_n_est_pas_ood():
    """Le seuil est inclusif côté accepté (>= seuil = identifié, cf. D-017
    `top1 >= 0.60 → identified`). Régression si l'inégalité bascule."""
    assert _ood.is_ood_top1(0.600, threshold=0.600) is False


def test_ambiguite_top12_gap_faible():
    """Écart top1-top2 < gap → ambiguïté → déclenche l'Akinator."""
    assert _ood.is_ambiguous_top12(0.70, 0.68, gap_threshold=0.05) is True
    assert _ood.is_ambiguous_top12(0.70, 0.60, gap_threshold=0.05) is False


# ─────────────────────────────────────────────────────────────────────────────
# RRF fusion (Cormack 2009, k=60)
# ─────────────────────────────────────────────────────────────────────────────


def test_rrf_doc_commun_aux_deux_vues_gagne():
    """Un doc présent en tête des DEUX vues doit sortir premier de la fusion
    (c'est tout le point du RRF : le consensus bat le rang isolé)."""
    # Vue A : doc 7 rank 0, doc 3 rank 1 ; vue B : doc 7 rank 0, doc 9 rank 1.
    view_a = np.array([[7, 3, 1]])
    view_b = np.array([[7, 9, 2]])
    fused = _rrf._rrf_fusion([view_a, view_b], k=60)
    assert fused[0][0] == 7, f"doc consensus doit être premier, vu {fused[0]}"


def test_rrf_une_seule_vue_preserve_l_ordre():
    """En mono-view (cas text-only D-014), le RRF doit préserver l'ordre."""
    view = np.array([[5, 2, 8, 1]])
    fused = _rrf._rrf_fusion([view], k=60)
    assert fused[0].tolist() == [5, 2, 8, 1]


def test_rrf_padding_si_moins_de_candidats_uniques():
    """Si les vues retournent moins d'items uniques que top_k, padding -1
    (régression : sans padding, np.array hétérogène plante)."""
    view_a = np.array([[4, 4, 4]])  # un seul doc unique
    fused = _rrf._rrf_fusion([view_a], k=60)
    assert fused.shape == (1, 3)
    assert fused[0][0] == 4
    assert -1 in fused[0], "le padding -1 doit compléter les slots vides"


# ─────────────────────────────────────────────────────────────────────────────
# Akinator backend (D-019 : facette discriminante par entropie normalisée)
# ─────────────────────────────────────────────────────────────────────────────


def test_akinator_ambiguite_et_clarification_seuils():
    """Seuils gap : < 0.05 ambigu ; > 0.10 clarifié (zone grise entre les deux)."""
    assert _akinator.is_ambiguous(0.70, 0.68) is True
    assert _akinator.is_ambiguous(0.70, 0.60) is False
    assert _akinator.is_clarified(0.70, 0.55) is True
    assert _akinator.is_clarified(0.70, 0.63) is False


def test_attribut_identique_partout_entropie_zero():
    """Un attribut où tous les candidats partagent la valeur ne discrimine RIEN
    (entropie 0) - il ne doit jamais être proposé comme observation."""
    candidates = [
        {"brand": "Apple", "color": "Black"},
        {"brand": "Apple", "color": "Red"},
        {"brand": "Apple", "color": "Blue"},
    ]
    scores = dict(_akinator.compute_discriminative_attributes(candidates))
    assert scores["brand"] == 0.0, "même valeur partout → entropie 0"
    assert scores["color"] == pytest.approx(1.0), "toutes valeurs uniques → entropie 1"


def test_select_next_observation_prend_le_plus_discriminant():
    """L'observation proposée doit porter sur l'attribut à plus forte entropie."""
    candidates = [
        {"brand": "Apple", "capacity": "128 GB"},
        {"brand": "Apple", "capacity": "256 GB"},
    ]
    obs = _akinator.select_next_observation(candidates)
    assert obs is not None
    assert obs.attribute == "capacity"
    assert 0.0 < obs.discriminative_score <= 1.0
    assert obs.candidates_count == 2


def test_select_next_observation_epuisement_renvoie_none():
    """Quand tous les attributs discriminants ont déjà été demandés → None
    (mode dégradé 'produit non identifié', cf. golden_rules Akinator)."""
    candidates = [
        {"capacity": "128 GB"},
        {"capacity": "256 GB"},
    ]
    obs = _akinator.select_next_observation(candidates, already_asked_attributes={"capacity"})
    assert obs is None


def test_select_next_observation_candidats_vides():
    """Liste vide → None, pas d'exception."""
    assert _akinator.select_next_observation([]) is None

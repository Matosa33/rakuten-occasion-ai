"""Tests du recouvrement texte-vendeur ↔ cible (Cycle 34.3, garde-fou anti-fuite)."""

from __future__ import annotations

from src.retrieval.annotation_overlap import compute_overlap


def test_identique_est_recouvrant():
    ov = compute_overlap("iPhone 13 128 Go", "iPhone 13 128 Go")
    assert ov["substring"] is True and ov["is_overlap"] is True and ov["jaccard"] == 1.0


def test_substring_est_recouvrant():
    # le texte vendeur est inclus dans la cible (accents/casse ignorés)
    ov = compute_overlap("redmi note 10 pro", "Xiaomi Redmi Note 10 Pro")
    assert ov["substring"] is True and ov["is_overlap"] is True


def test_disjoint_non_recouvrant():
    ov = compute_overlap("Télé", "MSI GeForce RTX 4080 Super Gaming X Trio")
    assert ov["substring"] is False and ov["is_overlap"] is False and ov["jaccard"] == 0.0


def test_jaccard_partiel_sous_seuil_non_recouvrant():
    # un mot commun sur beaucoup → Jaccard bas → pas de recouvrement
    ov = compute_overlap("chargeur samsung", "Samsung Galaxy A50 Verizon Black 64GB")
    assert ov["substring"] is False and ov["is_overlap"] is False

"""Cycle 36 — le texte vendeur fait FOI (déterministe) sur le choix du candidat.

Quand le vendeur nomme un produit présent dans les candidats, on le retient sans dépendre du LLM
rapide (qui ignore parfois la consigne). Match fort exigé (≥2 tokens + ≥50 % couverture).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.api.main import _seller_text_best_match


@dataclass
class C:
    parent_asin: str
    title: str


def _cands() -> list[C]:
    return [
        C("PHILIPS", "PHILIPS Fidelio X2HR Over-Ear Open-Air Headphone 50mm"),
        C("MOMENTUM", "Sennheiser Momentum 3 Wireless Noise Cancelling Headphones"),
        C("GARMIN", "Garmin Forerunner 55 GPS Running Watch"),
    ]


def test_seller_text_pins_named_product() -> None:
    # le vendeur nomme le Momentum (≠ top-1 Philips) → on le retient
    assert _seller_text_best_match("Sennheiser Momentum 3 Wireless", _cands()) == "MOMENTUM"


def test_rtx_tokens() -> None:
    cands = [C("A", "MSI RTX 4080 16GB Gaming"), C("B", "MSI RTX 3080 10GB")]
    assert _seller_text_best_match("MSI RTX 4080 Super", cands) == "A"


def test_weak_text_no_authority() -> None:
    # texte générique (état/couleur) → pas d'autorité
    assert _seller_text_best_match("neuf noir tres bon etat", _cands()) == ""


def test_single_token_no_authority() -> None:
    assert _seller_text_best_match("sennheiser", _cands()) == ""  # 1 seul token < 2


def test_no_match_returns_empty() -> None:
    assert _seller_text_best_match("Apple iPhone 13 256GB", _cands()) == ""


def test_empty_text() -> None:
    assert _seller_text_best_match("", _cands()) == ""

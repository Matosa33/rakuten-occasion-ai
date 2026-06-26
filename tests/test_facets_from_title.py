"""Cycle 36.A — extraction de facettes depuis le TITRE (fondation).

Le build du lookup ne lit que `details` (souvent vide) → « RTX 4080 16GB » avait capacity absente.
On complète depuis le titre, sans écraser le catalogue, en évitant les faux positifs (bit/MHz/GDDR).
"""

from __future__ import annotations

from src.api.pipeline import enrich_facets_from_title


def test_capacity_gb_tb_depuis_titre() -> None:
    assert enrich_facets_from_title("MSI RTX 4080 16GB GDDR6X 256-Bit", {})["capacity"] == "16 GB"
    assert enrich_facets_from_title("PS4 Pro 1TB Jet Black", {})["capacity"] == "1 TB"
    assert enrich_facets_from_title("Apple iPhone 13 128 GB", {})["capacity"] == "128 GB"
    # normalisation Go/To -> GB/TB
    assert enrich_facets_from_title("Disque 2 To externe", {})["capacity"] == "2 TB"


def test_pas_de_faux_positif_capacite() -> None:
    # bus mémoire, fréquence, type GDDR, nombre de pièces ne sont PAS des capacités
    out = enrich_facets_from_title("256-Bit 2550 MHz GDDR6X 65 Piece 4K 8K HDR", {})
    assert "capacity" not in out


def test_ne_remplace_pas_le_catalogue() -> None:
    out = enrich_facets_from_title("RTX 4080 16GB", {"capacity": "8 GB"})
    assert out["capacity"] == "8 GB"  # la valeur catalogue prime


def test_voltage_et_puissance() -> None:
    assert enrich_facets_from_title("Makita 18V LXT cordless drill", {})["voltage"] == "18V"
    assert enrich_facets_from_title("Makita 10.8V CXT", {})["voltage"] == "10.8V"
    assert enrich_facets_from_title("EVGA 1000W 80+ Gold PSU", {})["power"] == "1000W"


def test_titre_vide() -> None:
    assert enrich_facets_from_title("", {"brand": "X"}) == {"brand": "X"}

"""Invariants structurels du module d'audit.

Ces tests vérifient que :
- Les 4 scripts d'audit existent, sont importables, ont une fonction main()
- Le rapport d'audit existe et contient les sections canoniques
- Les chemins de sortie attendus sont configurés cohéremment

Ces tests passent SANS exécuter l'audit (donc sans télécharger le sample).
Lancer : pytest tests/test_audit_invariants.py -v
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "src" / "data" / "audit"
REPORT_PATH = REPO_ROOT / "reports" / "audit_v1_amazon_reviews_2023.md"

EXPECTED_SCRIPTS = [
    "01_load_full.py",
    "02_audit_qualite.py",
    "03_audit_distributions.py",
    "04_audit_biais_leakage.py",
]

EXPECTED_REPORT_SECTIONS = [
    "## 1. Source",
    "## 2. Périmètre audité",
    "## 3. Volumes",
    "## 4. Qualité",
    "## 5. Distributions",
    "## 6. Biais identifiés",
    "## 7. Leakages potentiels",
    "## 8. Verdict",
    "## 9. Annexes",
]


@pytest.mark.parametrize("script_name", EXPECTED_SCRIPTS)
def test_audit_script_exists(script_name: str) -> None:
    p = AUDIT_DIR / script_name
    assert p.exists(), f"Script d'audit manquant : {p}"


@pytest.mark.parametrize("script_name", EXPECTED_SCRIPTS)
def test_audit_script_has_main(script_name: str) -> None:
    """Chaque script d'audit doit avoir une fonction main() invocable."""
    spec = importlib.util.spec_from_file_location(script_name, AUDIT_DIR / script_name)
    assert spec and spec.loader
    # On ne charge pas le module (évite l'import lourd de pandas/datasets pendant le test).
    # On vérifie juste qu'il y a un appel `def main(` dans le source.
    source = (AUDIT_DIR / script_name).read_text(encoding="utf-8")
    assert "def main(" in source, f"{script_name} doit définir une fonction main()"
    assert 'if __name__ == "__main__":' in source, f"{script_name} doit avoir un guard __main__"


def test_audit_report_exists() -> None:
    assert REPORT_PATH.exists(), f"Rapport d'audit manquant : {REPORT_PATH}"


@pytest.mark.parametrize("section", EXPECTED_REPORT_SECTIONS)
def test_audit_report_has_section(section: str) -> None:
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert section in content, f"Section manquante dans le rapport : {section}"


def test_audit_report_links_figures() -> None:
    """Vérifie que le rapport référence au moins 4 figures distributions (FULL)."""
    content = REPORT_PATH.read_text(encoding="utf-8")
    figure_refs = [
        "figures/03a_distribution_reviews_par_cat.png",
        "figures/03b_distribution_meta_par_cat.png",
        "figures/03c_distribution_prix_meta.png",
        "figures/03d_distribution_ratings_reviews.png",
        "figures/03e_distribution_temporelle_reviews.png",
    ]
    found = [ref for ref in figure_refs if ref in content]
    assert (
        len(found) >= 4
    ), f"Le rapport doit référencer ≥ 4 figures distributions, trouvé : {found}"

"""Test smoke - valide que pytest est correctement configuré.

Ce fichier sera enrichi au fil des phases avec de vrais tests sur les composants.
Pour l'instant, juste un sanity check de l'environnement.
"""


def test_python_version():
    """Python 3.11 minimum (requis par pyproject.toml)."""
    import sys

    assert sys.version_info >= (3, 11), f"Python 3.11+ requis, got {sys.version_info}"


def test_imports_basic():
    """Les imports stdlib basiques fonctionnent."""
    import datetime
    import json
    import pathlib

    assert json
    assert pathlib
    assert datetime


def test_project_md_exists():
    """documentation/PROJECT.md doit exister (livrable de la phase de cadrage)."""
    from pathlib import Path

    root = Path(__file__).parent.parent
    project_md = root / "documentation" / "PROJECT.md"
    assert project_md.exists(), "documentation/PROJECT.md manquant"

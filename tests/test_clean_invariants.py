"""Invariants structurels du module data/clean (sous-todo 1.2).

Ces tests vérifient que :
- Les 5 scripts d'étape existent et ont une fonction main()
- Le module __init__.py documente les 5 étapes dans l'ordre
- Les chemins de sortie sont configurés cohéremment via src.config

Ces tests passent SANS exécuter le pipeline (donc sans avoir besoin des
parquets data/raw/full/).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = REPO_ROOT / "src" / "data" / "clean"
SPLIT_DIR = REPO_ROOT / "src" / "data" / "split"

EXPECTED_CLEAN_SCRIPTS = [
    "01_join_meta_with_review_aggregates.py",
    "02_drop_sparse_columns.py",
    "03_normalize_text.py",
    "04_cap_text_lengths.py",
    "05_feature_engineering.py",
]

EXPECTED_SPLIT_SCRIPTS = [
    "01_split_stratified_groupkfold.py",
]


@pytest.mark.parametrize("script_name", EXPECTED_CLEAN_SCRIPTS)
def test_clean_script_exists(script_name: str) -> None:
    p = CLEAN_DIR / script_name
    assert p.exists(), f"Script de cleaning manquant : {p}"


@pytest.mark.parametrize("script_name", EXPECTED_CLEAN_SCRIPTS)
def test_clean_script_has_main(script_name: str) -> None:
    """Chaque script doit avoir une fonction main() invocable."""
    source = (CLEAN_DIR / script_name).read_text(encoding="utf-8")
    assert "def main(" in source, f"{script_name} doit définir une fonction main()"
    assert 'if __name__ == "__main__":' in source, f"{script_name} doit avoir un guard __main__"


@pytest.mark.parametrize("script_name", EXPECTED_SPLIT_SCRIPTS)
def test_split_script_exists(script_name: str) -> None:
    p = SPLIT_DIR / script_name
    assert p.exists(), f"Script de split manquant : {p}"


@pytest.mark.parametrize("script_name", EXPECTED_SPLIT_SCRIPTS)
def test_split_script_has_main(script_name: str) -> None:
    source = (SPLIT_DIR / script_name).read_text(encoding="utf-8")
    assert "def main(" in source, f"{script_name} doit définir une fonction main()"


def test_clean_init_documents_pipeline() -> None:
    """Le __init__.py de clean doit documenter les 5 étapes dans l'ordre."""
    init = (CLEAN_DIR / "__init__.py").read_text(encoding="utf-8")
    for script in EXPECTED_CLEAN_SCRIPTS:
        # Extraire le numéro d'étape : "01_join..." → "01"
        step_num = script.split("_")[0]
        assert step_num in init, (
            f"Étape {step_num} non documentée dans clean/__init__.py (script {script})"
        )


def test_clean_scripts_use_streaming_engine() -> None:
    """R20/D-006 : tous les .collect() lourds doivent utiliser engine="streaming".

    Pour > 100M lignes, .collect() standard OOM. Tous les scripts d'étape
    doivent passer engine="streaming" au moins une fois pour signaler
    qu'ils sont conscients du volume.
    """
    for script_name in EXPECTED_CLEAN_SCRIPTS:
        source = (CLEAN_DIR / script_name).read_text(encoding="utf-8")
        # On accepte sink_parquet (lazy équivalent) ou collect(engine="streaming")
        has_streaming = (
            'engine="streaming"' in source
            or "engine='streaming'" in source
            or "sink_parquet(" in source
        )
        assert has_streaming, (
            f"{script_name} : doit utiliser engine='streaming' ou sink_parquet "
            "pour borner le pic mémoire (cf. R20 / D-006)"
        )


def test_clean_scripts_import_from_config() -> None:
    """Tous les scripts (clean/ + split/) doivent importer leurs paths depuis
    src.config (single source of truth, R8)."""
    paths_to_check = [CLEAN_DIR / s for s in EXPECTED_CLEAN_SCRIPTS] + [
        SPLIT_DIR / s for s in EXPECTED_SPLIT_SCRIPTS
    ]
    for path in paths_to_check:
        source = path.read_text(encoding="utf-8")
        assert "from src.config import" in source, (
            f"{path.name} doit importer ses paths depuis src.config (R8 single source of truth)"
        )

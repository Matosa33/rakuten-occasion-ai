"""Tests statiques du DAG Airflow `rakuten_retrain` (Cycle 12.1, D-022).

Le DAG importe `airflow` (absent du .venv) → on ne l'IMPORTE pas. On valide son
**contrat** par analyse statique (AST + compilation) : structure, tâches, garde-fou.
Cela protège le DAG d'une casse accidentelle sans tirer la dépendance airflow.
"""

from __future__ import annotations

import ast
from pathlib import Path

DAG_PATH = (
    Path(__file__).resolve().parents[1] / "infra" / "airflow" / "dags" / "rakuten_retrain_dag.py"
)


def _source() -> str:
    assert DAG_PATH.exists(), f"DAG introuvable : {DAG_PATH}"
    return DAG_PATH.read_text(encoding="utf-8")


def test_dag_compile():
    """Le fichier DAG est un Python valide (syntaxe)."""
    src = _source()
    compile(src, str(DAG_PATH), "exec")  # lève SyntaxError si invalide
    ast.parse(src)


def test_dag_id_et_taches_presentes():
    """Le DAG expose l'id attendu et les 5 tâches du graphe (12.1 + 12.3)."""
    src = _source()
    assert 'dag_id="rakuten_retrain"' in src
    for task_id in (
        "check_new_data",
        "train_classifiers",
        "evaluate_gate",
        "promote_gate",  # 12.3 (D-024) — champion/challenger
        "reimport_bento",  # 12.3 — API hot reload (BentoML)
    ):
        assert f'task_id="{task_id}"' in src, f"tâche manquante : {task_id}"
    # dépendances chaînées (graphe complet 5 tâches)
    assert "t_check >> t_train >> t_gate >> t_promote >> t_reimport" in src


def test_retrain_modules_sont_les_tetes_cpu():
    """Le retrain cible bien M5/M2/M4 (têtes CPU portables), pas M1 FAISS/M6 (D-022)."""
    src = _source()
    for module in (
        "src.classifiers.01_tfidf_linsvc",
        "src.classifiers.03_svm",
        "src.classifiers.05_mlp",
    ):
        assert module in src, f"module retrain manquant : {module}"
    assert "src.classifiers.02_knn" not in src  # M1 = FAISS, hors boucle planifiée


def test_garde_fou_qualite_defini():
    """Un seuil F1 garde-fou est défini (R15 : pas de régression silencieuse)."""
    src = _source()
    tree = ast.parse(src)
    gate = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "F1_GATE":
                    gate = node.value.value
    assert gate is not None, "F1_GATE non défini"
    assert 0.0 < gate < 1.0, f"seuil F1_GATE hors bornes : {gate}"

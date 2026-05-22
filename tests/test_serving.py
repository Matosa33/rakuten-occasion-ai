"""Tests statiques du serving BentoML (Cycle 12.2, D-022).

`service.py` appelle `bentoml.models.get(...)` au niveau module → l'importer exige
le modèle dans le store BentoML. On valide donc le **contrat** par analyse statique
(AST + compilation), sans dépendre d'un store peuplé ni du runtime bentoml.
"""

from __future__ import annotations

from pathlib import Path

SERVING = Path(__file__).resolve().parents[1] / "src" / "serving"
SERVICE = SERVING / "service.py"
IMPORT_MODEL = SERVING / "import_model.py"


def test_fichiers_serving_compilent():
    """service.py et import_model.py sont du Python valide."""
    for path in (SERVICE, IMPORT_MODEL):
        assert path.exists(), f"manquant : {path}"
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_service_expose_classify_et_modele():
    """Le service BentoML déclare l'endpoint classify sur le modèle du store."""
    src = SERVICE.read_text(encoding="utf-8")
    assert "@bentoml.service" in src
    assert "@bentoml.api" in src
    assert "def classify(self, texts: list[str])" in src
    assert 'bentoml.models.get("rakuten_classifier:latest")' in src
    # confiance retournée (pas seulement la catégorie)
    assert "confidence" in src and "predict_proba" in src


def test_import_model_pointe_sur_production():
    """L'import lit bien le modèle @Production du Registry MLflow (D-020)."""
    src = IMPORT_MODEL.read_text(encoding="utf-8")
    assert 'REGISTRY_MODEL = "rakuten-classifier"' in src
    assert "@Production" in src
    assert "bentoml.mlflow.import_model" in src

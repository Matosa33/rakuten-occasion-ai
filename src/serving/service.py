"""Service BentoML servant le classifieur `@Production` (Cycle 12.2, D-022).

Découplage API ↔ modèle (R5/D-020) : le service charge le pipeline sklearn du
modèle importé depuis le Registry MLflow (`src.serving.import_model`), sans coder
en dur de chemin de fichier. Métriques **Prometheus natives** exposées sur `/metrics`
(compteurs requêtes, latence, in-progress — fournis par BentoML).

`bentoml.mlflow.load_model` renvoie un pyfunc (predict seul) ; on charge donc le
pipeline sklearn natif (`predict_proba`) depuis le dossier MLflow du store BentoML
pour retourner une **confiance** en plus de la catégorie.

Lancer (après import) :

    bentoml serve src/serving/service.py:RakutenClassifier   # API :3000, /metrics
"""

from __future__ import annotations

import bentoml
import numpy as np
from bentoml.mlflow import MLFLOW_MODEL_FOLDER

BENTO_MODEL = bentoml.models.get("rakuten_classifier:latest")


@bentoml.service(
    name="rakuten_classifier",
    resources={"cpu": "1"},
    traffic={"timeout": 30},
)
class RakutenClassifier:
    """Classifie un texte produit (titre + description) en catégorie + confiance."""

    bento_model = BENTO_MODEL

    def __init__(self) -> None:
        import mlflow.sklearn

        # Pipeline sklearn natif (predict_proba) depuis le dossier MLflow du store.
        self.model = mlflow.sklearn.load_model(self.bento_model.path_of(MLFLOW_MODEL_FOLDER))
        self.classes = [str(c) for c in self.model.classes_]

    @bentoml.api
    def classify(self, texts: list[str]) -> list[dict]:
        """Prédit la catégorie + confiance pour chaque texte produit."""
        proba = self.model.predict_proba(texts)
        results: list[dict] = []
        for row in proba:
            idx = int(np.argmax(row))
            results.append({"category": self.classes[idx], "confidence": round(float(row[idx]), 4)})
        return results

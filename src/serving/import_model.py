"""Importe le modèle `@Production` du Registry MLflow dans le store BentoML (Cycle 12.2).

À lancer AVANT `bentoml serve` (le service référence `rakuten_category_classifier:latest`
dans le store BentoML). Réexécuter après chaque promotion `@Production` (la boucle
fermée 12.3 le déclenchera automatiquement).

    python -m src.serving.import_model
"""

from __future__ import annotations

import logging

import bentoml.mlflow
import mlflow

from src.config import REPO_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MLFLOW_URI = f"sqlite:///{(REPO_ROOT / 'mlflow.db').as_posix()}"
REGISTRY_MODEL = "rakuten-category-classifier"  # nom dans le Registry MLflow (D-020)
BENTO_NAME = "rakuten_category_classifier"  # nom dans le store BentoML (underscore)


def main() -> None:
    mlflow.set_tracking_uri(MLFLOW_URI)
    source = f"models:/{REGISTRY_MODEL}@Production"
    log.info("Import %s → bento '%s'…", source, BENTO_NAME)
    model = bentoml.mlflow.import_model(BENTO_NAME, source)
    log.info("✓ Modèle importé dans le store BentoML : %s", model.tag)


if __name__ == "__main__":
    main()

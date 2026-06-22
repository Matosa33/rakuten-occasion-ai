"""Configuration centralisée du projet.

Source unique de vérité pour les chemins absolus, seeds et paramètres
globaux. Tous les scripts (data, encoders, classifiers, retrieval, vlm,
llm, pricing, api, mlops, observability) importent depuis ici plutôt
que de redéfinir leurs propres constantes.

Convention :
- Tous les chemins sont absolus, calculés depuis REPO_ROOT.
- Aucun chemin absolu hardcodé hors de ce fichier.
- Les seeds sont fixées globalement (R3 anti-leakage, R8 reproductibilité).
"""

from __future__ import annotations

import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Racines
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """Charge `.env` (gitignored, R2/R5) dans os.environ si présent.

    Loader minimal sans dépendance externe : KEY=VALUE par ligne, ignore
    commentaires (#) et lignes vides. Ne surcharge pas une var déjà définie
    dans l'env (priorité à l'env système).
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

DATA_DIR = REPO_ROOT / "data"
DATA_RAW = DATA_DIR / "raw"
DATA_RAW_FULL = DATA_RAW / "full"
DATA_RAW_FULL_REVIEWS = DATA_RAW_FULL / "reviews"
DATA_RAW_FULL_META = DATA_RAW_FULL / "meta"
DATA_PROCESSED = DATA_DIR / "processed"  # P02 sortie cleaning + split
DATA_PROCESSED_PRODUCTS = DATA_PROCESSED / "products"  # product-level enrichi (M1-M8 carburant)
DATA_PROCESSED_REVIEWS_INDEX = DATA_PROCESSED / "reviews_index"  # index split-aware (RAG Cycle 6)
DATA_PROCESSED_INTERMEDIATE = (
    DATA_PROCESSED / "intermediate"
)  # parquets intermédiaires entre étapes 01..05
DATA_EMBEDDINGS = DATA_DIR / "embeddings"  # P03 sortie encoders
DATA_INDEX = DATA_DIR / "index"  # P05 sortie FAISS
DATA_MODELS = DATA_DIR / "models"  # P04+ artefacts entraînés (sklearn, etc.)

REPORTS_DIR = REPO_ROOT / "reports"
REPORTS_AUDIT = REPORTS_DIR / "01_audit"
REPORTS_CLEANING = REPORTS_DIR / "02_cleaning"
REPORTS_EMBEDDINGS = REPORTS_DIR / "03_embeddings"
REPORTS_CLASSIFIERS = REPORTS_DIR / "04_classifiers_bench"
REPORTS_RETRIEVAL = REPORTS_DIR / "05_retrieval"
REPORTS_VLM = REPORTS_DIR / "06_vlm_eval"
REPORTS_RAG = REPORTS_DIR / "07_rag_eval"
REPORTS_PRICING = REPORTS_DIR / "08_pricing"
REPORTS_EXPLAIN = REPORTS_DIR / "09_explainability"

NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
DOCS_DIR = REPO_ROOT / "docs"

# ─────────────────────────────────────────────────────────────────────────────
# Reproductibilité
# ─────────────────────────────────────────────────────────────────────────────

SEED = 42  # R8 — seed unique partagée par tous les sous-processus

# ─────────────────────────────────────────────────────────────────────────────
# Périmètre données — re-export depuis le package audit (D-008 single source of truth)
# ─────────────────────────────────────────────────────────────────────────────

from src.data.audit import CATEGORIES, COMPLEX_COLS_TO_DROP  # noqa: E402

__all__ = [
    "REPO_ROOT",
    "DATA_DIR",
    "DATA_RAW",
    "DATA_RAW_FULL",
    "DATA_RAW_FULL_REVIEWS",
    "DATA_RAW_FULL_META",
    "DATA_PROCESSED",
    "DATA_PROCESSED_PRODUCTS",
    "DATA_PROCESSED_REVIEWS_INDEX",
    "DATA_PROCESSED_INTERMEDIATE",
    "DATA_EMBEDDINGS",
    "DATA_INDEX",
    "DATA_MODELS",
    "REPORTS_DIR",
    "REPORTS_AUDIT",
    "REPORTS_CLEANING",
    "REPORTS_EMBEDDINGS",
    "REPORTS_CLASSIFIERS",
    "REPORTS_RETRIEVAL",
    "REPORTS_VLM",
    "REPORTS_RAG",
    "REPORTS_PRICING",
    "REPORTS_EXPLAIN",
    "NOTEBOOKS_DIR",
    "DOCS_DIR",
    "SEED",
    "CATEGORIES",
    "COMPLEX_COLS_TO_DROP",
]

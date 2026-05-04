"""Cycle 9.1 — FastAPI app : pipeline RAG-grounded en endpoint.

Endpoints
---------
- `GET /health` — version, modèles chargés
- `POST /identify` — image vendeur → top-K candidats + VLM validation + Akinator si ambig
- `POST /price` — produit identifié + condition → suggestion prix L1-L4
- `POST /describe` — produit identifié + condition → titre + description grounded RAG

Lifespan
--------
Au démarrage : charge en mémoire les modèles (FAISS index, M5 TF-IDF,
M8 pricing, prompt templates). Au shutdown : libère.

Pattern asynchrone (Cycle 9.3) : `aiohttp` pour appels VLM/LLM externes,
`asyncio.Semaphore(8)` pour throttler les appels OpenRouter.

Lance :

    uvicorn src.api.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from src.api.schemas import (
    DescribeRequest,
    DescribeResponse,
    HealthResponse,
    IdentifyRequest,
    IdentifyResponse,
    PriceRequest,
    PriceResponse,
)
from src.config import DATA_INDEX, DATA_MODELS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Singleton state (rempli au lifespan startup, consommé par les endpoints)
APP_STATE: dict[str, Any] = {
    "faiss_index": None,
    "m5_tfidf": None,
    "m8_pricing": None,
    "vlm_validator": None,
    "llm_writer": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hot loading des modèles au démarrage, free au shutdown."""
    log.info("=== Lifespan startup : chargement modèles ===")

    # FAISS index (lazy : seulement si fichier dispo)
    faiss_path = DATA_INDEX / "text_arctic_hnsw.index"
    if faiss_path.exists():
        try:
            import faiss

            APP_STATE["faiss_index"] = faiss.read_index(str(faiss_path))
            APP_STATE["faiss_index"].hnsw.efSearch = 64
            log.info("  FAISS HNSW chargé : %d vecteurs", APP_STATE["faiss_index"].ntotal)
        except ImportError:
            log.warning("  faiss non installé → /identify renverra 503")
    else:
        log.warning("  faiss index absent → /identify renverra 503")

    # M5 TF-IDF (fallback texte)
    m5_path = DATA_MODELS / "m5_tfidf_linsvc_v1.joblib"
    if m5_path.exists():
        import joblib

        APP_STATE["m5_tfidf"] = joblib.load(m5_path)
        log.info("  M5 TF-IDF chargé")

    # M8 Pricing (config algorithmique)
    m8_path = DATA_MODELS / "m8_pricing_v1.joblib"
    if m8_path.exists():
        import joblib

        APP_STATE["m8_pricing"] = joblib.load(m8_path)
        log.info("  M8 Pricing config chargée")

    # VLM + LLM : à instancier en Cycle 9.3 (OpenRouter via aiohttp)
    log.info("  VLM/LLM clients : à wirer en Cycle 9.3 (OpenRouter)")

    log.info("=== Lifespan ready ===")
    yield
    log.info("=== Lifespan shutdown ===")
    APP_STATE.clear()


app = FastAPI(
    title="Rakuten AI Assistant — RAG-grounded",
    description="Pipeline d'identification + pricing + rédaction pour vendeurs particuliers",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="0.1.0",
        models_loaded={
            "faiss_index": APP_STATE.get("faiss_index") is not None,
            "m5_tfidf": APP_STATE.get("m5_tfidf") is not None,
            "m8_pricing": APP_STATE.get("m8_pricing") is not None,
        },
    )


@app.post("/identify", response_model=IdentifyResponse)
async def identify(req: IdentifyRequest) -> IdentifyResponse:
    """Pipeline complet identification : retrieval → VLM → Akinator."""
    if APP_STATE.get("faiss_index") is None:
        raise HTTPException(503, "FAISS index pas chargé. Lance Cycle 2.4 d'abord.")
    raise HTTPException(501, "Endpoint non implémenté. Cf. Cycle 9.1 RUN.")


@app.post("/price", response_model=PriceResponse)
async def price(req: PriceRequest) -> PriceResponse:
    """Pricing transparent cascade L1-L4."""
    if APP_STATE.get("m8_pricing") is None:
        raise HTTPException(503, "M8 pricing pas chargé. Lance Cycle 7.1 d'abord.")
    raise HTTPException(501, "Endpoint non implémenté. Cf. Cycle 9.1 RUN.")


@app.post("/describe", response_model=DescribeResponse)
async def describe(req: DescribeRequest) -> DescribeResponse:
    """Génération titre + description grounded RAG."""
    raise HTTPException(501, "Endpoint non implémenté. Cf. Cycle 9.1 RUN.")

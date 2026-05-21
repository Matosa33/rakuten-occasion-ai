"""Cycle 9.1 — FastAPI app : pipeline RAG-grounded en endpoint.

Endpoints
---------
- `GET /health` — version, services chargés
- `POST /identify` — texte vendeur → top-K candidats + OOD + Akinator si ambig
- `POST /price` — produit identifié + condition → suggestion prix L1-L4
- `POST /describe` — produit identifié + condition → titre + description grounded RAG (Cycle 9.3b)

Lifespan
--------
Au démarrage : instancie + charge `IdentificationService` (FAISS HNSW +
métadonnées train, encodeur Arctic lazy) et `PricingService` (M8). Au
shutdown : libère.

Text-only MVP (cf. D-014) : `/identify` exploite `text_hint` encodé par
Arctic. La branche vision (image_url + SigLIP) est différée post-MVP.

Lance :

    uvicorn src.api.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from src.api.pipeline import IdentificationService, PricingService
from src.api.schemas import (
    CandidateMeta,
    DescribeRequest,
    DescribeResponse,
    HealthResponse,
    IdentifyRequest,
    IdentifyResponse,
    ObservationToRequest,
    PriceRequest,
    PriceResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Singleton state (rempli au lifespan startup, consommé par les endpoints)
APP_STATE: dict[str, Any] = {
    "identification": None,
    "pricing": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hot loading des services au démarrage, free au shutdown."""
    log.info("=== Lifespan startup : chargement services ===")

    # IdentificationService (FAISS + métadonnées train ; encodeur Arctic lazy)
    try:
        ident = IdentificationService()
        ident.load()
        APP_STATE["identification"] = ident
    except (FileNotFoundError, ImportError) as e:
        log.warning("  IdentificationService indispo : %s → /identify renverra 503", e)

    # PricingService (M8 cascade)
    try:
        pricing = PricingService()
        pricing.load()
        APP_STATE["pricing"] = pricing
    except (FileNotFoundError, ImportError) as e:
        log.warning("  PricingService indispo : %s → /price renverra 503", e)

    log.info("  VLM/LLM clients : à wirer en Cycle 9.3b (OpenRouter)")
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
    ident = APP_STATE.get("identification")
    pricing = APP_STATE.get("pricing")
    return HealthResponse(
        status="ok",
        version="0.1.0",
        models_loaded={
            "identification": ident is not None and ident.ready,
            "pricing": pricing is not None and pricing.ready,
        },
    )


@app.post("/identify", response_model=IdentifyResponse)
async def identify(req: IdentifyRequest) -> IdentifyResponse:
    """Identification retrieval-first (text-only MVP) : FAISS → OOD → Akinator."""
    ident: IdentificationService | None = APP_STATE.get("identification")
    if ident is None or not ident.ready:
        raise HTTPException(
            503, "IdentificationService indisponible. Vérifie Cycle 2.4 (index FAISS)."
        )

    query = req.text_hint.strip()
    if not query:
        raise HTTPException(
            422,
            "text_hint vide. Le MVP text-only requiert une description texte "
            "(la branche vision image_url est différée post-MVP, cf. D-014).",
        )

    result = ident.identify(query, already_observed=req.already_observed)

    next_obs = None
    if result.next_observation is not None:
        obs = result.next_observation
        next_obs = ObservationToRequest(
            attribute=obs.attribute,
            observation_type=obs.observation_type,
            instruction=obs.instruction,
            discriminative_score=obs.discriminative_score,
        )

    return IdentifyResponse(
        status=result.status,
        top_candidates=[
            CandidateMeta(
                parent_asin=c.parent_asin,
                title=c.title,
                brand=c.store,
                category=c.category,
                score=max(0.0, min(1.0, c.score)),
            )
            for c in result.candidates
        ],
        vlm_validation=None,  # Cycle 9.3b
        next_observation=next_obs,
        explanation=result.explanation,
    )


@app.post("/price", response_model=PriceResponse)
async def price(req: PriceRequest) -> PriceResponse:
    """Pricing transparent cascade L1-L4 (M8)."""
    pricing: PricingService | None = APP_STATE.get("pricing")
    if pricing is None or not pricing.ready:
        raise HTTPException(503, "PricingService indisponible. Vérifie Cycle 7.1 (M8).")

    result = pricing.suggest(
        category=req.category.value,
        condition=req.condition.value,
        age_years=req.age_years,
    )
    return PriceResponse(
        suggested_price_eur=result.suggested_price_eur,
        confidence_level=result.confidence_level,
        confidence_score=result.confidence_score,
        range_low=result.range_low,
        range_high=result.range_high,
        explanation=result.explanation,
        method=result.method,
    )


@app.post("/describe", response_model=DescribeResponse)
async def describe(req: DescribeRequest) -> DescribeResponse:
    """Génération titre + description grounded RAG via OpenRouter (Cycle 9.3b)."""
    raise HTTPException(
        501,
        "Endpoint /describe : wiring OpenRouter prévu Cycle 9.3b (nécessite OPENROUTER_API_KEY).",
    )

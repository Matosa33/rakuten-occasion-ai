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

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api import persistence
from src.api.middleware import request_id_middleware
from src.api.pipeline import DescribeService, IdentificationService, PricingService
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
    "describe": None,
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

    # DescribeService (métadonnées train ; writer OpenRouter si clé, sinon mock)
    try:
        desc = DescribeService()
        desc.load()
        APP_STATE["describe"] = desc
    except (FileNotFoundError, ImportError) as e:
        log.warning("  DescribeService indispo : %s → /describe renverra 503", e)

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

# Observabilité C14.1 (D-029) : middleware request_id + access log structuré JSON.
# Ajouté EN PREMIER → le request_id est dispo dans tous les autres middlewares
# et handlers (CORS, body parsing, etc.).
app.middleware("http")(request_id_middleware)

# Observabilité C14.2 (D-030) : Prometheus /metrics (histogram latence + counter
# requêtes + gauge in-progress = saturation 4ᵉ golden signal). Activé via env var
# `ENABLE_METRICS=true` (mise en compose `api`) — opt-in propre qui évite
# `ValueError: Duplicated timeseries` quand pytest recrée l'app : la lib leak la
# Gauge inprogress vers le REGISTRY global, donc on désactive en tests.
Instrumentator(
    should_instrument_requests_inprogress=True,
    should_respect_env_var=True,
    env_var_name="ENABLE_METRICS",
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app)

# CORS — autorise le frontend (Vite :5173) en dev. En prod, restreindre aux origines connues.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ident = APP_STATE.get("identification")
    pricing = APP_STATE.get("pricing")
    desc = APP_STATE.get("describe")
    return HealthResponse(
        status="ok",
        version="0.1.0",
        models_loaded={
            "identification": ident is not None and ident.ready,
            "pricing": pricing is not None and pricing.ready,
            "describe": desc is not None and desc.ready,
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

    # Persistence (Cycle 9.5) : trace l'identification
    top1 = result.candidates[0] if result.candidates else None
    try:
        persistence.log_identification(
            query_text=query,
            status=result.status,
            top1_parent_asin=top1.parent_asin if top1 else None,
            top1_category=top1.category if top1 else None,
            top1_score=top1.score if top1 else None,
        )
    except Exception as e:  # noqa: BLE001 — la persistance ne doit jamais casser l'API
        log.warning("Persistence log échoué (non bloquant) : %s", e)

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
                brand=c.brand,
                category=c.category,
                image_url=c.image_url,
                score=max(0.0, min(1.0, c.score)),
                price=c.price,
                category_fine=c.category_fine,
                attributes=c.attributes,
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
        catalog_price=req.catalog_price,
        knn_neighbors_prices=req.neighbor_prices or None,
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
    """Génération titre + description grounded RAG (E4 OpenRouter si clé, sinon mock D-013)."""
    desc: DescribeService | None = APP_STATE.get("describe")
    if desc is None or not desc.ready:
        raise HTTPException(
            503, "DescribeService indisponible. Vérifie le catalogue train.parquet."
        )
    try:
        result = await asyncio.to_thread(desc.describe, req.parent_asin, req.condition.value)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return DescribeResponse(
        title=result.title,
        description=result.description,
        grounding_sentences_count=result.grounding_sentences_count,
        grounding_sentences_preview=result.grounding_sentences_preview,
        parse_ok=result.parse_ok,
    )


@app.get("/history")
async def history(limit: int = 20) -> dict:
    """Cycle 9.5 — N dernières identifications historisées (traçabilité)."""
    try:
        return {"logs": persistence.recent_logs(limit=limit)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Historique indisponible : {e}") from e


@app.post("/identify/stream")
async def identify_stream(req: IdentifyRequest):
    """Cycle 9.4 — SSE : streame les étapes du pipeline pour UX progressive.

    Chaque étape = un event JSON. Le frontend (Cycle 10) affiche la
    progression (encodage → recherche → garde-fous → résultat).
    """
    ident: IdentificationService | None = APP_STATE.get("identification")
    if ident is None or not ident.ready:
        raise HTTPException(503, "IdentificationService indisponible.")
    query = req.text_hint.strip()
    if not query:
        raise HTTPException(422, "text_hint vide (MVP text-only, cf. D-014).")

    async def event_generator():
        def _sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield _sse("step", {"phase": "encoding", "message": "Encodage de la requête…"})
        await asyncio.sleep(0)
        # Le pipeline est synchrone (FAISS/Arctic) → exécuté en thread pour ne pas bloquer la loop
        result = await asyncio.to_thread(ident.identify, query, req.already_observed)
        yield _sse("step", {"phase": "retrieval", "message": "Recherche catalogue terminée."})
        yield _sse(
            "result",
            {
                "status": result.status,
                "top_candidates": [
                    {
                        "parent_asin": c.parent_asin,
                        "title": c.title,
                        "category": c.category,
                        "score": round(c.score, 4),
                    }
                    for c in result.candidates
                ],
                "explanation": result.explanation,
            },
        )
        yield _sse("done", {"ok": True})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

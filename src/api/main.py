"""FastAPI app : pipeline d'identification RAG-grounded exposé en API.

Endpoints
---------
- `POST /auth/login` - authentification (OAuth2 password) → Bearer JWT
- `POST /upload` - stocke une photo vendeur (entrée du flow photo-first)
- `GET  /uploads/{image_id}` - sert une photo (capability-URL publique)
- `GET  /health` - version, services chargés
- `POST /identify` - photos (+ texte optionnel) → top-K candidats + validation VLM + Akinator
- `POST /price` - produit identifié + état → suggestion prix (cascade L1-L4)
- `POST /describe` - produit identifié + état → titre + description grounded
- `GET  /history` - N dernières identifications (traçabilité)
- `POST /identify/stream` - SSE : étapes du pipeline en temps réel

Lifespan
--------
Au démarrage : instancie + charge `IdentificationService` (FAISS HNSW +
métadonnées train, encodeur Arctic en lazy), `PricingService` et
`DescribeService` (fail-soft : un service indisponible → 503 actionnable,
le serveur démarre quand même).

Flow photo-first : `/identify` lit les photos (extraction VLM → titre +
attributs), complétées par un texte optionnel, avant le retrieval. La
recherche visuelle directe du catalogue (SigLIP) est différée (test gated).

Lance :

    uvicorn src.api.main:app --reload
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import statistics
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from prometheus_fastapi_instrumentator import Instrumentator

from src.api import persistence, uploads
from src.api.middleware import request_id_middleware
from src.api.pipeline import DescribeService, IdentificationService, PricingService
from src.api.schemas import (
    AssembledListingOut,
    CandidateMeta,
    DescribeRequest,
    DescribeResponse,
    HealthResponse,
    IdentifyRequest,
    IdentifyResponse,
    ListingFieldOut,
    ObservationToRequest,
    PriceRequest,
    PriceResponse,
    ReasonedFacetOut,
    ReasonedIdentificationOut,
    TokenResponse,
    UploadResponse,
)
from src.auth import authenticate, create_access_token, get_current_user
from src.config import REPO_ROOT
from src.observability.logging import get_logger
from src.serving.listing_fill import assemble_listing
from src.vlm.photo_extraction import PhotoExtractionUnavailable
from src.vlm.photo_extraction import extract as extract_from_photos
from src.vlm.reasoned_identification import reason_identify
from src.vlm.validator import validate_top1

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)
# Logger structuré (structlog) pour les événements MÉTIER inspectables (issue réelle + timings LLM),
# au-delà des métriques HTTP Prometheus (C14.2) : on veut LIRE ce que fait chaque requête.
obs_log = get_logger("rakuten.api")

# Mots non discriminants du texte vendeur (état/couleur/génériques) → exclus du match d'autorité.
_SELLER_STOPWORDS = frozenset(
    {
        "neuf",
        "occasion",
        "tres",
        "bon",
        "etat",
        "avec",
        "sans",
        "pour",
        "the",
        "and",
        "les",
        "des",
        "noir",
        "noire",
        "blanc",
        "blanche",
        "gris",
        "grise",
        "rouge",
        "bleu",
        "bleue",
        "vert",
        "comme",
        "parfait",
        "tbe",
        "complet",
        "complete",
        "vends",
        "vendre",
    }
)


def _seller_text_best_match(text: str, candidates: list) -> str:
    """Texte vendeur AUTORITAIRE : s'il nomme un produit présent dans les candidats, renvoie son
    parent_asin (déterministe, indépendant du LLM qui ignore parfois la consigne).

    Match fort exigé : ≥ 2 tokens discriminants du texte présents dans le titre candidat ET ≥ 50 %
    des tokens du texte couverts. Parmi les candidats à égalité, on retient celui au prix
    REPRÉSENTATIF (le plus proche de la médiane) pour éviter une fiche à la donnée corrompue
    (ex. un même « Momentum 3 » listé à 9755 $ par erreur). "" si pas de match fort.
    """
    # On garde les tokens ≥2 car ET les NUMÉROS de modèle (même 1 chiffre : « Momentum 3 » vs « 2.0 »)
    # pour départager les variantes.
    toks = {
        t
        for t in re.split(r"[^a-z0-9]+", (text or "").lower())
        if (len(t) >= 2 or t.isdigit()) and t not in _SELLER_STOPWORDS
    }
    if len(toks) < 2:
        return ""
    scored = [(sum(1 for t in toks if t in (c.title or "").lower()), c) for c in candidates]
    best_hits = max((h for h, _ in scored), default=0)
    if best_hits < 2 or best_hits / len(toks) < 0.5:
        return ""
    tied = [c for h, c in scored if h == best_hits]
    priced = [c for c in tied if getattr(c, "price", None) and c.price > 0]
    if priced:
        med = statistics.median([c.price for c in priced])
        return min(priced, key=lambda c: abs(c.price - med)).parent_asin
    return tied[0].parent_asin


# Singleton state (rempli au lifespan startup, consommé par les endpoints)
APP_STATE: dict[str, Any] = {
    "identification": None,
    "pricing": None,
    "describe": None,
    "expected_facets": {},  # schéma fixe des facettes attendues par macro (rangement, D-041)
}

# Schéma fixe des facettes attendues par catégorie (dénominateur stable de la complétude).
EXPECTED_FACETS_PATH = REPO_ROOT / "src" / "serving" / "expected_facets.json"


def _load_expected_facets() -> dict[str, list[str]]:
    """Charge le schéma de facettes par macro (config committée). Vide si absent."""
    try:
        raw = json.loads(EXPECTED_FACETS_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, list)}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.warning("  expected_facets.json indispo (%s) → complétude sur schéma ad-hoc", e)
        return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hot loading des services au démarrage, free au shutdown."""
    log.info("=== Lifespan startup : chargement services ===")
    APP_STATE["expected_facets"] = _load_expected_facets()

    # IdentificationService (FAISS + métadonnées train ; encodeur Arctic lazy)
    try:
        ident = IdentificationService()
        ident.load()
        APP_STATE["identification"] = ident
    except (FileNotFoundError, ImportError) as e:
        log.warning("  IdentificationService indispo : %s → /identify renverra 503", e)

    # PricingService (pricing-cascade cascade)
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
    title="Rakuten AI Assistant - RAG-grounded",
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
# `ENABLE_METRICS=true` (mise en compose `api`) - opt-in propre qui évite
# `ValueError: Duplicated timeseries` quand pytest recrée l'app : la lib leak la
# Gauge inprogress vers le REGISTRY global, donc on désactive en tests.
Instrumentator(
    should_instrument_requests_inprogress=True,
    should_respect_env_var=True,
    env_var_name="ENABLE_METRICS",
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app)

# CORS - autorise le frontend (Vite :5173) en dev. En prod (build statique servi
# par nginx + proxy /api/ même-origine), CORS n'est pas sollicité. Audit 2026-06-05
# (P1) : méthodes + headers explicites (au lieu de "*") pour réduire le vecteur
# CSRF sur /auth/login public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["authorization", "content-type"],
    expose_headers=["x-request-id"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Auth (Cycle 15.1, D-032) - `/auth/login` reste PUBLIC pour pouvoir s'authentifier,
# `/health` + `/metrics` restent publics pour les sondes K8s + scrape Prometheus.
# Tous les autres endpoints métier sont protégés par `Depends(get_current_user)`.
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/auth/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:  # noqa: B008 - pattern FastAPI standard
    """OAuth2 password flow stub démo. Retourne un Bearer JWT HS256.

    `form.username` + `form.password` arrivent en `application/x-www-form-urlencoded`
    (standard OAuth2). Stub : seul `demo/demo` est valide (cf. D-032, `src/auth/users.py`).
    """
    if not authenticate(form.username, form.password):
        raise HTTPException(
            status_code=401,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(subject=form.username))


# ─────────────────────────────────────────────────────────────────────────────
# Photos vendeur (Cycle 17.1, D-035) - la photo est l'entrée du flow photo-first.
# POST protégé (vendeur connecté) ; GET public (capability-URL uuid4 non devinable,
# nécessaire pour afficher les photos dans l'annonce).
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/upload", response_model=UploadResponse)
async def upload_photo(
    file: UploadFile,
    user: str = Depends(get_current_user),  # D-032 : Bearer JWT requis
) -> UploadResponse:
    """Stocke une photo vendeur (≥ 1 obligatoire dans le flow, D-035)."""
    content = await file.read()
    try:
        image_id = uploads.save_upload(content, file.content_type or "")
    except uploads.UploadError as e:
        raise HTTPException(422, str(e)) from e
    log.info("upload by user=%s id=%s (%d o)", user, image_id, len(content))
    return UploadResponse(image_id=image_id, url=f"/uploads/{image_id}")


@app.get("/uploads/{image_id}")
async def serve_upload(image_id: str) -> FileResponse:
    """Sert une photo vendeur (annonce, préviews). Public : capability-URL."""
    path = uploads.get_upload_path(image_id)
    if path is None:
        raise HTTPException(404, "Photo introuvable")
    return FileResponse(path)


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
async def identify(
    req: IdentifyRequest,
    user: str = Depends(get_current_user),  # D-032 : Bearer JWT requis
) -> IdentifyResponse:
    """Identification retrieval-first (text-only MVP) : FAISS → OOD → Akinator."""
    log.info("identify by user=%s photos=%d", user, len(req.image_ids))
    ident: IdentificationService | None = APP_STATE.get("identification")
    if ident is None or not ident.ready:
        raise HTTPException(
            503, "Service d'identification indisponible : index de recherche non chargé."
        )

    # v3 photo-first (D-035) : les photos vendeur sont extraites par le VLM
    # (titre probable + attributs observés) → requête catalogue. Le texte
    # vendeur (optionnel) complète la requête.
    query = req.text_hint.strip()
    observed = dict(req.already_observed)
    extraction_ms = 0.0  # observabilité : temps de l'extraction VLM
    if req.image_ids:
        paths = [p for p in (uploads.get_upload_path(i) for i in req.image_ids) if p]
        if not paths:
            raise HTTPException(422, "Aucune photo valide (image_ids inconnus ou expirés).")
        _t0 = time.perf_counter()
        try:
            extraction = await asyncio.to_thread(extract_from_photos, paths)
        except PhotoExtractionUnavailable as e:
            raise HTTPException(
                503,
                "Analyse photo indisponible (clé OpenRouter absente). "
                "Décrivez le produit en texte pour continuer.",
            ) from e
        except Exception as e:  # noqa: BLE001 - VLM down ≠ flow mort si texte fourni
            if not query:
                raise HTTPException(
                    503, f"Analyse photo en échec ({e}). Réessayez ou décrivez en texte."
                ) from e
            log.warning("photo extraction échouée, fallback texte seul : %s", e)
            extraction = None
        extraction_ms = round((time.perf_counter() - _t0) * 1000, 1)
        if extraction is not None:
            query = f"{extraction.title_guess} {query}".strip()
            # Attributs observés par le VLM = observations Akinator pré-remplies.
            for k, v in extraction.attributes.items():
                observed.setdefault(k, v)

    if not query:
        raise HTTPException(
            422,
            "Aucune entrée exploitable : envoyez au moins une photo (image_ids) "
            "ou décrivez le produit (text_hint).",
        )

    result = ident.identify(query, already_observed=observed)
    candidates = list(result.candidates)

    # Identification raisonnée (Cycle 36) : le LLM JUGE le top-15 → famille + ancre prix neuf +
    # question discriminante. Best-effort, non bloquant (R15) : None si VLM indispo/échec. Calculée
    # TÔT car son choix (chosen_parent_asin) fait remonter le BON candidat en tête - fiche, prix et
    # validation portent alors sur le produit JUGÉ, pas sur le top-1 retrieval qui peut être un
    # accessoire (ex. coque iPhone). Sans elle, on garde l'ordre retrieval inchangé.
    r_paths = (
        [p for p in (uploads.get_upload_path(i) for i in req.image_ids) if p]
        if req.image_ids
        else []
    )
    ri = None
    reason_ms = 0.0
    if r_paths and candidates:
        _t0 = time.perf_counter()
        ri = await asyncio.to_thread(
            reason_identify, r_paths, candidates[:15], observed, req.text_hint
        )
        reason_ms = round((time.perf_counter() - _t0) * 1000, 1)
    # Le texte vendeur fait FOI s'il nomme un produit présent dans les candidats (déterministe,
    # indépendant du LLM rapide qui ignore parfois la consigne) ; sinon on suit le choix de la passe
    # raisonnée. Le candidat retenu remonte en tête → fiche/prix/validation portent dessus.
    seller_asin = _seller_text_best_match(req.text_hint, candidates)
    final_asin = seller_asin or (ri.chosen_parent_asin if ri is not None else "")
    if final_asin:
        idx = next((i for i, c in enumerate(candidates) if c.parent_asin == final_asin), -1)
        if idx > 0:
            candidates = [candidates[idx], *candidates[:idx], *candidates[idx + 1 :]]

    reasoned_out = None
    if ri is not None:
        reasoned_out = ReasonedIdentificationOut(
            product_family=ri.product_family,
            family_confidence=ri.family_confidence,
            chosen_parent_asin=ri.chosen_parent_asin,
            catalog_miss=ri.catalog_miss,
            reference_new_price_usd=ri.reference_new_price_usd,
            reference_new_confidence=ri.reference_new_confidence,
            ask_question=ri.ask_question,
            facet_question=ri.facet_question,
            facets=[ReasonedFacetOut(key=f.key, value=f.value, source=f.source) for f in ri.facets],
        )

    # top-1 effectif (réordonné par la passe raisonnée si disponible)
    top1 = candidates[0] if candidates else None

    # VLM validateur F0.4 (17.2, D-035) : « la photo du vendeur montre-t-elle le top-1 ? » → badge
    # de confiance visuelle. Best-effort (None si pas de photos/image catalogue/VLM down, R15).
    # Économie de latence (Cycle 36) : si la passe raisonnée a déjà tranché AVEC confiance, on
    # n'ajoute PAS ce 3ᵉ appel LLM séquentiel (reason couvre déjà le jugement de correspondance).
    reason_confident = ri is not None and ri.family_confidence >= 0.70 and not ri.catalog_miss
    vlm_validation = None
    if r_paths and top1 is not None and not reason_confident:
        catalog_img = (top1.images[0] if top1.images else "") or top1.image_url
        if catalog_img:
            cand_attrs = (
                {"brand": top1.brand, **top1.attributes} if top1.brand else dict(top1.attributes)
            )
            _t0 = time.perf_counter()
            verdict = await asyncio.to_thread(
                validate_top1, r_paths, catalog_img, top1.title, cand_attrs
            )
            validate_ms = round((time.perf_counter() - _t0) * 1000, 1)
            log.info("vlm_validate_ms=%s", validate_ms)
            if verdict is not None:
                vlm_validation = {
                    "match": verdict.match,
                    "confidence": verdict.confidence,
                    "reason": verdict.reason,
                }
    try:
        persistence.log_identification(
            query_text=query,
            status=result.status,
            top1_parent_asin=top1.parent_asin if top1 else None,
            top1_category=top1.category if top1 else None,
            top1_score=top1.score if top1 else None,
        )
    except Exception as e:  # noqa: BLE001 - la persistance ne doit jamais casser l'API
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

    # Fiche structurée du top-1 : facettes explicites + provenance + complétude (D-041).
    # C'est le « rangement à facettes » : observé (photo) > catalogue > typique-à-vérifier,
    # complétude mesurée sur le schéma FIXE de la catégorie (dénominateur stable).
    informations_cles = None
    if top1 is not None:
        expected = APP_STATE.get("expected_facets", {}).get(top1.category)
        # Complétude PAR CATÉGORIE FINE : on ne garde du schéma macro que les facettes réellement
        # pertinentes pour cette catégorie fine (présentes chez ≥1 candidat de même catégorie fine)
        # → on ne pénalise pas une enceinte pour l'absence de « capacité ».
        if expected and top1.category_fine:
            present = {
                k
                for c in candidates
                if c.category_fine == top1.category_fine
                for k in (c.attributes or {})
            }
            relevant = [f for f in expected if f in present]
            expected = (
                relevant or expected
            )  # garde-fou : si rien ne matche, on garde le schéma macro
        # OVERRIDE VENDEUR : le vendeur a nommé ce produit (≠ perception VLM/raisonné, souvent
        # mal perçu) → on bâtit la fiche sur SA fiche catalogue (fiable), en IGNORANT l'extraction
        # et le raisonné qui portaient sur un autre produit. Sinon : logique normale.
        seller_override = bool(
            seller_asin
            and top1.parent_asin == seller_asin
            and (ri is None or ri.chosen_parent_asin != seller_asin)
        )
        if seller_override:
            catalog_miss = False
            match_reliable = True  # le vendeur a explicitement confirmé ce produit
            display_leaf = top1.category_fine or result.predicted_category_fine
            observed_listing = {}  # l'« observé » VLM concernait le mauvais produit → écarté
            match_listing = dict(top1.attributes)
        else:
            # Fiabilité : score retrieval élevé OU candidat choisi par la passe raisonnée (confiant).
            # En catalog-miss, le candidat catalogue n'EST PAS le produit → ses specs ne sont pas des
            # faits (on s'appuie sur l'observé + le typique, pas sur le mauvais catalogue).
            catalog_miss = ri is not None and ri.catalog_miss
            # family_confidence = confiance FAMILLE, pas variante. Si l'IA pose une question
            # discriminante (ask_question), la variante est incertaine → specs « à vérifier ».
            match_reliable = not catalog_miss and (
                top1.score >= 0.60
                or (
                    ri is not None
                    and ri.chosen_parent_asin == top1.parent_asin
                    and ri.family_confidence >= 0.70
                    and not ri.ask_question
                )
            )
            # « Type de produit » = catégorie du produit IDENTIFIÉ (réordonné), pas le vote pollué.
            reordered = ri is not None and ri.chosen_parent_asin == top1.parent_asin
            display_leaf = (
                top1.category_fine
                if reordered and top1.category_fine
                else (result.predicted_category_fine or top1.category_fine)
            )
            # Facettes JUGÉES par l'IA → génère TOUTES les données structurées : « observed » (photo)
            # → observé ; index d'une fiche RÉELLE → catalogue (seulement si la passe concerne CE
            # produit) ; « analogy » (estimé) → NON injecté comme fait (anti-invention).
            observed_listing = dict(observed)
            match_listing = dict(top1.attributes)
            if ri is not None:
                reasoned_for_top1 = ri.chosen_parent_asin == top1.parent_asin
                for f in ri.facets:
                    if not f.value:
                        continue
                    if f.source == "observed":
                        observed_listing[f.key] = f.value  # lu sur la photo → produit réel, valide
                    elif f.source.isdigit() and reasoned_for_top1:
                        # facette d'une fiche RÉELLE : seulement si la passe concerne CE produit
                        match_listing.setdefault(f.key, f.value)
        assembled = assemble_listing(
            category_leaf=display_leaf,
            category_confidence=result.predicted_category_confidence,
            condition_label="",  # l'état (checklist vendeur) est ajouté côté front
            photo_attributes=observed_listing,  # observé VLM + facettes IA lues sur la photo
            seller_metadata=req.text_hint,
            match_brand=top1.brand,
            match_attributes=match_listing,  # catalogue top-1 + facettes IA sourcées d'une fiche
            match_reliable=match_reliable,
            expected_facets=expected,
        )
        informations_cles = AssembledListingOut(
            level=assembled.level,
            fields=[
                ListingFieldOut(name=f.name, value=f.value, source=f.source)
                for f in assembled.fields
            ],
            completeness=assembled.completeness,
            missing=assembled.missing,
        )

    # Observabilité MÉTIER (inspectable) : issue réelle de la requête + timings des appels LLM.
    obs_log.info(
        "identify_done",
        status=result.status,
        n_candidates=len(candidates),
        top1_score=round(top1.score, 4) if top1 else None,
        category_fine=result.predicted_category_fine,
        category_conf=round(result.predicted_category_confidence, 4),
        reasoned=ri is not None,
        reordered=bool(ri and top1 and ri.chosen_parent_asin == top1.parent_asin),
        catalog_miss=ri.catalog_miss if ri else None,
        anchor_usd=ri.reference_new_price_usd if ri else None,
        ask_question=ri.ask_question if ri else None,
        family_conf=round(ri.family_confidence, 3) if ri else None,
        completeness=informations_cles.completeness if informations_cles else None,
        extraction_ms=extraction_ms,
        reason_ms=reason_ms,
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
                images=c.images,
                score=max(0.0, min(1.0, c.score)),
                price=c.price,
                category_fine=c.category_fine,
                category_path=c.category_path,
                attributes=c.attributes,
            )
            for c in candidates
        ],
        vlm_validation=vlm_validation,  # F0.4 (17.2, D-035) - None si pas de photos
        next_observation=next_obs,
        explanation=result.explanation,
        predicted_category_fine=result.predicted_category_fine,
        predicted_category_confidence=result.predicted_category_confidence,
        predicted_category_path=result.predicted_category_path,
        informations_cles=informations_cles,
        reasoned=reasoned_out,
    )


@app.post("/price", response_model=PriceResponse)
async def price(
    req: PriceRequest,
    user: str = Depends(get_current_user),  # D-032 : Bearer JWT requis
) -> PriceResponse:
    """Pricing transparent cascade L1-L4 (pricing-cascade)."""
    log.info("price by user=%s", user)
    pricing: PricingService | None = APP_STATE.get("pricing")
    if pricing is None or not pricing.ready:
        raise HTTPException(503, "Service de prix indisponible : modèle de prix non chargé.")

    result = pricing.suggest(
        category=req.category.value,
        condition=req.condition.value,
        age_years=req.age_years,
        catalog_price=req.catalog_price,
        knn_neighbors_prices=req.neighbor_prices or None,
        llm_anchor_price=req.reference_new_price_usd,  # L1.5 (Cycle 36)
        llm_anchor_confidence=req.reference_new_confidence,
        # Garde-fou anti sous-éval ancré sur l'ESTIMATION IA seule (pas le prix catalogue, qui est un
        # fait déjà géré par L1) → pas de changement de comportement pour un ancien client.
        expected_order_of_magnitude=req.reference_new_price_usd,
    )
    # Observabilité métier : niveau de cascade réellement utilisé + présence d'une ancre IA.
    obs_log.info(
        "price_done",
        level=str(result.confidence_level),
        method=result.method,
        suggested_eur=result.suggested_price_eur,
        has_anchor=req.reference_new_price_usd is not None,
        category=req.category.value,
        condition=req.condition.value,
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
async def describe(
    req: DescribeRequest,
    user: str = Depends(get_current_user),  # D-032 : Bearer JWT requis
) -> DescribeResponse:
    """Génération titre + description grounded RAG (llm-writer OpenRouter si clé, sinon mock D-013)."""
    log.info("describe by user=%s", user)
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
async def history(
    limit: int = 20,
    user: str = Depends(get_current_user),  # D-032 : Bearer JWT requis
) -> dict:
    """Cycle 9.5 - N dernières identifications historisées (traçabilité)."""
    log.info("history by user=%s", user)
    try:
        return {"logs": persistence.recent_logs(limit=limit)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Historique indisponible : {e}") from e


@app.post("/identify/stream")
async def identify_stream(
    req: IdentifyRequest,
    user: str = Depends(get_current_user),  # D-032 : Bearer JWT requis
):
    """Cycle 9.4 - SSE : streame les étapes du pipeline pour UX progressive.

    Chaque étape = un event JSON. Le frontend (Cycle 10) affiche la
    progression (encodage → recherche → garde-fous → résultat).
    """
    log.info("identify/stream by user=%s", user)
    ident: IdentificationService | None = APP_STATE.get("identification")
    if ident is None or not ident.ready:
        raise HTTPException(503, "IdentificationService indisponible.")
    query = req.text_hint.strip()
    if not query:
        raise HTTPException(422, "text_hint vide : décrivez le produit en quelques mots.")

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

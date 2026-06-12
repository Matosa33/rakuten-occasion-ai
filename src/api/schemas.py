"""Cycle 9.2 — Pydantic v2 schemas pour l'API FastAPI.

Tous les contrats request/response du pipeline `/identify`, `/price`,
`/describe`, `/observe` sont définis ici. Source unique de vérité.

Conventions :
- Aucun field optional sauf si **vraiment** optional (préférer default explicite)
- Validation forte aux frontières (R3 anti-leakage : aucune donnée sans pedigree)
- Tous les enums sont str-based pour serialization JSON propre
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ConditionEnum(StrEnum):
    NEUF = "neuf"
    TRES_BON_ETAT = "tres_bon_etat"
    BON_ETAT = "bon_etat"
    CORRECT = "correct"


class CategoryEnum(StrEnum):
    ELECTRONICS = "Electronics"
    CELL_PHONES = "Cell_Phones_and_Accessories"
    VIDEO_GAMES = "Video_Games"
    TOOLS = "Tools_and_Home_Improvement"


class ConfidenceLevelEnum(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


# ─────────────────────────────────────────────────────────────────────────────
# /auth/login — JWT auth stub démo (Cycle 15.1, D-032)
# ─────────────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """Réponse standard OAuth2 password flow : Bearer token + type."""

    access_token: str = Field(
        ..., description="JWT HS256 signé, à mettre dans Authorization: Bearer"
    )
    token_type: str = Field(default="bearer", description="Type de schema (toujours 'bearer' ici)")


# ─────────────────────────────────────────────────────────────────────────────
# /upload — photos vendeur (Cycle 17.1, D-035)
# ─────────────────────────────────────────────────────────────────────────────


class UploadResponse(BaseModel):
    """Photo stockée : id (capability) + URL servable par le frontend."""

    image_id: str
    url: str = Field(..., description="URL relative GET /uploads/{image_id}")


# ─────────────────────────────────────────────────────────────────────────────
# /identify — pipeline complet (retrieval + VLM validate + Akinator si ambig)
# ─────────────────────────────────────────────────────────────────────────────


class IdentifyRequest(BaseModel):
    # v3 photo-first (D-035) : `image_ids` = photos uploadées via POST /upload.
    # L'API accepte photo(s) ET/OU texte (le frontend impose ≥ 1 photo ; l'API
    # reste tolérante pour le text-only legacy + tests). `image_url` historique
    # conservé pour compat schémas (ignoré).
    image_ids: list[str] = Field(
        default_factory=list, description="IDs des photos vendeur (POST /upload)"
    )
    image_url: str = Field(default="", description="(déprécié, ignoré)")
    text_hint: str = Field(default="", description="Texte vendeur (optionnel si photos)")
    already_observed: dict[str, str] = Field(
        default_factory=dict,
        description="Observations déjà demandées dans la session Akinator (attribut → valeur)",
    )


class CandidateMeta(BaseModel):
    parent_asin: str
    title: str
    brand: str = ""
    category: CategoryEnum
    image_url: str = ""
    images: list[str] = Field(
        default_factory=list, description="Toutes les vues catalogue (visionneuse 17.2, D-035)"
    )
    score: float = Field(..., ge=0.0, le=1.0)
    price: float | None = None  # prix catalogue USD (pour le pricing F4)
    category_fine: str = ""  # catégorie L2/L3 réelle du produit (ex: "Graphics Cards")
    category_path: str = Field(
        default="", description="Breadcrumb complet « A > B > C » (rangement marketplace, 17.4b)"
    )
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Facettes Akinator (color, capacity, brand…)"
    )


class ObservationToRequest(BaseModel):
    """Si retrieval ambig, on demande au vendeur une observation spécifique."""

    attribute: str
    observation_type: str  # back_view | label_scan | barcode_scan | …
    instruction: str
    discriminative_score: float


class IdentifyResponse(BaseModel):
    status: str = Field(..., description="identified | ambiguous | ood")
    top_candidates: list[CandidateMeta]
    vlm_validation: dict | None = None  # {match, confidence, reason}
    next_observation: ObservationToRequest | None = None
    explanation: str


# ─────────────────────────────────────────────────────────────────────────────
# /price — pricing transparent (cascade L1-L4)
# ─────────────────────────────────────────────────────────────────────────────


class PriceRequest(BaseModel):
    parent_asin: str | None = Field(None, description="ID produit identifié (None si OOD)")
    category: CategoryEnum
    condition: ConditionEnum = ConditionEnum.BON_ETAT
    age_years: float = Field(default=2.0, ge=0.0, le=50.0)
    # Contexte produit pour le pricing F4 (fourni par le front depuis /identify) :
    catalog_price: float | None = Field(
        None, description="Prix catalogue du produit identifié (USD) → L1"
    )
    neighbor_prices: list[float] = Field(
        default_factory=list, description="Prix des candidats voisins FAISS (USD) → L2"
    )


class PriceResponse(BaseModel):
    suggested_price_eur: float
    confidence_level: ConfidenceLevelEnum
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    range_low: float
    range_high: float
    explanation: str
    method: str  # catalog_meta | knn_median | category_median | fallback


# ─────────────────────────────────────────────────────────────────────────────
# /describe — LLM rédacteur grounded (RAG)
# ─────────────────────────────────────────────────────────────────────────────


class DescribeRequest(BaseModel):
    parent_asin: str
    condition: ConditionEnum = ConditionEnum.BON_ETAT


class DescribeResponse(BaseModel):
    title: str
    description: str
    grounding_sentences_count: int
    grounding_sentences_preview: list[str] = Field(
        default_factory=list, description="3 premières phrases utilisées (debug)"
    )
    parse_ok: bool


# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    models_loaded: dict[str, bool] = Field(default_factory=dict)

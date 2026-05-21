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
# /identify — pipeline complet (retrieval + VLM validate + Akinator si ambig)
# ─────────────────────────────────────────────────────────────────────────────


class IdentifyRequest(BaseModel):
    image_url: str = Field(..., description="URL ou data URI de l'image vendeur")
    text_hint: str = Field(default="", description="Texte libre du vendeur (optionnel)")
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
    score: float = Field(..., ge=0.0, le=1.0)
    price: float | None = None  # prix catalogue USD (pour le pricing F4)
    category_fine: str = ""  # catégorie L2/L3 réelle du produit (ex: "Graphics Cards")


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

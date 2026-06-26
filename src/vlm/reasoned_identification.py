"""Identification raisonnée (Cycle 36) — le LLM/VLM JUGE le top-15 du retriever.

Le retriever apporte la connaissance (top-15 fiches réelles), le VLM apporte le jugement :
à partir de la/des photo(s) vendeur + la métadonnée + les 15 fiches candidates RÉSUMÉES (texte),
il produit la FAMILLE de produit, des facettes sourcées (grounding par index de fiche), un
PRIX NEUF de référence estimé (ancré sur les prix neufs PROPRES du top-15, accessoires exclus),
et un éventuel besoin de question discriminante.

Discipline (R15/R19) : best-effort, NON bloquant. Toute défaillance (pas de clé, VLM down,
JSON inexploitable, ASIN halluciné) → `reason_identify` retourne None et le pipeline retombe sur
le classement retrieval + la cascade pricing actuelle. Le LLM ne peut JAMAIS introduire un produit
hors des 15 fiches (grounded-avant-génératif).

Coût/latence : 1 seul appel ; on envoie 1-2 photos vendeur (pas les 15 images catalogue) + les
fiches en TEXTE compact. Déterminisme repro (D-042) : température 0 + seed + reasoning off.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.observability.logging import get_logger
from src.vlm.photo_extraction import (
    VLM_MODEL,
    VLM_PROVIDER,
    VLM_REASONING,
    VLM_SEED,
    VLM_TEMPERATURE,
    _to_data_url,
    post_with_retry,
)

if TYPE_CHECKING:
    from src.api.pipeline import Candidate

_log = get_logger(__name__)

# Modèle dédié (fallback sur le VLM d'extraction). Tâche multimodale + raisonnement léger.
IDENTIFY_MODEL = os.environ.get("PHOTO_VLM_IDENTIFY_MODEL", VLM_MODEL)
IDENTIFY_MAX_TOKENS = int(os.environ.get("PHOTO_VLM_IDENTIFY_MAX_TOKENS", "700"))
MAX_CANDIDATES = 15
MAX_USER_PHOTOS = 2
TITLE_TRUNC = 140

# Mots-clés d'accessoire/bundle : leurs prix NE SONT PAS le prix du produit → exclus de l'ancre.
ACCESSORY_KEYWORDS = (
    "case", "cover", "screen protector", "charger", "cable", "strap", "band", "mount",
    "skin", "sleeve", "adapter", "bundle", "lot", "pack", "accessory", "kit",
)

IDENTIFY_PROMPT = (
    "You are an expert second-hand product appraiser. You see photo(s) of ONE used product a "
    "seller wants to list, plus the {n} closest catalog candidates retrieved by similarity search "
    "(TEXT only) and the attributes already observed.\n\n"
    "STRICT GROUNDING RULES (zero invention):\n"
    "- Decide ONLY from the candidate records below + what is visible in the seller photo(s) + the "
    "observed attributes. Do NOT use outside knowledge to assert facts.\n"
    "- Every facet you output MUST cite its source: an integer candidate index, or \"observed\" "
    "(seen on the photo), or \"analogy\" (inferred from comparable candidates when the exact "
    "product is missing).\n"
    "- For the REFERENCE NEW PRICE you MUST anchor on the new/clean prices (price_usd) of the REAL "
    "product candidates, and list the candidate indices you used in \"price_anchor_evidence\".\n"
    "- EXCLUDE from the price anchor any candidate that is an accessory or bundle (title/leaf with: "
    "case, cover, screen protector, charger, cable, strap, band, mount, skin, sleeve, adapter, "
    "bundle, lot, pack, accessory, kit). Their prices are NOT the product price.\n"
    "- If none of the candidates is the actual product (catalog miss), set \"catalog_miss\": true, "
    "estimate the reference new price BY ANALOGY from the closest comparable real products, and "
    "still fill \"price_anchor_evidence\" with the analog indices.\n"
    "- If a single discriminating facet (capacity, color, exact model variant) would change the "
    "family or the price, set \"ask_question\": true and put ONE short buyer-facing question in "
    "\"facet_question\".\n\n"
    "CANDIDATES (index | summary):\n{candidate_lines}\n\n"
    "OBSERVED ON PHOTO (VLM) + SELLER TEXT:\n{observed_block}\n\n"
    "Reply in STRICT JSON, no markdown, exactly this shape:\n"
    '{{"product_family": "<short product family/model>",\n'
    ' "family_confidence": 0.0,\n'
    ' "chosen_parent_asin": "<parent_asin of the best-matching candidate, or \'\' if catalog miss>",\n'
    ' "catalog_miss": false,\n'
    ' "reference_new_price_usd": 0,\n'
    ' "reference_new_confidence": 0.0,\n'
    ' "price_anchor_evidence": [0],\n'
    ' "ask_question": false,\n'
    ' "facet_question": "",\n'
    ' "facets": [{{"key": "capacity", "value": "16 GB", "source": "0"}}]}}'
)


@dataclass
class SourcedFacet:
    """Une facette + sa provenance ('observed' | 'analogy' | index de fiche stringifié)."""

    key: str
    value: str
    source: str


@dataclass
class ReasonedIdentification:
    """Jugement du LLM sur le top-15 (tout grounded sur les fiches réelles + l'observé)."""

    product_family: str
    family_confidence: float
    chosen_parent_asin: str
    catalog_miss: bool
    reference_new_price_usd: float | None
    reference_new_confidence: float
    price_anchor_evidence: list[int]
    ask_question: bool
    facet_question: str
    facets: list[SourcedFacet] = field(default_factory=list)
    raw: str = ""


def summarize_candidate(idx: int, c: Candidate) -> str:
    """Sérialise UNE fiche en une ligne texte compacte et stable pour le prompt.

    L'index `idx` est l'evidence pointer : le modèle doit citer les index utilisés pour l'ancre.
    """
    title = (c.title or "")[:TITLE_TRUNC]
    parts = [f"[{idx}] {title}"]
    if c.brand:
        parts.append(f"brand={c.brand}")
    if c.category_fine:
        parts.append(f"leaf={c.category_fine}")
    attrs = c.attributes or {}
    attr_str = ",".join(
        f"{k}={v}" for k, v in attrs.items() if k not in ("brand", "category") and v
    )
    if attr_str:
        parts.append(f"attrs:{attr_str}")
    if c.price and c.price > 0:
        parts.append(f"price_usd={c.price:.2f}")
    parts.append(f"asin={c.parent_asin}")
    return " | ".join(parts)


def build_identify_prompt(
    candidates: list[Candidate], observed: dict[str, str], seller_text: str
) -> str:
    """Assemble le prompt complet (fiches résumées + observé)."""
    cands = candidates[:MAX_CANDIDATES]
    lines = "\n".join(summarize_candidate(i, c) for i, c in enumerate(cands))
    obs_parts = [f"{k}={v}" for k, v in (observed or {}).items() if v]
    if seller_text:
        obs_parts.append(f"seller_text: {seller_text}")
    observed_block = "; ".join(obs_parts) if obs_parts else "(none)"
    return IDENTIFY_PROMPT.format(
        n=len(cands), candidate_lines=lines, observed_block=observed_block
    )


def _clamp01(x: object) -> float:
    try:
        return max(0.0, min(1.0, float(x)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _loads_tolerant(raw: str) -> object:
    """Parse JSON tolérant (JSON pur, fences markdown, 1er objet {...}) — calque sur _parse VLM."""
    candidates = [raw]
    if "```" in raw:
        candidates.insert(0, raw.split("```")[1].removeprefix("json").strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    for cand in candidates:
        try:
            return json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _parse(raw: str, candidates: list[Candidate]) -> ReasonedIdentification | None:
    """Parse + VALIDE/clamp la sortie LLM. None si inexploitable.

    Garde-fous : confidence ∈ [0,1] ; ASIN halluciné → retombe sur le top-1 (grounded) ;
    evidence filtrée [0..n-1] ; ancre jetée si non groundée (pas d'evidence hors catalog-miss) ;
    facette à source invalide jetée (jamais d'affirmation non sourcée).
    """
    data = _loads_tolerant(raw)
    if not isinstance(data, dict):
        return None
    n = len(candidates)
    asins = {c.parent_asin for c in candidates}

    chosen = str(data.get("chosen_parent_asin") or "")
    if chosen not in asins:
        chosen = candidates[0].parent_asin if candidates else ""  # R19 : top-1 retrieval

    catalog_miss = bool(data.get("catalog_miss"))
    evidence = [
        i for i in (data.get("price_anchor_evidence") or []) if isinstance(i, int) and 0 <= i < n
    ]

    ref = data.get("reference_new_price_usd")
    try:
        ref_val: float | None = float(ref) if ref is not None else None
    except (TypeError, ValueError):
        ref_val = None
    if ref_val is not None and ref_val <= 0:
        ref_val = None
    # Ancre non groundée (aucune fiche citée hors catalog-miss) → on la rejette.
    if ref_val is not None and not evidence and not catalog_miss:
        ref_val = None

    facets: list[SourcedFacet] = []
    for f in data.get("facets") or []:
        if not isinstance(f, dict):
            continue
        key = str(f.get("key") or "").strip()
        val = str(f.get("value") or "").strip()
        src = str(f.get("source") or "").strip()
        if not key or not val:
            continue
        valid_src = src in ("observed", "analogy") or (src.isdigit() and 0 <= int(src) < n)
        if not valid_src:
            continue
        facets.append(SourcedFacet(key=key, value=val, source=src))

    return ReasonedIdentification(
        product_family=str(data.get("product_family") or "")[:120],
        family_confidence=_clamp01(data.get("family_confidence")),
        chosen_parent_asin=chosen,
        catalog_miss=catalog_miss,
        reference_new_price_usd=ref_val,
        reference_new_confidence=_clamp01(data.get("reference_new_confidence")),
        price_anchor_evidence=evidence,
        ask_question=bool(data.get("ask_question")),
        facet_question=str(data.get("facet_question") or "")[:200],
        facets=facets,
        raw=raw,
    )


def _anchor_price_usd(ri: ReasonedIdentification | None) -> tuple[float | None, float]:
    """Extrait (prix neuf de référence USD, confiance) d'un jugement exploitable, sinon (None, 0)."""
    if ri is None or ri.reference_new_price_usd is None:
        return None, 0.0
    return ri.reference_new_price_usd, ri.reference_new_confidence


def reason_identify(
    user_photo_paths: list[Path],
    candidates: list[Candidate],
    observed: dict[str, str] | None = None,
    seller_text: str = "",
) -> ReasonedIdentification | None:
    """Passe d'identification raisonnée. None (best-effort) si indisponible/échec — JAMAIS bloquant.

    Args:
        user_photo_paths: photos vendeur locales (1-2 envoyées en data-url).
        candidates: top-K du retriever (on garde les 15 premières, fiches en texte).
        observed: attributs observés par le VLM d'extraction (+ on ajoute le texte vendeur).
        seller_text: précisions texte du vendeur.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key or not candidates:
        return None
    try:
        prompt = build_identify_prompt(candidates, observed or {}, seller_text)
        content: list[dict] = [{"type": "text", "text": prompt}]
        for p in list(user_photo_paths)[:MAX_USER_PHOTOS]:
            content.append({"type": "image_url", "image_url": {"url": _to_data_url(Path(p))}})
        payload: dict = {
            "model": IDENTIFY_MODEL,
            "max_tokens": IDENTIFY_MAX_TOKENS,
            "temperature": VLM_TEMPERATURE,
            "seed": VLM_SEED,
            "messages": [{"role": "user", "content": content}],
        }
        if VLM_PROVIDER:
            payload["provider"] = {"order": [VLM_PROVIDER], "allow_fallbacks": False}
        if VLM_REASONING == "off":
            payload["reasoning"] = {"enabled": False}
        r = post_with_retry(payload, key)
        msg = r.json()["choices"][0]["message"]
        raw = (msg.get("content") or msg.get("reasoning") or "").strip()
        if not raw:
            _log.warning("reasoned_identify_empty")
            return None
        ri = _parse(raw, candidates)
        if ri is None:
            _log.warning("reasoned_identify_parse_failed", raw_preview=raw[:120])
        return ri
    except Exception as e:  # noqa: BLE001 — best-effort, ne doit JAMAIS casser /identify (R15)
        _log.warning("reasoned_identify_failed", error=str(e))
        return None

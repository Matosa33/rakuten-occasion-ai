"""VLM validateur top-1 (F0.4, Cycle 17.2, D-035 — spécifié dès D-009).

« La photo du vendeur montre-t-elle bien le candidat top-1 ? » Le VLM compare
les photos UTILISATEUR à l'image CATALOGUE du candidat → `{match, confidence,
reason}`. Garde-fou anti-hallucination : un badge de confiance visuelle dans
l'UI, jamais une décision automatique (l'humain valide, R19).

Dégradation propre : toute erreur (pas de clé, VLM down, image catalogue
morte) → `None` — la validation est un BONUS, jamais un bloqueur du flow.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from src.observability.logging import get_logger
from src.vlm.photo_extraction import VLM_REASONING, _to_data_url, post_with_retry

_log = get_logger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Aligné sur l'extracteur champion (D-043) par défaut ; surchargeable séparément pour
# expérimenter le validateur sans toucher à l'extraction.
VLM_MODEL = os.environ.get(
    "PHOTO_VLM_VALIDATOR_MODEL", os.environ.get("PHOTO_VLM_MODEL", "qwen/qwen3.5-flash-02-23")
)
TIMEOUT_SEC = 60
MAX_USER_PHOTOS = 2  # le match se joue sur la vue principale, pas besoin de tout
# Facettes qui distinguent les VARIANTES d'un même modèle (à vérifier si visibles).
_VARIANT_KEYS = ("brand", "model", "capacity", "color", "size")

VALIDATION_PROMPT = (
    "First image(s): a seller's photo(s) of a second-hand product. "
    "Last image: a catalog picture of the product '{title}'. "
    "{attrs}"
    "Do the seller's photos show the SAME product model as the catalog picture? "
    "Ignore condition, background and accessories. Judge the product MODEL, and the listed "
    "attributes ONLY if they are clearly visible on the seller's photos (do not assume). "
    'Reply in strict JSON: {{"match": true/false, "confidence": 0.0-1.0, '
    '"reason": "<one short sentence>"}}'
)


@dataclass
class VLMValidation:
    """Verdict de correspondance visuelle photo vendeur ↔ candidat catalogue."""

    match: bool
    confidence: float
    reason: str


def _attrs_hint(candidate_attributes: dict[str, str] | None) -> str:
    """Phrase d'attributs attendus (marque/modèle/capacité…) pour vérifier la VARIANTE."""
    if not candidate_attributes:
        return ""
    pairs = [f"{k}={candidate_attributes[k]}" for k in _VARIANT_KEYS if candidate_attributes.get(k)]
    return f"Expected attributes of the catalog product: {', '.join(pairs)}. " if pairs else ""


def validate_top1(
    user_photo_paths: list[Path],
    catalog_image_url: str,
    candidate_title: str,
    candidate_attributes: dict[str, str] | None = None,
) -> VLMValidation | None:
    """Compare photos vendeur ↔ image catalogue du top-1. None si indisponible.

    `candidate_attributes` (marque/modèle/capacité/couleur/taille du candidat) est injecté
    dans le prompt pour que le VLM vérifie la VARIANTE si elle est visible, pas seulement le
    modèle générique (utile en tech/électro où les variantes se ressemblent).
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key or not catalog_image_url or not user_photo_paths:
        return None

    prompt = VALIDATION_PROMPT.format(
        title=candidate_title[:120], attrs=_attrs_hint(candidate_attributes)
    )
    content: list[dict] = [{"type": "text", "text": prompt}]
    for p in user_photo_paths[:MAX_USER_PHOTOS]:
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(p)}})
    content.append({"type": "image_url", "image_url": {"url": catalog_image_url}})

    payload: dict = {
        "model": VLM_MODEL,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": content}],
    }
    if VLM_REASONING == "off":  # cohérent avec l'extraction : pas de chaîne de raisonnement
        payload["reasoning"] = {"enabled": False}
    try:
        r = post_with_retry(payload, key, timeout=TIMEOUT_SEC)
        msg = r.json()["choices"][0]["message"]
        raw = (msg.get("content") or msg.get("reasoning") or "").strip()
        return _parse(raw) if raw else None
    except Exception as e:  # noqa: BLE001 — la validation est best-effort (R15)
        _log.warning("vlm_validation_failed", error=str(e))
        return None


def _parse(raw: str) -> VLMValidation | None:
    """Parse tolérant (JSON pur / fences / noyé) — None si inexploitable."""
    candidates = [raw]
    if "```" in raw:
        candidates.insert(0, raw.split("```")[1].removeprefix("json").strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    for cand in candidates:
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and "match" in data:
            try:
                return VLMValidation(
                    match=bool(data["match"]),
                    confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
                    reason=str(data.get("reason", ""))[:200],
                )
            except (TypeError, ValueError):
                continue
    _log.warning("vlm_validation_parse_failed", raw_preview=raw[:100])
    return None

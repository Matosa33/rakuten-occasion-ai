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

import requests

from src.observability.logging import get_logger
from src.vlm.photo_extraction import _to_data_url

_log = get_logger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VLM_MODEL = os.environ.get("PHOTO_VLM_MODEL", "google/gemma-4-31b-it")
TIMEOUT_SEC = 60
MAX_USER_PHOTOS = 2  # le match se joue sur la vue principale, pas besoin de tout

VALIDATION_PROMPT = (
    "First image(s): a seller's photo(s) of a second-hand product. "
    "Last image: a catalog picture of the product '{title}'. "
    "Do the seller's photos show the SAME product model as the catalog picture? "
    "Ignore condition, background and accessories — judge the product model only. "
    'Reply in strict JSON: {{"match": true/false, "confidence": 0.0-1.0, '
    '"reason": "<one short sentence>"}}'
)


@dataclass
class VLMValidation:
    """Verdict de correspondance visuelle photo vendeur ↔ candidat catalogue."""

    match: bool
    confidence: float
    reason: str


def validate_top1(
    user_photo_paths: list[Path], catalog_image_url: str, candidate_title: str
) -> VLMValidation | None:
    """Compare photos vendeur ↔ image catalogue du top-1. None si indisponible."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key or not catalog_image_url or not user_photo_paths:
        return None

    content: list[dict] = [
        {"type": "text", "text": VALIDATION_PROMPT.format(title=candidate_title[:120])}
    ]
    for p in user_photo_paths[:MAX_USER_PHOTOS]:
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(p)}})
    content.append({"type": "image_url", "image_url": {"url": catalog_image_url}})

    try:
        r = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": VLM_MODEL,
                "max_tokens": 120,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=TIMEOUT_SEC,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        return _parse(raw)
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

"""Extraction produit depuis photo(s) vendeur via VLM OpenRouter (Cycle 17.1, D-035).

Le VLM transforme les photos en requête catalogue (titre probable) + attributs
observés. Le retrieval IDENTIFIE, le VLM OBSERVE (R19 grounded-avant-génératif).
Prompt validé par le PoC 17.0 (format « titre Amazon » : same-model@5 ≈ 52 %
en conditions réelles, `reports/11_poc_photo/poc_photo_bench.md`).

Dégradation propre (D-013) : sans OPENROUTER_API_KEY, `extract()` lève
`PhotoExtractionUnavailable` — le caller (API) renvoie un 503 explicite invitant
à la saisie texte (le flow text-only reste fonctionnel).
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import requests

from src.observability.logging import get_logger

_log = get_logger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VLM_MODEL = os.environ.get("PHOTO_VLM_MODEL", "google/gemma-4-31b-it")
# Déterminisme (repro protocole D-042) : température 0 + seed fixe. Provider épinglable
# (fixe la quantization) via env `PHOTO_VLM_PROVIDER` — sinon routing OpenRouter par défaut.
VLM_TEMPERATURE = float(os.environ.get("PHOTO_VLM_TEMPERATURE", "0"))
VLM_SEED = int(os.environ.get("PHOTO_VLM_SEED", "42"))
VLM_PROVIDER = os.environ.get("PHOTO_VLM_PROVIDER", "")
TIMEOUT_SEC = 90
MAX_PHOTOS_PER_CALL = 4  # toutes les vues passent dans UN appel (moins cher, contexte commun)

_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
}

# Prompt v2 du PoC (titre catalogue) + extraction structurée des attributs
# observables → pré-remplissage des facettes Akinator (D-035 décision 2b).
EXTRACTION_PROMPT = (
    "You are looking at photo(s) of ONE second-hand product a seller wants to list. "
    "Reply in strict JSON with two fields:\n"
    '{"title": "<the most likely Amazon product listing title: brand, model name/number, '
    'key specs, color — use any text visible in the images>",\n'
    ' "attributes": {"brand": "...", "color": "...", "capacity": "...", "model": "...", '
    '"visible_text": "..."}}\n'
    "Omit attribute keys you cannot observe. JSON only, no markdown."
)


class PhotoExtractionUnavailable(RuntimeError):
    """Pas de clé OpenRouter → la branche photo est indisponible (texte reste OK)."""


@dataclass
class PhotoExtraction:
    """Résultat d'extraction : la requête catalogue + les attributs observés."""

    title_guess: str
    attributes: dict[str, str] = field(default_factory=dict)
    raw: str = ""


def _to_data_url(path: Path) -> str:
    mime = _MIME_BY_EXT.get(path.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def extract(photo_paths: list[Path]) -> PhotoExtraction:
    """Extrait titre probable + attributs depuis 1-N photos (un seul appel VLM).

    Raises:
        PhotoExtractionUnavailable: clé OpenRouter absente.
        requests.HTTPError / requests.Timeout: erreurs API (le caller dégrade).
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise PhotoExtractionUnavailable("OPENROUTER_API_KEY absente — branche photo indisponible")

    content: list[dict] = [{"type": "text", "text": EXTRACTION_PROMPT}]
    for p in photo_paths[:MAX_PHOTOS_PER_CALL]:
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(p)}})

    payload: dict = {
        "model": VLM_MODEL,
        "max_tokens": 250,
        "temperature": VLM_TEMPERATURE,  # déterminisme repro (D-042)
        "seed": VLM_SEED,
        "messages": [{"role": "user", "content": content}],
    }
    if VLM_PROVIDER:  # provider épinglé → quantization stable
        payload["provider"] = {"order": [VLM_PROVIDER], "allow_fallbacks": False}
    r = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=TIMEOUT_SEC,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    return _parse(raw)


def _parse(raw: str) -> PhotoExtraction:
    """Parse tolérant (JSON pur, fences markdown, prose) — même esprit que C6."""
    candidates = [raw]
    if "```" in raw:
        inner = raw.split("```")[1]
        candidates.insert(0, inner.removeprefix("json").strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])

    for cand in candidates:
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("title"):
            attrs = data.get("attributes") or {}
            return PhotoExtraction(
                title_guess=str(data["title"]),
                attributes={k: str(v) for k, v in attrs.items() if v},
                raw=raw,
            )
    # Repli : le VLM a répondu en texte libre → on l'utilise tel quel comme requête.
    _log.warning("photo_extraction_parse_fallback", raw_preview=raw[:120])
    return PhotoExtraction(title_guess=raw[:300], attributes={}, raw=raw)

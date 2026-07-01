"""Cycle 9.3b - Client OpenRouter (chat completions) pour VLM + LLM.

Wrapper httpx minimal autour de l'API OpenRouter (compatible OpenAI
chat/completions). Utilisé par :
- le LLM rédacteur grounded (llm-writer) : `/describe`
- le VLM validateur (vlm-validator) : validation matching (Cycle 5 vraie impl, post-MVP)

Active uniquement si `OPENROUTER_API_KEY` présent dans l'env (sinon raise
RuntimeError clair → l'endpoint bascule sur un mock). Mock-first par défaut.

Modèle par défaut : google/gemma-4-31b-it (vision-capable) - sert le rédacteur
LLM, l'extraction photo et le validateur VLM. Surchargeable par variable d'env.
"""

from __future__ import annotations

import json
import logging
import os
import time

import httpx

log = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
# Modèle vérifié dispo sur OpenRouter (query /models 2026-05). Gemma 4 31B IT
# (tier payant, pas de rate-limit free) - text-only, suffisant pour le rédacteur llm-writer.
DEFAULT_LLM_MODEL = "google/gemma-4-31b-it"
DEFAULT_TIMEOUT_SEC = 30.0

# Retry : les modèles :free sont fréquemment rate-limited (429) upstream.
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


class OpenRouterError(RuntimeError):
    """Erreur d'appel OpenRouter (clé absente, HTTP, parse)."""


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise OpenRouterError(
            "OPENROUTER_API_KEY absent de l'env. Ajoute-le dans .env pour activer /describe."
        )
    return key


def chat_completion(
    prompt: str,
    model: str = DEFAULT_LLM_MODEL,
    temperature: float = 0.4,
    max_tokens: int = 1024,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> str:
    """Appelle OpenRouter chat/completions (texte seul) et retourne le contenu brut.

    Raises:
        OpenRouterError: clé absente, erreur HTTP, ou réponse malformée.
    """
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/rakuten-ai-assistant",
        "X-Title": "Rakuten AI Assistant",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            # 429 (rate limit) / 5xx (provider) → retry avec backoff exponentiel
            if e.response.status_code in (429, 500, 502, 503) and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF_SEC * (2**attempt)
                log.warning(
                    "OpenRouter %d (tentative %d/%d), retry dans %.1fs",
                    e.response.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                last_err = e
                continue
            raise OpenRouterError(
                f"OpenRouter HTTP {e.response.status_code} : {e.response.text[:200]}"
            ) from e
        except (httpx.RequestError, KeyError, IndexError, json.JSONDecodeError) as e:
            raise OpenRouterError(f"OpenRouter call échoué : {e}") from e
    raise OpenRouterError(f"OpenRouter échec après {MAX_RETRIES} tentatives : {last_err}")


def is_available() -> bool:
    """True si la clé OpenRouter est configurée (sans tester le réseau)."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))


_TRANSLATE_PROMPT = (
    "Translate this French second-hand product description into a concise English "
    "product search query (brand, model, key specs, color). The catalog is in English. "
    "Output ONLY the English query, no quotes, no explanation.\n\nFrench: {text}\nEnglish:"
)


def translate_to_english(text: str, timeout: float = 15.0) -> str:
    """Traduit une requête produit FR → EN pour l'aligner sur le catalogue anglais.

    Aligne le décalage cross-lingue mesuré (requête FR score ~0.08 plus bas qu'EN
    sur catalogue Amazon US). Raises OpenRouterError si clé absente / appel KO -
    l'appelant doit gérer le fallback (requête brute).
    """
    raw = chat_completion(
        _TRANSLATE_PROMPT.format(text=text),
        temperature=0.0,
        max_tokens=128,
        timeout=timeout,
    )
    return raw.strip().strip('"').strip()

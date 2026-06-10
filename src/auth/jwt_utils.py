"""JWT encoding / decoding (Cycle 15.1, D-032).

HS256 secret partagé via env `JWT_SECRET`. Durée par défaut 60 min via
`JWT_EXPIRE_MINUTES`. Aucun refresh token (différé post-soutenance).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

ALGORITHM = "HS256"

# Lecture lazy de l'env : permet aux tests de monkeypatch avant `create_access_token()`
# (sinon le secret serait figé au moment de l'import).
_DEFAULT_DEV_SECRET = "dev-secret-change-me-in-prod"  # noqa: S105 — stub démo, jamais en .env prod (R2)
_DEFAULT_EXPIRE_MINUTES = 60


_warned_default_secret = False


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET", _DEFAULT_DEV_SECRET)
    # Audit 2026-06-05 (P1) : sans ce warning, une API déployée sans JWT_SECRET
    # signe silencieusement avec le secret par défaut committé → tokens forgeables
    # par quiconque lit le repo. Warning une seule fois (pas à chaque requête).
    global _warned_default_secret
    if secret == _DEFAULT_DEV_SECRET and not _warned_default_secret:
        _warned_default_secret = True
        from src.observability.logging import get_logger

        get_logger(__name__).warning(
            "jwt_secret_default_in_use",
            hint="JWT_SECRET non défini — tokens signés avec le secret DEV committé. "
            "Inacceptable hors développement local.",
        )
    return secret


def _expire_minutes() -> int:
    try:
        return int(os.environ.get("JWT_EXPIRE_MINUTES", str(_DEFAULT_EXPIRE_MINUTES)))
    except ValueError:
        return _DEFAULT_EXPIRE_MINUTES


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Crée un JWT HS256 signé avec `sub=subject` + `exp` (durée configurable).

    Args:
        subject: identifiant utilisateur (sera placé dans le claim `sub`).
        expires_delta: durée custom ; sinon utilise `JWT_EXPIRE_MINUTES` env (défaut 60 min).

    Returns:
        JWT compact serialization (chaîne `header.payload.signature`).
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=_expire_minutes())
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Décode + valide signature + expiration. Lève `JWTError` si invalide.

    Returns:
        dict des claims (`sub`, `iat`, `exp`).
    """
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])


__all__ = ["create_access_token", "decode_token", "JWTError", "ALGORITHM"]

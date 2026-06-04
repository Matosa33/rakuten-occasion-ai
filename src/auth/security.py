"""FastAPI security dependency (Cycle 15.1, D-032).

`get_current_user` est utilisé via `Depends()` sur chaque endpoint protégé.
Lève `HTTPException(401)` si le token est absent, invalide, ou expiré.

Le `sub` (subject) du token est retourné comme identifiant utilisateur, puis
bind dans `structlog.contextvars` (C14.1) pour la traçabilité request_id+user.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from src.auth.jwt_utils import decode_token
from src.observability.logging import get_logger

_log = get_logger(__name__)

# `tokenUrl="auth/login"` indique à FastAPI / Swagger UI où récupérer le token.
# Path relatif sans `/` initial : compatible montage sous-chemin (proxy / ingress).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Vérifie le token Bearer et retourne le `sub` (username).

    Raises:
        HTTPException 401 : token absent, signature invalide, expiré, ou sans `sub`.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except JWTError as e:
        _log.warning("jwt_decode_failed", error=str(e))
        raise credentials_exception from e

    username = payload.get("sub")
    if not username or not isinstance(username, str):
        _log.warning("jwt_missing_sub", payload_keys=list(payload.keys()))
        raise credentials_exception
    return username


__all__ = ["get_current_user", "oauth2_scheme"]

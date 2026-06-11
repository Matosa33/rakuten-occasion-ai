"""Stockage des photos vendeur (Cycle 17.1, D-035).

Photos = preuve acheteur + entrée du pipeline d'identification photo-first.
Stockage local démo : `data/uploads/<uuid>.<ext>` (gitignored, R2). Les URLs
sont des capability-URLs (uuid4 non devinable) → le GET est public, le POST
exige le Bearer (seul un vendeur connecté uploade).

Post-soutenance : objet storage (MinIO, déjà dans la stack) si multi-instance.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from src.config import REPO_ROOT

UPLOADS_DIR = REPO_ROOT / "data" / "uploads"

# Types accumulés par les navigateurs/appareils mobiles courants.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 Mo — au-delà c'est un fichier suspect


class UploadError(ValueError):
    """Erreur de validation upload (type ou taille)."""


def save_upload(content: bytes, content_type: str) -> str:
    """Valide et stocke une photo. Retourne l'image_id (uuid + extension).

    Raises:
        UploadError: type non supporté ou taille hors borne.
    """
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise UploadError(
            f"Type {content_type!r} non supporté (attendu : {', '.join(ALLOWED_CONTENT_TYPES)})"
        )
    if not content:
        raise UploadError("Fichier vide")
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadError(f"Fichier trop volumineux ({len(content)} o > {MAX_UPLOAD_BYTES} o)")

    image_id = f"{uuid.uuid4().hex}{ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / image_id).write_bytes(content)
    return image_id


def get_upload_path(image_id: str) -> Path | None:
    """Path du fichier si l'image_id est valide et existe, sinon None.

    Garde anti path-traversal : l'id doit être exactement `<hex32><ext connu>`.
    """
    stem, dot, ext = image_id.partition(".")
    if not (dot and len(stem) == 32 and all(c in "0123456789abcdef" for c in stem)):
        return None
    if f".{ext}" not in ALLOWED_CONTENT_TYPES.values():
        return None
    path = UPLOADS_DIR / image_id
    return path if path.is_file() else None

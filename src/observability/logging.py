"""Configuration structlog centrale (Cycle 14.1, D-029).

Usage standard dans tout le code :

    from src.observability.logging import get_logger
    log = get_logger(__name__)
    log.info("event-name", model="m5", f1=0.95)

- En **prod / docker** : JSON sur stdout, Loki/Promtail/ECS-friendly.
- En **dev (terminal interactif)** : pretty console colorée.
- Niveau via env `LOG_LEVEL` (défaut INFO).
- `bind_request_id(req_id)` (cf. `src/api/middleware.py`) injecte le request_id
  via `structlog.contextvars` → tout log émis pendant la requête le porte.
"""

from __future__ import annotations

import logging
import os
import sys

import structlog

_DEFAULT_LEVEL = "INFO"
_CONFIGURED = False


def _format_is_json() -> bool:
    """JSON par défaut sauf TTY interactif (DX dev) + override env `LOG_FORMAT=json`."""
    fmt = os.environ.get("LOG_FORMAT", "").lower()
    if fmt == "json":
        return True
    if fmt == "console":
        return False
    # Auto : pretty-console seulement si stderr est un TTY (dev local).
    return not sys.stderr.isatty()


def configure() -> None:
    """Configure structlog une seule fois (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = os.environ.get("LOG_LEVEL", _DEFAULT_LEVEL).upper()
    # Pont vers le `logging` stdlib pour que les libs (uvicorn, sqlalchemy…)
    # émettent au même niveau et soient capturées par les mêmes processors.
    logging.basicConfig(format="%(message)s", level=getattr(logging, level, logging.INFO))

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,  # injecte request_id, etc.
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if _format_is_json():
        renderer: object = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Récupère un logger structlog (configure() automatique si pas déjà fait)."""
    configure()
    log = structlog.get_logger()
    return log.bind(logger=name) if name else log


def bind_request_id(request_id: str) -> None:
    """Lie un request_id au context (utilisé par le middleware FastAPI, D-029)."""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_context() -> None:
    """Nettoie le context après une requête (à appeler en fin de middleware)."""
    structlog.contextvars.clear_contextvars()

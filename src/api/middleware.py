"""Middleware FastAPI : request_id + access log structuré (Cycle 14.1, D-029).

Lit le header `X-Request-ID` du client (ou en génère un `uuid4()` si absent),
le bind dans le contexte structlog → tous les logs émis pendant la requête le
portent. Renvoie le request_id dans le header de réponse pour traçabilité E2E
(client/gateway/api).

Exemple log produit (JSON) :

    {"timestamp":"2026-06-04T...","level":"info","logger":"src.api.access",
     "request_id":"a8f3...","method":"POST","path":"/identify",
     "status":200,"duration_ms":12.4,"event":"http_request"}
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from src.observability.logging import bind_request_id, clear_request_context, get_logger

REQUEST_ID_HEADER = "x-request-id"
_log = get_logger("src.api.access")


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Génère/propage un request_id et logue chaque requête en JSON structuré."""
    req_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
    bind_request_id(req_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = req_id
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    finally:
        clear_request_context()

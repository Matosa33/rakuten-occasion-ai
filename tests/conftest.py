"""Fixtures pytest partagées (Cycle 15.1, D-032).

Depuis que tous les endpoints métier exigent un Bearer JWT (D-032), les tests
existants doivent injecter un header Authorization. Cette fixture évite la
duplication et garantit que la migration est uniforme.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Headers HTTP avec un Bearer JWT valide pour le user `demo` (D-032).

    Usage :
        def test_something(client, auth_headers):
            r = client.post("/identify", json={...}, headers=auth_headers)
    """
    from src.auth.jwt_utils import create_access_token

    token = create_access_token(subject="demo")
    return {"Authorization": f"Bearer {token}"}

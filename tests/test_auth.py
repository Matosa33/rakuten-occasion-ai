"""Tests JWT auth stub démo (Cycle 15.1, D-032).

Sans padding : chaque test attrape une régression réelle.
- Login OK avec demo/demo → 200 + token JWT bearer
- Login wrong → 401
- Token valide → endpoint protégé accessible
- Pas de token → 401
- Token expiré → 401
- Token signé avec autre secret → 401
- /health + /auth/login restent publics
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from src.auth.jwt_utils import create_access_token, decode_token
from src.auth.users import authenticate

# ─────────────────────────────────────────────────────────────────────────────
# Unitaire : users + jwt_utils (sans réseau, rapide)
# ─────────────────────────────────────────────────────────────────────────────


def test_authenticate_demo_ok():
    """Le user stub `demo` / `demo` est valide."""
    assert authenticate("demo", "demo") is True


def test_authenticate_wrong_password_refused():
    """Mauvais password → False (jamais un crash)."""
    assert authenticate("demo", "wrong") is False


def test_authenticate_unknown_user_refused_constant_time():
    """User inconnu → False. (Le helper fait un hash bidon pour timing-safe.)"""
    assert authenticate("alice", "demo") is False


def test_jwt_create_decode_roundtrip():
    """Token signé localement se décode et retourne le sub."""
    tok = create_access_token(subject="demo")
    payload = decode_token(tok)
    assert payload["sub"] == "demo"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_decode_expired_token_raises():
    """Token expiré (durée négative) doit lever JWTError."""
    from jose import JWTError

    tok = create_access_token(subject="demo", expires_delta=timedelta(seconds=-10))
    with pytest.raises(JWTError):
        decode_token(tok)


def test_jwt_decode_tampered_signature_raises(monkeypatch):
    """Token signé avec un autre secret → JWTError (signature invalide)."""
    from jose import JWTError

    monkeypatch.setenv("JWT_SECRET", "secret-A")
    tok = create_access_token(subject="demo")

    monkeypatch.setenv("JWT_SECRET", "secret-B")
    with pytest.raises(JWTError):
        decode_token(tok)


# ─────────────────────────────────────────────────────────────────────────────
# Intégration : endpoints FastAPI (TestClient, sans Pushgateway/Prometheus réel)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """TestClient de l'app FastAPI réelle (lifespan tronqué : services peuvent
    être indispo, on s'en fiche — on teste l'auth, pas le pipeline ML)."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    with TestClient(app) as c:
        yield c


def test_health_reste_public(client):
    """`/health` ne doit JAMAIS exiger de token (sonde K8s/Docker)."""
    r = client.get("/health")
    assert r.status_code == 200


def test_auth_login_reste_public_et_renvoie_bearer_token(client):
    """`/auth/login` accepte form-data `username` + `password` et renvoie un Bearer."""
    r = client.post("/auth/login", data={"username": "demo", "password": "demo"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"].count(".") == 2, "JWT format = header.payload.signature"


def test_auth_login_wrong_credentials_renvoie_401(client):
    """Mauvais creds → 401 avec WWW-Authenticate: Bearer."""
    r = client.post("/auth/login", data={"username": "demo", "password": "wrong"})
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("www-authenticate", "")


def test_identify_sans_token_renvoie_401(client):
    """Endpoint protégé sans Authorization → 401, pas 422 (la dependency tire en 1er)."""
    r = client.post("/identify", json={"text_hint": "iphone"})
    assert r.status_code == 401


def test_identify_token_invalide_renvoie_401(client):
    """Token bidon → 401."""
    r = client.post(
        "/identify",
        headers={"Authorization": "Bearer not-a-real-jwt"},
        json={"text_hint": "iphone"},
    )
    assert r.status_code == 401


def test_endpoints_metier_tous_proteges(client):
    """Régression : si on oublie de protéger un endpoint, il répondra autre chose
    que 401 sans Authorization."""
    # /price : sans token → 401 (et pas 422 sur le body)
    r = client.post("/price", json={})
    assert r.status_code == 401, f"/price doit exiger un token, vu {r.status_code}"
    # /describe : idem
    r = client.post("/describe", json={})
    assert r.status_code == 401, f"/describe doit exiger un token, vu {r.status_code}"
    # /history : GET sans token → 401
    r = client.get("/history")
    assert r.status_code == 401, f"/history doit exiger un token, vu {r.status_code}"
    # /identify/stream : POST sans token → 401
    r = client.post("/identify/stream", json={"text_hint": "iphone"})
    assert r.status_code == 401, f"/identify/stream doit exiger un token, vu {r.status_code}"


def test_token_valide_accede_aux_endpoints_proteges(client):
    """Un token valide passe la dependency (même si l'endpoint plante après en
    503 pour service indispo — c'est l'auth qu'on teste ici, pas le service)."""
    # Récupère un vrai token via /auth/login
    login = client.post("/auth/login", data={"username": "demo", "password": "demo"})
    token = login.json()["access_token"]

    # /history n'a pas de pré-condition métier → si auth passe, on doit avoir 200
    r = client.get("/history", headers={"Authorization": f"Bearer {token}"})
    # 200 si la DB est OK, 503 si KO — l'important : PAS 401.
    assert r.status_code != 401, f"token valide refusé par /history (vu {r.status_code})"

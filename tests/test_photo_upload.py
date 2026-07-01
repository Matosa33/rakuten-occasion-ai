"""Tests photo-first backend (Cycle 17.1, D-035) - upload + extraction + identify.

Sans padding : upload (validation type/taille/path-traversal), serve, et le
branchement /identify avec image_ids (extraction VLM mockée - pas d'appel réseau).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api import uploads
from src.auth.jwt_utils import create_access_token
from src.vlm.photo_extraction import PhotoExtraction, _parse

client = TestClient(api_main.app)
AUTH = {"Authorization": f"Bearer {create_access_token(subject='demo')}"}

# 1×1 px JPEG minimal valide (généré une fois, déterministe).
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fca8ffd9"
)


# ─────────────────────────────────────────────────────────────────────────────
# uploads.py - validation pure (sans HTTP)
# ─────────────────────────────────────────────────────────────────────────────


def test_save_upload_type_inconnu_refuse():
    with pytest.raises(uploads.UploadError, match="non supporté"):
        uploads.save_upload(b"x", "application/pdf")


def test_save_upload_vide_refuse():
    with pytest.raises(uploads.UploadError, match="vide"):
        uploads.save_upload(b"", "image/jpeg")


def test_save_upload_trop_gros_refuse():
    big = b"x" * (uploads.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(uploads.UploadError, match="volumineux"):
        uploads.save_upload(big, "image/jpeg")


def test_save_et_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    image_id = uploads.save_upload(TINY_JPEG, "image/jpeg")
    assert image_id.endswith(".jpg")
    path = uploads.get_upload_path(image_id)
    assert path is not None and path.read_bytes() == TINY_JPEG


def test_get_upload_path_anti_traversal():
    """Un image_id forgé ne doit JAMAIS sortir du dossier uploads."""
    for evil in (
        "../../.env",
        "..%2F.env",
        "abc.jpg",
        "x" * 32 + ".exe",
        "../" + "a" * 32 + ".jpg",
    ):
        assert uploads.get_upload_path(evil) is None, f"path-traversal accepté : {evil!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints HTTP
# ─────────────────────────────────────────────────────────────────────────────


def test_upload_endpoint_exige_auth():
    r = client.post("/upload", files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    assert r.status_code == 401


def test_upload_puis_serve(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    r = client.post("/upload", headers=AUTH, files={"file": ("photo.jpg", TINY_JPEG, "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"] == f"/uploads/{body['image_id']}"
    # GET public (capability URL) - pas de header auth.
    served = client.get(body["url"])
    assert served.status_code == 200
    assert served.content == TINY_JPEG


def test_upload_type_refuse_en_422():
    r = client.post(
        "/upload", headers=AUTH, files={"file": ("doc.pdf", b"%PDF", "application/pdf")}
    )
    assert r.status_code == 422


def test_serve_inconnu_404():
    assert client.get("/uploads/" + "0" * 32 + ".jpg").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# /identify avec image_ids - extraction VLM mockée
# ─────────────────────────────────────────────────────────────────────────────


class _FakeIdent:
    ready = True
    last_query: str = ""
    last_observed: dict = {}

    def identify(self, q, already_observed=None):
        from src.api.pipeline import Candidate, IdentificationResult

        _FakeIdent.last_query = q
        _FakeIdent.last_observed = dict(already_observed or {})
        return IdentificationResult(
            status="identified",
            candidates=[Candidate("B0PHOTO", "iPhone 13 128GB", "Apple", "Electronics", 0.9)],
            next_observation=None,
            explanation="ok",
        )


@pytest.fixture(autouse=True)
def _state():
    for key in ("identification", "pricing", "describe"):
        api_main.APP_STATE[key] = None
    yield
    for key in ("identification", "pricing", "describe"):
        api_main.APP_STATE[key] = None


def test_identify_photo_first_via_extraction_mockee(tmp_path, monkeypatch):
    """Photo → extraction (mock) → la requête retrieval = titre VLM + texte,
    et les attributs VLM pré-remplissent already_observed (Akinator)."""
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    image_id = uploads.save_upload(TINY_JPEG, "image/jpeg")

    def fake_extract(paths):
        assert len(paths) == 1
        return PhotoExtraction(
            title_guess="Apple iPhone 13 128GB Black Unlocked",
            attributes={"brand": "Apple", "color": "Black"},
        )

    monkeypatch.setattr(api_main, "extract_from_photos", fake_extract)
    api_main.APP_STATE["identification"] = _FakeIdent()

    r = client.post(
        "/identify",
        headers=AUTH,
        json={"image_ids": [image_id], "text_hint": "très bon état"},
    )
    assert r.status_code == 200, r.text
    assert "Apple iPhone 13 128GB Black Unlocked" in _FakeIdent.last_query
    assert "très bon état" in _FakeIdent.last_query
    assert _FakeIdent.last_observed.get("brand") == "Apple"


def test_identify_image_ids_inconnus_422(monkeypatch):
    api_main.APP_STATE["identification"] = _FakeIdent()
    r = client.post("/identify", headers=AUTH, json={"image_ids": ["nimporte.jpg"]})
    assert r.status_code == 422


def test_identify_sans_photo_ni_texte_422():
    api_main.APP_STATE["identification"] = _FakeIdent()
    r = client.post("/identify", headers=AUTH, json={})
    assert r.status_code == 422


def test_identify_extraction_indisponible_503_message_actionnable(tmp_path, monkeypatch):
    """Sans clé OpenRouter : 503 explicite qui invite à la saisie texte (D-013/D-035)."""
    from src.vlm.photo_extraction import PhotoExtractionUnavailable

    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    image_id = uploads.save_upload(TINY_JPEG, "image/jpeg")

    def unavailable(paths):
        raise PhotoExtractionUnavailable("no key")

    monkeypatch.setattr(api_main, "extract_from_photos", unavailable)
    api_main.APP_STATE["identification"] = _FakeIdent()

    r = client.post("/identify", headers=AUTH, json={"image_ids": [image_id]})
    assert r.status_code == 503
    assert "texte" in r.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# photo_extraction._parse - robustesse réponses VLM
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_json_pur():
    p = _parse('{"title": "JBL Flip 5", "attributes": {"color": "Teal"}}')
    assert p.title_guess == "JBL Flip 5"
    assert p.attributes == {"color": "Teal"}


def test_parse_fence_markdown():
    p = _parse('```json\n{"title": "DEWALT DW5348", "attributes": {}}\n```')
    assert p.title_guess == "DEWALT DW5348"


def test_parse_texte_libre_fallback():
    """Réponse non-JSON → utilisée telle quelle comme requête (pas de crash)."""
    p = _parse("Bosch IMSDC2 step drill bit, high speed steel")
    assert "Bosch IMSDC2" in p.title_guess
    assert p.attributes == {}

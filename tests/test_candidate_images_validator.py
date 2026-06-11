"""Tests 17.2 (D-035) — images multiples candidats + VLM validateur F0.4.

Sans padding : extraction N vues (pure), parse verdict, branchement /identify
(vlm_validation peuplé avec photos / absent sans), images[] dans la réponse.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api import uploads
from src.auth.jwt_utils import create_access_token
from src.vlm.photo_extraction import PhotoExtraction
from src.vlm.validator import VLMValidation
from src.vlm.validator import _parse as parse_verdict

_lookup_builder = importlib.import_module("src.data.clean.06_build_product_lookup")

client = TestClient(api_main.app)
AUTH = {"Authorization": f"Bearer {create_access_token(subject='demo')}"}

TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fca8ffd9"
)


# ─────────────────────────────────────────────────────────────────────────────
# _extract_all_image_urls — extraction pure des N vues
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_all_images_main_en_premier_et_dedup():
    images_str = str(
        [
            {"variant": "PT01", "large": "http://x/side.jpg", "thumb": "http://x/side_t.jpg"},
            {"variant": "MAIN", "large": "http://x/main.jpg", "thumb": "http://x/main_t.jpg"},
            {"variant": "PT02", "large": "http://x/side.jpg"},  # doublon URL
        ]
    )
    urls = _lookup_builder._extract_all_image_urls(images_str)
    assert urls[0] == "http://x/main.jpg", "la vue MAIN doit être première (cohérence vignette)"
    assert urls.count("http://x/side.jpg") == 1, "doublons URL dédupliqués"
    assert len(urls) == 2


def test_extract_all_images_cap_max():
    entries = [{"variant": f"PT{i:02d}", "large": f"http://x/{i}.jpg"} for i in range(20)]
    urls = _lookup_builder._extract_all_image_urls(str(entries))
    assert len(urls) == _lookup_builder.MAX_IMAGES_PER_PRODUCT


def test_extract_all_images_malformed():
    assert _lookup_builder._extract_all_image_urls(None) == []
    assert _lookup_builder._extract_all_image_urls("[]") == []
    assert _lookup_builder._extract_all_image_urls("pas du python") == []


# ─────────────────────────────────────────────────────────────────────────────
# validator._parse — robustesse verdicts VLM
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_verdict_json_pur():
    v = parse_verdict('{"match": true, "confidence": 0.92, "reason": "Same model"}')
    assert v is not None and v.match is True and v.confidence == 0.92


def test_parse_verdict_confidence_clampee():
    v = parse_verdict('{"match": false, "confidence": 1.7, "reason": "x"}')
    assert v is not None and v.confidence == 1.0


def test_parse_verdict_inexploitable_none():
    assert parse_verdict("le produit semble correspondre") is None


# ─────────────────────────────────────────────────────────────────────────────
# /identify — images[] exposées + vlm_validation peuplé
# ─────────────────────────────────────────────────────────────────────────────


class _FakeIdentWithImages:
    ready = True

    def identify(self, q, already_observed=None):
        from src.api.pipeline import Candidate, IdentificationResult

        return IdentificationResult(
            status="identified",
            candidates=[
                Candidate(
                    "B0MULTI",
                    "iPhone 13 128GB",
                    "Apple",
                    "Electronics",
                    0.9,
                    image_url="http://x/main_t.jpg",
                    images=["http://x/main.jpg", "http://x/back.jpg", "http://x/side.jpg"],
                )
            ],
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


def test_identify_expose_les_images_multiples():
    """La visionneuse frontend a besoin de TOUTES les vues du candidat."""
    api_main.APP_STATE["identification"] = _FakeIdentWithImages()
    r = client.post("/identify", headers=AUTH, json={"text_hint": "iphone 13"})
    assert r.status_code == 200, r.text
    c = r.json()["top_candidates"][0]
    assert c["images"] == ["http://x/main.jpg", "http://x/back.jpg", "http://x/side.jpg"]


def test_identify_avec_photos_peuple_vlm_validation(tmp_path, monkeypatch):
    """Photos vendeur + top-1 avec image catalogue → validateur appelé,
    verdict structuré dans la réponse."""
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    image_id = uploads.save_upload(TINY_JPEG, "image/jpeg")

    monkeypatch.setattr(
        api_main,
        "extract_from_photos",
        lambda paths: PhotoExtraction(title_guess="iPhone 13", attributes={}),
    )
    captured = {}

    def fake_validate(paths, catalog_img, title):
        captured["catalog_img"] = catalog_img
        captured["n_photos"] = len(paths)
        return VLMValidation(match=True, confidence=0.91, reason="Même modèle visible")

    monkeypatch.setattr(api_main, "validate_top1", fake_validate)
    api_main.APP_STATE["identification"] = _FakeIdentWithImages()

    r = client.post("/identify", headers=AUTH, json={"image_ids": [image_id]})
    assert r.status_code == 200, r.text
    v = r.json()["vlm_validation"]
    assert v == {"match": True, "confidence": 0.91, "reason": "Même modèle visible"}
    # Le validateur reçoit la vue large (images[0]), pas la vignette thumb.
    assert captured["catalog_img"] == "http://x/main.jpg"
    assert captured["n_photos"] == 1


def test_identify_sans_photo_vlm_validation_none():
    """Text-only → pas de validation visuelle possible → null (pas d'erreur)."""
    api_main.APP_STATE["identification"] = _FakeIdentWithImages()
    r = client.post("/identify", headers=AUTH, json={"text_hint": "iphone"})
    assert r.status_code == 200
    assert r.json()["vlm_validation"] is None


def test_identify_validateur_down_degrade_en_none(tmp_path, monkeypatch):
    """VLM validateur en échec → vlm_validation=None, le flow continue (R15)."""
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    image_id = uploads.save_upload(TINY_JPEG, "image/jpeg")
    monkeypatch.setattr(
        api_main,
        "extract_from_photos",
        lambda paths: PhotoExtraction(title_guess="iPhone 13", attributes={}),
    )
    monkeypatch.setattr(api_main, "validate_top1", lambda *a: None)
    api_main.APP_STATE["identification"] = _FakeIdentWithImages()

    r = client.post("/identify", headers=AUTH, json={"image_ids": [image_id]})
    assert r.status_code == 200
    assert r.json()["vlm_validation"] is None
    assert r.json()["top_candidates"], "les candidats restent servis"

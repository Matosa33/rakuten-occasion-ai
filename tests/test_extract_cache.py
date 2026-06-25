"""Tests du cache d'extraction VLM (Cycle 34.2).

Vérifie : 1er appel = miss (appelle l'extracteur, écrit le cache) ; 2e appel mêmes photos = hit
(aucun appel) ; photos au contenu différent = miss (clé différente) ; persistance disque relue.
"""

from __future__ import annotations

from src.vlm.extract_cache import ExtractionCache
from src.vlm.photo_extraction import PhotoExtraction


def _fake_extractor():
    """Extracteur factice qui compte ses appels."""
    calls = {"n": 0}

    def _fn(paths):
        calls["n"] += 1
        return PhotoExtraction(
            title_guess=f"titre {calls['n']}", attributes={"brand": "X"}, raw="{}"
        )

    return _fn, calls


def _photo(tmp_path, name, content: bytes):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_miss_puis_hit_sur_memes_photos(tmp_path):
    fn, calls = _fake_extractor()
    cache = ExtractionCache(tmp_path / "cache.jsonl")
    photo = _photo(tmp_path, "a.jpg", b"AAA")

    ext1, hit1 = cache.get_or_extract([photo], extract_fn=fn)
    assert hit1 is False and calls["n"] == 1

    ext2, hit2 = cache.get_or_extract([photo], extract_fn=fn)
    assert hit2 is True and calls["n"] == 1  # PAS de second appel
    assert ext2.title_guess == ext1.title_guess  # même résultat servi du cache


def test_contenu_different_donne_miss(tmp_path):
    fn, calls = _fake_extractor()
    cache = ExtractionCache(tmp_path / "cache.jsonl")
    cache.get_or_extract([_photo(tmp_path, "a.jpg", b"AAA")], extract_fn=fn)
    cache.get_or_extract([_photo(tmp_path, "b.jpg", b"BBB")], extract_fn=fn)  # contenu différent
    assert calls["n"] == 2  # deux extractions distinctes


def test_persistance_relue_par_nouvelle_instance(tmp_path):
    fn, calls = _fake_extractor()
    photo = _photo(tmp_path, "a.jpg", b"AAA")
    ExtractionCache(tmp_path / "cache.jsonl").get_or_extract([photo], extract_fn=fn)
    # nouvelle instance → relit le JSONL → hit sans appel
    _, hit = ExtractionCache(tmp_path / "cache.jsonl").get_or_extract([photo], extract_fn=fn)
    assert hit is True and calls["n"] == 1

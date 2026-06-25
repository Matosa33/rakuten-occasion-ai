"""Cache disque des extractions VLM (Cycle 34.2 — prérequis protocole D-042).

Trois raisons, toutes des conditions de **validité** ou de **reproductibilité** de l'expérience :
1. **Validité** : les conditions C2/C3/C3t doivent partager UNE extraction — sinon on confond
   l'effet « métadonnée » avec un simple **tirage VLM différent** (l'API n'est pas déterministe).
2. **Reproductibilité** : on peut rejouer le *scoring* sur les sorties brutes mises en cache,
   sans rappeler l'API (qui peut changer de provider/quantization).
3. **Coût / temps**.

Clé = SHA-256 de **tout ce qui détermine la sortie** : modèle + température + seed + prompt +
**contenu des photos** (octets, pas le chemin). Stockage **JSONL append-only**. Ce module
**n'altère pas** `extract()` : c'est un wrapper pur, testable sans réseau (injection `extract_fn`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.vlm import photo_extraction
from src.vlm.photo_extraction import PhotoExtraction


def extraction_key(photo_paths: list[Path | str]) -> str:
    """Clé de cache = hash(modèle + température + seed + prompt + contenu des photos)."""
    h = hashlib.sha256()
    h.update(photo_extraction.VLM_MODEL.encode())
    h.update(str(photo_extraction.VLM_TEMPERATURE).encode())
    h.update(str(photo_extraction.VLM_SEED).encode())
    h.update(str(photo_extraction.VLM_MAX_TOKENS).encode())
    h.update(str(photo_extraction.VLM_REASONING).encode())
    h.update(photo_extraction.EXTRACTION_PROMPT.encode())
    for p in photo_paths:
        h.update(Path(p).read_bytes())  # contenu, robuste aux changements de chemin
    return h.hexdigest()


class ExtractionCache:
    """Cache JSONL append-only pour `photo_extraction.extract`."""

    def __init__(self, cache_path: Path | str):
        self.path = Path(cache_path)
        self._mem: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self._mem[rec["key"]] = rec

    def get_or_extract(
        self, photo_paths: list[Path | str], *, extract_fn=photo_extraction.extract
    ) -> tuple[PhotoExtraction, bool]:
        """Retourne (extraction, hit) : hit=True si servie du cache (pas d'appel API)."""
        k = extraction_key(photo_paths)
        if k in self._mem:
            r = self._mem[k]
            return PhotoExtraction(
                r["title_guess"], dict(r.get("attributes", {})), r.get("raw", "")
            ), True
        ext = extract_fn([Path(p) for p in photo_paths])
        rec = {
            "key": k,
            "title_guess": ext.title_guess,
            "attributes": ext.attributes,
            "raw": ext.raw,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._mem[k] = rec
        return ext, False

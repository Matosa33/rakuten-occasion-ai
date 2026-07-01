"""Recouvrement texte-vendeur ↔ cible d'annotation (Cycle 34.3 - garde-fou anti-fuite, D-042).

`seller_metadata` (entrée légitime de production) et `true_name` (cible) proviennent de la MÊME
annonce → recouvrement possible. Si le texte vendeur **contient déjà** le nom du produit, un gain
de la condition « + métadonnée » serait un **artefact de fuite d'annotation**, pas un vrai apport.

Ce module mesure ce recouvrement **par produit** (substring + Jaccard de mots) → le benchmark
**stratifie** dessus : le gain métadonnée crédible se lit sur les produits **sans recouvrement**.
On ne nie pas la fuite, on la **borne et l'étiquette** (honnêteté).

`main()` enrichit chaque `meta.json` d'un champ `seller_meta_overlap` (non destructif) + rapporte
la répartition.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
JACCARD_OVERLAP_THRESHOLD = 0.6  # au-delà : considéré recouvrant même sans inclusion stricte


def _norm(s: str) -> str:
    """Minuscule, sans accents, alphanum + espaces, espaces compactés."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def compute_overlap(seller_metadata: str, true_name: str) -> dict:
    """Recouvrement entre le texte vendeur et la cible. Retourne jaccard, substring, is_overlap."""
    a, b = _norm(seller_metadata), _norm(true_name)
    wa, wb = set(a.split()), set(b.split())
    jaccard = len(wa & wb) / len(wa | wb) if (wa and wb) else 0.0
    substring = bool(a and b and (a in b or b in a))
    return {
        "jaccard": round(jaccard, 3),
        "substring": substring,
        "is_overlap": substring or jaccard >= JACCARD_OVERLAP_THRESHOLD,
    }


def main() -> None:
    files = sorted(DATASET_DIR.glob("*/meta.json"))
    stats: Counter = Counter()
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        ov = compute_overlap(m.get("seller_metadata", ""), m.get("true_name", ""))
        stats["overlap" if ov["is_overlap"] else "clean"] += 1
        if m.get("seller_meta_overlap") != ov:
            m["seller_meta_overlap"] = ov
            f.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(files)
    print(f"{n} produits analysés.")
    print(f"  recouvrants (gain métadonnée = borne haute, étiqueté) : {stats['overlap']}")
    print(f"  sans recouvrement (gain métadonnée crédible)          : {stats['clean']}")


if __name__ == "__main__":
    main()

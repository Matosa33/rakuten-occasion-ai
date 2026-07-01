"""Normalise le champ `condition` des meta.json d'éval (Cycle 34.0, prérequis protocole D-042).

Les `meta.json` contiennent des **libellés FR** (« Très bon état », « État neuf »… + des vides),
or le pricing/condition attend des **clés snake_case** (`neuf`, `tres_bon_etat`, `bon_etat`,
`correct`). Ce script ajoute un champ `condition_key` (clé canonique) **sans détruire** le libellé
FR d'origine, et applique le défaut `bon_etat` aux vides.

NB : aucune corruption d'encodage - les fichiers sont du UTF-8 sain (vérifié sur les codepoints ;
le « mojibake » vu en console était un artefact d'affichage du terminal). On ne « répare » donc
rien, on **mappe** seulement.

Lancer :
    .venv/Scripts/python.exe scripts/annotation_tool/normalize_meta.py
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
DEFAULT_KEY = "bon_etat"  # défaut documenté (cf. pipeline) pour les conditions vides
VALID_KEYS = {"neuf", "tres_bon_etat", "bon_etat", "correct"}


def _to_key(label: str) -> str:
    """Libellé FR (accent-insensible) → clé canonique snake_case."""
    s = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode().lower().strip()
    if not s:
        return DEFAULT_KEY
    if "neuf" in s:
        return "neuf"
    if "tres bon" in s:
        return "tres_bon_etat"
    if "satisfaisant" in s or "correct" in s or "piece" in s:  # « pour pièces » → état le plus bas
        return "correct"
    if "bon" in s:
        return "bon_etat"
    return DEFAULT_KEY


def main() -> None:
    files = sorted(DATASET_DIR.glob("*/meta.json"))
    before: Counter = Counter()
    after: Counter = Counter()
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        label = m.get("condition", "")
        before[label] += 1
        key = _to_key(label)
        assert key in VALID_KEYS, f"clé invalide {key!r} pour {label!r}"  # noqa: S101
        after[key] += 1
        if m.get("condition_key") != key:
            m["condition_key"] = key
            f.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(files)} meta.json normalisés.")
    print("libellés FR (avant) :", dict(before))
    print("clés canoniques (après) :", dict(after))


if __name__ == "__main__":
    main()

"""Dérive les métadonnées structurées depuis le texte d'annonce (Phase 2, lot).

Tu saisis photos + annonce via l'interface (`app.py`). Ce script lit chaque produit
`annotated:false` et **dérive** par LLM (OpenRouter) les champs structurés nécessaires au
benchmark, puis les écrit dans `meta.json` (`annotated:true`). Conçu pour passer à l'échelle
(~100 produits) : séquentiel, idempotent (skip déjà annotés sauf `--force`), tolérant.

Champs dérivés :
- `macro`              : l'une des 4 macro-catégories du projet (pour scorer + le gate).
- `true_category_path` : breadcrumb fin proposé (taxonomie cible « A > B > C »).
- `true_name`          : libellé produit normalisé.
- `seller_metadata`    : texte court que taperait le vendeur (= condition C3 « + métadonnée »).

Lancer :

    .venv/Scripts/python.exe scripts/annotation_tool/derive_meta.py            # les non-annotés
    .venv/Scripts/python.exe scripts/annotation_tool/derive_meta.py --force    # tout re-dériver

Nécessite `OPENROUTER_API_KEY` dans `.env`. Sans clé : liste les produits à annoter à la main.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import src.config  # noqa: E402, F401 — son import charge .env (OPENROUTER_API_KEY) dans l'env
from src.config import CATEGORIES  # noqa: E402 — source de vérité des 4 macros
from src.llm import openrouter_client as orc  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
MACROS = list(CATEGORIES)  # valeurs réelles de `_source_category`

PROMPT = """Tu classes une annonce de produit d'occasion. Réponds en JSON STRICT, rien d'autre.

Annonce :
TITRE: {title}
DESCRIPTION: {desc}

Renvoie :
{{
  "true_name": "libellé produit normalisé (marque + modèle + variante)",
  "macro": "UNE de ces 4 valeurs EXACTES: Electronics | Cell_Phones_and_Accessories | Video_Games | Tools_and_Home_Improvement",
  "true_category_path": "taxonomie fine en anglais, format 'A > B > C' (ex: 'Electronics > Computers > Graphics Cards')",
  "seller_metadata": "texte court que le vendeur taperait (marque + modèle + mots-clés, ~5-8 mots)"
}}

Règles : macro DOIT être l'une des 4 valeurs. Téléphone/smartphone → Cell_Phones_and_Accessories ;
jeu/console → Video_Games ; outil/bricolage → Tools_and_Home_Improvement ; reste high-tech → Electronics."""


def _parse_json(text: str) -> dict | None:
    """Extrait le 1er objet JSON d'une réponse LLM (tolère les fences ```)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def derive_one(meta: dict) -> dict | None:
    title = meta.get("listing_title", "")
    desc = meta.get("listing_description", "")
    prompt = PROMPT.format(title=title or "(vide)", desc=desc or "(vide)")
    data = _parse_json(orc.chat_completion(prompt))
    if not data:
        return None
    macro = str(data.get("macro", "")).strip()
    if macro not in MACROS:  # garde-fou : recale sur une des 4 si le LLM dévie
        low = macro.lower()
        macro = next((m for m in MACROS if m.lower() in low or low in m.lower()), "")
        if not macro:
            log.warning("macro hors-liste (%r) → à corriger à la main.", data.get("macro"))
            return None
    return {
        "true_name": str(data.get("true_name", title)).strip(),
        "macro": macro,
        "true_category_path": str(data.get("true_category_path", "")).strip(),
        "seller_metadata": str(data.get("seller_metadata", title)).strip(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-dériver même les déjà annotés")
    args = ap.parse_args()

    if not DATASET_DIR.exists():
        log.error("%s absent — saisis d'abord des produits via app.py.", DATASET_DIR)
        return
    dirs = sorted(d for d in DATASET_DIR.iterdir() if d.is_dir() and (d / "meta.json").exists())
    if not orc.is_available():
        todo = [d.name for d in dirs if not json.loads((d / "meta.json").read_text("utf-8")).get("annotated")]
        log.error("OPENROUTER_API_KEY absente. À dériver (manuel ou avec clé) : %s", todo or "aucun")
        return

    done = skipped = failed = 0
    for d in dirs:
        meta_f = d / "meta.json"
        meta = json.loads(meta_f.read_text(encoding="utf-8"))
        if meta.get("annotated") and not args.force:
            skipped += 1
            continue
        derived = derive_one(meta)
        if derived is None:
            failed += 1
            log.warning("%s : dérivation échouée (à corriger à la main).", d.name)
            continue
        meta.update(derived)
        meta["annotated"] = True
        meta_f.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        done += 1
        log.info("%s → %s | %s", d.name, derived["macro"], derived["true_name"])

    log.info("Terminé : %d dérivés, %d déjà annotés, %d échecs (sur %d).", done, skipped, failed, len(dirs))


if __name__ == "__main__":
    main()

"""Ingestion des PDF scrappés (Lebonscrap) → dataset `data/photos_eval/`.

Les PDF leboncoin scrappés sont **image-only** (aucune couche texte) : page 0 = carte
(titre / catégorie / prix / état / description en pixels), pages suivantes = 1 photo chacune
(avec légende « Photo i/N » + filigrane). Ce script automatise tout :

  1. **photos** : rend chaque page-photo, recadre (retire légende + marges) → 01.jpg…0N.jpg ;
  2. **carte** : rend la page 0 et la fait lire par le **VLM** (Gemma/OpenRouter) → champs
     structurés (titre, catégorie→macro, taxo fine, prix, état, seller_metadata) ;
  3. **rangement** : `data/photos_eval/<NN>_<slug>/` + `meta.json` (`annotated:true`).

Idempotent (skip si le `source_pdf` est déjà ingéré). Sans clé OpenRouter : extrait quand même
les photos et laisse les champs à dériver (`annotated:false`, via `derive_meta.py`).

Lancer :

    .venv/Scripts/python.exe scripts/annotation_tool/ingest_pdf.py                # depuis ~/Downloads
    .venv/Scripts/python.exe scripts/annotation_tool/ingest_pdf.py --src <dossier> [--limit N]
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import logging
import os
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import src.config  # noqa: E402, F401 — charge .env (OPENROUTER_API_KEY)
from src.config import CATEGORIES  # noqa: E402 — source de vérité des 4 macros

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
DEFAULT_SRC = Path.home() / "Downloads"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VLM_MODEL = os.environ.get("PHOTO_VLM_MODEL", "google/gemma-4-31b-it")
MACROS = list(CATEGORIES)  # Electronics | Cell_Phones_and_Accessories | Video_Games | Tools_and_Home_Improvement
RENDER_DPI = 150
CAPTION_BAND = 0.09  # fraction haute coupée (légende « Photo i/N »)

# Alias formes courtes → canonique (si le VLM renvoie une forme abrégée).
_MACRO_ALIASES = {
    "cell_phones": "Cell_Phones_and_Accessories",
    "phones": "Cell_Phones_and_Accessories",
    "tools": "Tools_and_Home_Improvement",
}
# Repli déterministe catégorie FR leboncoin → macro canonique (si le VLM dévie).
_FR_TO_MACRO = [
    (("téléphone", "smartphone", "objets connectés", "phone"), "Cell_Phones_and_Accessories"),
    (("console", "jeux vidéo", "jeu vidéo", "gaming"), "Video_Games"),
    (("bricolage", "outillage", "jardinage", "outil"), "Tools_and_Home_Improvement"),
    (("ordinateur", "informatique", "image & son", "électronique", "tablette", "tv", "photo"),
     "Electronics"),
]

CARD_PROMPT = (
    "This image is a scraped second-hand marketplace (leboncoin) listing card. "
    "Read it and reply in STRICT JSON only, no markdown:\n"
    '{"true_name": "normalized product name (brand + model + variant)",\n'
    ' "category_fr": "the listing category shown (Catégorie field)",\n'
    ' "macro": "ONE of EXACTLY: Electronics | Cell_Phones_and_Accessories | Video_Games | '
    'Tools_and_Home_Improvement",\n'
    ' "true_category_path": "fine taxonomy in English, format A > B > C",\n'
    ' "price_eur": <number or null>,\n'
    ' "condition": "état shown (e.g. Pour pièces, Bon état) or empty",\n'
    ' "seller_metadata": "short text a seller would type (brand + model + keywords)"}'
)


def _render(page: fitz.Page) -> Image.Image:
    pix = page.get_pixmap(dpi=RENDER_DPI)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _crop_photo(img: Image.Image) -> Image.Image:
    """Retire la bande légende du haut puis recadre sur le contenu non-blanc."""
    w, h = img.size
    body = img.crop((0, int(h * CAPTION_BAND), w, h))
    diff = ImageChops.difference(body, Image.new("RGB", body.size, (255, 255, 255)))
    bbox = diff.getbbox()
    return body.crop(bbox) if bbox else body


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return (s[:40] or "produit").strip("_")


def _next_index() -> int:
    if not DATASET_DIR.exists():
        return 1
    nums = [
        int(m.group(1))
        for d in DATASET_DIR.iterdir()
        if d.is_dir() and (m := re.match(r"(\d+)_", d.name))
    ]
    return (max(nums) + 1) if nums else 1


def _already_ingested() -> set[str]:
    out: set[str] = set()
    if not DATASET_DIR.exists():
        return out
    for d in DATASET_DIR.iterdir():
        mf = d / "meta.json"
        if mf.exists():
            with contextlib.suppress(json.JSONDecodeError):
                out.add(json.loads(mf.read_text(encoding="utf-8")).get("source_pdf", ""))
    return out


def _map_macro(macro: str, category_fr: str) -> str:
    macro = macro.strip()
    if macro in MACROS:
        return macro
    if macro.lower() in _MACRO_ALIASES:
        return _MACRO_ALIASES[macro.lower()]
    blob = f"{macro} {category_fr}".lower()
    for keys, m in _FR_TO_MACRO:
        if any(k in blob for k in keys):
            return m
    return ""


def _read_card(card: Image.Image) -> dict | None:
    """Lit la carte (page 0) via le VLM OpenRouter → champs structurés (None si pas de clé)."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    import requests

    buf = io.BytesIO()
    card.save(buf, format="JPEG", quality=85)
    data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    content = [
        {"type": "text", "text": CARD_PROMPT},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    r = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": VLM_MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": content}]},
        timeout=90,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def ingest_one(pdf: Path) -> str:
    doc = fitz.open(pdf)
    if doc.page_count < 2:
        return "skip (pas de page photo)"
    # page 0 = carte ; pages 1.. = photos
    fields = _read_card(_render(doc[0])) or {}
    macro = _map_macro(str(fields.get("macro", "")), str(fields.get("category_fr", "")))
    name = str(fields.get("true_name") or pdf.stem.replace("LBC-", ""))

    idx = _next_index()
    target = DATASET_DIR / f"{idx:02d}_{_slugify(name)}"
    target.mkdir(parents=True, exist_ok=False)

    photos: list[str] = []
    for i in range(1, doc.page_count):
        crop = _crop_photo(_render(doc[i]))
        fname = f"{i:02d}.jpg"
        crop.save(target / fname, quality=90)
        photos.append(fname)

    annotated = bool(fields and macro)
    meta = {
        "source_pdf": pdf.name,
        "true_name": name,
        "macro": macro,
        "category_fr": str(fields.get("category_fr", "")),
        "true_category_path": str(fields.get("true_category_path", "")),
        "price_eur": fields.get("price_eur"),
        "condition": str(fields.get("condition", "")),
        "seller_metadata": str(fields.get("seller_metadata") or name),
        "photos": photos,
        "main_photo": photos[0] if photos else "",
        "annotated": annotated,
    }
    (target / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tag = f"{macro or '?'} | {name[:40]}" + ("" if annotated else "  (champs à dériver)")
    return f"{target.name} ({len(photos)} photos) → {tag}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="dossier des PDF (défaut: ~/Downloads)")
    ap.add_argument("--limit", type=int, default=0, help="n'ingérer que N PDF (0 = tous)")
    args = ap.parse_args()

    src = Path(args.src)
    pdfs = sorted(src.glob("LBC-*.pdf"))
    done = _already_ingested()
    todo = [p for p in pdfs if p.name not in done]
    if args.limit:
        todo = todo[: args.limit]
    log.info("%d PDF trouvés, %d déjà ingérés → %d à traiter.", len(pdfs), len(done), len(todo))
    if not os.environ.get("OPENROUTER_API_KEY"):
        log.warning("Pas de clé OpenRouter → photos extraites mais champs à dériver ensuite.")

    for p in todo:
        try:
            log.info("✓ %s", ingest_one(p))
        except Exception as e:  # noqa: BLE001 — un PDF cassé ne doit pas arrêter le lot
            log.warning("✗ %s : %s", p.name, e)


if __name__ == "__main__":
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    main()

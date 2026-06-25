"""Bench qualité de fiche & richesse d'entrée — NOYAU (Cycle 34.4+, protocole D-042).

Évalue **la fiche produite** (pas un proxy) sous un design factoriel d'entrées, sur les vraies
annonces (`data/photos_eval/`). Ce fichier (34.4) produit les **sorties brutes** par
(produit, condition) ; les métriques dures (34.5), les stats appariées (34.6) et MLflow (34.7)
s'appuieront dessus.

Conditions (richesse d'entrée croissante, design factoriel) :
- **C0**  : texte vendeur seul (FR), 0 photo            — baseline texte
- **C0t** : texte vendeur traduit EN                    — isole la LANGUE
- **C1**  : 1 photo                                      — base photo (extraction VLM)
- **C2**  : N photos (≤4)                                — multi-vues
- **C3**  : N photos + texte vendeur (FR brut)          — + métadonnée
- **C3t** : N photos + texte vendeur traduit            — + traduction

Garde-fous de VALIDITÉ : extraction VLM **mise en cache** (C2/C3/C3t partagent UNE extraction —
sinon on confond métadonnée et tirage VLM) ; **anti-fuite** = on logge `seller_meta_overlap` par
produit pour stratifier (gain métadonnée crédible sur les produits SANS recouvrement).

Lancer :
    PHOTO_BENCH_LIMIT=5 .venv/Scripts/python.exe -m src.retrieval.07_listing_quality_bench  # smoke
    .venv/Scripts/python.exe -m src.retrieval.07_listing_quality_bench                       # complet
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path

from src.api.pipeline import IdentificationService
from src.config import REPO_ROOT
from src.serving.listing_fill import assemble_listing
from src.vlm.extract_cache import ExtractionCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
REPORT_DIR = REPO_ROOT / "reports" / "05_retrieval"
CACHE_PATH = DATASET_DIR / "_cache" / "extractions.jsonl"
RAW_OUT = REPORT_DIR / "listing_quality_raw.jsonl"
CONDITIONS = ["C0", "C0t", "C1", "C2", "C3", "C3t"]
LIMIT = int(os.environ.get("PHOTO_BENCH_LIMIT", "0"))
RELIABLE = 0.60  # seuil match fiable (= IDENTIFIED_THRESHOLD)

CONDITION_FR = {
    "neuf": "Neuf",
    "tres_bon_etat": "Très bon état",
    "bon_etat": "Bon état",
    "correct": "État correct",
}


def _macro_vote(candidates) -> str:
    acc: dict[str, float] = defaultdict(float)
    for c in candidates:
        acc[c.category] += max(0.0, c.score)
    return max(acc, key=acc.get) if acc else ""


def _load_products() -> list[tuple]:
    out = []
    for d in sorted(DATASET_DIR.iterdir()):
        f = d / "meta.json"
        if d.is_dir() and f.exists():
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("annotated") and m.get("photos") and m.get("true_category_path"):
                out.append((d, m))
    return out[:LIMIT] if LIMIT else out


def _conditions_for(meta: dict, photos: list[Path], cache: ExtractionCache) -> dict:
    """Construit les 6 conditions : (query, translate, photo_attributes). Extraction cachée."""
    seller = meta.get("seller_metadata", "")
    ext1, _ = cache.get_or_extract([photos[0]])
    extn, _ = cache.get_or_extract(photos[:4]) if len(photos) > 1 else (ext1, True)
    c3q = f"{extn.title_guess} {seller}".strip()
    return {
        "C0": (seller, False, {}),
        "C0t": (seller, True, {}),
        "C1": (ext1.title_guess, False, ext1.attributes),
        "C2": (extn.title_guess, False, extn.attributes),
        "C3": (c3q, False, extn.attributes),
        "C3t": (c3q, True, extn.attributes),
    }


def run() -> None:
    log.info("Chargement IdentificationService (index FAISS HNSW)…")
    ident = IdentificationService()
    ident.load()
    cache = ExtractionCache(CACHE_PATH)
    products = _load_products()
    log.info("%d produits × %d conditions.", len(products), len(CONDITIONS))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw_records: list[dict] = []

    for k, (d, meta) in enumerate(products, 1):
        photos = [d / p for p in meta["photos"]]
        cond_label = CONDITION_FR.get(meta.get("condition_key", "bon_etat"), "Bon état")
        try:
            conds = _conditions_for(meta, photos, cache)
        except Exception as e:  # noqa: BLE001 — un produit en échec n'arrête pas le run
            log.warning("skip %s (extraction VLM) : %s", d.name, e)
            continue

        for cond, (query, translate, photo_attrs) in conds.items():
            res = ident.identify(query, translate=translate)
            top1 = res.candidates[0] if res.candidates else None
            listing = assemble_listing(
                category_leaf=res.predicted_category_fine,
                category_confidence=res.predicted_category_confidence,
                condition_label=cond_label,
                photo_attributes=photo_attrs,
                seller_metadata=meta.get("seller_metadata", ""),
                match_brand=top1.brand if top1 else "",
                match_attributes=top1.attributes if top1 else None,
                match_reliable=bool(top1 and top1.score >= RELIABLE),
                expected_facets=None,  # schéma FIXE par catégorie → 34.5
            )
            raw_records.append(
                {
                    "product": d.name,
                    "condition": cond,
                    # entrées de stratification
                    "metadata_quality": meta.get("metadata_quality", {}).get("score", 0),
                    "is_overlap": meta.get("seller_meta_overlap", {}).get("is_overlap", False),
                    "n_photos": len(photos),
                    "macro": meta.get("macro", ""),
                    # vérité terrain
                    "true_name": meta.get("true_name", ""),
                    "true_category_path": meta.get("true_category_path", ""),
                    # prédictions / fiche produite
                    "pred_macro": _macro_vote(res.candidates),
                    "pred_leaf": res.predicted_category_fine,
                    "pred_path": res.predicted_category_path,
                    "status": res.status,
                    "confidence": round(float(res.predicted_category_confidence), 4),
                    "cascade_level": listing.level,
                    "completeness": listing.completeness,
                    "n_fields": len(listing.fields),
                    "fields": [
                        {"name": f.name, "value": f.value, "source": f.source}
                        for f in listing.fields
                    ],
                }
            )
        log.info("[%d/%d] %s — 6 conditions OK", k, len(products), d.name[:34])

    with RAW_OUT.open("w", encoding="utf-8") as f:
        for r in raw_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("Sorties brutes : %s (%d lignes)", RAW_OUT, len(raw_records))

    if LIMIT:  # smoke : sanity par condition sur le 1er produit
        _smoke_print(raw_records)


def _smoke_print(rows: list[dict]) -> None:
    if not rows:
        log.warning("Aucune ligne (dataset vide ?)")
        return
    first = rows[0]["product"]
    log.info("=== SMOKE — produit %s ===", first)
    log.info(
        "%-5s %-9s %-26s %-5s %-5s %s", "cond", "status", "leaf prédite", "conf", "compl", "niveau"
    )
    for r in rows:
        if r["product"] != first:
            continue
        log.info(
            "%-5s %-9s %-26s %-5.2f %-5.2f %s",
            r["condition"],
            r["status"],
            (r["pred_leaf"] or "—")[:26],
            r["confidence"],
            r["completeness"],
            r["cascade_level"],
        )


if __name__ == "__main__":
    run()

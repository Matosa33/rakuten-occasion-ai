"""Comparaison d'extracteurs VLM (Cycle 34.8, protocole D-042).

Quelle VLM lit le mieux les photos pour produire une bonne fiche ? Pour 4 extracteurs **VISION
vérifiés sur OpenRouter** (tous bon marché), sur la condition **C2 (N photos)** — celle qui dépend
du modèle — on produit la fiche et on mesure la qualité (métriques dures 34.5) + la latence.

Index chargé **UNE fois** (on boucle les modèles dessus). Cache d'extraction **keyé par modèle**
→ sans collision, incrémental (Gemma déjà en cache via le run baseline). Coût ~centimes.

Lancer :
    PHOTO_BENCH_LIMIT=3 .venv/Scripts/python.exe -m src.retrieval.08_extractor_comparison  # smoke
    .venv/Scripts/python.exe -m src.retrieval.08_extractor_comparison                       # complet
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict

from src.api.pipeline import IdentificationService
from src.config import REPO_ROOT
from src.retrieval.listing_quality_metrics import induce_expected_facets, metrics_for
from src.serving.listing_fill import assemble_listing
from src.vlm import photo_extraction
from src.vlm.extract_cache import ExtractionCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
REPORT_DIR = REPO_ROOT / "reports" / "05_retrieval"
CACHE_PATH = DATASET_DIR / "_cache" / "extractions.jsonl"
EXPERIMENT = "rakuten-extractor-comparison"
LIMIT = int(os.environ.get("PHOTO_BENCH_LIMIT", "0"))
RELIABLE = 0.60
# 4 extracteurs VISION vérifiés (modalité image confirmée) + leur prix ($/Mtok in) pour info.
MODELS = [
    ("google/gemma-4-31b-it", 0.12),  # baseline (cache déjà chaud)
    ("xiaomi/mimo-v2.5", 0.105),
    ("google/gemini-2.5-flash-lite", 0.10),
    ("qwen/qwen3.5-flash-02-23", 0.065),
]
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


def run() -> dict:
    log.info("Chargement IdentificationService (index FAISS HNSW)…")
    # 512 tokens : équitable pour les modèles à raisonnement (mimo) qui consomment du budget
    # en `reasoning`. Inclus dans la clé de cache → namespace propre (ne mélange pas avec 250).
    photo_extraction.VLM_MAX_TOKENS = 512
    ident = IdentificationService()
    ident.load()
    cache = ExtractionCache(CACHE_PATH)
    products = _load_products()
    expected = induce_expected_facets()
    keys = [
        "macro_acc",
        "leaf_exact",
        "leaf_overlap",
        "entity_match",
        "brand_correct",
        "completeness",
        "usable",
    ]

    results: dict[str, dict] = {}
    raw_records: list[dict] = []  # une ligne par (produit, modèle) : vraies valeurs inspectables
    for model, price in MODELS:
        photo_extraction.VLM_MODEL = model  # le cache key inclut le modèle → pas de collision
        per: dict[str, list] = defaultdict(list)
        latencies: list[float] = []
        for d, meta in products:
            photos = [d / p for p in meta["photos"]]
            try:
                t0 = time.perf_counter()
                ext, hit = cache.get_or_extract(photos[:4])
                if not hit:
                    latencies.append(time.perf_counter() - t0)
            except Exception as e:  # noqa: BLE001
                log.warning("skip %s (%s) : %s", d.name, model, e)
                continue
            res = ident.identify(ext.title_guess, translate=False)
            top1 = res.candidates[0] if res.candidates else None
            listing = assemble_listing(
                category_leaf=res.predicted_category_fine,
                category_confidence=res.predicted_category_confidence,
                condition_label=CONDITION_FR.get(meta.get("condition_key", "bon_etat"), "Bon état"),
                photo_attributes=ext.attributes,
                seller_metadata=meta.get("seller_metadata", ""),
                match_brand=top1.brand if top1 else "",
                match_attributes=top1.attributes if top1 else None,
                match_reliable=bool(top1 and top1.score >= RELIABLE),
            )
            rec = {
                "macro": meta.get("macro", ""),
                "pred_macro": _macro_vote(res.candidates),
                "pred_path": res.predicted_category_path,
                "true_category_path": meta.get("true_category_path", ""),
                "true_name": meta.get("true_name", ""),
                "top1_title": top1.title if top1 else "",
                "fields": [
                    {"name": f.name, "value": f.value, "source": f.source} for f in listing.fields
                ],
            }
            m = metrics_for(rec, expected)
            for key in keys:
                per[key].append(m[key])
            raw_records.append(
                {
                    "product": d.name,
                    "model": model,
                    "true_name": meta.get("true_name", ""),
                    "extracted_title": ext.title_guess,
                    "extracted_attrs": ext.attributes,
                    "top1_title": rec["top1_title"],
                    "entity_match": m["entity_match"],
                    "leaf_exact": m["leaf_exact"],
                    "completeness": m["completeness"],
                }
            )
        results[model] = {
            "price_usd_per_mtok_in": price,
            "n": len(per["completeness"]),
            "mean_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
            **{key: round(sum(per[key]) / len(per[key]), 4) if per[key] else 0.0 for key in keys},
        }
        log.info(
            "%-32s entity=%.3f completeness=%.3f macro=%.3f",
            model,
            results[model]["entity_match"],
            results[model]["completeness"],
            results[model]["macro_acc"],
        )

    (REPORT_DIR / "extractor_comparison_raw.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in raw_records) + "\n", encoding="utf-8"
    )
    summary = {"by_model": results, "condition": "C2 (N photos)", "n_products": len(products)}
    _log_mlflow(summary)
    _write_report(summary)
    return summary


def _log_mlflow(summary: dict) -> None:
    try:
        import mlflow

        from src.mlops.mlflow_utils import setup_mlflow

        setup_mlflow()
        mlflow.set_experiment(EXPERIMENT)
        for model, m in summary["by_model"].items():
            with mlflow.start_run(run_name=model.split("/")[-1]):
                mlflow.set_tags({"extractor": model})
                mlflow.log_metrics({k: v for k, v in m.items() if isinstance(v, int | float)})
        print(f"Tracé MLflow ({EXPERIMENT}).")
    except Exception as e:  # noqa: BLE001
        print("MLflow indisponible :", e)


def _write_report(summary: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "extractor_comparison.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    cols = [
        "entity_match",
        "leaf_exact",
        "completeness",
        "macro_acc",
        "mean_latency_s",
        "price_usd_per_mtok_in",
    ]
    lines = [
        "# Comparaison d'extracteurs VLM — condition C2 (N photos)",
        "",
        f"- **{summary['n_products']} produits** · métriques dures · cache keyé par modèle.",
        "",
        "| Extracteur | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for model, m in summary["by_model"].items():
        lines.append(f"| {model} | " + " | ".join(str(m.get(c, "—")) for c in cols) + " |")
    lines += [
        "",
        "> `entity_match` = identification du bon produit ; `completeness` = remplissage ;",
        "> `mean_latency_s` = latence moyenne d'extraction ; prix = $/Mtok entrée.",
    ]
    (REPORT_DIR / "extractor_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Rapport :", REPORT_DIR / "extractor_comparison.md")


if __name__ == "__main__":
    run()

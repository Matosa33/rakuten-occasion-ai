"""Phase 2 — richesse d'entrée : prouver **1 photo < N photos < N + métadonnée**.

Pour chaque produit d'éval réel (`data/photos_eval/`, ingéré depuis les annonces scrappées),
on rejoue 3 conditions d'entrée et on mesure la qualité d'identification :

- **C1** : photo principale seule (`01`) → extraction VLM → requête.
- **C2** : toutes les photos → extraction VLM (multi-vues) → requête.
- **C3** : C2 **+ la métadonnée vendeur** (titre verbatim) ajoutée à la requête.

Chaîne commune : extraction VLM (Gemma) → retrieval FAISS + **vote A2** → macro + taxo + confiance.
Traduction FR→EN **désactivée** ici pour isoler la variable « richesse d'entrée » (les titres
VLM sont déjà en anglais ; en prod la traduction ajoute un gain connu et séparé de +0,085).

Mesures (vérité terrain = `meta.json` dérivé des annonces) :
- **macro_acc** : la macro-catégorie prédite (vote pondéré des voisins) est-elle correcte ;
- **fine_overlap** : recouvrement (Jaccard de mots) entre le breadcrumb réel et le breadcrumb
  prédit — score fin robuste aux écarts de formulation entre taxonomies ;
- **confidence** : part du vote A2.
On **stratifie le gain C3−C2 par `metadata_quality`** → la métadonnée aide ∝ sa qualité.

Chaque condition = un run MLflow (`rakuten-photo-richness`) + rapport
`reports/05_retrieval/photo_richness_bench.{md,json}`.

Lancer :

    .venv/Scripts/python.exe -m src.retrieval.06_photo_richness_bench
    PHOTO_BENCH_LIMIT=5 .venv/Scripts/python.exe -m src.retrieval.06_photo_richness_bench  # validation
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict

from src.api.pipeline import IdentificationService
from src.config import REPO_ROOT
from src.vlm import photo_extraction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
REPORT_DIR = REPO_ROOT / "reports" / "05_retrieval"
EXPERIMENT = "rakuten-photo-richness"
# C3  = métadonnée vendeur BRUTE (FR), sans traduction (isole l'effet texte pur).
# C3t = métadonnée TRADUITE FR→EN avant recherche = conditions réelles de production.
CONDITIONS = ["C1", "C2", "C3", "C3t"]
LIMIT = int(os.environ.get("PHOTO_BENCH_LIMIT", "0"))


def _macro_vote(candidates) -> str:
    """Macro-catégorie par vote pondéré par similarité des candidats."""
    acc: dict[str, float] = defaultdict(float)
    for c in candidates:
        acc[c.category] += max(0.0, c.score)
    return max(acc, key=acc.get) if acc else ""


def _overlap(a: str, b: str) -> float:
    """Jaccard de mots entre deux breadcrumbs (robuste aux formulations différentes)."""
    wa = set(re.findall(r"[a-z0-9]+", (a or "").lower()))
    wb = set(re.findall(r"[a-z0-9]+", (b or "").lower()))
    return len(wa & wb) / len(wa | wb) if (wa and wb) else 0.0


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


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
    ident = IdentificationService()
    ident.load()

    products = _load_products()
    log.info("%d produits d'éval à évaluer × %d conditions.", len(products), len(CONDITIONS))

    rows: list[dict] = []
    t0 = time.perf_counter()
    for k, (d, meta) in enumerate(products, 1):
        photos = [d / p for p in meta["photos"]]
        try:
            ext1 = photo_extraction.extract([photos[0]])
            ext2 = photo_extraction.extract(photos) if len(photos) > 1 else ext1
        except Exception as e:  # noqa: BLE001 — un produit qui échoue ne casse pas le run
            log.warning("skip %s (extraction VLM) : %s", d.name, e)
            continue

        meta_txt = meta.get("seller_metadata", "")
        c3q = f"{ext2.title_guess} {meta_txt}".strip()
        queries = {
            "C1": (ext1.title_guess, False),  # 1 photo
            "C2": (ext2.title_guess, False),  # N photos
            "C3": (c3q, False),  # N + métadonnée brute (FR)
            "C3t": (c3q, True),  # N + métadonnée traduite FR→EN (production)
        }
        gt_macro = meta["macro"]
        gt_path = meta.get("true_category_path", "")
        rec = {
            "product": d.name,
            "quality": meta.get("metadata_quality", {}).get("score", 0),
            "n_photos": len(photos),
        }
        for cond, (query, tr) in queries.items():
            res = ident.identify(query, translate=tr)
            pm = _macro_vote(res.candidates)
            rec[cond] = {
                "macro_ok": int(pm == gt_macro),
                "fine_overlap": round(_overlap(gt_path, res.predicted_category_path), 4),
                "confidence": round(float(res.predicted_category_confidence), 4),
            }
        rows.append(rec)
        log.info("[%d/%d] %s q=%s : overlap C1/C2/C3/C3t=%.2f/%.2f/%.2f/%.2f",
                 k, len(products), d.name[:30], rec["quality"], rec["C1"]["fine_overlap"],
                 rec["C2"]["fine_overlap"], rec["C3"]["fine_overlap"], rec["C3t"]["fine_overlap"])

    # ---- agrégats par condition ----
    agg = {
        c: {
            "macro_acc": round(_mean([r[c]["macro_ok"] for r in rows]), 4),
            "fine_overlap": round(_mean([r[c]["fine_overlap"] for r in rows]), 4),
            "confidence": round(_mean([r[c]["confidence"] for r in rows]), 4),
        }
        for c in CONDITIONS
    }
    # ---- gain métadonnée traduite (C3t−C2) stratifié par qualité de métadonnée ----
    by_q: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        by_q[r["quality"]].append(r["C3t"]["fine_overlap"] - r["C2"]["fine_overlap"])
    strat = {str(q): {"gain_c3t_c2": round(_mean(v), 4), "n": len(v)} for q, v in sorted(by_q.items())}

    summary = {
        "n_products": len(rows),
        "elapsed_sec": round(time.perf_counter() - t0, 1),
        "by_condition": agg,
        "c3t_minus_c2_gain_by_metadata_quality": strat,
        "note": "C3=métadonnée brute FR (sans traduction) ; C3t=métadonnée traduite FR→EN (production)",
    }
    _log_mlflow(summary)
    _write_report(summary, rows)
    log.info("FAIT : C1/C2/C3 fine_overlap = %.3f / %.3f / %.3f",
             agg["C1"]["fine_overlap"], agg["C2"]["fine_overlap"], agg["C3"]["fine_overlap"])
    return summary


def _log_mlflow(summary: dict) -> None:
    try:
        import mlflow

        from src.mlops.mlflow_utils import setup_mlflow

        setup_mlflow()
        mlflow.set_experiment(EXPERIMENT)
        for cond, m in summary["by_condition"].items():
            with mlflow.start_run(run_name=cond):
                mlflow.set_tags({"condition": cond, "task": "photo_richness"})
                mlflow.log_param("n_products", summary["n_products"])
                mlflow.log_metrics(m)
        with mlflow.start_run(run_name="gain_by_quality"):
            for q, g in summary["c3t_minus_c2_gain_by_metadata_quality"].items():
                mlflow.log_metric(f"gain_c3t_c2_q{q}", g["gain_c3t_c2"])
        log.info("Conditions tracées dans MLflow ('%s').", EXPERIMENT)
    except Exception as e:  # noqa: BLE001
        log.warning("MLflow indisponible (scores calculés) : %s", e)


def _write_report(summary: dict, rows: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "photo_richness_bench.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    a = summary["by_condition"]

    def _row(label, c):
        return f"| {label} | {a[c]['macro_acc']:.3f} | {a[c]['fine_overlap']:.3f} | {a[c]['confidence']:.3f} |"

    lines = [
        "# Phase 2 — richesse d'entrée (1 photo < N photos < N + métadonnée)",
        "",
        f"- **{summary['n_products']} produits réels** d'éval · extraction VLM Gemma 4 31B · "
        "retrieval + vote A2.",
        f"- {summary['note']}",
        "",
        "| Condition | macro_acc | fine_overlap | confiance |",
        "|---|---|---|---|",
        _row("C1 — 1 photo", "C1"),
        _row("C2 — N photos", "C2"),
        _row("C3 — N + métadonnée brute (FR)", "C3"),
        _row("**C3t — N + métadonnée traduite (prod)**", "C3t"),
        "",
        "## Gain C3t−C2 (métadonnée traduite) par qualité de métadonnée (`metadata_quality` /5)",
        "",
        "| Qualité /5 | gain fine_overlap (C3t−C2) | n |",
        "|---|---|---|",
    ]
    for q, g in summary["c3t_minus_c2_gain_by_metadata_quality"].items():
        lines.append(f"| {q} | {g['gain_c3t_c2']:+.3f} | {g['n']} |")
    lines += [
        "",
        "> Lecture : `fine_overlap` = recouvrement breadcrumb réel ↔ prédit. C1→C2 = apport des "
        "photos multiples ; C2→C3t = apport de la métadonnée (traduite, conditions production). "
        "Le gain stratifié montre si la métadonnée aide ∝ sa qualité.",
    ]
    (REPORT_DIR / "photo_richness_bench.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Rapport : %s", REPORT_DIR / "photo_richness_bench.md")


if __name__ == "__main__":
    run()

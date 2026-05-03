"""Cycle 3 — Bench global M1-M6.

Agrège les JSON de métriques produits par M1-M5 + M6 fusion en un rapport
markdown comparatif. Permet la sélection du modèle vainqueur pour MLflow
Registry alias `@Production` (Cycle 11).

Sortie :
- `reports/04_classifiers_bench/bench_v1.md` (synthèse humaine)
- `reports/04_classifiers_bench/bench_v1.json` (machine-readable)

Lance APRÈS M1-M6 :

    python -m src.classifiers.07_bench_report
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import REPORTS_CLASSIFIERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_FILES = [
    "m1_knn_v1.json",
    "m2_svm_v1.json",
    "m3_rf_v1.json",
    "m4_mlp_v1.json",
    "m5_tfidf_linsvc_v1.json",
    "m6_fusion_v1.json",
]

OUT_MD = REPORTS_CLASSIFIERS / "bench_v1.md"
OUT_JSON = REPORTS_CLASSIFIERS / "bench_v1.json"


def _load_metrics(path: Path) -> dict | None:
    """Load JSON métriques d'un modèle, ou None si absent."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _format_row(model_metrics: dict) -> dict:
    """Extrait une ligne synthétique d'un modèle pour le rapport tabulaire."""
    test = model_metrics.get("results", {}).get("test", {})
    val = model_metrics.get("results", {}).get("val", {})
    return {
        "model": model_metrics.get("model", "?"),
        "type": model_metrics.get("type", "?"),
        "f1_w_test": test.get("f1_weighted", 0),
        "f1_w_val": val.get("f1_weighted", 0),
        "f1_macro_test": test.get("f1_macro", 0),
        "accuracy_test": test.get("accuracy", 0),
        "top_3_test": test.get("top_3_accuracy", 0),
        "ece_test": test.get("ece", 0),
        "duration_train_sec": model_metrics.get("duration_train_sec", 0),
    }


def main() -> None:
    log.info("=== Cycle 3 — Bench global M1-M6 ===")

    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    rows = []
    for fname in MODEL_FILES:
        path = REPORTS_CLASSIFIERS / fname
        m = _load_metrics(path)
        if m is None:
            log.warning("  ⚠️ %s introuvable, skip", fname)
            continue
        rows.append(_format_row(m))

    if not rows:
        log.error("Aucun modèle trouvé. Lance d'abord les scripts M1-M6.")
        return

    # Tri par F1 weighted test décroissant (vainqueur en premier)
    rows.sort(key=lambda r: r["f1_w_test"], reverse=True)
    winner = rows[0]
    log.info("Vainqueur : %s (F1_w_test=%.4f)", winner["model"], winner["f1_w_test"])

    # Format markdown
    lines = [
        "# Bench classifieurs Cycle 3 — M1-M6",
        "",
        "> Synthèse comparative des 6 modèles entraînés en Cycle 3 (P04, C12-C15).",
        "> Tri par F1_weighted_test décroissant. Vainqueur en haut → MLflow alias `@Production` (Cycle 11).",
        "",
        "## Comparaison",
        "",
        "| Rang | Modèle | Type | F1_w test | F1_w val | F1_macro test | Acc test | Top-3 test | ECE test | Train (s) |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, r in enumerate(rows, 1):
        lines.append(
            f"| {rank} | **{r['model']}** | {r['type']} | "
            f"**{r['f1_w_test']:.4f}** | {r['f1_w_val']:.4f} | "
            f"{r['f1_macro_test']:.4f} | {r['accuracy_test']:.4f} | "
            f"{r['top_3_test']:.4f} | {r['ece_test']:.4f} | {r['duration_train_sec']:.0f} |"
        )

    lines.extend(
        [
            "",
            "## Lecture",
            "",
            f"- **Vainqueur** : `{winner['model']}` avec F1_weighted test = **{winner['f1_w_test']:.4f}**",
            "- **Calibration la mieux** : modèle avec ECE test minimum (cible < 0.05)",
            "- **Latence inférence** : non mesurée ici (à mesurer en Cycle 11 quand on serve via API)",
            "",
            "## Décision",
            "",
            f"Pour MLflow Registry (Cycle 11), promouvoir `{winner['model']}` au stage `@Production`. ",
            "Les autres modèles restent disponibles via alias `@Latest` pour A/B test futur.",
            "",
            "## Fusion adaptive",
            "",
        ]
    )

    fusion_row = next((r for r in rows if "fusion" in r["model"].lower()), None)
    if fusion_row:
        best_individual = max(
            (r for r in rows if "fusion" not in r["model"].lower()),
            key=lambda r: r["f1_w_test"],
        )
        gain = fusion_row["f1_w_test"] - best_individual["f1_w_test"]
        gain_str = f"+{gain:.4f}" if gain >= 0 else f"{gain:.4f}"
        lines.extend(
            [
                f"- M6 fusion (`{fusion_row['model']}`) F1_w test = {fusion_row['f1_w_test']:.4f}",
                f"- Meilleur modèle individuel : `{best_individual['model']}` à {best_individual['f1_w_test']:.4f}",
                f"- **Gain fusion vs best individual : {gain_str}**",
                "  - Si gain > +0,02 : la fusion vaut son coût computationnel (predict 4-5 modèles)",
                "  - Si gain < +0,02 : préférer le modèle individuel le plus rapide",
            ]
        )
    else:
        lines.append("- M6 fusion non disponible (lance src.classifiers.06_fusion_adaptive)")

    lines.extend(
        [
            "",
            "## Annexes",
            "",
            "- Scripts : `src/classifiers/01..06_*.py`",
            "- Module métriques : `src/classifiers/metrics.py`",
            "- JSON détaillés : `reports/04_classifiers_bench/m{1..6}_*.json`",
            "- ADR référencées : D-009 (RAG-grounded), D-011 (4 cat MVP)",
            "- Règle R3 : anti-leakage strict (fit train, predict val/test)",
        ]
    )

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps({"rows": rows, "winner": winner}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info("→ %s + %s", OUT_MD.name, OUT_JSON.name)
    log.info("Cycle 3 bench OK.")


if __name__ == "__main__":
    main()

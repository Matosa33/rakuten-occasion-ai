"""Analyse finale du bench qualité de fiche (Cycle 34.7, protocole D-042).

Relie tout : lit le brut (`listing_quality_raw.jsonl`), calcule les métriques dures (34.5),
applique les stats appariées (34.6), trace MLflow et écrit le rapport chiffré.

Comparaisons confirmatoires (appariées) :
- **HV** valeur de la photo : one-photo vs text-only (stratifié `metadata_quality`≤2).
- **H1** multi-photos       : one-photo vs multi-photo + Page's L sur text-only→one-photo→multi-photo→multi-photo-meta.
- **H1b** métadonnée        : multi-photo vs multi-photo-meta (Wilcoxon + **TOST** non-effet) - stratifié `is_overlap=False`.
- **H1c** traduction nuit   : multi-photo-meta vs multi-photo-meta-fr-en.

Lancer (après `07_listing_quality_bench`) :
    .venv/Scripts/python.exe -m src.retrieval.listing_quality_report
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from src.config import REPO_ROOT
from src.retrieval.listing_quality_metrics import aggregate, induce_expected_facets, metrics_for
from src.retrieval.listing_quality_stats import (
    RICHNESS_ORDER,
    clustered_bootstrap_ci,
    page_trend,
    paired_values,
    product_family,
    tost_equivalence,
    wilcoxon_pair,
)

REPORT_DIR = REPO_ROOT / "reports" / "05_retrieval"
RAW_IN = REPORT_DIR / "listing_quality_raw.jsonl"
EXPERIMENT = "rakuten-listing-quality"
SESOI = 0.05  # seuil métier d'équivalence (leaf_overlap/completeness) : < 1 mot de breadcrumb
HEADLINE = "completeness"  # métrique principale (fiche produite)


def _per_product(records: list[dict], expected: dict, metric: str, subset=None) -> dict:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for r in records:
        if subset and not subset(r):
            continue
        out[r["product"]][r["condition"]] = metrics_for(r, expected)[metric]
    return out


def _compare(records, expected, metric, ca, cb, subset=None) -> dict:
    pp = _per_product(records, expected, metric, subset)
    prods, mat = paired_values(pp, [ca, cb])
    if len(prods) < 3:
        return {"n": len(prods), "note": "trop peu de paires"}
    # gain = b - a (sens « b améliore-t-il a »). median_diff aligné sur l'IC (même direction).
    w = wilcoxon_pair(mat[cb], mat[ca])
    fams = [product_family(p) for p in prods]
    diff = [mat[cb][i] - mat[ca][i] for i in range(len(prods))]
    ci = clustered_bootstrap_ci(diff, fams)
    return {"metric": metric, "a": ca, "b": cb, "n": len(prods), **w, "gain_ci": ci}


def run() -> dict:
    records = [
        json.loads(line) for line in RAW_IN.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    expected = induce_expected_facets()
    agg = aggregate(records, expected)

    # Page's L (monotonie richesse) sur les métriques continues.
    trends = {}
    for metric in ("completeness", "leaf_overlap"):
        prods, mat = paired_values(_per_product(records, expected, metric), RICHNESS_ORDER)
        trends[metric] = page_trend(mat, RICHNESS_ORDER) if len(prods) >= 3 else {"n": len(prods)}

    clean = lambda r: not r.get("is_overlap", False)  # noqa: E731
    poor = lambda r: r.get("metadata_quality", 0) <= 2  # noqa: E731

    comparisons = {
        # completeness (remplissage de la fiche)
        "HV completeness photo>texte (qual<=2)": _compare(
            records, expected, "completeness", "text-only", "one-photo", poor
        ),
        "H1 completeness multiphoto (one-photo->multi-photo)": _compare(
            records, expected, "completeness", "one-photo", "multi-photo"
        ),
        "H1b completeness metadonnee (multi-photo->multi-photo-meta)": _compare(
            records, expected, "completeness", "multi-photo", "multi-photo-meta"
        ),
        "H1b completeness metadonnee sans-fuite": _compare(
            records, expected, "completeness", "multi-photo", "multi-photo-meta", clean
        ),
        "H1c completeness traduction (multi-photo-meta->multi-photo-meta-fr-en)": _compare(
            records, expected, "completeness", "multi-photo-meta", "multi-photo-meta-fr-en"
        ),
        # entity_match (identification du bon produit) - la metadonnee y prouve sa valeur
        "H2 entity multiphoto (one-photo->multi-photo)": _compare(
            records, expected, "entity_match", "one-photo", "multi-photo"
        ),
        "H2 entity metadonnee (multi-photo->multi-photo-meta)": _compare(
            records, expected, "entity_match", "multi-photo", "multi-photo-meta"
        ),
        "H2 entity metadonnee sans-fuite": _compare(
            records, expected, "entity_match", "multi-photo", "multi-photo-meta", clean
        ),
    }
    # TOST équivalence métadonnée (non-effet prédit) sur les produits sans fuite.
    pp = _per_product(records, expected, HEADLINE, clean)
    prods, mat = paired_values(pp, ["multi-photo", "multi-photo-meta"])
    tost = (
        tost_equivalence(mat["multi-photo"], mat["multi-photo-meta"], SESOI)
        if len(prods) >= 3
        else {"n": len(prods)}
    )

    summary = {
        "headline_metric": HEADLINE,
        "n_records": len(records),
        "by_condition": agg,
        "page_trend": trends,
        "comparisons": comparisons,
        "tost_metadata_clean": tost,
        "expected_facets_by_macro": expected,
    }
    _log_mlflow(summary)
    _write_report(summary)
    return summary


def _log_mlflow(summary: dict) -> None:
    try:
        import mlflow

        from src.mlops.mlflow_utils import setup_mlflow

        setup_mlflow()
        mlflow.set_experiment(EXPERIMENT)
        for cond, m in summary["by_condition"].items():
            with mlflow.start_run(run_name=cond):
                mlflow.set_tags({"condition": cond})
                mlflow.log_metrics({k: v for k, v in m.items() if isinstance(v, int | float)})
        with mlflow.start_run(run_name="comparisons"):
            for name, c in summary["comparisons"].items():
                if "p" in c:
                    safe = re.sub(r"[^A-Za-z0-9_./ -]", "_", name)[:50]  # noms MLflow valides
                    mlflow.log_metric(f"p__{safe}", c["p"])
        log_ok = True
    except Exception as e:  # noqa: BLE001
        log_ok = False
        print("MLflow indisponible :", e)
    if log_ok:
        print(f"Tracé MLflow ({EXPERIMENT}).")


def _write_report(summary: dict) -> None:
    a = summary["by_condition"]
    (REPORT_DIR / "listing_quality_report.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    cols = ["macro_acc", "leaf_exact", "leaf_overlap", "entity_match", "completeness", "usable"]
    lines = [
        "# Qualité de fiche & richesse d'entrée - résultats (Cycle 34, D-042)",
        "",
        f"- **{summary['n_records']} fiches** (produits × conditions) · métrique principale : "
        f"`{summary['headline_metric']}` · stats appariées.",
        "",
        "| Condition | " + " | ".join(cols) + " | n |",
        "|---|" + "---|" * (len(cols) + 1),
    ]
    for cond in [
        "text-only",
        "text-fr-en",
        "one-photo",
        "multi-photo",
        "multi-photo-meta",
        "multi-photo-meta-fr-en",
    ]:
        m = a.get(cond)
        if m:
            lines.append(
                f"| {cond} | " + " | ".join(f"{m[c]:.3f}" for c in cols) + f" | {m['n']} |"
            )
    lines += ["", "## Tests confirmatoires (appariés)", ""]
    for name, c in summary["comparisons"].items():
        if "p" in c:
            ci = c["gain_ci"]
            lines.append(
                f"- **{name}** : gain médian {c['median_diff']:+.3f} "
                f"(IC95 [{ci['ci_low']:+.3f}, {ci['ci_high']:+.3f}], {ci['n_families']} familles) · "
                f"p={c['p']:.4f} · n={c['n']}"
            )
        else:
            lines.append(f"- **{name}** : {c.get('note', 'n/a')} (n={c.get('n', 0)})")
    t = summary["tost_metadata_clean"]
    if "p_tost" in t:
        verdict = "ÉQUIVALENCE (métadonnée sans effet)" if t["equivalent"] else "non concluante"
        lines.append(
            f"- **TOST multi-photo≈multi-photo-meta (sans fuite, SESOI {t['sesoi']})** : {verdict} · p={t['p_tost']:.4f}"
        )
    lines += [
        "",
        "## Monotonie (Page's L, richesse text-only→one-photo→multi-photo→multi-photo-meta)",
        "",
    ]
    for metric, tr in summary["page_trend"].items():
        if "p" in tr:
            lines.append(f"- `{metric}` : L={tr['L']} · p={tr['p']:.4f}")
    (REPORT_DIR / "listing_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Rapport :", REPORT_DIR / "listing_quality_report.md")


if __name__ == "__main__":
    run()

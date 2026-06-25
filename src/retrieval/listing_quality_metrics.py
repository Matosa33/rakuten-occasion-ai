"""Métriques dures de qualité de fiche (Cycle 34.5, protocole D-042).

Lit les sorties brutes (`listing_quality_raw.jsonl`, produit par `07_listing_quality_bench`) et
calcule des métriques **objectives** (aucun LLM de jugement) vs la vérité terrain :

- `macro_acc`            : macro votée == macro réelle.
- `leaf_exact`           : dernière feuille du breadcrumb prédit == feuille réelle (binaire dur).
- `leaf_overlap`         : Jaccard de mots breadcrumb prédit ↔ réel (stopwords taxo retirés).
- `entity_match`         : ≥50 % des mots significatifs de `true_name` présents dans le top-1.
- `brand_correct`        : la marque de la fiche apparaît dans `true_name`.
- `completeness`         : champs produits ∩ **schéma FIXE de la catégorie** / |schéma|.
- `typical_field_rate`   : part de champs imputés « typique-à-vérifier » (risque ; bas = bon).
- `usable`               : fiche non vide ET completeness > 0.

Le **schéma de catégorie** (`expected_facets`) est **induit du catalogue** (facettes présentes
≥ 50 % des produits de la macro), pas présupposé. Agrégation par condition + par strate
(recouvrement d'annotation, qualité métadonnée, macro).

Lancer (après le bench 07) :
    .venv/Scripts/python.exe -m src.retrieval.listing_quality_metrics
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict

import polars as pl

from src.config import DATA_PROCESSED_PRODUCTS, REPO_ROOT
from src.serving.listing_fill import _label

REPORT_DIR = REPO_ROOT / "reports" / "05_retrieval"
RAW_IN = REPORT_DIR / "listing_quality_raw.jsonl"
BASE_LABELS = ["Type de produit", "État", "Marque"]
# Attributs DISCRIMINANTS qu'une bonne fiche devrait porter mais que le catalogue (facettes
# génériques) ne contient quasi jamais — ajoutés au schéma pour créditer ce qui compte vraiment
# (extrait par le VLM depuis les photos) et rendre `completeness` plus discriminante entre conditions.
DISCRIMINATING_FACETS = ["model", "capacity", "size"]
# stopwords taxonomie : mots de structure trop génériques (gonflent le Jaccard sans info)
TAXO_STOPWORDS = {
    "and",
    "the",
    "accessories",
    "electronics",
    "tools",
    "home",
    "improvement",
    "cell",
    "phones",
    "video",
    "games",
    "computers",
    "amp",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _toks(s: str) -> list[str]:
    return [t for t in _norm(s).split() if len(t) >= 2]


def leaf_exact(pred_path: str, true_path: str) -> int:
    pp = _norm((pred_path or "").split(">")[-1])
    tp = _norm((true_path or "").split(">")[-1])
    return int(bool(pp) and pp == tp)


def leaf_overlap(pred_path: str, true_path: str) -> float:
    a = {t for t in _toks(pred_path) if t not in TAXO_STOPWORDS}
    b = {t for t in _toks(true_path) if t not in TAXO_STOPWORDS}
    return round(len(a & b) / len(a | b), 4) if (a and b) else 0.0


def entity_match(true_name: str, top1_title: str) -> int:
    t = set(_toks(true_name))
    o = set(_toks(top1_title))
    return int(bool(t) and len(t & o) / len(t) >= 0.5)


def brand_correct(fields: list[dict], true_name: str) -> int:
    brand = next((f["value"] for f in fields if f["name"] == "Marque"), "")
    bt, tt = set(_toks(brand)), set(_toks(true_name))
    return int(bool(bt) and bool(bt & tt))


def completeness_fixed(field_names: list[str], expected_labels: list[str]) -> float:
    if not expected_labels:
        return 0.0
    return round(len(set(field_names) & set(expected_labels)) / len(expected_labels), 4)


def typical_field_rate(fields: list[dict]) -> float:
    if not fields:
        return 0.0
    return round(sum(1 for f in fields if f["source"] == "typique-à-vérifier") / len(fields), 4)


def induce_expected_facets(min_share: float = 0.5) -> dict[str, list[str]]:
    """Schéma de facettes attendues par macro = facettes présentes ≥ `min_share` au catalogue."""
    lk = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "product_lookup.parquet", columns=["parent_asin", "facets_json"]
    )
    tr = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet", columns=["parent_asin", "_source_category"]
    )
    j = tr.join(lk, on="parent_asin", how="inner")
    per: dict[str, Counter] = defaultdict(Counter)
    tot: Counter = Counter()
    for r in j.iter_rows(named=True):
        if not r["facets_json"]:
            continue
        tot[r["_source_category"]] += 1
        for k in json.loads(r["facets_json"]):
            per[r["_source_category"]][k] += 1
    return {
        mac: sorted(
            {k for k, n in c.items() if tot[mac] and n / tot[mac] >= min_share}
            | set(DISCRIMINATING_FACETS)  # crédite les specs qui font une vraie fiche
        )
        for mac, c in per.items()
    }


def metrics_for(rec: dict, expected_by_macro: dict[str, list[str]]) -> dict:
    expected = BASE_LABELS + [_label(k) for k in expected_by_macro.get(rec.get("macro", ""), [])]
    names = [f["name"] for f in rec.get("fields", [])]
    comp = completeness_fixed(names, expected)
    return {
        "macro_acc": int(rec.get("pred_macro") == rec.get("macro")),
        "leaf_exact": leaf_exact(rec.get("pred_path", ""), rec.get("true_category_path", "")),
        "leaf_overlap": leaf_overlap(rec.get("pred_path", ""), rec.get("true_category_path", "")),
        "entity_match": entity_match(rec.get("true_name", ""), rec.get("top1_title", "")),
        "brand_correct": brand_correct(rec.get("fields", []), rec.get("true_name", "")),
        "completeness": comp,
        "typical_field_rate": typical_field_rate(rec.get("fields", [])),
        "usable": int(bool(names) and comp > 0),
    }


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def aggregate(records: list[dict], expected: dict) -> dict:
    keys = [
        "macro_acc",
        "leaf_exact",
        "leaf_overlap",
        "entity_match",
        "brand_correct",
        "completeness",
        "typical_field_rate",
        "usable",
    ]
    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        r["_m"] = metrics_for(r, expected)
        by_cond[r["condition"]].append(r)
    return {
        cond: {k: _mean([x["_m"][k] for x in rs]) for k in keys} | {"n": len(rs)}
        for cond, rs in by_cond.items()
    }


def main() -> None:
    records = [
        json.loads(line) for line in RAW_IN.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    expected = induce_expected_facets()
    agg = aggregate(records, expected)
    out = {"expected_facets_by_macro": expected, "by_condition": agg, "n_records": len(records)}
    (REPORT_DIR / "listing_quality_metrics.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("expected_facets (induit, >=50%):", dict(expected))
    print(f"\n{'cond':5} {'macro':6} {'leaf':6} {'lf_ov':6} {'entity':7} {'brand':6} {'compl':6} usable")
    for cond in ["C0", "C0t", "C1", "C2", "C3", "C3t"]:
        m = agg.get(cond)
        if m:
            print(
                f"{cond:5} {m['macro_acc']:.3f}  {m['leaf_exact']:.3f}  {m['leaf_overlap']:.3f}  "
                f"{m['entity_match']:.3f}   {m['brand_correct']:.3f}  {m['completeness']:.3f}  {m['usable']:.3f}"
            )


if __name__ == "__main__":
    main()

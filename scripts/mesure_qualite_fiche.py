"""Cycle 36 - protocole de MESURE de la qualité de fiche (rigueur R21, pas d'anecdotes).

Fait passer le panel réel `data/photos_eval/` (noms de dossiers = vérité-terrain) par l'API
(/upload → /identify → /price) et mesure, de façon reproductible et chiffrée :
  - identification : rappel des tokens clés du nom de produit dans (famille IA + titre top-1) ;
  - complétude de la fiche structurée (informations_cles.completeness) ;
  - prix : niveau de cascade (L1/L1.5/L2/L3/L4) + valeur ;
  - signaux : passe raisonnée présente, catalog-miss, question discriminante.

Sortie : `reports/09_fiche_quality/mesure_fiche.{json,md}`.

Usage (API démarrée sur :8000) :
    .venv/Scripts/python.exe -m scripts.mesure_qualite_fiche [--limit N] [--base URL]

Local uniquement (data/photos_eval/ est gitignoré). Best-effort : un produit en échec est
compté `error`, le run continue.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import statistics
from pathlib import Path

import requests

import src.config  # noqa: F401 - charge .env (clé API, secret JWT) avant le reste
from src.auth.jwt_utils import create_access_token
from src.config import REPORTS_DIR

EVAL_DIR = Path("data/photos_eval")
OUT_DIR = REPORTS_DIR / "09_fiche_quality"
# Mots non discriminants (présents dans les noms mais pas identifiants) - retirés du rappel tokens.
_STOPWORDS = {"and", "the", "with", "of", "et", "le", "la", "les", "complete", "pour"}
_IMG_GLOB = ("*.jpg", "*.jpeg", "*.png", "*.webp")
_MAX_PHOTOS = 2
_IDENTIFY_OK_THRESHOLD = 0.5  # ≥ 50 % des tokens clés retrouvés → identification jugée correcte


def _expected_tokens(folder: str) -> list[str]:
    """Tokens clés de la vérité-terrain depuis le nom de dossier (« 07_coros_pace_2 » → coros/pace/2)."""
    name = re.sub(r"^\d+_", "", folder)  # retire le préfixe numérique
    toks = [t for t in re.split(r"[_\W]+", name.lower()) if len(t) >= 2 and t not in _STOPWORDS]
    return toks


def _photos(folder: str) -> list[str]:
    paths: list[str] = []
    for pat in _IMG_GLOB:
        paths.extend(sorted(glob.glob(str(EVAL_DIR / folder / pat))))
    return sorted(set(paths))[:_MAX_PHOTOS]


def _measure_one(base: str, auth: dict, folder: str) -> dict:
    photos = _photos(folder)
    if not photos:
        return {"folder": folder, "status": "no_photo"}
    ids = []
    for p in photos:
        with open(p, "rb") as f:
            r = requests.post(
                f"{base}/upload", headers=auth, files={"file": (Path(p).name, f, "image/jpeg")}, timeout=60
            )
        ids.append(r.json()["image_id"])
    d = requests.post(
        f"{base}/identify", headers=auth, json={"image_ids": ids, "text_hint": ""}, timeout=180
    ).json()
    cands = d.get("top_candidates", [])
    top1 = cands[0] if cands else None
    rz = d.get("reasoned")
    ic = d.get("informations_cles")

    # Identification : rappel des tokens clés dans (famille IA + titre top-1).
    expected = _expected_tokens(folder)
    found_text = ((rz or {}).get("product_family", "") + " " + (top1 or {}).get("title", "")).lower()
    hits = [t for t in expected if t in found_text]
    recall = len(hits) / len(expected) if expected else 0.0

    # Prix : on mime le front (catalog-miss → ancre IA ; sinon catalogue + voisins même type).
    miss = bool(rz and rz.get("catalog_miss"))
    key = lambda c: (c.get("category_fine") or c.get("category"))  # noqa: E731
    neigh = (
        []
        if miss or not top1
        else sorted([c["price"] for c in cands if key(c) == key(top1) and c.get("price")])
    )
    body = {
        "category": (top1.get("category") if top1 else "Electronics"),
        "condition": "bon_etat",
        "age_years": 2,
        "catalog_price": None if miss else (top1.get("price") if top1 else None),
        "neighbor_prices": neigh,
    }
    if rz and rz.get("reference_new_price_usd"):
        body["reference_new_price_usd"] = rz["reference_new_price_usd"]
        body["reference_new_confidence"] = rz.get("reference_new_confidence", 0)
    p = requests.post(f"{base}/price", headers=auth, json=body, timeout=30).json()

    return {
        "folder": folder,
        "status": "ok",
        "expected_tokens": expected,
        "found": (rz or {}).get("product_family", "") or (top1 or {}).get("title", ""),
        "token_recall": round(recall, 3),
        "identified_ok": recall >= _IDENTIFY_OK_THRESHOLD,
        "completeness": (ic or {}).get("completeness"),
        "price_eur": p.get("suggested_price_eur"),
        "price_level": str(p.get("confidence_level")),
        "reasoned": rz is not None,
        "catalog_miss": miss,
        "ask_question": bool(rz and rz.get("ask_question")),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = tout le panel")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    auth = {"Authorization": f"Bearer {create_access_token(subject='measure')}"}
    folders = sorted(d.name for d in EVAL_DIR.iterdir() if d.is_dir())
    if args.limit:
        folders = folders[: args.limit]

    rows: list[dict] = []
    for i, folder in enumerate(folders, 1):
        try:
            row = _measure_one(args.base, auth, folder)
        except Exception as e:  # noqa: BLE001 - best-effort par produit
            row = {"folder": folder, "status": "error", "error": str(e)[:120]}
        rows.append(row)
        m = row.get("token_recall")
        print(f"[{i}/{len(folders)}] {folder[:40]:<40} {row['status']:<8} "
              f"recall={m if m is not None else '-'} "
              f"compl={row.get('completeness')} {row.get('price_level','')}", flush=True)

    ok = [r for r in rows if r["status"] == "ok"]
    n = len(ok) or 1
    levels: dict[str, int] = {}
    for r in ok:
        levels[r["price_level"]] = levels.get(r["price_level"], 0) + 1
    comps = [r["completeness"] for r in ok if r.get("completeness") is not None]
    agg = {
        "n_total": len(rows),
        "n_ok": len(ok),
        "n_error": sum(r["status"] == "error" for r in rows),
        "identification_rate": round(sum(r["identified_ok"] for r in ok) / n, 3),
        "mean_token_recall": round(sum(r["token_recall"] for r in ok) / n, 3),
        "mean_completeness": round(statistics.mean(comps), 3) if comps else None,
        "median_completeness": round(statistics.median(comps), 3) if comps else None,
        "reasoned_rate": round(sum(r["reasoned"] for r in ok) / n, 3),
        "catalog_miss_rate": round(sum(r["catalog_miss"] for r in ok) / n, 3),
        "ask_question_rate": round(sum(r["ask_question"] for r in ok) / n, 3),
        "price_levels": levels,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mesure_fiche.json").write_text(
        json.dumps({"aggregate": agg, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md = [
        "# Mesure de qualité de fiche (panel réel)",
        "",
        f"- Produits : **{agg['n_ok']}/{agg['n_total']}** mesurés ({agg['n_error']} erreurs)",
        f"- **Identification** (≥50 % tokens clés) : **{agg['identification_rate']:.0%}** "
        f"(rappel moyen {agg['mean_token_recall']:.0%})",
        f"- **Complétude fiche** : moyenne {agg['mean_completeness']} · médiane {agg['median_completeness']}",
        f"- Passe raisonnée : {agg['reasoned_rate']:.0%} · catalog-miss : {agg['catalog_miss_rate']:.0%} "
        f"· question posée : {agg['ask_question_rate']:.0%}",
        f"- Niveaux de prix : {agg['price_levels']}",
        "",
        "| Produit | recall | identifié | complétude | prix | niveau |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] != "ok":
            md.append(f"| {r['folder']} | - | {r['status']} | - | - | - |")
            continue
        md.append(
            f"| {r['folder']} | {r['token_recall']:.0%} | {'✅' if r['identified_ok'] else '❌'} "
            f"| {r['completeness']} | {r['price_eur']} € | {r['price_level']} |"
        )
    (OUT_DIR / "mesure_fiche.md").write_text("\n".join(md), encoding="utf-8")
    print("\n=== AGRÉGAT ===")
    for k, v in agg.items():
        print(f"  {k}: {v}")
    print(f"\n-> {OUT_DIR / 'mesure_fiche.md'}")


if __name__ == "__main__":
    main()

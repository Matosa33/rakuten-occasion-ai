"""Sous-todo 1.3 — Vérification anti-leakage 5 patterns canoniques.

À ce stade, le split est :
- 70/15/15 stratifié par `_source_category` (anti-B1 déséquilibre)
- Group=parent_asin (anti-L1 variantes du même produit)

On vérifie ici les 5 patterns canoniques de data leakage (cf. R3 + audit
findings L1/L2/L3 du rapport 01_audit/audit_v1_amazon_reviews_2023.md).

Patterns vérifiés
-----------------
P1 — Doublons parent_asin train/test
    Doit être 0 (groupé par parent_asin au split). Si > 0 → bug split.

P2 — Métadonnées qui contiennent le label
    Vérifier que les champs textuels (title, description) ne contiennent
    pas systématiquement le nom de la catégorie (`_source_category`).
    Mesure : pour chaque cat, % de title/description contenant le mot
    de la cat. Si > 80 %, alerte.

P3 — Fuite temporelle
    Pour un split product-level, ce n'est pas critique (les produits
    n'ont pas de "date de création" stricte). On vérifie que les
    distributions temporelles (year_first_review, year_last_review)
    sont similaires entre splits — KL divergence ou écart de médianes.

P4 — Fuite de groupe user_id (sur reviews_index)
    Au product-level, c'est sans objet. Au reviews_index, on mesure
    l'overlap users train ∩ test. **C'est attendu d'avoir overlap** car
    le split est anti-L1, pas anti-L2. À documenter explicitement
    comme limitation : pour les modèles qui apprennent les préférences
    user, refaire un split GroupKFold(user_id) en C07.

P5 — Fuite feature engineering
    Vérifier que toutes les features dérivées (log_price, n_reviews_log,
    price_band, etc.) sont **stateless** : leur calcul ne dépend pas
    du dataset (juste de la valeur de la ligne). On grep le code source
    de `src/data/clean/05_feature_engineering.py` pour détecter tout
    `mean()`, `std()`, `quantile()`, `min()`, `max()` global qui
    introduirait du leakage en dérivant la feature de l'ensemble du
    dataset au lieu du seul train.

Sortie : `reports/02_cleaning/anti_leakage_check.md` + JSON métriques.

Lance ce script depuis la racine du repo :

    python -m src.data.validate.01_anti_leakage_check
"""

from __future__ import annotations

import json
import logging

import polars as pl

from src.config import (
    CATEGORIES,
    DATA_PROCESSED_PRODUCTS,
    DATA_PROCESSED_REVIEWS_INDEX,
    REPO_ROOT,
    REPORTS_CLEANING,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUT_JSON = REPORTS_CLEANING / "anti_leakage_metrics.json"
SOURCE_FE = REPO_ROOT / "src" / "data" / "clean" / "05_feature_engineering.py"


def check_p1_parent_asin_overlap() -> dict:
    """P1 — Doublons parent_asin train/test (cible : 0)."""
    log.info("P1 — Doublons parent_asin train/test…")
    train_pa = (
        pl.scan_parquet(DATA_PROCESSED_PRODUCTS / "train.parquet")
        .select("parent_asin")
        .collect(engine="streaming")
    )
    test_pa = (
        pl.scan_parquet(DATA_PROCESSED_PRODUCTS / "test.parquet")
        .select("parent_asin")
        .collect(engine="streaming")
    )
    val_pa = (
        pl.scan_parquet(DATA_PROCESSED_PRODUCTS / "val.parquet")
        .select("parent_asin")
        .collect(engine="streaming")
    )

    train_set = set(train_pa["parent_asin"].to_list())
    test_set = set(test_pa["parent_asin"].to_list())
    val_set = set(val_pa["parent_asin"].to_list())

    overlap_train_test = len(train_set & test_set)
    overlap_train_val = len(train_set & val_set)
    overlap_val_test = len(val_set & test_set)

    return {
        "label": "P1 — Doublons parent_asin train/test",
        "severity": "critical" if overlap_train_test > 0 else "ok",
        "overlap_train_test": overlap_train_test,
        "overlap_train_val": overlap_train_val,
        "overlap_val_test": overlap_val_test,
        "n_train_unique": len(train_set),
        "n_val_unique": len(val_set),
        "n_test_unique": len(test_set),
    }


def check_p2_metadata_contains_label() -> dict:
    """P2 — Le titre/description contient-il systématiquement le nom de la catégorie ?

    Mesure par cat : % de titles contenant n'importe lequel des mots-clés
    significatifs de la cat (ex: "book" pour Books, "phone" pour
    Cell_Phones, etc.). Si > 80 %, alerte (le classifier triche).
    """
    log.info("P2 — Metadata contient le label…")

    # Mots-clés discriminants par cat (case-insensitive search)
    CAT_KEYWORDS = {
        "Books": ["book"],
        "Electronics": ["electronic", "device"],
        "Cell_Phones_and_Accessories": ["phone", "smartphone", "mobile"],
        "Toys_and_Games": ["toy", "game", "puzzle"],
        "Clothing_Shoes_and_Jewelry": ["shirt", "shoe", "dress", "jewelry"],
        "Home_and_Kitchen": ["kitchen", "home"],
        "Tools_and_Home_Improvement": ["tool", "drill"],
        "Automotive": ["car", "auto", "vehicle"],
        "Sports_and_Outdoors": ["sport", "outdoor"],
        "Movies_and_TV": ["movie", "film", "dvd", "blu-ray"],
        "CDs_and_Vinyl": ["cd ", "vinyl", "album"],
        "Baby_Products": ["baby", "infant"],
        "Video_Games": ["game", "console"],
        "Musical_Instruments": ["guitar", "piano", "instrument"],
        "Appliances": ["refrigerator", "washer", "dryer", "appliance"],
    }

    train_lf = pl.scan_parquet(DATA_PROCESSED_PRODUCTS / "train.parquet")
    by_cat = {}
    for cat in CATEGORIES:
        kws = CAT_KEYWORDS.get(cat, [])
        if not kws:
            continue
        # Pattern regex case-insensitive : "(?i)keyword1|keyword2"
        pattern = "(?i)" + "|".join(kws)
        stats = (
            train_lf.filter(pl.col("_source_category") == cat)
            .select(
                pl.len().alias("n_total"),
                pl.col("title")
                .str.contains(pattern)
                .fill_null(False)
                .sum()
                .alias("n_title_has_kw"),
                pl.col("description")
                .str.contains(pattern)
                .fill_null(False)
                .sum()
                .alias("n_desc_has_kw"),
            )
            .collect(engine="streaming")
            .to_dicts()[0]
        )
        n_total = int(stats["n_total"])
        if n_total == 0:
            continue
        pct_title = round(100 * stats["n_title_has_kw"] / n_total, 1)
        pct_desc = round(100 * stats["n_desc_has_kw"] / n_total, 1)
        by_cat[cat] = {
            "n_total": n_total,
            "pct_title_contains_kw": pct_title,
            "pct_description_contains_kw": pct_desc,
            "alert_title": pct_title > 80,
            "alert_description": pct_desc > 80,
        }
        log.info("  %-30s title %.1f %% / desc %.1f %% (kws: %s)", cat, pct_title, pct_desc, kws)

    n_alerts = sum(1 for v in by_cat.values() if v["alert_title"] or v["alert_description"])
    return {
        "label": "P2 — Metadata contient le label",
        "severity": "high" if n_alerts > 5 else ("medium" if n_alerts > 0 else "ok"),
        "n_alerts": n_alerts,
        "by_cat": by_cat,
        "note": (
            "Un % élevé n'est pas forcément un leakage si l'utilisation prévue est "
            "production réelle (le vendeur écrit librement). Mais en train, ça permet "
            "au classifier de tricher en cherchant juste le mot-clé."
        ),
    }


def check_p3_temporal_distribution() -> dict:
    """P3 — Distributions temporelles similaires entre splits ?"""
    log.info("P3 — Distribution temporelle train vs val vs test…")
    stats_per_split = {}
    for split_name in ("train", "val", "test"):
        df = (
            pl.scan_parquet(DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet")
            .filter(pl.col("year_last_review").is_not_null())
            .select(
                pl.col("year_last_review").min().alias("min_year"),
                pl.col("year_last_review").max().alias("max_year"),
                pl.col("year_last_review").median().alias("median_year"),
                pl.col("year_last_review").mean().alias("mean_year"),
            )
            .collect(engine="streaming")
            .to_dicts()[0]
        )
        stats_per_split[split_name] = {
            "min_year": int(df["min_year"]) if df["min_year"] is not None else None,
            "max_year": int(df["max_year"]) if df["max_year"] is not None else None,
            "median_year": float(df["median_year"]) if df["median_year"] is not None else None,
            "mean_year": round(float(df["mean_year"]), 2) if df["mean_year"] is not None else None,
        }

    # Calcul de l'écart max entre médianes
    medians = [s["median_year"] for s in stats_per_split.values() if s["median_year"] is not None]
    median_spread = max(medians) - min(medians) if medians else 0

    return {
        "label": "P3 — Fuite temporelle (médianes year_last_review entre splits)",
        "severity": "ok" if median_spread < 1 else ("medium" if median_spread < 3 else "high"),
        "stats_per_split": stats_per_split,
        "median_spread_years": median_spread,
        "note": (
            "Au split product-level, fuite temporelle = écart de médiane > 1 an "
            "entre splits (signe que train ≠ test temporellement). Acceptable < 1 an."
        ),
    }


def check_p4_user_overlap_reviews_index() -> dict:
    """P4 — Overlap user_id train/test dans reviews_index.

    LIMITATION ATTENDUE et documentée : le split est product-level
    (anti-L1), pas user-level. Pour les modèles préférence user (futurs
    cycles), refaire GroupKFold(user_id) explicit.
    """
    log.info("P4 — Overlap user_id train/test sur reviews_index…")
    train_users = (
        pl.scan_parquet(DATA_PROCESSED_REVIEWS_INDEX / "train.parquet")
        .select(pl.col("user_id").unique())
        .collect(engine="streaming")
    )
    test_users = (
        pl.scan_parquet(DATA_PROCESSED_REVIEWS_INDEX / "test.parquet")
        .select(pl.col("user_id").unique())
        .collect(engine="streaming")
    )

    train_set = set(train_users["user_id"].to_list())
    test_set = set(test_users["user_id"].to_list())

    overlap = len(train_set & test_set)
    n_train_users = len(train_set)
    n_test_users = len(test_set)
    pct_test_users_in_train = round(100 * overlap / n_test_users, 1) if n_test_users else 0

    return {
        "label": "P4 — Overlap user_id train/test (reviews_index)",
        "severity": "expected" if pct_test_users_in_train > 0 else "n/a",
        "n_train_users_unique": n_train_users,
        "n_test_users_unique": n_test_users,
        "n_overlap_users": overlap,
        "pct_test_users_in_train": pct_test_users_in_train,
        "note": (
            "ATTENDU. Le split est product-level (anti-L1 variantes), pas user-level. "
            "Conséquence : un user qui a noté plusieurs produits peut apparaître dans "
            "train ET test (avec des produits différents). Pour des modèles préférence "
            "user (futurs Cycles 4-7), refaire un split GroupKFold(user_id) dédié, "
            "ou utiliser un masking par user au train."
        ),
    }


def check_p5_feature_engineering_stateless() -> dict:
    """P5 — Feature engineering stateless (pas d'agrégat global)."""
    log.info("P5 — Feature engineering stateless (grep dans script 05)…")
    source = SOURCE_FE.read_text(encoding="utf-8")

    # Patterns à chercher (statefuls forbidden)
    statefuls_forbidden = [
        ".mean()",
        ".std()",
        ".quantile(",
        ".min()",
        ".max()",
        ".median()",
    ]
    found = []
    for pat in statefuls_forbidden:
        if pat in source:
            found.append(pat)

    return {
        "label": "P5 — Feature engineering stateless (pas d'agrégat global)",
        "severity": "high" if found else "ok",
        "statefuls_found_in_source": found,
        "source_file": str(SOURCE_FE.relative_to(REPO_ROOT)),
        "note": (
            "Si statefuls trouvés, vérifier qu'ils sont calculés sur le **train uniquement** "
            "et passés explicitement (R3 anti-leakage). Aucun calcul global ne doit dériver "
            "une feature qui sera ensuite appliquée à val/test."
        ),
    }


def main() -> None:
    log.info("=== Sous-todo 1.3 — Vérification anti-leakage 5 patterns ===")

    REPORTS_CLEANING.mkdir(parents=True, exist_ok=True)

    findings = {
        "P1": check_p1_parent_asin_overlap(),
        "P2": check_p2_metadata_contains_label(),
        "P3": check_p3_temporal_distribution(),
        "P4": check_p4_user_overlap_reviews_index(),
        "P5": check_p5_feature_engineering_stateless(),
    }

    OUT_JSON.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Métriques → %s", OUT_JSON)

    log.info("\n=== Synthèse anti-leakage ===")
    for pid, f in findings.items():
        log.info("  [%s] %s — %s", f.get("severity", "?"), pid, f.get("label"))

    log.info("\nSous-todo 1.3 OK.")


if __name__ == "__main__":
    main()

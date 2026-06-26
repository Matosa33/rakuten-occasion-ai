"""Cycle 7.1 — Pricing algorithmique transparent (pricing-cascade).

Système déterministe (aucun ML opaque) qui retourne un **prix indicatif**
+ **niveau de confiance** + **explication lisible**. Préféré à un modèle
ML opaque (R19 grounded-avant-génératif) car le vendeur particulier doit
comprendre POURQUOI le prix lui est suggéré.

5 niveaux de confiance (cascade)
--------------------------------
- **L1 (haute)** : prix présent dans la fiche meta du produit identifié
  → prix catalogue × pénalité état × dépréciation âge
- **L1.5 (haute-moyenne)** : prix NEUF de référence estimé par IA (passe d'identification
  raisonnée, Cycle 36) → ancre IA × pénalité état × dépréciation. La décote reste 100 %
  déterministe ; seule l'ANCRE est une estimation IA. Placée AVANT L2 car les médianes de
  voisins sont polluées par accessoires/coques/bundles (elles donnaient 6 € pour une montre à 150 €).
- **L2 (moyenne)** : prix médian des KNN top-10 voisins valides (avec garde-fou anti sous-éval)
  → médiane KNN prix × pénalité état × dépréciation âge
- **L3 (basse)** : seule la catégorie est connue (avec garde-fou anti sous-éval)
  → médiane prix par catégorie × pénalité état
- **L4 (très basse)** : produit inconnu / catégorie inconnue
  → retourne une fourchette large + mode dégradé "saisie manuelle"

Pénalités état (multiplicateur sur prix neuf)
---------------------------------------------
- neuf : 1.00
- très bon état : 0.75
- bon état : 0.55
- correct (avec défauts) : 0.35

Dépréciation linéaire par catégorie (config YAML)
-------------------------------------------------
- Electronics : -15 %/an (vieillit vite)
- Cell_Phones_and_Accessories : -20 %/an (très volatile)
- Video_Games : -10 %/an (collection rallume valeur)
- Tools_and_Home_Improvement : -5 %/an (vieillit lentement)

Sortie :
- `data/models/pricing-cascade_v1.joblib` (config sérialisée + KNN référence)
- `reports/08_pricing/pricing_v1.{md,json}` (MAPE par niveau, couverture)

Lance APRÈS Cycle 4.1 (FAISS index pour KNN voisins) :

    python -m src.pricing.01_algorithmique
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

import joblib
import numpy as np
import polars as pl

from src.config import (
    DATA_EMBEDDINGS,
    DATA_INDEX,
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_PRICING,
    SEED,
)

# NB: `log_training_run` (D-021) est importé LAZILY dans `main()`. Ce module est
# aussi chargé par `src/api/pipeline.py` (importlib) pour réutiliser `suggest_price` ;
# l'import au top tirait mlflow + ses 100 Mo dans l'image API (cf. smoke C13.1).

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "pricing-cascade_v1"

# Seuil prix valide : exclut les "0.0" parasites des metas Amazon
MIN_VALID_PRICE_USD = 0.01

KNN_K = 10
EVAL_N_QUERIES = 1000

# Conversion USD→EUR (17.4b, D-036) : les prix catalogue sont en USD (Amazon),
# l'UI affiche des EUR. Taux FIXE documenté (moyenne 2024-2026 ~0.92), override
# par env `PRICE_USD_EUR_RATE` pour ajustement sans redéploiement. Un taux live
# (API de change) serait de la sur-ingénierie pour un prix INDICATIF arrondi.
USD_TO_EUR = float(os.environ.get("PRICE_USD_EUR_RATE", "0.92"))

# Pénalités état (multiplicatives sur prix neuf)
CONDITION_MULTIPLIER = {
    "neuf": 1.00,
    "tres_bon_etat": 0.75,
    "bon_etat": 0.55,
    "correct": 0.35,
    "pour_pieces": 0.15,  # HS / pour pièces : valeur résiduelle (Cycle 36)
}

# Libellés humains (17.4b) : les codes snake_case ne doivent JAMAIS fuiter
# dans un texte montré au vendeur.
CONDITION_LABELS_FR = {
    "neuf": "Neuf",
    "tres_bon_etat": "Très bon état",
    "bon_etat": "Bon état",
    "correct": "État correct",
    "pour_pieces": "Pour pièces / HS",
}

# Dépréciation linéaire par catégorie (taux annuel)
CATEGORY_DEPRECIATION_RATE = {
    "Electronics": 0.15,
    "Cell_Phones_and_Accessories": 0.20,
    "Video_Games": 0.10,
    "Tools_and_Home_Improvement": 0.05,
}

OUT_MODEL = DATA_MODELS / f"{MODEL_NAME}.joblib"
OUT_JSON = REPORTS_PRICING / "pricing_v1.json"


@dataclass
class PricingResult:
    """Résultat d'une suggestion de prix."""

    suggested_price_eur: float
    confidence_level: str  # L1 | L1.5 | L2 | L3 | L4
    confidence_score: float  # 0..1
    range_low: float
    range_high: float
    explanation: str
    method: str  # "catalog_meta" | "llm_anchor" | "knn_median" | "category_median" | "fallback"


def _depreciate(price: float, age_years: float, category: str) -> float:
    """Applique la dépréciation linéaire selon la catégorie."""
    rate = CATEGORY_DEPRECIATION_RATE.get(category, 0.10)
    multiplier = max(0.10, 1.0 - rate * max(0.0, age_years))
    return price * multiplier


def _apply_condition(price: float, condition: str) -> float:
    return price * CONDITION_MULTIPLIER.get(condition, 0.55)  # défaut bon_etat


# Garde-fou anti sous-évaluation (Cycle 36). Une médiane de voisins (L2/L3) polluée par des
# accessoires/coques/bundles peut s'effondrer (ex. 6 € pour une montre à 150 €). Si la suggestion
# tombe sous ce ratio du prix neuf de référence décoté au MÊME état/âge, on la relève à ce plancher.
UNDERPRICING_FLOOR_RATIO = 0.25

# Garde-fou de cohérence L1 (Cycle 36). Si une ancre IA existe et que le prix catalogue du top-1 est
# très en-dessous (< ce ratio × ancre), le top-1 est probablement un ACCESSOIRE mal apparié (coque à
# 43 $ pour un iPhone à 598 $) → on ignore ce prix catalogue pollué et on bascule sur l'ancre L1.5.
L1_ANCHOR_MIN_RATIO = 0.5


def _floor_against_underpricing(
    suggested_eur: float,
    condition: str,
    age_years: float,
    category: str,
    expected_order_of_magnitude: float | None,
) -> tuple[float, bool]:
    """Relève une suggestion absurde sous un ratio du prix neuf attendu décoté.

    `expected_order_of_magnitude` = prix NEUF de référence (USD : ancre IA ou prix catalogue).
    Retourne (prix_éventuellement_relevé_eur, was_floored). Inactif si pas d'ordre de grandeur
    (rétro-compatibilité : aucun appel existant ne le fournit).
    """
    if expected_order_of_magnitude is None or expected_order_of_magnitude < MIN_VALID_PRICE_USD:
        return suggested_eur, False
    expected_decote_eur = (
        _apply_condition(_depreciate(expected_order_of_magnitude, age_years, category), condition)
        * USD_TO_EUR
    )
    floor = expected_decote_eur * UNDERPRICING_FLOOR_RATIO
    if suggested_eur < floor:
        return round(floor, 2), True
    return suggested_eur, False


def suggest_price(
    catalog_price: float | None,
    knn_neighbors_prices: list[float] | None,
    category_median_price: float | None,
    condition: str = "bon_etat",
    age_years: float = 0.0,
    category: str = "",
    llm_anchor_price: float | None = None,
    llm_anchor_confidence: float = 0.0,
    expected_order_of_magnitude: float | None = None,
) -> PricingResult:
    """Cascade L1→L4 (+ L1.5) pour suggérer un prix avec niveau de confiance.

    Entrées en USD (catalogue Amazon) ; sorties en EUR (17.4b, D-036 :
    conversion par taux fixe USD_TO_EUR appliquée APRÈS dépréciation+état).

    Cycle 36 (params optionnels, 100 % rétro-compatibles) :
    - `llm_anchor_price` : prix NEUF de référence estimé par IA (passe raisonnée) → niveau L1.5,
      placé AVANT les médianes de voisins (polluées). La décote reste déterministe.
    - `expected_order_of_magnitude` : prix neuf de référence (USD) pour le garde-fou anti
      sous-évaluation appliqué aux médianes L2/L3.
    """
    cond_label = CONDITION_LABELS_FR.get(condition, condition)

    # L1 : catalogue meta (prix RÉEL du produit identifié → prioritaire sur l'ancre IA).
    # Sauf si le prix catalogue est incohérent avec l'ancre IA (top-1 = accessoire mal apparié) :
    # on l'ignore alors au profit de L1.5 (évite « iPhone à 15 € » car top-1 = coque à 43 $).
    _anchor_valid = llm_anchor_price is not None and llm_anchor_price >= MIN_VALID_PRICE_USD
    _catalog_valid = catalog_price is not None and catalog_price >= MIN_VALID_PRICE_USD
    _catalog_polluted = (
        _anchor_valid
        and _catalog_valid
        and catalog_price < llm_anchor_price * L1_ANCHOR_MIN_RATIO  # type: ignore[operator]
    )
    if _catalog_valid and not _catalog_polluted:
        depreciated = _depreciate(catalog_price, age_years, category)  # type: ignore[arg-type]
        suggested = _apply_condition(depreciated, condition) * USD_TO_EUR
        return PricingResult(
            suggested_price_eur=round(suggested, 2),
            confidence_level="L1",
            confidence_score=0.90,
            range_low=round(suggested * 0.85, 2),
            range_high=round(suggested * 1.15, 2),
            explanation=(
                f"Basé sur le prix catalogue neuf de {catalog_price:.2f} $ "
                f"(≈ {catalog_price * USD_TO_EUR:.0f} €) : dépréciation "
                f"{CATEGORY_DEPRECIATION_RATE.get(category, 0.10) * 100:.0f} %/an "
                f"sur {age_years:.1f} an(s), ajustement « {cond_label} »."
            ),
            method="catalog_meta",
        )

    # L1.5 : ancre prix NEUF estimée par IA (Cycle 36). Décote déterministe ; placée AVANT L2
    # car les médianes de voisins sont polluées par accessoires/coques/bundles.
    if llm_anchor_price is not None and llm_anchor_price >= MIN_VALID_PRICE_USD:
        depreciated = _depreciate(llm_anchor_price, age_years, category)
        suggested = _apply_condition(depreciated, condition) * USD_TO_EUR
        conf = max(0.55, min(0.85, 0.60 + 0.25 * float(llm_anchor_confidence)))
        return PricingResult(
            suggested_price_eur=round(suggested, 2),
            confidence_level="L1.5",
            confidence_score=round(conf, 2),
            range_low=round(suggested * 0.80, 2),
            range_high=round(suggested * 1.20, 2),
            explanation=(
                f"Prix neuf estimé par IA : {llm_anchor_price:.0f} $ "
                f"(≈ {llm_anchor_price * USD_TO_EUR:.0f} €), dépréciation "
                f"{CATEGORY_DEPRECIATION_RATE.get(category, 0.10) * 100:.0f} %/an "
                f"sur {age_years:.1f} an(s), ajustement « {cond_label} »."
            ),
            method="llm_anchor",
        )

    # L2 : KNN voisins valides (avec garde-fou anti sous-évaluation)
    if knn_neighbors_prices:
        valid_prices = [p for p in knn_neighbors_prices if p >= MIN_VALID_PRICE_USD]
        if len(valid_prices) >= 3:
            knn_median = float(np.median(valid_prices))
            depreciated = _depreciate(knn_median, age_years, category)
            suggested = _apply_condition(depreciated, condition) * USD_TO_EUR
            suggested, floored = _floor_against_underpricing(
                suggested, condition, age_years, category, expected_order_of_magnitude
            )
            spread = float(np.std(valid_prices)) / max(knn_median, 1.0)
            confidence_score = max(0.50, min(0.80, 0.80 - spread))
            explanation = (
                f"Basé sur le prix médian de {len(valid_prices)} produits similaires "
                f"({knn_median:.2f} $ ≈ {knn_median * USD_TO_EUR:.0f} €), "
                f"dépréciation par âge et ajustement « {cond_label} »."
            )
            if floored:
                explanation += (
                    " (Prix relevé : la médiane des voisins était incohérente avec le prix "
                    "neuf attendu — voisins probablement pollués par des accessoires.)"
                )
            return PricingResult(
                suggested_price_eur=round(suggested, 2),
                confidence_level="L2",
                confidence_score=round(confidence_score, 2),
                range_low=round(suggested * 0.70, 2),
                range_high=round(suggested * 1.30, 2),
                explanation=explanation,
                method="knn_median",
            )

    # L3 : catégorie seule (avec garde-fou anti sous-évaluation)
    if category_median_price is not None and category_median_price >= MIN_VALID_PRICE_USD:
        suggested = _apply_condition(category_median_price, condition) * USD_TO_EUR
        suggested, floored = _floor_against_underpricing(
            suggested, condition, age_years, category, expected_order_of_magnitude
        )
        explanation = (
            f"Estimation large : prix médian de la catégorie "
            f"({category_median_price * USD_TO_EUR:.0f} €), ajustement « {cond_label} ». "
            f"Produit non identifié précisément."
        )
        if floored:
            explanation += " (Prix relevé : incohérent avec le prix neuf attendu.)"
        return PricingResult(
            suggested_price_eur=round(suggested, 2),
            confidence_level="L3",
            confidence_score=0.30,
            range_low=round(suggested * 0.50, 2),
            range_high=round(suggested * 1.50, 2),
            explanation=explanation,
            method="category_median",
        )

    # L4 : fallback
    return PricingResult(
        suggested_price_eur=0.0,
        confidence_level="L4",
        confidence_score=0.0,
        range_low=0.0,
        range_high=0.0,
        explanation=(
            "Produit non identifié et catégorie inconnue. Saisie manuelle requise par le vendeur."
        ),
        method="fallback",
    )


def main() -> None:
    # Import lazy : mlflow n'est nécessaire qu'au train standalone (cf. note module).
    from src.mlops.mlflow_utils import log_training_run

    log.info("=== Cycle 7.1 — Pricing algorithmique transparent (pricing-cascade) ===")
    REPORTS_PRICING.mkdir(parents=True, exist_ok=True)
    DATA_MODELS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip", OUT_MODEL.name)
        return

    log.info("Lecture train + val + index FAISS pour KNN voisins…")
    train = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet",
        columns=["parent_asin", "_source_category", "price_num"],
    )
    val = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "val.parquet",
        columns=["parent_asin", "_source_category", "price_num"],
    )

    # Médianes catégorie (train) — calibration L3
    category_medians = (
        train.filter(pl.col("price_num") >= MIN_VALID_PRICE_USD)
        .group_by("_source_category")
        .agg(pl.col("price_num").median().alias("median_price"))
    )
    cat_median_dict = {
        row["_source_category"]: float(row["median_price"])
        for row in category_medians.iter_rows(named=True)
    }
    log.info("Médianes catégorie (USD) : %s", cat_median_dict)

    # Évaluation : on simule un "produit du val" comme query, on cherche KNN dans train,
    # on suggère prix L2, on compare au prix vrai du val
    text_index_path = DATA_INDEX / "text_arctic_hnsw.index"
    has_index = text_index_path.exists()
    val_emb_path = DATA_EMBEDDINGS / "text" / "text_arctic_val.npy"
    has_val_emb = val_emb_path.exists()

    eval_results = {"L1": [], "L2": [], "L3": [], "L4": []}
    train_prices = train["price_num"].to_numpy()

    if has_index and has_val_emb:
        import faiss

        log.info("Index FAISS + embeddings val OK → eval L2 sur %d queries", EVAL_N_QUERIES)
        index = faiss.read_index(str(text_index_path))
        val_emb = np.load(val_emb_path).astype(np.float32)
        rng = np.random.default_rng(SEED)
        n_queries = min(EVAL_N_QUERIES, val_emb.shape[0])
        query_idx = rng.choice(val_emb.shape[0], size=n_queries, replace=False)
        queries = val_emb[query_idx]

        _, knn_indices = index.search(queries, KNN_K)

        for i, q_idx in enumerate(query_idx):
            true_row = val.row(int(q_idx), named=True)
            true_price = true_row["price_num"]
            if true_price is None or float(true_price) < MIN_VALID_PRICE_USD:
                continue
            true_price = float(true_price)
            category = true_row["_source_category"]
            knn_prices = [
                float(train_prices[j]) for j in knn_indices[i] if not np.isnan(train_prices[j])
            ]
            result = suggest_price(
                catalog_price=None,  # Pas de catalogue meta direct ici (simulation)
                knn_neighbors_prices=knn_prices,
                category_median_price=cat_median_dict.get(category),
                condition="bon_etat",
                age_years=2.0,  # défaut simulé
                category=category,
            )
            ape = abs(result.suggested_price_eur - true_price) / true_price * 100
            eval_results[result.confidence_level].append(ape)
    else:
        log.warning("Index ou val_emb absent → eval L2 skippée. Run Cycle 2.3 + 4.1 puis relancer.")

    # Synthèse MAPE par niveau
    metrics = {}
    for level, apes in eval_results.items():
        if apes:
            metrics[level] = {
                "n": len(apes),
                "mape_mean": round(float(np.mean(apes)), 2),
                "mape_median": round(float(np.median(apes)), 2),
                "mape_p90": round(float(np.percentile(apes, 90)), 2),
            }
        else:
            metrics[level] = {"n": 0}

    log.info("Métriques pricing par niveau :")
    for level, m in metrics.items():
        log.info("  %s : %s", level, m)

    artifact = {
        "model_type": "Algorithmique transparent (cascade L1-L4)",
        "category_medians_usd": cat_median_dict,
        "condition_multipliers": CONDITION_MULTIPLIER,
        "category_depreciation_rate": CATEGORY_DEPRECIATION_RATE,
        "min_valid_price_usd": MIN_VALID_PRICE_USD,
        "knn_k": KNN_K,
        "seed": SEED,
    }
    joblib.dump(artifact, OUT_MODEL)

    full = {
        "model": MODEL_NAME,
        "type": "Pricing algorithmique cascade L1-L4",
        "config": artifact,
        "eval_metrics": metrics,
        "sample_suggestion": asdict(
            suggest_price(
                catalog_price=799.99,
                knn_neighbors_prices=[750.0, 780.0, 820.0, 790.0],
                category_median_price=500.0,
                condition="bon_etat",
                age_years=3.0,
                category="Electronics",
            )
        ),
    }
    OUT_JSON.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s + %s", OUT_MODEL.name, OUT_JSON.name)

    # MLflow LIVE (R5) : run pricing (MAPE par niveau aplati en test_*). Modèle =
    # cascade algorithmique déterministe (config dict) → sklearn=False, non registré.
    flat_pricing = {
        f"{level}_{k}": v
        for level, m in metrics.items()
        for k, v in m.items()
        if k.startswith("mape") and isinstance(v, int | float)
    }
    log_training_run(
        MODEL_NAME,
        model=None,
        hyperparams={
            "knn_k": KNN_K,
            "eval_n_queries": EVAL_N_QUERIES,
            "min_valid_price_usd": MIN_VALID_PRICE_USD,
            "seed": SEED,
        },
        results={"test": flat_pricing},
        sklearn=False,
        cycle="7",
    )

    log.info("Cycle 7.1 pricing algorithmique OK.")


if __name__ == "__main__":
    main()

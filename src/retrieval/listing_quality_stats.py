"""Stats appariées du bench qualité de fiche (Cycle 34.6, protocole D-042).

Design **within-product** → tests APPARIÉS (chaque produit passe toutes les conditions). On fournit :
- **Page's L** (monotonie ORDONNÉE des conditions de richesse) — `scipy.stats.page_trend_test`.
- **Wilcoxon apparié** (comparaison de 2 conditions) + différence médiane.
- **TOST** (équivalence, pour le NON-effet prédit multi-photo≈multi-photo-meta) avec SESOI métier.
- **Bootstrap CLUSTERISÉ par famille de produit** (gère les doublons iPhone14×2, PS4×… → N_eff).

Fonctions pures (matrices appariées en entrée) → testables sans I/O. Le run complet (34.7) les
applique sur les métriques dures (34.5).
"""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
from scipy import stats

# Axe de RICHESSE (croissant) pour la monotonie. text-fr-en/multi-photo-meta-fr-en = facteur LANGUE, comparés à part.
RICHNESS_ORDER = ["text-only", "one-photo", "multi-photo", "multi-photo-meta"]


def product_family(product: str) -> str:
    """Famille = slug sans l'index de tête → les doublons (11_/12_ iphone_14) partagent la famille."""
    return re.sub(r"^\d+_", "", product)


def paired_values(
    per_product: dict[str, dict[str, float]], conditions: list[str]
) -> tuple[list[str], dict[str, list[float]]]:
    """Aligne les valeurs par produit présent dans TOUTES les conditions demandées."""
    prods = [p for p, d in per_product.items() if all(c in d for c in conditions)]
    return prods, {c: [per_product[p][c] for p in prods] for c in conditions}


def page_trend(matrix: dict[str, list[float]], order: list[str]) -> dict:
    """Test de tendance de Page (monotonie croissante le long de `order`). Continu recommandé."""
    arr = np.array([matrix[c] for c in order]).T  # (sujets, conditions ordonnées croissant)
    res = stats.page_trend_test(arr)
    return {"L": round(float(res.statistic), 3), "p": float(res.pvalue), "order": order}


def wilcoxon_pair(a: list[float], b: list[float]) -> dict:
    """Wilcoxon apparié a vs b (+ différence médiane). p=1 si identiques."""
    a_, b_ = np.asarray(a, float), np.asarray(b, float)
    if np.allclose(a_, b_):
        return {"p": 1.0, "median_diff": 0.0}
    res = stats.wilcoxon(a_, b_)
    return {"p": float(res.pvalue), "median_diff": round(float(np.median(a_ - b_)), 4)}


def tost_equivalence(a: list[float], b: list[float], sesoi: float) -> dict:
    """TOST apparié : a et b équivalents si |moyenne(a-b)| significativement < SESOI."""
    d = np.asarray(a, float) - np.asarray(b, float)
    if np.allclose(d, 0):
        return {"p_tost": 0.0, "equivalent": True, "sesoi": sesoi}
    p_low = stats.ttest_1samp(d, -sesoi, alternative="greater").pvalue
    p_high = stats.ttest_1samp(d, sesoi, alternative="less").pvalue
    p = float(max(p_low, p_high))
    return {"p_tost": p, "equivalent": p < 0.05, "sesoi": sesoi}


def clustered_bootstrap_ci(
    values: list[float], families: list[str], n_boot: int = 10000, seed: int = 42
) -> dict:
    """IC 95 % de la moyenne par rééchantillonnage des FAMILLES (clusters) → N effectif honnête."""
    rng = np.random.default_rng(seed)
    fam_vals: dict[str, list[float]] = defaultdict(list)
    for v, f in zip(values, families, strict=False):
        fam_vals[f].append(v)
    fams = list(fam_vals)
    boot = np.empty(n_boot)
    for i in range(n_boot):
        picked = rng.choice(fams, size=len(fams), replace=True)
        vals = [v for f in picked for v in fam_vals[f]]
        boot[i] = np.mean(vals)
    return {
        "mean": round(float(np.mean(values)), 4),
        "ci_low": round(float(np.percentile(boot, 2.5)), 4),
        "ci_high": round(float(np.percentile(boot, 97.5)), 4),
        "n_families": len(fams),
        "n_obs": len(values),
    }

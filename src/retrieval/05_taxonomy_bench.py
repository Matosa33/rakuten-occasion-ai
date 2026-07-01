"""Benchmark end-to-end : prédiction de taxonomie par retrieval (bras top1-copy → coarse-to-fine).

Question : avec notre stack (embeddings Arctic + index FAISS), quelle architecture
prédit le mieux la catégorie **la plus fine possible** d'un produit ? On compare
plusieurs montages sur le MÊME protocole (anti-fuite, échantillon stratifié du test),
on mesure des scores honnêtes (pas de vanity metric), on trace chaque bras dans MLflow,
et on désigne le meilleur (champion/challenger sur l'accuracy leaf).

Pourquoi par retrieval et pas un classifieur 2 956 classes : l'index EST déjà un
classifieur fin - un vote k-NN pondéré sur la taxonomie (`category_path`) des voisins
donne la feuille la plus probable, à chaque niveau, sans entraîner de modèle géant.

Les bras
--------
- **top1-copy actuel**       : on prend la taxo du **top-1** voisin (ce que fait l'app aujourd'hui).
- **macro-gated gate macro**   : vote macro (4 cl.) → on **post-filtre** les voisins de cette macro,
                        puis top-1 leaf des voisins restants.
- **knn-vote vote k-NN fin**: **vote pondéré** par similarité sur la leaf des top-k voisins
                        (le gain quasi-gratuit), sans gate.
- **coarse-to-fine coarse-to-fine**: gate macro **+** vote pondéré sur les voisins de la macro prédite
                        (recherche élargie puis filtrée - approxime des sous-index par macro).

Métriques (par niveau de taxo `category_path` = breadcrumb « A > B > C »)
- accuracy macro (`_source_category`, 4 cl.), L1/L2/leaf (breadcrumb),
- **F1 pondéré leaf** (équilibre précision/rappel sans bruit des classes à 1 exemple),
- **F1 hiérarchique** (crédit partiel le long du chemin) - la courbe de progression,
- **recall@k leaf** (la bonne feuille est-elle parmi les voisins votants).

Lancer :

    python -m src.retrieval.05_taxonomy_bench
    BENCH_SAMPLE_N=2000 python -m src.retrieval.05_taxonomy_bench   # run rapide de validation
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict

import numpy as np
import polars as pl
from sklearn.metrics import f1_score

from src.config import DATA_INDEX, DATA_PROCESSED_PRODUCTS, REPO_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EMBEDDINGS_DIR = REPO_ROOT / "data" / "embeddings" / "text"
INDEX_PATH = DATA_INDEX / "text_arctic_hnsw.index"
LOOKUP_PATH = DATA_PROCESSED_PRODUCTS / "product_lookup.parquet"
REPORT_DIR = REPO_ROOT / "reports" / "05_retrieval"

SAMPLE_N = int(os.environ.get("BENCH_SAMPLE_N", "15000"))
TOP_K = int(os.environ.get("BENCH_TOP_K", "200"))  # voisins ramenés (vote + recall@k)
EF_SEARCH = int(os.environ.get("BENCH_EF_SEARCH", "128"))
SEED = 42
EXPERIMENT = "rakuten-taxonomy-bench"
PATH_SEP = " > "


# ───────────────────────────── chargement données ──────────────────────────────
def _split_path(path: str | None) -> list[str]:
    """Breadcrumb « A > B > C » → ['A','B','C'] (vide si absent)."""
    if not path or not isinstance(path, str):
        return []
    return [p.strip() for p in path.split(PATH_SEP) if p.strip()]


def _load_taxonomy_lookup() -> dict[str, tuple[str, list[str]]]:
    """parent_asin → (leaf, path_levels) depuis le lookup produit."""
    lk = pl.read_parquet(LOOKUP_PATH, columns=["parent_asin", "category_leaf", "category_path"])
    out: dict[str, tuple[str, list[str]]] = {}
    for asin, leaf, path in zip(
        lk["parent_asin"].to_list(),
        lk["category_leaf"].to_list(),
        lk["category_path"].to_list(),
        strict=False,
    ):
        if leaf:
            out[str(asin)] = (str(leaf), _split_path(path))
    return out


def _load_split_arrays(split: str, taxo: dict[str, tuple[str, list[str]]]):
    """Charge (asin, macro, leaf, path) d'un split, ALIGNÉ sur l'ordre des embeddings."""
    meta = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / f"{split}.parquet", columns=["parent_asin", "_source_category"]
    )
    asins = meta["parent_asin"].to_list()
    macro = np.array([str(m) for m in meta["_source_category"].to_list()])
    leaf = np.empty(len(asins), dtype=object)
    path = np.empty(len(asins), dtype=object)
    for i, a in enumerate(asins):
        t = taxo.get(str(a))
        leaf[i] = t[0] if t else None
        path[i] = t[1] if t else []
    return np.array([str(a) for a in asins]), macro, leaf, path


# ───────────────────────────── prédicteurs (bras) ──────────────────────────────
def _weighted_vote(labels, scores) -> str | None:
    """Vote pondéré par similarité : label de poids cumulé max (None si rien)."""
    acc: dict[str, float] = defaultdict(float)
    for lab, sc in zip(labels, scores, strict=False):
        if lab is not None and lab != "":
            acc[lab] += float(sc)
    return max(acc, key=acc.get) if acc else None


def _path_of_leaf(leaf_pred, n_leaf, n_path, n_score):
    """Path du voisin de score max dont la leaf == leaf_pred (cohérence leaf↔path)."""
    best, best_s = [], -1.0
    for lf, pa, sc in zip(n_leaf, n_path, n_score, strict=False):
        if lf == leaf_pred and sc > best_s:
            best, best_s = pa, sc
    return best


def predict_arm(arm, n_macro, n_leaf, n_path, n_score):
    """Retourne (macro_pred, leaf_pred, path_pred) pour un bras donné, sur les voisins triés."""
    if arm == "top1-copy":
        return n_macro[0], n_leaf[0], n_path[0]

    if arm == "macro-gated":
        macro_pred = _weighted_vote(n_macro, n_score)
        keep = [i for i, m in enumerate(n_macro) if m == macro_pred]
        if not keep:  # garde-fou : aucun voisin de la macro votée → top-1 brut
            return macro_pred, n_leaf[0], n_path[0]
        i0 = keep[0]  # déjà triés par score décroissant
        return macro_pred, n_leaf[i0], n_path[i0]

    if arm == "knn-vote":
        macro_pred = _weighted_vote(n_macro, n_score)
        leaf_pred = _weighted_vote(n_leaf, n_score)
        return macro_pred, leaf_pred, _path_of_leaf(leaf_pred, n_leaf, n_path, n_score)

    if arm == "coarse-to-fine":
        macro_pred = _weighted_vote(n_macro, n_score)
        keep = [i for i, m in enumerate(n_macro) if m == macro_pred]
        if not keep:
            leaf_pred = _weighted_vote(n_leaf, n_score)
            return macro_pred, leaf_pred, _path_of_leaf(leaf_pred, n_leaf, n_path, n_score)
        kl = [n_leaf[i] for i in keep]
        ks = [n_score[i] for i in keep]
        kp = [n_path[i] for i in keep]
        leaf_pred = _weighted_vote(kl, ks)
        return macro_pred, leaf_pred, _path_of_leaf(leaf_pred, kl, kp, ks)

    raise ValueError(f"bras inconnu : {arm}")


# ───────────────────────────── métriques ───────────────────────────────────────
def _prefix_nodes(path: list[str]) -> set[str]:
    """Encodage préfixe : ['A','B','C'] → {'A','A > B','A > B > C'} (F1 hiérarchique)."""
    return {PATH_SEP.join(path[: i + 1]) for i in range(len(path))}


def _hierarchical_prf(true_paths, pred_paths) -> tuple[float, float, float]:
    """F1 hiérarchique (Kiritchenko) sur nœuds préfixés : crédit partiel le long du chemin."""
    inter = tp = pp = 0
    for t, p in zip(true_paths, pred_paths, strict=False):
        ts, ps = _prefix_nodes(t), _prefix_nodes(p)
        inter += len(ts & ps)
        tp += len(ts)
        pp += len(ps)
    hp = inter / pp if pp else 0.0
    hr = inter / tp if tp else 0.0
    hf = 2 * hp * hr / (hp + hr) if (hp + hr) else 0.0
    return hp, hr, hf


def _level_acc(true_paths, pred_paths, level: int) -> float:
    """Accuracy au niveau `level` du breadcrumb (sur les exemples qui ont ce niveau)."""
    ok = tot = 0
    for t, p in zip(true_paths, pred_paths, strict=False):
        if len(t) > level:
            tot += 1
            if len(p) > level and p[level] == t[level]:
                ok += 1
    return ok / tot if tot else 0.0


# ───────────────────────────── benchmark ───────────────────────────────────────
def run() -> dict:
    import faiss

    rng = np.random.default_rng(SEED)
    log.info("Chargement taxonomie + métadonnées train (aligné index)…")
    taxo = _load_taxonomy_lookup()
    _, tr_macro, tr_leaf, tr_path = _load_split_arrays("train", taxo)
    te_asin, te_macro, te_leaf, te_path = _load_split_arrays("test", taxo)

    # Échantillon stratifié par macro, uniquement les produits de test AVEC taxo fine.
    valid = np.array([i for i in range(len(te_leaf)) if te_leaf[i] is not None and te_path[i]])
    per_macro = defaultdict(list)
    for i in valid:
        per_macro[te_macro[i]].append(i)
    sample: list[int] = []
    n_per = max(1, SAMPLE_N // len(per_macro))
    for _macro, idxs in per_macro.items():
        idxs = np.array(idxs)
        take = min(n_per, len(idxs))
        sample.extend(rng.choice(idxs, size=take, replace=False).tolist())
    sample = np.array(sample)
    rng.shuffle(sample)
    log.info("Échantillon test stratifié : %d requêtes (sur %d valides).", len(sample), len(valid))

    log.info("Chargement embeddings test (mmap) + index HNSW (%s)…", INDEX_PATH.name)
    te_emb = np.load(EMBEDDINGS_DIR / "text_arctic_test.npy", mmap_mode="r")
    queries = np.ascontiguousarray(te_emb[sample], dtype=np.float32)
    index = faiss.read_index(str(INDEX_PATH))
    index.hnsw.efSearch = EF_SEARCH

    log.info("Recherche top-%d pour %d requêtes…", TOP_K, len(sample))
    t0 = time.perf_counter()
    scores, neighbors = index.search(queries, TOP_K)
    search_sec = time.perf_counter() - t0
    latency_ms = 1000.0 * search_sec / len(sample)

    arms = ["top1-copy", "macro-gated", "knn-vote", "coarse-to-fine"]
    results: dict[str, dict] = {}

    for arm in arms:
        macro_true, macro_pred = [], []
        leaf_true, leaf_pred = [], []
        true_paths, pred_paths = [], []
        recall_hits = 0
        for q, qi in enumerate(sample):
            nb = neighbors[q]
            sc = scores[q]
            ok = nb >= 0
            nb, sc = nb[ok], sc[ok]
            if len(nb) == 0:
                continue
            n_macro = tr_macro[nb]
            n_leaf = [tr_leaf[j] for j in nb]
            n_path = [tr_path[j] for j in nb]
            mp, lp, pp = predict_arm(arm, n_macro, n_leaf, n_path, sc)
            macro_true.append(te_macro[qi])
            macro_pred.append(mp if mp is not None else "")
            leaf_true.append(te_leaf[qi])
            leaf_pred.append(lp if lp is not None else "")
            true_paths.append(te_path[qi])
            pred_paths.append(pp if pp else [])
            if te_leaf[qi] in set(n_leaf):  # recall@k : la vraie feuille est-elle votable ?
                recall_hits += 1

        macro_acc = float(np.mean([a == b for a, b in zip(macro_true, macro_pred, strict=False)]))
        leaf_acc = float(np.mean([a == b for a, b in zip(leaf_true, leaf_pred, strict=False)]))
        leaf_wf1 = float(f1_score(leaf_true, leaf_pred, average="weighted", zero_division=0))
        l1_acc = _level_acc(true_paths, pred_paths, 0)
        l2_acc = _level_acc(true_paths, pred_paths, 1)
        hp, hr, hf = _hierarchical_prf(true_paths, pred_paths)
        recall_at_k = recall_hits / len(leaf_true) if leaf_true else 0.0

        results[arm] = {
            "macro_acc": round(macro_acc, 4),
            "path_L1_acc": round(l1_acc, 4),
            "path_L2_acc": round(l2_acc, 4),
            "leaf_acc": round(leaf_acc, 4),
            "leaf_weighted_f1": round(leaf_wf1, 4),
            "hierarchical_f1": round(hf, 4),
            f"recall_at_{TOP_K}_leaf": round(recall_at_k, 4),
            "n_eval": len(leaf_true),
        }
        log.info("%-18s leaf_acc=%.4f  hF=%.4f  macro_acc=%.4f", arm, leaf_acc, hf, macro_acc)

    champion = max(results, key=lambda a: results[a]["leaf_acc"])
    summary = {
        "config": {
            "sample_n": len(sample),
            "top_k": TOP_K,
            "ef_search": EF_SEARCH,
            "seed": SEED,
            "search_latency_ms_per_query": round(latency_ms, 3),
            "n_train_index": int(index.ntotal),
        },
        "results": results,
        "champion_by_leaf_acc": champion,
    }

    _log_mlflow(summary)
    _write_report(summary)
    log.info("CHAMPION (accuracy leaf) : %s", champion)
    return summary


def _log_mlflow(summary: dict) -> None:
    """Un run MLflow par bras (params = config, metrics = panel) - traçabilité."""
    try:
        import mlflow

        from src.mlops.mlflow_utils import setup_mlflow

        setup_mlflow()
        mlflow.set_experiment(EXPERIMENT)
        for arm, metrics in summary["results"].items():
            with mlflow.start_run(run_name=arm):
                mlflow.set_tags({"arm": arm, "task": "taxonomy_prediction"})
                mlflow.log_params(summary["config"])
                mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, int | float)})
                if arm == summary["champion_by_leaf_acc"]:
                    mlflow.set_tag("champion_by_leaf_acc", "true")
        log.info("Bras tracés dans MLflow (expérience '%s').", EXPERIMENT)
    except Exception as e:  # noqa: BLE001 - la traçabilité ne doit pas casser le calcul des scores
        log.warning("MLflow indisponible (scores calculés quand même) : %s", e)


def _write_report(summary: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "taxonomy_bench.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    cfg = summary["config"]
    cols = [
        "macro_acc",
        "path_L1_acc",
        "path_L2_acc",
        "leaf_acc",
        "leaf_weighted_f1",
        "hierarchical_f1",
        f"recall_at_{cfg['top_k']}_leaf",
    ]
    lines = [
        "# Benchmark taxonomie par retrieval (top1-copy → coarse-to-fine)",
        "",
        f"- Échantillon test stratifié : **{cfg['sample_n']}** requêtes · top-k={cfg['top_k']} · "
        f"efSearch={cfg['ef_search']} · seed={cfg['seed']}",
        f"- Index : {cfg['n_train_index']:_} vecteurs train · "
        f"latence recherche {cfg['search_latency_ms_per_query']:.2f} ms/requête",
        "",
        "| Bras | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for arm, m in summary["results"].items():
        star = " 🏆" if arm == summary["champion_by_leaf_acc"] else ""
        lines.append(f"| {arm}{star} | " + " | ".join(f"{m[c]:.4f}" for c in cols) + " |")
    lines += [
        "",
        f"**Champion (accuracy leaf) : `{summary['champion_by_leaf_acc']}`.**",
        "",
        "> Lecture : `leaf_acc` = catégorie la plus fine exacte ; `hierarchical_f1` = crédit "
        "partiel le long du breadcrumb (montre la progression) ; `recall@k` = la bonne feuille "
        "est présente parmi les voisins (plafond atteignable par un meilleur vote/re-ranking).",
    ]
    (REPORT_DIR / "taxonomy_bench.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Rapport écrit : %s", REPORT_DIR / "taxonomy_bench.md")


if __name__ == "__main__":
    run()

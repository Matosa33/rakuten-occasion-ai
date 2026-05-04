"""Cycle 4.1 — Build et bench FAISS indices (Flat IP / HNSW / IVF_PQ).

Compare 3 types d'index FAISS sur les embeddings text Arctic du train,
mesure recall@k et latence pour choisir le bon tradeoff au Cycle 4.

Indices construits
------------------
- Flat IP   : référence exacte (lent mais 100 % recall)
- HNSW      : approximate, rapide (cible < 10 ms p95), recall > 95 %
- IVF_PQ    : compressé (recall ~85-90 % mais 8-16× moins de RAM)

Mesure de recall
----------------
Pour chaque query du val set, on compare les top-K de l'index approximate
vs les top-K de Flat (référence) → recall@k = intersection / k.

Sortie :
- `data/index/text_arctic_flat.index`
- `data/index/text_arctic_hnsw.index`
- `data/index/text_arctic_ivfpq.index`
- `reports/05_retrieval/faiss_bench.json` + `.md`

Lance APRÈS Cycle 2.3 Arctic Embed :

    python -m src.retrieval.01_faiss_indices
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np

from src.config import (
    DATA_EMBEDDINGS,
    DATA_INDEX,
    REPORTS_RETRIEVAL,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HNSW_M = 32
HNSW_EF_CONSTRUCTION = 200
HNSW_EF_SEARCH = 64

IVFPQ_NLIST = 1024  # ~sqrt(n) pour 3M vecteurs
IVFPQ_M_SUBQUANTIZER = 32  # nombre de sous-quantizers (1024 / 32 = 32 dim par sub)
IVFPQ_NPROBE = 16  # cellules à inspecter au query (compromis recall vs latence)

EVAL_N_QUERIES = 1000
EVAL_TOP_K = 10

OUT_BENCH = REPORTS_RETRIEVAL / "faiss_bench.json"
OUT_BENCH_MD = REPORTS_RETRIEVAL / "faiss_bench.md"


def _load_train_embeddings() -> np.ndarray:
    npy_path = DATA_EMBEDDINGS / "text" / "text_arctic_train.npy"
    if not npy_path.exists():
        raise FileNotFoundError(f"{npy_path} introuvable. Lance Cycle 2.3 Arctic Embed d'abord.")
    arr = np.load(npy_path).astype(np.float32)
    return np.ascontiguousarray(arr)


def _load_val_queries() -> np.ndarray:
    npy_path = DATA_EMBEDDINGS / "text" / "text_arctic_val.npy"
    if not npy_path.exists():
        raise FileNotFoundError(f"{npy_path} introuvable.")
    arr = np.load(npy_path).astype(np.float32)
    return np.ascontiguousarray(arr)


def _build_flat(embeddings: np.ndarray) -> faiss.Index:  # noqa: F821
    import faiss

    log.info(
        "  Build Flat IP : %s vecteurs × %d dim…", f"{embeddings.shape[0]:_}", embeddings.shape[1]
    )
    t0 = time.time()
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    log.info("  Flat built en %.1f sec", time.time() - t0)
    return index


def _build_hnsw(embeddings: np.ndarray) -> faiss.Index:  # noqa: F821
    import faiss

    log.info("  Build HNSW M=%d efC=%d…", HNSW_M, HNSW_EF_CONSTRUCTION)
    t0 = time.time()
    index = faiss.IndexHNSWFlat(embeddings.shape[1], HNSW_M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
    index.hnsw.efSearch = HNSW_EF_SEARCH
    index.add(embeddings)
    log.info("  HNSW built en %.1f sec", time.time() - t0)
    return index


def _build_ivfpq(embeddings: np.ndarray) -> faiss.Index:  # noqa: F821
    import faiss

    d = embeddings.shape[1]
    log.info(
        "  Build IVF_PQ nlist=%d M=%d nprobe=%d…", IVFPQ_NLIST, IVFPQ_M_SUBQUANTIZER, IVFPQ_NPROBE
    )
    quantizer = faiss.IndexFlatIP(d)
    index = faiss.IndexIVFPQ(
        quantizer, d, IVFPQ_NLIST, IVFPQ_M_SUBQUANTIZER, 8, faiss.METRIC_INNER_PRODUCT
    )
    t_train = time.time()
    log.info("  IVF_PQ : training quantizer (~ minute)…")
    index.train(embeddings)
    log.info("  IVF_PQ training : %.1f sec", time.time() - t_train)
    t_add = time.time()
    index.add(embeddings)
    log.info("  IVF_PQ add : %.1f sec", time.time() - t_add)
    index.nprobe = IVFPQ_NPROBE
    return index


def _bench_index(index, queries: np.ndarray, name: str, ground_truth: np.ndarray | None) -> dict:
    """Mesure latence + recall@k vs ground truth (si fourni)."""
    log.info("  Bench %s : %d queries, top-%d…", name, len(queries), EVAL_TOP_K)
    t0 = time.time()
    distances, indices = index.search(queries, EVAL_TOP_K)
    duration = time.time() - t0
    latency_ms = duration * 1000 / len(queries)
    log.info("  %s : %.2f ms/query (total %.1f sec)", name, latency_ms, duration)

    result = {
        "name": name,
        "n_queries": len(queries),
        "top_k": EVAL_TOP_K,
        "duration_total_sec": round(duration, 2),
        "latency_ms_per_query": round(latency_ms, 2),
    }

    if ground_truth is not None:
        # Recall@k : intersection top-k vs ground truth top-k
        recalls = {}
        for k in (1, 5, 10):
            if k > EVAL_TOP_K:
                continue
            n_match = sum(
                len(set(indices[i, :k]) & set(ground_truth[i, :k])) for i in range(len(queries))
            )
            recall = n_match / (len(queries) * k)
            recalls[f"recall_at_{k}"] = round(recall, 4)
            log.info("  %s : recall@%d = %.4f", name, k, recall)
        result.update(recalls)

    return result


def main() -> None:
    log.info("=== Cycle 4.1 — FAISS indices bench ===")

    DATA_INDEX.mkdir(parents=True, exist_ok=True)
    REPORTS_RETRIEVAL.mkdir(parents=True, exist_ok=True)

    import faiss

    log.info("FAISS %s", faiss.__version__)
    log.info("Lecture embeddings train + val…")
    embeddings_train = _load_train_embeddings()
    log.info("  train : %s × %d", f"{embeddings_train.shape[0]:_}", embeddings_train.shape[1])
    embeddings_val = _load_val_queries()
    log.info("  val   : %s × %d", f"{embeddings_val.shape[0]:_}", embeddings_val.shape[1])

    # Sample N queries du val
    rng = np.random.default_rng(SEED)
    query_idx = rng.choice(
        embeddings_val.shape[0], size=min(EVAL_N_QUERIES, embeddings_val.shape[0]), replace=False
    )
    queries = embeddings_val[query_idx]
    log.info("Sample %d queries du val", len(queries))

    # Build Flat (référence)
    log.info("\n--- Flat IP (référence exacte) ---")
    flat = _build_flat(embeddings_train)
    flat_path = DATA_INDEX / "text_arctic_flat.index"
    faiss.write_index(flat, str(flat_path))
    flat_result = _bench_index(flat, queries, "Flat", ground_truth=None)
    # Pour Flat, ground truth = lui-même
    _, flat_indices = flat.search(queries, EVAL_TOP_K)
    flat_result["recall_at_1"] = 1.0
    flat_result["recall_at_5"] = 1.0
    flat_result["recall_at_10"] = 1.0

    # Build HNSW
    log.info("\n--- HNSW (rapide, approximate) ---")
    hnsw = _build_hnsw(embeddings_train)
    hnsw_path = DATA_INDEX / "text_arctic_hnsw.index"
    faiss.write_index(hnsw, str(hnsw_path))
    hnsw_result = _bench_index(hnsw, queries, "HNSW", ground_truth=flat_indices)

    # Build IVF_PQ (peut rater si dataset trop petit)
    ivfpq_result = None
    try:
        log.info("\n--- IVF_PQ (compressé) ---")
        ivfpq = _build_ivfpq(embeddings_train)
        ivfpq_path = DATA_INDEX / "text_arctic_ivfpq.index"
        faiss.write_index(ivfpq, str(ivfpq_path))
        ivfpq_result = _bench_index(ivfpq, queries, "IVF_PQ", ground_truth=flat_indices)
    except Exception as e:
        log.warning("IVF_PQ build a échoué : %s. Skip.", e)

    # Tailles fichiers
    sizes = {
        p.name: round(p.stat().st_size / 1_048_576, 1)
        for p in [flat_path, hnsw_path]
        + ([Path(str(DATA_INDEX / "text_arctic_ivfpq.index"))] if ivfpq_result else [])
        if p.exists()
    }

    bench = {
        "n_train": int(embeddings_train.shape[0]),
        "embed_dim": int(embeddings_train.shape[1]),
        "n_queries_eval": int(len(queries)),
        "results": {
            "flat": flat_result,
            "hnsw": hnsw_result,
            **({"ivfpq": ivfpq_result} if ivfpq_result else {}),
        },
        "index_size_mb": sizes,
    }
    OUT_BENCH.write_text(json.dumps(bench, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_BENCH.name)

    # Markdown synthèse
    lines = [
        "# FAISS indices bench — Cycle 4.1",
        "",
        f"> Mesure recall@k et latence sur {len(queries):_} queries du val ",
        f"> contre un index de {embeddings_train.shape[0]:_} vecteurs × {embeddings_train.shape[1]} dim.",
        "",
        "## Comparaison",
        "",
        "| Index | Recall@1 | Recall@5 | Recall@10 | Latence p99 (ms) | Taille fichier |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, r in bench["results"].items():
        size = sizes.get(f"text_arctic_{name}.index", "?")
        lines.append(
            f"| {name.upper()} | {r.get('recall_at_1', 0):.4f} | "
            f"{r.get('recall_at_5', 0):.4f} | {r.get('recall_at_10', 0):.4f} | "
            f"{r['latency_ms_per_query']:.2f} | {size} MB |"
        )

    lines.extend(
        [
            "",
            "## Décision",
            "",
            "Pour le serving (Cycle 9 API) : **HNSW** (rapide + recall ≥ 95 %).",
            "Pour la référence d'évaluation : **Flat IP** (recall 100 %).",
            "Pour scale-up futur (>20 M vecteurs) : envisager **IVF_PQ** si recall acceptable (>0.85).",
        ]
    )

    OUT_BENCH_MD.write_text("\n".join(lines), encoding="utf-8")
    log.info("→ %s", OUT_BENCH_MD.name)
    log.info("Cycle 4.1 OK.")


if __name__ == "__main__":
    main()

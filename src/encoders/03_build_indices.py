"""Sous-todo 2.4 - Build indices FAISS sur les embeddings vision + texte.

Crée les indices FAISS qui permettront le retrieval rapide en Cycle 4.

Indices construits
------------------
- `data/index/text_arctic_flat.index`  : Flat IP (référence exacte, lent)
- `data/index/text_arctic_hnsw.index`  : HNSW (rapide, < 10ms cible)
- `data/index/vision_siglip_hnsw.index` : si vision_siglip_v1.npy dispo

Méthode HNSW : M=32, efConstruction=200, efSearch=64 (cf. ADR D-009 §3.2).
Métrique : INNER_PRODUCT (équivalent cosine sur vecteurs L2-normalisés,
plus rapide en FAISS que cosine direct).

Sanity check intégré
--------------------
Après build, sur 10 queries aléatoires du train, vérifier :
- top-1 retrouve le query lui-même (cosine ≈ 1) → preuve que l'index est correct
- top-5 ont des cosines > 0.5 → preuve que les voisins sémantiques existent

Lance ce script depuis la racine :

    python -m src.encoders.03_build_indices
"""

from __future__ import annotations

import logging
import time

import numpy as np

from src.config import (
    DATA_EMBEDDINGS,
    DATA_INDEX,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Paramètres HNSW (cf. ADR D-009 §3.2)
HNSW_M = 32
HNSW_EF_CONSTRUCTION = 200
HNSW_EF_SEARCH = 64

# Sanity check
N_SANITY_QUERIES = 10
SANITY_TOP_K = 5


def _load_embeddings(npy_path) -> np.ndarray:
    """Load .npy en mémoire (FP16 → FP32 pour FAISS)."""
    arr = np.load(npy_path)
    log.info("  Loaded %s : shape=%s, dtype=%s", npy_path.name, arr.shape, arr.dtype)
    # FAISS ne supporte pas FP16 nativement → cast en FP32 pour build
    if arr.dtype != np.float32:
        arr = arr.astype(np.float32)
    return np.ascontiguousarray(arr)


def _build_hnsw_index(embeddings: np.ndarray, name: str) -> faiss.Index:  # noqa: F821
    """Build FAISS HNSW index (INNER_PRODUCT métrique)."""
    import faiss

    n, d = embeddings.shape
    log.info(
        "  Build HNSW M=%d efC=%d : %s vecteurs × %d dim…",
        HNSW_M,
        HNSW_EF_CONSTRUCTION,
        f"{n:_}",
        d,
    )
    t0 = time.time()
    index = faiss.IndexHNSWFlat(d, HNSW_M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
    index.hnsw.efSearch = HNSW_EF_SEARCH
    index.add(embeddings)
    duration = time.time() - t0
    log.info(
        "  HNSW %s built : %s vecteurs en %.1f sec (%.0f items/sec)",
        name,
        f"{n:_}",
        duration,
        n / duration,
    )
    return index


def _build_flat_index(embeddings: np.ndarray, name: str) -> faiss.Index:  # noqa: F821
    """Build FAISS Flat index (référence exacte, baseline pour mesure recall)."""
    import faiss

    n, d = embeddings.shape
    log.info("  Build Flat IP : %s vecteurs × %d dim…", f"{n:_}", d)
    t0 = time.time()
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    log.info("  Flat %s built en %.1f sec", name, time.time() - t0)
    return index


def _sanity_check(index, embeddings: np.ndarray, name: str) -> dict:
    """Sanity : tirer N queries du corpus, vérifier que top-1 = self."""
    rng = np.random.default_rng(SEED)
    n = embeddings.shape[0]
    query_idx = rng.choice(n, size=N_SANITY_QUERIES, replace=False)
    queries = embeddings[query_idx]

    log.info("  Sanity check %s : %d queries, top-%d…", name, N_SANITY_QUERIES, SANITY_TOP_K)
    t0 = time.time()
    distances, indices = index.search(queries, SANITY_TOP_K)
    latency_ms = (time.time() - t0) * 1000 / N_SANITY_QUERIES

    # Vérifications
    n_top1_self = sum(1 for q, top1 in zip(query_idx, indices[:, 0], strict=False) if top1 == q)
    mean_top1_score = float(distances[:, 0].mean())
    mean_top5_score = float(distances[:, :SANITY_TOP_K].mean())

    log.info(
        "  Sanity %s : top-1 = self pour %d/%d queries (cible %d/%d)",
        name,
        n_top1_self,
        N_SANITY_QUERIES,
        N_SANITY_QUERIES,
        N_SANITY_QUERIES,
    )
    log.info("  Sanity %s : mean top-1 score = %.4f (cible ≈ 1.0)", name, mean_top1_score)
    log.info("  Sanity %s : mean top-5 score = %.4f", name, mean_top5_score)
    log.info("  Sanity %s : latence = %.2f ms par query", name, latency_ms)

    return {
        "n_top1_self": n_top1_self,
        "mean_top1_score": round(mean_top1_score, 4),
        "mean_top5_score": round(mean_top5_score, 4),
        "latency_ms_per_query": round(latency_ms, 2),
    }


def main() -> None:
    log.info("=== Sous-todo 2.4 - Build indices FAISS + sanity check ===")

    DATA_INDEX.mkdir(parents=True, exist_ok=True)

    import faiss

    log.info("FAISS %s", faiss.__version__)

    results = {}

    # --- TEXT (Arctic Embed) ---
    text_npy_train = DATA_EMBEDDINGS / "text" / "text_arctic_train.npy"
    if text_npy_train.exists():
        log.info("\n--- Text Arctic Embed (train uniquement pour index ; val/test = queries) ---")
        embeddings_text = _load_embeddings(text_npy_train)

        idx_hnsw_text = _build_hnsw_index(embeddings_text, "text_arctic")
        out_path = DATA_INDEX / "text_arctic_hnsw.index"
        faiss.write_index(idx_hnsw_text, str(out_path))
        log.info("  → %s écrit (%.1f MB)", out_path.name, out_path.stat().st_size / 1_048_576)

        results["text_arctic_hnsw"] = _sanity_check(idx_hnsw_text, embeddings_text, "text_hnsw")
    else:
        log.warning("text_arctic_train.npy non trouvé, skip TEXT")

    # --- VISION (SigLIP) ---
    vision_npy = DATA_EMBEDDINGS / "vision_siglip_v1.npy"
    if vision_npy.exists():
        log.info("\n--- Vision SigLIP (concat global) ---")
        embeddings_vision = _load_embeddings(vision_npy)

        idx_hnsw_vision = _build_hnsw_index(embeddings_vision, "vision_siglip")
        out_path = DATA_INDEX / "vision_siglip_hnsw.index"
        faiss.write_index(idx_hnsw_vision, str(out_path))
        log.info("  → %s écrit (%.1f MB)", out_path.name, out_path.stat().st_size / 1_048_576)

        results["vision_siglip_hnsw"] = _sanity_check(
            idx_hnsw_vision, embeddings_vision, "vision_hnsw"
        )
    else:
        log.warning("vision_siglip_v1.npy non trouvé, skip VISION (à générer en sous-todo 2.2)")

    if not results:
        log.error("Aucun embedding trouvé, sortie sans build d'index.")
        return

    log.info("\n=== Synthèse ===")
    for name, r in results.items():
        log.info(
            "  [%s] top-1=self : %d/%d, mean_top1_score=%.4f, latency=%.2fms",
            name,
            r["n_top1_self"],
            N_SANITY_QUERIES,
            r["mean_top1_score"],
            r["latency_ms_per_query"],
        )

    log.info("\nSous-todo 2.4 OK.")


if __name__ == "__main__":
    main()

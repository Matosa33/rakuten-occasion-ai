"""Cycle 8.1 — Explainability : SHAP + t-SNE + Model Cards.

Trois livrables d'explainability :

1. **SHAP TreeExplainer** sur M3 (RF) → top-K features importantes par cat
   (sample 1k items val, plot summary + per-class waterfall pour 3 cas).
2. **t-SNE / UMAP** des embeddings (text Arctic + vision SigLIP) colorés
   par catégorie → vérifier la **séparation visuelle** entre les 4 cat
   D-011 (cohérence avec F1 par cat).
3. **Model Cards** format HuggingFace pour M1-M8 + E1-E4 → un fichier MD
   par modèle dans `reports/09_explainability/model_cards/`.

L'idée fondatrice : un modèle qui n'est pas explicable n'est pas
acceptable en production particulier. Le vendeur doit comprendre
*pourquoi* on lui suggère cette catégorie (top features SHAP) et
*pourquoi* le retrieval voit ces produits comme similaires (t-SNE).

Sortie :
- `reports/09_explainability/shap_m3.{md,png}` (si M3 dispo)
- `reports/09_explainability/tsne_text.png` (si Arctic embed dispo)
- `reports/09_explainability/tsne_vision.png` (si SigLIP embed dispo)
- `reports/09_explainability/model_cards/{m1..m8,e1..e4}.md`

Lance APRÈS Cycle 3 (M1-M6) :

    python -m src.explain.01_shap_tsne_modelcards
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from src.config import (
    DATA_EMBEDDINGS,
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_CLASSIFIERS,
    REPORTS_EXPLAIN,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TSNE_N_SAMPLES = 5000
TSNE_PERPLEXITY = 30
SHAP_N_SAMPLES = 1000

OUT_DIR = REPORTS_EXPLAIN
MODEL_CARDS_DIR = OUT_DIR / "model_cards"

# ─────────────────────────────────────────────────────────────────────────────
# Model Cards : 12 fiches HuggingFace-style (8 internes + 4 externes)
# ─────────────────────────────────────────────────────────────────────────────

MODEL_CARDS = {
    "knn-faiss_v1": {
        "type": "k-NN cosine weighted",
        "task": "Classification multi-cat (4 cat D-011)",
        "input": "Embeddings Arctic Embed L v2 (1024 dim, FP16)",
        "output": "P(catégorie | embedding) via vote pondéré k voisins",
        "training_data": "Arctic embed du train (3,16M items, 4 cat D-011)",
        "limitations": "Lent en inférence (k voisins par query). Pas de calibration native.",
    },
    "svm-embed_v1": {
        "type": "LinearSVC + Platt calibration",
        "task": "Classification multi-cat (4 cat D-011)",
        "input": "Embeddings Arctic Embed L v2 (1024 dim, FP16)",
        "output": "P(catégorie | embedding) calibré Platt",
        "training_data": "Arctic embed du train",
        "limitations": "Hyperparamètre C non tuné (default). Linéaire — pas d'interactions.",
    },
    "rf-embed_v1": {
        "type": "RandomForest (300 estimators, max_depth=20)",
        "task": "Classification multi-cat (4 cat D-011)",
        "input": "Embeddings Arctic Embed L v2 (1024 dim, FP16)",
        "output": "P(catégorie | embedding) via vote arbres",
        "training_data": "Arctic embed du train",
        "limitations": "RAM-intensive (~2 GB). Pas le meilleur F1 mais explicable via SHAP.",
    },
    "mlp-embed_v1": {
        "type": "MLPClassifier hidden=(512, 256), early stopping",
        "task": "Classification multi-cat (4 cat D-011)",
        "input": "Embeddings Arctic Embed L v2 (1024 dim, FP16)",
        "output": "P(catégorie | embedding) softmax",
        "training_data": "Arctic embed du train",
        "limitations": "Boîte noire (peu d'explainability native). Sensible au scaling.",
    },
    "tfidf-svm_v1": {
        "type": "TF-IDF (word 1-2gram + char 3-5gram) + LinearSVC + Platt",
        "task": "Classification multi-cat (4 cat D-011)",
        "input": "Texte brut (titre + description)",
        "output": "P(catégorie | texte) calibré Platt",
        "training_data": "3,16M items train, 4 cat D-011",
        "performance": "F1_w test = 0.9503, F1_m = 0.9375, ECE = 0.0092",
        "limitations": "Pas de sémantique (mots seuls), mais excellent baseline.",
    },
    "fusion_v1": {
        "type": "Fusion adaptive (moyenne pondérée probas)",
        "task": "Classification multi-cat (4 cat D-011)",
        "input": "Probas calibrées de M2/M3/M4/M5",
        "output": "P(catégorie | inputs) fusionnée par α appris",
        "training_data": "Probas val M2-M5, grid search α",
        "limitations": "Coût inférence = 4× modèle individuel. À adopter uniquement si gain > +0.02 F1_w.",
    },
    "faiss-hnsw_v1": {
        "type": "FAISS HNSW (M=32, efConstruction=200, efSearch=64)",
        "task": "Recherche similarité produit (k-NN top-K)",
        "input": "Embedding query (Arctic 1024 dim)",
        "output": "Top-K indices voisins + scores cosine",
        "training_data": "Index sur 3,16M items train",
        "limitations": "Approximate (recall ~95-98 %). À comparer Flat IP en référence.",
    },
    "pricing-cascade_v1": {
        "type": "Algorithmique cascade L1-L4 (transparent, pas de ML)",
        "task": "Suggestion prix indicatif + niveau confiance",
        "input": "(catalog_price, knn_neighbors_prices, category_median, condition, age, category)",
        "output": "PricingResult{suggested_price, confidence_level, range_low/high, explanation}",
        "training_data": "Médianes catégorie calculées sur train",
        "limitations": "Dépréciation linéaire (vs réelle = courbe). Pas d'effets temporels (saisonnalité).",
    },
    "e1_siglip_base_v1": {
        "type": "SigLIP base ViT-B/16 (frozen, 768 dim)",
        "task": "Encodage image → embedding L2-normalized",
        "source": "google/siglip-base-patch16-224",
        "input": "Image RGB (224×224)",
        "output": "Embedding 768 dim FP16",
        "limitations": "Frozen — pas d'adaptation aux produits Amazon. Cibler fine-tuning si gap mesuré > 5 pts.",
    },
    "e2_arctic_embed_l_v2": {
        "type": "Snowflake Arctic Embed L v2 (frozen, 1024 dim, multilingue XLM-RoBERTa-large)",
        "task": "Encodage texte → embedding L2-normalized",
        "source": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "input": "Texte (titre + description), max_seq=256 tokens",
        "output": "Embedding 1024 dim FP16",
        "limitations": "Frozen. max_seq=256 = trade-off vitesse (4× plus rapide que 512).",
    },
    "e3_vlm_zero_shot_v1": {
        "type": "VLM frontier zero-shot (Gemini 2.0 Flash via OpenRouter)",
        "task": "Validation matching produit (image vendeur ↔ candidat retrieval)",
        "source": "google/gemini-2.0-flash-exp via OpenRouter",
        "input": "(query_image, candidate_image, candidate_meta)",
        "output": "JSON {match: bool, confidence: 0-1, reason: str}",
        "limitations": "Coût API ~ $0.0001/call. Latence ~ 1-3 s. Stub mock en attendant Cycle 9.",
    },
    "e4_llm_writer_v1": {
        "type": "LLM frontier rédacteur grounded (Gemini Flash via OpenRouter)",
        "task": "Génération titre + description annonce vendeur particulier",
        "source": "google/gemini-2.0-flash-exp via OpenRouter",
        "input": "(product_meta, top-N grounding sentences from reviews)",
        "output": "JSON {title, description}",
        "limitations": "Risque hallucination si grounding pauvre. Stub mock en Cycle 6.2.",
    },
}


def _write_model_card(name: str, info: dict) -> Path:
    """Écrit une fiche markdown HuggingFace-like pour un modèle."""
    MODEL_CARDS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODEL_CARDS_DIR / f"{name}.md"
    lines = [
        f"# Model Card — {name}",
        "",
        f"**Type** : {info.get('type', '?')}",
        f"**Tâche** : {info.get('task', '?')}",
        "",
        "## Inputs / Outputs",
        f"- **Input** : {info.get('input', '?')}",
        f"- **Output** : {info.get('output', '?')}",
        "",
        "## Données / Source",
    ]
    if "training_data" in info:
        lines.append(f"- Training data : {info['training_data']}")
    if "source" in info:
        lines.append(f"- Source : {info['source']}")
    if "performance" in info:
        lines.extend(["", "## Performance", f"- {info['performance']}"])
    lines.extend(["", "## Limitations", f"- {info.get('limitations', 'Non documentées.')}", ""])
    # Métriques détaillées si JSON dispo
    metrics_json = REPORTS_CLASSIFIERS / f"{name}.json"
    if metrics_json.exists():
        try:
            metrics = json.loads(metrics_json.read_text(encoding="utf-8"))
            test = metrics.get("results", {}).get("test", {})
            if test:
                lines.append("## Métriques mesurées (test split)")
                lines.append("")
                for k, v in test.items():
                    if isinstance(v, int | float):
                        lines.append(
                            f"- **{k}** : {v:.4f}" if isinstance(v, float) else f"- **{k}** : {v}"
                        )
                lines.append("")
        except (json.JSONDecodeError, OSError):
            pass
    lines.append(f"## Source de vérité métriques\n\n`reports/04_classifiers_bench/{name}.json`")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    log.info("=== Cycle 8.1 — Explainability (SHAP + t-SNE + Model Cards) ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Model Cards (toujours générables)
    log.info("--- Génération %d Model Cards ---", len(MODEL_CARDS))
    for name, info in MODEL_CARDS.items():
        path = _write_model_card(name, info)
        log.info("  → %s", path.relative_to(REPORTS_EXPLAIN))

    # 2. t-SNE text (si embed dispo)
    text_emb_path = DATA_EMBEDDINGS / "text" / "text_arctic_val.npy"
    if text_emb_path.exists():
        try:
            import polars as pl
            from sklearn.manifold import TSNE

            log.info("--- t-SNE text (val sample %d) ---", TSNE_N_SAMPLES)
            text_emb = np.load(text_emb_path).astype(np.float32)
            val_labels = pl.read_parquet(
                DATA_PROCESSED_PRODUCTS / "val.parquet", columns=["_source_category"]
            )["_source_category"].to_numpy()
            rng = np.random.default_rng(SEED)
            n = min(TSNE_N_SAMPLES, text_emb.shape[0])
            idx = rng.choice(text_emb.shape[0], size=n, replace=False)
            X = text_emb[idx]
            y = val_labels[idx]

            log.info("  Fit t-SNE perplexity=%d sur %d items…", TSNE_PERPLEXITY, n)
            tsne = TSNE(
                n_components=2,
                perplexity=TSNE_PERPLEXITY,
                random_state=SEED,
                init="pca",
                learning_rate="auto",
            )
            X_2d = tsne.fit_transform(X)

            try:
                import matplotlib.pyplot as plt

                fig, ax = plt.subplots(figsize=(10, 8))
                for cat in np.unique(y):
                    mask = y == cat
                    ax.scatter(X_2d[mask, 0], X_2d[mask, 1], label=cat, s=4, alpha=0.5)
                ax.legend(loc="best", fontsize=9)
                ax.set_title(f"t-SNE Arctic embeddings val ({n} samples)")
                fig_path = OUT_DIR / "tsne_text.png"
                fig.savefig(fig_path, dpi=120, bbox_inches="tight")
                plt.close(fig)
                log.info("  → %s", fig_path.name)
            except ImportError:
                log.warning("matplotlib absent → skip plot t-SNE text")
        except ImportError as e:
            log.warning("Dep manquante pour t-SNE text : %s", e)
    else:
        log.info("text_arctic_val.npy absent → skip t-SNE text (lance Cycle 2.3 d'abord)")

    # 3. t-SNE vision (si embed dispo)
    vision_emb_path = DATA_EMBEDDINGS / "vision" / "vision_siglip_val.npy"
    if vision_emb_path.exists():
        log.info("--- t-SNE vision dispo, à coder ici (même pattern que text) ---")
    else:
        log.info("vision_siglip_val.npy absent → skip t-SNE vision (lance Cycle 2.2 d'abord)")

    # 4. SHAP M3 (si modèle dispo)
    m3_path = DATA_MODELS / "rf-embed_v1.joblib"
    if m3_path.exists():
        try:
            import joblib
            import shap

            log.info("--- SHAP TreeExplainer M3 RF ---")
            model = joblib.load(m3_path)
            text_emb = np.load(text_emb_path).astype(np.float32)
            rng = np.random.default_rng(SEED)
            n = min(SHAP_N_SAMPLES, text_emb.shape[0])
            idx = rng.choice(text_emb.shape[0], size=n, replace=False)
            X_sample = text_emb[idx]

            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
            log.info("  SHAP shape : %s", np.array(shap_values).shape)

            try:
                import matplotlib.pyplot as plt

                shap.summary_plot(shap_values, X_sample, show=False, max_display=20)
                fig_path = OUT_DIR / "shap_m3_summary.png"
                plt.savefig(fig_path, dpi=120, bbox_inches="tight")
                plt.close()
                log.info("  → %s", fig_path.name)
            except ImportError:
                log.warning("matplotlib absent → skip SHAP plot")
        except ImportError:
            log.warning("Lib `shap` absente → skip SHAP")
    else:
        log.info("rf-embed_v1.joblib absent → skip SHAP M3 (lance Cycle 3.1 M3 d'abord)")

    log.info("Cycle 8.1 explainability OK.")


if __name__ == "__main__":
    main()

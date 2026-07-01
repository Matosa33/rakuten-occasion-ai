"""Cycle 4.3 - Akinator backend : désambiguation par observations dirigées.

Quand le retrieval renvoie plusieurs candidats à scores proches
(top1_score - top2_score < seuil_ambiguïté), on lève l'ambiguïté **par
observations dirigées** (R19 grounded-avant-génératif) :

1. Calculer les **attributs discriminants** entre top-K (différence de
   schéma sur leurs métadonnées indexées : storage, color, model_number,
   version, year, dimensions…).
2. Mapper l'attribut le plus discriminant à un **type d'observation à
   demander à l'utilisateur** (vue dos, scan étiquette, OCR ciblé…) -
   PAS de question textuelle au vendeur (cf. golden_rules R19).
3. Re-scorer les candidats avec la nouvelle observation (côté API).
4. Boucler jusqu'à `top1_score - top2_score > seuil_clarté` OU épuisement
   des observations possibles → mode dégradé "produit non identifié".

Module **importable** (utilisé par `src/api/`) + demo CLI sur val.

Lance pour démo + métriques :

    python -m src.retrieval.04_akinator_backend
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass

import numpy as np
import polars as pl

from src.config import (
    DATA_EMBEDDINGS,
    DATA_INDEX,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_RETRIEVAL,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EVAL_N_QUERIES = 2000
TOP_K_AMBIG = 5  # Nombre de candidats considérés pour calcul discriminants
AMBIGUITY_GAP_THRESHOLD = 0.05
CLARITY_GAP_THRESHOLD = 0.10  # Seuil pour considérer la situation comme désambiguïsée

OUT_JSON = REPORTS_RETRIEVAL / "akinator_backend_eval.json"

# ─────────────────────────────────────────────────────────────────────────────
# Mapping attribut métadonnée → observation à demander
# ─────────────────────────────────────────────────────────────────────────────
# Heuristique : pour chaque famille d'attributs discriminants, on retourne
# une instruction d'observation (lisible par l'API frontend pour guider
# l'utilisateur). L'idée fondatrice : "demander à voir, pas à savoir".

ATTRIBUTE_OBSERVATION_MAP: dict[str, dict[str, str]] = {
    "color": {
        "type": "color_close_up",
        "instruction": "Prenez une photo en lumière naturelle d'un détail bien coloré du produit (façade, coque arrière)",
    },
    "storage_capacity": {
        "type": "label_scan",
        "instruction": "Photographiez l'étiquette du produit (souvent au dos) où la capacité est imprimée",
    },
    "memory": {
        "type": "label_scan",
        "instruction": "Photographiez la zone où la mémoire est indiquée (étiquette, écran 'À propos' si appareil démarrable)",
    },
    "model_number": {
        "type": "back_view",
        "instruction": "Tournez le produit pour photographier sa face arrière où le numéro de modèle est imprimé",
    },
    "version": {
        "type": "label_scan",
        "instruction": "Photographiez l'étiquette indiquant la version/génération",
    },
    "year": {
        "type": "back_view",
        "instruction": "Photographiez la zone où l'année de fabrication est gravée (souvent sous le produit)",
    },
    "dimensions": {
        "type": "dimensions_compare",
        "instruction": "Posez le produit à côté d'un objet de référence (carte bancaire, smartphone) pour photo",
    },
    "connector_type": {
        "type": "connector_view",
        "instruction": "Photographiez les ports/connecteurs (USB, jack, etc.)",
    },
    "port": {
        "type": "connector_view",
        "instruction": "Photographiez les ports/connecteurs en gros plan",
    },
    "upc": {
        "type": "barcode_scan",
        "instruction": "Scannez le code-barres (au dos ou sur l'emballage)",
    },
    "ean": {
        "type": "barcode_scan",
        "instruction": "Scannez le code-barres EAN (au dos ou sur l'emballage)",
    },
    "barcode": {
        "type": "barcode_scan",
        "instruction": "Scannez le code-barres",
    },
    "brand": {
        "type": "logo_zone",
        "instruction": "Photographiez le logo de la marque sur le produit",
    },
}

# Fallback si attribut inconnu : on demande une vue arrière générique
DEFAULT_OBSERVATION = {
    "type": "back_view",
    "instruction": "Photographiez la face arrière du produit où les informations techniques sont généralement imprimées",
}


@dataclass
class ObservationRequest:
    """Réponse Akinator : observation à demander à l'utilisateur."""

    attribute: str  # nom de l'attribut métadonnée discriminant
    observation_type: str  # type d'observation (back_view, label_scan, …)
    instruction: str  # instruction lisible pour le frontend
    candidates_count: int  # nb de candidats encore en lice
    discriminative_score: float  # entropie normalisée [0, 1]


def is_ambiguous(
    top1_score: float, top2_score: float, threshold: float = AMBIGUITY_GAP_THRESHOLD
) -> bool:
    """True si l'écart top-1 / top-2 est trop faible → Akinator nécessaire."""
    return (top1_score - top2_score) < threshold


def is_clarified(
    top1_score: float, top2_score: float, threshold: float = CLARITY_GAP_THRESHOLD
) -> bool:
    """True si après désambiguation, l'écart est suffisant pour conclure."""
    return (top1_score - top2_score) > threshold


def compute_discriminative_attributes(
    candidates_metadata: list[dict],
    candidate_attributes: list[str] | None = None,
) -> list[tuple[str, float]]:
    """Calcule pour chaque attribut son pouvoir discriminant entre les candidats.

    On utilise l'**entropie normalisée** des valeurs : un attribut est très
    discriminant si chaque candidat a une valeur unique (entropie max).
    Un attribut où tous les candidats partagent la même valeur est inutile
    pour désambiguer (entropie = 0).

    Args:
        candidates_metadata: liste de dicts `{attribute: value}` pour chaque
            candidat top-K.
        candidate_attributes: si fourni, restreint l'analyse à ces attributs
            (utile pour ignorer les colonnes non observables comme price).

    Returns:
        Liste de (attribute_name, normalized_entropy) triée par discriminance
        décroissante. Entropie normalisée ∈ [0, 1] où 1 = tous différents.
    """
    if not candidates_metadata:
        return []

    # Collecte des attributs présents dans au moins 2 candidats
    attr_counter: Counter[str] = Counter()
    for cand in candidates_metadata:
        for attr in cand:
            if cand[attr] is not None and cand[attr] != "":
                attr_counter[attr] += 1
    eligible_attrs = [a for a, n in attr_counter.items() if n >= 2]

    if candidate_attributes is not None:
        eligible_attrs = [a for a in eligible_attrs if a in candidate_attributes]

    n_candidates = len(candidates_metadata)
    max_entropy = np.log2(n_candidates) if n_candidates > 1 else 1.0

    scores: list[tuple[str, float]] = []
    for attr in eligible_attrs:
        values = [
            str(c.get(attr, "")) for c in candidates_metadata if c.get(attr) not in (None, "")
        ]
        if len(values) < 2:
            continue
        # Entropie de Shannon sur la distribution des valeurs
        value_counts = Counter(values)
        total = sum(value_counts.values())
        entropy = -sum((n / total) * np.log2(n / total) for n in value_counts.values() if n > 0)
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0
        scores.append((attr, normalized))

    return sorted(scores, key=lambda x: -x[1])


def select_next_observation(
    candidates_metadata: list[dict],
    already_asked_attributes: set[str] | None = None,
) -> ObservationRequest | None:
    """Sélectionne la prochaine observation à demander à l'utilisateur.

    Picks l'attribut le plus discriminant qui n'a pas encore été demandé,
    puis le mappe à un type d'observation via `ATTRIBUTE_OBSERVATION_MAP`.

    Args:
        candidates_metadata: top-K candidats avec leur metadata.
        already_asked_attributes: attributs déjà observés dans la session.

    Returns:
        ObservationRequest ou None si plus rien à demander (épuisement →
        mode dégradé "produit non identifié").
    """
    already_asked_attributes = already_asked_attributes or set()
    discriminants = compute_discriminative_attributes(candidates_metadata)

    for attr, score in discriminants:
        if attr in already_asked_attributes or score < 0.1:
            continue
        # Cherche un mapping exact, puis un mapping par préfixe (storage_capacity → storage)
        obs = ATTRIBUTE_OBSERVATION_MAP.get(attr)
        if obs is None:
            for key in ATTRIBUTE_OBSERVATION_MAP:
                if attr.startswith(key) or key in attr:
                    obs = ATTRIBUTE_OBSERVATION_MAP[key]
                    break
        if obs is None:
            obs = DEFAULT_OBSERVATION

        return ObservationRequest(
            attribute=attr,
            observation_type=obs["type"],
            instruction=obs["instruction"],
            candidates_count=len(candidates_metadata),
            discriminative_score=round(score, 4),
        )

    return None


def main() -> None:
    """Démo / mesure : combien de queries val seraient déclenchées par
    Akinator (gap top1-top2 < seuil), et quels attributs sont les plus
    discriminants en pratique."""
    log.info("=== Cycle 4.3 - Akinator backend (mesure déclenchement sur val) ===")
    REPORTS_RETRIEVAL.mkdir(parents=True, exist_ok=True)

    text_index_path = DATA_INDEX / "text_arctic_hnsw.index"
    if not text_index_path.exists():
        log.error("text_arctic_hnsw.index introuvable. Lance Cycle 4.1 d'abord.")
        return

    import faiss

    log.info("Lecture index + val embeddings…")
    index = faiss.read_index(str(text_index_path))
    val_emb = np.load(DATA_EMBEDDINGS / "text" / "text_arctic_val.npy").astype(np.float32)
    train_meta_cols = ["title", "store", "main_category", "_source_category", "price_band"]
    train_meta = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet",
        columns=train_meta_cols,
    )

    rng = np.random.default_rng(SEED)
    n_queries = min(EVAL_N_QUERIES, val_emb.shape[0])
    query_idx = rng.choice(val_emb.shape[0], size=n_queries, replace=False)
    queries = val_emb[query_idx]
    log.info("Sample %d queries", n_queries)

    log.info("Search top-%d…", TOP_K_AMBIG)
    distances, indices = index.search(queries, TOP_K_AMBIG)
    gaps = distances[:, 0] - distances[:, 1]

    n_ambiguous = int((gaps < AMBIGUITY_GAP_THRESHOLD).sum())
    log.info(
        "Queries ambiguës (gap top1-top2 < %.3f) : %d / %d (%.1f %%)",
        AMBIGUITY_GAP_THRESHOLD,
        n_ambiguous,
        n_queries,
        100 * n_ambiguous / n_queries,
    )

    # Pour les queries ambiguës : quel attribut est le plus souvent discriminant ?
    log.info("Calcul attributs discriminants sur les queries ambiguës…")
    attribute_top_picks: Counter[str] = Counter()
    observation_top_picks: Counter[str] = Counter()
    n_observations_proposable = 0

    for q in range(n_queries):
        if gaps[q] >= AMBIGUITY_GAP_THRESHOLD:
            continue
        # Récupère les K candidats et leurs metadata
        cand_indices = indices[q]
        cand_meta = [train_meta.row(int(i), named=True) for i in cand_indices]
        obs = select_next_observation(cand_meta)
        if obs is None:
            continue
        attribute_top_picks[obs.attribute] += 1
        observation_top_picks[obs.observation_type] += 1
        n_observations_proposable += 1

    log.info(
        "  %d / %d queries ambiguës ont au moins 1 observation proposable",
        n_observations_proposable,
        n_ambiguous,
    )
    log.info("  Top attributs discriminants : %s", attribute_top_picks.most_common(5))
    log.info("  Top observations demandées : %s", observation_top_picks.most_common(5))

    full = {
        "n_queries_eval": n_queries,
        "ambiguity_gap_threshold": AMBIGUITY_GAP_THRESHOLD,
        "n_ambiguous": n_ambiguous,
        "ambiguous_rate": round(n_ambiguous / n_queries, 4),
        "n_observations_proposable": n_observations_proposable,
        "top_discriminative_attributes": dict(attribute_top_picks.most_common(10)),
        "top_observation_types": dict(observation_top_picks.most_common(10)),
        "observation_map_keys": list(ATTRIBUTE_OBSERVATION_MAP.keys()),
    }
    OUT_JSON.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_JSON.name)
    log.info("Cycle 4.3 Akinator backend OK.")


if __name__ == "__main__":
    main()

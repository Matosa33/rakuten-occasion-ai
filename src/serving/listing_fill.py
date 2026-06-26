"""Assemblage de fiche robuste en cas de « catalog-miss » (Cycle 33.8, D-041).

Quand le produit n'est PAS (ou mal) présent au catalogue, on **ne s'ancre pas sur un mauvais
voisin** : on remplit les champs structurés de la fiche depuis les **faits observés sur la photo**
(extraction VLM) + la **catégorie votée** + la **métadonnée vendeur**. Chaque champ porte sa
**provenance**, et on mesure la **complétude**. Anti-hallucination préservé : aucune valeur non
vérifiée n'est affirmée — les valeurs « typiques » imputées des voisins sont marquées *à vérifier*.

Cascade de complétude (même esprit que le pricing L1-L4) :
- **N1_catalog**        : match catalogue fiable → specs du produit réel.
- **N2_category_photo** : pas de match fiable mais catégorie sûre → photo + schéma catégorie + métadonnée.
- **N3_observed**       : catégorie incertaine → observé seul + champs à compléter par le vendeur.

Module **pur** (aucune I/O) → testable sans modèle ni réseau. Le caller (API `/describe`) fournit
les attributs extraits par le VLM, la catégorie votée et le meilleur candidat.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Provenances possibles d'un champ (affichables tel quel sur la fiche).
SRC_OBSERVED = "observé"  # lu sur la photo (VLM) — le plus fiable pour CET objet
SRC_CATALOG = "catalogue"  # spec du produit catalogue matché (fiable si match correct)
SRC_TYPICAL = "typique-à-vérifier"  # imputé des voisins, NON affirmé
SRC_CATEGORY = "catégorie"  # déduit de la catégorie votée
SRC_SELLER = "vendeur"  # saisi/choisi par le vendeur

# Seuil de match fiable — aligné sur IDENTIFIED_THRESHOLD du pipeline (0.60).
RELIABLE_MATCH_THRESHOLD = 0.60

FIELD_LABELS = {
    "brand": "Marque",
    "color": "Couleur",
    "capacity": "Capacité",
    "model": "Modèle",
    "size": "Taille",
    "storage": "Stockage",
    "material": "Matière",
    "voltage": "Tension",
    "power": "Puissance",
    "feature": "Caractéristiques",
    "form_factor": "Format",
    "model_variant": "Variante",
    "connectivity": "Connectivité",
    "compatible_with": "Compatible avec",
    "screen_type": "Type d'écran",
}

# Au-delà des facettes du schéma, on affiche aussi les attributs RICHES observés/catalogue (le
# vendeur veut une fiche complète) — valeurs longues tronquées pour éviter le bruit (listes Amazon).
_MAX_FACET_VALUE = 80


@dataclass
class ListingField:
    name: str
    value: str
    source: str


@dataclass
class AssembledListing:
    level: str  # N1_catalog | N2_category_photo | N3_observed
    fields: list[ListingField] = field(default_factory=list)
    completeness: float = 0.0  # part des champs attendus qui sont remplis
    missing: list[str] = field(default_factory=list)  # champs attendus non remplis


def _label(key: str) -> str:
    return FIELD_LABELS.get(key, key.replace("_", " ").capitalize())


def assemble_listing(
    *,
    category_leaf: str,
    category_confidence: float,
    condition_label: str,
    photo_attributes: dict[str, str] | None = None,
    seller_metadata: str = "",
    match_brand: str = "",
    match_attributes: dict[str, str] | None = None,
    match_reliable: bool = False,
    expected_facets: list[str] | None = None,
) -> AssembledListing:
    """Assemble les champs structurés de la fiche avec provenance + complétude.

    Args:
        category_leaf: catégorie fine votée (« Smartwatches »…).
        category_confidence: confiance du vote (part).
        condition_label: état choisi par le vendeur (« Bon état »).
        photo_attributes: attributs lus sur la photo par le VLM (brand, color, capacity…).
        seller_metadata: texte vendeur (titre) — repli pour le titre.
        match_brand / match_attributes: marque + facettes du meilleur candidat catalogue.
        match_reliable: True si le candidat est jugé fiable (score ≥ seuil).
        expected_facets: facettes attendues pour cette catégorie (dénominateur de complétude).
            Défaut : l'union des clés observées + candidat.

    Returns:
        AssembledListing (niveau de la cascade, champs sourcés, complétude, manquants).
    """
    photo = {k: v for k, v in (photo_attributes or {}).items() if v}
    match_attrs = {k: v for k, v in (match_attributes or {}).items() if v}

    # Niveau de la cascade.
    if match_reliable:
        level = "N1_catalog"
    elif category_leaf:
        level = "N2_category_photo"
    else:
        level = "N3_observed"

    def value_with_source(key: str) -> ListingField | None:
        """Priorité : observé (photo) > catalogue (si fiable) > typique (à vérifier)."""
        if key in photo:
            return ListingField(_label(key), photo[key], SRC_OBSERVED)
        if key in match_attrs:
            src = SRC_CATALOG if match_reliable else SRC_TYPICAL
            return ListingField(_label(key), match_attrs[key], src)
        return None

    fields: list[ListingField] = []

    # Type de produit = la catégorie votée.
    if category_leaf:
        fields.append(ListingField("Type de produit", category_leaf, SRC_CATEGORY))

    # État = choix vendeur.
    if condition_label:
        fields.append(ListingField("État", condition_label, SRC_SELLER))

    # Marque : photo > catalogue/typique.
    brand_f = value_with_source("brand")
    if brand_f is None and match_brand:
        brand_f = ListingField(
            "Marque", match_brand, SRC_CATALOG if match_reliable else SRC_TYPICAL
        )
    if brand_f:
        fields.append(brand_f)

    # Facettes attendues pour la catégorie (schéma) → remplies par photo/catalogue.
    facets = expected_facets or sorted(set(photo) | set(match_attrs))
    shown_keys = {"brand", "category"}
    for key in facets:
        if key in ("brand",):  # déjà traité
            continue
        shown_keys.add(key)
        f = value_with_source(key)
        if f:
            fields.append(f)

    # Attributs RICHES hors schéma (form_factor, feature, voltage…) : on génère TOUT le structuré
    # pertinent observé/catalogue (valeurs longues tronquées). Le vendeur dispose d'une fiche complète.
    for key in [*photo, *match_attrs]:
        if key in shown_keys or key == "category":
            continue
        shown_keys.add(key)
        f = value_with_source(key)
        if f:
            if len(f.value) > _MAX_FACET_VALUE:
                f.value = f.value[: _MAX_FACET_VALUE - 1].rstrip() + "…"
            fields.append(f)

    # Complétude = facettes du SCHÉMA remplies (Type + Marque + facettes attendues). L'« État » est
    # un choix vendeur (toujours disponible à l'affichage) → exclu du dénominateur (ne pénalise pas).
    expected_labels = ["Type de produit", "Marque"] + [_label(k) for k in facets if k != "brand"]
    filled_labels = {f.name for f in fields}
    missing = [lbl for lbl in expected_labels if lbl not in filled_labels]
    completeness = (
        (len(expected_labels) - len(missing)) / len(expected_labels) if expected_labels else 0.0
    )

    return AssembledListing(
        level=level,
        fields=fields,
        completeness=round(completeness, 4),
        missing=missing,
    )

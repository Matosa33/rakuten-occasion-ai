// Akinator text-only (D-019) : sélection de la facette la plus discriminante
// parmi les attributs des candidats, par entropie de Shannon normalisée.
// Objectif : minimiser les clics en maximisant la réduction du set à chaque étape
// (comme un arbre de décision / le jeu Akinator).

import type { CandidateMeta } from "./api";

// Libellés FR des facettes canoniques (clés venant du backend `attributes`).
export const FACET_LABELS: Record<string, string> = {
  brand: "Marque",
  category: "Type de produit",
  color: "Couleur",
  capacity: "Capacité",
  size: "Taille",
  material: "Matière",
  form_factor: "Format",
  style: "Style",
  feature: "Caractéristique",
  compatible_with: "Compatible avec",
};

/** Libellé FR d'une facette ; repli humanisé (`form_factor` → « Form factor ») au lieu de la clé brute. */
export function facetLabel(key: string): string {
  return FACET_LABELS[key] ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

// Priorité sémantique : le TYPE de produit (téléphone vs coque) est la
// désambiguation la plus utile pour le vendeur — bien plus que la marque.
// On pondère le score d'entropie pour que `category` passe en premier quand
// les types sont mixtes, sans écraser les autres facettes.
const FACET_PRIORITY: Record<string, number> = {
  category: 2.0,
  capacity: 1.2,
  size: 1.1,
};

export interface FacetChoice {
  key: string;
  label: string;
  options: string[]; // valeurs distinctes triées par fréquence décroissante
}

/** Entropie de Shannon normalisée [0,1] d'une distribution de valeurs. */
function normalizedEntropy(values: string[]): number {
  if (values.length < 2) return 0;
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  if (counts.size < 2) return 0; // une seule valeur = aucune discrimination
  const total = values.length;
  let h = 0;
  for (const n of counts.values()) {
    const p = n / total;
    h -= p * Math.log2(p);
  }
  const maxH = Math.log2(counts.size);
  return maxH > 0 ? h / maxH : 0;
}

/**
 * Choisit la facette la plus discriminante parmi les candidats visibles,
 * en excluant celles déjà demandées. Retourne null si aucune ne discrimine.
 */
export function bestDiscriminativeFacet(
  candidates: CandidateMeta[],
  excludeKeys: Set<string>
): FacetChoice | null {
  if (candidates.length < 2) return null;

  // Collecte toutes les clés d'attributs présentes
  const keys = new Set<string>();
  for (const c of candidates) for (const k of Object.keys(c.attributes ?? {})) keys.add(k);

  let best: FacetChoice | null = null;
  let bestScore = -1;
  for (const key of keys) {
    if (excludeKeys.has(key)) continue;
    const values = candidates
      .map((c) => c.attributes?.[key])
      .filter((v): v is string => !!v && v.trim() !== "");
    // Il faut au moins 2 candidats porteurs et 2 valeurs distinctes
    if (values.length < 2) continue;
    const distinct = [...new Set(values)];
    if (distinct.length < 2) continue;

    const entropy = normalizedEntropy(values);
    // Score : entropie × couverture × priorité sémantique (type produit > marque > détails)
    const coverage = values.length / candidates.length;
    const priority = FACET_PRIORITY[key] ?? 1.0;
    const score = entropy * coverage * priority;
    if (score > bestScore) {
      bestScore = score;
      // Options triées par fréquence décroissante
      const freq = new Map<string, number>();
      for (const v of values) freq.set(v, (freq.get(v) ?? 0) + 1);
      const options = [...freq.entries()].sort((a, b) => b[1] - a[1]).map(([v]) => v);
      best = { key, label: FACET_LABELS[key] ?? key, options };
    }
  }
  return best;
}

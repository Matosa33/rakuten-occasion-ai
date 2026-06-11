// Cycle 17.3 (D-035) — pré-qualification de l'état : les « bābā » d'une annonce
// parfaite. Checklist UNIVERSELLE + questions SPÉCIFIQUES par type de produit
// (mapping statique curé, décision humaine 2026-06-11).
//
// Les réponses : (1) guident le choix de l'état pricing, (2) sont injectées en
// bloc « État détaillé » dans la description de l'annonce (étape 3).

export type ProductKind = "phone" | "laptop" | "console" | "tool" | "camera" | "other";

export const PRODUCT_KINDS: { value: ProductKind; label: string }[] = [
  { value: "phone", label: "📱 Téléphone / tablette" },
  { value: "laptop", label: "💻 Ordinateur" },
  { value: "console", label: "🎮 Console / jeu" },
  { value: "tool", label: "🔧 Outil" },
  { value: "camera", label: "📷 Photo / audio / vidéo" },
  { value: "other", label: "📦 Autre" },
];

/** Vues de prise de photo conseillées par type (guidage D-035 décision 6). */
export const SHOT_GUIDES: Record<ProductKind, string[]> = {
  phone: ["Face avant allumée", "Dos (caméras visibles)", "Tranches / coins", "Écran de réglages (modèle + capacité)"],
  laptop: ["Ouvert allumé", "Fermé (capot)", "Clavier de près", "Étiquette dessous (modèle / série)"],
  console: ["Face avant", "Arrière (ports)", "Manettes / accessoires", "Étiquette (modèle)"],
  tool: ["Vue d'ensemble", "Plaque signalétique (modèle / puissance)", "Accessoires / coffret", "Zone d'usure"],
  camera: ["Face avant", "Dessus (molettes)", "Étiquette / numéro de série", "Accessoires inclus"],
  other: ["Vue d'ensemble", "Étiquette ou marquage visible", "Défauts éventuels de près"],
};

export interface ChecklistQuestion {
  key: string;
  label: string;
  options: string[]; // la 1ʳᵉ option = la plus favorable
}

/** Socle universel — vaut pour tout objet d'occasion. */
export const UNIVERSAL_CHECKLIST: ChecklistQuestion[] = [
  { key: "works", label: "Fonctionne parfaitement ?", options: ["Oui", "Non testé", "Non / panne"] },
  { key: "box", label: "Boîte d'origine ?", options: ["Oui", "Non"] },
  { key: "accessories", label: "Accessoires complets ?", options: ["Complets", "Partiels", "Aucun"] },
  { key: "invoice", label: "Facture / preuve d'achat ?", options: ["Oui", "Non"] },
];

/** Questions spécifiques par type (2 max — vitesse avant exhaustivité). */
export const KIND_CHECKLIST: Record<ProductKind, ChecklistQuestion[]> = {
  phone: [
    { key: "battery", label: "Santé batterie", options: ["Bonne (>85%)", "Moyenne", "Faible", "Inconnue"] },
    { key: "screen", label: "État écran", options: ["Parfait", "Micro-rayures", "Rayé / fêlé"] },
  ],
  laptop: [
    { key: "battery", label: "Autonomie batterie", options: ["Bonne", "Moyenne", "Faible", "Inconnue"] },
    { key: "keyboard", label: "Clavier / châssis", options: ["Parfait", "Traces d'usage", "Usé"] },
  ],
  console: [
    { key: "controllers", label: "Manettes incluses", options: ["Oui, complètes", "Partielles", "Aucune"] },
    { key: "storage", label: "Jeux / comptes effacés ?", options: ["Oui, réinitialisée", "À faire"] },
  ],
  tool: [
    { key: "usage", label: "Intensité d'usage", options: ["Léger", "Régulier", "Intensif"] },
    { key: "battery", label: "Batterie(s) incluse(s)", options: ["Oui", "Non", "Sans objet"] },
  ],
  camera: [
    { key: "lens", label: "Optique / objectif", options: ["Parfait", "Poussières", "Rayures"] },
    { key: "shutter", label: "Usure (déclenchements)", options: ["Faible", "Moyenne", "Élevée", "Inconnue"] },
  ],
  other: [],
};

const CHECKLIST_LABELS: Record<string, string> = Object.fromEntries(
  [...UNIVERSAL_CHECKLIST, ...Object.values(KIND_CHECKLIST).flat()].map((q) => [q.key, q.label])
);

/** Bloc « État détaillé » prêt à injecter dans la description de l'annonce. */
export function checklistToText(answers: Record<string, string>): string {
  const lines = Object.entries(answers)
    .filter(([, v]) => v)
    .map(([k, v]) => `- ${CHECKLIST_LABELS[k] ?? k} : ${v}`);
  return lines.length ? `\n\nÉtat détaillé :\n${lines.join("\n")}` : "";
}

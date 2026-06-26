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

/** Questions spécifiques par type (2 max — vitesse avant exhaustivité).
 * 17.4b : clés PRÉFIXÉES par le type — bug jugé par l'humain : la clé `battery`
 * partagée laptop/tool écrasait le label affiché (« Batterie(s) incluse(s) :
 * Bonne » au lieu d'« Autonomie batterie : Bonne »). */
export const KIND_CHECKLIST: Record<ProductKind, ChecklistQuestion[]> = {
  phone: [
    { key: "phone_battery", label: "Santé batterie", options: ["Bonne (>85%)", "Moyenne", "Faible", "Inconnue"] },
    { key: "phone_screen", label: "État écran", options: ["Parfait", "Micro-rayures", "Rayé / fêlé"] },
  ],
  laptop: [
    { key: "laptop_battery", label: "Autonomie batterie", options: ["Bonne", "Moyenne", "Faible", "Inconnue"] },
    { key: "laptop_keyboard", label: "Clavier / châssis", options: ["Parfait", "Traces d'usage", "Usé"] },
  ],
  console: [
    { key: "console_controllers", label: "Manettes incluses", options: ["Oui, complètes", "Partielles", "Aucune"] },
    { key: "console_reset", label: "Jeux / comptes effacés", options: ["Oui, réinitialisée", "À faire"] },
  ],
  tool: [
    { key: "tool_usage", label: "Intensité d'usage", options: ["Léger", "Régulier", "Intensif"] },
    { key: "tool_battery", label: "Batterie(s) incluse(s)", options: ["Oui", "Non", "Sans objet"] },
  ],
  camera: [
    { key: "camera_lens", label: "Optique / objectif", options: ["Parfait", "Poussières", "Rayures"] },
    { key: "camera_shutter", label: "Usure (déclenchements)", options: ["Faible", "Moyenne", "Élevée", "Inconnue"] },
  ],
  other: [],
};

// Labels SANS la ponctuation de question (17.4b : « Fonctionne parfaitement ? : Oui »
// devenait illisible dans l'annonce — on strip le « ? » à l'affichage).
const CHECKLIST_LABELS: Record<string, string> = Object.fromEntries(
  [...UNIVERSAL_CHECKLIST, ...Object.values(KIND_CHECKLIST).flat()].map((q) => [
    q.key,
    q.label.replace(/\s*\?$/, ""),
  ])
);

/** Lignes « État détaillé » structurées (label propre → valeur). */
export function checklistEntries(answers: Record<string, string>): [string, string][] {
  return Object.entries(answers)
    .filter(([, v]) => v)
    .map(([k, v]) => [CHECKLIST_LABELS[k] ?? k, v]);
}

/** Bloc texte prêt à injecter dans la description de l'annonce. */
export function checklistToText(answers: Record<string, string>): string {
  const lines = checklistEntries(answers).map(([label, v]) => `- ${label} : ${v}`);
  return lines.length ? `\n\nÉtat détaillé :\n${lines.join("\n")}` : "";
}

/** Cycle 36 : dérive le type d'objet de la catégorie IDENTIFIÉE (plus de choix manuel vendeur).
 * Sert à afficher les questions d'état SPÉCIFIQUES au bon moment (après l'identification).
 * `fine` (catégorie fine votée) prime ; repli sur la macro-catégorie. null = pas de type dédié
 * (ex. carte graphique, audio) → seules les questions universelles s'appliquent. */
export function kindFromCategory(macro: string, fine: string): ProductKind | null {
  const f = (fine || "").toLowerCase();
  if (/laptop|notebook/.test(f)) return "laptop";
  if (/camera|dslr|mirrorless|camcorder/.test(f)) return "camera";
  if (/phone|tablet|smartphone/.test(f)) return "phone";
  if (/console/.test(f)) return "console";
  switch (macro) {
    case "Cell_Phones_and_Accessories":
      return "phone";
    case "Video_Games":
      return "console";
    case "Tools_and_Home_Improvement":
      return "tool";
    default:
      return null; // Electronics non spécifique (GPU, audio…) → universel seulement
  }
}

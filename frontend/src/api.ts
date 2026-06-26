// Cycle 10 — Client API typé pour le backend FastAPI (Cycle 9).
// En dev, les appels passent par le proxy Vite /api → http://localhost:8000.
// Cycle 15 (D-032) : tous les endpoints métier exigent un Bearer JWT —
// injecté ici, point unique de passage de tous les appels.

import { clearToken, getToken } from "./auth";

const BASE = "/api";
// Timeout réseau : /identify fait de l'extraction VLM (peut être lent), mais au-delà l'utilisateur
// ne doit pas rester sur une appli figée → message actionnable.
const REQUEST_TIMEOUT_MS = 60_000;

function _netError(e: unknown): Error {
  if (e instanceof DOMException && e.name === "TimeoutError")
    return new Error("Le serveur met trop de temps à répondre — réessayez ou saisissez le produit en texte.");
  return new Error("Réseau indisponible — vérifiez votre connexion puis réessayez.");
}

export type Condition = "neuf" | "tres_bon_etat" | "bon_etat" | "correct" | "pour_pieces";
export type Category =
  | "Electronics"
  | "Cell_Phones_and_Accessories"
  | "Video_Games"
  | "Tools_and_Home_Improvement";

export interface CandidateMeta {
  parent_asin: string;
  title: string;
  brand: string;
  category: Category;
  image_url: string;
  images: string[]; // toutes les vues catalogue (visionneuse 17.2/17.4)
  score: number;
  price: number | null;
  category_fine: string;
  category_path: string; // breadcrumb complet « A > B > C » (rangement marketplace, 17.4b)
  attributes: Record<string, string>;
}

export interface VLMValidation {
  match: boolean;
  confidence: number;
  reason: string;
}

export interface UploadResponse {
  image_id: string;
  url: string;
}

export interface ObservationToRequest {
  attribute: string;
  observation_type: string;
  instruction: string;
  discriminative_score: number;
}

// Fiche structurée à facettes explicites + provenance (rangement marketplace, D-041).
export interface ListingField {
  name: string; // libellé FR (« Marque », « Capacité »…)
  value: string;
  source: string; // observé | catalogue | typique-à-vérifier | catégorie | vendeur
}

export interface AssembledListing {
  level: string; // N1_catalog | N2_category_photo | N3_observed
  fields: ListingField[];
  completeness: number; // part des facettes attendues qui sont remplies
  missing: string[];
}

export interface ReasonedFacet {
  key: string;
  value: string;
  source: string; // 'observed' | 'analogy' | index de fiche
}

// Jugement LLM sur le top-15 (Cycle 36) : famille + ancre prix neuf + question discriminante.
export interface ReasonedIdentification {
  product_family: string;
  family_confidence: number;
  chosen_parent_asin: string;
  catalog_miss: boolean;
  reference_new_price_usd: number | null;
  reference_new_confidence: number;
  ask_question: boolean;
  facet_question: string;
  facets: ReasonedFacet[];
}

export interface IdentifyResponse {
  status: "identified" | "to_confirm" | "uncertain";
  top_candidates: CandidateMeta[];
  vlm_validation: VLMValidation | null;
  next_observation: ObservationToRequest | null;
  explanation: string;
  // Catégorie fine VOTÉE (vote pondéré des voisins) + confiance + breadcrumb — la classification
  // finale robuste, à afficher (plus fiable que la catégorie du seul candidat choisi).
  predicted_category_fine: string;
  predicted_category_confidence: number;
  predicted_category_path: string;
  // Fiche structurée du top-1 : facettes explicites + provenance + complétude (D-041).
  informations_cles: AssembledListing | null;
  // Jugement LLM sur le top-15 (Cycle 36) : null si la passe raisonnée est indisponible.
  reasoned: ReasonedIdentification | null;
}

export interface PriceResponse {
  suggested_price_eur: number;
  confidence_level: "L1" | "L1.5" | "L2" | "L3" | "L4";
  confidence_score: number;
  range_low: number;
  range_high: number;
  explanation: string;
  method: string;
}

export interface DescribeResponse {
  title: string;
  description: string;
  grounding_sentences_count: number;
  grounding_sentences_preview: string[];
  parse_ok: boolean;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (e) {
    throw _netError(e);
  }
  if (res.status === 401) {
    // Token absent/expiré/invalide → purge → App re-render vers LoginPage.
    clearToken();
    throw new Error("Session expirée — reconnectez-vous.");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof detail.detail === "string" ? detail.detail : `Erreur ${res.status}`
    );
  }
  return res.json() as Promise<T>;
}

/** Upload d'une photo vendeur (≥ 1 obligatoire, D-035). Bearer requis. */
export async function uploadPhoto(file: File): Promise<UploadResponse> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${BASE}/upload`, {
      method: "POST",
      headers,
      body: form,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (e) {
    throw _netError(e);
  }
  if (res.status === 401) {
    clearToken();
    throw new Error("Session expirée — reconnectez-vous.");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof detail.detail === "string" ? detail.detail : `Erreur ${res.status}`
    );
  }
  return res.json() as Promise<UploadResponse>;
}

export function identify(
  imageIds: string[],
  textHint: string,
  alreadyObserved: Record<string, string> = {}
) {
  return postJson<IdentifyResponse>("/identify", {
    image_ids: imageIds,
    text_hint: textHint,
    already_observed: alreadyObserved,
  });
}

export function priceProduct(
  category: Category,
  condition: Condition,
  opts: {
    parentAsin?: string;
    catalogPrice?: number | null;
    neighborPrices?: number[];
    ageYears?: number;
    // Cycle 36 : ancre prix neuf estimée par IA (issue de /identify.reasoned) → niveau L1.5.
    referenceNewPriceUsd?: number | null;
    referenceNewConfidence?: number;
  } = {}
) {
  return postJson<PriceResponse>("/price", {
    parent_asin: opts.parentAsin ?? null,
    category,
    condition,
    age_years: opts.ageYears ?? 2,
    catalog_price: opts.catalogPrice ?? null,
    neighbor_prices: opts.neighborPrices ?? [],
    reference_new_price_usd: opts.referenceNewPriceUsd ?? null,
    reference_new_confidence: opts.referenceNewConfidence ?? 0,
  });
}

export function describe(parentAsin: string, condition: Condition) {
  return postJson<DescribeResponse>("/describe", {
    parent_asin: parentAsin,
    condition,
  });
}

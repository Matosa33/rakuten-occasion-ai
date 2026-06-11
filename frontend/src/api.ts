// Cycle 10 — Client API typé pour le backend FastAPI (Cycle 9).
// En dev, les appels passent par le proxy Vite /api → http://localhost:8000.
// Cycle 15 (D-032) : tous les endpoints métier exigent un Bearer JWT —
// injecté ici, point unique de passage de tous les appels.

import { clearToken, getToken } from "./auth";

const BASE = "/api";

export type Condition = "neuf" | "tres_bon_etat" | "bon_etat" | "correct";
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

export interface IdentifyResponse {
  status: "identified" | "to_confirm" | "uncertain";
  top_candidates: CandidateMeta[];
  vlm_validation: VLMValidation | null;
  next_observation: ObservationToRequest | null;
  explanation: string;
}

export interface PriceResponse {
  suggested_price_eur: number;
  confidence_level: "L1" | "L2" | "L3" | "L4";
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
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
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
  const res = await fetch(`${BASE}/upload`, { method: "POST", headers, body: form });
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
  } = {}
) {
  return postJson<PriceResponse>("/price", {
    parent_asin: opts.parentAsin ?? null,
    category,
    condition,
    age_years: opts.ageYears ?? 2,
    catalog_price: opts.catalogPrice ?? null,
    neighbor_prices: opts.neighborPrices ?? [],
  });
}

export function describe(parentAsin: string, condition: Condition) {
  return postJson<DescribeResponse>("/describe", {
    parent_asin: parentAsin,
    condition,
  });
}

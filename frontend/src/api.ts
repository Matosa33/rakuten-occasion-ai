// Cycle 10 — Client API typé pour le backend FastAPI (Cycle 9).
// En dev, les appels passent par le proxy Vite /api → http://localhost:8000.

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
  score: number;
  price: number | null;
  category_fine: string;
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
  vlm_validation: unknown | null;
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
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `Erreur ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function identify(textHint: string, alreadyObserved: Record<string, string> = {}) {
  return postJson<IdentifyResponse>("/identify", {
    image_url: "",
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

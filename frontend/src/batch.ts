// Cycle 17.5 (D-035, lève D-016) — mode « mitrailler » déménagement :
// l'utilisateur photographie N objets À LA CHAÎNE sans attendre ; les
// identifications tournent en arrière-plan ; un tableau de bord liste les
// annonces à valider / prêtes. La queue survit au refresh (localStorage —
// les photos, elles, sont déjà sur le serveur via /upload).

import {
  describe,
  identify,
  priceProduct,
  type Category,
  type Condition,
  type DescribeResponse,
  type IdentifyResponse,
  type PriceResponse,
} from "./api";
import type { UploadedPhoto } from "./components/PhotoUploader";

export type BatchStatus =
  | "queued" // photos prises, en attente d'analyse
  | "identifying" // VLM + retrieval en cours
  | "choose" // candidats reçus → l'humain doit choisir
  | "generating" // prix + annonce en cours
  | "ready" // annonce complète
  | "error";

export interface BatchItem {
  id: string;
  createdAt: number;
  photos: UploadedPhoto[];
  textHint: string;
  condition: Condition;
  status: BatchStatus;
  error?: string;
  ident?: IdentifyResponse;
  chosenAsin?: string;
  chosenCategory?: Category;
  price?: PriceResponse;
  listing?: DescribeResponse;
}

const STORAGE_KEY = "rakuten_batch_v1";

export function newItem(photos: UploadedPhoto[], textHint: string, condition: Condition): BatchItem {
  return {
    id: crypto.randomUUID(),
    createdAt: Date.now(),
    photos,
    textHint,
    condition,
    status: "queued",
  };
}

export function loadQueue(): BatchItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const items = JSON.parse(raw) as BatchItem[];
    // Un item interrompu en plein vol au refresh redevient actionnable.
    return items.map((it) =>
      it.status === "identifying"
        ? { ...it, status: "queued" }
        : it.status === "generating"
          ? { ...it, status: "choose" }
          : it
    );
  } catch {
    return [];
  }
}

export function saveQueue(items: BatchItem[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

/** Lance l'identification d'un item (VLM + retrieval). */
export async function identifyItem(item: BatchItem): Promise<BatchItem> {
  try {
    const ident = await identify(
      item.photos.map((p) => p.imageId),
      item.textHint
    );
    return { ...item, status: "choose", ident, error: undefined };
  } catch (e) {
    return {
      ...item,
      status: "error",
      error: e instanceof Error ? e.message : "Erreur d'analyse",
    };
  }
}

/** Après choix du candidat : prix + annonce (même logique que le flow unitaire). */
export async function finalizeItem(
  item: BatchItem,
  asin: string,
  category: Category
): Promise<BatchItem> {
  const chosen = item.ident?.top_candidates.find((c) => c.parent_asin === asin);
  const sameType = (c: { category_fine: string; category: Category }) =>
    chosen ? (c.category_fine || c.category) === (chosen.category_fine || chosen.category) : true;
  const neighborPrices = (item.ident?.top_candidates ?? [])
    .filter(sameType)
    .map((c) => c.price)
    .filter((p): p is number => p != null && p > 0);
  try {
    const [price, listing] = await Promise.all([
      priceProduct(category, item.condition, {
        parentAsin: asin,
        catalogPrice: chosen?.price ?? null,
        neighborPrices,
      }),
      describe(asin, item.condition),
    ]);
    return {
      ...item,
      status: "ready",
      chosenAsin: asin,
      chosenCategory: category,
      price,
      listing,
      error: undefined,
    };
  } catch (e) {
    return {
      ...item,
      status: "choose",
      error: e instanceof Error ? e.message : "Erreur de génération",
    };
  }
}

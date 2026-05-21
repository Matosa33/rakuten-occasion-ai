import type { PriceResponse } from "../api";

// Anchoring : on affiche le prix conseillé en grand (ancre), avec la fourchette
// autour. Le niveau de confiance est explicite (transparence M8).
const CONFIDENCE_LABEL: Record<PriceResponse["confidence_level"], string> = {
  L1: "Confiance élevée (prix catalogue)",
  L2: "Confiance moyenne (produits similaires)",
  L3: "Estimation par catégorie",
  L4: "Saisie manuelle conseillée",
};

export function PriceCard({ price }: { price: PriceResponse }) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm">
      <p className="text-sm font-medium text-slate-500">Prix conseillé</p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-4xl font-bold text-rose-700">
          {price.suggested_price_eur.toFixed(2)} €
        </span>
        {price.range_high > 0 && (
          <span className="text-sm text-slate-400">
            ({price.range_low.toFixed(0)}–{price.range_high.toFixed(0)} €)
          </span>
        )}
      </div>
      <div className="mt-3 flex items-center gap-2">
        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
          {CONFIDENCE_LABEL[price.confidence_level]}
        </span>
        <span className="text-xs text-slate-400">
          {(price.confidence_score * 100).toFixed(0)}%
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-500">{price.explanation}</p>
    </div>
  );
}

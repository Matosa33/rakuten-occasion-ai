import { useMemo, useState } from "react";
import type { Category, IdentifyResponse } from "../api";
import { bestDiscriminativeFacet, FACET_LABELS } from "../facets";

// Hick's Law : top 3 mis en avant, liste complète déroulable (triée par similarité).
const TOP_HIGHLIGHT = 3;

const STATUS_LABEL: Record<IdentifyResponse["status"], { text: string; color: string }> = {
  identified: { text: "Produit identifié ✓", color: "text-emerald-600" },
  to_confirm: { text: "Est-ce l'un de ces produits ?", color: "text-amber-600" },
  uncertain: { text: "Correspondance incertaine", color: "text-rose-600" },
};

export function CandidatePicker({
  ident,
  loading,
  onChoose,
  onBack,
}: {
  ident: IdentifyResponse;
  loading: boolean;
  onChoose: (asin: string, category: Category) => void;
  onBack: () => void;
}) {
  const status = STATUS_LABEL[ident.status];
  // Akinator multi-étapes (D-019) : filtres appliqués {facette: valeur}.
  const [applied, setApplied] = useState<Record<string, string>>({});

  const visible = useMemo(
    () =>
      ident.top_candidates.filter((c) =>
        Object.entries(applied).every(([k, v]) => (c.attributes?.[k] ?? "") === v)
      ),
    [ident, applied]
  );

  // Facette la plus discriminante sur le set courant, hors facettes déjà choisies.
  const facet = useMemo(
    () => bestDiscriminativeFacet(visible, new Set(Object.keys(applied))),
    [visible, applied]
  );

  function pick(key: string, value: string) {
    setApplied((prev) => ({ ...prev, [key]: value }));
  }
  function removeFilter(key: string) {
    setApplied((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm">
      <p className={`text-sm font-semibold ${status.color}`}>{status.text}</p>
      <p className="mt-1 text-xs text-slate-500">{ident.explanation}</p>

      {/* Filtres déjà appliqués (retirables) */}
      {Object.keys(applied).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {Object.entries(applied).map(([k, v]) => (
            <button
              key={k}
              onClick={() => removeFilter(k)}
              className="rounded-full bg-rose-100 px-2.5 py-1 text-xs text-rose-700 hover:bg-rose-200"
              title="Retirer ce filtre"
            >
              {(FACET_LABELS[k] ?? k)}: {v} ✕
            </button>
          ))}
        </div>
      )}

      {/* Akinator : question sur la facette la plus discriminante (narrowing). */}
      {facet && visible.length > 1 && (
        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-medium text-amber-800">{facet.label} ?</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {facet.options.map((opt) => (
              <button
                key={opt}
                onClick={() => pick(facet.key, opt)}
                className="rounded-full bg-white px-2.5 py-1 text-xs text-amber-700 transition hover:bg-amber-100"
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Candidats TOUJOURS affichés (humain = validateur, R19). */}
      {visible.length > 0 ? (
        <ul className="mt-4 max-h-96 space-y-2 overflow-y-auto pr-1">
          {visible.map((c, idx) => (
            <li key={c.parent_asin}>
              <button
                disabled={loading}
                onClick={() => onChoose(c.parent_asin, c.category)}
                className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left transition hover:border-rose-300 hover:bg-rose-50 disabled:opacity-40 ${
                  idx < TOP_HIGHLIGHT ? "border-slate-200" : "border-slate-100"
                }`}
              >
                {c.image_url ? (
                  <img
                    src={c.image_url}
                    alt=""
                    loading="lazy"
                    onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                    className="h-12 w-12 shrink-0 rounded-lg border border-slate-100 object-contain"
                  />
                ) : (
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-300">
                    📦
                  </div>
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-800">
                    {c.title || "(sans titre)"}
                  </span>
                  <span className="text-xs text-slate-400">
                    {[c.brand, c.category_fine || c.category].filter(Boolean).join(" · ")}
                  </span>
                </span>
                <span className="ml-1 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                  {(c.score * 100).toFixed(0)}%
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-4 text-sm text-slate-600">
          Aucun candidat avec ces critères — retirez un filtre ou saisissez manuellement.
        </div>
      )}

      <button
        onClick={onBack}
        className="mt-4 text-sm text-slate-500 underline-offset-2 hover:underline"
      >
        ← Recommencer
      </button>
    </div>
  );
}

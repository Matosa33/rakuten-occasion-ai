import type { Category, IdentifyResponse } from "../api";

// Hick's Law : on met en avant le top 3 (les plus probables), mais on laisse
// dérouler la liste complète (triée par similarité) pour le vendeur exigeant.
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

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm">
      <p className={`text-sm font-semibold ${status.color}`}>{status.text}</p>
      <p className="mt-1 text-xs text-slate-500">{ident.explanation}</p>

      {ident.next_observation && (
        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <span className="font-medium">Pour préciser : </span>
          {ident.next_observation.instruction}
        </div>
      )}

      {/* Candidats TOUJOURS affichés (humain = validateur, R19) — même en incertain. */}
      {ident.top_candidates.length > 0 ? (
        <ul className="mt-4 max-h-96 space-y-2 overflow-y-auto pr-1">
          {ident.top_candidates.map((c, idx) => (
            <li key={c.parent_asin}>
              <button
                disabled={loading}
                onClick={() => onChoose(c.parent_asin, c.category)}
                className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left transition hover:border-rose-300 hover:bg-rose-50 disabled:opacity-40 ${
                  idx < TOP_HIGHLIGHT ? "border-slate-200" : "border-slate-100"
                }`}
              >
                {/* Vignette produit (URL CDN Amazon). Fallback : masquée si KO. */}
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
                  <span className="text-xs text-slate-400">{c.category_fine || c.category}</span>
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
          Aucun candidat — vous pouvez saisir l'annonce manuellement.
        </div>
      )}

      {ident.status === "uncertain" && ident.top_candidates.length > 0 && (
        <p className="mt-3 text-xs text-slate-400">
          Si aucun ne correspond, recommencez avec plus de détails (marque, modèle, capacité).
        </p>
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

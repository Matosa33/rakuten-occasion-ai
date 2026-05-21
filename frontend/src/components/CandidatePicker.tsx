import type { Category, IdentifyResponse } from "../api";

// Hick's Law : on limite l'affichage aux 3 meilleurs candidats pour ne pas
// noyer le vendeur sous les choix.
const MAX_CANDIDATES = 3;

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
        <ul className="mt-4 space-y-2">
          {ident.top_candidates.slice(0, MAX_CANDIDATES).map((c) => (
            <li key={c.parent_asin}>
              <button
                disabled={loading}
                onClick={() => onChoose(c.parent_asin, c.category)}
                className="flex w-full items-center justify-between rounded-xl border border-slate-200 p-3 text-left transition hover:border-rose-300 hover:bg-rose-50 disabled:opacity-40"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-slate-800">
                    {c.title || "(sans titre)"}
                  </span>
                  <span className="text-xs text-slate-400">{c.category}</span>
                </span>
                <span className="ml-3 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
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

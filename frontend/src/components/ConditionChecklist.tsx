// Cycle 17.3 (D-035) — checklist état rapide. 2-3 taps = les « bābā » d'une annonce parfaite.
// Cycle 36 : plus de « Type d'objet » MANUEL (le vendeur ne sait pas où ranger une carte
// graphique). Le type est dérivé de la catégorie IDENTIFIÉE → les questions spécifiques
// (`kind`, optionnel) s'affichent après l'identification ; ici on ne montre que l'universel.

import {
  KIND_CHECKLIST,
  SHOT_GUIDES,
  UNIVERSAL_CHECKLIST,
  type ChecklistQuestion,
  type ProductKind,
} from "../condition";

function QuestionChips({
  q,
  value,
  onPick,
}: {
  q: ChecklistQuestion;
  value: string | undefined;
  onPick: (key: string, value: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="w-44 shrink-0 text-xs text-slate-600">{q.label}</span>
      {q.options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onPick(q.key, value === opt ? "" : opt)}
          className={`rounded-full px-2.5 py-1 text-xs transition ${
            value === opt
              ? "bg-rose-600 text-white"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

export function ConditionChecklist({
  kind = null,
  answers,
  onAnswersChange,
}: {
  // `kind` (optionnel) = type DÉRIVÉ de la catégorie identifiée ; quand fourni, on ajoute
  // ses questions spécifiques. Plus de sélecteur manuel (Cycle 36).
  kind?: ProductKind | null;
  answers: Record<string, string>;
  onAnswersChange: (a: Record<string, string>) => void;
}) {
  function pick(key: string, value: string) {
    onAnswersChange({ ...answers, [key]: value });
  }

  return (
    <div className="mt-4 space-y-3">
      {/* Guidage prises de vue (D-035) — incitatif, pas bloquant */}
      {kind && (
        <div className="rounded-xl bg-sky-50 p-3 text-xs text-sky-800">
          <span className="font-medium">📸 Photos conseillées pour bien vendre :</span>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {SHOT_GUIDES[kind].map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Checklist état : universelle + spécifique au type */}
      <div>
        <span className="text-sm font-medium text-slate-700">
          État en 3 clics
          <span className="ml-1 font-normal text-slate-400">(enrichit votre annonce)</span>
        </span>
        <div className="mt-2 space-y-1.5">
          {UNIVERSAL_CHECKLIST.map((q) => (
            <QuestionChips key={q.key} q={q} value={answers[q.key]} onPick={pick} />
          ))}
          {kind &&
            KIND_CHECKLIST[kind].map((q) => (
              <QuestionChips key={q.key} q={q} value={answers[q.key]} onPick={pick} />
            ))}
        </div>
      </div>
    </div>
  );
}

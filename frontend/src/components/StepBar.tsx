import { motion } from "framer-motion";

// Zeigarnik effect : une barre de progression incite à compléter la tâche commencée.
const LABELS = ["Décrire", "Identifier", "Vendre"];

export function StepBar({ step, total }: { step: number; total: number }) {
  const pct = (step / total) * 100;
  return (
    <div>
      <div className="flex justify-between text-xs font-medium text-slate-500">
        {LABELS.map((label, i) => (
          <span key={label} className={i + 1 <= step ? "text-rose-600" : ""}>
            {label}
          </span>
        ))}
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200">
        <motion.div
          className="h-full bg-rose-500"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 20 }}
        />
      </div>
    </div>
  );
}

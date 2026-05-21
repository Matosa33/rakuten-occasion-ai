import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  type Category,
  type Condition,
  type DescribeResponse,
  type IdentifyResponse,
  type PriceResponse,
  describe,
  identify,
  priceProduct,
} from "./api";
import { StepBar } from "./components/StepBar";
import { CandidatePicker } from "./components/CandidatePicker";
import { PriceCard } from "./components/PriceCard";
import { ListingCard } from "./components/ListingCard";

const CONDITIONS: { value: Condition; label: string }[] = [
  { value: "neuf", label: "Neuf" },
  { value: "tres_bon_etat", label: "Très bon état" },
  { value: "bon_etat", label: "Bon état" },
  { value: "correct", label: "Correct" },
];

export default function App() {
  const [step, setStep] = useState(1);
  const [textHint, setTextHint] = useState("");
  const [condition, setCondition] = useState<Condition>("bon_etat");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ident, setIdent] = useState<IdentifyResponse | null>(null);
  const [chosenAsin, setChosenAsin] = useState<string | null>(null);
  const [chosenCategory, setChosenCategory] = useState<Category | null>(null);
  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [listing, setListing] = useState<DescribeResponse | null>(null);

  async function runIdentify() {
    if (!textHint.trim()) return;
    setLoading(true);
    setError(null);
    // Nettoie tout l'état aval d'une analyse précédente (évite de rester
    // "bloqué" sur le 1er résultat si on relance une identification).
    setIdent(null);
    setChosenAsin(null);
    setChosenCategory(null);
    setPrice(null);
    setListing(null);
    try {
      const res = await identify(textHint);
      setIdent(res);
      setStep(2);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function chooseCandidate(asin: string, category: Category) {
    setChosenAsin(asin);
    setChosenCategory(category);
    setLoading(true);
    setError(null);
    try {
      // Hick's Law : on enchaîne prix + description automatiquement (pas de choix superflu)
      const [p, l] = await Promise.all([
        priceProduct(category, condition),
        describe(asin, condition),
      ]);
      setPrice(p);
      setListing(l);
      setStep(3);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep(1);
    setTextHint("");
    setIdent(null);
    setChosenAsin(null);
    setChosenCategory(null);
    setPrice(null);
    setListing(null);
    setError(null);
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-rose-700">Vendez en un éclair ⚡</h1>
        <p className="mt-2 text-slate-600">
          Décrivez votre objet, l'IA l'identifie, fixe un prix juste et rédige l'annonce.
        </p>
      </header>

      <StepBar step={step} total={3} />

      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {error}
        </motion.div>
      )}

      <AnimatePresence mode="wait">
        {step === 1 && (
          <motion.section
            key="step1"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="mt-6 rounded-2xl bg-white p-6 shadow-sm"
          >
            <label className="block text-sm font-medium text-slate-700">
              Décrivez votre produit
            </label>
            <textarea
              value={textHint}
              onChange={(e) => setTextHint(e.target.value)}
              placeholder="Ex : iPhone 13 128 Go noir débloqué, très bon état"
              rows={3}
              className="mt-2 w-full resize-none rounded-xl border border-slate-300 p-3 text-slate-800 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
            />
            <div className="mt-4">
              <span className="text-sm font-medium text-slate-700">État de l'objet</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {CONDITIONS.map((c) => (
                  <button
                    key={c.value}
                    onClick={() => setCondition(c.value)}
                    className={`rounded-full px-4 py-1.5 text-sm transition ${
                      condition === c.value
                        ? "bg-rose-600 text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={runIdentify}
              disabled={loading || !textHint.trim()}
              className="mt-6 w-full rounded-xl bg-rose-600 py-3 font-semibold text-white transition hover:bg-rose-700 disabled:opacity-40"
            >
              {loading ? "Identification…" : "Identifier mon produit"}
            </button>
          </motion.section>
        )}

        {step === 2 && ident && (
          <motion.section
            key="step2"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="mt-6"
          >
            <CandidatePicker
              ident={ident}
              loading={loading}
              onChoose={chooseCandidate}
              onBack={reset}
            />
          </motion.section>
        )}

        {step === 3 && price && listing && (
          <motion.section
            key="step3"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="mt-6 space-y-4"
          >
            <PriceCard price={price} />
            <ListingCard
              key={chosenAsin ?? "listing"}
              listing={listing}
              initialCondition={condition}
            />
            <button
              onClick={reset}
              className="w-full rounded-xl border border-slate-300 py-2.5 text-slate-600 transition hover:bg-slate-50"
            >
              Vendre un autre objet
            </button>
          </motion.section>
        )}
      </AnimatePresence>

      <footer className="mt-10 text-center text-xs text-slate-400">
        Identification ancrée sur catalogue (RAG-grounded) — aucune invention. ASIN:{" "}
        {chosenAsin ?? "—"} · {chosenCategory ?? ""}
      </footer>
    </div>
  );
}

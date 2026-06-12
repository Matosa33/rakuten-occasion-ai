import { useState, useSyncExternalStore } from "react";
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
import { clearToken, getToken, subscribe } from "./auth";
import { checklistToText, type ProductKind } from "./condition";
import { StepBar } from "./components/StepBar";
import { CandidatePicker } from "./components/CandidatePicker";
import { ConditionChecklist } from "./components/ConditionChecklist";
import { MarketplaceListing } from "./components/MarketplaceListing";
import { PhotoUploader, type UploadedPhoto } from "./components/PhotoUploader";
import { LoginPage } from "./components/LoginPage";

const CONDITIONS: { value: Condition; label: string }[] = [
  { value: "neuf", label: "Neuf" },
  { value: "tres_bon_etat", label: "Très bon état" },
  { value: "bon_etat", label: "Bon état" },
  { value: "correct", label: "Correct" },
];

export default function App() {
  // Auth D-032 : store externe (localStorage) → re-render auto au login/logout/401.
  const token = useSyncExternalStore(subscribe, getToken);

  const [step, setStep] = useState(1);
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]); // ≥ 1 OBLIGATOIRE (D-035)
  const [kind, setKind] = useState<ProductKind | null>(null);
  const [checklist, setChecklist] = useState<Record<string, string>>({});
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
    if (photos.length === 0) return; // photo-first : la photo est la preuve
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
      const res = await identify(
        photos.map((p) => p.imageId),
        textHint
      );
      setIdent(res);
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  async function chooseCandidate(asin: string, category: Category) {
    setChosenAsin(asin);
    setChosenCategory(category);
    setLoading(true);
    setError(null);
    // Contexte prix (F4) : prix du produit choisi (L1) + prix des voisins (L2).
    // IMPORTANT : on filtre les voisins au MÊME type de produit que le choisi
    // (sinon les coques/accessoires pas chers polluent la médiane → prix absurde).
    const chosen = ident?.top_candidates.find((c) => c.parent_asin === asin);
    const sameType = (c: { category_fine: string; category: Category }) =>
      chosen ? (c.category_fine || c.category) === (chosen.category_fine || chosen.category) : true;
    const neighborPrices = (ident?.top_candidates ?? [])
      .filter(sameType)
      .map((c) => c.price)
      .filter((p): p is number => p != null && p > 0);
    try {
      // Hick's Law : on enchaîne prix + description automatiquement (pas de choix superflu)
      const [p, l] = await Promise.all([
        priceProduct(category, condition, {
          parentAsin: asin,
          catalogPrice: chosen?.price ?? null,
          neighborPrices,
        }),
        describe(asin, condition),
      ]);
      setPrice(p);
      // 17.3 (D-035) : la checklist état (les « bābā ») enrichit la description —
      // l'annonce finale porte l'état détaillé déclaré par le vendeur.
      setListing({ ...l, description: l.description + checklistToText(checklist) });
      setStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep(1);
    setPhotos([]);
    setKind(null);
    setChecklist({});
    setTextHint("");
    setIdent(null);
    setChosenAsin(null);
    setChosenCategory(null);
    setPrice(null);
    setListing(null);
    setError(null);
  }

  if (!token) {
    return <LoginPage />;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-rose-700">Vendez en un éclair ⚡</h1>
        <p className="mt-2 text-slate-600">
          Décrivez votre objet, l'IA l'identifie, fixe un prix juste et rédige l'annonce.
        </p>
        <button
          onClick={() => clearToken()}
          className="mt-2 text-xs text-slate-400 underline transition hover:text-slate-600"
        >
          Se déconnecter
        </button>
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
            {/* 17.3 (D-035) : la PHOTO d'abord — preuve acheteur + entrée du pipeline */}
            <PhotoUploader photos={photos} onChange={setPhotos} disabled={loading} />

            <ConditionChecklist
              kind={kind}
              onKindChange={setKind}
              answers={checklist}
              onAnswersChange={setChecklist}
            />

            <label className="mt-4 block text-sm font-medium text-slate-700">
              Précisions <span className="font-normal text-slate-400">(facultatif)</span>
            </label>
            <textarea
              value={textHint}
              onChange={(e) => setTextHint(e.target.value)}
              placeholder="Ex : modèle exact, capacité, défaut particulier…"
              rows={2}
              className="mt-2 w-full resize-none rounded-xl border border-slate-300 p-3 text-slate-800 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
            />
            <div className="mt-4">
              <span className="text-sm font-medium text-slate-700">État général</span>
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
              disabled={loading || photos.length === 0}
              className="mt-6 w-full rounded-xl bg-rose-600 py-3 font-semibold text-white transition hover:bg-rose-700 disabled:opacity-40"
            >
              {loading
                ? "Analyse de vos photos…"
                : photos.length === 0
                  ? "Ajoutez au moins une photo"
                  : "Identifier mon produit"}
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
            {/* 17.4b (D-035) : l'écran final EST l'annonce d'occasion —
                breadcrumb catégorie, photos vendeur, prix + badge état,
                caractéristiques structurées, description éditable. */}
            <MarketplaceListing
              key={chosenAsin ?? "listing"}
              photos={photos}
              chosen={ident?.top_candidates.find((c) => c.parent_asin === chosenAsin) ?? null}
              price={price}
              listing={listing}
              condition={condition}
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

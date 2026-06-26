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
import { checklistToText } from "./condition";
import { StepBar } from "./components/StepBar";
import { BatchMode } from "./components/BatchMode";
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
  { value: "pour_pieces", label: "Pour pièces / HS" },
];

const CURRENT_YEAR = new Date().getFullYear();

export default function App() {
  // Auth D-032 : store externe (localStorage) → re-render auto au login/logout/401.
  const token = useSyncExternalStore(subscribe, getToken);

  // Mode batch « mitrailler » (17.5, F5 déménagement, lève D-016).
  const [batchMode, setBatchMode] = useState(false);

  const [step, setStep] = useState(1);
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]); // ≥ 1 OBLIGATOIRE (D-035)
  const [checklist, setChecklist] = useState<Record<string, string>>({});
  const [textHint, setTextHint] = useState("");
  const [condition, setCondition] = useState<Condition>("bon_etat");
  const [purchaseYear, setPurchaseYear] = useState(""); // année d'achat (option) → âge → décote
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
      const top1 = res.top_candidates[0];
      // Plus de sélection forcée : si l'IA est SÛRE (status identified), on enchaîne directement
      // vers la fiche. Sinon (à confirmer / incertain), on montre les candidats. Dans les deux cas
      // le vendeur garde la main (« ce n'est pas le bon ? » sur la fiche).
      if (res.status === "identified" && top1) {
        await chooseCandidate(top1.parent_asin, top1.category, res);
      } else {
        setStep(2);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  async function chooseCandidate(
    asin: string,
    category: Category,
    identData: IdentifyResponse | null = ident
  ) {
    setChosenAsin(asin);
    setChosenCategory(category);
    setLoading(true);
    setError(null);
    // Contexte prix (F4) : prix du produit choisi (L1) + prix des voisins (L2).
    // IMPORTANT : on filtre les voisins au MÊME type de produit que le choisi
    // (sinon les coques/accessoires pas chers polluent la médiane → prix absurde).
    // `identData` passé explicitement lors de l'auto-confirmation (state pas encore commité).
    const cands = identData?.top_candidates ?? [];
    const chosen = cands.find((c) => c.parent_asin === asin);
    const sameType = (c: { category_fine: string; category: Category }) =>
      chosen ? (c.category_fine || c.category) === (chosen.category_fine || chosen.category) : true;
    const neighborPrices = cands
      .filter(sameType)
      .map((c) => c.price)
      .filter((p): p is number => p != null && p > 0);
    // Année d'achat (option) → âge → dépréciation pricing.
    const ageYears = purchaseYear
      ? Math.max(0, CURRENT_YEAR - parseInt(purchaseYear, 10))
      : undefined;
    // Cycle 36 : ancre prix neuf estimée par l'IA (passe raisonnée) → niveau L1.5, tue le 6 €/150 €.
    const reasoned = identData?.reasoned ?? null;
    try {
      // Hick's Law : on enchaîne prix + description automatiquement (pas de choix superflu)
      const [p, l] = await Promise.all([
        priceProduct(category, condition, {
          parentAsin: asin,
          catalogPrice: chosen?.price ?? null,
          neighborPrices,
          ageYears,
          referenceNewPriceUsd: reasoned?.reference_new_price_usd ?? null,
          referenceNewConfidence: reasoned?.reference_new_confidence ?? 0,
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
    setChecklist({});
    setTextHint("");
    setPurchaseYear("");
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

      {/* 17.5 (D-035) : bascule flow unitaire ↔ mode déménagement « mitrailler » */}
      <div className="mb-6 flex justify-center gap-1 rounded-full bg-slate-100 p-1">
        {[
          { value: false, label: "🎯 Un objet" },
          { value: true, label: "📦 Déménagement" },
        ].map((m) => (
          <button
            key={m.label}
            onClick={() => setBatchMode(m.value)}
            className={`flex-1 rounded-full px-4 py-1.5 text-sm font-medium transition ${
              batchMode === m.value
                ? "bg-white text-rose-700 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {batchMode ? (
        <BatchMode />
      ) : (
        <>
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

            <ConditionChecklist answers={checklist} onAnswersChange={setChecklist} />

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
            <div className="mt-4">
              <label className="block text-sm font-medium text-slate-700">
                Année d'achat{" "}
                <span className="font-normal text-slate-400">(facultatif — affine la décote)</span>
              </label>
              <input
                type="number"
                inputMode="numeric"
                min={1990}
                max={CURRENT_YEAR}
                value={purchaseYear}
                onChange={(e) => setPurchaseYear(e.target.value)}
                placeholder={`Ex : ${CURRENT_YEAR - 2}`}
                className="mt-2 w-36 rounded-xl border border-slate-300 p-2 text-slate-800 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
              />
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
              predicted={
                ident
                  ? {
                      fine: ident.predicted_category_fine,
                      confidence: ident.predicted_category_confidence,
                      path: ident.predicted_category_path,
                    }
                  : null
              }
              price={price}
              listing={listing}
              condition={condition}
              informationsCles={ident?.informations_cles ?? null}
              reasoned={ident?.reasoned ?? null}
            />
            {ident && ident.top_candidates.length > 1 && (
              <button
                onClick={() => setStep(2)}
                className="w-full rounded-xl border border-amber-300 bg-amber-50 py-2.5 text-amber-800 transition hover:bg-amber-100"
              >
                Ce n'est pas le bon produit ? Voir les autres résultats
              </button>
            )}
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
        </>
      )}
    </div>
  );
}

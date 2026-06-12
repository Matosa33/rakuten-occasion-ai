// Cycle 17.5 (D-035, lève D-016) — UI du mode « mitrailler » :
// capture à la chaîne (photos → Objet suivant → photos → …), analyses en
// arrière-plan (1 à la fois pour ménager le VLM), tableau de bord cliquable.

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { Category, Condition } from "../api";
import {
  finalizeItem,
  identifyItem,
  loadQueue,
  newItem,
  saveQueue,
  type BatchItem,
} from "../batch";
import { CandidatePicker } from "./CandidatePicker";
import { MarketplaceListing } from "./MarketplaceListing";
import { PhotoUploader, type UploadedPhoto } from "./PhotoUploader";

const CONDITIONS: { value: Condition; label: string }[] = [
  { value: "neuf", label: "Neuf" },
  { value: "tres_bon_etat", label: "Très bon état" },
  { value: "bon_etat", label: "Bon état" },
  { value: "correct", label: "Correct" },
];

const STATUS_UI: Record<BatchItem["status"], { label: string; cls: string }> = {
  queued: { label: "En file", cls: "bg-slate-100 text-slate-600" },
  identifying: { label: "Analyse…", cls: "bg-sky-100 text-sky-700 animate-pulse" },
  choose: { label: "À valider", cls: "bg-amber-100 text-amber-700" },
  generating: { label: "Annonce…", cls: "bg-sky-100 text-sky-700 animate-pulse" },
  ready: { label: "Prête ✓", cls: "bg-emerald-100 text-emerald-700" },
  error: { label: "Erreur", cls: "bg-rose-100 text-rose-700" },
};

export function BatchMode() {
  const [items, setItems] = useState<BatchItem[]>(() => loadQueue());
  const [openId, setOpenId] = useState<string | null>(null);

  // Capture de l'objet COURANT (pas encore en file).
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [textHint, setTextHint] = useState("");
  const [condition, setCondition] = useState<Condition>("bon_etat");

  const processing = useRef(false);

  useEffect(() => saveQueue(items), [items]);

  const patch = useCallback((id: string, updated: BatchItem) => {
    setItems((prev) => prev.map((it) => (it.id === id ? updated : it)));
  }, []);

  // Boucle de traitement en arrière-plan : 1 identification à la fois
  // (le mitraillage côté humain n'attend JAMAIS l'analyse).
  useEffect(() => {
    if (processing.current) return;
    const next = items.find((it) => it.status === "queued");
    if (!next) return;
    processing.current = true;
    patch(next.id, { ...next, status: "identifying" });
    identifyItem(next).then((done) => {
      patch(next.id, done);
      processing.current = false;
      // déclenche le useEffect suivant via le setItems de patch
    });
  }, [items, patch]);

  function addToQueue() {
    if (photos.length === 0) return;
    setItems((prev) => [...prev, newItem(photos, textHint, condition)]);
    // Reset express → objet suivant immédiatement (Zeigarnik du mitraillage).
    setPhotos([]);
    setTextHint("");
  }

  function removeItem(id: string) {
    setItems((prev) => prev.filter((it) => it.id !== id));
    if (openId === id) setOpenId(null);
  }

  async function choose(item: BatchItem, asin: string, category: Category) {
    patch(item.id, { ...item, status: "generating" });
    const done = await finalizeItem(item, asin, category);
    patch(item.id, done);
  }

  const open = items.find((it) => it.id === openId) ?? null;
  const readyCount = items.filter((it) => it.status === "ready").length;

  return (
    <div className="space-y-4">
      {/* Capture à la chaîne */}
      <section className="rounded-2xl bg-white p-5 shadow-sm">
        <p className="text-sm font-semibold text-slate-700">
          🔥 Mode déménagement — photographiez, ajoutez, passez au suivant
        </p>
        <div className="mt-3">
          <PhotoUploader photos={photos} onChange={setPhotos} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {CONDITIONS.map((c) => (
            <button
              key={c.value}
              onClick={() => setCondition(c.value)}
              className={`rounded-full px-3 py-1 text-xs transition ${
                condition === c.value
                  ? "bg-rose-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <input
          value={textHint}
          onChange={(e) => setTextHint(e.target.value)}
          placeholder="Précision (facultatif)"
          className="mt-3 w-full rounded-lg border border-slate-200 p-2 text-sm outline-none focus:border-rose-400"
        />
        <button
          onClick={addToQueue}
          disabled={photos.length === 0}
          className="mt-3 w-full rounded-xl bg-rose-600 py-2.5 font-semibold text-white transition hover:bg-rose-700 disabled:opacity-40"
        >
          ➕ Ajouter à la file et passer au suivant
        </button>
      </section>

      {/* Tableau de bord */}
      {items.length > 0 && (
        <section className="rounded-2xl bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-700">
              File ({items.length} objet{items.length > 1 ? "s" : ""})
            </p>
            <span className="text-xs text-slate-400">
              {readyCount} annonce{readyCount > 1 ? "s" : ""} prête{readyCount > 1 ? "s" : ""}
            </span>
          </div>
          <ul className="mt-3 space-y-2">
            {items.map((it) => (
              <li
                key={it.id}
                className="flex items-center gap-3 rounded-xl border border-slate-100 p-2"
              >
                {it.photos[0] ? (
                  <img
                    src={it.photos[0].url}
                    alt=""
                    className="h-11 w-11 shrink-0 rounded-lg object-cover"
                  />
                ) : (
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-slate-100">
                    📦
                  </div>
                )}
                <button
                  onClick={() => setOpenId(openId === it.id ? null : it.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-sm text-slate-700">
                    {it.listing?.title ||
                      it.ident?.top_candidates[0]?.title ||
                      it.textHint ||
                      `Objet (${it.photos.length} photo${it.photos.length > 1 ? "s" : ""})`}
                  </span>
                  {it.error && <span className="text-xs text-rose-500">{it.error}</span>}
                </button>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${STATUS_UI[it.status].cls}`}>
                  {STATUS_UI[it.status].label}
                </span>
                {it.status === "error" && (
                  <button
                    onClick={() => patch(it.id, { ...it, status: "queued", error: undefined })}
                    className="shrink-0 text-xs text-sky-600 underline-offset-2 hover:underline"
                  >
                    Réessayer
                  </button>
                )}
                <button
                  onClick={() => removeItem(it.id)}
                  aria-label="Retirer cet objet"
                  className="shrink-0 text-slate-300 hover:text-rose-500"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Drill-down : valider un objet (réutilise les composants du flow unitaire) */}
      <AnimatePresence>
        {open && open.status === "choose" && open.ident && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <CandidatePicker
              ident={open.ident}
              loading={false}
              onChoose={(asin, cat) => choose(open, asin, cat)}
              onBack={() => setOpenId(null)}
            />
          </motion.div>
        )}
        {open && open.status === "ready" && open.price && open.listing && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <MarketplaceListing
              photos={open.photos}
              chosen={
                open.ident?.top_candidates.find((c) => c.parent_asin === open.chosenAsin) ?? null
              }
              price={open.price}
              listing={open.listing}
              condition={open.condition}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

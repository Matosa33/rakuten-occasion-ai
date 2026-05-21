import { useEffect, useState } from "react";
import type { Condition, DescribeResponse } from "../api";

// IKEA effect : le vendeur peut éditer le titre/description générés. En
// s'appropriant le texte, il valorise davantage son annonce et la publie.
export function ListingCard({
  listing,
  initialCondition,
}: {
  listing: DescribeResponse;
  initialCondition: Condition;
}) {
  const [title, setTitle] = useState(listing.title);
  const [description, setDescription] = useState(listing.description);
  const [copied, setCopied] = useState(false);

  // Re-synchronise l'état local quand une NOUVELLE annonce arrive (sinon on
  // reste bloqué sur le 1er produit — bug derived-state-from-props).
  useEffect(() => {
    setTitle(listing.title);
    setDescription(listing.description);
  }, [listing]);

  async function copyAll() {
    await navigator.clipboard.writeText(`${title}\n\n${description}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm">
      <p className="text-sm font-medium text-slate-500">Votre annonce (modifiable)</p>

      <label className="mt-3 block text-xs font-medium text-slate-600">Titre</label>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-800 outline-none focus:border-rose-400"
      />

      <label className="mt-3 block text-xs font-medium text-slate-600">Description</label>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={6}
        className="mt-1 w-full resize-y rounded-lg border border-slate-300 p-2 text-sm text-slate-800 outline-none focus:border-rose-400"
      />

      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-slate-400">
          État : {initialCondition.replace(/_/g, " ")}
          {!listing.parse_ok && " · génération dégradée"}
        </span>
        <button
          onClick={copyAll}
          className="rounded-lg bg-slate-800 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-slate-900"
        >
          {copied ? "Copié ✓" : "Copier l'annonce"}
        </button>
      </div>
    </div>
  );
}

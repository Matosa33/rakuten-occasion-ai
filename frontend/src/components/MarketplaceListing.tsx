// Cycle 17.4b (D-035) — l'écran final est une VRAIE annonce d'occasion :
// breadcrumb catégorie (le rangement marketplace visible), photos vendeur en
// galerie, prix + badge état, tableau de caractéristiques structurées (la
// metadata parfaite), titre/description éditables (IKEA effect), copie enrichie.

import { useEffect, useMemo, useState } from "react";
import type { CandidateMeta, Condition, DescribeResponse, PriceResponse } from "../api";
import { FACET_LABELS } from "../facets";
import { PhotoLightbox } from "./PhotoLightbox";
import type { UploadedPhoto } from "./PhotoUploader";

const CONDITION_LABELS: Record<Condition, string> = {
  neuf: "Neuf",
  tres_bon_etat: "Très bon état",
  bon_etat: "Bon état",
  correct: "État correct",
};

const CONFIDENCE_LABEL: Record<PriceResponse["confidence_level"], string> = {
  L1: "Confiance élevée (prix catalogue)",
  L2: "Confiance moyenne (produits similaires)",
  L3: "Estimation par catégorie",
  L4: "Saisie manuelle conseillée",
};

export function MarketplaceListing({
  photos,
  chosen,
  price,
  listing,
  condition,
}: {
  photos: UploadedPhoto[];
  chosen: CandidateMeta | null;
  price: PriceResponse;
  listing: DescribeResponse;
  condition: Condition;
}) {
  const [title, setTitle] = useState(listing.title);
  const [description, setDescription] = useState(listing.description);
  const [mainPhoto, setMainPhoto] = useState(0);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);

  // Re-synchronise quand une NOUVELLE annonce arrive (anti derived-state bug).
  useEffect(() => {
    setTitle(listing.title);
    setDescription(listing.description);
    setMainPhoto(0);
  }, [listing]);

  // Caractéristiques structurées = la metadata marketplace parfaite :
  // marque + facettes catalogue du produit choisi (couleur, capacité, taille…).
  const specs = useMemo(() => {
    if (!chosen) return [] as [string, string][];
    const rows: [string, string][] = [];
    if (chosen.brand) rows.push(["Marque", chosen.brand]);
    for (const [k, v] of Object.entries(chosen.attributes ?? {})) {
      if (k === "brand" || k === "category") continue;
      rows.push([FACET_LABELS[k] ?? k, v]);
    }
    return rows;
  }, [chosen]);

  const breadcrumb = chosen?.category_path || chosen?.category_fine || "";
  const conditionLabel = CONDITION_LABELS[condition];

  async function copyAll() {
    const specsText = specs.map(([k, v]) => `${k} : ${v}`).join("\n");
    await navigator.clipboard.writeText(
      [
        title,
        "",
        `Prix : ${price.suggested_price_eur.toFixed(2)} € · ${conditionLabel}`,
        breadcrumb ? `Catégorie : ${breadcrumb}` : "",
        specsText ? `\nCaractéristiques :\n${specsText}` : "",
        "",
        description,
      ]
        .filter(Boolean)
        .join("\n")
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const photoUrls = photos.map((p) => p.url);

  return (
    <div className="overflow-hidden rounded-2xl bg-white shadow-sm">
      {/* Breadcrumb catégorie — la preuve du rangement marketplace parfait */}
      {breadcrumb && (
        <nav className="border-b border-slate-100 bg-slate-50 px-5 py-2 text-xs text-slate-500">
          {breadcrumb.split(" > ").map((part, i, arr) => (
            <span key={part + String(i)}>
              <span className={i === arr.length - 1 ? "font-medium text-slate-700" : ""}>
                {part}
              </span>
              {i < arr.length - 1 && <span className="mx-1 text-slate-300">›</span>}
            </span>
          ))}
        </nav>
      )}

      <div className="grid gap-5 p-5 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        {/* Galerie photos VENDEUR (la preuve acheteur) */}
        <div>
          {photos.length > 0 ? (
            <>
              <button
                type="button"
                onClick={() => setLightboxIndex(mainPhoto)}
                title="Agrandir"
                className="block w-full overflow-hidden rounded-xl border border-slate-200"
              >
                <img
                  src={photos[mainPhoto]?.url}
                  alt="Photo principale de l'annonce"
                  className="aspect-square w-full object-cover transition hover:scale-[1.02]"
                />
              </button>
              {photos.length > 1 && (
                <div className="mt-2 flex gap-1.5 overflow-x-auto">
                  {photos.map((p, i) => (
                    <button
                      key={p.imageId}
                      type="button"
                      onClick={() => setMainPhoto(i)}
                      className={`shrink-0 overflow-hidden rounded-lg border-2 ${
                        i === mainPhoto ? "border-rose-500" : "border-transparent"
                      }`}
                    >
                      <img src={p.url} alt="" className="h-14 w-14 object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="flex aspect-square items-center justify-center rounded-xl bg-slate-100 text-4xl text-slate-300">
              📦
            </div>
          )}
        </div>

        {/* Titre + prix + état + confiance */}
        <div className="flex flex-col">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            aria-label="Titre de l'annonce (modifiable)"
            className="w-full rounded-lg border border-transparent p-1.5 text-lg font-semibold text-slate-800 outline-none transition hover:border-slate-200 focus:border-rose-400"
          />

          <div className="mt-3 flex flex-wrap items-baseline gap-2">
            <span className="text-4xl font-bold text-rose-700">
              {price.suggested_price_eur.toFixed(2)} €
            </span>
            <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-medium text-white">
              {conditionLabel}
            </span>
          </div>
          {price.range_high > 0 && (
            <span className="mt-1 text-sm text-slate-400">
              Fourchette conseillée : {price.range_low.toFixed(0)}–{price.range_high.toFixed(0)} €
            </span>
          )}
          <div className="mt-2 flex items-center gap-2">
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
              {CONFIDENCE_LABEL[price.confidence_level]}
            </span>
            <span className="text-xs text-slate-400">
              {(price.confidence_score * 100).toFixed(0)}%
            </span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">{price.explanation}</p>

          {/* Caractéristiques structurées — la metadata parfaite */}
          {specs.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Caractéristiques
              </p>
              <dl className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-1.5">
                {specs.map(([k, v]) => (
                  <div key={k} className="flex flex-col">
                    <dt className="text-xs text-slate-400">{k}</dt>
                    <dd className="truncate text-sm text-slate-700" title={v}>
                      {v}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>

      {/* Description éditable (IKEA effect) */}
      <div className="border-t border-slate-100 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Description <span className="font-normal normal-case">(modifiable)</span>
        </p>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={9}
          className="mt-2 w-full resize-y rounded-lg border border-slate-200 p-3 text-sm leading-relaxed text-slate-800 outline-none focus:border-rose-400"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            {!listing.parse_ok && "Génération dégradée · "}
            {photos.length} photo(s) jointe(s)
          </span>
          <button
            onClick={copyAll}
            className="rounded-lg bg-slate-800 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-slate-900"
          >
            {copied ? "Copié ✓" : "Copier l'annonce"}
          </button>
        </div>
      </div>

      <PhotoLightbox
        images={photoUrls}
        index={lightboxIndex}
        onIndexChange={setLightboxIndex}
        onClose={() => setLightboxIndex(null)}
      />
    </div>
  );
}

// Cycle 17.4b (D-035) — l'écran final est une VRAIE annonce d'occasion :
// breadcrumb catégorie (le rangement marketplace visible), photos vendeur en
// galerie, prix + badge état, tableau de caractéristiques structurées (la
// metadata parfaite), titre/description éditables (IKEA effect), copie enrichie.

import { useEffect, useMemo, useState } from "react";
import type {
  AssembledListing,
  CandidateMeta,
  Condition,
  DescribeResponse,
  PriceResponse,
  ReasonedIdentification,
} from "../api";
import { facetLabel } from "../facets";
import { KIND_CHECKLIST, PRODUCT_KINDS, type ProductKind } from "../condition";

// Couleur du tag de provenance d'un champ (transparence du rangement).
const SOURCE_STYLE: Record<string, string> = {
  observé: "bg-emerald-50 text-emerald-700",
  catalogue: "bg-sky-50 text-sky-700",
  "typique-à-vérifier": "bg-amber-50 text-amber-700",
  catégorie: "bg-slate-100 text-slate-600",
  vendeur: "bg-violet-50 text-violet-700",
};
import { PhotoLightbox } from "./PhotoLightbox";
import type { UploadedPhoto } from "./PhotoUploader";

const CONDITION_LABELS: Record<Condition, string> = {
  neuf: "Neuf",
  tres_bon_etat: "Très bon état",
  bon_etat: "Bon état",
  correct: "État correct",
  pour_pieces: "Pour pièces / HS",
};

const CONFIDENCE_LABEL: Record<PriceResponse["confidence_level"], string> = {
  L1: "Confiance élevée (prix catalogue)",
  "L1.5": "Prix neuf estimé par IA",
  L2: "Confiance moyenne (produits similaires)",
  L3: "Estimation par catégorie",
  L4: "Saisie manuelle conseillée",
};

export function MarketplaceListing({
  photos,
  chosen,
  predicted,
  price,
  listing,
  condition,
  informationsCles,
  reasoned,
  kind,
  purchaseYear,
}: {
  photos: UploadedPhoto[];
  chosen: CandidateMeta | null;
  // Classification VOTÉE (vote pondéré des voisins) : la catégorisation finale robuste.
  predicted: { fine: string; confidence: number; path: string } | null;
  price: PriceResponse;
  listing: DescribeResponse;
  condition: Condition;
  // Fiche structurée du produit identifié : facettes + provenance + complétude (D-041).
  informationsCles?: AssembledListing | null;
  // Jugement LLM (Cycle 36) : famille + catalog-miss + question discriminante.
  reasoned?: ReasonedIdentification | null;
  // Type DÉRIVÉ de la catégorie identifiée (Cycle 36) → questions d'état spécifiques au bon moment.
  kind?: ProductKind | null;
  // Année d'achat saisie par le vendeur (affichée dans les données structurées de la fiche).
  purchaseYear?: string;
}) {
  const [title, setTitle] = useState(listing.title);
  const [description, setDescription] = useState(listing.description);
  const [mainPhoto, setMainPhoto] = useState(0);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  // État spécifique au type (Cycle 36) : questions dérivées de la catégorie identifiée.
  const [typeAnswers, setTypeAnswers] = useState<Record<string, string>>({});

  // Re-synchronise quand une NOUVELLE annonce arrive (anti derived-state bug).
  useEffect(() => {
    setTitle(listing.title);
    setDescription(listing.description);
    setMainPhoto(0);
    setTypeAnswers({});
  }, [listing]);

  const kindQuestions = kind ? KIND_CHECKLIST[kind] : [];
  const kindLabel = PRODUCT_KINDS.find((k) => k.value === kind)?.label ?? "";

  const conditionLabel = CONDITION_LABELS[condition];
  // Type de produit = catégorie du produit CHOISI (réordonné par l'IA si dispo) ; le vote pondéré
  // peut être pollué par des accessoires (une coque ferait afficher « Basic Cases » pour un iPhone).
  const productType = chosen?.category_fine || predicted?.fine || "";
  const confidencePct = predicted ? Math.round(predicted.confidence * 100) : 0;

  // « Informations clés » façon marketplace : type produit + état + marque + facettes
  // (couleur, capacité, taille…). C'est la metadata structurée, visible et navigable.
  const keyInfo = useMemo(() => {
    const rows: { name: string; value: string; source: string }[] = [];
    // Année = donnée VENDEUR pertinente (l'État est déjà le badge sous le prix → pas de doublon ici).
    if (purchaseYear) rows.push({ name: "Année d'achat", value: purchaseYear, source: "vendeur" });
    // Données structurées générées par l'API (facettes + provenance) : type, marque, capacité, etc.
    if (informationsCles && informationsCles.fields.length > 0) {
      for (const f of informationsCles.fields) {
        if (f.name === "État") continue; // l'état général est le badge sous le prix
        rows.push({ name: f.name, value: f.value, source: f.source });
      }
      return rows;
    }
    // Repli : reconstruit depuis le candidat choisi (sans provenance fine).
    if (productType) rows.push({ name: "Type de produit", value: productType, source: "" });
    if (chosen?.brand) rows.push({ name: "Marque", value: chosen.brand, source: "" });
    for (const [k, v] of Object.entries(chosen?.attributes ?? {})) {
      if (k === "brand" || k === "category") continue;
      rows.push({ name: facetLabel(k), value: v, source: "" });
    }
    return rows;
  }, [chosen, productType, conditionLabel, informationsCles, purchaseYear]);

  const completenessPct = informationsCles ? Math.round(informationsCles.completeness * 100) : null;

  // Breadcrumb : le rangement du produit CHOISI d'abord (réordonné par l'IA), repli sur le vote.
  const breadcrumb = chosen?.category_path || predicted?.path || chosen?.category_fine || "";

  async function copyAll() {
    const keyInfoText = keyInfo.map((r) => `${r.name} : ${r.value}`).join("\n");
    // État spécifique vérifié (type dérivé) inclus dans l'annonce copiée.
    const typeText = kindQuestions
      .filter((q) => typeAnswers[q.key])
      .map((q) => `${q.label.replace(/\s*\?$/, "")} : ${typeAnswers[q.key]}`)
      .join("\n");
    const priceLine =
      price.suggested_price_eur > 0
        ? `Prix : ${price.suggested_price_eur.toFixed(2)} € (${conditionLabel})`
        : `Prix : à fixer (saisie manuelle) — ${conditionLabel}`;
    await navigator.clipboard.writeText(
      [
        title,
        "",
        priceLine,
        breadcrumb ? `Catégorie : ${breadcrumb}` : "",
        keyInfoText ? `\nInformations clés :\n${keyInfoText}` : "",
        typeText ? `\nÉtat vérifié :\n${typeText}` : "",
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

      {/* Cycle 36 : catalog-miss → la fiche est une ESTIMATION (produit absent du catalogue). */}
      {reasoned?.catalog_miss && (
        <div className="border-b border-amber-200 bg-amber-50 px-5 py-2.5 text-sm text-amber-800">
          ⚠ Produit <strong>estimé</strong>
          {reasoned.product_family ? ` « ${reasoned.product_family} »` : ""} — absent du catalogue.
          Prix et caractéristiques à vérifier.
        </div>
      )}
      {/* Question discriminante proposée par l'IA (capacité, variante…) pour affiner. */}
      {reasoned?.ask_question && reasoned.facet_question && (
        <div className="border-b border-sky-200 bg-sky-50 px-5 py-2.5 text-sm text-sky-800">
          💡 Pour affiner : {reasoned.facet_question}
        </div>
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

          {/* Catégorie détectée automatiquement (vote des voisins) + confiance */}
          {productType && (
            <div className="mt-1.5 flex flex-wrap items-center gap-2 px-1.5 text-xs">
              <span className="rounded-full bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">
                🏷️ {productType}
              </span>
              {predicted && (
                <span className="text-slate-400">
                  catégorie détectée · {confidencePct}% de confiance
                </span>
              )}
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-baseline gap-2">
            {/* L4 / pas de prix exploitable : ne JAMAIS afficher « 0,00 € » comme une suggestion. */}
            {price.suggested_price_eur > 0 ? (
              <span className="text-4xl font-bold text-rose-700">
                {price.suggested_price_eur.toFixed(2)} €
              </span>
            ) : (
              <span className="text-2xl font-bold text-slate-500">Prix à fixer (saisie manuelle)</span>
            )}
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
              fiabilité prix {(price.confidence_score * 100).toFixed(0)}%
            </span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">{price.explanation}</p>
          {/* Âge supposé par défaut (2 ans) quand le vendeur n'a pas saisi l'année → on l'indique. */}
          {!purchaseYear && price.suggested_price_eur > 0 && (
            <p className="mt-1 text-xs italic text-slate-400">
              Âge supposé : 2 ans — saisis l'année d'achat pour affiner le prix.
            </p>
          )}

          {/* Informations clés — la metadata structurée à facettes, façon marketplace.
              Chaque champ porte sa provenance (observé / catalogue / typique-à-vérifier),
              et la complétude indique le remplissage sur le schéma attendu de la catégorie. */}
          <div className="mt-4">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Informations clés
              </p>
              {completenessPct !== null && (
                <span
                  className="text-xs text-slate-400"
                  title="Part des facettes attendues pour cette catégorie qui sont remplies"
                >
                  Fiche remplie à {completenessPct}%
                </span>
              )}
            </div>
            {keyInfo.length > 0 ? (
              <dl className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-1.5">
                {keyInfo.map((r) => (
                  <div key={r.name} className="flex flex-col">
                    <dt className="flex items-center gap-1 text-xs text-slate-400">
                      {r.name}
                      {r.source && (
                        <span
                          className={`rounded px-1 py-px text-[10px] ${SOURCE_STYLE[r.source] ?? "bg-slate-100 text-slate-500"}`}
                        >
                          {r.source}
                        </span>
                      )}
                    </dt>
                    <dd className="truncate text-sm text-slate-700" title={r.value}>
                      {r.value}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="mt-1.5 text-sm text-slate-400">(aucun attribut détecté)</p>
            )}
          </div>
        </div>
      </div>

      {/* Cycle 36 : checklist d'état SPÉCIFIQUE au type DÉRIVÉ de la catégorie identifiée — affichée
          au bon moment (après l'identification), plus de « type d'objet » deviné par le vendeur. */}
      {kindQuestions.length > 0 && (
        <div className="border-t border-slate-100 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Points à vérifier{" "}
            <span className="font-normal normal-case text-slate-500">{kindLabel}</span>
          </p>
          <div className="mt-2 space-y-2">
            {kindQuestions.map((q) => (
              <div key={q.key} className="flex flex-wrap items-center gap-1.5">
                <span className="w-44 shrink-0 text-xs text-slate-600">{q.label}</span>
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() =>
                      setTypeAnswers((a) => ({ ...a, [q.key]: a[q.key] === opt ? "" : opt }))
                    }
                    className={`rounded-full px-2.5 py-1 text-xs transition ${
                      typeAnswers[q.key] === opt
                        ? "bg-rose-600 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

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

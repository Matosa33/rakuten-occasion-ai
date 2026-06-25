# Interface d'annotation — photos d'éval (Phase 2)

Outil pour constituer **vite** le jeu de produits réels qui prouvera la chaîne de valeur
photo-first (**1 photo < N photos < N photos + métadonnée**).

## 0) Le plus rapide — ingestion de PDF scrappés — `ingest_pdf.py`

Avec l'extension **Lebonscrap** (Chrome), exporte chaque annonce leboncoin en PDF dans
`~/Downloads` (nom `LBC-*.pdf`). Puis :

```bash
.venv/Scripts/python.exe scripts/annotation_tool/ingest_pdf.py            # depuis ~/Downloads
.venv/Scripts/python.exe scripts/annotation_tool/ingest_pdf.py --src <dossier> --limit 5
```

Le PDF est *image-only* (pas de texte) : le script **rend + recadre** chaque page-photo
(retire la légende/filigrane) → `01.jpg…0N.jpg`, et fait **lire la carte** (page 0) par le VLM
(Gemma) → `meta.json` complet (titre, catégorie→macro, taxo fine, prix, état, seller_metadata,
`annotated:true`). Idempotent (skip les `source_pdf` déjà ingérés), tolérant. **C'est la voie
recommandée** : tu scrapes, je n'ai qu'à lancer l'ingestion.

Le script note aussi la **qualité de la métadonnée d'entrée** (`metadata_quality.score` ∈ [0,5],
5 critères : marque / modèle / spec / état / non-ambigu). C'est ce qui permettra de **mesurer
l'impact réel de la métadonnée** selon sa richesse (Phase 2, condition C3).

> Besoin des extras `[annotation]` (pymupdf, pillow) + `[api]` (requests) + clé OpenRouter.

## 1) Alternative manuelle — saisie rapide (humain) — `app.py`

```bash
.venv/Scripts/python.exe scripts/annotation_tool/app.py     # http://127.0.0.1:8200
```

Pour chaque produit : glisser-déposer les **photos** + coller le **texte de l'annonce réelle**
(titre + description Leboncoin/Vinted…). C'est tout. L'outil range automatiquement :

```
data/photos_eval/<NN>_<slug>/
    01.jpg 02.jpg …        # 01 = photo principale (bordure verte), sert seule en condition C1
    meta.json              # { listing_title, listing_description, photos, annotated:false }
```

Astuce : <kbd>Ctrl/Cmd + Entrée</kbd> enregistre. Le tableau de bord suit l'avancement
(objectif ~100 produits, alerte « <2 photos »).

## 2) Dérivation des métadonnées (auto) — `derive_meta.py`

```bash
.venv/Scripts/python.exe scripts/annotation_tool/derive_meta.py          # les non-annotés
.venv/Scripts/python.exe scripts/annotation_tool/derive_meta.py --force  # tout re-dériver
```

Lit chaque produit `annotated:false` et **dérive par LLM** (OpenRouter, clé dans `.env`) les
champs structurés, écrits dans `meta.json` (`annotated:true`) :
- `macro` (une des 4 : Electronics / Cell_Phones / Video_Games / Tools),
- `true_category_path` (taxonomie fine « A > B > C »),
- `true_name` (libellé normalisé),
- `seller_metadata` (texte court vendeur = condition C3).

Idempotent (skip les déjà annotés), tolérant (un échec n'arrête pas le lot), passe à l'échelle
(~100 produits). Les cas hors-liste sont signalés pour relecture humaine.

## Pour un jeu « bien rempli »

- **~100 produits**, répartis sur les 4 macro-catégories ;
- des **near-duplicates** (iPhone 13 vs 14, deux consoles proches…) — c'est là que N photos +
  métadonnée prouvent leur valeur ;
- **≥ 2 photos** par produit (sinon le test 1 vs N ne montre rien) ;
- la **photo principale** doit être la plus représentative.

> Les photos restent **locales** (`data/photos_eval/` gitignoré) — rien n'est publié.

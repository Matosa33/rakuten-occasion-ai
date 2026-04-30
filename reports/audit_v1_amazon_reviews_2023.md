# Audit dataset — Amazon Reviews 2023 (FULL sur 15 catégories evergreen-occasion)

> Version : v2 FULL D-008 (chiffres mesurés le 2026-04-30 sur les 15 catégories complètes)
> Statut : `completed` — chiffres issus des 3 fichiers JSON dans `reports/`
> (`audit_qualite_metrics.json`, `audit_distributions_metrics.json`,
> `audit_biais_leakage_metrics.json`). Aucun chiffre inventé (R8 du brain).
>
> **Supersede** la v1 (3 cat Electronics + Toys_and_Games + All_Beauty) qui calibrait
> sur un périmètre choisi par hypothèse (cf. R18 — biais de supposition explicite).
> Périmètre actuel défini par méta-first (Range HTTP probes, cf. R17) puis filtre
> evergreen-occasion (cf. `BRAIN/decisions.md` D-008).

---

## 1. Source

- **Dataset** : `McAuley-Lab/Amazon-Reviews-2023`
- **Provenance** : HuggingFace, page officielle https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
- **Documentation académique** : https://amazon-reviews-2023.github.io/
- **Référence paper** : Hou et al. *"Bridging Language and Items for Retrieval and Recommendation"* (2024)
- **Volume total officiel du dataset complet** : 571,54 M reviews + 48 M items sur 33 catégories, période mai 1996 → septembre 2023
- **Licence** : académique / non-commercial (licence McAuley Lab)

## 2. Périmètre audité — D-008

- **Stratégie** : 15 catégories COMPLÈTES (full, pas un sample) — voir `BRAIN/decisions.md` D-008
- **Filtre evergreen-occasion** : produits qui se revendent en seconde main après plusieurs années (ni numérique, ni consommable, ni abonnement). Exclues : Kindle, Software, Digital_Music, Magazine_Subscriptions, Subscription_Boxes, Gift_Cards, Beauty, Health, Office, Pet_Supplies, Arts, Unknown.
- **Catégories retenues (15)** : Clothing_Shoes_and_Jewelry, Home_and_Kitchen, Books, Electronics, Tools_and_Home_Improvement, Automotive, Sports_and_Outdoors, Cell_Phones_and_Accessories, Movies_and_TV, Toys_and_Games, CDs_and_Vinyl, Baby_Products, Video_Games, Musical_Instruments, Appliances.
- **Total reviews** : **348 367 044** (348,4 M, soit 60,9 % du dataset complet)
- **Total items meta** : **26 369 078** (26,4 M, soit 54,9 % du dataset complet)
- **Mode de chargement** : `huggingface_hub.hf_hub_download` (resume natif, cache, sha256) puis conversion lazy en parquet zstd via `polars.scan_ndjson(...).sink_parquet(...)`. Pour les meta dont le polars cale (`'�'` non parseable comme Float64, types hétérogènes), fallback `pandas.read_json(lines=True, chunksize=50_000)` avec schéma string fixe (cf. `01_load_full.py`).
- **Volumes téléchargés et stockés localement** :
  - Reviews parquet zstd : **43,0 GB** sur 15 fichiers (Home_and_Kitchen 7,8 GB ; Clothing 6,6 GB ; Books 6,2 GB ; Electronics 5,4 GB)
  - Meta parquet zstd : **17,6 GB** sur 15 fichiers (Books 5,1 GB ; Clothing 3,5 GB ; Home_and_Kitchen 2,7 GB ; Automotive 1,2 GB ; Electronics 1,2 GB)
  - **Total parquet sur disque : ~60,6 GB** (vs ~227 GB en JSONL côté cache HF, ratio compression ~3,7×)
- **Date d'audit** : 2026-04-30
- **Durée totale mesurée** : ~2h download + ~9 min audit polars (4 étapes)

## 3. Volumes

| Métrique | Reviews | Meta |
|----------|--------:|-----:|
| Total lignes | **348 367 044** | **26 369 078** |
| Colonnes (après drop des List/Struct) | 9 + `_source_category` | 10 + `_source_category` |
| `parent_asin` uniques | **26 362 426** | **26 369 078** |
| `user_id` uniques | **48 808 303** | n/a |
| `asin` uniques | **38 387 481** | n/a |

**Observation** : `meta.n_unique_parent_asin = meta.n_total = 26 369 078` → meta sans doublons sur la clé. `reviews.n_unique_parent_asin = 26 362 426` (couverture 99,975 %) → seulement **6 652 produits** sur 26,37 M ont des reviews sans metadata. La discipline méta-first fonctionne, vs les ~99 % de NaN qu'on aurait sur un sample naïf.

> Note : les colonnes `images`, `videos`, `features`, `categories`, `details`, `bought_together` sont droppées au scan_concat. Raison : type mixte List[Struct]/String entre fichiers (selon polars natif vs fallback pandas) qui casse le concat. Aucune analyse d'audit ne s'appuie dessus.

## 4. Qualité

### NaN par colonne (reviews)

![NaN reviews](figures/02a_nan_par_colonne_reviews.png)

**Toutes les colonnes reviews sont à 0 % NaN.** Le dataset reviews est totalement renseigné — confirmation sur 348 M lignes du même finding qu'en v1.

### NaN par colonne (meta)

![NaN meta](figures/02b_nan_par_colonne_meta.png)

| Colonne | % NaN | Interprétation |
|---------|------:|----------------|
| `author` | **89,12 %** | Pertinent uniquement pour Books/CDs/Movies (les autres cat → vide) |
| `subtitle` | **84,81 %** | Idem (Books/Movies surtout) |
| `price` | **57,87 %** | 42,1 % des items ont un prix exploitable, soit 10 759 353 items (B3 ci-dessous) |
| `main_category` | 7,30 % | OK |
| `store` | 2,95 % | OK |
| `title`, `description` | 1,19 % | quasi-complet |
| `parent_asin`, `average_rating`, `rating_number` | 0,00 % | OK |

**Décision pour C06** : drop `subtitle` et `author` (≥ 84 % vide) sauf pour les sous-catégories où ils sont denses (Books). Conserver `price` mais ne l'utiliser que pour les ~10,76 M items qui en ont un.

### Doublons et unicité

| Métrique | Reviews | Meta |
|----------|--------:|-----:|
| Lignes / parent_asin uniques | 348 367 044 / 26 362 426 = **13,21** | 26 369 078 / 26 369 078 = **1,00** |

**Interprétation** : chaque produit a en moyenne **13 reviews**. Plus bas que la v1 sur 3 cat (23,29) car les 12 nouvelles catégories (Books, CDs, Movies, Clothing…) ont une distribution plus étalée qu'Electronics/Toys.

### Longueurs textes (reviews)

| Champ | n non-null | Médiane | p95 | Max | n < 5 chars |
|-------|----------:|--------:|----:|----:|------------:|
| `title` | 348 367 044 | 17 | 57 | 4 002 | 8 955 925 (2,6 %) |
| `text` | 348 367 044 | 109 | 711 | 42 373 | 3 856 195 (1,1 %) |

### Longueurs textes (meta)

| Champ | n non-null | Médiane | p95 | Max | n < 5 chars |
|-------|----------:|--------:|----:|----:|------------:|
| `title` | 26 055 090 | 76 | 190 | 2 000 | 29 675 (~0 %) |
| `description` | 26 055 090 | 79 | 1 714 | **1 476 557** | 11 747 131 (45 %) |

**Observations** :
- `text` review : médiane 109 chars, p95 711 → exploitable directement par Arctic Embed L v2 (8 192 tokens).
- `description` meta : **45 % des descriptions font moins de 5 chars** → ~11,75 M items ont une description vide ou ultra-courte. Le max à 1 476 557 chars (~370 K mots, format JSON sérialisé probablement) est un outlier qu'il faudra tronquer.

## 5. Distributions

### Distribution par catégorie

![reviews_par_cat](figures/03a_distribution_reviews_par_cat.png)
![meta_par_cat](figures/03b_distribution_meta_par_cat.png)

**Distribution reviews (Top 15)** :

| Catégorie | Reviews | % du total |
|-----------|--------:|----------:|
| Home_and_Kitchen | 67 409 944 | 19,4 % |
| Clothing_Shoes_and_Jewelry | 66 033 346 | 19,0 % |
| Electronics | 43 886 944 | 12,6 % |
| Books | 29 475 453 | 8,5 % |
| Tools_and_Home_Improvement | 26 982 256 | 7,7 % |
| Cell_Phones_and_Accessories | 20 812 945 | 6,0 % |
| Automotive | 19 955 450 | 5,7 % |
| Sports_and_Outdoors | 19 595 170 | 5,6 % |
| Movies_and_TV | 17 328 314 | 5,0 % |
| Toys_and_Games | 16 260 406 | 4,7 % |
| Baby_Products | 6 028 884 | 1,7 % |
| CDs_and_Vinyl | 4 827 273 | 1,4 % |
| Video_Games | 4 624 615 | 1,3 % |
| Musical_Instruments | 3 017 439 | 0,9 % |
| Appliances | 2 128 605 | 0,6 % |

**Distribution meta (items)** :

| Catégorie | Items | % du total |
|-----------|------:|----------:|
| Clothing_Shoes_and_Jewelry | 7 218 481 | 27,4 % |
| Books | 4 448 181 | 16,9 % |
| Home_and_Kitchen | 3 735 584 | 14,2 % |
| Automotive | 2 003 129 | 7,6 % |
| Electronics | 1 610 012 | 6,1 % |
| Sports_and_Outdoors | 1 587 421 | 6,0 % |
| Tools_and_Home_Improvement | 1 473 810 | 5,6 % |
| Cell_Phones_and_Accessories | 1 288 490 | 4,9 % |
| Toys_and_Games | 890 874 | 3,4 % |
| Movies_and_TV | 748 224 | 2,8 % |
| CDs_and_Vinyl | 701 959 | 2,7 % |
| Musical_Instruments | 213 593 | 0,8 % |
| Baby_Products | 217 724 | 0,8 % |
| Video_Games | 137 269 | 0,5 % |
| Appliances | 94 327 | 0,4 % |

**Phénomène long-tail confirmé** : ratio max/min = **31,67** (Home_and_Kitchen 67,4 M reviews vs Appliances 2,1 M). Plus modéré que la v1 (× 62,56) car les 12 nouvelles cat sont plus uniformes, mais reste **high** au seuil B1.

### Distribution prix

![prix](figures/03c_distribution_prix_meta.png)

Sur les **10 759 353 prix valides** (40,8 % des items meta) :

| Statistique | Valeur |
|-------------|-------:|
| Moyenne | 46,86 $ |
| Médiane | 18,99 $ |
| p95 | 159,95 $ |
| p99 | 464,99 $ |
| Max | 1 000 000,00 $ |
| Items > 500 $ | 93 548 |

**Distribution log-normale classique** : la médiane (18,99 $) est très inférieure à la moyenne (46,86 $) → queue longue à droite avec des outliers (max 1 M $, probablement données saisies à la main). p99 raisonnable (465 $).

### Distribution ratings

![ratings](figures/03d_distribution_ratings_reviews.png)

| Note | Effectif | % |
|-----:|---------:|--:|
| 5★ | 228 156 382 | **65,5 %** |
| 4★ | 43 979 066 | 12,6 % |
| 3★ | 24 557 169 | 7,1 % |
| 2★ | 17 165 327 | 4,9 % |
| 1★ | 34 509 093 | 9,9 % |
| 0★ | 7 | anomalies |

**Skew positif confirmé** : 78,1 % de notes ≥ 4★ contre 9,9 % de 1★. À mitiger par class_weight si on entraîne du sentiment.

### Distribution temporelle

![temporel](figures/03e_distribution_temporelle_reviews.png)

Étendue : **1996 → 2023** (28 ans). Distribution clairement croissante :

| Année | Reviews | Note |
|-------|--------:|------|
| 2014 | 17,4 M | premier seuil > 17 M |
| 2019 | 41,2 M | accélération |
| 2020 | 44,9 M | COVID (e-commerce dopé) |
| **2021** | **47,2 M** | **pic absolu** |
| 2022 | 40,7 M | décrue |
| 2023 | 16,6 M | sample arrêté en sept 2023 (cohérent avec doc officielle) |

Avant 2010 : moins de 1,5 % du total. Reviews sur 3 dernières années (2021-2023) : **30 %** → étalement satisfaisant, B4 reste **low**.

## 6. Biais identifiés (mesurés sur le FULL D-008)

| ID | Label | Sévérité | Métrique mesurée |
|----|-------|----------|------------------|
| **B1** | déséquilibre catégoriel | **high** | ratio max/min Home_and_Kitchen/Appliances = **31,67** |
| B2 | verified_purchase | low | **90,4 %** `verified_purchase=True` (signal majoritairement vérifié) |
| **B3** | concentration low-end (prix) | medium | **82,0 %** des prix valides < 50 $ (sur n=10 759 353), 57,9 % sans prix du tout |
| B4 | concentration temporelle récente | low | **30,0 %** en 2021-2023 (étalement satisfaisant 1996-2023) |
| B5 | langue (anglais 100 %) | high | détecté **a priori** : Amazon US |
| B6 | plateforme (Amazon US ≠ Rakuten FR) | medium | détecté **a priori** : proxy assumé |
| **B7** | rating skew positif | medium | **78,1 %** de 4-5★ vs 9,9 % de 1★ |

## 7. Leakages potentiels (mesurés sur le FULL D-008)

| ID | Label | Sévérité | Métrique mesurée |
|----|-------|----------|------------------|
| **L1** | variantes (asin / parent_asin) | **high** | duplication factor **13,21** (348,4 M reviews / 26,36 M parent_asin uniques) |
| **L2** | user_id répétés | medium | 48,8 M users uniques → **36,2 M users avec > 1 review** (74,2 %) |
| **L3** | titres identiques | medium | **214,9 M** titres dupliqués sur 348,4 M (61,7 %) — typiquement "Five Stars", "Great", etc. |

**Interprétation L1** : duplication factor de 13,21 = chaque produit a en moyenne 13 reviews. Sans précaution au split (groupage par `parent_asin`), un produit pourra apparaître dans train ET test → leakage massif.

**Interprétation L2** : 36,2 M users (74,2 %) ont > 1 review. Si on splitte aléatoirement, ces users feront fuiter leur préférence entre train et test → group leakage. À corriger en C07 avec `GroupKFold(group=user_id)`.

**Interprétation L3** : 61,7 % de titres dupliqués est énorme (vs 57,3 % sur 3 cat). Largement dû aux titres ultra-courts ("Five Stars", "Great product", etc.). À investiguer en C06 — la médiane de longueur titre = 17 chars, donc beaucoup de titres minimaux.

## 8. Verdict

> **Utilisable comme proxy pour Rakuten v3 ?** **Oui, avec conditions.**
>
> **Conditions à respecter** :
>
> - **C1** (cleaning, C06) : drop les colonnes meta très NaN (`subtitle` 85 %, `author` 89 %) sauf si on isole le sous-périmètre Books (où ces deux champs sont denses).
> - **C2** (cleaning, C06) : pour le pricing, ne garder que les ~10,76 M items avec un `price` valide (40,8 % des items). Cap les prix à p99 (~465 $) si on entraîne un modèle de pricing standard, ou utiliser un modèle log-normal pour absorber la queue longue (max 1 M $).
> - **C3** (cleaning, C06) : tronquer les `description` meta à 8 192 tokens (max actuel 1 476 557 chars > 370 K mots, outlier énorme). Évaluer si on filtre les ~11,75 M items avec description < 5 chars (45 %).
> - **C4** (split, C07) : utiliser **`GroupKFold(group=parent_asin)` ou `group=user_id`** pour éviter L1 (variantes) et L2 (group leakage). Préférer parent_asin si on évalue produit-level, user_id si user-level.
> - **C5** (modélisation, P03+) : la langue anglaise (B5) impose l'**Arctic Embed L v2 multilingue** prévu en P03.
> - **C6** (validation finale) : ne JAMAIS valider la performance finale uniquement sur ce dataset. Croiser avec un dump FR (Vinted/Rakuten via API officielle) à terme. Le proxy est un outil d'**itération**, pas un benchmark de production.
> - **C7** (rating skew B7) : pour un modèle de sentiment, downsampler 5★ ou utiliser `class_weight='balanced'`.
> - **C8** (déséquilibre catégoriel B1) : si on garde les 15 catégories, le **stratified split** par catégorie est non-négociable pour éviter qu'Home_and_Kitchen et Clothing écrasent les petites cat (Appliances, Musical_Instruments). Si on entraîne un classifieur de catégorie, prévoir aussi un downsampling des dominantes ou des poids inversement proportionnels.

## 9. Annexes

- Scripts utilisés : `src/data/audit/01..04_*.py` (4 scripts polars + fallback pandas, `scan_concat` factorisé dans `__init__.py`)
- Notebooks compagnons : `notebooks/00_meta_exploration.ipynb` (méta-first Range HTTP) + `notebooks/01_audit_exploratoire.ipynb` (pandas pour exploration interactive < 1 GB)
- Métriques machine-readable : `reports/audit_*_metrics.json` (3 fichiers, regénérables)
- Graphiques : `reports/figures/*.png` (≥ 11 PNG, gitignored, regénérables via `make audit`)
- Tests d'invariants : `tests/test_audit_invariants.py`
- Stack utilisée : `polars 1.40.1` (engine streaming) + `pandas 2.2` + `pyarrow 21` + `huggingface-hub` + `matplotlib 3.10` + `seaborn 0.13`
- Décisions tracées dans `BRAIN/decisions.md` : D-004 (dataset Amazon Reviews 2023, active), D-006 (polars lazy + streaming, active), D-007 (full vs sample, active), D-008 (périmètre 15 cat evergreen-occasion, active)
- Règles méthodologiques : R17 (méta-first avant data-first), R18 (biais de supposition explicite) dans `BRAIN/golden_rules.md`

# PoC bench — branche photo : VLM-extraction vs SigLIP (Cycle 17.0)

> 2026-06-11. Exigence : scorer « très factuellement, en induisant la solution
> et pas en la déduisant ». Tous les chiffres ci-dessous sont MESURÉS sur notre
> pipeline / notre catalogue, scripts committés (`src/vlm/02_poc_photo_identification.py`,
> `src/encoders/04_poc_siglip_sample.py`), JSON bruts dans ce dossier.

## Protocoles

| PoC | Chemin testé | Espace de recherche | Query |
|---|---|---|---|
| **A** (VLM-extraction) | photo → VLM OpenRouter (titre probable) → `/identify` API réelle | **3,16 M produits (index complet prod)** | 2ᵉ vue catalogue (proxy photo user) |
| **A-ter** | idem, échantillon CIBLÉ « déménagement » (33 produits de marque : iPhone, MacBook, Xbox, ThinkPad, Bosch…) | 3,16 M | idem |
| **B** (SigLIP visuel pur) | photo → SigLIP → recherche cosine parmi les images MAIN | **2 000 produits** (échantillon) | 2ᵉ vue catalogue |

## Résultats mesurés

| Métrique | PoC A (aléatoire) | PoC A-ter (déménagement) | PoC B (SigLIP) |
|---|---:|---:|---:|
| hit@1 (asin exact) | 4 % | 9 % | **75 %** |
| hit@5 (asin exact) | 16 % | 24 % | **88 %** |
| hit@30 (asin exact) | 24 % | 36 % | 94 % |
| **same-model@5** (le bon produit ou variante quasi-identique dans l'écran de choix) | — | **≈ 52 %** | — |
| Latence / query | ~2,2 s (VLM) + retrieval | idem | ~0,1 s (encode) |
| Dispo aujourd'hui | ✅ immédiate | ✅ | ❌ (catalogue non encodé) |

**⚠ Les colonnes ne sont PAS directement comparables** — c'est le cœur de la lecture honnête :
- PoC B cherche dans un espace **1 580× plus petit** que la prod (2 k vs 3,16 M) → optimiste.
- PoC B est **studio→studio** : la vraie photo utilisateur (lumière jaune, fond chaotique, angle) introduit un **domain shift jamais mesuré** — c'était le risque n°1 documenté dès D-009. Aucun de nos jeux de données ne contient de vraies photos utilisateur → ce risque est **non mesurable avant d'avoir investi**.
- PoC A est mesuré dans les **conditions réelles exactes** de la prod (index complet, chemin API complet).

## Lecture qualitative (inspection des 33 cas déménagement)

- Les descriptions VLM sont **excellentes** (« Apple iPhone 8 Plus, Fully Unlocked, 256GB - Gold » lu sur la photo) — le maillon faible n'est PAS le VLM.
- Les échecs exact-asin viennent de la **confusion inter-générations dans le matching texte** (iPhone 7 vs 8 Plus, JBL Flip 5 vs Charge 5, ThinkPad E495 vs P15s) : des produits visuellement et textuellement quasi identiques.
- Or ce problème est EXACTEMENT ce que le produit traite déjà par design : facettes Akinator (capacité, génération) + visionneuse + **validation humaine** (R19/D-017 : l'humain tranche). La métrique produit pertinente est « le bon produit est dans l'écran de sélection » (~52 % direct, plus avec une boucle facette), pas « asin exact en top-1 ».

## Question jury : « a-t-on fait assez d'entraînement ? »

Fait mesuré dans MLflow : **3 entraînements réels** trackés (svm-embed SVM 596 s, mlp-embed MLP 399 s,
tfidf-svm TF-IDF+LinearSVC+Platt 1 585 s) + bench comparatif 5 modèles + calibration (ECE)
+ Registry @Production + **boucle de ré-entraînement automatisée** (Airflow,
champion/challenger — des retrains réels ont créé les versions v4/v5 du registry).
**SigLIP n'ajouterait RIEN ici : c'est un encoder FROZEN** (inférence + indexation,
zéro entraînement). Le seul vrai « plus d'entraînement » serait F8 (fine-tuning VLM
QLoRA), conditionnel à une preuve de gain (D-009) — indépendant du choix ci-dessous.

## Scoring final

| Critère | VLM-extraction | SigLIP index complet |
|---|---|---|
| Précision mesurée en conditions réelles | ~52 % same-model@5 (mesuré, espace complet) | non mesurable sans investir (88 % @5 en conditions doublement optimistes) |
| Délai jusqu'à démontrable | **0 jour** (modèle actuel a la vision) | ~73 h de download CDN (mesuré 13 img/s, D-014) + encode + rebuild index |
| Risque | dépendance API (fallback texte existant) | **domain shift photo réelle inconnu** → risque de découvrir le problème APRÈS 73 h |
| Ce que ça débloque | TOUT le recadrage photo-first : upload obligatoire, guidage vues, extraction état, **VLM validateur F0.4**, OCR étiquettes | uniquement le matching visuel (multi-view RRF D-009) |
| Valeur jury « entraînement » | 0 (API) | 0 (frozen) |
| Casse l'existant ? | non (alimente le pipeline actuel) | non (vue additionnelle RRF) |

## Recommandation (induite des mesures)

1. **VLM-extraction MAINTENANT** : c'est le seul chemin mesuré en conditions réelles,
   disponible immédiatement, et c'est lui qui débloque l'INTÉGRALITÉ du recadrage
   photo-first (la photo entre enfin dans le produit). La précision exact-asin
   moyenne est compensée par le design existant (facettes + visionneuse + humain).
2. **SigLIP en option B mesurée AVANT d'investir** : lancer UNE nuit de download sur
   la plus petite catégorie (Video_Games, 2,9 GB) → encoder → mesurer le multi-view
   RRF réel et surtout tester le domain shift avec quelques vraies photos prises au
   téléphone. GO/NO-GO sur les 73 h complètes seulement après CE chiffre.
3. Ni l'un ni l'autre ne change la réponse jury « entraînement » — elle est déjà
   couverte (svm-embed/mlp-embed/tfidf-svm + boucle retrain) et le seul levier serait F8 (hors décision).

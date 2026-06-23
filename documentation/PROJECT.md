# Rakuten AI — Document de cadrage

> Version 3.0 — 2026-06-11
> Auteur(s): Mathieu Klopp
> Statut: active — v3 réaffirme le **photo-first** fondateur : la photo (≥ 1, preuve acheteur)
> est l'entrée OBLIGATOIRE du flow ;
> la branche photo passe par **VLM-extraction** (mesuré PoC) — l'encodage
> vision du catalogue (SigLIP) reste gated sur mesure réelle du domain shift.
> Supersede v2.1 sur la modalité d'entrée de F0/F5; périmètre 4 cat inchangé.

> **Note méthodologique**: ce document distingue **chiffres sourcés** (web,
> études, mesures internes) et **hypothèses à valider** (à confirmer par tests
> utilisateurs ou benchmark). Les hypothèses non sourcées seront mesurées plus
> tard, jamais inventées.

---

## 1. Contexte

Le marché français de la seconde main entre particuliers est en croissance forte. Selon les sources convergentes du secteur, il pèse autour de **7 à 14 milliards d'euros** en 2024 (le delta s'expliquant par le périmètre retenu: textile seul ou tous biens, reconditionné inclus ou non), avec une croissance annuelle de l'ordre de **+15 % au global** et **+8,5 % sur le textile** [^1] [^2]. **Près de 3 Français sur 4** ont acheté un produit d'occasion en 2024 [^3].

Ce marché est dominé en C2C (particulier-à-particulier) par **Vinted** (813,4 M€ de CA en 2024, 17,3 M visiteurs mensuels) sur la mode et **Leboncoin** (~520 M€ de CA, 30 M visiteurs mensuels, 800 000 nouvelles annonces par jour) sur le généraliste [^4] [^5]. **Rakuten France** se positionne sur un créneau hybride (neuf + occasion), avec **55,4 % de ventes en occasion en 2025** sur certaines catégories (en hausse de +5 points vs 2023) [^6]. À noter: un écosystème commercial d'**outils d'IA pour générer des descriptions Vinted** existe déjà (VintyLook, QuickListAI, Listed AI, SharkScribe…) [^7] — donc le besoin est validé par le marché, mais aucun acteur ne semble dominer côté Rakuten.

L'utilisateur cible est **le vendeur particulier occasionnel**: pas un revendeur pro, mais quelqu'un qui veut écouler 1 à 50 objets (déménagement, vide-grenier, garde-robe, héritage). Cette population est **mal servie par les UX actuelles**: choix manuel dans des taxonomies de centaines de catégories, rédaction de titre SEO, écriture de description, recherche du prix marché — autant d'étapes qui demandent une expertise que le particulier n'a pas envie d'acquérir pour vendre 5 objets par an.

## 2. Proposition de valeur

Pour les **vendeurs particuliers occasionnels** (cible: ceux qui mettent en ligne moins de 50 articles par an), qui **butent sur les étapes manuelles de catégorisation, rédaction et estimation prix**, notre solution est une **app web** qui **génère la fiche produit complète (catégorie, attributs, titre, description, prix indicatif) à partir de quelques photos**, contrairement aux **interfaces actuelles** qui demandent au vendeur d'effectuer toutes ces tâches manuellement.

Le différentiateur vs les outils AI existants type VintyLook: **un seul flux end-to-end** (photo → fiche complète), un **pipeline d'identification ancré dans un catalogue de référence** (anti-hallucination par design), et un **pricing transparent avec breakdown** plutôt qu'une suggestion opaque.

## 3. Hypothèses-clés

> Ces hypothèses **ne sont pas encore validées**. Elles sont **mesurables** et seront vérifiées par tests utilisateurs ou benchmark.

- **H1**: Nous croyons qu'auto-générer la fiche depuis les photos permettra aux vendeurs particuliers de **réduire significativement le temps de création d'annonce**. *Mesure cible*: temps médian < 5 min sur un panel de 10 utilisateurs vs leur baseline personnelle. *Note*: aucune source publique fiable ne donne le temps moyen actuel de création d'annonce — à mesurer en interne avant et après.
- **H2**: Nous croyons qu'afficher une **barre de complétude dynamique** + un **score de confiance d'identification** augmentera la qualité moyenne des fiches. *Mesure cible*: taux de complétude (champs renseignés / champs possibles) > 75 %.
- **H3**: Nous croyons qu'un **pricing transparent avec breakdown** sera plus accepté qu'un pricing ML opaque. *Mesure cible*: taux de validation du prix suggéré par le vendeur > 60 %.
- **H4**: Nous croyons qu'un **pipeline d'identification grounded** (retrieval ancré sur catalogue + VLM validateur) battra un VLM zero-shot pur en précision et en absence d'hallucination. *Mesure cible*: Recall@5 retrieval > 80 % sur un panel de produits réels, taux d'hallucination < 5 % (faux positifs identification mesurés à la main).

## 4. Récquis fonctionnels (in-scope)

> **F0** est le cœur du projet. F1-F7 sont les fonctionnalités produit. F8 est optionnel.

- **F0 — Cœur d'identification grounded photo-first**: pipeline **retrieval-first** qui identifie un produit à partir d'**une ou plusieurs photos (≥ 1 obligatoire — preuve acheteur)** en cherchant son **plus proche voisin** dans un catalogue indexé (~4,5 M items, périmètre **MVP focused 4 cat**). Étapes (v3):
 1. **VLM-extraction** (OpenRouter, mesuré PoC): la photo → titre catalogue probable + attributs observés (marque, couleur, texte/étiquette lisible); le texte vendeur reste un complément optionnel.
 2. Encodage texte (Arctic Embed L v2 frozen) → recherche FAISS HNSW → top-K candidats avec score de confiance. (Recherche multi-vue vision SigLIP = gated sur mesure réelle du domain shift.)
 3. Si ambiguïté (top1-top2 < seuil) → **Akinator**: facettes discriminantes (entropie) pré-remplies par les attributs VLM + guidage de prise de vue (« montrez le dos/l'étiquette »).
 4. **VLM validateur** sur le top-1: « la photo du vendeur montre-t-elle ce produit ? » → garde-fou anti-hallucination (badge de confiance visuelle).
 5. Garde-fous OOD si aucun candidat ne dépasse le seuil → mode dégradé "produit non identifié, saisie assistée".
- **F1 — Classification automatique**: prédire la catégorie L2 du produit avec F1 weighted ≥ 0.90 (mesurable en P04). Plusieurs modèles benchmarkés (k-NN, SVM, RF, MLP) + baseline TF-IDF + fusion adaptive multimodale.
- **F2 — Extraction d'attributs**: peupler marque, modèle, couleur, matière, version depuis la fiche meta du produit identifié, **complétée par observations dirigées** si la fiche ne contient pas l'info (OCR étiquette, code-barres). Pas d'extraction par hallucination VLM.
- **F3 — Génération texte ancrée**: produire titre + description en français vendeur particulier, **ancrés sur les reviews Amazon réelles du produit identifié** (RAG: retrieval des phrases vendeur → augmentation prompt LLM → génération style-cohérente). BLEU-4 ≥ +5 % vs zero-shot mesurable en P07.
- **F4 — Pricing transparent**: prix indicatif **algorithmique** (KNN voisins prix + dépréciation par catégorie + pénalité état + ajustement complétude info) avec **niveau de confiance** et **fourchette explicable**. Pas de ML opaque pour le prix (cf. hors-scope §6).
- **F5 — UI progressive multi-modes**: express (30 s, photo seule + checklist état rapide), assisté (observations ciblées Akinator + guidage prises de vue par type de produit), **batch déménagement « mitrailler »** (queue de N objets photo-first avec persistance navigateur). Les photos du vendeur figurent dans l'annonce finale (+ zoom); visionneuse des photos catalogue sur les candidats.
- **F6 — Garde-fous OOD**: détecter les produits hors-catalogue d'identification et basculer en mode dégradé "produit non reconnu, saisie assistée" plutôt que d'inventer.
- **F7 — Cycle de vie modèle automatisé**: retraining hebdomadaire des classifieurs benchmarks, drift detection sur embeddings et distribution catégorielle, hot-reload du modèle servi sans downtime de l'API.
- **F8 — [OPTIONNEL] Fine-tuning VLM en QLoRA**: à activer **uniquement** si un benchmark montre un gain mesurable > +0.05 F1 macro vs le VLM zero-shot grounded. Non déclenché à ce jour (pas de bénéfice démontré).

## 5. Métriques de succès

| Dimension | Métrique | Seuil cible | Statut |
|-----------|----------|-------------|--------|
| Identification | Recall@5 retrieval (FAISS) | ≥ 0.80 | à mesurer P05 |
| Identification | Hit rate top-1 (avec validation VLM) | ≥ 0.70 | à mesurer P05/P06 |
| Identification | Taux d'hallucination (faux positifs) | < 5 % | à mesurer P06 |
| Classification | F1 weighted (test set) | ≥ 0.90 | à mesurer P04 |
| Génération texte | BLEU-4 vs zero-shot | gain ≥ +5 % | à mesurer P07 |
| Pricing | 4 niveaux de confiance distincts | mécanisme implémenté | à coder P08 |
| Latence | P95 identification end-to-end | < 5 s | à mesurer P10 |
| Démo | `make` sur VM Ubuntu vierge | stack UP en < 15 min | à valider P14 |
| Tests | Couverture pytest | 100 % passent (sans gpu/slow) | maintenu en continu |

## 6. Hors-scope (explicite)

- **Pas de pricing par ML supervisé** — sans données de vente marketplace réelles (historique Rakuten ou équivalent), une régression ML reste un *leurre*. Remplacé par un algo déterministe transparent (dépréciation par catégorie + médiane KNN voisins + pénalité état).
- **Pas de fine-tuning d'un LLM texte pur** (type Qwen3.5-4B local) — gain marginal mesuré en exploration vs LLM frontier + RAG (ordre de +0.06 BLEU pour 8h+ de training), pas rentable. Le **LLM rédacteur grounded** (F3) utilise un modèle frontier en zero-shot avec retrieval, pas de fine-tune.
- **Pas de re-entraînement du vision encoder** (SigLIP est figé, utilisé en feature extractor —) — hors scope d'un projet 3 mois.
- **Pas d'application mobile native** — React responsive web couvre le besoin démo.
- **Pas d'intégration API Rakuten réelle** — projet école, démo locale suffit. Intégration prod hors scope.
- **Pas de support multi-langue à l'UI** — focus français uniquement (mais l'encoder texte est multilingue pour absorber le biais B5 anglais des reviews Amazon).
- **Pas d'authentification utilisateurs réelle** — JWT stub pour la démo. Auth IAM = autre projet.
- **Pas de scraping Rakuten / Vinted / Leboncoin** — risque légal et instable (documente le rejet). On s'appuie sur le dataset public Amazon Reviews 2023 comme catalogue proxy d'identification.
- **Pas de live video stream temps réel** dans le scope nominal — l'UX cible est "stable shot" (capture quand la frame est nette + bien éclairée détectée), pas de tracking continu YOLO. Un cycle dynamique pourra explorer le live video si le projet le justifie après MVP.
- **Pas de fine-tuning VLM dans le scope nominal** — F8 est explicitement optionnel, ne s'active que sur preuve de bénéfice mesurable.
- **Périmètre opérationnel restreint à 4 catégories** — Electronics, Cell_Phones_and_Accessories, Video_Games, Tools_and_Home_Improvement (~4,5 M items meta + ~96 M reviews). Les 11 autres cat de (Clothing, Home, Books, Automotive, Sports, Movies_and_TV, Toys, CDs_and_Vinyl, Baby_Products, Musical_Instruments, Appliances) restent téléchargées dans `data/raw/full/` mais hors-périmètre actif. Justification: focus MVP démontrable, vision via CDN faisable (~3-4 h vs jours), FAISS RAM ~9 GB confortable. Extension à plus de cat = trivial via édition `CATEGORIES` dans `src/data/audit/__init__.py` (single source of truth).

## 7. Contraintes techniques structurantes

- **Hardware fixe**: RTX 4080 16 GB VRAM + 96 GB RAM. Le **catalogue indexé** (26 M items × 1024 dim float16 ≈ 54 GB embeddings) tient en RAM, ce qui rend le retrieval instantané (FAISS HNSW < 10 ms à confirmer en).
- **Soutenance**: à supposer une VM vierge fournie par le jury. La commande `make` doit suffire pour démarrer la stack, pas de manipulation manuelle.
- **Latence perçue**: streaming SSE obligatoire sur le parcours vendeur, pour que l'utilisateur voie les éléments arriver au lieu d'attendre un spinner. Cible P95 < 5 s pour les premiers tokens.
- **Pas de marketplace data réelle**: pricing ML impossible (cf. hors-scope).
- **Délai**: ~3 mois jusqu'à soutenance. Discipline stricte sur l'out-of-scope (dans les du projet).
- **Reproductibilité**: DVC pour les données + MLflow Registry pour les modèles + dvc.lock + seeds fixes. Doit pouvoir tourner identique sur 2 machines.
- **Anti-hallucination par design**: « ancrer avant générer » est la règle structurante du pipeline d'identification.

## 8. Stakeholders

| Rôle | Personne / Entité | Attente principale |
|------|-------------------|---------------------|
| Lead ML moderne | Mathieu Klopp | Pipeline ML SOTA grounded + UX progressive démontrable |
| Lead MLOps + classification baseline | Jean-Baptiste Quéméneur | Infra Bento + Prometheus + Grafana + classifieur classique exploité |
| Mentor externe | Sébastien (Liora) | Architecture défendable, pattern API découplée du modèle, gateway, closed-loop DAG |
| Jury final | DataScientest | Couverture sprints (MLOps complet), démo `make` sur VM, soutenance 20 min + Q&A |
| Utilisateur cible (imaginé) | Vendeur particulier occasionnel | UX < 5 min de création annonce, pas de saisie manuelle inutile, prix transparent, **sentiment de fiabilité** (pas d'invention) |

## 9. Livrables attendus

- **Repo Git** avec branche `main` à jour, démontrable en `make` sur VM vierge, **autonome** (aucune dépendance à un autre repo local).
- **Démo live** parcours vendeur: mode express (1 photo) + mode batch déménagement (N photos) + mode assisté (avec observations dirigées Akinator-backend).
- **Script oral 8 sections + slides** pour soutenance 20 min.
- **Diagramme architecture interactif** (HTML) avec les 8 modèles (M1-M8) + 4 modèles externes (E1-E4) du pipeline (cf. `00_vue_ensemble.md` et `03_classification_benchmark.md`).
- **Modèles** trackés dans MLflow Registry avec alias `@Production`.
- **Datasets versionnés** dans DVC (avec remote local ou MinIO bonus).
- **Documentation interne** complète (9 fichiers canoniques + archive si besoin).
- **Tests pytest** automatisés avec couverture mesurée.
- **Documentation produit**: `PROJECT.md` (cadrage), `00_vue_ensemble.md` (vue système), `03_classification_benchmark.md` (fiche par modèle), `exigences_coverage.md` (matrice cycles × exigences).

---

> **Convention**: ce document tient en 1 page A4 imprimable.
> Si on ajoute une section, on doit en couper une autre.
> Toute révision majeure → nouvelle ADR dans les ADR du projet qui supersede.

---

## Sources

[^1]: [Bigmedia BPI France - 5 chiffres à connaître sur le marché de la seconde main](https://bigmedia.bpifrance.fr/infographies/5-chiffres-a-connaitre-sur-le-marche-de-la-seconde-main)

[^2]: [Wavestone - Seconde main: un marché qui continue son expansion en 2024](https://www.wavestone.com/fr/insight/seconde-main-un-marche-qui-continue-son-expansion-en-2024/)

[^3]: [Républik Retail - Un marché de la seconde main estimé à 14 milliards d'euros en 2023](https://www.republik-retail.fr/rse/seconde-main/pratiques/un-marche-de-la-seconde-main-estime-a-14-milliards-d-euros-en-2023.html)

[^4]: [Cekome - Classement 2025 des sites e-commerce en France](https://www.cekome.com/articles/blog/tendances-digitales-insights/veille-technologique-restez-en-tete-du-digital/classement-2025-des-sites-e-commerce-en-france-amazon-temu-vinted-en-tete/)

[^5]: [Mystudies - Comparaison des plateformes de seconde main entre particuliers](https://www.mystudies.com/fr-ad/blog/decryptage-economique/marche-seconde-main-particuliers-analyse-strategique-comparative-vinted-leboncoin-beebs-vestiaire-collective-13-01-2026.html)

[^6]: [Joseph Torregrossa - Que vendre sur Rakuten en 2025](https://josephtorregrossa.com/blogs/rakuten/que-vendre-sur-rakuten-les-meilleurs-produits-a-proposer-en-2025)

[^7]: [VintyLook - AI Mannequin Vinted](https://vintylook.com/en); [QuickListAI](https://quicklistai.org/vinted-ai-listing-generator/); [Listed AI](https://listedai.app/en/); [SharkScribe](https://sharkscribeai.com/listed-ai-vinted) — exemples d'outils AI commerciaux pour annonces marketplace, validant la demande mais sur Vinted majoritairement.

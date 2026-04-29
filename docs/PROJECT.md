# Rakuten AI — Document de cadrage

> Version 1.0 — 2026-04-29
> Auteur(s) : Mathieu Klopp
> Statut : draft

> Note méthodologique : ce document distingue **chiffres sourcés** (web, études)
> et **hypothèses à valider** (à confirmer par tests utilisateurs ou benchmark).
> Les hypothèses non sourcées seront mesurées plus tard, jamais inventées.

---

## 1. Contexte

Le marché français de la seconde main entre particuliers est en croissance forte. Selon les sources convergentes du secteur, il pèse autour de **7 à 14 milliards d'euros** en 2024 (le delta s'expliquant par le périmètre retenu : textile seul ou tous biens, reconditionné inclus ou non), avec une croissance annuelle de l'ordre de **+15 % au global** et **+8,5 % sur le textile** [^1] [^2]. **Près de 3 Français sur 4** ont acheté un produit d'occasion en 2024 [^3].

Ce marché est dominé en C2C (particulier-à-particulier) par **Vinted** (813,4 M€ de CA en 2024, 17,3 M visiteurs mensuels) sur la mode et **Leboncoin** (~520 M€ de CA, 30 M visiteurs mensuels, 800 000 nouvelles annonces par jour) sur le généraliste [^4] [^5]. **Rakuten France** se positionne sur un créneau hybride (neuf + occasion), avec **55,4 % de ventes en occasion en 2025** sur certaines catégories (en hausse de +5 points vs 2023) [^6]. À noter : un écosystème commercial d'**outils d'IA pour générer des descriptions Vinted** existe déjà (VintyLook, QuickListAI, Listed AI, SharkScribe…) [^7] — donc le besoin est validé par le marché, mais aucun acteur ne semble dominer côté Rakuten.

L'utilisateur cible est **le vendeur particulier occasionnel** : pas un revendeur pro, mais quelqu'un qui veut écouler 1 à 50 objets (déménagement, vide-grenier, garde-robe, héritage). Cette population est **mal servie par les UX actuelles** : choix manuel dans des taxonomies de centaines de catégories, rédaction de titre SEO, écriture de description, recherche du prix marché — autant d'étapes qui demandent une expertise que le particulier n'a pas envie d'acquérir pour vendre 5 objets par an.

## 2. Proposition de valeur

Pour les **vendeurs particuliers occasionnels** (cible : ceux qui mettent en ligne moins de 50 articles par an), qui **butent sur les étapes manuelles de catégorisation, rédaction et estimation prix**, notre solution est une **app web** qui **génère la fiche produit complète (catégorie, attributs, titre, description, prix indicatif) à partir de quelques photos**, contrairement aux **interfaces actuelles** qui demandent au vendeur d'effectuer toutes ces tâches manuellement.

Le différentiateur vs les outils AI existants type VintyLook : **un seul flux end-to-end** (photo → fiche complète) au lieu d'un assistant à insérer dans une boucle Vinted, et un **pricing transparent avec breakdown** plutôt qu'une suggestion opaque.

## 3. Hypothèses-clés

> Ces hypothèses **ne sont pas encore validées**. Elles sont **mesurables** et seront vérifiées par tests utilisateurs ou benchmark.

- **H1** : Nous croyons qu'auto-générer la fiche depuis les photos permettra aux vendeurs particuliers de **réduire significativement le temps de création d'annonce**. *Mesure cible* : temps médian < 5 min sur un panel de 10 utilisateurs vs leur baseline personnelle. *Note* : aucune source publique fiable ne donne le temps moyen actuel de création d'annonce — à mesurer en interne avant et après.
- **H2** : Nous croyons qu'afficher une **barre de complétude dynamique** augmentera la qualité moyenne des fiches. *Mesure cible* : taux de complétude (champs renseignés / champs possibles) > 75 %.
- **H3** : Nous croyons qu'un **pricing transparent avec breakdown** sera plus accepté qu'un pricing ML opaque. *Mesure cible* : taux de validation du prix suggéré par le vendeur > 60 %.
- **H4** : Nous croyons qu'un **VLM fine-tuné** sur le domaine produit-marketplace battra un VLM zero-shot grand public sur l'extraction d'attributs structurés (catégorie, marque, modèle, couleur). *Mesure cible* : F1 macro per-attribute > +0.10 vs baseline Gemini Flash zero-shot.

## 4. Récquis fonctionnels (in-scope)

- **F0 — Cœur multimodal** : entraîner ou fine-tuner un **modèle multimodal vision-langage** (VLM type Qwen2.5-VL ou équivalent) sur des données produits annotées, en QLoRA 4-bit pour tenir sur 16 GB VRAM. C'est **la valeur technique principale** du projet.
- **F1 — Classification automatique** : prédire la catégorie L2 du produit depuis 1 ou plusieurs photos avec F1 weighted ≥ 0.90 (cible mesurable en cours de projet).
- **F2 — Extraction d'attributs visuels** : peupler marque, modèle, couleur, matière, connectivité depuis les photos avec un taux d'hallucination borné.
- **F3 — Génération texte ancrée** : produire titre + description en français vendeur particulier, ancrés sur des annonces voisines réelles (RAG), pour réduire l'hallucination.
- **F4 — Pricing transparent** : prix indicatif avec **niveau de confiance** et **fourchette explicable** selon la complétude des informations fournies.
- **F5 — UI progressive multi-modes** : express (30 s, photo seule), assisté (avec quelques questions ciblées), batch déménagement (queue de N photos avec persistance navigateur).
- **F6 — Garde-fous OOD** : détecter les produits hors-catalogue d'entraînement et basculer en mode dégradé "produit non reconnu" plutôt que d'inventer.
- **F7 — Cycle de vie modèle automatisé** : retraining hebdomadaire, drift detection, hot-reload du modèle servi sans downtime de l'API.

## 5. Métriques de succès

| Dimension | Métrique | Seuil cible | Statut |
|-----------|----------|-------------|--------|
| Classification | F1 weighted (test set) | ≥ 0.90 | à mesurer P04 |
| VLM extraction | Parse rate JSON valide | ≥ 95 % | à mesurer P06 |
| VLM extraction | F1 macro per-attribute | > +0.10 vs zero-shot | à mesurer P06 |
| Génération texte | BLEU-4 vs zero-shot | gain ≥ +5 % | à mesurer P07 |
| Pricing | 4 niveaux de confiance distincts | mécanisme implémenté | à coder P08 |
| Démo | `make` sur VM Ubuntu vierge | stack UP en < 15 min | à valider P14 |
| Tests | Couverture pytest | 100 % passent (sans gpu/slow) | maintenu en continu |

## 6. Hors-scope (explicite)

- **Pas de pricing par ML supervisé** — sans données de vente marketplace réelles (historique Rakuten ou équivalent), une régression ML reste un *leurre* : on a constaté lors d'une exploration v2 qu'un XGBoost atteignait MAPE ~38 % vs cible 20 %, plafond imposé par l'absence de signal véritable. Remplacé par un algo déterministe transparent (dépréciation par catégorie + médiane KNN voisins + pénalité état).
- **Pas de fine-tuning d'un LLM texte pur** (type Qwen3.5-4B local) — gain marginal mesuré en exploration vs Gemini Flash + RAG (ordre de +0.06 BLEU pour 8h+ de training), pas rentable. Le **VLM**, lui, est in-scope (F0).
- **Pas de re-entraînement du vision encoder** (SigLIP est figé, utilisé en feature extractor) — hors scope d'un projet 3 mois.
- **Pas d'application mobile native** — React responsive web couvre le besoin démo.
- **Pas d'intégration API Rakuten réelle** — projet école, démo locale suffit. Intégration prod hors scope.
- **Pas de support multi-langue** — focus français uniquement.
- **Pas d'authentification utilisateurs réelle** — JWT stub pour la démo. Auth IAM = autre projet.
- **Pas de scraping Rakuten** — risque légal et instable. On s'appuie sur un dataset public proxy (à choisir en P02 selon disponibilité : Amazon Reviews, eBay scrapes publics, datasets HuggingFace dédiés…).

## 7. Contraintes techniques structurantes

- **Hardware fixe** : RTX 4080 16 GB VRAM. Tout doit tenir → quantization 4-bit (NF4 / bitsandbytes) obligatoire pour VLM 7B+.
- **Soutenance** : à supposer une VM vierge fournie par le jury. La commande `make` doit suffire pour démarrer la stack, pas de manipulation manuelle.
- **Latence perçue** : streaming SSE obligatoire sur le parcours vendeur, pour que l'utilisateur voie les éléments arriver au lieu d'attendre un spinner. Cible P95 < 5 s pour les premiers tokens.
- **Pas de marketplace data réelle** : pricing ML impossible (cf. hors-scope).
- **Délai** : ~3 mois jusqu'à soutenance. Discipline stricte sur l'out-of-scope (R16 dans `BRAIN/golden_rules.md`).
- **Reproductibilité** : DVC pour les données + MLflow Registry pour les modèles + dvc.lock + seeds fixes. Doit pouvoir tourner identique sur 2 machines.

## 8. Stakeholders

| Rôle | Personne / Entité | Attente principale |
|------|-------------------|---------------------|
| Lead ML moderne | Mathieu Klopp | Pipeline ML SOTA + UX progressive démontrable |
| Lead MLOps + classification baseline | Jean-Baptiste Quéméneur | Infra Bento + Prometheus + Grafana + classifieur classique exploité |
| Mentor externe | Sébastien (Liora) | Architecture défendable, pattern API découplée du modèle, gateway, closed-loop DAG |
| Jury final | DataScientest | Couverture sprints 17-20 (MLOps complet), démo `make` sur VM, soutenance 20 min + Q&A |
| Utilisateur cible (imaginé) | Vendeur particulier occasionnel | UX < 5 min de création annonce, pas de saisie manuelle inutile, prix transparent |

## 9. Livrables attendus

- **Repo Git public ou privé** avec branche `main` à jour, démontrable en `make` sur VM vierge
- **Démo live** parcours vendeur : mode express (1 photo) + mode batch déménagement (N photos)
- **Script oral 8 sections + slides** pour soutenance 20 min
- **Diagramme architecture interactif** (HTML)
- **Modèles fine-tunés** trackés dans MLflow Registry avec alias `@Production`
- **Datasets versionnés** dans DVC (avec remote local ou MinIO bonus)
- **Documentation BRAIN/** complète (9 fichiers canoniques + blocs techniques)
- **Tests pytest** automatisés avec couverture mesurée

---

> **Convention** : ce document tient en 1 page A4 imprimable.
> Si on ajoute une section, on doit en couper une autre.
> Toute révision majeure → nouveau document, l'ancien marqué `superseded`.

---

## Sources

[^1]: [Bigmedia BPI France - 5 chiffres à connaître sur le marché de la seconde main](https://bigmedia.bpifrance.fr/infographies/5-chiffres-a-connaitre-sur-le-marche-de-la-seconde-main)

[^2]: [Wavestone - Seconde main : un marché qui continue son expansion en 2024](https://www.wavestone.com/fr/insight/seconde-main-un-marche-qui-continue-son-expansion-en-2024/)

[^3]: [Républik Retail - Un marché de la seconde main estimé à 14 milliards d'euros en 2023](https://www.republik-retail.fr/rse/seconde-main/pratiques/un-marche-de-la-seconde-main-estime-a-14-milliards-d-euros-en-2023.html)

[^4]: [Cekome - Classement 2025 des sites e-commerce en France](https://www.cekome.com/articles/blog/tendances-digitales-insights/veille-technologique-restez-en-tete-du-digital/classement-2025-des-sites-e-commerce-en-france-amazon-temu-vinted-en-tete/)

[^5]: [Mystudies - Comparaison des plateformes de seconde main entre particuliers](https://www.mystudies.com/fr-ad/blog/decryptage-economique/marche-seconde-main-particuliers-analyse-strategique-comparative-vinted-leboncoin-beebs-vestiaire-collective-13-01-2026.html)

[^6]: [Joseph Torregrossa - Que vendre sur Rakuten en 2025](https://josephtorregrossa.com/blogs/rakuten/que-vendre-sur-rakuten-les-meilleurs-produits-a-proposer-en-2025)

[^7]: [VintyLook - AI Mannequin Vinted](https://vintylook.com/en) ; [QuickListAI](https://quicklistai.org/vinted-ai-listing-generator/) ; [Listed AI](https://listedai.app/en/) ; [SharkScribe](https://sharkscribeai.com/listed-ai-vinted) — exemples d'outils AI commerciaux pour annonces marketplace, validant la demande mais sur Vinted majoritairement.

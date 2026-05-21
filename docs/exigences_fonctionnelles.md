# Couverture fonctionnelle F0-F8 — état réel

> Version 1.0 — 2026-05-21
> Statut : **matrice de traçabilité exigence → cycle → état RÉEL → gap**.
> Ce document manquait au BRAIN (cf. ADR D-018) : `exigences_coverage.md` traçait
> les *cours* DataScientest, pas les *exigences produit* F0-F8 de `PROJECT.md`.
> C'est ICI qu'on vérifie "est-ce qu'on construit le bon MVP ?".

Légende état : ✅ conforme · 🟡 partiel · 🔴 cassé/manquant · ⚪ non démarré · ⏸️ différé (ADR)

## Matrice F0-F8

| Réq | Intention (PROJECT.md) | Cycle(s) | État réel | Gap mesuré |
|---|---|---|---|---|
| **F0** Identification grounded | photo→retrieval→Akinator→VLM validateur | 2,4,5,9 | ✅ conforme (text-only) | retrieval ✅ + Akinator multi-facette ✅ (F2). VLM validateur E3 **gated vision** : en text-only il n'y a pas d'image user à valider → revient avec SigLIP (D-014). |
| **F1** Classification **L2** | sous-catégorie, F1≥0.90 | 3 | ✅ conforme (via grounding) | L1 classifieurs M1-M6 (F1_w=0.954, garde-fou) **+** catégorie fine réelle du produit identifié surface (breadcrumb `categories` → ex "Graphics Cards"). Résolu D-018 : pas de classifieur L2 séparé, on a le produit exact. |
| **F2** Extraction attributs + Akinator | marque/modèle/couleur/version + obs. dirigées | 4 | ✅ conforme (text-only) | **Akinator multi-facette par entropie** (D-019) : attributs curés (brand, color, capacity, size, material, form_factor, style, feature, compatible_with) extraits de `details` (74% coverage). Le frontend choisit la facette **la plus discriminante** (entropie×couverture) → narrowing multi-étapes. Obs. photo/OCR = couche future (vision D-014). |
| **F3** Génération ancrée | RAG sur données réelles du produit | 6,9 | ✅ conforme (description) | Gemma ancré sur la **description catalogue réelle** (paragraphes → top-N phrases grounding). Validé : "Snapdragon 732G" vient du grounding, pas du titre ni de la mémoire LLM. Grounding sur **reviews** (vs description) = enhancement futur (join raw). |
| **F4** Pricing transparent KNN | KNN voisins prix + dépréciation + état | 7,9 | ✅ conforme | `/price` reçoit `parent_asin` + `catalog_price` (L1) + `neighbor_prices` (L2). **RTX 4080 = 589€** (était 12€). Reste : conversion USD→EUR à raffiner (mineur). |
| **F5** UI multi-modes | express / assisté / batch | 10 | 🟡 partiel | express ✅ ; **assisté (boucle Akinator) non câblé** ; batch ⏸️ (D-016, dépend vision) |
| **F6** Garde-fous OOD | seuil + mode dégradé | 4,9 | ✅ conforme | 3 niveaux confiance D-017, candidats toujours montrés |
| **F7** Cycle de vie auto | retrain + drift + hot-reload | 11-14 | 🟡 partiel | MLflow tracking **LIVE** (instrumentation dans chaque script, D-021) + Registry `@Production=M5` + reload testé ✅ (C11). DVC DAG validé (lock→C13). Retrain Airflow (C12) + drift Evidently (C14) + câblage hot-reload API à venir. |
| **F8** Fine-tuning VLM QLoRA | OPTIONNEL si gain >+0.05 | 5.2 | ⏸️ conditionnel | non déclenché (pas de preuve de bénéfice) |

## Verdict synthétique (mis à jour 2026-05-21)

**Cœur F0-F4 = ✅ conforme en text-only.** F0 (retrieval+Akinator), F1 (cat fine), F2 (Akinator multi-facette entropie), F3 (grounding description), F4 (pricing réel), F6 (OOD 3-niveaux) — tous conformes. Restent **gated vision** (D-014) : la branche photo de F0 (entrée image + VLM validateur E3) et l'observation-photo Akinator. F5 mode assisté = le filtre facette (boucle de narrowing) fait office d'assisté text-only ; batch ⏸️ (D-016).

**Racine commune** des gaps initiaux F1/F2/F3 = **D-006 a droppé les colonnes riches** (`images`, `details`, `categories`, `description`) au cleaning. Remédiés par **lookups depuis raw meta** (`product_lookup.parquet` : image + cat fine + brand + facettes) + re-chargement `description` (déjà dans processed). Pattern validé, sans re-matérialiser le join lourd.

## Reste à faire (ordre)

Cœur F0-F4 text-only conforme + F7 (MLOps tracking) entamé (C11 ✅). Suite :
- **Cycle 12-15** : Airflow/BentoML (retrain, closed-loop) → Docker → Observabilité (drift Evidently, rembourse R6) → Prod (JWT, CI/CD, soutenance).
- **Vision (post-MVP D-014)** : réactive entrée photo → branche vision F0 + VLM validateur E3 + observation-photo Akinator + batch F5.
- Enhancements mineurs : grounding reviews (vs description), conversion USD→EUR, normalisation casse marques.

## Maintenance

Mis à jour à chaque RESTIT de cycle touchant une exigence. `exigences_coverage.md` (cours) et `modeles.md` sont à re-synchroniser (statuts périmés, dette RESTIT identifiée 2026-05-21).

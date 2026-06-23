# Couverture fonctionnelle F0-F8 — état réel

> Version 2.0 — 2026-06-13 (resync photo-first,.4; v1.0 text-only)
> Statut: **matrice de traçabilité exigence → cycle → état RÉEL → gap**.
> Ce document manquait à la mémoire projet: `exigences_coverage.md` traçait
> les *cours* DataScientest, pas les *exigences produit* F0-F8 de `PROJECT.md`.
> C'est ICI qu'on vérifie "est-ce qu'on construit le bon MVP ?".

Légende état: ✅ conforme · 🟡 partiel · 🔴 cassé/manquant · ⚪ non démarré · ⏸️ différé (ADR)

## Matrice F0-F8

| Réq | Intention (PROJECT.md) | Cycle(s) | État réel | Gap mesuré |
|---|---|---|---|---|
| **F0** Identification grounded | photo→retrieval→Akinator→VLM validateur | 2,4,5,9,**17** | ✅ conforme (**photo-first**) | **Entrée photo LIVE**: upload → VLM-extraction (Gemma lit la photo → titre+attributs) → retrieval grounded. **VLM validateur F0.4 LIVE** (photo user × image catalogue → match/confidence/reason). Reste **gated**: indexation visuelle SigLIP du catalogue (image→image direct). |
| **F1** Classification **L2** | sous-catégorie, F1≥0.90 | 3 | ✅ conforme (via grounding) | L1 classifieurs M1-M6 (F1_w=0.954, garde-fou) **+** catégorie fine réelle du produit identifié surface (breadcrumb `category_path` → ex "Graphics Cards"). Résolu: pas de classifieur L2 séparé, on a le produit exact. |
| **F2** Extraction attributs + Akinator | marque/modèle/couleur/version + obs. dirigées | 4,**17** | ✅ conforme (**photo-first**) | **Akinator multi-facette par entropie**: attributs curés extraits de `details` (74% coverage), facette la plus discriminante (entropie×couverture). **Obs. photo LIVE**: la VLM-extraction pré-remplit les attributs observés depuis la photo + checklist état guidée par type d'objet. |
| **F3** Génération ancrée | RAG sur données réelles du produit | 6,9 | ✅ conforme (description) | Gemma ancré sur la **description catalogue réelle** (paragraphes → top-N phrases grounding). Validé: "Snapdragon 732G" vient du grounding, pas du titre ni de la mémoire LLM. Grounding sur **reviews** (vs description) = enhancement futur (join raw). |
| **F4** Pricing transparent KNN | KNN voisins prix + dépréciation + état | 7,9 | ✅ conforme | `/price` reçoit `parent_asin` + `catalog_price` (L1) + `neighbor_prices` (L2). **Conversion USD→EUR résolue** (taux fixe 0.92 env-overridable, explications double-devise). |
| **F5** UI multi-modes | express / assisté / batch | 10,**17** | ✅ conforme | express ✅; assisté = filtre facette Akinator + checklist état guidée ✅; **batch « mitrailler » ✅** (mode 📦 Déménagement) |
| **F6** Garde-fous OOD | seuil + mode dégradé | 4,9 | ✅ conforme | 3 niveaux confiance, candidats toujours montrés |
| **F7** Cycle de vie auto | retrain + drift + hot-reload | 11-14 | ✅ conforme | MLflow tracking + Registry `@Production` + reload testé; DVC DAG; **retrain Airflow boucle fermée** (retrains réels → v4/v5); **drift Evidently**. Hot-reload API = enhancement futur. |
| **F8** Fine-tuning VLM QLoRA | OPTIONNEL si gain >+0.05 | 5.2 | ⏸️ conditionnel | non déclenché (pas de preuve de bénéfice — anti-sur-ingénierie) |

## Verdict synthétique (mis à jour 2026-06-13)

**F0-F7 = ✅ conforme, pipeline photo-first complet.** Le recadrage a réactivé l'entrée photo érodée par les différés: F0 (entrée photo via VLM-extraction + retrieval grounded + VLM validateur F0.4 LIVE), F1 (cat fine), F2 (Akinator multi-facette + observation photo), F3 (grounding description), F4 (pricing réel + USD→EUR), F5 (express + assisté + **batch mitrailler**), F6 (OOD 3-niveaux), F7 (MLOps boucle fermée Airflow + drift Evidently). **Seuls différés assumés**: indexation visuelle SigLIP du catalogue (GO/NO-GO) et fine-tuning QLoRA F8 (conditionnel à un gain mesuré).

**Racine commune** des gaps initiaux F1/F2/F3 = ** a droppé les colonnes riches** (`images`, `details`, `categories`, `description`) au cleaning. Remédiés par **lookups depuis raw meta** (`product_lookup.parquet`: images multi-vues + `category_path` breadcrumb + brand + facettes) + re-chargement `description`. Pattern validé, sans re-matérialiser le join lourd.

## Reste à faire (ordre)

Cœur F0-F7 conforme photo-first. Suite:
- **Test SigLIP gated** (1 nuit): décide GO/NO-GO sur l'indexation visuelle du catalogue complet — par mesure, pas intuition.
- **F8 QLoRA**: à déclencher uniquement si un benchmark montre un gain > +0.05 F1 macro vs zero-shot grounded.
- Enhancements mineurs: grounding reviews (vs description), hot-reload modèle dans l'API, normalisation casse marques.

## Maintenance

Mis à jour à chaque RESTIT de cycle touchant une exigence. `exigences_coverage.md` (cours) et `modeles.md` à re-synchroniser si statuts périmés.

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
| **F0** Identification grounded | photo→retrieval→Akinator→VLM validateur | 2,4,5,9 | 🟡 partiel | retrieval ✅ (text-only D-014) ; **VLM validateur E3 = mock, pas câblé** ; **Akinator superficiel** (attributs droppés D-006) |
| **F1** Classification **L2** | sous-catégorie, F1≥0.90 | 3 | ✅ conforme (via grounding) | L1 classifieurs M1-M6 (F1_w=0.954, garde-fou) **+** catégorie fine réelle du produit identifié surface (breadcrumb `categories` → ex "Graphics Cards"). Résolu D-018 : pas de classifieur L2 séparé, on a le produit exact. |
| **F2** Extraction attributs | marque/modèle/couleur/version + obs. dirigées | 4 | 🔴 manquant | attributs riches **droppés au cleaning (D-006)** → ni extraction, ni Akinator discriminant |
| **F3** Génération ancrée reviews | RAG sur reviews réelles du produit | 6,9 | 🟡 partiel | Gemma génère depuis **meta produit**, **PAS depuis reviews réelles** (`reviews_index` sans colonne `text`) |
| **F4** Pricing transparent KNN | KNN voisins prix + dépréciation + état | 7,9 | ✅ conforme | `/price` reçoit `parent_asin` + `catalog_price` (L1) + `neighbor_prices` (L2). **RTX 4080 = 589€** (était 12€). Reste : conversion USD→EUR à raffiner (mineur). |
| **F5** UI multi-modes | express / assisté / batch | 10 | 🟡 partiel | express ✅ ; **assisté (boucle Akinator) non câblé** ; batch ⏸️ (D-016, dépend vision) |
| **F6** Garde-fous OOD | seuil + mode dégradé | 4,9 | ✅ conforme | 3 niveaux confiance D-017, candidats toujours montrés |
| **F7** Cycle de vie auto | retrain + drift + hot-reload | 11-14 | ⚪ non démarré | cycles MLOps à venir |
| **F8** Fine-tuning VLM QLoRA | OPTIONNEL si gain >+0.05 | 5.2 | ⏸️ conditionnel | non déclenché (pas de preuve de bénéfice) |

## Verdict synthétique

**Cœur F0-F4 = ~50% conforme.** Ce qui marche : F6 (OOD), F0 retrieval, F3 génération (partielle). Ce qui cloche : **F4 cassé (wiring)**, **F1 écart L1/L2**, **F2 manquant**, **F0.3 Akinator superficiel**, **F3 grounding reviews**.

**Racine commune** des gaps F1/F2/F0.3/F3 = **D-006 a droppé les colonnes riches** (`images`, `details`, `features`, `categories`) au cleaning. On vient de prouver le pattern de remédiation avec `images_lookup.parquet` (Cycle 10.x) : re-exposer les colonnes nécessaires via des lookups depuis la raw meta, sans re-matérialiser le join lourd.

## Priorité dérivée (R13 zéro-dette + "F0 est le cœur")

R13 interdit d'avancer (Cycle 11 MLOps) tant que les artefacts du cœur sont cassés. Ordre dérivé **sans arbitrage humain** (de la spec, pas d'une préférence) :

1. **F4 pricing wiring** 🔴 — `/price` reçoit `parent_asin` → L1 prix catalogue réel + L2 KNN voisins. Quick + impact max.
2. **F1 catégorie fine** 🔴 — lookup `parent_asin → main_category` (raw meta) → afficher la vraie sous-cat. Aligne F1 via l'architecture grounded (pas de classifieur L2 à entraîner : on a le produit exact).
3. **F2 + F0.3 Akinator attributs** 🔴 — lookup `details/features` → Akinator compare attributs réels + observation ciblée + boucle re-score (mode assisté F5).
4. **F3 grounding reviews** 🟡 — lazy join raw reviews → RAG sur avis réels.
5. **F0 VLM validateur E3** 🟡 — OpenRouter Gemini Vision réel (on a la clé) en validateur top-1.

Une fois F0-F4 conformes → reprise ordre normal (Cycle 11 MLOps).

## Maintenance

Mis à jour à chaque RESTIT de cycle touchant une exigence. `exigences_coverage.md` (cours) et `modeles.md` sont à re-synchroniser (statuts périmés, dette RESTIT identifiée 2026-05-21).

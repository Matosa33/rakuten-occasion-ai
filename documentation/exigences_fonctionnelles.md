# Couverture fonctionnelle F0-F8 — état réel

> Matrice de traçabilité : pour chaque exigence **produit** (F0 à F8 définies dans
> [PROJECT.md](PROJECT.md)), on indique **l'état réellement livré** et le **gap** éventuel.
> C'est ici qu'on vérifie « est-ce qu'on construit le bon produit ? » (la couverture
> *technique* vs les 4 phases est dans [exigences_coverage.md](exigences_coverage.md)).

Légende : ✅ conforme · 🟡 partiel · 🔴 manquant · ⏸️ différé (décision assumée)

## Matrice F0-F8

| Réq | Intention | État réel | Gap mesuré |
|---|---|---|---|
| **F0** Identification ancrée | photo → retrieval → Akinator → validateur VLM | ✅ conforme (**photo-first**) | Entrée photo **en direct** : upload → extraction VLM (Gemma lit la photo → titre + attributs) → retrieval ancré. Validateur VLM **en direct** (photo vendeur × image catalogue → match / confiance / raison). Reste différé : indexation visuelle directe du catalogue (image → image). |
| **F1** Classification fine | sous-catégorie, F1 ≥ 0,90 | ✅ conforme | Classifieurs M1-M6 (F1 pondéré 0,954) **+** catégorie fine réelle du produit identifié (fil d'Ariane `category_path`, ex. « Graphics Cards »). Pas besoin d'un classifieur de second niveau séparé : on a le produit exact. |
| **F2** Attributs + Akinator | marque / modèle / couleur / version + observations dirigées | ✅ conforme | Akinator multi-facette par **entropie** (attributs curés depuis `details`, ~74 % de couverture, facette la plus discriminante). Les attributs visibles sont pré-remplis depuis la photo (extraction VLM) + checklist d'état guidée par type d'objet. |
| **F3** Génération ancrée | RAG sur les données réelles du produit | ✅ conforme | Gemma ancré sur la **description catalogue réelle** (phrases de grounding sélectionnées). Preuve : « Snapdragon 732G » vient du grounding, pas de la mémoire du LLM. Ancrage sur les *avis* (en plus de la description) = amélioration future. |
| **F4** Pricing transparent | k-NN des prix voisins + dépréciation + état | ✅ conforme | `/price` reçoit le prix catalogue (L1) et les prix voisins (L2). Conversion USD → EUR (taux 0,92 surchargeable) + explication double-devise. |
| **F5** UI multi-modes | express / assisté / lot | ✅ conforme | Express ✅ ; assisté (facette Akinator + checklist d'état) ✅ ; **mode « mitraillage »** 📦 Déménagement ✅. |
| **F6** Garde-fous OOD | seuil + mode dégradé | ✅ conforme | 3 niveaux de confiance, candidats **toujours** montrés (l'humain valide). |
| **F7** Cycle de vie auto | ré-entraînement + dérive + rechargement | ✅ conforme | MLflow (tracking + Registry `@Production`) ; DVC ; **ré-entraînement Airflow en boucle fermée** (retrains réels → v3-v5) ; **dérive Evidently**. Rechargement à chaud de l'API = amélioration future. |
| **F8** Fine-tuning VLM (QLoRA) | optionnel si gain > +0,05 | ⏸️ conditionnel | Non déclenché : pas de preuve de bénéfice mesuré (anti sur-ingénierie). |

## Verdict synthétique

**F0-F7 = ✅ conforme, pipeline photo-first complet.** L'entrée photo est pleinement active :
F0 (extraction VLM + retrieval ancré + validateur VLM), F1 (catégorie fine), F2 (Akinator
multi-facette + observation par la photo), F3 (grounding sur la description), F4 (pricing réel +
conversion devise), F5 (express + assisté + **mitraillage**), F6 (OOD 3 niveaux), F7 (boucle MLOps
fermée Airflow + dérive Evidently). **Seuls différés assumés** : indexation visuelle directe du
catalogue (SigLIP, sous décision GO/NO-GO) et fine-tuning QLoRA (F8, conditionné à un gain mesuré).

**Origine des gaps initiaux F1/F2/F3** : le nettoyage initial avait écarté les colonnes riches
(`images`, `details`, `categories`, `description`). Corrigé par des **tables de correspondance
reconstruites depuis les métadonnées brutes** (`product_lookup.parquet` : vues multiples +
fil d'Ariane catégorie + marque + facettes) et le rechargement de `description` — sans
re-matérialiser la jointure lourde.

## Reste à faire

Le cœur F0-F7 est conforme. Suite :
- **Test SigLIP différé** (≈ 1 nuit de calcul) : décider GO/NO-GO sur l'indexation visuelle du
  catalogue complet — par la mesure, pas par intuition.
- **F8 (QLoRA)** : à déclencher uniquement si un benchmark montre un gain > +0,05 de F1 macro
  face au zero-shot ancré.
- Améliorations mineures : grounding sur les avis (vs description), rechargement à chaud du
  modèle dans l'API, normalisation de la casse des marques.

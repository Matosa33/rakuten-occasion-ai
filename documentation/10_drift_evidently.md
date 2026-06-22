# 10 — Détection de dérive (drift) avec Evidently

> Surveiller si les données d'aujourd'hui **ressemblent encore** à celles sur lesquelles le
> modèle a appris. Si elles dérivent, le modèle « vieillit » → il faut ré-entraîner.

---

## 1. La technologie : qu'est-ce que c'est ?

La **dérive (drift)** = les données reçues en production **changent de distribution** par
rapport à celles d'entraînement (nouveaux produits, nouveau vocabulaire, nouvelles
proportions de catégories…). Conséquence : le modèle, entraîné sur « l'ancien monde »,
devient peu à peu moins juste — **sans erreur visible**, juste une lente baisse de qualité.

**Evidently** est une bibliothèque qui compare deux jeux de données (référence vs actuel) et
produit un **rapport visuel** disant quelles colonnes ont dérivé et de combien.

---

## 2. État de l'art

- On détecte la dérive en comparant les **distributions** (référence vs production) avec :
  - **PSI** (*Population Stability Index*) : > 0,25 = dérive significative (souvent seuil 0,2),
  - **test de Kolmogorov-Smirnov**, **Chi-deux**, divergence de **Jensen-Shannon**.
- **Bonnes pratiques** :
  - **logguer une référence** (distributions de base) au déploiement,
  - **seuils quantitatifs** + **déclencher un ré-entraînement** au-delà de la tolérance,
  - intégrer la détection **dès la conception** (pas en après-coup).
- **Evidently** offre 20+ méthodes prêtes + visualisations interactives.

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Détection | `src/monitoring/drift_detection.py` | Evidently `DataDriftPreset` (référence vs actuel) → rapport HTML |
| Métriques | `src/monitoring/push_metrics.py` | pousse les scores de drift au **Pushgateway** Prometheus |
| Orchestration | `infra/airflow/dags/rakuten_drift_check_dag.py` | vérifie la dérive ; peut déclencher `rakuten_retrain` |
| Visualisation | `monitoring/grafana/dashboards/evidently_drift.json` | dashboard Grafana de la dérive |

Logique : on compare un jeu **référence** (un split) à un jeu **actuel**. Si la **part de
features ayant dérivé dépasse le seuil** (`DRIFT_SHARE_THRESHOLD = 0,5`, soit ≥ 50 % des
features), on **déclare la dérive** → le DAG drift peut déclencher le ré-entraînement.
Le rapport HTML détaillé est écrit dans `monitoring/evidently/reports/`.

C'est la **brique qui ferme la boucle** : drift détecté → ré-entraînement (cf. thème Airflow).

---

## 4. Résultats (mesurés)

- **Rapport Evidently réel** généré : `monitoring/evidently/reports/drift_latest.html`
  (~3,8 Mo) — un vrai rapport visuel interactif, pas un placeholder.
- **Seuil de décision** explicite (≥ 50 % de features driftées → alerte).
- **Câblage drift → retrain** présent (DAG dédié) + **scores poussés** vers Prometheus
  (Pushgateway) → visibles dans Grafana.
- Tests : `test_drift_detection.py`, `test_drift_check_dag.py`, `test_push_metrics.py`.

> 📊 **Chiffres slide** : « détection Evidently (DataDriftPreset) », « seuil 50 % de features
> driftées → ré-entraînement », « drift → Pushgateway → Grafana ». 📸 **Capture** : le rapport
> HTML Evidently (`drift_latest.html`, les barres de drift par feature) + le dashboard Grafana
> de drift. **Très visuel = excellent pour une slide.**

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Outil standard (Evidently)** + rapport visuel réel.
- ✅ **Seuil quantitatif** + **déclenchement de ré-entraînement** → exactement la bonne pratique
  « détecter puis agir ».
- ✅ **Intégré dès la conception** (DAG dédié, métriques poussées, dashboard) — pas un après-coup.
- ✅ Tests présents.

**Limites assumées :**
- **Seuil sur la *part* de features driftées** (50 %) plutôt qu'un **PSI par feature** finement
  réglé — plus simple, mais moins granulaire que l'état de l'art (PSI > 0,2 par variable).
- **Référence figée** (un split) : la bonne pratique est une **référence mise à jour** (fenêtre
  glissante) — non fait.
- **Drift de données seulement**, pas de **drift de concept** (la relation entrée→sortie qui
  change) ni de suivi de la **performance réelle** en prod (faute de retours terrain).
- **Déclenchement auto** drift→retrain : le câblage existe mais reste à confirmer de bout en
  bout en conditions réelles.

---

## 6. Références
- Evidently AI — *What is data drift in ML* — https://www.evidentlyai.com/ml-in-production/data-drift
- Evidently AI — *Comparing 5 drift detection methods on large datasets* — https://www.evidentlyai.com/blog/data-drift-detection-large-datasets
- DataCamp — *Understanding data drift and model drift* — https://www.datacamp.com/tutorial/understanding-data-drift-model-drift
- MachineLearningMastery — *Detecting & handling data drift in production* — https://machinelearningmastery.com/detecting-handling-data-drift-in-production/
- IBM — *What is model drift?* — https://www.ibm.com/think/topics/model-drift

---

### En une phrase (pour la défense)
*« On surveille la dérive des données avec Evidently : un rapport visuel compare la référence à
l'actuel, et si trop de features ont dérivé, on déclenche le ré-entraînement. C'est intégré
dès la conception (DAG dédié, scores poussés vers Grafana) — la brique qui ferme la boucle de
vie du modèle. »*

# 10 — Détection de dérive (drift) avec Evidently

> Surveiller si les données d'aujourd'hui **ressemblent encore** à celles sur lesquelles le
> modèle a appris. Si elles dérivent, le modèle « vieillit » → il faut ré-entraîner. C'est la
> brique qui **ferme la boucle** de vie.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
La **dérive (drift)** = les données reçues en production **changent de distribution** par rapport
à celles d'entraînement (nouveaux produits, nouveau vocabulaire, nouvelles proportions de
catégories…). Conséquence sournoise: le modèle, entraîné sur « l'ancien monde », devient peu à
peu **moins juste — sans erreur visible**, juste une lente baisse de qualité.

**Evidently** compare deux jeux de données (**référence** vs **actuel**) et produit un **rapport
visuel**: quelles colonnes ont dérivé, et de combien.

### Pour l'expert
- On compare des **distributions** (pas des valeurs individuelles) via des tests statistiques:
 **PSI** (*Population Stability Index*), **Kolmogorov-Smirnov**, **Chi-deux**, divergence de
 **Jensen-Shannon**. Seuil usuel PSI > 0,2-0,25 = dérive significative.
- **Drift de données** (l'entrée change) ≠ **drift de concept** (la relation entrée→sortie
 change). On traite le premier.
- La détection doit **déclencher une action** (ré-entraînement), pas juste alerter.

---

## 2. État de l'art

- Détecter via PSI / KS / Chi²; **logguer une référence** (distributions de base) au déploiement.
- **Seuils quantitatifs** + **déclencher un ré-entraînement** au-delà de la tolérance.
- Suivre PSI / Jensen-Shannon en plus de l'accuracy (qui peut masquer une dérive).
- **Intégrer dès la conception**, pas en après-coup. Evidently offre 20+ méthodes + visualisations.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

| Brique | Fichier | Rôle |
|---|---|---|
| Détection | `src/monitoring/drift_detection.py` | Evidently **`DataDriftPreset`** (référence vs actuel) → rapport HTML |
| Métriques | `src/monitoring/push_metrics.py` | pousse les scores de drift au **Pushgateway** Prometheus |
| Orchestration | `infra/airflow/dags/rakuten_drift_check_dag.py` | vérifie la dérive; peut déclencher `rakuten_retrain` |
| Visualisation | `monitoring/grafana/dashboards/evidently_drift.json` | dashboard Grafana de la dérive |

Logique exacte: on compare un jeu **référence** (un split) à un jeu **actuel** via le
`DataDriftPreset` d'Evidently. Si la **part de features ayant dérivé dépasse le seuil**
(**`DRIFT_SHARE_THRESHOLD = 0,5`**, soit ≥ 50 % des features), on **déclare la dérive** → le DAG
drift peut déclencher le ré-entraînement. Le rapport HTML détaillé est écrit dans
`monitoring/evidently/reports/`. C'est ce qui **ferme la boucle**: drift → retrain (cf. *Airflow*).

---

## 4. Résultats (mesurés)

- **Rapport Evidently réel**: `monitoring/evidently/reports/drift_latest.html` (~**3,8 Mo**) —
 un vrai rapport visuel interactif, pas un placeholder.
- **Seuil de décision** explicite (≥ 50 % de features driftées → alerte).
- **Câblage drift → retrain** présent (DAG dédié) + **scores poussés** vers Prometheus
 (Pushgateway) → visibles dans Grafana.
- Tests: `test_drift_detection.py`, `test_drift_check_dag.py`, `test_push_metrics.py`.

> 📊 **Chiffres slide**: « détection Evidently (`DataDriftPreset`) », « seuil 50 % de features
> driftées → ré-entraînement », « drift → Pushgateway → Grafana ». 📸 **Capture**: le rapport
> HTML Evidently (`drift_latest.html`, barres de drift par feature) + le dashboard Grafana de
> drift. **Très visuel = excellent pour une slide.**

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Outil standard (Evidently)** + rapport visuel réel.
- ✅ **Seuil quantitatif** + **déclenchement de ré-entraînement** → bonne pratique « détecter
 puis agir ».
- ✅ **Intégré dès la conception** (DAG dédié, métriques poussées, dashboard) — pas un après-coup.
- ✅ Tests présents.

**Limites assumées:**
- **Seuil sur la *part* de features driftées** (50 %) plutôt qu'un **PSI par feature** finement
 réglé → plus simple, moins granulaire que l'état de l'art (PSI > 0,2 par variable).
- **Référence figée** (un split): la bonne pratique est une **référence glissante** (fenêtre) →
 non fait.
- **Drift de données seulement**, pas de **drift de concept** ni de suivi de la **performance
 réelle** en prod (faute de retours terrain).
- **Déclenchement auto** drift→retrain: le câblage existe mais reste à valider de bout en bout
 en conditions réelles.

---

## 6. Références
- Evidently AI — *What is data drift in ML* — https://www.evidentlyai.com/ml-in-production/data-drift
- Evidently AI — *Comparing 5 drift detection methods on large datasets* — https://www.evidentlyai.com/blog/data-drift-detection-large-datasets
- DataCamp — *Understanding data drift and model drift* — https://www.datacamp.com/tutorial/understanding-data-drift-model-drift
- IBM — *What is model drift?* — https://www.ibm.com/think/topics/model-drift

---

### En une phrase (pour la défense)
*« On surveille la dérive des données avec Evidently: un rapport visuel compare la référence à
l'actuel, et si plus de 50 % des features ont dérivé, on déclenche le ré-entraînement. C'est
intégré dès la conception (DAG dédié, scores poussés vers Grafana) — la brique qui ferme la
boucle de vie du modèle. »*

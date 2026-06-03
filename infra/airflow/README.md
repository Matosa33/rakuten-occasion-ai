# Airflow — orchestration de la boucle de ré-entraînement (Cycle 12.1)

Orchestrateur du retrain Rakuten via **Docker Compose** (cf. `BRAIN/decisions.md` D-022).
Principe : **l'orchestrateur orchestre, il ne calcule pas le GPU**. Le DAG ré-entraîne
les têtes CPU (M5/M2/M4) sur les embeddings en cache, logge dans MLflow (D-021) et
enregistre `rakuten-classifier@Production`. L'encodage GPU est une tâche amont isolée
(worker GPU en prod ; no-op sur cache en démo).

## Lancer

Depuis la racine du repo :

```bash
make up                # build + démarre TOUTE la stack (api, frontend, airflow, postgres)
# UI Airflow : http://localhost:8088 (admin / admin)
make airflow-trigger   # déclenche le DAG rakuten_retrain (cible Airflow)
make logs SVC=airflow-scheduler  # suit les logs d'un service (ex : scheduler)
make down              # arrête toute la stack (préserve volumes)
```

> Sous Windows, Docker Desktop doit utiliser le backend **WSL2**.

## DAG `rakuten_retrain`

```
check_new_data  →  train_classifiers  →  evaluate_gate
```

| Tâche | Rôle |
|---|---|
| `check_new_data` | Étape encode (GPU isolé). No-op si embeddings présents (cache) ; échoue sinon avec un message clair. |
| `train_classifiers` | Supprime les anciens `.joblib` puis `python -m src.classifiers.{01_tfidf_linsvc,03_svm,05_mlp}` → log MLflow live + register + `@Production`. |
| `evaluate_gate` | Garde-fou qualité : échoue le DAG si `test_f1_weighted < 0.85` (R15, pas de régression silencieuse). |

Planification : `@weekly`, en pause à la création (déclenchement manuel pour la démo).

## Volumes montés

Le conteneur monte le **repo complet** sur `/opt/rakuten` (code `src/`, `data/`,
`mlflow.db`, `mlartifacts/`) : les tâches lisent/écrivent les vrais artefacts, et
`MLFLOW_TRACKING_URI` pointe sur le `mlflow.db` partagé avec la dev.

## Limites connues / suite

- **Promote conditionnel champion/challenger** (ne promeut que si meilleur que la
  version courante) → sous-todo **12.3** (boucle fermée). Ici, `train` réutilise
  l'auto-promote M5 du Cycle 11.
- **Encodage GPU réel** du delta → worker GPU dédié (hors `make up` portable).
- **Intégration Airflow ↔ DVC** (`dvc repro` par stage) → à reconsidérer au Cycle 13
  une fois `dvc.lock` + remote MinIO en place (alternative C de D-022).

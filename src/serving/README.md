# Serving BentoML — classifieur `@Production` (Cycle 12.2, D-022)

Sert le modèle promu `@Production` du Registry MLflow (tfidf-svm TF-IDF, D-020) via BentoML,
avec **métriques Prometheus natives** sur `/metrics`. Découplage API ↔ modèle : le
service charge le modèle depuis le store BentoML, alimenté par le Registry MLflow.

## Lancer

```bash
make bento-import   # importe models:/rakuten-category-classifier@Production → store BentoML
make bento-serve    # sert sur http://localhost:8500 (UI OpenAPI à la racine)
```

> Port 8500 (le 3000 par défaut de BentoML est souvent déjà pris). `BENTOML_DO_NOT_TRACK=1`
> désactive la télémétrie. Réexécuter `bento-import` après chaque promotion `@Production`
> (la boucle fermée 12.3 l'automatisera).

## Endpoint

`POST /classify` — corps `{"texts": ["...", "..."]}` → `[{"category", "confidence"}, ...]`

```bash
curl -s -X POST http://localhost:8500/classify -H "Content-Type: application/json" \
  -d '{"texts":["Apple iPhone 13 128GB","DEWALT 20V cordless drill"]}'
# [{"category":"Cell_Phones_and_Accessories","confidence":0.998}, {"category":"Tools_and_Home_Improvement","confidence":0.995}]
```

`GET /metrics` — métriques Prometheus (`bentoml_service_request_total`,
`bentoml_service_request_duration_seconds`, `..._request_in_progress`).

## Fichiers

- `import_model.py` — importe le modèle `@Production` dans le store BentoML.
- `service.py` — service BentoML (`@bentoml.service`), endpoint `classify` (catégorie + confiance).
- `bentofile.yaml` (racine) — config de build (`bentoml build`).

## Suite

Scrape Prometheus + dashboard Grafana → Cycle 14 (observabilité). Conteneurisation
du service → Cycle 13 (Docker).

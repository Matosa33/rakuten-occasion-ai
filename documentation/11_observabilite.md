# 11 — Observabilité (logs, métriques, dashboards)

> **Voir** si l'application va bien en production: combien de requêtes, quelle vitesse, combien
> d'erreurs — et pouvoir **retracer** ce qui s'est passé pour une requête donnée.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
L'**observabilité** rend un système **lisible de l'extérieur**, via 3 piliers:
- **Logs structurés**: des messages au format machine (JSON) avec un **identifiant de requête**
 (`request_id`) pour suivre une requête de bout en bout, plutôt que du texte libre illisible.
- **Métriques**: des chiffres mesurés en continu (requêtes/s, temps de réponse, erreurs),
 collectés par **Prometheus**.
- **Dashboards**: des tableaux de bord visuels (**Grafana**) qui affichent ces métriques.

### Les 4 « golden signals » (référence SRE)
- **Latence**: temps de réponse (à suivre en **percentile p95**, pas en moyenne — la moyenne
 « ment »: 1 requête à 10 s noyée dans 99 rapides reste invisible).
- **Trafic**: requêtes par seconde.
- **Erreurs**: taux d'échec.
- **Saturation**: à quel point le service est « plein » (CPU/mémoire, requêtes en cours).

### Pour l'expert
- Le **`request_id`** est injecté par un middleware via `structlog.contextvars` → **tous** les
 logs émis pendant la requête le portent automatiquement (corrélation sans le passer partout).
- **Pushgateway**: pour les **jobs batch** (drift, retrain) qui n'ont pas d'endpoint à scraper,
 on *pousse* les métriques vers une passerelle que Prometheus scrape.

---

## 2. État de l'art

- **4 golden signals** + **Prometheus (métriques) + Grafana (dashboards)** = la combinaison
 standard.
- **Percentiles (p95)** plutôt que moyenne; **alerter sur les symptômes** qui touchent
 l'utilisateur (latence/erreurs), pas seulement les causes.
- **Logs structurés + identifiant de corrélation** pour relier tous les événements d'une requête
 (3ᵉ pilier = traces distribuées, OpenTelemetry, pour le multi-service).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

| Brique | Fichier | Rôle |
|---|---|---|
| Logs structurés | `src/observability/logging.py` | **structlog** JSON, horodatage ISO, niveau, pile d'erreur, `contextvars` |
| Corrélation | `src/api/middleware.py` | injecte un **`request_id`** ajouté **en premier** → présent dans tous les logs |
| Métriques | `prometheus_fastapi_instrumentator` (opt-in `ENABLE_METRICS`) | latence (histogram) + requêtes (counter) + **in-progress (gauge = saturation)** |
| Métriques batch | `src/monitoring/push_metrics.py` | pousse les métriques des jobs (drift, retrain) au **Pushgateway** |
| Dashboards | `monitoring/grafana/dashboards/` | **golden_signals**, **evidently_drift**, **mlops_promote_gate** |
| Config Prometheus | `monitoring/prometheus/prometheus.yml` | quelles cibles scraper |

Détails: l'instrumentation est **opt-in** (variable d'env `ENABLE_METRICS`) — désactivée en
tests pour éviter `Duplicated timeseries` (la lib leak la gauge in-progress vers le registre
global quand pytest recrée l'app). Les logs JSON corrélés permettent de filtrer **tous** les
événements d'une requête par son `request_id`. **3 dashboards** couvrent l'app (golden signals)
ET le MLOps (dérive, promotions de modèle) — l'observabilité ne s'arrête pas à l'API.

---

## 4. Résultats (mesurés)

- **Logs JSON avec `request_id`**: chaque requête traçable de bout en bout
 (`docker compose logs api` → lignes JSON corrélées).
- **4 golden signals** instrumentés et visibles dans `golden_signals.json`.
- **3 dashboards Grafana** opérationnels (app + drift + promote gate).
- Tests: `test_observability_logging.py`, `test_push_metrics.py`.

> 📊 **Chiffres slide**: « 4 golden signals (latence p95/trafic/erreurs/saturation) », « logs
> JSON corrélés par `request_id` », « 3 dashboards Grafana (app + MLOps) ». 📸 **Capture**: le
> dashboard `golden_signals` peuplé pendant une démo + un extrait de logs JSON avec le même
> `request_id`.

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **4 golden signals** + **Prometheus/Grafana** → combinaison et métriques standard.
- ✅ **Logs structurés JSON + `request_id`** (contextvars) → corrélation de bout en bout.
- ✅ **Pushgateway** pour les jobs batch → on observe aussi le MLOps, pas que l'API.
- ✅ 3 dashboards (app + MLOps).

**Limites assumées:**
- **Instrumentation opt-in** (variable d'env): il faut penser à l'allumer; en prod on
 l'activerait par défaut.
- **Pas de règles d'alerte** (Alertmanager): on visualise, mais on n'**alerte** pas encore
 automatiquement (« alerter sur les symptômes ») → axe d'amélioration clair.
- **Pas de tracing distribué** (OpenTelemetry): on a logs + métriques, pas les *traces* (3ᵉ
 pilier) — non nécessaire à cette échelle mono-service, mais à citer.

---

## 6. Références
- SRE School — *Four golden signals* — https://sreschool.com/blog/four-golden-signals/
- Grafana — *Building dashboards with the four golden signals* — https://learn.grafana.com/building-effective-dashboards-with-the-four-golden-signals
- structlog — *documentation* — https://www.structlog.org/en/stable/
- Prometheus — *Pushgateway* — https://prometheus.io/docs/practices/pushing/

---

### En une phrase (pour la défense)
*« On observe l'app via les 4 golden signals (latence p95, trafic, erreurs, saturation) dans
Prometheus/Grafana, et des logs JSON corrélés par `request_id` permettent de suivre chaque
requête de bout en bout — y compris les jobs MLOps (drift, promotions) via Pushgateway. »*

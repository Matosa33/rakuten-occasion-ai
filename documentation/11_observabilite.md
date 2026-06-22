# 11 — Observabilité (logs, métriques, dashboards)

> Pouvoir **voir** si l'application va bien en production : combien de requêtes, quelle
> vitesse, combien d'erreurs — et retrouver ce qui s'est passé pour une requête donnée.

---

## 1. La technologie : qu'est-ce que c'est ?

L'**observabilité**, c'est l'ensemble des outils qui rendent un système **lisible de
l'extérieur** :
- **Logs structurés** : des messages au format machine (JSON) plutôt que du texte libre, avec
  un **identifiant de requête** (`request_id`) pour suivre une requête de bout en bout.
- **Métriques** : des chiffres mesurés en continu (nombre de requêtes, temps de réponse,
  erreurs), collectés par **Prometheus**.
- **Dashboards** : des tableaux de bord visuels (**Grafana**) qui affichent ces métriques.

---

## 2. État de l'art

- **Les 4 « golden signals »** (référence SRE) : **latence** (temps de réponse), **trafic**
  (requêtes/s), **erreurs** (taux d'échec), **saturation** (CPU/mémoire). Surveiller ces
  quatre-là suffit à détecter la majorité des problèmes.
- **Prometheus** pour les métriques + **Grafana** pour la visualisation = la combinaison
  standard.
- **Bonnes pratiques** :
  - utiliser des **percentiles** (p95) plutôt que la moyenne (la moyenne « ment » : 1 requête
    à 10 s noyée dans 99 rapides reste invisible),
  - **alerter sur les symptômes** qui touchent l'utilisateur (latence/erreurs), pas seulement
    les causes,
  - **logs structurés + identifiant de corrélation** pour relier tous les événements d'une requête.

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Logs structurés | `src/observability/logging.py` | **structlog** JSON, horodatage ISO, niveau, pile d'erreur |
| Corrélation | `src/api/middleware.py` | injecte un **`request_id`** ; tous les logs de la requête le portent |
| Métriques | instrumentation Prometheus (opt-in via variable d'env) | expose les métriques de l'API |
| Métriques batch | `src/monitoring/push_metrics.py` | pousse les métriques des jobs (drift, retrain) au **Pushgateway** |
| Dashboards | `monitoring/grafana/dashboards/` | **golden_signals**, **evidently_drift**, **mlops_promote_gate** |
| Config Prometheus | `monitoring/prometheus/prometheus.yml` | quelles cibles scraper |

Choix : logs **JSON corrélés** (on peut filtrer tous les événements d'une requête par son
`request_id`), et **3 dashboards** Grafana couvrant l'app (golden signals) ET le MLOps
(dérive, promotions de modèle).

---

## 4. Résultats (mesurés)

- **Logs JSON avec `request_id`** : chaque requête est traçable de bout en bout
  (`docker compose logs api` montre les lignes JSON corrélées).
- **4 golden signals** instrumentés et visibles dans le dashboard `golden_signals.json`.
- **3 dashboards Grafana** opérationnels (app + drift + promote gate).
- Tests : `test_observability_logging.py`, `test_push_metrics.py`.

> 📊 **Chiffres slide** : « 4 golden signals (latence/trafic/erreurs/saturation) », « logs
> JSON corrélés par request_id », « 3 dashboards Grafana (app + MLOps) ». 📸 **Capture** : le
> dashboard `golden_signals` peuplé pendant une démo + un extrait de logs JSON avec le même
> `request_id`. **Visuellement parlant pour le jury.**

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **4 golden signals** + **Prometheus/Grafana** → la combinaison et les métriques standard.
- ✅ **Logs structurés JSON + request_id** → corrélation de bout en bout, bonne pratique clé.
- ✅ **Pushgateway** pour les jobs batch (drift/retrain) → on observe aussi le MLOps, pas que l'API.
- ✅ 3 dashboards (app + MLOps).

**Limites assumées :**
- **Instrumentation opt-in** (activée par variable d'env) : il faut penser à l'allumer ; en
  prod on l'activerait par défaut.
- **Pas de règles d'alerte** (Alertmanager) : on visualise, mais on n'**alerte** pas encore
  automatiquement (« alerter sur les symptômes »). Axe d'amélioration clair.
- **Pas de tracing distribué** (OpenTelemetry) : on a logs + métriques, pas les *traces* (le
  3ᵉ pilier de l'observabilité) — non nécessaire à cette échelle, mais à citer.

---

## 6. Références
- SRE School — *Four golden signals* — https://sreschool.com/blog/four-golden-signals/
- Grafana — *Building dashboards with the four golden signals* — https://learn.grafana.com/building-effective-dashboards-with-the-four-golden-signals
- Rootly — *How SREs use Prometheus and Grafana* — https://rootly.com/sre/how-sres-use-prometheus-and-grafana-to-crush-mttr-in-2025
- PFLB — *The 4 golden signals in SRE* — https://pflb.us/blog/4-golden-signals-sre/

---

### En une phrase (pour la défense)
*« On observe l'application via les 4 golden signals (latence, trafic, erreurs, saturation)
dans Prometheus/Grafana, et des logs JSON corrélés par `request_id` permettent de suivre
chaque requête de bout en bout — y compris les jobs MLOps (drift, promotions) via Pushgateway. »*

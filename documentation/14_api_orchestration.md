# 14 — API & orchestration runtime (la plomberie qui câble tout)

> Le **chef d'orchestre** : la couche qui reçoit les requêtes, charge les modèles, enchaîne
> retrieval → VLM → Akinator → pricing → rédaction, et renvoie une réponse propre. Sans elle,
> les briques ML ne sont que des fichiers isolés.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
Une **API** (Application Programming Interface) est une « prise » par laquelle un programme
(ici le frontend) parle à un autre (ici nos modèles). Le frontend envoie une requête HTTP
(« voici une photo, identifie-la »), l'API exécute le travail et renvoie une réponse JSON.

Le rôle de l'**orchestrateur** : aucune brique ne fait tout. Le retrieval trouve le produit, le
VLM lit la photo, l'Akinator lève le doute, le pricing calcule le prix, le LLM rédige.
Quelqu'un doit les **appeler dans le bon ordre, passer les données de l'une à l'autre, et gérer
les erreurs**. C'est le fichier `src/api/pipeline.py` (470 lignes) + `src/api/main.py` (439).

### Pour l'expert
- **FastAPI** (Python async) : validation des entrées/sorties par **Pydantic v2** (schémas
  typés → erreurs 422 automatiques), serveur ASGI (uvicorn).
- **Chargement au démarrage** (*lifespan*) : les modèles (index FAISS 13 Go, métadonnées) sont
  chargés **une fois** au boot, pas à chaque requête.
- **Async correct** : FAISS/Arctic/VLM sont **synchrones et lourds** → on les exécute via
  `asyncio.to_thread(...)` pour **ne pas bloquer la boucle d'événements** (sinon une requête
  lente gèlerait toutes les autres).

---

## 2. État de l'art

- **Servir un modèle ML = une API** (REST/gRPC) avec validation des entrées, chargement du
  modèle au démarrage, et **dégradation gracieuse** (si un modèle manque, renvoyer une erreur
  claire plutôt que planter).
- **Observabilité dès l'API** : identifiant de corrélation par requête + métriques (cf. rapport
  *Observabilité*).
- **Sécurité** : authentifier les endpoints métier, garder publics seulement le strict
  nécessaire (login, sondes de santé).
- **Streaming** (SSE/WebSocket) pour les UX progressives (montrer l'avancement étape par étape).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Les endpoints (`src/api/main.py`)
| Endpoint | Auth | Rôle |
|---|---|---|
| `POST /auth/login` | public | OAuth2 password → Bearer **JWT HS256** (`demo/demo`) |
| `POST /upload` | Bearer | stocke une photo vendeur (entrée du flow, D-035) |
| `GET /uploads/{id}` | public (**capability-URL** uuid4) | sert la photo (affichage annonce) |
| `GET /health` | public | sondes K8s : quels services sont chargés |
| `POST /identify` | Bearer | **le cœur** : photos → candidats + Akinator + validation VLM |
| `POST /price` | Bearer | cascade prix L1-L4 |
| `POST /describe` | Bearer | titre + description grounded |
| `GET /history` | Bearer | N dernières identifications (traçabilité) |
| `POST /identify/stream` | Bearer | **SSE** : étapes du pipeline en temps réel |

### Le chargement au démarrage (`lifespan`)
Au boot, on instancie **3 services** et on les charge en *fail-soft* : si l'un échoue (artefact
absent), l'app démarre quand même et l'endpoint correspondant renverra **503** avec un message
actionnable (au lieu de crasher tout le serveur).

### L'orchestrateur (`src/api/pipeline.py`) — 3 services
**`IdentificationService`** (le plus riche) :
- charge l'index **FAISS HNSW** (`efSearch=64`), les métadonnées train, et **6 lookups**
  produit (vignette, toutes les vues, catégorie fine, breadcrumb complet, marque, facettes) ;
- **encodeur Arctic chargé en lazy** (à la 1ʳᵉ requête, pas au boot) ;
- `encode_query` : prompt `"query"` + normalisation L2 + **garde-fou de dimension R7 par `raise`
  et non `assert`** (les `assert` sont supprimés sous `python -O` → le garde-fou survivrait pas
  en prod) ;
- `_maybe_translate` : **FR→EN** via OpenRouter (le catalogue est anglais ; décalage mesuré
  ~0,08), avec **fallback gracieux** sur la requête brute si pas de clé/échec ;
- `identify` : `(traduire) → encoder → FAISS top-30 → construire candidats → OOD 3 niveaux
  (≥0,60 identifié / ≥0,45 à confirmer / sinon incertain) → Akinator si écart top1-top2 < 0,05`.

**`PricingService`** : charge `m8_pricing_v1.joblib`, délègue à la cascade transparente.
**`DescribeService`** : charge les métadonnées + **grounding sur la description réelle** ; writer
**OpenRouter si clé, sinon Mock** (D-013) ; convertit les états snake_case en libellés FR
**avant** le prompt (sinon « bon_etat » fuyait dans le titre, 17.4b).

### Le flow d'une requête `/identify` (la plomberie, étape par étape)
```
 POST /identify {image_ids, text_hint, already_observed}
   │  (Bearer JWT vérifié)
   ▼
 1. récupérer les chemins des photos (image_ids → fichiers)         [422 si aucun valide]
   ▼
 2. VLM extraction (asyncio.to_thread)  -> titre probable + attributs   [503 si clé absente & pas de texte]
   ▼
 3. query = titre_VLM + text_hint  ;  attributs VLM -> observed (pré-remplit Akinator)
   ▼
 4. IdentificationService.identify(query, observed)  -> candidats + OOD + Akinator
   ▼
 5. VLM validateur sur le top-1 (photo vendeur × image catalogue)   [best-effort, jamais bloquant]
   ▼
 6. persistence.log_identification(...)                              [non bloquant : try/except]
   ▼
 7. réponse JSON : top_candidates + vlm_validation + next_observation + explanation
```

### Patterns transverses
- **Middleware `request_id`** ajouté **en premier** → présent dans tous les logs de la requête.
- **Prometheus** instrumentator **opt-in** (`ENABLE_METRICS`) — désactivé en tests (sinon
  `Duplicated timeseries` quand pytest recrée l'app).
- **CORS** explicite (méthodes/headers listés, pas `*`) pour réduire le vecteur CSRF sur le
  login public (durci à l'audit P1).
- **Persistance** (`src/api/persistence.py`, SQLAlchemy) : historise chaque identification —
  **best-effort** (un échec de log ne casse jamais l'API).
- **Schémas** (`src/api/schemas.py`, Pydantic v2) : 181 lignes de contrats typés entrée/sortie.

---

## 4. Résultats (mesurés)

- **9 endpoints** opérationnels, documentés automatiquement (OpenAPI sur `/docs`).
- **Smoke E2E LIVE 6/6** : login → upload → identify (30 candidats + validation VLM 1.0) →
  price (L1) → describe (titre cohérent) — joué en conteneur réel.
- **Dégradation gracieuse vérifiée** : sans clé OpenRouter, `/describe` bascule en mock ; sans
  index, `/identify` renvoie 503 actionnable (l'app ne crashe pas).
- **Async** : FAISS/VLM en `to_thread` → la boucle reste libre.

> 📊 **Chiffres slide** : « 9 endpoints, 3 services chargés au lifespan », « flow /identify en
> 7 étapes (photo→VLM→retrieval→Akinator→validation→persistance→réponse) », « dégradation
> gracieuse (503 actionnable / mock) », « smoke E2E 6/6 ». 📸 **Capture** : la page `/docs`
> (OpenAPI) avec la liste des endpoints + une réponse `/identify` JSON.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Orchestration claire et testée** : un service par responsabilité, un flow lisible, garde-fous
  d'erreur à chaque étape (401/422/404/503).
- ✅ **Async correct** (`to_thread` sur le synchrone lourd) + **SSE** pour l'UX progressive.
- ✅ **Dégradation gracieuse partout** (R15) : la photo échoue → fallback texte ; LLM down →
  mock ; persistance down → on continue. La démo ne plante pas.
- ✅ **Garde-fous de robustesse** : R7 par `raise` (survit à `-O`), best-effort sur le validateur
  et la persistance.
- ✅ Sécurité : Bearer sur tout le métier, capability-URL pour les photos, CORS explicite.

**Limites assumées :**
- **État global en singleton** (`APP_STATE` dict) : simple et suffisant pour un mono-process,
  mais pas idéal pour un scaling multi-worker avec état partagé (chaque worker recharge l'index).
- **Persistance SQLite** (historique) : OK démo, à passer en Postgres pour la prod multi-instance.
- **Quelques docstrings « text-only » legacy** (héritage avant le recadrage photo-first D-035) —
  le code, lui, est bien photo-first ; à nettoyer (backlog).
- **Pas de rate-limiting applicatif** (délégué à Traefik) ; **SSE** ne gère que `text_hint`
  (pas encore le flow photo).

---

## 6. Références
- FastAPI — *Lifespan events* — https://fastapi.tiangolo.com/advanced/events/
- FastAPI — *Concurrency & async / await* — https://fastapi.tiangolo.com/async/
- Pydantic v2 — *Models* — https://docs.pydantic.dev/latest/concepts/models/
- MDN — *Server-Sent Events* — https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

---

### En une phrase (pour la défense)
*« Le cœur runtime, c'est `pipeline.py` : il charge les modèles une fois au démarrage, puis pour
chaque requête `/identify` enchaîne photo → extraction VLM → recherche FAISS → garde-fous OOD →
Akinator → validation visuelle → persistance, le tout en async (pour ne pas bloquer) et avec une
dégradation gracieuse à chaque étape (un composant qui tombe ne casse jamais le flux). »*

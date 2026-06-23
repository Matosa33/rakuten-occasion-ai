# 14 — API & orchestration runtime (la plomberie qui câble tout)

> Le **chef d'orchestre**: la couche qui reçoit les requêtes, charge les modèles, enchaîne
> retrieval → VLM → Akinator → pricing → rédaction, et renvoie une réponse propre. Sans elle,
> les briques ML ne sont que des fichiers isolés.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
Une **API** (Application Programming Interface) est une « prise » par laquelle un programme
(ici le frontend) parle à un autre (ici nos modèles). Le frontend envoie une requête HTTP
(« voici une photo, identifie-la »), l'API exécute le travail et renvoie une réponse JSON.

Le rôle de l'**orchestrateur**: aucune brique ne fait tout. Le retrieval trouve le produit, le
VLM lit la photo, l'Akinator lève le doute, le pricing calcule le prix, le LLM rédige.
Quelqu'un doit les **appeler dans le bon ordre, passer les données de l'une à l'autre, et gérer
les erreurs**. C'est le fichier `src/api/pipeline.py` (470 lignes) + `src/api/main.py` (439).

### Pour l'expert
- **FastAPI** (Python async): validation des entrées/sorties par **Pydantic v2** (schémas
 typés → erreurs 422 automatiques), serveur ASGI (uvicorn).
- **Chargement au démarrage** (*lifespan*): les modèles (index FAISS 13 Go, métadonnées) sont
 chargés **une fois** au boot, pas à chaque requête.
- **Async correct**: FAISS/Arctic/VLM sont **synchrones et lourds** → on les exécute via
 `asyncio.to_thread(...)` pour **ne pas bloquer la boucle d'événements** (sinon une requête
 lente gèlerait toutes les autres).

---

## 2. État de l'art

- **Servir un modèle ML = une API** (REST/gRPC) avec validation des entrées, chargement du
 modèle au démarrage, et **dégradation gracieuse** (si un modèle manque, renvoyer une erreur
 claire plutôt que planter).
- **Observabilité dès l'API**: identifiant de corrélation par requête + métriques (cf. rapport
 *Observabilité*).
- **Sécurité**: authentifier les endpoints métier, garder publics seulement le strict
 nécessaire (login, sondes de santé).
- **Streaming** (SSE/WebSocket) pour les UX progressives (montrer l'avancement étape par étape).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Les endpoints (`src/api/main.py`)
| Endpoint | Auth | Rôle |
|---|---|---|
| `POST /auth/login` | public | OAuth2 password → Bearer **JWT HS256** (`demo/demo`) |
| `POST /upload` | Bearer | stocke une photo vendeur (entrée du flow) |
| `GET /uploads/{id}` | public (**capability-URL** uuid4) | sert la photo (affichage annonce) |
| `GET /health` | public | sondes K8s: quels services sont chargés |
| `POST /identify` | Bearer | **le cœur**: photos → candidats + Akinator + validation VLM |
| `POST /price` | Bearer | cascade prix L1-L4 |
| `POST /describe` | Bearer | titre + description grounded |
| `GET /history` | Bearer | N dernières identifications (traçabilité) |
| `POST /identify/stream` | Bearer | **SSE**: étapes du pipeline en temps réel |

### Le chargement au démarrage (`lifespan`)
Au boot, on instancie **3 services** et on les charge en *fail-soft*: si l'un échoue (artefact
absent), l'app démarre quand même et l'endpoint correspondant renverra **503** avec un message
actionnable (au lieu de crasher tout le serveur).

### L'orchestrateur (`src/api/pipeline.py`) — 3 services

#### `IdentificationService` — le plus riche (il transforme une requête en candidats)

**Ce qu'il charge au démarrage** (une fois, pour ne pas relire le disque à chaque requête):
- **l'index FAISS HNSW** = le moteur de recherche vectorielle. Son réglage `efSearch=64` dit
 *« combien de voisins explorer pendant la recherche »*: plus c'est haut, plus c'est précis
 mais lent. 64 est notre compromis (déjà recall 0,948 à 0,29 ms).
- **les métadonnées du train** (titre, marque, prix… de chaque produit) → pour pouvoir
 **afficher** les candidats trouvés.
- **6 tables de correspondance** (« lookups ») `parent_asin → info`, préchargées en mémoire: la
 vignette, **toutes** les vues photo, la catégorie fine, le breadcrumb complet (« A > B > C »),
 la marque, les facettes (couleur, capacité…). On les a en RAM pour enrichir instantanément
 chaque candidat.

**L'encodeur Arctic est chargé en *lazy*** = pas au démarrage, mais à la **première requête**.
Pourquoi ? Le modèle est lourd à charger; si personne n'identifie, autant ne pas le charger
(démarrage du serveur plus rapide).

**`encode_query` — transformer le texte en vecteur**, avec 3 subtilités:
- **prompt `"query"`**: Arctic encode légèrement différemment une *requête* et un *document*.
 On lui précise explicitement qu'ici c'est une requête (sinon scores faussés).
- **normalisation L2**: pour que la comparaison se fasse sur le *sens* (cosinus), cf. rapport
 *Embeddings*.
- **garde-fou de dimension** : on vérifie que le vecteur fait bien **1024 nombres**. Détail
 qui compte: on lève une vraie erreur (`raise`) et **pas** un `assert` — parce que Python
 **supprime les `assert`** quand on lance en mode optimisé (`python -O`). Un `assert` aurait
 donc disparu silencieusement en production; le `raise`, lui, survit.

**`_maybe_translate` — traduire avant de chercher**: le catalogue est en **anglais**, le vendeur
écrit en **français**. On traduit donc la requête FR→EN avant la recherche (on a **mesuré** que
ça améliore la pertinence, +0,085). Et si la traduction échoue (pas de clé API, service down),
on **continue avec la requête brute**: Arctic est multilingue, juste un peu moins précis — on ne
bloque jamais le vendeur pour une traduction ratée.

**`identify` — l'enchaînement complet**:
`traduire → encoder → chercher les 30 plus proches (FAISS) → construire la liste de candidats →
appliquer les garde-fous OOD → désambiguïser si besoin`. Les **garde-fous OOD** donnent 3 niveaux
de confiance selon le score du meilleur candidat: **≥ 0,60** = « identifié », **entre 0,45 et
0,60** = « à confirmer », **en dessous** = « incertain » (mais on montre **toujours** les
candidats — c'est l'humain qui tranche). Enfin, si les **deux premiers candidats sont trop
proches** (écart < 0,05, typiquement deux variantes du même produit), on déclenche l'**Akinator**
pour poser la question qui les sépare.

#### `PricingService` — le prix
Charge le fichier de configuration du modèle de prix (`m8_pricing_v1.joblib`) et **délègue à la
cascade transparente** L1-L4 (cf. rapport *Pricing*).

#### `DescribeService` — la rédaction de l'annonce
Charge les métadonnées produit + **les phrases de grounding** (la vraie description catalogue).
Le rédacteur est **OpenRouter si une clé est présente, sinon un Mock** → la démo ne plante
jamais. Subtilité corrigée en 17.4b: on **convertit les codes d'état** (`bon_etat`) **en libellés
français** (« Bon état ») **avant** de construire le prompt — sinon le code technique « fuyait »
dans le titre généré.

### Le flow d'une requête `/identify` (la plomberie, étape par étape)
```
 POST /identify {image_ids, text_hint, already_observed}
 │ (Bearer JWT vérifié)
 ▼
 1. récupérer les chemins des photos (image_ids → fichiers) [422 si aucun valide]
 ▼
 2. VLM extraction (asyncio.to_thread) -> titre probable + attributs [503 si clé absente & pas de texte]
 ▼
 3. query = titre_VLM + text_hint; attributs VLM -> observed (pré-remplit Akinator)
 ▼
 4. IdentificationService.identify(query, observed) -> candidats + OOD + Akinator
 ▼
 5. VLM validateur sur le top-1 (photo vendeur × image catalogue) [best-effort, jamais bloquant]
 ▼
 6. persistence.log_identification(...) [non bloquant: try/except]
 ▼
 7. réponse JSON: top_candidates + vlm_validation + next_observation + explanation
```

### Patterns transverses
- **Middleware `request_id`** ajouté **en premier** → présent dans tous les logs de la requête.
- **Prometheus** instrumentator **opt-in** (`ENABLE_METRICS`) — désactivé en tests (sinon
 `Duplicated timeseries` quand pytest recrée l'app).
- **CORS** explicite (méthodes/headers listés, pas `*`) pour réduire le vecteur CSRF sur le
 login public (durci à l'audit P1).
- **Persistance** (`src/api/persistence.py`, SQLAlchemy): historise chaque identification —
 **best-effort** (un échec de log ne casse jamais l'API).
- **Schémas** (`src/api/schemas.py`, Pydantic v2): 181 lignes de contrats typés entrée/sortie.

---

## 4. Résultats (mesurés)

- **9 endpoints** opérationnels, documentés automatiquement (OpenAPI sur `/docs`).
- **Smoke E2E LIVE 6/6**: login → upload → identify (30 candidats + validation VLM 1.0) →
 price (L1) → describe (titre cohérent) — joué en conteneur réel.
- **Dégradation gracieuse vérifiée**: sans clé OpenRouter, `/describe` bascule en mock; sans
 index, `/identify` renvoie 503 actionnable (l'app ne crashe pas).
- **Async**: FAISS/VLM en `to_thread` → la boucle reste libre.

> 📊 **Chiffres slide**: « 9 endpoints, 3 services chargés au lifespan », « flow /identify en
> 7 étapes (photo→VLM→retrieval→Akinator→validation→persistance→réponse) », « dégradation
> gracieuse (503 actionnable / mock) », « smoke E2E 6/6 ». 📸 **Capture**: la page `/docs`
> (OpenAPI) avec la liste des endpoints + une réponse `/identify` JSON.

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Orchestration claire et testée**: un service par responsabilité, un flow lisible, garde-fous
 d'erreur à chaque étape (401/422/404/503).
- ✅ **Async correct** (`to_thread` sur le synchrone lourd) + **SSE** pour l'UX progressive.
- ✅ **Dégradation gracieuse partout**: la photo échoue → fallback texte; LLM down →
 mock; persistance down → on continue. La démo ne plante pas.
- ✅ **Garde-fous de robustesse**: par `raise` (survit à `-O`), best-effort sur le validateur
 et la persistance.
- ✅ Sécurité: Bearer sur tout le métier, capability-URL pour les photos, CORS explicite.

**Limites assumées:**
- **État global en singleton** (`APP_STATE` dict): simple et suffisant pour un mono-process,
 mais pas idéal pour un scaling multi-worker avec état partagé (chaque worker recharge l'index).
- **Persistance SQLite** (historique): OK démo, à passer en Postgres pour la prod multi-instance.
- **Quelques docstrings « text-only » legacy** (héritage avant le recadrage photo-first) —
 le code, lui, est bien photo-first; à nettoyer (backlog).
- **Pas de rate-limiting applicatif** (délégué à Traefik); **SSE** ne gère que `text_hint`
 (pas encore le flow photo).

---

## 6. Références
- FastAPI — *Lifespan events* — https://fastapi.tiangolo.com/advanced/events/
- FastAPI — *Concurrency & async / await* — https://fastapi.tiangolo.com/async/
- Pydantic v2 — *Models* — https://docs.pydantic.dev/latest/concepts/models/
- MDN — *Server-Sent Events* — https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

---

### En une phrase (pour la défense)
*« Le cœur runtime, c'est `pipeline.py`: il charge les modèles une fois au démarrage, puis pour
chaque requête `/identify` enchaîne photo → extraction VLM → recherche FAISS → garde-fous OOD →
Akinator → validation visuelle → persistance, le tout en async (pour ne pas bloquer) et avec une
dégradation gracieuse à chaque étape (un composant qui tombe ne casse jamais le flux). »*

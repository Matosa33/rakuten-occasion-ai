# 11 - Observabilité (journaux, métriques, tableaux de bord)

> Le but de ce composant : pouvoir voir, en permanence et de l'extérieur, si l'application
> fonctionne bien une fois mise en service (combien de demandes elle reçoit, à quelle vitesse elle
> répond, combien d'erreurs elle produit), et pouvoir retracer précisément ce qui s'est passé pour
> une demande précise quand un problème survient.

Pour situer le projet en deux phrases : il s'agit d'un assistant qui aide un vendeur de
particulier à mettre en vente un produit d'occasion (il identifie le produit à partir d'une photo,
suggère un prix, et rédige une annonce). Cet assistant est exposé sous forme d'un service web, et
c'est ce service que l'on cherche ici à surveiller.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre à partir de zéro

L'observabilité est la capacité à comprendre l'état interne d'un logiciel rien qu'en regardant ce
qu'il émet vers l'extérieur, sans avoir à ouvrir le code ni à deviner. Elle repose ici sur trois
familles d'informations.

- Les journaux structurés (en anglais « logs »). Un journal est la trace écrite que laisse le
  logiciel à chaque événement (« j'ai reçu une demande », « j'ai renvoyé une réponse »,
  « une erreur s'est produite »). « Structuré » signifie que chaque ligne est écrite dans un format
  que la machine sait relire facilement, le format JSON (un format texte standard composé de
  paires « nom : valeur », par exemple `"status": 200`), plutôt qu'en texte libre désorganisé.
  Chaque ligne porte un identifiant de demande (un `request_id`, c'est-à-dire un numéro unique
  attribué à chaque demande entrante) qui permet de regrouper tous les événements d'une même
  demande, du début à la fin. On distingue deux usages de ces journaux : les journaux
  *techniques* (la demande HTTP est arrivée, a duré tant de millisecondes, a renvoyé tel code) et
  les journaux *métier*, qui racontent ce que le pipeline a réellement décidé pour cette demande
  (quel produit identifié, avec quelle confiance, à quel niveau de prix). Cette seconde famille
  est ce qui permet de répondre à des questions de fond comme « combien de fois
  le produit n'était-il pas au catalogue ? » ou « le niveau de prix estimé par l'IA sert-il
  souvent ? », sans rejouer manuellement les demandes.

- Les métriques. Ce sont des chiffres mesurés en continu : nombre de demandes par seconde, temps
  de réponse, nombre d'erreurs. Ces chiffres sont collectés par Prometheus, un logiciel libre
  spécialisé dans la collecte et le stockage de mesures chiffrées au fil du temps.

- Les tableaux de bord. Ce sont les écrans visuels (courbes, jauges, voyants) qui affichent ces
  mesures de façon lisible. On utilise pour cela Grafana, un logiciel libre qui transforme les
  chiffres bruts de Prometheus en graphiques.

### Les quatre signaux fondamentaux (« golden signals »)

Pour surveiller un service, la profession (les ingénieurs de fiabilité, appelés SRE pour « Site
Reliability Engineering ») recommande de suivre en priorité quatre indicateurs, dits « signaux en
or » :

- La latence : le temps que met le service à répondre. On la suit au 95e percentile (noté p95),
  c'est-à-dire la valeur en dessous de laquelle se situent 95 % des réponses. On évite la moyenne,
  car la moyenne peut mentir : une seule demande lente à 10 secondes, noyée parmi 99 demandes
  rapides, devient invisible dans une moyenne, alors que le p95 la fait ressortir.

- Le trafic : le nombre de demandes par seconde, c'est-à-dire la charge réelle subie.

- Les erreurs : la proportion de demandes qui échouent.

- La saturation : le degré de « remplissage » du service, ici mesuré par le nombre de demandes en
  cours de traitement à un instant donné.

### Pour l'expert

L'identifiant de demande (`request_id`) est injecté par un intercepteur (un « middleware », c'est-à-dire
un bout de code qui s'exécute automatiquement avant et après chaque demande) au moyen des
« contextvars » de la bibliothèque structlog. Concrètement, structlog est la bibliothèque Python qui
fabrique nos journaux structurés, et ses « contextvars » sont une mémoire de contexte propre à
chaque demande : une fois le `request_id` posé dans ce contexte, tous les journaux émis pendant la
demande le portent automatiquement, sans avoir à le passer manuellement à chaque appel.

Pour les traitements par lots (les calculs lancés ponctuellement, comme la détection de dérive des
données ou le réentraînement du modèle), il n'y a pas de service en marche permanente que
Prometheus pourrait interroger. On utilise alors une passerelle, le Pushgateway : le traitement par
lots y dépose (« pousse ») ses mesures à la fin de son exécution, et c'est Prometheus qui vient
ensuite les y récupérer.

---

## 2. État de l'art

- La combinaison standard de l'industrie pour ce besoin est : quatre signaux fondamentaux,
  Prometheus pour les métriques, Grafana pour les tableaux de bord.

- La bonne pratique est de raisonner en percentiles (le p95) plutôt qu'en moyenne, et d'alerter en
  priorité sur les symptômes que ressent l'utilisateur (lenteur, erreurs) plutôt que sur les seules
  causes techniques internes.

- Côté journaux, la pratique de référence est d'avoir des journaux structurés assortis d'un
  identifiant de corrélation, afin de relier entre eux tous les événements d'une même demande.

- Le troisième pilier de l'observabilité, au-delà des journaux et des métriques, est le « traçage
  distribué » (avec des outils comme OpenTelemetry) : il consiste à suivre une demande qui traverse
  plusieurs services différents. Il devient utile quand l'application est découpée en de nombreux
  services communiquant entre eux.

---

## 3. Notre implémentation (précisément ce qui a été fait)

| Brique | Fichier | Rôle |
|---|---|---|
| Journaux structurés | `src/observability/logging.py` | structlog au format JSON, horodatage normalisé (format ISO, en temps universel UTC), niveau de gravité, pile d'erreur en cas d'exception, contexte par demande |
| Corrélation | `src/api/middleware.py` | attribue un `request_id` à chaque demande, intercepteur ajouté en tout premier pour que l'identifiant soit présent dans tous les journaux suivants |
| Journaux métier | `src/api/main.py` (logger `rakuten.api`) | deux événements inspectables par demande, `identify_done` et `price_done`, qui consignent la décision réelle du pipeline et les temps des appels au modèle de langage |
| Métriques du service | bibliothèque `prometheus_fastapi_instrumentator`, branchée dans `src/api/main.py` | latence (histogramme), nombre de requêtes (compteur) et demandes en cours (jauge, qui mesure la saturation) |
| Métriques des traitements par lots | `src/monitoring/push_metrics.py` | pousse vers le Pushgateway les mesures des calculs ponctuels (dérive des données et décision de promotion de modèle) |
| Tableaux de bord | `monitoring/grafana/dashboards/` | trois tableaux : `golden_signals`, `evidently_drift`, `mlops_promote_gate` |
| Configuration de Prometheus | `monitoring/prometheus/prometheus.yml` | liste des cibles à interroger |

### Comment les journaux sont produits

Le fichier `src/observability/logging.py` configure structlog une seule fois pour tout le projet.
Par défaut, les journaux sortent au format JSON sur la sortie standard (idéal pour être collectés
en production), mais quand le code tourne dans un terminal interactif (en développement), ils
s'affichent au contraire en couleur et lisibles à l'œil. On peut forcer l'un ou l'autre mode avec
la variable d'environnement `LOG_FORMAT` (valeurs `json` ou `console`). Le niveau de détail se
règle avec la variable `LOG_LEVEL` (valeur par défaut `INFO`). Une passerelle relie aussi les
journaux des bibliothèques tierces (le serveur web uvicorn, la couche base de données, etc.) au
même format, pour que tout sorte de façon homogène.

### Comment l'identifiant de demande circule

À chaque demande entrante, l'intercepteur du fichier `src/api/middleware.py` lit l'en-tête
`X-Request-ID` envoyé par le client s'il existe, sinon il en fabrique un nouveau (un identifiant
aléatoire de 16 caractères). Il enregistre cet identifiant dans le contexte de la demande, mesure
le temps de traitement, écrit une ligne de journal `http_request` contenant la méthode, le chemin,
le code de statut et la durée en millisecondes, puis renvoie le même identifiant au client dans
l'en-tête de réponse. Réutiliser un identifiant fourni par le client permet de suivre une même
demande à travers plusieurs maillons (le client, la passerelle d'entrée, l'application). Le
contexte est systématiquement nettoyé à la fin, pour qu'un identifiant ne « déborde » pas sur la
demande suivante.

### Les journaux métier : lire ce que le pipeline a vraiment décidé

Les métriques Prometheus décrites plus bas répondent à des questions techniques (combien de
demandes, à quelle vitesse, avec combien d'erreurs), mais elles ne disent rien du *contenu* d'une
demande : elles ne savent pas si le produit a été correctement identifié, si l'IA a dû avouer que le
produit était absent du catalogue, ou à quel niveau de prix on a abouti. Pour combler ce manque, le
fichier `src/api/main.py` émet, en plus des métriques HTTP, deux événements de journal structurés et
volontairement riches, l'un à la fin de l'identification et l'autre à la fin du calcul de prix. Ils
passent par le même logger structlog que le reste (`get_logger("rakuten.api")`), ce qui veut dire
qu'ils héritent automatiquement du `request_id` de la demande en cours : on peut donc relier
l'événement métier d'une demande à sa ligne HTTP technique et à toute erreur survenue, en filtrant
sur le même identifiant. L'intérêt direct est qu'on « lit » le comportement du pipeline en
production (taux de produits hors catalogue, fréquence d'usage du prix estimé par IA, endroit où part
la latence) sans avoir à rejouer les demandes à la main. Rien n'est décoratif : chaque champ sert à
répondre à une question concrète.

L'événement `identify_done`, écrit une fois que l'identification est entièrement résolue (y compris
le réordonnancement des candidats par la passe raisonnée), consigne les champs suivants :

- `status` : l'issue de l'identification (par exemple un produit clairement identifié ou une liste de
  candidats à départager).
- `n_candidates` : le nombre de candidats remontés par la recherche par similarité.
- `top1_score` : le score de similarité du meilleur candidat (arrondi à 4 décimales), c'est-à-dire à
  quel point le produit le mieux classé ressemble à la photo. Vaut une valeur vide s'il n'y a aucun
  candidat.
- `category_fine` et `category_conf` : la catégorie fine prédite et la confiance associée (la part du
  vote des plus proches voisins sur cette catégorie fine, arrondie à 4 décimales).
- `reasoned` : un drapeau vrai/faux indiquant si la passe d'identification raisonnée (l'appel au
  modèle de langage qui juge le top-15) a bien tourné pour cette demande, ou si elle a été sautée ou
  a échoué en silence.
- `reordered` : vrai si la passe raisonnée a fait remonter en tête un candidat différent du premier
  résultat brut de la recherche. C'est l'indicateur qui dit si le « jugement » de l'IA a effectivement
  corrigé le classement (par exemple écarter une coque de téléphone affichée à tort comme produit
  principal).
- `catalog_miss` : vrai si l'IA a estimé que le produit réel n'est dans aucune des fiches candidates
  (produit absent du catalogue). Vaut une valeur vide si la passe raisonnée n'a pas tourné.
- `anchor_usd` : le prix neuf de référence estimé par l'IA, en dollars, qui servira d'ancre au calcul
  de prix. Vaut une valeur vide si la passe raisonnée n'a pas tourné.
- `ask_question` : vrai si l'IA juge qu'une question discriminante (par exemple la capacité ou la
  variante exacte) est nécessaire pour lever une ambiguïté.
- `family_conf` : la confiance de l'IA sur la *famille* de produit (arrondie à 3 décimales), à
  distinguer de la confiance sur la variante exacte.
- `completeness` : le taux de complétude de la fiche assemblée (la proportion de champs attendus
  effectivement renseignés). Vaut une valeur vide si aucune fiche n'a pu être bâtie.
- `extraction_ms` et `reason_ms` : les deux temps qui dominent la latence de l'identification, en
  millisecondes (arrondis au dixième). Le premier est la durée de l'extraction des photos par le
  modèle de vision (lecture de la photo pour en tirer un titre probable et des attributs) ; le second
  est la durée de la passe raisonnée (l'appel qui juge le top-15). Mesurer ces deux temps séparément
  permet de savoir précisément lequel des appels au modèle de langage coûte cher quand une demande
  est lente. Ils valent zéro lorsque l'appel correspondant n'a pas eu lieu (par exemple une demande
  en texte seul, sans photo).

L'événement `price_done`, écrit à la fin du calcul de prix, consigne :

- `level` : le niveau de la cascade de prix réellement atteint, parmi `L1`, `L1.5`, `L2`, `L3` et
  `L4`. C'est cet indicateur qui permet de mesurer, sur le trafic réel, à quel point on s'appuie sur
  le prix catalogue (L1), sur le prix neuf estimé par IA (L1.5), sur les médianes de voisins ou de
  catégorie (L2/L3), ou sur la saisie manuelle de repli (L4).
- `method` : la méthode de calcul correspondante (par exemple `catalog_meta` pour L1, `llm_anchor`
  pour L1.5, `knn_median` pour L2, `category_median` pour L3, `fallback` pour L4).
- `suggested_eur` : le prix suggéré en euros.
- `has_anchor` : vrai si une ancre de prix neuf estimée par IA était fournie pour cette demande.
- `category` et `condition` : la catégorie et l'état déclaré (le choix du vendeur), qui permettent de
  croiser les niveaux de prix par type de produit et par état.

Un détail utile à connaître : il existe un troisième appel possible au modèle de langage,
le validateur visuel (« la photo du vendeur montre-t-elle bien le meilleur candidat ? »). Sa durée
est tracée à part dans un journal technique `vlm_validate_ms`, mais cet appel est volontairement
sauté quand la passe raisonnée a déjà tranché avec confiance, afin d'économiser un aller-retour
réseau et donc de la latence. C'est pour cela qu'il n'apparaît pas systématiquement dans les
journaux d'une demande.

### Les métriques du service web et le choix « opt-in »

L'instrumentation des métriques du service est volontairement « opt-in », c'est-à-dire qu'elle ne
s'active que si on le demande explicitement via la variable d'environnement `ENABLE_METRICS=true`
(elle est positionnée à `true` pour le service `api` dans la configuration de déploiement). On
expose ainsi un point d'accès `/metrics` que Prometheus vient lire. Les chemins `/metrics` et
`/health` sont exclus de la mesure pour ne pas se compter eux-mêmes.

Pourquoi rendre cette activation optionnelle : pendant les tests automatisés, le cadre de test
recrée l'application plusieurs fois dans le même processus. Or la bibliothèque de métriques
enregistre la jauge des demandes en cours dans un registre global partagé, ce qui provoque l'erreur
« Duplicated timeseries » (deux séries de mesures portant le même nom) à la deuxième création. En
laissant l'instrumentation désactivée par défaut et en ne l'allumant qu'en production, on évite
proprement ce conflit.

### Les métriques des traitements par lots

Le fichier `src/monitoring/push_metrics.py` envoie au Pushgateway les mesures des calculs ponctuels.
Le Pushgateway est joint par défaut à l'adresse `http://pushgateway:9091` (modifiable par la
variable d'environnement `PUSHGATEWAY_URL`), et toutes les mesures poussées sont regroupées sous le
nom de tâche `rakuten_batch`. Toutes les métriques métier portent le préfixe `rakuten_` pour les
distinguer des métriques techniques du service web (qui commencent par `http_`).

Deux types de calculs sont remontés. Le premier est la détection de dérive des données : avec le
temps, les nouvelles données peuvent s'éloigner de celles ayant servi à entraîner le modèle, ce qui
dégrade ses prédictions ; détecter cet écart permet de décider un réentraînement. Sept mesures sont
poussées : la part de colonnes qui ont dérivé (`rakuten_drift_share`), le nombre absolu de colonnes
ayant dérivé (`rakuten_drift_columns_count`), un voyant binaire indiquant si la dérive dépasse le
seuil (`rakuten_drift_detected`), le seuil d'alerte lui-même (`rakuten_drift_threshold`), l'horodatage
du dernier calcul (`rakuten_drift_last_run_timestamp`), et les tailles des deux échantillons comparés,
celui de référence et celui en cours (`rakuten_drift_reference_sample_size` et
`rakuten_drift_current_sample_size`).

Le second calcul est la décision de promotion de modèle, qui compare le modèle actuellement en
production (le « champion ») à un nouveau modèle candidat (le « challenger »), et ne remplace
l'ancien que si le nouveau est meilleur d'une marge minimale (appelée epsilon, pour éviter de
changer de modèle pour une amélioration insignifiante due au hasard). Les mesures poussées sont le
score de qualité du champion (`rakuten_promote_champion_f1`), celui du challenger
(`rakuten_promote_challenger_f1`), la marge minimale exigée (`rakuten_promote_epsilon`), la décision
prise sous forme d'un indicateur par valeur possible parmi `promoted`, `kept`,
`skipped_no_challenger` et `no_versions` (`rakuten_promote_decision`), et l'horodatage du dernier
calcul (`rakuten_promote_last_run_timestamp`). Le score de qualité utilisé ici est le « F1 pondéré »,
une note entre 0 et 1 qui résume la justesse d'un modèle de classification en équilibrant les
différentes catégories.

Point important de robustesse : si le Pushgateway n'est pas joignable (par exemple lors d'une
démonstration sans toute l'infrastructure démarrée), l'envoi échoue en douceur. La fonction écrit un
avertissement dans les journaux et renvoie `False`, mais ne fait jamais planter le calcul métier :
il serait absurde de perdre un long calcul de modèle à cause d'un simple problème de remontée de
mesures.

### Les trois tableaux de bord

Les tableaux de bord sont chargés automatiquement par Grafana au démarrage, ainsi que la connexion
à Prometheus (la « source de données »). Cette source porte un identifiant fixe, `rakuten-prom`, qui
est référencé en dur dans les tableaux ; sans cet identifiant fixe, Grafana en générerait un au
hasard et les graphiques afficheraient « source de données introuvable ».

- `golden_signals.json` couvre le service web avec les quatre signaux fondamentaux : la latence aux
  percentiles p50, p95 et p99 (avec la cible de p95 inférieur à 5 secondes), le trafic en requêtes
  par seconde réparti par point d'entrée, le taux d'erreurs serveur (les statuts de la famille 5xx,
  avec une cible inférieure à 1 % en régime établi) et la saturation via le nombre de demandes en
  cours.

- `evidently_drift.json` montre la dérive des données : la part de colonnes ayant dérivé comparée à
  son seuil, le nombre de colonnes touchées, un voyant « dérive détectée » (vert ou rouge), le temps
  écoulé depuis le dernier calcul, et les tailles des échantillons comparés. Le nom « Evidently »
  désigne la bibliothèque libre utilisée pour calculer cette dérive.

- `mlops_promote_gate.json` montre la décision de promotion de modèle : la décision du dernier
  calcul, le temps écoulé depuis, l'évolution comparée des scores du champion et du challenger, et la
  marge minimale exigée.

### L'infrastructure qui fait tourner le tout

L'ensemble est déclaré dans la configuration de déploiement (`docker-compose.yml`), avec des
versions figées pour la reproductibilité : Prometheus (`prom/prometheus:v2.55.1`) qui interroge ses
cibles toutes les 15 secondes, le Pushgateway (`prom/pushgateway:v1.10.0`) qui conserve les mesures
des traitements par lots, et Grafana (`grafana/grafana:11.3.1`) pour l'affichage. La configuration
de Prometheus liste quatre cibles à interroger : l'application elle-même (`api:8000`), le serveur
web et routeur d'entrée Traefik (`traefik:8080`, qui expose aussi ses propres métriques),
Prometheus lui-même, et le Pushgateway (`pushgateway:9091`). Pour ce dernier, l'option
`honor_labels: true` est essentielle : sans elle, Prometheus écraserait le nom de tâche
`rakuten_batch` posé par nos traitements par lots, et il deviendrait impossible de distinguer le
calcul de dérive de celui de promotion de modèle dans les graphiques.

---

## 4. Résultats (mesurés et vérifiés)

- Journaux JSON avec `request_id` : chaque demande est traçable de bout en bout. En production, la
  commande `docker compose logs api` affiche des lignes JSON corrélées, où l'on retrouve toutes les
  étapes d'une même demande en filtrant sur son `request_id`.

- Journaux métier `identify_done` et `price_done` : en plus des métriques HTTP, on lit pour chaque
  demande la décision réelle du pipeline (produit identifié, confiance, produit hors catalogue ou
  non, niveau de prix atteint) et la répartition de la latence entre les appels au modèle de langage
  (`extraction_ms`, `reason_ms`). Comme ils portent le même `request_id`, on relie sans effort la
  décision métier à la ligne HTTP technique de la même demande.

- Les quatre signaux fondamentaux sont instrumentés et visibles dans le tableau `golden_signals`.

- Trois tableaux de bord Grafana sont opérationnels : le service web, la dérive des données, et la
  décision de promotion de modèle.

- Le comportement est vérifié par des tests automatisés. Le fichier
  `tests/test_observability_logging.py` vérifie que le journal sort bien du JSON valide avec niveau
  et horodatage, que l'identifiant de demande se propage puis disparaît après nettoyage, que
  l'intercepteur génère et renvoie l'identifiant dans l'en-tête de réponse, qu'il réutilise celui
  fourni par le client, et que le niveau de détail (`LOG_LEVEL`) est bien respecté. Le fichier
  `tests/test_push_metrics.py` vérifie que le service Pushgateway est bien déclaré et possède un
  contrôle de santé, que l'option `honor_labels` est active, que les identifiants de source de
  données des tableaux concordent, que les noms de métriques attendus figurent bien dans les
  graphiques, que les sept mesures de dérive sont bien construites, et que l'envoi échoue en douceur
  (sans planter) quand le Pushgateway est injoignable.

> Chiffres à mettre en avant sur une diapositive : « quatre signaux fondamentaux (latence p95,
> trafic, erreurs, saturation) », « journaux JSON corrélés par `request_id` », « journaux métier
> `identify_done` / `price_done` avec les temps des appels au modèle de langage », « trois tableaux
> de bord Grafana couvrant à la fois l'application et les traitements de cycle de vie du modèle ».
> Capture d'écran recommandée : le tableau `golden_signals` rempli pendant une démonstration, à
> côté d'un extrait de journaux JSON portant tous le même `request_id` (une ligne `http_request`
> technique et la ligne `identify_done` métier de la même demande).

---

## 5. Critique (état de l'art comparé à notre réalisation)

### Points solides

- Les quatre signaux fondamentaux avec Prometheus et Grafana : on suit la combinaison et les
  métriques standard de l'industrie.

- Des journaux structurés en JSON avec un `request_id` propagé automatiquement : la corrélation de
  bout en bout d'une demande est en place.

- Des journaux métier dédiés (`identify_done`, `price_done`) au-delà des seules métriques techniques :
  on observe le contenu des décisions du pipeline (identification, produit hors catalogue, niveau de
  prix) et la répartition fine de la latence entre les appels au modèle de langage, ce qui rend le
  comportement réel du système lisible en production.

- Le Pushgateway pour les traitements par lots : on observe aussi le cycle de vie du modèle (dérive
  des données, décisions de promotion), pas seulement le service web.

- Trois tableaux de bord couvrant l'application et la partie modèle.

### Limites assumées

- Activation des métriques en mode optionnel : il faut penser à allumer la variable
  `ENABLE_METRICS`. C'est volontaire pour la stabilité des tests ; en production réelle, on
  l'activerait par défaut.

- Pas de règles d'alerte automatiques : il n'y a pas encore d'outil de déclenchement d'alertes (de
  type Alertmanager). On visualise les problèmes sur les tableaux de bord, mais le système ne
  prévient pas tout seul quand un seuil est franchi. C'est l'axe d'amélioration le plus net.

- Pas de traçage distribué (le troisième pilier, avec un outil comme OpenTelemetry) : on dispose des
  journaux et des métriques, mais pas du suivi d'une demande à travers plusieurs services. Ce n'est
  pas nécessaire à l'échelle actuelle, où l'application est essentiellement un service unique, mais
  c'est à mentionner comme évolution possible si l'architecture se complexifie.

---

## 6. Références

- SRE School, *Four golden signals* : https://sreschool.com/blog/four-golden-signals/
- Grafana, *Building dashboards with the four golden signals* : https://learn.grafana.com/building-effective-dashboards-with-the-four-golden-signals
- structlog, *documentation* : https://www.structlog.org/en/stable/
- Prometheus, *Pushgateway* : https://prometheus.io/docs/practices/pushing/

---

### En une phrase (pour la défense)

« On observe l'application via les quatre signaux fondamentaux (latence p95, trafic, erreurs,
saturation) affichés dans Prometheus et Grafana, complétés par des journaux métier (`identify_done`,
`price_done`) qui consignent la décision réelle du pipeline et les temps des appels au modèle de
langage ; des journaux JSON corrélés par un identifiant de demande (`request_id`) permettent de
suivre chaque demande de bout en bout, y compris les traitements de cycle de vie du modèle (dérive
des données et décisions de promotion) remontés via le Pushgateway. »

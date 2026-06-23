# Glossaire — tous les termes, en une ligne

> Le « décodeur » du projet : chaque mot technique des 17 rapports, expliqué **simplement**.
> But : un débutant peut lire n'importe quel rapport sans bloquer sur le jargon.

## Données & représentations
- **Embedding (vecteur)** — une liste de ~1024 nombres qui résume le *sens* d'un texte/image.
- **Normalisation L2** — ramener tous les vecteurs à la même longueur (1) pour ne comparer que la *direction* (= le sens).
- **Similarité cosinus** — mesure l'*angle* entre deux vecteurs : petit angle = sens proche.
- **FP16 (float16)** — nombres sur 16 bits au lieu de 32 → 2× moins de disque, précision suffisante.
- **mmap (memory-map)** — lire un gros fichier « à la demande » sans tout charger en RAM.
- **GroupKFold** — découper train/test en gardant tout un *groupe* (ici un produit) du même côté.
- **Stratification** — garder les mêmes proportions de catégories dans chaque jeu (train/val/test).
- **Data leakage (fuite)** — une info du test qui « fuit » dans l'entraînement → score gonflé, faux.
- **Pandera** — outil qui vérifie que chaque colonne respecte un *contrat* (type, plage, non-nul).

## Recherche (retrieval)
- **FAISS** — bibliothèque qui trouve très vite les vecteurs les plus proches parmi des millions.
- **HNSW** — type d'index FAISS en graphe à étages (« autoroute → rue ») : rapide + précis.
- **IVF_PQ** — index FAISS *compressé* (moins de RAM, recall plus bas).
- **ANN (recherche approchée)** — trouver « presque » les plus proches, beaucoup plus vite qu'exact.
- **Recall@k** — proportion de fois où le bon résultat est dans les *k* premiers.
- **RRF (Reciprocal Rank Fusion)** — fusionne plusieurs classements en regardant les *rangs* (formule `1/(60+rang)`).
- **OOD (Out-Of-Distribution)** — cas « inconnu » (produit hors catalogue) → on le signale, on n'invente pas.
- **Akinator** — lever le doute entre candidats proches en posant *la* question la plus discriminante.
- **Entropie de Shannon** — mesure « à quel point une question sépare bien » les candidats.

## IA génératives
- **VLM (Vision-Language Model)** — IA qui comprend les images (ici : lit la photo, vérifie le match).
- **LLM (Large Language Model)** — IA qui comprend/écrit du texte (ici : rédige l'annonce).
- **RAG / grounded (ancré)** — donner les *faits réels* à l'IA et lui interdire d'inventer.
- **Hallucination** — quand une IA invente une info plausible mais fausse.
- **Prompt** — les instructions données à l'IA ; Arctic distingue *prompt query* (requête) et *document*.
- **Température** — réglage de « créativité » du LLM (0,4 = factuel, peu inventif).

## Modèles & métriques
- **F1-score** — note 0-1 de qualité d'un classifieur (équilibre précision/rappel).
- **F1 pondéré vs macro** — pondéré = par taille des classes ; macro = toutes à égalité (sévère sur les rares).
- **Top-k accuracy** — la bonne réponse est-elle dans les *k* premières propositions ?
- **ECE (Expected Calibration Error)** — le modèle est-il *honnête* sur sa confiance ? (bas = oui).
- **Calibration Platt** — transformer les scores d'un SVM en vraies probabilités.
- **MAPE** — erreur moyenne en pourcentage (pour le prix).
- **k-NN** — prédire d'après les *k* exemples les plus proches (« comparables »).

## MLOps
- **MLflow** — le « carnet de labo » : enregistre chaque entraînement (réglages, scores, modèle).
- **Run** — une exécution d'entraînement tracée dans MLflow.
- **Model Registry** — l'étagère des modèles + leurs versions.
- **Alias `@Production`** — étiquette qui désigne *le* modèle servi (on le change en bougeant un pointeur).
- **Champion / challenger** — modèle en place vs candidat ; on remplace seulement si meilleur (+ ε).
- **DAG** — graphe de tâches enchaînées (Airflow) avec ordre et dépendances.
- **Airflow** — le planificateur qui lance le ré-entraînement automatiquement.
- **Drift (dérive)** — les données récentes ne ressemblent plus à celles d'entraînement.
- **PSI / KS / Chi²** — tests statistiques qui mesurent la dérive d'une variable.
- **Evidently** — outil qui compare deux jeux de données et fait un rapport de drift visuel.
- **DVC** — versionne les *données* (comme git pour le code).
- **BentoML** — empaquette un modèle pour le servir comme une API.

## Observabilité & infra
- **4 golden signals** — latence, trafic, erreurs, saturation : les 4 métriques santé d'un service.
- **Percentile p95** — la valeur en dessous de laquelle tombent 95 % des cas (plus honnête que la moyenne).
- **Prometheus** — collecte les métriques ; **Grafana** — les affiche en tableaux de bord.
- **structlog** — logs au format machine (JSON) plutôt que texte libre.
- **request_id** — identifiant unique par requête → suivre tous ses logs de bout en bout.
- **Pushgateway** — passerelle où les jobs batch *poussent* leurs métriques (Prometheus les scrape).
- **Docker / conteneur** — empaqueter une app + ses dépendances → « marche partout pareil ».
- **Build multi-stage** — construire dans une image « atelier », ne garder que le nécessaire (léger, sûr).
- **Docker Compose** — lancer plusieurs conteneurs ensemble en une commande.
- **Kubernetes (k8s)** — orchestrer/scaler des conteneurs en prod ; **Deployment** (sans état),
  **StatefulSet** (avec état), **Ingress** (routage), **HPA** (autoscaling).

## Qualité & sécurité
- **CI/CD** — re-tester (CI) et publier (CD) automatiquement à chaque modification.
- **GHCR** — le registre d'images Docker de GitHub.
- **SAST / SCA** — analyse du *code* (SAST) / audit des *dépendances* (SCA) pour la sécurité.
- **pip-audit** — scanne les dépendances Python pour des failles connues (CVE).
- **JWT** — jeton signé qui prouve qu'un utilisateur est authentifié ; **bcrypt** — hachage de mot de passe.
- **Path-traversal** — attaque qui sort du dossier autorisé (ex. `../../`) — bloquée chez nous.
- **Capability-URL** — une URL imprévisible (uuid4) qui sert de « clé » d'accès à une ressource.

## Explainability
- **SHAP** — explique *quelles caractéristiques* ont poussé une prédiction (valeurs de Shapley).
- **t-SNE / UMAP** — projeter des vecteurs en 2D pour *voir* si les catégories se regroupent.
- **Model Card** — fiche d'identité d'un modèle (usage, données, métriques, limites).

## Conventions internes (notre méthode)
- **R3, R7, R11, R19…** — nos « règles d'or » (anti-fuite, garde-fou dimension, garde-fou norme zéro,
  ancré-avant-génératif…).
- **D-035, D-011…** — nos décisions d'architecture tracées (ADR), datées et justifiées.
- **lazy loading** — charger une ressource lourde seulement à la première utilisation.
- **idempotent** — relancer ne refait pas le travail déjà fait (skip si déjà produit).
- **best-effort / fail-soft** — si un composant secondaire échoue, on continue sans casser le flux.

# 05. Les IA génératives ancrées dans les faits (VLM et LLM "grounded")

> Le projet utilise deux intelligences artificielles génératives. L'une "voit" (elle lit la photo d'un objet), l'autre "rédige" (elle écrit l'annonce de vente). Les deux sont volontairement bridées par des faits réels pour les empêcher d'inventer. C'est le garde-fou anti-invention du projet, du début à la fin.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre, en partant de zéro

Le projet aide une personne à revendre un objet d'occasion (un téléphone, une console, un outil, etc.). Pour cela, il faut deux compétences que des IA génératives savent fournir.

- **VLM** veut dire "Vision-Language Model", c'est-à-dire un modèle qui comprend les images en plus du texte. Concrètement, c'est une IA à qui on montre une photo et qui répond en mots. Dans le projet, elle sert à deux choses. D'abord elle lit la photo prise par le vendeur et propose un titre probable (par exemple "iPhone 13 noir 128 Go") plus une liste d'attributs observés (marque, couleur, capacité de stockage). Ensuite elle vérifie : "la photo du vendeur montre-t-elle bien le même produit que l'image officielle du catalogue ?".

- **LLM** veut dire "Large Language Model", c'est-à-dire un modèle de langage entraîné sur d'énormes quantités de texte. C'est une IA qui écrit du texte fluide. Dans le projet, elle rédige le titre et la description de l'annonce de vente.

- **RAG** veut dire "Retrieval-Augmented Generation", soit "génération assistée par récupération de faits". L'idée est simple : au lieu de laisser l'IA écrire de mémoire (ce qui la pousse à inventer), on lui fournit d'abord les vrais faits (la vraie fiche du produit qu'on a retrouvé dans le catalogue) et on lui demande de ne rédiger qu'à partir de ces faits. On appelle cela "ancrer" l'IA dans les faits (en anglais "grounding").

### Pourquoi c'est crucial

Un modèle de langage invente par nature. Il complète une phrase avec ce qui est statistiquement plausible, que ce soit vrai ou faux. Si on lui dit simplement "écris une annonce pour un iPhone 13", il fabriquera des caractéristiques techniques qui ont l'air crédibles mais qui peuvent être fausses. Le RAG change la nature de la tâche : on ne lui demande plus de "générer" (action libre, propice à l'invention) mais de "reformuler ces faits précis" (action contrainte, vérifiable).

### Pour aller plus loin (lecteur technique)

- Le projet sépare strictement les rôles. Une première étape, appelée "retrieval", retrouve le produit dans le catalogue : c'est elle qui décide de l'identité de l'objet. Le VLM ne fait que vérifier visuellement, et le LLM ne fait que rédiger. Aucune des deux IA génératives ne décide de l'identité du produit, ce qui supprime la principale source d'invention.

- L'ancrage est testable. Un mot présent dans la description générée doit appartenir soit aux mots du prompt, soit aux mots des faits fournis. Si un mot apparaît sans venir de l'une de ces deux sources, c'est une invention détectable automatiquement.

---

## 2. État de l'art

- Le RAG est aujourd'hui l'un des moyens les plus efficaces pour ancrer un modèle de langage dans des faits : on lui fournit le contexte au moment précis où il génère.
- Les bonnes pratiques reconnues contre l'invention sont au nombre de trois : récupérer un contexte de bonne qualité, écrire des règles d'ancrage explicites dans le prompt (par exemple "n'utilise que le contexte fourni"), et exiger une sortie structurée au format JSON (un format texte standard où chaque information porte un nom, ce qui contraint le modèle et facilite la vérification automatique).
- Les VLM inventent eux aussi. Le RAG les contraint à s'appuyer sur la connaissance qu'on leur fournit plutôt que sur leur mémoire interne.
- Une limite connue subsiste : un modèle peut mal interpréter une source, ou ne pas se rendre compte que la source ne contient pas la réponse cherchée.

---

## 3. Notre implémentation (exactement ce qui a été fait)

Tous les appels d'IA passent par OpenRouter, un service en ligne qui donne accès à de nombreux modèles via une seule interface. Le modèle utilisé par défaut est **`google/gemma-4-31b-it`**, un modèle capable de traiter à la fois le texte et les images. Il sert les trois usages décrits ci-dessous.

### Le client d'accès au modèle (`src/llm/openrouter_client.py`)

C'est la brique technique qui parle à OpenRouter.

- La fonction `chat_completion` envoie un texte au modèle et récupère sa réponse. Elle utilise une **température de 0,4**. La température règle la créativité du modèle entre 0 (toujours la réponse la plus probable, donc très factuel) et 1 (réponses variées et créatives) : à 0,4 le modèle reste donc plutôt factuel. La longueur de réponse est limitée à **1024 jetons** (un "jeton", ou "token", est un petit morceau de mot ; 1024 jetons valent à peu près 700 à 800 mots).
- Si un appel échoue à cause d'une saturation du service (erreur 429) ou d'un souci côté serveur (erreurs 500, 502, 503), la fonction réessaie jusqu'à **3 fois**, avec un délai d'attente qui double à chaque tentative (2 secondes, puis 4, puis 8). C'est une attente "exponentielle" classique pour laisser le service se rétablir.
- La fonction `is_available` indique simplement si une clé d'accès OpenRouter est configurée. Si la clé est absente, le projet ne plante pas : il bascule sur un mode de remplacement (un "mock", c'est-à-dire une fausse réponse de démonstration). On appelle cela la dégradation propre : l'absence d'un service externe n'arrête pas l'application.
- La fonction `translate_to_english` traduit la requête du français vers l'anglais avant la recherche, car le catalogue de produits est en anglais. Cette traduction se fait à température 0 (résultat le plus stable possible) et limite la réponse à 128 jetons.

### L'extraction depuis la photo (`src/vlm/photo_extraction.py`)

C'est l'étape où le VLM regarde les photos du vendeur et en tire une description exploitable.

- La fonction `extract(photo_paths)` reçoit une ou plusieurs photos et renvoie un objet contenant un titre probable (`title_guess`) et un dictionnaire d'attributs observés (`attributes`).
- Le réglage **`MAX_PHOTOS_PER_CALL = 4`** signifie que jusqu'à 4 vues du même objet passent dans **un seul appel** au modèle. Cela coûte moins cher (un appel au lieu de quatre) et donne au modèle un contexte commun pour mieux raisonner. Chaque photo est convertie en "data-URL base64", c'est-à-dire encodée directement en texte pour être envoyée dans la requête, sans hébergement de fichier.
- Pour garantir des résultats reproductibles d'un essai à l'autre, l'extraction tourne à **température 0** (réponse la plus déterministe possible) avec une graine aléatoire fixe (`seed = 42`). La longueur de réponse est limitée à **250 jetons** et le délai d'attente maximal est de **90 secondes**. Un fournisseur de calcul précis peut être épinglé via une variable d'environnement pour fixer la précision numérique du modèle, sinon OpenRouter choisit automatiquement.
- Le prompt demande explicitement une réponse au format **JSON** de la forme `{title, attributes{brand, color, capacity, model, visible_text}}`. La lecture de la réponse est volontairement tolérante : elle sait extraire le JSON même s'il est entouré de balises de code (les trois accents graves) ou noyé dans du texte. Si le modèle répond malgré tout en texte libre, ce texte est repris tel quel comme requête de secours.
- Si la clé OpenRouter est absente, la fonction lève une erreur claire (`PhotoExtractionUnavailable`). L'application répond alors par un message explicite invitant le vendeur à décrire l'objet par écrit, et le parcours sans photo continue de fonctionner.

### Le vérificateur visuel (`src/vlm/validator.py`)

C'est l'étape où le VLM confirme que la photo du vendeur correspond bien au produit retrouvé.

- La fonction `validate_top1(user_photos, catalog_image_url, title)` compare les photos du vendeur à l'image officielle du meilleur candidat retrouvé dans le catalogue. Elle renvoie un verdict au format JSON strict : `match` (vrai ou faux), `confidence` (un score de confiance entre 0 et 1) et `reason` (une phrase courte expliquant le verdict).
- Le réglage **`MAX_USER_PHOTOS = 2`** limite la comparaison aux deux premières photos du vendeur, car la correspondance se joue surtout sur la vue principale. La réponse est limitée à 120 jetons et le délai d'attente à 60 secondes.
- Le prompt précise au modèle d'ignorer l'état, l'arrière-plan et les accessoires, et de ne juger que le modèle du produit.
- Cette vérification est un bonus, jamais un bloqueur. Si une condition manque (pas de photo, pas d'image catalogue, ou modèle indisponible), la fonction renvoie simplement `None` et l'identification du produit continue sans elle. Le verdict, quand il existe, sert à afficher un badge de confiance visuelle dans l'application ; c'est toujours l'humain qui valide, jamais une décision automatique.

### Le rédacteur ancré (`src/llm/01_prompt_templates.py` et `src/llm/02_rag_grounded_writer.py`)

C'est l'étape où le LLM écrit l'annonce finale à partir des faits.

- Le prompt suit une structure imposée : **rôle, puis instruction, puis contexte de faits, puis format de sortie JSON**. L'instruction contient des consignes explicites contre l'invention : "n'utilise que le contexte fourni", "pas d'invention de caractéristiques absentes du contexte". Elle impose aussi de reprendre exactement l'état déclaré par le vendeur (le champ `seller_condition`), pour éviter que le modèle ne transforme par exemple un "bon état" choisi par le vendeur en "très bon état" inventé.
- La fonction `extract_useful_sentences(reviews, top_n)` sélectionne les phrases qui serviront d'ancrage. Elle découpe les textes en phrases, garde celles d'au moins **50 caractères** (`MIN_SENTENCE_CHARS`), supprime les doublons, puis trie par longueur décroissante pour ne conserver que les **5 meilleures** (`TOP_N_GROUNDING_SENTENCES`). Ces phrases proviennent de textes réels et non d'une invention du modèle.
- Le code repose sur une abstraction `LLMWriter`, c'est-à-dire une interface commune avec deux implémentations interchangeables : `OpenRouterWriter` qui appelle le vrai modèle, et `MockLLMWriter` qui produit une fausse annonce de démonstration. Le projet bascule automatiquement de l'une à l'autre selon que la clé d'accès est présente ou non. C'est ce qui rend la démonstration robuste et le code facile à tester sans dépendre du réseau.
- Le résultat (`GeneratedListing`) conserve la liste exacte des phrases d'ancrage utilisées (`grounding_sentences_used`). On garde donc une trace de ce qui a servi à écrire l'annonce : c'est la traçabilité de l'ancrage.

---

## 4. Résultats (mesurés et observés)

- **Preuve concrète d'ancrage.** Sur un produit testé, la mention "Snapdragon 732G" (le nom d'un processeur) apparaît dans l'annonce générée uniquement parce qu'elle figure dans la vraie fiche du produit. Elle ne vient ni du titre saisi, ni de la mémoire du modèle. C'est la démonstration que l'annonce s'appuie bien sur les faits fournis.
- **Vérificateur visuel en fonctionnement.** Sur une photo d'iPhone, le modèle renvoie `{match: true, confidence: 1.0, reason: "diagonal dual-camera layout"}`, c'est-à-dire une correspondance confirmée avec une raison factuelle et observable (la disposition en diagonale du double appareil photo).
- **Dégradation propre vérifiée.** Sans clé OpenRouter, la fonctionnalité de description bascule sur le mode de remplacement (un titre générique reconnaissable), pendant que l'identification du produit et l'estimation du prix, qui tournent en local, continuent normalement.
- **Quel modèle lit le mieux les photos.** Quatre modèles de lecture d'image disponibles via le
  service OpenRouter ont été comparés sur 93 produits réels : Gemma 4 31B, MiMo V2.5, Gemini 2.5
  Flash Lite et Qwen 3.5 Flash. Tous identifient aussi bien le bon produit (aucun écart
  statistiquement significatif entre eux), mais **Qwen 3.5 Flash remplit la fiche plus complètement**
  (différence réelle, confirmée par un test apparié) tout en étant **le moins cher**. Il a donc été
  retenu comme modèle de lecture par défaut. Détail technique important : pour cette tâche de simple
  lecture d'image, on désactive le « raisonnement » du modèle, car certains modèles passeraient
  sinon tout leur budget de réponse à réfléchir sans jamais produire le résultat demandé.

- **L'apport réel de la photo, mesuré sur la qualité de la fiche.** Une étude rigoureuse sur
  **93 annonces réelles** compare ce que reçoit le système en entrée. La mesure principale est la
  **complétude** de la fiche produite, c'est-à-dire la part des caractéristiques attendues pour ce
  type de produit qui sont effectivement remplies, et non seulement la grande catégorie.

  | Entrée du système | Complétude de la fiche | Bon produit identifié |
  |---|---|---|
  | Texte du vendeur seul | 0,505 | 0,720 |
  | Une seule photo | 0,641 | 0,656 |
  | Plusieurs photos | 0,699 | 0,785 |
  | Plusieurs photos + description vendeur | 0,694 | 0,850 |

  Trois enseignements, tous appuyés par des tests statistiques appariés (chaque produit est son
  propre point de comparaison). D'abord, **la photo est le maillon décisif** : sur les produits dont
  la description vendeur est pauvre, passer du texte seul à une photo fait gagner 0,145 de complétude
  (résultat hautement significatif), et plusieurs photos valent mieux qu'une. Ensuite, **la
  description écrite du vendeur n'apporte rien** une fois les photos disponibles : l'absence d'effet
  a été formellement prouvée par un test d'équivalence dédié, après avoir écarté un faux gain dû au
  fait que, sur certains produits, le texte du vendeur contenait déjà la réponse. Enfin, **traduire
  l'entrée en anglais ne change rien**. Conséquence produit : on peut alléger la saisie demandée au
  vendeur sans dégrader la fiche.

> 📊 **Chiffres et faits pour la slide** : lecture des photos par Qwen 3.5 Flash (champion d'une
> comparaison de quatre modèles, retenu pour sa complétude et son coût), jusqu'à 4 vues en un seul
> appel, sortie JSON, raisonnement désactivé, déterminisme à température 0 avec graine fixe pour
> l'extraction et température 0,4 pour la rédaction ; la photo prouvée comme maillon décisif (gain de
> 0,145 de complétude par rapport au texte seul) ; description vendeur prouvée sans effet (test
> d'équivalence) ; preuve d'ancrage avec "Snapdragon 732G" venu des faits et non de la mémoire ;
> dégradation propre par mode de remplacement quand le service externe est absent.
> 📸 **Capture suggérée** : l'annonce générée affichée à côté de la fiche catalogue (les caractéristiques correspondent) et le badge de correspondance visuelle dans l'application.

---

## 5. Analyse critique (état de l'art comparé à notre travail)

**Points solides :**

- ✅ RAG avec règles d'ancrage explicites et sortie JSON : ce sont exactement les bonnes pratiques recommandées.
- ✅ Rôles séparés (la récupération identifie, le VLM vérifie, le LLM rédige), ce qui supprime la principale source d'invention.
- ✅ Comportement non bloquant partout : le vérificateur et l'extraction ne cassent jamais le parcours du vendeur.
- ✅ Dégradation propre (mode de remplacement) et abstraction du rédacteur, ce qui rend la démonstration robuste et le code testable.
- ✅ Optimisation des coûts : 4 vues en un seul appel et température basse pour rester factuel.

**Limites assumées :**

- **Dépendance à un service externe.** Le modèle Gemma passe par OpenRouter, ce qui implique un coût, une latence et une disponibilité non garantie. Le mode de remplacement atténue le problème mais ne supprime pas la dépendance.
- **Ancrage sur la fiche, pas encore sur les avis acheteurs.** Aujourd'hui l'annonce est ancrée dans la description du produit. L'enrichir avec les avis acheteurs réels apporterait du naturel et des arguments de vente : c'est une amélioration prévue, qui demande de rapprocher les avis du produit au moment voulu.
- **Confusion entre générations proches.** Le VLM peut hésiter entre deux modèles très similaires (par exemple un iPhone 13 et un iPhone 14). C'est mesuré et assumé : le questionnaire interactif et l'humain tranchent. Le projet ne prétend pas à une précision de 100 %.
- **Pas de citation phrase par phrase dans l'annonce.** Une bonne pratique avancée consisterait à indiquer dans l'annonce de quel passage source vient chaque affirmation. Ce n'est pas encore fait : c'est une piste d'amélioration.

---

## 6. Références

- Prompting Guide, "Retrieval Augmented Generation (RAG) for LLMs" : https://www.promptingguide.ai/research/rag
- Lewis et al., "Retrieval-Augmented Generation" (article fondateur du RAG) : https://arxiv.org/abs/2005.11401
- arXiv 2407.12858, "Grounding and evaluation for LLMs" (synthèse) : https://arxiv.org/pdf/2407.12858
- arXiv 2501.03995, "RAG-Check : evaluating multimodal RAG" : https://arxiv.org/pdf/2501.03995

---

### En une phrase (pour la défense)

*« Nos IA génératives ne devinent jamais. Le produit est d'abord retrouvé dans le catalogue, puis un modèle qui lit les images (Gemma 4 31B) vérifie visuellement la correspondance, et un modèle de langage rédige l'annonce uniquement à partir de la vraie fiche du produit, avec des règles d'ancrage explicites et une sortie JSON. On le prouve : une caractéristique comme "Snapdragon 732G" vient des faits fournis, pas de la mémoire du modèle. Et si le service externe tombe, tout continue de fonctionner grâce à un mode de remplacement local. »*

# 05. Les IA génératives ancrées dans les faits (VLM et LLM "grounded")

> Le projet utilise deux intelligences artificielles génératives. L'une "voit" (elle lit la photo d'un objet, puis la JUGE par rapport à de vrais candidats), l'autre "rédige" (elle écrit l'annonce de vente). Les deux sont volontairement bridées par des faits réels pour les empêcher d'inventer. C'est le garde-fou anti-invention du projet, du début à la fin.

> Le rôle du modèle qui "voit" a été élargi : en plus de lire la photo et de vérifier la correspondance, il pose désormais un **jugement raisonné** sur une liste de vrais produits candidats. Ce jugement reste strictement ancré dans les faits : le modèle ne peut JAMAIS introduire un produit qui n'est pas dans la liste, et chaque caractéristique qu'il propose doit citer sa source. Toute cette partie est décrite en détail à la section 3 ("L'identification raisonnée").

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre, en partant de zéro

Le projet aide une personne à revendre un objet d'occasion (un téléphone, une console, un outil, etc.). Pour cela, il faut deux compétences que des IA génératives savent fournir.

- **VLM** veut dire "Vision-Language Model", c'est-à-dire un modèle qui comprend les images en plus du texte. Concrètement, c'est une IA à qui on montre une photo et qui répond en mots. Dans le projet, elle sert à trois choses. D'abord elle lit la photo prise par le vendeur et propose un titre probable (par exemple "iPhone 13 noir 128 Go") plus une liste d'attributs observés (marque, couleur, capacité de stockage). Ensuite, elle réalise une "identification raisonnée" : on lui montre les 15 vrais produits candidats que la recherche a trouvés (résumés en texte) et on lui demande de JUGER lequel correspond, ou de signaler qu'aucun ne correspond. Enfin elle peut vérifier visuellement : "la photo du vendeur montre-t-elle bien le même produit que l'image officielle du catalogue ?".

- **LLM** veut dire "Large Language Model", c'est-à-dire un modèle de langage entraîné sur d'énormes quantités de texte. C'est une IA qui écrit du texte fluide. Dans le projet, elle rédige le titre et la description de l'annonce de vente.

- **RAG** veut dire "Retrieval-Augmented Generation", soit "génération assistée par récupération de faits". L'idée est simple : au lieu de laisser l'IA écrire de mémoire (ce qui la pousse à inventer), on lui fournit d'abord les vrais faits (la vraie fiche du produit qu'on a retrouvé dans le catalogue) et on lui demande de ne rédiger qu'à partir de ces faits. On appelle cela "ancrer" l'IA dans les faits (en anglais "grounding"). Le même principe est étendu à l'identification raisonnée : le modèle ne juge qu'à partir des 15 candidats réels fournis, jamais de sa mémoire interne.

- **Le partage des rôles, en une image.** Le moteur de recherche par similarité apporte la CONNAISSANCE : il sort du catalogue les 15 produits réels les plus proches. Le modèle génératif apporte le JUGEMENT : il choisit, parmi ces 15 produits réels, lequel est le bon, ou dit honnêtement qu'aucun ne l'est. C'est volontaire : on laisse l'IA faire ce qu'elle fait de mieux (comparer, juger une image) tout en l'empêchant de faire ce qu'elle fait de pire (inventer un produit qui n'existe pas dans nos données). On appelle ce principe "grounded avant génératif" : d'abord les faits, ensuite seulement le jugement.

- **"Catalog-miss" (produit absent du catalogue).** C'est le cas où le vrai produit du vendeur n'est dans aucun des 15 candidats (par exemple une carte graphique d'une génération qu'on n'a pas en base). Plutôt que de coller de force sur le candidat le plus ressemblant et de mentir, l'IA a le droit de déclarer "catalog_miss" : la fiche devient alors une ESTIMATION clairement étiquetée comme telle, et on ne traite pas les caractéristiques du mauvais candidat comme des faits.

### Pourquoi c'est crucial

Un modèle de langage invente par nature. Il complète une phrase avec ce qui est statistiquement plausible, que ce soit vrai ou faux. Si on lui dit simplement "écris une annonce pour un iPhone 13", il fabriquera des caractéristiques techniques qui ont l'air crédibles mais qui peuvent être fausses. Le RAG change la nature de la tâche : on ne lui demande plus de "générer" (action libre, propice à l'invention) mais de "reformuler ces faits précis" (action contrainte, vérifiable).

### Pour aller plus loin (lecteur technique)

- Le projet sépare strictement les rôles. Une première étape, appelée "retrieval", retrouve les candidats dans le catalogue : c'est elle qui borne l'espace des identités possibles (les 15 produits réels). Le VLM JUGE à l'intérieur de cet espace (il choisit le bon candidat ou déclare le catalog-miss), il VÉRIFIE visuellement, et le LLM ne fait que rédiger. Aucune des IA génératives ne peut faire apparaître une identité hors des candidats réels, ce qui supprime la principale source d'invention. Initialement, le retrieval décidait seul de l'identité (le top-1 brut) ; désormais le VLM peut REORDONNER les candidats pour faire remonter le bon, mais toujours en restant dans la liste fournie.

- Le garde-fou anti-hallucination est implémenté concrètement (`src/vlm/reasoned_identification.py`, fonction `_parse`). Trois protections principales : (1) si le modèle nomme un produit (`chosen_parent_asin`) qui n'est pas dans les 15 candidats ET qu'il n'a pas déclaré de catalog-miss, on ignore son choix et on retombe sur le candidat n°1 du retrieval, en remettant sa confiance à zéro (le modèle n'a pas réellement endossé un candidat valide, donc l'aval ne doit pas le traiter comme un fait certain) ; (2) toute caractéristique ("facette") dont la source citée est invalide (ni "observé", ni "analogie", ni un index de candidat existant) est jetée, jamais d'affirmation non sourcée ; (3) le prix neuf de référence est conservé même sans preuve, mais il est alors une ESTIMATION explicitement étiquetée, pas un fait catalogue.

- L'ancrage de la rédaction reste testable. Un mot présent dans la description générée doit appartenir soit aux mots du prompt, soit aux mots des faits fournis. Si un mot apparaît sans venir de l'une de ces deux sources, c'est une invention détectable automatiquement.

- Trois provenances pour les caractéristiques jugées par l'IA, qui montrent le degré d'ancrage de chaque information : "observé" (le modèle l'a vu sur la photo du vendeur), un numéro de candidat (l'information vient d'une vraie fiche du catalogue, c'est le plus solide), ou "analogie" (le modèle l'estime à partir de produits comparables quand le produit exact manque). Seules les deux premières sont injectées dans la fiche comme des faits ; l'"analogie" n'est jamais affirmée comme une vérité.

---

## 2. État de l'art

- Le RAG est aujourd'hui l'un des moyens les plus efficaces pour ancrer un modèle de langage dans des faits : on lui fournit le contexte au moment précis où il génère.
- Les bonnes pratiques reconnues contre l'invention sont au nombre de trois : récupérer un contexte de bonne qualité, écrire des règles d'ancrage explicites dans le prompt (par exemple "n'utilise que le contexte fourni"), et exiger une sortie structurée au format JSON (un format texte standard où chaque information porte un nom, ce qui contraint le modèle et facilite la vérification automatique).
- Les VLM inventent eux aussi. Le RAG les contraint à s'appuyer sur la connaissance qu'on leur fournit plutôt que sur leur mémoire interne.
- Une limite connue subsiste : un modèle peut mal interpréter une source, ou ne pas se rendre compte que la source ne contient pas la réponse cherchée.

---

## 3. Notre implémentation (exactement ce qui a été fait)

Tous les appels d'IA passent par OpenRouter, un service en ligne qui donne accès à de nombreux modèles via une seule interface. Deux modèles cohabitent, chacun sur la tâche pour laquelle il a été retenu :

- **Pour tout ce qui regarde une image** (lecture de la photo, identification raisonnée, vérification visuelle), le modèle par défaut est **`qwen/qwen3.5-flash-02-23`** (Qwen 3.5 Flash). Il a été choisi à l'issue d'une comparaison de quatre modèles de vision, pour sa complétude de fiche et son faible coût (voir section 4). Ce choix est centralisé dans `src/vlm/photo_extraction.py` (variable `VLM_MODEL`) et réutilisé par le validateur et l'identification raisonnée. Chaque usage est surchargeable indépendamment par variable d'environnement (`PHOTO_VLM_MODEL`, `PHOTO_VLM_VALIDATOR_MODEL`, `PHOTO_VLM_IDENTIFY_MODEL`).

- **Pour la rédaction de l'annonce en français** (titre + description) et pour la traduction de la requête, le modèle par défaut est **`google/gemma-4-31b-it`** (Gemma 4 31B), défini dans `src/llm/openrouter_client.py` (`DEFAULT_LLM_MODEL`). C'est une tâche purement textuelle, qui n'a pas besoin de vision.

Ce découpage a évolué : historiquement un seul modèle (Gemma) servait les trois usages ; depuis le benchmark de modèles de vision, les tâches "image" sont passées sur Qwen, tandis que la rédaction texte est restée sur Gemma. Les sous-sections ci-dessous détaillent chaque brique.

### Le client d'accès au modèle texte (`src/llm/openrouter_client.py`)

C'est la brique technique qui parle à OpenRouter pour les tâches de TEXTE (rédaction et traduction). Les tâches qui regardent une image ont leur propre client, plus bas (extraction, validateur, identification raisonnée).

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

### L'identification raisonnée (`src/vlm/reasoned_identification.py`)

C'est une étape centrale du pipeline. Au lieu de faire confiance aveuglément au premier résultat de la recherche, on demande au modèle de vision de JUGER, à partir des photos, lequel des vrais candidats correspond.

- **Le principe (le "pourquoi").** Le moteur de recherche par similarité est excellent pour rapprocher des produits proches, mais il ne "comprend" pas l'image : son premier résultat peut être un accessoire (par exemple une coque d'iPhone affichée comme s'il s'agissait de l'iPhone lui-même). Le moteur de recherche apporte donc la CONNAISSANCE (les 15 candidats réels), et le modèle génératif apporte le JUGEMENT (lequel est le bon, et avec quelle confiance). C'est le coeur du principe "grounded avant génératif" décrit en section 1.

- **L'entrée et la sortie.** La fonction `reason_identify(user_photo_paths, candidates, observed, seller_text)` fait **un seul appel** à OpenRouter. Elle envoie : 1 à 2 photos du vendeur (`MAX_USER_PHOTOS = 2`, encodées en data-URL base64), les 15 fiches candidates **résumées en texte** (`MAX_CANDIDATES = 15`, et non leurs 15 images : c'est une économie volontaire de jetons), les attributs déjà observés sur la photo, et le texte du vendeur. Elle renvoie un objet JSON structuré contenant notamment : la famille du produit (`product_family`) et sa confiance (`family_confidence`), le candidat choisi (`chosen_parent_asin`), le drapeau catalog-miss (`catalog_miss`), un prix neuf de référence en dollars (`reference_new_price_usd`, l'"ancre prix") et sa confiance, les fiches qui ont servi à estimer ce prix (`price_anchor_evidence`), un éventuel besoin de question discriminante (`ask_question` + `facet_question`), et une liste de caractéristiques sourcées (`facets`).

- **Réutilisation et déterminisme.** Pour ne pas dupliquer du code, ce module réutilise les fonctions `post_with_retry` (l'appel HTTP avec réessais) et `_to_data_url` (l'encodage d'image) déjà écrites pour l'extraction photo : il n'y a donc qu'un seul client HTTP de vision. Comme l'extraction, l'appel tourne à **température 0** avec une **graine fixe** et le **raisonnement désactivé**, pour des résultats reproductibles d'un essai à l'autre. Le budget de sortie par défaut est de **700 jetons** (`IDENTIFY_MAX_TOKENS`), un peu plus large que l'extraction car la sortie est plus riche.

- **Les garde-fous anti-hallucination (le coeur du "grounding").** La lecture de la réponse (`_parse`) valide tout : (1) une confiance est ramenée dans l'intervalle [0, 1] ; (2) si le candidat choisi n'est pas dans les 15 candidats ET qu'aucun catalog-miss n'est déclaré, on retombe sur le candidat n°1 du retrieval et on remet la confiance à zéro (le modèle a "halluciné" un identifiant, on ne le suit pas) ; (3) une caractéristique dont la source citée est invalide est jetée ; (4) le prix de référence est GARDÉ même sans preuve, car c'est une estimation honnêtement étiquetée "prix neuf estimé par IA" et c'est nettement mieux que de retomber sur une médiane de catégorie polluée (le fameux "11 € pour une montre à 150 €"). Pour calculer ce prix neuf, le modèle est explicitement invité à EXCLURE les candidats qui sont des accessoires ou des lots (coque, câble, chargeur, bundle, etc.) car leurs prix ne sont pas le prix du produit.

- **La dégradation propre (non bloquante).** Si la clé OpenRouter est absente, si le modèle est indisponible, si la réponse est inexploitable, ou en cas d'exception quelconque, la fonction renvoie simplement `None`. Le pipeline garde alors le classement du retrieval et la cascade de prix habituelle. Cette étape ne fait JAMAIS planter l'identification et ne produit jamais de fiche vide : c'est un bonus, jamais un point de passage obligé.

- **L'effet concret : le bon produit remonte en tête.** Le candidat choisi par le jugement est RÉORDONNÉ pour passer en première position (logique dans `src/api/main.py`, endpoint `/identify`). Conséquence : la fiche produite, le prix suggéré et la vérification visuelle portent ensuite sur le BON produit. Auparavant, le premier résultat du retrieval pouvait être un accessoire, et toute la fiche en héritait.

### Le texte du vendeur fait foi (`src/api/main.py`, fonction `_seller_text_best_match`)

Un garde-fou déterministe complète le jugement de l'IA, parce qu'un modèle rapide ignore parfois la consigne de respecter ce que le vendeur a écrit.

- **Le principe.** Si le texte de précisions saisi par le vendeur nomme un produit qui est présent dans les candidats, ce candidat est retenu de façon **déterministe** (sans dépendre du modèle). La métadonnée du vendeur fait alors autorité : c'est une donnée fiable que l'humain a fournie volontairement.

- **Le critère de correspondance.** On exige une correspondance forte : au moins 2 mots discriminants du texte présents dans le titre du candidat, ET au moins 50 % des mots du texte couverts. Détail important : on garde les **numéros de modèle même à un seul chiffre** (par exemple distinguer "Momentum 3" de "Momentum 2.0"), car c'est souvent ce numéro qui départage deux variantes.

- **Le départage par le prix représentatif.** Parmi plusieurs candidats à égalité de score, on retient celui dont le prix est le plus proche de la médiane. Cela évite de bâtir la fiche sur une donnée corrompue (par exemple un même "Momentum 3" listé par erreur à 9755 dollars).

- **La branche "override vendeur".** Quand le vendeur a ainsi nommé le produit, la fiche est bâtie sur la fiche catalogue de CE produit, et les attributs observés par le VLM sur le mauvais produit sont écartés. Sur un texte vide, cette logique est sans effet (aucune régression possible).

### Le vérificateur visuel (`src/vlm/validator.py`)

C'est l'étape où le VLM confirme que la photo du vendeur correspond bien au produit retrouvé.

- La fonction `validate_top1(user_photos, catalog_image_url, title, candidate_attributes)` compare les photos du vendeur à l'image officielle du meilleur candidat retrouvé dans le catalogue. Elle renvoie un verdict au format JSON strict : `match` (vrai ou faux), `confidence` (un score de confiance entre 0 et 1) et `reason` (une phrase courte expliquant le verdict).
- Le réglage **`MAX_USER_PHOTOS = 2`** limite la comparaison aux deux premières photos du vendeur, car la correspondance se joue surtout sur la vue principale. La réponse est limitée à 200 jetons et le délai d'attente à 60 secondes.
- Le prompt précise au modèle d'ignorer l'état, l'arrière-plan et les accessoires, et de ne juger que le modèle du produit. On lui injecte aussi les attributs attendus du candidat (marque, modèle, capacité, couleur, taille), à vérifier UNIQUEMENT s'ils sont clairement visibles sur les photos du vendeur : utile en électronique où des variantes d'un même modèle se ressemblent beaucoup.
- Cette vérification est un bonus, jamais un bloqueur. Si une condition manque (pas de photo, pas d'image catalogue, ou modèle indisponible), la fonction renvoie simplement `None` et l'identification du produit continue sans elle. Le verdict, quand il existe, sert à afficher un badge de confiance visuelle dans l'application ; c'est toujours l'humain qui valide, jamais une décision automatique.
- **Optimisation de latence.** Ce vérificateur est un troisième appel au modèle, exécuté en plus de l'extraction et de l'identification raisonnée. Pour ne pas allonger inutilement le temps de réponse, on le SAUTE quand l'identification raisonnée a déjà tranché avec confiance (famille sûre, pas de catalog-miss) : dans ce cas le jugement raisonné couvre déjà la correspondance, le badge visuel n'apporterait rien de plus.

### Le rédacteur ancré (`src/llm/01_prompt_templates.py` et `src/llm/02_rag_grounded_writer.py`)

C'est l'étape où le LLM écrit l'annonce finale à partir des faits.

- Le prompt suit une structure imposée : **rôle, puis instruction, puis contexte de faits, puis format de sortie JSON**. L'instruction contient des consignes explicites contre l'invention : "n'utilise que le contexte fourni", "pas d'invention de caractéristiques absentes du contexte". Elle impose aussi de reprendre exactement l'état déclaré par le vendeur (le champ `seller_condition`), pour éviter que le modèle ne transforme par exemple un "bon état" choisi par le vendeur en "très bon état" inventé.
- La fonction `extract_useful_sentences(reviews, top_n)` sélectionne les phrases qui serviront d'ancrage. Elle découpe les textes en phrases, garde celles d'au moins **50 caractères** (`MIN_SENTENCE_CHARS`), supprime les doublons, puis trie par longueur décroissante pour ne conserver que les **5 meilleures** (`TOP_N_GROUNDING_SENTENCES`). Ces phrases proviennent de textes réels et non d'une invention du modèle.
- Le code repose sur une abstraction `LLMWriter`, c'est-à-dire une interface commune avec deux implémentations interchangeables : `OpenRouterWriter` qui appelle le vrai modèle, et `MockLLMWriter` qui produit une fausse annonce de démonstration. Le projet bascule automatiquement de l'une à l'autre selon que la clé d'accès est présente ou non. C'est ce qui rend la démonstration robuste et le code facile à tester sans dépendre du réseau.
- Le résultat (`GeneratedListing`) conserve la liste exacte des phrases d'ancrage utilisées (`grounding_sentences_used`). On garde donc une trace de ce qui a servi à écrire l'annonce : c'est la traçabilité de l'ancrage.
- Le rédacteur, lui, reste sur le modèle texte Gemma 4 31B (via le client `src/llm/openrouter_client.py`). En l'absence de clé OpenRouter, c'est le `MockLLMWriter` qui prend le relais (dégradation propre).

### L'ancre prix de l'IA dans la cascade de prix (`src/pricing/01_algorithmique.py`)

Le jugement de l'IA ne sert pas qu'à identifier le produit : il fournit aussi une "ancre prix", c'est-à-dire une estimation du prix NEUF du produit, qui s'insère dans la cascade de prix déterministe. C'est important pour le grounding car cela évite de baser le prix sur des médianes polluées.

- **La cascade complète : L1 → L1.5 → L2 → L3 → L4.** Le niveau L1 (confiance haute) part du prix catalogue RÉEL du produit identifié, auquel on applique une décote selon l'état et une dépréciation selon l'âge. Le niveau **L1.5** (confiance haute-moyenne) part de l'ANCRE prix neuf estimée par l'IA lors de la passe raisonnée, à laquelle on applique exactement la MÊME décote déterministe. Point crucial pour l'honnêteté du discours : seule l'ANCRE est une estimation de l'IA ; la décote (état, âge) reste 100 % déterministe et transparente. La promesse "pas de pricing par boîte noire ML" reste donc vraie. Les niveaux L2 et L3 (médianes des voisins et de la catégorie) ont été RÉTROGRADÉS sous L1.5, parce que ce sont eux, pollués par des accessoires et des lots, qui donnaient par exemple environ 6 € pour une montre valant 150 €. Le niveau L4 est le dernier recours (saisie manuelle) : le front n'affiche plus "0,00 €" mais "Prix à fixer".

- **Trois garde-fous métier.** (a) Anti sous-évaluation : si une médiane de voisins tombe très en dessous du prix neuf attendu décoté, on la relève à un plancher (un quart de ce prix attendu, constante `UNDERPRICING_FLOOR_RATIO = 0.25`). (b) Cohérence L1 : si le prix catalogue du premier candidat est ridiculement bas par rapport à l'ancre IA (moins de 0,2 fois l'ancre, constante `L1_ANCHOR_MIN_RATIO = 0.2`), c'est que ce candidat est probablement un accessoire mal apparié (une coque à 43 $ pour un iPhone) : on ignore ce prix catalogue et on bascule sur L1.5, ce qui évite d'afficher "iPhone à 15 €". (c) Prix catalogue aberrant : si le prix catalogue dépasse 4 fois la médiane des voisins (avec au moins 3 voisins, constante `CATALOG_OUTLIER_FACTOR = 4.0`), c'est une donnée corrompue (un casque listé à 9755 $) et on l'ignore.

- **L'état "pour pièces / HS".** Un cinquième état a été ajouté (`pour_pieces`), avec un multiplicateur de **0,15** (valeur résiduelle). Les multiplicateurs complets sont : neuf 1,00 ; très bon état 0,75 ; bon état 0,55 ; correct 0,35 ; pour pièces 0,15. Les prix du catalogue sont en dollars, convertis en euros par un taux fixe (environ 0,92, surchargeable par la variable d'environnement `PRICE_USD_EUR_RATE`).

### La fiche exhaustive et sourcée (`src/serving/listing_fill.py` + `src/api/main.py`)

La fiche finale doit être la plus complète possible tout en restant honnête sur l'origine de chaque information.

- **Toutes les données structurées sont générées.** La fonction `assemble_listing` produit les facettes attendues par le schéma de la catégorie (`expected_facets`), PLUS les attributs riches hors schéma (format, caractéristiques, certification, tension, puissance, connectivité…, les valeurs trop longues étant tronquées), PLUS les caractéristiques jugées par l'IA. Pour ces dernières, la provenance pilote l'usage : une facette "observé" devient un fait observé sur la photo ; une facette dont la source est l'index d'une vraie fiche devient un fait catalogue (seulement si le jugement porte bien sur ce produit) ; une facette "analogie" est ESTIMÉE et n'est JAMAIS affirmée comme un fait. Le texte OCR brut (`visible_text`, souvent un titre ou un filigrane) est exclu de l'affichage.

- **Le "type de produit" suit le produit identifié.** Le type affiché est la catégorie du produit réordonné par l'IA, et non plus le vote de catégorie qui pouvait être pollué (une coque faisait afficher "Basic Cases" pour un iPhone).

- **La complétude est mesurée par catégorie FINE.** On ne garde du schéma de la macro-catégorie que les facettes réellement présentes chez au moins un candidat de la même catégorie fine. Ainsi une enceinte n'est plus pénalisée pour l'absence d'une "capacité" qui n'a pas de sens pour elle. L'état (choix du vendeur) est exclu du dénominateur de la complétude.

- **Cinq provenances possibles par champ**, affichées telles quelles : observé (photo), catalogue (match fiable), typique-à-vérifier (imputé des voisins, donc non affirmé), catégorie, vendeur. En cas de catalog-miss, les caractéristiques du mauvais candidat ne sont PAS traitées comme des faits. Une cascade de niveaux résume la situation : N1_catalog (match catalogue fiable), N2_category_photo (catégorie sûre mais pas de match fiable), N3_observed (catégorie incertaine).

### L'observabilité métier (`src/api/main.py`)

En plus des métriques HTTP exposées à Prometheus (latence, compteurs), on émet des journaux structurés (via structlog) inspectables requête par requête.

- À l'identification, l'événement `identify_done` consigne notamment : le statut, le nombre de candidats, le score du premier, la catégorie fine et sa confiance, la présence d'un jugement raisonné, le fait qu'on ait réordonné les candidats, le catalog-miss, l'ancre prix en dollars, la présence d'une question, la confiance famille, la complétude, et les temps d'extraction et de raisonnement.
- À la tarification, l'événement `price_done` consigne le niveau de cascade réellement utilisé, la méthode, le prix suggéré en euros, la présence d'une ancre IA, la catégorie et l'état.
- Le but est de pouvoir LIRE ce que fait le pipeline (taux de catalog-miss, fréquence d'usage de L1.5, où part la latence), sans rien de décoratif.

### Le durcissement de sécurité

Une revue adverse a conduit à plusieurs corrections de robustesse, visibles dans le code.

- Des bornes Pydantic sur les prix (strictement positifs, inférieurs à un million, ni infini ni NaN) et sur les longueurs de texte et de listes en entrée, pour éviter qu'une entrée démesurée ne gonfle le prompt envoyé au modèle (coût et déni de service).
- Le texte du vendeur est inséré dans le prompt d'identification raisonnée comme une DONNÉE explicitement non fiable et délimitée, jamais comme une instruction : c'est une protection contre l'injection de prompt (un vendeur malveillant qui essaierait de faire dévier le modèle).
- L'optimisation de latence décrite plus haut (sauter le validateur visuel quand le raisonné est déjà confiant) fait aussi partie de ce durcissement.

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

- **La qualité de fiche bout-en-bout, mesurée sur de vraies photos.** Un protocole
  reproductible (`scripts/mesure_qualite_fiche.py`, sortie dans
  `reports/09_fiche_quality/mesure_fiche.{json,md}`) fait passer le panel réel `data/photos_eval`
  (94 produits, les noms de dossiers servant de vérité-terrain) par l'API complète (upload →
  identification → prix), en photo seule (sans précisions du vendeur). On respecte ainsi la doctrine
  du projet : mesurer sur de VRAIES sorties, pas sur des anecdotes. Résultats mesurés sur les
  **93 produits** traités (1 dossier non mesuré) :
  - **Identification** : **90,3 %** des produits sont correctement identifiés (critère : au moins
    50 % des mots clés du nom de produit retrouvés dans la famille jugée par l'IA et le titre du
    premier candidat), avec un **rappel moyen de 78 %** des mots clés.
  - **Complétude de la fiche** : **0,84** de moyenne (médiane 0,83).
  - **Passe raisonnée** : présente sur **100 %** des produits. **Catalog-miss : 28 %**. Question
    discriminante posée : **11 %**. Répartition des niveaux de prix : **L1 pour 42 produits, L1.5
    pour 51 produits** (les médianes polluées L2/L3 ne sont jamais le recours final ici).
  - Les **9 produits non identifiés** sont TOUS expliqués : une perception du modèle exact erronée
    (une RTX 4080 Super lue comme une 3080, une Xbox Series S, un casque Sennheiser Momentum lu comme
    un Philips), un catalog-miss légitime (SSD, station d'accueil), ou un nom de dossier ambigu (un
    artefact de la mesure elle-même). C'est un chiffre défendable, pas une impression.

- **Le parcours vendeur, refondu côté interface.** Plusieurs changements rendent visible,
  pour le vendeur, l'honnêteté du système (code dans `frontend/src` : `App.tsx`, `condition.ts`,
  `components/MarketplaceListing.tsx`).
  - Le choix manuel du "type d'objet" a été SUPPRIMÉ : le type est désormais DÉRIVÉ de la catégorie
    identifiée (`kindFromCategory`), avec des motifs sur le mot entier et une exclusion des
    accessoires (un casque "Over-Ear Headphones", qui contient le mot "phone", et les chargeurs ne
    sont plus classés comme un téléphone). La checklist d'état spécifique (batterie/écran d'un
    téléphone, clavier d'un ordinateur portable, manettes d'une console…) s'affiche APRÈS
    l'identification, au bon moment.
  - L'état "Pour pièces / HS" a été ajouté, ainsi qu'un champ optionnel "Année d'achat" qui alimente
    la dépréciation (sans cette information, on suppose un âge de 2 ans, ce qui est signalé).
  - Auto-confirmation : si l'IA est sûre (statut "identified"), on enchaîne directement vers la
    fiche ; sinon on montre les candidats. Dans tous les cas, un bouton "Ce n'est pas le bon
    produit ? Voir les autres résultats" laisse la main au vendeur.
  - Drapeau "Modèle à confirmer" : le pourcentage de confiance affiché est la part du vote des
    voisins (k-NN) sur la catégorie fine, et il n'est montré que s'il est net (au moins 60 %). Un
    pourcentage bas reflète une FRAGMENTATION du vote (produit exact ambigu, par exemple un casque
    à 34 %), pas un doute sur la grande catégorie : dans ce cas on affiche un bandeau actionnable
    "Modèle à confirmer : précisez le modèle ou ajoutez une photo de l'étiquette / de la boîte",
    reprenant la question discriminante de l'IA si elle existe. Un bandeau séparé signale le
    catalog-miss ("Produit estimé, absent du catalogue"), et une étiquette honnête "Prix neuf estimé
    par IA" accompagne le niveau de prix L1.5.

> 📊 **Chiffres et faits pour la slide** : lecture des photos par Qwen 3.5 Flash (champion d'une
> comparaison de quatre modèles, retenu pour sa complétude et son coût), jusqu'à 4 vues en un seul
> appel, sortie JSON, raisonnement désactivé, déterminisme à température 0 avec graine fixe pour
> l'extraction et température 0,4 pour la rédaction ; identification raisonnée = le modèle
> JUGE le top-15 du moteur de recherche par similarité sans pouvoir inventer hors liste (grounded avant génératif) ; qualité
> de fiche mesurée sur 93 photos réelles : 90,3 % d'identification (rappel moyen 78 %), complétude
> 0,84, catalog-miss 28 %, niveaux de prix L1 = 42 / L1.5 = 51 ; la photo prouvée comme maillon
> décisif (gain de 0,145 de complétude par rapport au texte seul) ; description vendeur prouvée sans
> effet (test d'équivalence) ; preuve d'ancrage avec "Snapdragon 732G" venu des faits et non de la
> mémoire ; dégradation propre par mode de remplacement quand le service externe est absent.
> 📸 **Capture suggérée** : l'annonce générée affichée à côté de la fiche catalogue (les caractéristiques correspondent), le badge de correspondance visuelle, le bandeau "Produit estimé, absent du catalogue" (catalog-miss) et l'étiquette "Prix neuf estimé par IA" (niveau L1.5).

---

## 5. Analyse critique (état de l'art comparé à notre travail)

**Points solides :**

- ✅ RAG avec règles d'ancrage explicites et sortie JSON : ce sont exactement les bonnes pratiques recommandées.
- ✅ Rôles séparés (la récupération apporte la connaissance, le VLM JUGE à l'intérieur des candidats réels et vérifie, le LLM rédige), ce qui supprime la principale source d'invention. Le modèle ne peut JAMAIS introduire un produit hors des candidats fournis.
- ✅ Grounding implémenté et testé, pas seulement promis : un identifiant halluciné est ignoré, une caractéristique non sourcée est jetée, et le catalog-miss permet d'admettre honnêtement "ce produit n'est pas dans le catalogue" au lieu de mentir sur un sosie.
- ✅ Comportement non bloquant partout : extraction, identification raisonnée et vérificateur ne cassent jamais le parcours du vendeur (chacun retombe proprement sur la chaîne de secours).
- ✅ Dégradation propre (mode de remplacement) et abstraction du rédacteur, ce qui rend la démonstration robuste et le code testable.
- ✅ Optimisation des coûts et de la latence : 4 vues en un seul appel, un seul appel pour l'identification raisonnée (15 fiches en texte, pas 15 images), validateur sauté quand le raisonné est déjà confiant, température basse pour rester factuel.
- ✅ Qualité mesurée sur de vraies photos (90,3 % d'identification, complétude 0,84), pas sur des anecdotes.

**Limites assumées :**

- **Dépendance à un service externe.** Les modèles (Qwen pour la vision, Gemma pour la rédaction) passent par OpenRouter, ce qui implique un coût, une latence et une disponibilité non garantie. Le mode de remplacement atténue le problème pour la rédaction mais ne supprime pas la dépendance.
- **Perception du modèle exact limitée en photo seule.** Pour un produit sans marquage visible sur les photos envoyées (par exemple un Sennheiser Momentum 3 dont le logo est sur l'étui), le modèle de vision peut choisir un sosie avec aplomb. C'est la cause principale des erreurs mesurées. On le mitige par trois mécanismes : (a) le texte vendeur qui fait autorité (la métadonnée fixe le produit quand il est au catalogue), (b) le drapeau "Modèle à confirmer", (c) le bouton "Ce n'est pas le bon ?". À ne pas survendre : ces garde-fous réduisent le problème, ils ne le suppriment pas.
- **Le modèle rapide sous-déclenche le catalog-miss.** Qwen 3.5 Flash a tendance à coller à un sosie d'une autre génération (un iPhone 14 lu comme un 13, une RTX 4080 comme une 3080) plutôt que de déclarer le produit absent. Un modèle jugé plus puissant ferait probablement mieux : la variable d'environnement `PHOTO_VLM_IDENTIFY_MODEL` permet de le brancher, mais ce n'est pas activé par défaut.
- **Le garde-fou anti sous-évaluation est surtout défensif.** C'est en réalité le niveau L1.5 (l'ancre prix de l'IA) qui fait le vrai travail contre les prix absurdes ; le plancher anti sous-évaluation n'est qu'un filet de sécurité supplémentaire.
- **Ancrage sur la fiche, pas encore sur les avis acheteurs.** Aujourd'hui l'annonce est ancrée dans la description du produit. L'enrichir avec les avis acheteurs réels apporterait du naturel et des arguments de vente : c'est une amélioration prévue, qui demande de rapprocher les avis du produit au moment voulu.
- **Pas de citation phrase par phrase dans l'annonce.** Une bonne pratique avancée consisterait à indiquer dans l'annonce de quel passage source vient chaque affirmation. Ce n'est pas encore fait : c'est une piste d'amélioration.

---

## 6. Les modèles mobilisés (rappel)

Pour situer ces IA génératives dans l'ensemble du projet : la plupart des "modèles" du projet sont des modèles entraînés ou construits par nous, et seules les briques génératives sont externalisées via OpenRouter.

- **La recherche par similarité (k-NN / FAISS HNSW sur des embeddings texte Arctic Embed)** : c'est le moteur d'identification en direct, qui fournit le top-15 des candidats réels.
- **Le vote pondéré des voisins (k-NN) sur la catégorie fine** : c'est le classifieur champion du projet ; il fournit le signal de confiance qui pilote le drapeau "Modèle à confirmer".
- **Un modèle texte TF-IDF / SVM** en production dans le registre MLflow.
- **La cascade de prix déterministe** (sans ML opaque), décrite plus haut.
- **Le VLM Qwen 3.5 Flash** : extraction depuis la photo, identification raisonnée et vérification visuelle.
- **Le LLM rédacteur Gemma 4 31B** : la rédaction grounded (RAG) de l'annonce.

## 7. Références

- Prompting Guide, "Retrieval Augmented Generation (RAG) for LLMs" : https://www.promptingguide.ai/research/rag
- Lewis et al., "Retrieval-Augmented Generation" (article fondateur du RAG) : https://arxiv.org/abs/2005.11401
- arXiv 2407.12858, "Grounding and evaluation for LLMs" (synthèse) : https://arxiv.org/pdf/2407.12858
- arXiv 2501.03995, "RAG-Check : evaluating multimodal RAG" : https://arxiv.org/pdf/2501.03995
- Mesure interne de qualité de fiche (panel réel) : `scripts/mesure_qualite_fiche.py` → `reports/09_fiche_quality/mesure_fiche.{json,md}`

---

### En une phrase (pour la défense)

*« Nos IA génératives ne devinent jamais. La recherche apporte la connaissance (les 15 vrais produits candidats), puis un modèle qui lit les images (Qwen 3.5 Flash) JUGE lequel correspond, ou admet honnêtement qu'aucun n'est le bon (catalog-miss) ; il ne peut jamais inventer un produit hors de cette liste. Un modèle de langage (Gemma 4 31B) rédige ensuite l'annonce uniquement à partir de la vraie fiche, avec des règles d'ancrage explicites et une sortie JSON. On le prouve : un identifiant halluciné est ignoré, une caractéristique non sourcée est jetée, et "Snapdragon 732G" vient des faits, pas de la mémoire. Mesuré sur de vraies photos : 90,3 % d'identification, complétude de fiche 0,84. Et si le service externe tombe, tout continue grâce à un mode de remplacement local. »*

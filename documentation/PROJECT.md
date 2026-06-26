# Rakuten AI : document de cadrage

> Version 3.1 (2026-06-26). Auteur : Mathieu Klopp. Statut : actif.
>
> Ce document définit ce que le projet cherche à faire, pour qui, pourquoi, et
> ce qui est explicitement laissé de côté. Il se lit seul, sans connaissance
> technique préalable et sans avoir lu aucun autre fichier. Chaque terme
> technique est expliqué en une phrase à sa première apparition.
>
> Principe fondateur, dit "photo d'abord" : la photo est l'entrée obligatoire
> du parcours de vente (au moins une photo, qui sert aussi de preuve pour
> l'acheteur). À partir de cette photo, un modèle qui sait "lire" les images
> propose un titre probable et des attributs observés. Le périmètre couvre
> quatre catégories de produits, choix maintenu depuis le début du projet.

> Note de méthode : ce document sépare clairement deux types d'affirmations.
> Les chiffres sourcés proviennent du web, d'études publiques ou de mesures
> faites en interne. Les hypothèses à valider sont des paris explicites,
> mesurables, qui seront confirmés ou infirmés par des tests utilisateurs ou
> des comparaisons chiffrées. Aucune hypothèse n'est présentée comme un fait,
> et rien n'est inventé.

---

## 1. Contexte

Le marché français de la seconde main entre particuliers est en forte
croissance. Les sources convergentes du secteur l'estiment entre 7 et 14
milliards d'euros en 2024 (l'écart vient du périmètre retenu : textile seul ou
tous les biens, avec ou sans le reconditionné), pour une croissance annuelle de
l'ordre de +15 % au global et +8,5 % sur le textile [^1] [^2]. Près de 3
Français sur 4 ont acheté un produit d'occasion en 2024 [^3].

Ce marché de particulier à particulier (un vendeur privé vend directement à un
acheteur privé, sans professionnel intermédiaire) est dominé par deux acteurs.
Vinted (813,4 millions d'euros de chiffre d'affaires en 2024, 17,3 millions de
visiteurs par mois) règne sur la mode. Leboncoin (environ 520 millions d'euros
de chiffre d'affaires, 30 millions de visiteurs par mois, 800 000 nouvelles
annonces par jour) domine le généraliste [^4] [^5]. Rakuten France occupe un
créneau hybride qui mélange le neuf et l'occasion, avec 55,4 % de ventes en
occasion en 2025 sur certaines catégories, soit 5 points de plus qu'en 2023
[^6]. Un écosystème d'outils payants pour générer automatiquement des
descriptions d'annonces existe déjà (VintyLook, QuickListAI, Listed AI,
SharkScribe et d'autres) [^7]. Le besoin est donc validé par le marché, mais
ces outils visent surtout Vinted et aucun ne s'impose côté Rakuten.

L'utilisateur cible est le vendeur particulier occasionnel : pas un revendeur
professionnel, mais une personne qui veut écouler entre 1 et 50 objets
(déménagement, vide-grenier, tri de garde-robe, héritage). Cette population est
mal servie par les interfaces actuelles. Elle doit choisir manuellement dans
des classements de centaines de catégories, rédiger un titre optimisé pour le
référencement (le fait d'être bien retrouvé dans une recherche), écrire une
description, puis chercher le prix du marché. Autant d'étapes qui demandent une
expertise qu'un particulier n'a pas envie d'acquérir pour vendre cinq objets
par an.

## 2. Proposition de valeur

Pour les vendeurs particuliers occasionnels (cible : ceux qui mettent en ligne
moins de 50 articles par an), qui butent sur les étapes manuelles de
catégorisation, de rédaction et d'estimation du prix, notre solution est une
application web qui génère la fiche produit complète (catégorie, attributs,
titre, description, prix indicatif) à partir de quelques photos. Les interfaces
actuelles, au contraire, demandent au vendeur d'effectuer toutes ces tâches
lui-même.

Trois éléments distinguent notre approche des outils existants de type
VintyLook. D'abord, un parcours unique de bout en bout : de la photo à la fiche
complète, sans rupture. Ensuite, un mécanisme d'identification ancré dans un
catalogue de référence (une base de produits réels qui sert de source de
vérité), conçu pour ne pas inventer de détails faux. Enfin, un prix expliqué et
décomposé (on montre comment il est calculé) plutôt qu'une suggestion opaque
que l'utilisateur doit croire sur parole.

## 3. Hypothèses-clés

> Ces hypothèses ne sont pas encore validées. Elles sont mesurables et seront
> vérifiées par des tests utilisateurs ou des comparaisons chiffrées.

- **H1** : générer automatiquement la fiche depuis les photos devrait réduire
  fortement le temps de création d'une annonce. Mesure visée : un temps médian
  inférieur à 5 minutes sur un panel de 10 utilisateurs, comparé à leur propre
  habitude. Aucune source publique fiable ne donne le temps moyen actuel de
  création d'annonce : il sera mesuré en interne, avant et après usage de
  l'outil.
- **H2** : afficher une barre de complétude qui se remplit en temps réel (elle
  montre quelle part des informations utiles est déjà renseignée) et un score
  de confiance d'identification devrait améliorer la qualité moyenne des
  fiches. Mesure visée : un taux de complétude (nombre de champs remplis divisé
  par le nombre de champs possibles) supérieur à 75 %. Première mesure (Cycle
  36, voir section 4 bis) : 0,84 en moyenne sur le panel réel, au-dessus du seuil,
  à consolider et à compléter par un test utilisateur sur la qualité perçue.
- **H3** : un prix transparent et décomposé devrait être mieux accepté qu'un
  prix produit par un modèle opaque. Mesure visée : plus de 60 % des vendeurs
  valident le prix suggéré.
- **H4** : un parcours d'identification ancré (on retrouve d'abord le produit
  dans le catalogue, puis un modèle vérifie) devrait battre un modèle qui
  devine directement, à la fois en précision et en absence d'inventions.
  Mesure visée : retrouver le bon produit parmi les 5 premiers candidats dans
  plus de 80 % des cas, et moins de 5 % d'identifications faussement positives
  (un produit présenté à tort comme le bon, compté à la main).

## 4. Fonctionnalités prévues (dans le périmètre)

> La fonctionnalité F0 est le cœur du projet. Les fonctionnalités F1 à F7 sont
> les briques produit. La fonctionnalité F8 est optionnelle.

- **F0, cœur d'identification ancré, photo d'abord** : un parcours qui identifie
  un produit à partir d'une ou plusieurs photos (au moins une, obligatoire,
  preuve pour l'acheteur) en cherchant son plus proche voisin dans un catalogue
  indexé. Le catalogue couvre quatre catégories de produits (environ 4,5
  millions de fiches produit sur ce périmètre). Le déroulé est le suivant.
  1. Lecture de la photo par un modèle qui sait analyser les images, appelé
     ici "modèle de vision-langage" (un modèle qui prend une image et produit
     du texte la décrivant), via un service externe sur internet : la photo
     donne un titre catalogue probable et des attributs observés (marque,
     couleur, texte ou étiquette lisible). Un texte saisi par le vendeur reste
     un complément facultatif. Cette étape a été validée par un essai chiffré.
  2. Encodage de la requête texte par un modèle qui transforme une phrase en
     une liste de 1024 nombres capturant son sens (et non ses seuls mots). Ce
     modèle, nommé Arctic Embed, est utilisé tel quel, sans réentraînement.
     Cette requête sert ensuite à interroger un moteur de recherche rapide par
     similarité, appelé FAISS (une bibliothèque qui retrouve très vite les
     éléments les plus proches parmi des millions). On obtient les meilleurs
     candidats avec un score de confiance. Une recherche complémentaire à
     partir de l'image elle-même (avec un modèle de vision nommé SigLIP) reste
     conditionnée à une mesure réelle de l'écart entre les images d'un
     catalogue commercial et les photos prises par un particulier.
  3. En cas de doute (deux meilleurs candidats trop proches en score), un mode
     de questions, comme le jeu Akinator, pose la question qui sépare le mieux
     les candidats restants. Les attributs déjà lus sur la photo pré-remplissent
     certaines réponses, et le système peut guider la prise de vue ("montrez le
     dos", "montrez l'étiquette").
  4. Vérification visuelle finale : un modèle qui voit compare la photo du
     vendeur avec l'image du candidat retenu et confirme, ou non, qu'il s'agit
     bien du même produit. C'est le garde-fou contre l'invention, matérialisé
     par un badge de confiance.
  5. Filets de sécurité : si aucun candidat ne dépasse le seuil de confiance,
     le système bascule en mode dégradé ("produit non identifié, saisie
     assistée") plutôt que de proposer un mauvais résultat.
- **F1, classification automatique** : prédire la sous-catégorie du produit
  (par exemple "smartphones" à l'intérieur de "téléphonie"). Objectif chiffré :
  un score F1 pondéré supérieur ou égal à 0,90. Le F1 est une note de 0 à 1 qui
  combine la capacité à ne pas se tromper et à ne rien oublier ; "pondéré"
  signifie que chaque catégorie compte à proportion de sa taille. Plusieurs
  modèles sont comparés (recherche du plus proche voisin, machine à vecteurs de
  support, forêt aléatoire, réseau de neurones simple), avec une méthode de
  référence simple et une fusion qui combine texte et image selon la situation.
- **F2, extraction d'attributs** : remplir la marque, le modèle, la couleur, la
  matière et la version à partir de la fiche du produit identifié, complétée par
  des observations dirigées quand la fiche ne contient pas l'information
  (lecture d'une étiquette par reconnaissance de texte sur image, lecture d'un
  code-barres). Aucun attribut n'est inventé par le modèle.
- **F3, génération de texte ancrée** : produire un titre et une description en
  français adapté au vendeur particulier, en s'appuyant sur les avis clients
  réels écrits sur Amazon pour le produit identifié. La technique, appelée
  "génération augmentée par recherche", consiste à retrouver d'abord des
  phrases réelles écrites par des acheteurs, puis à les fournir au modèle
  rédacteur pour qu'il s'en inspire au lieu d'inventer. Objectif chiffré : un
  gain de qualité de texte d'au moins +5 % par rapport à une génération sans
  cet appui, mesuré par un score de ressemblance au texte attendu.
- **F4, prix transparent** : un prix indicatif calculé par une règle claire et
  reproductible (et non par un modèle opaque). Il combine le prix médian de
  voisins proches, une dépréciation par catégorie qui dépend de l'âge, une
  pénalité liée à l'état et un ajustement selon la quantité d'informations
  disponibles. Le résultat est accompagné d'un niveau de confiance et d'une
  fourchette expliquée. La règle est organisée en cascade de cinq niveaux, du
  plus fiable au moins fiable : prix catalogue du produit exact ; prix neuf de
  référence estimé par le modèle puis décoté (niveau L1.5 ajouté au Cycle 36, voir
  section 4 bis) ; médiane des voisins ; médiane de la catégorie ; saisie manuelle
  en dernier recours. Seule l'ancre de départ du niveau L1.5 est estimée : la
  décote reste entièrement déterministe, donc aucun modèle opaque n'est utilisé
  pour le prix (voir la section 6, hors-périmètre).
- **F5, interface progressive à plusieurs modes** : un mode express (environ 30
  secondes, photo seule plus une courte liste de cases à cocher sur l'état) ;
  un mode assisté (observations ciblées via le mode de questions, plus un
  guidage de prise de vue adapté au type de produit) ; un mode déménagement
  par lots, qui permet de photographier à la chaîne un grand nombre d'objets,
  avec une file d'attente sauvegardée dans le navigateur. Les photos du vendeur
  apparaissent dans l'annonce finale (avec zoom), et une visionneuse permet de
  comparer avec les images des candidats du catalogue.
- **F6, filets de sécurité hors catalogue** : détecter les produits absents du
  catalogue d'identification et basculer en mode dégradé ("produit non reconnu,
  saisie assistée") plutôt que d'inventer une fiche.
- **F7, cycle de vie automatisé du modèle** : réentraînement hebdomadaire des
  classifieurs comparés ; détection de dérive (un changement progressif des
  données entrantes qui dégrade le modèle), à la fois sur les représentations
  numériques et sur la répartition des catégories ; remplacement du modèle en
  service sans interruption de l'application.
- **F8 (optionnel), spécialisation du modèle de vision-langage** : à activer
  uniquement si une comparaison chiffrée démontre un gain net (au moins +0,05
  de score F1 moyenné par catégorie) face au modèle de vision-langage ancré non
  spécialisé. La technique envisagée, dite QLoRA, ajuste finement un modèle en
  ne modifiant qu'une petite fraction de ses réglages pour rester économe en
  mémoire. Cette option n'est pas déclenchée à ce jour, faute de bénéfice
  démontré.

## 4 bis. Statut d'avancement (Cycle 36, mesuré le 2026-06-26)

> Cette section donne l'état réel de l'implémentation à la date indiquée. Elle
> distingue ce qui est codé et mesuré de ce qui reste un pari. Le travail décrit
> ici vit pour l'instant sur une branche de travail
> (`feat/cycle34-listing-quality-bench`) et n'est pas encore fusionné dans la
> branche principale. Il a toutefois été exécuté en direct sur de vraies photos
> et mesuré sur le panel réel décrit plus bas.

**Ce qui change avec le Cycle 36, en une phrase.** Le parcours d'identification
ne se contente plus de classer des candidats par ressemblance : un modèle qui
voit et raisonne (le modèle de vision-langage) examine les quinze meilleurs
candidats réels proposés par le moteur de recherche et rend un jugement motivé.
Le moteur de recherche apporte la connaissance (quinze fiches réelles du
catalogue), le modèle apporte le jugement (lequel correspond, à quel prix neuf,
quelle question poser en cas de doute). C'est la mise en pratique concrète du
principe "ancrer avant de générer" de la section 7 : le modèle ne peut jamais
choisir un produit absent de ces quinze candidats.

- **Identification raisonnée (nouveau cœur du parcours).** Un seul appel au
  service externe envoie une ou deux photos du vendeur, plus les quinze fiches
  candidates résumées en texte (et non leurs images, pour économiser le coût),
  plus les attributs déjà lus sur la photo et le texte facultatif du vendeur. Le
  modèle renvoie la famille du produit, un niveau de confiance, le candidat
  choisi, un éventuel signalement "produit absent du catalogue", un prix neuf de
  référence estimé, une éventuelle question discriminante, et des attributs dont
  chacun cite sa source (vu sur la photo, tiré d'une fiche précise, ou estimé
  par analogie). Plusieurs garde-fous anti-invention encadrent cette sortie : un
  candidat choisi hors des quinze est ignoré (on retombe sur le premier candidat
  du moteur de recherche et on remet la confiance à zéro, car le modèle n'a pas
  endossé ce choix) ; une donnée dont la source est invalide est jetée ; et toute
  défaillance (pas de clé d'accès, service indisponible, réponse illisible)
  renvoie un résultat vide qui laisse le parcours fonctionner sur le seul
  classement du moteur de recherche, sans jamais planter ni produire de fiche
  vide.
- **Le bon produit porte la fiche.** Le candidat retenu (par le jugement du
  modèle ou par le texte du vendeur) remonte en tête de liste. Avant, le premier
  candidat du moteur de recherche pouvait être un accessoire (une coque
  d'iPhone présentée comme le produit lui-même) ; désormais la fiche, le prix et
  la vérification portent sur le bon objet.
- **Le texte du vendeur fait foi.** Si le vendeur nomme un produit présent dans
  les candidats (avec assez de mots distinctifs, en gardant les numéros de
  modèle pour séparer les variantes), ce candidat est retenu de façon
  déterministe, indépendamment du modèle rapide qui ignore parfois cette
  consigne. La métadonnée du vendeur "sauve" l'identification quand le produit
  exact est mal perçu sur la photo mais présent au catalogue.
- **Prix transparent, désormais à cinq niveaux.** La règle de prix de la section
  4 (F4) gagne un niveau intermédiaire L1.5 : quand le prix catalogue du produit
  exact n'est pas disponible, on part du prix neuf estimé par le modèle, puis on
  applique exactement la même décote déterministe (état, âge). Seule l'ancre de
  départ est estimée ; la décote reste entièrement transparente et reproductible,
  donc la promesse "pas de prix par modèle opaque" tient toujours. Ce niveau est
  placé avant les médianes de voisins, car celles-ci, polluées par des
  accessoires et des lots, donnaient des prix absurdes (de l'ordre de quelques
  euros pour une montre à cent cinquante euros). Des garde-fous écartent une
  médiane manifestement sous-évaluée, un premier candidat qui serait un
  accessoire mal apparié, et un prix catalogue aberrant (donnée corrompue). Un
  état "pour pièces / hors service" a été ajouté à la grille d'état.
- **Fiche plus complète et plus honnête.** La fiche structurée liste désormais
  toutes les données pertinentes (les attributs attendus pour la catégorie, plus
  des attributs riches hors schéma), chaque champ portant sa provenance parmi
  cinq possibles : observé sur la photo, tiré d'une fiche catalogue fiable,
  typique mais à vérifier, déduit de la catégorie, ou saisi par le vendeur. La
  complétude se mesure par catégorie fine, pour ne pas pénaliser une enceinte qui
  n'a pas de "capacité".
- **Parcours vendeur revu.** Le choix manuel du type d'objet a disparu : il est
  déduit de la catégorie identifiée. La liste de vérification de l'état
  spécifique au type de produit s'affiche après l'identification, au bon moment.
  Quand le modèle est sûr, la fiche s'affiche directement ; sinon les candidats
  sont proposés, avec toujours un bouton "ce n'est pas le bon produit ?". Le
  pourcentage de confiance n'est affiché que s'il est net (au moins 60 %) ;
  sinon un bandeau actionnable "modèle à confirmer" invite à préciser le modèle
  ou à photographier l'étiquette, et un bandeau distinct signale un produit
  estimé absent du catalogue.

**Mesure de qualité de fiche (protocole reproductible, pas d'anecdotes).** Un
script dédié fait passer un panel réel de 94 produits (les noms de dossiers
servent de vérité-terrain) par le parcours complet, à partir de la photo seule,
sans le texte facultatif du vendeur. Résultats mesurés à la date de cette
section :

- **Identification : 90,3 %** des produits sont correctement identifiés (au
  moins la moitié des mots-clés du nom retrouvés dans la famille proposée par le
  modèle et dans le titre du premier candidat), pour un rappel moyen de 78 %.
- **Complétude de la fiche : 0,84 en moyenne** (médiane 0,83), au-dessus du seuil
  visé de 0,75 de l'hypothèse H2.
- La passe raisonnée s'exécute dans 100 % des cas ; un produit est signalé absent
  du catalogue dans 28 % des cas ; une question discriminante est posée dans 11 %
  des cas ; le prix se répartit entre le niveau catalogue (42 produits) et le
  niveau ancre estimée par le modèle (51 produits).
- **Neuf produits ne sont pas identifiés, et tous sont expliqués** : limite de
  perception du modèle (une carte graphique RTX 4080 Super lue comme une 3080,
  une console Xbox Series S, un casque Sennheiser confondu avec un sosie), produit
  réellement absent du catalogue (un SSD, une station d'accueil), ou nom de
  dossier ambigu qui est un artefact de la mesure plus qu'une vraie erreur.

**Limites assumées, sans survente.** Sur photo seule, la perception du modèle
exact reste limitée pour les produits sans marquage visible sur les clichés
envoyés (par exemple un casque dont le logo est sur l'étui, pas sur l'objet
photographié) : le modèle peut alors choisir un sosie avec aplomb. Trois
mécanismes atténuent ce risque : le texte du vendeur qui fait foi quand le
produit est au catalogue, le bandeau "modèle à confirmer", et le bouton "ce
n'est pas le bon produit ?". Le modèle rapide utilisé par défaut sous-déclenche
le signalement "absent du catalogue" (il s'accroche à un sosie d'une autre
génération, par exemple un iPhone 14 lu comme un 13) ; un modèle jugé plus
puissant ferait mieux, mais cette option n'est pas activée par défaut. Enfin, le
garde-fou anti sous-évaluation reste surtout défensif : c'est le niveau de prix
L1.5 (l'ancre estimée par le modèle) qui fait l'essentiel du travail.

**Modèles et services mobilisés par le parcours (rappel).** Le moteur
d'identification en direct est le moteur de recherche par plus proche voisin
construit dans le projet (sur les représentations textuelles Arctic Embed,
quinze candidats remontés). Un vote pondéré de ce moteur sur la catégorie fine
sert de signal de confiance et alimente le bandeau "modèle à confirmer". Un
classifieur classique enregistré dans le registre dédié reste disponible. La
règle de prix est déterministe (aucun modèle opaque). Le modèle de vision-langage
externe assure l'extraction depuis la photo, la vérification visuelle, et la
nouvelle passe raisonnée ; un modèle rédacteur ancré produit la description.

## 5. Indicateurs de succès

Le tableau ci-dessous liste les seuils visés. La colonne "statut" indique si la
mesure est déjà disponible ou reste à faire. Les mesures du Cycle 36 (section 4
bis) portent sur un panel réel, en photo seule, et ne sont pas encore fusionnées
dans la branche principale ; elles sont donc reportées ici comme premières
mesures, à consolider.

| Dimension | Indicateur mesuré | Seuil visé | Statut |
|-----------|-------------------|------------|--------|
| Identification | Bon produit présent dans les 5 premiers candidats | au moins 0,80 | à mesurer |
| Identification | Bon produit en première position après vérification visuelle | au moins 0,70 | première mesure : 0,903 sur le panel Cycle 36 (photo seule, branche non fusionnée), à consolider |
| Identification | Taux d'identifications faussement positives | moins de 5 % | à mesurer |
| Classification | Score F1 pondéré sur le jeu de test | au moins 0,90 | à mesurer |
| Génération de texte | Gain de qualité face à une génération sans appui | au moins +5 % | à mesurer |
| Complétude de la fiche | Champs remplis sur champs possibles (hypothèse H2) | au moins 0,75 | première mesure : 0,84 sur le panel Cycle 36, à consolider |
| Prix | Quatre niveaux de confiance distincts | mécanisme en place | en place : cinq niveaux (L1, L1.5, L2, L3, L4) |
| Latence | Temps de réponse de l'identification (seuil dépassé dans 95 % des cas) | moins de 5 s | à mesurer |
| Démonstration | Installation sur une machine virtuelle Ubuntu vierge | démarrée en moins de 15 min | à valider |
| Tests | Tests automatisés | 100 % passent (hors tests lents ou nécessitant une carte graphique) | maintenu en continu |

## 6. Hors-périmètre (choix assumés)

- **Pas de prix par apprentissage automatique supervisé.** Sans historique réel
  de ventes (les transactions passées de Rakuten ou d'un équivalent), un modèle
  de prix entraîné ressemblerait à un résultat sérieux sans en être un. Il est
  remplacé par une règle déterministe et transparente : dépréciation par
  catégorie, prix médian de voisins proches, pénalité d'état.
- **Pas de spécialisation d'un modèle de texte seul** (par exemple un petit
  modèle de langue tournant en local). L'exploration a mesuré un gain marginal
  (de l'ordre de +0,06 sur le score de qualité de texte) pour plus de 8 heures
  d'entraînement, ce qui n'est pas rentable. Le rédacteur ancré (F3) utilise un
  modèle de pointe accessible par internet, sans entraînement spécifique, en
  s'appuyant sur la recherche d'avis réels.
- **Pas de réentraînement du modèle de vision.** Le modèle SigLIP est utilisé
  tel quel comme extracteur de caractéristiques (il transforme une image en
  nombres exploitables) ; le réentraîner sort du cadre d'un projet de trois
  mois.
- **Pas d'application mobile native.** Une interface web qui s'adapte à
  l'écran couvre le besoin de démonstration.
- **Pas d'intégration réelle aux services de Rakuten.** Projet d'école : une
  démonstration locale suffit, la mise en production est hors sujet.
- **Pas de traduction de l'interface.** Focus sur le français uniquement. Le
  modèle qui encode le texte reste toutefois multilingue, car les avis clients
  d'Amazon utilisés comme source sont majoritairement en anglais.
- **Pas d'authentification réelle des utilisateurs.** Un mécanisme minimal de
  connexion est mis en place pour la démonstration. La gestion fine des
  identités relève d'un autre projet.
- **Pas d'aspiration automatique des sites concurrents** (Rakuten, Vinted,
  Leboncoin). Le risque légal et l'instabilité technique l'excluent. Le projet
  s'appuie sur un jeu de données public, les avis Amazon de 2023, qui sert de
  catalogue de référence pour l'identification.
- **Pas de flux vidéo en direct dans la version nominale.** L'expérience visée
  est celle d'une photo nette : la capture se déclenche quand l'image est
  bien cadrée et bien éclairée, sans suivi vidéo en continu. Un travail
  ultérieur pourra explorer la vidéo en direct si le projet le justifie après
  la première version.
- **Pas de spécialisation du modèle de vision-langage dans la version
  nominale.** La fonctionnalité F8 est explicitement optionnelle et ne
  s'active que sur preuve d'un bénéfice mesurable.
- **Périmètre limité à quatre catégories** : électronique, téléphonie et
  accessoires, jeux vidéo, outils et bricolage (environ 4,5 millions de fiches
  produit et environ 96 millions d'avis clients). Onze autres catégories
  (vêtements, maison, livres, automobile, sport, films et télévision, jouets,
  CD et vinyles, produits pour bébé, instruments de musique, électroménager)
  restent téléchargées sur le disque mais hors du périmètre actif. La
  justification : un projet de démonstration plus solide quand il est ciblé, un
  traitement des images réalisable en quelques heures plutôt qu'en plusieurs
  jours, et une consommation mémoire du moteur de recherche confortable
  (environ 9 gigaoctets). Étendre le périmètre est simple : il suffit de
  modifier une seule liste de catégories dans le code, qui sert de source
  unique de vérité pour tout le projet.

## 7. Contraintes techniques structurantes

- **Matériel fixe** : une carte graphique RTX 4080 avec 16 gigaoctets de
  mémoire vidéo et 96 gigaoctets de mémoire vive. Le catalogue indexé tient en
  mémoire vive, ce qui rend la recherche quasi instantanée. Concrètement,
  environ 3,16 millions de produits sont indexés sur les quatre catégories,
  chacun représenté par 1024 nombres stockés en demi-précision (un format
  numérique compact qui divise par deux la place occupée). Le moteur de
  recherche utilisé, dit "HNSW" (une structure qui relie chaque produit à ses
  voisins pour naviguer très vite vers les plus proches), vise un temps de
  réponse de l'ordre de quelques millisecondes, à confirmer par la mesure.
- **Soutenance** : on suppose que le jury fournit une machine virtuelle vierge.
  Une seule commande (`make`) doit suffire pour démarrer toute l'installation,
  sans manipulation manuelle.
- **Latence perçue** : les résultats doivent s'afficher au fil de l'eau sur le
  parcours du vendeur (technique d'envoi progressif depuis le serveur), pour
  que l'utilisateur voie les éléments apparaître au lieu d'attendre devant un
  indicateur de chargement. Objectif : les premiers mots affichés en moins de 5
  secondes dans 95 % des cas.
- **Absence de données réelles de marché** : un prix par apprentissage
  automatique est donc impossible (voir la section 6).
- **Délai** : environ trois mois jusqu'à la soutenance, avec une discipline
  stricte sur ce qui reste hors du périmètre.
- **Reproductibilité** : les données sont versionnées avec un outil de suivi de
  fichiers volumineux (DVC), les modèles sont enregistrés dans un registre
  dédié (MLflow), et toutes les sources d'aléa sont figées par une graine fixe.
  Une graine est un nombre de départ qui rend les tirages "au hasard"
  identiques d'une exécution à l'autre. Le projet doit pouvoir tourner à
  l'identique sur deux machines différentes.
- **Anti-invention par conception** : la règle structurante du parcours
  d'identification est "ancrer avant de générer", c'est-à-dire retrouver le
  vrai produit avant de laisser un modèle rédiger quoi que ce soit.

## 8. Parties prenantes

| Rôle | Personne ou entité | Attente principale |
|------|--------------------|--------------------|
| Responsable des modèles d'apprentissage modernes | Mathieu Klopp | Un parcours d'apprentissage ancré et à l'état de l'art, plus une interface progressive démontrable |
| Responsable de l'industrialisation et de la classification de base | Jean-Baptiste Quéméneur | Une infrastructure de mise en service, de la surveillance technique, des tableaux de bord, et un classifieur classique exploité |
| Mentor externe | Sébastien (Liora) | Une architecture défendable : l'interface séparée du modèle, un point d'entrée unique, et un cycle d'amélioration en boucle fermée |
| Évaluation finale | Revue technique externe | Une couverture complète de l'industrialisation, une démonstration reproductible en ligne de commande, une architecture défendable |
| Utilisateur cible (imaginé) | Vendeur particulier occasionnel | Une création d'annonce en moins de 5 minutes, sans saisie manuelle inutile, avec un prix transparent et un sentiment de fiabilité (rien d'inventé) |

## 9. Livrables attendus

- **Dépôt de code** avec une branche principale à jour, démontrable par une
  seule commande sur une machine vierge, et autonome (aucune dépendance à un
  autre dépôt local).
- **Démonstration en direct** du parcours vendeur : mode express (une photo),
  mode déménagement par lots (plusieurs photos), mode assisté (avec les
  observations dirigées du mode de questions).
- **Trame orale et diapositives** pour une soutenance de 20 minutes.
- **Schéma d'architecture interactif** (page web) présentant les modèles
  entraînés en interne et les services externes utilisés par le parcours.
- **Modèles enregistrés** dans le registre dédié, avec une étiquette désignant
  la version mise en production.
- **Jeux de données versionnés** avec l'outil de suivi de fichiers volumineux.
- **Documentation interne complète.**
- **Tests automatisés** avec une couverture mesurée.

---

> Convention : ce document tient sur une page imprimable. Ajouter une section
> oblige à en retirer une autre. Toute révision majeure du cadrage donne lieu à
> une nouvelle version datée.

---

## Sources

[^1]: [Bigmedia BPI France, 5 chiffres à connaître sur le marché de la seconde main](https://bigmedia.bpifrance.fr/infographies/5-chiffres-a-connaitre-sur-le-marche-de-la-seconde-main)

[^2]: [Wavestone, Seconde main : un marché qui continue son expansion en 2024](https://www.wavestone.com/fr/insight/seconde-main-un-marche-qui-continue-son-expansion-en-2024/)

[^3]: [Républik Retail, un marché de la seconde main estimé à 14 milliards d'euros en 2023](https://www.republik-retail.fr/rse/seconde-main/pratiques/un-marche-de-la-seconde-main-estime-a-14-milliards-d-euros-en-2023.html)

[^4]: [Cekome, classement 2025 des sites e-commerce en France](https://www.cekome.com/articles/blog/tendances-digitales-insights/veille-technologique-restez-en-tete-du-digital/classement-2025-des-sites-e-commerce-en-france-amazon-temu-vinted-en-tete/)

[^5]: [Mystudies, comparaison des plateformes de seconde main entre particuliers](https://www.mystudies.com/fr-ad/blog/decryptage-economique/marche-seconde-main-particuliers-analyse-strategique-comparative-vinted-leboncoin-beebs-vestiaire-collective-13-01-2026.html)

[^6]: [Joseph Torregrossa, que vendre sur Rakuten en 2025](https://josephtorregrossa.com/blogs/rakuten/que-vendre-sur-rakuten-les-meilleurs-produits-a-proposer-en-2025)

[^7]: [VintyLook, AI Mannequin Vinted](https://vintylook.com/en) ; [QuickListAI](https://quicklistai.org/vinted-ai-listing-generator/) ; [Listed AI](https://listedai.app/en/) ; [SharkScribe](https://sharkscribeai.com/listed-ai-vinted). Ces outils commerciaux d'aide à la rédaction d'annonces valident la demande, mais visent majoritairement Vinted.

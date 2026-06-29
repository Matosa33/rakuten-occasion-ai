# 00. Vue d'ensemble du système

> Ce document est une lecture de cadrage. Il se lit seul, sans aucune connaissance
> technique préalable. Objectif : comprendre à quoi sert le système, pourquoi il est
> construit ainsi, comment il fonctionne, ce qu'il produit et quelles sont ses limites.

## 1. Le problème que l'on résout

Un particulier veut vendre un objet d'occasion (un smartphone, une console, un outil).
Rédiger une bonne annonce est long et fastidieux : il faut trouver la bonne catégorie,
écrire un titre clair, décrire l'objet honnêtement et fixer un prix juste. Beaucoup de
vendeurs abandonnent ou rédigent une annonce de mauvaise qualité.

Notre système prend en entrée une ou plusieurs photos de l'objet et produit l'annonce
complète à la place du vendeur. Pour ne rien inventer, il s'appuie sur un catalogue de
référence : une grande base de produits réels qui sert de source de vérité.

## 2. L'idée centrale : un système ancré (en anglais « grounded »)

> Principe directeur : on ne demande jamais à une intelligence artificielle de deviner
> quel est le produit. On le retrouve d'abord dans un catalogue de produits réels, puis
> une intelligence artificielle rédige l'annonce à partir de ces faits vérifiés.

Les modèles génératifs (les intelligences artificielles qui produisent du texte) ont un
défaut connu : ils « hallucinent », c'est-à-dire qu'ils inventent des détails plausibles
mais faux. C'est un comportement structurel, pas un bug que l'on pourrait corriger.

La parade consiste à retrouver d'abord le vrai produit dans le catalogue. On transforme
ainsi une tâche risquée (« inventer la fiche d'un produit ») en une tâche vérifiable
(« choisir le bon produit dans une courte liste de candidats »). Ce mot, ancré, revient
souvent dans ce document : il signifie simplement que l'intelligence artificielle
s'appuie sur des données réelles plutôt que sur sa seule mémoire.

## 3. Le pipeline, étape par étape

Voici le trajet complet d'une photo jusqu'à l'annonce finale. Chaque flèche indique une
transformation.

```
 [1] ENTRÉE du vendeur
 - PHOTO(S) ............ OBLIGATOIRE (preuve pour l'acheteur + point de départ)
 - précision texte ..... optionnel (exemple : "iPhone 13 128 Go")
 - état général ........ optionnel (neuf / très bon état / bon état / correct /
                          pour pièces ou HS)
 - année d'achat ....... optionnel (sert à la dépréciation par âge)
 - checklist par type .. optionnel (fonctionne ? boîte ? accessoires ? facture ?
                          plus des questions adaptées au type d'objet, affichées
                          après l'identification)
 |
 [2] Lecture des photos par un modèle qui "voit" les images
     produit un titre probable et des attributs (marque, couleur, capacité...)
     la précision texte du vendeur vient compléter ce titre pour la recherche
 |
 [3] Transformation de la requête en une liste de 1024 nombres (un "embedding")
     ces nombres capturent le sens de la description, pas seulement les mots
 |
 [4] Recherche dans le catalogue : on retrouve les 30 produits les plus proches
     parmi environ 3,16 millions de produits indexés
 |
 [5] Identification raisonnée : un modèle qui voit et qui raisonne reçoit les
     1-2 photos du vendeur ET les 15 meilleurs candidats (résumés en texte). Il
     JUGE lequel est le bon produit, estime un prix neuf de référence, et signale
     un éventuel produit absent du catalogue. La recherche dans le catalogue apporte
     la connaissance, le modèle apporte le jugement.
 |
 [5 bis] Texte vendeur autoritaire : si le vendeur a nommé un produit présent
     dans les candidats, ce candidat est retenu de façon déterministe (la
     métadonnée fait foi, indépendamment du modèle).
 |
 [6] Levée de doute (mode "Akinator") : si deux candidats se ressemblent trop,
     le système pose la question qui les sépare le mieux
     les attributs déjà lus sur la photo pré-remplissent certaines réponses
 |
 [7] Vérification visuelle (sautée si la passe raisonnée est déjà confiante) :
     un modèle qui voit compare la photo du vendeur avec l'image du produit
     retenu et confirme (ou non) la ressemblance
 |
 [8a] PRIX                          [8b] DESCRIPTION
      état -> décote sur le prix         un modèle qui écrit, ancré sur la vraie
      du produit réel ou estimé          fiche, plus la checklist d'état intégrée
 |                                   |
 [9] ANNONCE FINALE
     catégorie + photos + prix + caractéristiques exhaustives + description,
     avec un éventuel flag « modèle à confirmer » ou « produit estimé »
```

Un mot sur les **caractéristiques** de l'annonce finale (le bloc « informations clés »). Elles ne
sont pas un simple recopiage : chaque champ (marque, couleur, capacité, modèle, taille…) porte sa
**provenance**, c'est-à-dire d'où vient l'information. Cinq origines, par ordre de fiabilité :
**observé** (lu directement sur la photo du vendeur, le plus sûr pour cet objet précis),
**catalogue** (tiré de la fiche du produit retrouvé, fiable quand le produit est bien identifié),
**typique-à-vérifier** (valeur habituelle pour ce genre de produit, imputée des voisins, donc à
confirmer et jamais affirmée comme un fait), **catégorie** (déduit de la catégorie votée, comme le
type de produit) et **vendeur** (saisi ou choisi par le vendeur, comme l'état ou l'année d'achat).
La fiche ne se limite plus aux quelques facettes attendues du schéma : on génère aussi tous les
attributs riches disponibles (format, fonctionnalités, certification, tension, puissance,
connectivité…), les valeurs trop longues étant tronquées pour rester lisibles. On mesure aussi la
**complétude** de la fiche, c'est-à-dire la part des caractéristiques attendues pour cette catégorie
qui sont effectivement remplies. Cette complétude est calculée **par catégorie fine** : on ne retient
du schéma général que les facettes réellement pertinentes pour cette catégorie précise (présentes
chez au moins un produit voisin de même catégorie fine), si bien qu'une enceinte n'est plus pénalisée
pour l'absence de « capacité » qui n'a aucun sens pour elle. L'état, qui est un choix du vendeur
toujours disponible, est exclu du calcul pour ne pas fausser le score. Ce rangement à champs sourcés
est ce qui rend les fiches exploitables par un moteur de recherche acheteur (filtrer par couleur, par
capacité…), au lieu d'une simple grande catégorie.

> À retenir : la photo est la seule entrée obligatoire. C'est à la fois la preuve pour
> l'acheteur et le point de départ du traitement. Toutes les autres informations sont
> facultatives mais améliorent le résultat : la précision texte affine la recherche,
> l'état ajuste le prix et le titre, la checklist enrichit la description. Le système
> fonctionne avec une photo seule et devient meilleur avec ces compléments.

### Ce que fait réellement le code

Le service d'identification fonctionne ainsi, dans cet ordre précis :

1. La requête texte du vendeur (quand elle existe) est d'abord traduite du français vers
   l'anglais. Le catalogue est en anglais (issu d'Amazon États-Unis) et une mesure interne
   a montré qu'une requête en français obtient un score de similarité environ 0,08 plus bas
   qu'en anglais. La traduction est optionnelle : si elle échoue ou si la clé d'accès au
   service externe manque, on continue avec la requête brute, sans bloquer.
2. La requête est encodée en un vecteur de 1024 nombres par un modèle de texte appelé
   Arctic Embed (nom complet : Snowflake snowflake-arctic-embed-l-v2.0). Le système vérifie
   à chaud que ce vecteur fait bien 1024 dimensions, sinon il s'arrête, ce qui évite des
   résultats silencieusement faux.
3. Ce vecteur est comparé à l'index du catalogue, qui renvoie les 30 produits les plus
   proches, triés par ressemblance. L'index utilise une structure de recherche rapide
   réglée pour explorer 64 voisins candidats à chaque recherche, un compromis entre vitesse
   et précision.
4. Le système classe le résultat en trois niveaux de confiance, selon le score de
   ressemblance du meilleur candidat (un nombre entre 0 et 1). Au-dessus de 0,60, le produit
   est considéré comme identifié. Entre 0,45 et 0,60, il est « à confirmer » par le vendeur.
   En dessous de 0,45, la correspondance est jugée incertaine et l'on propose une saisie
   manuelle. Dans tous les cas, la liste des candidats est toujours montrée : c'est l'humain
   qui valide, jamais la machine seule.
5. Si les deux meilleurs candidats sont trop proches (écart de score inférieur à 0,05), le
   système déclenche une question de levée de doute pour départager ces variantes.

Ces seuils méritent une explication. Un premier seuil de 0,600 avait été calibré en
comparant des fiches complètes entre elles. Mais en usage réel, la requête d'un vendeur est
courte (« iPhone 13 noir »), donc son score de ressemblance est mécaniquement plus bas.
C'est pourquoi on a retenu trois niveaux au lieu d'un seul couperet et que l'on affiche
toujours les candidats à l'humain.

### L'identification raisonnée : la recherche sait, le modèle juge

À partir des 30 candidats retrouvés, le système ajoute une étape de jugement. Le principe est
résumé en une phrase : **la recherche dans le catalogue apporte la connaissance, le modèle apporte le jugement.**
La recherche dans le catalogue est très douée pour rapprocher des produits qui se ressemblent,
mais elle peut placer en tête un accessoire plutôt que l'objet lui-même (par exemple une coque
d'iPhone classée avant l'iPhone). On confie donc aux 15 meilleurs candidats un seul appel à un
modèle qui voit et qui raisonne : il reçoit les 1 à 2 photos du vendeur plus les 15 fiches
candidates **résumées en texte** (pas les 15 images du catalogue, ce qui économise beaucoup de
ressources), ainsi que les attributs déjà lus sur la photo et le texte du vendeur. Il produit en
retour la **famille du produit**, le **candidat qu'il choisit**, un **prix neuf de référence
estimé**, des **facettes sourcées** (chacune cite sa provenance) et, au besoin, une **question
discriminante** à poser au vendeur.

Cette étape est entourée de garde-fous stricts, dans l'esprit ancré du projet :

- Le modèle **ne peut jamais introduire un produit absent des 15 candidats**. S'il désigne un
  produit hors de cette liste sans déclarer de cas hors catalogue, on retombe sur le premier
  candidat de la recherche, et l'on remet sa confiance à zéro (le modèle n'a pas endossé ce
  candidat, donc l'aval ne le traite pas comme un fait certain).
- Une facette dont la provenance est invalide est **jetée** : on n'affiche jamais une valeur non
  sourcée.
- Le candidat choisi est **remonté en tête** des candidats, de sorte que la fiche, le prix et la
  vérification visuelle portent sur le **bon** produit, et non sur le premier résultat de la
  recherche qui pouvait être un accessoire.
- Toute cette étape est **best-effort et non bloquante** : pas de clé d'accès, modèle indisponible,
  réponse illisible ou erreur quelconque, et l'on retourne simplement « rien », le pipeline gardant
  alors le classement de la recherche et la cascade de prix habituelle. Le système ne plante jamais
  et ne produit jamais une fiche vide.

### Le texte du vendeur fait foi

Quand le vendeur précise lui-même le nom du produit (champ « précisions »), cette métadonnée est
traitée comme **autoritaire**. Si le texte nomme un produit présent dans les candidats (au moins
deux mots vraiment discriminants, couvrant au moins la moitié des mots du texte, en gardant les
numéros de modèle même à un seul chiffre pour distinguer un « Momentum 3 » d'un « 2.0 »), ce
candidat est retenu de façon **déterministe**, indépendamment du modèle rapide qui ignore parfois
cette consigne. En cas d'égalité entre plusieurs candidats, on prend celui dont le prix est le plus
**représentatif** (le plus proche de la médiane), pour éviter de bâtir la fiche sur une donnée
corrompue (par exemple un même « Momentum 3 » listé par erreur à 9 755 dollars). Sur un texte vide,
cette branche ne fait rien du tout : aucun risque de régression.

### Une vérification visuelle économe

La vérification visuelle (comparer la photo du vendeur à l'image du produit retenu) reste
disponible, mais on **saute** ce troisième appel à un modèle quand la passe raisonnée a déjà tranché
avec confiance : le jugement de correspondance est alors déjà couvert, et l'on gagne en latence sans
rien perdre en fiabilité.

## 4. Les deux moitiés du projet

Le projet a deux faces complémentaires.

**A. Données et intelligence artificielle : construire l'intelligence**
- Ingénierie des données : récupérer, nettoyer et valider les données, en évitant la fuite
  de données (le fait qu'une information du jeu de test se retrouve par erreur dans le jeu
  d'entraînement, ce qui fausserait les scores à la hausse).
- Modèles : entraîner et comparer plusieurs modèles classiques, puis mesurer le meilleur.
- Recherche (en anglais « retrieval ») : l'index qui retrouve très vite le bon produit dans
  le catalogue.
- Modèles génératifs : un modèle qui voit les images et un modèle qui rédige du texte,
  utilisés tous deux de façon ancrée sur des faits réels.

**B. Mise en production durable (en anglais « MLOps ») : exploiter l'intelligence dans le temps**
- Suivi d'entraînement : chaque entraînement est enregistré dans un carnet de bord
  automatique (réglages utilisés, scores obtenus).
- Registre de modèles : une étagère qui range les modèles et marque clairement lequel est
  « en production ». On ne remplace le modèle en place que si un candidat fait mieux.
- Orchestration : le ré-entraînement peut être relancé automatiquement.
- Détection de dérive : on surveille si les données récentes ressemblent encore à celles
  d'entraînement, car un modèle vieillit quand le monde change.
- Observabilité : des tableaux de bord montrent la santé du système (latence, nombre de
  requêtes, erreurs). Le serveur expose ces mesures et trace chaque requête avec un
  identifiant unique.
- Infrastructure et automatisation : empaqueter le système, le déployer et le tester
  automatiquement à chaque modification du code.

> En une phrase : la partie A construit le modèle, la partie B garantit qu'il reste fiable,
> traçable et reproductible dans le temps.

## 5. Le prix : comment il est calculé

Le prix n'est pas produit par un modèle opaque mais par une suite de règles transparentes,
pour que le vendeur comprenne pourquoi tel prix lui est proposé. Le système descend une
cascade de cinq niveaux et s'arrête au premier qui s'applique :

- Niveau 1 (confiance haute) : le produit identifié a un prix dans sa fiche catalogue. On
  part de ce prix réel, on applique la décote liée à l'état, puis la dépréciation liée à
  l'âge.
- Niveau 1.5 (confiance haute-moyenne) : pas de prix de fiche utilisable, mais la passe
  d'identification raisonnée a fourni un **prix neuf de référence estimé par l'IA**. On part de
  cette ancre estimée, puis on applique exactement les **mêmes décotes déterministes** que pour le
  niveau 1. C'est un point important : seule l'**ancre** est une estimation de l'IA ; la décote
  reste 100 % déterministe et transparente, si bien que la promesse « pas de prix produit par un
  modèle opaque » reste vraie. Ce niveau est placé **avant** les médianes de voisins parce que
  celles-ci sont souvent polluées par des accessoires, des coques ou des lots : ce sont elles qui
  donnaient par exemple environ 6 euros pour une montre qui en vaut 150.
- Niveau 2 (confiance moyenne) : pas de prix de fiche ni d'ancre, mais on connaît le prix des dix
  produits voisins les plus ressemblants. On prend leur prix médian, puis les mêmes décotes.
- Niveau 3 (confiance basse) : on ne connaît que la catégorie. On part du prix médian de
  cette catégorie, puis la décote d'état.
- Niveau 4 (confiance très basse) : produit ou catégorie inconnus. Le système ne propose plus
  « 0,00 euro » mais affiche « prix à fixer », un mode dégradé invitant le vendeur à une saisie
  manuelle.

La décote selon l'état est un multiplicateur appliqué sur le prix de référence : neuf 1,00 ;
très bon état 0,75 ; bon état 0,55 ; correct avec défauts 0,35 ; et un état **pour pièces / hors
service** à 0,15 (valeur résiduelle), ajouté car c'est un cas courant en occasion. La dépréciation
par âge dépend de la catégorie, car les objets ne perdent pas leur valeur au même rythme : environ
moins 15 % par an pour l'électronique, moins 20 % par an pour les téléphones et accessoires
(marché très volatil), moins 10 % par an pour les jeux vidéo (la collection peut ralentir la
perte), moins 5 % par an pour l'outillage et le bricolage (qui vieillit lentement). Si le vendeur
ne renseigne pas l'année d'achat (champ optionnel), un âge de deux ans est supposé par défaut et
signalé comme tel. Les prix du catalogue sont en dollars (source Amazon États-Unis) tandis que
l'annonce s'affiche en euros : la conversion se fait par un **taux fixe documenté** (environ 0,92,
moyenne 2024-2026, ajustable sans redéploiement), appliqué après les décotes. Un taux en temps réel
serait de la sur-ingénierie pour un prix volontairement indicatif et arrondi.

Trois garde-fous protègent ce calcul contre les données corrompues du catalogue :

- **Anti sous-évaluation** : si une médiane de voisins (niveaux 2 ou 3), polluée par des
  accessoires, s'effondre très en dessous du prix neuf attendu décoté au même état et au même âge,
  on relève la suggestion à un plancher (un quart de ce prix attendu) et on l'explique au vendeur.
- **Cohérence du niveau 1** : si le prix catalogue du premier candidat est anormalement bas par
  rapport à l'ancre estimée par l'IA (moins d'un cinquième), c'est probablement un accessoire mal
  apparié (une coque à 43 dollars pour un iPhone à près de 600) ; on ignore alors ce prix catalogue
  pollué et on bascule sur le niveau 1.5. Ce seuil est volontairement bas car un prix catalogue est
  un fait (un reconditionné ou une promotion peuvent légitimement être bas) : on ne l'écarte que
  s'il est aberrant.
- **Prix catalogue aberrant** : un prix catalogue très au-dessus de la médiane des voisins (plus de
  quatre fois, avec au moins trois voisins) est une donnée corrompue, par exemple 9 755 dollars
  pour un casque à cause d'une faute de saisie ; on l'ignore au profit des voisins.

## 6. La description : rédaction ancrée

La description finale est rédigée par un modèle de texte, mais pas à partir de sa seule
mémoire. Le système récupère la description réelle du produit dans le catalogue, en extrait
les phrases utiles, et fournit ces phrases au modèle comme matière première. On évite ainsi
les inventions. Si la clé d'accès au service de génération externe est présente, la rédaction
est faite par ce service ; sinon, un générateur de secours produit une sortie de
démonstration, ce qui permet au système de fonctionner même sans connexion externe.

Un détail compte : les codes techniques internes de l'état (par exemple le libellé
informatique « bon_etat ») sont traduits en libellés lisibles (« Bon état ») avant d'être
envoyés au modèle, faute de quoi ce dernier risquait de recopier le code brut dans le titre
de l'annonce.

## 7. Comment on retrouve la bonne catégorie

Pour choisir la catégorie fine du produit (par exemple « cartes graphiques » plutôt que le
vague « électronique »), le système ne se fie pas à la seule catégorie du tout premier
candidat. Il fait voter les candidats retrouvés, chaque vote étant pondéré par la
ressemblance du candidat avec la requête. La catégorie qui rassemble le plus de poids
l'emporte, et la confiance correspond à sa part du vote total. Cette méthode de vote pondéré
a été mesurée comme meilleure que la catégorie du seul premier candidat : un gain de 2,4
points de justesse sur 15 000 requêtes de test.

Le « type de produit » affiché en haut de la fiche est désormais celui du **produit
effectivement identifié** (le candidat remonté en tête par la passe raisonnée), et non plus le
seul résultat du vote pondéré, qui pouvait être pollué : auparavant, une coque pouvait faire
afficher « étuis basiques » pour un iPhone. Quand l'identification raisonnée a tranché, on lui fait
confiance pour le type de produit ; sinon on retombe sur le vote.

## 8. Le parcours du vendeur et le drapeau de confiance

L'interface du vendeur a été repensée pour demander les bonnes informations au bon moment.

- **Plus de choix manuel du type d'objet.** Le type (téléphone, ordinateur, console, outil,
  appareil photo…) est désormais **déduit de la catégorie identifiée**. La déduction se fait sur des
  mots entiers et exclut explicitement les accessoires, afin qu'un casque (« over-ear headphones »,
  qui contient le mot « phone ») ou un chargeur ne soient plus classés à tort comme « téléphone ».
- **La checklist d'état spécifique apparaît après l'identification**, au bon moment : questions sur
  la batterie et l'écran pour un téléphone, le clavier pour un ordinateur, les manettes pour une
  console, etc. Une checklist universelle (fonctionne ? boîte ? accessoires ? facture ?) s'applique
  à tout objet.
- **Auto-confirmation.** Si l'IA est sûre de son identification, on enchaîne directement vers la
  fiche finale, sans étape de choix superflue. Sinon, on présente la liste des candidats. Dans tous
  les cas, un bouton « Ce n'est pas le bon produit ? Voir les autres résultats » reste disponible
  sur la fiche : l'humain garde toujours la main.

Un point mérite une explication, car il évite un piège classique. Le pourcentage de confiance
affiché correspond à la **part du vote des voisins sur la catégorie fine**. Il n'est montré que
**lorsqu'il est net** (au moins 60 %). Un pourcentage bas ne veut pas forcément dire que le système
s'est trompé de catégorie : il reflète souvent une **fragmentation du vote** (par exemple un casque
dont les voisins sont des marques et modèles variés, ce qui peut donner 34 %). Afficher « 34 % de
confiance » serait trompeur. Dans ce cas, on affiche plutôt un bandeau actionnable **« modèle à
confirmer »**, qui invite le vendeur à préciser le modèle ou à ajouter une photo de l'étiquette ou
de la boîte, et qui reprend la question discriminante de l'IA si elle en a posé une. Un autre
bandeau, **« produit estimé, absent du catalogue »**, prévient honnêtement quand le produit n'a pas
été trouvé au catalogue. Enfin, l'étiquette **« prix neuf estimé par IA »** signale clairement les
prix issus du niveau 1.5, pour ne jamais faire passer une estimation pour un fait.

## 9. Observabilité métier : lire ce que fait le pipeline

Au-delà des mesures techniques classiques (latence, nombre de requêtes, erreurs) exposées au format
Prometheus, le serveur écrit pour chaque requête des **journaux structurés inspectables**. À
l'identification, on enregistre par exemple le statut, le nombre de candidats, le score du meilleur
candidat, la catégorie fine et sa confiance, le fait que la passe raisonnée a eu lieu et a réordonné
les candidats, le cas hors catalogue, l'ancre de prix estimée, la question posée, la complétude de
la fiche et le temps passé dans chaque appel au modèle. Au prix, on enregistre le niveau de cascade
réellement utilisé, la méthode, le prix suggéré et la présence d'une ancre IA. L'objectif est de
**lire** ce que fait le pipeline (taux de cas hors catalogue, recours au niveau 1.5, où part la
latence) plutôt que d'accumuler des indicateurs décoratifs.

## 10. Résultats mesurés sur un panel réel

Pour remplacer les anecdotes par un chiffre défendable, un protocole reproductible fait passer un
panel réel de **94 produits** (les noms de dossiers servant de vérité-terrain) par l'API, **photo
seule, sans précisions texte**, et mesure la qualité de bout en bout. Sur ce panel :

- **Identification : 90,3 %** des produits sont correctement identifiés (au moins la moitié des mots
  clés du nom retrouvés dans la famille proposée par l'IA et le titre du meilleur candidat), avec un
  rappel moyen de 78 %.
- **Complétude de la fiche : 0,84 en moyenne** (0,83 en médiane).
- La passe raisonnée a fonctionné dans **100 %** des cas ; le cas hors catalogue a été déclaré dans
  **28 %** des cas ; une question discriminante a été posée dans **11 %** des cas.
- Côté prix, la cascade s'est arrêtée au niveau 1 pour 42 produits et au niveau 1.5 pour 51 produits
  sur ce panel.
- **9 produits n'ont pas été identifiés, et tous les échecs sont expliqués** : limite de perception
  du modèle sur des modèles très proches (une RTX 4080 Super perçue comme une 3080, une Xbox Series
  S, un casque Sennheiser Momentum confondu avec un Philips), cas hors catalogue (un SSD, une station
  d'accueil) ou nom de dossier ambigu (un simple artefact de la mesure).

## 11. Limites honnêtes

Ces limites sont assumées et documentées telles quelles, sans les survendre.

- **La photo seule a ses limites.** La perception du **modèle exact** est difficile pour des
  produits sans marquage visible sur les photos envoyées (par exemple un Sennheiser Momentum 3 dont
  le logo se trouve sur l'étui). Le modèle peut alors choisir un sosie avec aplomb. Trois garde-fous
  atténuent ce risque : le texte vendeur autoritaire (la métadonnée fixe le produit), le drapeau
  « modèle à confirmer », et le bouton « ce n'est pas le bon ? ». Quand le produit est bien présent
  au catalogue, la métadonnée du vendeur le « sauve ».
- **Le modèle rapide sous-déclenche le cas hors catalogue** : il colle parfois à un sosie d'une
  autre génération (un iPhone 14 perçu comme un 13, une 4080 comme une 3080). Un modèle jugé plus
  fort ferait mieux ; c'est une option, non activée par défaut.
- **Le garde-fou anti sous-évaluation est surtout défensif** : c'est le niveau 1.5 (l'ancre estimée
  par l'IA) qui fait le vrai travail pour éviter les prix absurdes.

## 12. Vocabulaire minimum

| Terme | Définition simple |
|---|---|
| Embedding (vecteur) | liste de nombres qui résume le sens d'un texte ou d'une image |
| Index de recherche vectorielle | structure qui retrouve très vite les vecteurs les plus ressemblants parmi des millions |
| Retrieval (recherche) | aller chercher le bon produit dans le catalogue |
| Grounded (ancré) | l'intelligence artificielle s'appuie sur des faits réels, elle n'invente pas |
| Modèle qui voit (VLM) | intelligence artificielle qui comprend le contenu des images |
| Modèle qui écrit (LLM) | intelligence artificielle qui comprend et rédige du texte |
| Suivi d'entraînement | carnet de bord qui enregistre chaque entraînement (réglages et scores) |
| Registre de modèles | étagère des modèles, avec l'étiquette « en production » |
| Modèle en place et candidat | le modèle actuel face à un prétendant ; on ne remplace que si le candidat fait mieux |
| Dérive (drift) | les données récentes ne ressemblent plus à celles d'entraînement |
| Score F1 | note de 0 à 1 de la qualité d'un classement (1 = parfait) |
| Erreur moyenne en pourcentage (MAPE) | écart moyen, exprimé en pour-cent, entre le prix prédit et le vrai prix |
| Cas hors catalogue | produit absent du catalogue ; on le signale plutôt que d'inventer |
| Identification raisonnée | étape où un modèle juge les meilleurs candidats de la recherche pour choisir le bon produit, sans pouvoir en inventer un |
| Ancre de prix (prix neuf de référence) | prix neuf estimé par l'IA, utilisé comme point de départ du prix quand la fiche catalogue manque (niveau 1.5) |
| Complétude de fiche | part des caractéristiques attendues pour la catégorie qui sont effectivement remplies |

## 13. Périmètre et choix assumés

- Les modèles entraînés en interne sont des modèles d'apprentissage automatique classiques
  (méthode des plus proches voisins, machines à vecteurs de support, petit réseau de
  neurones, pondération de mots TF-IDF). L'encodeur de texte (Arctic Embed) est pré-entraîné
  et figé : on l'utilise tel quel sans le ré-entraîner. Le modèle qui voit les images et le
  modèle qui rédige sont externes, appelés via une interface de programmation distante. Ce
  choix est justifié : pour identifier un produit dans un catalogue, la recherche ancrée bat
  un modèle qui devine, et elle coûte moins cher à maintenir.
- La valeur d'ingénierie tient dans la chaîne complète : des données propres, des modèles
  comparés et mesurés, mis en production, surveillés, et ré-entraînables.
- Les modèles construits dans le projet sont bien ceux qui font tourner le pipeline en
  conditions réelles : la recherche par plus proches voisins sur l'index vectoriel est le moteur
  d'identification (les 15 meilleurs candidats), le vote pondéré des voisins sur la catégorie fine
  est le classifieur champion qui alimente le signal de confiance et le drapeau « modèle à
  confirmer », un classifieur TF-IDF/SVM est enregistré « en production » dans le registre, et la
  cascade de prix est déterministe (aucun modèle de prix opaque). Le modèle qui voit et le modèle
  qui rédige, externes, n'interviennent que pour observer, juger et rédiger, jamais pour décider
  seuls du produit.
- Données : faute d'un jeu de données public Rakuten, on utilise le jeu « Amazon Reviews
  2023 » comme substitut. Le biais introduit est documenté et l'architecture reste
  transposable à de vraies données Rakuten.

## 14. Phrase de défense

Notre système ne devine pas un produit, il le retrouve dans un catalogue réel puis rédige
l'annonce à partir de ces faits vérifiés. La photo suffit à démarrer, l'humain valide
toujours le résultat, le prix s'explique en clair, et toute la chaîne, des données propres
jusqu'à la surveillance en production, est mesurée et reproductible.

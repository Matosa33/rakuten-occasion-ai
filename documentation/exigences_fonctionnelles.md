# Les fonctions du produit : ce qui a été promis, ce qui est livré

## À quoi sert ce document

Le projet est une application web qui aide un vendeur particulier à créer une annonce de
revente à partir de quelques photos. Le but est simple : la personne prend une ou plusieurs
photos d'un objet d'occasion, et l'application produit toute seule la fiche de vente complète,
c'est-à-dire la catégorie de l'objet, ses caractéristiques, un titre, une description et un
prix indicatif. On vise les vendeurs occasionnels (quelqu'un qui veut écouler entre un et
cinquante objets après un déménagement ou un vide-grenier), pas les revendeurs professionnels.

Au démarrage du projet, on a écrit une liste des neuf fonctions attendues. Ce sont les
promesses faites au début. Ce document fait le bilan honnête : pour chacune de ces neuf
fonctions, il dit ce qui a été réellement construit, comment cela marche, et ce qui reste
à faire. Il répond à la question « est-ce qu'on construit le bon produit ? ». Il se lit seul :
aucune connaissance technique préalable n'est nécessaire, et chaque terme technique est
expliqué en une phrase à sa première apparition.

Quelques mots de vocabulaire qui reviennent souvent :

- Le **catalogue** est notre base de référence de produits connus. Faute d'accès aux vraies
  données de vente d'une marketplace française, on utilise un grand jeu de données public
  d'Amazon comme catalogue de référence. Le périmètre actif compte 3 156 705 produits, limités
  à quatre familles : l'électronique, les téléphones et accessoires, les jeux vidéo, et
  l'outillage et bricolage.
- **Identifier** un produit, c'est retrouver dans ce catalogue le produit exact (ou le plus
  proche) que le vendeur photographie. Une fois le bon produit retrouvé, on connaît sa vraie
  catégorie, sa marque, ses caractéristiques et son prix de référence.
- Un **VLM** (Vision Language Model) est une intelligence artificielle capable de regarder une
  image et d'en parler en texte. Ici, on s'en sert pour décrire une photo et la transformer en
  une requête de recherche.
- **Ancrer** (en anglais « grounding ») veut dire forcer le texte généré à coller aux données
  réelles du produit retrouvé, au lieu de laisser l'IA inventer. C'est la règle centrale du
  projet : on retrouve un vrai produit avant de générer quoi que ce soit, pour éviter les
  inventions (les « hallucinations »).

Légende des états : conforme = la fonction est livrée et marche ; partiel = livrée en partie ;
différé = volontairement reporté, avec une raison assumée.

## Tableau de bord des neuf fonctions

| Fonction | Ce qui était promis | État | En une phrase |
|---|---|---|---|
| **Identification ancrée** | photo vers recherche vers désambiguïsation vers vérification visuelle | conforme | L'entrée par photo est active de bout en bout : la photo est lue par un VLM, transformée en requête, le bon produit est retrouvé, jugé par une étape d'identification raisonnée, puis une vérification visuelle confirme le résultat (90,3 % d'identification mesurés sur un panel réel de 94 produits). |
| **Catégorie précise** | trouver la sous-catégorie, qualité supérieure à 0,90 | conforme | On affiche la vraie catégorie fine du produit retrouvé, et un banc d'essai de six modèles de classement atteint un F1 de 0,954. |
| **Caractéristiques et observations dirigées** | marque, modèle, couleur, version, plus observations guidées | conforme | Les caractéristiques visibles sont pré-remplies depuis la photo, et l'application demande des observations ciblées quand deux produits se ressemblent trop. |
| **Génération ancrée** | rédaction appuyée sur les données réelles du produit | conforme | Le titre et la description sont rédigés en s'appuyant sur la description réelle du produit dans le catalogue, pas sur la mémoire de l'IA. |
| **Prix transparent** | prix expliqué à partir de produits voisins, état et ancienneté | conforme | Le prix est calculé par une formule lisible (cascade L1 à L4, plus un niveau L1.5 d'ancre IA), avec un niveau de confiance, une fourchette, des garde-fous anti-aberrations et une conversion dollar vers euro. |
| **Plusieurs modes d'usage** | mode express, mode assisté, mode lot | conforme | Les trois modes existent, dont un mode « déménagement » qui enchaîne les objets à la chaîne. |
| **Garde-fous contre l'inconnu** | seuil de confiance et mode dégradé | conforme | Trois niveaux de confiance ; les candidats sont toujours montrés et c'est l'humain qui valide. |
| **Entretien automatique du modèle** | ré-entraînement, détection de dérive, rechargement | conforme | Une chaîne automatisée ré-entraîne, compare et remplace le modèle en service ; un outil surveille la dérive des données. |
| **Spécialisation poussée du VLM** | optionnelle, seulement si le gain dépasse un seuil mesuré | différé | Non déclenchée faute de preuve d'un gain suffisant (refus assumé de la sur-ingénierie). |

## Détail de chaque fonction

### Identification ancrée : identifier le produit à partir de la photo, sans inventer

C'est le cœur du projet. Le parcours d'identification fonctionne en plusieurs étapes, et
l'entrée par photo est pleinement active.

1. **Lecture de la photo par un VLM.** Le vendeur envoie une ou plusieurs photos (jusqu'à
   quatre passent dans un seul appel pour limiter le coût). Le VLM utilisé pour lire la photo est
   le modèle Qwen (plus précisément qwen3.5-flash, choisi parce qu'il est rapide et peu coûteux
   pour une tâche de perception visuelle), appelé via le service en ligne OpenRouter (une
   passerelle qui donne accès à plusieurs IA). Ce choix est réglable sans toucher au code, par une
   variable d'environnement, ce qui permettrait de brancher un modèle plus puissant si besoin. Le
   VLM regarde les photos et renvoie un titre de produit probable au format d'une fiche Amazon
   (marque, modèle, caractéristiques visibles, couleur) ainsi qu'une liste d'attributs observés
   (marque, couleur, capacité, texte lisible sur l'étiquette). Pour que le résultat soit
   reproductible, l'appel est réglé en mode déterministe (température fixée à 0, graine fixée à
   42). Si le vendeur ajoute du texte, il complète la requête, mais il reste facultatif.

2. **Recherche du produit dans le catalogue.** Le titre obtenu est transformé en une suite de
   nombres appelée vecteur (une « signature numérique » : deux produits qui se ressemblent ont
   des vecteurs proches). Cette transformation est faite par un modèle de texte multilingue
   nommé Arctic Embed, qui produit un vecteur de 1024 nombres. La signature est comparée à
   celles du catalogue grâce à FAISS, une bibliothèque qui retrouve très vite les éléments les
   plus proches parmi des millions de vecteurs. On récupère les 30 produits les plus proches,
   triés du plus ressemblant au moins ressemblant. Comme le catalogue est en anglais, la requête
   du vendeur est d'abord traduite en anglais (une requête française obtient un score inférieur
   d'environ 0,08) ; si la traduction échoue, la recherche continue quand même sur le texte brut.

3. **Désambiguïsation si deux produits se ressemblent trop.** Quand le meilleur et le deuxième
   candidat ont des scores très proches (écart inférieur à 0,05), l'application bascule en mode
   d'observation dirigée, décrit dans la fonction « Caractéristiques et observations dirigées ».

4. **Identification raisonnée : le moteur de recherche apporte la connaissance, l'IA apporte le
   jugement.** Une étape clé a été ajoutée pour fiabiliser le choix du bon produit. Le moteur de
   recherche fournit les quinze meilleurs candidats réels du catalogue (la « connaissance »), mais
   c'est ensuite une IA qui les « juge » (le « jugement »). En un seul appel, on envoie à l'IA une
   ou deux photos du vendeur plus les quinze fiches candidates résumées en texte (pas leurs images,
   pour économiser le coût) plus les attributs déjà observés. L'IA renvoie alors la famille de
   produit, le candidat qu'elle estime le bon, un prix neuf de référence estimé (utile pour le
   prix, voir la fonction « Prix transparent »), d'éventuelles caractéristiques avec leur source, et
   éventuellement une question à poser au vendeur. Le candidat choisi est remis en tête de liste, pour que la fiche, le prix et
   la vérification portent ensuite sur le bon produit. C'est cette étape qui corrige un défaut
   concret : auparavant, le tout premier résultat de la recherche pouvait être un accessoire (par
   exemple une coque d'iPhone affichée comme s'il s'agissait de l'iPhone lui-même). Des garde-fous
   stricts empêchent toute invention : si l'IA désigne un produit absent des quinze candidats, on
   revient au premier résultat de la recherche et on remet sa confiance à zéro ; une
   caractéristique dont la source n'est pas vérifiable est jetée. Toute cette étape est un bonus
   non bloquant : si l'IA est indisponible ou échoue, on garde simplement le classement de la
   recherche, sans jamais planter ni produire de fiche vide.

5. **Le texte du vendeur fait foi quand il nomme un produit présent dans les candidats.** Si le
   vendeur écrit des précisions qui nomment clairement un produit figurant dans les candidats (au
   moins deux mots distinctifs en commun, en conservant les numéros de modèle même à un seul
   chiffre, par exemple distinguer « Momentum 3 » de « Momentum 2 »), ce produit est retenu de
   façon certaine, indépendamment de l'IA rapide qui ignore parfois cette consigne. Quand plusieurs
   candidats sont à égalité, on garde celui dont le prix est le plus représentatif (le plus proche
   de la médiane), pour ne pas bâtir la fiche sur une donnée corrompue (par exemple un même produit
   listé par erreur à un prix aberrant). Sur un texte vide, cette règle ne fait rien : aucun risque
   de régression.

6. **Vérification visuelle du meilleur candidat.** Une fois le meilleur candidat trouvé, on
   demande au VLM de comparer les photos du vendeur à l'image officielle de ce candidat dans le
   catalogue, en posant la question : « ces photos montrent-elles le même modèle de produit ? ».
   Le VLM renvoie un verdict (correspondance oui ou non, un niveau de confiance entre 0 et 1, et
   une courte raison). Ce verdict s'affiche comme un badge de confiance dans l'interface ; il ne
   décide jamais à la place de l'humain. Si la vérification est indisponible (pas d'image
   catalogue, IA en panne), elle est simplement omise : c'est un bonus, jamais un bloqueur. Pour
   gagner du temps, on saute cet appel supplémentaire quand l'identification raisonnée a déjà
   tranché avec confiance, car elle a déjà jugé la correspondance.

7. **Filet de sécurité quand rien ne correspond.** Si aucun candidat n'est satisfaisant, on
   bascule honnêtement en mode dégradé « produit non identifié, saisie assistée » plutôt que
   d'afficher une mauvaise correspondance (voir la fonction « Garde-fous contre l'inconnu »).

Mesure réelle de bout en bout. Plutôt que de se fier à des impressions, on a mesuré ce parcours
sur un panel de 94 vrais produits photographiés (le nom du dossier de chaque produit servant de
vérité de référence), à partir de la photo seule, sans précisions texte. Le taux d'identification
atteint 90,3 % (on considère un produit identifié quand au moins la moitié des mots clés de son
nom se retrouvent dans la famille jugée par l'IA et dans le titre du premier candidat), avec un
rappel moyen de 78 %. L'étape d'identification raisonnée s'est déclenchée dans 100 % des cas. Les
9 produits non identifiés sont tous expliqués : soit une limite de perception du modèle (par
exemple une carte graphique RTX 4080 Super prise pour une 3080, ou un casque Sennheiser pris pour
un Philips), soit un produit réellement absent du catalogue, soit un nom de dossier ambigu (un
artefact de la mesure elle-même, pas une vraie erreur). Cette mesure est reproductible et
remplace les anecdotes par un chiffre défendable.

Limite honnête à connaître. À partir de la photo seule, la perception du modèle exact reste
limitée pour les produits dont le marquage n'est pas visible sur les photos envoyées (par exemple
un casque dont le logo se trouve sur l'étui). L'IA peut alors choisir un produit sosie avec
assurance. Trois mécanismes atténuent ce risque : le texte du vendeur qui fait foi (la précision
écrite fixe le produit quand il est au catalogue), le drapeau « modèle à confirmer » qui prévient
honnêtement le vendeur, et le bouton « ce n'est pas le bon produit ? ». Un modèle de vision plus
puissant ferait mieux ; c'est une option ouverte, non activée par défaut faute de besoin prouvé.

Reste à faire : l'indexation visuelle directe du catalogue, c'est-à-dire comparer la photo du
vendeur directement aux photos du catalogue (image contre image), et non plus en passant par le
texte. La mécanique est déjà prête dans le code, mais elle attend la production des signatures
d'image de tout le catalogue. Cette décision est volontairement reportée tant qu'une mesure
réelle ne prouve pas son utilité.

### Catégorie précise : afficher la bonne catégorie, fine et fiable

La promesse était de prédire la sous-catégorie d'un produit avec une qualité supérieure à 0,90.
La qualité se mesure par le F1, un score entre 0 et 1 qui combine deux choses : la précision
(quand on dit « téléphone », a-t-on raison ?) et le rappel (attrape-t-on bien tous les
téléphones ?).

Deux résultats valident cette fonction.

D'abord, par rigueur méthodologique, on a entraîné et comparé six modèles de classement sur
exactement le même protocole, sans tricher (entraînement sur un jeu, mesure sur un autre jamais
regardé pendant l'apprentissage). Le meilleur atteint un F1 pondéré de 0,9537, soit environ
0,954, bien au-dessus de l'objectif de 0,90. Fait notable, le F1 « macro » (qui traite les
catégories rares à égalité avec les fréquentes) reste proche du F1 pondéré, ce qui prouve que le
modèle gère bien les catégories rares.

Ensuite, et c'est le point important, l'application n'a pas besoin d'un classifieur séparé pour
afficher la catégorie. Puisqu'on a retrouvé le produit exact, on connaît sa vraie catégorie fine
et son rangement complet (le « fil d'Ariane », par exemple « Électronique puis Composants puis
Cartes graphiques »). Pour fiabiliser cette catégorie fine, on ne recopie pas bêtement celle du
tout premier candidat : on fait voter les catégories des produits voisins, chaque voix étant
pondérée par la ressemblance. Sur un banc d'essai, ce vote des voisins atteint une exactitude de
0,733 contre 0,710 en recopiant le premier, soit un gain de 2,4 points, et il fournit en prime
une confiance (la part du vote en faveur de la catégorie gagnante).

### Caractéristiques et observations dirigées : remplir les caractéristiques et lever les doutes par l'observation

La promesse était de remplir marque, modèle, couleur, version, et de compléter par des
observations guidées quand l'information manque.

Les caractéristiques visibles sont pré-remplies de deux façons. D'une part, ce que le VLM a lu
sur les photos (marque, couleur, capacité, texte d'étiquette) sert de point de départ. D'autre
part, on récupère les caractéristiques du produit retrouvé dans le catalogue. Ces
caractéristiques de catalogue sont extraites une fois pour toutes d'un champ de description
technique de chaque produit, et on ne garde que les caractéristiques utiles pour distinguer des
produits (couleur, capacité de stockage, taille d'écran, matière, format, et quelques autres),
en écartant le bruit inutile.

La fiche produite est volontairement la plus complète possible. Au-delà des caractéristiques du
schéma de la catégorie, on affiche aussi les attributs riches lus sur la photo ou trouvés au
catalogue (format, fonctionnalités, certifications, tension, puissance, connectivité, et autres),
les valeurs trop longues étant raccourcies pour rester lisibles. On y fusionne en plus les
caractéristiques jugées par l'IA lors de l'identification raisonnée, chacune avec sa provenance.
Cinq provenances coexistent et sont affichées telles quelles, pour que le vendeur sache d'où vient
chaque information : observée sur la photo, issue du catalogue d'un produit bien apparié, typique de
la catégorie et donc à vérifier, déduite de la catégorie, ou saisie par le vendeur. Quand le
produit est absent du catalogue, les caractéristiques d'un mauvais candidat ne sont jamais
présentées comme des faits. La complétude de la fiche est mesurée intelligemment, par catégorie
fine : on ne pénalise pas une enceinte pour l'absence d'une « capacité » qui n'a de sens que pour
un produit de stockage. Sur le panel réel de 94 produits, la complétude moyenne mesurée est de 0,84
(médiane 0,83).

La partie la plus originale est la levée d'ambiguïté, surnommée le mode « Akinator » par analogie
avec le jeu de devinettes. Quand deux candidats se ressemblent trop (écart de score inférieur à
0,05), l'application cherche, parmi au plus cinq candidats, l'attribut qui les distingue le mieux.
Pour mesurer ce pouvoir de distinction, elle utilise l'entropie de Shannon, une mesure de
diversité : si tous les candidats ont la même couleur, la couleur ne sert à rien (entropie
nulle) ; si chacun a une couleur différente, la couleur les sépare parfaitement (entropie
maximale). L'attribut le plus séparateur est alors traduit en une consigne visuelle concrète,
par exemple « photographiez l'étiquette au dos », « scannez le code-barres » ou « photographiez
les connecteurs ». Si aucune consigne précise n'existe, on demande par défaut une vue de la face
arrière. Le principe fondateur est : « on demande à voir, pas à savoir ». Plutôt que de poser au
vendeur une question technique qu'il ne saurait pas trancher, on lui demande une simple
observation visuelle. Sur un banc d'essai de 2 000 requêtes, environ 75 % des cas sont jugés
ambigus, et pour 1 492 d'entre eux le système trouve au moins une observation à proposer.

À cela s'ajoute une checklist d'état adaptée au type d'objet, pour que le vendeur décrive
facilement l'état réel de son article. Le « type d'objet » n'est plus choisi manuellement par le
vendeur : il est désormais déduit automatiquement de la catégorie identifiée, ce qui évite des
erreurs de classement (un casque qui contient le mot « phone » dans sa catégorie anglaise, ou un
chargeur, ne sont plus rangés comme des téléphones). La checklist d'état spécifique au type
(batterie et écran pour un téléphone, clavier pour un ordinateur portable, manettes pour une
console, et ainsi de suite) s'affiche après l'identification, c'est-à-dire au bon moment, une fois
qu'on sait de quel type d'objet il s'agit.

### Génération ancrée : rédiger un titre et une description ancrés sur la réalité

La promesse était de produire un titre et une description en français, sans inventer.

La rédaction est confiée à un grand modèle de langage (Gemma, via OpenRouter), mais avec une
contrainte forte : on ne le laisse pas écrire librement. On lui fournit la description réelle du
produit telle qu'elle figure dans le catalogue, et on lui demande de s'appuyer dessus. Cette
technique s'appelle l'ancrage par récupération de phrases (en anglais « RAG ») : on récupère les
phrases factuelles du produit, on les injecte dans les instructions données à l'IA, puis on
génère un texte cohérent avec ces faits. La preuve que l'ancrage marche : une mention technique
précise comme « Snapdragon 732G » dans une annonce provient bien de la description du catalogue,
pas de la mémoire du modèle. Si la clé d'accès à l'IA est absente, un rédacteur de remplacement
factice prend le relais pour que la démonstration reste fonctionnelle.

Amélioration future : ancrer aussi la rédaction sur les avis clients réels du produit (en plus de
sa description), ce qui demanderait une jointure de données supplémentaire encore à mettre en
place.

### Prix transparent : proposer un prix transparent et explicable

La promesse était un prix indicatif calculé par une formule claire, et non par un modèle
« boîte noire » dont on ne pourrait pas expliquer le chiffre. Ce choix est assumé : sans
historique réel de ventes, un prix appris par apprentissage automatique serait un leurre, et le
vendeur particulier doit comprendre pourquoi tel prix lui est suggéré.

Le calcul descend une cascade de niveaux de confiance, du plus sûr au moins sûr :

- **Niveau le plus haut (L1)** : le produit identifié a un prix dans sa fiche catalogue. On part de
  ce prix neuf et on applique l'ancienneté puis l'état (confiance affichée à 0,90).
- **Niveau haut-moyen (L1.5, ajouté avec l'identification raisonnée)** : pas de prix catalogue
  direct, mais l'IA a estimé un prix neuf de référence lors de l'étape d'identification raisonnée
  (voir la fonction « Identification ancrée »). On applique à cette ancre exactement la même décote
  déterministe d'ancienneté et
  d'état. Point important pour la transparence : seule l'ancre, c'est-à-dire le point de départ,
  est une estimation de l'IA ; la décote, elle, reste entièrement calculée par une formule lisible.
  La promesse « pas de prix boîte noire » tient donc toujours. Ce niveau est volontairement placé
  avant les médianes de voisins, car celles-ci sont souvent polluées : un casque à 150 € pouvait se
  retrouver suggéré à quelques euros parce que ses voisins étaient des accessoires ou des coques.
- **Niveau moyen (L2)** : pas de prix direct ni d'ancre IA, mais au moins trois produits voisins
  valides ont un prix. On prend le prix médian de ces voisins, puis on applique l'ancienneté et
  l'état (confiance entre 0,50 et 0,80 selon la dispersion des prix voisins).
- **Niveau bas (L3)** : on ne connaît que la catégorie. On part du prix médian de la catégorie,
  ajusté par l'état (confiance 0,30).
- **Niveau très bas (L4)** : produit et catégorie inconnus. On bascule en saisie manuelle, et
  l'interface n'affiche plus jamais « 0,00 € » comme s'il s'agissait d'une suggestion, mais
  « prix à fixer ».

Trois garde-fous, ajoutés pour fiabiliser le chiffre, méritent d'être cités car ils corrigent des
cas réels. D'abord, un garde-fou contre la sous-évaluation : une médiane de voisins absurdement
basse au regard du prix neuf attendu décoté est relevée à un plancher (c'est surtout une protection
défensive, le vrai travail étant fait par le niveau L1.5 d'ancre IA). Ensuite, un garde-fou de
cohérence : si le prix catalogue du premier candidat est dérisoire face à l'estimation IA (par
exemple une coque à 43 $ alors que l'iPhone vaut bien plus), c'est le signe que ce premier candidat
est un accessoire mal apparié, et on bascule sur l'ancre IA pour éviter d'afficher « iPhone à
15 € ». Enfin, un garde-fou contre les données corrompues : un prix catalogue très au-dessus de la
médiane des voisins (par exemple une saisie erronée à 9 755 $) est ignoré au profit des voisins.

Deux réglages chiffrés expliquent le résultat. L'état applique un multiplicateur sur le prix
neuf : neuf vaut 1,00, très bon état 0,75, bon état 0,55, état correct 0,35, et l'état « pour
pièces / hors service » 0,15 (une valeur résiduelle, ajoutée car c'est un cas courant en occasion).
L'ancienneté applique une dépréciation annuelle propre à chaque famille, car tout ne vieillit pas à
la même vitesse : moins 15 % par an pour l'électronique, moins 20 % pour les téléphones (très
volatils), moins 10 % pour les jeux vidéo, moins 5 % pour l'outillage (qui se déprécie lentement).
Quand l'année d'achat n'est pas renseignée par le vendeur, on suppose un âge de deux ans, et on le
signale. Comme les prix du catalogue sont en dollars et que l'interface affiche des euros, une
conversion est appliquée à la fin avec un taux fixe documenté de 0,92 (la moyenne sur la période
2024 à 2026), modifiable sans redéploiement par une variable d'environnement. Chaque prix
s'accompagne d'une fourchette et d'une explication en français qui détaille le calcul.

### Plusieurs modes d'usage : trois modes selon le besoin

La promesse était une interface progressive avec plusieurs modes. Les trois sont livrés dans
l'interface web :

- **Mode express** : le plus rapide, une photo et une checklist d'état brève.
- **Mode assisté** : la photo, plus les observations dirigées du mode Akinator et la checklist
  d'état guidée par type de produit, pour lever les doutes et enrichir la fiche.
- **Mode déménagement** (surnommé « mitrailler ») : le vendeur photographie un objet, l'ajoute à
  une file d'attente, et passe immédiatement au suivant sans attendre l'analyse, qui se fait en
  arrière-plan. La file est conservée par le navigateur. Ce mode est pensé pour traiter en série
  beaucoup d'objets, typiquement lors d'un déménagement.

### Garde-fous contre l'inconnu : avouer le doute plutôt qu'inventer

La promesse était de détecter les produits hors catalogue et de basculer en mode dégradé au lieu
d'afficher une fausse correspondance. « OOD » est le terme technique pour « hors distribution »,
c'est-à-dire un produit qui ne ressemble à rien de connu dans le catalogue.

Un seuil de référence avait d'abord été calibré à 0,600 en comparant des fiches catalogue
complètes entre elles, avec une précision mesurée de 0,953 et un rappel de 0,988 (autrement dit,
quand le système affirme avoir identifié un produit, il a raison dans 95,3 % des cas). Mais en
usage réel, la requête d'un vendeur (une photo et quelques mots) est plus courte qu'une fiche
catalogue, donc son score est systématiquement plus bas. Pour cette raison, on ne cache jamais
les candidats : on les montre toujours et on laisse l'humain valider. On affiche en plus un
niveau de confiance à trois paliers, calculé sur le score du meilleur candidat :

- score supérieur ou égal à 0,60 : produit *identifié* ;
- score entre 0,45 inclus et 0,60 exclu : produit *à confirmer* par le vendeur ;
- score inférieur à 0,45 : correspondance *incertaine*, à vérifier ou à saisir à la main.

Deux affichages honnêtes ont été ajoutés pour mieux dire le doute au bon endroit. D'abord, quand
l'identification raisonnée conclut que le produit n'est pas au catalogue, un bandeau « produit
estimé, absent du catalogue » prévient que la fiche et le prix sont à vérifier. Ensuite, un drapeau
« modèle à confirmer » distingue deux types de doute qui étaient confondus. La confiance affichée
sous forme de pourcentage correspond à la part du vote des voisins en faveur de la catégorie fine ;
on ne l'affiche que lorsqu'elle est nette (au moins 60 %). Un pourcentage bas ne veut pas dire qu'on
doute de la catégorie : il reflète le plus souvent une hésitation sur le modèle exact (par exemple,
pour un casque, le vote peut se fragmenter à 34 % entre plusieurs références très proches). Dans ce
cas, plutôt qu'un pourcentage trompeur, on affiche un bandeau actionnable « modèle à confirmer :
précisez le modèle ou ajoutez une photo de l'étiquette ou de la boîte », qui reprend la question
discriminante proposée par l'IA quand elle en a une. Enfin, l'interface auto-confirme la fiche
directement quand l'IA est sûre, tout en gardant toujours un bouton « ce n'est pas le bon
produit ? » pour revenir aux autres candidats : la décision finale reste à l'humain.

### Entretien automatique du modèle : entretenir le modèle tout seul

La promesse était un cycle de vie automatisé : ré-entraîner le modèle, détecter la dérive des
données, et recharger le nouveau modèle sans coupure.

Trois briques rendent cela réel.

D'abord, le suivi et le versionnement des modèles. Chaque entraînement est enregistré comme un
« run » avec ses réglages, ses scores et ses fichiers, grâce à MLflow (un outil de suivi
d'expériences d'IA). Les modèles sont rangés dans un registre, et celui qui est en service porte
une étiquette de production.

Ensuite, le ré-entraînement automatique en boucle fermée. Apache Airflow (un planificateur de
tâches qui exécute des étapes dans l'ordre, à l'heure prévue) lance régulièrement une suite
d'étapes : ré-entraîner un nouveau modèle, l'évaluer, le comparer à celui en service, et ne le
mettre en production que s'il fait clairement mieux. La règle de remplacement est volontairement
prudente : le nouveau modèle ne prend la place de l'ancien que s'il dépasse son score d'au moins
0,001 point, pour ne pas remplacer un modèle à cause d'un simple bruit de mesure. Cette boucle a
réellement produit plusieurs versions successives du modèle.

Enfin, la détection de dérive. Evidently (un outil qui compare la distribution des données
récentes à une distribution de référence) surveille si les données d'entrée se mettent à changer
au fil du temps, ce qui signalerait que le modèle risque de vieillir.

Amélioration future : le rechargement à chaud du modèle dans l'interface de programmation, pour
basculer sur le nouveau modèle sans aucune interruption de service.

### Spécialisation poussée du VLM, volontairement reportée

Cette fonction était dès le départ marquée comme optionnelle. L'idée était de spécialiser le VLM
sur nos données par une technique d'entraînement légère (le « fine-tuning QLoRA », qui ajuste un
gros modèle à moindre coût). La règle posée était claire : ne la déclencher que si un test
prouve un gain réel supérieur à 0,05 de qualité par rapport au VLM utilisé tel quel, sans
spécialisation. Ce gain n'a pas été démontré, donc la fonction n'a pas été déclenchée. C'est un
refus assumé de la sur-ingénierie : on ne dépense pas un effort coûteux sans preuve de bénéfice.

## Bilan en une phrase

Huit des neuf fonctions sont conformes : le parcours par photo est complet, de la lecture de
l'image jusqu'au prix expliqué, en passant par l'identification ancrée, la catégorie fine, la
levée d'ambiguïté, la rédaction ancrée, les trois modes d'usage, les garde-fous contre l'inconnu
et l'entretien automatique du modèle. Les seuls reports assumés sont l'indexation visuelle
directe du catalogue (image contre image, en attente d'une mesure de gain) et la spécialisation
poussée du VLM, conditionnée à une preuve de bénéfice.

## D'où venaient les manques au départ, et comment ils ont été comblés

Les fonctions « Catégorie précise », « Caractéristiques et observations dirigées » et « Génération
ancrée » ont d'abord souffert d'un choix de nettoyage initial : pour simplifier
les données, on avait écarté les colonnes riches de chaque produit (ses images, sa fiche
technique détaillée, son arborescence de catégories, sa description). On a corrigé cela en
reconstruisant une table de correspondance compacte à partir des métadonnées brutes. Cette table
associe à chaque produit ses différentes vues photo, sa catégorie fine et son fil d'Ariane
complet, sa marque réelle (plus fiable que le nom de la boutique, souvent un revendeur), et ses
caractéristiques utiles. On a aussi réintégré la description. Tout cela sans refaire la lourde
fusion de données d'origine, donc à coût maîtrisé.

## Ce qu'il reste à faire

Le cœur du produit est conforme. Les suites prévues sont :

- **Tester l'indexation visuelle directe du catalogue** (environ une nuit de calcul) puis décider,
  par la mesure et non par intuition, si on l'active.
- **Déclencher la spécialisation poussée du VLM** uniquement si un test démontre un gain réel
  supérieur à 0,05 de qualité face au VLM utilisé sans spécialisation.
- **Améliorations mineures** : ancrer la rédaction aussi sur les avis clients (en plus de la
  description), recharger à chaud le modèle dans l'interface de programmation, et normaliser la
  casse des noms de marques.

## En une phrase, pour la défense

« Toutes les fonctions promises sont livrées sauf deux volontairement reportées : le parcours par
photo va de la lecture de l'image jusqu'au prix expliqué, chaque étape s'ancre sur un vrai produit
du catalogue pour ne jamais inventer, et les seuls reports (la recherche image contre image et la
spécialisation poussée du modèle de vision) sont conditionnés à une preuve de gain mesurée, pas à
une intuition. »

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
 - état général ........ optionnel (neuf / très bon état / bon état / correct)
 - checklist par type .. optionnel (fonctionne ? boîte ? accessoires ? facture ?
                          plus des questions adaptées au type d'objet)
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
 [5] Levée de doute (mode "Akinator") : si deux candidats se ressemblent trop,
     le système pose la question qui les sépare le mieux
     les attributs déjà lus sur la photo pré-remplissent certaines réponses
 |
 [6] Vérification visuelle : un modèle qui voit compare la photo du vendeur
     avec l'image du produit retenu et confirme (ou non) la ressemblance
 |
 [7a] PRIX                          [7b] DESCRIPTION
      état -> décote sur le prix         un modèle qui écrit, ancré sur la vraie
      du produit réel                    fiche, plus la checklist d'état intégrée
 |                                   |
 [8] ANNONCE FINALE
     catégorie + photos + prix + caractéristiques + description
```

Un mot sur les **caractéristiques** de l'annonce finale (le bloc « informations clés »). Elles ne
sont pas un simple recopiage : chaque champ (marque, couleur, capacité, modèle, taille…) porte sa
**provenance**, c'est-à-dire d'où vient l'information. Trois origines, par ordre de fiabilité :
**observé** (lu directement sur la photo du vendeur, le plus sûr pour cet objet précis),
**catalogue** (tiré de la fiche du produit retrouvé) et **typique-à-vérifier** (valeur habituelle
pour ce genre de produit, donc à confirmer, jamais affirmée). On mesure aussi la **complétude** de
la fiche, c'est-à-dire la part des caractéristiques attendues pour cette catégorie qui sont
effectivement remplies. Ce rangement à champs sourcés est ce qui rend les fiches exploitables par
un moteur de recherche acheteur (filtrer par couleur, par capacité…), au lieu d'une simple grande
catégorie.

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
cascade de quatre niveaux et s'arrête au premier qui s'applique :

- Niveau 1 (confiance haute) : le produit identifié a un prix dans sa fiche catalogue. On
  part de ce prix réel, on applique la décote liée à l'état, puis la dépréciation liée à
  l'âge.
- Niveau 2 (confiance moyenne) : pas de prix de fiche, mais on connaît le prix des dix
  produits voisins les plus ressemblants. On prend leur prix médian, puis les mêmes décotes.
- Niveau 3 (confiance basse) : on ne connaît que la catégorie. On part du prix médian de
  cette catégorie, puis la décote d'état.
- Niveau 4 (confiance très basse) : produit ou catégorie inconnus. On renvoie une fourchette
  large et un mode dégradé invitant à une saisie manuelle.

La décote selon l'état est un multiplicateur appliqué sur le prix de référence : neuf 1,00 ;
très bon état 0,75 ; bon état 0,55 ; correct avec défauts 0,35. La dépréciation par âge
dépend de la catégorie, car les objets ne perdent pas leur valeur au même rythme : environ
moins 15 % par an pour l'électronique, moins 20 % par an pour les téléphones et accessoires
(marché très volatil), moins 10 % par an pour les jeux vidéo (la collection peut ralentir la
perte), moins 5 % par an pour l'outillage et le bricolage (qui vieillit lentement).

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

## 8. Vocabulaire minimum

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

## 9. Périmètre et choix assumés

- Les modèles entraînés en interne sont des modèles d'apprentissage automatique classiques
  (méthode des plus proches voisins, machines à vecteurs de support, petit réseau de
  neurones, pondération de mots TF-IDF). L'encodeur de texte (Arctic Embed) est pré-entraîné
  et figé : on l'utilise tel quel sans le ré-entraîner. Le modèle qui voit les images et le
  modèle qui rédige sont externes, appelés via une interface de programmation distante. Ce
  choix est justifié : pour identifier un produit dans un catalogue, la recherche ancrée bat
  un modèle qui devine, et elle coûte moins cher à maintenir.
- La valeur d'ingénierie tient dans la chaîne complète : des données propres, des modèles
  comparés et mesurés, mis en production, surveillés, et ré-entraînables.
- Données : faute d'un jeu de données public Rakuten, on utilise le jeu « Amazon Reviews
  2023 » comme substitut. Le biais introduit est documenté et l'architecture reste
  transposable à de vraies données Rakuten.

## 10. Phrase de défense

Notre système ne devine pas un produit, il le retrouve dans un catalogue réel puis rédige
l'annonce à partir de ces faits vérifiés. La photo suffit à démarrer, l'humain valide
toujours le résultat, le prix s'explique en clair, et toute la chaîne, des données propres
jusqu'à la surveillance en production, est mesurée et reproductible.

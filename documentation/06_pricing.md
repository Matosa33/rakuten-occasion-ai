# 06 — Estimation de prix transparente

> Proposer un **prix conseillé** pour l'objet d'occasion, avec une **fourchette**, un
> **niveau de confiance** et une **explication lisible** — plutôt qu'un nombre sorti d'une
> boîte noire.

---

## 1. La technologie : qu'est-ce que c'est ?

Estimer le prix d'un objet d'occasion, c'est répondre à : *« combien ça vaut, vu son état
et son âge ? »*. Deux familles d'approches :
- **Modèle ML opaque** : un réseau prédit un nombre, sans expliquer pourquoi.
- **Approche algorithmique transparente** (la nôtre) : un calcul **explicable** par étapes
  (prix de référence → dépréciation selon l'âge → ajustement selon l'état), avec un **niveau
  de confiance**.

La brique « comparables » : on regarde le prix de **produits voisins** (les « comps », comme
un agent immobilier regarde les ventes de maisons similaires). C'est une logique **KNN**
(k plus proches voisins).

---

## 2. État de l'art

- Le **KNN est une méthode reconnue** pour estimer un prix d'occasion : on prend les *k*
  observations les plus proches et on fait la **médiane/moyenne** de leur prix. Adapté aux
  petits jeux et très intuitif (« comps »). Des études occasion-auto rapportent ~85 %
  d'exactitude KNN vs ~71 % pour une régression linéaire.
- On ajuste *k* sur un jeu de validation ; distance euclidienne par défaut.
- **MAPE** (*Mean Absolute Percentage Error*) = erreur moyenne en pourcentage, métrique
  standard pour un prix.

---

## 3. Notre implémentation

Un seul module clair, `src/pricing/01_algorithmique.py`, qui applique une **cascade à 4
niveaux de confiance** (on utilise le niveau le plus fiable disponible) :

| Niveau | Quand | Calcul |
|---|---|---|
| **L1 (haute)** | le prix figure dans la fiche du produit identifié | prix catalogue × dépréciation × état |
| **L2 (moyenne)** | pas de prix direct, mais des voisins (KNN k=10) | **médiane** des prix voisins × dépréciation × état |
| **L3 (basse)** | seule la catégorie est connue | médiane de la catégorie × état |
| **L4 (très basse)** | produit/catégorie inconnus | fourchette large + « saisie manuelle » |

Réglages explicites (sérialisés dans `data/models/m8_pricing_v1.joblib`) :
- **Multiplicateurs d'état** : neuf 1,0 · très bon 0,75 · bon 0,55 · correct 0,35.
- **Dépréciation/an par catégorie** : Téléphones 20 % · Électronique 15 % · Jeux vidéo 10 %
  (la collection retient la valeur) · Outils 5 %.
- **Conversion USD→EUR** (taux fixe 0,92, paramétrable — D-036) : les prix catalogue sont en
  dollars (Amazon), l'app affiche des euros, avec l'explication des deux devises.

Choix structurant : **transparence plutôt qu'une fausse précision** (R19). Le vendeur doit
comprendre *pourquoi* ce prix ; un nombre opaque inspirerait moins confiance.

---

## 4. Résultats (mesurés)

- Cascade fonctionnelle : exemple live, iPhone 13 « bon état » → **~232 € (niveau L1)** avec
  explication double-devise (« 399 $ ≈ 367 € − dépréciation 2 ans − ajustement bon état »).
- **MAPE** (`reports/08_pricing/`) : L2 (KNN) **~62 %** médian, L3 (catégorie) **~56 %**.
- Tests : `test_pricing_cascade.py` (les 4 niveaux + conversion devise).

> ⚠️ **À expliquer honnêtement** : un MAPE de ~62 % paraît élevé. La raison est **structurelle** :
> les prix du catalogue sont des **prix NEUFS**, alors qu'on estime de l'**occasion** — sans
> données de **ventes réelles** d'occasion, aucun modèle ne pourrait être précis. On a donc
> choisi **un prix transparent par niveaux de confiance** plutôt qu'un ML opaque qui donnerait
> un faux sentiment de précision.

> 📊 **Chiffres slide** : « cascade 4 niveaux de confiance », « multiplicateurs d'état +
> dépréciation par catégorie », « prix L1 232 € expliqué ». 📸 **Capture** : la carte prix de
> l'app (prix + fourchette + badge état + explication double-devise).

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Logique KNN « comps »** alignée sur l'état de l'art de l'estimation d'occasion.
- ✅ **Transparence + niveaux de confiance + fourchette** → un vendeur comprend et peut
  ajuster (bien plus défendable qu'une boîte noire).
- ✅ **Honnêteté sur le MAPE** : on nomme la cause (prix neuf vs occasion) plutôt que de la
  cacher.
- ✅ Dépréciation **différenciée par catégorie** (un jeu vidéo ne se déprécie pas comme un
  téléphone) → finesse métier.

**Limites assumées :**
- **MAPE élevé** faute de **données de ventes d'occasion réelles** : c'est LA limite. Avec un
  historique de transactions Rakuten, on pourrait passer à un vrai modèle calibré.
- **Taux de change fixe** (0,92) : suffisant pour un indicatif, mais pas « temps réel ».
- **Pas de signal de demande/saisonnalité** (un modèle avancé intégrerait l'offre/demande).

---

## 6. Références
- ResearchGate — *Used Car Price Prediction using KNN-based model* — https://www.researchgate.net/publication/350094568_Used_Car_Price_Prediction_using_K-Nearest_Neighbor_Based_Model
- Hands-On ML with R — *Chapter 8: K-Nearest Neighbors* — https://bradleyboehmke.github.io/HOML/knn.html
- MDPI — *Spatially explicit KNN for house price predictions* — https://www.mdpi.com/2220-9964/15/1/46
- GeeksforGeeks — *KNN algorithm* — https://www.geeksforgeeks.org/machine-learning/k-nearest-neighbours/

---

### En une phrase (pour la défense)
*« On propose un prix par une cascade transparente à 4 niveaux de confiance (prix catalogue,
sinon médiane des voisins KNN, sinon médiane catégorie), ajusté par l'état et une dépréciation
propre à chaque catégorie, le tout expliqué au vendeur. On assume un MAPE élevé car les prix
de référence sont neufs et nous n'avons pas de données de ventes d'occasion — d'où le choix de
la transparence plutôt qu'une fausse précision. »*

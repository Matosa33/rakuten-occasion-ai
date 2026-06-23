# 06 — Estimation de prix transparente

> Proposer un **prix conseillé** avec une **fourchette**, un **niveau de confiance** et une
> **explication lisible** — plutôt qu'un nombre sorti d'une boîte noire que le vendeur ne peut
> pas comprendre.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
Estimer le prix d'un objet d'occasion = répondre à « combien ça vaut, vu son **état** et son
**âge** ? ». Deux familles:
- **ML opaque**: un modèle prédit un nombre, sans expliquer pourquoi.
- **Approche algorithmique transparente** (la nôtre): un calcul **explicable par étapes** —
 prix de référence → dépréciation selon l'âge → ajustement selon l'état — avec un **niveau de
 confiance**.

La brique « comparables »: on regarde le prix de **produits voisins** (les « comps », comme un
agent immobilier compare des maisons similaires). C'est une logique **k-NN**.

### Pour l'expert
- On assume une **précision limitée** (MAPE ~62 %) **par honnêteté structurelle**: nos prix de
 référence sont des **prix NEUFS** (catalogue Amazon), or on estime de l'**occasion**, sans
 données de **ventes réelles** d'occasion. Aucun ML ne serait précis là-dessus → on préfère un
 **prix transparent + fourchette + niveau de confiance** à une fausse précision.

---

## 2. État de l'art

- Le **k-NN** est reconnu pour l'estimation de prix d'occasion (médiane/moyenne des *k* voisins);
 études occasion-auto: ~85 % d'exactitude k-NN vs ~71 % régression linéaire.
- Distance euclidienne; *k* ajusté sur validation.
- **MAPE** (*Mean Absolute Percentage Error*) = métrique standard pour un prix.
- Tendance: afficher **incertitude + explication** plutôt qu'un point sec (confiance utilisateur).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

`src/pricing/01_algorithmique.py` — `suggest_price(...)` applique une **cascade à 4 niveaux de
confiance** (on prend le plus fiable disponible):

| Niveau | `method` | Quand | Calcul |
|---|---|---|---|
| **L1** | `catalog_meta` | prix dans la fiche du produit identifié | `prix × dépréciation(âge,cat) × état × USD_TO_EUR` |
| **L2** | `knn_median` | pas de prix direct, mais des voisins (k=10) | **médiane** des prix voisins × dépréciation × état |
| **L3** | `category_median` | seule la catégorie connue | médiane catégorie × état |
| **L4** | `fallback` | produit/catégorie inconnus | fourchette large + « saisie manuelle » |

Détails exacts:
- **`_depreciate(price, age, category)`**: `price × taux_cat ^ âge` avec des taux **différenciés
 par catégorie**: Téléphones 20 %/an, Électronique 15 %, **Jeux vidéo 10 %** (la collection
 retient la valeur), Outils 5 %.
- **`_apply_condition`**: multiplicateurs **neuf 1,0 · très bon 0,75 · bon 0,55 · correct 0,35**
 (défaut `bon_etat` = 0,55).
- **Conversion `USD_TO_EUR = 0,92`** (env `PRICE_USD_EUR_RATE`), appliquée **APRÈS** dépréciation
 + état → les prix catalogue (USD Amazon) deviennent des euros.
- **Fourchette = ±15 %** autour du prix (`range_low/high`).
- **Explication double-devise** générée: « 399,00 $ (≈ 367 €): dépréciation 15 %/an sur 2 ans,
 ajustement Bon état ».

> Choix structurant: **transparence plutôt qu'une fausse précision**. Le vendeur doit
> comprendre *pourquoi* ce prix; un nombre opaque inspirerait moins confiance.

---

## 4. Résultats (mesurés)

- Cascade live: iPhone 13 « bon état » → **~232 € (niveau L1)** avec explication double-devise.
- **MAPE** (`reports/08_pricing/`): L2 (k-NN) **~62 %** médian, L3 (catégorie) **~56 %**.
- Tests: `test_pricing_cascade.py` (les 4 niveaux + conversion devise + multiplicateurs).

> ⚠️ **À expliquer honnêtement**: un MAPE de ~62 % paraît élevé, mais c'est **structurel** —
> prix neuf vs occasion, sans données de ventes réelles. D'où le choix d'un **prix transparent
> par niveaux de confiance** plutôt qu'un ML opaque faussement précis.

> 📊 **Chiffres slide**: « cascade 4 niveaux de confiance », « dépréciation par catégorie +
> multiplicateurs d'état », « L1 232 € expliqué double-devise », « MAPE ~62 % assumé (neuf vs
> occasion) ». 📸 **Capture**: la carte prix de l'app (prix + fourchette + badge état +
> explication).

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Logique k-NN « comps »** alignée sur l'état de l'art de l'occasion.
- ✅ **Transparence + niveaux de confiance + fourchette** → un vendeur comprend et peut ajuster
 (bien plus défendable qu'une boîte noire).
- ✅ **Dépréciation différenciée par catégorie** → finesse métier (un jeu vidéo ≠ un téléphone).
- ✅ **Honnêteté sur le MAPE**: on nomme la cause (neuf vs occasion) plutôt que de la cacher.

**Limites assumées:**
- **MAPE élevé** faute de **ventes d'occasion réelles**: c'est LA limite. Avec un historique de
 transactions Rakuten, on passerait à un vrai modèle calibré.
- **Taux de change fixe** (0,92): suffisant pour un indicatif, pas « temps réel ».
- **Pas de signal de demande/saisonnalité** (un modèle avancé l'intégrerait).
- **Âge supposé** (2 ans par défaut) si non fourni → approximation.

---

## 6. Références
- ResearchGate — *Used Car Price Prediction using KNN-based model* — https://www.researchgate.net/publication/350094568_Used_Car_Price_Prediction_using_K-Nearest_Neighbor_Based_Model
- Hands-On ML with R — *Chapter 8: K-Nearest Neighbors* — https://bradleyboehmke.github.io/HOML/knn.html
- MDPI — *Spatially explicit KNN for house price predictions* — https://www.mdpi.com/2220-9964/15/1/46
- Wikipedia — *Mean absolute percentage error (MAPE)* — https://en.wikipedia.org/wiki/Mean_absolute_percentage_error

---

### En une phrase (pour la défense)
*« On propose un prix par une cascade transparente à 4 niveaux de confiance (catalogue, sinon
médiane des voisins k-NN, sinon médiane catégorie), ajusté par une dépréciation propre à chaque
catégorie et un multiplicateur d'état, converti en euros, et **expliqué** au vendeur. On assume
un MAPE élevé car les prix de référence sont neufs et nous n'avons pas de ventes d'occasion —
d'où le choix de la transparence plutôt qu'une fausse précision. »*

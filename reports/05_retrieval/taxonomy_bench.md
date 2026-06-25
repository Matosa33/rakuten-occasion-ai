# Benchmark taxonomie par retrieval (top1-copy → coarse-to-fine)

- Échantillon test stratifié : **15000** requêtes · top-k=200 · efSearch=128 · seed=42
- Index : 3_156_705 vecteurs train · latence recherche 0.31 ms/requête

| Bras | macro_acc | path_L1_acc | path_L2_acc | leaf_acc | leaf_weighted_f1 | hierarchical_f1 | recall_at_200_leaf |
|---|---|---|---|---|---|---|---|
| top1-copy | 0.9423 | 0.8889 | 0.8080 | 0.7097 | 0.7325 | 0.8118 | 0.9683 |
| macro-gated | 0.9494 | 0.8933 | 0.8099 | 0.7092 | 0.7288 | 0.8115 | 0.9683 |
| knn-vote 🏆 | 0.9494 | 0.9487 | 0.8491 | 0.7333 | 0.7051 | 0.8197 | 0.9683 |
| coarse-to-fine | 0.9494 | 0.9471 | 0.8478 | 0.7307 | 0.7031 | 0.8179 | 0.9683 |

**Champion (accuracy leaf) : `knn-vote`.**

> Lecture : `leaf_acc` = catégorie la plus fine exacte ; `hierarchical_f1` = crédit partiel le long du breadcrumb (montre la progression) ; `recall@k` = la bonne feuille est présente parmi les voisins (plafond atteignable par un meilleur vote/re-ranking).

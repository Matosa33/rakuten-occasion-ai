"""Classifiers benchmark module — Cycle 3 (P04 / C12-C15).

Scripts numérotés (R1) à exécuter dans l'ordre :

    metrics.py               Module utilitaire (F1, top-k, ECE, confusion matrix)
                             Importable, pas exécutable.

    01_tfidf_linsvc.py       M5 — TF-IDF + LinearSVC + Platt (baseline texte
                             brut, ne nécessite pas les embeddings du Cycle 2)

    02_knn.py                M1 — k-NN via FAISS HNSW (D-015, vainqueur F1_w=0.954)
    03_svm.py                M2 — LinearSVC + Platt (sample 500k, D-015)
    04_rf.py                 M3 — RandomForest. ⚠️ NON ENTRAÎNÉ (skippé D-015 :
                             inefficace en haute dim 1024). Script conservé pour
                             réactivation ; fusion/bench le skippent gracieusement.
    05_mlp.py                M4 — MLP head sur embeddings (sample 500k, D-015)

    06_fusion_adaptive.py    M6 — Fusion pondérée vision×texte (méta-modèle)

Stack : scikit-learn 1.5+ + polars + numpy. Tous les modèles sont trackés
MLflow (Cycle 11) en local pour comparaison.

Voir BRAIN/decisions.md D-009 (architecture cible RAG-grounded) et
docs/modeles.md pour les fiches détaillées M1-M6.
"""

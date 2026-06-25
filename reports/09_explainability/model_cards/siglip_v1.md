# Model Card — siglip_v1

**Type** : SigLIP base ViT-B/16 (frozen, 768 dim)
**Tâche** : Encodage image → embedding L2-normalized

## Inputs / Outputs
- **Input** : Image RGB (224×224)
- **Output** : Embedding 768 dim FP16

## Données / Source
- Source : google/siglip-base-patch16-224

## Limitations
- Frozen — pas d'adaptation aux produits Amazon. Cibler fine-tuning si gap mesuré > 5 pts.

## Source de vérité métriques

`reports/04_classifiers_bench/siglip_v1.json`
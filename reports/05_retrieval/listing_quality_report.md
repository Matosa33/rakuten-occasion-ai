# Qualité de fiche & richesse d'entrée — résultats (Cycle 34, D-042)

- **558 fiches** (produits × conditions) · métrique principale : `completeness` · stats appariées.

| Condition | macro_acc | leaf_exact | leaf_overlap | entity_match | completeness | usable | n |
|---|---|---|---|---|---|---|---|
| text-only | 0.871 | 0.150 | 0.225 | 0.720 | 0.505 | 1.000 | 93 |
| text-fr-en | 0.850 | 0.161 | 0.242 | 0.742 | 0.509 | 1.000 | 93 |
| one-photo | 0.817 | 0.194 | 0.246 | 0.656 | 0.641 | 1.000 | 93 |
| multi-photo | 0.903 | 0.194 | 0.269 | 0.785 | 0.699 | 1.000 | 93 |
| multi-photo-meta | 0.892 | 0.215 | 0.271 | 0.850 | 0.694 | 1.000 | 93 |
| multi-photo-meta-fr-en | 0.850 | 0.204 | 0.267 | 0.774 | 0.692 | 1.000 | 93 |

## Tests confirmatoires (appariés)

- **HV completeness photo>texte (qual<=2)** : gain médian +0.143 (IC95 [+0.107, +0.183], 41 familles) · p=0.0000 · n=41
- **H1 completeness multiphoto (one-photo->multi-photo)** : gain médian +0.000 (IC95 [+0.036, +0.081], 92 familles) · p=0.0000 · n=93
- **H1b completeness metadonnee (multi-photo->multi-photo-meta)** : gain médian +0.000 (IC95 [-0.015, +0.003], 92 familles) · p=0.2009 · n=93
- **H1b completeness metadonnee sans-fuite** : gain médian +0.000 (IC95 [-0.021, +0.001], 49 familles) · p=0.0741 · n=49
- **H1c completeness traduction (multi-photo-meta->multi-photo-meta-fr-en)** : gain médian +0.000 (IC95 [-0.011, +0.007], 92 familles) · p=0.5749 · n=93
- **H2 entity multiphoto (one-photo->multi-photo)** : gain médian +0.000 (IC95 [+0.054, +0.208], 92 familles) · p=0.0027 · n=93
- **H2 entity metadonnee (multi-photo->multi-photo-meta)** : gain médian +0.000 (IC95 [+0.011, +0.128], 92 familles) · p=0.0339 · n=93
- **H2 entity metadonnee sans-fuite** : gain médian +0.000 (IC95 [-0.041, +0.082], 49 familles) · p=0.5637 · n=49
- **TOST multi-photo≈multi-photo-meta (sans fuite, SESOI 0.05)** : ÉQUIVALENCE (métadonnée sans effet) · p=0.0000

## Monotonie (Page's L, richesse text-only→one-photo→multi-photo→multi-photo-meta)

- `completeness` : L=2589.0 · p=0.0000
- `leaf_overlap` : L=2362.5 · p=0.0890

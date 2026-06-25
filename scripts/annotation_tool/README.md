# Interface d'annotation — photos d'éval (Phase 2)

Outil local pour saisir **vite et bien** le jeu de produits réels qui servira à prouver
la chaîne de valeur photo-first (**1 photo < N photos < N photos + métadonnée**).

## Lancer

```bash
.venv/Scripts/python.exe scripts/annotation_tool/app.py
# → http://127.0.0.1:8200
```

## Ce qu'elle fait

Glisser-déposer les photos d'un produit, remplir le formulaire, « Enregistrer ». L'outil
**range automatiquement** au bon endroit et au bon format (aucune manip de fichiers) :

```
data/photos_eval/<NN>_<slug>/
    01.jpg 02.jpg …        # 01 = photo principale (sert seule en condition C1)
    meta.json
```

`meta.json` :
```json
{
  "true_name": "iPhone 13 128 Go noir",
  "macro": "Cell_Phones",
  "true_category_path": "Cell Phones & Accessories > Cell Phones",
  "seller_metadata": "Apple iPhone 13 128go",
  "notes": "near-dup avec iPhone 14",
  "photos": ["01.jpg", "02.jpg"],
  "main_photo": "01.jpg"
}
```

## Pour un jeu « bien rempli »

Le tableau de bord (à droite) suit l'avancement :
- **≈ 20 produits**, répartis sur les **4 macro-catégories** (Electronics, Cell_Phones,
  Video_Games, Tools) ;
- **4-6 near-duplicates** (écrire « near-dup » dans les notes) — c'est là que N photos +
  métadonnée prouvent leur valeur ;
- **≥ 2 photos** par produit (sinon le test 1 vs N ne montre rien) ;
- la **photo principale** (bordure verte) doit être la plus représentative.

> Les photos restent **locales** (`data/photos_eval/` est gitignoré) — rien n'est publié.

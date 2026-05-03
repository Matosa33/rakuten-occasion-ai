# Rakuten AI

Assistant IA pour vendeurs particuliers sur marketplace généraliste : génération automatique de fiches produit d'occasion (catégorie, attributs, titre, description, prix indicatif) à partir de photos.

Le cœur ML est un **pipeline d'identification grounded** (cf. ADR D-009) : retrieval ancré sur catalogue indexé (SigLIP+FAISS sur ~26 M items) + désambiguation Akinator backend + VLM zero-shot validateur + LLM rédacteur grounded. **Anti-hallucination par design** — les modèles génératifs valident et rédigent, ils n'identifient jamais sans ancre catalogue (golden rule R19).

> **Repo autonome** : aucune dépendance à un autre repo local. Toutes les références externes vivent dans `docs/PROJECT.md` (sources web sourcées) ou `BRAIN/decisions.md` (raisonnements).

## Démarrage rapide

```bash
git clone <url-du-repo> rakuten_de_zero
cd rakuten_de_zero

# 1. Créer le venv (Python 3.11+ requis)
python3.11 -m venv .venv
source .venv/bin/activate           # Linux/macOS/WSL
# ou : .venv\Scripts\activate       # Windows PowerShell

# 2. Installer le projet + extras data (audit, encoders, etc.)
pip install -e ".[dev,data]"
# Sur Linux/macOS avec Make : make install-data

# 3. Vérifier
pytest tests/ -v                    # 32 tests doivent passer
ruff check src/ tests/              # Lint clean
```

## Structure du repo

```
rakuten_de_zero/
├── BRAIN/                              # Mémoire opérationnelle (9 fichiers, maintenue par agent IA)
│   ├── bios.md                         # Point d'entrée, ordre de lecture
│   ├── state.md                        # Où on en est LÀ MAINTENANT (< 100 lignes)
│   ├── context.md, glossary.md         # QUOI/POURQUOI + lexique
│   ├── golden_rules.md                 # R1-R19 (R19 = grounded-avant-génératif)
│   ├── erreur_a_ne_plus_faire.md       # Pièges connus (append-only)
│   ├── decisions.md                    # ADR chronologique D-001..D-010 (append-only)
│   ├── learnings.md                    # Découvertes positives (append-only)
│   ├── to-do.md                        # Plan détaillé 16 cycles (Cycles 0-15)
│   └── archive/                        # Blocs archivés (avec README convention)
│
├── docs/
│   ├── PROJECT.md                      # Cadrage projet v2.0 (one-pager + sources web)
│   ├── architecture.md                 # Pipeline runtime + 8 modèles M1-M8 + 4 externes E1-E4
│   ├── modeles.md                      # Fiche détaillée par modèle
│   └── exigences_coverage.md           # Matrice 51 cours × 16 cycles d'implémentation
│
├── src/                                # Code applicatif — 1 module par phase
│   ├── config.py                       # Single source of truth des chemins + SEED
│   ├── data/
│   │   ├── audit/                      # ✅ P02 (Cycle 1.1 done)
│   │   ├── clean/                      # P02 cleaning + features (Cycle 1.2)
│   │   ├── split/                      # P02 split stratifié + GroupKFold (Cycle 1.2)
│   │   └── validate/                   # P02 Pandera schemas (Cycle 1.4)
│   ├── encoders/                       # P03 SigLIP + Arctic (Cycle 2)
│   ├── classifiers/                    # P04 4 modèles + TF-IDF + fusion (Cycle 3)
│   ├── retrieval/                      # P05 FAISS + RRF + OOD + Akinator (Cycle 4)
│   ├── vlm/                            # P06 zero-shot validateur (+ QLoRA optionnel) (Cycle 5)
│   ├── llm/                            # P07 prompt + RAG grounded writer (Cycle 6)
│   ├── pricing/                        # P08 algorithmique transparent (Cycle 7)
│   ├── explain/                        # P09 SHAP + t-SNE + Model Cards (Cycle 8)
│   ├── api/                            # P10 FastAPI + SSE (Cycle 9)
│   ├── mlops/                          # P12-P13 MLflow + DVC + Airflow (Cycles 11-12)
│   └── observability/                  # P15 structlog + Prometheus + Evidently (Cycle 14)
│
├── notebooks/
│   ├── 00_meta_exploration.ipynb       # ✅ Méta-first : Range probes + filtre périmètre
│   └── 01_audit_exploratoire.ipynb     # ✅ Sample stratifié interactif
│
├── reports/                            # Partition par phase 01..09
│   ├── 01_audit/ ✅                    # Rapport + JSON métriques + figures
│   ├── 02_cleaning/                    # P02 (à venir)
│   ├── 03_embeddings/                  # P03
│   ├── 04_classifiers_bench/           # P04
│   ├── 05_retrieval/                   # P05
│   ├── 06_vlm_eval/                    # P06
│   ├── 07_rag_eval/                    # P07
│   ├── 08_pricing/                     # P08
│   └── 09_explainability/              # P09
│
├── data/                               # gitignored (sauf .gitkeep et .dvc)
│   ├── raw/full/{reviews,meta}/        # ✅ 60 GB parquet zstd (15 cat D-008)
│   ├── processed/                      # P02 train/val/test
│   ├── embeddings/                     # P03 .npy + .parquet d'index
│   ├── index/                          # P05 FAISS .index
│   └── models/                         # P04+ artefacts entraînés
│
├── frontend/                           # P11 React app (à créer)
├── infra/                              # P14 docker / compose / traefik / minio / k8s
├── monitoring/                         # P15 prometheus / grafana / evidently
├── tests/                              # pytest 32/32 ✅
├── .github/workflows/                  # P16 CI/CD GHCR
├── pyproject.toml                      # deps + extras [data] + ruff + pytest
├── Makefile                            # cibles standardisées (Linux/macOS/Git Bash)
├── .pre-commit-config.yaml
├── .gitignore                          # Python + data + frontend + infra + monitoring
└── .vscode/settings.json
```

## Documentation

- **Cadrage produit** (1 page A4) : [docs/PROJECT.md](docs/PROJECT.md)
- **Architecture cible** (pipeline runtime + 8+4 modèles) : [docs/architecture.md](docs/architecture.md)
- **Fiche par modèle** (M1-M8 + E1-E4 + drift D1-D4) : [docs/modeles.md](docs/modeles.md)
- **Couverture pédagogique** (51 cours × 16 cycles + exigences MLOps) : [docs/exigences_coverage.md](docs/exigences_coverage.md)
- **Mémoire opérationnelle** (9 fichiers BRAIN maintenus par agent IA) : [BRAIN/bios.md](BRAIN/bios.md) en premier — voir note ci-dessous

> 🤖 **À propos du dossier `BRAIN/`** : il est **maintenu exclusivement par l'agent IA** (Claude Code, Cursor, ou équivalent). Si tu travailles sans agent IA, tu peux ignorer ce dossier — le projet reste utilisable via `docs/PROJECT.md` et le code. Si tu utilises un agent IA, demande-lui les phases INIT/RESTIT, ne touche pas aux fichiers à la main (cf. golden rule 9 dans `BRAIN/golden_rules.md`).

## Stack technique cible

| Couche | Composant | Phase | Statut |
|---|---|---|---|
| Vision encoder (frozen) | SigLIP base (Google 2023) — E1 | P03 | not_started |
| Text encoder (frozen) | Snowflake Arctic Embed L v2 — E2 | P03 | not_started |
| Retrieval (cœur identification) | FAISS HNSW multi-view + RRF — M7 | P05 | not_started |
| Désambiguation | Akinator backend (logique pure Python) | P05 | not_started |
| VLM validateur | zero-shot Gemini Flash / Qwen-VL — E3 | P06 | not_started |
| Classifieurs benchmark | k-NN, SVM, RF, MLP, TF-IDF, Fusion — M1-M6 | P04 | not_started |
| LLM rédacteur grounded | Gemini frontier + RAG — E4 | P07 | not_started |
| Pricing transparent | algorithmique déterministe — M8 | P08 | not_started |
| Backend API | FastAPI + Pydantic v2 + SSE | P10 | not_started |
| Frontend | React 19 + Vite + Tailwind | P11 | not_started |
| MLOps | MLflow Registry + DVC + Airflow + BentoML | P12-P13 | not_started |
| Infra | Docker + Compose + Traefik + MinIO (+ K8s) | P14 | not_started |
| Observabilité | structlog + Prometheus + Grafana + Evidently | P15 | not_started |
| CI/CD | GitHub Actions + GHCR | P16 | not_started |

**Fine-tuning VLM (QLoRA)** : OPTIONNEL, descend en F8 (cf. ADR D-010). À activer uniquement si benchmark C19 montre un gain mesurable > +0.05 F1 macro vs E3 zero-shot.

## Méthodologie (côté agent IA)

Si tu utilises un agent IA pour développer, le pattern de travail par sous-tâche est :

```
INIT     → l'agent relit les 9 fichiers BRAIN dans l'ordre bios.md
LECTURE  → l'agent identifie les fichiers projet à lire pour la sous-tâche
RUN      → l'agent exécute (code, tests, doc)
RESTIT   → l'agent update BRAIN/state.md + append decisions/learnings/erreurs + cocher to-do
```

Côté humain, ton rôle est de **donner les directions** (quelle sous-tâche, quels critères de succès) et de **valider les livrables** produits. Pas de saisie manuelle dans le BRAIN. Détails dans [BRAIN/bios.md](BRAIN/bios.md).

## État actuel (2026-04-30)

- ✅ **Cycle 0** complete (bootstrap repo + BRAIN system + conventions)
- ✅ **Cycle 1.1** complete : audit FULL D-008 sur 15 cat evergreen-occasion (348 M reviews + 26 M items, 60 GB parquet, ~9 min de polars streaming)
- ✅ **Pivot architectural acté** : ADR D-009 (RAG-grounded) + D-010 (PROJECT.md v2) + R19 grounded-avant-génératif
- ✅ **Repo restructuré** : 16 modules src/ par phase, 9 sous-dossiers reports/, 5 strates data/, src/config.py centralisé
- 🟡 **Prochaine sous-todo** : 1.2 cleaning + features + split (cf. `BRAIN/to-do.md`)

## Tests

```bash
pytest tests/ -v        # 32/32 doivent passer
ruff check src/ tests/  # Lint
ruff format src/ tests/ # Format
```

## Licence

MIT

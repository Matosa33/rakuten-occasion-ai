# Rakuten AI

Assistant IA pour vendeurs particuliers sur marketplace généraliste : génération automatique de fiches produit d'occasion (catégorie, attributs, titre, description, prix indicatif) à partir de photos.

Le cœur ML du projet est un **modèle multimodal vision-langage (VLM) fine-tuné** sur des données produits annotées, capable d'extraire un JSON structuré depuis une ou plusieurs photos.

## Démarrage rapide

```bash
git clone <url-du-repo> rakuten-ai
cd rakuten-ai

# 1. Créer le venv
python3.11 -m venv .venv
source .venv/bin/activate     # Linux/macOS/WSL
# ou .\.venv\Scripts\activate sur Windows pur

# 2. Installer
make install

# 3. Vérifier
pytest tests/ -v
```

## Structure du repo

```
rakuten-ai/
├── BRAIN/                          # Mémoire opérationnelle du projet (9 fichiers canoniques)
│   ├── bios.md                     # Point d'entrée, ordre de lecture
│   ├── state.md                    # Où on en est LÀ MAINTENANT
│   ├── context.md                  # QUOI + POURQUOI (figé)
│   ├── glossary.md                 # Lexique projet
│   ├── golden_rules.md             # R1-R16 + procédural brain
│   ├── erreur_a_ne_plus_faire.md   # Pièges connus (append-only)
│   ├── decisions.md                # ADR chronologique (append-only)
│   ├── learnings.md                # Découvertes positives (append-only)
│   ├── to-do.md                    # Cycles INIT/LECTURE/RUN/RESTIT
│   └── blocs/                      # Références techniques par domaine (à venir)
├── docs/
│   └── PROJECT.md                  # Cadrage projet (one-pager avec sources web)
├── src/                            # Code applicatif (à venir, phases P02+)
├── tests/                          # Tests pytest
├── pyproject.toml                  # Source unique de vérité : deps + config ruff + pytest
├── Makefile                        # Commandes standardisées
├── .pre-commit-config.yaml         # Hooks qualité au commit
└── .gitignore
```

## Documentation

- **Cadrage projet** (1 page, public) : [docs/PROJECT.md](docs/PROJECT.md)
- **Mémoire opérationnelle** (9 fichiers, équipe technique) : [BRAIN/bios.md](BRAIN/bios.md) en premier

## Stack technique cible

À enrichir au fil des phases. Pour l'instant : Python 3.11, structure prête à recevoir les composants ML.

| Couche | Composant prévu | Phase |
|--------|------------------|-------|
| Vision encoder (figé) | SigLIP SO400M FP16 | P03 |
| Text encoder | Snowflake Arctic Embed L v2 | P03 |
| Vector search | FAISS multi-view + RRF | P05 |
| **Cœur multimodal (fine-tuné)** | **Qwen2.5-VL-7B QLoRA + Unsloth** | **P06** |
| LLM génération | Gemini 2.0 Flash + RAG | P07 |
| Pricing | Algorithmique transparent | P08 |
| Backend API | FastAPI + SSE streaming | P10 |
| Frontend | React 19 + Vite + Tailwind | P11 |
| MLOps | MLflow Registry + DVC + Airflow + BentoML | P12-P13 |
| Infra | Docker + Compose + Traefik + K8s | P14 |
| Observabilité | Prometheus + Grafana + Evidently | P15 |
| CI/CD | GitHub Actions + GHCR | P16 |

## Méthodologie

Le projet suit le **protocole 4 phases** par sous-tâche :

```
INIT     → relire les 9 fichiers BRAIN dans l'ordre bios.md (~5 min)
LECTURE  → identifier les fichiers projet à lire pour la sous-tâche
RUN      → exécuter (code, tests, doc)
RESTIT   → update BRAIN/state.md + append decisions/learnings/erreurs + cocher to-do
```

Détails dans [BRAIN/bios.md](BRAIN/bios.md).

## Tests

```bash
make test           # 1 test smoke pour l'instant, s'enrichira phase par phase
```

## Licence

MIT

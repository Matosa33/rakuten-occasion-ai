"""Cycle 6.1 — Prompt templates LLM rédacteur grounded.

Templates Jinja2 pour le LLM rédacteur (E4) : génération titre annonce +
description en français pour vendeur particulier sur le périmètre 4 cat
D-011 (Electronics, Cell_Phones, Video_Games, Tools).

Tous les prompts suivent la structure :
  ROLE → INSTRUCTION → CONTEXT_GROUNDING → OUTPUT_FORMAT_JSON

Le **context_grounding** est la clé du RAG : on injecte les phrases
vendeur les plus utiles extraites des reviews du produit identifié
(retriever en Cycle 6.2). Le LLM ne doit PAS broder hors de ce
context_grounding (anti-hallucination).

Sortie : module **importable** (utilisé par `02_rag_grounded_writer.py`
et `src/api/`).
"""

from __future__ import annotations

from dataclasses import dataclass

# Templates en string ; on n'utilise pas Jinja2 pour rester sans dépendance
# externe (ces templates sont simples). Si on grossit, on bascule en Jinja.

PROMPT_TITLE_GENERATOR = """Tu es un rédacteur d'annonces pour vendeurs particuliers sur un site type Rakuten.

Tâche : rédige un **titre court** (max 80 caractères) pour mettre en vente l'objet suivant.

Fiche produit du catalogue (validée par retrieval) :
- Marque : {brand}
- Modèle : {title}
- Catégorie : {category}
- Caractéristiques observées : {observed_attrs_json}

État indiqué par le vendeur : {seller_condition}

Phrases tirées de vraies reviews acheteurs (à utiliser comme inspiration de ton/lexique) :
{grounding_sentences}

Contraintes :
- Français impeccable, ton vendeur particulier (pas marketing pro)
- Inclure marque + modèle + caractéristique distinctive si pertinente
- Si tu mentionnes l'état, utilise EXACTEMENT « {seller_condition} » — jamais un autre
- Pas d'émojis, pas de MAJUSCULES INTÉGRALES
- Pas d'invention de spécifications absentes du contexte ci-dessus

Réponds UNIQUEMENT en JSON strict :
{{"title": "<titre 80 chars max>"}}"""


PROMPT_DESCRIPTION_GENERATOR = """Tu es un rédacteur d'annonces pour vendeurs particuliers sur un site type Rakuten.

Tâche : rédige une **description de 5 à 10 phrases** pour mettre en vente l'objet suivant.

Fiche produit du catalogue (validée par retrieval) :
- Marque : {brand}
- Modèle : {title}
- Catégorie : {category}
- Caractéristiques observées : {observed_attrs_json}

État indiqué par le vendeur : {seller_condition}

Phrases tirées de vraies reviews acheteurs (à utiliser pour le ton et les arguments naturels) :
{grounding_sentences}

Contraintes :
- Français impeccable, ton vendeur particulier honnête
- Décrire d'abord l'objet (1-2 phrases), puis arguments d'achat (2-4 phrases inspirées des reviews), puis état réel (1-2 phrases)
- Pas d'invention de caractéristiques absentes du contexte
- Pas de superlatifs marketing ("incroyable", "exceptionnel")
- Format paragraphes (pas de bullets)

Réponds UNIQUEMENT en JSON strict :
{{"description": "<5 à 10 phrases>"}}"""


PROMPT_CATEGORY_SUGGESTER = """Tu es un classifieur de catégories Rakuten.

Catégorie L1 (déjà identifiée par notre pipeline) : {category_l1}

Fiche produit identifiée :
- Titre : {title}
- Marque : {brand}
- Caractéristiques : {observed_attrs_json}

Suggère la sous-catégorie L2 la plus appropriée pour cet objet sur Rakuten France.

Réponds UNIQUEMENT en JSON strict :
{{"l2_suggestion": "<nom L2>", "l3_suggestion": "<nom L3 ou null>", "confidence": 0.0..1.0}}"""


@dataclass
class PromptInputs:
    """Inputs canoniques pour les 3 prompts du Cycle 6."""

    brand: str = ""
    title: str = ""
    category: str = ""
    observed_attrs_json: str = "{}"
    grounding_sentences: str = ""  # multi-lignes "- phrase 1\n- phrase 2"
    seller_condition: str = "bon état"
    category_l1: str = ""

    def render_title(self) -> str:
        return PROMPT_TITLE_GENERATOR.format(
            brand=self.brand or "(marque inconnue)",
            title=self.title or "(modèle inconnu)",
            category=self.category or "(catégorie inconnue)",
            observed_attrs_json=self.observed_attrs_json,
            # 17.4b : le titre doit refléter l'état RÉEL choisi par le vendeur
            # (bug jugé par l'humain : « Très bon état » inventé vs « bon état » choisi).
            seller_condition=self.seller_condition,
            grounding_sentences=self.grounding_sentences or "(aucune review disponible)",
        )

    def render_description(self) -> str:
        return PROMPT_DESCRIPTION_GENERATOR.format(
            brand=self.brand or "(marque inconnue)",
            title=self.title or "(modèle inconnu)",
            category=self.category or "(catégorie inconnue)",
            observed_attrs_json=self.observed_attrs_json,
            seller_condition=self.seller_condition,
            grounding_sentences=self.grounding_sentences or "(aucune review disponible)",
        )

    def render_category(self) -> str:
        return PROMPT_CATEGORY_SUGGESTER.format(
            category_l1=self.category_l1 or self.category,
            title=self.title,
            brand=self.brand,
            observed_attrs_json=self.observed_attrs_json,
        )

"""Tests du rédacteur RAG grounded (Cycle 15.3, D-034 - modules aveugles audit 15.0).

Couvre la logique pure sans LLM réel ni artefact : MockLLMWriter (contrat D-013),
extract_useful_sentences (heuristique grounding), _extract_json_field (parse robuste
des réponses LLM), generate_listing E2E avec mock, et les templates de prompts.
"""

from __future__ import annotations

import importlib
import json

import polars as pl

_writer = importlib.import_module("src.llm.02_rag_grounded_writer")
_templates = importlib.import_module("src.llm.01_prompt_templates")


# ─────────────────────────────────────────────────────────────────────────────
# MockLLMWriter - le fallback D-013 quand OPENROUTER_API_KEY absente
# ─────────────────────────────────────────────────────────────────────────────


def test_mock_writer_repond_title_sur_prompt_title():
    """Prompt finissant par le schéma {"title"} → JSON avec champ title."""
    raw = _writer.MockLLMWriter().generate('Réponds en JSON strict : {"title": "<titre>"}')
    assert json.loads(raw)["title"]


def test_mock_writer_repond_description_sur_prompt_description():
    raw = _writer.MockLLMWriter().generate(
        'Réponds en JSON strict : {"description": "<description>"}'
    )
    assert json.loads(raw)["description"]


# ─────────────────────────────────────────────────────────────────────────────
# extract_useful_sentences - heuristique de grounding (pré-RAG embeddings)
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_sentences_filtre_les_courtes_et_deduplique():
    long_a = "Cette perceuse est vraiment excellente pour les travaux de précision domestiques"
    long_b = "La batterie tient une journée complète de chantier sans aucun souci de charge"
    reviews = pl.DataFrame(
        {
            "text": [
                f"{long_a}. Court. {long_b}.",
                f"{long_a}.",  # doublon (dedup lower attendu)
            ]
        }
    )
    sentences = _writer.extract_useful_sentences(reviews, top_n=5)
    assert long_a in sentences
    assert long_b in sentences
    assert sentences.count(long_a) == 1, "doublon non dédupliqué"
    assert all(len(s) >= _writer.MIN_SENTENCE_CHARS for s in sentences)


def test_extract_sentences_dataframe_vide_ou_sans_text():
    assert _writer.extract_useful_sentences(pl.DataFrame({"text": []})) == []
    assert _writer.extract_useful_sentences(pl.DataFrame({"autre": ["x"]})) == []


# ─────────────────────────────────────────────────────────────────────────────
# _extract_json_field - parse robuste des réponses LLM (markdown, prose, JSON pur)
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_json_field_json_pur():
    assert _writer._extract_json_field('{"title": "iPhone 13"}', "title") == "iPhone 13"


def test_extract_json_field_fence_markdown():
    raw = 'Voici :\n```json\n{"title": "RTX 4080"}\n```\nVoilà.'
    assert _writer._extract_json_field(raw, "title") == "RTX 4080"


def test_extract_json_field_noye_dans_prose():
    raw = 'Bien sûr ! {"description": "Très bon état"} - j\'espère que ça convient.'
    assert _writer._extract_json_field(raw, "description") == "Très bon état"


def test_extract_json_field_invalide_renvoie_none():
    assert _writer._extract_json_field("pas du json du tout", "title") is None
    assert _writer._extract_json_field('{"autre_champ": 1}', "title") is None


# ─────────────────────────────────────────────────────────────────────────────
# generate_listing E2E avec mock - le contrat consommé par DescribeService
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_listing_e2e_mock_parse_ok():
    meta = {
        "parent_asin": "B0TEST",
        "brand": "TestBrand",
        "title": "Produit Test 128GB",
        "_source_category": "Electronics",
    }
    reviews = pl.DataFrame(
        {"text": ["Ce produit est vraiment excellent pour un usage quotidien intensif."]}
    )
    listing = _writer.generate_listing(meta, reviews, _writer.MockLLMWriter())
    assert listing.parse_ok is True
    assert listing.product_id == "B0TEST"
    assert listing.title and listing.title != "(parse error)"
    assert listing.description and listing.description != "(parse error)"
    assert listing.n_reviews_available == 1


class _BrokenWriter(_writer.LLMWriter):
    """Writer qui renvoie du non-JSON → teste la dégradation parse_ok=False."""

    name = "broken"

    def generate(self, prompt: str) -> str:
        return "réponse libre sans aucun JSON"


def test_generate_listing_writer_casse_degrade_proprement():
    """Un LLM qui ne respecte pas le format ne doit PAS lever - parse_ok=False
    + placeholders (le caller décide quoi afficher)."""
    listing = _writer.generate_listing(
        {"parent_asin": "B1"}, pl.DataFrame({"text": []}), _BrokenWriter()
    )
    assert listing.parse_ok is False
    assert listing.title == "(parse error)"


# ─────────────────────────────────────────────────────────────────────────────
# Templates de prompts - les placeholders attendus par PromptInputs
# ─────────────────────────────────────────────────────────────────────────────


def test_templates_contiennent_les_placeholders_canoniques():
    """Si un placeholder est renommé d'un côté (template) sans l'autre
    (PromptInputs.render_*), le .format() lèvera KeyError au runtime - ce test
    le catch statiquement. 17.4b : {seller_condition} est exigé dans les DEUX
    prompts (bug jugé par l'humain : le titre inventait « Très bon état »
    alors que le vendeur avait choisi « bon état »)."""
    common = ("{brand}", "{title}", "{grounding_sentences}", "{seller_condition}")
    for placeholder in common:
        assert placeholder in _templates.PROMPT_TITLE_GENERATOR, (
            f"PROMPT_TITLE_GENERATOR : {placeholder} manquant"
        )
        assert placeholder in _templates.PROMPT_DESCRIPTION_GENERATOR, (
            f"PROMPT_DESCRIPTION_GENERATOR : {placeholder} manquant"
        )


def test_prompt_inputs_render_ne_leve_pas():
    """render_title/render_description doivent formatter sans KeyError avec
    des inputs vides (defaults)."""
    inputs = _templates.PromptInputs()
    assert isinstance(inputs.render_title(), str)
    assert isinstance(inputs.render_description(), str)

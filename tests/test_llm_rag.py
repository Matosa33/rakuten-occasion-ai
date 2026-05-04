"""Tests pour LLM rédacteur grounded (src/llm/01_prompt_templates.py + 02_rag_grounded_writer.py)."""

from __future__ import annotations

import importlib
import json

import polars as pl

_prompts = importlib.import_module("src.llm.01_prompt_templates")
_rag = importlib.import_module("src.llm.02_rag_grounded_writer")

PromptInputs = _prompts.PromptInputs
extract_useful_sentences = _rag.extract_useful_sentences
generate_listing = _rag.generate_listing
MockLLMWriter = _rag.MockLLMWriter


class TestPromptInputs:
    def test_render_title_includes_brand_and_model(self):
        inputs = PromptInputs(brand="Apple", title="iPhone 14", category="Cell_Phones")
        prompt = inputs.render_title()
        assert "Apple" in prompt
        assert "iPhone 14" in prompt
        assert '"title"' in prompt  # JSON format demandé

    def test_render_title_handles_missing_brand(self):
        inputs = PromptInputs(brand="", title="Mystery model")
        prompt = inputs.render_title()
        assert "marque inconnue" in prompt
        assert "Mystery model" in prompt

    def test_render_description_includes_grounding(self):
        inputs = PromptInputs(
            brand="Sony",
            title="WH-1000XM4",
            category="Electronics",
            grounding_sentences="- Excellent isolation phonique\n- Confortable",
        )
        prompt = inputs.render_description()
        assert "Excellent isolation phonique" in prompt
        assert "Confortable" in prompt

    def test_render_category_falls_back_to_category(self):
        inputs = PromptInputs(category="Electronics", title="T", brand="B")
        prompt = inputs.render_category()
        assert "Electronics" in prompt


class TestSentenceExtraction:
    def test_extract_filters_short_sentences(self):
        df = pl.DataFrame(
            {
                "text": [
                    "Court.",  # < MIN_SENTENCE_CHARS
                    "Cette phrase est suffisamment longue pour être conservée comme phrase utile pour le grounding.",
                ]
            }
        )
        sentences = extract_useful_sentences(df, top_n=5)
        assert len(sentences) == 1
        assert "suffisamment longue" in sentences[0]

    def test_extract_dedupes(self):
        df = pl.DataFrame(
            {
                "text": [
                    "Cette phrase est suffisamment longue pour être conservée comme phrase utile.",
                    "Cette phrase est suffisamment longue pour être conservée comme phrase utile.",
                ]
            }
        )
        sentences = extract_useful_sentences(df, top_n=5)
        assert len(sentences) == 1

    def test_extract_handles_empty_df(self):
        df = pl.DataFrame({"text": []}, schema={"text": pl.Utf8})
        assert extract_useful_sentences(df) == []

    def test_extract_handles_no_text_column(self):
        df = pl.DataFrame({"other": [1, 2, 3]})
        assert extract_useful_sentences(df) == []

    def test_extract_returns_top_n_longest(self):
        df = pl.DataFrame(
            {
                "text": [
                    "Phrase A " + "x" * 60 + ".",  # ~70 chars
                    "Phrase B " + "x" * 100 + ".",  # ~110 chars
                    "Phrase C " + "x" * 80 + ".",  # ~90 chars
                ]
            }
        )
        sentences = extract_useful_sentences(df, top_n=2)
        assert len(sentences) == 2
        assert "Phrase B" in sentences[0]  # le plus long en premier


class TestMockLLMWriter:
    def test_mock_returns_valid_json_for_title_prompt(self):
        writer = MockLLMWriter()
        out = writer.generate('Réponds UNIQUEMENT en JSON : {"title": "..."}')
        data = json.loads(out)
        assert "title" in data
        assert isinstance(data["title"], str)

    def test_mock_returns_valid_json_for_description_prompt(self):
        writer = MockLLMWriter()
        out = writer.generate('Réponds UNIQUEMENT en JSON : {"description": "..."}')
        data = json.loads(out)
        assert "description" in data
        assert len(data["description"]) > 50


class TestGenerateListing:
    def test_generate_listing_returns_parseable_outputs(self):
        product_meta = {
            "parent_asin": "B00ABCDEF1",
            "title": "iPhone 14 Pro",
            "brand": "Apple",
            "_source_category": "Cell_Phones_and_Accessories",
        }
        reviews_df = pl.DataFrame(
            {"text": ["Très bon téléphone, autonomie correcte sur une journée d'usage normal."]}
        )
        writer = MockLLMWriter()
        listing = generate_listing(product_meta, reviews_df, writer)
        assert listing.parse_ok
        assert listing.product_id == "B00ABCDEF1"
        assert len(listing.title) > 0
        assert len(listing.description) > 0

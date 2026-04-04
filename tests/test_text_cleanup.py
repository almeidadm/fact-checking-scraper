"""Tests for the TextCleanupPipeline (5.11)."""

from __future__ import annotations

from factcheck_scrape.text_cleanup import TextCleanupPipeline, clean_stored_text


class FakeSpider:
    name = "test_spider"


class TestCleanStoredText:
    def test_html_unescape(self):
        assert clean_stored_text("caf&eacute; &amp; bar") == "café & bar"

    def test_mojibake_fix(self):
        mojibake = "informa" + "ção".encode("utf-8").decode("latin-1")
        assert clean_stored_text(mojibake) == "informação"

    def test_nfkc_normalization(self):
        assert clean_stored_text("\ufb01nance") == "finance"

    def test_whitespace_collapse(self):
        assert clean_stored_text("  hello   world  ") == "hello world"

    def test_nbsp_replaced(self):
        assert clean_stored_text("hello\xa0world") == "hello world"

    def test_none_returns_none(self):
        assert clean_stored_text(None) is None

    def test_empty_returns_none(self):
        assert clean_stored_text("   ") is None

    def test_preserves_normal_text(self):
        assert clean_stored_text("Texto normal em português") == "Texto normal em português"


class TestTextCleanupPipeline:
    def test_cleans_text_fields(self):
        pipeline = TextCleanupPipeline()
        spider = FakeSpider()
        item = {
            "title": "Teste &amp; Verifica\u00e7\u00e3o",
            "claim": "  multiple   spaces  ",
            "summary": None,
            "source_url": "https://example.com",
        }
        result = pipeline.process_item(item, spider)
        assert result["title"] == "Teste & Verificação"
        assert result["claim"] == "multiple spaces"
        assert result["summary"] is None
        assert result["source_url"] == "https://example.com"

    def test_cleans_list_fields(self):
        pipeline = TextCleanupPipeline()
        spider = FakeSpider()
        item = {
            "topics": ["pol&iacute;tica", "  sa\u00fade  ", None, ""],
            "tags": ["tag1", "  tag2  "],
            "entities": [],
        }
        result = pipeline.process_item(item, spider)
        assert result["topics"] == ["política", "saúde"]
        assert result["tags"] == ["tag1", "tag2"]
        assert result["entities"] == []

    def test_pipeline_passes_through_non_text_fields(self):
        pipeline = TextCleanupPipeline()
        spider = FakeSpider()
        item = {
            "item_id": "abc123",
            "source_url": "https://example.com/article",
            "title": "Normal title",
        }
        result = pipeline.process_item(item, spider)
        assert result["item_id"] == "abc123"
        assert result["source_url"] == "https://example.com/article"

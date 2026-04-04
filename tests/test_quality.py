"""Tests for quality metrics (5.13)."""

from __future__ import annotations

import json
from pathlib import Path

from factcheck_scrape.quality import (
    SpiderQuality,
    analyze_items,
    analyze_run,
    format_quality_text,
)


def _make_item(spider: str, **overrides) -> dict:
    base = {
        "spider": spider,
        "title": "Test",
        "source_url": "https://example.com",
        "canonical_url": "https://example.com",
        "published_at": "2026-04-01",
        "collected_at": "2026-04-01",
    }
    base.update(overrides)
    return base


class TestAnalyzeItems:
    def test_groups_by_spider(self):
        items = [
            _make_item("spider_a"),
            _make_item("spider_b"),
            _make_item("spider_a"),
        ]
        result = analyze_items(items)
        assert result["spider_a"].total_items == 2
        assert result["spider_b"].total_items == 1

    def test_counts_optional_fill(self):
        items = [
            _make_item("s1", verdict="Falso", claim="some claim"),
            _make_item("s1", verdict=None, claim="another claim"),
            _make_item("s1", verdict="Verdadeiro", claim=None),
        ]
        result = analyze_items(items)
        sq = result["s1"]
        assert sq.optional_fill.get("verdict", 0) == 2
        assert sq.optional_fill.get("claim", 0) == 2

    def test_verdict_fill_rate(self):
        items = [
            _make_item("s1", verdict="Falso"),
            _make_item("s1", verdict=None),
            _make_item("s1", verdict=""),
            _make_item("s1", verdict="Verdadeiro"),
        ]
        result = analyze_items(items)
        sq = result["s1"]
        assert sq.verdict_filled_count == 2
        assert sq.verdict_null_count == 2
        assert sq.verdict_fill_rate == 0.5

    def test_average_lengths(self):
        items = [
            _make_item("s1", summary="12345", claim="1234567890", body="12345678901234567890"),
            _make_item("s1", summary="123456789012345", claim=None, body=None),
        ]
        result = analyze_items(items)
        sq = result["s1"]
        assert sq.avg_summary_length == 10.0  # (5 + 15) / 2
        assert sq.avg_claim_length == 10.0  # only one item
        assert sq.avg_body_length == 20.0  # only one item

    def test_empty_items(self):
        result = analyze_items([])
        assert result == {}


class TestSpiderQuality:
    def test_optional_fill_rates_with_zero_items(self):
        sq = SpiderQuality(spider="test")
        assert sq.optional_fill_rates == {}
        assert sq.verdict_fill_rate == 0.0
        assert sq.avg_summary_length == 0.0

    def test_to_dict(self):
        sq = SpiderQuality(spider="test", total_items=10, verdict_filled_count=8)
        d = sq.to_dict()
        assert d["spider"] == "test"
        assert d["total_items"] == 10
        assert d["verdict_fill_rate"] == 0.8


class TestAnalyzeRun:
    def test_reads_items_from_jsonl(self, tmp_path):
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        items_path = run_dir / "items.jsonl"
        items = [
            _make_item("spider_a", verdict="Falso", summary="Short summary"),
            _make_item("spider_a", verdict=None, summary="Another one here"),
            _make_item("spider_b", verdict="Verdadeiro"),
        ]
        items_path.write_text(
            "\n".join(json.dumps(item) for item in items) + "\n",
            encoding="utf-8",
        )
        result = analyze_run(run_dir)
        assert "spider_a" in result
        assert "spider_b" in result
        assert result["spider_a"].total_items == 2
        assert result["spider_b"].total_items == 1

    def test_missing_items_file(self, tmp_path):
        result = analyze_run(tmp_path / "nonexistent")
        assert result == {}


class TestFormatQualityText:
    def test_empty_quality(self):
        assert format_quality_text({}) == "No items to analyze."

    def test_formats_table(self):
        items = [
            _make_item("test_spider", verdict="Falso", summary="A short summary"),
        ]
        quality = analyze_items(items)
        text = format_quality_text(quality)
        assert "test_spider" in text
        assert "Verdict" in text
        assert "Optional field fill rates" in text

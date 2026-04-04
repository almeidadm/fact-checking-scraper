"""End-to-end integration tests for the scraping pipeline.

Tests the full flow: Spider -> Pipeline -> Storage -> Dedupe,
using a minimal in-process spider with fake responses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factcheck_scrape.dedupe import DedupeStore
from factcheck_scrape.pipelines import FactCheckPipeline
from factcheck_scrape.storage import RunCounts, RunWriter
from factcheck_scrape.utils import make_item_id


class FakeSpider:
    name = "test_spider"
    agency_id = "test_agency"
    agency_name = "Test Agency"


def _make_item(url: str, title: str, published_at: str = "2026-04-01T10:00:00+00:00") -> dict:
    return {
        "source_url": url,
        "canonical_url": url,
        "title": title,
        "published_at": published_at,
        "item_id": make_item_id("test_agency", url),
        "agency_id": "test_agency",
        "agency_name": "Test Agency",
        "spider": "test_spider",
        "collected_at": "2026-04-01T10:00:01+00:00",
        "run_id": "test-run",
    }


# ---------------------------------------------------------------------------
# Pipeline + Storage integration
# ---------------------------------------------------------------------------

class TestPipelineStorageIntegration:
    def test_pipeline_writes_valid_item_to_storage(self, tmp_path):
        pipeline = FactCheckPipeline(str(tmp_path), "test-run-1")
        spider = FakeSpider()
        pipeline.open_spider(spider)

        item = _make_item("https://example.com/article-1", "Article One")
        result = pipeline.process_item(item, spider)

        pipeline.close_spider(spider)

        assert result["title"] == "Article One"
        assert pipeline.counts.items_stored == 1
        assert pipeline.counts.items_seen == 1

        items_path = tmp_path / "runs" / "test-run-1" / "items.jsonl"
        assert items_path.exists()
        stored = json.loads(items_path.read_text(encoding="utf-8").strip())
        assert stored["title"] == "Article One"

    def test_pipeline_deduplicates_same_url(self, tmp_path):
        pipeline = FactCheckPipeline(str(tmp_path), "test-run-2")
        spider = FakeSpider()
        pipeline.open_spider(spider)

        item1 = _make_item("https://example.com/dup", "Duplicate Article")
        item2 = _make_item("https://example.com/dup", "Duplicate Article Copy")

        pipeline.process_item(item1, spider)
        with pytest.raises(Exception, match="Duplicate"):
            pipeline.process_item(item2, spider)

        pipeline.close_spider(spider)

        assert pipeline.counts.items_stored == 1
        assert pipeline.counts.items_deduped == 1

    def test_pipeline_rejects_invalid_item(self, tmp_path):
        pipeline = FactCheckPipeline(str(tmp_path), "test-run-3")
        spider = FakeSpider()
        pipeline.open_spider(spider)

        item = _make_item("https://example.com/invalid", "")
        item["title"] = ""

        with pytest.raises(Exception):
            pipeline.process_item(item, spider)

        pipeline.close_spider(spider)

        assert pipeline.counts.items_invalid == 1
        assert pipeline.counts.items_stored == 0

    def test_pipeline_generates_consistent_run_json(self, tmp_path):
        pipeline = FactCheckPipeline(str(tmp_path), "test-run-4")
        spider = FakeSpider()
        pipeline.open_spider(spider)

        for i in range(5):
            item = _make_item(f"https://example.com/art-{i}", f"Article {i}")
            pipeline.process_item(item, spider)

        pipeline.close_spider(spider)

        run_path = tmp_path / "runs" / "test-run-4" / "run.json"
        assert run_path.exists()

        run_data = json.loads(run_path.read_text(encoding="utf-8"))
        assert run_data["run_id"] == "test-run-4"
        assert run_data["totals"]["items_stored"] == 5
        assert run_data["totals"]["items_seen"] == 5
        assert "test_spider" in run_data["spiders"]
        assert run_data["spiders"]["test_spider"]["items_stored"] == 5

        items_path = tmp_path / "runs" / "test-run-4" / "items.jsonl"
        items_lines = [l for l in items_path.read_text(encoding="utf-8").strip().split("\n") if l]
        assert len(items_lines) == 5


# ---------------------------------------------------------------------------
# Dedupe persistence across runs
# ---------------------------------------------------------------------------

class TestDedupeAcrossRuns:
    def test_dedupe_persists_between_pipeline_runs(self, tmp_path):
        spider = FakeSpider()

        # Run 1: store an item
        p1 = FactCheckPipeline(str(tmp_path), "run-1")
        p1.open_spider(spider)
        item1 = _make_item("https://example.com/persisted", "Persisted Article")
        p1.process_item(item1, spider)
        p1.close_spider(spider)

        assert p1.counts.items_stored == 1

        # Run 2: same item should be deduped
        p2 = FactCheckPipeline(str(tmp_path), "run-2")
        p2.open_spider(spider)
        item2 = _make_item("https://example.com/persisted", "Persisted Article Again")
        with pytest.raises(Exception, match="Duplicate"):
            p2.process_item(item2, spider)
        p2.close_spider(spider)

        assert p2.counts.items_deduped == 1
        assert p2.counts.items_stored == 0

    def test_dedupe_ignore_existing_allows_recollection(self, tmp_path):
        spider = FakeSpider()

        # Run 1: store an item
        p1 = FactCheckPipeline(str(tmp_path), "run-1", ignore_existing_seen_state=False)
        p1.open_spider(spider)
        item1 = _make_item("https://example.com/recollect", "Recollectable")
        p1.process_item(item1, spider)
        p1.close_spider(spider)

        # Run 2: ignore existing, should allow re-storage
        p2 = FactCheckPipeline(str(tmp_path), "run-2", ignore_existing_seen_state=True)
        p2.open_spider(spider)
        item2 = _make_item("https://example.com/recollect", "Recollectable Again")
        result = p2.process_item(item2, spider)
        p2.close_spider(spider)

        assert p2.counts.items_stored == 1
        assert result["title"] == "Recollectable Again"

    def test_dedupe_sqlite_survives_close_and_reopen(self, tmp_path):
        store1 = DedupeStore(tmp_path, "agency_x")
        store1.mark_seen("https://example.com/sqlite-test", "https://example.com/sqlite-test")
        store1.close()

        store2 = DedupeStore(tmp_path, "agency_x")
        assert store2.is_seen("https://example.com/sqlite-test") is True

        assert store2.is_seen("https://example.com/unseen") is False
        store2.close()


# ---------------------------------------------------------------------------
# RunWriter consistency
# ---------------------------------------------------------------------------

class TestRunWriterConsistency:
    def test_multiple_spiders_in_same_run(self, tmp_path):
        writer = RunWriter(tmp_path, "multi-spider-run")

        writer.write_item({"spider": "spider_a", "data": "a"})
        writer.write_item({"spider": "spider_b", "data": "b"})
        writer.close()

        writer.update_run(
            spider_name="spider_a",
            agency_id="agency_a",
            agency_name="Agency A",
            counts=RunCounts(items_seen=10, items_stored=8, items_deduped=2, items_invalid=0),
            spider_started_at="2026-04-01T10:00:00+00:00",
            spider_finished_at="2026-04-01T10:05:00+00:00",
        )

        writer.update_run(
            spider_name="spider_b",
            agency_id="agency_b",
            agency_name="Agency B",
            counts=RunCounts(items_seen=20, items_stored=15, items_deduped=3, items_invalid=2),
            spider_started_at="2026-04-01T10:05:00+00:00",
            spider_finished_at="2026-04-01T10:10:00+00:00",
        )

        run_path = tmp_path / "runs" / "multi-spider-run" / "run.json"
        payload = json.loads(run_path.read_text(encoding="utf-8"))

        assert len(payload["spiders"]) == 2
        assert payload["totals"]["items_seen"] == 30
        assert payload["totals"]["items_stored"] == 23
        assert payload["totals"]["items_deduped"] == 5
        assert payload["totals"]["items_invalid"] == 2
        assert payload["started_at"] == "2026-04-01T10:00:00+00:00"
        assert payload["finished_at"] == "2026-04-01T10:10:00+00:00"

    def test_items_jsonl_count_matches_stored_count(self, tmp_path):
        writer = RunWriter(tmp_path, "count-check")
        for i in range(7):
            writer.write_item({"index": i})
        writer.close()
        writer.update_run(
            spider_name="test",
            agency_id="test",
            agency_name="Test",
            counts=RunCounts(items_seen=10, items_stored=7, items_deduped=3, items_invalid=0),
            spider_started_at="2026-04-01T10:00:00+00:00",
            spider_finished_at="2026-04-01T10:05:00+00:00",
        )

        items_path = tmp_path / "runs" / "count-check" / "items.jsonl"
        run_path = tmp_path / "runs" / "count-check" / "run.json"

        items_count = len([l for l in items_path.read_text(encoding="utf-8").strip().split("\n") if l])
        run_data = json.loads(run_path.read_text(encoding="utf-8"))

        assert items_count == run_data["totals"]["items_stored"]

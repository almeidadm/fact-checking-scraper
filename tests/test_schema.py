from __future__ import annotations

import pytest

from factcheck_scrape.schema import validate_item


def _valid_item(**overrides) -> dict:
    item = {
        "item_id": "example-item",
        "agency_id": "example_agency",
        "agency_name": "Example Agency",
        "spider": "example_spider",
        "source_url": "https://example.com/article",
        "canonical_url": "https://example.com/article",
        "title": "Example article title",
        "published_at": "2026-03-17T10:00:00+00:00",
        "collected_at": "2026-03-17T10:05:00+00:00",
        "run_id": "test-run",
        "claim": None,
        "summary": None,
        "verdict": None,
        "rating": None,
        "author": None,
        "body": None,
        "language": "pt-BR",
        "country": "BR",
        "topics": [],
        "tags": [],
        "entities": [],
        "source_type": "ClaimReview",
    }
    item.update(overrides)
    return item


def test_validate_item_rejects_title_matching_source_url():
    with pytest.raises(ValueError, match="Invalid title: matches item URL"):
        validate_item(_valid_item(title="https://example.com/article"))


def test_validate_item_rejects_placeholder_published_at():
    with pytest.raises(ValueError, match="Invalid published_at: placeholder value"):
        validate_item(_valid_item(published_at="-"))

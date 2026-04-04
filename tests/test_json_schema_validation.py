"""Tests for JSON Schema validation (5.12)."""

from __future__ import annotations

import pytest

from factcheck_scrape.schema import (
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    generate_json_schema,
    validate_item,
)
from factcheck_scrape.utils import make_item_id


def _valid_item(**overrides) -> dict:
    url = overrides.pop("source_url", "https://example.com/article")
    base = {
        "item_id": make_item_id("test_agency", url),
        "agency_id": "test_agency",
        "agency_name": "Test Agency",
        "spider": "test_spider",
        "source_url": url,
        "canonical_url": url,
        "title": "Test Title",
        "published_at": "2026-04-01T10:00:00+00:00",
        "collected_at": "2026-04-01T10:00:01+00:00",
        "run_id": "test-run",
    }
    base.update(overrides)
    return base


class TestJsonSchemaValidation:
    def test_valid_item_passes(self):
        validate_item(_valid_item())

    def test_missing_required_field_raises(self):
        item = _valid_item()
        del item["title"]
        with pytest.raises(ValueError):
            validate_item(item)

    def test_unexpected_field_raises(self):
        item = _valid_item(unknown_field="oops")
        with pytest.raises(ValueError):
            validate_item(item)

    def test_empty_required_field_raises(self):
        item = _valid_item(title="")
        with pytest.raises(ValueError):
            validate_item(item)

    def test_optional_fields_nullable(self):
        item = _valid_item(claim=None, summary=None, verdict=None)
        validate_item(item)

    def test_list_fields_accept_arrays(self):
        item = _valid_item(topics=["topic1"], tags=["tag1"], entities=["entity1"])
        validate_item(item)

    def test_list_field_rejects_non_array(self):
        item = _valid_item(topics="not a list")
        with pytest.raises(ValueError):
            validate_item(item)


class TestGenerateJsonSchema:
    def test_schema_has_all_required_fields(self):
        schema = generate_json_schema()
        assert set(schema["required"]) == REQUIRED_FIELDS

    def test_schema_has_all_properties(self):
        schema = generate_json_schema()
        all_fields = REQUIRED_FIELDS | OPTIONAL_FIELDS
        assert set(schema["properties"].keys()) == all_fields

    def test_schema_disallows_additional_properties(self):
        schema = generate_json_schema()
        assert schema["additionalProperties"] is False

    def test_optional_string_fields_are_nullable(self):
        schema = generate_json_schema()
        nullable_fields = {"claim", "summary", "verdict", "rating", "author",
                          "body", "language", "country", "source_type"}
        for field in nullable_fields:
            assert schema["properties"][field]["type"] == ["string", "null"], (
                f"{field} should be nullable"
            )

    def test_list_fields_are_arrays(self):
        schema = generate_json_schema()
        for field in ("topics", "tags", "entities"):
            assert schema["properties"][field]["type"] == "array", (
                f"{field} should be array"
            )

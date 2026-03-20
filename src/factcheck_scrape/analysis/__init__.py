from __future__ import annotations

from datetime import UTC, datetime

from .processing import (
    PROCESSED_RECORD_FIELDS,
    build_processed_record,
    build_processed_snapshot,
    clean_text,
    clean_text_list,
    compose_analysis_text,
    export_processed_spider,
    load_spacy_model,
    normalize_published_at,
    normalize_standard_label,
    process_spider_items,
    should_drop_item,
    validate_processed_record,
)
from .profiles import SPIDER_ORDER, SpiderProfile, get_spider_profile
from .runs import (
    RunSelection,
    SpiderRunRecord,
    build_manifest,
    iter_spider_runs,
    load_items_for_run,
    runs_by_spider,
    select_run_for_spider,
    select_runs_for_spiders,
    write_manifest,
)

__all__ = [
    "PROCESSED_RECORD_FIELDS",
    "RunSelection",
    "SPIDER_ORDER",
    "SpiderProfile",
    "SpiderRunRecord",
    "build_manifest",
    "build_processed_record",
    "build_processed_snapshot",
    "clean_text",
    "clean_text_list",
    "compose_analysis_text",
    "default_snapshot_id",
    "export_processed_spider",
    "get_spider_profile",
    "iter_spider_runs",
    "load_items_for_run",
    "load_spacy_model",
    "normalize_published_at",
    "normalize_standard_label",
    "process_spider_items",
    "runs_by_spider",
    "select_run_for_spider",
    "select_runs_for_spiders",
    "should_drop_item",
    "validate_processed_record",
    "write_manifest",
]


def default_snapshot_id(prefix: str = "processed") -> str:
    """Generate a deterministic-looking UTC snapshot id for processed exports."""

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{prefix}"

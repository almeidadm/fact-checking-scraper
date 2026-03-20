from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profiles import SPIDER_ORDER, SpiderProfile, get_spider_profile


@dataclass(frozen=True, slots=True)
class SpiderRunRecord:
    """Run metadata for a single spider inside a run directory."""

    run_id: str
    spider: str
    agency_id: str | None
    agency_name: str | None
    run_started_at: str | None
    run_finished_at: str | None
    spider_started_at: str | None
    spider_finished_at: str | None
    items_seen: int
    items_stored: int
    items_deduped: int
    items_invalid: int
    run_path: Path
    items_path: Path

    @property
    def has_items_file(self) -> bool:
        return self.items_path.exists() and self.items_path.stat().st_size > 0

    @property
    def is_valid(self) -> bool:
        return self.items_stored > 0 and self.has_items_file

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "spider": self.spider,
            "agency_id": self.agency_id,
            "agency_name": self.agency_name,
            "run_started_at": self.run_started_at,
            "run_finished_at": self.run_finished_at,
            "spider_started_at": self.spider_started_at,
            "spider_finished_at": self.spider_finished_at,
            "items_seen": self.items_seen,
            "items_stored": self.items_stored,
            "items_deduped": self.items_deduped,
            "items_invalid": self.items_invalid,
            "has_items_file": self.has_items_file,
            "is_valid": self.is_valid,
        }


@dataclass(frozen=True, slots=True)
class RunSelection:
    """Selected and reference runs for a spider-level analysis export."""

    spider: str
    profile: SpiderProfile
    latest_run: SpiderRunRecord
    selected_run: SpiderRunRecord
    latest_valid_run: SpiderRunRecord | None
    fallback_applied: bool
    selection_reason: str

    @property
    def agency_id(self) -> str | None:
        return self.selected_run.agency_id

    @property
    def agency_name(self) -> str | None:
        return self.selected_run.agency_name

    @property
    def latest_run_id(self) -> str:
        return self.latest_run.run_id

    @property
    def latest_valid_run_id(self) -> str | None:
        return self.latest_valid_run.run_id if self.latest_valid_run else None

    @property
    def selected_run_id(self) -> str:
        return self.selected_run.run_id

    @property
    def diagnostic_run_ids(self) -> tuple[str, ...]:
        return self.profile.diagnostic_run_ids

    @property
    def cleaning_flags(self) -> tuple[str, ...]:
        flags = list(self.profile.cleaning_flags)
        if self.fallback_applied and "fallback_to_latest_valid_run" not in flags:
            flags.append("fallback_to_latest_valid_run")
        return tuple(flags)

    def to_manifest_entry(self, exported_records: int = 0) -> dict[str, Any]:
        return {
            "selected_run_id": self.selected_run_id,
            "latest_run_id": self.latest_run_id,
            "latest_valid_run_id": self.latest_valid_run_id,
            "fallback_applied": self.fallback_applied,
            "selection_reason": self.selection_reason,
            "exported_records": exported_records,
            "cleaning_flags": list(self.cleaning_flags),
            "diagnostic_run_ids": list(self.diagnostic_run_ids),
            "agency_id": self.agency_id,
            "agency_name": self.agency_name,
        }


def iter_spider_runs(data_dir: str | Path) -> list[SpiderRunRecord]:
    """Load all spider runs from `data/runs/*/run.json`, ignoring invalid entries."""

    runs_dir = Path(data_dir) / "runs"
    records: list[SpiderRunRecord] = []
    if not runs_dir.exists():
        return records

    for run_path in sorted(runs_dir.glob("*/run.json")):
        payload = _load_run_payload(run_path)
        if not payload:
            continue
        run_id = payload.get("run_id") or run_path.parent.name
        spiders = payload.get("spiders") or {}
        items_path = run_path.parent / "items.jsonl"
        for spider, info in spiders.items():
            records.append(
                SpiderRunRecord(
                    run_id=run_id,
                    spider=spider,
                    agency_id=info.get("agency_id"),
                    agency_name=info.get("agency_name"),
                    run_started_at=payload.get("started_at"),
                    run_finished_at=payload.get("finished_at"),
                    spider_started_at=info.get("started_at"),
                    spider_finished_at=info.get("finished_at"),
                    items_seen=int(info.get("items_seen", 0) or 0),
                    items_stored=int(info.get("items_stored", 0) or 0),
                    items_deduped=int(info.get("items_deduped", 0) or 0),
                    items_invalid=int(info.get("items_invalid", 0) or 0),
                    run_path=run_path,
                    items_path=items_path,
                )
            )
    return records


def runs_by_spider(data_dir: str | Path) -> dict[str, list[SpiderRunRecord]]:
    """Group run metadata by spider, ordered chronologically by run id."""

    grouped: dict[str, list[SpiderRunRecord]] = {}
    for record in iter_spider_runs(data_dir):
        grouped.setdefault(record.spider, []).append(record)
    for spider_records in grouped.values():
        spider_records.sort(key=lambda record: record.run_id)
    return grouped


def select_run_for_spider(
    data_dir: str | Path,
    spider: str,
    profile: SpiderProfile | None = None,
) -> RunSelection:
    """Select the latest valid run for a spider, with fallback when needed."""

    profile = profile or get_spider_profile(spider)
    spider_runs = runs_by_spider(data_dir).get(spider, [])
    if not spider_runs:
        raise ValueError(f"No run metadata found for spider '{spider}'")

    latest_run = spider_runs[-1]
    latest_valid_run = next((record for record in reversed(spider_runs) if record.is_valid), None)

    if latest_run.is_valid:
        selected_run = latest_run
        fallback_applied = False
        selection_reason = "latest_valid_run"
    elif latest_valid_run is not None:
        selected_run = latest_valid_run
        fallback_applied = True
        selection_reason = "fallback_to_latest_valid_run"
    else:
        selected_run = latest_run
        fallback_applied = False
        selection_reason = "latest_run_without_valid_items"

    return RunSelection(
        spider=spider,
        profile=profile,
        latest_run=latest_run,
        selected_run=selected_run,
        latest_valid_run=latest_valid_run,
        fallback_applied=fallback_applied,
        selection_reason=selection_reason,
    )


def select_runs_for_spiders(
    data_dir: str | Path,
    spiders: tuple[str, ...] | list[str] | None = None,
) -> dict[str, RunSelection]:
    """Select analysis runs for the configured spider order."""

    available = runs_by_spider(data_dir)
    if spiders is None:
        ordered_spiders = [spider for spider in SPIDER_ORDER if spider in available]
        extras = [spider for spider in sorted(available) if spider not in SPIDER_ORDER]
        spiders = ordered_spiders + extras

    return {spider: select_run_for_spider(data_dir, spider) for spider in spiders}


def load_items_for_run(
    data_dir: str | Path,
    run_id: str,
    spider: str | None = None,
) -> list[dict[str, Any]]:
    """Load items for a run, optionally filtered to a single spider."""

    items_path = Path(data_dir) / "runs" / run_id / "items.jsonl"
    if not items_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with items_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if spider and payload.get("spider") != spider:
                continue
            rows.append(payload)
    return rows


def build_manifest(
    snapshot_id: str,
    selections: dict[str, RunSelection],
    export_counts: dict[str, int],
    combined_count: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Build the processed snapshot manifest structure."""

    return {
        "snapshot_id": snapshot_id,
        "output_dir": str(output_dir),
        "combined_export_path": str(output_dir / "factcheck_scrape_unified.jsonl"),
        "combined_export_count": combined_count,
        "spiders": {
            spider: selection.to_manifest_entry(exported_records=export_counts.get(spider, 0))
            for spider, selection in selections.items()
        },
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Persist the manifest as JSON."""

    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_run_payload(run_path: Path) -> dict[str, Any]:
    try:
        return json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

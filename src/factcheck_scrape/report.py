from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class SpiderReport:
    spider: str
    agency_id: str
    agency_name: str
    items_seen: int = 0
    items_stored: int = 0
    items_deduped: int = 0
    items_invalid: int = 0
    started_at: str = ""
    finished_at: str = ""

    @property
    def store_rate(self) -> float:
        if self.items_seen == 0:
            return 0.0
        return self.items_stored / self.items_seen

    @property
    def has_zero_items(self) -> bool:
        return self.items_stored == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spider": self.spider,
            "agency_id": self.agency_id,
            "agency_name": self.agency_name,
            "items_seen": self.items_seen,
            "items_stored": self.items_stored,
            "items_deduped": self.items_deduped,
            "items_invalid": self.items_invalid,
            "store_rate": round(self.store_rate, 4),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class RunReport:
    run_id: str
    started_at: str
    finished_at: str
    spiders: List[SpiderReport] = field(default_factory=list)
    totals: Dict[str, int] = field(default_factory=dict)

    @property
    def alerts(self) -> List[str]:
        alerts = []
        for spider in self.spiders:
            if spider.has_zero_items:
                alerts.append(
                    f"{spider.spider}: 0 items stored"
                    f" (seen={spider.items_seen}, invalid={spider.items_invalid})"
                )
        return alerts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "spiders": [s.to_dict() for s in self.spiders],
            "totals": self.totals,
            "alerts": self.alerts,
        }


def load_run_report(run_path: Path) -> RunReport | None:
    if not run_path.exists():
        return None
    try:
        payload = json.loads(run_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    spiders = []
    for name, data in payload.get("spiders", {}).items():
        spiders.append(
            SpiderReport(
                spider=name,
                agency_id=data.get("agency_id", name),
                agency_name=data.get("agency_name", name),
                items_seen=data.get("items_seen", 0),
                items_stored=data.get("items_stored", 0),
                items_deduped=data.get("items_deduped", 0),
                items_invalid=data.get("items_invalid", 0),
                started_at=data.get("started_at", ""),
                finished_at=data.get("finished_at", ""),
            )
        )

    return RunReport(
        run_id=payload.get("run_id", ""),
        started_at=payload.get("started_at", ""),
        finished_at=payload.get("finished_at", ""),
        spiders=spiders,
        totals=payload.get("totals", {}),
    )


def find_latest_runs(data_dir: Path, count: int = 1) -> List[Path]:
    runs_dir = data_dir / "runs"
    if not runs_dir.exists():
        return []
    run_dirs = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )
    results = []
    for d in run_dirs[:count]:
        run_path = d / "run.json"
        if run_path.exists():
            results.append(run_path)
    return results


def generate_report(data_dir: Path, count: int = 1) -> List[RunReport]:
    reports = []
    for run_path in find_latest_runs(data_dir, count):
        report = load_run_report(run_path)
        if report:
            reports.append(report)
    return reports


def format_report_text(reports: List[RunReport]) -> str:
    if not reports:
        return "No runs found."

    lines: list[str] = []
    for report in reports:
        lines.append(f"Run: {report.run_id}")
        lines.append(f"  Period: {report.started_at} -> {report.finished_at}")
        total_stored = report.totals.get("items_stored", 0)
        total_seen = report.totals.get("items_seen", 0)
        lines.append(f"  Total: {total_stored} stored / {total_seen} seen")
        lines.append("")

        header = f"  {'Spider':<25} {'Stored':>8} {'Seen':>8} {'Deduped':>8} {'Invalid':>8} {'Rate':>7}"
        lines.append(header)
        lines.append(f"  {'-' * 72}")

        for spider in sorted(report.spiders, key=lambda s: s.spider):
            rate_str = f"{spider.store_rate:.0%}"
            marker = " (!)" if spider.has_zero_items else ""
            lines.append(
                f"  {spider.spider:<25} {spider.items_stored:>8} {spider.items_seen:>8}"
                f" {spider.items_deduped:>8} {spider.items_invalid:>8} {rate_str:>7}{marker}"
            )

        if report.alerts:
            lines.append("")
            lines.append("  Alerts:")
            for alert in report.alerts:
                lines.append(f"    - {alert}")

        lines.append("")

    return "\n".join(lines)

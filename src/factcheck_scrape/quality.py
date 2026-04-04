"""Quality metrics per spider — analyzes items from a run's items.jsonl."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .schema import OPTIONAL_FIELDS


QUALITY_TEXT_FIELDS = {"claim", "summary", "body", "verdict", "author"}


@dataclass
class SpiderQuality:
    spider: str
    total_items: int = 0
    optional_fill: Dict[str, int] = field(default_factory=dict)
    verdict_null_count: int = 0
    verdict_filled_count: int = 0
    summary_lengths: List[int] = field(default_factory=list)
    claim_lengths: List[int] = field(default_factory=list)
    body_lengths: List[int] = field(default_factory=list)

    @property
    def optional_fill_rates(self) -> Dict[str, float]:
        if self.total_items == 0:
            return {}
        return {
            k: round(v / self.total_items, 4)
            for k, v in sorted(self.optional_fill.items())
        }

    @property
    def verdict_fill_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return round(self.verdict_filled_count / self.total_items, 4)

    @property
    def avg_summary_length(self) -> float:
        return round(sum(self.summary_lengths) / len(self.summary_lengths), 1) if self.summary_lengths else 0.0

    @property
    def avg_claim_length(self) -> float:
        return round(sum(self.claim_lengths) / len(self.claim_lengths), 1) if self.claim_lengths else 0.0

    @property
    def avg_body_length(self) -> float:
        return round(sum(self.body_lengths) / len(self.body_lengths), 1) if self.body_lengths else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spider": self.spider,
            "total_items": self.total_items,
            "optional_fill_rates": self.optional_fill_rates,
            "verdict_fill_rate": self.verdict_fill_rate,
            "avg_summary_length": self.avg_summary_length,
            "avg_claim_length": self.avg_claim_length,
            "avg_body_length": self.avg_body_length,
        }


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    return True


def analyze_items(items: list[dict[str, Any]]) -> Dict[str, SpiderQuality]:
    by_spider: Dict[str, SpiderQuality] = {}

    for item in items:
        spider = item.get("spider", "unknown")
        if spider not in by_spider:
            by_spider[spider] = SpiderQuality(spider=spider)
        sq = by_spider[spider]
        sq.total_items += 1

        for opt_field in OPTIONAL_FIELDS:
            if _is_filled(item.get(opt_field)):
                sq.optional_fill[opt_field] = sq.optional_fill.get(opt_field, 0) + 1

        if _is_filled(item.get("verdict")):
            sq.verdict_filled_count += 1
        else:
            sq.verdict_null_count += 1

        summary = item.get("summary")
        if isinstance(summary, str) and summary.strip():
            sq.summary_lengths.append(len(summary.strip()))

        claim = item.get("claim")
        if isinstance(claim, str) and claim.strip():
            sq.claim_lengths.append(len(claim.strip()))

        body = item.get("body")
        if isinstance(body, str) and body.strip():
            sq.body_lengths.append(len(body.strip()))

    return by_spider


def analyze_run(run_dir: Path) -> Dict[str, SpiderQuality]:
    items_path = run_dir / "items.jsonl"
    if not items_path.exists():
        return {}
    items = []
    for line in items_path.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return analyze_items(items)


def format_quality_text(quality: Dict[str, SpiderQuality]) -> str:
    if not quality:
        return "No items to analyze."

    lines: list[str] = []
    lines.append(f"{'Spider':<25} {'Items':>6} {'Verdict':>8} {'AvgSumm':>8} {'AvgClaim':>9} {'AvgBody':>8}")
    lines.append("-" * 70)

    for name in sorted(quality):
        sq = quality[name]
        lines.append(
            f"{sq.spider:<25} {sq.total_items:>6} {sq.verdict_fill_rate:>7.0%}"
            f" {sq.avg_summary_length:>8.0f} {sq.avg_claim_length:>9.0f} {sq.avg_body_length:>8.0f}"
        )

    lines.append("")
    lines.append("Optional field fill rates:")
    all_fields = sorted(OPTIONAL_FIELDS)
    header = f"  {'Spider':<25}" + "".join(f" {f[:6]:>7}" for f in all_fields)
    lines.append(header)
    lines.append("  " + "-" * (25 + 7 * len(all_fields)))

    for name in sorted(quality):
        sq = quality[name]
        rates = sq.optional_fill_rates
        row = f"  {sq.spider:<25}"
        for f in all_fields:
            rate = rates.get(f, 0.0)
            row += f" {rate:>6.0%}"
        lines.append(row)

    return "\n".join(lines)

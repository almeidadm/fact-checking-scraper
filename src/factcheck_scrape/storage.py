from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .utils import utc_now_iso


@dataclass
class RunCounts:
    items_seen: int = 0
    items_stored: int = 0
    items_deduped: int = 0
    items_invalid: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "items_seen": self.items_seen,
            "items_stored": self.items_stored,
            "items_deduped": self.items_deduped,
            "items_invalid": self.items_invalid,
        }


class RunWriter:
    def __init__(self, data_dir: Path, run_id: str) -> None:
        self.data_dir = Path(data_dir)
        self.run_id = run_id
        self.run_dir = self.data_dir / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.items_path = self.run_dir / "items.jsonl"
        self.run_path = self.run_dir / "run.json"
        self.started_at = utc_now_iso()
        self._items_handle = None

    def _get_items_handle(self):
        if self._items_handle is None or self._items_handle.closed:
            self._items_handle = self.items_path.open("a", encoding="utf-8")
        return self._items_handle

    def write_item(self, item: Dict[str, Any]) -> None:
        handle = self._get_items_handle()
        handle.write(json.dumps(item, ensure_ascii=False))
        handle.write("\n")
        handle.flush()

    def close(self) -> None:
        if self._items_handle and not self._items_handle.closed:
            self._items_handle.close()

    def update_run(
        self,
        spider_name: str,
        agency_id: str,
        agency_name: str,
        counts: RunCounts,
        spider_started_at: str,
        spider_finished_at: str,
    ) -> None:
        payload = self._load_run()
        if not payload:
            payload = {
                "run_id": self.run_id,
                "started_at": self.started_at,
                "finished_at": spider_finished_at,
                "spiders": {},
                "totals": {},
            }

        payload.setdefault("spiders", {})
        payload["spiders"][spider_name] = {
            "agency_id": agency_id,
            "agency_name": agency_name,
            "started_at": spider_started_at,
            "finished_at": spider_finished_at,
            **counts.to_dict(),
        }

        # Update run timestamps
        payload["started_at"] = min(payload.get("started_at", self.started_at), spider_started_at)
        payload["finished_at"] = max(
            payload.get("finished_at", spider_finished_at), spider_finished_at
        )

        # Update totals
        totals = {
            "items_seen": 0,
            "items_stored": 0,
            "items_deduped": 0,
            "items_invalid": 0,
        }
        for spider_data in payload["spiders"].values():
            totals["items_seen"] += spider_data.get("items_seen", 0)
            totals["items_stored"] += spider_data.get("items_stored", 0)
            totals["items_deduped"] += spider_data.get("items_deduped", 0)
            totals["items_invalid"] += spider_data.get("items_invalid", 0)
        payload["totals"] = totals

        with self.run_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _load_run(self) -> Dict[str, Any]:
        if not self.run_path.exists():
            return {}
        try:
            return json.loads(self.run_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

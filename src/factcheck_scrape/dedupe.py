from __future__ import annotations

import json
from pathlib import Path
from typing import Set

from .utils import make_item_id, utc_now_iso


class DedupeStore:
    def __init__(
        self,
        data_dir: Path,
        agency_id: str,
        *,
        ignore_existing_seen_state: bool = False,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.agency_id = agency_id
        self.ignore_existing_seen_state = ignore_existing_seen_state
        self.state_dir = self.data_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / f"seen_{agency_id}.jsonl"
        self._existing_seen: Set[str] = set()
        self._run_seen: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        with self.state_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item_id = payload.get("item_id")
                if item_id:
                    self._existing_seen.add(item_id)

    def is_seen(self, canonical_url: str) -> bool:
        item_id = make_item_id(self.agency_id, canonical_url)
        if item_id in self._run_seen:
            return True
        if self.ignore_existing_seen_state:
            return False
        return item_id in self._existing_seen

    def mark_seen(self, canonical_url: str, source_url: str) -> str:
        item_id = make_item_id(self.agency_id, canonical_url)
        if item_id in self._run_seen:
            return item_id

        if item_id not in self._existing_seen:
            payload = {
                "item_id": item_id,
                "canonical_url": canonical_url,
                "source_url": source_url,
                "seen_at": utc_now_iso(),
            }
            with self.state_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True))
                handle.write("\n")
            self._existing_seen.add(item_id)

        self._run_seen.add(item_id)
        return item_id

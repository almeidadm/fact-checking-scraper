from __future__ import annotations

import json
import sqlite3
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
        self.db_path = self.state_dir / f"seen_{agency_id}.db"
        self._legacy_path = self.state_dir / f"seen_{agency_id}.jsonl"
        self._run_seen: Set[str] = set()
        self._conn = self._open_db()
        self._migrate_legacy()

    def _open_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), isolation_level="DEFERRED")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            "  item_id TEXT PRIMARY KEY,"
            "  canonical_url TEXT,"
            "  source_url TEXT,"
            "  seen_at TEXT"
            ")"
        )
        conn.commit()
        return conn

    def _migrate_legacy(self) -> None:
        if not self._legacy_path.exists():
            return
        count = 0
        with self._legacy_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item_id = payload.get("item_id")
                if not item_id:
                    continue
                self._conn.execute(
                    "INSERT OR IGNORE INTO seen (item_id, canonical_url, source_url, seen_at)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        item_id,
                        payload.get("canonical_url", ""),
                        payload.get("source_url", ""),
                        payload.get("seen_at", ""),
                    ),
                )
                count += 1
        self._conn.commit()
        backup_path = self._legacy_path.with_suffix(".jsonl.bak")
        self._legacy_path.rename(backup_path)

    def is_seen(self, canonical_url: str) -> bool:
        item_id = make_item_id(self.agency_id, canonical_url)
        if item_id in self._run_seen:
            return True
        if self.ignore_existing_seen_state:
            return False
        row = self._conn.execute(
            "SELECT 1 FROM seen WHERE item_id = ?", (item_id,)
        ).fetchone()
        return row is not None

    def mark_seen(self, canonical_url: str, source_url: str) -> str:
        item_id = make_item_id(self.agency_id, canonical_url)
        if item_id in self._run_seen:
            return item_id

        self._conn.execute(
            "INSERT OR IGNORE INTO seen (item_id, canonical_url, source_url, seen_at)"
            " VALUES (?, ?, ?, ?)",
            (item_id, canonical_url, source_url, utc_now_iso()),
        )
        self._conn.commit()
        self._run_seen.add(item_id)
        return item_id

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def __del__(self) -> None:
        self.close()

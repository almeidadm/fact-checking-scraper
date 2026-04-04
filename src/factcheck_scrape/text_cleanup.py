"""Text cleanup pipeline — normalizes text fields before storage.

Registered at priority 200 (runs before FactCheckPipeline at 300).
Applies: html.unescape, mojibake repair, NFKC normalization, whitespace collapse.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2", "\ufffd")

TEXT_FIELDS = {
    "title",
    "claim",
    "summary",
    "verdict",
    "rating",
    "author",
    "body",
    "language",
    "country",
    "source_type",
}

LIST_TEXT_FIELDS = {
    "topics",
    "tags",
    "entities",
}


def clean_stored_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = html.unescape(text)
    text = _maybe_fix_mojibake(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def _maybe_fix_mojibake(text: str) -> str:
    if not any(marker in text for marker in MOJIBAKE_MARKERS):
        return text
    try:
        candidate = text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text
    return candidate if _mojibake_score(candidate) < _mojibake_score(text) else text


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


class TextCleanupPipeline:
    """Scrapy pipeline that normalizes text fields on every item."""

    def process_item(self, item: dict[str, Any], spider) -> dict[str, Any]:
        for field in TEXT_FIELDS:
            if field in item:
                item[field] = clean_stored_text(item[field])

        for field in LIST_TEXT_FIELDS:
            raw = item.get(field)
            if isinstance(raw, list):
                cleaned = []
                for v in raw:
                    c = clean_stored_text(v)
                    if c:
                        cleaned.append(c)
                item[field] = cleaned

        return item

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlsplit

from .utils import canonicalize_url

REQUIRED_FIELDS = {
    "item_id",
    "agency_id",
    "agency_name",
    "spider",
    "source_url",
    "canonical_url",
    "title",
    "published_at",
    "collected_at",
    "run_id",
}

OPTIONAL_FIELDS = {
    "claim",
    "summary",
    "verdict",
    "rating",
    "language",
    "country",
    "topics",
    "tags",
    "entities",
    "source_type",
}

PLACEHOLDER_PUBLISHED_AT_VALUES = frozenset({"-", "–", "—"})


@dataclass
class FactCheckItem:
    item_id: str
    agency_id: str
    agency_name: str
    spider: str
    source_url: str
    canonical_url: str
    title: str
    published_at: str
    collected_at: str
    run_id: str
    claim: Optional[str] = None
    summary: Optional[str] = None
    verdict: Optional[str] = None
    rating: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    topics: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "agency_id": self.agency_id,
            "agency_name": self.agency_name,
            "spider": self.spider,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "run_id": self.run_id,
            "claim": self.claim,
            "summary": self.summary,
            "verdict": self.verdict,
            "rating": self.rating,
            "language": self.language,
            "country": self.country,
            "topics": self.topics,
            "tags": self.tags,
            "entities": self.entities,
            "source_type": self.source_type,
        }


def validate_item(item: Dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if not item.get(field)]
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Missing required fields: {missing_str}")

    allowed = REQUIRED_FIELDS | OPTIONAL_FIELDS
    unexpected = [field for field in item.keys() if field not in allowed]
    if unexpected:
        unexpected_str = ", ".join(sorted(unexpected))
        raise ValueError(f"Unexpected fields: {unexpected_str}")

    _validate_item_quality(item)


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        key: value for key, value in item.items() if key in REQUIRED_FIELDS | OPTIONAL_FIELDS
    }
    # Ensure list fields are lists
    for key in ("topics", "tags", "entities"):
        if key in normalized and normalized[key] is None:
            normalized[key] = []
    return normalized


def as_item_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, FactCheckItem):
        return item.to_dict()
    if isinstance(item, Mapping):
        return dict(item)
    raise TypeError("Item must be dict or FactCheckItem")


def required_fields() -> Iterable[str]:
    return sorted(REQUIRED_FIELDS)


def optional_fields() -> Iterable[str]:
    return sorted(OPTIONAL_FIELDS)


def _validate_item_quality(item: Dict[str, Any]) -> None:
    title = str(item.get("title", "")).strip()
    published_at = str(item.get("published_at", "")).strip()

    if title and _is_probable_url(title):
        candidates = {
            canonicalize_url(str(item.get("source_url", "")).strip()),
            canonicalize_url(str(item.get("canonical_url", "")).strip()),
        }
        if canonicalize_url(title) in candidates:
            raise ValueError("Invalid title: matches item URL")

    if published_at in PLACEHOLDER_PUBLISHED_AT_VALUES:
        raise ValueError("Invalid published_at: placeholder value")


def _is_probable_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

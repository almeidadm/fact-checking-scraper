from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union, get_args, get_origin, get_type_hints
from urllib.parse import urlsplit

from .utils import canonicalize_url

PLACEHOLDER_PUBLISHED_AT_VALUES = frozenset({"-", "\u2013", "\u2014"})

URI_FIELDS = frozenset({"source_url", "canonical_url"})


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
    author: Optional[str] = None
    body: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    topics: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _derive_field_sets() -> tuple[frozenset[str], frozenset[str]]:
    required = set()
    optional = set()
    for f in fields(FactCheckItem):
        has_default = (
            f.default is not dataclasses.MISSING
            or f.default_factory is not dataclasses.MISSING
        )
        if has_default:
            optional.add(f.name)
        else:
            required.add(f.name)
    return frozenset(required), frozenset(optional)


REQUIRED_FIELDS, OPTIONAL_FIELDS = _derive_field_sets()


def _python_type_to_json_schema(name: str, resolved_type: Any) -> dict[str, Any]:
    origin = get_origin(resolved_type)
    args = get_args(resolved_type)

    if origin is list:
        return {"type": "array", "items": {"type": "string"}}

    is_optional = origin is Union and type(None) in args
    if is_optional:
        schema: dict[str, Any] = {"type": ["string", "null"]}
    else:
        schema = {"type": "string"}

    if name in URI_FIELDS:
        schema["format"] = "uri"

    return schema


def generate_json_schema() -> dict[str, Any]:
    hints = get_type_hints(FactCheckItem)
    properties = {}
    required = []
    for f in fields(FactCheckItem):
        properties[f.name] = _python_type_to_json_schema(f.name, hints[f.name])
        if f.name in REQUIRED_FIELDS:
            required.append(f.name)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FactCheckItem",
        "type": "object",
        "required": sorted(required),
        "properties": properties,
        "additionalProperties": False,
    }


def write_json_schema(path: Path | str = "docs/schema.json") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = generate_json_schema()
    path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


_CACHED_SCHEMA: dict[str, Any] | None = None
_CACHED_VALIDATOR: Any = None


def _get_validator():
    global _CACHED_SCHEMA, _CACHED_VALIDATOR
    if _CACHED_VALIDATOR is None:
        from jsonschema import Draft202012Validator

        _CACHED_SCHEMA = generate_json_schema()
        Draft202012Validator.check_schema(_CACHED_SCHEMA)
        _CACHED_VALIDATOR = Draft202012Validator(_CACHED_SCHEMA)
    return _CACHED_VALIDATOR


def validate_item(item: Dict[str, Any]) -> None:
    validator = _get_validator()
    errors = sorted(validator.iter_errors(item), key=lambda e: list(e.path))
    if errors:
        messages = []
        for err in errors:
            path = ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
            messages.append(f"{path}: {err.message}")
        raise ValueError("; ".join(messages))

    # Required fields must be non-empty strings (jsonschema only checks presence)
    missing = [f for f in REQUIRED_FIELDS if not item.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")

    _validate_item_quality(item)


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        key: value for key, value in item.items() if key in REQUIRED_FIELDS | OPTIONAL_FIELDS
    }
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

"""JSON-LD extraction and parsing utilities."""

from __future__ import annotations

import json
from typing import Any, Iterable


def extract_jsonld(response, *, logger=None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scripts = response.css("script[type='application/ld+json']::text").getall()
    for raw in scripts:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if logger:
                logger.debug("jsonld_parse_error", url=response.url)
            continue
        items.extend(_normalize_jsonld(payload))
    return items


def _normalize_jsonld(payload: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            normalized.extend(_normalize_jsonld(item))
        return normalized
    if not isinstance(payload, dict):
        return normalized

    graph = payload.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            normalized.extend(_normalize_jsonld(item))
        return normalized

    normalized.append(payload)
    return normalized


def jsonld_type_matches(item: dict[str, Any], expected: str) -> bool:
    item_type = item.get("@type")
    if isinstance(item_type, list):
        return expected in item_type
    return item_type == expected


def pick_jsonld(items: Iterable[dict[str, Any]], *expected_types: str) -> dict[str, Any]:
    collected = list(items)
    for expected in expected_types:
        for item in collected:
            if jsonld_type_matches(item, expected):
                return item
    return collected[0] if collected else {}

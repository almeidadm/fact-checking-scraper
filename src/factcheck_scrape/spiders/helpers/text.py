"""Text processing utilities for fact-check spiders."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlsplit

from ...utils import ensure_list

PLACEHOLDER_PUBLISHED_AT_VALUES = frozenset({"-", "\u2013", "\u2014"})


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                cleaned = clean_text(item)
                if cleaned:
                    return cleaned
            continue
        cleaned = clean_text(value)
        if cleaned:
            return cleaned
    return None


def is_probable_url(value: Any) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    parsed = urlsplit(cleaned)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_placeholder_published_at(value: Any) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    return cleaned in PLACEHOLDER_PUBLISHED_AT_VALUES


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def unique_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def extract_names(value: Any) -> list[str]:
    names: list[str] = []
    for item in listify(value):
        if isinstance(item, dict):
            name = first_text(item.get("name"), item.get("headline"))
            if name:
                names.append(name)
            continue
        cleaned = clean_text(item)
        if cleaned:
            names.append(cleaned)
    return unique_list(names)


def split_keywords(value: Any) -> list[str]:
    parts: list[str] = []
    for item in ensure_list(value):
        if item is None:
            continue
        for part in str(item).split(","):
            cleaned = clean_text(part)
            if cleaned:
                parts.append(cleaned)
    return unique_list(parts)


def extract_label_prefix_before_colon(value: Any) -> str | None:
    cleaned = clean_text(value)
    if not cleaned or ":" not in cleaned:
        return None
    prefix = cleaned.split(":", 1)[0]
    return clean_text(prefix)


def extract_text_after_colon(value: Any) -> str | None:
    cleaned = clean_text(value)
    if not cleaned or ":" not in cleaned:
        return None
    suffix = cleaned.split(":", 1)[1]
    return clean_text(suffix)


def meta_first(response, *selectors: str) -> str | None:
    for selector in selectors:
        value = response.css(selector).get()
        cleaned = clean_text(value)
        if cleaned:
            return cleaned
    return None

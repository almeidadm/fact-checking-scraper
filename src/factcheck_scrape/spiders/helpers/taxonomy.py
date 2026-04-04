"""Taxonomy extraction: topics, tags, entities, source type, language."""

from __future__ import annotations

from typing import Any

from .text import (
    clean_text,
    extract_names,
    first_text,
    meta_first,
    split_keywords,
    unique_list,
)


def extract_taxonomy(*items: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    topics: list[str] = []
    tags: list[str] = []
    entities: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        topics.extend(extract_names(item.get("articleSection")))
        topics.extend(extract_names(item.get("about")))
        tags.extend(split_keywords(item.get("keywords")))
        entities.extend(extract_names(item.get("mentions")))

    return (
        unique_list(topics),
        unique_list(tags),
        unique_list(entities),
    )


def extract_source_type(*items: dict[str, Any]) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("@type")
        if isinstance(item_type, list):
            joined = first_text(",".join(str(value) for value in item_type))
            if joined:
                return joined
        cleaned = clean_text(item_type)
        if cleaned:
            return cleaned
    return None


def extract_language(response, *items: dict[str, Any]) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        value = clean_text(item.get("inLanguage"))
        if value:
            return value
    return meta_first(response, "html::attr(lang)")

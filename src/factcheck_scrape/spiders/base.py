from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import scrapy

from ..logging import get_logger
from ..utils import canonicalize_url, ensure_list, make_item_id, utc_now_iso

PLACEHOLDER_PUBLISHED_AT_VALUES = frozenset({"-", "–", "—"})


class BaseFactCheckSpider(scrapy.Spider):
    agency_id: str = ""
    agency_name: str = ""
    start_urls: list[str] = []
    allowed_domains: list[str] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger_struct = get_logger(self.name)

    def canonicalize(self, url: str) -> str:
        return canonicalize_url(url)

    def clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return " ".join(text.split())

    def first_text(self, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    cleaned = self.clean_text(item)
                    if cleaned:
                        return cleaned
                continue
            cleaned = self.clean_text(value)
            if cleaned:
                return cleaned
        return None

    def is_probable_url(self, value: Any) -> bool:
        cleaned = self.clean_text(value)
        if not cleaned:
            return False
        parsed = urlsplit(cleaned)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def is_placeholder_published_at(self, value: Any) -> bool:
        cleaned = self.clean_text(value)
        if not cleaned:
            return False
        return cleaned in PLACEHOLDER_PUBLISHED_AT_VALUES

    def validate_extracted_article(
        self,
        response,
        *,
        title: Any,
        published_at: Any,
        source_url: str | None = None,
        canonical_url: str | None = None,
    ) -> bool:
        cleaned_title = self.clean_text(title)
        cleaned_published_at = self.clean_text(published_at)
        source_candidate = source_url or response.url
        canonical_candidate = canonical_url or source_candidate
        invalid_reasons: list[str] = []

        if not cleaned_title:
            invalid_reasons.append("missing_title")
        elif self.is_probable_url(cleaned_title):
            title_candidate = self.canonicalize(cleaned_title)
            url_candidates = {
                self.canonicalize(response.url),
                self.canonicalize(source_candidate),
                self.canonicalize(canonical_candidate),
            }
            if title_candidate in url_candidates:
                invalid_reasons.append("title_matches_url")

        if not cleaned_published_at:
            invalid_reasons.append("missing_published_at")
        elif self.is_placeholder_published_at(cleaned_published_at):
            invalid_reasons.append("placeholder_published_at")

        if invalid_reasons:
            self.logger_struct.warning(
                "dropping_invalid_article",
                url=response.url,
                canonical_url=canonical_candidate,
                invalid_reasons=invalid_reasons,
            )
            return False

        return True

    def extract_jsonld(self, response) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        scripts = response.css("script[type='application/ld+json']::text").getall()
        for raw in scripts:
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self.logger_struct.debug("jsonld_parse_error", url=response.url)
                continue
            items.extend(self._normalize_jsonld(payload))
        return items

    def _normalize_jsonld(self, payload: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if isinstance(payload, list):
            for item in payload:
                normalized.extend(self._normalize_jsonld(item))
            return normalized
        if not isinstance(payload, dict):
            return normalized

        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                normalized.extend(self._normalize_jsonld(item))
            return normalized

        normalized.append(payload)
        return normalized

    def jsonld_type_matches(self, item: dict[str, Any], expected: str) -> bool:
        item_type = item.get("@type")
        if isinstance(item_type, list):
            return expected in item_type
        return item_type == expected

    def pick_jsonld(self, items: Iterable[dict[str, Any]], *expected_types: str) -> dict[str, Any]:
        collected = list(items)
        for expected in expected_types:
            for item in collected:
                if self.jsonld_type_matches(item, expected):
                    return item
        return collected[0] if collected else {}

    def meta_first(self, response, *selectors: str) -> str | None:
        for selector in selectors:
            value = response.css(selector).get()
            cleaned = self.clean_text(value)
            if cleaned:
                return cleaned
        return None

    def listify(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def split_keywords(self, value: Any) -> list[str]:
        parts: list[str] = []
        for item in ensure_list(value):
            if item is None:
                continue
            for part in str(item).split(","):
                cleaned = self.clean_text(part)
                if cleaned:
                    parts.append(cleaned)
        return self.unique_list(parts)

    def extract_names(self, value: Any) -> list[str]:
        names: list[str] = []
        for item in self.listify(value):
            if isinstance(item, dict):
                name = self.first_text(item.get("name"), item.get("headline"))
                if name:
                    names.append(name)
                continue
            cleaned = self.clean_text(item)
            if cleaned:
                names.append(cleaned)
        return self.unique_list(names)

    def unique_list(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            cleaned = self.clean_text(value)
            if not cleaned:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            unique.append(cleaned)
        return unique

    def extract_taxonomy(self, *items: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
        topics: list[str] = []
        tags: list[str] = []
        entities: list[str] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            topics.extend(self.extract_names(item.get("articleSection")))
            topics.extend(self.extract_names(item.get("about")))
            tags.extend(self.split_keywords(item.get("keywords")))
            entities.extend(self.extract_names(item.get("mentions")))

        return (
            self.unique_list(topics),
            self.unique_list(tags),
            self.unique_list(entities),
        )

    def extract_source_type(self, *items: dict[str, Any]) -> str | None:
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if isinstance(item_type, list):
                joined = self.first_text(",".join(str(value) for value in item_type))
                if joined:
                    return joined
            cleaned = self.clean_text(item_type)
            if cleaned:
                return cleaned
        return None

    def extract_language(self, response, *items: dict[str, Any]) -> str | None:
        for item in items:
            if not isinstance(item, dict):
                continue
            value = self.clean_text(item.get("inLanguage"))
            if value:
                return value
        return self.meta_first(response, "html::attr(lang)")

    def extract_canonical_url(self, response, *items: dict[str, Any]) -> str:
        candidate = None
        for item in items:
            if not isinstance(item, dict):
                continue
            main_entity = item.get("mainEntityOfPage")
            main_entity_url = None
            if isinstance(main_entity, dict):
                main_entity_url = self.first_text(main_entity.get("@id"), main_entity.get("url"))
            else:
                main_entity_url = self.clean_text(main_entity)
            candidate = self.first_text(item.get("url"), main_entity_url)
            if candidate:
                break

        if not candidate:
            candidate = self.meta_first(
                response,
                "link[rel='canonical']::attr(href)",
                "meta[property='og:url']::attr(content)",
            )

        if candidate:
            candidate = urljoin(response.url, candidate)

        return self.canonicalize(candidate or response.url)

    def extract_verdict_and_rating(
        self, claim_review: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        review_rating = claim_review.get("reviewRating")
        if not isinstance(review_rating, dict):
            return (None, None)

        verdict = self.first_text(
            self._normalize_verdict_label(review_rating.get("alternateName")),
            self._normalize_verdict_label(review_rating.get("name")),
        )
        rating = self.first_text(
            review_rating.get("ratingValue"),
            review_rating.get("bestRating"),
            review_rating.get("worstRating"),
        )
        return (verdict, rating)

    def _normalize_verdict_label(self, value: Any) -> str | None:
        cleaned = self.clean_text(value)
        if not cleaned:
            return None
        if re.fullmatch(r"\d+(?:[.,]\d+)?", cleaned):
            return None
        return cleaned

    def extract_label_prefix_before_colon(self, value: Any) -> str | None:
        cleaned = self.clean_text(value)
        if not cleaned or ":" not in cleaned:
            return None
        prefix = cleaned.split(":", 1)[0]
        return self.clean_text(prefix)

    def extract_text_after_colon(self, value: Any) -> str | None:
        cleaned = self.clean_text(value)
        if not cleaned or ":" not in cleaned:
            return None
        suffix = cleaned.split(":", 1)[1]
        return self.clean_text(suffix)

    def infer_verdict(self, *values: Any) -> str | None:
        patterns = (
            (r"\bverdade,?\s*mas\b", "Verdade, mas"),
            (r"\bimprecis[oa]\b", "Impreciso"),
            (r"\berrado\b", "Errado"),
            (r"\bverdadeir[oa]\b|\bé verdade\b|\btem raz[aã]o\b", "Verdadeiro"),
            (r"\bfals[oa]\b|\bn[aã]o [ée] verdade\b|\bboato\b|\bfake\b|\bhoax\b", "Falso"),
        )
        for value in values:
            cleaned = self.clean_text(value)
            if not cleaned:
                continue
            lowered = cleaned.lower()
            for pattern, verdict in patterns:
                if re.search(pattern, lowered):
                    return verdict
        return None

    def build_item(
        self,
        source_url: str,
        title: str,
        published_at: str,
        canonical_url: Optional[str] = None,
        claim: Optional[str] = None,
        summary: Optional[str] = None,
        verdict: Optional[str] = None,
        rating: Optional[str] = None,
        language: Optional[str] = None,
        country: Optional[str] = None,
        topics: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_canonical = canonical_url or self.canonicalize(source_url)
        item_id = make_item_id(self.agency_id or self.name, resolved_canonical)
        return {
            "item_id": item_id,
            "agency_id": self.agency_id or self.name,
            "agency_name": self.agency_name or self.name,
            "spider": self.name,
            "source_url": source_url,
            "canonical_url": resolved_canonical,
            "title": title,
            "published_at": published_at,
            "collected_at": utc_now_iso(),
            "claim": claim,
            "summary": summary,
            "verdict": verdict,
            "rating": rating,
            "language": language,
            "country": country,
            "topics": topics or [],
            "tags": tags or [],
            "entities": entities or [],
            "source_type": source_type,
        }

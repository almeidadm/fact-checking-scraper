from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import scrapy

from ..logging import get_logger
from ..utils import canonicalize_url, make_item_id, utc_now_iso
from .helpers import claimreview as _cr
from .helpers import jsonld as _jl
from .helpers import taxonomy as _tx
from .helpers import text as _txt


class BaseFactCheckSpider(scrapy.Spider):
    agency_id: str = ""
    agency_name: str = ""
    start_urls: list[str] = []
    allowed_domains: list[str] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger_struct = get_logger(self.name)

    # -- text helpers (delegate to helpers.text) --

    def canonicalize(self, url: str) -> str:
        return canonicalize_url(url)

    def clean_text(self, value: Any) -> str | None:
        return _txt.clean_text(value)

    def first_text(self, *values: Any) -> str | None:
        return _txt.first_text(*values)

    def is_probable_url(self, value: Any) -> bool:
        return _txt.is_probable_url(value)

    def is_placeholder_published_at(self, value: Any) -> bool:
        return _txt.is_placeholder_published_at(value)

    def listify(self, value: Any) -> list[Any]:
        return _txt.listify(value)

    def split_keywords(self, value: Any) -> list[str]:
        return _txt.split_keywords(value)

    def extract_names(self, value: Any) -> list[str]:
        return _txt.extract_names(value)

    def unique_list(self, values: Iterable[str]) -> list[str]:
        return _txt.unique_list(values)

    def extract_label_prefix_before_colon(self, value: Any) -> str | None:
        return _txt.extract_label_prefix_before_colon(value)

    def extract_text_after_colon(self, value: Any) -> str | None:
        return _txt.extract_text_after_colon(value)

    def meta_first(self, response, *selectors: str) -> str | None:
        return _txt.meta_first(response, *selectors)

    # -- validation --

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

    # -- JSON-LD (delegate to helpers.jsonld) --

    def extract_jsonld(self, response) -> list[dict[str, Any]]:
        return _jl.extract_jsonld(response, logger=self.logger_struct)

    def jsonld_type_matches(self, item: dict[str, Any], expected: str) -> bool:
        return _jl.jsonld_type_matches(item, expected)

    def pick_jsonld(self, items: Iterable[dict[str, Any]], *expected_types: str) -> dict[str, Any]:
        return _jl.pick_jsonld(items, *expected_types)

    # -- ClaimReview (delegate to helpers.claimreview) --

    def extract_verdict_and_rating(
        self, claim_review: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        return _cr.extract_verdict_and_rating(claim_review)

    def extract_canonical_url(self, response, *items: dict[str, Any]) -> str:
        return _cr.extract_canonical_url(response, *items, canonicalize_fn=self.canonicalize)

    def extract_author(self, response, *items: dict[str, Any]) -> str | None:
        return _cr.extract_author(response, *items)

    def extract_body(self, response, *items: dict[str, Any]) -> str | None:
        return _cr.extract_body(response, *items)

    def infer_verdict(self, *values: Any) -> str | None:
        return _cr.infer_verdict(*values)

    # -- Taxonomy (delegate to helpers.taxonomy) --

    def extract_taxonomy(self, *items: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
        return _tx.extract_taxonomy(*items)

    def extract_source_type(self, *items: dict[str, Any]) -> str | None:
        return _tx.extract_source_type(*items)

    def extract_language(self, response, *items: dict[str, Any]) -> str | None:
        return _tx.extract_language(response, *items)

    # -- Item builder --

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
        author: Optional[str] = None,
        body: Optional[str] = None,
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
            "author": author,
            "body": body,
            "language": language,
            "country": country,
            "topics": topics or [],
            "tags": tags or [],
            "entities": entities or [],
            "source_type": source_type,
        }

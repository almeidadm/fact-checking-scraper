"""ClaimReview extraction: verdicts, canonical URLs, authors, body text."""

from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urljoin

from .text import clean_text, first_text, meta_first


def extract_verdict_and_rating(
    claim_review: dict[str, Any],
) -> tuple[str | None, str | None]:
    review_rating = claim_review.get("reviewRating")
    if not isinstance(review_rating, dict):
        return (None, None)

    verdict = first_text(
        _normalize_verdict_label(review_rating.get("alternateName")),
        _normalize_verdict_label(review_rating.get("name")),
    )
    rating = first_text(
        review_rating.get("ratingValue"),
        review_rating.get("bestRating"),
        review_rating.get("worstRating"),
    )
    return (verdict, rating)


def _normalize_verdict_label(value: Any) -> str | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None
    if re.fullmatch(r"\d+(?:[.,]\d+)?", cleaned):
        return None
    return cleaned


def extract_canonical_url(
    response,
    *items: dict[str, Any],
    canonicalize_fn: Callable[[str], str] | None = None,
) -> str:
    candidate = None
    for item in items:
        if not isinstance(item, dict):
            continue
        main_entity = item.get("mainEntityOfPage")
        main_entity_url = None
        if isinstance(main_entity, dict):
            main_entity_url = first_text(main_entity.get("@id"), main_entity.get("url"))
        else:
            main_entity_url = clean_text(main_entity)
        candidate = first_text(item.get("url"), main_entity_url)
        if candidate:
            break

    if not candidate:
        candidate = meta_first(
            response,
            "link[rel='canonical']::attr(href)",
            "meta[property='og:url']::attr(content)",
        )

    if candidate:
        candidate = urljoin(response.url, candidate)

    canon = canonicalize_fn or (lambda u: u)
    return canon(candidate or response.url)


def extract_author(response, *items: dict[str, Any]) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        if isinstance(author, list):
            names = [_extract_author_name(a) for a in author]
            joined = ", ".join(n for n in names if n)
            if joined:
                return joined
        name = _extract_author_name(author)
        if name:
            return name
    return meta_first(
        response,
        "meta[name='author']::attr(content)",
        "meta[property='article:author']::attr(content)",
    )


def _extract_author_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return first_text(value.get("name"), value.get("alternateName"))
    return clean_text(value)


def extract_body(response, *items: dict[str, Any]) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        body = clean_text(item.get("articleBody"))
        if body:
            return body
    paragraphs = response.css(
        "article p::text, "
        ".article-body p::text, "
        ".content-text p::text, "
        "[itemprop='articleBody'] p::text"
    ).getall()
    if paragraphs:
        cleaned = [clean_text(p) for p in paragraphs]
        joined = " ".join(p for p in cleaned if p)
        if joined:
            return joined
    return None


def infer_verdict(*values: Any) -> str | None:
    patterns = (
        (r"\bverdade,?\s*mas\b", "Verdade, mas"),
        (r"\bimprecis[oa]\b", "Impreciso"),
        (r"\berrado\b", "Errado"),
        (r"\bverdadeir[oa]\b|\b\u00e9 verdade\b|\btem raz[\u00e3a]o\b", "Verdadeiro"),
        (r"\bfals[oa]\b|\bn[\u00e3a]o [\u00e9e] verdade\b|\bboato\b|\bfake\b|\bhoax\b", "Falso"),
    )
    for value in values:
        cleaned = clean_text(value)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        for pattern, verdict in patterns:
            if re.search(pattern, lowered):
                return verdict
    return None

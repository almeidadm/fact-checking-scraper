from __future__ import annotations

import json
from urllib.parse import quote

import scrapy

from .base import BaseFactCheckSpider

REUTERS_API_URL = (
    "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1"
)
REUTERS_SECTION = "/fact-check/portugues/"
REUTERS_PAGE_SIZE = 20
REUTERS_LISTING_WAIT_SELECTOR = "a[href*='/fact-check/portugues/']"
REUTERS_ARTICLE_WAIT_SELECTOR = "script[type='application/ld+json'], h1"
REUTERS_API_HEADERS = {
    "Accept": "*/*",
    "Referer": "https://www.reuters.com/fact-check/portugues/",
}
REUTERS_DOWNLOAD_DELAY_SECONDS = 2.0
REUTERS_AUTOTHROTTLE_MAX_DELAY_SECONDS = 12.0
REUTERS_BLOCK_MARKERS = (
    "just a moment",
    "attention required",
    "cf-browser-verification",
    "/cdn-cgi/challenge-platform",
)


class ReutersFactCheckSpider(BaseFactCheckSpider):
    name = "reuters_fact_check"
    agency_id = "reuters"
    agency_name = "Reuters Fact Check"
    allowed_domains = ["reuters.com"]
    start_urls = ["https://www.reuters.com/fact-check/portugues/"]
    handle_httpstatus_list = [401, 403]
    custom_settings = {
        "FACTCHECK_SCRAPLING_HEADLESS": False,
        "FACTCHECK_SCRAPLING_REAL_CHROME": True,
        "FACTCHECK_SCRAPLING_BLOCK_WEBRTC": True,
        "FACTCHECK_SCRAPLING_HIDE_CANVAS": True,
        "FACTCHECK_SCRAPLING_ALLOW_WEBGL": True,
        "FACTCHECK_SCRAPLING_BLOCK_STATUSES": [401, 403, 429, 503],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": REUTERS_DOWNLOAD_DELAY_SECONDS,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": REUTERS_DOWNLOAD_DELAY_SECONDS,
        "AUTOTHROTTLE_MAX_DELAY": REUTERS_AUTOTHROTTLE_MAX_DELAY_SECONDS,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_offsets: set[int] = set()

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta=self._scrapling_meta(wait_selector=REUTERS_LISTING_WAIT_SELECTOR),
            )

    async def start(self):
        for request in self.start_requests():
            yield request

    def parse(self, response):
        if self._is_blocked_response(response):
            self.logger_struct.warning(
                "reuters_listing_blocked",
                url=response.url,
                status=response.status,
            )
            return

        for href in self._extract_listing_links(response):
            yield response.follow(
                href,
                callback=self.parse_article,
                meta=self._scrapling_meta(wait_selector=REUTERS_ARTICLE_WAIT_SELECTOR),
            )

        yield from self._schedule_api(response, 0)

    def parse_api(self, response):
        if self._is_blocked_response(response):
            self.logger_struct.warning(
                "reuters_api_blocked",
                url=response.url,
                status=response.status,
                offset=response.meta.get("offset"),
            )
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger_struct.warning("reuters_api_invalid_json", url=response.url)
            return

        entries = self._extract_api_entries(payload)
        for entry in entries:
            url = self._extract_entry_url(entry)
            if not url:
                continue
            yield response.follow(
                url,
                callback=self.parse_article,
                meta=self._scrapling_meta(wait_selector=REUTERS_ARTICLE_WAIT_SELECTOR),
            )

        current_offset = int(response.meta.get("offset", 0))
        next_offset = self._extract_next_offset(payload, current_offset, len(entries))
        if next_offset is not None:
            yield from self._schedule_api(response, next_offset)

    def parse_article(self, response):
        if self._is_blocked_response(response):
            self.logger_struct.warning(
                "reuters_article_blocked",
                url=response.url,
                status=response.status,
            )
            return

        jsonld_items = self.extract_jsonld(response)
        claim_review = self.pick_jsonld(jsonld_items, "ClaimReview")
        article = self.pick_jsonld(jsonld_items, "NewsArticle", "Article", "WebPage")

        title = self.first_text(
            article.get("headline"),
            article.get("name"),
            self.meta_first(
                response,
                "meta[property='og:title']::attr(content)",
                "h1::text",
                "title::text",
            ),
        )
        published_at = self.first_text(
            claim_review.get("datePublished"),
            article.get("datePublished"),
            article.get("dateModified"),
            self.meta_first(
                response,
                "meta[property='article:published_time']::attr(content)",
                "time::attr(datetime)",
            ),
        )
        canonical_url = self.extract_canonical_url(response, claim_review, article)
        summary = self.first_text(
            article.get("description"),
            claim_review.get("reviewBody"),
            self.meta_first(
                response,
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            ),
        )
        claim = self.first_text(claim_review.get("claimReviewed"), title, summary)
        verdict, rating = self.extract_verdict_and_rating(claim_review)
        verdict = self.infer_verdict(verdict, title, summary) or verdict
        rating = rating or verdict
        language = self.extract_language(response, claim_review, article)
        topics, tags, entities = self.extract_taxonomy(claim_review, article)
        keyword_content = response.css("meta[name='keywords']::attr(content)").get()
        tags = self.unique_list(tags + self.split_keywords(keyword_content))
        source_type = self.extract_source_type(claim_review, article)

        if not self.validate_extracted_article(
            response,
            title=title,
            published_at=published_at,
            canonical_url=canonical_url,
        ):
            return

        yield self.build_item(
            source_url=response.url,
            canonical_url=canonical_url,
            title=title,
            published_at=published_at,
            claim=claim,
            summary=summary,
            verdict=verdict,
            rating=rating,
            language=language,
            country=None,
            topics=topics,
            tags=tags,
            entities=entities,
            source_type=source_type,
        )

    def _schedule_api(self, response, offset: int):
        if offset in self._seen_offsets:
            return
        self._seen_offsets.add(offset)
        yield response.follow(
            self._build_api_url(offset),
            callback=self.parse_api,
            headers=REUTERS_API_HEADERS,
            meta=self._scrapling_meta(meta={"offset": offset}),
        )

    def _scrapling_meta(
        self,
        *,
        wait_selector: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        request_meta = dict(meta or {})
        request_meta["scrapling"] = {"enabled": True}
        if wait_selector:
            request_meta["scrapling"]["wait_selector"] = wait_selector
        return request_meta

    def _build_api_url(self, offset: int) -> str:
        query = {
            "arc-site": "reuters",
            "offset": offset,
            "requestId": (offset // REUTERS_PAGE_SIZE) + 1,
            "section_id": REUTERS_SECTION,
            "size": REUTERS_PAGE_SIZE,
            "uri": REUTERS_SECTION,
            "website": "reuters",
        }
        encoded = quote(json.dumps(query, separators=(",", ":")))
        return f"{REUTERS_API_URL}?query={encoded}&d=354&mxId=00000000&_website=reuters"

    def _extract_listing_links(self, response) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for href in response.css("a[href*='/fact-check/portugues/']::attr(href)").getall():
            absolute = response.urljoin(href)
            if not self._is_article_url(absolute):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def _extract_api_entries(self, payload: object) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        stack: list[object] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, list):
                stack.extend(current)
                continue
            if not isinstance(current, dict):
                continue
            url = self._extract_entry_url(current)
            if url and url not in seen_urls:
                seen_urls.add(url)
                entries.append(current)
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        return entries

    def _extract_entry_url(self, entry: dict[str, object]) -> str | None:
        if "canonical_url" not in entry and "website_url" not in entry and "headlines" not in entry:
            return None
        for key in ("canonical_url", "website_url", "url"):
            value = entry.get(key)
            cleaned = self.clean_text(value)
            if not cleaned:
                continue
            if cleaned.startswith("/"):
                absolute = f"https://www.reuters.com{cleaned}"
                if self._is_article_url(absolute):
                    return absolute
                continue
            if cleaned.startswith("http"):
                if self._is_article_url(cleaned):
                    return cleaned
        return None

    def _extract_next_offset(
        self, payload: dict[str, object], current_offset: int, entry_count: int
    ) -> int | None:
        result = payload.get("result")
        if isinstance(result, dict):
            pagination = result.get("pagination")
            if isinstance(pagination, dict):
                for key in ("next", "next_offset"):
                    value = pagination.get(key)
                    if isinstance(value, int) and value > current_offset:
                        return value
        if entry_count >= REUTERS_PAGE_SIZE:
            return current_offset + REUTERS_PAGE_SIZE
        return None

    def _is_article_url(self, url: str) -> bool:
        cleaned = self.clean_text(url)
        if not cleaned:
            return False
        absolute = cleaned
        if absolute.startswith("/"):
            absolute = f"https://www.reuters.com{absolute}"
        prefix = f"https://www.reuters.com{REUTERS_SECTION}"
        if not absolute.startswith(prefix):
            return False
        return absolute.rstrip("/") != self.start_urls[0].rstrip("/")

    def _is_blocked_response(self, response) -> bool:
        if response.status in {401, 403}:
            return True
        snippet = response.text[:32768].lower()
        return any(marker in snippet for marker in REUTERS_BLOCK_MARKERS)

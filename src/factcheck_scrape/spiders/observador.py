from __future__ import annotations

import json
from urllib.parse import urljoin

import scrapy
from scrapy import Selector

from .base import BaseFactCheckSpider

OBSERVADOR_API_TEMPLATE = (
    "https://observador.pt/wp-json/obs_api/v4/grids/filter/archive/obs_factcheck"
    "?offset={offset}&scroll=true"
)
OBSERVADOR_API_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://observador.pt/factchecks/",
}
OBSERVADOR_LISTING_WAIT_SELECTOR = ".editorial-grid"
OBSERVADOR_ARTICLE_WAIT_SELECTOR = "script[type='application/ld+json'], h1"
OBSERVADOR_BLOCK_MARKERS = (
    "just a moment",
    "attention required",
    "cf-browser-verification",
    "/cdn-cgi/challenge-platform",
)


class ObservadorSpider(BaseFactCheckSpider):
    name = "observador"
    agency_id = "observador"
    agency_name = "Observador"
    allowed_domains = ["observador.pt"]
    start_urls = ["https://observador.pt/factchecks/"]
    custom_settings = {
        "FACTCHECK_SCRAPLING_HEADLESS": False,
        "FACTCHECK_SCRAPLING_REAL_CHROME": True,
        "FACTCHECK_SCRAPLING_BLOCK_WEBRTC": True,
        "FACTCHECK_SCRAPLING_HIDE_CANVAS": True,
        "FACTCHECK_SCRAPLING_ALLOW_WEBGL": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_offsets: set[str] = set()

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta=self._scrapling_meta(wait_selector=OBSERVADOR_LISTING_WAIT_SELECTOR),
            )

    async def start(self):
        for request in self.start_requests():
            yield request

    def parse(self, response):
        if self._is_challenge_page(response):
            self.logger_struct.warning("observador_listing_challenge_page", url=response.url)
            return

        for href in self._extract_listing_links(response, response.url):
            yield response.follow(
                href,
                callback=self.parse_article,
                meta=self._scrapling_meta(wait_selector=OBSERVADOR_ARTICLE_WAIT_SELECTOR),
            )

        offset = self.first_text(response.css(".editorial-grid::attr(data-offset)").get())
        if offset:
            yield from self._schedule_api(response, offset)

    def parse_api(self, response):
        if self._is_challenge_page(response):
            self.logger_struct.warning("observador_api_challenge_page", url=response.url)
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger_struct.warning("observador_api_invalid_json", url=response.url)
            return

        rendered = payload.get("rendered")
        if not isinstance(rendered, dict):
            self.logger_struct.warning("observador_api_missing_rendered", url=response.url)
            return

        modules = rendered.get("modules")
        if not isinstance(modules, str) or not modules.strip():
            self.logger_struct.warning("observador_api_missing_modules", url=response.url)
            return

        selector = Selector(text=modules)
        for href in self._extract_listing_links(selector, self.start_urls[0]):
            yield response.follow(
                href,
                callback=self.parse_article,
                meta=self._scrapling_meta(wait_selector=OBSERVADOR_ARTICLE_WAIT_SELECTOR),
            )

        current_offset = str(response.meta.get("offset", ""))
        next_offset = self._extract_next_offset(selector, current_offset)
        if next_offset:
            yield from self._schedule_api(response, next_offset)

    def parse_article(self, response):
        if self._is_challenge_page(response):
            self.logger_struct.warning(
                "observador_article_challenge_page",
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
            self.meta_first(response, "time::attr(datetime)"),
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
        author = self.extract_author(response, claim_review, article)
        body = self.extract_body(response, claim_review, article)
        language = self.extract_language(response, claim_review, article)
        topics, tags, entities = self.extract_taxonomy(claim_review, article)
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
            author=author,
            body=body,
            language=language,
            country="PT",
            topics=topics,
            tags=tags,
            entities=entities,
            source_type=source_type,
        )

    def _schedule_api(self, response, offset: str):
        if offset in self._seen_offsets:
            return
        self._seen_offsets.add(offset)
        yield response.follow(
            OBSERVADOR_API_TEMPLATE.format(offset=offset),
            callback=self.parse_api,
            headers=OBSERVADOR_API_HEADERS,
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

    def _extract_listing_links(self, selector, base_url: str) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for href in selector.css("a[href*='/factchecks/']::attr(href)").getall():
            absolute = urljoin(base_url, href)
            if "/factchecks/" not in absolute:
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def _extract_next_offset(self, selector: Selector, current_offset: str) -> str | None:
        older_dates: set[str] = set()
        for value in selector.css("time::attr(datetime)").getall():
            cleaned = self.clean_text(value)
            if not cleaned or len(cleaned) < 10:
                continue
            day = cleaned[:10].replace("-", "")
            if current_offset and day < current_offset:
                older_dates.add(day)
        if not older_dates:
            return None
        return min(older_dates)

    def _is_challenge_page(self, response) -> bool:
        if response.status in {403, 429, 503}:
            return True
        snippet = response.text[:32768].lower()
        return any(marker in snippet for marker in OBSERVADOR_BLOCK_MARKERS)

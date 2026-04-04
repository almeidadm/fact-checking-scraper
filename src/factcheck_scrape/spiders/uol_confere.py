from __future__ import annotations

import html
import json
import unicodedata
from typing import Any, Iterable
from urllib.parse import quote

from scrapy import Selector

from .base import BaseFactCheckSpider

CONFERE_INDEX_URL = "https://noticias.uol.com.br/confere/"
SITEMAP_URLS = (
    "https://noticias.uol.com.br/sitemap/v2/news-01.xml",
    "https://noticias.uol.com.br/sitemap/v2/news-02.xml",
    "https://noticias.uol.com.br/sitemap/v2/news-03.xml",
)
SERVICE_BASE_URL = "https://noticias.uol.com.br/service/?loadComponent=results-index&data="
MAX_PAGES = 100
UOL_GENERIC_SUMMARY_PREFIX = "Veja as principais notícias e manchetes do dia no Brasil e no Mundo."
UOL_SUMMARY_SELECTORS = (
    "h2.content-head__subtitle::text",
    ".content-head__subtitle::text",
    "[data-testid='article-subtitle']::text",
)
UOL_TOPIC_SELECTORS = (
    "meta[property='article:section']::attr(content)",
    ".article-topics a::text",
    "[data-testid='article-breadcrumb'] a::text",
)
UOL_TAG_SELECTORS = (
    ".article-tags a::text",
    "[data-testid='article-tags'] a::text",
)
UOL_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Sec-GPC": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}
UOL_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
    **UOL_DEFAULT_HEADERS,
}
UOL_AJAX_HEADERS = {
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": CONFERE_INDEX_URL,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-GPC": "1",
    "Priority": "u=0",
}


class UolConfereSpider(BaseFactCheckSpider):
    name = "uol_confere"
    agency_id = "uol_confere"
    agency_name = "UOL Confere"
    allowed_domains = ["uol.com.br", "noticias.uol.com.br"]
    start_urls = [CONFERE_INDEX_URL]
    handle_httpstatus_list = [403, 404]
    custom_settings = {
        "USER_AGENT": UOL_BROWSER_HEADERS["User-Agent"],
        "DEFAULT_REQUEST_HEADERS": UOL_DEFAULT_HEADERS,
    }
    browser_headers = UOL_BROWSER_HEADERS
    ajax_headers = UOL_AJAX_HEADERS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sitemap_fallback_scheduled = False
        self._seen_next_tokens: set[str] = set()
        self._page_count = 0

    def parse(self, response):
        if response.status == 403:
            if not response.meta.get("retry_with_headers"):
                yield response.request.replace(
                    headers=self.browser_headers,
                    meta={**response.meta, "retry_with_headers": True},
                    dont_filter=True,
                )
                return
            self.logger_struct.warning("index_forbidden", url=response.url)
            yield from self._schedule_sitemap_fallback(response)
            return

        if response.status == 404:
            self.logger_struct.info("index_not_found", url=response.url)
            yield from self._schedule_sitemap_fallback(response)
            return

        links, payload = self._extract_listing(response)
        if not links and payload is None:
            self.logger_struct.warning("index_parse_failed", url=response.url)
            yield from self._schedule_sitemap_fallback(response)
            return

        for loc in links:
            yield response.follow(loc, callback=self.parse_article)

        if payload:
            yield from self._paginate(payload, response)

    def parse_sitemap(self, response):
        if response.status == 403:
            if not response.meta.get("retry_with_headers"):
                yield response.request.replace(
                    headers=self.browser_headers,
                    meta={**response.meta, "retry_with_headers": True},
                    dont_filter=True,
                )
                return
            self.logger_struct.warning("sitemap_forbidden", url=response.url)
            return

        if response.status == 404:
            self.logger_struct.info("sitemap_not_found", url=response.url)
            return

        sitemap_links = response.xpath(
            "//*[local-name()='sitemap']/*[local-name()='loc']/text()"
        ).getall()
        if sitemap_links:
            for loc in sitemap_links:
                yield response.follow(loc, callback=self.parse_sitemap)
            return

        for loc in self._extract_urlset(response):
            if "/confere/" in loc:
                yield response.follow(loc, callback=self.parse_article)

    def _parse_results(self, response):
        if response.status in {403, 404}:
            self.logger_struct.warning(
                "service_response_invalid", url=response.url, status=response.status
            )
            yield from self._schedule_sitemap_fallback(response)
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger_struct.warning("service_response_invalid", url=response.url)
            yield from self._schedule_sitemap_fallback(response)
            return

        body = payload.get("body")
        if not body:
            self.logger_struct.warning("service_response_invalid", url=response.url)
            yield from self._schedule_sitemap_fallback(response)
            return

        selector = Selector(text=body)
        links, next_payload = self._extract_listing(selector)
        if not links and next_payload is None:
            self.logger_struct.warning("index_parse_failed", url=response.url)
            yield from self._schedule_sitemap_fallback(response)
            return

        for loc in links:
            yield response.follow(loc, callback=self.parse_article)

        if next_payload:
            yield from self._paginate(next_payload, response)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
        claim_review = self.pick_jsonld(jsonld_items, "ClaimReview")
        news = self.pick_jsonld(jsonld_items, "NewsArticle", "Article", "WebPage")

        title = self.first_text(
            news.get("headline"),
            news.get("name"),
            claim_review.get("headline"),
            claim_review.get("name"),
            self.meta_first(
                response,
                "meta[property='og:title']::attr(content)",
                "title::text",
            ),
        )
        published_at = self.first_text(
            claim_review.get("datePublished"),
            news.get("datePublished"),
            news.get("dateModified"),
            self.meta_first(
                response,
                "meta[property='article:published_time']::attr(content)",
                "meta[itemprop='datePublished']::attr(content)",
            ),
        )
        canonical_url = self.extract_canonical_url(response, claim_review, news)
        summary = self._extract_summary(response, claim_review, news)
        claim_text = self.first_text(claim_review.get("claimReviewed"), title)
        verdict, rating = self.extract_verdict_and_rating(claim_review)
        verdict = verdict or self.infer_verdict(title, summary)
        rating = rating or verdict
        author = self.extract_author(response, claim_review, news)
        body = self.extract_body(response, claim_review, news)
        language = self.extract_language(response, claim_review, news)
        topics, tags, entities = self._extract_taxonomy(response, claim_review, news)
        source_type = self.extract_source_type(claim_review, news)

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
            claim=claim_text,
            summary=summary,
            verdict=verdict,
            rating=rating,
            author=author,
            body=body,
            language=language,
            country="BR",
            topics=topics,
            tags=tags,
            entities=entities,
            source_type=source_type,
        )

    def _extract_urlset(self, response) -> Iterable[str]:
        return response.xpath("//*[local-name()='url']/*[local-name()='loc']/text()").getall()

    def _extract_listing(self, selector) -> tuple[list[str], dict[str, Any] | None]:
        links: list[str] = []
        seen: set[str] = set()
        for href in selector.css("section.results-index a[href]::attr(href)").getall():
            if "/confere/" not in href:
                continue
            if href in seen:
                continue
            seen.add(href)
            links.append(href)

        payload = None
        data_request = selector.css("button.ver-mais.btn-more::attr(data-request)").get()
        if data_request:
            try:
                data_request = html.unescape(data_request).strip()
                payload = json.loads(data_request)
            except json.JSONDecodeError:
                payload = None

        return links, payload

    def _build_service_url(self, payload: dict[str, Any]) -> str:
        encoded = quote(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return f"{SERVICE_BASE_URL}{encoded}&json"

    def _paginate(self, payload: dict[str, Any], response):
        if not payload.get("hasNext"):
            return

        next_token = payload.get("busca", {}).get("params", {}).get("next")
        if not next_token:
            self.logger_struct.warning("service_response_invalid", url=response.url)
            return
        if next_token in self._seen_next_tokens:
            self.logger_struct.info("pagination_next_seen", next=next_token)
            return
        if self._page_count >= MAX_PAGES:
            self.logger_struct.info("pagination_max_pages_reached", max_pages=MAX_PAGES)
            return

        self._seen_next_tokens.add(next_token)
        self._page_count += 1
        next_url = self._build_service_url(payload)
        yield response.follow(
            next_url,
            callback=self._parse_results,
            headers=self.ajax_headers,
        )

    def _schedule_sitemap_fallback(self, response):
        if self._sitemap_fallback_scheduled:
            return
        self._sitemap_fallback_scheduled = True
        self.logger_struct.info("sitemap_fallback_scheduled", urls=list(SITEMAP_URLS))
        for sitemap_url in SITEMAP_URLS:
            yield response.follow(
                sitemap_url,
                callback=self.parse_sitemap,
                dont_filter=True,
            )

    def _extract_summary(
        self, response, claim_review: dict[str, Any], news: dict[str, Any]
    ) -> str | None:
        summary = self.first_text(
            claim_review.get("reviewBody"),
            self.meta_first(response, *UOL_SUMMARY_SELECTORS),
            news.get("description"),
            self.meta_first(
                response,
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            ),
        )
        if summary and self._is_generic_summary(summary):
            return None
        return summary

    def _extract_taxonomy(
        self,
        response,
        claim_review: dict[str, Any],
        news: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        topics, tags, entities = self.extract_taxonomy(claim_review, news)
        topic_values: list[str] = []
        tag_values: list[str] = []

        for selector in UOL_TOPIC_SELECTORS:
            topic_values.extend(response.css(selector).getall())
        for selector in UOL_TAG_SELECTORS:
            tag_values.extend(response.css(selector).getall())

        tags = self.unique_list(
            tags
            + tag_values
            + self.split_keywords(response.css("meta[name='keywords']::attr(content)").get())
            + self.split_keywords(response.css("meta[name='news_keywords']::attr(content)").get())
        )
        topics = self.unique_list(topics + topic_values)
        return (topics, tags, entities)

    def _is_generic_summary(self, summary: str) -> bool:
        normalized = self.clean_text(summary)
        if not normalized:
            return False
        return self._normalize_summary_text(normalized).startswith(
            self._normalize_summary_text(UOL_GENERIC_SUMMARY_PREFIX)
        )

    def _normalize_summary_text(self, value: str) -> str:
        ascii_only = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        return ascii_only.lower()

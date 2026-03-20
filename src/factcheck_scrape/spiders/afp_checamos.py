from __future__ import annotations

import json
import re
from urllib.parse import urlencode, urljoin, urlsplit

from scrapy import Selector

from .base import BaseFactCheckSpider

AFP_AJAX_URL = "https://checamos.afp.com/views/ajax"
AFP_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0"
AFP_AJAX_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://checamos.afp.com/list",
}
VIEW_DOM_ID_PATTERNS = (
    r'data-view-dom-id=["\']([^"\']+)["\']',
    r'view_dom_id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    r"view-dom-id-([a-zA-Z0-9_-]+)",
)
AFP_ARTICLE_PREFIX = "/doc.afp.com."
AFP_EDITORIAL_PATHS = frozenset(
    {
        "/",
        "/como-trabalhamos",
        "/conheca-equipe",
        "/contato",
        "/configuracoes-de-cookies",
        "/correcoes",
        "/manual-de-estilo-de-verificacao-digital-da-afp",
        "/normas-eticas-e-editoriais-da-afp",
        "/sobre-afp",
    }
)


class AfpChecamosSpider(BaseFactCheckSpider):
    name = "afp_checamos"
    agency_id = "afp_checamos"
    agency_name = "AFP Checamos"
    allowed_domains = ["checamos.afp.com"]
    start_urls = ["https://checamos.afp.com/list"]
    handle_httpstatus_list = [403]
    custom_settings = {"USER_AGENT": AFP_USER_AGENT}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ajax_pages: set[int] = set()

    def parse(self, response):
        if response.status == 403:
            self.logger_struct.warning("afp_list_forbidden", url=response.url)

        for href in self._extract_listing_links(response, response.url):
            yield response.follow(href, callback=self.parse_article)

        ajax_params = self._extract_ajax_params(response)
        if ajax_params:
            request = self._build_ajax_request(response, ajax_params, page=1)
            if request:
                yield request

    def parse_ajax(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger_struct.warning("afp_ajax_invalid_json", url=response.url)
            return

        fragments: list[str] = []
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("data"), str):
                fragments.append(item["data"])
        if not fragments:
            self.logger_struct.warning("afp_ajax_missing_fragments", url=response.url)
            return

        selector = Selector(text="\n".join(fragments))
        for href in self._extract_listing_links(selector, self.start_urls[0]):
            yield response.follow(href, callback=self.parse_article)

        next_page = self._extract_next_page(selector, response.meta.get("page", 1))
        if next_page is None:
            return
        request = self._build_ajax_request(response, response.meta["ajax_params"], next_page)
        if request:
            yield request

    def parse_article(self, response):
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
            country="BR",
            topics=topics,
            tags=tags,
            entities=entities,
            source_type=source_type,
        )

    def _extract_listing_links(self, selector, base_url: str) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        selectors = (
            "article a[href]::attr(href)",
            ".views-row a[href]::attr(href)",
            "a[href*='checamos.afp.com/']::attr(href)",
        )
        for css_selector in selectors:
            for href in selector.css(css_selector).getall():
                absolute = urljoin(base_url, href)
                if not self._is_article_url(absolute):
                    continue
                if absolute in seen:
                    continue
                seen.add(absolute)
                links.append(absolute)
        return links

    def _is_article_url(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.netloc != "checamos.afp.com":
            return False
        if "/views/ajax" in parts.path:
            return False

        normalized_path = parts.path.rstrip("/") or "/"
        if normalized_path.lower() in AFP_EDITORIAL_PATHS:
            return False
        return normalized_path.startswith(AFP_ARTICLE_PREFIX)

    def _extract_ajax_params(self, response) -> dict[str, str] | None:
        body = response.text
        view_dom_id = None
        for pattern in VIEW_DOM_ID_PATTERNS:
            match = re.search(pattern, body)
            if match:
                view_dom_id = match.group(1)
                break
        if not view_dom_id:
            return None

        return {
            "_wrapper_format": "drupal_ajax",
            "view_name": "rubriques",
            "view_display_id": "page_2",
            "view_args": "",
            "view_path": "/list",
            "view_base_path": "list",
            "view_dom_id": view_dom_id,
            "pager_element": "0",
            "_drupal_ajax": "1",
        }

    def _build_ajax_request(self, response, ajax_params: dict[str, str], page: int):
        if page in self._seen_ajax_pages:
            return None
        self._seen_ajax_pages.add(page)
        params = {**ajax_params, "page": str(page)}
        url = f"{AFP_AJAX_URL}?{urlencode(params)}"
        return response.follow(
            url,
            callback=self.parse_ajax,
            headers=AFP_AJAX_HEADERS,
            meta={"page": page, "ajax_params": ajax_params},
        )

    def _extract_next_page(self, selector: Selector, current_page: int) -> int | None:
        if selector.css(".pager__item--next a, a[rel='next']").get():
            return current_page + 1
        for href in selector.css("a[href*='page=']::attr(href)").getall():
            match = re.search(r"[?&]page=(\d+)", href)
            if match:
                next_page = int(match.group(1))
                if next_page > current_page:
                    return next_page
        return None

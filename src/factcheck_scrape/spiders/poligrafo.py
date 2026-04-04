from __future__ import annotations

import re

from .base import BaseFactCheckSpider

MONTHS = {
    "janeiro": "01",
    "fevereiro": "02",
    "marco": "03",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}
POLIGRAFO_USER_AGENT = (
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0"
)


class PoligrafoSpider(BaseFactCheckSpider):
    name = "poligrafo"
    agency_id = "poligrafo"
    agency_name = "Poligrafo"
    allowed_domains = ["poligrafo.sapo.pt"]
    start_urls = ["https://poligrafo.sapo.pt/fact-checks/economia/"]
    custom_settings = {"USER_AGENT": POLIGRAFO_USER_AGENT}

    def parse(self, response):
        for href in self._extract_article_links(response):
            yield response.follow(href, callback=self.parse_article)

        next_url = self.meta_first(
            response,
            "a.page-numbers.next::attr(href)",
            "a[href*='?paged=']::attr(href)",
        )
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_article(self, response):
        title = self.meta_first(
            response,
            "meta[property='og:title']::attr(content)",
            "h1::text",
            "title::text",
        )
        published_at = self._parse_datetime_text(
            self.meta_first(response, ".custom-post-date-time::text")
        )
        canonical_url = self.extract_canonical_url(response)
        summary = self.first_text(
            self.meta_first(
                response,
                ".post-excerpt::text",
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            )
        )
        verdict_selector = "#footer-result .fact-check-result span::text"
        verdict = self.first_text(response.css(verdict_selector).get())
        rating = verdict
        claim = title
        author = self.meta_first(response, "meta[name='author']::attr(content)")
        body = self.extract_body(response)
        language = self.extract_language(response)
        topics = self.unique_list(response.css(".custom-post-categories::text").getall())
        source_type = "fact_check"

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
            tags=[],
            entities=[],
            source_type=source_type,
        )

    def _extract_article_links(self, response) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        hrefs = response.xpath(
            "//div[contains(@class,'elementor-posts-container')]"
            "//a[contains(@href,'/fact-check/')"
            " and following-sibling::div[contains(@class,'listing-post-categories')]"
            "//a[contains(@href,'/fact-checks/economia/')]]/@href"
        ).getall()
        if not hrefs:
            fallback_selector = ".elementor-posts-container a[href*='/fact-check/']::attr(href)"
            hrefs = response.css(fallback_selector).getall()
        for href in hrefs:
            absolute = response.urljoin(href)
            if "__trashed" in absolute:
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def _parse_datetime_text(self, raw: str | None) -> str | None:
        cleaned = self.clean_text(raw)
        if not cleaned:
            return None
        match = re.match(
            r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})"
            r"(?:\s+[àa]s?\s+(\d{1,2}:\d{2}))?",
            cleaned,
            re.IGNORECASE,
        )
        if not match:
            return cleaned
        day = match.group(1).zfill(2)
        month = MONTHS.get(match.group(2).lower())
        year = match.group(3)
        time_str = match.group(4) or "00:00"
        if not month:
            return cleaned
        return f"{year}-{month}-{day}T{time_str}:00"

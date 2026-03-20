from __future__ import annotations

import re
from datetime import datetime

import scrapy

from .base import BaseFactCheckSpider


class BoatosOrgSpider(BaseFactCheckSpider):
    name = "boatos_org"
    agency_id = "boatos_org"
    agency_name = "Boatos.org"
    allowed_domains = ["boatos.org", "www.boatos.org"]

    def start_requests(self):
        current_year = datetime.now().year
        for year in range(2013, current_year + 1):
            url = f"https://www.boatos.org/sitemap-posttype-post.{year}.xml"
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse(self, response):
        yield from self.parse_sitemap(response)

    def parse_sitemap(self, response):
        sitemap_links = response.xpath(
            "//*[local-name()='sitemap']/*[local-name()='loc']/text()"
        ).getall()
        if sitemap_links:
            for loc in sitemap_links:
                yield response.follow(loc, callback=self.parse_sitemap)
            return

        for loc in response.xpath("//*[local-name()='url']/*[local-name()='loc']/text()").getall():
            yield response.follow(loc, callback=self.parse_article)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
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
            article.get("datePublished"),
            self.meta_first(response, "meta[property='article:published_time']::attr(content)"),
            article.get("dateModified"),
        )
        canonical_url = self.extract_canonical_url(response, article)
        summary = self.first_text(
            article.get("description"),
            self.meta_first(
                response,
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            ),
        )
        verdict = self.infer_verdict(title, summary)
        rating = verdict
        claim = self._extract_claim(title, summary)
        language = self.extract_language(response, article)
        topics, tags, entities = self.extract_taxonomy(article)
        source_type = self.extract_source_type(article)

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

    def _extract_claim(self, title: str | None, summary: str | None) -> str | None:
        if not title:
            return summary
        return re.sub(r"\s+#boato\b", "", title, flags=re.IGNORECASE).strip()

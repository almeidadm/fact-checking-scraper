from __future__ import annotations

import re
from typing import Iterable

from .base import BaseFactCheckSpider

SITEMAP_INDEX = "https://g1.globo.com/sitemap/g1/sitemap.xml"
VERDICT_PATTERN = re.compile(r"#?(FAKE|FATO|VERDADE)\b", re.IGNORECASE)


class G1FatoOuFakeSpider(BaseFactCheckSpider):
    name = "g1_fato_ou_fake"
    agency_id = "g1_fato_ou_fake"
    agency_name = "G1 Fato ou Fake"
    allowed_domains = ["g1.globo.com"]
    start_urls = [SITEMAP_INDEX]

    def parse(self, response):
        sitemap_links = response.xpath(
            "//*[local-name()='sitemap']/*[local-name()='loc']/text()"
        ).getall()
        if sitemap_links:
            for loc in sitemap_links:
                yield response.follow(loc, callback=self.parse_sitemap)
            return

        for loc in self._extract_urlset(response):
            if "/fato-ou-fake/" in loc:
                yield response.follow(loc, callback=self.parse_article)

    def parse_sitemap(self, response):
        sitemap_links = response.xpath(
            "//*[local-name()='sitemap']/*[local-name()='loc']/text()"
        ).getall()
        if sitemap_links:
            for loc in sitemap_links:
                yield response.follow(loc, callback=self.parse_sitemap)
            return

        for loc in self._extract_urlset(response):
            if "/fato-ou-fake/" in loc:
                yield response.follow(loc, callback=self.parse_article)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
        article = self.pick_jsonld(jsonld_items, "NewsArticle", "Article", "WebPage")

        title = self.first_text(
            article.get("headline"),
            article.get("name"),
            self._meta_title(response),
        )
        published_at = self.first_text(
            article.get("datePublished"),
            self._meta_published_at(response),
            article.get("dateModified"),
        )
        canonical_url = self.extract_canonical_url(response, article)
        summary = self.first_text(
            article.get("description"),
            self._meta_summary(response),
        )
        verdict = self._extract_verdict(response, title)
        rating = verdict
        claim = self._extract_claim(title, verdict)
        author = self.extract_author(response, article)
        body = self.extract_body(response, article)
        language = self.extract_language(response, article)
        topics, tags, entities = self.extract_taxonomy(article)
        topics = topics or self._extract_topics(response)
        tags = tags or self._extract_tags(response)
        source_type = self.extract_source_type(article) or self._extract_source_type_microdata(
            response
        )

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
            country="BR",
            topics=topics,
            tags=tags,
            entities=entities,
            source_type=source_type,
        )

    def _extract_urlset(self, response) -> Iterable[str]:
        return response.xpath("//*[local-name()='url']/*[local-name()='loc']/text()").getall()

    def _meta_title(self, response) -> str | None:
        return (
            response.css("h1.content-head__title::text").get()
            or response.css("meta[property='og:title']::attr(content)").get()
            or response.css("title::text").get()
        )

    def _meta_published_at(self, response) -> str | None:
        return (
            response.css("meta[itemprop='datePublished']::attr(content)").get()
            or response.css("time[itemprop='datePublished']::attr(datetime)").get()
            or response.css("meta[property='article:published_time']::attr(content)").get()
        )

    def _meta_summary(self, response) -> str | None:
        return (
            response.css("h2.content-head__subtitle::text").get()
            or response.css("meta[itemprop='alternateName']::attr(content)").get()
            or response.css("meta[name='description']::attr(content)").get()
            or response.css("meta[property='og:description']::attr(content)").get()
        )

    def _extract_verdict(self, response, title: str | None) -> str | None:
        candidates = []
        if title:
            candidates.append(title)
        candidates.extend(response.css("strong::text").getall())
        candidates.extend(response.css("meta[property='og:title']::attr(content)").getall())
        for text in candidates:
            if not text:
                continue
            match = VERDICT_PATTERN.search(text)
            if match:
                return match.group(1).upper()
        return None

    def _extract_claim(self, title: str | None, verdict: str | None) -> str | None:
        if not title:
            return None
        cleaned = title.strip()
        if verdict:
            verdict_upper = verdict.upper()
            cleaned = re.sub(
                rf"^\s*(E|É)\s*#?{verdict_upper}\s*(que)?\s*[:\-–—]?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
        return cleaned.strip() if cleaned else None

    def _extract_topics(self, response) -> list[str]:
        topics = response.css("meta[property='article:section']::attr(content)").getall()
        return [topic.strip() for topic in topics if topic and topic.strip()]

    def _extract_tags(self, response) -> list[str]:
        keywords = response.css("meta[name='keywords']::attr(content)").get()
        if not keywords:
            return []
        return [part.strip() for part in keywords.split(",") if part.strip()]

    def _extract_source_type_microdata(self, response) -> str | None:
        itemtype = response.css("main[itemtype]::attr(itemtype)").get()
        if not itemtype:
            return None
        if "/" in itemtype:
            return itemtype.rsplit("/", 1)[-1]
        return itemtype

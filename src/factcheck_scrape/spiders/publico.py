from __future__ import annotations

import re

from .base import BaseFactCheckSpider

SITEMAP_INDEX = "https://www.publico.pt/sitemaps/sitemapindex.xml"


class PublicoSpider(BaseFactCheckSpider):
    name = "publico"
    agency_id = "publico"
    agency_name = "Publico"
    allowed_domains = ["publico.pt", "www.publico.pt"]
    start_urls = [SITEMAP_INDEX]

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
        if "/newsletter/" in response.url:
            return

        if not self._is_prova_dos_factos(response):
            return

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
            article.get("dateCreated"),
            article.get("dateModified"),
            self.meta_first(response, "meta[property='article:published_time']::attr(content)"),
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
        keywords = self.split_keywords(response.css("meta[name='keywords']::attr(content)").get())
        verdict = self.infer_verdict(title, *keywords)
        rating = verdict
        claim = self._extract_claim(title)
        author = self.extract_author(response, article)
        body = self.extract_body(response, article)
        language = self.extract_language(response, article)
        topics, tags, entities = self.extract_taxonomy(article)
        news_keyword_content = response.css("meta[name='news_keywords']::attr(content)").get()
        tags = self.unique_list(tags + keywords + self.split_keywords(news_keyword_content))
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
            author=author,
            body=body,
            language=language,
            country="PT",
            topics=topics,
            tags=tags,
            entities=entities,
            source_type=source_type,
        )

    def _is_prova_dos_factos(self, response) -> bool:
        keywords = self.first_text(
            response.css("meta[name='keywords']::attr(content)").get(),
            response.css("meta[name='news_keywords']::attr(content)").get(),
        )
        if not keywords:
            return False
        return "prova dos factos" in keywords.lower()

    def _extract_claim(self, title: str | None) -> str | None:
        if not title:
            return None
        return re.sub(
            r"\s+(Verdadeiro|Falso|Errado|Impreciso|Verdade,?\s*mas)$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

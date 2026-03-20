from __future__ import annotations

from .base import BaseFactCheckSpider

VERDICT_TERMS = {"Falso", "Verdadeiro", "Impreciso", "Errado", "Verdade, mas"}


class EFarsasSpider(BaseFactCheckSpider):
    name = "e_farsas"
    agency_id = "e_farsas"
    agency_name = "E-farsas"
    allowed_domains = ["e-farsas.com", "www.e-farsas.com"]
    start_urls = ["http://www.e-farsas.com/"]

    def parse(self, response):
        for href in self._extract_article_links(response):
            yield response.follow(href, callback=self.parse_article)

        next_url = (
            response.xpath(
                "//div[contains(@class,'pagination')]//a[contains(., 'Seguinte')]/@href"
            ).get()
            or response.xpath(
                "//div[contains(@class,'pagination')]//a[contains(@href, '/page/')][1]/@href"
            ).get()
        )
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
        article = self.pick_jsonld(jsonld_items, "ClaimReview", "NewsArticle", "Article", "WebPage")

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
        topics, tags, entities = self.extract_taxonomy(article)
        verdict = self.infer_verdict(*(topics + tags + [title, summary]))
        rating = verdict
        topics = [topic for topic in topics if topic not in VERDICT_TERMS]
        claim = title
        language = self.extract_language(response, article)
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

    def _extract_article_links(self, response) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for href in response.css(".mvp-main-blog-text > a[href]::attr(href)").getall():
            absolute = response.urljoin(href)
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

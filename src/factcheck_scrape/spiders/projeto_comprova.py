from __future__ import annotations

import re

from .base import BaseFactCheckSpider

PAGE_RE = re.compile(r"/page/(\d+)/")


class ProjetoComprovaSpider(BaseFactCheckSpider):
    name = "projeto_comprova"
    agency_id = "projeto_comprova"
    agency_name = "Projeto Comprova"
    allowed_domains = ["projetocomprova.com.br"]
    start_urls = ["https://projetocomprova.com.br/?filter=verificacao"]

    def parse(self, response):
        for href in self._extract_article_links(response):
            yield response.follow(href, callback=self.parse_article)

        next_url = self._extract_next_page(response)
        if next_url:
            yield response.follow(next_url, callback=self.parse)

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
        )
        canonical_url = self.extract_canonical_url(response, claim_review, article)
        verdict_text, rating = self.extract_verdict_and_rating(claim_review)
        verdict_context = self.extract_text_after_colon(verdict_text)
        summary = self.first_text(
            claim_review.get("reviewBody"),
            verdict_context,
            article.get("description"),
            self.meta_first(
                response,
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            ),
        )
        claim = self.first_text(claim_review.get("claimReviewed"), title, summary)
        verdict = self.extract_label_prefix_before_colon(verdict_text) or verdict_text
        verdict = self.infer_verdict(verdict, title, summary) or verdict
        rating = rating or verdict
        language = self.extract_language(response, article, claim_review)
        topics, tags, entities = self.extract_taxonomy(article, claim_review)
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

    def _extract_article_links(self, response) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for href in response.css("a.answer__title__link::attr(href)").getall():
            absolute = response.urljoin(href)
            if "/publica" not in absolute:
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def _extract_next_page(self, response) -> str | None:
        current_page = self._extract_page_number(response.url)
        expected_page = current_page + 1
        for href in response.css(".pagination a[href*='filter=verificacao']::attr(href)").getall():
            absolute = response.urljoin(href)
            if self._extract_page_number(absolute) == expected_page:
                return absolute
        return None

    def _extract_page_number(self, url: str) -> int:
        match = PAGE_RE.search(url)
        if match:
            return int(match.group(1))
        return 1

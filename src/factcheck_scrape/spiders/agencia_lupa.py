from __future__ import annotations

from .base import BaseFactCheckSpider


class AgenciaLupaSpider(BaseFactCheckSpider):
    name = "agencia_lupa"
    agency_id = "agencia_lupa"
    agency_name = "Agencia Lupa"
    allowed_domains = ["agencialupa.org", "www.agencialupa.org"]
    start_urls = ["https://www.agencialupa.org/checagem/"]

    def parse(self, response):
        for href in self._extract_article_links(response):
            yield response.follow(href, callback=self.parse_article)

        next_url = self.meta_first(
            response,
            "link[rel='next']::attr(href)",
            "a.next.page-numbers::attr(href)",
        )
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
        claim_review = self.pick_jsonld(jsonld_items, "ClaimReview")
        article = self.pick_jsonld(jsonld_items, "NewsArticle", "Article", "WebPage")

        title = self.first_text(
            claim_review.get("headline"),
            article.get("headline"),
            claim_review.get("name"),
            article.get("name"),
            self.meta_first(
                response,
                "h1::text",
                "meta[property='og:title']::attr(content)",
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
            claim_review.get("reviewBody"),
            article.get("description"),
            article.get("alternateName"),
            article.get("abstract"),
            self.meta_first(
                response,
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            ),
        )
        verdict, rating = self.extract_verdict_and_rating(claim_review)
        verdict = verdict or self.infer_verdict(title, summary)
        rating = rating or verdict
        claim = self.first_text(
            claim_review.get("claimReviewed"), article.get("claimReviewed"), title, summary
        )
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

    def _extract_article_links(self, response) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        selectors = ("div.archive-body article a.feed-link::attr(href)",)
        for selector in selectors:
            for href in response.css(selector).getall():
                absolute = response.urljoin(href)
                if "/checagem/" not in absolute:
                    continue
                if absolute in seen:
                    continue
                seen.add(absolute)
                links.append(absolute)
        return links

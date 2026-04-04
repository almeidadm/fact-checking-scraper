from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from .base import BaseFactCheckSpider


class AosFatosSpider(BaseFactCheckSpider):
    name = "aos_fatos"
    agency_id = "aos_fatos"
    agency_name = "Aos Fatos"
    allowed_domains = ["aosfatos.org", "www.aosfatos.org"]
    start_urls = ["https://www.aosfatos.org/noticias/?formato=checagem"]

    def parse(self, response):
        for href in self._extract_article_links(response):
            yield response.follow(href, callback=self.parse_article)

        next_url = self._extract_next_page(response)
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
        claim_review = self.pick_jsonld(jsonld_items, "ClaimReview")
        article = self.pick_jsonld(jsonld_items, "NewsArticle", "Article", "Review")

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
        summary = self.first_text(
            claim_review.get("reviewBody"),
            article.get("description"),
            self.meta_first(
                response,
                "meta[name='description']::attr(content)",
                "meta[property='og:description']::attr(content)",
            ),
        )
        claim = self.first_text(claim_review.get("claimReviewed"), title)
        verdict, rating = self.extract_verdict_and_rating(claim_review)
        verdict = self.infer_verdict(verdict, title, summary) or verdict
        rating = rating or verdict
        author = self.extract_author(response, article, claim_review)
        body = self.extract_body(response, article, claim_review)
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
            author=author,
            body=body,
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
        for href in response.css("a[href*='/noticias/']::attr(href)").getall():
            absolute = response.urljoin(href)
            if "/noticias/" not in absolute:
                continue
            if "formato=checagem" in absolute:
                continue
            if absolute.rstrip("/") == "https://www.aosfatos.org/noticias":
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def _extract_next_page(self, response) -> str | None:
        query = parse_qs(urlsplit(response.url).query)
        current_page = int(query.get("page", ["1"])[0])
        expected_page = str(current_page + 1)
        for href in response.css("a[href*='formato=checagem'][href*='page=']::attr(href)").getall():
            absolute = response.urljoin(href)
            href_query = parse_qs(urlsplit(absolute).query)
            if href_query.get("formato") != ["checagem"]:
                continue
            if href_query.get("page") == [expected_page]:
                return absolute
        return None

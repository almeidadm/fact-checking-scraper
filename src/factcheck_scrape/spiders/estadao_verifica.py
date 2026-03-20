from __future__ import annotations

from .base import BaseFactCheckSpider

SITEMAP_INDEX = "https://www.estadao.com.br/arc/outboundfeeds/sitemap-index-by-day/?outputType=xml"


class EstadaoVerificaSpider(BaseFactCheckSpider):
    name = "estadao_verifica"
    agency_id = "estadao_verifica"
    agency_name = "Estadao Verifica"
    allowed_domains = ["estadao.com.br"]
    start_urls = [SITEMAP_INDEX]

    def parse(self, response):
        sitemap_links = response.xpath(
            "//*[local-name()='sitemap']/*[local-name()='loc']/text()"
        ).getall()
        if not sitemap_links:
            self.logger_struct.warning("sitemap_index_empty", url=response.url)
        for loc in sitemap_links:
            yield response.follow(loc, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='url']/*[local-name()='loc']/text()").getall()
        for loc in urls:
            if "/estadao-verifica/" in loc:
                yield response.follow(loc, callback=self.parse_article)

    def parse_article(self, response):
        jsonld_items = self.extract_jsonld(response)
        claim_review = self.pick_jsonld(jsonld_items, "ClaimReview")
        article = self.pick_jsonld(jsonld_items, "NewsArticle", "Report", "Article", "WebPage")

        title = self.first_text(
            claim_review.get("headline"),
            article.get("headline"),
            claim_review.get("name"),
            article.get("name"),
            self.meta_first(
                response,
                "meta[property='og:title']::attr(content)",
                "title::text",
            ),
        )
        published_at = self.first_text(
            claim_review.get("datePublished"),
            article.get("datePublished"),
            article.get("dateModified"),
            article.get("dateCreated"),
            self.meta_first(response, "meta[property='article:published_time']::attr(content)"),
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
        claim = self.first_text(claim_review.get("claimReviewed"), summary)
        verdict, rating = self.extract_verdict_and_rating(claim_review)
        verdict = verdict or self.infer_verdict(title, summary)
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
            title=title,
            published_at=published_at,
            canonical_url=canonical_url,
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

import json
from urllib.parse import parse_qs, unquote, urlparse

from scrapy import Selector

from factcheck_scrape.spiders.uol_confere import SITEMAP_URLS, UolConfereSpider
from tests.helpers import make_html_response


def test_extract_listing_filters_confere_and_parses_payload():
    html = """
    <section class="results-index">
      <a href="https://noticias.uol.com.br/confere/ultimas-noticias/2026/02/25/teste.htm">Confere</a>
      <a href="https://www.uol.com.br/tilt/noticias/redacao/2026/02/26/outro.htm">Outro</a>
      <button class="btn-search align-center ver-mais btn-more btn btn-large btn-primary"
        data-request='{"history":false,"busca":{"params":{"next":"ABC"}},"hasNext":true}'>
        ver mais
      </button>
    </section>
    """
    selector = Selector(text=html)
    spider = UolConfereSpider()

    links, payload = spider._extract_listing(selector)

    assert links == ["https://noticias.uol.com.br/confere/ultimas-noticias/2026/02/25/teste.htm"]
    assert payload is not None
    assert payload["busca"]["params"]["next"] == "ABC"


def test_build_service_url_encodes_payload():
    spider = UolConfereSpider()
    payload = {
        "history": False,
        "busca": {"params": {"next": "0001TEST"}},
        "hasNext": True,
    }

    url = spider._build_service_url(payload)

    assert url.startswith("https://noticias.uol.com.br/service/?loadComponent=results-index&data=")
    assert url.endswith("&json")

    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    assert qs["loadComponent"] == ["results-index"]
    data_value = qs["data"][0]
    assert json.loads(unquote(data_value)) == payload


def test_schedule_sitemap_fallback_uses_known_news_sitemaps_once():
    spider = UolConfereSpider()
    response = make_html_response(spider.start_urls[0], "<html></html>")

    requests = list(spider._schedule_sitemap_fallback(response))

    assert [request.url for request in requests] == list(SITEMAP_URLS)
    assert all(request.callback == spider.parse_sitemap for request in requests)
    assert list(spider._schedule_sitemap_fallback(response)) == []

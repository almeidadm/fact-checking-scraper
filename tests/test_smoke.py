"""Smoke tests that make real HTTP requests to fact-checking sites.

These tests verify that each spider can still parse at least one real article
from its target site, detecting layout changes before they affect full runs.

Run with: pytest --run-smoke -m smoke
"""

from __future__ import annotations

import pytest
import scrapy
from scrapy import Request
from scrapy.http import HtmlResponse

from factcheck_scrape.spiders.afp_checamos import AfpChecamosSpider
from factcheck_scrape.spiders.agencia_lupa import AgenciaLupaSpider
from factcheck_scrape.spiders.aosfatos import AosFatosSpider
from factcheck_scrape.spiders.boatos_org import BoatosOrgSpider
from factcheck_scrape.spiders.e_farsas import EFarsasSpider
from factcheck_scrape.spiders.estadao_verifica import EstadaoVerificaSpider
from factcheck_scrape.spiders.g1_fato_ou_fake import G1FatoOuFakeSpider
from factcheck_scrape.spiders.poligrafo import PoligrafoSpider
from factcheck_scrape.spiders.projeto_comprova import ProjetoComprovaSpider
from factcheck_scrape.spiders.publico import PublicoSpider


def _fetch_url(url: str, *, headers: dict | None = None) -> HtmlResponse:
    """Fetch a URL synchronously for smoke testing."""
    import urllib.request

    default_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    if headers:
        default_headers.update(headers)

    req = urllib.request.Request(url, headers=default_headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        final_url = resp.url

    return HtmlResponse(
        url=final_url,
        request=Request(url=final_url),
        body=body,
        encoding="utf-8",
    )


def _items(results) -> list[dict]:
    return [r for r in results if isinstance(r, dict)]


def _assert_smoke_item(item: dict, spider_name: str):
    """Verify minimum viable extraction: title and published_at must be present."""
    assert item.get("title"), f"{spider_name}: title is empty"
    assert item.get("published_at"), f"{spider_name}: published_at is empty"
    assert item.get("source_url"), f"{spider_name}: source_url is empty"
    assert item.get("canonical_url"), f"{spider_name}: canonical_url is empty"


# ---------------------------------------------------------------------------
# Smoke tests — one real article per agency
# ---------------------------------------------------------------------------
# These URLs should be stable, long-lived articles from each agency.
# If a test fails, check if the article was removed or the site redesigned.

SMOKE_ARTICLES = [
    pytest.param(
        AgenciaLupaSpider,
        "https://www.agencialupa.org/checagem/2024/11/21/video-mostra-policial-federal-dando-tapas-em-cara-de-mulher-em-pf-de-brasilia/",
        id="agencia_lupa",
    ),
    pytest.param(
        AosFatosSpider,
        "https://www.aosfatos.org/noticias/falso-papa-francisco-doou-dinheiro-vitimas-enchentes-rs/",
        id="aos_fatos",
    ),
    pytest.param(
        BoatosOrgSpider,
        "https://www.boatos.org/politica/lula-decidiu-doar-10-milhoes-de-reais-a-maduro-da-venezuela.html",
        id="boatos_org",
    ),
    pytest.param(
        EFarsasSpider,
        "https://www.e-farsas.com/fenomeno-miraclein-em-fevereiro-de-2026-so-acontece-a-cada-823-anos.html",
        id="e_farsas",
    ),
    pytest.param(
        EstadaoVerificaSpider,
        "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial/",
        id="estadao_verifica",
    ),
    pytest.param(
        G1FatoOuFakeSpider,
        "https://g1.globo.com/fato-ou-fake/noticia/2025/10/27/e-fake-video-que-mostra-mulher-com-sapatos-voadores-em-exposicao.ghtml",
        id="g1_fato_ou_fake",
    ),
    pytest.param(
        PoligrafoSpider,
        "https://poligrafo.sapo.pt/fact-check/esta-tabela-com-valores-de-salarios-minimos-em-varios-paises-europeus-esta-correta/",
        id="poligrafo",
    ),
    pytest.param(
        ProjetoComprovaSpider,
        "https://projetocomprova.com.br/publicacoes/e-falso-que-alimentos-com-selo-da-ra-sejam-sinteticos-e-produzidos-por-bill-gates/",
        id="projeto_comprova",
    ),
    pytest.param(
        PublicoSpider,
        "https://www.publico.pt/2026/03/03/politica/noticia/economia-portuguesa-representa-menos-2-pib-europeu-afirmou-passos-coelho-verdadeiro-2166654",
        id="publico",
    ),
    pytest.param(
        AfpChecamosSpider,
        "https://checamos.afp.com/doc.afp.com.34YC4RP",
        id="afp_checamos",
    ),
]


@pytest.mark.smoke
@pytest.mark.parametrize("spider_cls,url", SMOKE_ARTICLES)
def test_smoke_parse_article(spider_cls, url):
    """Fetch a real article and verify the spider extracts title and published_at."""
    spider = spider_cls()

    try:
        response = _fetch_url(url)
    except Exception as exc:
        pytest.skip(f"Could not fetch {url}: {exc}")

    items = _items(list(spider.parse_article(response)))

    assert len(items) >= 1, f"{spider.name}: parse_article returned no items for {url}"
    _assert_smoke_item(items[0], spider.name)

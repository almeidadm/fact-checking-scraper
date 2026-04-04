"""Edge-case tests for spider parse_article methods.

Covers: missing JSON-LD, missing required fields, author/body extraction,
challenge pages, malformed JSON-LD, and fallback logic.
"""

from __future__ import annotations

# ruff: noqa: E501

import pytest
from scrapy import Request
from scrapy.http import HtmlResponse

from factcheck_scrape.spiders.afp_checamos import AfpChecamosSpider
from factcheck_scrape.spiders.agencia_lupa import AgenciaLupaSpider
from factcheck_scrape.spiders.aosfatos import AosFatosSpider
from factcheck_scrape.spiders.boatos_org import BoatosOrgSpider
from factcheck_scrape.spiders.e_farsas import EFarsasSpider
from factcheck_scrape.spiders.estadao_verifica import EstadaoVerificaSpider
from factcheck_scrape.spiders.g1_fato_ou_fake import G1FatoOuFakeSpider
from factcheck_scrape.spiders.observador import ObservadorSpider
from factcheck_scrape.spiders.poligrafo import PoligrafoSpider
from factcheck_scrape.spiders.projeto_comprova import ProjetoComprovaSpider
from factcheck_scrape.spiders.publico import PublicoSpider
from factcheck_scrape.spiders.reuters_fact_check import ReutersFactCheckSpider
from factcheck_scrape.spiders.uol_confere import UolConfereSpider
from tests.helpers import make_html_response


def _items(results) -> list[dict]:
    return [r for r in results if isinstance(r, dict)]


# ---------------------------------------------------------------------------
# 1. Articles WITHOUT JSON-LD — fallback to meta tags / CSS selectors
# ---------------------------------------------------------------------------

ARTICLE_NO_JSONLD = """
<html lang="pt-BR">
  <head>
    <title>Titulo do artigo sem JSON-LD</title>
    <meta property="og:title" content="Titulo do artigo sem JSON-LD" />
    <meta property="article:published_time" content="2026-04-01T10:00:00+00:00" />
    <meta name="description" content="Resumo do artigo." />
    <meta name="keywords" content="teste,edge-case" />
    <meta name="author" content="Autor Teste" />
    <link rel="canonical" href="https://example.com/article-no-jsonld" />
  </head>
  <body>
    <h1>Titulo do artigo sem JSON-LD</h1>
    <article><p>Paragrafo do corpo do artigo.</p></article>
  </body>
</html>
"""


@pytest.mark.parametrize(
    "spider_cls,url",
    [
        (AgenciaLupaSpider, "https://www.agencialupa.org/checagem/2026/04/01/artigo-sem-jsonld/"),
        (BoatosOrgSpider, "https://www.boatos.org/test/artigo-sem-jsonld.html"),
        (EFarsasSpider, "https://www.e-farsas.com/artigo-sem-jsonld.html"),
    ],
    ids=["agencia_lupa", "boatos_org", "e_farsas"],
)
def test_parse_article_without_jsonld_extracts_from_meta(spider_cls, url):
    """Spiders with meta tag fallbacks for published_at should extract without JSON-LD."""
    spider = spider_cls()
    response = make_html_response(url, ARTICLE_NO_JSONLD)

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["title"] == "Titulo do artigo sem JSON-LD"
    assert items[0]["published_at"] == "2026-04-01T10:00:00+00:00"
    assert items[0]["author"] == "Autor Teste"


@pytest.mark.parametrize(
    "spider_cls,url",
    [
        (AosFatosSpider, "https://www.aosfatos.org/noticias/artigo-sem-jsonld/"),
        (ProjetoComprovaSpider, "https://projetocomprova.com.br/publicacoes/artigo-sem-jsonld/"),
    ],
    ids=["aos_fatos", "projeto_comprova"],
)
def test_parse_article_without_jsonld_drops_when_no_date_fallback(spider_cls, url):
    """Spiders without meta tag fallback for published_at should drop items missing JSON-LD dates."""
    spider = spider_cls()
    response = make_html_response(url, ARTICLE_NO_JSONLD)

    items = _items(list(spider.parse_article(response)))
    assert items == []


def test_g1_parse_article_without_jsonld_extracts_from_microdata():
    spider = G1FatoOuFakeSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="E #FAKE que item sem jsonld" />
        <meta itemprop="datePublished" content="2026-04-01T12:00:00+00:00" />
        <meta name="description" content="Resumo do fake." />
        <link rel="canonical" href="https://g1.globo.com/fato-ou-fake/noticia/2026/04/01/item.ghtml" />
      </head>
      <body>
        <main itemscope itemtype="http://schema.org/NewsArticle">
          <h1 class="content-head__title">E #FAKE que item sem jsonld</h1>
        </main>
      </body>
    </html>
    """
    response = make_html_response(
        "https://g1.globo.com/fato-ou-fake/noticia/2026/04/01/item.ghtml", html
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["title"] == "E #FAKE que item sem jsonld"
    assert items[0]["verdict"] == "FAKE"
    assert items[0]["source_type"] == "NewsArticle"


# ---------------------------------------------------------------------------
# 2. Articles with MISSING required fields — should be dropped
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "spider_cls,url",
    [
        (AgenciaLupaSpider, "https://www.agencialupa.org/checagem/2026/04/01/no-title/"),
        (AosFatosSpider, "https://www.aosfatos.org/noticias/no-title/"),
        (EFarsasSpider, "https://www.e-farsas.com/no-title.html"),
        (EstadaoVerificaSpider, "https://www.estadao.com.br/estadao-verifica/no-title/"),
        (G1FatoOuFakeSpider, "https://g1.globo.com/fato-ou-fake/noticia/2026/04/01/no-title.ghtml"),
        (UolConfereSpider, "https://noticias.uol.com.br/confere/ultimas-noticias/2026/04/01/no-title.htm"),
    ],
    ids=["lupa", "aosfatos", "efarsas", "estadao", "g1", "uol"],
)
def test_parse_article_drops_missing_title(spider_cls, url):
    spider = spider_cls()
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="article:published_time" content="2026-04-01T10:00:00+00:00" />
        <link rel="canonical" href="{url}" />
      </head>
      <body></body>
    </html>
    """.format(url=url)
    response = make_html_response(url, html)

    items = _items(list(spider.parse_article(response)))
    assert items == []


@pytest.mark.parametrize(
    "spider_cls,url",
    [
        (AgenciaLupaSpider, "https://www.agencialupa.org/checagem/2026/04/01/no-date/"),
        (AosFatosSpider, "https://www.aosfatos.org/noticias/no-date/"),
        (BoatosOrgSpider, "https://www.boatos.org/test/no-date.html"),
        (G1FatoOuFakeSpider, "https://g1.globo.com/fato-ou-fake/noticia/2026/04/01/no-date.ghtml"),
    ],
    ids=["lupa", "aosfatos", "boatos", "g1"],
)
def test_parse_article_drops_missing_published_at(spider_cls, url):
    spider = spider_cls()
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="Artigo sem data" />
        <link rel="canonical" href="{url}" />
      </head>
      <body><h1>Artigo sem data</h1></body>
    </html>
    """.format(url=url)
    response = make_html_response(url, html)

    items = _items(list(spider.parse_article(response)))
    assert items == []


def test_parse_article_drops_placeholder_published_at():
    spider = G1FatoOuFakeSpider()
    url = "https://g1.globo.com/fato-ou-fake/noticia/2026/04/01/placeholder.ghtml"
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="E #FAKE artigo com data placeholder" />
        <meta itemprop="datePublished" content="-" />
        <link rel="canonical" href="{url}" />
      </head>
      <body><h1 class="content-head__title">E #FAKE artigo com data placeholder</h1></body>
    </html>
    """.format(url=url)
    response = make_html_response(url, html)

    items = _items(list(spider.parse_article(response)))
    assert items == []


# ---------------------------------------------------------------------------
# 3. Articles WITH author and body in JSON-LD
# ---------------------------------------------------------------------------

ARTICLE_WITH_AUTHOR_BODY = """
<html lang="pt-BR">
  <head>
    <link rel="canonical" href="https://example.com/with-author" />
    <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Artigo com autor e corpo",
        "datePublished": "2026-04-01T10:00:00+00:00",
        "description": "Resumo do artigo com autor.",
        "url": "https://example.com/with-author",
        "author": {{"@type": "Person", "name": "{author}"}},
        "articleBody": "Este e o corpo completo do artigo de fact-checking.",
        "inLanguage": "pt-BR"
      }}
    </script>
  </head>
  <body>
    <h1>Artigo com autor e corpo</h1>
    <article><p>Este e o corpo completo do artigo de fact-checking.</p></article>
  </body>
</html>
"""


@pytest.mark.parametrize(
    "spider_cls,url,author",
    [
        (AgenciaLupaSpider, "https://www.agencialupa.org/checagem/2026/04/01/with-author/", "Maria Silva"),
        (AosFatosSpider, "https://www.aosfatos.org/noticias/with-author/", "Joao Santos"),
        (EstadaoVerificaSpider, "https://www.estadao.com.br/estadao-verifica/with-author/", "Carlos Ferreira"),
        (ProjetoComprovaSpider, "https://projetocomprova.com.br/publicacoes/with-author/", "Ana Souza"),
    ],
    ids=["lupa", "aosfatos", "estadao", "comprova"],
)
def test_parse_article_extracts_author_from_jsonld(spider_cls, url, author):
    spider = spider_cls()
    html = ARTICLE_WITH_AUTHOR_BODY.format(author=author)
    response = make_html_response(url, html)

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["author"] == author
    assert items[0]["body"] == "Este e o corpo completo do artigo de fact-checking."


def test_parse_article_extracts_multiple_authors():
    spider = AgenciaLupaSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <link rel="canonical" href="https://www.agencialupa.org/checagem/2026/04/01/multi-author/" />
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": "Artigo com multiplos autores",
            "datePublished": "2026-04-01T10:00:00+00:00",
            "description": "Verificacao conjunta.",
            "url": "https://www.agencialupa.org/checagem/2026/04/01/multi-author/",
            "author": [
              {"@type": "Person", "name": "Maria Silva"},
              {"@type": "Person", "name": "Joao Santos"}
            ],
            "inLanguage": "pt-BR"
          }
        </script>
      </head>
      <body><h1>Artigo com multiplos autores</h1></body>
    </html>
    """
    response = make_html_response(
        "https://www.agencialupa.org/checagem/2026/04/01/multi-author/", html
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["author"] == "Maria Silva, Joao Santos"


def test_parse_article_extracts_body_from_css_when_no_jsonld_body():
    spider = BoatosOrgSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <link rel="canonical" href="https://www.boatos.org/test/body-css.html" />
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": "Boato sobre corpo CSS #boato",
            "datePublished": "2026-04-01T10:00:00+00:00",
            "description": "Resumo do boato.",
            "inLanguage": "pt-BR"
          }
        </script>
      </head>
      <body>
        <article>
          <p>Primeiro paragrafo do artigo.</p>
          <p>Segundo paragrafo com mais detalhes.</p>
        </article>
      </body>
    </html>
    """
    response = make_html_response("https://www.boatos.org/test/body-css.html", html)

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["body"] == "Primeiro paragrafo do artigo. Segundo paragrafo com mais detalhes."


# ---------------------------------------------------------------------------
# 4. Challenge / blocked pages — should yield nothing
# ---------------------------------------------------------------------------

CLOUDFLARE_CHALLENGE = '<html><title>Just a moment...</title><body>Checking your browser</body></html>'
BLOCKED_401 = "<html><title>blocked</title></html>"


def test_observador_drops_challenge_page_on_article():
    spider = ObservadorSpider()
    response = make_html_response(
        "https://observador.pt/factchecks/fact-check-example/", CLOUDFLARE_CHALLENGE
    )
    assert _items(list(spider.parse_article(response))) == []


def test_observador_drops_challenge_page_on_listing():
    spider = ObservadorSpider()
    response = make_html_response(
        "https://observador.pt/factchecks/", CLOUDFLARE_CHALLENGE
    )
    results = list(spider.parse(response))
    assert results == []


def test_reuters_drops_blocked_401():
    spider = ReutersFactCheckSpider()
    response = HtmlResponse(
        url="https://www.reuters.com/fact-check/portugues/blocked-article/",
        request=Request(
            url="https://www.reuters.com/fact-check/portugues/blocked-article/",
            meta={"scrapling": {"enabled": True}},
        ),
        body=BLOCKED_401.encode("utf-8"),
        status=401,
        encoding="utf-8",
    )
    assert _items(list(spider.parse_article(response))) == []


def test_reuters_drops_challenge_page_on_listing():
    spider = ReutersFactCheckSpider()
    response = make_html_response(
        "https://www.reuters.com/fact-check/portugues/",
        '<html><body>Attention Required! /cdn-cgi/challenge-platform/</body></html>',
    )
    results = list(spider.parse(response))
    assert results == []


def test_reuters_drops_blocked_api_response():
    spider = ReutersFactCheckSpider()
    response = HtmlResponse(
        url="https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?query=test",
        request=Request(
            url="https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?query=test",
            meta={"scrapling": {"enabled": True}, "offset": 0},
        ),
        body=b"<html><title>blocked</title></html>",
        status=403,
        encoding="utf-8",
    )
    assert _items(list(spider.parse_api(response))) == []


def test_observador_drops_403_challenge():
    spider = ObservadorSpider()
    response = HtmlResponse(
        url="https://observador.pt/factchecks/fact-check-example/",
        request=Request(url="https://observador.pt/factchecks/fact-check-example/"),
        body=b"<html><title>Forbidden</title></html>",
        status=403,
        encoding="utf-8",
    )
    assert _items(list(spider.parse_article(response))) == []


# ---------------------------------------------------------------------------
# 5. Malformed JSON-LD — should not crash, fallback gracefully
# ---------------------------------------------------------------------------

def test_parse_article_handles_malformed_jsonld():
    spider = AgenciaLupaSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="Artigo com JSON-LD quebrado" />
        <meta property="article:published_time" content="2026-04-01T10:00:00+00:00" />
        <meta name="description" content="Resumo." />
        <link rel="canonical" href="https://www.agencialupa.org/checagem/2026/04/01/jsonld-quebrado/" />
        <script type="application/ld+json">
          { this is not valid json }
        </script>
      </head>
      <body><h1>Artigo com JSON-LD quebrado</h1></body>
    </html>
    """
    response = make_html_response(
        "https://www.agencialupa.org/checagem/2026/04/01/jsonld-quebrado/", html
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["title"] == "Artigo com JSON-LD quebrado"
    assert items[0]["published_at"] == "2026-04-01T10:00:00+00:00"


def test_parse_article_handles_empty_jsonld_script():
    spider = EstadaoVerificaSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="Artigo com JSON-LD vazio" />
        <meta property="article:published_time" content="2026-04-01T10:00:00+00:00" />
        <meta name="description" content="Resumo." />
        <link rel="canonical" href="https://www.estadao.com.br/estadao-verifica/jsonld-vazio/" />
        <script type="application/ld+json">  </script>
      </head>
      <body><h1>Artigo com JSON-LD vazio</h1></body>
    </html>
    """
    response = make_html_response(
        "https://www.estadao.com.br/estadao-verifica/jsonld-vazio/", html
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["title"] == "Artigo com JSON-LD vazio"


# ---------------------------------------------------------------------------
# 6. Poligrafo date parsing edge cases
# ---------------------------------------------------------------------------

def test_poligrafo_parses_date_with_accent():
    spider = PoligrafoSpider()
    html = """
    <html lang="pt-PT">
      <head>
        <meta property="og:title" content="Artigo poligrafo com acento" />
        <link rel="canonical" href="https://poligrafo.sapo.pt/fact-check/artigo-acento/" />
        <meta name="description" content="Resumo." />
      </head>
      <body>
        <div class="custom-post-date-time">5 de Janeiro de 2026 às 14:30</div>
        <div id="footer-result"><div class="fact-check-result"><span>Falso</span></div></div>
        <h1>Artigo poligrafo com acento</h1>
      </body>
    </html>
    """
    response = make_html_response(
        "https://poligrafo.sapo.pt/fact-check/artigo-acento/", html
    )
    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["published_at"] == "2026-01-05T14:30:00"


def test_poligrafo_parses_date_without_accent():
    spider = PoligrafoSpider()
    html = """
    <html lang="pt-PT">
      <head>
        <meta property="og:title" content="Artigo poligrafo sem acento" />
        <link rel="canonical" href="https://poligrafo.sapo.pt/fact-check/artigo-sem-acento/" />
        <meta name="description" content="Resumo." />
      </head>
      <body>
        <div class="custom-post-date-time">11 de Marco de 2026 as 15:00</div>
        <div id="footer-result"><div class="fact-check-result"><span>Verdadeiro</span></div></div>
        <h1>Artigo poligrafo sem acento</h1>
      </body>
    </html>
    """
    response = make_html_response(
        "https://poligrafo.sapo.pt/fact-check/artigo-sem-acento/", html
    )
    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["published_at"] == "2026-03-11T15:00:00"


def test_poligrafo_parses_date_without_time():
    spider = PoligrafoSpider()
    html = """
    <html lang="pt-PT">
      <head>
        <meta property="og:title" content="Artigo sem hora" />
        <link rel="canonical" href="https://poligrafo.sapo.pt/fact-check/sem-hora/" />
        <meta name="description" content="Resumo." />
      </head>
      <body>
        <div class="custom-post-date-time">25 de Dezembro de 2025</div>
        <div id="footer-result"><div class="fact-check-result"><span>Falso</span></div></div>
        <h1>Artigo sem hora</h1>
      </body>
    </html>
    """
    response = make_html_response(
        "https://poligrafo.sapo.pt/fact-check/sem-hora/", html
    )
    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["published_at"] == "2025-12-25T00:00:00"


# ---------------------------------------------------------------------------
# 7. Title matches URL — should be dropped
# ---------------------------------------------------------------------------

def test_parse_article_drops_title_matching_url():
    spider = AosFatosSpider()
    url = "https://www.aosfatos.org/noticias/title-is-url/"
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="{url}" />
        <meta property="article:published_time" content="2026-04-01T10:00:00+00:00" />
        <link rel="canonical" href="{url}" />
        <script type="application/ld+json">
          {{
            "@type": "NewsArticle",
            "headline": "{url}",
            "datePublished": "2026-04-01T10:00:00+00:00"
          }}
        </script>
      </head>
      <body></body>
    </html>
    """.format(url=url)
    response = make_html_response(url, html)

    items = _items(list(spider.parse_article(response)))
    assert items == []


# ---------------------------------------------------------------------------
# 8. UOL Confere — generic summary rejection
# ---------------------------------------------------------------------------

def test_uol_confere_returns_null_for_generic_summary_with_accents():
    spider = UolConfereSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <title>Artigo real do UOL</title>
        <meta name="description" content="Veja as principais notícias e manchetes do dia no Brasil e no Mundo." />
        <meta property="og:description" content="Veja as principais notícias e manchetes do dia no Brasil e no Mundo." />
        <link rel="canonical" href="https://noticias.uol.com.br/confere/ultimas-noticias/2026/04/01/generic.htm" />
        <script type="application/ld+json">
          {
            "@type": "NewsArticle",
            "headline": "Artigo real do UOL",
            "datePublished": "2026-04-01T10:00:00.000Z",
            "description": "Veja as principais notícias e manchetes do dia no Brasil e no Mundo."
          }
        </script>
        <script type="application/ld+json">
          {
            "@type": "ClaimReview",
            "datePublished": "2026-04-01T10:00:00.000Z",
            "claimReviewed": "Boato antigo viraliza novamente",
            "reviewRating": {"@type": "Rating", "alternateName": "Falso", "ratingValue": "1"}
          }
        </script>
      </head>
      <body><h1>Artigo real do UOL</h1></body>
    </html>
    """
    response = make_html_response(
        "https://noticias.uol.com.br/confere/ultimas-noticias/2026/04/01/generic.htm", html
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["summary"] is None
    assert items[0]["verdict"] == "Falso"


# ---------------------------------------------------------------------------
# 9. AFP editorial page rejection
# ---------------------------------------------------------------------------

def test_afp_drops_editorial_page_that_lacks_title():
    spider = AfpChecamosSpider()
    html = """
    <html lang="pt-BR">
      <head>
        <meta property="og:title" content="" />
        <link rel="canonical" href="https://checamos.afp.com/como-trabalhamos" />
      </head>
      <body></body>
    </html>
    """
    response = make_html_response("https://checamos.afp.com/como-trabalhamos", html)

    items = _items(list(spider.parse_article(response)))
    assert items == []


# ---------------------------------------------------------------------------
# 10. Publico — rejects non "prova dos factos" articles
# ---------------------------------------------------------------------------

def test_publico_rejects_article_without_prova_keyword():
    spider = PublicoSpider()
    html = """
    <html lang="pt">
      <head>
        <meta name="keywords" content="Economia,Portugal" />
        <meta property="og:title" content="Artigo de economia normal" />
        <meta property="article:published_time" content="2026-04-01T10:00:00+00:00" />
        <script type="application/ld+json">
          {
            "@type": "NewsArticle",
            "headline": "Artigo de economia normal",
            "datePublished": "2026-04-01T10:00:00+00:00"
          }
        </script>
      </head>
      <body><h1>Artigo de economia normal</h1></body>
    </html>
    """
    response = make_html_response(
        "https://www.publico.pt/2026/04/01/economia/noticia/artigo-normal-2170000", html
    )

    items = _items(list(spider.parse_article(response)))
    assert items == []

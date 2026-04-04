from __future__ import annotations

# ruff: noqa: E501
# Long string literals here keep expected payloads and inline HTML fixtures exact and readable.
from datetime import datetime

import pytest
from scrapy import Request
from scrapy.http import HtmlResponse

from factcheck_scrape.runner import list_spiders
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
from tests.helpers import load_fixture, make_html_response, make_text_response


def _request_urls(results) -> list[str]:
    return [result.url for result in results if isinstance(result, Request)]


def _items(results) -> list[dict]:
    return [result for result in results if isinstance(result, dict)]


def _assert_item_fields(item: dict, expected: dict) -> None:
    for key, value in expected.items():
        assert item[key] == value


ARTICLE_CASES = [
    pytest.param(
        AgenciaLupaSpider,
        "agencia_lupa",
        "article.html",
        "https://www.agencialupa.org/checagem/2026/01/06/maduro-drogas-e-petroleo-o-que-e-fato-no-discurso-de-trump/",
        {
            "source_url": "https://www.agencialupa.org/checagem/2026/01/06/maduro-drogas-e-petroleo-o-que-e-fato-no-discurso-de-trump/",
            "canonical_url": "https://www.agencialupa.org/checagem/2026/01/06/maduro-drogas-e-petroleo-o-que-e-fato-no-discurso-de-trump",
            "title": "Maduro, drogas e petroleo: o que e fato no discurso de Trump",
            "published_at": "2026-01-06T17:48:21+00:00",
            "claim": "Maduro, drogas e petroleo: o que e fato no discurso de Trump",
            "summary": "Presidente dos Estados Unidos fez afirmacoes sem provas ou sem contexto sobre os ataques a Venezuela.",
            "verdict": None,
            "rating": None,
            "country": "BR",
            "topics": ["Checagem"],
            "tags": ["Donald Trump", "Nicolas Maduro", "Venezuela"],
            "entities": [],
            "source_type": "NewsArticle",
        },
        id="agencia_lupa",
    ),
    pytest.param(
        AosFatosSpider,
        "aos_fatos",
        "article.html",
        "https://www.aosfatos.org/noticias/nao-verdade-foto-mostra-missil-iraniano-mensagem-vitimas-epstein/",
        {
            "source_url": "https://www.aosfatos.org/noticias/nao-verdade-foto-mostra-missil-iraniano-mensagem-vitimas-epstein/",
            "canonical_url": "https://www.aosfatos.org/noticias/nao-verdade-foto-mostra-missil-iraniano-mensagem-vitimas-epstein",
            "title": "Nao e verdade que foto mostra missil iraniano com mensagem sobre vitimas de Epstein",
            "published_at": "2026-03-13",
            "claim": "Missil iraniano mostra inscricao em persa que faz alusao as vitimas de Epstein",
            "summary": "Foto foi editada pela ferramenta de IA Gemini, do Google.",
            "verdict": "Falso",
            "rating": "1",
            "country": "BR",
            "topics": [],
            "tags": ["inteligencia artificial", "Estados Unidos", "Israel", "Ira"],
            "entities": [],
            "source_type": "Review,ClaimReview",
        },
        id="aos_fatos",
    ),
    pytest.param(
        BoatosOrgSpider,
        "boatos_org",
        "article.html",
        "https://www.boatos.org/saude/perigo-hoax-mamografia-causar-cancer-tireoide.html",
        {
            "source_url": "https://www.boatos.org/saude/perigo-hoax-mamografia-causar-cancer-tireoide.html",
            "canonical_url": "https://www.boatos.org/saude/perigo-hoax-mamografia-causar-cancer-tireoide.html",
            "title": "Mamografia pode causar cancer na tireoide #boato",
            "published_at": "2013-09-11T11:10:49+00:00",
            "claim": "Mamografia pode causar cancer na tireoide",
            "summary": "Boato - O exame de mamografia causaria cancer na tireoide.",
            "verdict": "Falso",
            "rating": "Falso",
            "country": "BR",
            "topics": ["Saude"],
            "tags": [],
            "entities": [],
            "source_type": "NewsArticle",
        },
        id="boatos_org",
    ),
    pytest.param(
        EFarsasSpider,
        "e_farsas",
        "article.html",
        "http://www.e-farsas.com/fenomeno-miraclein-em-fevereiro-de-2026-so-acontece-a-cada-823-anos.html",
        {
            "source_url": "http://www.e-farsas.com/fenomeno-miraclein-em-fevereiro-de-2026-so-acontece-a-cada-823-anos.html",
            "canonical_url": "http://www.e-farsas.com/fenomeno-miraclein-em-fevereiro-de-2026-so-acontece-a-cada-823-anos.html",
            "title": "Fenomeno MiracleIn em fevereiro de 2026 so acontece a cada 823 anos?",
            "published_at": "2026-01-14T10:00:00+00:00",
            "claim": "Fenomeno MiracleIn em fevereiro de 2026 so acontece a cada 823 anos?",
            "summary": "Boato sobre calendario manipulado.",
            "verdict": "Verdadeiro",
            "rating": "Verdadeiro",
            "country": "BR",
            "topics": ["Tecnologia"],
            "tags": [],
            "entities": [],
            "source_type": "Article",
        },
        id="e_farsas",
    ),
    pytest.param(
        EstadaoVerificaSpider,
        "estadao_verifica",
        "article.html",
        "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial/",
        {
            "source_url": "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial/",
            "canonical_url": "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial",
            "title": "Video nao mostra caminhoes com misseis saindo de tunel no Ira; conteudo foi criado com IA",
            "published_at": "2026-03-06T16:58:29.508Z",
            "claim": "Video mostra caminhoes carregados com misseis saindo de tunel no Ira.",
            "summary": "Imagem tem distorcoes caracteristicas de arquivos gerados com inteligencia artificial",
            "verdict": "Falso",
            "rating": "1",
            "country": "BR",
            "topics": [],
            "tags": [
                "ira-asia",
                "fake-news-noticia-falsa",
                "estados-unidos-america-do-norte",
                "israel-asia",
            ],
            "entities": [],
            "source_type": "ClaimReview",
        },
        id="estadao_verifica",
    ),
    pytest.param(
        G1FatoOuFakeSpider,
        "g1_fato_ou_fake",
        "article.html",
        "https://g1.globo.com/fato-ou-fake/noticia/2025/10/27/e-fake-video-que-mostra-mulher-com-sapatos-voadores-em-exposicao.ghtml",
        {
            "source_url": "https://g1.globo.com/fato-ou-fake/noticia/2025/10/27/e-fake-video-que-mostra-mulher-com-sapatos-voadores-em-exposicao.ghtml",
            "canonical_url": "https://g1.globo.com/fato-ou-fake/noticia/2025/10/27/e-fake-video-que-mostra-mulher-com-sapatos-voadores-em-exposicao.ghtml",
            "title": "E #FAKE video que mostra mulher com sapatos voadores em exposicao",
            "published_at": "2025-10-27T18:44:50.441-03:00",
            "claim": "video que mostra mulher com sapatos voadores em exposicao",
            "summary": "As imagens, supostamente na China, nao mostram um acontecimento real.",
            "verdict": "FAKE",
            "rating": "FAKE",
            "country": "BR",
            "topics": ["G1", "Fato ou Fake"],
            "tags": ["Fato ou Fake", "Inteligencia artificial", "China"],
            "entities": [],
            "source_type": "NewsArticle",
        },
        id="g1_fato_ou_fake",
    ),
    pytest.param(
        ObservadorSpider,
        "observador",
        "article.html",
        "https://observador.pt/factchecks/fact-check-von-der-leyen-disse-que-a-liberdade-de-expressao-e-um-virus-e-a-censura-e-a-vacina/",
        {
            "source_url": "https://observador.pt/factchecks/fact-check-von-der-leyen-disse-que-a-liberdade-de-expressao-e-um-virus-e-a-censura-e-a-vacina/",
            "canonical_url": "https://observador.pt/factchecks/fact-check-von-der-leyen-disse-que-a-liberdade-de-expressao-e-um-virus-e-a-censura-e-a-vacina",
            "title": "Fact Check. Von der Leyen disse que a liberdade de expressao e um virus e a censura e a vacina?",
            "published_at": "2026-02-18T15:41:27+00:00",
            "claim": "A liberdade de expressao e um virus e a censura e a vacina",
            "summary": "Nas redes sociais, circula a afirmacao atribuida a Presidente da Comissao Europeia.",
            "verdict": "Errado",
            "rating": "1",
            "country": "PT",
            "topics": [],
            "tags": ["Fact Check", "Observador", "Ursula von der Leyen", "Mundo"],
            "entities": [],
            "source_type": "ClaimReview",
        },
        id="observador",
    ),
    pytest.param(
        PoligrafoSpider,
        "poligrafo",
        "article.html",
        "https://poligrafo.sapo.pt/fact-check/esta-tabela-com-valores-de-salarios-minimos-em-varios-paises-europeus-esta-correta/",
        {
            "source_url": "https://poligrafo.sapo.pt/fact-check/esta-tabela-com-valores-de-salarios-minimos-em-varios-paises-europeus-esta-correta/",
            "canonical_url": "https://poligrafo.sapo.pt/fact-check/esta-tabela-com-valores-de-salarios-minimos-em-varios-paises-europeus-esta-correta",
            "title": "Esta tabela com valores de salarios minimos em varios paises europeus esta correta?",
            "published_at": "2026-03-11T15:00:00",
            "claim": "Esta tabela com valores de salarios minimos em varios paises europeus esta correta?",
            "summary": "Os numeros indicados tem fundamento? O Poligrafo verifica.",
            "verdict": "Impreciso",
            "rating": "Impreciso",
            "country": "PT",
            "topics": ["Economia"],
            "tags": [],
            "entities": [],
            "source_type": "fact_check",
        },
        id="poligrafo",
    ),
    pytest.param(
        ProjetoComprovaSpider,
        "projeto_comprova",
        "article.html",
        "https://projetocomprova.com.br/publicacoes/e-falso-que-alimentos-com-selo-da-ra-sejam-sinteticos-e-produzidos-por-bill-gates/",
        {
            "source_url": "https://projetocomprova.com.br/publicacoes/e-falso-que-alimentos-com-selo-da-ra-sejam-sinteticos-e-produzidos-por-bill-gates/",
            "canonical_url": "https://projetocomprova.com.br/publicacoes/e-falso-que-alimentos-com-selo-da-ra-sejam-sinteticos-e-produzidos-por-bill-gates",
            "title": "E falso que alimentos com selo da ra sejam sinteticos e produzidos por Bill Gates",
            "published_at": "2024-04-30",
            "claim": "Marca da ra revela plano para destruir o agro",
            "summary": "O simbolo representa o certificado Rainforest Alliance.",
            "verdict": "Falso",
            "rating": "Falso",
            "country": "BR",
            "topics": [],
            "tags": ["desinformacao", "meio ambiente"],
            "entities": [],
            "source_type": "ClaimReview",
        },
        id="projeto_comprova",
    ),
    pytest.param(
        PublicoSpider,
        "publico",
        "article_prova.html",
        "https://www.publico.pt/2026/03/03/politica/noticia/economia-portuguesa-representa-menos-2-pib-europeu-afirmou-passos-coelho-verdadeiro-2166654",
        {
            "source_url": "https://www.publico.pt/2026/03/03/politica/noticia/economia-portuguesa-representa-menos-2-pib-europeu-afirmou-passos-coelho-verdadeiro-2166654",
            "canonical_url": "https://www.publico.pt/2026/03/03/politica/noticia/economia-portuguesa-representa-menos-2-pib-europeu-afirmou-passos-coelho-verdadeiro-2166654",
            "title": "Economia portuguesa representa menos de 2% do PIB europeu, como afirmou Passos Coelho? Verdadeiro",
            "published_at": "Tue, 03 Mar 2026 15:22:23 GMT",
            "claim": "Economia portuguesa representa menos de 2% do PIB europeu, como afirmou Passos Coelho?",
            "summary": "De acordo com dados provisórios do Eurostat, a economia portuguesa representava 1,6% do PIB da Uniao Europeia.",
            "verdict": "Verdadeiro",
            "rating": "Verdadeiro",
            "country": "PT",
            "topics": ["Politica"],
            "tags": [
                "Prova dos Factos",
                "Verdadeiro",
                "Ibercheck",
                "Uniao Europeia",
                "Europa",
                "PIB",
                "Politica",
            ],
            "entities": [],
            "source_type": "NewsArticle",
        },
        id="publico",
    ),
    pytest.param(
        AfpChecamosSpider,
        "afp_checamos",
        "article.html",
        "https://checamos.afp.com/doc.afp.com.ABC123",
        {
            "source_url": "https://checamos.afp.com/doc.afp.com.ABC123",
            "canonical_url": "https://checamos.afp.com/doc.afp.com.ABC123",
            "title": "E falso que video mostre cena real apurada pela AFP",
            "published_at": "2026-03-01T12:00:00+00:00",
            "claim": "Video mostra cena real apurada pela AFP",
            "summary": "AFP Checamos investigou o conteudo e concluiu que ele e falso.",
            "verdict": "Falso",
            "rating": "1",
            "country": "BR",
            "topics": [],
            "tags": ["eleicoes", "desinformacao"],
            "entities": [],
            "source_type": "ClaimReview",
        },
        id="afp_checamos",
    ),
    pytest.param(
        ReutersFactCheckSpider,
        "reuters_fact_check",
        "article.html",
        "https://www.reuters.com/fact-check/portugues/exemplo-reuters/",
        {
            "source_url": "https://www.reuters.com/fact-check/portugues/exemplo-reuters/",
            "canonical_url": "https://www.reuters.com/fact-check/portugues/exemplo-reuters",
            "title": "Reuters apura que conteudo viral e falso",
            "published_at": "2026-03-02T11:00:00+00:00",
            "claim": "Conteudo viral compartilha fato inexistente",
            "summary": "Analise da Reuters mostra que o post compartilha informacao falsa.",
            "verdict": "Falso",
            "rating": "1",
            "country": None,
            "topics": [],
            "tags": ["fact check", "desinformacao"],
            "entities": [],
            "source_type": "ClaimReview",
        },
        id="reuters_fact_check",
    ),
    pytest.param(
        UolConfereSpider,
        "uol_confere",
        "article.html",
        "https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/10/governo-nao-pediu-alistamento-por-causa-da-guerra-no-oriente-medio.htm",
        {
            "source_url": "https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/10/governo-nao-pediu-alistamento-por-causa-da-guerra-no-oriente-medio.htm",
            "canonical_url": "https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/10/governo-nao-pediu-alistamento-por-causa-da-guerra-no-oriente-medio.htm",
            "title": "Governo Lula nao pediu alistamento por causa da guerra no Oriente Medio",
            "published_at": "2026-03-10T17:15:58.000Z",
            "claim": "Atencao: em meio a guerra, governo brasileiro pede que alem dos jovens, todas as mulheres tambem possam se alistar voluntariamente no exercito brasileiro",
            "summary": "O governo brasileiro nao alterou as regras de alistamento; o conteudo viral mistura guerra externa com normas ja existentes.",
            "verdict": "Falso",
            "rating": "1",
            "country": "BR",
            "topics": ["Alistamento militar", "Oriente Medio", "Politica"],
            "tags": ["Exercito brasileiro", "Governo Lula", "Desinformacao", "Oriente Medio"],
            "entities": [],
            "source_type": "ClaimReview",
        },
        id="uol_confere",
    ),
]


def test_list_spiders_includes_supported_spiders():
    names = set(list_spiders())
    expected = {
        "afp_checamos",
        "agencia_lupa",
        "aos_fatos",
        "boatos_org",
        "e_farsas",
        "estadao_verifica",
        "g1_fato_ou_fake",
        "observador",
        "poligrafo",
        "projeto_comprova",
        "publico",
        "reuters_fact_check",
        "uol_confere",
    }
    assert expected.issubset(names)


def test_agencia_lupa_parse_listing():
    spider = AgenciaLupaSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("agencia_lupa", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert (
        "https://www.agencialupa.org/checagem/2026/01/06/"
        "maduro-drogas-e-petroleo-o-que-e-fato-no-discurso-de-trump/" in urls
    )
    assert "https://www.agencialupa.org/checagem/page/2/" in urls
    assert all("/jornalismo/" not in url for url in urls)


def test_aos_fatos_parse_listing():
    spider = AosFatosSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("aos_fatos", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert (
        "https://www.aosfatos.org/noticias/"
        "nao-verdade-foto-mostra-missil-iraniano-mensagem-vitimas-epstein/" in urls
    )
    assert "https://www.aosfatos.org/noticias/?formato=checagem&page=2" in urls


def test_boatos_org_parse_sitemap():
    spider = BoatosOrgSpider()
    response = make_text_response(
        "https://www.boatos.org/sitemap-posttype-post.2013.xml",
        load_fixture("boatos_org", "sitemap.xml"),
    )

    urls = _request_urls(list(spider.parse_sitemap(response)))

    assert urls == [
        "https://www.boatos.org/saude/perigo-hoax-mamografia-causar-cancer-tireoide.html"
    ]


def test_e_farsas_parse_listing():
    spider = EFarsasSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("e_farsas", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert "http://www.e-farsas.com/as-previsoes-dos-videntes-que-falharam-em-2025.html" in urls
    assert "http://www.e-farsas.com/page/2" in urls


def test_estadao_verifica_parse_sitemap_index_and_urlset():
    spider = EstadaoVerificaSpider()
    index_response = make_text_response(
        spider.start_urls[0],
        load_fixture("estadao_verifica", "sitemapindex.xml"),
    )
    index_urls = _request_urls(list(spider.parse(index_response)))

    assert index_urls == ["https://www.estadao.com.br/sitemaps/estadao-verifica-2026-03-06.xml"]

    urlset_response = make_text_response(
        "https://www.estadao.com.br/sitemaps/estadao-verifica-2026-03-06.xml",
        load_fixture("estadao_verifica", "urlset.xml"),
    )
    urlset_urls = _request_urls(list(spider.parse_sitemap(urlset_response)))

    assert urlset_urls == [
        "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial/"
    ]


def test_g1_fato_ou_fake_parse_sitemap_index_and_urlset():
    spider = G1FatoOuFakeSpider()
    index_response = make_text_response(
        spider.start_urls[0],
        load_fixture("g1_fato_ou_fake", "sitemapindex.xml"),
    )
    index_urls = _request_urls(list(spider.parse(index_response)))

    assert index_urls == ["https://g1.globo.com/sitemap/fato-ou-fake-2025.xml"]

    urlset_response = make_text_response(
        "https://g1.globo.com/sitemap/fato-ou-fake-2025.xml",
        load_fixture("g1_fato_ou_fake", "urlset.xml"),
    )
    urlset_urls = _request_urls(list(spider.parse_sitemap(urlset_response)))

    assert urlset_urls == [
        "https://g1.globo.com/fato-ou-fake/noticia/2025/10/27/e-fake-video-que-mostra-mulher-com-sapatos-voadores-em-exposicao.ghtml"
    ]


def test_observador_parse_listing_and_api_seed():
    spider = ObservadorSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("observador", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert (
        "https://observador.pt/factchecks/"
        "fact-check-von-der-leyen-disse-que-a-liberdade-de-expressao-"
        "e-um-virus-e-a-censura-e-a-vacina/" in urls
    )
    assert (
        "https://observador.pt/wp-json/obs_api/v4/grids/filter/archive/"
        "obs_factcheck?offset=20260217&scroll=true" in urls
    )


def test_observador_start_requests_enable_scrapling_on_listing():
    spider = ObservadorSpider()

    requests = list(spider.start_requests())

    assert len(requests) == 1
    assert requests[0].meta["scrapling"] == {
        "enabled": True,
        "wait_selector": ".editorial-grid",
    }


def test_observador_parse_api_paginates():
    spider = ObservadorSpider()
    response = make_text_response(
        "https://observador.pt/wp-json/obs_api/v4/grids/filter/archive/obs_factcheck?offset=20260217&scroll=true",
        load_fixture("observador", "api.json"),
        meta={"offset": "20260217"},
    )

    results = list(spider.parse_api(response))
    urls = _request_urls(results)

    assert (
        "https://observador.pt/factchecks/"
        "fact-check-primeira-ministra-da-dinamarca-riu-se-de-trump-no-parlamento/" in urls
    )
    assert (
        "https://observador.pt/wp-json/obs_api/v4/grids/filter/archive/"
        "obs_factcheck?offset=20260216&scroll=true" in urls
    )

    requests = [result for result in results if isinstance(result, Request)]
    article_request = next(
        request for request in requests if "/factchecks/fact-check-primeira-ministra" in request.url
    )
    api_request = next(request for request in requests if "wp-json/obs_api" in request.url)

    assert article_request.meta["scrapling"] == {
        "enabled": True,
        "wait_selector": "script[type='application/ld+json'], h1",
    }
    assert api_request.meta["scrapling"] == {"enabled": True}
    assert api_request.meta["offset"] == "20260216"


def test_observador_parse_listing_marks_article_and_api_requests_for_scrapling():
    spider = ObservadorSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("observador", "listing.html"),
    )

    requests = [result for result in spider.parse(response) if isinstance(result, Request)]
    article_request = next(
        request for request in requests if "/factchecks/fact-check-von-der-leyen" in request.url
    )
    api_request = next(request for request in requests if "wp-json/obs_api" in request.url)

    assert article_request.meta["scrapling"] == {
        "enabled": True,
        "wait_selector": "script[type='application/ld+json'], h1",
    }
    assert api_request.meta["scrapling"] == {"enabled": True}
    assert api_request.meta["offset"] == "20260217"


def test_observador_parse_article_skips_cloudflare_challenge_page():
    spider = ObservadorSpider()
    response = make_html_response(
        "https://observador.pt/factchecks/fact-check-portugal-cresce-mais-rapido-que-a-zona-euro/",
        "<html><title>Just a moment...</title></html>",
    )

    assert list(spider.parse_article(response)) == []


def test_poligrafo_parse_listing_filters_economia_only():
    spider = PoligrafoSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("poligrafo", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert (
        "https://poligrafo.sapo.pt/fact-check/"
        "esta-tabela-com-valores-de-salarios-minimos-em-varios-paises-"
        "europeus-esta-correta/" in urls
    )
    assert (
        "https://poligrafo.sapo.pt/fact-check/"
        "ventura-diz-que-em-portugal-os-presos-ganham-mais-por-hora-"
        "do-que-os-bombeiros-e-verdade/" not in urls
    )
    assert "https://poligrafo.sapo.pt/fact-checks/economia/page/2/" in urls


def test_projeto_comprova_parse_listing():
    spider = ProjetoComprovaSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("projeto_comprova", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert (
        "https://projetocomprova.com.br/publicacoes/"
        "e-falso-que-alimentos-com-selo-da-ra-sejam-sinteticos-"
        "e-produzidos-por-bill-gates/" in urls
    )
    assert "https://projetocomprova.com.br/page/2/?filter=verificacao" in urls


def test_publico_parse_sitemap_index_and_urlset():
    spider = PublicoSpider()
    index_response = make_text_response(
        spider.start_urls[0],
        load_fixture("publico", "sitemapindex.xml"),
    )
    index_urls = _request_urls(list(spider.parse(index_response)))

    assert index_urls == ["https://www.publico.pt/sitemaps/articles/2026-3.xml"]

    urlset_response = make_text_response(
        "https://www.publico.pt/sitemaps/articles/2026-3.xml",
        load_fixture("publico", "urlset.xml"),
    )
    urlset_urls = _request_urls(list(spider.parse_sitemap(urlset_response)))

    assert urlset_urls == [
        "https://www.publico.pt/2026/03/03/economia/noticia/economia-portuguesa-representa-menos-2-pib-europeu-2166654",
        "https://www.publico.pt/2026/03/03/mundo/noticia/fora-do-escopo-2166000",
    ]


def test_publico_rejects_non_prova_article():
    spider = PublicoSpider()
    response = make_html_response(
        "https://www.publico.pt/2026/03/12/economia/noticia/numero-condutores-volante-electrico-quase-triplicou-ano-2167610",
        load_fixture("publico", "article_non_prova.html"),
    )

    assert list(spider.parse_article(response)) == []


def test_publico_rejects_newsletter_even_with_prova_dos_factos_tag():
    spider = PublicoSpider()
    response = make_html_response(
        "https://www.publico.pt/2025/11/24/newsletter/prova-dos-factos",
        """
        <html lang="pt">
          <head>
            <title>Um microfone desligado pode comecar a salvar a democracia nos debates televisivos</title>
            <meta property="article:published_time" content="Mon, 24 Nov 2025 19:31:52 GMT" />
            <meta name="keywords" content="Prova dos Factos,Newsletters" />
            <script type="application/ld+json">
              {
                "@context": "http://schema.org",
                "@type": "NewsArticle",
                "headline": "Um microfone desligado pode comecar a salvar a democracia nos debates televisivos",
                "datePublished": "Mon, 24 Nov 2025 19:31:52 GMT",
                "description": "Escrutinamos o que corre sem filtro no espaco publico.",
                "url": "https://www.publico.pt/2025/11/24/newsletter/prova-dos-factos",
                "keywords": ["Prova dos Factos", "Newsletters"],
                "articleSection": ["Newsletters"],
                "inLanguage": "pt"
              }
            </script>
          </head>
          <body>
            <h1>Um microfone desligado pode comecar a salvar a democracia nos debates televisivos</h1>
          </body>
        </html>
        """,
    )

    assert list(spider.parse_article(response)) == []


def test_afp_checamos_parse_listing_and_ajax_seed():
    spider = AfpChecamosSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("afp_checamos", "listing.html"),
    )

    urls = _request_urls(list(spider.parse(response)))

    assert "https://checamos.afp.com/doc.afp.com.ABC123" in urls
    assert "https://checamos.afp.com/Como-trabalhamos" not in urls
    assert any(url.startswith("https://checamos.afp.com/views/ajax?") for url in urls)


def test_afp_checamos_parse_ajax_paginates():
    spider = AfpChecamosSpider()
    response = make_text_response(
        "https://checamos.afp.com/views/ajax?page=1",
        load_fixture("afp_checamos", "ajax.json"),
        meta={
            "page": 1,
            "ajax_params": {
                "_wrapper_format": "drupal_ajax",
                "view_name": "rubriques",
                "view_display_id": "page_2",
                "view_args": "",
                "view_path": "/list",
                "view_base_path": "list",
                "view_dom_id": "fixture-dom-id",
                "pager_element": "0",
                "_drupal_ajax": "1",
            },
        },
    )

    urls = _request_urls(list(spider.parse_ajax(response)))

    assert "https://checamos.afp.com/doc.afp.com.DEF456" in urls
    assert "https://checamos.afp.com/Contato" not in urls
    assert any(
        "page=2" in url for url in urls if url.startswith("https://checamos.afp.com/views/ajax?")
    )


def test_afp_checamos_parse_article_drops_editorial_page():
    spider = AfpChecamosSpider()
    response = make_html_response(
        "https://checamos.afp.com/Como-trabalhamos",
        load_fixture("afp_checamos", "article_editorial.html"),
    )

    assert list(spider.parse_article(response)) == []


def test_reuters_parse_listing_and_api_seed():
    spider = ReutersFactCheckSpider()
    response = make_html_response(
        spider.start_urls[0],
        load_fixture("reuters_fact_check", "listing.html"),
    )

    results = list(spider.parse(response))
    urls = _request_urls(results)
    requests = [result for result in results if isinstance(result, Request)]
    article_request = next(
        request for request in requests if request.url.endswith("/exemplo-reuters/")
    )
    api_request = next(
        request
        for request in requests
        if request.url.startswith(
            "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1"
        )
    )

    assert "https://www.reuters.com/fact-check/portugues/exemplo-reuters/" in urls
    assert api_request.meta["scrapling"] == {"enabled": True}
    assert api_request.meta["offset"] == 0
    assert api_request.headers.get("Accept").decode() == "*/*"
    assert (
        api_request.headers.get("Referer").decode()
        == "https://www.reuters.com/fact-check/portugues/"
    )
    assert article_request.meta["scrapling"] == {
        "enabled": True,
        "wait_selector": "script[type='application/ld+json'], h1",
    }


def test_reuters_start_requests_enable_scrapling_on_listing():
    spider = ReutersFactCheckSpider()

    requests = list(spider.start_requests())

    assert len(requests) == 1
    assert requests[0].meta["scrapling"] == {
        "enabled": True,
        "wait_selector": "a[href*='/fact-check/portugues/']",
    }


def test_reuters_custom_settings_use_polite_rate_limits():
    settings = ReutersFactCheckSpider.custom_settings

    assert settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1
    assert settings["DOWNLOAD_DELAY"] == 2.0
    assert settings["RANDOMIZE_DOWNLOAD_DELAY"] is True
    assert settings["AUTOTHROTTLE_ENABLED"] is True
    assert settings["AUTOTHROTTLE_START_DELAY"] == 2.0
    assert settings["AUTOTHROTTLE_MAX_DELAY"] == 12.0
    assert settings["AUTOTHROTTLE_TARGET_CONCURRENCY"] == 1.0


def test_reuters_parse_api_paginates():
    spider = ReutersFactCheckSpider()
    response = make_text_response(
        "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?query=test",
        load_fixture("reuters_fact_check", "api.json"),
        meta={"offset": 0},
    )

    results = list(spider.parse_api(response))
    urls = _request_urls(results)
    requests = [result for result in results if isinstance(result, Request)]
    article_request = next(
        request for request in requests if request.url.endswith("/exemplo-reuters/")
    )
    api_request = next(request for request in requests if "%22offset%22%3A20" in request.url)

    assert "https://www.reuters.com/fact-check/portugues/exemplo-reuters/" in urls
    assert "https://www.reuters.com/fact-check/portugues/exemplo-reuters-2/" in urls
    assert api_request.meta["scrapling"] == {"enabled": True}
    assert api_request.meta["offset"] == 20
    assert api_request.headers.get("Accept").decode() == "*/*"
    assert (
        api_request.headers.get("Referer").decode()
        == "https://www.reuters.com/fact-check/portugues/"
    )
    assert article_request.meta["scrapling"] == {
        "enabled": True,
        "wait_selector": "script[type='application/ld+json'], h1",
    }


def test_reuters_extract_listing_links_ignores_section_root():
    spider = ReutersFactCheckSpider()
    response = make_html_response(
        spider.start_urls[0],
        """
        <html>
          <body>
            <a href="https://www.reuters.com/fact-check/portugues/">Secao</a>
            <a href="https://www.reuters.com/fact-check/portugues/exemplo-reuters/">Artigo</a>
          </body>
        </html>
        """,
    )

    assert spider._extract_listing_links(response) == [
        "https://www.reuters.com/fact-check/portugues/exemplo-reuters/"
    ]


def test_reuters_parse_article_skips_persistent_block():
    spider = ReutersFactCheckSpider()
    response = HtmlResponse(
        url="https://www.reuters.com/fact-check/portugues/exemplo-reuters-bloqueado/",
        request=Request(
            url="https://www.reuters.com/fact-check/portugues/exemplo-reuters-bloqueado/",
            meta={"scrapling": {"enabled": True}},
        ),
        body=b"<html><title>blocked</title></html>",
        status=401,
        encoding="utf-8",
    )

    assert list(spider.parse_article(response)) == []


@pytest.mark.parametrize(
    ("spider_cls", "folder", "filename", "url", "expected"),
    ARTICLE_CASES,
)
def test_article_parsers_extract_semantic_fields(spider_cls, folder, filename, url, expected):
    spider = spider_cls()
    response = make_html_response(url, load_fixture(folder, filename))

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    _assert_item_fields(items[0], expected)


def test_estadao_verifica_canonicalizes_relative_jsonld_url():
    spider = EstadaoVerificaSpider()
    response = make_html_response(
        "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial/",
        load_fixture("estadao_verifica", "article.html"),
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert (
        items[0]["canonical_url"]
        == "https://www.estadao.com.br/estadao-verifica/video-caminhoes-tunel-misseis-ira-falso-inteligencia-artificial"
    )


def test_extract_verdict_and_rating_ignores_numeric_labels():
    spider = AfpChecamosSpider()

    verdict, rating = spider.extract_verdict_and_rating(
        {
            "reviewRating": {
                "@type": "Rating",
                "alternateName": "1",
                "bestRating": "4",
            }
        }
    )

    assert verdict is None
    assert rating == "4"


def test_spider_drops_article_with_invalid_core_fields():
    spider = G1FatoOuFakeSpider()
    url = "https://g1.globo.com/fato-ou-fake/noticia/2026/03/17/item-invalido.ghtml"
    response = make_html_response(
        url,
        """
        <html>
          <head>
            <title>https://g1.globo.com/fato-ou-fake/noticia/2026/03/17/item-invalido.ghtml</title>
            <meta property="og:title" content="https://g1.globo.com/fato-ou-fake/noticia/2026/03/17/item-invalido.ghtml" />
            <meta itemprop="datePublished" content="-" />
            <link rel="canonical" href="https://g1.globo.com/fato-ou-fake/noticia/2026/03/17/item-invalido.ghtml" />
          </head>
          <body></body>
        </html>
        """,
    )

    assert list(spider.parse_article(response)) == []


def test_uol_confere_ignores_generic_portal_summary():
    spider = UolConfereSpider()
    response = make_html_response(
        "https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/11/exemplo.htm",
        """
        <html lang="pt-BR">
          <head>
            <title>Conteudo especifico do artigo</title>
            <meta name="description" content="Veja as principais noticias e manchetes do dia no Brasil e no Mundo. Leia textos e assista a videos de Politica, Cotidiano, Crimes e mais." />
            <meta property="og:description" content="Veja as principais noticias e manchetes do dia no Brasil e no Mundo. Leia textos e assista a videos de Politica, Cotidiano, Crimes e mais." />
            <link rel="canonical" href="https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/11/exemplo.htm" />
            <meta property="article:section" content="Politica" />
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": "Conteudo especifico do artigo",
                "datePublished": "2026-03-11T10:00:00.000Z",
                "description": "Veja as principais noticias e manchetes do dia no Brasil e no Mundo. Leia textos e assista a videos de Politica, Cotidiano, Crimes e mais.",
                "url": "https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/11/exemplo.htm"
              }
            </script>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "ClaimReview",
                "datePublished": "2026-03-11T10:00:00.000Z",
                "url": "https://noticias.uol.com.br/confere/ultimas-noticias/2026/03/11/exemplo.htm",
                "claimReviewed": "Boato reaproveita uma regra antiga como se fosse nova.",
                "reviewRating": {
                  "@type": "Rating",
                  "alternateName": "Falso",
                  "ratingValue": "1"
                }
              }
            </script>
          </head>
          <body>
            <h1>Conteudo especifico do artigo</h1>
          </body>
        </html>
        """,
    )

    items = _items(list(spider.parse_article(response)))

    assert len(items) == 1
    assert items[0]["summary"] is None
    assert items[0]["verdict"] == "Falso"


def test_boatos_org_start_requests_cover_all_years():
    spider = BoatosOrgSpider()
    requests = list(spider.start_requests())

    assert requests[0].url == "https://www.boatos.org/sitemap-posttype-post.2013.xml"
    assert (
        requests[-1].url
        == f"https://www.boatos.org/sitemap-posttype-post.{datetime.now().year}.xml"
    )

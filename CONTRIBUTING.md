# Contribuindo com o fact-checking-scrape

Guia para adicionar novas spiders e contribuir com o projeto.

## Requisitos

- Python 3.12+
- Dependencias: `pip install -e ".[dev]"`
- Para analise: `pip install -e ".[analysis]"`
- Para spiders com Scrapling: `pip install -e ".[scrapling]"`

## Estrutura do projeto

```
src/factcheck_scrape/
  spiders/
    helpers/         # Funcoes puras: text.py, jsonld.py, claimreview.py, taxonomy.py
    base.py          # BaseFactCheckSpider — classe base com metodos delegados aos helpers
    <nome>.py        # Um arquivo por spider
  schema.py          # FactCheckItem dataclass (fonte unica de verdade do schema)
  pipelines.py       # FactCheckPipeline (validacao, dedupe, storage)
  text_cleanup.py    # TextCleanupPipeline (normalizacao pre-storage)
  storage.py         # RunWriter (items.jsonl + run.json)
  dedupe.py          # DedupeStore (SQLite)
  quality.py         # Metricas de qualidade por spider
  report.py          # Relatorio de execucao
  runner.py          # Executor de spiders (sequencial e paralelo)
  cli.py             # Ponto de entrada CLI
tests/
  test_spiders.py    # Testes unitarios dos spiders (fixtures HTML)
  test_spider_edge_cases.py  # Edge cases (sem JSON-LD, campos faltantes, etc.)
  test_smoke.py      # Smoke tests contra sites reais (--run-smoke)
  test_integration.py # Pipeline + storage + dedupe
docs/
  spiders.md         # Contrato tecnico de cada spider
  schema.json        # JSON Schema gerado da dataclass
```

## Adicionando uma nova spider

### 1. Criar o arquivo da spider

Crie `src/factcheck_scrape/spiders/<nome_agencia>.py`:

```python
from __future__ import annotations

from .base import BaseFactCheckSpider


class MinhaAgenciaSpider(BaseFactCheckSpider):
    name = "minha_agencia"
    agency_id = "minha_agencia"
    agency_name = "Minha Agencia"
    allowed_domains = ["minhaagencia.com.br"]
    start_urls = ["https://minhaagencia.com.br/checagens/"]

    def parse(self, response):
        # Extrair links de artigos da listagem
        for href in response.css("a.article-link::attr(href)").getall():
            yield response.follow(href, callback=self.parse_article)

        # Paginacao
        next_url = self.meta_first(response, "a.next::attr(href)")
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_article(self, response):
        # 1. Extrair JSON-LD
        jsonld_items = self.extract_jsonld(response)
        claim_review = self.pick_jsonld(jsonld_items, "ClaimReview")
        article = self.pick_jsonld(jsonld_items, "NewsArticle", "Article", "WebPage")

        # 2. Extrair campos com fallbacks
        title = self.first_text(
            article.get("headline"),
            article.get("name"),
            self.meta_first(response, "meta[property='og:title']::attr(content)", "h1::text"),
        )
        published_at = self.first_text(
            claim_review.get("datePublished"),
            article.get("datePublished"),
            self.meta_first(response, "meta[property='article:published_time']::attr(content)"),
        )
        canonical_url = self.extract_canonical_url(response, claim_review, article)
        summary = self.first_text(
            article.get("description"),
            self.meta_first(response, "meta[name='description']::attr(content)"),
        )
        claim = self.first_text(claim_review.get("claimReviewed"), title)
        verdict, rating = self.extract_verdict_and_rating(claim_review)
        verdict = self.infer_verdict(verdict, title, summary) or verdict
        rating = rating or verdict
        author = self.extract_author(response, claim_review, article)
        body = self.extract_body(response, claim_review, article)
        language = self.extract_language(response, claim_review, article)
        topics, tags, entities = self.extract_taxonomy(claim_review, article)
        source_type = self.extract_source_type(claim_review, article)

        # 3. Validar campos obrigatorios
        if not self.validate_extracted_article(
            response, title=title, published_at=published_at, canonical_url=canonical_url,
        ):
            return

        # 4. Emitir item
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
```

### 2. Ordem de prioridade para extracao de campos

1. **JSON-LD** (ClaimReview > NewsArticle > Article > WebPage)
2. **Meta tags** (`og:title`, `article:published_time`, `description`)
3. **Seletores CSS** (`h1::text`, `time::attr(datetime)`)
4. **Inferencia** (`infer_verdict` para veredictos)

Sempre use `self.first_text()` para encadear multiplas fontes com fallback.

### 3. Metodos disponiveis na BaseFactCheckSpider

| Metodo | Descricao |
|---|---|
| `extract_jsonld(response)` | Extrai todos os blocos JSON-LD |
| `pick_jsonld(items, *types)` | Seleciona o primeiro JSON-LD do tipo desejado |
| `extract_canonical_url(response, *items)` | URL canonica com fallback para meta/og |
| `extract_verdict_and_rating(claim_review)` | Veredicto e rating do ClaimReview |
| `infer_verdict(*values)` | Infere veredicto por heuristica em portugues |
| `extract_author(response, *items)` | Autor do JSON-LD ou meta tags |
| `extract_body(response, *items)` | Corpo do artigo (articleBody ou paragrafos) |
| `extract_taxonomy(*items)` | topics, tags, entities do JSON-LD |
| `extract_language(response, *items)` | Idioma do JSON-LD ou `html lang` |
| `extract_source_type(*items)` | Tipo schema.org (`@type`) |
| `first_text(*values)` | Primeiro valor nao-vazio da cadeia |
| `clean_text(value)` | Normaliza whitespace e strip |
| `meta_first(response, *selectors)` | Primeiro resultado CSS nao-vazio |
| `split_keywords(value)` | Divide por virgula e limpa |
| `validate_extracted_article(...)` | Valida title e published_at obrigatorios |
| `build_item(...)` | Monta o dict do item com todos os campos |

### 4. Escrever testes

#### Teste unitario com fixture HTML

Em `tests/test_spiders.py`, adicione uma fixture e um teste:

```python
# No topo do arquivo
from factcheck_scrape.spiders.minha_agencia import MinhaAgenciaSpider

# Fixture HTML minima com JSON-LD
MINHA_AGENCIA_HTML = """
<html lang="pt-BR">
<head>
  <script type="application/ld+json">
  {
    "@type": "NewsArticle",
    "headline": "Titulo da Checagem",
    "datePublished": "2026-04-01T10:00:00-03:00",
    "url": "https://minhaagencia.com.br/checagem/artigo-1"
  }
  </script>
</head>
<body><article><p>Corpo do artigo.</p></article></body>
</html>
"""

def test_minha_agencia_parse_article():
    spider = MinhaAgenciaSpider()
    response = fake_response("https://minhaagencia.com.br/checagem/artigo-1", MINHA_AGENCIA_HTML)
    items = list(spider.parse_article(response))
    assert len(items) == 1
    assert items[0]["title"] == "Titulo da Checagem"
    assert items[0]["published_at"].startswith("2026-04-01")
```

#### Smoke test

Adicione uma entrada em `tests/test_smoke.py`:

```python
pytest.param(
    MinhaAgenciaSpider,
    "https://minhaagencia.com.br/checagem/artigo-estavel",
    id="minha_agencia",
),
```

Use uma URL de artigo estavel e antiga (menos chance de ser removido).

### 5. Checklist antes de enviar

- [ ] Spider herda de `BaseFactCheckSpider`
- [ ] `name`, `agency_id`, `agency_name`, `allowed_domains`, `start_urls` definidos
- [ ] `parse_article` usa `extract_jsonld` + `pick_jsonld` quando o site tem JSON-LD
- [ ] `validate_extracted_article` chamado antes de `build_item`
- [ ] Teste unitario com fixture HTML passando
- [ ] Smoke test adicionado em `test_smoke.py`
- [ ] Contrato documentado em `docs/spiders.md`
- [ ] `python -m pytest tests/` passa sem erros
- [ ] `ruff check src/` sem violacoes

### 6. Sites com Cloudflare/anti-bot

Se o site usa protecao anti-bot, configure Scrapling no `custom_settings`:

```python
custom_settings = {
    "FACTCHECK_SCRAPLING_HEADLESS": False,
    "FACTCHECK_SCRAPLING_REAL_CHROME": True,
    "FACTCHECK_SCRAPLING_BLOCK_WEBRTC": True,
    "FACTCHECK_SCRAPLING_HIDE_CANVAS": True,
}
```

E envie requests com meta Scrapling:

```python
def start_requests(self):
    for url in self.start_urls:
        yield scrapy.Request(
            url, callback=self.parse,
            meta={"scrapling": {"enabled": True, "wait_selector": "h1"}},
        )
```

Adicione deteccao de challenge pages (ver `observador.py` e `reuters_fact_check.py`).

## Executando testes

```bash
# Testes unitarios
python -m pytest tests/

# Smoke tests (requer rede)
python -m pytest tests/ --run-smoke

# Lint
ruff check src/ tests/
```

## Comandos uteis

```bash
# Listar spiders
factcheck-scrape list

# Executar uma spider
factcheck-scrape run --spider minha_agencia --data-dir data

# Executar todas (4 em paralelo)
factcheck-scrape run --spider all --data-dir data

# Relatorio da ultima execucao
factcheck-scrape report

# Metricas de qualidade
factcheck-scrape quality
```

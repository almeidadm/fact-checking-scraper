# fact-checking-scrape

Pipeline de web scraping para 13 agencias de fact-checking em portugues, com coleta padronizada em JSONL, deduplicacao SQLite, validacao JSON Schema, limpeza de texto pre-storage e execucao paralela.

## Agencias suportadas

| Spider | Agencia | Pais | Descoberta |
|---|---|---|---|
| `afp_checamos` | AFP Checamos | BR | AJAX Drupal |
| `agencia_lupa` | Agencia Lupa | BR | HTML + paginacao |
| `aos_fatos` | Aos Fatos | BR | HTML + paginacao |
| `boatos_org` | Boatos.org | BR | Sitemaps anuais |
| `e_farsas` | E-farsas | BR | HTML + paginacao |
| `estadao_verifica` | Estadao Verifica | BR | Sitemap Arc |
| `g1_fato_ou_fake` | G1 Fato ou Fake | BR | Sitemap Globo |
| `observador` | Observador | PT | HTML + API JSON |
| `poligrafo` | Poligrafo | PT | HTML Elementor |
| `projeto_comprova` | Projeto Comprova | BR | HTML + paginacao |
| `publico` | Publico | PT | Sitemap completo |
| `reuters_fact_check` | Reuters Fact Check | Intl | HTML + API interna |
| `uol_confere` | UOL Confere | BR | HTML + Service + Sitemap fallback |

Detalhes tecnicos de cada spider em [`docs/spiders.md`](docs/spiders.md).

## Arquitetura

```
Spider -> TextCleanupPipeline -> FactCheckPipeline -> Storage
               (200)                  (300)
                                    |       |
                                 Dedupe   RunWriter
                                (SQLite)  (JSONL)
```

- **TextCleanupPipeline**: html.unescape, mojibake repair, NFKC, whitespace
- **FactCheckPipeline**: validacao JSON Schema, deduplicacao, storage
- **DedupeStore**: SQLite com WAL mode, migracao automatica de JSONL legado
- **RunWriter**: file handle persistente, `ensure_ascii=False`
- **Runner**: ate 4 spiders em paralelo via `ProcessPoolExecutor`

Diagrama completo em [`docs/design.md`](docs/design.md).

## Instalacao

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Extras opcionais:

```bash
# Analise e NLP
uv pip install -e ".[analysis]"
python -m spacy download pt_core_news_lg

# Scrapling (anti-bot para observador e reuters)
uv pip install -e ".[scrapling]"
scrapling install --force
```

## Uso

```bash
# Listar spiders
factcheck-scrape list

# Executar uma spider
factcheck-scrape run --spider afp_checamos

# Executar todas (4 em paralelo)
factcheck-scrape run --spider all

# Recoletar ignorando deduplicacao historica
factcheck-scrape run --spider observador --ignore-existing-seen-state

# Agendar execucoes
factcheck-scrape schedule --config configs/schedule.yaml

# Relatorio da ultima execucao
factcheck-scrape report [--count 5] [--json]

# Metricas de qualidade por spider
factcheck-scrape quality [--run-id <id>] [--json]
```

## Saida de dados

```
data/
  runs/<run_id>/
    items.jsonl          # Itens coletados
    run.json             # Metadados da execucao
  state/
    seen_<agency>.db     # Deduplicacao SQLite
logs/
  <run_id>.log           # Logs estruturados (structlog)
```

## Schema

O schema e derivado da dataclass `FactCheckItem` em `src/factcheck_scrape/schema.py` (fonte unica de verdade). A validacao usa `jsonschema.Draft202012Validator`.

**Campos obrigatorios**: `item_id`, `agency_id`, `agency_name`, `spider`, `source_url`, `canonical_url`, `title`, `published_at`, `collected_at`, `run_id`

**Campos opcionais**: `claim`, `summary`, `verdict`, `rating`, `author`, `body`, `language`, `country`, `topics`, `tags`, `entities`, `source_type`

Schema JSON gerado em [`docs/schema.json`](docs/schema.json).

## Testes

```bash
# Unitarios + integracao (165 testes)
python -m pytest tests/

# Smoke tests contra sites reais
python -m pytest tests/ --run-smoke

# Lint
ruff check src/ tests/
```

## Contribuindo

Consulte [`CONTRIBUTING.md`](CONTRIBUTING.md) para o guia de adicao de novas spiders.

## Documentacao

- [`docs/design.md`](docs/design.md) — arquitetura, diagrama Mermaid e decisoes do pipeline
- [`docs/spiders.md`](docs/spiders.md) — contrato tecnico de cada spider
- [`docs/analysis.md`](docs/analysis.md) — regras do modulo de analise/NLP
- [`docs/schema.json`](docs/schema.json) — JSON Schema do item

## Licenca

MIT

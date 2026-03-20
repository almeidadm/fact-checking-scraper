# User Guide

## Requisitos
- Python 3.12
- uv

## Instalacao
```bash
uv venv
uv pip install -e .
uv pip install -e ".[dev]"
```

## Instalacao opcional do Scrapling
Use este extra se voce quiser habilitar o fallback anti-bot com browser para `observador` e `reuters_fact_check`.

```bash
uv pip install -e ".[scrapling]"
scrapling install --force
```

## Ambiente de analise
Os notebooks de EDA e de dataset processado usam o extra `analysis` e dependem do modelo `spaCy pt_core_news_lg`.

```bash
uv pip install -e ".[analysis]"
uv run python -m spacy download pt_core_news_lg
```

Para abrir os notebooks:

```bash
uv run jupyter lab
```

## Testes
```bash
uv run pytest
```

## Rodar spiders manualmente
```bash
factcheck-scrape list
factcheck-scrape run --spider reuters_fact_check
factcheck-scrape run --spider all
factcheck-scrape run --spider observador --ignore-existing-seen-state
```

## Spiders suportadas
- `afp_checamos`
- `agencia_lupa`
- `aos_fatos`
- `boatos_org`
- `e_farsas`
- `estadao_verifica`
- `g1_fato_ou_fake`
- `observador`
- `poligrafo`
- `projeto_comprova`
- `publico`
- `reuters_fact_check`
- `uol_confere`

## Restricoes editoriais
- `poligrafo`: coleta apenas a secao `fact-checks/economia/`.
- `publico`: percorre os sitemaps completos do site, exclui superficies de newsletter e so aceita artigos cujo metadado de palavras-chave contenha `Prova dos Factos`.
- `afp_checamos`, `observador` e `reuters_fact_check`: combinam descoberta inicial em HTML com paginacao por endpoints internos.
- `afp_checamos`: so segue URLs com shape editorial de artigo `doc.afp.com.*` e ignora paginas institucionais como `Como trabalhamos` e `Contato`.
- `uol_confere`: usa a listagem `/confere/` e, em fallback, percorre explicitamente os sitemaps `news-01.xml`, `news-02.xml` e `news-03.xml`, priorizando `ClaimReview.reviewBody`, taxonomia do artigo e tags especificas da pagina em vez do boilerplate generico do portal.

## Politica de qualidade na coleta
- A coleta agora descarta o item ainda na spider quando `title` ou `published_at` sao invalidos.
- Sao tratados como invalidos, no minimo: `title` vazio, `title` igual a URL do artigo, `published_at` vazio e placeholders como `-`, `–` e `—`.
- As spiders nao fazem mais fallback silencioso de `title` para `response.url` nem de `published_at` para `utc_now_iso()`.
- O pipeline continua validando o mesmo contrato como backstop para impedir que spiders futuras persistam itens degradados.

## Perfil de crawl
- `reuters_fact_check` usa um perfil mais conservador por spider, com `CONCURRENT_REQUESTS_PER_DOMAIN=1`, `DOWNLOAD_DELAY=2.0` e `AutoThrottle` habilitado para reduzir rajadas de requests contra a secao da Reuters.
- Se voce precisar endurecer ainda mais a civilidade da coleta, prefira ajustar esse perfil no proprio spider em vez de mudar o runner global e afetar todas as agencias.

## Fallback anti-bot com Scrapling
- O middleware de Scrapling e carregado globalmente, mas fica inativo por padrao.
- No rollout atual, as spiders `observador` e `reuters_fact_check` marcam requests com `request.meta["scrapling"]`.
- O fallback so e tentado quando a resposta normal do Scrapy parece bloqueada, como `403`, `429`, `503` ou HTML com sinais como `Just a moment`.
- No `reuters_fact_check`, o perfil da spider tambem trata `401` como bloqueio recuperavel para listagem, API interna e paginas de artigo.
- Se `scrapling` nao estiver instalado, o crawl segue com Scrapy puro e registra warning estruturado quando o fallback seria necessario.
- Quando o fallback retorna HTML browserizado, o middleware normaliza headers como `Content-Encoding` e `Content-Length` antes de reinjetar a resposta no Scrapy, evitando incompatibilidades de descompressao com o corpo ja materializado.
- A integracao reutiliza uma sessao `StealthySession` por spider e fecha a sessao ao encerrar a execucao.
- Em `observador` e `reuters_fact_check`, o perfil padrao do fallback usa browser visivel (`headless=False`), `real_chrome=True`, `block_webrtc=True`, `hide_canvas=True` e `allow_webgl=True`.
- Mesmo quando o fallback falha, a spider `observador` deixa de persistir paginas de desafio como se fossem noticias validas.
- Mesmo quando o fallback falha, a spider `reuters_fact_check` nao persiste a landing page da secao nem artigos que seguem bloqueados apos a tentativa browserizada.

## Recoleta ignorando deduplicacao historica
- Use `--ignore-existing-seen-state` quando voce precisar recolher uma agencia inteira sem reaproveitar o arquivo `data/state/seen_<agency>.jsonl`.
- Esse modo ignora apenas o historico carregado do disco; a execucao atual continua deduplicando URLs repetidas dentro do proprio run.
- O arquivo de estado continua preservado e nao e apagado automaticamente.

## Agendar spiders
Edite `configs/schedule.yaml` e ative os jobs desejados.

```bash
factcheck-scrape schedule --config configs/schedule.yaml
```

## Saida de dados bruta
Cada execucao cria:
- `data/runs/<run_id>/items.jsonl`
- `data/runs/<run_id>/run.json`

A deduplicacao fica em:
- `data/state/seen_<agency_id>.jsonl`

## Trilha de notebooks por spider
Os notebooks gerais continuam em `notebooks/01_runs_metadata.ipynb`, `notebooks/02_data_quality.ipynb` e `notebooks/03_content_metadata.ipynb`.

A trilha nova adiciona:
- `notebooks/spiders/<spider>_eda.ipynb`: um notebook por spider, com selecao de run, overview, qualidade, limpeza, NLP e export JSONL processado.
- `notebooks/99_processed_snapshot.ipynb`: consolida os spiders, grava o corpus unificado e registra `manifest.json`.

Cada notebook por spider segue a mesma estrutura:
- selecao do run e evidencias do player;
- overview de volume, cobertura temporal e qualidade;
- histograma de tamanho de texto por `original_label` e `standard_label`;
- contagem de categoria, topics/tags e distribuicao temporal;
- campos ausentes e datas invalidas;
- limpeza e normalizacao;
- NLP com stop words, lemmas e NER;
- export do JSONL processado.

## Politica de selecao de run para analise
- O modulo `src/factcheck_scrape/analysis/` seleciona o run mais recente por spider.
- Se o run mais recente estiver vazio ou invalido para export, o notebook usa fallback para o run mais recente com `items_stored > 0` e `items.jsonl` presente.
- Diretorios sem `run.json` sao ignorados na selecao.
- Perfis por spider registram regras explicitas de limpeza, composicao de `analysis_text` e diagnosticos conhecidos, como o caso de `uol_confere`.

## Schema do dataset processado
Cada registro processado inclui:
- `record_id`, `source_record_id`, `dataset_id`
- `source_url`, `published_at`, `language`, `title`, `author`, `subtitle`
- `claim_text`, `body_text`, `analysis_text`, `text_for_ner`
- `text_without_stopwords`, `lemmatized_text`
- `original_label`, `standard_label`, `category`
- `entities`
- `variant`
- `metadata`

Campos relevantes de `metadata`:
- `analysis_text_length`, `entity_count`
- `spider`, `agency_id`, `agency_name`
- `run_id`, `latest_run_id`, `fallback_applied`
- `source_type`, `source_topics`, `source_tags`, `source_rating`

## Saida de dados processada
O snapshot processado usa:
- `data/processed/<snapshot_id>/spiders/<spider>.jsonl`
- `data/processed/<snapshot_id>/factcheck_scrape_unified.jsonl`
- `data/processed/<snapshot_id>/manifest.json`

O manifesto registra, por spider:
- `selected_run_id`
- `latest_run_id`
- `latest_valid_run_id`
- `fallback_applied`
- `exported_records`
- `cleaning_flags`

## Como implementar uma spider real
1. Abra a spider em `src/factcheck_scrape/spiders/`.
2. No metodo `parse`, descubra URLs de artigos e paginacao.
3. No metodo `parse_article`, extraia `source_url`, `title`, `published_at` e outros campos.
4. Antes de persistir, valide os campos centrais com `self.validate_extracted_article(...)`.
5. Use `self.build_item(...)` para construir o item.
6. Evite fallbacks silenciosos para `title` e `published_at`; se a pagina nao oferecer esses campos de forma confiavel, descarte o item.
7. Cubra a spider com fixtures e testes em `tests/fixtures/spiders/` e `tests/test_spiders.py`.
8. `yield` o item para o pipeline.

## Logs
Os logs sao gerados em `logs/<run_id>.log` e tambem no stdout, no formato JSON.

# Changelog

## [Unreleased]

## [0.1.0] - 2026-03-19

### Added

- Adicionado `README.md` na raiz com visao geral do projeto, arquitetura, instalacao, CLI, estrutura de saida, fluxo de desenvolvimento e links para a documentacao principal.
- Adicionado o pacote `src/factcheck_scrape/analysis/` com perfis por spider, selecao de runs com fallback, parsing de datas, limpeza textual, composicao de `analysis_text`, taxonomia de `standard_label`, NLP com spaCy e export do dataset processado com `manifest.json`.
- Adicionado `docs/analysis.md` com documentacao detalhada das regras de negocio do submodulo `analysis`, incluindo selecao de runs, normalizacao, contrato processado e diagramas Mermaid do fluxo `raw -> processed`.
- Adicionados `13` notebooks em `notebooks/spiders/`, um por spider, com secoes fixas para selecao de run, overview, qualidade, limpeza, NLP e export JSONL processado.
- Adicionado `notebooks/99_processed_snapshot.ipynb` para consolidar os spiders, validar o contrato processado, gravar o corpus unificado e comparar o panorama agregado entre spiders.
- Adicionados testes unitarios e smoke tests para fallback de runs, parsing de datas, limpeza, normalizacao de labels, composicao de `analysis_text`, shape de NER e export de snapshot processado.
- Documento `analise_spiders_comentarios.md` na raiz com a analise dos comentarios das spiders, os dados ausentes por arquivo e as proximas etapas de implementacao.
- Implementadas as spiders `afp_checamos`, `agencia_lupa`, `aos_fatos`, `boatos_org`, `e_farsas`, `observador`, `poligrafo`, `projeto_comprova`, `publico` e `reuters_fact_check`, com suporte a descoberta de artigos, paginação e parse dos campos principais do schema.
- Adicionados fixtures e testes parametrizados para listagens, paginação AJAX/API/sitemap, parse de artigos e registro das spiders na CLI.
- Adicionado um downloader middleware opt-in que integra Scrapy com `scrapling[fetchers]` para retry com `StealthySession` quando respostas marcadas parecem bloqueadas por anti-bot.
- Adicionados testes unitarios do middleware de Scrapling cobrindo fallback por status, pagina Cloudflare, conversao de respostas HTML/JSON e degradacao graciosa sem quebrar o crawl.
- Adicionado o modo `--ignore-existing-seen-state` para permitir recolheita completa de uma agencia sem reutilizar o estado historico de deduplicacao.

### Changed

- `pyproject.toml` agora aponta o campo `readme` para `README.md`, alinhando a metadata do pacote com a documentacao principal da raiz.
- O Ruff agora ignora `E402` em notebooks `.ipynb`, preservando o bootstrap local de `sys.path` usado para carregar `eda_utils` sem quebrar o lint do repositório.
- `notebooks/eda_utils.py` agora atua como camada leve para os notebooks e delega selecao, processamento e export ao pacote `factcheck_scrape.analysis`.
- `pyproject.toml` agora inclui `spacy` no extra `analysis` e o guia do usuario documenta o download de `pt_core_news_lg`.
- `docs/user_guide.md` e `docs/design.md` agora documentam a trilha `runs -> notebooks por spider -> processed snapshot`, as regras de selecao de run e o layout de saida em `data/processed/<snapshot_id>/`.
- `docs/user_guide.md` agora documenta a lista completa de spiders suportadas, o fluxo de testes com `uv run pytest` e as restricoes editoriais de `poligrafo` e `publico`.
- A coleta agora valida `title` e `published_at` ainda na spider e deixa de persistir itens com titulo vazio, titulo igual a URL ou datas placeholder; o pipeline replica esse contrato como backstop.
- `publico` agora percorre os sitemaps completos e confia na validacao semantica de `Prova dos Factos` na pagina do artigo, sem filtrar discovery por `/economia/` e sem aceitar newsletters como se fossem checagens.
- `estadao_verifica` e `uol_confere` agora reutilizam os helpers compartilhados de JSON-LD, canonicalizacao, taxonomia e `ClaimReview` da base das spiders.
- `uol_confere` agora prioriza `ClaimReview.reviewBody`, tags reais do artigo e taxonomia especifica da pagina, em vez de resumir itens com o boilerplate generico do portal.
- `projeto_comprova` agora normaliza o veredito bruto para o prefixo semantico antes de `:` durante a coleta, preservando o texto explicativo em `summary`.
- `agencia_lupa` agora prefere `claimReviewed` e `reviewRating` estruturados quando `ClaimReview` esta disponivel.
- `reuters_fact_check` agora usa um perfil de crawl mais conservador, com requests serializados por dominio, `DOWNLOAD_DELAY` e `AutoThrottle`, para reduzir rajadas contra a Reuters.
- `uol_confere` agora agenda explicitamente os sitemaps `news-01.xml`, `news-02.xml` e `news-03.xml` no fallback, em vez de depender de incremento sequencial do nome do arquivo.
- `observador` agora marca listagem, artigos e paginação interna com perfil opt-in de Scrapling, mas so usa o browser quando a resposta do Scrapy aparenta bloqueio.
- `docs/design.md` e `docs/user_guide.md` agora documentam o fluxo opcional de fallback anti-bot com Scrapling no caminho de download.
- `observador` agora descarta paginas de desafio do Cloudflare em vez de persisti-las como itens validos e usa um perfil stealth mais forte com browser visivel e `real_chrome`.
- `reuters_fact_check` agora usa o fallback opt-in de Scrapling na listagem, na API interna e nas paginas de artigo, com perfil stealth reforcado e tratamento de `401` como bloqueio recuperavel.

### Fixed

- `agencia_lupa` agora ignora links de listagem fora de `/checagem/`, como entradas de `/jornalismo/`, alinhando o crawl ao escopo editorial esperado e restaurando a cobertura do teste da spider.
- `afp_checamos` agora segue apenas URLs editoriais `doc.afp.com.*`, ignora paginas institucionais na descoberta e deixa de aceitar `published_at="-"` ou vereditos numericos como se fossem artigos validos.
- `estadao_verifica` agora resolve URLs canonicas relativas antes da deduplicacao, evitando itens com canonical malformada como `https:///...`.
- `uol_confere` agora rejeita explicitamente resumos genericos do portal, evitando persistir a string repetida `Veja as principais noticias...` como conteudo do artigo.
- `publico` agora pode encontrar artigos validos fora de `/economia/` sem relaxar o filtro editorial de `Prova dos Factos`.
- O middleware de Scrapling agora normaliza respostas browserizadas antes de devolve-las ao Scrapy, removendo headers de transporte stale como `Content-Encoding` e evitando falhas de descompressao como o `BadGzipFile` observado na Reuters.
- `reuters_fact_check` agora ignora a landing page `/fact-check/portugues/` durante a descoberta de links e deixa de persisti-la como se fosse um artigo valido.
- `reuters_fact_check` agora registra bloqueios persistentes da Reuters e aborta apenas o request afetado, em vez de tentar persistir respostas incompletas ou perder silenciosamente a causa da falha.

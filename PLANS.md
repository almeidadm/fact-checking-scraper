# EDA e Dataset Processado por Spider

**Resumo**
- Criar uma trilha de análise focada em `1 notebook por spider` em `notebooks/spiders/`, sem substituir os notebooks gerais já existentes.
- Cada notebook fará: seleção do run, overview do player, evidências de qualidade, limpeza, normalização, NLP com `spaCy pt_core_news_lg` e export do dataset processado daquele spider.
- Adicionar um notebook final `notebooks/99_processed_snapshot.ipynb` para consolidar todos os spiders, gerar o corpus unificado e registrar um `manifest.json`.
- Fonte principal: usar o run mais recente por spider; quando o mais recente estiver vazio ou inválido, aplicar fallback para o último run com `items_stored > 0`. Isso afeta `uol_confere`, que deve usar `20260314T232736Z-2cced5c3` em vez do run vazio de `2026-03-15`. Diretórios sem `run.json` devem ser ignorados.

**Mudanças de Implementação**
- Adicionar um módulo reutilizável e testável em `src/factcheck_scrape/analysis/` para concentrar:
  - seleção de runs por spider e geração de manifesto;
  - parsing/normalização de datas;
  - limpeza textual, `html.unescape`, normalização Unicode, colapso de whitespace e heurísticas leves de correção de encoding;
  - composição de `analysis_text`;
  - mapeamento `original_label -> standard_label`;
  - remoção de stop words, lematização e NER com `spaCy`.
- Manter `notebooks/eda_utils.py` apenas como camada leve de apoio para visualização/carga, chamando o módulo novo em vez de concentrar toda a lógica de processamento dentro do notebook.
- Criar um arquivo de perfis por spider com regras explícitas de seleção e limpeza. Regras iniciais:
  - `observador`: ignorar o `title` genérico `"Observador"` na composição do texto e usar `claim + summary` como base principal.
  - `publico`: decodificar entidades HTML e converter `published_at` em formato RFC 822 para ISO 8601.
  - `afp_checamos` e `aos_fatos`: remover do export processado linhas claramente não editoriais, como títulos genéricos do tipo `"Como trabalhamos"` e `"Últimas notícias"`.
  - `projeto_comprova`: extrair o prefixo semântico do veredito antes do `:` para normalização.
  - `g1_fato_ou_fake`: mapear `FAKE/FATO` diretamente.
  - `uol_confere`: notebook com seção diagnóstica do run vazio de `2026-03-15` e processamento usando o último run bem-sucedido.
- Criar `notebooks/spiders/<spider>_eda.ipynb` com seções fixas:
  - seleção do run e evidências do player;
  - overview de volume, cobertura temporal e qualidade;
  - histograma de tamanho de texto por `original_label` e por `standard_label`;
  - contagem de categoria, topics/tags e distribuição temporal;
  - campos ausentes e datas inválidas;
  - limpeza e normalização;
  - NLP com stop words, lemmas e NER;
  - export do JSONL processado.
- Criar `notebooks/99_processed_snapshot.ipynb` para:
  - concatenar os exports por spider;
  - validar o schema final;
  - gravar corpus combinado e manifesto;
  - produzir comparação agregada entre spiders.
- Atualizar `pyproject.toml` para incluir `spacy` no extra `analysis` e documentar a instalação do modelo com `uv run python -m spacy download pt_core_news_lg`.
- Atualizar `docs/user_guide.md`, `docs/design.md` e `CHANGELOG.md` na mesma entrega. Em `design.md`, incluir o fluxo novo `runs -> notebooks por spider -> processed snapshot`.

**Interfaces e Schema Público**
- Export por snapshot em `data/processed/<snapshot_id>/spiders/<spider>.jsonl`.
- Export consolidado em `data/processed/<snapshot_id>/factcheck_scrape_unified.jsonl`.
- Manifesto em `data/processed/<snapshot_id>/manifest.json` com `snapshot_id`, `selected_run_id` por spider, `latest_run_id`, `fallback_applied`, contagem de registros exportados e flags de limpeza relevantes.
- Cada registro processado deve seguir o contrato abaixo, alinhado ao exemplo externo:
  - `record_id`: `factcheck_scrape_<spider>:<item_id>`
  - `source_record_id`: `item_id`
  - `dataset_id`: `factcheck_scrape_<spider>`
  - `source_url`, `published_at`, `language`, `title`, `author`, `subtitle`
  - `claim_text`: claim limpo
  - `body_text`: summary limpo
  - `analysis_text`: composição normalizada e em minúsculas de `title`, `claim` e `summary`, com deduplicação simples e exclusão de campos genéricos por spider
  - `text_for_ner`: igual a `analysis_text`
  - `text_without_stopwords`, `lemmatized_text`
  - `original_label`: veredito bruto
  - `standard_label`
  - `category`: `topics[0]` quando existir; senão `tags[0]`; senão `null`
  - `entities`: lista de objetos `{text, label, start_char, end_char}`
  - `variant`: fixo em `claim_summary`
  - `metadata`: `analysis_text_length`, `entity_count`, `spider`, `agency_id`, `agency_name`, `run_id`, `latest_run_id`, `fallback_applied`, `source_type`, `source_topics`, `source_tags`, `source_rating`
- Taxonomia enxuta de `standard_label`:
  - `true`: `Verdadeiro`, `Certo`, `FATO`, `Comprovado`
  - `false`: `Falso`, `Errado`, `FAKE`, `Montagem`
  - `misleading`: `Enganoso`, `Enganador`, `Falta contexto`, `Fora de contexto`, `Sem contexto`, `Descontextualizado`, `distorcido`, `não_é_bem_assim`, `exagerado`, `Esticado`, `Verdadeiro, mas…` e variantes prefixadas como `Enganoso:` ou `Contextualizando:`
  - `unverified`: `Inconclusivo`, `Sem provas`, `Sem indícios`, `Sem evidências`, `Sem evidência`, `Sem registro`
  - `satire`: `Sátira`, `Pimenta na Língua`
  - `other`: ruído editorial, URL, número isolado e valores não classificáveis
  - `missing`: nulo ou vazio

**Plano de Testes**
- Testes unitários para seleção de run e fallback de `uol_confere`.
- Testes unitários para parsing de datas ISO, date-only, RFC 822 e placeholders inválidos como `-`.
- Testes unitários para limpeza textual: HTML entities, whitespace, lowercasing e descarte de linhas genéricas por spider.
- Testes unitários para normalização de veredito e mapeamento de `standard_label`, incluindo casos com prefixos longos do `projeto_comprova`.
- Testes unitários para composição de `analysis_text`, garantindo que `observador` não use o título genérico.
- Testes unitários para shape do output de NER e metadados derivados.
- Smoke test do export JSONL e do `manifest.json` com um subconjunto pequeno de fixtures; os notebooks em si ficam com validação manual/smoke de abertura, não com execução integral em CI.

**Assumptions**
- O escopo é criar `13 notebooks individualizados`, um por spider, mais `1 notebook` final de consolidação.
- O dataset processado será `JSONL` como formato principal, sem adicionar `parquet` nesta etapa para manter simplicidade.
- Não haverá deduplicação entre spiders no corpus processado; a deduplicação continua sendo intra-spider/intra-run via pipeline existente.
- O trabalho altera documentação e changelog, mas não pressupõe criação de tag ou bump de versão nesta entrega.

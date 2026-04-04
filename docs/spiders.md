# Contratos dos Spiders

Referencia tecnica de cada spider: URL base, mecanismo de descoberta, campos extraidos
vs inferidos, fragilidades conhecidas e data da ultima validacao.

Ultima atualizacao: 2026-04-03

---

## afp_checamos

| | |
|---|---|
| **Agencia** | AFP Checamos |
| **Pais** | BR |
| **URL base** | `https://checamos.afp.com/list` |
| **Descoberta** | Listagem HTML + paginacao AJAX (Drupal Views) |
| **Filtro** | Links com prefixo `/doc.afp.com.`; exclui paginas editoriais |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict` quando ClaimReview nao fornece) |
| **Fragilidades** | `view_name=rubriques` e `view_display_id=page_2` hardcoded no AJAX; User-Agent customizado |
| **Scrapling** | Nao |

---

## agencia_lupa

| | |
|---|---|
| **Agencia** | Agencia Lupa |
| **Pais** | BR |
| **URL base** | `https://www.agencialupa.org/checagem/` |
| **Descoberta** | Listagem HTML com paginacao via `link[rel='next']` |
| **Filtro** | Links contendo `/checagem/` |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description`; seletor `h1::text` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict` se ClaimReview nao fornece) |
| **Fragilidades** | Seletor CSS `div.archive-body article a.feed-link` depende do tema WordPress |
| **Scrapling** | Nao |

---

## aos_fatos

| | |
|---|---|
| **Agencia** | Aos Fatos |
| **Pais** | BR |
| **URL base** | `https://www.aosfatos.org/noticias/?formato=checagem` |
| **Descoberta** | Listagem HTML com paginacao por query param `page=` |
| **Filtro** | Links contendo `/noticias/`; exclui a propria listagem |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Article`/`Review`) |
| **Fallback** | Meta tags `og:title`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict`) |
| **Fragilidades** | `published_at` depende exclusivamente do JSON-LD (sem fallback meta tag) |
| **Scrapling** | Nao |

---

## boatos_org

| | |
|---|---|
| **Agencia** | Boatos.org |
| **Pais** | BR |
| **URL base** | Sitemaps anuais `https://www.boatos.org/sitemap-posttype-post.{year}.xml` (2013-atual) |
| **Descoberta** | Sitemap XML hierarquico |
| **Filtro** | Todos os URLs do sitemap |
| **Fonte primaria** | JSON-LD (`NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict e rating (100% via `infer_verdict` — nao tem ClaimReview); claim (remove `#boato` do titulo) |
| **Fragilidades** | Sem ClaimReview no JSON-LD; volume alto (~12k+ artigos desde 2013) |
| **Scrapling** | Nao |

---

## e_farsas

| | |
|---|---|
| **Agencia** | E-farsas |
| **Pais** | BR |
| **URL base** | `https://www.e-farsas.com/` |
| **Descoberta** | Listagem HTML com paginacao via link "Seguinte" |
| **Filtro** | Links extraidos de `.mvp-main-blog-text > a` |
| **Fonte primaria** | JSON-LD (`ClaimReview`/`NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict` em topics + tags + title + summary); claim = title |
| **Fragilidades** | Seletores do tema MVP (`mvp-main-blog-text`); paginacao depende de texto "Seguinte"; verditos inferidos de categorias do WordPress |
| **Scrapling** | Nao |

---

## estadao_verifica

| | |
|---|---|
| **Agencia** | Estadao Verifica |
| **Pais** | BR |
| **URL base** | `https://www.estadao.com.br/arc/outboundfeeds/sitemap-index-by-day/?outputType=xml` |
| **Descoberta** | Sitemap XML index (Arc Publishing) |
| **Filtro** | URLs contendo `/estadao-verifica/` |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Report`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict` se ClaimReview nao fornece) |
| **Fragilidades** | Nenhuma critica — sitemap e JSON-LD sao estaveis |
| **Scrapling** | Nao |

---

## g1_fato_ou_fake

| | |
|---|---|
| **Agencia** | G1 Fato ou Fake |
| **Pais** | BR |
| **URL base** | `https://g1.globo.com/sitemap/g1/sitemap.xml` |
| **Descoberta** | Sitemap XML hierarquico |
| **Filtro** | URLs contendo `/fato-ou-fake/` |
| **Fonte primaria** | JSON-LD (`NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Microdata CSS: `h1.content-head__title`, `meta[itemprop='datePublished']`, `h2.content-head__subtitle`, `main[itemtype]` |
| **Campos extraidos** | title, published_at, canonical_url, summary, author, body, language, topics, tags, source_type |
| **Campos inferidos** | verdict (via regex `VERDICT_PATTERN` em titulo e `<strong>`); claim (remove prefixo "E #FAKE que") |
| **Fragilidades** | Seletores microdata especificos do CMS Globo (`content-head__title`, `content-head__subtitle`); regex de veredicto |
| **Scrapling** | Nao |

---

## observador

| | |
|---|---|
| **Agencia** | Observador |
| **Pais** | PT |
| **URL base** | `https://observador.pt/factchecks/` |
| **Descoberta** | Listagem HTML + API JSON paginada (`wp-json/obs_api/v4/grids/filter/archive/obs_factcheck`) |
| **Filtro** | Links contendo `/factchecks/` |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `description`; seletor `h1::text`, `time::attr(datetime)` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict`) |
| **Fragilidades** | Depende de Scrapling com `real_chrome=True` (Cloudflare); deteccao de challenge pages |
| **Scrapling** | Sim (`real_chrome=True`, `block_webrtc=True`, `hide_canvas=True`) |

---

## poligrafo

| | |
|---|---|
| **Agencia** | Poligrafo |
| **Pais** | PT |
| **URL base** | `https://poligrafo.sapo.pt/fact-checks/economia/` |
| **Descoberta** | Listagem HTML com paginacao via `a.page-numbers.next` |
| **Filtro** | Links contendo `/fact-check/` em container Elementor |
| **Fonte primaria** | CSS/meta tags (sem JSON-LD) |
| **Fallback** | N/A — CSS e a unica fonte |
| **Campos extraidos** | title, published_at, canonical_url, summary, verdict, author, body, language, topics |
| **Campos inferidos** | Nenhum — todos via seletores CSS diretos |
| **Fragilidades** | Sem JSON-LD — totalmente dependente de seletores Elementor (`#footer-result .fact-check-result span`, `.custom-post-date-time`, `.post-excerpt`); parsing de data em portugues com regex; User-Agent customizado |
| **Scrapling** | Nao |

---

## projeto_comprova

| | |
|---|---|
| **Agencia** | Projeto Comprova |
| **Pais** | BR |
| **URL base** | `https://projetocomprova.com.br/?filter=verificacao` |
| **Descoberta** | Listagem HTML com paginacao via `.pagination a` |
| **Filtro** | Links contendo `/publica` |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (extrai prefixo antes de `:` do ClaimReview + `infer_verdict`) |
| **Fragilidades** | Seletor `a.answer__title__link` especifico; `published_at` depende exclusivamente do JSON-LD |
| **Scrapling** | Nao |

---

## publico

| | |
|---|---|
| **Agencia** | Publico |
| **Pais** | PT |
| **URL base** | `https://www.publico.pt/sitemaps/sitemapindex.xml` |
| **Descoberta** | Sitemap XML hierarquico completo |
| **Filtro** | Artigos com keyword "prova dos factos" em `meta[name='keywords']` ou `meta[name='news_keywords']`; exclui `/newsletter/` |
| **Fonte primaria** | JSON-LD (`NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, author, body, language, topics, tags, source_type |
| **Campos inferidos** | verdict e rating (via `infer_verdict` em titulo + keywords); claim (remove sufixo de veredicto do titulo) |
| **Fragilidades** | Sem ClaimReview; filtragem por keyword "prova dos factos" pode perder artigos com keywords diferentes; volume muito alto de sitemap (todos os artigos do Publico sao processados antes do filtro) |
| **Scrapling** | Nao |

---

## reuters_fact_check

| | |
|---|---|
| **Agencia** | Reuters Fact Check |
| **Pais** | (internacional) |
| **URL base** | `https://www.reuters.com/fact-check/portugues/` |
| **Descoberta** | Listagem HTML + API interna PF (`/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1`) |
| **Filtro** | URLs contendo `/fact-check/portugues/`; exclui a listagem raiz |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`, `description` |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict`) |
| **Fragilidades** | Anti-bot agressivo (Cloudflare); rate limiting proprio (`DOWNLOAD_DELAY=2.0`, `CONCURRENT_REQUESTS_PER_DOMAIN=1`); zona cinzenta legal |
| **Scrapling** | Sim (`real_chrome=True`, `block_webrtc=True`, `hide_canvas=True`) |

---

## uol_confere

| | |
|---|---|
| **Agencia** | UOL Confere |
| **Pais** | BR |
| **URL base** | `https://noticias.uol.com.br/confere/` |
| **Descoberta** | Listagem HTML + endpoint service JSON + sitemap fallback (3 niveis) |
| **Filtro** | Links contendo `/confere/` |
| **Fonte primaria** | JSON-LD (`ClaimReview` + `NewsArticle`/`Article`/`WebPage`) |
| **Fallback** | Meta tags `og:title`, `article:published_time`; seletores CSS (`h2.content-head__subtitle`, `article-topics`, `article-tags`); sitemap fallback em caso de 403/404 |
| **Campos extraidos** | title, published_at, canonical_url, summary, claim, verdict, rating, author, body, language, topics, tags, entities, source_type |
| **Campos inferidos** | verdict (via `infer_verdict`); summary generico filtrado (prefixo UOL descartado) |
| **Fragilidades** | Complexidade alta (358 linhas, 3 niveis de fallback); headers customizados para evitar 403; paginacao via `data-request` JSON em botao "Ver mais" |
| **Scrapling** | Nao |

---

## Tabela Resumo

| Spider | Pais | Descoberta | JSON-LD | ClaimReview | Scrapling | Fragilidade |
|---|---|---|---|---|---|---|
| afp_checamos | BR | AJAX | Sim | Sim | Nao | AJAX params hardcoded |
| agencia_lupa | BR | HTML | Sim | Sim | Nao | Seletores WordPress |
| aos_fatos | BR | HTML | Sim | Sim | Nao | Sem fallback de data |
| boatos_org | BR | Sitemap | Sim | Nao | Nao | Sem ClaimReview |
| e_farsas | BR | HTML | Sim | Parcial | Nao | Seletores tema MVP |
| estadao_verifica | BR | Sitemap | Sim | Sim | Nao | Nenhuma |
| g1_fato_ou_fake | BR | Sitemap | Sim | Nao | Nao | Microdata CMS Globo |
| observador | PT | HTML+API | Sim | Sim | Sim | Cloudflare |
| poligrafo | PT | HTML | Nao | Nao | Nao | Tudo via CSS |
| projeto_comprova | BR | HTML | Sim | Sim | Nao | Seletor especifico |
| publico | PT | Sitemap | Sim | Nao | Nao | Filtro keyword |
| reuters_fact_check | Intl | HTML+API | Sim | Sim | Sim | Anti-bot |
| uol_confere | BR | HTML+Service | Sim | Sim | Nao | Complexidade |

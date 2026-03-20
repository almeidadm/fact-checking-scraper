# Spider Extraction Quality Review

Date: 2026-03-17

Scope:

- Review of `src/factcheck_scrape/spiders/`, the shared extraction helpers, and spider-related tests.
- Focus on selector quality, parsing logic, discovery strategy, and how extraction failures are handled.
- This review is based on local code and fixtures only. No live site validation was performed.

Validation performed:

- `uv run pytest tests/test_spiders.py tests/test_uol_confere_pagination.py tests/test_middlewares.py -q`
- Result: all tests passed locally.

## Executive summary

The repository has a solid baseline for fact-check scraping: most spiders are JSON-LD-first, several sites use source-specific discovery paths instead of generic crawling, and the Reuters/Observador anti-bot strategy is materially better than the rest of the fleet.

The main weakness is data-quality protection. Most spiders still emit items when core extraction fails, substituting `response.url` for `title` and `utc_now_iso()` for `published_at`. That means selector drift can silently produce low-quality but schema-valid rows instead of failing fast. Stored run artifacts already show that this is not just a theoretical risk: `afp_checamos` is collecting non-article pages, `uol_confere` is frequently storing generic portal summaries, and `projeto_comprova` is leaking long explanatory text into the `verdict` field.

Test coverage is also uneven. Three spiders are effectively unreviewed by fixture-based extraction tests, and even the covered spiders mostly assert only presence of a few fields instead of checking whether the extracted values are semantically correct.

## Strengths

- Shared JSON-LD helpers in `src/factcheck_scrape/spiders/base.py:49-228` reduce per-site selector noise and make the stronger spiders rely on structured metadata before brittle HTML selectors.
- Reuters and Observador use explicit anti-block handling, wait selectors, and controlled pagination through internal APIs instead of only scraping rendered listing HTML:
  - `src/factcheck_scrape/spiders/reuters_fact_check.py:39-87`
  - `src/factcheck_scrape/spiders/observador.py:36-109`
  - `src/factcheck_scrape/middlewares.py:187-320`
- Several spiders use discovery sources with inherently better coverage than homepage crawling:
  - sitemaps in `publico.py`, `boatos_org.py`, `g1_fato_ou_fake.py`, `estadao_verifica.py`
  - AJAX/API pagination in `afp_checamos.py`, `observador.py`, `reuters_fact_check.py`, `uol_confere.py`

## Prioritized findings

### 1. High: extraction failures are masked instead of rejected

This is the biggest data-quality risk in the repo.

Across the spider set, missing `title` and `published_at` are logged but the item is still emitted with fallback values:

- `title=title or response.url`
- `published_at=published_at or utc_now_iso()`

Examples:

- `src/factcheck_scrape/spiders/aosfatos.py:64-77`
- `src/factcheck_scrape/spiders/publico.py:81-94`
- `src/factcheck_scrape/spiders/reuters_fact_check.py:174-186`
- `src/factcheck_scrape/spiders/uol_confere.py:176-188`

Because `src/factcheck_scrape/pipelines.py:64-90` validates only field presence and not field quality, a broken selector can still pass the pipeline as a valid item. `src/factcheck_scrape/schema.py:82-91` enforces completeness, but not correctness.

Impact:

- silent contamination of `items.jsonl`
- publication timestamps that reflect crawl time instead of article time
- titles that degrade to URLs and still look valid to downstream systems
- difficulty distinguishing a real sparse article from a selector regression

This failure mode is already visible in local data. In `data/runs/20260315T010005Z-1d265f16/items.jsonl`, `afp_checamos` stored `https://checamos.afp.com/Como-trabalhamos` with `published_at="-"`, no summary, and no verdict. That row should have been rejected or filtered much earlier.

### 2. High: `AfpChecamosSpider` is leaking non-article pages and malformed verdict/date fields

`src/factcheck_scrape/spiders/afp_checamos.py:148-169` accepts links from three broad selectors and only excludes `/list` and `/views/ajax`. There is no positive article-shape filter, no section allowlist, and no negative filtering for editorial pages such as "Como trabalhamos".

The same spider also trusts raw ClaimReview rating fields through `src/factcheck_scrape/spiders/base.py:214-228`, where `bestRating` can be treated as a fallback verdict. In practice that produces values like `"1"` and `"5"` as verdict labels when a human-readable label is absent.

Observed output from `data/runs/20260315T010005Z-1d265f16/items.jsonl`:

- one sampled row is `https://checamos.afp.com/Como-trabalhamos` with `published_at="-"`, `summary=null`, `verdict=null`
- 3964 of 3982 AFP rows in that run have `published_at` without an ISO timestamp
- sampled verdicts include `"1"` and `"5"`

This makes AFP the clearest example of selector breadth and weak field normalization directly degrading extracted data.

### 3. High: `UolConfereSpider` is producing low-fidelity summaries and no taxonomy

`src/factcheck_scrape/spiders/uol_confere.py:327-333` treats `NewsArticle.description` or page meta description as the article summary. On UOL Confere, that frequently resolves to a generic portal snippet rather than article-specific content. At the same time, `src/factcheck_scrape/spiders/uol_confere.py:355-372` only extracts taxonomy from `NewsArticle.articleSection` and `keywords`, which appear to be absent in many real pages.

Observed output from `data/runs/20260315T155922Z-f06891f9/items.jsonl`:

- 779 of 906 rows share the same generic summary: `Veja as principais notícias e manchetes do dia no Brasil e no Mundo. Leia textos e assista a vídeos de Política, Cotidiano, Crimes e mais.`
- 906 of 906 rows have empty `topics`
- 906 of 906 rows have empty `tags`

The discovery strategy itself is reasonably resilient because it combines the `/confere/` index, a service endpoint, and sitemap fallback. The weak point is article-field quality after discovery succeeds.

### 4. Medium: `PublicoSpider` discovery is over-constrained and likely to miss valid fact-checks

`src/factcheck_scrape/spiders/publico.py:25-28` only follows sitemap URLs containing `/economia/`, and `src/factcheck_scrape/spiders/publico.py:97-103` then applies a second semantic filter requiring `Prova dos Factos` in keywords.

The local fixtures already show why this is risky:

- the sitemap entry is under `/economia/`: `tests/fixtures/spiders/publico/urlset.xml:3-5`
- the article canonical URL is under `/politica/`: `tests/fixtures/spiders/publico/article_prova.html:12-19`

So the spider currently depends on a section-path heuristic that is weaker than the article-level semantic check it already has. If Publico publishes or canonicalizes fact-checks outside `/economia/`, the spider will miss them before parsing begins.

### 5. Medium: `ProjetoComprovaSpider` is still leaking explanatory prose into `verdict`

`src/factcheck_scrape/spiders/projeto_comprova.py:56-64` relies on generic ClaimReview extraction, but real Comprova pages appear to expose verdict text in a longer human sentence. The downstream analysis layer already compensates for this with `extract_label_prefix_before_colon=True` in `src/factcheck_scrape/analysis/profiles.py:99-104`, which is a strong sign that raw extraction is not returning a normalized verdict.

Observed output from `data/runs/20260315T010005Z-1d265f16/items.jsonl`:

- sampled verdict: `Enganoso: Embora a covid-19 contribua para casos de SRAG, os dados no Brasil não indicam um aumento anormal nem caracterizam um surto da doença.`
- the same full sentence is duplicated into `rating`

This is good enough for storage, but not good enough for consistent downstream labeling unless later cleanup continues to repair it.

### 6. Medium: test coverage is uneven and under-asserts extraction quality

The current suite is useful but not sufficient for selector quality.

Coverage gaps:

- `tests/test_spiders.py:30-44` does not even include `estadao_verifica`, `g1_fato_ou_fake`, or `uol_confere` in the spider-registry expectation set.
- `tests/test_spiders.py:448-545` has article fixture tests for ten spiders, but not for `EstadaoVerificaSpider`, `G1FatoOuFakeSpider`, or `UolConfereSpider`.
- `tests/test_uol_confere_pagination.py:10-58` only covers UOL listing/pagination helpers, not article extraction.

Assertion depth is also shallow. For the spiders that are tested, the common article test only checks:

- `source_url`
- non-empty `canonical_url`
- non-empty `title`
- non-empty `published_at`
- `country`
- sometimes `verdict`

It does not verify `claim`, `summary`, `topics`, `tags`, `entities`, or `source_type`, even though these are core quality fields for downstream analysis.

The most important consequence is that all spider tests can pass while obviously degraded output still lands in stored runs. That is exactly what the local artifact sampling shows.

### 7. Medium: several listing selectors are either too broad or too brittle

Examples of brittle selectors:

- `src/factcheck_scrape/spiders/agencia_lupa.py:94-109` uses a single very specific selector: `div.archive-body article a.feed-link`
- `src/factcheck_scrape/spiders/e_farsas.py:92-101` uses a single container-specific selector: `.mvp-main-blog-text > a`

Examples of broad selectors with weak URL-shape filtering:

- `src/factcheck_scrape/spiders/afp_checamos.py:148-169`
- `src/factcheck_scrape/spiders/aosfatos.py:89-103`
- `src/factcheck_scrape/spiders/observador.py:205-216`

This pattern is important because downstream analysis already compensates for generic or non-article outputs:

- `src/factcheck_scrape/analysis/profiles.py:49-64` drops editorial/generic rows for AFP and Aos Fatos
- `src/factcheck_scrape/analysis/profiles.py:86-92` ignores generic `observador` titles in analysis
- `src/factcheck_scrape/analysis/profiles.py:99-104` extracts a verdict prefix for Projeto Comprova instead of trusting the raw stored label

That suggests selector quality is not fully enforced at collection time and some noise is being deferred to later cleanup.

### 8. Medium: `EstadaoVerificaSpider` and `UolConfereSpider` duplicate core extraction logic, and Estadao skips canonicalization

Both spiders reimplement JSON-LD normalization and primary-object selection instead of reusing the shared helpers in `src/factcheck_scrape/spiders/base.py:49-228`:

- `src/factcheck_scrape/spiders/estadao_verifica.py:74-112`
- `src/factcheck_scrape/spiders/uol_confere.py:266-300`

This raises maintenance risk because fixes to JSON-LD parsing behavior will not automatically propagate.

`EstadaoVerificaSpider` also returns the canonical URL without passing it through canonicalization:

- `src/factcheck_scrape/spiders/estadao_verifica.py:133-138`

That is inconsistent with the shared base behavior in `src/factcheck_scrape/spiders/base.py:190-212` and can hurt dedupe quality if Estadao exposes variant URLs, query strings, or redirect-style canonicals.

### 9. Medium: `AgenciaLupaSpider` likely underuses ClaimReview metadata

`src/factcheck_scrape/spiders/agencia_lupa.py:27-67` selects one JSON-LD object as `article`, even if that object is a `ClaimReview`, and then derives `verdict` only via `infer_verdict(title, summary)`.

Unlike the stronger ClaimReview-based spiders, it does not separately extract:

- `reviewRating`
- explicit `claimReviewed`
- structured verdict/rating values

If Lupa pages expose proper ClaimReview schema, this spider is likely leaving higher-fidelity verdict data on the table and relying on text heuristics instead.

## Test coverage summary

Well covered relative to the rest of the repo:

- AFP Checamos
- Agencia Lupa
- Aos Fatos
- Boatos.org
- E-farsas
- Observador
- Poligrafo
- Projeto Comprova
- Publico
- Reuters
- Scrapling fallback middleware behavior

Weak or missing coverage:

- `EstadaoVerificaSpider`: no fixture-based listing/article tests found
- `G1FatoOuFakeSpider`: no fixture-based listing/article tests found
- `UolConfereSpider`: helper tests only, no article extraction test found
- taxonomy fields and non-required metadata are mostly unasserted across the whole suite

## Recommended next steps

1. Stop emitting fallback production values for missing `title` or `published_at`. Log the failure and drop the item instead.
2. Tighten `AfpChecamosSpider` discovery with positive article URL filters and negative fixtures for editorial pages such as `Como trabalhamos`.
3. Normalize verdict extraction so numeric ratings like `1` and `5` do not become human verdict labels; keep numeric values in `rating` only.
4. Add fixture-backed article tests for Estadao, G1, and UOL, and extend existing article tests to assert `claim`, `summary`, `topics`, `tags`, `entities`, and `source_type`.
5. Remove the `/economia/` hard filter from `PublicoSpider` discovery and rely on article-level fact-check detection.
6. Improve `UolConfereSpider` article extraction so `summary`, `topics`, and `tags` come from article-specific data rather than generic portal metadata.
7. Refactor Estadao and UOL to reuse the shared JSON-LD extraction helpers; canonicalize Estadao canonical URLs before dedupe.
8. Where ClaimReview exists, prefer structured verdict extraction over text inference, and add spider-specific normalization where the site uses compound labels such as `Enganoso: ...`.

from __future__ import annotations

from dataclasses import dataclass

SPIDER_ORDER: tuple[str, ...] = (
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
)


@dataclass(frozen=True, slots=True)
class SpiderProfile:
    """Selection and cleaning rules applied to a spider during analysis."""

    spider: str
    display_name: str
    analysis_field_order: tuple[str, ...] = ("title", "claim", "summary")
    ignored_analysis_titles: frozenset[str] = frozenset()
    dropped_export_titles: frozenset[str] = frozenset()
    extract_label_prefix_before_colon: bool = False
    diagnostic_run_ids: tuple[str, ...] = ()
    cleaning_flags: tuple[str, ...] = ()


DEFAULT_PROFILE = SpiderProfile(
    spider="default",
    display_name="Default",
    cleaning_flags=(
        "html_unescape",
        "unicode_normalize",
        "collapse_whitespace",
        "light_encoding_fix",
    ),
)


SPIDER_PROFILES: dict[str, SpiderProfile] = {
    "afp_checamos": SpiderProfile(
        spider="afp_checamos",
        display_name="AFP Checamos",
        dropped_export_titles=frozenset({"como trabalhamos"}),
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags + ("drop_generic_editorial_titles",),
    ),
    "agencia_lupa": SpiderProfile(
        spider="agencia_lupa",
        display_name="Agencia Lupa",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
    ),
    "aos_fatos": SpiderProfile(
        spider="aos_fatos",
        display_name="Aos Fatos",
        dropped_export_titles=frozenset({"ultimas noticias", "últimas notícias"}),
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags + ("drop_generic_editorial_titles",),
    ),
    "boatos_org": SpiderProfile(
        spider="boatos_org",
        display_name="Boatos.org",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
    ),
    "e_farsas": SpiderProfile(
        spider="e_farsas",
        display_name="E-farsas",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
    ),
    "estadao_verifica": SpiderProfile(
        spider="estadao_verifica",
        display_name="Estadao Verifica",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
    ),
    "g1_fato_ou_fake": SpiderProfile(
        spider="g1_fato_ou_fake",
        display_name="G1 Fato ou Fake",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags + ("direct_fake_fato_mapping",),
    ),
    "observador": SpiderProfile(
        spider="observador",
        display_name="Observador",
        analysis_field_order=("claim", "summary", "title"),
        ignored_analysis_titles=frozenset({"observador"}),
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags
        + ("ignore_generic_title_in_analysis", "claim_summary_priority"),
    ),
    "poligrafo": SpiderProfile(
        spider="poligrafo",
        display_name="Poligrafo",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
    ),
    "projeto_comprova": SpiderProfile(
        spider="projeto_comprova",
        display_name="Projeto Comprova",
        extract_label_prefix_before_colon=True,
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags + ("extract_verdict_prefix",),
    ),
    "publico": SpiderProfile(
        spider="publico",
        display_name="Publico",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags + ("parse_rfc822_dates",),
    ),
    "reuters_fact_check": SpiderProfile(
        spider="reuters_fact_check",
        display_name="Reuters Fact Check",
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
    ),
    "uol_confere": SpiderProfile(
        spider="uol_confere",
        display_name="UOL Confere",
        diagnostic_run_ids=("20260315T010005Z-1d265f16", "20260314T232736Z-2cced5c3"),
        cleaning_flags=DEFAULT_PROFILE.cleaning_flags + ("diagnose_empty_latest_run",),
    ),
}


def get_spider_profile(spider: str) -> SpiderProfile:
    """Return the analysis profile for a spider."""

    return SPIDER_PROFILES.get(
        spider,
        SpiderProfile(
            spider=spider,
            display_name=spider.replace("_", " ").title(),
            cleaning_flags=DEFAULT_PROFILE.cleaning_flags,
        ),
    )

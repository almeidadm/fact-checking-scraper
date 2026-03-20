from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from factcheck_scrape.analysis import (
    RunSelection,
    build_processed_record,
    build_processed_snapshot,
    clean_text,
    compose_analysis_text,
    normalize_published_at,
    normalize_standard_label,
    process_spider_items,
    select_run_for_spider,
)
from factcheck_scrape.analysis.profiles import get_spider_profile
from factcheck_scrape.analysis.runs import SpiderRunRecord


def test_select_run_for_spider_falls_back_to_latest_valid_and_ignores_missing_run_json(
    tmp_path: Path,
):
    data_dir = tmp_path / "data"
    _write_run(
        data_dir,
        "20260314T232736Z-2cced5c3",
        {
            "uol_confere": {
                "items_seen": 906,
                "items_stored": 19,
                "items": [_raw_item(spider="uol_confere", title="Titulo valido")],
            }
        },
    )
    _write_run(
        data_dir,
        "20260315T010005Z-1d265f16",
        {
            "uol_confere": {
                "items_seen": 906,
                "items_stored": 0,
                "items": [],
            }
        },
    )
    orphan_dir = data_dir / "runs" / "20260315T143409Z-b69c230f"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "items.jsonl").write_text(
        json.dumps(_raw_item(spider="uol_confere")),
        encoding="utf-8",
    )

    selection = select_run_for_spider(data_dir, "uol_confere")

    assert selection.latest_run_id == "20260315T010005Z-1d265f16"
    assert selection.selected_run_id == "20260314T232736Z-2cced5c3"
    assert selection.fallback_applied is True
    assert selection.selection_reason == "fallback_to_latest_valid_run"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-03-11T19:44:05.868Z", "2026-03-11T19:44:05.868000+00:00"),
        ("2025-12-04", "2025-12-04T00:00:00+00:00"),
        ("Tue, 16 Feb 2016 19:56:38 GMT", "2016-02-16T19:56:38+00:00"),
        ("-", None),
    ],
)
def test_normalize_published_at_supports_iso_date_only_rfc822_and_placeholders(
    value: str,
    expected: str | None,
):
    assert normalize_published_at(value) == expected


def test_clean_text_normalizes_entities_whitespace_lowercase_and_encoding():
    assert clean_text("Num dos v&#xED;deos") == "Num dos vídeos"
    assert clean_text(" OlÃ¡\n\tMundo ") == "Olá Mundo"
    assert clean_text("  Titulo\nDuplicado  ", lowercase=True) == "titulo duplicado"


def test_should_drop_generic_editorial_rows_via_processed_record():
    selection = _selection_for("afp_checamos")
    dropped = build_processed_record(
        _raw_item(spider="afp_checamos", title="Como trabalhamos", claim="Como trabalhamos"),
        selection,
    )
    assert dropped is None


@pytest.mark.parametrize(
    ("spider", "label", "expected"),
    [
        ("g1_fato_ou_fake", "FAKE", "false"),
        ("g1_fato_ou_fake", "FATO", "true"),
        ("projeto_comprova", "Enganoso: Texto longo de apoio", "misleading"),
        ("poligrafo", "Pimenta na Língua", "satire"),
        ("afp_checamos", "Sem evidências", "unverified"),
        ("observador", "Praticamente certo", "true"),
        ("aos_fatos", "não_é_bem_assim", "misleading"),
        ("afp_checamos", "https://example.com", "other"),
    ],
)
def test_normalize_standard_label_maps_taxonomy(spider: str, label: str, expected: str):
    assert normalize_standard_label(label, spider) == expected


def test_compose_analysis_text_ignores_observador_generic_title():
    profile = get_spider_profile("observador")
    assert (
        compose_analysis_text(
            "observador",
            title="Observador",
            claim="Afirmação principal",
            summary="Resumo validado",
            profile=profile,
        )
        == "afirmação principal resumo validado"
    )


def test_process_spider_items_enriches_nlp_entities_and_metadata():
    selection = _selection_for("agencia_lupa")
    item = _raw_item(
        spider="agencia_lupa",
        title="Lula erra",
        claim="Lula fala sobre o Brasil",
        summary="Checagem sobre o Brasil",
        verdict="Falso",
    )

    records = process_spider_items([item], selection=selection, nlp=StubNLP())

    assert len(records) == 1
    record = records[0]
    assert record["standard_label"] == "false"
    assert record["text_without_stopwords"] == "lula erra lula fala brasil checagem brasil"
    assert record["lemmatized_text"] == "lula erra lula fala sobre o brasil checagem sobre o brasil"
    assert record["entities"] == [
        {"text": "lula", "label": "PERSON", "start_char": 0, "end_char": 4},
        {"text": "brasil", "label": "GPE", "start_char": 28, "end_char": 34},
    ]
    assert record["metadata"]["entity_count"] == 2
    assert record["metadata"]["analysis_text_length"] == len(record["analysis_text"])


def test_build_processed_snapshot_writes_jsonl_and_manifest(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_run(
        data_dir,
        "20260315T010005Z-1d265f16",
        {
            "agencia_lupa": {
                "items_seen": 1,
                "items_stored": 1,
                "items": [
                    _raw_item(
                        spider="agencia_lupa",
                        title="Checagem Lupa",
                        claim="Lula falou",
                        summary="Resumo de checagem",
                        verdict="Falso",
                    )
                ],
            },
            "observador": {
                "items_seen": 1,
                "items_stored": 1,
                "items": [
                    _raw_item(
                        spider="observador",
                        title="Observador",
                        claim="Teoria não procede",
                        summary="Resumo factual",
                        verdict="Errado",
                    )
                ],
            },
        },
    )

    manifest = build_processed_snapshot(
        data_dir=data_dir,
        snapshot_root=data_dir / "processed",
        snapshot_id="20260315T190000Z-processed",
        nlp=StubNLP(),
        spiders=["agencia_lupa", "observador"],
    )

    snapshot_dir = data_dir / "processed" / "20260315T190000Z-processed"
    spider_export = snapshot_dir / "spiders" / "agencia_lupa.jsonl"
    combined_export = snapshot_dir / "factcheck_scrape_unified.jsonl"
    manifest_path = snapshot_dir / "manifest.json"

    assert spider_export.exists()
    assert combined_export.exists()
    assert manifest_path.exists()
    assert manifest["snapshot_id"] == "20260315T190000Z-processed"
    assert manifest["combined_export_count"] == 2
    assert manifest["spiders"]["agencia_lupa"]["selected_run_id"] == "20260315T010005Z-1d265f16"
    assert manifest["spiders"]["agencia_lupa"]["exported_records"] == 1

    lines = combined_export.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["variant"] == "claim_summary"


def _selection_for(spider: str) -> RunSelection:
    run_id = "20260315T010005Z-1d265f16"
    run_record = SpiderRunRecord(
        run_id=run_id,
        spider=spider,
        agency_id=spider,
        agency_name=spider.replace("_", " ").title(),
        run_started_at="2026-03-15T01:00:05+00:00",
        run_finished_at="2026-03-15T01:10:05+00:00",
        spider_started_at="2026-03-15T01:00:05+00:00",
        spider_finished_at="2026-03-15T01:05:05+00:00",
        items_seen=1,
        items_stored=1,
        items_deduped=0,
        items_invalid=0,
        run_path=Path("/tmp/run.json"),
        items_path=Path("/tmp/items.jsonl"),
    )
    return RunSelection(
        spider=spider,
        profile=get_spider_profile(spider),
        latest_run=run_record,
        selected_run=run_record,
        latest_valid_run=run_record,
        fallback_applied=False,
        selection_reason="latest_valid_run",
    )


def _write_run(data_dir: Path, run_id: str, spiders: dict[str, dict[str, object]]) -> None:
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": run_id,
        "started_at": "2026-03-15T01:00:05+00:00",
        "finished_at": "2026-03-15T01:10:05+00:00",
        "spiders": {},
        "totals": {"items_seen": 0, "items_stored": 0, "items_deduped": 0, "items_invalid": 0},
    }
    item_lines: list[str] = []
    for spider, config in spiders.items():
        items = config.get("items", [])
        payload["spiders"][spider] = {
            "agency_id": spider,
            "agency_name": spider.replace("_", " ").title(),
            "started_at": "2026-03-15T01:00:05+00:00",
            "finished_at": "2026-03-15T01:05:05+00:00",
            "items_seen": config.get("items_seen", len(items)),
            "items_stored": config.get("items_stored", len(items)),
            "items_deduped": config.get("items_deduped", 0),
            "items_invalid": config.get("items_invalid", 0),
        }
        payload["totals"]["items_seen"] += int(config.get("items_seen", len(items)))
        payload["totals"]["items_stored"] += int(config.get("items_stored", len(items)))
        payload["totals"]["items_deduped"] += int(config.get("items_deduped", 0))
        payload["totals"]["items_invalid"] += int(config.get("items_invalid", 0))
        item_lines.extend(json.dumps(item, ensure_ascii=False) for item in items)

    (run_dir / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if item_lines:
        (run_dir / "items.jsonl").write_text("\n".join(item_lines) + "\n", encoding="utf-8")


def _raw_item(
    spider: str = "agencia_lupa",
    title: str = "Titulo",
    claim: str = "Claim principal",
    summary: str = "Resumo com Brasil",
    verdict: str | None = "Verdadeiro",
) -> dict[str, object]:
    return {
        "item_id": f"{spider}-item-1",
        "agency_id": spider,
        "agency_name": spider.replace("_", " ").title(),
        "spider": spider,
        "source_url": f"https://example.com/{spider}",
        "canonical_url": f"https://example.com/{spider}",
        "title": title,
        "published_at": "2026-03-11T19:44:05.868Z",
        "collected_at": "2026-03-15T01:00:05+00:00",
        "run_id": "20260315T010005Z-1d265f16",
        "claim": claim,
        "summary": summary,
        "verdict": verdict,
        "rating": verdict,
        "language": "pt-BR",
        "country": "BR",
        "topics": ["Economia"],
        "tags": ["Brasil"],
        "entities": [],
        "source_type": "NewsArticle",
    }


@dataclass
class StubToken:
    text: str
    lemma_: str
    is_stop: bool = False
    is_punct: bool = False
    is_space: bool = False


@dataclass
class StubEntity:
    text: str
    label_: str
    start_char: int
    end_char: int


class StubDoc:
    def __init__(self, tokens: list[StubToken], ents: list[StubEntity]) -> None:
        self._tokens = tokens
        self.ents = ents

    def __iter__(self):
        return iter(self._tokens)


class StubNLP:
    def pipe(self, texts, batch_size: int = 64):
        for text in texts:
            words = text.split()
            tokens = [
                StubToken(
                    text=word,
                    lemma_=word.lower(),
                    is_stop=word.lower() in {"sobre", "o"},
                )
                for word in words
            ]
            ents: list[StubEntity] = []
            lower_text = text.lower()
            if "lula" in lower_text:
                start = lower_text.index("lula")
                ents.append(
                    StubEntity(text="lula", label_="PERSON", start_char=start, end_char=start + 4)
                )
            if "brasil" in lower_text:
                start = lower_text.index("brasil")
                ents.append(
                    StubEntity(text="brasil", label_="GPE", start_char=start, end_char=start + 6)
                )
            yield StubDoc(tokens, ents)

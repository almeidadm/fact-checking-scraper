from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .profiles import SpiderProfile, get_spider_profile
from .runs import (
    RunSelection,
    build_manifest,
    load_items_for_run,
    select_runs_for_spiders,
    write_manifest,
)

PLACEHOLDER_VALUES = {"", "-", "none", "null", "nan", "n/a"}
MOJIBAKE_MARKERS = ("Ã", "Â", "â", "\ufffd")
NUMERIC_LABEL_RE = re.compile(r"^\d+$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

PROCESSED_RECORD_FIELDS = {
    "record_id",
    "source_record_id",
    "dataset_id",
    "source_url",
    "published_at",
    "language",
    "title",
    "author",
    "subtitle",
    "claim_text",
    "body_text",
    "analysis_text",
    "text_for_ner",
    "text_without_stopwords",
    "lemmatized_text",
    "original_label",
    "standard_label",
    "category",
    "entities",
    "variant",
    "metadata",
}

TRUE_LABEL_KEYS = {"verdadeiro", "certo", "fato", "comprovado", "praticamente_certo"}
FALSE_LABEL_KEYS = {"falso", "errado", "fake", "montagem"}
MISLEADING_LABEL_KEYS = {
    "enganoso",
    "enganador",
    "falta_contexto",
    "fora_de_contexto",
    "sem_contexto",
    "descontextualizado",
    "distorcido",
    "nao_e_bem_assim",
    "exagerado",
    "esticado",
    "verdadeiro_mas",
    "impreciso",
    "insustentavel",
    "contraditorio",
}
UNVERIFIED_LABEL_KEYS = {
    "inconclusivo",
    "sem_provas",
    "sem_indicios",
    "sem_evidencias",
    "sem_evidencia",
    "sem_registro",
}
SATIRE_LABEL_KEYS = {"satira", "pimenta_na_lingua"}
OTHER_LABEL_KEYS = {"checamos"}


def clean_text(value: Any, *, lowercase: bool = False) -> str | None:
    """Normalize textual fields while preserving readable UTF-8 content."""

    if value is None:
        return None

    text = str(value)
    text = html.unescape(text)
    text = _maybe_fix_mojibake(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    if text.casefold() in PLACEHOLDER_VALUES:
        return None
    if lowercase:
        text = text.lower()
    return text


def clean_text_list(values: list[Any] | tuple[Any, ...] | None) -> list[str]:
    """Clean and deduplicate ordered textual lists such as topics or tags."""

    if not values:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = clean_text(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        cleaned.append(normalized)
        seen.add(key)
    return cleaned


def normalize_published_at(value: Any) -> str | None:
    """Parse heterogeneous published_at formats into ISO 8601 UTC strings."""

    text = clean_text(value)
    if not text:
        return None

    parsed = _parse_iso_datetime(text) or _parse_date_only(text) or _parse_rfc822_datetime(text)
    if parsed is None:
        return None
    return parsed.astimezone(UTC).isoformat()


def compose_analysis_text(
    spider: str,
    title: str | None,
    claim: str | None,
    summary: str | None,
    profile: SpiderProfile | None = None,
) -> str:
    """Compose a normalized analysis text with simple ordered deduplication."""

    profile = profile or get_spider_profile(spider)
    fields = {"title": title, "claim": claim, "summary": summary}
    parts: list[str] = []
    seen: set[str] = set()

    for field_name in profile.analysis_field_order:
        value = clean_text(fields.get(field_name))
        if not value:
            continue
        if field_name == "title" and value.casefold() in profile.ignored_analysis_titles:
            continue
        key = value.casefold()
        if key in seen:
            continue
        parts.append(value.lower())
        seen.add(key)

    return " ".join(parts)


def normalize_standard_label(
    original_label: str | None,
    spider: str,
    profile: SpiderProfile | None = None,
) -> str:
    """Map heterogeneous verdicts into the compact processed taxonomy."""

    if not clean_text(original_label):
        return "missing"

    profile = profile or get_spider_profile(spider)
    semantic_label = clean_text(original_label) or ""
    if profile.extract_label_prefix_before_colon and ":" in semantic_label:
        semantic_label = clean_text(semantic_label.split(":", 1)[0]) or semantic_label

    label_key = _label_key(semantic_label)
    original_key = _label_key(original_label)

    if URL_RE.match(semantic_label) or NUMERIC_LABEL_RE.match(semantic_label):
        return "other"
    if label_key in TRUE_LABEL_KEYS or original_key in TRUE_LABEL_KEYS:
        return "true"
    if label_key in FALSE_LABEL_KEYS or original_key in FALSE_LABEL_KEYS:
        return "false"
    if label_key in MISLEADING_LABEL_KEYS or original_key in MISLEADING_LABEL_KEYS:
        return "misleading"
    if label_key in UNVERIFIED_LABEL_KEYS or original_key in UNVERIFIED_LABEL_KEYS:
        return "unverified"
    if label_key in SATIRE_LABEL_KEYS or original_key in SATIRE_LABEL_KEYS:
        return "satire"
    if label_key in OTHER_LABEL_KEYS or original_key in OTHER_LABEL_KEYS:
        return "other"
    if semantic_label.casefold().startswith(("enganoso:", "contextualizando:")):
        return "misleading"
    return "other"


def should_drop_item(
    item: dict[str, Any],
    spider: str,
    profile: SpiderProfile | None = None,
) -> bool:
    """Return True when a raw item should not appear in the processed export."""

    profile = profile or get_spider_profile(spider)
    title = clean_text(item.get("title"))
    if title and title.casefold() in profile.dropped_export_titles:
        return True
    return False


def build_processed_record(item: dict[str, Any], selection: RunSelection) -> dict[str, Any] | None:
    """Transform a raw scraped item into the processed snapshot contract."""

    profile = selection.profile
    if should_drop_item(item, selection.spider, profile=profile):
        return None

    title = clean_text(item.get("title"))
    claim_text = clean_text(item.get("claim"))
    body_text = clean_text(item.get("summary"))
    analysis_text = compose_analysis_text(
        selection.spider,
        title=title,
        claim=claim_text,
        summary=body_text,
        profile=profile,
    )
    original_label = clean_text(item.get("verdict") or item.get("rating"))
    source_topics = clean_text_list(item.get("topics"))
    source_tags = clean_text_list(item.get("tags"))
    item_id = str(item.get("item_id"))
    dataset_id = f"factcheck_scrape_{selection.spider}"

    record = {
        "record_id": f"{dataset_id}:{item_id}",
        "source_record_id": item_id,
        "dataset_id": dataset_id,
        "source_url": clean_text(item.get("source_url")),
        "published_at": normalize_published_at(item.get("published_at")),
        "language": clean_text(item.get("language")),
        "title": title,
        "author": clean_text(item.get("author")),
        "subtitle": clean_text(item.get("subtitle")),
        "claim_text": claim_text,
        "body_text": body_text,
        "analysis_text": analysis_text,
        "text_for_ner": analysis_text,
        "text_without_stopwords": "",
        "lemmatized_text": "",
        "original_label": original_label,
        "standard_label": normalize_standard_label(
            original_label,
            selection.spider,
            profile=profile,
        ),
        "category": _pick_category(source_topics, source_tags),
        "entities": [],
        "variant": "claim_summary",
        "metadata": {
            "analysis_text_length": len(analysis_text),
            "entity_count": 0,
            "spider": selection.spider,
            "agency_id": selection.agency_id,
            "agency_name": selection.agency_name,
            "run_id": selection.selected_run_id,
            "latest_run_id": selection.latest_run_id,
            "fallback_applied": selection.fallback_applied,
            "source_type": clean_text(item.get("source_type")),
            "source_topics": source_topics,
            "source_tags": source_tags,
            "source_rating": clean_text(item.get("rating")),
        },
    }
    validate_processed_record(record)
    return record


def process_spider_items(
    items: list[dict[str, Any]],
    selection: RunSelection,
    nlp: Any | None = None,
    batch_size: int = 64,
) -> list[dict[str, Any]]:
    """Clean and enrich a spider dataset, optionally applying NLP features."""

    records = [
        record
        for record in (build_processed_record(item, selection) for item in items)
        if record is not None
    ]

    if nlp is None:
        for record in records:
            record["lemmatized_text"] = record["analysis_text"]
        return records

    docs = nlp.pipe((record["text_for_ner"] for record in records), batch_size=batch_size)
    for record, doc in zip(records, docs):
        record["text_without_stopwords"] = _text_without_stopwords(doc)
        record["lemmatized_text"] = _lemmatized_text(doc)
        record["entities"] = _extract_entities(doc)
        record["metadata"]["entity_count"] = len(record["entities"])
        validate_processed_record(record)
    return records


def export_processed_spider(
    data_dir: str | Path,
    selection: RunSelection,
    snapshot_dir: str | Path,
    nlp: Any | None = None,
    batch_size: int = 64,
) -> tuple[Path, list[dict[str, Any]]]:
    """Process and export one spider dataset into the snapshot layout."""

    snapshot_dir = Path(snapshot_dir)
    spider_dir = snapshot_dir / "spiders"
    spider_dir.mkdir(parents=True, exist_ok=True)

    items = load_items_for_run(data_dir, selection.selected_run_id, spider=selection.spider)
    records = process_spider_items(items, selection=selection, nlp=nlp, batch_size=batch_size)
    output_path = spider_dir / f"{selection.spider}.jsonl"
    _write_jsonl(output_path, records)
    return output_path, records


def build_processed_snapshot(
    data_dir: str | Path,
    snapshot_root: str | Path,
    snapshot_id: str,
    nlp: Any | None = None,
    spiders: list[str] | tuple[str, ...] | None = None,
    batch_size: int = 64,
) -> dict[str, Any]:
    """Export processed JSONL files for each spider plus a unified corpus and manifest."""

    snapshot_dir = Path(snapshot_root) / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    selections = select_runs_for_spiders(data_dir, spiders=spiders)

    combined_path = snapshot_dir / "factcheck_scrape_unified.jsonl"
    combined_records: list[dict[str, Any]] = []
    export_counts: dict[str, int] = {}

    for spider, selection in selections.items():
        _, records = export_processed_spider(
            data_dir,
            selection=selection,
            snapshot_dir=snapshot_dir,
            nlp=nlp,
            batch_size=batch_size,
        )
        export_counts[spider] = len(records)
        combined_records.extend(records)

    _write_jsonl(combined_path, combined_records)
    manifest = build_manifest(
        snapshot_id=snapshot_id,
        selections=selections,
        export_counts=export_counts,
        combined_count=len(combined_records),
        output_dir=snapshot_dir,
    )
    write_manifest(snapshot_dir / "manifest.json", manifest)
    return manifest


def load_spacy_model(model_name: str = "pt_core_news_lg") -> Any:
    """Load the configured spaCy model with a notebook-friendly error message."""

    try:
        import spacy
    except ImportError as exc:  # pragma: no cover - exercised only without optional dependency
        raise RuntimeError(
            'spaCy nao esta instalado. Rode `uv pip install -e ".[analysis]"` '
            "e `uv run python -m spacy download pt_core_news_lg`."
        ) from exc

    try:
        return spacy.load(model_name)
    except OSError as exc:  # pragma: no cover - exercised only without model download
        raise RuntimeError(
            f"Modelo spaCy '{model_name}' nao encontrado. Rode "
            "`uv run python -m spacy download pt_core_news_lg`."
        ) from exc


def validate_processed_record(record: dict[str, Any]) -> None:
    """Validate the processed export contract used by notebooks and snapshot exports."""

    missing_fields = [field for field in PROCESSED_RECORD_FIELDS if field not in record]
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Missing processed fields: {missing}")

    if record.get("variant") != "claim_summary":
        raise ValueError("Processed variant must be 'claim_summary'")

    if not isinstance(record.get("entities"), list):
        raise ValueError("Processed entities must be a list")

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Processed metadata must be an object")

    if metadata.get("analysis_text_length") != len(record.get("analysis_text") or ""):
        raise ValueError("analysis_text_length does not match analysis_text")

    if metadata.get("entity_count") != len(record.get("entities") or []):
        raise ValueError("entity_count does not match entities")


def _maybe_fix_mojibake(text: str) -> str:
    if not any(marker in text for marker in MOJIBAKE_MARKERS):
        return text

    try:
        candidate = text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text

    return candidate if _mojibake_score(candidate) < _mojibake_score(text) else text


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def _parse_iso_datetime(text: str) -> datetime | None:
    candidate = text
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _parse_date_only(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def _parse_rfc822_datetime(text: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _label_key(value: str | None) -> str:
    text = clean_text(value, lowercase=True)
    if not text:
        return ""
    text = text.replace("…", " ")
    text = text.replace("...", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9:]+", "_", text)
    return text.strip("_")


def _pick_category(source_topics: list[str], source_tags: list[str]) -> str | None:
    if source_topics:
        return source_topics[0]
    if source_tags:
        return source_tags[0]
    return None


def _token_text(token: Any) -> str:
    return clean_text(getattr(token, "text", "")) or ""


def _text_without_stopwords(doc: Any) -> str:
    parts = [
        _token_text(token).lower()
        for token in doc
        if not getattr(token, "is_space", False)
        and not getattr(token, "is_punct", False)
        and not getattr(token, "is_stop", False)
        and _token_text(token)
    ]
    return " ".join(parts)


def _lemmatized_text(doc: Any) -> str:
    lemmas: list[str] = []
    for token in doc:
        if getattr(token, "is_space", False) or getattr(token, "is_punct", False):
            continue
        lemma = clean_text(getattr(token, "lemma_", None), lowercase=True)
        if not lemma:
            lemma = _token_text(token).lower()
        if lemma:
            lemmas.append(lemma)
    return " ".join(lemmas)


def _extract_entities(doc: Any) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for entity in getattr(doc, "ents", ()):
        text = clean_text(getattr(entity, "text", None))
        if not text:
            continue
        entities.append(
            {
                "text": text,
                "label": clean_text(getattr(entity, "label_", None)),
                "start_char": int(getattr(entity, "start_char", 0)),
                "end_char": int(getattr(entity, "end_char", 0)),
            }
        )
    return entities


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")

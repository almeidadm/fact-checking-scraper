from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from factcheck_scrape.analysis import (
    PROCESSED_RECORD_FIELDS as _PROCESSED_RECORD_FIELDS,
)
from factcheck_scrape.analysis import (
    SPIDER_ORDER as _SPIDER_ORDER,
)
from factcheck_scrape.analysis import (
    RunSelection,
    build_manifest,
    default_snapshot_id,
    get_spider_profile,
    iter_spider_runs,
    load_items_for_run,
    load_spacy_model,
    process_spider_items,
    select_run_for_spider,
    select_runs_for_spiders,
    write_manifest,
)

DEFAULT_DATA_DIR = Path("data")
PROCESSED_RECORD_FIELDS = _PROCESSED_RECORD_FIELDS
SPIDER_ORDER = _SPIDER_ORDER


def resolve_data_dir(data_dir: str | None = None) -> Path:
    """Resolve data directory from arg, env, or default."""
    if data_dir:
        return Path(data_dir)
    env = os.getenv("FACTCHECK_DATA_DIR")
    if env:
        return Path(env)
    return DEFAULT_DATA_DIR


def iter_items_paths(data_dir: Path, run_ids: Sequence[str] | None = None) -> list[Path]:
    """Return paths to items.jsonl files, optionally filtered by run_ids."""
    runs_dir = data_dir / "runs"
    if not runs_dir.exists():
        return []
    if run_ids:
        paths = []
        for run_id in run_ids:
            path = runs_dir / run_id / "items.jsonl"
            if path.exists():
                paths.append(path)
        return paths
    return sorted(runs_dir.glob("*/items.jsonl"))


def load_runs_df(data_dir: Path) -> pd.DataFrame:
    """Load run.json files into a dataframe with one row per spider per run."""
    rows = [record.to_dict() for record in iter_spider_runs(data_dir)]
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for col in ("run_started_at", "run_finished_at", "spider_started_at", "spider_finished_at"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    df["run_duration_s"] = (df["run_finished_at"] - df["run_started_at"]).dt.total_seconds()
    df["spider_duration_s"] = (
        df["spider_finished_at"] - df["spider_started_at"]
    ).dt.total_seconds()

    df["items_per_min"] = df["items_stored"] / (df["spider_duration_s"] / 60.0)
    df.loc[df["spider_duration_s"] <= 0, "items_per_min"] = np.nan
    return df


def load_items_df(
    data_dir: Path,
    columns: Iterable[str] | None = None,
    run_ids: Sequence[str] | None = None,
    chunksize: int | None = 100_000,
) -> pd.DataFrame:
    """Load items.jsonl files into a dataframe, with optional chunking and derived fields."""
    paths = iter_items_paths(data_dir, run_ids=run_ids)
    if not paths:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for path in paths:
        if chunksize:
            chunks = pd.read_json(path, lines=True, chunksize=chunksize)
        else:
            chunks = [pd.read_json(path, lines=True)]

        for chunk in chunks:
            if columns:
                keep = [col for col in columns if col in chunk.columns]
                chunk = chunk[keep]
            chunk = _add_derived_columns(chunk)
            frames.append(chunk)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def field_coverage(
    df: pd.DataFrame, fields: Iterable[str], groupby: str | Iterable[str] | None = None
) -> pd.DataFrame:
    """Percent of non-null values per field, optionally grouped."""
    fields = [field for field in fields if field in df.columns]
    if not fields:
        return pd.DataFrame()

    if groupby is None:
        coverage = df[fields].notna().mean().mul(100).reset_index()
        coverage.columns = ["field", "coverage_pct"]
        return coverage

    group_cols = [groupby] if isinstance(groupby, str) else list(groupby)
    grouped = df.groupby(group_cols, dropna=False)[fields]
    coverage = grouped.apply(lambda group: group.notna().mean().mul(100))
    return coverage.reset_index()


def duplicate_stats(
    df: pd.DataFrame, keys: Iterable[str], groupby: str | Iterable[str] | None = None
) -> pd.DataFrame:
    """Compute duplicate counts and rates for given keys, optionally grouped."""
    keys = [key for key in keys if key in df.columns]
    if not keys:
        return pd.DataFrame()

    if groupby is None:
        total = len(df)
        dup_mask = df.duplicated(subset=keys, keep=False)
        dup_count = int(dup_mask.sum())
        return pd.DataFrame(
            [
                {
                    "total": total,
                    "duplicate_count": dup_count,
                    "duplicate_rate_pct": (dup_count / total * 100) if total else 0.0,
                }
            ]
        )

    group_cols = [groupby] if isinstance(groupby, str) else list(groupby)
    rows: list[dict] = []
    for name, group in df.groupby(group_cols, dropna=False):
        if not isinstance(name, tuple):
            name = (name,)
        total = len(group)
        dup_mask = group.duplicated(subset=keys, keep=False)
        dup_count = int(dup_mask.sum())
        row = {col: val for col, val in zip(group_cols, name)}
        row["total"] = total
        row["duplicate_count"] = dup_count
        row["duplicate_rate_pct"] = (dup_count / total * 100) if total else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def top_n(df: pd.DataFrame, col: str, n: int = 15) -> pd.DataFrame:
    """Return top-n value counts with optional 'Outros' bucket."""
    if col not in df.columns:
        return pd.DataFrame(columns=[col, "count"])

    series = df[col]
    if series.apply(lambda value: isinstance(value, list)).any():
        series = series.explode()

    counts = series.dropna().value_counts()
    if counts.empty:
        return pd.DataFrame(columns=[col, "count"])

    if len(counts) > n:
        top = counts.head(n)
        others = counts.iloc[n:].sum()
        counts = pd.concat([top, pd.Series({"Outros": others})])

    return counts.reset_index().rename(columns={"index": col})


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "published_at" in df.columns:
        df["published_at_dt"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    if "collected_at" in df.columns:
        df["collected_at_dt"] = pd.to_datetime(df["collected_at"], utc=True, errors="coerce")

    if "published_at_dt" in df.columns and "collected_at_dt" in df.columns:
        df["lag_hours"] = (df["collected_at_dt"] - df["published_at_dt"]).dt.total_seconds() / 3600

    for field, target in (
        ("title", "title_len"),
        ("claim", "claim_len"),
        ("summary", "summary_len"),
    ):
        if field in df.columns:
            df[target] = df[field].astype("string").str.len()

    if "canonical_url" in df.columns:
        df["canonical_host"] = df["canonical_url"].apply(_extract_host)

    if "source_url" in df.columns and "canonical_url" in df.columns:
        source = df["source_url"].fillna("")
        canonical = df["canonical_url"].fillna("")
        mask = source.ne("") & canonical.ne("")
        df["source_equals_canonical"] = np.where(mask, source == canonical, np.nan)

    return df


def _extract_host(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        return urlparse(url).netloc.lower() or None
    except Exception:
        return None


def select_spider_run(data_dir: Path, spider: str) -> RunSelection:
    """Select the notebook run for a spider using the shared analysis policy."""

    return select_run_for_spider(data_dir, spider)


def load_spider_items_df(data_dir: Path, spider: str, run_id: str | None = None) -> pd.DataFrame:
    """Load raw spider items as a dataframe with derived helper columns."""

    if run_id:
        rows = load_items_for_run(data_dir, run_id=run_id, spider=spider)
        df = pd.DataFrame(rows)
        return _add_derived_columns(df) if not df.empty else df

    return load_items_df(data_dir, run_ids=None).query("spider == @spider").reset_index(drop=True)


def selection_to_frame(selection: RunSelection) -> pd.DataFrame:
    """Convert run selection metadata into a one-row dataframe for display."""

    return pd.DataFrame(
        [
            {
                "spider": selection.spider,
                "agency_id": selection.agency_id,
                "agency_name": selection.agency_name,
                "selected_run_id": selection.selected_run_id,
                "latest_run_id": selection.latest_run_id,
                "latest_valid_run_id": selection.latest_valid_run_id,
                "fallback_applied": selection.fallback_applied,
                "selection_reason": selection.selection_reason,
                "cleaning_flags": ", ".join(selection.cleaning_flags),
                "diagnostic_run_ids": ", ".join(selection.diagnostic_run_ids),
            }
        ]
    )


def diagnostic_runs_df(data_dir: Path, spider: str) -> pd.DataFrame:
    """Return the diagnostic runs configured for a spider profile."""

    profile = get_spider_profile(spider)
    rows: list[dict] = []
    runs_df = load_runs_df(data_dir)
    for run_id in profile.diagnostic_run_ids:
        matches = runs_df[(runs_df["spider"] == spider) & (runs_df["run_id"] == run_id)]
        if not matches.empty:
            rows.extend(matches.to_dict(orient="records"))
    return pd.DataFrame(rows)


def build_processed_records(
    data_dir: Path,
    spider: str,
    selection: RunSelection | None = None,
    nlp: object | None = None,
    batch_size: int = 64,
) -> tuple[RunSelection, list[dict]]:
    """Process the selected raw spider items into the JSONL contract."""

    selection = selection or select_spider_run(data_dir, spider)
    items = load_items_for_run(data_dir, selection.selected_run_id, spider=spider)
    records = process_spider_items(items, selection=selection, nlp=nlp, batch_size=batch_size)
    return selection, records


def processed_records_to_df(records: Sequence[dict]) -> pd.DataFrame:
    """Flatten processed records into a dataframe with metadata columns expanded."""

    if not records:
        return pd.DataFrame()
    return pd.json_normalize(records, sep=".")


def export_processed_records(
    data_dir: Path,
    spider: str,
    records: Sequence[dict],
    selection: RunSelection,
    snapshot_id: str | None = None,
    processed_root: Path | None = None,
) -> dict:
    """Persist already-processed records using the shared snapshot layout."""

    snapshot_id = snapshot_id or default_snapshot_id(prefix=spider)
    processed_root = processed_root or (data_dir / "processed")
    snapshot_dir = processed_root / snapshot_id
    spider_dir = snapshot_dir / "spiders"
    spider_dir.mkdir(parents=True, exist_ok=True)

    spider_path = spider_dir / f"{spider}.jsonl"
    with spider_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    manifest = build_manifest(
        snapshot_id=snapshot_id,
        selections={spider: selection},
        export_counts={spider: len(records)},
        combined_count=len(records),
        output_dir=snapshot_dir,
    )
    combined_path = snapshot_dir / "factcheck_scrape_unified.jsonl"
    with combined_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    write_manifest(snapshot_dir / "manifest.json", manifest)
    return {
        "snapshot_id": snapshot_id,
        "spider_path": spider_path,
        "combined_path": combined_path,
        "manifest_path": snapshot_dir / "manifest.json",
        "record_count": len(records),
    }


def build_snapshot_exports(
    data_dir: Path,
    snapshot_id: str | None = None,
    spiders: Sequence[str] | None = None,
    nlp: object | None = None,
    batch_size: int = 64,
) -> dict:
    """Process and export the full processed snapshot for the selected spiders."""

    from factcheck_scrape.analysis import build_processed_snapshot

    snapshot_id = snapshot_id or default_snapshot_id()
    return build_processed_snapshot(
        data_dir=data_dir,
        snapshot_root=data_dir / "processed",
        snapshot_id=snapshot_id,
        nlp=nlp,
        spiders=list(spiders) if spiders else None,
        batch_size=batch_size,
    )


def load_nlp_model(model_name: str = "pt_core_news_lg") -> object:
    """Load the configured spaCy model used by the EDA notebooks."""

    return load_spacy_model(model_name)


def select_snapshot_runs(
    data_dir: Path,
    spiders: Sequence[str] | None = None,
) -> dict[str, RunSelection]:
    """Select runs for a full processed snapshot, preserving spider order."""

    return select_runs_for_spiders(data_dir, spiders=list(spiders) if spiders else None)

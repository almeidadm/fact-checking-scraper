import json

from factcheck_scrape.dedupe import DedupeStore
from factcheck_scrape.utils import canonicalize_url


def test_dedupe_store(tmp_path):
    store = DedupeStore(tmp_path, "reuters")
    url = "https://example.com/a?utm_source=x"
    canonical = canonicalize_url(url)

    assert store.is_seen(canonical) is False
    store.mark_seen(canonical, url)
    assert store.is_seen(canonical) is True

    store.close()
    store2 = DedupeStore(tmp_path, "reuters")
    assert store2.is_seen(canonical) is True
    store2.close()


def test_dedupe_store_can_ignore_existing_seen_state(tmp_path):
    url = "https://example.com/a?utm_source=x"
    canonical = canonicalize_url(url)

    original = DedupeStore(tmp_path, "reuters")
    original.mark_seen(canonical, url)
    original.close()

    refreshed = DedupeStore(tmp_path, "reuters", ignore_existing_seen_state=True)
    assert refreshed.is_seen(canonical) is False

    refreshed.mark_seen(canonical, url)
    assert refreshed.is_seen(canonical) is True
    refreshed.close()


def test_dedupe_store_uses_sqlite(tmp_path):
    store = DedupeStore(tmp_path, "reuters")
    store.mark_seen("https://example.com/a", "https://example.com/a")
    store.close()

    db_path = tmp_path / "state" / "seen_reuters.db"
    assert db_path.exists()


def test_dedupe_store_migrates_legacy_jsonl(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    legacy_path = state_dir / "seen_test.jsonl"

    from factcheck_scrape.utils import make_item_id

    item_id = make_item_id("test", "https://example.com/migrated")
    legacy_path.write_text(
        json.dumps({
            "item_id": item_id,
            "canonical_url": "https://example.com/migrated",
            "source_url": "https://example.com/migrated?ref=x",
            "seen_at": "2026-01-01T00:00:00+00:00",
        })
        + "\n",
        encoding="utf-8",
    )

    store = DedupeStore(tmp_path, "test")
    assert store.is_seen("https://example.com/migrated") is True
    assert not legacy_path.exists()
    assert legacy_path.with_suffix(".jsonl.bak").exists()
    store.close()


def test_dedupe_store_mark_seen_idempotent(tmp_path):
    store = DedupeStore(tmp_path, "reuters")
    url = "https://example.com/idem"

    id1 = store.mark_seen(url, url)
    id2 = store.mark_seen(url, url)
    assert id1 == id2
    store.close()

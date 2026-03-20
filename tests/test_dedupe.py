from factcheck_scrape.dedupe import DedupeStore
from factcheck_scrape.utils import canonicalize_url


def test_dedupe_store(tmp_path):
    store = DedupeStore(tmp_path, "reuters")
    url = "https://example.com/a?utm_source=x"
    canonical = canonicalize_url(url)

    assert store.is_seen(canonical) is False
    store.mark_seen(canonical, url)
    assert store.is_seen(canonical) is True

    store2 = DedupeStore(tmp_path, "reuters")
    assert store2.is_seen(canonical) is True


def test_dedupe_store_can_ignore_existing_seen_state(tmp_path):
    url = "https://example.com/a?utm_source=x"
    canonical = canonicalize_url(url)

    original = DedupeStore(tmp_path, "reuters")
    original.mark_seen(canonical, url)

    refreshed = DedupeStore(tmp_path, "reuters", ignore_existing_seen_state=True)
    assert refreshed.is_seen(canonical) is False

    refreshed.mark_seen(canonical, url)
    assert refreshed.is_seen(canonical) is True

    state_path = tmp_path / "state" / "seen_reuters.jsonl"
    assert state_path.read_text(encoding="utf-8").count("\n") == 1

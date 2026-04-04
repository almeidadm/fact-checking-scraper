import json

from factcheck_scrape.storage import RunCounts, RunWriter


def test_run_writer(tmp_path):
    writer = RunWriter(tmp_path, "run-1")
    writer.write_item({"foo": "bar"})
    writer.close()

    counts = RunCounts(items_seen=1, items_stored=1, items_deduped=0, items_invalid=0)
    writer.update_run(
        spider_name="reuters_fact_check",
        agency_id="reuters",
        agency_name="Reuters",
        counts=counts,
        spider_started_at="2024-01-01T00:00:00+00:00",
        spider_finished_at="2024-01-01T00:10:00+00:00",
    )

    items_path = tmp_path / "runs" / "run-1" / "items.jsonl"
    run_path = tmp_path / "runs" / "run-1" / "run.json"

    assert items_path.exists()
    assert run_path.exists()
    assert items_path.read_text(encoding="utf-8").count("\n") == 1

    payload = json.loads(run_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-1"
    assert payload["totals"]["items_stored"] == 1

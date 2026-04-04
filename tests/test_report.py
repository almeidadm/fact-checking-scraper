import json

from factcheck_scrape.report import (
    format_report_text,
    generate_report,
    load_run_report,
)


def _write_run_json(tmp_path, run_id, spiders_data):
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    totals = {
        "items_seen": sum(s.get("items_seen", 0) for s in spiders_data.values()),
        "items_stored": sum(s.get("items_stored", 0) for s in spiders_data.values()),
        "items_deduped": sum(s.get("items_deduped", 0) for s in spiders_data.values()),
        "items_invalid": sum(s.get("items_invalid", 0) for s in spiders_data.values()),
    }
    payload = {
        "run_id": run_id,
        "started_at": "2026-03-18T04:00:00+00:00",
        "finished_at": "2026-03-18T06:00:00+00:00",
        "spiders": spiders_data,
        "totals": totals,
    }
    (run_dir / "run.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_run_report(tmp_path):
    _write_run_json(tmp_path, "run-1", {
        "afp_checamos": {
            "agency_id": "afp_checamos",
            "agency_name": "AFP Checamos",
            "started_at": "2026-03-18T04:00:00+00:00",
            "finished_at": "2026-03-18T04:10:00+00:00",
            "items_seen": 100,
            "items_stored": 95,
            "items_deduped": 3,
            "items_invalid": 2,
        },
    })

    report = load_run_report(tmp_path / "runs" / "run-1" / "run.json")

    assert report is not None
    assert report.run_id == "run-1"
    assert len(report.spiders) == 1
    assert report.spiders[0].spider == "afp_checamos"
    assert report.spiders[0].items_stored == 95
    assert report.spiders[0].store_rate == 0.95
    assert report.alerts == []


def test_load_run_report_alerts_on_zero_items(tmp_path):
    _write_run_json(tmp_path, "run-2", {
        "agencia_lupa": {
            "agency_id": "agencia_lupa",
            "agency_name": "Agencia Lupa",
            "started_at": "2026-03-18T04:00:00+00:00",
            "finished_at": "2026-03-18T04:05:00+00:00",
            "items_seen": 0,
            "items_stored": 0,
            "items_deduped": 0,
            "items_invalid": 0,
        },
    })

    report = load_run_report(tmp_path / "runs" / "run-2" / "run.json")

    assert len(report.alerts) == 1
    assert "agencia_lupa: 0 items stored" in report.alerts[0]


def test_generate_report_returns_latest(tmp_path):
    _write_run_json(tmp_path, "20260317-aaa", {
        "spider_a": {
            "agency_id": "a", "agency_name": "A",
            "items_seen": 10, "items_stored": 10, "items_deduped": 0, "items_invalid": 0,
        },
    })
    _write_run_json(tmp_path, "20260318-bbb", {
        "spider_b": {
            "agency_id": "b", "agency_name": "B",
            "items_seen": 20, "items_stored": 20, "items_deduped": 0, "items_invalid": 0,
        },
    })

    reports = generate_report(tmp_path, count=1)
    assert len(reports) == 1
    assert reports[0].run_id == "20260318-bbb"


def test_generate_report_multiple_runs(tmp_path):
    _write_run_json(tmp_path, "20260317-aaa", {"s": {
        "agency_id": "a", "agency_name": "A",
        "items_seen": 10, "items_stored": 10, "items_deduped": 0, "items_invalid": 0,
    }})
    _write_run_json(tmp_path, "20260318-bbb", {"s": {
        "agency_id": "b", "agency_name": "B",
        "items_seen": 20, "items_stored": 20, "items_deduped": 0, "items_invalid": 0,
    }})

    reports = generate_report(tmp_path, count=2)
    assert len(reports) == 2


def test_format_report_text_no_runs():
    assert format_report_text([]) == "No runs found."


def test_format_report_text_includes_alert(tmp_path):
    _write_run_json(tmp_path, "run-alert", {
        "broken_spider": {
            "agency_id": "broken", "agency_name": "Broken",
            "started_at": "", "finished_at": "",
            "items_seen": 5, "items_stored": 0, "items_deduped": 0, "items_invalid": 5,
        },
    })
    reports = generate_report(tmp_path, count=1)
    text = format_report_text(reports)

    assert "broken_spider" in text
    assert "Alerts:" in text
    assert "0 items stored" in text


def test_load_run_report_missing_file(tmp_path):
    assert load_run_report(tmp_path / "nonexistent" / "run.json") is None

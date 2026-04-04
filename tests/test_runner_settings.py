from pathlib import Path

from factcheck_scrape.runner import build_settings


def test_build_settings_has_rate_limiting():
    settings = build_settings(Path("data"), "test-run")

    assert settings.get("DOWNLOAD_DELAY") == 1.0
    assert settings.get("RANDOMIZE_DOWNLOAD_DELAY") is True
    assert settings.get("CONCURRENT_REQUESTS_PER_DOMAIN") == 2
    assert settings.get("AUTOTHROTTLE_ENABLED") is True
    assert settings.get("AUTOTHROTTLE_START_DELAY") == 1.0
    assert settings.get("AUTOTHROTTLE_MAX_DELAY") == 10.0
    assert settings.get("AUTOTHROTTLE_TARGET_CONCURRENCY") == 1.5


def test_build_settings_has_retry():
    settings = build_settings(Path("data"), "test-run")

    assert settings.get("RETRY_TIMES") == 3
    assert settings.get("RETRY_HTTP_CODES") == [500, 502, 503, 504]


def test_build_settings_robotstxt_obey_false():
    settings = build_settings(Path("data"), "test-run")

    assert settings.get("ROBOTSTXT_OBEY") is False

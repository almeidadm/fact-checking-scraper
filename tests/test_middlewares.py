from __future__ import annotations

import asyncio
from dataclasses import dataclass

from scrapy import Request
from scrapy.downloadermiddlewares.httpcompression import HttpCompressionMiddleware
from scrapy.http import HtmlResponse, TextResponse
from scrapy.utils.defer import maybe_deferred_to_future

from factcheck_scrape.middlewares import (
    ScraplingFallbackMiddleware,
    ScraplingFetchResult,
)


class DummySpider:
    name = "observador"


@dataclass
class FakeAdapter:
    result: ScraplingFetchResult | None = None
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.calls: list[dict] = []
        self.closed = False

    async def fetch(
        self,
        request: Request,
        *,
        timeout_ms: int,
        wait_ms: int,
        wait_selector: str | None,
        extra_headers: dict[str, str] | None,
    ) -> ScraplingFetchResult:
        self.calls.append(
            {
                "request": request,
                "timeout_ms": timeout_ms,
                "wait_ms": wait_ms,
                "wait_selector": wait_selector,
                "extra_headers": extra_headers,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    async def close(self) -> None:
        self.closed = True


def _build_middleware(
    adapter: FakeAdapter,
    *,
    block_statuses: list[int] | None = None,
) -> ScraplingFallbackMiddleware:
    return ScraplingFallbackMiddleware(
        headless=True,
        solve_cloudflare=True,
        timeout_ms=60000,
        wait_ms=1000,
        block_statuses=block_statuses or [403, 429, 503],
        real_chrome=True,
        block_webrtc=True,
        hide_canvas=True,
        allow_webgl=True,
        adapter_factory=lambda **_: adapter,
    )


def _resolve(value):
    if asyncio.iscoroutine(value):
        return asyncio.run(value)
    if hasattr(value, "addCallback"):
        return asyncio.run(maybe_deferred_to_future(value))
    return value


def _html_response(
    url: str,
    body: str,
    *,
    status: int = 200,
    meta: dict | None = None,
    headers: dict[str, str] | None = None,
) -> HtmlResponse:
    request = Request(url=url, meta=meta or {})
    return HtmlResponse(
        url=url,
        request=request,
        body=body.encode("utf-8"),
        status=status,
        headers=headers,
        encoding="utf-8",
    )


def _text_response(
    url: str,
    body: str,
    *,
    status: int = 200,
    meta: dict | None = None,
    headers: dict[str, str] | None = None,
) -> TextResponse:
    request = Request(url=url, meta=meta or {})
    return TextResponse(
        url=url,
        request=request,
        body=body.encode("utf-8"),
        status=status,
        headers=headers,
        encoding="utf-8",
    )


def test_middleware_is_noop_without_scrapling_meta():
    adapter = FakeAdapter()
    middleware = _build_middleware(adapter)
    response = _html_response("https://observador.pt/factchecks/", "<html><body>ok</body></html>")

    processed = middleware.process_response(response.request, response)

    assert processed is response
    assert adapter.calls == []


def test_middleware_falls_back_on_cloudflare_marker_html():
    adapter = FakeAdapter(
        result=ScraplingFetchResult(
            url="https://observador.pt/factchecks/",
            status=200,
            body=b"<html><div class='editorial-grid'>ok</div></html>",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    )
    middleware = _build_middleware(adapter)
    response = _html_response(
        "https://observador.pt/factchecks/",
        "<html><title>Just a moment</title></html>",
        meta={"scrapling": {"enabled": True, "wait_selector": ".editorial-grid"}},
    )

    processed = _resolve(middleware.process_response(response.request, response))

    assert isinstance(processed, HtmlResponse)
    assert "editorial-grid" in processed.text
    assert response.request.meta["scrapling_attempted"] is True
    assert adapter.calls[0]["wait_selector"] == ".editorial-grid"


def test_middleware_normalizes_html_headers_before_httpcompression():
    adapter = FakeAdapter(
        result=ScraplingFetchResult(
            url="https://www.reuters.com/fact-check/portugues/exemplo-reuters/",
            status=200,
            body=b"<!doctype html><html><body>resolved</body></html>",
            headers={
                "Content-Encoding": "gzip",
                "Content-Length": "999",
                "Content-Type": "text/html",
            },
        )
    )
    middleware = _build_middleware(adapter, block_statuses=[401, 403, 429, 503])
    response = _html_response(
        "https://www.reuters.com/fact-check/portugues/exemplo-reuters/",
        "<html><body>blocked</body></html>",
        status=401,
        meta={"scrapling": {"enabled": True}},
    )

    processed = _resolve(middleware.process_response(response.request, response))
    httpcompression = HttpCompressionMiddleware(None)
    decompressed = httpcompression.process_response(processed.request, processed)

    assert isinstance(decompressed, HtmlResponse)
    assert decompressed.text == "<!doctype html><html><body>resolved</body></html>"
    assert decompressed.headers.get("Content-Encoding") is None
    assert decompressed.headers.get("Content-Length") is None


def test_middleware_normalizes_html_response_to_utf8():
    adapter = FakeAdapter(
        result=ScraplingFetchResult(
            url="https://observador.pt/factchecks/exemplo/",
            status=200,
            body="<html><body>ação</body></html>".encode("utf-8"),
            headers={
                "Content-Type": "text/html; charset=iso-8859-1",
                "Transfer-Encoding": "chunked",
            },
        )
    )
    middleware = _build_middleware(adapter)
    response = _html_response(
        "https://observador.pt/factchecks/exemplo/",
        "<html><title>Just a moment</title></html>",
        meta={"scrapling": {"enabled": True}},
    )

    processed = _resolve(middleware.process_response(response.request, response))

    assert isinstance(processed, HtmlResponse)
    assert processed.encoding == "utf-8"
    assert processed.text == "<html><body>ação</body></html>"
    assert processed.headers.get("Content-Type").decode() == "text/html; charset=utf-8"
    assert processed.headers.get("Transfer-Encoding") is None


def test_middleware_falls_back_on_block_status_codes():
    for status in (403, 503):
        adapter = FakeAdapter(
            result=ScraplingFetchResult(
                url="https://observador.pt/factchecks/",
                status=200,
                body=b"<html><body>resolved</body></html>",
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        )
        middleware = _build_middleware(adapter)
        response = _html_response(
            "https://observador.pt/factchecks/",
            "<html><body>blocked</body></html>",
            status=status,
            meta={"scrapling": {"enabled": True}},
        )

        processed = _resolve(middleware.process_response(response.request, response))

        assert isinstance(processed, HtmlResponse)
        assert "resolved" in processed.text
        assert adapter.calls[0]["timeout_ms"] == 60000


def test_middleware_falls_back_on_configured_401_status():
    adapter = FakeAdapter(
        result=ScraplingFetchResult(
            url="https://www.reuters.com/fact-check/portugues/exemplo-reuters/",
            status=200,
            body=b"<html><h1>resolved</h1></html>",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    )
    middleware = _build_middleware(adapter, block_statuses=[401, 403, 429, 503])
    response = _html_response(
        "https://www.reuters.com/fact-check/portugues/exemplo-reuters/",
        "<html><body>blocked</body></html>",
        status=401,
        meta={"scrapling": {"enabled": True}},
    )

    processed = _resolve(middleware.process_response(response.request, response))

    assert isinstance(processed, HtmlResponse)
    assert "resolved" in processed.text
    assert adapter.calls[0]["request"].url == response.url


def test_middleware_uses_single_attempt_guard():
    adapter = FakeAdapter()
    middleware = _build_middleware(adapter)
    response = _html_response(
        "https://observador.pt/factchecks/",
        "<html><title>Just a moment</title></html>",
        meta={"scrapling": {"enabled": True}, "scrapling_attempted": True},
    )

    processed = middleware.process_response(response.request, response)

    assert processed is response
    assert adapter.calls == []


def test_middleware_degrades_gracefully_when_fetch_fails():
    adapter = FakeAdapter(error=RuntimeError("browser failed"))
    middleware = _build_middleware(adapter)
    response = _html_response(
        "https://observador.pt/factchecks/",
        "<html><title>Just a moment</title></html>",
        meta={"scrapling": {"enabled": True}},
    )

    processed = _resolve(middleware.process_response(response.request, response))

    assert processed is response
    assert response.request.meta["scrapling_attempted"] is True
    assert adapter.calls[0]["wait_ms"] == 1000


def test_middleware_converts_json_result_to_text_response():
    adapter = FakeAdapter(
        result=ScraplingFetchResult(
            url="https://observador.pt/wp-json/obs_api/v4/grids/filter/archive/obs_factcheck",
            status=200,
            body=b'{"rendered": {"modules": "<div></div>"}}',
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    )
    middleware = _build_middleware(adapter)
    response = _text_response(
        "https://observador.pt/wp-json/obs_api/v4/grids/filter/archive/obs_factcheck",
        "Attention Required",
        meta={"scrapling": {"enabled": True}},
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    processed = _resolve(middleware.process_response(response.request, response))

    assert type(processed) is TextResponse
    assert processed.status == 200
    assert processed.url == response.url
    assert processed.text == '{"rendered": {"modules": "<div></div>"}}'
    assert processed.headers.get("Content-Type").decode() == "application/json; charset=utf-8"

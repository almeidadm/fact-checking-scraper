from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from scrapy import signals
from scrapy.http import HtmlResponse, Request, Response, TextResponse
from scrapy.http.headers import Headers
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import is_reactor_installed

from .logging import get_logger

CLOUDFLARE_BLOCK_MARKERS = (
    b"just a moment",
    b"attention required",
    b"cf-browser-verification",
    b"/cdn-cgi/challenge-platform",
)
SCRAPLING_STRIPPED_RESPONSE_HEADERS = (
    "Content-Encoding",
    "Transfer-Encoding",
    "Content-Length",
    "Content-MD5",
)
SCRAPLING_HTML_CONTENT_TYPE = "text/html; charset=utf-8"


@dataclass(slots=True)
class ScraplingFetchResult:
    """Normalized result returned by the Scrapling adapter."""

    url: str
    status: int
    body: bytes
    headers: dict[str, str]


class ScraplingSessionAdapter:
    """Wrap Scrapling's stealth browser session behind a small stable API."""

    def __init__(
        self,
        *,
        headless: bool,
        solve_cloudflare: bool,
        real_chrome: bool,
        block_webrtc: bool,
        hide_canvas: bool,
        allow_webgl: bool,
    ) -> None:
        self.headless = headless
        self.solve_cloudflare = solve_cloudflare
        self.real_chrome = real_chrome
        self.block_webrtc = block_webrtc
        self.hide_canvas = hide_canvas
        self.allow_webgl = allow_webgl
        self._session: Any | None = None

    async def fetch(
        self,
        request: Request,
        *,
        timeout_ms: int,
        wait_ms: int,
        wait_selector: str | None,
        extra_headers: dict[str, str] | None,
    ) -> ScraplingFetchResult:
        session = await self._get_session()
        headers = self._merge_headers(request, extra_headers)
        page = await session.fetch(
            request.url,
            timeout=timeout_ms,
            wait=wait_ms,
            wait_selector=wait_selector,
            extra_headers=headers or None,
        )
        return ScraplingFetchResult(
            url=self._extract_url(page, request.url),
            status=self._extract_status(page),
            body=self._extract_body(page),
            headers=self._extract_headers(page),
        )

    async def close(self) -> None:
        session = self._session
        self._session = None
        if session is None:
            return

        close = getattr(session, "close", None)
        if callable(close):
            maybe_coro = close()
            if maybe_coro is not None:
                await maybe_coro
            return

        exit_method = getattr(session, "__aexit__", None)
        if callable(exit_method):
            await exit_method(None, None, None)

    async def _get_session(self) -> Any:
        if self._session is not None:
            return self._session

        from scrapling.fetchers import AsyncStealthySession

        session = AsyncStealthySession(
            headless=self.headless,
            solve_cloudflare=self.solve_cloudflare,
            real_chrome=self.real_chrome,
            block_webrtc=self.block_webrtc,
            hide_canvas=self.hide_canvas,
            allow_webgl=self.allow_webgl,
        )
        enter = getattr(session, "__aenter__", None)
        if callable(enter):
            session = await enter()
        self._session = session
        return session

    def _merge_headers(
        self, request: Request, extra_headers: dict[str, str] | None
    ) -> dict[str, str]:
        headers = self._normalize_mapping(request.headers.to_unicode_dict())
        if extra_headers:
            headers.update(self._normalize_mapping(extra_headers))
        return headers

    def _extract_url(self, page: Any, fallback_url: str) -> str:
        value = getattr(page, "url", None)
        if isinstance(value, str) and value:
            return value
        return fallback_url

    def _extract_status(self, page: Any) -> int:
        for attr in ("status", "status_code"):
            value = getattr(page, attr, None)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return 200

    def _extract_body(self, page: Any) -> bytes:
        for attr in ("body", "content", "html", "text"):
            if not hasattr(page, attr):
                continue
            body = self._coerce_bytes(getattr(page, attr))
            if body is not None:
                return body
        return str(page).encode("utf-8")

    def _extract_headers(self, page: Any) -> dict[str, str]:
        for attr in ("headers", "response_headers"):
            value = getattr(page, attr, None)
            if value is None:
                continue
            if isinstance(value, Mapping):
                return self._normalize_mapping(value)
        return {}

    def _normalize_mapping(self, mapping: Mapping[Any, Any]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in mapping.items():
            normalized[self._stringify(key)] = self._stringify(value)
        return normalized

    def _coerce_bytes(self, value: Any) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        return None

    def _stringify(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)


class ScraplingFallbackMiddleware:
    """Retry opt-in requests through Scrapling when the original response looks blocked."""

    def __init__(
        self,
        *,
        headless: bool,
        solve_cloudflare: bool,
        timeout_ms: int,
        wait_ms: int,
        block_statuses: list[int],
        real_chrome: bool,
        block_webrtc: bool,
        hide_canvas: bool,
        allow_webgl: bool,
        adapter_factory: type[ScraplingSessionAdapter] = ScraplingSessionAdapter,
    ) -> None:
        self.headless = headless
        self.solve_cloudflare = solve_cloudflare
        self.timeout_ms = timeout_ms
        self.wait_ms = wait_ms
        self.block_statuses = {int(status) for status in block_statuses}
        self.real_chrome = real_chrome
        self.block_webrtc = block_webrtc
        self.hide_canvas = hide_canvas
        self.allow_webgl = allow_webgl
        self.adapter_factory = adapter_factory
        self.adapter: ScraplingSessionAdapter | None = None
        self.adapter_unavailable = False
        self.crawler = None
        self.logger = get_logger("scrapling_middleware")

    @classmethod
    def from_crawler(cls, crawler) -> "ScraplingFallbackMiddleware":
        middleware = cls(
            headless=crawler.settings.getbool("FACTCHECK_SCRAPLING_HEADLESS", True),
            solve_cloudflare=crawler.settings.getbool("FACTCHECK_SCRAPLING_SOLVE_CLOUDFLARE", True),
            timeout_ms=crawler.settings.getint("FACTCHECK_SCRAPLING_TIMEOUT_MS", 60000),
            wait_ms=crawler.settings.getint("FACTCHECK_SCRAPLING_WAIT_MS", 1000),
            block_statuses=[
                int(status)
                for status in crawler.settings.getlist(
                    "FACTCHECK_SCRAPLING_BLOCK_STATUSES", [403, 429, 503]
                )
            ],
            real_chrome=crawler.settings.getbool("FACTCHECK_SCRAPLING_REAL_CHROME", False),
            block_webrtc=crawler.settings.getbool("FACTCHECK_SCRAPLING_BLOCK_WEBRTC", False),
            hide_canvas=crawler.settings.getbool("FACTCHECK_SCRAPLING_HIDE_CANVAS", False),
            allow_webgl=crawler.settings.getbool("FACTCHECK_SCRAPLING_ALLOW_WEBGL", True),
        )
        middleware.crawler = crawler
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_response(self, request: Request, response: Response) -> Response:
        profile = request.meta.get("scrapling")
        if not isinstance(profile, dict) or not profile.get("enabled"):
            return response
        if request.meta.get("scrapling_attempted"):
            return response
        if not self._response_looks_blocked(response):
            return response

        request.meta["scrapling_attempted"] = True
        return self._as_deferred(self._fetch_with_scrapling(request, response, profile))

    def spider_closed(self, spider):
        return self._as_deferred(self._reset_adapter())

    def _get_adapter(self) -> ScraplingSessionAdapter | None:
        if self.adapter_unavailable:
            return None
        if self.adapter is not None:
            return self.adapter
        try:
            self.adapter = self.adapter_factory(
                headless=self.headless,
                solve_cloudflare=self.solve_cloudflare,
                real_chrome=self.real_chrome,
                block_webrtc=self.block_webrtc,
                hide_canvas=self.hide_canvas,
                allow_webgl=self.allow_webgl,
            )
        except Exception as exc:
            self.adapter_unavailable = True
            self.logger.warning(
                "scrapling_unavailable",
                spider=self._spider_name,
                error=str(exc),
            )
            return None
        return self.adapter

    async def _reset_adapter(self) -> None:
        if self.adapter is None:
            return
        try:
            await self.adapter.close()
        finally:
            self.adapter = None

    async def _fetch_with_scrapling(
        self,
        request: Request,
        response: Response,
        profile: dict[str, Any],
    ) -> Response:
        adapter = self._get_adapter()
        if adapter is None:
            return response

        self.logger.info(
            "scrapling_fallback_triggered",
            spider=self._spider_name,
            url=request.url,
            status=response.status,
        )
        try:
            result = await adapter.fetch(
                request,
                timeout_ms=int(profile.get("timeout_ms", self.timeout_ms)),
                wait_ms=int(profile.get("wait_ms", self.wait_ms)),
                wait_selector=self._clean_string(profile.get("wait_selector")),
                extra_headers=self._coerce_headers(profile.get("extra_headers")),
            )
        except Exception as exc:
            self.logger.warning(
                "scrapling_fetch_failed",
                spider=self._spider_name,
                url=request.url,
                error=str(exc),
            )
            await self._reset_adapter()
            return response

        return self._build_response(request, result)

    def _response_looks_blocked(self, response: Response) -> bool:
        if response.status in self.block_statuses:
            return True
        snippet = response.body[:32768].lower()
        return any(marker in snippet for marker in CLOUDFLARE_BLOCK_MARKERS)

    def _build_response(self, request: Request, result: ScraplingFetchResult) -> Response:
        original_headers = Headers(result.headers)
        original_content_type = self._header_value(original_headers, "Content-Type").lower()
        is_html = self._looks_like_html(result.body, original_content_type)
        headers = self._normalize_result_headers(original_headers, is_html=is_html)
        content_type = self._header_value(headers, "Content-Type").lower()
        encoding = "utf-8" if is_html else (self._extract_charset(content_type) or "utf-8")
        response_cls = HtmlResponse if is_html else TextResponse
        return response_cls(
            url=result.url,
            status=result.status,
            headers=headers,
            body=result.body,
            encoding=encoding,
            request=request,
        )

    def _normalize_result_headers(self, headers: Headers, *, is_html: bool) -> Headers:
        normalized = Headers(headers)
        for header_name in SCRAPLING_STRIPPED_RESPONSE_HEADERS:
            normalized.pop(header_name, None)

        if is_html:
            normalized["Content-Type"] = SCRAPLING_HTML_CONTENT_TYPE

        return normalized

    def _coerce_headers(self, value: Any) -> dict[str, str] | None:
        if isinstance(value, Mapping):
            return {str(key): str(item) for key, item in value.items()}
        return None

    def _clean_string(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _header_value(self, headers: Headers, key: str) -> str:
        value = headers.get(key.encode("utf-8"))
        if value is None:
            value = headers.get(key)
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _extract_charset(self, content_type: str) -> str | None:
        marker = "charset="
        if marker not in content_type:
            return None
        return content_type.split(marker, maxsplit=1)[1].split(";", maxsplit=1)[0].strip()

    def _looks_like_html(self, body: bytes, content_type: str) -> bool:
        if "html" in content_type:
            return True
        stripped = body.lstrip().lower()
        return stripped.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))

    @property
    def _spider_name(self) -> str:
        if self.crawler is not None and getattr(self.crawler, "spider", None) is not None:
            return self.crawler.spider.name
        return "unknown"

    def _as_deferred(self, value):
        if not is_reactor_installed():
            return value
        return deferred_from_coro(value)

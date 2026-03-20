from __future__ import annotations

from pathlib import Path

from scrapy import Request
from scrapy.http import HtmlResponse, TextResponse

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "spiders"


def load_fixture(*parts: str) -> str:
    return (FIXTURES_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def make_html_response(url: str, body: str) -> HtmlResponse:
    request = Request(url=url)
    return HtmlResponse(url=url, request=request, body=body.encode("utf-8"), encoding="utf-8")


def make_text_response(url: str, body: str, *, meta: dict | None = None) -> TextResponse:
    request = Request(url=url, meta=meta or {})
    return TextResponse(url=url, request=request, body=body.encode("utf-8"), encoding="utf-8")

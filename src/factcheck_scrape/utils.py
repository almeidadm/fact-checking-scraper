from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS_EXACT = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def generate_run_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    random_part = uuid.uuid4().hex[:8]
    return f"{now}-{random_part}"


def canonicalize_url(url: str) -> str:
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query_params = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_"):
            continue
        if key_lower in TRACKING_PARAMS_EXACT:
            continue
        query_params.append((key, value))

    query_params.sort()
    query = urlencode(query_params)
    return urlunsplit((scheme, netloc, path, query, ""))


def make_item_id(agency_id: str, canonical_url: str) -> str:
    raw = f"{agency_id}|{canonical_url}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ensure_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)

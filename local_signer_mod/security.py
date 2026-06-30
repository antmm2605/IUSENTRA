from __future__ import annotations

import re
from urllib.parse import urlparse

_LOCALHOST_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}
_TRUSTED_NULL_ORIGIN_REFERER_HOSTS = {
    "app.iusentra.it",
    "localhost",
    "127.0.0.1",
    "::1",
}


def normalize_origin(origin: str) -> str:
    origin = (origin or "").strip().rstrip("/")
    if not origin:
        return ""
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    port = parsed.port
    default_port = 80 if parsed.scheme == "http" else 443
    if port and port != default_port:
        return f"{parsed.scheme}://{host}:{port}"
    return f"{parsed.scheme}://{host}"


def is_loopback_origin(origin: str) -> bool:
    parsed = urlparse((origin or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    return parsed.hostname.lower() in _LOCALHOST_ORIGIN_HOSTS


def build_allowed_origins(raw_origins: str) -> set[str]:
    origins: set[str] = set()
    for chunk in re.split(r"[\s,;]+", raw_origins or ""):
        origin = normalize_origin(chunk)
        if origin:
            origins.add(origin)
    return origins


def is_allowed_origin(origin: str, raw_origins: str) -> bool:
    if not origin:
        return True
    if is_loopback_origin(origin):
        return True
    return normalize_origin(origin) in build_allowed_origins(raw_origins)


def is_allowed_origin_or_referer(origin: str, referer: str, raw_origins: str) -> bool:
    """Allow sandboxed browser Origin:null only when Referer is IUSENTRA."""

    normalized_origin = (origin or "").strip().lower()
    if normalized_origin != "null":
        return is_allowed_origin(origin, raw_origins)
    if not referer:
        return False
    parsed = urlparse((referer or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host not in _TRUSTED_NULL_ORIGIN_REFERER_HOSTS:
        return False
    referer_origin = normalize_origin(f"{parsed.scheme}://{host}{':' + str(parsed.port) if parsed.port else ''}")
    return is_allowed_origin(referer_origin, raw_origins)

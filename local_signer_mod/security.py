from __future__ import annotations

import re
from urllib.parse import urlparse

_LOCALHOST_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}


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

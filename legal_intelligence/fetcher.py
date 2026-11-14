"""Download controllato delle fonti ufficiali."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit

import requests

from .sources import LegalSource


USER_AGENT = "IUSENTRA-Legal-Intelligence-Daily/1.0 (+https://iusentra.local)"


@dataclass
class FetchResult:
    ok: bool
    url: str
    status_code: int = 0
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""


class OfficialSourceFetcher:
    def __init__(self, *, timeout: float = 15.0, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch(self, source: LegalSource, *, previous_headers: Mapping[str, str] | None = None) -> FetchResult:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xml,application/rss+xml,text/plain,*/*;q=0.8",
        }
        previous_headers = previous_headers or {}
        if previous_headers.get("etag"):
            headers["If-None-Match"] = previous_headers["etag"]
        if previous_headers.get("last_modified"):
            headers["If-Modified-Since"] = previous_headers["last_modified"]
        # Il portale MEF non sempre invia l'intermedio: il bundle locale
        # aggiunge il certificato emittente alle radici ordinarie.
        opzioni = {}
        if source.id == "documentazione_tributaria" and urlsplit(source.url).hostname == "def.finanze.it":
            bundle = os.getenv("IUSENTRA_TRIBUTARIO_CA_BUNDLE", "").strip()
            if bundle:
                opzioni["verify"] = bundle
        try:
            response = self.session.get(
                source.url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True,
                **opzioni,
            )
            return FetchResult(
                ok=200 <= response.status_code < 400,
                url=response.url,
                status_code=response.status_code,
                content=response.content or b"",
                headers={str(k).lower(): str(v) for k, v in response.headers.items()},
                error="" if response.status_code < 400 else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return FetchResult(ok=False, url=source.url, error=str(exc))

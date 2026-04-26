from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

import requests


class OfficialSourceHttpClient:
    def __init__(self, timeout: int = 120, delay_seconds: float = 0.8):
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "IUSENTRA-Lex-OfficialSources/1.0 (+studio-legale; polite sync)",
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json,application/pdf,application/zip,*/*",
        })

    def get(self, url: str, *, headers: dict | None = None, params: dict | None = None, allow_redirects: bool = True) -> requests.Response:
        time.sleep(self.delay_seconds)
        response = self.session.get(url, headers=headers or {}, params=params, timeout=self.timeout, allow_redirects=allow_redirects)
        response.raise_for_status()
        return response

    def download(self, url: str, output_dir: Path, *, filename: str | None = None, headers: dict | None = None, params: dict | None = None) -> Path:
        response = self.get(url, headers=headers, params=params, allow_redirects=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            parsed = urlparse(response.url)
            filename = Path(parsed.path).name or "download.bin"
        path = output_dir / sanitize_filename(filename)
        path.write_bytes(response.content)
        return path


def sanitize_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " ._-()[]" else "_" for ch in value).strip()
    return safe[:180] or "download.bin"

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .base import BaseConnector
from ..models import DocumentCandidate
from ..http_client import sanitize_filename


class StaticUrlsConnector(BaseConnector):
    def fetch(self, output_dir: Path):
        urls = self.source.settings.get("urls", []) or []
        for url in urls:
            if isinstance(url, dict):
                href = url.get("url")
                title = url.get("title") or href
            else:
                href = str(url)
                title = href
            if not href:
                continue
            response = self.client.get(href)
            name = Path(urlparse(response.url).path).name or sanitize_filename(title) or "document.bin"
            path = self._write_content(output_dir, name, response.content)
            yield DocumentCandidate(
                source_id=self.source.id,
                title=title,
                url=response.url,
                content_type=response.headers.get("content-type", ""),
                filename=name,
                topics=self.source.topics,
                metadata={"connector": "static_urls"},
            ), path

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import feedparser

from .base import BaseConnector
from ..models import DocumentCandidate
from ..http_client import sanitize_filename


class FeedConnector(BaseConnector):
    def fetch(self, output_dir: Path):
        feeds = self.source.settings.get("feeds", []) or []
        max_items = int(self.source.settings.get("max_items", 50))
        for feed_url in feeds:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:max_items]:
                href = getattr(entry, "link", "")
                if not href:
                    continue
                response = self.client.get(href)
                title = getattr(entry, "title", href)
                name = Path(urlparse(response.url).path).name or sanitize_filename(title) + ".html"
                path = self._write_content(output_dir, name, response.content)
                yield DocumentCandidate(
                    source_id=self.source.id,
                    title=title,
                    url=response.url,
                    content_type=response.headers.get("content-type", ""),
                    filename=name,
                    published_at=getattr(entry, "published", None) or getattr(entry, "updated", None),
                    topics=self.source.topics,
                    metadata={"connector": "feed", "feed": feed_url},
                ), path

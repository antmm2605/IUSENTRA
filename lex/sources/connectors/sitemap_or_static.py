from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from lxml import etree

from .base import BaseConnector
from ..models import DocumentCandidate
from ..http_client import sanitize_filename


class SitemapOrStaticConnector(BaseConnector):
    def fetch(self, output_dir: Path):
        yielded = False
        for item in self._fetch_static(output_dir):
            yielded = True
            yield item
        for item in self._fetch_sitemaps(output_dir):
            yielded = True
            yield item
        if not yielded and self.source.settings.get("discovery_required"):
            print(f"[INFO] {self.source.id}: nessun URL/feed/sitemap configurato. Usa tools/source_endpoint_capture.py o inserisci URL ufficiali in config.")

    def _fetch_static(self, output_dir: Path):
        urls = self.source.settings.get("urls", []) or []
        for url in urls:
            href = url.get("url") if isinstance(url, dict) else str(url)
            title = (url.get("title") if isinstance(url, dict) else None) or href
            if not href:
                continue
            response = self.client.get(href)
            name = Path(urlparse(response.url).path).name or sanitize_filename(title) + ".html"
            path = self._write_content(output_dir, name, response.content)
            yield DocumentCandidate(self.source.id, title, response.url, content_type=response.headers.get("content-type", ""), filename=name, topics=self.source.topics, metadata={"connector": "static"}), path

    def _fetch_sitemaps(self, output_dir: Path):
        sitemaps = self.source.settings.get("sitemaps", []) or []
        allowed = [v.lower() for v in self.source.settings.get("allowed_path_contains", []) or []]
        max_urls = int(self.source.settings.get("max_urls", 100))
        count = 0
        for sitemap_url in sitemaps:
            xml = self.client.get(sitemap_url).content
            urls = self._parse_sitemap(xml)
            for href in urls:
                if count >= max_urls:
                    break
                if allowed and not any(term in href.lower() for term in allowed):
                    continue
                response = self.client.get(href)
                title = Path(urlparse(response.url).path).name or response.url
                name = Path(urlparse(response.url).path).name or sanitize_filename(title) + ".html"
                path = self._write_content(output_dir, name, response.content)
                count += 1
                yield DocumentCandidate(self.source.id, title, response.url, content_type=response.headers.get("content-type", ""), filename=name, topics=self.source.topics, metadata={"connector": "sitemap", "sitemap": sitemap_url}), path

    def _parse_sitemap(self, xml: bytes) -> list[str]:
        root = etree.fromstring(xml)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = root.xpath(".//sm:url/sm:loc/text()", namespaces=ns)
        if not locs:
            locs = root.xpath(".//*[local-name()='url']/*[local-name()='loc']/text()")
        return [str(x).strip() for x in locs if str(x).strip()]

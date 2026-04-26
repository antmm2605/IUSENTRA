from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models import DocumentCandidate, SourceConfig
from ..http_client import OfficialSourceHttpClient, sanitize_filename


class BaseConnector:
    def __init__(self, source: SourceConfig, client: OfficialSourceHttpClient | None = None):
        self.source = source
        self.client = client or OfficialSourceHttpClient()

    def fetch(self, output_dir: Path) -> Iterable[tuple[DocumentCandidate, Path]]:
        raise NotImplementedError

    def _write_content(self, output_dir: Path, filename: str, content: bytes | str) -> Path:
        source_dir = output_dir / self.source.id
        source_dir.mkdir(parents=True, exist_ok=True)
        path = source_dir / sanitize_filename(filename)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
        return path

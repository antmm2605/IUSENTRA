from __future__ import annotations

import json
from pathlib import Path

from .models import SourceConfig


def load_sources(config_path: str | Path) -> list[SourceConfig]:
    path = Path(config_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = []
    for item in data.get("sources", []):
        sources.append(SourceConfig(
            id=item["id"],
            name=item.get("name", item["id"]),
            enabled=bool(item.get("enabled", False)),
            priority=int(item.get("priority", 50)),
            connector=item.get("connector", "static_urls"),
            type=item.get("type", ""),
            refresh=item.get("refresh", "manual"),
            base_url=item.get("base_url", ""),
            topics=list(item.get("topics", [])),
            settings=dict(item.get("settings", {})),
        ))
    return sources


def write_default_config(target_path: str | Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "config" / "lex_official_sources.example.json"
    source = source.resolve()
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target

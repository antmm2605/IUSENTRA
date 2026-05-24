from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PageArtifact:
    page: int
    image_path: str
    sha256: str
    width: int
    height: int
    source_kind: str = "raster"
    text_hint: str = ""
    preprocessing: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EngineRun:
    engine: str
    version: str
    tokens: list[dict[str, Any]]
    text: str
    pages_text: list[str]
    language: str = "ita"
    language_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

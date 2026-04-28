"""Discovery dei file JSON persistenti nel data root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JsonDataFile:
    path: Path
    relative_path: str
    size_bytes: int


def discover_json_files(root: str | Path) -> list[JsonDataFile]:
    base = Path(root)
    if not base.exists():
        return []
    files: list[JsonDataFile] = []
    for path in sorted(base.rglob("*.json")):
        if any(part.startswith(".") for part in path.relative_to(base).parts):
            continue
        files.append(
            JsonDataFile(
                path=path,
                relative_path=path.relative_to(base).as_posix(),
                size_bytes=path.stat().st_size,
            )
        )
    return files

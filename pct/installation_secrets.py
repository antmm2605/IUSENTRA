from __future__ import annotations

import base64
import os
from pathlib import Path
from uuid import uuid4


def _ensure_private_file(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, raw)
        finally:
            os.close(fd)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _load_local_key(path: Path) -> bytes:
    if not path.exists():
        return b""
    raw = path.read_bytes().strip()
    if not raw:
        return b""
    try:
        return base64.urlsafe_b64decode(raw)
    except Exception:
        return raw


def _store_local_key(path: Path, raw: bytes) -> None:
    _ensure_private_file(path, base64.urlsafe_b64encode(raw))


def _new_local_key_material() -> bytes:
    return uuid4().bytes + uuid4().bytes


def ensure_installation_local_key(path: str | Path) -> None:
    key_path = Path(path)
    if _load_local_key(key_path):
        return
    _store_local_key(key_path, _new_local_key_material())

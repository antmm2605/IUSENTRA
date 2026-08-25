"""Runtime metadata for the browser-local IUSENTRA Local Signer."""

from __future__ import annotations

import re
import os
from functools import lru_cache
from pathlib import Path

LOCAL_SIGNER_BROWSER_URL = os.getenv("IUSENTRA_LOCAL_SIGNER_BROWSER_URL", "http://127.0.0.1:27272")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def latest_local_signer_release() -> dict[str, str]:
    """Return the latest Local Signer release advertised to the browser UI."""

    tools_dir = _repo_root() / "tools"
    source = (tools_dir / "local_signer.py").read_text(encoding="utf-8")
    match = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', source)
    version = match.group(1) if match else "n.d."

    macos_dmg = tools_dir / "dist" / f"IUSENTRA-LocalSigner-{version}.dmg"
    return {
        "version": version,
        "browser_url": LOCAL_SIGNER_BROWSER_URL,
        "download_page": "/impostazioni?tab=firma",
        "windows_filename": f"SetupLocalSigner-{version}.exe",
        "macos_filename": macos_dmg.name if macos_dmg.exists() else f"InstallaLocalSigner-{version}.command",
        "linux_filename": f"InstallaLocalSigner-{version}.run",
    }

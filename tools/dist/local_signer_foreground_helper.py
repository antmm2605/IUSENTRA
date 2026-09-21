"""Ponte monouso tra il clic IUSENTRA e il processo Local Signer su Windows.

Il processo viene avviato dal protocol handler registrato per il singolo clic.
Non enumera, legge, sposta o compila finestre: concede soltanto al PID restituito
dal Local Signer il diritto Win32 di presentare naturalmente la propria UI.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


_LOOPBACK = "http://127.0.0.1:27272"
_NONCE_RE = re.compile(r"[A-Za-z0-9_-]{32,64}")


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{_LOOPBACK}{path}",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3.0) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _nonce_from_uri(raw_uri: str) -> str:
    parsed = urlparse(str(raw_uri or "").strip())
    if parsed.scheme.casefold() != "iusentra-local-signer" or parsed.netloc.casefold() != "foreground":
        return ""
    if parsed.path not in {"", "/"} or parsed.fragment:
        return ""
    values = parse_qs(parsed.query, keep_blank_values=True)
    if set(values) != {"nonce"} or len(values.get("nonce") or []) != 1:
        return ""
    nonce = str(values["nonce"][0] or "")
    return nonce if _NONCE_RE.fullmatch(nonce) else ""


def _allow_set_foreground_window(process_id: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    user32.AllowSetForegroundWindow.restype = wintypes.BOOL
    return bool(user32.AllowSetForegroundWindow(wintypes.DWORD(int(process_id))))


def _control_action_from_uri(raw_uri: str) -> str:
    parsed = urlparse(str(raw_uri or "").strip())
    if parsed.scheme.casefold() != "iusentra-local-signer":
        return ""
    action = parsed.netloc.casefold()
    if action not in {"restart", "update"}:
        return ""
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return ""
    return action


def _launch_control_action(raw_uri: str) -> int:
    starter = Path(__file__).resolve().with_name("start_local_signer.vbs")
    wscript = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "wscript.exe"
    if not starter.is_file() or not wscript.is_file():
        return 7
    subprocess.Popen(
        [str(wscript), str(starter), raw_uri],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
    return 0


def run(raw_uri: str) -> int:
    if sys.platform != "win32":
        return 2
    nonce = _nonce_from_uri(raw_uri)
    if not nonce:
        return _launch_control_action(raw_uri) if _control_action_from_uri(raw_uri) else 3
    try:
        claim = _post_json("/foreground/claim", {"nonce": nonce})
        process_id = int(claim.get("target_pid") or 0)
        claim_token = str(claim.get("claim_token") or "")
        if claim.get("ok") is not True or process_id <= 0 or not claim_token:
            return 4
        granted = _allow_set_foreground_window(process_id)
        completed = _post_json(
            "/foreground/complete",
            {"nonce": nonce, "claim_token": claim_token, "granted": granted},
        )
        return 0 if granted and completed.get("state") == "granted" else 5
    except Exception:
        return 6


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1] if len(sys.argv) == 2 else ""))

"""Presenza realtime in memoria per l'assistenza remota."""

from __future__ import annotations

import json
import threading
from typing import Any


_ROOMS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def support_presence(public_id: str) -> dict[str, bool]:
    with _LOCK:
        room = _ROOMS.get(str(public_id or ""), {})
        return {
            "operator": bool(room.get("operator")),
            "client": bool(room.get("client")),
        }


def register_support_peer(public_id: str, role: str, ws: Any) -> Any:
    with _LOCK:
        room = _ROOMS.setdefault(str(public_id or ""), {"operator": None, "client": None})
        room[str(role or "")] = ws
        other_role = "client" if role == "operator" else "operator"
        return room.get(other_role)


def get_support_peer(public_id: str, role: str) -> Any:
    with _LOCK:
        return (_ROOMS.get(str(public_id or ""), {}) or {}).get(str(role or ""))


def unregister_support_peer(public_id: str, role: str, ws: Any) -> Any:
    with _LOCK:
        room = _ROOMS.get(str(public_id or ""))
        if not room:
            return None
        if room.get(str(role or "")) is ws:
            room[str(role or "")] = None
        other_role = "client" if role == "operator" else "operator"
        other_ws = room.get(other_role)
        if not room.get("operator") and not room.get("client"):
            _ROOMS.pop(str(public_id or ""), None)
        return other_ws


def safe_support_send(ws: Any, payload: dict[str, Any]) -> None:
    if ws is None:
        return
    try:
        ws.send(json.dumps(payload))
    except Exception:
        return

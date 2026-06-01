"""Presenza realtime e relay messaggi per l'assistenza remota."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any


_ROOMS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()
_SEND_LOCKS: dict[int, threading.Lock] = {}
_REDIS_CLIENT: Any | None = None
_REDIS_LOCK = threading.Lock()
_PRESENCE_TTL_SECONDS = 300
_CHANNEL_PREFIX = "iusentra:support:relay"
_PRESENCE_PREFIX = "iusentra:support:presence"


def new_support_connection_id() -> str:
    return uuid.uuid4().hex


def _redis_url() -> str:
    return str(os.getenv("REDIS_URL") or "").strip()


def _redis() -> Any | None:
    global _REDIS_CLIENT
    url = _redis_url()
    if not url:
        return None
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        try:
            import redis

            client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
            client.ping()
            _REDIS_CLIENT = client
        except Exception:
            _REDIS_CLIENT = None
        return _REDIS_CLIENT


def _presence_key(public_id: str) -> str:
    return f"{_PRESENCE_PREFIX}:{str(public_id or '').strip()}"


def _channel(public_id: str) -> str:
    return f"{_CHANNEL_PREFIX}:{str(public_id or '').strip()}"


def _redis_touch(public_id: str, role: str) -> None:
    client = _redis()
    if client is None:
        return
    key = _presence_key(public_id)
    try:
        client.hset(key, str(role or ""), str(time.time()))
        client.expire(key, _PRESENCE_TTL_SECONDS)
    except Exception:
        return


def _redis_remove(public_id: str, role: str) -> None:
    client = _redis()
    if client is None:
        return
    try:
        client.hdel(_presence_key(public_id), str(role or ""))
    except Exception:
        return


def _redis_presence(public_id: str) -> dict[str, bool]:
    client = _redis()
    if client is None:
        return {"operator": False, "client": False}
    try:
        values = client.hgetall(_presence_key(public_id)) or {}
    except Exception:
        return {"operator": False, "client": False}
    now = time.time()
    result = {"operator": False, "client": False}
    for role in result:
        try:
            ts = float(values.get(role) or "0")
        except Exception:
            ts = 0.0
        result[role] = bool(ts and now - ts <= _PRESENCE_TTL_SECONDS)
    return result


def support_presence(public_id: str) -> dict[str, bool]:
    with _LOCK:
        room = _ROOMS.get(str(public_id or ""), {})
        local = {
            "operator": bool(room.get("operator")),
            "client": bool(room.get("client")),
        }
    remote = _redis_presence(public_id)
    return {
        "operator": bool(local["operator"] or remote["operator"]),
        "client": bool(local["client"] or remote["client"]),
    }


def register_support_peer(public_id: str, role: str, ws: Any) -> Any:
    with _LOCK:
        room = _ROOMS.setdefault(str(public_id or ""), {"operator": None, "client": None})
        room[str(role or "")] = ws
        _SEND_LOCKS.setdefault(id(ws), threading.Lock())
        other_role = "client" if role == "operator" else "operator"
        other_ws = room.get(other_role)
    _redis_touch(public_id, role)
    return other_ws


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
        _SEND_LOCKS.pop(id(ws), None)
        other_role = "client" if role == "operator" else "operator"
        other_ws = room.get(other_role)
        if not room.get("operator") and not room.get("client"):
            _ROOMS.pop(str(public_id or ""), None)
    _redis_remove(public_id, role)
    return other_ws


def safe_support_send(ws: Any, payload: dict[str, Any]) -> None:
    if ws is None:
        return
    try:
        lock = _SEND_LOCKS.setdefault(id(ws), threading.Lock())
        with lock:
            ws.send(json.dumps(payload))
    except Exception:
        return


def publish_support_message(
    public_id: str,
    *,
    target_role: str,
    payload: dict[str, Any],
    source_role: str = "",
    source_connection_id: str = "",
) -> None:
    client = _redis()
    if client is None:
        return
    envelope = {
        "target_role": str(target_role or ""),
        "source_role": str(source_role or ""),
        "source_connection_id": str(source_connection_id or ""),
        "payload": payload,
    }
    try:
        client.publish(_channel(public_id), json.dumps(envelope, ensure_ascii=False))
    except Exception:
        return


def start_support_relay_listener(
    public_id: str,
    *,
    role: str,
    ws: Any,
    connection_id: str,
    stop_event: threading.Event,
) -> threading.Thread | None:
    client = _redis()
    if client is None:
        return None

    def _listen() -> None:
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        try:
            pubsub.subscribe(_channel(public_id))
            while not stop_event.is_set():
                message = pubsub.get_message(timeout=1.0)
                if not message:
                    continue
                raw = message.get("data")
                try:
                    envelope = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
                except Exception:
                    continue
                if str(envelope.get("source_connection_id") or "") == connection_id:
                    continue
                if str(envelope.get("target_role") or "") != str(role or ""):
                    continue
                payload = envelope.get("payload")
                if isinstance(payload, dict):
                    safe_support_send(ws, payload)
        finally:
            try:
                pubsub.close()
            except Exception:
                pass

    thread = threading.Thread(target=_listen, name=f"iusentra-support-relay-{role}", daemon=True)
    thread.start()
    return thread

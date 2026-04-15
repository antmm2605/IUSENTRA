"""Replay richieste Lex."""

from __future__ import annotations


def replay_request(payload: dict) -> dict:
    return {"replayed": True, "payload": payload}

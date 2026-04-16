"""Store in-memory leggeri per la memoria strutturata di Lex."""

from __future__ import annotations

from collections import defaultdict


class StateStore:
    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}

    def update(self, key: str, payload: dict) -> None:
        if not key:
            return
        self.entries[key] = dict(payload or {})

    def get(self, key: str) -> dict:
        return dict(self.entries.get(key) or {})


class UniqueListStore:
    def __init__(self) -> None:
        self.entries = defaultdict(list)

    def extend(self, key: str, items, *, key_builder) -> None:
        if not key:
            return
        bucket = list(self.entries.get(key) or [])
        seen = {key_builder(item) for item in bucket}
        for item in list(items or []):
            item_key = key_builder(item)
            if item_key in seen:
                continue
            seen.add(item_key)
            bucket.append(item)
        self.entries[key] = bucket

    def get(self, key: str):
        return list(self.entries.get(key) or [])
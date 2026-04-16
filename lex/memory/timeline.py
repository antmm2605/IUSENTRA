"""Timeline strutturata degli eventi Lex."""

from __future__ import annotations

from .store import UniqueListStore


class TimelineStore:
    def __init__(self) -> None:
        self._session = UniqueListStore()
        self._case = UniqueListStore()

    @staticmethod
    def _event_key(event) -> tuple:
        return (
            str(getattr(event, "module", "") or ""),
            str(getattr(event, "event_type", "") or ""),
            str(getattr(event, "entity_id", "") or ""),
            repr(dict(getattr(event, "payload", {}) or {})),
        )

    def record(self, session_id: str, fascicolo_id: str, events) -> None:
        self._session.extend(session_id, events, key_builder=self._event_key)
        self._case.extend(fascicolo_id, events, key_builder=self._event_key)

    def session_events(self, session_id: str):
        return self._session.get(session_id)

    def case_events(self, fascicolo_id: str):
        return self._case.get(fascicolo_id)
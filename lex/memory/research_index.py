"""Indice leggero delle fonti e query richiamate da Lex."""

from __future__ import annotations

from .store import UniqueListStore


class ResearchIndexStore:
    def __init__(self) -> None:
        self._session = UniqueListStore()
        self._case = UniqueListStore()

    @staticmethod
    def _key(item: str) -> str:
        return str(item or "").strip()

    def remember(self, session_id: str, fascicolo_id: str, evidence_pack: dict) -> None:
        items = [
            *list(evidence_pack.get("queries") or []),
            *list(evidence_pack.get("official_sources") or []),
            *list(evidence_pack.get("trusted_sources") or []),
        ]
        self._session.extend(session_id, items, key_builder=self._key)
        self._case.extend(fascicolo_id, items, key_builder=self._key)

    def session_items(self, session_id: str):
        return self._session.get(session_id)

    def case_items(self, fascicolo_id: str):
        return self._case.get(fascicolo_id)
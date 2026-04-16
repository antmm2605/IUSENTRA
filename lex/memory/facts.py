"""Store facts per sessione e fascicolo."""

from __future__ import annotations

from .store import UniqueListStore


class FactMemoryStore:
    def __init__(self) -> None:
        self._session = UniqueListStore()
        self._case = UniqueListStore()

    @staticmethod
    def _fact_key(fact) -> tuple:
        return (
            str(getattr(fact, "module", "") or ""),
            str(getattr(fact, "fact_type", "") or ""),
            repr(getattr(fact, "value", None)),
            str(getattr(fact, "entity_id", "") or ""),
            str(getattr(fact, "kind", "") or ""),
        )

    def remember(self, session_id: str, fascicolo_id: str, facts) -> None:
        self._session.extend(session_id, facts, key_builder=self._fact_key)
        self._case.extend(fascicolo_id, facts, key_builder=self._fact_key)

    def session_facts(self, session_id: str):
        return self._session.get(session_id)

    def case_facts(self, fascicolo_id: str):
        return self._case.get(fascicolo_id)
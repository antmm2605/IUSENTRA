"""Cache TTL in-process per risposte React costose e identiche tra richieste.

Pensata per pagine il cui payload non dipende dalla query (es. `/ricerca-legale`
senza termini di ricerca): la costruzione attraversa pipeline aggiornamenti,
registri, audit fonti e archivi ufficiali e può costare secondi di CPU e decine
di MB di allocazioni per richiesta. Entro il TTL la risposta già serializzata
viene riusata, azzerando il costo delle viste ripetute.

La cache conserva i byte JSON finali (già passati dalla redazione di sicurezza),
così le richieste in cache non condividono strutture mutabili tra loro.
"""

from __future__ import annotations

import threading
import time


class ReactPayloadTTLCache:
    """Cache chiave → byte JSON con scadenza e numero massimo di voci."""

    def __init__(self, *, ttl_seconds: float = 120.0, max_entries: int = 8) -> None:
        self.ttl_seconds = max(0.0, float(ttl_seconds or 0.0))
        self.max_entries = max(1, int(max_entries or 1))
        self._lock = threading.Lock()
        self._entries: dict[tuple, tuple[float, bytes]] = {}

    @property
    def enabled(self) -> bool:
        return self.ttl_seconds > 0

    def get(self, key: tuple) -> bytes | None:
        if not self.enabled:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at < now:
                self._entries.pop(key, None)
                return None
            return payload

    def set(self, key: tuple, payload: bytes) -> None:
        if not self.enabled or not isinstance(payload, (bytes, bytearray)):
            return
        now = time.monotonic()
        with self._lock:
            self._entries[key] = (now + self.ttl_seconds, bytes(payload))
            if len(self._entries) > self.max_entries:
                excess = len(self._entries) - self.max_entries
                # Espelle le voci più vicine alla scadenza per restare nel limite.
                for stale_key, _ in sorted(self._entries.items(), key=lambda item: item[1][0])[:excess]:
                    self._entries.pop(stale_key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

"""
Sincronizzazione multi-operatore per lo studio legale PCT.

Componenti:
  - FileLock       — lock esclusivo su file JSON (fcntl cross-process + threading)
  - GestoreSincronizzazione
      * lock_file()          acquisisce lock su un percorso
      * pubblica()           invia evento SSE a tutti i client connessi
      * subscribe()          registra un client SSE, restituisce (id, queue)
      * unsubscribe()        rimuove un client
      * sse_stream()         generatore SSE (heartbeat ogni 25 s)
      * versione_file()      mtime del file come ETag stringa
      * n_connessi           numero di client SSE attivi
"""

from __future__ import annotations

import fcntl
import json
import queue
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, Optional, Tuple


# ================================================================ File lock

class FileLock:
    """
    Lock esclusivo su file (cross-process via fcntl + cross-thread via RLock).

    Crea un file .lock accanto al percorso originale.
    Uso:
        with FileLock('/dati/clienti.json'):
            leggi_e_scrivi()
    """

    # Lock a livello di thread per ogni percorso (mappa globale)
    _thread_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

    def __init__(self, path: str):
        self._path = str(path)
        self._lock_path = self._path + ".lock"
        self._fd = None

    def _get_thread_lock(self) -> threading.RLock:
        with FileLock._meta_lock:
            if self._path not in FileLock._thread_locks:
                FileLock._thread_locks[self._path] = threading.RLock()
            return FileLock._thread_locks[self._path]

    def __enter__(self) -> "FileLock":
        self._get_thread_lock().acquire()
        Path(self._lock_path).parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self._lock_path, "w")
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None
        self._get_thread_lock().release()


# ================================================================ Evento

class Evento:
    """Evento di sincronizzazione pubblicato sull'event bus."""

    __slots__ = ("tipo", "modulo", "id_risorsa", "utente", "ts", "extra")

    def __init__(
        self,
        tipo: str,
        modulo: str,
        id_risorsa: str = "",
        utente: str = "",
        **extra: Any,
    ):
        self.tipo = tipo            # crea | modifica | elimina | info | reload
        self.modulo = modulo        # clienti | fascicoli | scadenze | agenda | messaggi | auth
        self.id_risorsa = id_risorsa
        self.utente = utente
        self.ts = int(time.time() * 1000)
        self.extra = extra

    def to_json(self) -> str:
        d = {
            "tipo": self.tipo,
            "modulo": self.modulo,
            "id": self.id_risorsa,
            "utente": self.utente,
            "ts": self.ts,
        }
        d.update(self.extra)
        return json.dumps(d, ensure_ascii=False)

    def to_sse(self) -> str:
        return f"data: {self.to_json()}\n\n"


# ================================================================ Gestore

# Sentinella per segnalare a un generatore SSE di terminare
_SENTINEL = object()


class GestoreSincronizzazione:
    """
    Gestore centralizzato di sincronizzazione multi-operatore.

    Thread-safe. Istanza singleton creata nel factory di Flask.
    """

    def __init__(self):
        self._bus_lock = threading.Lock()
        # client_id → queue.Queue
        self._subscribers: Dict[str, queue.Queue] = {}
        # username → client_id corrente (una sola connessione SSE per utente)
        self._user_to_client: Dict[str, str] = {}

    # ---------------------------------------------------------------- File locking

    @contextmanager
    def lock_file(self, path: str) -> Iterator[None]:
        """
        Acquisisce lock esclusivo su un file JSON.
        Garantisce che due operatori non scrivano lo stesso file contemporaneamente.
        """
        with FileLock(path):
            yield

    def leggi_atomico(self, path: str) -> Tuple[Any, str]:
        """
        Legge un file JSON in modo atomico.
        Restituisce (dati, versione) dove versione è il mtime come stringa.
        """
        p = Path(path)
        if not p.exists():
            return [], ""
        with FileLock(path):
            raw = p.read_text(encoding="utf-8")
            versione = str(p.stat().st_mtime)
        try:
            return json.loads(raw), versione
        except json.JSONDecodeError:
            return [], versione

    def scrivi_atomico(
        self,
        path: str,
        data: Any,
        versione_attesa: str = "",
    ) -> Tuple[bool, str]:
        """
        Scrive JSON in modo atomico con lock.

        Se versione_attesa è fornita, controlla che il file non sia stato
        modificato da un altro operatore (optimistic locking).

        Restituisce (successo, versione_nuova_o_attuale).
        """
        with FileLock(path):
            p = Path(path)
            if versione_attesa and p.exists():
                versione_attuale = str(p.stat().st_mtime)
                if versione_attuale != versione_attesa:
                    return False, versione_attuale   # conflitto!

            p.parent.mkdir(parents=True, exist_ok=True)
            # Scrittura atomica: scrive su temp poi rinomina
            tmp = Path(str(path) + f".tmp.{uuid.uuid4().hex[:8]}")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(p)
            return True, str(p.stat().st_mtime)

    def versione_file(self, path: str) -> str:
        """Restituisce il mtime del file come stringa ETag."""
        p = Path(path)
        if not p.exists():
            return ""
        return str(p.stat().st_mtime)

    # ---------------------------------------------------------------- SSE event bus

    def subscribe(self, user_key: str = "") -> Tuple[str, "queue.Queue[Evento]"]:
        """
        Registra un client SSE.

        Se user_key è fornito (username), sostituisce immediatamente la
        connessione precedente dello stesso utente, evitando l'accumulo
        di subscriber zombie quando l'utente naviga tra le pagine.

        Restituisce (client_id, queue) da usare con sse_stream().
        """
        client_id = uuid.uuid4().hex
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._bus_lock:
            if user_key:
                old_id = self._user_to_client.get(user_key)
                if old_id:
                    old_q = self._subscribers.pop(old_id, None)
                    if old_q is not None:
                        # Segnala al vecchio generatore di terminare
                        try:
                            old_q.put_nowait(_SENTINEL)
                        except queue.Full:
                            pass
                self._user_to_client[user_key] = client_id
            self._subscribers[client_id] = q
        return client_id, q

    def unsubscribe(self, client_id: str) -> None:
        with self._bus_lock:
            self._subscribers.pop(client_id, None)
            # Rimuovi il mapping utente se appartiene a questo client
            stale = [u for u, c in self._user_to_client.items() if c == client_id]
            for u in stale:
                del self._user_to_client[u]

    def pubblica(
        self,
        tipo: str,
        modulo: str,
        id_risorsa: str = "",
        utente: str = "",
        **extra: Any,
    ) -> int:
        """
        Pubblica un evento a tutti i client SSE connessi.
        Restituisce il numero di client raggiunti.
        """
        evento = Evento(tipo, modulo, id_risorsa, utente, **extra)
        morti: list = []
        raggiunti = 0
        with self._bus_lock:
            for cid, q in list(self._subscribers.items()):
                try:
                    q.put_nowait(evento)
                    raggiunti += 1
                except queue.Full:
                    morti.append(cid)
            for cid in morti:
                del self._subscribers[cid]
        return raggiunti

    def sse_stream(
        self,
        client_id: str,
        q: "queue.Queue[Evento]",
    ) -> Generator[str, None, None]:
        """
        Generatore per la response SSE di un client.
        Invia heartbeat ogni 25 secondi per mantenere la connessione aperta.
        """
        try:
            # Messaggio iniziale di connessione
            yield "data: {\"tipo\":\"connesso\"}\n\n"
            while True:
                try:
                    evento = q.get(timeout=25)
                    if evento is _SENTINEL:
                        # Connessione sostituita da una più recente dello stesso utente
                        break
                    yield evento.to_sse()
                except queue.Empty:
                    # heartbeat
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(client_id)

    @property
    def n_connessi(self) -> int:
        """Numero di client SSE attualmente connessi."""
        with self._bus_lock:
            return len(self._subscribers)

    def lista_connessi(self) -> list:
        """Restituisce la lista degli id dei client connessi."""
        with self._bus_lock:
            return list(self._subscribers.keys())

    # ---------------------------------------------------------------- Utilità

    def pubblica_broadcast(self, messaggio: str, utente: str = "sistema") -> int:
        """Invia un messaggio informativo a tutti gli operatori connessi."""
        return self.pubblica("info", "sistema", utente=utente, messaggio=messaggio)


# ================================================================ Singleton Flask-aware

_gestore: Optional[GestoreSincronizzazione] = None
_gestore_lock = threading.Lock()


def get_gestore() -> GestoreSincronizzazione:
    """Restituisce il singleton GestoreSincronizzazione (thread-safe)."""
    global _gestore
    if _gestore is None:
        with _gestore_lock:
            if _gestore is None:
                _gestore = GestoreSincronizzazione()
    return _gestore


def reset_gestore() -> None:
    """Reset del singleton (solo per test)."""
    global _gestore
    with _gestore_lock:
        _gestore = None

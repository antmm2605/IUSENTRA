"""Checkpoint della riconvalida nativa; nessuna modifica all'archivio SQL fonte."""
from __future__ import annotations

from pathlib import Path


def firma_archivio(conn):
    filename = next((row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main"), "")
    if not filename:
        raise ValueError("La riconvalida riprendibile richiede un archivio SQLite persistente")
    source = Path(filename).resolve(strict=True)
    signature = {"path": str(source)}
    # Il WAL è parte della fonte. Lo SHM è soltanto coordinamento dei lettori.
    # Anche checkpoint o riscritture senza nuovi fatti fanno ripartire il
    # controllo: è una scelta conservativa, mai una falsa conferma.
    for suffix in ("", "-wal", "-journal"):
        path = Path(str(source) + suffix)
        try:
            stat = path.stat()
            signature[suffix or "main"] = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino]
        except FileNotFoundError:
            signature[suffix] = None
    return signature


def prepara(conn, meta):
    if not (meta.get("prima_costruzione") or {}).get("completa"):
        raise ValueError("Terminare la prima costruzione prima della riconvalida finale")
    signature = firma_archivio(conn)
    state = meta.get("riconvalida_iniziale")
    if not state or state.get("firma_archivio") != signature:
        state = {"ultimo_id": 0, "posizione_pulizia": 0, "fase": "impronte",
                 "firma_archivio": signature, "completa": False}
        meta["riconvalida_iniziale"] = state
    meta["riconvalida_finale_richiesta"] = True
    return state, int(conn.execute("PRAGMA data_version").fetchone()[0])


def concludi(conn, meta, state, data_version):
    stable = (state["firma_archivio"] == firma_archivio(conn)
              and data_version == int(conn.execute("PRAGMA data_version").fetchone()[0]))
    if not stable:
        meta.pop("riconvalida_iniziale", None)
        meta["riconvalida_finale_richiesta"] = True
        return False
    meta["riconvalida_finale_richiesta"] = not state["completa"]
    return True

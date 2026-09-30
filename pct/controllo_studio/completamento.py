"""Completamento collettivo esplicito: SQL tenant come fonte operativa."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pct import cache
from pct.scadenziario import StatoTermine


def completa_scadute(database, mirror_path, ids: list[str], *, oggi: date | None = None, attore: str = "") -> dict:
    """Valida l'intero insieme e aggiorna soltanto i record richiesti, atomicamente.

    Il chiamante deve verificare il permesso e la conferma di adempimento.
    SQLite usa BEGIN IMMEDIATE; PostgreSQL blocca le righe nella medesima
    transazione nativa. Una richiesta ripetuta non cambia note o timestamp.
    """
    if not isinstance(ids, list) or not ids or len(ids) > 10000:
        raise ValueError("Selezione non valida. Aggiorna il quadro dello studio.")
    if any(not isinstance(sid, str) or not sid or len(sid) > 128 for sid in ids):
        raise ValueError("Selezione non valida. Aggiorna il quadro dello studio.")
    ids = list(dict.fromkeys(ids))
    if database is None:
        raise RuntimeError("Archivio SQL non disponibile: nessuna scadenza è stata modificata.")
    giorno = oggi or datetime.now(ZoneInfo("Europe/Rome")).date()
    timestamp = datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")
    operazione_id = str(uuid.uuid4())
    modificati: list[str] = []
    dati: dict[str, dict] = {}

    def aggiorna(conn, _selezione):
        modificati.clear()
        dati.clear()
        lock = " FOR UPDATE" if getattr(database, "backend_kind", "") == "postgresql" else ""
        for riga in conn.execute("SELECT * FROM scadenze" + lock).fetchall():
            colonne = dict(riga)
            payload = json.loads(colonne.get("dati_json") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("Archivio scadenze da verificare: nessuna modifica eseguita.")
            payload.update({k: colonne[k] for k in ("id", "stato", "data_scadenza", "note", "completata_il")})
            dati[str(colonne["id"])] = payload
        # Prima si controllano TUTTI gli ID; nessuna scrittura parziale.
        for sid in ids:
            riga = dati.get(sid)
            if riga is None:
                raise ValueError("La selezione è cambiata. Aggiorna il quadro e riprova.")
            if riga["stato"] == StatoTermine.COMPLETATO.value:
                continue
            try:
                scaduta = date.fromisoformat(str(riga["data_scadenza"])[:10]) < giorno
            except ValueError:
                scaduta = False
            if riga["stato"] not in {StatoTermine.APERTO.value, StatoTermine.SCADUTO.value} or not scaduta:
                raise ValueError("Alcune scadenze non sono più aperte e scadute. Aggiorna il quadro e riprova.")
            modificati.append(sid)
        for sid in modificati:
            riga = dati[sid]
            riga.update(stato=StatoTermine.COMPLETATO.value, completata_il=timestamp, completamento_collettivo_id=operazione_id,
                        note=((riga.get("note") or "") + f"\nAdempimento confermato nel completamento collettivo dal Controllo Studio. Operazione {operazione_id}" + (f"; operatore: {attore}" if attore else "") + ".").strip())
            conn.execute("UPDATE scadenze SET stato = ?, completata_il = ?, note = ?, dati_json = ? WHERE id = ?",
                         (riga["stato"], timestamp, riga["note"], json.dumps(riga, ensure_ascii=False), sid))

    database.salva_tabella("scadenze", [ids], aggiorna, delete_all=False)
    mirror_allineato = True
    try:
        cache.save(mirror_path, dati)
    except Exception:
        mirror_allineato = False
        logging.getLogger(__name__).exception("Completamento registrato in SQL; mirror scadenze da riallineare")
    return {"completate": modificati, "gia_completate": len(ids) - len(modificati), "mirror_allineato": mirror_allineato, "operazione_id": operazione_id}

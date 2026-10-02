"""Dati verificati del caso: SQL core del tenant, parità SQLite/PostgreSQL."""
from __future__ import annotations

import hashlib
import json
import uuid
import threading
import weakref
from datetime import datetime, timezone
from pathlib import Path

_PRONTI = weakref.WeakSet()
_SCHEMA_LOCK = threading.RLock()


class VerificaNotificheRepository:
    def __init__(self, database, tenant_id: str):
        if database is None or not tenant_id:
            raise RuntimeError("Archivio SQL dello studio non disponibile.")
        self.database, self.tenant_id = database, tenant_id
        nome = "20260930_notifiche_verifica_postgres.sql" if getattr(database, "backend_kind", "") == "postgresql" else "20260930_notifiche_verifica.sql"
        istruzioni = (Path(__file__).parent / "sql" / nome).read_text(encoding="utf-8")
        def crea(conn, _):
            for istruzione in istruzioni.split(";"):
                if istruzione.strip():
                    conn.execute(istruzione)
        with _SCHEMA_LOCK:
            if database not in _PRONTI:
                database.salva_tabella("notifiche_verifiche", [None], crea, delete_all=False)
                _PRONTI.add(database)

    def elenco(self, fascicolo_id: str) -> dict:
        righe = self.database.conn.execute(
            "SELECT documento_id,dati_json,revisione FROM notifiche_verifiche WHERE tenant_id=? AND fascicolo_id=?",
            (self.tenant_id, fascicolo_id),
        ).fetchall()
        return {r["documento_id"]: {**json.loads(r["dati_json"]), "revisione": r["revisione"]} for r in righe}

    def salva(self, fascicolo_id: str, documento_id: str, dati: dict, *, attore: str, revisione: int) -> int:
        nuovo = revisione + 1
        testo = json.dumps(dati, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        timestamp = datetime.now(timezone.utc).isoformat()
        def scrivi(conn, _):
            if getattr(self.database, "backend_kind", "") == "postgresql":
                chiave = hashlib.sha256((self.tenant_id + ":" + fascicolo_id + ":" + documento_id).encode()).digest()
                conn.execute("SELECT pg_advisory_xact_lock(?)", (int.from_bytes(chiave[:8], "big", signed=True),))
            lock = " FOR UPDATE" if getattr(self.database, "backend_kind", "") == "postgresql" else ""
            attuale = conn.execute("SELECT revisione,dati_json FROM notifiche_verifiche WHERE tenant_id=? AND fascicolo_id=? AND documento_id=?" + lock,
                                   (self.tenant_id, fascicolo_id, documento_id)).fetchone()
            if (int(attuale["revisione"]) if attuale else 0) != revisione:
                raise ValueError("La verifica è stata aggiornata da un altro operatore. Ricarica il pannello.")
            conn.execute("INSERT INTO notifiche_verifiche (tenant_id,fascicolo_id,documento_id,dati_json,revisione,attore,aggiornato_il) VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant_id,fascicolo_id,documento_id) DO UPDATE SET dati_json=excluded.dati_json,revisione=excluded.revisione,attore=excluded.attore,aggiornato_il=excluded.aggiornato_il",
                         (self.tenant_id, fascicolo_id, documento_id, testo, nuovo, attore, timestamp))
            precedente = str(attuale["dati_json"]) if attuale else "{}"
            impronta = hashlib.sha256((self.tenant_id + fascicolo_id + documento_id + precedente + testo + attore + timestamp).encode("utf-8")).hexdigest()
            conn.execute("INSERT INTO notifiche_verifiche_audit (id,tenant_id,fascicolo_id,documento_id,prima_json,dopo_json,attore,registrato_il,impronta) VALUES (?,?,?,?,?,?,?,?,?)",
                         (str(uuid.uuid4()), self.tenant_id, fascicolo_id, documento_id, precedente, testo, attore, timestamp, impronta))
        self.database.salva_tabella("notifiche_verifiche", [None], scrivi, delete_all=False)
        return nuovo

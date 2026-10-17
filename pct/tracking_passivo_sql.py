"""Proposte di lavoro nel database proprietario; nessuna lettura JSON runtime."""
from __future__ import annotations

import json
from datetime import datetime

from pct.timesheet_sql_writer import TimesheetConflict


SCHEMA = """
CREATE TABLE IF NOT EXISTS time_tracking_proposals (
    id TEXT PRIMARY KEY,
    chiave TEXT NOT NULL UNIQUE,
    stato TEXT NOT NULL,
    utente_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    inizio TEXT NOT NULL,
    dati_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tracking_proposals_queue
ON time_tracking_proposals(stato,utente_id,inizio);
"""


def decode(row):
    if row is None:
        return None
    value = json.loads(row["dati_json"])
    if not isinstance(value, dict) or any(value.get(k) != row[k] for k in
            ("id", "chiave", "stato", "utente_id", "fascicolo_id", "inizio")):
        raise ValueError("Proposta Timesheet discordante dalla fonte SQL: verifica necessaria.")
    return value


class TrackingPassivoSQL:
    def __init__(self, database):
        self.database = database

    def recent_events(self, since, until, *, batch_size=500):
        """Audit SQL nella finestra richiesta, senza caricare lo storico utenti."""
        from pct.auth import EventoAudit
        cursor_time, cursor_id = since, ''
        size = max(1, min(int(batch_size), 1000))
        while True:
            rows = self.database.fetchall_readonly(
                "SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito "
                "FROM audit_log WHERE risorsa_tipo='fascicolo' AND esito='OK' AND timestamp>=? AND timestamp<=? "
                "AND (timestamp>? OR (timestamp=? AND id>?)) ORDER BY timestamp,id LIMIT ?",
                (since, until, cursor_time, cursor_time, cursor_id, size))
            for row in rows:
                yield EventoAudit.from_dict(dict(row))
            if len(rows) < size:
                return
            cursor_time, cursor_id = rows[-1]['timestamp'], rows[-1]['id']

    def get(self, key):
        rows = self.database.fetchall_readonly("SELECT * FROM time_tracking_proposals WHERE id=?", (key,))
        return decode(rows[0]) if rows else None

    def bozze(self, *, utente_id="", limit=50):
        size = max(1, min(int(limit), 500))
        sql = "SELECT * FROM time_tracking_proposals WHERE stato='BOZZA'"
        params = []
        if utente_id:
            sql += " AND utente_id=?"
            params.append(utente_id)
        return [decode(row) for row in self.database.fetchall_readonly(
            sql + " ORDER BY inizio DESC,id LIMIT ?", (*params, size))]

    def insert(self, proposals):
        added = {}
        def write(conn, batch):
            # Un retry del repository riparte dopo il rollback del tentativo.
            added.clear()
            for proposal in batch:
                row = conn.execute(
                    "INSERT INTO time_tracking_proposals (id,chiave,stato,utente_id,fascicolo_id,inizio,dati_json) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT(chiave) DO NOTHING RETURNING id",
                    tuple(proposal[k] for k in ("id", "chiave", "stato", "utente_id", "fascicolo_id", "inizio"))
                    + (json.dumps(proposal, ensure_ascii=False),)).fetchone()
                if row:
                    added[proposal["id"]] = proposal
        if proposals:
            self.database.salva_tabella("time_tracking_proposals", [proposals], write, delete_all=False)
        return list(added.values())

    def transition(self, key, *, actor_id, timesheet=None, create=None, minutes=None, description="", reason="", owner_id=None):
        if not actor_id:
            raise PermissionError("Utente della proposta non identificato.")
        if create is not None and (timesheet is None or timesheet._studio_db is not self.database):
            raise ValueError("Proposta e voce devono appartenere allo stesso studio SQL.")
        owner_id = owner_id or actor_id
        result = {}
        def write(conn, _):
            if create is not None:
                bind(self.database, conn)
            lock = " FOR UPDATE" if getattr(self.database, "raw_conn", None) is not None else ""
            proposal = decode(conn.execute(
                "SELECT * FROM time_tracking_proposals WHERE id=? AND utente_id=?" + lock,
                (key, owner_id)).fetchone())
            if proposal is None:
                raise KeyError("Proposta non trovata per l’utente corrente.")
            target = "CONFERMATA" if create is not None else "SCARTATA"
            if proposal["stato"] != "BOZZA":
                if proposal["stato"] != target:
                    raise TimesheetConflict("Proposta già definita: nessuna modifica registrata.")
                if create is not None:
                    if minutes is not None and int(minutes) != proposal["minuti"]:
                        raise TimesheetConflict("Proposta già confermata con una durata differente.")
                    if description.strip() and description.strip() != proposal.get("descrizione_confermata"):
                        raise TimesheetConflict("Proposta già confermata con una descrizione differente.")
                    linked = conn.execute("SELECT id FROM timesheet_entries WHERE id=?",
                                          (proposal.get("voce_timesheet_id"),)).fetchone()
                    if linked is None:
                        raise TimesheetConflict("Voce confermata non reperibile: verifica necessaria, nessun duplicato creato.")
                result.clear()
                result.update(proposal, gia_presente=True)
                return
            if create is not None:
                duration = int(minutes if minutes is not None else proposal["minuti"])
                if duration <= 0:
                    raise ValueError("La durata deve essere positiva.")
                text = description.strip() or proposal["descrizione"]
                entry = create({"id_fascicolo": proposal["fascicolo_id"], "id_utente": owner_id,
                    "username": proposal.get("username", ""), "data_attivita": proposal["inizio"][:10],
                    "minuti": duration, "descrizione": text, "origine": "tracking_passivo",
                    "note": f"Proposta automatica {key} confermata dall'avvocato."})
                entry_id = entry.get("id") if isinstance(entry, dict) else getattr(entry, "id", None)
                persisted = conn.execute("SELECT id_utente,id_fascicolo,origine,minuti,descrizione FROM timesheet_entries WHERE id=?",
                                         (entry_id,)).fetchone()
                if persisted is None or tuple(persisted[k] for k in
                        ("id_utente", "id_fascicolo", "origine", "minuti", "descrizione")) != (
                            owner_id, proposal["fascicolo_id"], "tracking_passivo", duration, text):
                    raise ValueError("La voce Timesheet non dimostra la conferma della proposta.")
                proposal.update(minuti=duration, descrizione_confermata=text, voce_timesheet_id=entry_id)
            else:
                proposal["motivo_scarto"] = reason.strip()
            proposal.update(stato=target, definito_da=actor_id, definito_il=datetime.now().isoformat(timespec="seconds"))
            conn.execute("UPDATE time_tracking_proposals SET stato=?,dati_json=? WHERE id=?",
                         (target, json.dumps(proposal, ensure_ascii=False), key))
            result.clear()
            result.update(proposal, gia_presente=False)
        if create is not None:
            with timesheet.transazione_condivisa() as bind:
                self.database.salva_tabella("time_tracking_proposals", [key], write, delete_all=False)
        else:
            self.database.salva_tabella("time_tracking_proposals", [key], write, delete_all=False)
        return result

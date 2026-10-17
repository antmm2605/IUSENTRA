"""Scritture puntuali del Timesheet sul database proprietario già risolto."""
from __future__ import annotations

import json

COLUMNS = ("id", "id_fascicolo", "id_cliente", "id_utente", "username", "data_attivita",
           "descrizione", "minuti", "valore_unitario", "fatturabile", "stato", "origine",
           "creato_il", "modificato_il", "dati_json")


class TimesheetConflict(RuntimeError):
    """Una voce concorrente non può essere sovrascritta da uno snapshot vecchio."""


def encode_model(entry):
    return json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def row_values(entry):
    return (entry.id, entry.id_fascicolo or None, entry.id_cliente or None,
            entry.id_utente or None, entry.username, entry.data_attivita,
            entry.descrizione, int(entry.minuti or 0), float(entry.valore_unitario or 0),
            int(entry.fatturabile), entry.stato.value, entry.origine, entry.creato_il,
            entry.modificato_il, json.dumps(entry.to_dict(), ensure_ascii=False))


def save_changes(database, *, original_rows, original_models, current):
    encoded = {key: encode_model(value) for key, value in current.items()}
    changed = sorted(key for key in original_models.keys() | encoded.keys()
                     if original_models.get(key) != encoded.get(key))
    if not changed:
        return {}

    confirmed = {}

    def write(conn, key):
        before, after = original_rows.get(key), current.get(key)
        if after is None:
            raise TimesheetConflict("Eliminazione Timesheet non prevista: nessuna modifica registrata.")
        identity_changed = before is None or any((before[name] or "") != (getattr(after, name) or "") for name in ("id_fascicolo", "id_cliente"))
        if identity_changed:
            # I collegamenti restano stabili fino al commit anche su PostgreSQL.
            lock = " FOR SHARE" if getattr(database, "raw_conn", None) is not None else ""
            if after.id_cliente and conn.execute("SELECT id FROM clienti WHERE id=?" + lock, (after.id_cliente,)).fetchone() is None:
                raise ValueError("Cliente Timesheet non presente nello studio: nessuna associazione registrata.")
            if after.id_fascicolo:
                case = conn.execute("SELECT id_cliente FROM fascicoli WHERE id=?" + lock, (after.id_fascicolo,)).fetchone()
                if case is None:
                    raise ValueError("Fascicolo Timesheet non presente nello studio: nessuna associazione registrata.")
                if after.id_cliente and (case[0] or "") != after.id_cliente:
                    raise ValueError("Cliente e fascicolo Timesheet discordanti: nessuna associazione registrata.")
        if before is None:
            updated = conn.execute(
                f"INSERT INTO timesheet_entries ({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)}) "
                "ON CONFLICT(id) DO NOTHING RETURNING id", row_values(after)).fetchone()
        else:
            condition = " AND ".join(f"({name}=? OR ({name} IS NULL AND ? IS NULL))" for name in COLUMNS)
            expected = tuple(value for name in COLUMNS for value in (before[name], before[name]))
            updated = conn.execute(
                f"UPDATE timesheet_entries SET {','.join(name+'=?' for name in COLUMNS[1:])} "
                f"WHERE {condition} RETURNING id", row_values(after)[1:] + expected).fetchone()
        if updated is None:
            raise TimesheetConflict("Voce Timesheet aggiornata da un altro processo: ricarica i dati prima di riprovare; la modifica non è stata registrata.")

        confirmed[key] = dict(conn.execute("SELECT * FROM timesheet_entries WHERE id=?", (key,)).fetchone())

    database.salva_tabella("timesheet_entries", changed, write, delete_all=False)
    return confirmed

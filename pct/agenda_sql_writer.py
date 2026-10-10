"""Scrittura puntuale del motore nativo: nessuna sostituzione dell’Agenda.

Il runtime risolve già il database proprietario del tenant. La transazione e
il retry restano quelli di StudioDB; ogni riga cambiata richiede lo snapshot
SQL originale, anche nelle colonne non contenute nel JSON del modello.
"""
from __future__ import annotations

import json

COLUMNS = ("id", "tipo", "stato", "titolo", "data_ora", "durata_minuti", "luogo",
           "descrizione", "cliente", "cf_cliente", "procedimento", "tribunale",
           "note", "creato_il", "dati_json")


class AgendaConflict(RuntimeError):
    """Uno snapshot superato non può cancellare o sovrascrivere dati SQL."""


def encode_model(appuntamento):
    return json.dumps(appuntamento.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def row_values(appuntamento):
    a = appuntamento
    return (a.id, a.tipo.value, a.stato.value, a.titolo, a.data_ora,
            a.durata_minuti, a.luogo, a.note, a.cliente, a.cf_cliente,
            a.procedimento, a.tribunale, a.note, a.creato_il,
            json.dumps(a.to_dict(), ensure_ascii=False))


def write_changes(conn, *, original_rows, original_models, current):
    """Partecipa alla transazione del chiamante, senza commit o rollback propri."""
    encoded = {key: encode_model(value) for key, value in current.items()}
    changed = sorted(key for key in set(original_models) | set(encoded) if original_models.get(key) != encoded.get(key))
    if not changed:
        return 0

    def write(conn, key):
        before = original_rows.get(key)
        after = current.get(key)
        if before is None:
            if after is None:
                raise AgendaConflict("Fonte dell’appuntamento mancante: nessuna modifica registrata.")
            inserted = conn.execute(f"INSERT INTO appuntamenti ({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)}) "
                                    "ON CONFLICT(id) DO NOTHING RETURNING id", row_values(after)).fetchone()
            if inserted is None:
                raise AgendaConflict("L’appuntamento è già presente: nessuna copia o sovrascrittura registrata.")
            return
        # Confronto null-safe e portabile: SQL e JSON devono essere entrambi invariati.
        condition = " AND ".join(f"({name}=? OR ({name} IS NULL AND ? IS NULL))" for name in COLUMNS)
        expected = tuple(value for name in COLUMNS for value in (before[name], before[name]))
        if after is None:
            updated = conn.execute(f"DELETE FROM appuntamenti WHERE {condition} RETURNING id", expected).fetchone()
        else:
            values = row_values(after)
            updated = conn.execute(f"UPDATE appuntamenti SET {','.join(name+'=?' for name in COLUMNS[1:])} "
                                   f"WHERE {condition} RETURNING id", values[1:] + expected).fetchone()
        if updated is None:
            raise AgendaConflict("Appuntamento aggiornato da un altro processo: modifiche non registrate.")

    for key in changed:
        write(conn, key)
    return len(changed)


def save_changes(database, *, original_rows, original_models, current):
    """Percorso nativo autonomo; usa le stesse regole del chiamante composto."""
    def write(conn, _):
        write_changes(conn, original_rows=original_rows, original_models=original_models, current=current)
    if all(original_models.get(key) == encode_model(value) for key, value in current.items()) and original_models.keys() == current.keys():
        return
    database.salva_tabella("appuntamenti", [None], write, delete_all=False)

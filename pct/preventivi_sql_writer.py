"""Scritture puntuali di preventivi e incarichi sul repository SQL proprietario."""

from __future__ import annotations

import json

PREVENTIVI_COLUMNS = (
    "preventivo_id",
    "numero",
    "id_cliente",
    "id_fascicolo",
    "data_emissione",
    "data_scadenza",
    "oggetto",
    "stato",
    "workflow_channel",
    "tipo_compenso",
    "tipo_procedimento",
    "area_pratica",
    "id_pratica",
    "procedura_operativa_codice",
    "procedura_operativa_nome",
    "canale_operativo",
    "registro_operativo",
    "classificazioni_tassonomiche_json",
    "criterio_arrotondamento_orario",
    "minuti_stimati",
    "ore_fatturabili_calcolate",
    "compenso_orario_base",
    "massimale_ore",
    "soglia_preapprovazione_ore",
    "warning_compenso_orario_json",
    "totale",
    "accettato_il",
    "id_preventivo_precedente",
    "token_portale",
    "creato_il",
    "profilo_deposito_json",
    "dati_json",
)


def preventivi_values(preventivo):
    payload = preventivo.to_dict()
    return (
        preventivo.id,
        preventivo.numero,
        preventivo.id_cliente,
        preventivo.id_fascicolo or None,
        preventivo.data_emissione,
        preventivo.data_scadenza or "",
        preventivo.oggetto,
        preventivo.stato.value,
        preventivo.workflow_channel,
        preventivo.tipo_compenso,
        preventivo.tipo_procedimento,
        preventivo.area_pratica,
        preventivo.id_pratica,
        preventivo.procedura_operativa_codice,
        preventivo.procedura_operativa_nome,
        preventivo.canale_operativo,
        preventivo.registro_operativo,
        json.dumps(preventivo.classificazioni_tassonomiche or [], ensure_ascii=False),
        preventivo.criterio_arrotondamento_orario or "",
        int(preventivo.minuti_stimati or 0),
        float(preventivo.ore_fatturabili_calcolate or 0.0),
        float(preventivo.compenso_orario_base or 0.0),
        float(preventivo.massimale_ore or 0.0),
        float(preventivo.soglia_preapprovazione_ore or 0.0),
        json.dumps(preventivo.warning_compenso_orario or [], ensure_ascii=False),
        float(preventivo.totale or 0.0),
        preventivo.accettato_il or "",
        preventivo.id_preventivo_precedente or "",
        preventivo.token_portale or "",
        preventivo.creato_il,
        json.dumps(preventivo.profilo_deposito or {}, ensure_ascii=False),
        json.dumps(payload, ensure_ascii=False),
    )


CONFERIMENTI_COLUMNS = (
    "conferimento_id",
    "numero",
    "id_preventivo",
    "id_cliente",
    "id_fascicolo",
    "data_incarico",
    "oggetto",
    "stato",
    "workflow_channel",
    "tipo_compenso",
    "tipo_procedimento",
    "area_pratica",
    "id_pratica",
    "procedura_operativa_codice",
    "procedura_operativa_nome",
    "canale_operativo",
    "registro_operativo",
    "classificazioni_tassonomiche_json",
    "criterio_arrotondamento_orario",
    "massimale_ore",
    "soglia_preapprovazione_ore",
    "warning_compenso_orario_json",
    "compenso_pattuito",
    "firma_cliente_eseguita",
    "fascicolo_aperto_il",
    "profilo_deposito_json",
    "dati_json",
)


def conferimenti_values(conferimento):
    payload = conferimento.to_dict()
    return (
        conferimento.id,
        conferimento.numero,
        conferimento.id_preventivo or "",
        conferimento.id_cliente,
        conferimento.id_fascicolo or None,
        conferimento.data_incarico,
        conferimento.oggetto,
        conferimento.stato.value,
        conferimento.workflow_channel,
        conferimento.tipo_compenso,
        conferimento.tipo_procedimento,
        conferimento.area_pratica,
        conferimento.id_pratica,
        conferimento.procedura_operativa_codice,
        conferimento.procedura_operativa_nome,
        conferimento.canale_operativo,
        conferimento.registro_operativo,
        json.dumps(conferimento.classificazioni_tassonomiche or [], ensure_ascii=False),
        conferimento.criterio_arrotondamento_orario or "",
        float(conferimento.massimale_ore or 0.0),
        float(conferimento.soglia_preapprovazione_ore or 0.0),
        json.dumps(conferimento.warning_compenso_orario or [], ensure_ascii=False),
        float(conferimento.compenso_pattuito or 0.0),
        1 if conferimento.firma_cliente_eseguita else 0,
        conferimento.fascicolo_aperto_il or "",
        json.dumps(conferimento.profilo_deposito or {}, ensure_ascii=False),
        json.dumps(payload, ensure_ascii=False),
    )


class PreventiviConflict(RuntimeError):
    """Snapshot concorrente: nessuna sovrascrittura silenziosa."""


def encode_model(item):
    return json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_rows(database, table):
    if table not in ("preventivi_records", "conferimenti_records"):
        raise ValueError("Archivio preventivi non consentito.")
    return [dict(row) for row in database.fetchall_readonly(f"SELECT * FROM {table}")]


def decode_row(row, model, key):
    payload = json.loads(row["dati_json"])
    if not isinstance(payload, dict) or payload.get("id") != row[key]:
        raise ValueError("Identità SQL e contenuto del preventivo discordanti: verifica la fonte.")
    item = model.from_dict(payload)
    item._sql_discordanze = [
        name
        for name in ("id_cliente", "id_fascicolo", "numero", "stato")
        if (payload.get(name) or "") != (row[name] or "")
    ]
    return item


def save_changes(database, table, original_rows, original_models, current):
    if table not in ("preventivi_records", "conferimenti_records"):
        raise ValueError("Archivio preventivi non consentito.")
    columns, values = (
        (PREVENTIVI_COLUMNS, preventivi_values)
        if table == "preventivi_records"
        else (CONFERIMENTI_COLUMNS, conferimenti_values)
    )
    key_column = columns[0]
    encoded = {key: encode_model(item) for key, item in current.items()}
    changed = sorted(
        key for key in original_models.keys() | encoded.keys() if original_models.get(key) != encoded.get(key)
    )
    if not changed:
        return {}
    confirmed = {}

    def write(conn, key):
        before, after = original_rows.get(key), current.get(key)
        if after is not None and after.id != key:
            raise ValueError("Identificativo preventivo o incarico non modificabile.")
        if before is None:
            if getattr(database, "raw_conn", None) is not None:
                conn.execute(
                    "SELECT pg_advisory_xact_lock(?)", (778215601 if table == "preventivi_records" else 778215602,)
                )
            prefix = str(after.numero).split("/", 1)[0] + "/"
            rows = conn.execute(f"SELECT numero FROM {table} WHERE numero LIKE ?", (prefix + "%",)).fetchall()
            numbers = [int(row[0][len(prefix) :]) for row in rows if row[0][len(prefix) :].isdigit()]
            after.numero = f"{prefix}{max(numbers, default=0) + 1:03d}"
            updated = conn.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT({key_column}) DO NOTHING RETURNING {key_column}",
                values(after),
            ).fetchone()
        else:
            condition = " AND ".join(f"({name}=? OR ({name} IS NULL AND ? IS NULL))" for name in columns)
            expected = tuple(value for name in columns for value in (before[name], before[name]))
            if after is None:
                updated = conn.execute(
                    f"DELETE FROM {table} WHERE {condition} RETURNING {key_column}", expected
                ).fetchone()
            else:
                data = list(values(after))
                # Metadati storici non modellati conservati nella stessa riga SQL.
                payload = json.loads(before["dati_json"])
                before_payload = dict(payload)
                after_payload = after.to_dict()
                # Non trasformare metadati storici discordanti in nuove associazioni.
                for index, name in enumerate(columns):
                    if name in after_payload and after_payload.get(name) == before_payload.get(name):
                        data[index] = before[name]
                payload.update(after_payload)
                data[-1] = json.dumps(payload, ensure_ascii=False)
                updated = conn.execute(
                    f"UPDATE {table} SET {','.join(name + '=?' for name in columns[1:])} WHERE {condition} RETURNING {key_column}",
                    tuple(data[1:]) + expected,
                ).fetchone()
        if updated is None:
            raise PreventiviConflict(
                "Preventivo o incarico modificato da un'altra sessione: ricarica i dati. Nessuna modifica registrata."
            )
        confirmed[key] = (
            dict(conn.execute(f"SELECT * FROM {table} WHERE {key_column}=?", (key,)).fetchone())
            if after is not None
            else None
        )

    database.salva_tabella(table, changed, write, delete_all=False)
    return confirmed

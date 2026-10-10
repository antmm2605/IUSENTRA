"""Consegna CTU nella transazione proprietaria: regole e modelli nativi."""
from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5

from pct.ctu import IncaricoCtu, proposte_scadenze_incarico
from pct.scadenziario import Scadenza, StatoTermine, TipoTermine
from pct.scadenziario_sql_writer import COLUMNS, encode_model, write_changes


def deliver_deadlines(conn, record, *, tenant, actor):
    if not tenant or not actor:
        raise ValueError("Studio o operatore della consegna CTU assente.")
    incarico = IncaricoCtu.from_dict(record)
    cursor = conn.execute(f"SELECT {','.join(COLUMNS)} FROM scadenze WHERE id_fascicolo=?", (incarico.fascicolo_id,))
    rows = cursor.fetchall()
    originals, models, current = {}, {}, {}
    for row in rows:
        raw = dict(row) if hasattr(row, "keys") else dict(zip(COLUMNS, row, strict=True))
        if not raw.get("dati_json"):
            raise ValueError("Scadenza senza payload governato: recupero necessario prima della consegna CTU.")
        item = Scadenza.from_dict(json.loads(raw["dati_json"]))
        if item.id != raw["id"] or item.id_fascicolo != incarico.fascicolo_id:
            raise ValueError("Identità della scadenza SQL discordante: consegna CTU annullata.")
        if any(raw.get(key) != expected for key, expected in {
            "tipo": item.tipo.value, "stato": item.stato.value,
            "data_scadenza": item.data_scadenza, "note": item.note,
        }.items()):
            raise ValueError("Scadenza SQL e contenuto discordanti: nessuna decisione precedente sovrascritta.")
        originals[item.id], models[item.id], current[item.id] = raw, encode_model(item), item
    results = []
    for proposta in proposte_scadenze_incarico(incarico):
        marker = proposta["chiave"]
        matches = [item for item in current.values() if marker in {line.strip() for line in item.note.splitlines()}]
        if len(matches) > 1:
            raise ValueError("Più scadenze per la stessa tappa CTU: verifica necessaria, nessuna nuova copia registrata.")
        if matches:
            item = matches[0]
            if item.tipo != TipoTermine.ADEMPIMENTO:
                raise ValueError("Natura della scadenza CTU discordante: nessuna modifica registrata.")
            if item.data_scadenza == proposta["data_scadenza"]:
                status = "already_present"
            elif item.stato != StatoTermine.BOZZA:
                status = "manual_preserved"
            else:
                item.data_scadenza = proposta["data_scadenza"]
                item.sync_date_fields()
                item.aggiorna_priorita()
                status = "updated"
        else:
            identifier = str(uuid5(NAMESPACE_URL, json.dumps(["ctu-deadline", tenant, incarico.id, marker], ensure_ascii=False)))
            item = Scadenza(id=identifier, titolo=proposta["titolo"], tipo=TipoTermine.ADEMPIMENTO,
                data_scadenza=proposta["data_scadenza"], id_fascicolo=incarico.fascicolo_id,
                descrizione=proposta["fonte"], note=f"{marker}\nFonte: {proposta['fonte']}",
                id_utente_responsabile=actor, stato=StatoTermine.BOZZA)
            item.sync_date_fields()
            item.aggiorna_priorita()
            current[item.id] = item
            status = "created"
        results.append({"key": marker, "id": item.id, "status": status,
                        "date": item.data_scadenza, "proposedDate": proposta["data_scadenza"]})
    write_changes(conn, original_rows=originals, original_models=models, current=current)
    return {"kind": "deadlines", "items": results,
            "created": sum(item["status"] == "created" for item in results),
            "updated": sum(item["status"] == "updated" for item in results)}

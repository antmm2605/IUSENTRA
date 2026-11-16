"""Collegamenti delle azioni alle proiezioni SQL riunite e verificate."""
from __future__ import annotations
import json
from urllib.parse import quote
from pct.eventi_unici_repository import EventiUniciRepository


def collegamento_scadenza(database, tenant_id, fascicolo_id, azione):
    """La stessa prova canonica, non il solo giorno, individua la scadenza."""
    if database is None or not tenant_id or not fascicolo_id or not azione.get('fattoId'):
        return ''
    repo=EventiUniciRepository(database,tenant_id)
    if not repo.presente():
        return ''
    rows=database.conn.execute('SELECT origine_id,evidenza_json FROM eventi_unici_correlazioni WHERE tenant_id=? AND fascicolo_id=? AND area=?',
                               (tenant_id,fascicolo_id,'scadenze')).fetchall()
    verified=set()
    for row in rows:
        evidence=json.loads(row['evidenza_json'])
        if azione['fattoId'] not in {evidence.get('canonico_fatto_id'),evidence.get('fatto_id')}:
            continue
        _,payload=repo.risolvi_verificato('scadenze',row['origine_id'],fascicolo_id=fascicolo_id)
        verified.add(payload['id'])
    if len(verified)>1:
        raise ValueError('La stessa prova risulta collegata a più scadenze: verifica necessaria.')
    return '/scadenziario?focus='+quote(next(iter(verified)),safe='') if verified else ''


def collegamenti_adempimenti_pec(database, fascicolo_id, azioni, fonte_per_azione):
    """Riusa note e appuntamenti già registrati per la stessa comunicazione."""
    from pct.agenda import StatoAppuntamento
    from pct.calendar_sql_records import appointment_candidates_for_case, deadlines_for_case
    from pct.note_127_ter.proposta import CODICE_NOTE_127_TER
    from pct.scadenziario import StatoTermine

    note = [a for a in azioni if a.get("type") == "note_127_ter" and fonte_per_azione.get(a["id"])]
    udienze = [a for a in azioni if a.get("type") == "udienza_documento" and fonte_per_azione.get(a["id"])]
    if database is None or not fascicolo_id or not (note or udienze):
        return {}
    collegamenti = {}
    if note:
        scadenze = [
            voce for voce in deadlines_for_case(database, fascicolo_id)
            if voce.deadline_profile_code == CODICE_NOTE_127_TER and voce.stato != StatoTermine.ANNULLATO
        ]
        for azione in note:
            matching = [voce for voce in scadenze
                        if voce.source_message_id == fonte_per_azione[azione["id"]]
                        and voce.data_scadenza[:10] == azione["dateIso"]]
            if len(matching) == 1:
                collegamenti[azione["id"]] = "/scadenziario?focus=" + quote(matching[0].id, safe="")
    if udienze:
        appuntamenti = [voce for voce in appointment_candidates_for_case(database, fascicolo_id)
                       if voce.id_fascicolo == fascicolo_id and voce.stato != StatoAppuntamento.ANNULLATO]
        for azione in udienze:
            prefisso = f"PEC_AUDIT:{fonte_per_azione[azione['id']]}:"
            quando = azione["dateIso"] + ("T" + azione["time"] if azione.get("time") else "")
            matching = [voce for voce in appuntamenti if str(voce.external_uid or "").startswith(prefisso)
                        and str(voce.data_ora or "").startswith(quando)]
            if len(matching) == 1:
                collegamenti[azione["id"]] = "/agenda/" + quote(matching[0].id, safe="") + "/modifica"
    return collegamenti

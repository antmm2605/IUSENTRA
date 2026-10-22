"""Ricostruzione nativa delle singole righe SQL di Agenda e Scadenziario.

Nessun caricamento di gestori, mirror o archivi. Mantiene le precedenze già
usate dalle procedure ordinarie, anche per i record storici.
"""
import json


def updated_payload(row, original_model, current_model):
    """Conserva estensioni non modificate dopo il confronto SQL dello snapshot.

    I campi nativi mancanti ricevono gli stessi valori del writer precedente;
    una variazione del modello non cancella i dati storici estranei ad essa.
    Non è una fusione di due scritture concorrenti.
    """
    from pct.json_snapshot_delta import merge_delta
    encoded = row.get('dati_json')
    if not encoded:
        return current_model
    source = json.loads(encoded)
    if not isinstance(source, dict) or not isinstance(original_model, dict) or not isinstance(current_model, dict):
        raise ValueError('Snapshot JSON del calendario non valido: nessuna modifica registrata.')
    return {**current_model, **merge_delta(source, original_model, current_model)}


def appointment_from_row(row):
    from pct.agenda import Appuntamento

    payload = dict(row)
    data = {key: value for key, value in payload.items() if key in Appuntamento.__dataclass_fields__}
    if payload.get('dati_json'):
        data.update(json.loads(payload['dati_json']))
    value = Appuntamento.from_dict(data)
    if value.id != str(payload['id']):
        raise RuntimeError('Identità dell’appuntamento SQL discordante: recupero necessario.')
    return value


def deadline_from_row(row):
    from pct.scadenziario import Scadenza

    payload = dict(row)
    encoded = payload.get('dati_json')
    data = json.loads(encoded) if encoded else payload
    if not encoded:
        data['giorni_preavviso'] = json.loads(payload.get('giorni_preavviso') or '[]')
        data['avvisi_inviati'] = json.loads(payload.get('avvisi_inviati') or '[]')
    value = Scadenza.from_dict(data)
    if value.id != str(payload['id']):
        raise ValueError('Identità della scadenza SQL discordante.')
    return value

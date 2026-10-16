import json

from pct.calendar_query_projection import projected_fields


def appointment(**changes):
    return dict(id='controlled', tipo='CONSULTAZIONE', stato='PROGRAMMATO', titolo='Controllo',
                data_ora='2026-10-13T22:30:00Z', durata_minuti=30, luogo='Studio', **changes)


def test_agenda_giorno_italiano_e_precedenza_modello():
    row = appointment(dati_json=json.dumps({'stato': 'COMPLETATO'}))
    result = projected_fields('agenda', row)
    assert result['event_day'] == '2026-10-14'
    assert result['status'] == 'COMPLETATO'
    assert result['sort_key'] == '2026-10-13T22:30:00.000000+00:00'
    row['dati_json'] = json.dumps({'stato': 'ANNULLATO'})
    assert projected_fields('agenda', row)['source_revision'] != result['source_revision']


def test_scadenza_usa_giorno_legale_non_data_aggiornamento_o_presidio_oggi():
    row = {'id': 'controlled', 'dati_json': json.dumps({'id': 'controlled', 'titolo': 'Termine',
        'legal_due_at': '2026-10-14T22:30:00Z', 'stato': 'APERTO', 'source_event_type': 'legal_notification_presidio'})}
    result = projected_fields('deadlines', row)
    assert result['event_day'] == '2026-10-14'
    assert result['status'] == 'APERTO'


def test_fonte_discordante_e_data_assente_restano_esplicite():
    broken = projected_fields('agenda', appointment(dati_json='{"id":"other"}'))
    assert broken['issue'] == 'native_record_not_readable'
    assert broken['event_day'] == broken['status'] == ''
    missing = projected_fields('deadlines', {'id': 'controlled', 'dati_json': '{"id":"controlled"}'})
    assert missing['issue'] == 'date_not_available'
    assert missing['event_day'] == ''


def test_ora_ripetuta_al_cambio_legale_conserva_i_due_istanti():
    first, second = appointment(), appointment()
    first['data_ora'], second['data_ora'] = '2026-10-25T00:30:00Z', '2026-10-25T01:30:00Z'
    a, b = projected_fields('agenda', first), projected_fields('agenda', second)
    assert a['event_day'] == b['event_day'] == '2026-10-25'
    assert a['sort_key'] < b['sort_key']

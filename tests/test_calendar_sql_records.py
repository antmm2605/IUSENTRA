import json

import pytest

from pct.calendar_sql_records import appointment_from_row, deadline_from_row


def test_agenda_riusa_precedenza_json_con_colonne_storiche_integrative():
    row = {'id': 'one', 'titolo': 'Titolo SQL', 'tipo': 'CONSULTAZIONE', 'stato': 'PROGRAMMATO',
           'data_ora': '2026-10-13T12:00:00', 'durata_minuti': 30, 'luogo': 'Studio',
           'dati_json': json.dumps({'id': 'one', 'titolo': 'Titolo governato', 'data_ora': '2026-10-13T22:30:00Z'})}
    value = appointment_from_row(row)
    assert value.titolo == 'Titolo governato'
    assert value.data_ora_dt.isoformat() == '2026-10-14T00:30:00'
    assert row['data_ora'] == '2026-10-13T12:00:00'


def test_scadenza_colonne_legacy_non_mutano_snapshot_per_salvataggio_ottimistico():
    row = {'id': 'one', 'titolo': 'Termine controllato', 'data_scadenza': '2026-10-14',
           'tipo': 'ALTRO', 'stato': 'APERTO', 'priorita': 'MEDIA', 'dati_json': '',
           'giorni_preavviso': '[7,3,1]', 'avvisi_inviati': '[]'}
    value = deadline_from_row(row)
    assert value.data_scadenza_obj.isoformat() == '2026-10-14'
    assert value.giorni_preavviso == [7, 3, 1]
    assert row['giorni_preavviso'] == '[7,3,1]'
    assert row['avvisi_inviati'] == '[]'


def test_scadenza_usa_data_legale_nativa_quando_data_scadenza_assente():
    value = deadline_from_row({'id': 'one', 'dati_json': json.dumps({
        'id': 'one', 'titolo': 'Termine', 'legal_due_at': '2026-10-14T12:00:00+02:00', 'stato': 'COMPLETATO'})})
    assert value.data_scadenza_obj.isoformat() == '2026-10-14'
    assert value.stato.value == 'COMPLETATO'


@pytest.mark.parametrize('reader', [appointment_from_row, deadline_from_row])
def test_identita_discordante_non_produce_oggetti_attribuiti(reader):
    with pytest.raises((ValueError, RuntimeError, TypeError, KeyError)):
        reader({'id': 'one', 'dati_json': json.dumps({'id': 'other'})})

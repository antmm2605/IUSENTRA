import json

import pytest

from pct.pec_deposit_query_projection import projected_receipt
from pct.pec_pipeline import _pct_deposit_state_from_lifecycle, sha256_json


def source(stage='accettazione_deposito', final='accepted'):
    report = {'deposit_lifecycle': {'current_stage': {'id': stage}, 'final_state': final,
        'history_event': {'stage': stage, 'occurred_at': '2026-10-13T22:30:00Z'},
        'correlation': {'key': 'controlled-deposit', 'manual_review': False}}}
    return dict(id='controlled-report', message_id='controlled-message', report_json=json.dumps(report),
                report_sha256=sha256_json(report), linked_fascicolo_id='', mime_sha256='a' * 64)


def test_accettazioni_distinte_senza_inventare_associazione_fascicolo():
    receipt = projected_receipt(source())
    assert receipt['state'] == 'ACCETTATO_CANCELLERIA'
    assert receipt['event_at'] == '2026-10-13T22:30:00.000000+00:00'
    assert receipt['case_id'] == ''
    assert projected_receipt(source('accettazione_pec', ''))['state'] == 'ACCETTATO_PEC'
    assert projected_receipt(source('intervento_cancelleria', 'awaiting_clerk_confirmation'))['state'] == ''


def test_impronta_e_fase_discordanti_non_producono_accettazione():
    row = source()
    row['report_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='Impronta'):
        projected_receipt(row)
    row = source()
    report = json.loads(row['report_json'])
    report['deposit_lifecycle']['history_event']['stage'] = 'accettazione_pec'
    row.update(report_json=json.dumps(report), report_sha256=sha256_json(report))
    with pytest.raises(ValueError, match='discordanti'):
        projected_receipt(row)


def test_data_importazione_non_sostituisce_data_evento_mancante():
    row = source()
    report = json.loads(row['report_json'])
    report['deposit_lifecycle']['history_event']['occurred_at'] = ''
    row.update(report_json=json.dumps(report), report_sha256=sha256_json(report), created_at='2026-10-16T12:00:00Z')
    result = projected_receipt(row)
    assert result['event_at'] == ''
    assert result['issue'] == 'event_date_not_available'


def test_collegamento_legacy_non_diventa_identita_confermata():
    row = source()
    row.update(linked_fascicolo_id='controlled-case', case_link_status='auto_linked')
    result = projected_receipt(row)
    assert not result['case_link_confirmed']
    assert result['case_id'] == ''
    assert result['candidate_case_id'] == 'controlled-case'
    row['case_link_status'] = 'ricevuta_identificativi_verificati'
    assert projected_receipt(row)['case_id'] == 'controlled-case'


@pytest.mark.parametrize(
    "stage, final, accepted",
    [
        ("consegna_pec", "consegna_pec", False),
        ("intervento_cancelleria", "awaiting_clerk_confirmation", False),
        ("intervento_cancelleria", "intervento_cancelleria", False),
        ("intervento_cancelleria", "accepted_manually", True),
        ("accettazione_deposito", "accepted", True),
        ("accettazione_deposito", "technical_error", False),
        ("rifiuto_deposito", "rejected", False),
    ],
)
def test_fascicolo_e_indice_ricevute_concordano_sull_accettazione(stage, final, accepted):
    row = source(stage, final)
    life = json.loads(row["report_json"])["deposit_lifecycle"]

    assert (projected_receipt(row)["state"] == "ACCETTATO_CANCELLERIA") is accepted
    assert (_pct_deposit_state_from_lifecycle(life)[0] == "ACCETTATO_CANCELLERIA") is accepted

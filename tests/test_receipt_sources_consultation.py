import os

import pytest

from pct.registro_letture import Fatto, Oggetto, RegistroLetture
from pct.registro_letture.lettori import versione_lettore
from pct.registro_letture.ricevute_consultazione import _receipt_date, group_exact_receipt_copies, receipt_sources
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def registry(request, tmp_path):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(request.param)
    dsn = ''
    if request.param == 'postgresql':
        from psycopg2.extensions import make_dsn
        dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
    value = RegistroLetture(tmp_path / 'readings.db', postgres_dsn=dsn)
    try:
        yield value
    finally:
        value.close()
        factory.close()


def put(registry, *, tenant='study-a', case='case-a', kind='documento', key='doc-one', sha='a' * 64, verdict='verificata', version=None):
    source = Oggetto(tipo=kind, oggetto_id=key, nome='Ricevuta controllata', sha256=sha)
    registry.registra_inventario(tenant, case, [source], tipi=[kind])
    engine = 'documenti' if kind == 'documento' else 'pec'
    registry.registra_fatti(tenant, case, source, engine,
        [Fatto(categoria='prova_notifica', campo='rac', valore='rac', verifica=verdict)],
        versione=version or versione_lettore('motore_' + engine))


def test_documento_nel_fascicolo_e_pec_presenti_insieme_con_provenienza(registry):
    put(registry)
    put(registry, kind='pec', key='pec-one')
    page = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])
    assert {row['tipo'] for row in page['rows']} == {'documento', 'pec'}
    assert all(row['verified'] for row in page['rows'])
    assert len({row['exact_copy_key'] for row in page['rows']}) == 1
    assert {row['oggetto_id'] for row in page['rows']} == {'doc-one', 'pec-one'}
    grouped = group_exact_receipt_copies(page['rows'] + page['rows'])
    assert len(grouped) == 1
    assert len(grouped[0]['sources']) == 2
    assert receipt_sources(registry, tenant='other-study', case_ids=['case-a'])['rows'] == []
    assert receipt_sources(registry, tenant='study-a', case_ids=['other-case'])['rows'] == []


def test_fonte_modificata_o_non_verificata_non_diventa_ricevuta_certa(registry):
    put(registry)
    replacement = Oggetto(tipo='documento', oggetto_id='doc-one', nome='Sostituita', sha256='b' * 64)
    registry.registra_inventario('study-a', 'case-a', [replacement], tipi=['documento'])
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['issue'] == 'source_revision_changed'
    assert not row['verified']
    put(registry, kind='pec', key='pec-one', verdict='plausibile')
    page = receipt_sources(registry, tenant='study-a', case_ids=['case-a'], limit=1)
    assert page['has_more']
    next_page = receipt_sources(registry, tenant='study-a', case_ids=['case-a'], limit=1, cursor=page['cursor'])
    assert not next_page['has_more']
    assert {row['issue'] for row in page['rows'] + next_page['rows']} == {'source_revision_changed', 'proof_not_confirmed'}
    assert len(group_exact_receipt_copies(page['rows'] + next_page['rows'])) == 2


def test_data_ricevuta_da_fatto_della_stessa_fonte_senza_usare_importazione(registry):
    source = Oggetto(tipo='documento', oggetto_id='doc-one', nome='Ricevuta controllata', sha256='a' * 64)
    registry.registra_inventario('study-a', 'case-a', [source], tipi=['documento'])
    facts = [Fatto(categoria='prova_notifica', campo='rac', valore='rac', verifica='verificata'),
             Fatto(categoria='data', campo='accettazione', valore='2026-10-14T09:30', verifica='verificata'),
             Fatto(categoria='data', campo='deposito', valore='2026-10-15', verifica='verificata')]
    registry.registra_fatti('study-a', 'case-a', source, 'documenti', facts, versione=versione_lettore('motore_documenti'))
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['event_date'] == '2026-10-14T09:30:00+02:00'
    assert row['date_issue'] == ''
    facts.append(Fatto(categoria='data', campo='accettazione', valore='2026-10-16', verifica='corretta'))
    registry.registra_fatti('study-a', 'case-a', source, 'documenti', facts, versione=versione_lettore('motore_documenti'))
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['event_date'] == ''
    assert row['date_issue'] == 'source_dates_discordant'


def test_prova_classificata_senza_data_non_diventa_deposito_accettato(registry):
    put(registry)
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['verified']  # È verificato il tipo di documento.
    assert row['event_date'] == ''
    assert row['date_issue'] == 'event_date_not_available'
    assert 'ACCETTATO_CANCELLERIA' not in row.values()


def test_versione_obsoleta_non_conferma_la_prova_e_correzione_manuale_preservata(registry):
    put(registry, version='controlled-obsolete-version')
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['issue'] == 'reader_version_not_current'
    assert not row['classification_verified']
    put(registry, verdict='corretta', version='controlled-obsolete-version')
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['classification_verified']
    assert row['issue'] == ''


def test_data_di_altro_motore_non_e_la_data_della_ricevuta(registry):
    source = Oggetto(tipo='documento', oggetto_id='doc-one', nome='Ricevuta controllata', sha256='a' * 64)
    put(registry)
    registry.registra_fatti('study-a', 'case-a', source, 'pec',
        [Fatto(categoria='data', campo='accettazione', valore='2026-10-14', verifica='verificata')],
        versione=versione_lettore('motore_pec'))
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['classification_verified']
    assert row['event_date'] == ''
    assert row['date_issue'] == 'event_date_not_available'


def test_data_corretta_manualmente_preservata_sulla_stessa_fonte(registry):
    source = Oggetto(tipo='documento', oggetto_id='doc-one', nome='Ricevuta controllata', sha256='a' * 64)
    put(registry)
    registry.registra_fatti('study-a', 'case-a', source, 'pec',
        [Fatto(categoria='data', campo='accettazione', valore='2026-10-14', verifica='corretta')],
        versione='controlled-old-version')
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert row['event_date'] == '2026-10-14'
    assert row['date_issue'] == ''
    replacement = Oggetto(tipo='documento', oggetto_id='doc-one', nome='Sostituita', sha256='b' * 64)
    registry.registra_inventario('study-a', 'case-a', [replacement], tipi=['documento'])
    row = receipt_sources(registry, tenant='study-a', case_ids=['case-a'])['rows'][0]
    assert not row['classification_verified']
    assert row['issue'] == 'source_revision_changed'


@pytest.mark.parametrize('values,expected,issue,precision', [
    (['2026-01-09', '2026-01-09T09:37'], '2026-01-09T09:37:00+01:00', '', 'minute'),
    (['2026-01-09T09:37', '2026-01-09T09:37:32'], '2026-01-09T09:37:32+01:00', '', 'second'),
    (['2026-01-09T09:37:32', '2026-01-09T09:37:54'], '', 'source_dates_discordant', ''),
    (['2026-10-14T09:30+02:00', '2026-10-14T07:30Z'], '2026-10-14T07:30:00+00:00', '', 'minute'),
    (['2026-10-14', '2026-10-13T22:30Z'], '2026-10-13T22:30:00+00:00', '', 'minute'),
    (['2026-10-13', '2026-10-13T22:30Z'], '', 'source_dates_discordant', ''),
    (['2026-03-29', '2026-03-29T21:30Z'], '2026-03-29T21:30:00+00:00', '', 'minute'),
    (['2026-03-29', '2026-03-29T22:30Z'], '', 'source_dates_discordant', ''),
    (['2026-03-29T02:30'], '', 'source_date_invalid', ''),
    (['2026-10-25T02:30'], '', 'source_time_zone_ambiguous', ''),
    (['2026-10-25T02:30+02:00'], '2026-10-25T02:30:00+02:00', '', 'minute'),
    (['2026-02-31'], '', 'source_date_invalid', ''),
])
def test_precisione_date_stesso_evento_e_fuso_italiano(values, expected, issue, precision):
    assert _receipt_date(set(values)) == (expected, issue, precision)

from datetime import date

import pytest

from pct.registro_letture import Fatto, Oggetto
from pct.registro_letture.lettori import versione_lettore
from pct.registro_letture.ricevute_query import AGGREGATE, ReceiptArchiveQuery, install
from tests.test_receipt_sources_consultation import registry as registry
from web.services.receipt_archive_runtime import resume_archive_owner
from web.services.registro_letture_runtime import connessione_registro


def put(registry, key, *, day='2026-10-14T09:30', sha='a' * 64, case='case-a'):
    source = Oggetto(tipo='documento', oggetto_id=key, nome='Ricevuta controllata', sha256=sha)
    inventory = [row for row in registry.oggetti('study-a', case) if row.oggetto_id != key]
    registry.registra_inventario('study-a', case, [*inventory, source], tipi=['documento'])
    registry.registra_fatti('study-a', case, source, 'documenti', [
        Fatto(categoria='prova_notifica', campo='rac', valore='rac', verifica='verificata'),
        Fatto(categoria='data', campo='accettazione', valore=day, verifica='verificata'),
    ], versione=versione_lettore('motore_documenti'))


def prepare(registry):
    with connessione_registro(registry) as conn:
        install(conn, 'study-a', postgres=registry.backend_kind == 'postgres')
        ReceiptArchiveQuery(conn, 'study-a').project_case(registry, 'case-a')
        conn.execute("UPDATE receipt_archive_query_owner SET ready=1 WHERE tenant_id='study-a'")
        conn.commit()


def test_catalogo_date_e_copie_identiche_non_confermano_notifica(registry):
    put(registry, 'one')
    put(registry, 'copy')
    prepare(registry)
    with connessione_registro(registry) as conn:
        page = ReceiptArchiveQuery(conn, 'study-a').list_page(
            kind='rac', ranges=((date(2026, 10, 14), date(2026, 10, 14)),))
        assert len(page['rows']) == 1
        row = page['rows'][0]
        assert len(row['sources']) == 2
        assert row['event_at'] == '2026-10-14T07:30:00.000000+00:00'
        assert not row['legal_notification_confirmed']
        assert not ReceiptArchiveQuery(conn, 'study-a').list_page(
            ranges=((date(2026, 10, 13), date(2026, 10, 13)),))['rows']
        with pytest.raises(RuntimeError):
            ReceiptArchiveQuery(conn, 'other-study').list_page()


def test_cambio_fonte_blocca_stato_vecchio_e_worker_riprende_solo_evento(registry):
    put(registry, 'one')
    prepare(registry)
    replacement = Oggetto(tipo='documento', oggetto_id='one', nome='Fonte modificata', sha256='b' * 64)
    registry.registra_inventario('study-a', 'case-a', [replacement], tipi=['documento'])
    with connessione_registro(registry) as conn:
        with pytest.raises(RuntimeError):
            ReceiptArchiveQuery(conn, 'study-a').list_page()
    result = resume_archive_owner(registry, 'study-a')
    assert result['delivered'] and result['failed'] == 0
    with connessione_registro(registry) as conn:
        page = ReceiptArchiveQuery(conn, 'study-a').list_page()
        assert page['rows'][0]['issue'] == 'source_revision_changed'
        assert not page['rows'][0]['verified']
    assert resume_archive_owner(registry, 'study-a')['delivered'] == 0


def test_eventi_estranei_e_aggiornamenti_identici_non_creano_lavoro(registry):
    put(registry, 'one')
    prepare(registry)
    with connessione_registro(registry) as conn:
        before = conn.execute('SELECT COUNT(*) FROM transactional_outbox WHERE aggregate_type=?', (AGGREGATE,)).fetchone()[0]
        conn.execute("UPDATE letture_fatti SET valore=valore WHERE tenant_id='study-a'")
        conn.commit()
        after = conn.execute('SELECT COUNT(*) FROM transactional_outbox WHERE aggregate_type=?', (AGGREGATE,)).fetchone()[0]
        assert after == before


def test_pagine_stabili_e_date_non_determinate_restano_esplicite(registry):
    put(registry, 'one', sha='a' * 64)
    put(registry, 'two', day='2026-10-15', sha='b' * 64)
    prepare(registry)
    with connessione_registro(registry) as conn:
        first = ReceiptArchiveQuery(conn, 'study-a').list_page(limit=1)
        assert first['has_more']
        second = ReceiptArchiveQuery(conn, 'study-a').list_page(limit=1, cursor=first['cursor'])
        assert not second['has_more'] and second['rows'][0]['id'] != first['rows'][0]['id']


def test_preparazione_conferma_anche_con_piu_lotti_di_consegne(registry, monkeypatch, tmp_path):
    from web.services.receipt_archive_runtime import prepare_archive_receipts

    put(registry, 'one')
    prepare(registry)
    # Qui si verifica la consegna, non la procedura di backup già collaudata.
    monkeypatch.setattr('scripts.query_index_backup.verified_backup',
                        lambda *_: (tmp_path / 'controlled-snapshot', 'a' * 64))
    with connessione_registro(registry) as conn:
        for number in range(51):
            conn.execute("UPDATE letture_oggetti SET nome=? WHERE tenant_id='study-a'",
                         (f'Ricevuta controllata {number}',))
        conn.commit()
    result = prepare_archive_receipts(registry, 'study-a', tmp_path / 'backup', max_batches=3)
    assert result['phase'] == 'COMPLETED'
    with connessione_registro(registry) as conn:
        page = ReceiptArchiveQuery(conn, 'study-a').list_page()
        assert page['rows'][0]['title'] == 'Ricevuta controllata 50'
    assert resume_archive_owner(registry, 'study-a')['delivered'] == 0


def test_budget_consegne_esaurito_non_dichiara_preparazione_conclusa(registry, monkeypatch, tmp_path):
    from web.services.receipt_archive_runtime import prepare_archive_receipts

    put(registry, 'one')
    prepare(registry)
    monkeypatch.setattr('scripts.query_index_backup.verified_backup',
                        lambda *_: (tmp_path / 'controlled-snapshot', 'a' * 64))
    with connessione_registro(registry) as conn:
        for number in range(51):
            conn.execute("UPDATE letture_oggetti SET nome=? WHERE tenant_id='study-a'",
                         (f'Ricevuta controllata {number}',))
        conn.commit()
    with pytest.raises(RuntimeError, match='Budget delle consegne'):
        prepare_archive_receipts(registry, 'study-a', tmp_path / 'backup', max_batches=1)
    result = prepare_archive_receipts(registry, 'study-a', tmp_path / 'backup', max_batches=3)
    assert result['phase'] == 'COMPLETED'


def test_cambio_compatibilita_lettore_richiede_riproiezione_esplicita(registry, monkeypatch):
    put(registry, 'one')
    prepare(registry)
    monkeypatch.setattr('pct.registro_letture.ricevute_query.reader_signature', lambda: 'new-reader-contract')
    with connessione_registro(registry) as conn:
        with pytest.raises(RuntimeError, match='non ancora confermato'):
            ReceiptArchiveQuery(conn, 'study-a').list_page()
        install(conn, 'study-a', postgres=registry.backend_kind == 'postgres')
        owner = conn.execute("SELECT ready,after_case FROM receipt_archive_query_owner WHERE tenant_id='study-a'").fetchone()
        assert (owner[0], owner[1]) == (0, '')
        conn.commit()


def test_studio_vuoto_preparato_con_backup_reale_e_riapertura(tmp_path):
    import hashlib
    import json

    from pct.registro_letture import RegistroLetture
    from web.services.receipt_archive_runtime import prepare_archive_receipts

    path = tmp_path / 'readings.db'
    registry = RegistroLetture(path)
    try:
        result = prepare_archive_receipts(registry, 'new-study', tmp_path / 'backup')
        assert result['phase'] == 'COMPLETED'
        manifest = json.loads((tmp_path / 'backup' / 'manifest.json').read_text())
        snapshot = tmp_path / 'backup' / 'studio.db'
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == manifest['backup']['sha256']
    finally:
        registry.close()
    registry = RegistroLetture(path, read_only=True)
    try:
        with connessione_registro(registry) as conn:
            assert ReceiptArchiveQuery(conn, 'new-study').list_page()['rows'] == []
    finally:
        registry.close()


def test_proiezione_riusa_transazione_sotto_spill_sqlite(tmp_path):
    """Un lotto ampio può detenere EXCLUSIVE: una seconda connessione si blocca da sola."""
    import json

    from pct.registro_letture import RegistroLetture
    from web.services.fascicoli_list_events_runtime import registry_outbox_writer

    registry = RegistroLetture(tmp_path / 'spill.db')
    try:
        put(registry, 'one', case='case-a')
        put(registry, 'two', case='case-b')
        with registry.connection() as source:
            source.execute('UPDATE letture_fatti SET prove_json=? WHERE fascicolo_id=?',
                           (json.dumps([{'text': 'evidenza sintetica ' * 8000}]), 'case-a'))
        with registry_outbox_writer(registry) as writer:
            install(writer, 'study-a')
            writer.commit()
            writer.execute('PRAGMA cache_size=1')
            writer.execute('PRAGMA cache_spill=ON')
            projection = ReceiptArchiveQuery(writer, 'study-a')
            projection.project_case(registry, 'case-a')
            projection.project_case(registry, 'case-b')
            assert writer.execute('SELECT COUNT(*) FROM receipt_archive_query_rows').fetchone()[0] == 2
            writer.rollback()
            assert writer.execute('SELECT COUNT(*) FROM receipt_archive_query_rows').fetchone()[0] == 0
    finally:
        registry.close()

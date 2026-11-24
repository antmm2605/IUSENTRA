"""Consegna delle ricevute archiviate con transazioni di scrittura brevi (verifica del 24/11/2026 sull'8080).

Il giro ``receipt_query_projection`` partito alle 10:00:26 non si chiudeva e il registro delle letture restava
bloccato in scrittura: la prenotazione della consegna apriva la transazione e le letture delle prove (una
scansione di tutti i fatti dello studio per ogni pagina) giravano dentro quella transazione.
"""

import sqlite3

import pytest

from pct.registro_letture.ricevute_consultazione import receipt_sources
from pct.registro_letture.ricevute_query import AGGREGATE, ReceiptArchiveQuery
from tests.test_receipt_archive_query import prepare, put
from tests.test_receipt_sources_consultation import registry as registry
from web.services import receipt_archive_runtime
from web.services.receipt_archive_runtime import resume_archive_owner
from web.services.registro_letture_runtime import connessione_registro


@pytest.fixture
def registro_sqlite(registry):
    if registry.backend_kind != 'sqlite':
        pytest.skip('Il blocco di scrittura qui misurato è quello di SQLite.')
    return registry


def _fonte_cambiata(registry):
    from pct.registro_letture import Oggetto

    replacement = Oggetto(tipo='documento', oggetto_id='one', nome='Fonte modificata', sha256='b' * 64)
    registry.registra_inventario('study-a', 'case-a', [replacement], tipi=['documento'])


def test_le_letture_delle_prove_non_tengono_il_registro_in_scrittura(registro_sqlite, monkeypatch):
    put(registro_sqlite, 'one')
    prepare(registro_sqlite)
    _fonte_cambiata(registro_sqlite)
    originale = ReceiptArchiveQuery.read_case
    scrittore_libero = []

    def read_case_misurato(self, registry, case_id):
        # Un altro scrittore (la lettura di un documento dell'avvocato) deve poter scrivere subito.
        altro = sqlite3.connect(registro_sqlite.db_path, timeout=0)
        try:
            altro.execute('BEGIN IMMEDIATE')
            altro.rollback()
            scrittore_libero.append(True)
        except sqlite3.OperationalError:
            scrittore_libero.append(False)
        finally:
            altro.close()
        return originale(self, registry, case_id)

    monkeypatch.setattr(ReceiptArchiveQuery, 'read_case', read_case_misurato)
    risultato = resume_archive_owner(registro_sqlite, 'study-a')
    assert risultato['delivered'] == 1 and risultato['failed'] == 0
    assert scrittore_libero == [True], 'le letture della proiezione giravano dentro la transazione di scrittura'


def test_il_giro_si_ferma_al_tempo_massimo_e_lascia_il_resto_al_giro_dopo(registro_sqlite, monkeypatch):
    put(registro_sqlite, 'one')
    prepare(registro_sqlite)
    _fonte_cambiata(registro_sqlite)
    monkeypatch.setattr(receipt_archive_runtime, 'TEMPO_GIRO_SECONDI', 0.0)
    assert resume_archive_owner(registro_sqlite, 'study-a') == dict(delivered=0, failed=0, not_migrated=0)
    with connessione_registro(registro_sqlite) as conn:
        in_attesa = conn.execute("SELECT COUNT(*) FROM transactional_outbox WHERE aggregate_type=? AND status='PENDING'",
                                 (AGGREGATE,)).fetchone()[0]
    assert in_attesa == 1
    monkeypatch.setattr(receipt_archive_runtime, 'TEMPO_GIRO_SECONDI', 20.0)
    assert resume_archive_owner(registro_sqlite, 'study-a')['delivered'] == 1


def test_le_date_delle_prove_si_cercano_per_fascicolo_con_l_indice(registro_sqlite):
    put(registro_sqlite, 'one')
    istruzioni = []
    with connessione_registro(registro_sqlite) as conn:
        conn.set_trace_callback(istruzioni.append)
        receipt_sources(registro_sqlite, tenant='study-a', case_ids=['case-a'], connection=conn)
        conn.set_trace_callback(None)
        date = [sql for sql in istruzioni if "categoria='data'" in sql]
        assert date, 'nessuna ricerca delle date eseguita'
        piano = ' '.join(str(riga[-1]) for riga in conn.execute('EXPLAIN QUERY PLAN ' + date[0]).fetchall())
    assert 'fascicolo_id=?' in piano, piano

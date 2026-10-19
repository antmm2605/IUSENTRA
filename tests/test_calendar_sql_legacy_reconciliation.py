"""La manutenzione legacy non ricrea l'archivio SQL già adottato."""
import pytest

from pct.agenda import Agenda, TipoAppuntamento
from pct.database import GestioneDatabase
from pct.scadenziario_sql_adoption import adopt
from pct.storage import StudioDB


@pytest.fixture
def archive(tmp_path):
    source = tmp_path / 'agenda/appuntamenti.json'
    old = Agenda(str(source)).aggiungi('Storico', TipoAppuntamento.RIUNIONE, '2026-12-01T10:00:00')
    original = source.read_bytes()
    db = StudioDB.get(str(tmp_path / 'studio.db'))
    adopt(db, source, tenant='studio-test', destination=tmp_path / 'backup/adozione',
          data_root=tmp_path, writers_drained=True, domain='agenda')
    current = Agenda(str(source), studio_db=db)
    current.elimina(old.id)
    item = current.aggiungi('Solo SQL', TipoAppuntamento.RIUNIONE, '2026-12-02T10:00:00')
    db.conn.execute('CREATE TABLE dati_nativi_preservati (id TEXT PRIMARY KEY,valore TEXT)')
    db.conn.execute("INSERT INTO dati_nativi_preservati VALUES ('controllato','Decisione conservata')")
    db.conn.commit()
    return db, source, old, item, original


def test_rimigrazione_preserva_sql_audit_e_tabelle_native_senza_resurrezione_json(archive):
    db, source, old, item, original = archive
    result = GestioneDatabase({'appuntamenti': str(source)}).migra_verso_sqlite(str(db.db_path))
    assert result.riuscita, result.errori
    current = Agenda(str(source))
    assert current.get(old.id) is None
    assert current.get(item.id).titolo == 'Solo SQL'
    assert source.read_bytes() == original
    assert current._sql_only
    assert db.conn.execute('SELECT valore FROM dati_nativi_preservati').fetchone()[0] == 'Decisione conservata'
    assert db.conn.execute("SELECT count(*) FROM audit_log WHERE azione='agenda.adozione_sql'").fetchone()[0] == 1


def test_importazione_legacy_distinta_aggiunge_senza_ricreare_archivio_nativo(archive, tmp_path):
    db, source, old, item, _ = archive
    from pct.calendar_query_preparation import prepare_calendar_query_catalog
    from pct.calendar_query_repository import CalendarQueryRepository
    prepare_calendar_query_catalog(db, tenant='studio-test', backup_dir=tmp_path / 'backup/query')
    incoming = tmp_path / 'legacy/appuntamenti.json'
    imported = Agenda(str(incoming)).aggiungi('Importazione esplicita', TipoAppuntamento.RIUNIONE, '2026-12-03T10:00:00')
    result = GestioneDatabase({'appuntamenti': str(incoming)}).riconcilia_verso_sqlite(str(db.db_path))
    assert result.riuscita, result.errori
    current = Agenda(str(source))
    assert current.get(old.id) is None
    assert current.get(item.id).titolo == 'Solo SQL'
    assert current.get(imported.id).titolo == 'Importazione esplicita'
    assert current._sql_only
    page = CalendarQueryRepository(db, 'studio-test').list_page(domain='agenda')
    assert {row['id'] for row in page['rows']} == {item.id, imported.id}
    assert page['has_more'] is False


def test_errore_importazione_rollback_senza_perdere_conferma_e_dati(archive, tmp_path):
    db, source, _, item, original = archive
    incoming = tmp_path / 'legacy/appuntamenti.json'
    imported = Agenda(str(incoming)).aggiungi('Importazione rifiutata', TipoAppuntamento.RIUNIONE, '2026-12-03T10:00:00')
    db.conn.execute("CREATE TRIGGER rifiuto_controllato BEFORE INSERT ON appuntamenti BEGIN SELECT RAISE(ABORT,'rifiuto controllato'); END")
    db.conn.commit()
    result = GestioneDatabase({'appuntamenti': str(incoming)}).riconcilia_verso_sqlite(str(db.db_path))
    assert not result.riuscita
    assert any('rifiuto controllato' in error for error in result.errori)
    current = Agenda(str(source))
    assert current.get(item.id) is not None and current.get(imported.id) is None
    assert current._sql_only and source.read_bytes() == original


def test_confronto_perdite_usa_sql_prima_del_comando_non_il_conteggio_finale():
    from pct.storage_migration_full import _build_diff_summary
    inventory = {'domains': [{'code': 'appuntamenti', 'title': 'Agenda', 'storage_kind': 'core',
                              'json_count': 99, 'sqlite_count': 0}],
                 'sql_authoritative_counts': {'appuntamenti': 0}}
    report = _build_diff_summary(inventory=inventory, target='sqlite', authoritative_counts={'appuntamenti': 1})
    assert report['rows'][0]['source_count'] == 1
    assert report['rows'][0]['source_label'] == 'SQL locale autorevole'
    assert report['rows'][0]['loss_risk'] is True
    current = _build_diff_summary(inventory=inventory, target='sqlite')
    assert current['rows'][0]['source_count'] == 0
    assert current['rows'][0]['loss_risk'] is False

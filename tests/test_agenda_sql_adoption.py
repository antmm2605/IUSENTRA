"""Adozione nativa Agenda: dati, storico, isolamento, ripresa e concorrenza."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.agenda_sql_writer import AgendaConflict
from pct.scadenziario_sql_adoption import adopt
from pct.scadenziario_sql_owner import owner_path
from tests.test_scadenziario_sql_adoption import archive  # noqa: F401


@pytest.fixture
def agenda(archive, monkeypatch):  # noqa: F811
    db, old_source, _, _, _ = archive
    source = old_source.parent.parent / 'agenda/appuntamenti.json'
    legacy = Agenda(str(source))
    item = legacy.aggiungi('Udienza controllata', TipoAppuntamento.UDIENZA, '2026-12-01T10:00:00',
                           note='Fonte conservata', id_fascicolo='fascicolo-controllato')
    def migrate(**kwargs):
        return adopt(db, source, tenant='studio-test', destination=source.parent.parent / 'backup/agenda',
                     data_root=source.parent.parent, writers_drained=True, domain='agenda', **kwargs)
    # Il resolver PostgreSQL del fixture deve riconoscere entrambi i domini.
    if getattr(db, 'backend_kind', '') == 'postgresql':
        owner = SimpleNamespace(database=object(), slug='studio-test')
        monkeypatch.setattr('pct.tenant.GestioneTenant', lambda **kwargs: SimpleNamespace(
            get=lambda slug: owner if slug == 'studio-test' else None,
            percorsi_dati=lambda *args, **kwargs: {'AGENDA_DB': str(source),
                'SCADENZIARIO_DB': str(old_source), 'STUDIO_DB': str(source.parent.parent / 'studio.db')}))
    return db, source, legacy, item, migrate


def test_adozione_preserva_fonte_sql_collegamenti_e_produttori(agenda):
    db, source, legacy, item, migrate = agenda
    before = source.read_bytes()
    assert migrate()['source_records'] == 1
    current = Agenda(str(source))
    assert current.get(item.id).to_dict() == item.to_dict()
    current.modifica(item.id, note='Aggiornato in SQL')
    assert Agenda(str(source), studio_db=db).get(item.id).note == 'Aggiornato in SQL'
    assert source.read_bytes() == before
    assert migrate() == {'changed': False, 'tenant': 'studio-test'}
    assert db.conn.execute("SELECT count(*) FROM audit_log WHERE azione='agenda.adozione_sql'").fetchone()[0] == 1
    with pytest.raises(RuntimeError, match='scrittura JSON storica bloccata'):
        legacy.modifica(item.id, note='Snapshot superato')


def test_sql_operativo_conservato_e_differenze_storiche_auditate(agenda):
    db, source, _, item, migrate = agenda
    current = Agenda(str(source), studio_db=db)
    current.modifica(item.id, stato=StatoAppuntamento.COMPLETATO)
    payload = json.loads(source.read_bytes())
    payload[item.id]['stato'] = 'PROGRAMMATO'
    source.write_text(json.dumps(payload), encoding='utf-8')
    before = source.read_bytes()
    migrate()
    assert Agenda(str(source)).get(item.id).stato == StatoAppuntamento.COMPLETATO
    assert source.read_bytes() == before
    details = json.loads(db.conn.execute("SELECT dettagli FROM audit_log WHERE azione='agenda.adozione_sql'").fetchone()[0])
    assert details['historical_differences'][0]['fields'] == ['stato']
    assert details['historical_differences'][0]['id'] == item.id
    assert Path(details['backup_reference']).is_file()


def test_consultazione_non_legge_ne_scrive_json(agenda, monkeypatch):
    _, source, _, item, migrate = agenda
    migrate()
    def forbidden(*args, **kwargs):
        raise AssertionError('Lavorazione estranea alla consultazione SQL')
    monkeypatch.setattr(Agenda, '_carica_json_file', forbidden)
    monkeypatch.setattr(Agenda, '_salva', forbidden)
    monkeypatch.setattr(Agenda, '_salva_json_file', forbidden)
    assert Agenda(str(source)).get(item.id).id_fascicolo == 'fascicolo-controllato'


def test_cancellazione_non_resuscita_e_json_corrotto_non_importa(agenda):
    db, source, _, item, migrate = agenda
    migrate()
    current = Agenda(str(source))
    current.elimina(item.id)
    source.write_text('storico corrotto', encoding='utf-8')
    assert Agenda(str(source), studio_db=db).get(item.id) is None


def test_concorrenza_conserva_cas(agenda):
    _, source, _, item, migrate = agenda
    migrate()
    left, right = Agenda(str(source)), Agenda(str(source))
    left.modifica(item.id, note='Vincitore')
    with pytest.raises(AgendaConflict):
        right.modifica(item.id, note='Snapshot superato')
    assert Agenda(str(source)).get(item.id).note == 'Vincitore'


def test_identita_backend_errata_e_studio_diverso_respinti(agenda, tmp_path):
    db, source, _, _, migrate = agenda
    migrate()
    from pct.storage import StudioDB
    with pytest.raises(RuntimeError, match='diverso dal proprietario'):
        Agenda(str(source), studio_db=StudioDB.get(str(tmp_path / 'altro.db')))
    other = source.with_name('altro.json')
    other.write_text('{}')
    with pytest.raises(RuntimeError):
        adopt(db, other, tenant='altro-studio', destination=tmp_path / 'backup/altro',
              data_root=tmp_path, writers_drained=True, domain='agenda')


def test_backup_fallito_non_attiva_fence(agenda, monkeypatch):
    _, source, _, _, migrate = agenda
    def failed(*args, **kwargs):
        raise RuntimeError('Backup fallito')
    monkeypatch.setattr('scripts.query_index_backup.verified_backup', failed)
    with pytest.raises(RuntimeError, match='Backup fallito'):
        migrate()
    assert not owner_path(source).exists()


def test_campi_sconosciuti_non_scartati(agenda):
    _, source, _, item, migrate = agenda
    payload = json.loads(source.read_bytes())
    payload[item.id]['campo_non_mappato'] = 'Da conservare'
    source.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='Campi storici'):
        migrate()
    assert not owner_path(source).exists()


def test_righe_solo_sql_restano_e_ripresa_non_duplica(agenda, monkeypatch):
    db, source, _, item, migrate = agenda
    native = Agenda(str(source), studio_db=db)
    extra = native.aggiungi('Solo SQL', TipoAppuntamento.RIUNIONE, '2026-12-02T10:00:00')
    payload = json.loads(source.read_bytes())
    del payload[extra.id]
    source.write_text(json.dumps(payload))
    from pct.agenda_sql_writer import write_changes
    def interrupted(*args, **kwargs):
        raise RuntimeError('Interruzione controllata')
    monkeypatch.setattr('pct.agenda_sql_writer.write_changes', interrupted)
    with pytest.raises(RuntimeError, match='Interruzione controllata'):
        migrate()
    with pytest.raises(RuntimeError, match='non confermata'):
        Agenda(str(source))
    monkeypatch.setattr('pct.agenda_sql_writer.write_changes', write_changes)
    migrate()
    assert Agenda(str(source)).get(extra.id).titolo == 'Solo SQL'
    assert Agenda(str(source)).get(item.id) is not None
    assert migrate()['changed'] is False


def test_stesso_studio_puo_adottare_entrambi_i_domini(agenda, archive):  # noqa: F811
    _, _, _, _, migrate = agenda
    _, _, _, _, migrate_deadlines = archive
    migrate_deadlines()
    migrate()


def test_altro_studio_non_puo_riassegnare_database_del_calendario(agenda, archive, tmp_path):  # noqa: F811
    db, source, _, _, _ = agenda
    archive[4]()
    with pytest.raises(RuntimeError, match='altro studio'):
        adopt(db, source, tenant='altro-studio', destination=tmp_path / 'backup/altro',
              data_root=tmp_path, writers_drained=True, domain='agenda')

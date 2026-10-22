"""Guardrail SQL: writes from stale managers must not erase other clients."""
import json
import os
import pytest

from pct.clienti import GestioneClienti, TipoCliente
from pct.storage import StudioDB


def preservation_backend(tmp_path):
    if os.environ.get('CLIENTI_TEST_POSTGRES') == '1':
        from psycopg2.extensions import make_dsn
        from pct.storage_postgres import PostgresStudioDB
        from tests.test_condivisioni_sql_repository import SQLFactory
        factory = SQLFactory('postgresql')
        return PostgresStudioDB(make_dsn(**factory.pg_parameters,
                                         options=f'-c search_path={factory.schema}')), factory
    return StudioDB(str(tmp_path / 'studio.db')), None


def test_updates_of_different_clients_preserve_both_commits(tmp_path):
    backend = StudioDB(str(tmp_path / "studio.db"))
    first = GestioneClienti(studio_db=backend)
    one = first.nuovo(TipoCliente.PERSONA_FISICA, nome="Uno", cognome="Controllato")
    two = first.nuovo(TipoCliente.PERSONA_FISICA, nome="Due", cognome="Controllato")
    stale = GestioneClienti(studio_db=backend)
    first.aggiorna(one.id, note="primo aggiornamento")
    stale.aggiorna(two.id, note="secondo aggiornamento")
    fresh = GestioneClienti(studio_db=backend)
    assert fresh.get(one.id).note == "primo aggiornamento"
    assert fresh.get(two.id).note == "secondo aggiornamento"


def test_competing_update_of_same_client_is_explicit_and_not_overwritten(tmp_path):
    backend = StudioDB(str(tmp_path / "studio.db"))
    first = GestioneClienti(studio_db=backend)
    client = first.nuovo(TipoCliente.PERSONA_FISICA, nome="Uno", cognome="Controllato")
    stale = GestioneClienti(studio_db=backend)
    first.aggiorna(client.id, note="dato già confermato")
    revision = backend.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain = 'clienti'").fetchone()[0]
    with pytest.raises(ValueError, match="altro utente"):
        stale.aggiorna(client.id, note="scrittura concorrente obsoleta")
    assert GestioneClienti(studio_db=backend).get(client.id).note == "dato già confermato"
    assert backend.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain = 'clienti'").fetchone()[0] == revision


def test_client_update_preserves_case_link_and_uses_single_row_signal(tmp_path):
    backend = StudioDB(str(tmp_path / "studio.db"))
    manager = GestioneClienti(studio_db=backend)
    client = manager.nuovo(TipoCliente.PERSONA_FISICA, nome="Uno", cognome="Controllato")
    manager.nuovo(TipoCliente.PERSONA_FISICA, nome="Due", cognome="Controllato")
    backend.conn.execute("INSERT INTO fascicoli(id, id_cliente) VALUES (?, ?)", ("caso-controllato", client.id))
    backend.conn.commit()
    revision = backend.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain = 'clienti'").fetchone()[0]
    manager.aggiorna_documento(client.id, rilasciato_da="Comune controllato")
    assert backend.conn.execute("SELECT id_cliente FROM fascicoli WHERE id = ?", ("caso-controllato",)).fetchone()[0] == client.id
    assert backend.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain = 'clienti'").fetchone()[0] == revision + 1


def test_normal_edits_keep_historical_contact_metadata_across_reloads(tmp_path):
    backend, factory = preservation_backend(tmp_path)
    try:
        manager = GestioneClienti(studio_db=backend)
        client = manager.nuovo(TipoCliente.PERSONA_FISICA, nome='Collaudo conservazione')
        source = json.loads(backend.conn.execute('SELECT dati_json FROM clienti WHERE id=?', (client.id,)).fetchone()[0])
        source['recapiti']['provenienza_storica'] = {'importazione': 'controllata', 'revisione': 7}
        backend.conn.execute('UPDATE clienti SET dati_json=? WHERE id=?', (json.dumps(source), client.id))
        (getattr(backend, 'raw_conn', None) or backend.conn).commit()
        manager = GestioneClienti(studio_db=backend)
        manager.aggiorna(client.id, note='Nota confermata')
        manager.aggiorna_recapiti(client.id, telefono='0965000000')
        reloaded = GestioneClienti(studio_db=backend)
        reloaded.aggiorna(client.id, note='Seconda nota confermata')
        stored = json.loads(backend.conn.execute('SELECT dati_json FROM clienti WHERE id=?', (client.id,)).fetchone()[0])
        assert stored['recapiti']['provenienza_storica'] == source['recapiti']['provenienza_storica']
        assert stored['recapiti']['telefono'] == '0965000000'
        assert stored['note'] == 'Seconda nota confermata'
    finally:
        backend.chiudi()
        if factory:
            factory.close()


def test_rejected_edit_cannot_reappear_in_another_client_save(tmp_path):
    backend, factory = preservation_backend(tmp_path)
    try:
        manager = GestioneClienti(studio_db=backend)
        first = manager.nuovo(TipoCliente.PERSONA_FISICA, nome='Primo controllato')
        second = manager.nuovo(TipoCliente.PERSONA_FISICA, nome='Secondo controllato')
        stale = GestioneClienti(studio_db=backend)
        manager.aggiorna(first.id, note='Nota già confermata')
        with pytest.raises(ValueError, match='altro utente'):
            stale.aggiorna(first.id, note='Modifica rifiutata')
        stale.aggiorna(second.id, note='Altro comando valido')
        current = GestioneClienti(studio_db=backend)
        assert current.get(first.id).note == 'Nota già confermata'
        assert current.get(second.id).note == 'Altro comando valido'
    finally:
        backend.chiudi()
        if factory:
            factory.close()

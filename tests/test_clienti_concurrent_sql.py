"""Guardrail SQL: writes from stale managers must not erase other clients."""
import pytest

from pct.clienti import GestioneClienti, TipoCliente
from pct.storage import StudioDB


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

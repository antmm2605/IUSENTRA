"""Salvataggi Timesheet puntuali: nessuna perdita fra snapshot concorrenti."""
import json
import os
from types import MethodType

import pytest

from pct.storage import StudioDB
from pct.timesheet import GestioneTimesheet


@pytest.fixture
def managers(tmp_path):
    factory = None
    if os.environ.get("TIMESHEET_TEST_POSTGRES") == "1":
        from tests.test_condivisioni_sql_repository import SQLFactory
        from pct.storage_postgres import PostgresStudioDB
        from pct.timesheet_sql_writer import COLUMNS
        factory = SQLFactory("postgresql")
        db = factory.new()
        numeric = {"minuti": "INTEGER", "fatturabile": "INTEGER", "valore_unitario": "REAL"}
        columns = [name + " " + numeric.get(name, "TEXT") + (" PRIMARY KEY" if name == "id" else "") for name in COLUMNS]
        db.conn.execute(f"CREATE TABLE timesheet_entries ({','.join(columns)})")
        db.conn.execute("CREATE TABLE clienti (id TEXT PRIMARY KEY)")
        db.conn.execute("CREATE TABLE fascicoli (id TEXT PRIMARY KEY,id_cliente TEXT)")
        factory.commit(db)
        db.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, db)
        db.fetchall_readonly = lambda sql, parameters=(): db.conn.execute(sql, parameters).fetchall()
        def open_peer():
            peer = factory.new()
            peer.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, peer)
            peer.fetchall_readonly = lambda sql, parameters=(): peer.conn.execute(sql, parameters).fetchall()
            return peer
        db.open_peer = open_peer
    else:
        db = StudioDB(str(tmp_path / "studio.db"))
        db.open_peer = lambda: StudioDB(str(tmp_path / "studio.db"))
    path = str(tmp_path / "entries.json")
    def open_manager():
        return GestioneTimesheet(path, studio_db=db)
    initial = open_manager()
    first = initial.crea(descrizione="Prima attività", minuti=15)
    second = initial.crea(descrizione="Seconda attività", minuti=30)
    try:
        yield db, open_manager, first.id, second.id
    finally:
        factory.close() if factory else db.chiudi()


def test_modifiche_su_voci_distinte_non_si_sovrascrivono(managers):
    db, open_manager, first, second = managers
    left, right = open_manager(), open_manager()
    left.aggiorna(first, note="Nota primo processo")
    right.aggiorna(second, note="Nota secondo processo")
    rows = {row["id"]: json.loads(row["dati_json"]) for row in db.conn.execute("SELECT id,dati_json FROM timesheet_entries").fetchall()}
    assert rows[first]["note"] == "Nota primo processo"
    assert rows[second]["note"] == "Nota secondo processo"


def test_transazione_condivisa_conferma_solo_al_commit_esterno(managers):
    db, open_manager, _, _ = managers
    manager = open_manager()
    created = []
    with manager.transazione_condivisa() as bind:
        def write(conn, _):
            bind(db, conn)
            created.append(manager.crea(descrizione="Conferma unica", minuti=12).id)
        db.salva_tabella("timesheet_entries", [None], write, delete_all=False)
    assert open_manager().get(created[-1]).minuti == 12


def test_transazione_condivisa_rollback_ripristina_sql_e_snapshot(managers):
    db, open_manager, first, _ = managers
    manager = open_manager()
    manager.get(first)
    before = manager.get(first).to_dict()
    created = []
    with pytest.raises(ValueError, match="Esito proposta fallito"):
        with manager.transazione_condivisa() as bind:
            def write(conn, _):
                bind(db, conn)
                created.append(manager.crea(descrizione="Non confermata", minuti=12).id)
                manager.aggiorna(first, note="Non persistita")
                raise ValueError("Esito proposta fallito")
            db.salva_tabella("timesheet_entries", [None], write, delete_all=False)
    assert manager.get(first).to_dict() == before
    assert open_manager().get(first).to_dict() == before
    assert manager.get(created[-1]) is None
    assert open_manager().get(created[-1]) is None


def test_transazione_condivisa_vieta_connessione_di_altro_studio(managers):
    db, open_manager, _, _ = managers
    manager = open_manager()
    with manager.transazione_condivisa() as bind:
        with pytest.raises(ValueError, match="stesso studio"):
            bind(object(), db.conn)
        with pytest.raises(RuntimeError, match="non associata"):
            manager.crea(descrizione="Non consentita", minuti=1)
        with pytest.raises(RuntimeError, match="già attiva"):
            with manager.transazione_condivisa():
                pass


def test_creazione_da_snapshot_precedente_non_cancella_nuove_voci(managers):
    db, open_manager, _, _ = managers
    left, right = open_manager(), open_manager()
    first = left.crea(descrizione="Nuova prima", minuti=10)
    second = right.crea(descrizione="Nuova seconda", minuti=20)
    ids = {row[0] for row in db.conn.execute("SELECT id FROM timesheet_entries").fetchall()}
    assert {first.id, second.id} <= ids


def test_stessa_voce_in_conflitto_non_sovrascrive_il_salvataggio(managers):
    from pct.timesheet_sql_writer import TimesheetConflict
    db, open_manager, first, _ = managers
    left, right = open_manager(), open_manager()
    left.get(first)
    right.get(first)
    left.aggiorna(first, note="Prima versione confermata")
    with pytest.raises(TimesheetConflict, match="altro processo"):
        right.aggiorna(first, note="Snapshot superato")
    assert open_manager().get(first).note == "Prima versione confermata"


def test_righe_non_toccate_non_generano_scritture_o_riletture_globali(managers):
    db, open_manager, first, _ = managers
    if not hasattr(db, "_conn_per_scrittura"):
        pytest.skip("Probe del connettore SQLite; regole di scrittura provate anche PostgreSQL")
    manager = open_manager()
    trace = []
    from unittest.mock import patch
    conn = db._conn_per_scrittura()
    class ConnectionProbe:
        def execute(self, sql, *args):
            trace.append(sql)
            return conn.execute(sql, *args)
    with patch.object(db, "_conn_per_scrittura", return_value=ConnectionProbe()):
        manager.aggiorna(first, note="Solo questa voce")
    commands = [sql.strip().upper() for sql in trace]
    assert not any(sql.startswith("DELETE FROM TIMESHEET_ENTRIES") for sql in commands)
    assert sum(sql.startswith("UPDATE TIMESHEET_ENTRIES") for sql in commands) == 1
    assert not any(sql == "SELECT * FROM TIMESHEET_ENTRIES" for sql in commands)


def test_colonne_sql_primarie_non_vengono_sostituite_dal_json_storico(managers):
    db, open_manager, first, _ = managers
    db.conn.execute("UPDATE timesheet_entries SET descrizione=? WHERE id=?", ("Descrizione SQL confermata", first))
    (getattr(db, "raw_conn", None) or db.conn).commit()
    manager = open_manager()
    assert manager.get(first).descrizione == "Descrizione SQL confermata"
    manager.aggiorna(first, note="Nota conservata")
    again = open_manager().get(first)
    assert again.descrizione == "Descrizione SQL confermata"
    assert again.note == "Nota conservata"


def test_creazione_non_legge_archivio_e_modifica_legge_solo_id(managers):
    from unittest.mock import patch
    db, open_manager, first, _ = managers
    reads = []
    native = db.fetchall_readonly
    def read(sql, parameters=()):
        reads.append((sql, parameters))
        return native(sql, parameters)
    with patch.object(db, "fetchall_readonly", side_effect=read):
        fresh = open_manager()
        assert fresh.get(None) is None
        assert fresh.get("") is None
        fresh.crea(descrizione="Inserimento mirato", minuti=2)
        assert reads == []
        fresh.aggiorna(first, note="Modifica mirata")
    assert reads == [("SELECT * FROM timesheet_entries WHERE id=?", (first,))]


def test_sql_non_legge_ne_riscrive_json_storici(managers, tmp_path):
    _, open_manager, first, _ = managers
    path = tmp_path / "entries.json"
    original = '{"fonte_storica": "da conservare, non operativa"}'
    path.write_text(original, encoding="utf-8")
    manager = open_manager()
    manager.aggiorna(first, note="Fonte SQL")
    assert path.read_text(encoding="utf-8") == original
    assert open_manager().get(first).note == "Fonte SQL"


def test_conflitto_annulla_tutte_le_scritture_del_comando(managers):
    from pct.timesheet_sql_writer import TimesheetConflict
    _, open_manager, first, second = managers
    free, conflicting = sorted((first, second))
    left, right = open_manager(), open_manager()
    left.get(free).note = "Non deve essere confermata"
    left.get(conflicting).note = "Snapshot in conflitto"
    right.aggiorna(conflicting, note="Confermata dall’altro processo")
    with pytest.raises(TimesheetConflict):
        left._salva()
    fresh = open_manager()
    assert fresh.get(free).note == ""
    assert fresh.get(conflicting).note == "Confermata dall’altro processo"


def test_metadati_invalidi_restano_espliciti_solo_per_la_voce_interessata(managers):
    db, open_manager, first, second = managers
    db.conn.execute("UPDATE timesheet_entries SET dati_json=? WHERE id=?", ("[]", second))
    (getattr(db, "raw_conn", None) or db.conn).commit()
    manager = open_manager()
    manager.aggiorna(first, note="Modifica indipendente valida")
    with pytest.raises(ValueError, match="Metadati"):
        manager.get(second)
    assert open_manager().get(first).note == "Modifica indipendente valida"


def test_note_e_metadati_annidati_restano_persistiti(managers):
    _, open_manager, _, _ = managers
    manager = open_manager()
    entry = manager.crea(descrizione="Metadati da conservare", minuti=10,
                         note="Nota originale", dati_json={"importato": {"riferimento": "origine-controllata"}})
    reopened = open_manager()
    reopened.aggiorna(entry.id, minuti=20)
    confirmed = open_manager().get(entry.id)
    assert confirmed.note == "Nota originale"
    assert confirmed.dati_json == {"importato": {"riferimento": "origine-controllata"}}
    assert confirmed.minuti == 20


def test_collegamenti_assenti_o_discordanti_non_vengono_registrati(managers):
    db, open_manager, _, _ = managers
    manager = open_manager()
    with pytest.raises(ValueError, match="Cliente Timesheet"):
        manager.crea(descrizione="Cliente assente", minuti=1, id_cliente="cliente-assente")
    with pytest.raises(ValueError, match="Fascicolo Timesheet"):
        manager.crea(descrizione="Fascicolo assente", minuti=1, id_fascicolo="fascicolo-assente")
    for key in ("cliente-uno", "cliente-due"):
        db.conn.execute("INSERT INTO clienti (id) VALUES (?)", (key,))
    db.conn.execute("INSERT INTO fascicoli (id,id_cliente) VALUES (?,?)", ("caso-uno", "cliente-uno"))
    (getattr(db, "raw_conn", None) or db.conn).commit()
    with pytest.raises(ValueError, match="discordanti"):
        manager.crea(descrizione="Collegamento errato", minuti=1, id_fascicolo="caso-uno", id_cliente="cliente-due")
    valid = manager.crea(descrizione="Collegamento corretto", minuti=1, id_fascicolo="caso-uno", id_cliente="cliente-uno")
    assert open_manager().get(valid.id).id_cliente == "cliente-uno"
    assert len(open_manager().tutte()) == 3


def test_identificativo_sql_non_puo_cambiare_con_una_modifica(managers):
    _, open_manager, first, _ = managers
    manager = open_manager()
    with pytest.raises(ValueError, match="identificativo"):
        manager.aggiorna(first, id="nuovo-identificativo")
    assert open_manager().get(first).id == first
    assert open_manager().get("nuovo-identificativo") is None


def test_due_connessioni_indipendenti_conservano_dati_e_conflitti(managers, tmp_path):
    from pct.timesheet_sql_writer import TimesheetConflict
    db, open_manager, first, second = managers
    peer = db.open_peer()
    try:
        left = open_manager()
        right = GestioneTimesheet(str(tmp_path / "entries.json"), studio_db=peer)
        left.get(first)
        right.get(first)
        left.aggiorna(first, note="Conferma connessione uno")
        with pytest.raises(TimesheetConflict):
            right.aggiorna(first, note="Conferma superata connessione due")
        right.aggiorna(second, note="Altra riga connessione due")
        confirmed = open_manager()
        assert confirmed.get(first).note == "Conferma connessione uno"
        assert confirmed.get(second).note == "Altra riga connessione due"
    finally:
        if hasattr(peer, "chiudi"):
            peer.chiudi()

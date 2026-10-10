"""Archivi controllati: guardrail del candidato, non accettazione utente."""
import copy
import json
import os
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from pct.ctu import IncaricoCtu
from pct.ctu_repository import DDL, CtuConflict, CtuRejected, CtuRepository, validate_payload


@pytest.fixture
def database(tmp_path):
    if os.environ.get("CTU_TEST_POSTGRES") == "1":
        import psycopg2
        from pct.storage_postgres import PostgresCompatConnection
        raw = psycopg2.connect(host=os.environ.get("CTU_TEST_PG_HOST", "audit-postgres"),
                               dbname=os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                               user=os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                               password=os.environ["AUDIT_POSTGRES_PASSWORD"])
        db = SimpleNamespace(raw_conn=raw)
        db.conn = PostgresCompatConnection(db)
        for statement in DDL:
            db.conn.execute(statement.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
        conn = db.conn
    else:
        raw = sqlite3.connect(tmp_path / "ctu.db")
        conn = raw
        db = SimpleNamespace(conn=conn)
        CtuRepository(db, "studio", actor_key="avvocato").ensure_schema()
    conn.execute(("CREATE TEMP TABLE" if hasattr(db, "raw_conn") else "CREATE TABLE") +
                 " audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                 "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
    raw.commit()
    yield db
    raw.close()


def fail_audit(database):
    if hasattr(database, "raw_conn"):
        database.conn.execute("ALTER TABLE audit_log ADD CONSTRAINT audit_indisponibile CHECK (azione='ctu.adozione')")
        database.raw_conn.commit()
        from psycopg2 import IntegrityError
        return IntegrityError
    database.conn.execute("CREATE TRIGGER audit_fail BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT,'audit indisponibile'); END")
    database.conn.commit()
    return sqlite3.IntegrityError


def adopted(db, tenant="studio", payload=None):
    repo = CtuRepository(db, tenant, actor_key="avvocato")
    repo.initialize(payload or {}, source_sha256="a" * 64, backup_reference="backup-verificato")
    return repo


def record(**fields):
    return IncaricoCtu(fascicolo_id="F1", nome_ctu="Ing. Bruni", **fields).to_dict()


def command(repo, **intent):
    return repo.command(str(uuid4()), "registrazione", intent, repo.revision)


def test_nessun_bootstrap_nel_costruttore(tmp_path):
    conn = sqlite3.connect(tmp_path / "vuoto.db")
    try:
        repo = CtuRepository(SimpleNamespace(conn=conn), "studio")
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []
        with pytest.raises(sqlite3.OperationalError):
            repo.load()
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []
    finally:
        conn.close()


def test_salvataggio_audit_e_replay(database):
    repo = adopted(database)
    item = record()
    cmd = command(repo, nome="Ing. Bruni", fascicolo="F1")
    result = repo.save({item["id"]: item}, command=cmd)
    assert result == {"record": item, "revision": 1}
    assert repo.replay(cmd) == result
    assert repo.load() == {item["id"]: item}
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 1
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_audit").fetchone()[0] == 2
    assert database.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 2


def test_rifiuto_persistente_non_diventa_scrittura_dopo_retry(database):
    repo = adopted(database)
    cmd = command(repo, nome="Prova")
    with pytest.raises(CtuRejected) as rejected:
        repo.reject(cmd, code="validation", message="Dati non validi.")
    item = record()
    with pytest.raises(CtuRejected) as replayed:
        repo.save({item["id"]: item}, command=cmd)
    assert replayed.value.result == rejected.value.result
    assert repo.load() == {} and repo.revision == 0
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 0
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_command_rejections").fetchone()[0] == 1
    assert database.conn.execute("SELECT COUNT(*) FROM audit_log WHERE esito='RIFIUTATO'").fetchone()[0] == 1


def test_commit_gia_presente_prevale_sul_tentativo_di_rifiuto(database):
    repo = adopted(database)
    cmd, item = command(repo), record()
    saved = repo.save({item["id"]: item}, command=cmd)
    assert repo.reject(cmd, code="conflict", message="Risposta ritardata.") == saved
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_command_rejections").fetchone()[0] == 0


def test_rifiuto_senza_audit_concordante_non_e_un_esito_recuperabile(database):
    repo = adopted(database)
    cmd = command(repo)
    with pytest.raises(CtuRejected):
        repo.reject(cmd, code="validation", message="Dati non validi.")
    database.conn.execute("UPDATE audit_log SET dettagli='{}' WHERE esito='RIFIUTATO'")
    getattr(database, "raw_conn", database.conn).commit()
    with pytest.raises(RuntimeError, match="audit concordante"):
        repo.replay(cmd)
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_command_rejections").fetchone()[0] == 1
    assert repo.load() == {} and repo.revision == 0


def test_rifiuto_non_e_riutilizzabile_da_altro_attore_o_contenuto(database):
    repo = adopted(database)
    cmd = command(repo, nome="Prova")
    with pytest.raises(CtuRejected):
        repo.reject(cmd, code="validation", message="Dati non validi.")
    other = CtuRepository(database, "studio", actor_key="altro")
    with pytest.raises(ValueError, match="attore o contenuto"):
        other.replay(cmd)
    changed = repo.command(cmd["key"], cmd["operation"], {"nome": "Differente"}, 0)
    with pytest.raises(ValueError, match="attore o contenuto"):
        repo.replay(changed)


def test_rifiuto_non_simula_aggiornamento_live_del_registro(database):
    repo = adopted(database)
    database.conn.execute("CREATE TEMP TABLE ctu_live_probe (revision INTEGER)")
    if hasattr(database, "raw_conn"):
        database.conn.execute("CREATE FUNCTION pg_temp.ctu_live_probe() RETURNS trigger LANGUAGE plpgsql AS $$ "
                              "BEGIN INSERT INTO ctu_live_probe VALUES (NEW.revision); RETURN NEW; END $$")
        database.conn.execute("CREATE TRIGGER ctu_live_probe AFTER UPDATE ON ctu_state "
                              "FOR EACH ROW EXECUTE FUNCTION pg_temp.ctu_live_probe()")
    else:
        database.conn.execute("CREATE TEMP TRIGGER ctu_live_probe AFTER UPDATE ON ctu_state "
                              "BEGIN INSERT INTO ctu_live_probe VALUES (NEW.revision); END")
    getattr(database, "raw_conn", database.conn).commit()
    with pytest.raises(CtuRejected):
        repo.reject(command(repo), code="validation", message="Dati non validi.")
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_live_probe").fetchone()[0] == 0
    item = record()
    repo.save({item["id"]: item}, command=command(repo))
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_live_probe").fetchone()[0] == 1


def test_audit_rifiuto_fallito_non_produce_esito_definitivo(database):
    repo = adopted(database)
    error = fail_audit(database)
    cmd = command(repo)
    with pytest.raises(error):
        repo.reject(cmd, code="validation", message="Dati non validi.")
    assert repo.replay(cmd) is None
    assert repo.load() == {} and repo.revision == 0


def test_conflitto_preserva_due_snapshot(database):
    first, second = adopted(database), adopted(database)
    item, other = record(), record()
    first.save({item["id"]: item}, command=command(first))
    with pytest.raises(CtuConflict):
        second.save({other["id"]: other}, command=command(second))
    assert first.load() == {item["id"]: item}
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 1


def test_audit_fallito_annulla_dati_revisione_e_comando(database):
    repo = adopted(database)
    error = fail_audit(database)
    item = record()
    with pytest.raises(error):
        repo.save({item["id"]: item}, command=command(repo))
    assert repo.load() == {} and repo.revision == 0
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 0
    assert database.conn.execute("SELECT COUNT(*) FROM ctu_audit WHERE revision>0").fetchone()[0] == 0


def test_tenant_separati_e_comando_legato_all_attore(database):
    a, b = adopted(database), adopted(database, "altro")
    item = record()
    cmd = command(a)
    a.save({item["id"]: item}, command=cmd)
    assert b.load() == {} and b.revision == 0 and b.replay(cmd) is None
    another_actor = CtuRepository(database, "studio", actor_key="altro-avvocato")
    with pytest.raises(ValueError, match="attore"):
        another_actor.replay(cmd)


def test_replay_non_richiede_che_incarico_sia_immutato(database):
    repo = adopted(database)
    item = record()
    cmd = command(repo)
    first = repo.save({item["id"]: item}, command=cmd)
    changed = {**item, "stato": "GIURAMENTO"}
    repo.save({item["id"]: changed}, command=command(repo, stato="GIURAMENTO"))
    assert repo.replay(cmd) == first
    assert repo.load()[item["id"]]["stato"] == "GIURAMENTO"


def test_identico_comando_da_snapshot_superato_restituisce_primo_esito(database):
    a, b = adopted(database), adopted(database)
    item, duplicate = record(), record()
    cmd = command(a, nome="Ing. Bruni")
    first = a.save({item["id"]: item}, command=cmd)
    assert b.save({duplicate["id"]: duplicate}, command=cmd) == first
    assert b.load() == {item["id"]: item}


def test_replay_discordante_non_crea_secondo_incarico(database):
    repo = adopted(database)
    item = record()
    cmd = command(repo, nome="Ing. Bruni")
    repo.save({item["id"]: item}, command=cmd)
    altered = repo.command(cmd["key"], cmd["operation"], {"nome": "Altro"}, 0)
    with pytest.raises(ValueError, match="contenuto"):
        repo.replay(altered)
    assert len(repo.load()) == 1


def test_no_trasferimento_o_cancellazione(database):
    item = record()
    repo = adopted(database, payload={item["id"]: item})
    with pytest.raises(ValueError, match="eliminato"):
        repo.save({}, command=command(repo))
    with pytest.raises(ValueError, match="trasferire"):
        repo.save({item["id"]: {**item, "fascicolo_id": "ALTRO"}}, command=command(repo))
    assert repo.load() == {item["id"]: item}


@pytest.mark.parametrize("revision", [None, True, -1, 0.5, "0"])
def test_revisione_non_valida(database, revision):
    repo = adopted(database)
    with pytest.raises(ValueError, match="Revisione"):
        repo.command(str(uuid4()), "registrazione", {}, revision)


@pytest.mark.parametrize("field,value", [
    ("id", "altro"), ("campo_sconosciuto", "dato"), ("fascicolo_id", ""),
    ("creato_il", ""), ("stato", "INVENTATO"), ("ruolo_studio", "INVENTATO"),
    ("termine_bozza", "09/10/2026"), ("consulenti_parte", ["riga scartabile"]),
    ("consulenti_parte", [{"campo_sconosciuto": "dato"}]),
    ("compenso_input", {"spese": float("nan")}), ("operazioni", [{"id": "O1", "data": "2026-10-09", "minuti": True}]),
])
def test_fonte_invalida_non_diventa_archivio_vuoto(field, value):
    item = record()
    key = item["id"]
    item[field] = value
    with pytest.raises((ValueError, TypeError)):
        validate_payload({key: item})


def test_adozione_ripetuta_non_sovrascrive_scritture(database):
    repo = adopted(database)
    item = record()
    repo.save({item["id"]: item}, command=command(repo))
    assert adopted(database).load() == {item["id"]: item}
    with pytest.raises(ValueError, match="backup diversi"):
        repo.initialize({}, source_sha256="b" * 64, backup_reference="backup-verificato")


def test_replay_senza_audit_non_dichiara_successo(database):
    repo = adopted(database)
    item = record()
    cmd = command(repo)
    repo.save({item["id"]: item}, command=cmd)
    database.conn.execute("DELETE FROM ctu_audit WHERE revision=1")
    CtuRepository(database, "studio")._finish(database.conn)
    with pytest.raises(RuntimeError, match="audit concordante"):
        repo.replay(cmd)


def test_fonte_storica_roundtrip_non_perde_campi():
    item = record()
    item["consulenti_parte"] = [{"nome": "Geom. Neri", "parte": "Convenuto", "email": "", "telefono": "", "note": ""}]
    assert validate_payload({item["id"]: copy.deepcopy(item)}) == {item["id"]: item}
    assert json.loads(json.dumps(item)) == item


def test_manager_riusa_le_procedure_senza_leggere_la_fonte(database, tmp_path):
    from pct.ctu import GestioneCtu
    source = tmp_path / "incarichi.json"
    source.write_text("fonte non leggibile, non usare", encoding="utf-8")
    repo = adopted(database)
    manager = GestioneCtu(str(source), repository=repo)
    key = str(uuid4())
    result = manager.execute_command("registrazione", {"fascicolo_id": "F1"}, command_key=key, expected_revision=0,
                                     mutate=lambda: manager.nuovo(fascicolo_id="F1", nome_ctu="Ing. Bruni"))
    replay = manager.execute_command("registrazione", {"fascicolo_id": "F1"}, command_key=key, expected_revision=0,
                                     mutate=lambda: pytest.fail("La procedura non va ripetuta"))
    assert result == replay and len(manager.per_fascicolo("F1")) == 1
    assert source.read_text(encoding="utf-8") == "fonte non leggibile, non usare"


def test_manager_non_mantiene_dati_di_un_comando_rifiutato(database, tmp_path):
    from pct.ctu import GestioneCtu
    repo = adopted(database)
    manager = GestioneCtu(str(tmp_path / "non-creare" / "incarichi.json"), repository=repo)
    error = fail_audit(database)
    with pytest.raises(error):
        manager.execute_command("registrazione", {}, command_key=str(uuid4()), expected_revision=0,
                                mutate=lambda: manager.nuovo(fascicolo_id="F1"))
    assert manager.per_fascicolo("F1") == []
    assert not (tmp_path / "non-creare").exists()


def test_manager_impedisce_scritture_senza_comando_prima_di_mutare(database, tmp_path):
    from pct.ctu import GestioneCtu
    item = record()
    repo = adopted(database, payload={item["id"]: item})
    manager = GestioneCtu(str(tmp_path / "non-leggere.json"), repository=repo)
    with pytest.raises(ValueError, match="Comando persistente"):
        manager.aggiungi_ctp(item["id"], nome="Geom. Neri", parte="Convenuto")
    assert manager.get(item["id"]).consulenti_parte == []
    with pytest.raises(ValueError, match="Comando persistente"):
        manager.nuovo(fascicolo_id="F1")
    assert len(manager.per_fascicolo("F1")) == 1


def test_manager_operazioni_e_compenso_nativi(database, tmp_path):
    from pct.ctu import GestioneCtu
    item = record()
    repo = adopted(database, payload={item["id"]: item})
    manager = GestioneCtu(str(tmp_path / "non-leggere.json"), repository=repo)
    def run(operation, mutate):
        return manager.execute_command(operation, {}, command_key=str(uuid4()), expected_revision=repo.revision, mutate=mutate)
    result = run("operazione", lambda: manager.aggiungi_operazione(item["id"], {"data": "2026-10-09", "minuti": 120}))
    assert result["record"]["operazioni"][0]["minuti"] == 120
    run("compenso", lambda: manager.salva_compenso(item["id"], {"modalita": "vacazioni", "iva_perc": 0}))
    assert repo.load()[item["id"]]["compenso_input"] == {"modalita": "vacazioni", "iva_perc": 0}
    operation_id = result["record"]["operazioni"][0]["id"]
    run("rimozione_operazione", lambda: manager.rimuovi_operazione(item["id"], operation_id))
    assert repo.load()[item["id"]]["operazioni"] == []


def test_replay_senza_audit_generale_non_dichiara_successo(database):
    repo = adopted(database)
    item = record()
    cmd = command(repo)
    repo.save({item["id"]: item}, command=cmd)
    database.conn.execute("DELETE FROM audit_log WHERE azione='ctu.registrazione'")
    repo._finish(database.conn)
    with pytest.raises(RuntimeError, match="Audit generale"):
        repo.replay(cmd)

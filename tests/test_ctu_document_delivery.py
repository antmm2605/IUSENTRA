"""Guardrail della consegna documentale, distinti dall’accettazione reale."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from pct.ctu_compensi.onorari import compenso
from pct.ctu import GestioneCtu
from pct.ctu_repository import CtuRepository
from pct.ctu_document_delivery import deliver_liquidation_document
from pct.document_crypto import decrypt_doc, ENC_MAGIC
from pct.fascicoli import Fascicolo, GestioneFascicoli, TipoFascicolo
from tests.test_ctu_sql_repository import adopted, command, database as database, fail_audit, record


@pytest.fixture
def documents(database, tmp_path, monkeypatch):
    monkeypatch.setenv("PCT_DOC_KEY", "chiave-del-solo-test-controllato")
    prefix = "CREATE TEMP TABLE" if hasattr(database, "raw_conn") else "CREATE TABLE"
    database.conn.execute(prefix + " fascicoli (id TEXT PRIMARY KEY,documenti_json TEXT,attivita_json TEXT,"
        "scadenze_json TEXT,profilo_deposito_json TEXT,dati_json TEXT,modificato_il TEXT)")
    fascicolo = Fascicolo(id="F1", numero="PROVA/1", titolo="Procedimento controllato", tipo=TipoFascicolo.CIVILE,
                          numero_rg="123", anno_rg=2026)
    payload = GestioneFascicoli._dati_json_snello(fascicolo.to_dict())
    payload["metadata_esteso_preservato"] = "preservato"
    database.conn.execute("INSERT INTO fascicoli VALUES (?,?,?,?,?,?,?)",
        ("F1", "[]", "[]", "[]", "{}", json.dumps(payload), fascicolo.modificato_il))
    getattr(database, "raw_conn", database.conn).commit()
    return database, adopted(database), tmp_path / "documenti"


def prepare(root, key):
    return lambda conn, saved: deliver_liquidation_document(conn, saved, tenant="studio", actor="avvocato",
        command_key=key, documents_dir=root, calculate=lambda item: compenso({"modalita": "vacazioni", "vacazioni": 2, "iva_perc": 0}))


def test_bozza_cifrata_riscontro_audit_e_replay(documents):
    db, repo, root = documents
    item = record(ruolo_studio="AUSILIARIO")
    cmd = command(repo)
    result = repo.save({item["id"]: item}, command=cmd, delivery=prepare(root, cmd["key"]))
    delivery = result["delivery"]
    content = (root / delivery["path"]).read_bytes()
    assert content.startswith(ENC_MAGIC)
    assert "Istanza di liquidazione" in decrypt_doc(content).decode("utf-8")
    assert "R.G. n. 123/2026" in decrypt_doc(content).decode("utf-8")
    assert "€ 29,36" in decrypt_doc(content).decode("utf-8")
    assert "14,68 euro" not in decrypt_doc(content).decode("utf-8")
    docs = json.loads(db.conn.execute("SELECT documenti_json FROM fascicoli").fetchone()[0])
    assert len(docs) == 1 and docs[0]["id"] == delivery["document_id"]
    payload = json.loads(db.conn.execute("SELECT dati_json FROM fascicoli").fetchone()[0])
    assert payload["metadata_esteso_preservato"] == "preservato"
    assert payload["pagamenti"]["_presidio_documentale"]["document_id"] == delivery["document_id"]
    assert repo.replay(cmd) == result
    assert len(list(root.rglob("*.html"))) == 1


def test_audit_fallito_non_registra_documento(documents):
    db, repo, root = documents
    error = fail_audit(db)
    item = record(ruolo_studio="AUSILIARIO")
    cmd = command(repo)
    with pytest.raises(error):
        repo.save({item["id"]: item}, command=cmd, delivery=prepare(root, cmd["key"]))
    assert db.conn.execute("SELECT documenti_json FROM fascicoli").fetchone()[0] == "[]"
    assert db.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 0


def test_file_preparato_dopo_rollback_riutilizzato_senza_duplicazione(documents):
    db, repo, root = documents
    item = record(ruolo_studio="AUSILIARIO")
    cmd = command(repo)
    delivery = prepare(root, cmd["key"])
    def fail(conn, saved):
        delivery(conn, saved)
        raise RuntimeError("Dopo preparazione")
    with pytest.raises(RuntimeError, match="Dopo preparazione"):
        repo.save({item["id"]: item}, command=cmd, delivery=fail)
    before = {path: path.read_bytes() for path in root.rglob("*.html")}
    assert len(before) == 1
    result = repo.save({item["id"]: item}, command=cmd, delivery=delivery)
    assert {path: path.read_bytes() for path in root.rglob("*.html")} == before
    assert len(json.loads(db.conn.execute("SELECT documenti_json FROM fascicoli").fetchone()[0])) == 1
    assert (root / result["delivery"]["path"]).is_file()


def test_ruolo_parte_non_produce_documento(documents):
    db, repo, root = documents
    item = record()
    cmd = command(repo)
    with pytest.raises(ValueError, match="consulente"):
        repo.save({item["id"]: item}, command=cmd, delivery=prepare(root, cmd["key"]))
    assert not root.exists()
    assert db.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 0


def test_route_riscontro_persistente_e_integrita_file_prima_del_successo(documents):
    from flask import Flask, g
    from web.bootstrap.ctu_compensi_routes import register_ctu_compensi_routes
    db, repo, root = documents
    item = record(ruolo_studio="AUSILIARIO")
    repo.save({item["id"]: item}, command=command(repo))
    app = Flask(__name__)
    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda permission: True)
    core = {
        "get_ctu": lambda: GestioneCtu("NON_LEGGERE.json", repository=CtuRepository(db, "studio", actor_key="avvocato")),
        "get_fascicoli": lambda: SimpleNamespace(get=lambda key: object() if key == "F1" else None, documents_dir=root),
        "audit": lambda *args, **kwargs: pytest.fail("L’audit della consegna è nella transazione SQL"),
    }
    register_ctu_compensi_routes(app, core)
    client = app.test_client()
    body = {"modalita": "vacazioni", "vacazioni": 2, "iva_perc": 0, "commandKey": str(uuid4()), "expectedRevision": 1}
    url = f"/fascicoli/F1/ctu/{item['id']}/istanza"
    first = client.post(url, json=body)
    assert first.status_code == 200 and first.json["ok"] is True
    assert first.json["confirmedCommand"]["committedRevision"] == 2
    assert client.post(url, json=body).json == first.json
    path = next(root.rglob("*.html"))
    content = path.read_bytes()
    path.write_bytes(b"alterato")
    broken = client.post(url, json=body)
    assert broken.status_code == 503 and "confirmedCommand" not in broken.json
    path.write_bytes(content)
    assert client.post(url, json=body).json == first.json
    assert len(json.loads(db.conn.execute("SELECT documenti_json FROM fascicoli").fetchone()[0])) == 1

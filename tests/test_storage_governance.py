from __future__ import annotations

import json
from pathlib import Path

from flask import g

from pct.database import GestioneDatabase
from pct.product_governance import build_migration_program_payload, build_storage_parity_payload
from pct.storage import StudioDB
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.storage_runtime import get_request_studio_db


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_storage_parity_payload_mostra_domini_e_stato_postgres():
    payload = build_storage_parity_payload()

    assert payload["summary"]["domains_total"] >= 10
    assert payload["summary"]["sqlite_rw_ready"] >= 5
    assert payload["summary"]["postgres_rw_ready"] >= 5
    assert payload["summary"]["fallback_ready"] >= 5
    assert any(row["module_id"] == "auth_audit" for row in payload["rows"])
    assert any(row["module_id"] == "telematico" for row in payload["rows"])
    uffici_row = next(row for row in payload["rows"] if row["module_id"] == "uffici_giudiziari_pec")
    assert uffici_row["sqlite_mode"] == "R"
    assert uffici_row["postgres_mode"] == "R"
    assert "PEC di deposito" in " ".join(uffici_row["consistency_checks"])
    assert all("postgres_parity" in row for row in payload["rows"])


def test_schema_uffici_giudiziari_pec_presidia_sqlite_e_postgres():
    sqlite_schema = Path("pct/sql/20260430_uffici_giudiziari_pec.sql").read_text(encoding="utf-8")
    postgres_schema = Path("pct/sql/20260430_uffici_giudiziari_pec_postgres.sql").read_text(encoding="utf-8")

    for schema in (sqlite_schema, postgres_schema):
        assert "CREATE TABLE IF NOT EXISTS uffici_giudiziari" in schema
        assert "CREATE TABLE IF NOT EXISTS indirizzi_telematici" in schema
        assert "uffici_giudiziari_verifiche" in schema
        assert "uffici_giudiziari_variazioni" in schema
        assert "'deposito_pct'" in schema
        assert "'protocollo'" in schema
        assert "'PST'" in schema
        assert "'IPA'" in schema


def test_schema_termini_processuali_presidia_audit_sqlite_e_postgres():
    sqlite_schema = Path("pct/sql/20260430_termini_processuali.sql").read_text(encoding="utf-8")
    postgres_schema = Path("pct/sql/20260430_termini_processuali_postgres.sql").read_text(encoding="utf-8")

    for schema in (sqlite_schema, postgres_schema):
        assert "CREATE TABLE IF NOT EXISTS deadline_templates" in schema
        assert "CREATE TABLE IF NOT EXISTS deadline_audit_logs" in schema
        assert "CREATE TABLE IF NOT EXISTS official_holidays" in schema
        assert "CREATE TABLE IF NOT EXISTS calendar_versions" in schema
        assert "CREATE TABLE IF NOT EXISTS deadline_notification_logs" in schema
        assert "ferial_suspension_policy" in schema
        assert "immutable_hash" in schema
        assert "idx_deadline_audit_deadline" in schema


def test_programma_migrazione_formalizza_fasi_e_fallback():
    payload = build_migration_program_payload()

    assert payload["summary"]["phases_total"] == 4
    assert payload["summary"]["domains_postgres_pending"] >= 1
    assert payload["phases"][0]["phase_id"] == "inventory"
    assert payload["phases"][0]["fallback_rules"]


def test_migrazione_json_verso_sqlite_produce_report_e_consistenza(tmp_path: Path):
    clienti = tmp_path / "clienti" / "anagrafica.json"
    fascicoli = tmp_path / "fascicoli" / "fascicoli.json"
    appuntamenti = tmp_path / "agenda" / "appuntamenti.json"
    scadenze = tmp_path / "scadenziario" / "scadenze.json"
    messaggi = tmp_path / "messaggi" / "storico.json"
    utenti = tmp_path / "auth" / "utenti.json"
    audit = tmp_path / "auth" / "audit.json"
    privacy = tmp_path / "privacy" / "registro.json"
    notifiche = tmp_path / "notifiche" / "log.json"
    backup = tmp_path / "backup" / "registro.json"
    sqlite_path = tmp_path / "studio.db"

    _write_json(
        clienti,
        [
            {
                "id": "cli-1",
                "tipo": "PERSONA_FISICA",
                "nome": "Mario",
                "cognome": "Rossi",
                "codice_fiscale": "RSSMRA80A01H501U",
                "email": "mario.rossi@example.it",
                "recapiti": {"telefono_principale": "3331234567"},
            }
        ],
    )
    _write_json(
        fascicoli,
        [
            {
                "id": "fas-1",
                "numero": "2026/001",
                "titolo": "Ricorso monitorio",
                "id_cliente": "cli-1",
                "tribunale": "Tribunale di Milano",
                "data_apertura": "2026-04-17",
                "documenti": [{"id": "doc-1", "nome_file": "atto.pdf"}],
            }
        ],
    )
    _write_json(
        appuntamenti,
        [
            {
                "id": "app-1",
                "titolo": "Udienza monitoria",
                "data_ora": "2026-04-20T09:30:00",
                "tribunale": "Tribunale di Milano",
            }
        ],
    )
    _write_json(
        scadenze,
        [
            {
                "id": "scad-1",
                "titolo": "Deposito note",
                "data_scadenza": "2026-04-25",
                "id_fascicolo": "fas-1",
                "id_appuntamento": "app-1",
            }
        ],
    )
    _write_json(
        messaggi,
        [
            {
                "id": "msg-1",
                "canale": "EMAIL",
                "stato": "INVIATO",
                "oggetto": "Aggiornamento pratica",
                "corpo": "Testo",
                "id_cliente": "cli-1",
                "id_fascicolo": "fas-1",
            }
        ],
    )
    _write_json(
        utenti,
        [
            {
                "id": "usr-1",
                "username": "amministratore",
                "email": "admin@example.it",
                "nome_completo": "Amministratore Studio",
                "ruolo": "AMMINISTRATORE",
                "password_hash": "hash-fittizio",
                "attivo": True,
            }
        ],
    )
    _write_json(
        audit,
        [
            {
                "id": "audit-1",
                "timestamp": "2026-04-17T10:00:00",
                "username": "amministratore",
                "azione": "auth.login",
                "esito": "OK",
            }
        ],
    )
    _write_json(privacy, [])
    _write_json(notifiche, [])
    _write_json(backup, [])

    migratore = GestioneDatabase(
        {
            "clienti": str(clienti),
            "fascicoli": str(fascicoli),
            "appuntamenti": str(appuntamenti),
            "scadenze": str(scadenze),
            "messaggi": str(messaggi),
            "utenti": str(utenti),
            "audit": str(audit),
            "privacy": str(privacy),
            "notifiche": str(notifiche),
            "backup": str(backup),
        }
    )
    risultato = migratore.migra_verso_sqlite(str(sqlite_path))

    assert risultato.riuscita is True
    assert risultato.errori == []
    assert risultato.record_migrati["clienti"] == 1
    assert risultato.record_migrati["fascicoli"] == 1
    assert risultato.record_migrati["utenti"] == 1

    studio_db = StudioDB.get(str(sqlite_path))
    assert studio_db.conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] >= 1


def test_runtime_storage_crea_sqlite_da_json_senza_fallback_operativo(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "SQLITE_MODE": True})

    legacy_clienti = Path(app.config["CLIENTI_DB"])
    _write_json(
        legacy_clienti,
        [
            {
                "id": "cli-legacy",
                "nome": "Anna",
                "cognome": "Bianchi",
            }
        ],
    )

    with app.test_request_context("/clienti"):
        studio_db = get_request_studio_db(app.config["CLIENTI_DB"])

        assert studio_db is not None
        assert g._storage_runtime_profile.effective_mode == "SQLITE"
        assert g._storage_runtime_profile.uses_sqlite is True
        row = studio_db.conn.execute(
            "SELECT dati_json FROM clienti WHERE id = ?",
            ("cli-legacy",),
        ).fetchone()

    assert row is not None

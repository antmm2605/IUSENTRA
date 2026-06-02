from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from click.testing import CliRunner

from pct.cli import cli
from pct.legal_update_pipeline import build_legal_update_pipeline
from pct.legal_update_repository import (
    LegalUpdateDbConfig,
    LegalUpdateRepository,
    POSTGRES_SCHEMA_LEGAL_UPDATE_PIPELINE,
)
from pct.storage import StudioDB
from pct.storage_migration import migrate_core_storage_to_postgres
from pct.storage_migration_full import _copy_legal_updates_to_postgres, migrate_full_storage_to_sqlite
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normativa_html() -> str:
    return """
    <html><body>
      <article>
        <a href="/atti/decreto-legge-38-2026">Decreto-legge 27 marzo 2026, n. 38 - Credito d'imposta per investimenti</a>
        <p>Pubblicato il 27/03/2026. Il decreto-legge n. 38/2026 aggiorna il regime applicativo del credito d'imposta.</p>
      </article>
    </body></html>
    """


def _postgres_schema_to_sqlite(script: str) -> str:
    return (
        str(script or "")
        .replace("CURRENT_TIMESTAMP::text", "CURRENT_TIMESTAMP")
        .replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY")
        .replace("BIGSERIAL", "INTEGER")
        .replace("BIGINT", "INTEGER")
        .replace("DOUBLE PRECISION", "REAL")
    )


class _SqlitePostgresCompatConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False

    def execute(self, sql: str, params=()):
        statement = str(sql or "").strip()
        if statement.upper().startswith("TRUNCATE TABLE "):
            chunk = statement[len("TRUNCATE TABLE ") :]
            chunk = chunk.split(" RESTART IDENTITY", 1)[0]
            tables = [item.strip() for item in chunk.split(",") if item.strip()]
            self._connection.execute("PRAGMA foreign_keys = OFF")
            try:
                for table_name in tables:
                    self._connection.execute(f"DELETE FROM {table_name}")
            finally:
                self._connection.execute("PRAGMA foreign_keys = ON")
            return self._connection.execute("SELECT 1")
        if "pg_get_serial_sequence" in statement or statement.startswith("SELECT setval("):
            return self._connection.execute("SELECT 1")
        return self._connection.execute(statement, tuple(params or ()))

    def executemany(self, sql: str, seq_of_params):
        return self._connection.executemany(str(sql or ""), list(seq_of_params or []))

    def executescript(self, script: str):
        return self._connection.executescript(_postgres_schema_to_sqlite(script))

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


class _FakePostgresRepositoryBackend:
    target_db_path: Path | None = None

    def __init__(self, dsn: str, schema_path: Path) -> None:
        if self.target_db_path is None:
            raise RuntimeError("Path PostgreSQL di test non configurato.")
        self._db_path = Path(self.target_db_path)
        self._schema_path = Path(schema_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        schema_sql = _postgres_schema_to_sqlite(self._schema_path.read_text(encoding="utf-8"))
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(schema_sql)
            conn.commit()

    def connection(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return _SqlitePostgresCompatConnection(conn)


def _tenant_paths(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "tenant"
    return {
        "CLIENTI_DB": str(root / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(root / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(root / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(root / "fascicoli" / "archivio"),
        "AGENDA_DB": str(root / "agenda" / "appuntamenti.json"),
        "CALENDAR_SYNC_DB": str(root / "agenda" / "calendar_sync.json"),
        "SCADENZIARIO_DB": str(root / "scadenziario" / "scadenze.json"),
        "CONDIVISIONI_DB": str(root / "clienti" / "condivisioni.json"),
        "NOTE_FALDONE_DB": str(root / "clienti" / "note_faldone.json"),
        "MESSAGGI_DB": str(root / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(root / "email" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(root / "email" / "ordinaria.json"),
        "AUTH_DB": str(root / "auth" / "utenti.json"),
        "AUDIT_DB": str(root / "auth" / "audit.json"),
        "PRIVACY_DB": str(root / "privacy" / "registro.json"),
        "NOTIFICHE_LOG": str(root / "notifiche" / "log.json"),
        "SEARCH_INDEX": str(root / "search" / "index.db"),
        "BACKUP_DIR": str(root / "backup"),
        "TIMESHEET_DB": str(root / "timesheet" / "entries.json"),
        "TIME_TRACKING_DB": str(root / "timesheet" / "time_tracking.json"),
        "PREVENTIVI_DB": str(root / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(root / "fatturazione" / "parcelle.json"),
        "PAGAMENTI_DIR": str(root / "pagamenti"),
        "STUDIO_CONFIG": str(root / "config" / "studio.json"),
        "PORTALE_DB": str(root / "portale" / "portali.json"),
        "SOGGETTI_DB": str(root / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(root / "soggetti" / "parti.json"),
        "TEMPLATE_ATTI_DB": str(root / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(root / "template_atti" / "editor_layout.json"),
        "LEGAL_INTELLIGENCE_DB": str(root / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(root / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(root / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(root / "intelligence" / "workspace_intelligence.json"),
        "VALIDATION_RUNS_DB": str(root / "intelligence" / "validation_runs.json"),
        "REDACTION_ASSISTANT_DB": str(root / "intelligence" / "assistente_redazionale.json"),
        "LOCAL_AI_DB": str(root / "intelligence" / "local_ai.json"),
        "WIZARD_PRO_DB": str(root / "wizard_pro" / "sessioni.json"),
        "TELEMATICO_DB": str(root / "telematico" / "runtime.json"),
        "STUDIO_DB": str(root / "studio.db"),
    }


def _seed_core_json(paths: dict[str, str]) -> None:
    _write_json(
        Path(paths["CLIENTI_DB"]),
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
        Path(paths["FASCICOLI_DB"]),
        [
            {
                "id": "fas-1",
                "numero": "2026/001",
                "titolo": "Ricorso monitorio",
                "tipo": "CIVILE",
                "stato": "APERTO",
                "id_cliente": "cli-1",
                "nome_cliente": "Mario Rossi",
                "documenti": [],
                "attivita": [],
                "avanzamento": [],
                "depositi_pct": [],
            }
        ],
    )
    _write_json(
        Path(paths["AGENDA_DB"]),
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
        Path(paths["SCADENZIARIO_DB"]),
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
        Path(paths["AUTH_DB"]),
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
        Path(paths["AUDIT_DB"]),
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
    _write_json(
        Path(paths["TIMESHEET_DB"]),
        [
            {
                "id": "ts-1",
                "id_fascicolo": "fas-1",
                "id_cliente": "cli-1",
                "username": "amministratore",
                "data_attivita": "2026-04-17",
                "descrizione": "Studio fascicolo",
                "minuti": 60,
                "valore_unitario": 100.0,
                "fatturabile": True,
                "stato": "VALIDATO",
                "origine": "seed",
                "note": "",
                "dati_json": {},
            }
        ],
    )
    _write_json(
        Path(paths["TIME_TRACKING_DB"]),
        [
            {
                "id": "timer-1",
                "user_id": "usr-1",
                "username": "amministratore",
                "id_fascicolo": "fas-1",
                "id_cliente": "cli-1",
                "activity_type": "studio",
                "description": "Timer topbar su fascicolo",
                "started_at": "2026-04-17T09:00:00",
                "elapsed_seconds": 1800,
                "status": "stopped",
                "dati_json": {"campo_ui": "valore timer"},
            }
        ],
    )
    _write_json(
        Path(paths["PREVENTIVI_DB"]),
        [
            {
                "id": "prev-1",
                "numero": "2026/001",
                "id_cliente": "cli-1",
                "id_fascicolo": "fas-1",
                "data_emissione": "2026-04-17",
                "data_scadenza": "2026-04-30",
                "oggetto": "Assistenza monitoria",
                "voci": [{"descrizione": "Fase iniziale", "importo": 500.0, "tipo": "ONORARIO"}],
                "stato": "ACCETTATO",
            }
        ],
    )
    _write_json(
        Path(paths["PREVENTIVI_DB"]).with_name("conferimenti.json"),
        [
            {
                "id": "conf-1",
                "numero": "CONF-2026-001",
                "id_cliente": "cli-1",
                "id_preventivo": "prev-1",
                "id_fascicolo": "fas-1",
                "data_incarico": "2026-04-18",
                "oggetto": "Assistenza monitoria",
                "avvocato_referente": "Avv. Demo",
                "stato": "ATTIVO",
                "onorario_pattuito": 500.0,
            }
        ],
    )
    _write_json(
        Path(paths["FATTURAZIONE_DB"]),
        [
            {
                "id": "parc-1",
                "numero": "2026/001",
                "id_cliente": "cli-1",
                "id_fascicolo": "fas-1",
                "data_emissione": "2026-04-18",
                "data_scadenza": "2026-05-18",
                "voci": [{"descrizione": "Parcella iniziale", "quantita": 1.0, "prezzo_unitario": 300.0}],
                "stato": "EMESSA",
            }
        ],
    )
    _write_json(
        Path(paths["PAGAMENTI_DIR"]) / "config.json",
        {
            "stripe": {"abilitato": False},
            "paypal": {"abilitato": False},
            "satispay": {"abilitato": False},
            "sumup": {"abilitato": False},
            "bonifico": {"abilitato": True, "iban": "IT60X0542811101000000123456"},
        },
    )
    _write_json(
        Path(paths["PAGAMENTI_DIR"]) / "transazioni.json",
        [
            {
                "id": "pay-1",
                "token": "tok-1",
                "id_parcella": "parc-1",
                "id_cliente": "cli-1",
                "importo": 300.0,
                "descrizione": "Saldo parcella",
                "stato": "ATTESO",
            }
        ],
    )
    _write_json(
        Path(paths["STUDIO_CONFIG"]),
        {
            "studio": {"nome": "Studio Demo", "avvocato": "Avv. Demo"},
            "sdi": {
                "abilitato": True,
                "modalita": "intermediario",
                "nome_intermediario": "Intermediario FatturaPA",
                "codice_canale": "ABC1234",
            },
        },
    )
    _write_json(Path(paths["MESSAGGI_DB"]), [])
    _write_json(Path(paths["PRIVACY_DB"]), [])
    _write_json(Path(paths["NOTIFICHE_LOG"]), [])
    _write_json(Path(paths["CALENDAR_SYNC_DB"]), {"profiles": [{"id": "cal-1", "provider": "google"}]})
    _write_json(Path(paths["CONDIVISIONI_DB"]), {"link": {"lnk-1": {"id": "lnk-1"}}})
    _write_json(Path(paths["NOTE_FALDONE_DB"]), {"nf-1": {"id": "nf-1", "titolo": "Nota"}})
    _write_json(Path(paths["EMAIL_CASELLA_DB"]), {"account": {"indirizzo": "studio@example.it"}})
    _write_json(Path(paths["EMAIL_ORDINARIA_DB"]), [{"id": "mail-1", "oggetto": "Messaggio"}])
    _write_json(Path(paths["PORTALE_DB"]), {"pst": {"attivo": True}})
    _write_json(Path(paths["SOGGETTI_DB"]), [{"id": "sogg-1", "nome": "Mario Rossi"}])
    _write_json(Path(paths["SOGGETTI_PARTI_DB"]), {"parti": [{"id": "parte-1"}]})
    _write_json(Path(paths["WIZARD_PRO_DB"]), [{"id": "wiz-1"}])
    _write_json(Path(paths["TEMPLATE_ATTI_DB"]), {})
    _write_json(Path(paths["TEMPLATE_ATTI_PREFS_DB"]), {"editor_layout": {}})
    _write_json(Path(paths["LEGAL_INTELLIGENCE_DB"]), {})
    _write_json(Path(paths["NORMATIVE_TABLES_DB"]), [])
    _write_json(Path(paths["GIURISPRUDENZA_DB"]), {})
    _write_json(Path(paths["WORKSPACE_INTELLIGENCE_DB"]), {})
    _write_json(Path(paths["VALIDATION_RUNS_DB"]), {"runs": [{"id": "val-1"}]})
    _write_json(Path(paths["REDACTION_ASSISTANT_DB"]), [])
    _write_json(Path(paths["LOCAL_AI_DB"]), {"runtime": {"enabled": False}})
    if paths.get("TELEMATICO_DB"):
        _write_json(Path(paths["TELEMATICO_DB"]), {"stato": "configurato"})


def test_migrate_full_storage_to_sqlite_copre_repository_estesi(tmp_path: Path):
    paths = _tenant_paths(tmp_path)
    _seed_core_json(paths)

    report = migrate_full_storage_to_sqlite(
        paths=paths,
        tenant_slug="studio-completo",
        database_config=DatabaseConfig(mode=DbMode.SQLITE),
    )

    assert report["success"] is True
    assert report["core"]["record_migrati"]["clienti"] == 1
    assert report["core"]["record_migrati"]["time_tracking"] == 1
    assert report["diff_summary"]["by_domain"]["time_tracking"]["dopo"] == 1
    assert report["repositories"]["template_atti"]["sqlite_stats"]["template_repository"] >= 1
    assert report["repositories"]["legal_intelligence"]["sqlite_stats"]["legal_sources_repository"] >= 1
    assert report["repositories"]["telematico_repository"]["sqlite_stats"]["telematico_sources_repository"] >= 1
    assert report["repositories"]["giurisprudenza"]["sqlite_stats"]["giurisprudenza_sources_repository"] >= 1
    assert report["repositories"]["workspace_intelligence"]["sqlite_stats"]["workspace_intelligence_snapshots"] == 1
    assert report["repositories"]["aggiornamenti_legali"]["sqlite_stats"]["sources"] >= 1
    assert Path(report["report_path"]).exists()


def test_migrate_full_storage_to_sqlite_rigenera_studio_db_senza_unlink(tmp_path: Path):
    paths = _tenant_paths(tmp_path)
    _seed_core_json(paths)
    target = Path(paths["STUDIO_DB"])
    target.parent.mkdir(parents=True, exist_ok=True)
    locked = sqlite3.connect(str(target))
    locked.execute("CREATE TABLE IF NOT EXISTS prova_runtime (id INTEGER PRIMARY KEY, nome TEXT)")
    locked.commit()

    try:
        report = migrate_full_storage_to_sqlite(
            paths=paths,
            tenant_slug="studio-lock-safe",
            database_config=DatabaseConfig(mode=DbMode.SQLITE),
        )
    finally:
        locked.close()

    assert report["success"] is True
    assert Path(paths["STUDIO_DB"]).exists()
    assert report["core"]["record_migrati"]["clienti"] == 1


def test_provision_storage_backend_sqlite_usa_migrazione_completa(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Completo", "studio-completo", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    _seed_core_json(paths)

    payload = tm.provision_storage_backend(studio.slug, migrate_existing=True)

    assert payload["ok"] is True
    assert payload["migrated"] is True
    assert payload["migration_report"]["repositories"]["template_atti"]["ok"] is True
    assert payload["migration_report"]["repositories"]["legal_intelligence"]["ok"] is True
    assert Path(payload["migration_report_path"]).exists()


def test_migrate_full_storage_to_sqlite_blocca_svuotamento_studio_db_operativo(tmp_path: Path):
    paths = _tenant_paths(tmp_path)
    _seed_core_json(paths)

    primo = migrate_full_storage_to_sqlite(
        paths=paths,
        tenant_slug="studio-anti-perdita",
        database_config=DatabaseConfig(mode=DbMode.SQLITE),
    )
    assert primo["success"] is True

    _write_json(Path(paths["CLIENTI_DB"]), [])
    _write_json(Path(paths["FASCICOLI_DB"]), [])

    secondo = migrate_full_storage_to_sqlite(
        paths=paths,
        tenant_slug="studio-anti-perdita",
        database_config=DatabaseConfig(mode=DbMode.SQLITE),
    )

    assert secondo["success"] is False
    assert secondo["core"]["riuscita"] is False
    assert any("Blocco anti-perdita" in err for err in secondo["core"]["errori"])
    conn = sqlite3.connect(paths["STUDIO_DB"])
    try:
        clienti = conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0]
        fascicoli = conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone()[0]
        timers = conn.execute("SELECT COUNT(*) FROM time_tracking_timers").fetchone()[0]
    finally:
        conn.close()
    assert (clienti, fascicoli, timers) == (1, 1, 1)


def test_provision_storage_backend_sqlite_blocca_cutover_su_json_vuoti(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Anti Perdita", "studio-anti-perdita", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    _seed_core_json(paths)

    primo = tm.provision_storage_backend(studio.slug, migrate_existing=True)
    assert primo["ok"] is True
    assert primo["migrated"] is True

    _write_json(Path(paths["CLIENTI_DB"]), [])
    _write_json(Path(paths["FASCICOLI_DB"]), [])

    secondo = tm.provision_storage_backend(studio.slug, migrate_existing=True)

    assert secondo["ok"] is False
    assert secondo["migrated"] is False
    assert secondo["sqlite_ready"] is False
    assert any("Blocco anti-perdita" in err for err in secondo["migration_errors"])
    conn = sqlite3.connect(paths["STUDIO_DB"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone()[0] == 1
    finally:
        conn.close()


def test_audit_sqlite_migration_integrity_script_blocca_delta(tmp_path: Path):
    paths = _tenant_paths(tmp_path)
    _seed_core_json(paths)
    report = migrate_full_storage_to_sqlite(
        paths=paths,
        tenant_slug="studio-audit-script",
        database_config=DatabaseConfig(mode=DbMode.SQLITE),
    )
    assert report["success"] is True

    repo_root = Path(__file__).resolve().parents[1]
    audit_json = tmp_path / "audit-ok.json"
    ok = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "audit_sqlite_migration_integrity.py"),
            "--db",
            paths["STUDIO_DB"],
            "--data-root",
            str(tmp_path / "tenant"),
            "--report-json",
            str(audit_json),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(audit_json.read_text(encoding="utf-8"))["ok"] is True

    conn = sqlite3.connect(paths["STUDIO_DB"])
    try:
        conn.execute("DELETE FROM clienti WHERE id = 'cli-1'")
        conn.commit()
    finally:
        conn.close()

    fail_json = tmp_path / "audit-fail.json"
    fail = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "audit_sqlite_migration_integrity.py"),
            "--db",
            paths["STUDIO_DB"],
            "--data-root",
            str(tmp_path / "tenant"),
            "--report-json",
            str(fail_json),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert fail.returncode == 1
    fail_payload = json.loads(fail_json.read_text(encoding="utf-8"))
    assert fail_payload["ok"] is False
    assert any("clienti" in errore for errore in fail_payload["errors"])


def test_migrate_core_storage_to_postgres_produce_report_consistente(tmp_path: Path, monkeypatch):
    paths = _tenant_paths(tmp_path)
    _seed_core_json(paths)
    target_backend = StudioDB.get(str(tmp_path / "postgres-shadow.db"))

    monkeypatch.setattr(
        "pct.storage_migration.build_postgres_backend",
        lambda database_config: target_backend,
    )

    report = migrate_core_storage_to_postgres(
        paths=paths,
        database_config=DatabaseConfig(
            mode=DbMode.POSTGRESQL,
            host="db.example.local",
            porta=5432,
            db_name="iusentra",
            utente="iusentra",
            password="secret",
            connessione_ok=True,
        ),
        secret_key="test-secret",
        tenant_slug="studio-demo",
    )

    assert report["success"] is True
    assert report["counts"]["sqlite"]["clienti"] == 1
    assert report["counts"]["postgres"]["clienti"] == 1
    assert report["counts"]["postgres"]["fascicoli"] == 1
    assert report["counts"]["postgres"]["preventivi"] == 1
    assert report["counts"]["postgres"]["conferimenti"] == 1
    assert report["counts"]["postgres"]["fatturazione"] == 1
    assert report["counts"]["postgres"]["pagamenti_links"] == 1
    assert report["counts"]["postgres"]["impostazioni"] >= 10
    assert report["counts"]["postgres"]["soggetti"] == 1
    assert report["counts"]["postgres"]["soggetti_parti"] == 1
    assert report["counts"]["sqlite"]["moduli_json_records"] >= 10
    assert report["counts"]["postgres"]["moduli_json_records"] == report["counts"]["sqlite"]["moduli_json_records"]

    moduli_estesi = {
        row[0]
        for row in target_backend.conn.execute(
            "SELECT DISTINCT modulo FROM moduli_json_records"
        ).fetchall()
    }
    assert {"calendar_sync", "email_ordinaria", "telematico"}.issubset(moduli_estesi)
    sdi_row = target_backend.conn.execute(
        "SELECT dati_json FROM settings_config WHERE section='sdi'"
    ).fetchone()
    assert sdi_row is not None
    assert json.loads(sdi_row[0])["codice_canale"] == "ABC1234"
    assert Path(report["report_path"]).exists()


def test_cli_migrate_to_postgres_attiva_cutover(monkeypatch, tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio CLI", "studio-cli", db_config={"mode": "POSTGRESQL"})

    monkeypatch.setattr(
        "pct.tenant.GestioneTenant.provision_storage_backend",
        lambda self, slug, migrate_existing, activate_external=False, secret_key="": {
            "ok": True,
            "activated": activate_external,
            "migrated": migrate_existing,
            "migration_report_path": str(tmp_path / "report.json"),
            "effective_runtime_kind": "postgresql" if activate_external else "json",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "migrate",
            "--to=postgres",
            f"--tenant={studio.slug}",
            f"--registry={registry}",
            "--host=db.example.local",
            "--db-name=iusentra",
            "--user=iusentra",
            "--password=secret",
        ],
    )

    assert result.exit_code == 0
    assert "Cutover storage completato" in result.output


def test_provision_storage_backend_postgres_non_attiva_cutover_se_la_migrazione_fallisce(
    monkeypatch,
    tmp_path: Path,
):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea(
        "Studio Cutover",
        "studio-cutover",
        db_config={
            "mode": "POSTGRESQL",
            "host": "db.example.local",
            "porta": 5432,
            "db_name": "iusentra",
            "utente": "iusentra",
            "password": "secret",
            "connessione_ok": True,
        },
    )

    monkeypatch.setattr(
        "pct.storage_migration_full.migrate_full_storage_to_postgres",
        lambda **kwargs: {
            "success": False,
            "report_path": str(tmp_path / "report-fallito.json"),
            "core": {
                "consistency": {},
                "errori": ["clienti: duplicate key su codice fiscale"],
            },
            "repositories": {},
        },
    )

    payload = tm.provision_storage_backend(
        studio.slug,
        migrate_existing=True,
        activate_external=True,
        secret_key="test-secret",
    )
    studio_live = tm.get(studio.slug)

    assert payload["ok"] is False
    assert payload["migrated"] is False
    assert payload["activated"] is False
    assert payload["migration_report"]["core"]["errori"] == ["clienti: duplicate key su codice fiscale"]
    assert studio_live is not None
    assert studio_live.database.core_runtime_enabled is False
    assert studio_live.database.effective_runtime_kind != "postgresql"


def test_cli_demo_check_racconta_il_prossimo_passo(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Demo", "studio-demo", db_config={"mode": "JSON"})
    paths = tm.percorsi_dati(studio.slug)
    _seed_core_json(paths)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "demo-check",
            f"--tenant={studio.slug}",
            f"--registry={registry}",
        ],
    )

    assert result.exit_code == 0
    assert "Studio: Studio Demo (studio-demo)" in result.output
    assert "Copertura workflow" in result.output
    assert '"ready_steps":' in result.output


def test_copy_legal_updates_to_postgres_migra_news_normativa_e_review(tmp_path: Path, monkeypatch):
    paths = _tenant_paths(tmp_path)
    _seed_core_json(paths)

    pipeline = build_legal_update_pipeline(
        paths["LEGAL_INTELLIGENCE_DB"],
        giurisprudenza_db_path=paths["GIURISPRUDENZA_DB"],
    )
    pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: type(
            "Response",
            (),
            {
                "text": _normativa_html(),
                "content": _normativa_html().encode("utf-8"),
                "status_code": 200,
                "headers": {"content-type": "text/html; charset=utf-8"},
            },
        )(),
        auto_publish=False,
    )
    review = pipeline.repository.list_review_queue(limit=10)[0]
    pipeline.approve_review(int(review["id"]), reviewer="superadmin")
    pipeline.publish_review(int(review["id"]), reviewer="superadmin")

    cfg = LegalUpdateDbConfig.from_anchor(paths["LEGAL_INTELLIGENCE_DB"])
    _FakePostgresRepositoryBackend.target_db_path = tmp_path / "postgres" / "legal_updates.db"
    monkeypatch.setattr(
        "pct.legal_update_repository.PostgresRepositoryBackend",
        _FakePostgresRepositoryBackend,
    )
    postgres_repo = LegalUpdateRepository(
        cfg.db_path,
        json_path=cfg.json_path,
        postgres_dsn="postgresql://test",
        postgres_schema_path=POSTGRES_SCHEMA_LEGAL_UPDATE_PIPELINE,
    )

    copied = _copy_legal_updates_to_postgres(cfg.db_path, postgres_repo)
    sqlite_headline = pipeline.repository.dashboard_snapshot()["headline"]
    sqlite_review_total = len(pipeline.repository.list_review_queue(limit=20))
    postgres_headline = postgres_repo.dashboard_snapshot()["headline"]

    assert copied["sources"] >= 1
    assert copied["source_documents_raw"] == sqlite_headline["raw_documents"]
    assert copied["ai_documents_analysis"] == sqlite_headline["analyses"]
    assert copied["review_queue"] == sqlite_review_total
    assert postgres_headline["sources"] == sqlite_headline["sources"]
    assert postgres_headline["raw_documents"] == sqlite_headline["raw_documents"]
    assert postgres_headline["analyses"] == sqlite_headline["analyses"]
    assert len(postgres_repo.list_review_queue(limit=20)) == sqlite_review_total
    assert postgres_headline["published_news"] == sqlite_headline["published_news"]
    assert postgres_headline["published_normative"] == sqlite_headline["published_normative"]

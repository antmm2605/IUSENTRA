from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pct.cli import cli
from pct.storage import StudioDB
from pct.storage_migration import migrate_core_storage_to_postgres
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _tenant_paths(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "tenant"
    return {
        "CLIENTI_DB": str(root / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(root / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(root / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(root / "fascicoli" / "archivio"),
        "AGENDA_DB": str(root / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(root / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(root / "messaggi" / "storico.json"),
        "AUTH_DB": str(root / "auth" / "utenti.json"),
        "AUDIT_DB": str(root / "auth" / "audit.json"),
        "PRIVACY_DB": str(root / "privacy" / "registro.json"),
        "NOTIFICHE_LOG": str(root / "notifiche" / "log.json"),
        "SEARCH_INDEX": str(root / "search" / "index.db"),
        "BACKUP_DIR": str(root / "backup"),
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
    _write_json(Path(paths["MESSAGGI_DB"]), [])
    _write_json(Path(paths["PRIVACY_DB"]), [])
    _write_json(Path(paths["NOTIFICHE_LOG"]), [])


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

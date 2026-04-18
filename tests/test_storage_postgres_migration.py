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
        "TIMESHEET_DB": str(root / "timesheet" / "entries.json"),
        "PREVENTIVI_DB": str(root / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(root / "fatturazione" / "parcelle.json"),
        "PAGAMENTI_DIR": str(root / "pagamenti"),
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
    assert report["counts"]["postgres"]["preventivi"] == 1
    assert report["counts"]["postgres"]["conferimenti"] == 1
    assert report["counts"]["postgres"]["fatturazione"] == 1
    assert report["counts"]["postgres"]["pagamenti_links"] == 1
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

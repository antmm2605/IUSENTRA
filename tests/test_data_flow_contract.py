import json
import sqlite3
from pathlib import Path

from pct.data_flow_contract import (
    audit_data_flow_contract,
    required_json_modules,
    required_menu_items,
    required_postgres_tables,
    required_react_routes,
    required_sqlite_tables,
)
from pct.database import GestioneDatabase
from pct.tenant import GestioneTenant
from scripts.audit_data_flow_contract import _audit_tenant, _json_sources


def _write_json(path: str, payload) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_data_flow_contract_copre_menu_operativo_storage_e_route_react():
    report = audit_data_flow_contract()

    assert report["ok"], report["errors"]
    areas = report["areas"]
    for area in (
        "panoramica",
        "regia_operativa",
        "ricerca_studio",
        "agenda",
        "fascicoli",
        "clienti_anagrafiche",
        "soggetti_parti",
        "comunicazioni",
        "scadenze_termini",
        "servizi_telematici",
        "studio",
        "sito_studio",
        "impostazioni",
        "amministrazione",
        "topbar",
    ):
        assert area in areas

    assert "/fascicoli/:id/deposito/prepara" in required_react_routes()
    assert "/admin/database" in required_react_routes()
    assert "/legal-skills" in required_react_routes()
    assert "/workflow-agents" in required_react_routes()
    assert "/guida/firma-digitale" in required_react_routes()
    assert "/importa-pratiche-studio-telematico" in required_react_routes()
    assert "/database" not in required_react_routes()
    assert "messaggi" in required_sqlite_tables()
    assert "messaggi" in required_postgres_tables()
    assert "backup_config" in required_postgres_tables()
    assert "backup_config" in required_json_modules()
    assert "Voce Studio" in areas["topbar"]["topbar_hooks"]
    assert "Assistenza remota" in areas["topbar"]["topbar_hooks"]

    menu = required_menu_items()
    assert menu["Calendario"] == {"/agenda"}
    assert menu["Nuovo Appuntamento"] == {"/agenda/nuovo"}
    assert menu["Timesheet"] == {"/timesheet"}
    assert menu["Email PEC"] == {"/email"}
    assert menu["PEC"] == {"/email"}
    assert menu["Notifiche legali"] == {"/notifiche-legali"}
    assert menu["L.53"] == {"/notifiche-legali"}
    assert menu["Email ordinaria"] == {"/email-ordinaria"}
    assert menu["SMTP"] == {"/email-ordinaria"}
    assert menu["Nuovo SMS/WA"] == {"/messaggi/nuovo"}
    assert "/clienti" in menu["Anagrafica"]
    assert "/soggetti" in menu["Anagrafica"]
    assert menu["Legal Skills"] == {"/legal-skills"}
    assert menu["Regia Agentica"] == {"/workflow-agents"}
    assert menu["Guida firma digitale"] == {"/guida/firma-digitale"}
    assert menu["Importa pratiche da Studio Telematico"] == {
        "/importa-pratiche-studio-telematico"
    }

    for key, area in areas.items():
        if area["menu_items"]:
            assert area["tenant_path_keys"], key
            assert (
                area["sqlite_tables"]
                or area["postgres_tables"]
                or area["json_modules"]
                or area["external_repositories"]
            ), key


def test_data_flow_contract_indicizza_json_nello_studio_db_tenant(tmp_path: Path):
    manager = GestioneTenant(str(tmp_path / "tenants.json"))
    manager.crea("Studio prova", "studio-prova")
    paths = manager.percorsi_dati(
        "studio-prova",
        reconcile_aliases=False,
        ensure_baseline=False,
    )
    sources = _json_sources(paths)

    _write_json(
        sources["messaggi"],
        [{"id": "msg-1", "oggetto": "Comunicazione", "id_cliente": "cli-1"}],
    )
    _write_json(
        sources["privacy"],
        [{"id": "privacy-1", "nome": "Registro clienti"}],
    )
    _write_json(
        sources["backup_config"],
        {"retention": 30, "cifratura": True},
    )

    sync_report = GestioneDatabase(sources).sincronizza_moduli_json_sqlite(
        paths["STUDIO_DB"],
        include_structured=True,
    )
    assert sync_report["ok"], sync_report["errors"]

    audit = audit_data_flow_contract(
        paths=paths,
        tenant_root=Path(paths["STUDIO_DB"]).parent,
    )
    assert audit["ok"], audit["errors"]

    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        modules = {
            row[0]
            for row in conn.execute(
                "SELECT nome FROM moduli_dati WHERE nome IN ('messaggi', 'privacy', 'backup_config')"
            ).fetchall()
        }
        records = conn.execute(
            "SELECT COUNT(*) FROM moduli_json_records WHERE modulo IN ('messaggi', 'privacy', 'backup_config')"
        ).fetchone()[0]

    assert modules == {"messaggi", "privacy", "backup_config"}
    assert records >= 3


def test_repair_json_mirror_resetta_solo_mirror_rigenerabile(tmp_path: Path):
    manager = GestioneTenant(str(tmp_path / "tenants.json"))
    manager.crea("Studio prova", "studio-prova")
    paths = manager.percorsi_dati(
        "studio-prova",
        reconcile_aliases=False,
        ensure_baseline=False,
    )
    sources = _json_sources(paths)
    _write_json(
        sources["messaggi"],
        [{"id": "msg-1", "oggetto": "Comunicazione", "id_cliente": "cli-1"}],
    )

    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS moduli_dati (
                nome TEXT PRIMARY KEY,
                percorso TEXT NOT NULL,
                storage_kind TEXT NOT NULL DEFAULT 'json',
                inizializzato_il TEXT,
                payload_json TEXT DEFAULT '{}'
            )
            """
        )
        conn.execute("DROP TABLE IF EXISTS moduli_json_records")
        conn.execute("CREATE TABLE moduli_json_records (colonna_non_valida TEXT)")
        conn.commit()

    report = _audit_tenant(
        manager,
        "studio-prova",
        repair_json_mirror=True,
        repair_search_index=False,
    )
    repair = report["repair_json_mirror"] or {}
    mirror = repair.get("mirror") or {}
    reset = mirror.get("reset") or {}

    assert repair["ok"], repair
    assert report["sqlite_diagnostics"]["opened"] is True
    assert report["sqlite_diagnostics"]["json_mirror"]["readable"] is True
    assert mirror["reset_executed"] is True
    assert "colonne mancanti" in mirror["before"]["reason"]
    assert reset["protected_data"] == [
        "clienti",
        "fascicoli",
        "agenda",
        "scadenze",
        "documenti",
        "comunicazioni",
    ]

    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM moduli_json_records WHERE modulo = ?",
            ("messaggi",),
        ).fetchone()[0]
    assert count == 1


def test_repair_search_index_ricrea_solo_cache_fts(tmp_path: Path):
    manager = GestioneTenant(str(tmp_path / "tenants.json"))
    manager.crea("Studio prova", "studio-prova")
    paths = manager.percorsi_dati(
        "studio-prova",
        reconcile_aliases=False,
        ensure_baseline=False,
    )

    source_search = Path(paths["SEARCH_INDEX"])
    source_search.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_search) as conn:
        conn.execute(
            """
            CREATE VIRTUAL TABLE documenti USING fts5(
                tipo UNINDEXED,
                entity_id UNINDEXED,
                titolo,
                corpo,
                meta UNINDEXED
            )
            """
        )
        conn.execute(
            """
            INSERT INTO documenti(tipo, entity_id, titolo, corpo, meta)
            VALUES ('fascicolo','f-1','RG 1/2026','Cliente Rossi','{}')
            """
        )
        conn.execute("CREATE TABLE meta_indice (chiave TEXT PRIMARY KEY, valore TEXT)")
        conn.execute("INSERT INTO meta_indice VALUES ('ultimo','2026-06-14')")
        conn.execute(
            """
            CREATE TABLE ocr_cache (
                hash_sha256 TEXT PRIMARY KEY,
                testo TEXT,
                elaborato_il TEXT
            )
            """
        )
        conn.commit()

    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        conn.execute("DROP TABLE IF EXISTS search_documenti")
        conn.execute("CREATE TABLE search_documenti (colonna_non_valida TEXT)")
        conn.commit()

    report = _audit_tenant(
        manager,
        "studio-prova",
        repair_json_mirror=False,
        repair_search_index=True,
    )
    repair = report["repair_search_index"] or {}

    assert repair["ok"], repair
    assert repair["reset_executed"] is True
    assert repair["before"]["schema_ok"] is False
    assert repair["source"]["documenti"] == 1
    assert report["sqlite_diagnostics"]["search_index"]["readable"] is True

    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        count = conn.execute("SELECT COUNT(*) FROM search_documenti").fetchone()[0]
    assert count == 1


def test_topbar_operativa_resta_collegata_a_dati_reali_e_testi_professionali():
    topbar = Path("frontend/src/components/layout/TopBar.tsx").read_text(encoding="utf-8")
    create_menu = Path("frontend/src/components/layout/TopBarCreateMenu.tsx").read_text(encoding="utf-8")
    topbar_api = Path("frontend/src/services/topbarApi.ts").read_text(encoding="utf-8")

    assert "StudioVoiceAssistant" in topbar
    assert "/support/studio/sessione" in topbar
    assert "TopBarTodayMenu" in topbar
    assert "TopBarNotifications" in topbar
    assert "TopBarDeadlines" in topbar
    assert "TopBarRecentItems" in topbar
    assert "TopBarCreateMenu" in topbar
    assert "Intl.DateTimeFormat('it-IT'" in topbar
    assert "fetchTodaySummary" in topbar_api
    assert "fetchNotifications" in topbar_api
    assert "fetchQuickDeadlines" in topbar_api
    assert "fetchRecentItems" in topbar_api
    assert "trackRecentSearch" in topbar_api
    assert "/api/time-tracking/active" in topbar_api
    assert "/api/notifications" in topbar_api
    assert "/api/deadlines/quick-summary" in topbar_api
    assert "/api/recent" in topbar_api
    assert "/api/recent/search" in topbar_api
    assert "Nuova attività" in create_menu
    assert "già collegata" in create_menu

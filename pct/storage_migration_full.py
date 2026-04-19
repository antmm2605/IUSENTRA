"""Migrazione completa tenant-aware: JSON -> SQL locale -> PostgreSQL.

Questo modulo porta in esecuzione reale il percorso di migrazione dello
storage, coprendo:

- core unificato su ``studio.db`` (clienti, fascicoli, agenda, scadenze, ecc.)
- repository SQL dedicati per template, legal intelligence, telematico,
  giurisprudenza, workspace intelligence
- legal updates su repository SQL locale e PostgreSQL
- coverage AI su schema SQL reale locale e PostgreSQL quando disponibile

La migrazione produce sempre un report JSON persistito nella directory
``backup/`` del tenant.
"""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.agenda import Agenda
from pct.calendar_sync import GestioneCalendarSync
from pct.core_storage_backend import build_postgres_backend
from pct.database import GestioneDatabase
from pct.fascicoli import GestioneFascicoli
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.giurisprudenza_repository import (
    GestioneRepositoryGiurisprudenza,
    derive_giurisprudenza_repository_db_path,
)
from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository
from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig, SQLiteCoverageRepository
from pct.legal_intelligence import GestioneLegalIntelligence
from pct.legal_intelligence_repository import (
    GestioneLegalIntelligenceRepository,
    derive_legal_intelligence_repository_db_path,
)
from pct.legal_update_pipeline import build_legal_update_pipeline
from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository
from pct.postgres_runtime_support import database_config_to_dsn
from pct.scadenziario import GestioneScadenziario
from pct.storage import StudioDB
from pct.storage_migration import migrate_core_storage_to_postgres
from pct.telematico_repository import GestioneTelematicoRepository
from pct.telematico_repository import derive_telematico_repository_db_path
from pct.telematico_repository import derive_telematico_sources_json_path
from pct.template_atti import GestionePreferenzeTemplateAtti, GestioneTemplateAtti
from pct.template_atti_repository import (
    GestioneTemplateRepository,
    derive_template_repository_db_path,
)
from pct.tenant import DatabaseConfig, DbMode
from pct.workspace_intelligence_repository import (
    WorkspaceIntelligenceRepository,
    derive_workspace_intelligence_repository_db_path,
)
from pct.workspace_intelligente import WorkspaceIntelligenteService


_CORE_TABLES = {
    "clienti": "clienti",
    "fascicoli": "fascicoli",
    "appuntamenti": "appuntamenti",
    "scadenze": "scadenze",
    "timesheet": "timesheet_entries",
    "preventivi": "preventivi_records",
    "conferimenti": "conferimenti_records",
    "fatturazione": "parcelle",
    "pagamenti_links": "payment_links",
    "pagamenti_config": "payment_config",
    "messaggi": "messaggi",
    "utenti": "utenti",
    "audit": "audit_log",
    "privacy": "privacy_trattamenti",
    "notifiche": "notifiche_log",
    "backup": "backup_records",
}

_LEGAL_UPDATE_COPY_TABLES = (
    ("legal_update_meta", "legal_update_meta"),
    ("matters", "matters"),
    ("sources", "sources"),
    ("source_documents_raw", "source_documents_raw"),
    ("source_documents_normalized", "source_documents_normalized"),
    ("ai_documents_analysis", "ai_documents_analysis"),
    ("normative", "normative"),
    ("normative_versions", "normative_versions"),
    ("normative_relations", "normative_relations"),
    ("jurisprudence", "jurisprudence"),
    ("prassi", "prassi"),
    ("news", "news"),
    ("review_queue", "review_queue"),
    ("audit_log", "legal_update_audit_log"),
)

_LEGAL_UPDATE_ID_TABLES = {
    "sources",
    "source_documents_raw",
    "source_documents_normalized",
    "matters",
    "ai_documents_analysis",
    "normative",
    "normative_versions",
    "normative_relations",
    "jurisprudence",
    "prassi",
    "news",
    "review_queue",
    "legal_update_audit_log",
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _json_record_count(path: str) -> int:
    file_path = Path(str(path or "").strip())
    if not file_path.exists() or file_path.suffix.lower() != ".json":
        return 0
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 1 if payload else 0


def _count_files(path: str, suffixes: tuple[str, ...] = ()) -> int:
    root = Path(str(path or "").strip())
    if not root.exists():
        return 0
    if root.is_file():
        if suffixes and root.suffix.lower() not in suffixes:
            return 0
        return 1
    total = 0
    for child in root.rglob("*"):
        if not child.is_file():
            continue
        if suffixes and child.suffix.lower() not in suffixes:
            continue
        total += 1
    return total


def _sqlite_table_count(db_path: str, table_name: str) -> int:
    target = Path(str(db_path or "").strip())
    if not target.exists():
        return 0
    try:
        with sqlite3.connect(str(target)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            ).fetchone()
            if not row or int(row[0] or 0) == 0:
                return 0
            result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    except sqlite3.Error:
        return 0
    return int((result or [0])[0] or 0)


def _postgres_table_count(database_config: Any, table_name: str) -> int:
    try:
        backend = build_postgres_backend(database_config)
    except Exception:
        return 0
    if backend is None:
        return 0
    try:
        row = backend.conn.execute("SELECT to_regclass(?) AS table_name", (table_name,)).fetchone()
        table_ref = None
        if isinstance(row, dict):
            table_ref = row.get("table_name")
        elif row:
            table_ref = row[0]
        if not table_ref:
            return 0
        result = backend.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    except Exception:
        return 0
    if isinstance(result, dict):
        return int(next(iter(result.values()), 0) or 0)
    return int((result or [0])[0] or 0)


def _postgres_is_online(database_config: Any | None) -> bool:
    if database_config is None:
        return False
    try:
        backend = build_postgres_backend(database_config)
    except Exception:
        return False
    return backend is not None


def _postgres_candidate_config(database_config: Any | None) -> DatabaseConfig | None:
    if database_config is None:
        return None
    if isinstance(database_config, DatabaseConfig):
        cfg = DatabaseConfig.from_dict(database_config.to_dict())
    elif hasattr(database_config, "to_dict"):
        try:
            cfg = DatabaseConfig.from_dict(database_config.to_dict())
        except Exception:
            return None
    else:
        cfg = DatabaseConfig.from_dict(database_config)
    host = str(cfg.host or "").strip()
    db_name = str(cfg.db_name or "").strip()
    user = str(cfg.utente or "").strip()
    if not all((host, db_name, user)):
        return None
    cfg.mode = DbMode.POSTGRESQL
    return cfg


def _query_sqlite_counts(db_path: str, queries: dict[str, str]) -> dict[str, int]:
    target = Path(str(db_path or "").strip())
    if not target.exists():
        return {key: 0 for key in queries}
    output = {key: 0 for key in queries}
    try:
        with sqlite3.connect(str(target)) as conn:
            conn.row_factory = sqlite3.Row
            for key, sql in queries.items():
                try:
                    row = conn.execute(sql).fetchone()
                except sqlite3.Error:
                    row = None
                if row is None:
                    output[key] = 0
                elif isinstance(row, sqlite3.Row):
                    output[key] = int(row[0] or 0)
                else:
                    output[key] = int((row or [0])[0] or 0)
    except sqlite3.Error:
        return output
    return output


def _sqlite_table_columns(db_path: str, table_name: str) -> list[str]:
    target = Path(str(db_path or "").strip())
    if not target.exists():
        return []
    try:
        with sqlite3.connect(str(target)) as conn:
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.Error:
        return []
    return [str(row[1]) for row in rows if row and row[1]]


def _sqlite_table_rows(db_path: str, table_name: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    columns = _sqlite_table_columns(db_path, table_name)
    if not columns:
        return [], []
    order_column = "id" if "id" in columns else columns[0]
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM {table_name} ORDER BY {order_column}"
        ).fetchall()
    payload_rows = [tuple(row[column] for column in columns) for row in rows]
    return columns, payload_rows


def _reset_postgres_sequence(conn: Any, table_name: str) -> None:
    if table_name not in _LEGAL_UPDATE_ID_TABLES:
        return
    row = conn.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()
    total = int((row or {}).get("total") or 0) if isinstance(row, dict) else int((row or [0])[0] or 0)
    if total:
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
            f"(SELECT MAX(id) FROM {table_name}), true)"
        )
    else:
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), 1, false)"
        )


def _copy_legal_updates_to_postgres(db_path: str, postgres_repo: LegalUpdateRepository) -> dict[str, int]:
    counts: dict[str, int] = {}
    with postgres_repo._connect() as conn:  # noqa: SLF001 - migrazione interna controllata
        conn.execute(
            "TRUNCATE TABLE "
            + ", ".join(target_table for _, target_table in reversed(_LEGAL_UPDATE_COPY_TABLES))
            + " RESTART IDENTITY CASCADE"
        )
        for source_table, target_table in _LEGAL_UPDATE_COPY_TABLES:
            columns, rows = _sqlite_table_rows(db_path, source_table)
            counts[source_table] = len(rows)
            if not columns or not rows:
                _reset_postgres_sequence(conn, target_table)
                continue
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(
                f"INSERT INTO {target_table} ({', '.join(columns)}) VALUES ({placeholders})",
                rows,
            )
            _reset_postgres_sequence(conn, target_table)
        conn.commit()
    return counts


def _base_sqlite_sources(paths: dict[str, str]) -> dict[str, str]:
    return {
        "clienti": paths.get("CLIENTI_DB", ""),
        "fascicoli": paths.get("FASCICOLI_DB", ""),
        "appuntamenti": paths.get("AGENDA_DB", ""),
        "scadenze": paths.get("SCADENZIARIO_DB", ""),
        "timesheet": paths.get("TIMESHEET_DB", ""),
        "messaggi": paths.get("MESSAGGI_DB", ""),
        "utenti": paths.get("AUTH_DB", ""),
        "audit": paths.get("AUDIT_DB", ""),
        "privacy": paths.get("PRIVACY_DB", ""),
        "notifiche": paths.get("NOTIFICHE_LOG", ""),
        "backup": str(Path(paths.get("BACKUP_DIR", "./backup")) / "registro.json"),
        "search_index": paths.get("SEARCH_INDEX", ""),
    }


def _extended_sqlite_sources(paths: dict[str, str]) -> dict[str, str]:
    sources = _base_sqlite_sources(paths)
    preventivi_path = str(paths.get("PREVENTIVI_DB", "") or "").strip()
    pagamenti_dir = str(paths.get("PAGAMENTI_DIR", "") or "").strip()
    sources.update(
        {
            "preventivi": preventivi_path,
            "conferimenti": str(Path(preventivi_path).with_name("conferimenti.json")) if preventivi_path else "",
            "fatturazione": paths.get("FATTURAZIONE_DB", ""),
            "pagamenti_links": str(Path(pagamenti_dir) / "transazioni.json") if pagamenti_dir else "",
            "pagamenti_config": str(Path(pagamenti_dir) / "config.json") if pagamenti_dir else "",
        }
    )
    return sources


def _migration_issue_mode(message: str) -> dict[str, str]:
    lowered = str(message or "").strip().lower()
    if "non trovato" in lowered:
        return {
            "code": "RIFERIMENTO_ORFANO",
            "title": "Riferimento legacy non risolto",
            "recovery": "Correggi o ricollega il riferimento al record mancante, poi rilancia il cutover dello stesso tenant.",
        }
    if "connessione postgresql" in lowered or "connection refused" in lowered or "could not connect" in lowered:
        return {
            "code": "POSTGRES_NON_RAGGIUNGIBILE",
            "title": "Connessione PostgreSQL non disponibile",
            "recovery": "Verifica host, porta, database, utente, password e SSL del tenant prima di ripetere la migrazione.",
        }
    if "database is locked" in lowered or " locked" in lowered:
        return {
            "code": "SQLITE_LOCKED",
            "title": "Database SQL locale bloccato",
            "recovery": "Chiudi i processi che tengono aperto studio.db e rilancia la migrazione dopo il riavvio del runtime.",
        }
    if "duplicate key" in lowered or "unique constraint failed" in lowered:
        return {
            "code": "CHIAVE_DUPLICATA",
            "title": "Chiavi duplicate nella sorgente",
            "recovery": "Ripulisci i duplicati sugli identificativi del dominio indicato e riesegui il cutover.",
        }
    if "no such table" in lowered or "undefinedtable" in lowered or "does not exist" in lowered:
        return {
            "code": "SCHEMA_SQL_MANCANTE",
            "title": "Schema SQL non allineato",
            "recovery": "Applica o ricrea lo schema SQL del dominio interessato prima di riprovare la migrazione.",
        }
    if "permission denied" in lowered or "access denied" in lowered or "forbidden" in lowered:
        return {
            "code": "PERMESSI_INSUFFICIENTI",
            "title": "Permessi insufficienti su storage o database",
            "recovery": "Verifica i permessi dell'utente applicativo e della directory tenant-aware, poi rilancia il flusso.",
        }
    return {
        "code": "CONSISTENZA_DA_VERIFICARE",
        "title": "Consistenza dati da verificare",
        "recovery": "Apri il report completo, correggi il dominio evidenziato e rilancia la migrazione dello stesso studio.",
    }


def _build_diff_summary(*, inventory: dict[str, Any], target: str) -> dict[str, Any]:
    source_key = "json_count" if target == "sqlite" else "sqlite_count"
    destination_key = "sqlite_count" if target == "sqlite" else "postgres_count"
    source_label = "JSON legacy" if target == "sqlite" else "SQL locale"
    destination_label = "SQL locale" if target == "sqlite" else "PostgreSQL"
    rows: list[dict[str, Any]] = []
    for domain in inventory.get("domains", []):
        kind = str(domain.get("storage_kind") or "")
        if kind == "filesystem":
            continue
        source_count = int(domain.get(source_key) or 0)
        destination_count = int(domain.get(destination_key) or 0)
        delta = destination_count - source_count
        ok = source_count == destination_count
        rows.append(
            {
                "code": str(domain.get("code") or ""),
                "title": str(domain.get("title") or ""),
                "source_label": source_label,
                "source_count": source_count,
                "destination_label": destination_label,
                "destination_count": destination_count,
                "delta": delta,
                "status": "success" if ok else "warning",
                "status_label": "Allineato" if ok else "Delta da presidiare",
                "note": str(domain.get("note") or ""),
            }
        )
    return {
        "rows": rows,
        "summary": {
            "rows_total": len(rows),
            "matched": sum(1 for row in rows if row["status"] == "success"),
            "mismatched": sum(1 for row in rows if row["status"] != "success"),
            "source_label": source_label,
            "destination_label": destination_label,
        },
    }


def _build_precheck_snapshot(*, inventory: dict[str, Any], target: str, paths: dict[str, str]) -> dict[str, Any]:
    source_label = "JSON legacy" if target == "sqlite" else "SQL locale"
    destination_label = "SQL locale" if target == "sqlite" else "PostgreSQL"
    return {
        "generated_at": str(inventory.get("generated_at") or _now_iso()),
        "source_label": source_label,
        "destination_label": destination_label,
        "domains_total": len(list(inventory.get("domains") or [])),
        "backup_dir": str(paths.get("BACKUP_DIR", "")),
        "filesystem_preserved": True,
        "note": (
            "Snapshot pre-migrazione costruito dal precheck tenant-aware prima del cutover."
        ),
    }


def _build_dirty_tenant_findings(
    *,
    errors: list[str],
    warnings: list[str],
    diff_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for message in errors:
        mode = _migration_issue_mode(message)
        findings.append(
            {
                "severity": "danger",
                "code": mode["code"],
                "title": mode["title"],
                "detail": str(message),
                "recovery": mode["recovery"],
            }
        )
    for message in warnings:
        mode = _migration_issue_mode(message)
        findings.append(
            {
                "severity": "warning",
                "code": mode["code"],
                "title": mode["title"],
                "detail": str(message),
                "recovery": mode["recovery"],
            }
        )
    for row in diff_summary.get("rows", []):
        if row.get("status") == "success":
            continue
        findings.append(
            {
                "severity": "warning",
                "code": "DELTA_PRE_POST",
                "title": "Differenza tra sorgente e destinazione",
                "detail": (
                    f"{row['title']}: {row['source_label']}={row['source_count']} | "
                    f"{row['destination_label']}={row['destination_count']}."
                ),
                "recovery": "Verifica il dominio con delta, correggi la sorgente o il repository e riesegui il cutover.",
            }
        )
    unique_findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in findings:
        key = (str(item.get("code") or ""), str(item.get("detail") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique_findings.append(item)
    return unique_findings


def _build_operation_log(
    *,
    target: str,
    success: bool,
    core_success: bool,
    diff_summary: dict[str, Any],
    repository_rows: int,
    repository_errors: list[str] | None = None,
) -> list[dict[str, Any]]:
    repo_errors = list(repository_errors or [])
    mismatched = int((diff_summary.get("summary") or {}).get("mismatched") or 0)
    return [
        {
            "step": "precheck_snapshot",
            "label": "Precheck e snapshot",
            "status": "success",
            "detail": "Baseline del tenant congelata prima della migrazione con inventario domini e backup di riferimento.",
        },
        {
            "step": "core_transfer",
            "label": "Trasferimento domini core",
            "status": "success" if core_success else "danger",
            "detail": "Migrazione effettiva di clienti, fascicoli, agenda, scadenze e domini strutturati principali.",
        },
        {
            "step": "repository_sync",
            "label": "Sincronizzazione repository SQL",
            "status": "warning" if repo_errors else "success",
            "detail": (
                f"Repository strutturati elaborati: {repository_rows}. "
                + ("Sono presenti errori da correggere." if repo_errors else "Nessun errore strutturato nel sync.")
            ),
        },
        {
            "step": "diff_check",
            "label": "Diff pre/post e consistenza",
            "status": "warning" if mismatched else "success",
            "detail": (
                f"Domini con delta residuo: {mismatched}. "
                + ("Serve correzione prima del cutover definitivo." if mismatched else "Conteggi allineati nel report corrente.")
            ),
        },
        {
            "step": "cutover_ready",
            "label": "Prontezza al cutover",
            "status": "success" if success else "warning",
            "detail": (
                f"Target {target} {'pronto' if success else 'non ancora pronto'} secondo il report reale di migrazione."
            ),
        },
    ]


def _build_rollback_posture(*, target: str, success: bool) -> dict[str, Any]:
    if target == "postgresql":
        return {
            "status": "success" if success else "warning",
            "label": "Rollback tenant-aware disponibile",
            "detail": (
                "Il cutover PostgreSQL passa dallo staging SQL locale e non sposta i documenti su filesystem. "
                "Se smoke test o consistenza falliscono, il tenant puo' tornare al backend precedente con rollback controllato."
            ),
            "steps": [
                "Conserva il report di migrazione e il backup del tenant come prova del punto di ripristino.",
                "Riporta il tenant al backend strutturato precedente e verifica subito login, clienti, fascicoli, agenda e audit.",
                "Non spostare manualmente documenti o upload: restano filesystem-first e non vanno riallineati durante il rollback.",
            ],
        }
    return {
        "status": "success" if success else "warning",
        "label": "Recovery locale disponibile",
        "detail": (
            "La migrazione verso SQL locale lascia intatti JSON legacy, backup tenant-aware e documenti su filesystem. "
            "Il ripristino puo' usare il report corrente e le sorgenti precedenti senza perdita dei file."
        ),
        "steps": [
            "Conserva il report nel backup del tenant come baseline del passaggio.",
            "Se serve ripristino, usa le sorgenti JSON legacy e il backup dello studio per riallineare lo stato precedente.",
            "Dopo il recovery rilancia il precheck e correggi i domini con warning o delta prima di un nuovo cutover.",
        ],
    }


def _write_report(paths: dict[str, str], tenant_slug: str, target_label: str, report: dict[str, Any]) -> str:
    backup_dir = Path(paths.get("BACKUP_DIR", "./backup"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = backup_dir / f"storage_migration_full_{target_label}_{tenant_slug}_{stamp}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


def _workspace_service(paths: dict[str, str], *, postgres_dsn: str = "") -> WorkspaceIntelligenteService:
    studio_db = StudioDB.get(paths["STUDIO_DB"])
    studio_db.ensure_schema()
    agenda = Agenda(db_path=paths["AGENDA_DB"], studio_db=studio_db)
    scadenziario = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"], studio_db=studio_db)
    fascicoli = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=studio_db,
    )
    calendar_sync = GestioneCalendarSync(db_path=paths["CALENDAR_SYNC_DB"])
    giurisprudenza = GestioneGiurisprudenza(paths["GIURISPRUDENZA_DB"])
    return WorkspaceIntelligenteService(
        agenda=agenda,
        scadenziario=scadenziario,
        fascicoli=fascicoli,
        calendar_sync=calendar_sync,
        giurisprudenza=giurisprudenza,
        snapshot_path=paths["WORKSPACE_INTELLIGENCE_DB"],
        postgres_dsn=postgres_dsn,
    )


def _migrate_sqlite_repository_domains(paths: dict[str, str]) -> dict[str, Any]:
    report: dict[str, Any] = {}

    template_manager = GestioneTemplateAtti(paths["TEMPLATE_ATTI_DB"])
    template_prefs = GestionePreferenzeTemplateAtti(paths["TEMPLATE_ATTI_PREFS_DB"])
    template_prefs.salva(template_prefs.carica())
    report["template_atti"] = {
        "ok": True,
        "source_count": len(template_manager.tutti()),
        "sqlite_stats": template_manager.statistiche_repository(),
    }

    legal_manager = GestioneLegalIntelligence(
        paths["LEGAL_INTELLIGENCE_DB"],
        normative_db_path=paths["NORMATIVE_TABLES_DB"],
    )
    report["legal_intelligence"] = {
        "ok": True,
        "runtime_counts": {
            "monitor_runs": len(list(getattr(legal_manager, "_data", {}).get("monitor_runs") or [])),
            "alerts": len(list(getattr(legal_manager, "_data", {}).get("alerts") or [])),
            "audit_traces": len(list(getattr(legal_manager, "_data", {}).get("audit_traces") or [])),
        },
        "sqlite_stats": legal_manager.statistiche_repository(),
    }
    report["telematico_repository"] = {
        "ok": True,
        "sqlite_stats": legal_manager.statistiche_telematico_repository(),
    }

    giurisprudenza = GestioneGiurisprudenza(paths["GIURISPRUDENZA_DB"])
    report["giurisprudenza"] = {
        "ok": True,
        "source_count": len(giurisprudenza.cerca()),
        "sqlite_stats": giurisprudenza.statistiche_repository(),
    }

    workspace_service = _workspace_service(paths)
    snapshot = workspace_service.save_snapshot(paths["WORKSPACE_INTELLIGENCE_DB"])
    workspace_repo = WorkspaceIntelligenceRepository(
        derive_workspace_intelligence_repository_db_path(paths["WORKSPACE_INTELLIGENCE_DB"])
    )
    report["workspace_intelligence"] = {
        "ok": True,
        "snapshot_generated_at": snapshot.get("generated_at", ""),
        "sqlite_stats": workspace_repo.storage_stats(),
    }

    legal_updates = build_legal_update_pipeline(
        intelligence_db_path=paths["LEGAL_INTELLIGENCE_DB"],
        giurisprudenza_db_path=paths["GIURISPRUDENZA_DB"],
    )
    legal_updates_db_cfg = LegalUpdateDbConfig.from_anchor(paths["LEGAL_INTELLIGENCE_DB"])
    legal_updates_counts = _query_sqlite_counts(
        legal_updates_db_cfg.db_path,
        {
            "sources": "SELECT COUNT(*) FROM sources",
            "raw_documents": "SELECT COUNT(*) FROM source_documents_raw",
            "normalized_documents": "SELECT COUNT(*) FROM source_documents_normalized",
            "analyses": "SELECT COUNT(*) FROM ai_documents_analysis",
            "review_queue": "SELECT COUNT(*) FROM review_queue",
            "news": "SELECT COUNT(*) FROM news",
            "normative": "SELECT COUNT(*) FROM normative",
            "jurisprudence": "SELECT COUNT(*) FROM jurisprudence",
            "prassi": "SELECT COUNT(*) FROM prassi",
        },
    )
    report["aggiornamenti_legali"] = {
        "ok": True,
        "sqlite_stats": legal_updates_counts,
        "sources_seeded": len(legal_updates.list_sources(enabled_only=False)),
    }

    coverage_repo = SQLiteCoverageRepository(CoverageSqliteConfig(path=paths["STUDIO_DB"]))
    coverage_repo.ensure_schema()
    report["coverage_ai"] = {
        "ok": True,
        "sqlite_stats": {
            "snapshots": len(coverage_repo.list_latest_snapshots()),
            "open_gaps": len(coverage_repo.list_open_gaps(limit=500)),
            "drafts": len(coverage_repo.list_drafts(statuses=("generated", "validated", "needs_review", "approved", "published"))),
            "published_history": len(coverage_repo.list_published_history(limit=500)),
        },
    }
    return report


def _migrate_postgres_repository_domains(paths: dict[str, str], dsn: str) -> tuple[dict[str, Any], list[str]]:
    report: dict[str, Any] = {}
    errors: list[str] = []

    try:
        template_manager = GestioneTemplateAtti(paths["TEMPLATE_ATTI_DB"])
        template_repo = GestioneTemplateRepository(
            derive_template_repository_db_path(paths["TEMPLATE_ATTI_DB"]),
            postgres_dsn=dsn,
        )
        template_repo.synchronize_templates(template_manager.tutti(), export_json=False)
        prefs = GestionePreferenzeTemplateAtti(paths["TEMPLATE_ATTI_PREFS_DB"]).carica()
        template_repo.save_editor_preferences(prefs)
        report["template_atti"] = {
            "ok": True,
            "postgres_stats": template_repo.storage_stats(),
        }
    except Exception as exc:
        report["template_atti"] = {"ok": False, "error": str(exc)}
        errors.append(f"template_atti: {exc}")

    try:
        legal_manager = GestioneLegalIntelligence(
            paths["LEGAL_INTELLIGENCE_DB"],
            normative_db_path=paths["NORMATIVE_TABLES_DB"],
        )
        payload = legal_manager.repository_payload()
        legal_repo = GestioneLegalIntelligenceRepository(
            derive_legal_intelligence_repository_db_path(paths["LEGAL_INTELLIGENCE_DB"]),
            postgres_dsn=dsn,
        )
        legal_repo.synchronize_runtime(
            source_rows=list(payload.get("sources") or []),
            engine_rows=list(payload.get("engines") or []),
            keyword_engine_rows=list(payload.get("keyword_to_engine") or []),
            keyword_source_rows=list(payload.get("keyword_to_source") or []),
            edge_rows=list(payload.get("engine_source_edges") or []),
            monitoring_rows=list(payload.get("monitoring") or []),
            alert_rows=list(payload.get("alerts") or []),
            audit_rows=list(payload.get("audit_traces") or []),
            operational_rows=list(payload.get("operational_rules") or []),
            export_json=False,
        )
        legal_repo.save_runtime_state(dict(getattr(legal_manager, "_data", {})))
        report["legal_intelligence"] = {
            "ok": True,
            "postgres_stats": legal_repo.storage_stats(),
        }

        tele_payload = legal_manager.telematico_repository_payload()
        tele_repo = GestioneTelematicoRepository(
            legal_manager.telematico_repository_db_path,
            json_path=legal_manager.telematico_repository_json_path,
            snapshot_json_path=legal_manager.telematico_catalog_snapshot_json_path,
            methods_json_path=legal_manager.telematico_methods_json_path,
            wsdl_json_path=legal_manager.telematico_wsdl_json_path,
            xsd_json_path=legal_manager.telematico_xsd_json_path,
            catalog_sources_json_path=legal_manager.telematico_catalog_sources_json_path,
            sources_json_path=legal_manager.telematico_sources_json_path,
            capabilities_json_path=legal_manager.telematico_capabilities_json_path,
            rules_json_path=legal_manager.telematico_rules_json_path,
            actions_json_path=legal_manager.telematico_actions_json_path,
            wizard_json_path=legal_manager.telematico_wizard_json_path,
            monitoring_json_path=legal_manager.telematico_monitoring_json_path,
            postgres_dsn=dsn,
        )
        tele_repo.synchronize_runtime(
            {
                "catalog_snapshot": dict(tele_payload.get("catalog_snapshot") or {}),
                "methods": list(tele_payload.get("methods") or []),
                "wsdl_modules": list(tele_payload.get("wsdl_modules") or []),
                "xsd_channels": list(tele_payload.get("xsd_channels") or []),
                "catalog_sources": list(tele_payload.get("catalog_sources") or []),
                "sources": list(tele_payload.get("sources") or []),
                "capabilities": list(tele_payload.get("capabilities") or []),
                "rules": list(tele_payload.get("rules") or []),
                "actions": list(tele_payload.get("actions") or []),
                "wizard_sections": list(tele_payload.get("wizard_sections") or []),
                "monitoring": list(tele_payload.get("monitoring") or []),
            }
        )
        report["telematico_repository"] = {
            "ok": True,
            "postgres_stats": tele_repo.storage_stats(),
        }
    except Exception as exc:
        if "legal_intelligence" not in report:
            report["legal_intelligence"] = {"ok": False, "error": str(exc)}
        if "telematico_repository" not in report:
            report["telematico_repository"] = {"ok": False, "error": str(exc)}
        errors.append(f"legal_intelligence_telematico: {exc}")

    try:
        giurisprudenza = GestioneGiurisprudenza(paths["GIURISPRUDENZA_DB"])
        payload = giurisprudenza.repository_payload()
        repo = GestioneRepositoryGiurisprudenza(
            derive_giurisprudenza_repository_db_path(paths["GIURISPRUDENZA_DB"]),
            postgres_dsn=dsn,
        )
        repo.synchronize_runtime(
            source_rows=list(payload.get("sources") or []),
            taxonomy_rows=list(payload.get("taxonomy") or []),
            usage_rows=list(payload.get("usage_policy") or []),
            sync_rows=list(payload.get("sync_registry") or []),
            export_json=False,
        )
        repo.save_runtime_state(dict(getattr(giurisprudenza, "_data", {})))
        report["giurisprudenza"] = {
            "ok": True,
            "postgres_stats": repo.storage_stats(),
        }
    except Exception as exc:
        report["giurisprudenza"] = {"ok": False, "error": str(exc)}
        errors.append(f"giurisprudenza: {exc}")

    try:
        workspace_service = _workspace_service(paths)
        snapshot = workspace_service.save_snapshot(paths["WORKSPACE_INTELLIGENCE_DB"])
        workspace_repo = WorkspaceIntelligenceRepository(
            derive_workspace_intelligence_repository_db_path(paths["WORKSPACE_INTELLIGENCE_DB"]),
            postgres_dsn=dsn,
        )
        workspace_repo.save_snapshot(snapshot)
        report["workspace_intelligence"] = {
            "ok": True,
            "postgres_stats": workspace_repo.storage_stats(),
        }
    except Exception as exc:
        report["workspace_intelligence"] = {"ok": False, "error": str(exc)}
        errors.append(f"workspace_intelligence: {exc}")

    try:
        legal_updates_cfg = LegalUpdateDbConfig.from_anchor(paths["LEGAL_INTELLIGENCE_DB"])
        sqlite_legal_updates = LegalUpdateRepository(
            legal_updates_cfg.db_path,
            json_path=legal_updates_cfg.json_path,
        )
        postgres_legal_updates = LegalUpdateRepository(
            legal_updates_cfg.db_path,
            json_path=legal_updates_cfg.json_path,
            postgres_dsn=dsn,
        )
        copied_counts = _copy_legal_updates_to_postgres(
            legal_updates_cfg.db_path,
            postgres_legal_updates,
        )
        report["aggiornamenti_legali"] = {
            "ok": True,
            "copied_tables": copied_counts,
            "sqlite_headline": sqlite_legal_updates.dashboard_snapshot().get("headline", {}),
            "postgres_headline": postgres_legal_updates.dashboard_snapshot().get("headline", {}),
        }
    except Exception as exc:
        report["aggiornamenti_legali"] = {"ok": False, "error": str(exc)}
        errors.append(f"aggiornamenti_legali: {exc}")

    try:
        sqlite_coverage = SQLiteCoverageRepository(CoverageSqliteConfig(path=paths["STUDIO_DB"]))
        postgres_coverage = PostgresCoverageRepository(CoverageDbConfig(dsn=dsn, explicit=True))
        postgres_coverage.ensure_schema()
        snapshots = []
        for row in sqlite_coverage.list_latest_snapshots():
            snapshots.append(
                {
                    "subbranch_code": row.get("subbranch_code"),
                    "coverage_score": int(row.get("coverage_score") or 0),
                    "coverage_status": row.get("coverage_status") or "EMPTY",
                    "missing_blocks": list(row.get("missing_blocks_json") or []),
                    "procedure_count": int(row.get("procedure_count") or 0),
                }
            )
        if snapshots:
            postgres_coverage.replace_snapshots(snapshots)
        gaps = []
        for row in sqlite_coverage.list_open_gaps(limit=500):
            gaps.append(
                {
                    "subbranch_code": row.get("subbranch_code"),
                    "gap_type": row.get("gap_type"),
                    "priority_score": int(row.get("priority_score") or 0),
                    "gap_payload": dict(row.get("gap_payload_json") or {}),
                    "status": row.get("status") or "OPEN",
                }
            )
        if gaps:
            postgres_coverage.replace_gap_queue(gaps)
        report["coverage_ai"] = {
            "ok": True,
            "postgres_stats": {
                "snapshots": len(postgres_coverage.list_latest_snapshots()),
                "open_gaps": len(postgres_coverage.list_open_gaps(limit=500)),
                "drafts": len(postgres_coverage.list_drafts(statuses=("generated", "validated", "needs_review", "approved", "published"))),
                "published_history": len(postgres_coverage.list_published_history(limit=500)),
            },
        }
    except Exception as exc:
        report["coverage_ai"] = {"ok": False, "error": str(exc)}
        errors.append(f"coverage_ai: {exc}")
    return report, errors


def migrate_full_storage_to_sqlite(
    *,
    paths: dict[str, str],
    tenant_slug: str,
    database_config: Any | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    migratore = GestioneDatabase(_extended_sqlite_sources(paths))
    core = migratore.migra_verso_sqlite(paths["STUDIO_DB"]).to_dict()
    repositories = _migrate_sqlite_repository_domains(paths)
    inventory = build_full_storage_inventory(
        paths=paths,
        database_config=database_config,
        tenant_slug=tenant_slug,
    )
    core_errors = [str(item) for item in core.get("errori") or []]
    core_warnings = [str(item) for item in core.get("avvisi") or []]
    diff_summary = _build_diff_summary(inventory=inventory, target="sqlite")
    dirty_findings = _build_dirty_tenant_findings(
        errors=core_errors,
        warnings=core_warnings,
        diff_summary=diff_summary,
    )
    report = {
        "generated_at": _now_iso(),
        "tenant_slug": tenant_slug,
        "target": "sqlite",
        "success": bool(core.get("riuscita")),
        "core": core,
        "repositories": repositories,
        "documents": {
            "count": _count_files(paths.get("FASCICOLI_DOCS", ""), suffixes=(".pdf", ".docx", ".p7m", ".txt")),
            "archive_count": _count_files(paths.get("FASCICOLI_ARCH", "")),
            "storage_kind": "filesystem",
        },
        "precheck_snapshot": _build_precheck_snapshot(inventory=inventory, target="sqlite", paths=paths),
        "diff_summary": diff_summary,
        "dirty_tenant_findings": dirty_findings,
        "operation_log": _build_operation_log(
            target="sqlite",
            success=bool(core.get("riuscita")),
            core_success=bool(core.get("riuscita")),
            diff_summary=diff_summary,
            repository_rows=len(repositories),
        ),
        "rollback": _build_rollback_posture(target="sqlite", success=bool(core.get("riuscita"))),
    }
    report["inventory"] = inventory
    if write_report:
        report["report_path"] = _write_report(paths, tenant_slug, "sqlite", report)
    return report


def migrate_full_storage_to_postgres(
    *,
    paths: dict[str, str],
    database_config: Any,
    secret_key: str,
    tenant_slug: str,
) -> dict[str, Any]:
    dsn = database_config_to_dsn(database_config)
    if not dsn:
        raise ValueError("Configurazione PostgreSQL incompleta: impossibile avviare la migrazione completa.")

    sqlite_report = migrate_full_storage_to_sqlite(
        paths=paths,
        tenant_slug=tenant_slug,
        database_config=database_config,
        write_report=False,
    )
    try:
        StudioDB.get(paths["STUDIO_DB"]).chiudi()
    except Exception:
        pass
    core_report = migrate_core_storage_to_postgres(
        paths=paths,
        database_config=database_config,
        secret_key=secret_key,
        tenant_slug=tenant_slug,
    )
    repositories, repo_errors = _migrate_postgres_repository_domains(paths, dsn)
    success = bool(core_report.get("success")) and not repo_errors
    inventory = build_full_storage_inventory(
        paths=paths,
        database_config=database_config,
        tenant_slug=tenant_slug,
    )
    sqlite_warnings = [str(item) for item in (sqlite_report.get("core") or {}).get("avvisi") or []]
    repo_errors_text = [str(item) for item in repo_errors]
    diff_summary = _build_diff_summary(inventory=inventory, target="postgresql")
    dirty_findings = _build_dirty_tenant_findings(
        errors=repo_errors_text,
        warnings=sqlite_warnings,
        diff_summary=diff_summary,
    )
    report = {
        "generated_at": _now_iso(),
        "tenant_slug": tenant_slug,
        "target": "postgresql",
        "success": success,
        "sqlite_stage": sqlite_report,
        "core": core_report,
        "repositories": repositories,
        "repository_errors": repo_errors,
        "precheck_snapshot": _build_precheck_snapshot(inventory=inventory, target="postgresql", paths=paths),
        "diff_summary": diff_summary,
        "dirty_tenant_findings": dirty_findings,
        "operation_log": _build_operation_log(
            target="postgresql",
            success=success,
            core_success=bool(core_report.get("success")),
            diff_summary=diff_summary,
            repository_rows=len(repositories),
            repository_errors=repo_errors_text,
        ),
        "rollback": _build_rollback_posture(target="postgresql", success=success),
    }
    report["inventory"] = inventory
    report["report_path"] = _write_report(paths, tenant_slug, "postgresql", report)
    return report


def build_full_storage_inventory(
    *,
    paths: dict[str, str],
    database_config: Any | None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    postgres_config = _postgres_candidate_config(database_config)
    dsn = database_config_to_dsn(postgres_config) if postgres_config is not None else ""
    postgres_online = bool(dsn and _postgres_is_online(postgres_config))
    template_repo_db = derive_template_repository_db_path(paths["TEMPLATE_ATTI_DB"])
    legal_repo_db = derive_legal_intelligence_repository_db_path(paths["LEGAL_INTELLIGENCE_DB"])
    giuris_repo_db = derive_giurisprudenza_repository_db_path(paths["GIURISPRUDENZA_DB"])
    telematico_repo_db = derive_telematico_repository_db_path(paths["LEGAL_INTELLIGENCE_DB"])
    telematico_sources_json = derive_telematico_sources_json_path(paths["LEGAL_INTELLIGENCE_DB"])
    workspace_repo_db = derive_workspace_intelligence_repository_db_path(paths["WORKSPACE_INTELLIGENCE_DB"])
    legal_updates_cfg = LegalUpdateDbConfig.from_anchor(paths["LEGAL_INTELLIGENCE_DB"])
    conferimenti_json_path = (
        str(Path(paths["PREVENTIVI_DB"]).with_name("conferimenti.json"))
        if paths.get("PREVENTIVI_DB")
        else ""
    )
    pagamenti_dir = str(paths.get("PAGAMENTI_DIR", "") or "").strip()
    pagamenti_config_json_path = str(Path(pagamenti_dir) / "config.json") if pagamenti_dir else ""
    pagamenti_links_json_path = str(Path(pagamenti_dir) / "transazioni.json") if pagamenti_dir else ""

    domains = [
        {
            "code": "utenti",
            "title": "Utenti",
            "json_count": _json_record_count(paths["AUTH_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "utenti"),
            "postgres_count": _postgres_table_count(postgres_config, "utenti") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "audit",
            "title": "Audit",
            "json_count": _json_record_count(paths["AUDIT_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "audit_log"),
            "postgres_count": _postgres_table_count(postgres_config, "audit_log") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "clienti",
            "title": "Clienti",
            "json_count": _json_record_count(paths["CLIENTI_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "clienti"),
            "postgres_count": _postgres_table_count(postgres_config, "clienti") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "fascicoli",
            "title": "Fascicoli",
            "json_count": _json_record_count(paths["FASCICOLI_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "fascicoli"),
            "postgres_count": _postgres_table_count(postgres_config, "fascicoli") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "appuntamenti",
            "title": "Appuntamenti",
            "json_count": _json_record_count(paths["AGENDA_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "appuntamenti"),
            "postgres_count": _postgres_table_count(postgres_config, "appuntamenti") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "scadenze",
            "title": "Scadenze",
            "json_count": _json_record_count(paths["SCADENZIARIO_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "scadenze"),
            "postgres_count": _postgres_table_count(postgres_config, "scadenze") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "timesheet",
            "title": "Timesheet",
            "json_count": _json_record_count(paths["TIMESHEET_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "timesheet_entries"),
            "postgres_count": _postgres_table_count(postgres_config, "timesheet_entries") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "preventivi",
            "title": "Preventivi",
            "json_count": _json_record_count(paths["PREVENTIVI_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "preventivi_records"),
            "postgres_count": _postgres_table_count(postgres_config, "preventivi_records") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "conferimenti",
            "title": "Conferimenti",
            "json_count": _json_record_count(conferimenti_json_path),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "conferimenti_records"),
            "postgres_count": _postgres_table_count(postgres_config, "conferimenti_records") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "fatturazione",
            "title": "Fatturazione",
            "json_count": _json_record_count(paths["FATTURAZIONE_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "parcelle"),
            "postgres_count": _postgres_table_count(postgres_config, "parcelle") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "pagamenti_config",
            "title": "Pagamenti - configurazione",
            "json_count": _json_record_count(pagamenti_config_json_path),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "payment_config"),
            "postgres_count": _postgres_table_count(postgres_config, "payment_config") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "pagamenti_links",
            "title": "Pagamenti - link",
            "json_count": _json_record_count(pagamenti_links_json_path),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "payment_links"),
            "postgres_count": _postgres_table_count(postgres_config, "payment_links") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "messaggi",
            "title": "Messaggi",
            "json_count": _json_record_count(paths["MESSAGGI_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "messaggi"),
            "postgres_count": _postgres_table_count(postgres_config, "messaggi") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "privacy",
            "title": "Privacy",
            "json_count": _json_record_count(paths["PRIVACY_DB"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "privacy_trattamenti"),
            "postgres_count": _postgres_table_count(postgres_config, "privacy_trattamenti") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "notifiche",
            "title": "Notifiche",
            "json_count": _json_record_count(paths["NOTIFICHE_LOG"]),
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "notifiche_log"),
            "postgres_count": _postgres_table_count(postgres_config, "notifiche_log") if postgres_online else 0,
            "storage_kind": "core",
        },
        {
            "code": "documenti",
            "title": "Documenti",
            "json_count": _count_files(paths["FASCICOLI_DOCS"], suffixes=(".pdf", ".docx", ".p7m", ".txt")),
            "sqlite_count": _count_files(paths["FASCICOLI_DOCS"], suffixes=(".pdf", ".docx", ".p7m", ".txt")),
            "postgres_count": _count_files(paths["FASCICOLI_DOCS"], suffixes=(".pdf", ".docx", ".p7m", ".txt")),
            "storage_kind": "filesystem",
            "note": "I documenti restano sul filesystem tenant-aware.",
        },
        {
            "code": "template_atti",
            "title": "Template atti",
            "json_count": _json_record_count(paths["TEMPLATE_ATTI_DB"]),
            "sqlite_count": _sqlite_table_count(template_repo_db, "template_repository"),
            "postgres_count": _postgres_table_count(postgres_config, "template_repository") if postgres_online else 0,
            "storage_kind": "repository",
        },
        {
            "code": "legal_intelligence",
            "title": "Legal intelligence",
            "json_count": _json_record_count(paths["LEGAL_INTELLIGENCE_DB"]),
            "sqlite_count": _sqlite_table_count(legal_repo_db, "legal_sources_repository"),
            "postgres_count": _postgres_table_count(postgres_config, "legal_sources_repository") if postgres_online else 0,
            "storage_kind": "repository",
        },
        {
            "code": "giurisprudenza",
            "title": "Giurisprudenza",
            "json_count": _json_record_count(paths["GIURISPRUDENZA_DB"]),
            "sqlite_count": _sqlite_table_count(giuris_repo_db, "giurisprudenza_sources_repository"),
            "postgres_count": _postgres_table_count(postgres_config, "giurisprudenza_sources_repository") if postgres_online else 0,
            "storage_kind": "repository",
        },
        {
            "code": "telematico_repository",
            "title": "Telematico",
            "json_count": _json_record_count(telematico_sources_json),
            "sqlite_count": _sqlite_table_count(telematico_repo_db, "telematico_sources_repository"),
            "postgres_count": _postgres_table_count(postgres_config, "telematico_sources_repository") if postgres_online else 0,
            "storage_kind": "repository",
        },
        {
            "code": "workspace_intelligence",
            "title": "Workspace intelligence",
            "json_count": _json_record_count(paths["WORKSPACE_INTELLIGENCE_DB"]),
            "sqlite_count": _sqlite_table_count(workspace_repo_db, "workspace_intelligence_snapshot"),
            "postgres_count": _postgres_table_count(postgres_config, "workspace_intelligence_snapshot") if postgres_online else 0,
            "storage_kind": "repository",
        },
        {
            "code": "aggiornamenti_legali",
            "title": "Aggiornamenti legali",
            "json_count": _json_record_count(legal_updates_cfg.json_path),
            "sqlite_count": _sqlite_table_count(legal_updates_cfg.db_path, "sources"),
            "postgres_count": _postgres_table_count(postgres_config, "sources") if postgres_online else 0,
            "storage_kind": "repository",
            "note": "Repository SQL strutturato con parita' anche su PostgreSQL tenant-aware.",
        },
        {
            "code": "coverage_ai",
            "title": "Copertura AI",
            "json_count": 0,
            "sqlite_count": _sqlite_table_count(paths["STUDIO_DB"], "coverage_snapshots"),
            "postgres_count": _postgres_table_count(postgres_config, "coverage_snapshots") if postgres_online else 0,
            "storage_kind": "sql_pipeline",
        },
    ]
    return {
        "generated_at": _now_iso(),
        "tenant_slug": tenant_slug,
        "postgres_online": postgres_online,
        "domains": domains,
    }

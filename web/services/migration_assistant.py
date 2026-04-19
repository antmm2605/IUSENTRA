"""Superficie admin per migrazione dati completa tenant-aware."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from flask import current_app

from pct.checklist_atti import TUTTI_I_TEMPLATE
from pct.product_governance import build_migration_program_payload, build_storage_parity_payload
from pct.storage_migration_full import (
    attach_migration_rollback_context,
    build_full_storage_inventory,
)
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant


_DOMAIN_LABELS = {
    "clienti": "Clienti",
    "fascicoli": "Fascicoli",
    "appuntamenti": "Appuntamenti",
    "scadenze": "Scadenze",
    "timesheet": "Timesheet",
    "preventivi": "Preventivi",
    "conferimenti": "Conferimenti",
    "fatturazione": "Fatturazione",
    "pagamenti_links": "Pagamenti - link",
    "pagamenti_config": "Pagamenti - configurazione",
    "messaggi": "Messaggi",
    "utenti": "Utenti",
    "audit": "Audit",
    "privacy": "Privacy",
    "notifiche": "Notifiche",
    "backup": "Backup",
}

_REPOSITORY_LABELS = {
    "template_atti": "Template atti",
    "legal_intelligence": "Legal intelligence",
    "telematico_repository": "Repository telematico",
    "giurisprudenza": "Giurisprudenza",
    "workspace_intelligence": "Workspace intelligence",
    "aggiornamenti_legali": "Aggiornamenti legali",
    "coverage_ai": "Copertura AI",
}

_TARGET_LABELS = {
    "sqlite": "SQL locale tenant-aware",
    "postgresql": "PostgreSQL tenant-aware",
}


def _tenant_manager() -> GestioneTenant:
    registry = current_app.config.get("TENANTS_REGISTRY", "./data/tenants.json")
    return GestioneTenant(registry_path=registry)


def _resolve_selected_studio(selected_slug: str = "") -> tuple[GestioneTenant, Any | None]:
    tm = _tenant_manager()
    studios = tm.lista()
    wanted = str(selected_slug or "").strip().lower()
    studio = tm.get(wanted) if wanted else None
    if studio is None and studios:
        studio = studios[0]
    return tm, studio


def _copy_database_config(database: Any) -> DatabaseConfig:
    if isinstance(database, DatabaseConfig):
        return DatabaseConfig.from_dict(database.to_dict())
    if hasattr(database, "to_dict"):
        try:
            return DatabaseConfig.from_dict(database.to_dict())
        except Exception:
            return DatabaseConfig.from_dict({})
    return DatabaseConfig.from_dict(database)


def _has_postgres_credentials(database: Any) -> bool:
    cfg = _copy_database_config(database)
    host = str(cfg.host or "").strip()
    db_name = str(cfg.db_name or "").strip()
    user = str(cfg.utente or "").strip()
    return bool(host and db_name and user)


def _sqlite_target_config(database: Any) -> DatabaseConfig:
    cfg = _copy_database_config(database)
    cfg.mode = DbMode.SQLITE
    cfg.core_runtime_enabled = False
    return cfg


def _postgres_target_config(database: Any) -> DatabaseConfig:
    cfg = _copy_database_config(database)
    cfg.mode = DbMode.POSTGRESQL
    return cfg


def _latest_report_payload(backup_dir: str) -> dict[str, Any] | None:
    root = Path(str(backup_dir or "").strip())
    if not root.exists():
        return None
    best_payload: dict[str, Any] | None = None
    best_path: Path | None = None
    for candidate in root.glob("storage_migration_full_*.json"):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload["_path"] = str(candidate)
        if best_payload is None or _report_sort_key(payload) >= _report_sort_key(best_payload):
            best_payload = payload
            best_path = candidate
    if best_payload is None or best_path is None:
        return None
    best_payload["_path"] = str(best_path)
    return best_payload


def _load_report_payload(report_path: str) -> dict[str, Any] | None:
    target = Path(str(report_path or "").strip())
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    payload["_path"] = str(target)
    return payload


def _report_sort_key(payload: dict[str, Any] | None) -> tuple[str, str]:
    item = dict(payload or {})
    generated_at = str(item.get("generated_at") or "").strip()
    report_path = str(item.get("_path") or item.get("report_path") or "").strip()
    return generated_at, report_path


def _compact_counts(values: dict[str, Any] | None) -> str:
    payload = dict(values or {})
    chunks: list[str] = []
    for key, raw_value in payload.items():
        value = _to_int_or_none(raw_value)
        if value is None or value <= 0:
            continue
        chunks.append(f"{_DOMAIN_LABELS.get(key, key.replace('_', ' ').title())}: {value}")
    return " | ".join(chunks[:6]) if chunks else "Nessun record trasferito."


def _to_int_or_none(raw_value: Any) -> int | None:
    if isinstance(raw_value, bool):
        return int(raw_value)
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    try:
        text = str(raw_value or "").strip()
    except Exception:
        return None
    if not text:
        return None
    if text.isdigit():
        return int(text)
    return None


def _collect_domain_messages(messages: list[str], domain_code: str) -> list[str]:
    prefix = f"{domain_code}:"
    nested_prefix = f"{domain_code}/"
    matched = [
        str(message).strip()
        for message in messages
        if str(message or "").strip().startswith(prefix) or str(message or "").strip().startswith(nested_prefix)
    ]
    return matched


def _status_badge(ok: bool | None = None, *, warning: bool = False) -> str:
    if warning:
        return "warning"
    if ok is None:
        return "secondary"
    return "success" if ok else "danger"


def _resolution_steps(messages: list[str], *, target: str) -> list[str]:
    if not messages:
        if target == "postgresql":
            return [
                "Apri clienti, fascicoli, agenda, scadenze e fatturazione dello studio per confermare il cutover operativo.",
                "Verifica che il backend effettivo del tenant risulti PostgreSQL tenant-aware anche nella dashboard storage.",
                "Conserva il report nel backup del tenant come prova del passaggio riuscito.",
            ]
        return [
            "Apri i moduli core dello studio per verificare che i dati migrati siano leggibili dal database SQL locale.",
            "Controlla che il file `studio.db` del tenant sia stato aggiornato e che i repository laterali risultino coerenti.",
            "Conserva il report nel backup del tenant per eventuali confronti o rollback controllati.",
        ]
    joined = " \n".join(str(message or "") for message in messages).lower()
    steps: list[str] = []
    if "connessione postgresql" in joined or "could not connect" in joined or "connection refused" in joined:
        steps.extend(
            [
                "Verifica host, porta, nome database, utente e password nello studio selezionato.",
                "Esegui il test connessione dalla scheda database dello studio prima di rilanciare la migrazione.",
                "Controlla che il server PostgreSQL sia raggiungibile dal runtime dell'app e che SSL sia coerente con il server.",
            ]
        )
    if "database is locked" in joined or "locked" in joined:
        steps.extend(
            [
                "Chiudi eventuali processi che tengono aperto `studio.db` e ripeti la migrazione.",
                "Se il lock persiste, riavvia l'applicazione e rilancia il cutover dallo stesso studio.",
            ]
        )
    if "unique constraint failed" in joined or "duplicate key" in joined:
        steps.extend(
            [
                "Ripulisci duplicati sugli identificativi del dominio indicato prima di rilanciare la migrazione.",
                "Controlla i JSON legacy o il repository sorgente per record con lo stesso `id` o chiave univoca.",
            ]
        )
    if "no such table" in joined or "undefinedtable" in joined or "does not exist" in joined:
        steps.extend(
            [
                "Ricrea lo schema SQL del dominio interessato e verifica che la migrazione applicativa sia stata eseguita.",
                "Se il problema e' su PostgreSQL, verifica che il database selezionato sia quello corretto per il tenant.",
            ]
        )
    if "permission denied" in joined or "access denied" in joined or "forbidden" in joined:
        steps.extend(
            [
                "Verifica i permessi di lettura e scrittura sul database o sulla directory del tenant.",
                "Controlla che l'utente applicativo abbia privilegi sufficienti sullo schema SQL destinazione.",
            ]
        )
    if "ssl" in joined:
        steps.append("Allinea il flag SSL della connessione con la configurazione reale del server PostgreSQL.")
    if not steps and target == "postgresql":
        steps.extend(
            [
                "Controlla il report completo nel backup del tenant e correggi il dominio indicato come non consistente.",
                "Dopo la correzione, rilancia il cutover PostgreSQL dallo stesso studio senza modificare i dati su filesystem.",
            ]
        )
    if not steps:
        steps.extend(
            [
                "Apri il report completo generato nel backup del tenant e correggi il dominio segnato come non riuscito.",
                "Dopo la correzione, rilancia la migrazione dallo stesso studio e verifica di nuovo il riepilogo finale.",
            ]
        )
    unique_steps: list[str] = []
    for step in steps:
        if step not in unique_steps:
            unique_steps.append(step)
    return unique_steps


def _build_repository_rows(repositories: dict[str, Any], *, target: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, payload in repositories.items():
        item = dict(payload or {})
        ok = bool(item.get("ok"))
        details_source = (
            item.get("postgres_stats")
            or item.get("sqlite_stats")
            or item.get("copied_tables")
            or item.get("runtime_counts")
            or item.get("headline")
            or {}
        )
        detail = _compact_counts(details_source) if isinstance(details_source, dict) else ""
        if item.get("error"):
            detail = str(item.get("error"))
        rows.append(
            {
                "label": _REPOSITORY_LABELS.get(code, code.replace("_", " ").title()),
                "status": _status_badge(ok),
                "status_label": "OK" if ok else "Errore",
                "detail": detail or f"Repository sincronizzato su {_TARGET_LABELS.get(target, target)}.",
            }
        )
    return rows


def _build_diff_payload(report: dict[str, Any], *, target: str) -> dict[str, Any]:
    diff_summary = dict(report.get("diff_summary") or {})
    rows = list(diff_summary.get("rows") or [])
    if rows:
        return {"summary": dict(diff_summary.get("summary") or {}), "rows": rows}

    inventory = dict(report.get("inventory") or {})
    source_key = "json_count" if target == "sqlite" else "sqlite_count"
    destination_key = "sqlite_count" if target == "sqlite" else "postgres_count"
    source_label = "JSON legacy" if target == "sqlite" else "SQL locale"
    destination_label = "SQL locale" if target == "sqlite" else "PostgreSQL"
    fallback_rows: list[dict[str, Any]] = []
    for domain in inventory.get("domains", []):
        if str(domain.get("storage_kind") or "") == "filesystem":
            continue
        source_count = int(domain.get(source_key) or 0)
        destination_count = int(domain.get(destination_key) or 0)
        fallback_rows.append(
            {
                "code": str(domain.get("code") or ""),
                "title": str(domain.get("title") or ""),
                "source_label": source_label,
                "source_count": source_count,
                "destination_label": destination_label,
                "destination_count": destination_count,
                "delta": destination_count - source_count,
                "status": "success" if source_count == destination_count else "warning",
                "status_label": "Allineato" if source_count == destination_count else "Delta da presidiare",
            }
        )
    return {
        "summary": {
            "rows_total": len(fallback_rows),
            "matched": sum(1 for row in fallback_rows if row["status"] == "success"),
            "mismatched": sum(1 for row in fallback_rows if row["status"] != "success"),
            "source_label": source_label,
            "destination_label": destination_label,
        },
        "rows": fallback_rows,
    }


def _build_failure_modes(report: dict[str, Any], *, errors: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    findings = list(report.get("dirty_tenant_findings") or [])
    if findings:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for finding in findings:
            code = str(finding.get("code") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            rows.append(
                {
                    "code": code,
                    "severity": str(finding.get("severity") or "warning"),
                    "title": str(finding.get("title") or "Failure mode"),
                    "recovery": str(finding.get("recovery") or ""),
                }
            )
        return rows

    rows: list[dict[str, Any]] = []
    for message in errors + warnings:
        lowered = str(message or "").lower()
        if "non trovato" in lowered:
            rows.append(
                {
                    "code": "RIFERIMENTO_ORFANO",
                    "severity": "warning",
                    "title": "Riferimento legacy non risolto",
                    "recovery": "Correggi il collegamento al record mancante e rilancia la migrazione.",
                }
            )
        elif "connessione postgresql" in lowered or "connection refused" in lowered:
            rows.append(
                {
                    "code": "POSTGRES_NON_RAGGIUNGIBILE",
                    "severity": "danger",
                    "title": "Connessione PostgreSQL non disponibile",
                    "recovery": "Verifica credenziali, reachability e SSL del tenant prima del nuovo cutover.",
                }
            )
    return rows


def _build_sqlite_execution(report: dict[str, Any]) -> dict[str, Any]:
    core = dict(report.get("core") or {})
    repositories = dict(report.get("repositories") or {})
    core_errors = [str(item) for item in core.get("errori") or []]
    core_warnings = [str(item) for item in core.get("avvisi") or []]
    record_migrati = dict(core.get("record_migrati") or {})
    repository_rows = _build_repository_rows(repositories, target="sqlite")
    repository_errors = [
        str(payload.get("error"))
        for payload in repositories.values()
        if isinstance(payload, dict) and payload.get("error")
    ]
    core_rows: list[dict[str, Any]] = []
    for code, migrated_count in record_migrati.items():
        domain_errors = _collect_domain_messages(core_errors, code)
        domain_warnings = _collect_domain_messages(core_warnings, code)
        status = _status_badge(not domain_errors, warning=bool(domain_warnings and not domain_errors))
        note = (
            domain_errors[0]
            if domain_errors
            else domain_warnings[0]
            if domain_warnings
            else "Dominio trasferito nel database SQL locale."
            if int(migrated_count or 0) > 0
            else "Nessun record presente nella sorgente legacy."
        )
        core_rows.append(
            {
                "label": _DOMAIN_LABELS.get(code, code.replace("_", " ").title()),
                "migrated_count": int(migrated_count or 0),
                "status": status,
                "status_label": "Errore" if domain_errors else "Attenzione" if domain_warnings else "OK",
                "note": note,
            }
        )

    all_errors = core_errors + repository_errors
    success = bool(report.get("success"))
    repo_ok = sum(1 for row in repository_rows if row["status"] == "success")
    diff_payload = _build_diff_payload(report, target="sqlite")
    failure_modes = _build_failure_modes(report, errors=all_errors, warnings=core_warnings)
    return {
        "target": "sqlite",
        "target_label": _TARGET_LABELS["sqlite"],
        "success": success,
        "status": "success" if success else "error",
        "status_label": "Migrazione completata" if success else "Migrazione con errori",
        "headline": (
            "Il tenant e' stato migrato sul database SQL locale con report reale."
            if success
            else "La migrazione SQL locale ha trovato errori reali da correggere prima del cutover."
        ),
        "generated_at": report.get("generated_at") or "",
        "report_path": report.get("report_path") or report.get("_path") or "",
        "summary_cards": [
            {
                "label": "Record core migrati",
                "value": sum(int(value or 0) for value in record_migrati.values()),
                "detail": f"Domini core toccati: {len(record_migrati)}",
            },
            {
                "label": "Repository SQL sincronizzati",
                "value": repo_ok,
                "detail": f"Su {len(repository_rows)} repository strutturati",
            },
            {
                "label": "Documenti tenant",
                "value": int(((report.get("documents") or {}).get("count") or 0)),
                "detail": "File mantenuti sul filesystem tenant-aware",
            },
        ],
        "checkpoints": [
            {
                "title": "Migrazione SQL locale",
                "status": _status_badge(success),
                "detail": "Il motore ha eseguito davvero il trasferimento completo nel database SQL locale.",
            },
            {
                "title": "Repository strutturati",
                "status": _status_badge(repo_ok == len(repository_rows)),
                "detail": f"Repository sincronizzati con esito positivo: {repo_ok}/{len(repository_rows)}.",
            },
            {
                "title": "Documenti e archivi",
                "status": "success",
                "detail": "Documenti, archivio e upload restano sul filesystem del tenant e non vengono persi.",
            },
        ],
        "core_rows": core_rows,
        "repository_rows": repository_rows,
        "precheck_snapshot": dict(report.get("precheck_snapshot") or {}),
        "diff_summary": dict(diff_payload.get("summary") or {}),
        "diff_rows": list(diff_payload.get("rows") or []),
        "dirty_findings": list(report.get("dirty_tenant_findings") or []),
        "failure_modes": failure_modes,
        "operation_log": list(report.get("operation_log") or []),
        "rollback": dict(report.get("rollback") or {}),
        "warnings": core_warnings,
        "errors": all_errors,
        "resolution_steps": _resolution_steps(all_errors, target="sqlite"),
        "show_consistency_table": False,
    }


def _build_postgres_execution(report: dict[str, Any]) -> dict[str, Any]:
    sqlite_stage = dict(report.get("sqlite_stage") or {})
    sqlite_core = dict(sqlite_stage.get("core") or {})
    core = dict(report.get("core") or {})
    consistency = dict(core.get("consistency") or {})
    repositories = dict(report.get("repositories") or {})
    repository_rows = _build_repository_rows(repositories, target="postgresql")
    repository_errors = [str(item) for item in report.get("repository_errors") or []]
    warnings = [str(item) for item in sqlite_core.get("avvisi") or []]
    consistency_rows: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for code, values in consistency.items():
        item = dict(values or {})
        ok = bool(item.get("ok"))
        if not ok:
            mismatches.append(
                f"{_DOMAIN_LABELS.get(code, code)}: SQLite={int(item.get('sqlite') or 0)} | PostgreSQL={int(item.get('postgres') or 0)}"
            )
        consistency_rows.append(
            {
                "label": _DOMAIN_LABELS.get(code, code.replace("_", " ").title()),
                "json_count": int(item.get("json") or 0),
                "sqlite_count": int(item.get("sqlite") or 0),
                "postgres_count": int(item.get("postgres") or 0),
                "status": _status_badge(ok),
                "status_label": "OK" if ok else "Da correggere",
                "note": "Conteggi allineati tra staging SQLite e PostgreSQL." if ok else "I conteggi non coincidono tra stage e destinazione.",
            }
        )

    success = bool(report.get("success"))
    consistency_ok = sum(1 for row in consistency_rows if row["status"] == "success")
    repo_ok = sum(1 for row in repository_rows if row["status"] == "success")
    errors = repository_errors + mismatches
    diff_payload = _build_diff_payload(report, target="postgresql")
    failure_modes = _build_failure_modes(report, errors=errors, warnings=warnings)
    return {
        "target": "postgresql",
        "target_label": _TARGET_LABELS["postgresql"],
        "success": success,
        "status": "success" if success else "error",
        "status_label": "Cutover completato" if success else "Cutover con errori",
        "headline": (
            "Il tenant e' stato migrato su PostgreSQL con verifica di consistenza reale."
            if success
            else "Il cutover PostgreSQL ha trovato differenze o errori reali prima della messa in produzione."
        ),
        "generated_at": report.get("generated_at") or "",
        "report_path": report.get("report_path") or report.get("_path") or "",
        "summary_cards": [
            {
                "label": "Domini consistenti",
                "value": consistency_ok,
                "detail": f"Su {len(consistency_rows)} domini core verificati",
            },
            {
                "label": "Repository SQL sincronizzati",
                "value": repo_ok,
                "detail": f"Su {len(repository_rows)} repository strutturati",
            },
            {
                "label": "Record core su PostgreSQL",
                "value": sum(int(row["postgres_count"]) for row in consistency_rows),
                "detail": "Conteggi effettivi letti sul backend PostgreSQL",
            },
        ],
        "checkpoints": [
            {
                "title": "Stage SQL locale",
                "status": _status_badge(bool(sqlite_stage.get("success"))),
                "detail": "Prima del cutover il tenant passa sempre dallo staging SQLite con report persistito.",
            },
            {
                "title": "Replica core su PostgreSQL",
                "status": _status_badge(bool(core.get("success"))),
                "detail": f"Domini consistenti tra staging e PostgreSQL: {consistency_ok}/{len(consistency_rows)}.",
            },
            {
                "title": "Repository strutturati",
                "status": _status_badge(repo_ok == len(repository_rows)),
                "detail": f"Repository sincronizzati con esito positivo: {repo_ok}/{len(repository_rows)}.",
            },
        ],
        "core_rows": consistency_rows,
        "repository_rows": repository_rows,
        "precheck_snapshot": dict(report.get("precheck_snapshot") or {}),
        "diff_summary": dict(diff_payload.get("summary") or {}),
        "diff_rows": list(diff_payload.get("rows") or []),
        "dirty_findings": list(report.get("dirty_tenant_findings") or []),
        "failure_modes": failure_modes,
        "operation_log": list(report.get("operation_log") or []),
        "rollback": dict(report.get("rollback") or {}),
        "warnings": warnings,
        "errors": errors,
        "resolution_steps": _resolution_steps(errors + warnings, target="postgresql"),
        "show_consistency_table": True,
    }


def _build_failed_execution(
    *,
    target: str,
    error_message: str,
    generated_at: str = "",
) -> dict[str, Any]:
    messages = [str(error_message or "Migrazione non completata.")]
    return {
        "target": target,
        "target_label": _TARGET_LABELS.get(target, target.upper()),
        "success": False,
        "status": "error",
        "status_label": "Esecuzione non completata",
        "headline": "La migrazione non e' partita o si e' fermata prima di generare un report completo.",
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "report_path": "",
        "summary_cards": [
            {
                "label": "Stato",
                "value": "Errore",
                "detail": "Il motore non ha potuto chiudere la migrazione richiesta.",
            }
        ],
        "checkpoints": [
            {
                "title": "Esecuzione",
                "status": "danger",
                "detail": messages[0],
            }
        ],
        "core_rows": [],
        "repository_rows": [],
        "precheck_snapshot": {},
        "diff_summary": {},
        "diff_rows": [],
        "dirty_findings": [],
        "failure_modes": [],
        "operation_log": [],
        "rollback": {},
        "warnings": [],
        "errors": messages,
        "resolution_steps": _resolution_steps(messages, target=target),
        "show_consistency_table": False,
    }


def _build_execution_payload(
    *,
    latest_report: dict[str, Any] | None,
    execution_state: dict[str, Any] | None,
    selected_slug: str,
) -> dict[str, Any] | None:
    current_state = dict(execution_state or {})
    chosen_report = latest_report
    if current_state and str(current_state.get("slug") or "").strip().lower() == str(selected_slug or "").strip().lower():
        report_path = str(current_state.get("report_path") or "").strip()
        if report_path:
            report = _load_report_payload(report_path)
            if report:
                if chosen_report is None or _report_sort_key(report) >= _report_sort_key(chosen_report):
                    chosen_report = report
        if current_state.get("error_message"):
            return _build_failed_execution(
                target=str(current_state.get("target") or "").strip().lower(),
                error_message=str(current_state.get("error_message") or "").strip(),
                generated_at=str(current_state.get("generated_at") or ""),
            )
    if chosen_report is None:
        return None
    return _build_postgres_execution(chosen_report) if str(chosen_report.get("target") or "").strip().lower() == "postgresql" else _build_sqlite_execution(chosen_report)


def _effective_count(domain: dict[str, Any], effective_runtime_kind: str) -> int:
    kind = str(domain.get("storage_kind") or "")
    if kind == "filesystem":
        return int(domain.get("json_count") or 0)
    runtime = str(effective_runtime_kind or "").strip().lower()
    if runtime == "postgresql" and kind in {"core", "repository", "sql_pipeline"}:
        return int(domain.get("postgres_count") or 0)
    if runtime == "sqlite" and kind in {"core", "repository", "sqlite_repository", "sql_pipeline"}:
        return int(domain.get("sqlite_count") or 0)
    return int(domain.get("json_count") or 0)


def _module_cards(inventory: dict[str, Any], effective_runtime_kind: str) -> list[dict[str, Any]]:
    index = {row["code"]: row for row in inventory.get("domains", [])}
    cards = [
        {
            "title": "Clienti",
            "count": _effective_count(index.get("clienti", {}), effective_runtime_kind),
            "status": "ok" if _effective_count(index.get("clienti", {}), effective_runtime_kind) else "warning",
            "next_step": "Verificare anagrafica, codici fiscali, PEC e soggetti collegati.",
        },
        {
            "title": "Fascicoli",
            "count": _effective_count(index.get("fascicoli", {}), effective_runtime_kind),
            "status": "ok" if _effective_count(index.get("fascicoli", {}), effective_runtime_kind) else "warning",
            "next_step": "Allineare numero RG, tribunale, controparte e pratica attiva.",
        },
        {
            "title": "Appuntamenti",
            "count": _effective_count(index.get("appuntamenti", {}), effective_runtime_kind),
            "status": "ok" if _effective_count(index.get("appuntamenti", {}), effective_runtime_kind) else "warning",
            "next_step": "Importare udienze, riunioni e reminder della prima settimana.",
        },
        {
            "title": "Scadenze",
            "count": _effective_count(index.get("scadenze", {}), effective_runtime_kind),
            "status": "ok" if _effective_count(index.get("scadenze", {}), effective_runtime_kind) else "warning",
            "next_step": "Presidiare termini perentori e scadenze operative collegate.",
        },
        {
            "title": "Documenti",
            "count": _effective_count(index.get("documenti", {}), effective_runtime_kind),
            "status": "ok" if _effective_count(index.get("documenti", {}), effective_runtime_kind) else "warning",
            "next_step": "Indicizzare PDF, DOCX e firmati .p7m dei fascicoli prioritari.",
        },
        {
            "title": "Template base",
            "count": _effective_count(index.get("template_atti", {}), effective_runtime_kind),
            "status": "ok" if _effective_count(index.get("template_atti", {}), effective_runtime_kind) else "warning",
            "next_step": "Mappare i modelli interni piu' usati e le clausole ricorrenti.",
        },
    ]
    return cards


def build_migration_assistant(*, selected_slug: str = "", execution_state: dict[str, Any] | None = None) -> dict[str, Any]:
    tm, studio = _resolve_selected_studio(selected_slug)
    migration_program = build_migration_program_payload()
    storage_parity = build_storage_parity_payload()
    workflow = [
        "1. Caricare clienti e soggetti essenziali.",
        "2. Importare fascicoli aperti e documenti chiave.",
        "3. Sincronizzare agenda, udienze e scadenziario.",
        "4. Validare PEC, firma e canali telematici.",
        "5. Attivare Lex sui fascicoli prioritari e sulla regia giornaliera.",
    ]
    studies = [
        {
            "slug": studio_item.slug,
            "nome": studio_item.nome,
            "selected": bool(studio and studio_item.slug == studio.slug),
            "db_mode": studio_item.database.normalized_mode,
            "effective_runtime_kind": studio_item.database.effective_runtime_kind,
        }
        for studio_item in tm.lista()
    ]
    if studio is None:
        return {
            "studios": studies,
            "selected_studio": None,
            "modules": [],
            "workflow": workflow,
            "built_in_templates": len(TUTTI_I_TEMPLATE),
            "migration_program": migration_program,
            "storage_parity": storage_parity["summary"],
            "inventory": {"domains": [], "postgres_online": False},
            "latest_report": None,
            "last_execution": None,
        }

    paths = tm.percorsi_dati(studio.slug)
    inventory = build_full_storage_inventory(
        paths=paths,
        database_config=studio.database,
        tenant_slug=studio.slug,
    )
    latest_report = _latest_report_payload(paths["BACKUP_DIR"])
    effective_runtime_kind = studio.database.effective_runtime_kind

    execution = _build_execution_payload(
        latest_report=latest_report,
        execution_state=execution_state,
        selected_slug=studio.slug,
    )

    return {
        "studios": studies,
        "selected_studio": {
            "slug": studio.slug,
            "nome": studio.nome,
            "selected_mode": studio.database.normalized_mode,
            "effective_runtime_kind": effective_runtime_kind,
            "core_runtime_enabled": bool(studio.database.core_runtime_enabled),
            "connessione_ok": bool(studio.database.connessione_ok),
            "connection_url_safe": studio.database.connection_url_safe,
        },
        "modules": _module_cards(inventory, effective_runtime_kind),
        "workflow": workflow,
        "built_in_templates": len(TUTTI_I_TEMPLATE),
        "migration_program": migration_program,
        "storage_parity": storage_parity["summary"],
        "inventory": inventory,
        "latest_report": latest_report,
        "can_run_postgres": _has_postgres_credentials(studio.database),
        "last_execution": execution,
    }


def execute_migration_assistant(*, selected_slug: str, target: str) -> dict[str, Any]:
    tm, studio = _resolve_selected_studio(selected_slug)
    if studio is None:
        raise ValueError("Nessuno studio disponibile per la migrazione.")
    paths = tm.percorsi_dati(studio.slug)
    wanted = str(target or "").strip().lower()
    previous_config = _copy_database_config(studio.database)
    if wanted == "sqlite":
        sqlite_config = _sqlite_target_config(studio.database)
        tm.aggiorna_db_config(studio.slug, sqlite_config)
        try:
            payload = tm.provision_storage_backend(studio.slug, migrate_existing=True)
        except Exception:
            tm.aggiorna_db_config(studio.slug, previous_config)
            raise
        if not payload.get("ok"):
            tm.aggiorna_db_config(studio.slug, previous_config)
            raise RuntimeError(
                str(payload.get("error") or "Migrazione completa SQLite non riuscita.")
            )
        report = dict(payload.get("migration_report") or payload)
        return attach_migration_rollback_context(
            report=report,
            paths=paths,
            tenant_slug=studio.slug,
            previous_database_config=previous_config,
        )
    if wanted == "postgresql":
        if not _has_postgres_credentials(studio.database):
            raise ValueError(
                "Configura prima il backend PostgreSQL nello studio selezionato e riprova."
            )
        postgres_config = _postgres_target_config(studio.database)
        tm.aggiorna_db_config(studio.slug, postgres_config)
        connection_test = tm.testa_connessione(studio.slug)
        if not connection_test.get("ok"):
            tm.aggiorna_db_config(studio.slug, previous_config)
            raise RuntimeError(
                str(connection_test.get("messaggio") or "Connessione PostgreSQL non disponibile.")
            )
        try:
            payload = tm.provision_storage_backend(
                studio.slug,
                migrate_existing=True,
                activate_external=True,
                secret_key=current_app.secret_key,
            )
        except Exception:
            tm.aggiorna_db_config(studio.slug, previous_config)
            raise
        if not payload.get("ok"):
            tm.aggiorna_db_config(studio.slug, previous_config)
            raise RuntimeError(
                str(payload.get("error") or "Migrazione completa PostgreSQL non riuscita.")
            )
        report = dict(payload.get("migration_report") or payload)
        return attach_migration_rollback_context(
            report=report,
            paths=paths,
            tenant_slug=studio.slug,
            previous_database_config=previous_config,
        )
    raise ValueError("Target di migrazione non supportato.")

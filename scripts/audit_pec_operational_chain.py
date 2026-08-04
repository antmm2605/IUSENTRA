from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.pec_pipeline import _is_remote_hearing_url  # noqa: E402
from pct.tenant import GestioneTenant  # noqa: E402


def _registry_path(value: str = "") -> Path:
    raw = (
        value
        or os.environ.get("TENANTS_REGISTRY")
        or os.environ.get("IUSENTRA_TENANTS_REGISTRY")
        or os.environ.get("PCT_TENANTS_REGISTRY")
        or "data/tenants.json"
    )
    return Path(raw)


def _matches(slug: str, wanted: str) -> bool:
    if not wanted:
        return True
    return slug == wanted or slug.lower() == wanted.lower()


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _json_rows(path: Path) -> list[dict[str, Any]]:
    raw = _load_json(path, [])
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("items", "records", "data", "emails", "scadenze", "appuntamenti", "notifiche"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [item for item in raw.values() if isinstance(item, dict)]
    return []


def _email_relevant_for_pec(row: dict[str, Any]) -> bool:
    attachments = " ".join(
        str(item.get("nome") or item.get("nome_file") or "")
        for item in list(row.get("allegati") or [])
        if isinstance(item, dict)
    ).lower()
    text = " ".join(
        str(value or "")
        for value in (
            row.get("oggetto"),
            row.get("mittente"),
            row.get("mittente_nome"),
            row.get("corpo_testo"),
            row.get("stato_pct"),
            attachments,
        )
    ).lower()
    status_pct = str(row.get("stato_pct") or "").upper()
    origin = str(row.get("origine") or "").lower()
    return bool(
        row.get("e_pst")
        or status_pct
        or "pec" in origin
        or "posta certificata" in text
        or "giustiziacert" in text
        or "ptel.giustizia" in text
        or "deposito telematico" in text
        or "daticert" in text
        or "postacert" in text
        or any(marker in status_pct for marker in ("WARN", "RIFIUT", "ERRORE", "ACCETT", "CONSEGN", "CONTROLL", "DEPOSIT"))
    )


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    queries = {
        "pec_messages": "SELECT COUNT(*) FROM pec_messages",
        "pec_attachments": "SELECT COUNT(*) FROM pec_attachments",
        "pec_jobs": "SELECT COUNT(*) FROM pec_jobs",
        "pec_validation_reports": "SELECT COUNT(*) FROM pec_validation_reports",
        "pec_local_acquire_items": "SELECT COUNT(*) FROM pec_local_acquire_items",
        "notifications": "SELECT COUNT(*) FROM notifications",
        "push_subscriptions": "SELECT COUNT(*) FROM push_subscriptions",
        "notification_preferences": "SELECT COUNT(*) FROM notification_preferences",
        "notification_deliveries": "SELECT COUNT(*) FROM notification_deliveries",
    }
    query = queries.get(table)
    if not query:
        return 0
    try:
        return int(conn.execute(query).fetchone()[0] or 0)
    except sqlite3.Error:
        return 0


def _group_count(conn: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    queries = {
        ("pec_local_acquire_items", "status"): (
            "SELECT COALESCE(status, '') AS value, COUNT(*) AS total "
            "FROM pec_local_acquire_items GROUP BY status"
        ),
        ("pec_local_acquire_items", "deadline_status"): (
            "SELECT COALESCE(deadline_status, '') AS value, COUNT(*) AS total "
            "FROM pec_local_acquire_items GROUP BY deadline_status"
        ),
        ("pec_jobs", "status"): "SELECT COALESCE(status, '') AS value, COUNT(*) AS total FROM pec_jobs GROUP BY status",
        ("notifications", "type"): "SELECT COALESCE(type, '') AS value, COUNT(*) AS total FROM notifications GROUP BY type",
        ("notification_deliveries", "status"): (
            "SELECT COALESCE(status, '') AS value, COUNT(*) AS total "
            "FROM notification_deliveries GROUP BY status"
        ),
    }
    query = queries.get((table, column))
    if not query:
        return {}
    try:
        rows = conn.execute(query).fetchall()
    except sqlite3.Error:
        return {}
    return {str(row["value"]): int(row["total"] or 0) for row in rows}


def _url_fingerprint(url: str) -> dict[str, str]:
    parsed = urlsplit(str(url or ""))
    return {
        "host": parsed.netloc.lower(),
        "path_prefix": parsed.path[:80],
        "sha256": hashlib.sha256(str(url or "").encode("utf-8", errors="ignore")).hexdigest(),
    }


def _iter_report_links(report: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    candidates = [
        report.get("remote_hearing"),
        (report.get("procedural_profile") or {}).get("remote_hearing")
        if isinstance(report.get("procedural_profile"), dict)
        else {},
        (report.get("deadline_proposal") or {}).get("remote_hearing")
        if isinstance(report.get("deadline_proposal"), dict)
        else {},
    ]
    seen: set[str] = set()
    for remote in candidates:
        if not isinstance(remote, dict):
            continue
        for item in list(remote.get("links") or []):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            values.append(item)
    return values


def _report_has_127_false_remote(report: dict[str, Any]) -> bool:
    remote = report.get("remote_hearing")
    procedural = report.get("procedural_profile") if isinstance(report.get("procedural_profile"), dict) else {}
    proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
    if not isinstance(remote, dict) or not (remote.get("detected") or remote.get("links")):
        return False
    if proposal.get("auto_create") and proposal.get("due_date"):
        return False
    blob = json.dumps(procedural, ensure_ascii=False).lower()
    normalized = blob.replace("-", " ")
    is_decisory = any(
        marker in normalized
        for marker in (
            "sentenza a verbale",
            "sentenza resa",
            "sentenza definitiva",
            "provvedimento decisorio",
        )
    )
    return is_decisory and "127 ter" in normalized


def _audit_pec_db(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    report: dict[str, Any] = {"exists": True}
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        report["messages"] = _table_count(conn, "pec_messages")
        report["attachments"] = _table_count(conn, "pec_attachments")
        report["jobs"] = _table_count(conn, "pec_jobs")
        report["validation_reports"] = _table_count(conn, "pec_validation_reports")
        report["local_acquire_items"] = _table_count(conn, "pec_local_acquire_items")
        report["local_status"] = _group_count(conn, "pec_local_acquire_items", "status")
        report["deadline_status"] = _group_count(conn, "pec_local_acquire_items", "deadline_status")
        report["job_status"] = _group_count(conn, "pec_jobs", "status")
        latest_by_email: dict[str, dict[str, Any]] = {}
        latest_by_message: dict[str, dict[str, Any]] = {}
        try:
            local_rows = conn.execute(
                """
                SELECT email_id, message_id, status, deadline_status, updated_at
                FROM pec_local_acquire_items
                ORDER BY updated_at DESC, rowid DESC
                """
            ).fetchall()
        except sqlite3.Error:
            local_rows = []
        for local in local_rows:
            payload = {
                "email_id": str(local["email_id"] or ""),
                "message_id": str(local["message_id"] or ""),
                "status": str(local["status"] or ""),
                "deadline_status": str(local["deadline_status"] or ""),
                "updated_at": str(local["updated_at"] or ""),
            }
            email_id = payload["email_id"]
            message_id = payload["message_id"]
            if email_id and email_id not in latest_by_email:
                latest_by_email[email_id] = payload
            if message_id and message_id not in latest_by_message:
                latest_by_message[message_id] = payload
        report["latest_local_status"] = {
            "by_email": {},
            "by_message": {},
            "missing_mime_latest": sum(1 for item in latest_by_email.values() if item.get("status") == "missing_mime"),
        }
        for item in latest_by_email.values():
            status = str(item.get("status") or "")
            by_email = report["latest_local_status"]["by_email"]
            by_email[status] = int(by_email.get(status) or 0) + 1
        for item in latest_by_message.values():
            status = str(item.get("status") or "")
            by_message = report["latest_local_status"]["by_message"]
            by_message[status] = int(by_message.get(status) or 0) + 1
        # Dato tecnico interno: serve al confronto puntuale con gli identificativi
        # dell'archivio locale, senza inferire la copertura dai soli conteggi.
        report["_latest_local_email_ids"] = set(latest_by_email)
        reports = []
        try:
            rows = conn.execute(
                """
                SELECT r.message_id, r.report_json
                FROM pec_validation_reports r
                JOIN (
                    SELECT message_id, MAX(rowid) AS latest_rowid
                    FROM pec_validation_reports
                    GROUP BY message_id
                ) latest ON latest.message_id = r.message_id AND latest.latest_rowid = r.rowid
                """
            ).fetchall()
        except sqlite3.Error:
            rows = []
        invalid_links: list[dict[str, Any]] = []
        valid_links: list[dict[str, Any]] = []
        false_127 = 0
        auto_create = due_future = due_expired = due_empty = 0
        today = datetime.now().date().isoformat()
        for row in rows:
            try:
                current = json.loads(row["report_json"] or "{}")
            except Exception:
                current = {}
            reports.append(current)
            if _report_has_127_false_remote(current):
                false_127 += 1
            proposal = current.get("deadline_proposal") if isinstance(current.get("deadline_proposal"), dict) else {}
            if proposal.get("auto_create"):
                auto_create += 1
            due = str(proposal.get("due_date") or "")
            if due:
                if due[:10] < today:
                    due_expired += 1
                else:
                    due_future += 1
            else:
                due_empty += 1
            for item in _iter_report_links(current):
                url = str(item.get("url") or "")
                ok, reason = _is_remote_hearing_url(url, context=str(item.get("source") or ""))
                row_payload = {
                    "message_id": str(row["message_id"] or ""),
                    "source": str(item.get("source") or ""),
                    "reason": reason,
                    "link": _url_fingerprint(url),
                }
                if ok:
                    valid_links.append(row_payload)
                else:
                    invalid_links.append(row_payload)
        report["latest_reports"] = len(rows)
        report["deadline_proposals"] = {
            "auto_create": auto_create,
            "future_or_today": due_future,
            "expired": due_expired,
            "without_due_date": due_empty,
        }
        report["remote_hearing"] = {
            "valid_links": len(valid_links),
            "invalid_links": len(invalid_links),
            "false_127_remote_reports": false_127,
            "sample_valid_links": valid_links[:5],
            "sample_invalid_links": invalid_links[:10],
        }
    return report


def _audit_scadenze(path: Path) -> dict[str, Any]:
    rows = _json_rows(path)
    pec_rows = [row for row in rows if "PEC_AUDIT:" in str(row.get("note", ""))]
    invalid_links = []
    valid_links = []
    for row in pec_rows:
        url = str(row.get("remote_hearing_url") or "")
        if not url:
            continue
        ok, reason = _is_remote_hearing_url(url, context=str(row.get("remote_hearing_source") or ""))
        payload = {
            "id": str(row.get("id") or ""),
            "title": str(row.get("titolo") or "")[:160],
            "reason": reason,
            "link": _url_fingerprint(url),
        }
        if ok:
            valid_links.append(payload)
        else:
            invalid_links.append(payload)
    return {
        "exists": path.exists(),
        "total": len(rows),
        "pec_deadlines": len(pec_rows),
        "pec_with_agenda": sum(1 for row in pec_rows if str(row.get("id_appuntamento") or "").strip()),
        "pec_by_type": {
            "UDIENZA": sum(1 for row in pec_rows if str(row.get("tipo") or "").upper() == "UDIENZA"),
            "ADEMPIMENTO": sum(1 for row in pec_rows if str(row.get("tipo") or "").upper() == "ADEMPIMENTO"),
            "TERMINE": sum(1 for row in pec_rows if str(row.get("tipo") or "").upper() == "TERMINE"),
        },
        "remote_hearing": {
            "detected": sum(1 for row in pec_rows if row.get("remote_hearing_detected")),
            "valid_links": len(valid_links),
            "invalid_links": len(invalid_links),
            "pdf_required": sum(1 for row in pec_rows if row.get("remote_hearing_pdf_required")),
            "sample_valid_links": valid_links[:5],
            "sample_invalid_links": invalid_links[:10],
        },
    }


def _audit_agenda(path: Path) -> dict[str, Any]:
    rows = _json_rows(path)
    pec_rows = [
        row
        for row in rows
        if str(row.get("external_uid") or "").startswith("PEC_AUDIT:")
        or "PEC_AUDIT:" in str(row.get("note") or "")
        or "Presidio PEC" in str(row.get("titolo") or "")
    ]
    return {"exists": path.exists(), "total": len(rows), "pec_items": len(pec_rows)}


def _audit_notifications(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        return {
            "exists": True,
            "notifications": _table_count(conn, "notifications"),
            "push_subscriptions": _table_count(conn, "push_subscriptions"),
            "notification_preferences": _table_count(conn, "notification_preferences"),
            "notification_deliveries": _table_count(conn, "notification_deliveries"),
            "by_type": _group_count(conn, "notifications", "type"),
            "deliveries_by_status": _group_count(conn, "notification_deliveries", "status"),
        }


def audit_studio(paths: dict[str, str]) -> dict[str, Any]:
    base = Path(paths["EMAIL_CASELLA_DB"]).parent.parent
    email_rows = _json_rows(Path(paths["EMAIL_CASELLA_DB"]))
    pec_relevant_rows = [row for row in email_rows if _email_relevant_for_pec(row)]
    pec_db = Path(paths["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite"
    result = {
        "data_dir": str(base),
        "email_archive": {
            "exists": Path(paths["EMAIL_CASELLA_DB"]).exists(),
            "local_rows": len(email_rows),
            "pec_relevant": len(pec_relevant_rows),
            "with_eml_file": sum(1 for row in email_rows if str(row.get("eml_file") or "").strip()),
            "with_attachments": sum(1 for row in email_rows if row.get("allegati")),
        },
        "pec_control": _audit_pec_db(pec_db),
        "scadenziario": _audit_scadenze(Path(paths["SCADENZIARIO_DB"])),
        "agenda": _audit_agenda(Path(paths["AGENDA_DB"])),
        "notifications": _audit_notifications(Path(paths["NOTIFICATIONS_DB"])),
    }
    latest_email_ids = set(result["pec_control"].pop("_latest_local_email_ids", set())) if isinstance(result["pec_control"], dict) else set()
    pec_source_ids = {str(row.get("id") or "").strip() for row in pec_relevant_rows if str(row.get("id") or "").strip()}
    missing_local_ids = pec_source_ids - latest_email_ids
    result["email_archive"]["pec_controllabili"] = len(pec_source_ids)
    result["pec_control"]["local_coverage"] = {
        "expected": len(pec_source_ids),
        "controlled": len(pec_source_ids & latest_email_ids),
        "missing": len(missing_local_ids),
    }
    remote = result["pec_control"].get("remote_hearing", {}) if isinstance(result["pec_control"], dict) else {}
    scad_remote = result["scadenziario"].get("remote_hearing", {}) if isinstance(result["scadenziario"], dict) else {}
    blocking = []
    if int(remote.get("invalid_links") or 0):
        blocking.append("Report PEC con link tecnici/non udienza ancora presenti.")
    if int(remote.get("false_127_remote_reports") or 0):
        blocking.append("Report PEC 127-ter/sentenza classificati come udienza da remoto.")
    if int(scad_remote.get("invalid_links") or 0):
        blocking.append("Scadenziario con link udienza non valido.")
    local_coverage = result["pec_control"].get("local_coverage", {}) if isinstance(result["pec_control"], dict) else {}
    if int(local_coverage.get("missing") or 0):
        blocking.append(
            "PEC rilevanti non presidiate nell'archivio locale: "
            f"{local_coverage.get('controlled', 0)}/{local_coverage.get('expected', 0)}."
        )
    latest_local = result["pec_control"].get("latest_local_status", {}) if isinstance(result["pec_control"], dict) else {}
    if int(latest_local.get("missing_mime_latest") or 0):
        blocking.append("PEC ancora marcate missing_mime nell'ultimo presidio per email.")
    result["ok"] = not blocking
    result["blocking"] = blocking
    return result


def run_audit(*, registry: Path, tenant: str = "") -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if _matches(studio.slug, tenant)]
    payload: dict[str, Any] = {"ok": True, "registry": str(registry), "studios": {}}
    if not studios:
        payload["ok"] = False
        payload["errors"] = [
            f"Studio non trovato: {tenant}" if tenant else "Nessuno studio attivo nel registry: audit PEC non eseguito."
        ]
        return payload
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        studio_report = audit_studio(paths)
        payload["studios"][studio.slug] = studio_report
        payload["ok"] = bool(payload["ok"] and studio_report.get("ok"))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit catena PEC -> scadenziario -> agenda -> notifiche -> mobile.")
    parser.add_argument("--registry", default="", help="Percorso registry tenant; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio da controllare; vuoto = tutti gli studi nel registry.")
    args = parser.parse_args()
    result = run_audit(registry=_registry_path(args.registry), tenant=args.tenant)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

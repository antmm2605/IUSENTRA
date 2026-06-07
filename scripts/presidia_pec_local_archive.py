from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.email_client import GestioneEmailRicevute  # noqa: E402
from pct.notifications import NotificationRepository, NotificationService  # noqa: E402
from pct.pec_control_tower import PecControlTowerRepository, _reconstruct_email_archive_mime  # noqa: E402
from pct.pec_pipeline import PecAuditRepository, parse_pec_message  # noqa: E402
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


def _email_sort_key(email_obj: Any) -> str:
    return str(
        getattr(email_obj, "timestamp", "")
        or getattr(email_obj, "data", "")
        or getattr(email_obj, "ricevuta_il", "")
        or ""
    )


def _email_relevant_for_pec(email_obj: Any) -> bool:
    allegati = " ".join(
        str(item.get("nome") or item.get("nome_file") or "")
        for item in list(getattr(email_obj, "allegati", []) or [])
        if isinstance(item, dict)
    ).lower()
    text = " ".join(
        str(value or "")
        for value in (
            getattr(email_obj, "oggetto", ""),
            getattr(email_obj, "mittente", ""),
            getattr(email_obj, "mittente_nome", ""),
            getattr(email_obj, "corpo_testo", ""),
            getattr(email_obj, "stato_pct", ""),
            allegati,
        )
    ).lower()
    status_pct = str(getattr(email_obj, "stato_pct", "") or "").upper()
    message_id = str(getattr(email_obj, "message_id", "") or "").strip()
    origin = str(getattr(email_obj, "origine", "") or "").lower()
    return bool(
        getattr(email_obj, "e_pst", False)
        or message_id
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


def _read_or_reconstruct_mime(gestore: GestioneEmailRicevute, email_obj: Any) -> tuple[bytes, str]:
    raw_mime = gestore.leggi_eml_originale(email_obj)
    if raw_mime:
        return bytes(raw_mime), "originale"
    try:
        reconstructed = _reconstruct_email_archive_mime(gestore, email_obj)
    except Exception:
        reconstructed = b""
    if reconstructed:
        return bytes(reconstructed), "ricostruito"
    return b"", ""


def _schedule_deadline_with_local_mime(
    repo: PecAuditRepository,
    *,
    message_id: str,
    raw_mime: bytes,
    actor: str,
) -> dict[str, Any]:
    try:
        persisted = repo.schedule_deadline(message_id, actor=actor)
        if persisted.get("ok") or persisted.get("expired"):
            return persisted
    except Exception as exc:
        persisted = {"ok": False, "message": f"Audit PEC non disponibile: {exc}"}
    try:
        parsed = parse_pec_message(raw_mime)
        return repo.schedule_deadline_from_payload(
            message_id,
            parsed=parsed,
            message={"linked_fascicolo_id": ""},
            actor=actor,
        )
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Presidio non pronto: {persisted.get('message') or 'report mancante'}; MIME locale non schedulabile: {exc}",
        }


def _deadline_status(result: dict[str, Any]) -> str:
    if result.get("ok") and result.get("already_exists"):
        return "deadline_already_exists"
    if result.get("ok"):
        return "deadline_created"
    if result.get("expired"):
        return "deadline_expired"
    return "deadline_not_ready"


def _add_unique(values: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def _notification_user_ids(path: Path, actor: str, *, auth_path: Path | None = None) -> list[str]:
    values: list[str] = []
    if auth_path and auth_path.exists():
        try:
            from pct.auth import GestioneUtenti

            users = GestioneUtenti(
                db_path=str(auth_path),
                audit_path=str(auth_path.with_name("audit.json")),
                secret_key=os.environ.get("SECRET_KEY", ""),
                crea_admin_se_vuoto=False,
            ).tutti(solo_attivi=True)
            for user in users:
                _add_unique(values, getattr(user, "id", "") or getattr(user, "username", ""))
        except Exception:
            pass
    try:
        import sqlite3

        with sqlite3.connect(str(path)) as conn:
            queries = (
                "SELECT DISTINCT user_id FROM push_subscriptions WHERE COALESCE(user_id, '')<>'' LIMIT 40",
                "SELECT DISTINCT user_id FROM notification_preferences WHERE COALESCE(user_id, '')<>'' LIMIT 40",
                "SELECT DISTINCT user_id FROM notifications WHERE COALESCE(user_id, '')<>'' LIMIT 40",
            )
            for query in queries:
                try:
                    rows = conn.execute(query).fetchall()
                except sqlite3.Error:
                    continue
                for row in rows:
                    _add_unique(values, row[0])
    except Exception:
        pass
    fallback = str(actor or "pec-maintenance").strip()
    _add_unique(values, fallback)
    return values


def _notify_deadline(
    *,
    paths: dict[str, str],
    tenant_id: str,
    user_ids: list[str],
    message_id: str,
    result: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    if not result.get("ok"):
        return {"created": 0, "push_configured": False, "push_attempted": 0, "push_sent": 0}
    deadline_id = str(result.get("deadline_id") or "").strip()
    if not deadline_id:
        return {"created": 0, "push_configured": False, "push_attempted": 0, "push_sent": 0}
    agenda = result.get("agenda") if isinstance(result.get("agenda"), dict) else {}
    agenda_id = str(agenda.get("agenda_id") or "")
    due_date = str(result.get("due_date") or "")
    summary = {"created": 0, "push_configured": False, "push_attempted": 0, "push_sent": 0}
    try:
        service = NotificationService(NotificationRepository(paths["NOTIFICATIONS_DB"]))
    except Exception as exc:
        return {"created": 0, "push_configured": False, "push_attempted": 0, "push_sent": 0, "error": str(exc)[:180]}
    agenda_text = " e all'agenda" if agenda_id else ""
    due_text = f" per il {due_date}" if due_date else ""
    for user_id in user_ids:
        try:
            _record, created, push = service.create_notification(
                tenant_id=tenant_id,
                user_id=user_id or actor,
                type="pec_deadline",
                priority="important",
                title="Scadenza PEC registrata",
                body=f"Presidio PEC collegato allo scadenziario{agenda_text}{due_text}.",
                href="/scadenziario?vista=pec",
                source_type="pec_deadline",
                source_id=message_id or deadline_id,
                dedupe_key=f"PEC_AUDIT:{message_id or deadline_id}:deadline",
                payload_json={
                    "deadlineId": deadline_id,
                    "agendaId": agenda_id,
                    "dueDate": due_date,
                    "alreadyExists": bool(result.get("already_exists")),
                },
                send_push=True,
            )
        except Exception as exc:
            summary["error"] = str(exc)[:180]
            continue
        summary["created"] += int(bool(created))
        summary["push_configured"] = bool(summary["push_configured"] or push.configured)
        summary["push_attempted"] += int(push.attempted or 0)
        summary["push_sent"] += int(push.sent or 0)
    return summary


def _record_item(
    repo: PecAuditRepository,
    run_id: str,
    *,
    email_id: str,
    message_id: str = "",
    subject: str = "",
    status: str,
    deadline_status: str = "",
    due_date: str = "",
    deadline_id: str = "",
    agenda_id: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    repo.record_local_acquire_item(
        run_id,
        email_id=email_id,
        message_id=message_id,
        subject=subject,
        status=status,
        deadline_status=deadline_status,
        due_date=due_date,
        deadline_id=deadline_id,
        agenda_id=agenda_id,
        detail=detail or {},
    )


def presidia_studio(
    *,
    studio_slug: str,
    paths: dict[str, str],
    limit: int = 0,
    actor: str = "pec-maintenance",
    worker_limit: int = 12000,
    queue_repairs: bool = True,
) -> dict[str, Any]:
    email_db = Path(paths["EMAIL_CASELLA_DB"])
    gestore = GestioneEmailRicevute(str(email_db))
    repo = PecAuditRepository(
        email_db.parent / "pec_audit.sqlite",
        tenant_id=studio_slug,
        clienti_db_path=paths["CLIENTI_DB"],
        fascicoli_db_path=paths["FASCICOLI_DB"],
        fascicoli_docs_path=paths["FASCICOLI_DOCS"],
        scadenziario_db_path=paths["SCADENZIARIO_DB"],
        agenda_db_path=paths["AGENDA_DB"],
    )
    control_tower = PecControlTowerRepository(
        email_db.parent / "pec_control_tower.sqlite",
        tenant_id=studio_slug,
        fascicoli_db_path=paths["FASCICOLI_DB"],
        fascicoli_docs_path=paths["FASCICOLI_DOCS"],
        scadenziario_db_path=paths["SCADENZIARIO_DB"],
        agenda_db_path=paths["AGENDA_DB"],
    )
    emails = sorted(
        list(gestore._carica().values()),  # noqa: SLF001 - manutenzione tenant-aware della casella locale
        key=_email_sort_key,
        reverse=True,
    )
    selected = emails[: max(0, int(limit or 0))] if int(limit or 0) > 0 else emails
    relevant = [item for item in selected if _email_relevant_for_pec(item)]
    run = repo.start_local_acquire_run(total_emails=len(selected), batch_size=max(1, len(relevant) or 1), actor=actor)
    run_id = str(run.get("id") or "")
    existing_by_header = repo.ids_by_header_message_ids(
        str(getattr(item, "message_id", "") or "").strip() for item in relevant
    )
    report: dict[str, Any] = {
        "ok": True,
        "studio": studio_slug,
        "emails_scanned": len(selected),
        "pec_relevant": len(relevant),
        "acquired": 0,
        "ingested": 0,
        "duplicates": 0,
        "reconstructed": 0,
        "missing_mime": 0,
        "queued_repairs": 0,
        "deadline_created": 0,
        "deadline_already_exists": 0,
        "deadline_expired": 0,
        "deadline_not_ready": 0,
        "agenda_linked": 0,
        "notifications_created": 0,
        "push_configured": False,
        "push_attempted": 0,
        "push_sent": 0,
        "errors": [],
    }
    local_mime_by_message_id: dict[str, bytes] = {}
    message_email_index: dict[str, dict[str, str]] = {}
    controlled_ids: list[str] = []

    for index, email_obj in enumerate(relevant):
        email_id = str(getattr(email_obj, "id", "") or f"email-{index}")
        subject = str(getattr(email_obj, "oggetto", "") or "")[:240]
        header = str(getattr(email_obj, "message_id", "") or "").strip()
        raw_mime, mime_source = _read_or_reconstruct_mime(gestore, email_obj)
        if mime_source == "ricostruito":
            report["reconstructed"] += 1
        existing_message_id = existing_by_header.get(header)
        if existing_message_id:
            report["acquired"] += 1
            report["duplicates"] += 1
            controlled_ids.append(existing_message_id)
            message_email_index[existing_message_id] = {"email_id": email_id, "subject": subject, "status": "duplicate"}
            if raw_mime:
                local_mime_by_message_id[existing_message_id] = raw_mime
                _record_item(
                    repo,
                    run_id,
                    email_id=email_id,
                    message_id=existing_message_id,
                    subject=subject,
                    status="duplicate",
                    detail={"mime_source": mime_source},
                )
            else:
                report["missing_mime"] += 1
                _record_item(repo, run_id, email_id=email_id, message_id=existing_message_id, subject=subject, status="missing_mime")
            if queue_repairs:
                try:
                    repair = repo.enqueue_missing_operational_jobs(existing_message_id, actor=actor)
                    report["queued_repairs"] += int(bool(repair.get("queued")))
                except Exception as exc:
                    report["errors"].append({"email_id": email_id, "errore": f"Riparazione audit non accodata: {exc}"[:180]})
            continue
        if not raw_mime:
            report["missing_mime"] += 1
            _record_item(repo, run_id, email_id=email_id, subject=subject, status="missing_mime")
            continue
        report["acquired"] += 1
        fallback_message_id = f"email:{email_id}"
        try:
            result = repo.ingest_mime(
                raw_mime,
                account_email=str(getattr(email_obj, "destinatari", "") or getattr(email_obj, "mittente", "") or "casella PEC locale")[:240],
                folder=str(getattr(email_obj, "cartella", "") or "INBOX"),
                imap_uid=str(getattr(email_obj, "uid_imap", "") or f"legacy:{email_id}"),
                actor=actor,
            )
        except Exception as exc:
            result = {"id": fallback_message_id, "duplicate": False, "error": str(exc)[:180]}
            report["errors"].append({"email_id": email_id, "errore": str(exc)[:180]})
        message_id = str(result.get("id") or "") or fallback_message_id
        controlled_ids.append(message_id)
        local_mime_by_message_id[message_id] = raw_mime
        status = "duplicate" if result.get("duplicate") else "ingested"
        report["duplicates"] += int(bool(result.get("duplicate")))
        report["ingested"] += int(not result.get("duplicate") and not result.get("error"))
        message_email_index[message_id] = {"email_id": email_id, "subject": subject, "status": status}
        _record_item(
            repo,
            run_id,
            email_id=email_id,
            message_id=message_id,
            subject=subject,
            status=status,
            detail={"mime_source": mime_source, "mime_sha256": result.get("mime_sha256") or ""},
        )
        try:
            control_tower.ingest_eml(
                raw_mime,
                account_email=str(getattr(email_obj, "destinatari", "") or getattr(email_obj, "mittente", "") or "casella PEC locale")[:240],
                folder=str(getattr(email_obj, "cartella", "") or "INBOX"),
                actor=actor,
            )
        except Exception as exc:
            report["errors"].append({"email_id": email_id, "errore": f"Control Tower non aggiornata: {exc}"[:180]})
        if queue_repairs:
            try:
                repair = repo.enqueue_missing_operational_jobs(message_id, actor=actor)
                report["queued_repairs"] += int(bool(repair.get("queued")))
            except Exception as exc:
                report["errors"].append({"email_id": email_id, "errore": f"Riparazione audit non accodata: {exc}"[:180]})

    if worker_limit:
        try:
            report["workers"] = repo.run_pending_jobs(limit=max(1, int(worker_limit)), actor=actor)
        except Exception as exc:
            report["workers"] = {"processed": 0, "failed": 1, "error": str(exc)[:180]}
            report["errors"].append({"email_id": "pec-worker", "errore": str(exc)[:180]})
    try:
        refresh = repo.refresh_validation_reports(actor=actor, limit=0)
    except Exception as exc:
        refresh = {"ok": False, "error": str(exc)[:180]}
    report["refresh_reports"] = refresh

    unique_message_ids: list[str] = []
    seen: set[str] = set()
    for message_id in controlled_ids:
        if message_id and message_id not in seen:
            seen.add(message_id)
            unique_message_ids.append(message_id)
    existing_deadlines = repo.existing_deadlines_by_message_id(unique_message_ids)
    skipped_deadlines = repo.skipped_deadlines_by_message_id(unique_message_ids)
    notification_users = _notification_user_ids(
        Path(paths["NOTIFICATIONS_DB"]),
        actor,
        auth_path=Path(paths["AUTH_DB"]) if paths.get("AUTH_DB") else None,
    )
    for message_id in unique_message_ids:
        meta = message_email_index.get(message_id, {})
        existing = existing_deadlines.get(message_id) if isinstance(existing_deadlines, dict) else None
        if existing and existing.get("agenda_id"):
            result = {
                "ok": True,
                "message": "Scadenza PEC già presente e collegata all'agenda.",
                "due_date": str(existing.get("due_date") or ""),
                "deadline_id": str(existing.get("deadline_id") or ""),
                "agenda": {"agenda_id": str(existing.get("agenda_id") or "")},
                "already_exists": True,
                "expired": False,
            }
        else:
            skipped = skipped_deadlines.get(message_id) if isinstance(skipped_deadlines, dict) else None
            if skipped:
                result = {
                    "ok": False,
                    "message": str(skipped.get("message") or "Termine già superato: non riportato in scadenziario o agenda."),
                    "due_date": str(skipped.get("due_date") or ""),
                    "already_exists": False,
                    "expired": True,
                }
            elif local_mime_by_message_id.get(message_id):
                result = _schedule_deadline_with_local_mime(
                    repo,
                    message_id=message_id,
                    raw_mime=local_mime_by_message_id[message_id],
                    actor=actor,
                )
            else:
                result = {
                    "ok": False,
                    "message": "MIME originale o ricostruito non disponibile nella casella locale.",
                }
        status = _deadline_status(result)
        if status in report:
            report[status] += 1
        agenda = result.get("agenda") if isinstance(result.get("agenda"), dict) else {}
        agenda_id = str(agenda.get("agenda_id") or "")
        if agenda_id:
            report["agenda_linked"] += 1
        push = _notify_deadline(
            paths=paths,
            tenant_id=studio_slug,
            user_ids=notification_users,
            message_id=message_id,
            result=result,
            actor=actor,
        )
        report["notifications_created"] += int(push.get("created") or 0)
        report["push_configured"] = bool(report["push_configured"] or push.get("push_configured"))
        report["push_attempted"] += int(push.get("push_attempted") or 0)
        report["push_sent"] += int(push.get("push_sent") or 0)
        _record_item(
            repo,
            run_id,
            email_id=str(meta.get("email_id") or ""),
            message_id=message_id,
            subject=str(meta.get("subject") or ""),
            status=str(meta.get("status") or "processed"),
            deadline_status=status,
            due_date=str(result.get("due_date") or ""),
            deadline_id=str(result.get("deadline_id") or ""),
            agenda_id=agenda_id,
            detail={
                "ok": bool(result.get("ok")),
                "message": str(result.get("message") or "")[:180],
                "notification": push,
            },
        )
    try:
        report["repair_deadlines"] = repo.repair_pec_deadlines(actor=actor, limit=0)
        report["remote_hearing_backfill"] = repo.enrich_deadlines_with_remote_hearing_links(actor=actor, limit=0)
        report["control_tower"] = control_tower.backfill_from_email_archive(gestore, limit=len(relevant) or 1, actor=actor, max_seconds=0.0)
    except Exception as exc:
        report["errors"].append({"email_id": "pec-finalize", "errore": str(exc)[:180]})
    status = "completed" if not report["errors"] else "completed_with_warnings"
    run_report = repo.update_local_acquire_run(
        run_id,
        cursor_index=len(selected),
        total_emails=len(selected),
        batch_size=max(1, len(relevant) or 1),
        status=status,
        deltas={
            "acquired": int(report["acquired"]),
            "duplicates": int(report["duplicates"]),
            "skipped_missing_mime": int(report["missing_mime"]),
            "skipped_not_pec": max(0, len(selected) - len(relevant)),
            "queued_repairs": int(report["queued_repairs"]),
            "deadline_created": int(report["deadline_created"]),
            "deadline_already_exists": int(report["deadline_already_exists"]),
            "deadline_expired": int(report["deadline_expired"]),
            "deadline_not_ready": int(report["deadline_not_ready"]),
            "agenda_linked": int(report["agenda_linked"]),
            "errors": len(report["errors"]),
        },
        payload={"notification_users": notification_users},
        actor=actor,
    )
    report["run_id"] = run_id
    report["local_acquire"] = repo.local_acquire_run_report(run_id, limit=max(100, len(selected) or 1)) or run_report
    report["ok"] = not report["errors"] and int(report["missing_mime"] or 0) == 0
    return report


def run_presidio(*, registry: Path, tenant: str = "", limit: int = 0, actor: str = "pec-maintenance", worker_limit: int = 12000) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if _matches(studio.slug, tenant)]
    payload: dict[str, Any] = {"ok": True, "registry": str(registry), "studios": {}}
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        result = presidia_studio(
            studio_slug=studio.slug,
            paths=paths,
            limit=limit,
            actor=actor,
            worker_limit=worker_limit,
        )
        payload["studios"][studio.slug] = result
        payload["ok"] = bool(payload["ok"] and result.get("ok"))
    if tenant and not studios:
        payload["ok"] = False
        payload["errors"] = [f"Studio non trovato: {tenant}"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Presidia l'archivio PEC locale: MIME originali/ricostruiti, scadenziario, agenda, notifiche e Control Tower.")
    parser.add_argument("--registry", default="", help="Percorso registry tenant; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio da presidiare; vuoto = tutti gli studi nel registry.")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di email locali da scansionare per studio; 0 = tutte.")
    parser.add_argument("--actor", default="pec-maintenance", help="Attore audit da registrare.")
    parser.add_argument("--worker-limit", type=int, default=12000, help="Numero massimo di job PEC da eseguire per studio.")
    args = parser.parse_args()
    result = run_presidio(
        registry=_registry_path(args.registry),
        tenant=args.tenant,
        limit=args.limit,
        actor=args.actor,
        worker_limit=args.worker_limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

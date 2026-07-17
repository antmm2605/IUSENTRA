"""API REST per pipeline PEC audit-grade."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Response, g, jsonify, request

from pct.email_client import GestioneEmailRicevute
from pct.pec_control_tower import PecControlTowerRepository
from pct.pec_pipeline import PecAuditRepository, ingest_synthetic_dataset, parse_pec_message
from web.services.pec_pipeline_runtime import (
    build_pec_deadline_notification,
    email_rilevante_per_presidio_pec,
    local_email_sort_key,
    read_or_reconstruct_local_mime,
    rebuild_operational_matrix_for_paths,
    run_workers_for_paths,
    should_send_pec_deadline_web_push,
)
from web.services.security_redaction import redacted_json_response
from web.services.tenant_api_auth import api_key_valid_for_request
from web.services.tenant_paths import TenantDataPathError, tenant_data_path

pec_pipeline_api = Blueprint("pec_pipeline_api", __name__, url_prefix="/api/pec")


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or api_key_valid_for_request():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "errore": "Autenticazione richiesta."}), 401

    return wrapper


def _tenant_id() -> str:
    for value in (
        getattr(g, "api_tenant_slug", ""),
        getattr(g, "tenant_context_slug", ""),
        getattr(g, "tenant_slug", ""),
    ):
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    user = g.get("utente_corrente")
    candidate = str(getattr(user, "tenant_slug", "") or "").strip()
    return candidate or "default"


def _actor() -> str:
    user = g.get("utente_corrente")
    return str(getattr(user, "username", "") or getattr(user, "id", "") or "api")


def _runtime_path(key: str, default: str, *aliases: str, required: bool = True) -> str:
    try:
        return tenant_data_path(key, default, *aliases, require_tenant=required)
    except Exception:
        if not required:
            return ""
        raise


def _runtime_paths() -> dict[str, str]:
    paths = {str(key): str(value) for key, value in (getattr(g, "data_paths", {}) or {}).items() if value}
    defaults = {
        "EMAIL_CASELLA_DB": ("./email/casella.json", ()),
        "PEC_AUDIT_DB": ("", ()),
        "CLIENTI_DB": ("./clienti/anagrafica.json", ()),
        "FASCICOLI_DB": ("./fascicoli/fascicoli.json", ()),
        "FASCICOLI_DOCS": ("./fascicoli/documenti", ()),
        "SCADENZIARIO_DB": ("./scadenziario/scadenze.json", ()),
        "AGENDA_DB": ("./agenda/appuntamenti.json", ()),
        "CALENDAR_SYNC_DB": ("./agenda/calendar_sync.json", ()),
        "NOTIFICATIONS_DB": ("./notifications/notifications.db", ()),
        "AUTH_DB": ("./auth/utenti.json", ()),
        "AUDIT_DB": ("./auth/audit.json", ()),
    }
    for key, (default, aliases) in defaults.items():
        if key in paths and paths[key]:
            continue
        value = _runtime_path(key, default, *aliases, required=bool(default))
        if value:
            paths[key] = value
    if not paths.get("PEC_AUDIT_DB") and paths.get("EMAIL_CASELLA_DB"):
        paths["PEC_AUDIT_DB"] = str(Path(paths["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite")
    return paths


def _repo() -> PecAuditRepository:
    email_db = Path(_runtime_path("EMAIL_CASELLA_DB", "./email/casella.json"))
    paths = getattr(g, "data_paths", {}) or {}
    configured_db = paths.get("PEC_AUDIT_DB")
    db_path = Path(str(configured_db)) if configured_db else email_db.parent / "pec_audit.sqlite"
    return PecAuditRepository(
        db_path,
        tenant_id=_tenant_id(),
        clienti_db_path=_runtime_path("CLIENTI_DB", "./clienti/anagrafica.json"),
        fascicoli_db_path=_runtime_path("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_runtime_path("FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_runtime_path("SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_runtime_path("AGENDA_DB", "./agenda/appuntamenti.json"),
        calendar_sync_db_path=_runtime_path("CALENDAR_SYNC_DB", "./agenda/calendar_sync.json", required=False),
    )


def _control_tower_repo() -> PecControlTowerRepository:
    email_db = Path(_runtime_path("EMAIL_CASELLA_DB", "./email/casella.json"))
    paths = getattr(g, "data_paths", {}) or {}
    configured_db = paths.get("PEC_CONTROL_TOWER_DB")
    db_path = Path(str(configured_db)) if configured_db else email_db.parent / "pec_control_tower.sqlite"
    return PecControlTowerRepository(
        db_path,
        tenant_id=_tenant_id(),
        fascicoli_db_path=_runtime_path("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_runtime_path("FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_runtime_path("SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_runtime_path("AGENDA_DB", "./agenda/appuntamenti.json"),
        calendar_sync_db_path=_runtime_path("CALENDAR_SYNC_DB", "./agenda/calendar_sync.json", required=False),
    )


def _control_tower_feed_repo() -> PecControlTowerRepository:
    email_db = Path(_runtime_path("EMAIL_CASELLA_DB", "./email/casella.json"))
    paths = getattr(g, "data_paths", {}) or {}
    configured_db = paths.get("PEC_CONTROL_TOWER_DB")
    db_path = Path(str(configured_db)) if configured_db else email_db.parent / "pec_control_tower.sqlite"
    return PecControlTowerRepository(
        db_path,
        tenant_id=_tenant_id(),
        fascicoli_db_path=_runtime_path("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_runtime_path("FASCICOLI_DOCS", "./fascicoli/documenti"),
    )


def _deadline_fallback_repo() -> PecAuditRepository:
    import tempfile

    safe_tenant = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in _tenant_id()) or "default"
    db_path = Path(tempfile.gettempdir()) / f"iusentra-pec-deadline-fallback-{safe_tenant}.sqlite"
    return PecAuditRepository(
        db_path,
        tenant_id=_tenant_id(),
        clienti_db_path=_runtime_path("CLIENTI_DB", "./clienti/anagrafica.json"),
        fascicoli_db_path=_runtime_path("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_runtime_path("FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_runtime_path("SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_runtime_path("AGENDA_DB", "./agenda/appuntamenti.json"),
    )


def _json_error(status: int = 400):
    if status == 403:
        message = "Dati dello studio non disponibili per questa richiesta."
    elif status == 404:
        message = "Elemento PEC non trovato."
    else:
        message = "Operazione PEC non completata."
    return jsonify({"ok": False, "errore": message}), status


def _json_success(payload: dict, status: int = 200):
    return redacted_json_response(payload, status)


@pec_pipeline_api.get("/messages")
@_richiedi_auth
def pec_messages():
    try:
        repo = _repo()
        rows = repo.list_messages(
            limit=int(request.args.get("limit", "100") or 100),
            folder=request.args.get("folder", "").strip(),
            q=request.args.get("q", "").strip(),
        )
        return jsonify({"ok": True, "data": rows, "count": len(rows)})
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.get("/messages/<message_id>")
@_richiedi_auth
def pec_message_detail(message_id: str):
    try:
        return jsonify({"ok": True, "data": _repo().get_message_detail(message_id)})
    except KeyError:
        return _json_error(404)
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.get("/messages/<message_id>/mime")
@_richiedi_auth
def pec_message_mime(message_id: str):
    try:
        raw, row = _repo().original_mime(message_id)
    except KeyError:
        return _json_error(404)
    response = Response(raw, mimetype="message/rfc822")
    safe_name = f"{message_id}.eml"
    response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
    response.headers["X-IUSENTRA-MIME-SHA256"] = str(row.get("mime_sha256") or "")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@pec_pipeline_api.post("/fetch")
@_richiedi_auth
def pec_fetch():
    try:
        from web.services.mailbox_sync_runtime import _get_config_pec, _get_config_smtp, mailbox_context_for_current_request

        ctx = mailbox_context_for_current_request()
        pec_cfg = _get_config_pec(ctx)
        smtp_cfg = _get_config_smtp(ctx)
        cfg = pec_cfg if pec_cfg and getattr(pec_cfg, "imap_host", "") else smtp_cfg
        if not cfg or not getattr(cfg, "imap_host", ""):
            return jsonify({"ok": False, "errore": "IMAP PEC non configurato."}), 400
        username = str(getattr(cfg, "indirizzo", "") or getattr(cfg, "username", "") or "")
        report = _repo().fetch_imap(
            imap_host=str(getattr(cfg, "imap_host", "")),
            imap_port=int(getattr(cfg, "imap_port", 993) or 993),
            username=username,
            password=str(getattr(cfg, "password", "") or ""),
            use_ssl=bool(getattr(cfg, "use_ssl", getattr(cfg, "imap_use_ssl", True))),
            limit=int(request.args.get("limit", "50") or 50),
            actor=_actor(),
        )
        worker = _repo().run_pending_jobs(limit=200, actor=_actor())
        return _json_success({"ok": True, "fetch": report, "workers": worker})
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/email/<email_id>/acquisisci")
@_richiedi_auth
def pec_acquire_legacy_email(email_id: str):
    """Acquisisce nel presidio PEC il MIME originale già salvato nella casella storica."""

    try:
        email_db = _runtime_path("EMAIL_CASELLA_DB", "./email/casella.json")
        gestore = GestioneEmailRicevute(email_db)
        email_obj = gestore.get(email_id)
        if not email_obj:
            return _json_error(404)
        raw_mime, mime_source = _read_or_reconstruct_local_mime(gestore, email_obj)
        if not raw_mime:
            return _json_success(
                {
                    "ok": False,
                    "message": "MIME o allegati locali non disponibili: esegui la sincronizzazione PEC completa e riprova.",
                    "messaggio": "MIME o allegati locali non disponibili: esegui la sincronizzazione PEC completa e riprova.",
                    "requires_sync": True,
                },
                409,
            )
        audit_available = True
        try:
            repo = _repo()
        except Exception as exc:
            audit_available = False
            repo = _deadline_fallback_repo()
            audit_error = str(exc)[:180]
        account_email = str(getattr(email_obj, "destinatari", "") or getattr(email_obj, "mittente", "") or "casella PEC locale")
        if audit_available:
            result = repo.ingest_mime(
                raw_mime,
                account_email=account_email[:240],
                folder=str(getattr(email_obj, "cartella", "") or "INBOX"),
                imap_uid=str(getattr(email_obj, "uid_imap", "") or f"legacy:{email_id}"),
                actor=_actor(),
            )
        else:
            result = {"id": f"email:{email_id}", "duplicate": False, "audit_unavailable": True, "message": audit_error}
        message_id = str(result.get("id") or "") or f"email:{email_id}"
        analysis_refresh: dict[str, Any] = {}
        if audit_available and result.get("duplicate") and message_id:
            try:
                analysis_refresh = repo.refresh_message_analysis(message_id, actor=_actor())
            except Exception as exc:
                analysis_refresh = {"ok": False, "errors": [str(exc)[:240]]}
        deadline = _schedule_deadline_with_local_mime(
            repo,
            message_id=message_id,
            raw_mime=raw_mime,
            actor=_actor(),
        )
        try:
            run = repo.start_local_acquire_run(total_emails=1, batch_size=1, actor=_actor())
            _local_acquire_record(
                repo,
                str(run.get("id") or ""),
                email_id=email_id,
                message_id=message_id,
                subject=str(getattr(email_obj, "oggetto", "") or "")[:240],
                status="duplicate" if result.get("duplicate") else "ingested",
                deadline_status=_local_acquire_deadline_status(deadline),
                due_date=str(deadline.get("due_date") or ""),
                deadline_id=str(deadline.get("deadline_id") or ""),
                agenda_id=str((deadline.get("agenda") or {}).get("agenda_id") or "") if isinstance(deadline.get("agenda"), dict) else "",
                detail={
                    "mime_sha256": result.get("mime_sha256") or "",
                    "mime_source": mime_source,
                    "single_acquire": True,
                },
            )
            repo.update_local_acquire_run(
                str(run.get("id") or ""),
                cursor_index=1,
                total_emails=1,
                batch_size=1,
                status="completed",
                deltas={"acquired": 1, "duplicates": int(bool(result.get("duplicate")))},
                actor=_actor(),
            )
        except Exception:
            pass
        try:
            worker = repo.run_pending_jobs(limit=80, actor=_actor())
        except Exception as exc:
            worker = {"processed": 0, "failed": 1, "jobs": [], "error": str(exc)[:180]}
        try:
            control_tower = _control_tower_feed_repo().ingest_eml(
                raw_mime,
                account_email=account_email[:240],
                folder=str(getattr(email_obj, "cartella", "") or "INBOX"),
                actor=_actor(),
            )
        except Exception as exc:
            control_tower = {"ok": False, "error": str(exc)[:180]}
        message = "MIME PEC acquisito: allegati, controllo qualità e presidio operativo aggiornati."
        return _json_success(
            {
                "ok": True,
                "message": message,
                "messaggio": message,
                "email_id": email_id,
                "pec_message_id": message_id,
                "mime_source": mime_source,
                "duplicate": bool(result.get("duplicate")),
                "ingest": result,
                "analysis_refresh": analysis_refresh,
                "deadline": deadline,
                "workers": worker,
                "pec_control_tower": control_tower,
            }
        )
    except TenantDataPathError:
        return _json_error(403)


# Helper condivisi con il presidio automatico dello scheduler: la logica vive
# in web/services/pec_pipeline_runtime.py, qui restano gli alias storici.
_email_rilevante_per_presidio_pec = email_rilevante_per_presidio_pec
_read_or_reconstruct_local_mime = read_or_reconstruct_local_mime


def _schedule_deadline_with_local_mime(
    repo: PecAuditRepository,
    *,
    message_id: str,
    raw_mime: bytes,
    actor: str,
) -> dict[str, Any]:
    persisted: dict[str, Any] = {}
    try:
        persisted = repo.schedule_deadline(message_id, actor=actor)
        if persisted.get("expired"):
            return persisted
    except Exception as exc:
        persisted = {"ok": False, "message": f"Audit PEC non disponibile: {exc}"}
    try:
        parsed = parse_pec_message(raw_mime)
        try:
            detail = repo.get_message_detail(message_id)
            message = detail.get("message") if isinstance(detail.get("message"), dict) else {}
        except Exception:
            message = {}
        return repo.schedule_deadline_from_payload(
            message_id,
            parsed=parsed,
            message=message,
            actor=actor,
        )
    except Exception as exc:
        if persisted.get("ok"):
            return persisted
        return {
            "ok": False,
            "message": f"Presidio non pronto: {persisted.get('message') or 'report mancante'}; MIME locale non schedulabile: {exc}",
        }


_local_email_sort_key = local_email_sort_key


def _local_acquire_deadline_status(result: dict[str, Any]) -> str:
    if result.get("ok") and result.get("already_exists"):
        return "deadline_already_exists"
    if result.get("ok"):
        return "deadline_created"
    if result.get("expired"):
        return "deadline_expired"
    return "deadline_not_ready"


def _visible_deadline_report(deadline_report: dict[str, Any], limit: int) -> dict[str, Any]:
    items = deadline_report.get("items") if isinstance(deadline_report.get("items"), list) else []
    operational_items = [item for item in items if not bool(item.get("expired"))]
    return {
        **deadline_report,
        "items": operational_items[:limit],
        "expired_audit_only": int(deadline_report.get("expired") or 0),
    }


def _pec_deadline_summary_message(
    *,
    created: int,
    already_exists: int,
    agenda_linked: int,
    not_ready: int = 0,
    expired: int = 0,
) -> str:
    parts = [
        f"{created} scadenze operative create",
        f"{already_exists} già presenti",
        f"{agenda_linked} collegate all'agenda",
    ]
    if not_ready:
        parts.append(f"{not_ready} da verificare")
    if expired:
        parts.append("termini già superati conservati solo nello storico audit")
    return ", ".join(parts)


def _notify_pec_deadline(message_id: str, result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("ok"):
        return result
    deadline_results = (
        [item for item in list(result.get("hearing_results") or []) if isinstance(item, dict)]
        if isinstance(result.get("hearing_results"), list)
        else []
    ) or [result]
    deadline_results = [
        item for item in deadline_results if item.get("ok") and str(item.get("deadline_id") or "").strip()
    ]
    if not deadline_results:
        return result
    try:
        from web.services.notifications_runtime import (
            build_notification_service,
            current_tenant_id,
            current_user_id,
        )

        service = build_notification_service()
        notification_results: list[dict[str, Any]] = []
        for deadline in deadline_results:
            source_id = str(deadline.get("scheduled_message_id") or message_id or deadline.get("deadline_id"))
            notification = build_pec_deadline_notification(
                deadline,
                source_id=source_id,
                automatic=False,
            )
            _record, created, summary = service.create_notification(
                tenant_id=current_tenant_id(),
                user_id=current_user_id() or _actor(),
                type="pec_deadline",
                priority="important",
                title=notification["title"],
                body=notification["body"],
                href=notification["href"],
                source_type="pec_deadline",
                source_id=source_id,
                dedupe_key=f"PEC_AUDIT:{source_id}:deadline",
                payload_json=notification["payload_json"],
                send_push=should_send_pec_deadline_web_push(notification),
                redispatch_on_remote_hearing_enrichment=True,
            )
            notification_results.append(
                {
                    "sourceId": source_id,
                    "created": created,
                    "pushConfigured": summary.configured,
                    "pushAttempted": summary.attempted,
                    "pushSent": summary.sent,
                }
            )
        result["notification"] = {
            "created": any(item["created"] for item in notification_results),
            "pushConfigured": any(item["pushConfigured"] for item in notification_results),
            "pushAttempted": sum(int(item["pushAttempted"] or 0) for item in notification_results),
            "pushSent": sum(int(item["pushSent"] or 0) for item in notification_results),
            "items": notification_results,
        }
    except Exception as exc:
        result["notification"] = {"created": False, "error": str(exc)[:180]}
    return result


def _local_acquire_record(
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
    try:
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
    except Exception:
        pass


def _pec_acquire_local_emails_chunked():
    try:
        email_db = _runtime_path("EMAIL_CASELLA_DB", "./email/casella.json")
        gestore = GestioneEmailRicevute(email_db)
        actor = _actor()
        audit_available = True
        audit_error = ""
        try:
            repo = _repo()
        except Exception as exc:
            audit_available = False
            audit_error = str(exc)[:180]
            repo = _deadline_fallback_repo()
        try:
            limit = max(1, min(int(request.args.get("limit", "5000") or 5000), 10000))
        except ValueError:
            limit = 5000
        try:
            batch_size = max(1, min(int(request.args.get("batch_size", "50") or 50), 200))
        except ValueError:
            batch_size = 50
        force_repairs = str(request.args.get("queue_repairs") or "").strip().lower() in {"1", "true", "si", "sì", "yes"}
        emails = sorted(
            list(gestore._carica().values()),  # noqa: SLF001 - manutenzione tenant-aware su casella locale
            key=_local_email_sort_key,
            reverse=True,
        )
        requested_run_id = str(request.args.get("run_id") or "").strip()
        run = repo.get_local_acquire_run(requested_run_id) if audit_available and requested_run_id else {}
        is_resuming_run = bool(run)
        archive_candidates = emails[:limit]
        relevant_candidates = [item for item in archive_candidates if _email_rilevante_per_presidio_pec(item)]
        skipped_not_pec_initial = 0 if is_resuming_run else len(archive_candidates) - len(relevant_candidates)
        errors: list[dict[str, str]] = []
        if not audit_available:
            errors.append({"email_id": "audit-pec", "errore": f"Audit PEC persistente non disponibile: {audit_error}"})
        existing_by_header: dict[str, str] = {}
        presided_email_ids: set[str] = set()
        if audit_available:
            try:
                existing_by_header = repo.ids_by_header_message_ids(
                    str(getattr(item, "message_id", "") or "").strip()
                    for item in relevant_candidates
                )
            except Exception as exc:
                errors.append({"email_id": "audit-pec", "errore": f"Lookup PEC già acquisite non disponibile: {exc}"[:180]})
            try:
                presided_email_ids = repo.presided_email_ids(
                    str(getattr(item, "id", "") or "")
                    for item in relevant_candidates
                )
            except Exception as exc:
                errors.append({"email_id": "audit-pec", "errore": f"Lookup PEC già presidiate non disponibile: {exc}"[:180]})
        skipped_already_presided = 0
        candidates = relevant_candidates
        if not is_resuming_run and not force_repairs:
            candidates = []
            for item in relevant_candidates:
                email_id_candidate = str(getattr(item, "id", "") or "")
                header_candidate = str(getattr(item, "message_id", "") or "").strip()
                if (header_candidate and header_candidate in existing_by_header) or (
                    email_id_candidate and email_id_candidate in presided_email_ids
                ):
                    skipped_already_presided += 1
                    continue
                candidates.append(item)
        total_emails = len(candidates)
        if not run:
            run = repo.start_local_acquire_run(total_emails=total_emails, batch_size=batch_size, actor=actor)
        run_id = str(run.get("id") or requested_run_id or "")
        cursor_index = max(0, min(int(run.get("cursor_index") or 0), total_emails))
        acquired = 0
        duplicates = 0
        skipped_missing_mime = 0
        skipped_not_pec = skipped_not_pec_initial
        queued_repairs = 0
        repair_stages: dict[str, int] = {}
        controlled_ids: list[str] = []
        local_mime_by_message_id: dict[str, bytes] = {}
        message_email_index: dict[str, dict[str, str]] = {}
        relevant_processed = 0
        next_cursor = cursor_index
        for index in range(cursor_index, total_emails):
            email_obj = candidates[index]
            next_cursor = index + 1
            if relevant_processed >= batch_size:
                next_cursor = index
                break
            relevant_processed += 1
            email_id = str(getattr(email_obj, "id", "") or f"email-{index}")
            subject = str(getattr(email_obj, "oggetto", "") or "")[:240]
            header = str(getattr(email_obj, "message_id", "") or "").strip()
            existing_message_id = existing_by_header.get(header)
            raw_mime, mime_source = _read_or_reconstruct_local_mime(gestore, email_obj)
            if existing_message_id:
                acquired += 1
                duplicates += 1
                controlled_ids.append(existing_message_id)
                message_email_index[existing_message_id] = {"email_id": email_id, "subject": subject, "status": "duplicate"}
                if raw_mime:
                    local_mime_by_message_id[existing_message_id] = raw_mime
                    _local_acquire_record(repo, run_id, email_id=email_id, message_id=existing_message_id, subject=subject, status="duplicate")
                else:
                    skipped_missing_mime += 1
                    _local_acquire_record(repo, run_id, email_id=email_id, message_id=existing_message_id, subject=subject, status="missing_mime")
                if force_repairs:
                    try:
                        repair = repo.enqueue_missing_operational_jobs(existing_message_id, actor=actor)
                        if repair.get("queued"):
                            queued_repairs += 1
                            stage = str(repair.get("stage") or "queued")
                            repair_stages[stage] = repair_stages.get(stage, 0) + 1
                    except Exception as exc:
                        errors.append({"email_id": email_id, "errore": f"Riparazione audit non accodata: {exc}"[:180]})
                continue
            if not raw_mime:
                skipped_missing_mime += 1
                _local_acquire_record(repo, run_id, email_id=email_id, subject=subject, status="missing_mime")
                continue
            acquired += 1
            fallback_message_id = f"email:{email_id}"
            message_id = fallback_message_id
            try:
                result = repo.ingest_mime(
                    raw_mime,
                    account_email=str(getattr(email_obj, "destinatari", "") or getattr(email_obj, "mittente", "") or "casella PEC locale")[:240],
                    folder=str(getattr(email_obj, "cartella", "") or "INBOX"),
                    imap_uid=str(getattr(email_obj, "uid_imap", "") or f"legacy:{email_id}"),
                    actor=actor,
                )
                if result.get("duplicate"):
                    duplicates += 1
                message_id = str(result.get("id") or "") or fallback_message_id
                controlled_ids.append(message_id)
                local_mime_by_message_id[message_id] = raw_mime
                message_email_index[message_id] = {
                    "email_id": email_id,
                    "subject": subject,
                    "status": "duplicate" if result.get("duplicate") else "ingested",
                }
                _local_acquire_record(
                    repo,
                    run_id,
                    email_id=email_id,
                    message_id=message_id,
                    subject=subject,
                    status="duplicate" if result.get("duplicate") else "ingested",
                    detail={"mime_sha256": result.get("mime_sha256") or "", "mime_source": mime_source},
                )
                if force_repairs:
                    try:
                        repair = repo.enqueue_missing_operational_jobs(message_id, actor=actor)
                        if repair.get("queued"):
                            queued_repairs += 1
                            stage = str(repair.get("stage") or "queued")
                            repair_stages[stage] = repair_stages.get(stage, 0) + 1
                    except Exception as exc:
                        errors.append({"email_id": email_id, "errore": f"Riparazione audit non accodata: {exc}"[:180]})
            except Exception as exc:
                controlled_ids.append(message_id)
                local_mime_by_message_id[message_id] = raw_mime
                message_email_index[message_id] = {"email_id": email_id, "subject": subject, "status": "processed"}
                _local_acquire_record(repo, run_id, email_id=email_id, message_id=message_id, subject=subject, status="processed", detail={"errore": str(exc)[:180]})
                errors.append({"email_id": email_id, "errore": str(exc)[:180]})
        deadline_report = {
            "created": 0,
            "already_exists": 0,
            "expired": 0,
            "not_ready": 0,
            "agenda_linked": 0,
            "errors": 0,
            "items": [],
        }
        seen_message_ids: set[str] = set()
        unique_controlled_ids = [item for item in controlled_ids if item]
        existing_deadlines = repo.existing_deadlines_by_message_id(unique_controlled_ids)
        skipped_deadlines = repo.skipped_deadlines_by_message_id(unique_controlled_ids)
        for message_id in unique_controlled_ids:
            if message_id in seen_message_ids:
                continue
            seen_message_ids.add(message_id)
            email_meta = message_email_index.get(message_id, {})
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
                    try:
                        result = _schedule_deadline_with_local_mime(
                            repo,
                            message_id=message_id,
                            raw_mime=local_mime_by_message_id.get(message_id, b""),
                            actor=actor,
                        )
                    except Exception as exc:
                        deadline_report["errors"] += 1
                        result = {"ok": False, "message": str(exc)[:180]}
                else:
                    result = {
                        "ok": False,
                        "message": "MIME originale non disponibile nella casella locale: presidio registrato, verifica IMAP se serve la prova completa.",
                    }
            result = _notify_pec_deadline(message_id, result)
            deadline_status = _local_acquire_deadline_status(result)
            if deadline_status == "deadline_already_exists":
                deadline_report["already_exists"] += 1
            elif deadline_status == "deadline_created":
                deadline_report["created"] += 1
            elif deadline_status == "deadline_expired":
                deadline_report["expired"] += 1
            elif deadline_status == "deadline_not_ready":
                deadline_report["not_ready"] += 1
            agenda = result.get("agenda") if isinstance(result.get("agenda"), dict) else {}
            agenda_id = str(agenda.get("agenda_id") or "")
            if agenda_id:
                deadline_report["agenda_linked"] += 1
            item_payload = {
                "message_id": message_id,
                "ok": bool(result.get("ok")),
                "message": str(result.get("message") or "")[:180],
                "due_date": str(result.get("due_date") or ""),
                "deadline_id": str(result.get("deadline_id") or ""),
                "agenda_id": agenda_id,
                "already_exists": bool(result.get("already_exists")),
                "expired": bool(result.get("expired")),
            }
            deadline_report["items"].append(item_payload)
            _local_acquire_record(
                repo,
                run_id,
                email_id=str(email_meta.get("email_id") or ""),
                message_id=message_id,
                subject=str(email_meta.get("subject") or ""),
                status=str(email_meta.get("status") or "processed"),
                deadline_status=deadline_status,
                due_date=item_payload["due_date"],
                deadline_id=item_payload["deadline_id"],
                agenda_id=agenda_id,
                detail=item_payload,
            )
        try:
            default_worker_limit = min(max(batch_size * 8, 40), 300)
            worker_limit = max(0, min(int(request.args.get("worker_limit", str(default_worker_limit)) or default_worker_limit), 300))
        except ValueError:
            worker_limit = min(max(batch_size * 8, 40), 300)
        if worker_limit:
            try:
                worker = repo.run_pending_jobs(limit=worker_limit, actor=actor)
            except Exception as exc:
                worker = {"processed": 0, "failed": 1, "jobs": [], "error": str(exc)[:180]}
        else:
            worker = {
                "processed": 0,
                "failed": 0,
                "jobs": [],
                "queued": queued_repairs,
                "message": "Controlli pesanti accodati al worker PEC schedulato.",
            }
        try:
            control_tower_report = _control_tower_feed_repo().backfill_from_email_archive(
                gestore,
                limit=batch_size,
                max_seconds=8.0,
                actor=actor,
            )
        except Exception as exc:
            control_tower_report = {"ok": False, "errors": [{"email_id": "pec-control-tower", "errore": str(exc)[:180]}]}
        has_more = next_cursor < total_emails
        run_status = "running" if has_more else "completed"
        run_report = repo.update_local_acquire_run(
            run_id,
            cursor_index=next_cursor,
            total_emails=total_emails,
            batch_size=batch_size,
            status=run_status,
            deltas={
                "acquired": acquired,
                "duplicates": duplicates,
                "skipped_missing_mime": skipped_missing_mime,
                "skipped_not_pec": skipped_not_pec,
                "skipped_already_presided": skipped_already_presided,
                "queued_repairs": queued_repairs,
                "deadline_created": deadline_report["created"],
                "deadline_already_exists": deadline_report["already_exists"],
                "deadline_expired": deadline_report["expired"],
                "deadline_not_ready": deadline_report["not_ready"],
                "deadline_errors": deadline_report["errors"],
                "agenda_linked": deadline_report["agenda_linked"],
                "errors": len(errors) + int(deadline_report["errors"] or 0),
            },
            payload={
                "repair_stages": repair_stages,
                "has_more": has_more,
                "skipped_already_presided": skipped_already_presided,
            },
            actor=actor,
        )
        if has_more:
            summary_text = _pec_deadline_summary_message(
                created=int(deadline_report["created"] or 0),
                already_exists=int(deadline_report["already_exists"] or 0),
                agenda_linked=int(deadline_report["agenda_linked"] or 0),
                not_ready=int(deadline_report["not_ready"] or 0),
                expired=int(deadline_report["expired"] or 0),
            )
            message = (
                f"Blocco presidio PEC completato: esaminate {next_cursor}/{total_emails} nuove comunicazioni; "
                f"{summary_text}. "
                "Il controllo prosegue automaticamente."
            )
        else:
            summary_text = _pec_deadline_summary_message(
                created=int(run_report.get("deadline_created") or 0),
                already_exists=int(run_report.get("deadline_already_exists") or 0),
                agenda_linked=int(run_report.get("agenda_linked") or 0),
                not_ready=int(run_report.get("deadline_not_ready") or 0),
                expired=int(run_report.get("deadline_expired") or 0),
            )
            if int(run_report.get("acquired") or acquired) == 0 and skipped_already_presided:
                message = (
                    f"Nessuna nuova PEC da presidiare: {skipped_already_presided} comunicazioni erano già presidiate. "
                    "Il controllo ripartirà dalle prossime PEC non ancora lavorate."
                )
            else:
                message = (
                    f"Presidio PEC completato su {int(run_report.get('acquired') or acquired)} nuove comunicazioni PEC "
                    f"({int(run_report.get('duplicates') or duplicates)} già presenti, {skipped_already_presided} già presidiate saltate): "
                    f"{summary_text}. "
                    "Le PEC già presidiate non alimentano più l'avviso automatico."
                )
        return _json_success(
            {
                "ok": True,
                "message": message,
                "messaggio": message,
                "run_id": run_id,
                "status": run_status,
                "has_more": has_more,
                "cursor_index": next_cursor,
                "total_emails": total_emails,
                "batch_size": batch_size,
                "acquired": acquired,
                "duplicates": duplicates,
                "skipped_missing_mime": skipped_missing_mime,
                "skipped_not_pec": skipped_not_pec,
                "skipped_already_presided": skipped_already_presided,
                "queued_repairs": queued_repairs,
                "repair_stages": repair_stages,
                "deadline_report": _visible_deadline_report(deadline_report, 80),
                "pec_control_tower": control_tower_report,
                "local_acquire": repo.local_acquire_run_report(run_id, limit=80),
                "errors": errors[:20],
                "workers": worker,
            }
        )
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/email/acquisisci-locali")
@_richiedi_auth
def pec_acquire_local_emails():
    return _pec_acquire_local_emails_chunked()
    """Acquisisce in modo massivo i MIME locali già salvati e pertinenti alla PEC."""

    try:
        email_db = _runtime_path("EMAIL_CASELLA_DB", "./email/casella.json")
        gestore = GestioneEmailRicevute(email_db)
        audit_available = True
        audit_error = ""
        try:
            repo = _repo()
        except Exception as exc:
            audit_available = False
            audit_error = str(exc)[:180]
            repo = _deadline_fallback_repo()
        try:
            limit = max(1, min(int(request.args.get("limit", "1500") or 1500), 5000))
        except ValueError:
            limit = 1500
        acquired = 0
        duplicates = 0
        skipped_missing_mime = 0
        skipped_not_pec = 0
        queued_repairs = 0
        controlled_ids: list[str] = []
        local_mime_by_message_id: dict[str, bytes] = {}
        repair_stages: dict[str, int] = {}
        errors: list[dict[str, str]] = []
        force_repairs = str(request.args.get("queue_repairs") or "").strip().lower() in {"1", "true", "si", "sì", "yes"}
        if not audit_available:
            errors.append({"email_id": "audit-pec", "errore": f"Audit PEC persistente non disponibile: {audit_error}"})
        emails = list(gestore._carica().values())  # noqa: SLF001 - manutenzione tenant-aware su casella locale
        existing_by_header: dict[str, str] = {}
        if audit_available:
            try:
                existing_by_header = repo.ids_by_header_message_ids(
                    str(getattr(item, "message_id", "") or "").strip()
                    for item in emails
                    if _email_rilevante_per_presidio_pec(item)
                )
            except Exception as exc:
                errors.append({"email_id": "audit-pec", "errore": f"Lookup PEC già acquisite non disponibile: {exc}"[:180]})
        for email_obj in emails:
            if acquired >= limit:
                break
            if not _email_rilevante_per_presidio_pec(email_obj):
                skipped_not_pec += 1
                continue
            existing_message_id = existing_by_header.get(str(getattr(email_obj, "message_id", "") or "").strip())
            if existing_message_id:
                acquired += 1
                duplicates += 1
                controlled_ids.append(existing_message_id)
                raw_mime = gestore.leggi_eml_originale(email_obj)
                if raw_mime:
                    local_mime_by_message_id[existing_message_id] = raw_mime
                else:
                    skipped_missing_mime += 1
                if force_repairs:
                    try:
                        repair = repo.enqueue_missing_operational_jobs(existing_message_id, actor=_actor())
                        if repair.get("queued"):
                            queued_repairs += 1
                            stage = str(repair.get("stage") or "queued")
                            repair_stages[stage] = repair_stages.get(stage, 0) + 1
                    except Exception as exc:
                        errors.append({"email_id": str(getattr(email_obj, "id", "") or ""), "errore": f"Riparazione audit non accodata: {exc}"[:180]})
                continue
            raw_mime = gestore.leggi_eml_originale(email_obj)
            if not raw_mime:
                skipped_missing_mime += 1
                continue
            acquired += 1
            fallback_message_id = f"email:{getattr(email_obj, 'id', '') or acquired}"
            message_id = fallback_message_id
            try:
                result = repo.ingest_mime(
                    raw_mime,
                    account_email=str(getattr(email_obj, "destinatari", "") or getattr(email_obj, "mittente", "") or "casella PEC locale")[:240],
                    folder=str(getattr(email_obj, "cartella", "") or "INBOX"),
                    imap_uid=str(getattr(email_obj, "uid_imap", "") or f"legacy:{getattr(email_obj, 'id', '')}"),
                    actor=_actor(),
                )
                if result.get("duplicate"):
                    duplicates += 1
                message_id = str(result.get("id") or "") or fallback_message_id
                if message_id:
                    controlled_ids.append(message_id)
                    local_mime_by_message_id[message_id] = raw_mime
                    if force_repairs:
                        try:
                            repair = repo.enqueue_missing_operational_jobs(message_id, actor=_actor())
                            if repair.get("queued"):
                                queued_repairs += 1
                                stage = str(repair.get("stage") or "queued")
                                repair_stages[stage] = repair_stages.get(stage, 0) + 1
                        except Exception as exc:
                            errors.append({"email_id": str(getattr(email_obj, "id", "") or ""), "errore": f"Riparazione audit non accodata: {exc}"[:180]})
            except Exception as exc:
                controlled_ids.append(message_id)
                local_mime_by_message_id[message_id] = raw_mime
                errors.append({"email_id": str(getattr(email_obj, "id", "") or ""), "errore": str(exc)[:180]})
        worker: dict[str, Any] = {"processed": 0, "failed": 0, "jobs": []}
        deadline_report = {
            "created": 0,
            "already_exists": 0,
            "expired": 0,
            "not_ready": 0,
            "agenda_linked": 0,
            "errors": 0,
            "items": [],
        }
        seen_message_ids: set[str] = set()
        existing_deadlines = repo.existing_deadlines_by_message_id(controlled_ids)
        skipped_deadlines = repo.skipped_deadlines_by_message_id(controlled_ids)
        for message_id in controlled_ids:
            if message_id in seen_message_ids:
                continue
            seen_message_ids.add(message_id)
            existing = existing_deadlines.get(message_id) if isinstance(existing_deadlines, dict) else None
            if existing and existing.get("agenda_id"):
                deadline_report["already_exists"] += 1
                deadline_report["agenda_linked"] += 1
                deadline_report["items"].append(
                    {
                        "message_id": message_id,
                        "ok": True,
                        "message": "Scadenza PEC già presente e collegata all'agenda.",
                        "due_date": str(existing.get("due_date") or ""),
                        "already_exists": True,
                        "expired": False,
                    }
                )
                continue
            skipped = skipped_deadlines.get(message_id) if isinstance(skipped_deadlines, dict) else None
            if skipped:
                deadline_report["expired"] += 1
                deadline_report["items"].append(
                    {
                        "message_id": message_id,
                        "ok": False,
                        "message": str(skipped.get("message") or "Termine già superato: non riportato in scadenziario o agenda."),
                        "due_date": str(skipped.get("due_date") or ""),
                        "already_exists": False,
                        "expired": True,
                    }
                )
                continue
            try:
                result = _schedule_deadline_with_local_mime(
                    repo,
                    message_id=message_id,
                    raw_mime=local_mime_by_message_id.get(message_id, b""),
                    actor=_actor(),
                )
                if result.get("ok") and result.get("already_exists"):
                    deadline_report["already_exists"] += 1
                elif result.get("ok"):
                    deadline_report["created"] += 1
                elif result.get("expired"):
                    deadline_report["expired"] += 1
                else:
                    deadline_report["not_ready"] += 1
                agenda = result.get("agenda") if isinstance(result.get("agenda"), dict) else {}
                if agenda.get("agenda_id"):
                    deadline_report["agenda_linked"] += 1
                deadline_report["items"].append(
                    {
                        "message_id": message_id,
                        "ok": bool(result.get("ok")),
                        "message": str(result.get("message") or "")[:180],
                        "due_date": str(result.get("due_date") or ""),
                        "already_exists": bool(result.get("already_exists")),
                        "expired": bool(result.get("expired")),
                    }
                )
            except Exception as exc:
                deadline_report["errors"] += 1
                deadline_report["items"].append({"message_id": message_id, "ok": False, "message": str(exc)[:180]})
        try:
            worker_limit = max(0, min(int(request.args.get("worker_limit", "0") or 0), 300))
        except ValueError:
            worker_limit = 0
        if worker_limit:
            try:
                worker = repo.run_pending_jobs(limit=worker_limit, actor=_actor())
            except Exception as exc:
                worker = {"processed": 0, "failed": 1, "jobs": [], "error": str(exc)[:180]}
        else:
            worker = {
                "processed": 0,
                "failed": 0,
                "jobs": [],
                "queued": queued_repairs,
                "message": "Controlli pesanti accodati al worker PEC schedulato.",
            }
        try:
            control_tower_report = _control_tower_repo().backfill_from_email_archive(
                gestore,
                limit=limit,
                actor=_actor(),
            )
        except Exception as exc:
            control_tower_report = {"ok": False, "errors": [{"email_id": "pec-control-tower", "errore": str(exc)[:180]}]}
        message = (
            f"Presidio PEC eseguito su {acquired} MIME locali"
            f" ({duplicates} già presenti): "
            f"{deadline_report['created']} scadenze operative create, "
            f"{deadline_report['already_exists']} già presenti, "
            f"{deadline_report['agenda_linked']} collegate all'agenda. "
            + (
                "Termini già superati conservati solo nello storico audit. "
                if deadline_report["expired"]
                else ""
            )
            + f"{queued_repairs} controlli tecnici accodati."
        )
        return _json_success(
            {
                "ok": True,
                "message": message,
                "messaggio": message,
                "acquired": acquired,
                "duplicates": duplicates,
                "skipped_missing_mime": skipped_missing_mime,
                "skipped_not_pec": skipped_not_pec,
                "queued_repairs": queued_repairs,
                "repair_stages": repair_stages,
                "deadline_report": _visible_deadline_report(deadline_report, 50),
                "pec_control_tower": control_tower_report,
                "errors": errors[:20],
                "workers": worker,
            }
        )
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/workers/run")
@_richiedi_auth
def pec_workers_run():
    try:
        report = run_workers_for_paths(
            _runtime_paths(),
            tenant_label=_tenant_id(),
            limit=int(request.args.get("limit", "200") or 200),
        )
        return _json_success({"ok": True, "report": report})
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/messages/<message_id>/riesegui-controllo")
@_richiedi_auth
def pec_refresh_message_analysis(message_id: str):
    try:
        result = _repo().refresh_message_analysis(message_id, actor=_actor())
        if result.get("ok"):
            result["message"] = "Controllo PEC aggiornato sul messaggio e sugli allegati originali."
            result["messaggio"] = result["message"]
            return _json_success(result)
        result["message"] = "Controllo PEC non aggiornato: verifica il messaggio originale e riprova."
        result["messaggio"] = result["message"]
        return _json_success(result, 409)
    except KeyError:
        return _json_error(404)
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/rebuild-matrix")
@_richiedi_auth
def pec_rebuild_operational_matrix():
    try:
        limit = max(0, min(int(request.args.get("limit", "0") or 0), 10000))
    except ValueError:
        limit = 0
    try:
        worker_limit = max(1, min(int(request.args.get("worker_limit", "800") or 800), 20000))
    except ValueError:
        worker_limit = 800
    try:
        report = rebuild_operational_matrix_for_paths(
            _runtime_paths(),
            tenant_label=_tenant_id(),
            limit=limit,
            worker_limit=worker_limit,
        )
        return _json_success(
            {
                "ok": True,
                "message": "Matrice PEC riallineata: parser, fascicoli, agenda, scadenziario e notifiche sono stati riaccodati con la logica corrente.",
                "report": report,
            }
        )
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.get("/digest")
@_richiedi_auth
def pec_digest_get():
    try:
        return jsonify({"ok": True, "data": _repo().latest_digest()})
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/digest/run")
@_richiedi_auth
def pec_digest_run():
    try:
        digest = _repo().build_daily_digest(digest_date=request.args.get("date") or None, actor=_actor())
        return jsonify({"ok": True, "data": digest})
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/messages/<message_id>/salva-fascicolo")
@_richiedi_auth
def pec_save_to_fascicolo(message_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
        prepara = bool(payload.get("prepara") or payload.get("prepare"))
        if prepara or (not fascicolo_id and any(str(payload.get(key) or "").strip() for key in ("nome", "cognome", "cliente_id"))):
            result = _repo().prepare_save_to_fascicolo(
                message_id,
                nome=str(payload.get("nome") or ""),
                cognome=str(payload.get("cognome") or ""),
                cliente_id=str(payload.get("cliente_id") or ""),
                actor=_actor(),
            )
            return _json_success(result, 200 if result.get("ok") else 409)
        result = _repo().save_to_fascicolo(message_id, fascicolo_id=fascicolo_id, actor=_actor())
        return _json_success(result, 200 if result.get("ok") else 409)
    except KeyError:
        return _json_error(404)
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/messages/<message_id>/richiedi-allegato-mancante")
@_richiedi_auth
def pec_request_missing_attachment(message_id: str):
    try:
        return jsonify(_repo().request_missing_attachment(message_id, actor=_actor()))
    except KeyError:
        return _json_error(404)
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/messages/<message_id>/schedula-scadenza")
@_richiedi_auth
def pec_schedule_deadline(message_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        result = _repo().schedule_deadline(message_id, actor=_actor(), due_date=str(payload.get("data_scadenza") or ""))
        result = _notify_pec_deadline(message_id, result)
        return _json_success(result, 200 if result.get("ok") else 409)
    except KeyError:
        return _json_error(404)
    except TenantDataPathError:
        return _json_error(403)


@pec_pipeline_api.post("/demo/ingest")
@_richiedi_auth
def pec_demo_ingest():
    try:
        return _json_success({"ok": True, "data": ingest_synthetic_dataset(_repo(), run_workers=True)})
    except TenantDataPathError:
        return _json_error(403)

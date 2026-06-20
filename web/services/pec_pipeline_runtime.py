"""Runtime tenant-aware per worker, digest e acquisizione automatica della pipeline PEC."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flask import current_app, g, has_app_context

from pct.pec_pipeline import PecAuditRepository


def _path_from_mapping(paths: Mapping[str, Any], key: str, default: str) -> str:
    value = paths.get(key)
    if value:
        return str(value)
    if has_app_context() and current_app.config.get(key):
        return str(current_app.config[key])
    return default


def repository_from_paths(paths: Mapping[str, Any], *, tenant_label: str = "default") -> PecAuditRepository:
    email_db = Path(_path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json"))
    audit_db = Path(str(paths.get("PEC_AUDIT_DB") or email_db.parent / "pec_audit.sqlite"))
    return PecAuditRepository(
        audit_db,
        tenant_id="default",
        fascicoli_db_path=_path_from_mapping(paths, "FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_path_from_mapping(paths, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_path_from_mapping(paths, "SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_path_from_mapping(paths, "AGENDA_DB", "./agenda/appuntamenti.json"),
        calendar_sync_db_path=_path_from_mapping(paths, "CALENDAR_SYNC_DB", "./agenda/calendar_sync_engine.json"),
    )


def repository_for_current_request() -> PecAuditRepository:
    paths = getattr(g, "data_paths", {}) if has_app_context() else {}
    return repository_from_paths(paths or {}, tenant_label="default")


def run_workers_for_paths(paths: Mapping[str, Any], *, tenant_label: str, limit: int = 200) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    report = repo.run_pending_jobs(limit=limit, actor="scheduler")
    try:
        document_presidio = repo.recover_missing_hearings_from_fascicolo_documents(
            limit=max(10, min(int(limit or 200), 80)),
            actor="scheduler",
        )
        if (
            document_presidio.get("scheduled")
            or document_presidio.get("already_presided")
            or document_presidio.get("errors")
        ):
            report["document_presidio"] = document_presidio
    except Exception as exc:
        report["document_presidio"] = {"ok": False, "errors": [str(exc)]}
    try:
        notification_jobs = list(report.get("jobs") or [])
        if isinstance(report.get("document_presidio"), dict):
            notification_jobs.extend(list((report["document_presidio"] or {}).get("notification_jobs") or []))
        notified = notify_auto_deadlines_for_paths(
            paths,
            tenant_label=tenant_label,
            jobs=notification_jobs,
        )
        if notified.get("created") or notified.get("errors"):
            report["auto_deadline_notifications"] = notified
    except Exception:
        # La notifica è best-effort: la scadenza resta comunque registrata
        # in scadenziario/agenda anche se il centro notifiche non è raggiungibile.
        pass
    return report


def build_digest_for_paths(paths: Mapping[str, Any], *, tenant_label: str, digest_date: str | None = None) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    return repo.build_daily_digest(digest_date=digest_date, actor="scheduler")


def _tenant_notification_id(tenant_label: str) -> str:
    """Stesso identificativo usato dal web (`current_tenant_id`): id studio, poi slug."""

    slug = str(tenant_label or "").strip().lower()
    if not slug or slug == "default":
        return "default"
    try:
        from pct.tenant import GestioneTenant

        registry = str(current_app.config.get("TENANTS_REGISTRY") or "").strip() if has_app_context() else ""
        if registry:
            studio = GestioneTenant(registry_path=registry).get(slug)
            tenant_id = str(getattr(studio, "id", "") or "").strip()
            if tenant_id:
                return tenant_id
    except Exception:
        pass
    return slug


def _notification_recipients(paths: Mapping[str, Any]) -> list[str]:
    """Utenti attivi dello studio con lettura scadenziario: destinatari del presidio."""

    from pct.auth import GestioneUtenti

    auth_db = _path_from_mapping(paths, "AUTH_DB", "./auth/utenti.json")
    if not Path(auth_db).exists():
        return []
    audit_db = _path_from_mapping(paths, "AUDIT_DB", "./auth/audit.json")
    secret = str(current_app.config.get("SECRET_KEY", "") or "scheduler") if has_app_context() else "scheduler"
    gestore = GestioneUtenti(
        db_path=auth_db,
        audit_path=audit_db,
        secret_key=secret,
        crea_admin_se_vuoto=False,
    )
    recipients: list[str] = []
    for user in gestore.tutti(solo_attivi=True):
        try:
            if hasattr(user, "ha_permesso") and not user.ha_permesso("scadenziario.leggi"):
                continue
        except Exception:
            pass
        user_id = str(getattr(user, "id", "") or getattr(user, "username", "") or "").strip()
        if user_id:
            recipients.append(user_id)
    return recipients


def notify_auto_deadlines_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Notifica (centro notifiche + push) le scadenze create dal presidio automatico.

    Speculare a `_notify_pec_deadline` del percorso manuale: stessa `dedupe_key`
    per (tenant, utente), quindi nessun doppione se la stessa PEC passa da
    entrambi i percorsi. Destinatari: utenti attivi con lettura scadenziario.
    """

    report = {"created": 0, "duplicates": 0, "errors": 0, "recipients": 0}
    deadlines: list[tuple[str, dict[str, Any]]] = []
    for job in jobs:
        job_type = str(job.get("job_type") or "")
        if job_type not in {"link", "document_presidio"}:
            continue
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        deadline = result.get("auto_deadline") if isinstance(result.get("auto_deadline"), dict) else {}
        if deadline.get("ok") and str(deadline.get("deadline_id") or "").strip():
            deadlines.append((str(job.get("message_id") or ""), deadline))
    if not deadlines:
        return report

    from pct.notifications import NotificationRepository, NotificationService
    from pct.notifications.web_push import load_web_push_config

    recipients = _notification_recipients(paths)
    report["recipients"] = len(recipients)
    if not recipients:
        return report
    db_path = _path_from_mapping(paths, "NOTIFICATIONS_DB", "./notifications/notifications.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    config = current_app.config if has_app_context() else {}
    service = NotificationService(
        NotificationRepository(db_path),
        web_push_config=load_web_push_config(config),
    )
    tenant_id = _tenant_notification_id(tenant_label)
    for message_id, deadline in deadlines:
        agenda = deadline.get("agenda") if isinstance(deadline.get("agenda"), dict) else {}
        agenda_id = str(agenda.get("agenda_id") or "")
        due_date = str(deadline.get("due_date") or "")
        source_id = message_id or str(deadline.get("deadline_id") or "")
        agenda_text = " e all'agenda" if agenda_id else ""
        due_text = f" per il {due_date}" if due_date else ""
        origin = "Presidio documentale Lex" if source_id.startswith("docpresidio:") else "Presidio PEC automatico"
        body = f"{origin}: scadenza collegata allo scadenziario{agenda_text}{due_text}."
        for user_id in recipients:
            try:
                _record, created, _summary = service.create_notification(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    type="pec_deadline",
                    priority="important",
                    title="Scadenza operativa registrata" if source_id.startswith("docpresidio:") else "Scadenza PEC registrata",
                    body=body,
                    href="/scadenziario?vista=pec",
                    source_type="pec_deadline",
                    source_id=source_id,
                    dedupe_key=f"PEC_AUDIT:{source_id}:deadline",
                    payload_json={
                        "deadlineId": str(deadline.get("deadline_id") or ""),
                        "agendaId": agenda_id,
                        "dueDate": due_date,
                        "alreadyExists": bool(deadline.get("already_exists")),
                        "origin": "auto",
                    },
                    send_push=True,
                )
                report["created" if created else "duplicates"] += 1
            except Exception:
                report["errors"] += 1
    return report


def local_email_sort_key(email_obj: Any) -> str:
    return str(
        getattr(email_obj, "timestamp", "")
        or getattr(email_obj, "data", "")
        or getattr(email_obj, "ricevuta_il", "")
        or ""
    )


def email_rilevante_per_presidio_pec(email_obj: Any) -> bool:
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


def read_or_reconstruct_local_mime(gestore: Any, email_obj: Any) -> tuple[bytes, str]:
    raw_mime = gestore.leggi_eml_originale(email_obj)
    if raw_mime:
        return bytes(raw_mime), "originale"
    try:
        from pct.pec_control_tower import _reconstruct_email_archive_mime

        reconstructed = _reconstruct_email_archive_mime(gestore, email_obj)
    except Exception:
        reconstructed = b""
    if reconstructed:
        return bytes(reconstructed), "ricostruito"
    return b"", ""


def _record_auto_acquire_item(
    repo: PecAuditRepository,
    run_id: str,
    *,
    email_id: str,
    message_id: str = "",
    subject: str = "",
    status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        repo.record_local_acquire_item(
            run_id,
            email_id=email_id,
            message_id=message_id,
            subject=subject,
            status=status,
            detail=detail or {},
        )
    except Exception:
        pass


def acquire_local_pec_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    batch_size: int = 10,
    scan_limit: int = 250,
) -> dict[str, Any]:
    """Acquisisce nel presidio PEC le email rilevanti non ancora presidiate.

    Versione automatica e a budget del percorso manuale "Acquisisci dal locale":
    legge le email più recenti dell'archivio, salta quelle già presidiate
    (per Message-ID header o per ultimo esito registrato) e ingerisce solo le
    nuove. I job accodati vengono poi lavorati da `run_workers_for_paths`
    (parse, classificazione, validazione con scadenza automatica in
    scadenziario/agenda, collegamento al fascicolo, digest). Il budget per giro
    è volutamente prudente: il presidio gira ogni 5 minuti sul worker e l'OCR
    degli allegati è la fase più costosa in RAM/CPU.
    """

    from pct.email_client import GestioneEmailRicevute

    report: dict[str, Any] = {
        "scanned": 0,
        "relevant": 0,
        "ingested": 0,
        "duplicates": 0,
        "skipped_presided": 0,
        "missing_mime": 0,
        "errors": 0,
    }
    email_db = _path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json")
    if not Path(email_db).exists():
        return {**report, "skipped": True, "reason": "archivio email assente"}
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    gestore = GestioneEmailRicevute(db_path=email_db)
    emails = sorted(
        gestore._carica().values(),  # noqa: SLF001 - presidio tenant-aware sulla casella locale
        key=local_email_sort_key,
        reverse=True,
    )[: max(1, int(scan_limit or 250))]
    report["scanned"] = len(emails)
    relevant = [item for item in emails if email_rilevante_per_presidio_pec(item)]
    report["relevant"] = len(relevant)
    if not relevant:
        return report
    known_headers = repo.ids_by_header_message_ids(
        str(getattr(item, "message_id", "") or "").strip() for item in relevant
    )
    presided_ids = repo.presided_email_ids(
        str(getattr(item, "id", "") or "") for item in relevant
    )
    candidates: list[Any] = []
    for item in relevant:
        email_id = str(getattr(item, "id", "") or "")
        header = str(getattr(item, "message_id", "") or "").strip()
        if (header and header in known_headers) or (email_id and email_id in presided_ids):
            report["skipped_presided"] += 1
            continue
        candidates.append(item)
        if len(candidates) >= max(1, int(batch_size or 10)):
            break
    if not candidates:
        return report
    run_id = ""
    try:
        run = repo.start_local_acquire_run(
            total_emails=len(candidates), batch_size=len(candidates), actor="scheduler"
        )
        run_id = str(run.get("id") or "")
    except Exception:
        run_id = ""
    if not run_id:
        # Senza run tracciabile non si ingerisce nulla: con le foreign key attive
        # gli esiti per email non sarebbero registrabili e le stesse PEC
        # verrebbero rilette dal disco a ogni giro del presidio.
        return {**report, "skipped": True, "reason": "registro presidio non disponibile"}
    for item in candidates:
        email_id = str(getattr(item, "id", "") or "")
        subject = str(getattr(item, "oggetto", "") or "")[:240]
        raw_mime, mime_source = read_or_reconstruct_local_mime(gestore, item)
        if not raw_mime:
            report["missing_mime"] += 1
            _record_auto_acquire_item(repo, run_id, email_id=email_id, subject=subject, status="missing_mime")
            continue
        try:
            result = repo.ingest_mime(
                raw_mime,
                account_email=str(
                    getattr(item, "destinatari", "") or getattr(item, "mittente", "") or "casella PEC locale"
                )[:240],
                folder=str(getattr(item, "cartella", "") or "INBOX"),
                imap_uid=str(getattr(item, "uid_imap", "") or f"auto:{email_id}"),
                actor="scheduler",
            )
            duplicate = bool(result.get("duplicate"))
            report["duplicates" if duplicate else "ingested"] += 1
            _record_auto_acquire_item(
                repo,
                run_id,
                email_id=email_id,
                message_id=str(result.get("id") or ""),
                subject=subject,
                status="duplicate" if duplicate else "ingested",
                detail={"mime_source": mime_source, "origin": "auto"},
            )
        except Exception as exc:
            report["errors"] += 1
            _record_auto_acquire_item(
                repo,
                run_id,
                email_id=email_id,
                subject=subject,
                status="processed",
                detail={"errore": str(exc)[:180], "origin": "auto"},
            )
    if run_id:
        try:
            repo.update_local_acquire_run(
                run_id,
                cursor_index=len(candidates),
                total_emails=len(candidates),
                batch_size=len(candidates),
                deltas={
                    "acquired": int(report["ingested"]) + int(report["duplicates"]),
                    "duplicates": int(report["duplicates"]),
                    "skipped_missing_mime": int(report["missing_mime"]),
                    "errors": int(report["errors"]),
                },
                status="completed",
                payload={"origin": "auto", "tenant_label": tenant_label},
                actor="scheduler",
            )
        except Exception:
            pass
    return report

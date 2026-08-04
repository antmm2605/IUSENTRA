"""Runtime tenant-aware per worker, digest e acquisizione automatica della pipeline PEC."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flask import current_app, g, has_app_context

from pct.formatting import format_date_it

ROME_TZ = ZoneInfo("Europe/Rome")
GENERIC_REMOTE_HEARING_PLATFORMS = {
    "altra",
    "da verificare",
    "incerta",
    "sconosciuta",
}
GENERIC_REMOTE_HEARING_ACCESS_INFO = {
    f"piattaforma: {platform}" for platform in GENERIC_REMOTE_HEARING_PLATFORMS
}
from pct.incremental_jobs import cursor_tuple, is_after_cursor
from pct.notifications.web_push import safe_remote_hearing_url
from pct.pec_pipeline import PecAuditRepository, _remote_hearing_deadline_extra


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
        tenant_id=str(tenant_label or "default"),
        fascicoli_db_path=_path_from_mapping(paths, "FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_path_from_mapping(paths, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_path_from_mapping(paths, "SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_path_from_mapping(paths, "AGENDA_DB", "./agenda/appuntamenti.json"),
        calendar_sync_db_path=_path_from_mapping(paths, "CALENDAR_SYNC_DB", "./agenda/calendar_sync_engine.json"),
    )


def repository_for_current_request() -> PecAuditRepository:
    paths = getattr(g, "data_paths", {}) if has_app_context() else {}
    return repository_from_paths(paths or {}, tenant_label="default")


def run_workers_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    limit: int = 200,
    document_presidio_limit: int | None = None,
) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    try:
        maintenance = repo.enqueue_stale_attachment_repairs(
            limit=max(1, min(int(limit or 200), 20)),
            actor="scheduler",
        )
    except Exception as exc:
        maintenance = {"ok": False, "queued": 0, "unresolved": 1, "error": str(exc)[:180]}
    report = repo.run_pending_jobs(limit=limit, actor="scheduler")
    if maintenance.get("queued") or maintenance.get("unresolved") or maintenance.get("error"):
        report["attachment_maintenance"] = maintenance
    try:
        cleanup = repo.cleanup_legacy_pec_operational_items(actor="scheduler")
        if cleanup.get("scadenziario_removed") or cleanup.get("agenda_removed") or cleanup.get("errors"):
            report["legacy_cleanup"] = cleanup
    except Exception as exc:
        report["legacy_cleanup"] = {"errors": 1, "message": str(exc)[:180]}
    try:
        if document_presidio_limit is None:
            effective_document_limit = max(10, min(int(limit or 200), 80))
        else:
            effective_document_limit = max(0, int(document_presidio_limit or 0))
        if effective_document_limit <= 0:
            report["document_presidio"] = {
                "skipped_service": True,
                "reason": "budget_scheduler_esaurito",
                "limit": 0,
            }
        else:
            document_presidio = repo.recover_missing_hearings_from_fascicolo_documents(
                limit=effective_document_limit,
                actor="scheduler",
            )
            if (
                document_presidio.get("scheduled")
                or document_presidio.get("already_presided")
                or document_presidio.get("errors")
                or document_presidio.get("checked_fascicoli")
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
    try:
        economic = trigger_economic_audits_for_paths(
            paths,
            tenant_label=tenant_label,
            jobs=list(report.get("jobs") or []),
            pec_repo=repo,
        )
        if economic.get("triggered") or economic.get("errors"):
            report["economic_audits"] = economic
    except Exception:
        # Best-effort: il controllo economico è un'anteprima aggiuntiva; un suo
        # errore non deve fermare il presidio PEC (parse/classify/link restano validi).
        pass
    try:
        # Segnala al piano del giorno le entità toccate dal presidio PEC:
        # il refresh incrementale rielabora solo queste, mai tutto lo studio.
        from web.services.daily_plan_runtime import mark_dirty_for_paths

        touched_fascicoli: set[str] = set()
        touched_messages: set[str] = set()
        for job in list(report.get("jobs") or []):
            message_id = str(job.get("message_id") or "").strip()
            if message_id:
                touched_messages.add(message_id)
            result = job.get("result") if isinstance(job.get("result"), dict) else {}
            fascicolo_id = str(result.get("fascicolo_id") or "").strip()
            if fascicolo_id:
                touched_fascicoli.add(fascicolo_id)
        if touched_fascicoli:
            mark_dirty_for_paths(
                paths,
                tenant_label=tenant_label,
                entity_type="fascicolo",
                entity_ids=touched_fascicoli,
                reason="presidio_pec",
            )
        if touched_messages:
            mark_dirty_for_paths(
                paths,
                tenant_label=tenant_label,
                entity_type="pec_message",
                entity_ids=touched_messages,
                reason="presidio_pec",
            )
    except Exception:
        # Il piano del giorno è una proiezione derivata: un errore qui non deve
        # mai fermare il presidio PEC.
        pass
    return report


def rebuild_operational_matrix_for_paths(paths: Mapping[str, Any], *, tenant_label: str, limit: int = 0, worker_limit: int = 500) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    queued = repo.enqueue_operational_matrix_rebuild(limit=limit, actor="scheduler-rebuild")
    workers = run_workers_for_paths(paths, tenant_label=tenant_label, limit=max(1, int(worker_limit or 500)))
    return {"ok": True, "queued": queued, "workers": workers}


def build_digest_for_paths(paths: Mapping[str, Any], *, tenant_label: str, digest_date: str | None = None) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    return repo.build_daily_digest(digest_date=digest_date, actor="scheduler")


def _tenant_notification_id(tenant_label: str, paths: Mapping[str, Any] | None = None) -> str:
    """Stesso identificativo usato dal web (`current_tenant_id`): id studio, poi slug."""

    slug = str(tenant_label or "").strip().lower()
    if not slug or slug == "default":
        return "default"
    data_paths = paths or {}
    manifest = str(data_paths.get("STORAGE_CONFIG") or "").strip()
    if manifest:
        try:
            import json

            manifest_path = Path(manifest)
            storage = json.loads(manifest_path.read_text(encoding="utf-8"))
            tenant_id = str(storage.get("tenant_id") or storage.get("id") or "").strip()
            if tenant_id:
                return tenant_id
            tenant_root = manifest_path.parent.parent
            registry_path = tenant_root.parent.parent / "tenants.json"
            if registry_path.exists():
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                entry = registry.get(slug) if isinstance(registry, dict) else None
                if not isinstance(entry, dict):
                    entry = next(
                        (
                            value
                            for value in registry.values()
                            if isinstance(value, dict)
                            and str(value.get("storage_key") or "").strip() == tenant_root.name
                        ),
                        None,
                    )
                if isinstance(entry, dict):
                    tenant_id = str(entry.get("id") or entry.get("tenant_id") or "").strip()
                    if tenant_id:
                        return tenant_id
        except Exception:
            pass
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

    from web.services.notifications_runtime import notification_recipients_for_paths

    recipients: list[str] = []
    for user in notification_recipients_for_paths(
        paths,
        database=paths.get("_TENANT_DATABASE_CONFIG"),
    ):
        try:
            if hasattr(user, "ha_permesso") and not user.ha_permesso("scadenziario.leggi"):
                continue
        except Exception:
            pass
        user_id = str(getattr(user, "id", "") or getattr(user, "username", "") or "").strip()
        if user_id:
            recipients.append(user_id)
    return recipients


def build_pec_deadline_notification(
    deadline: Mapping[str, Any],
    *,
    source_id: str,
    automatic: bool,
) -> dict[str, Any]:
    """Costruisce la stessa notifica per schedulazione manuale e automatica."""

    agenda = deadline.get("agenda") if isinstance(deadline.get("agenda"), dict) else {}
    proposal = deadline.get("proposal") if isinstance(deadline.get("proposal"), dict) else {}
    remote = (
        dict(deadline.get("remote_hearing"))
        if isinstance(deadline.get("remote_hearing"), Mapping)
        else _remote_hearing_deadline_extra({}, proposal)
    )
    deadline_id = str(deadline.get("deadline_id") or "").strip()
    agenda_id = str(agenda.get("agenda_id") or "").strip()
    due_date = str(deadline.get("due_date") or "").strip()
    due_date_label = format_date_it(due_date) or due_date
    remote_detected = bool(
        remote.get("remote_hearing_detected")
        or remote.get("remote_hearing_url")
        or remote.get("remote_hearing_pdf_required")
    )
    remote_candidate = str(remote.get("remote_hearing_url") or "").strip()
    remote_url = safe_remote_hearing_url(
        {
            "remoteHearingUrl": remote_candidate,
            "remoteHearingSource": str(remote.get("remote_hearing_source") or "").strip(),
            "remoteHearingVerified": bool(remote.get("remote_hearing_verified")),
        },
        require_verified=True,
    )
    remote_verified = bool(remote_url)
    remote_access_info = str(remote.get("remote_hearing_access_info") or "").strip()
    remote_platform = str(remote.get("remote_hearing_platform") or "").strip()
    if remote_access_info.casefold() in GENERIC_REMOTE_HEARING_ACCESS_INFO:
        remote_access_info = ""
    if remote_platform.casefold() in GENERIC_REMOTE_HEARING_PLATFORMS:
        remote_platform = ""
    origin = "Presidio documentale Lex" if source_id.startswith("docpresidio:") else (
        "Presidio PEC automatico" if automatic else "Presidio PEC"
    )
    if agenda_id:
        href = str(agenda.get("agenda_href") or f"/agenda/{agenda_id}")
    elif deadline_id:
        href = f"/scadenziario/{deadline_id}?vista=tutte"
    else:
        href = "/scadenziario?vista=pec"

    if remote_detected:
        title = "Udienza audiovisiva registrata"
        if remote_url:
            remote_status = (
                "Collegamento audiovisivo verificato e disponibile."
                if remote_verified
                else "Collegamento audiovisivo disponibile e da controllare sulla fonte."
            )
        else:
            remote_status = (
                remote_access_info
                if remote_access_info
                else "Collegamento audiovisivo da acquisire dal documento dell'udienza."
            )
        body = (
            f"{origin}: udienza collegata ad Agenda e Scadenziario"
            f"{f' per il {due_date_label}' if due_date_label else ''}. {remote_status}"
        )
        action_label = "Collegati all'udienza" if remote_url else "Apri udienza"
    else:
        title = "Scadenza operativa registrata" if source_id.startswith("docpresidio:") else "Scadenza PEC registrata"
        agenda_text = " e all'Agenda" if agenda_id else ""
        body = (
            f"{origin}: scadenza collegata allo Scadenziario{agenda_text}"
            f"{f' per il {due_date_label}' if due_date_label else ''}."
        )
        action_label = "Apri scadenza"

    return {
        "title": title,
        "body": body,
        "href": href,
        "payload_json": {
            "deadlineId": deadline_id,
            "agendaId": agenda_id,
            "dueDate": due_date,
            "dueDateLabel": due_date_label,
            "alreadyExists": bool(deadline.get("already_exists")),
            "origin": "auto" if automatic else "manual",
            "actionLabel": action_label,
            "remoteHearingDetected": remote_detected,
            "remoteHearingMode": str(remote.get("remote_hearing_mode") or "").strip(),
            "remoteHearingUrl": remote_url,
            "remoteHearingSource": str(remote.get("remote_hearing_source") or "").strip(),
            "remoteHearingVerified": remote_verified,
            "remoteHearingTime": str(remote.get("remote_hearing_time") or "").strip(),
            "remoteHearingPlatform": remote_platform,
            "remoteHearingMeetingId": str(remote.get("remote_hearing_meeting_id") or "").strip(),
            "remoteHearingAccessInfo": remote_access_info,
            "remoteHearingPdfRequired": bool(remote.get("remote_hearing_pdf_required")),
        },
    }


def should_send_pec_deadline_web_push(notification: Mapping[str, Any]) -> bool:
    payload = notification.get("payload_json") if isinstance(notification.get("payload_json"), Mapping) else {}
    if not bool(payload.get("remoteHearingDetected")):
        return True
    return bool(
        (payload.get("remoteHearingUrl") and payload.get("remoteHearingVerified"))
        or payload.get("remoteHearingPdfRequired")
    )


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

    report = {"created": 0, "duplicates": 0, "errors": 0, "recipients": 0, "expired_legacy_duplicates": 0}
    deadlines: list[tuple[str, dict[str, Any], set[str]]] = []
    for job in jobs:
        job_type = str(job.get("job_type") or "")
        if job_type not in {"link", "document_presidio"}:
            continue
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        deadline = result.get("auto_deadline") if isinstance(result.get("auto_deadline"), dict) else {}
        deadline_results = (
            [item for item in list(deadline.get("hearing_results") or []) if isinstance(item, dict)]
            if isinstance(deadline.get("hearing_results"), list)
            else []
        ) or [deadline]
        for deadline_result in deadline_results:
            if not deadline_result.get("ok") or not str(deadline_result.get("deadline_id") or "").strip():
                continue
            source_id = str(
                deadline_result.get("deadline_id")
                or deadline_result.get("scheduled_message_id")
                or job.get("message_id")
                or ""
            )
            legacy_source_ids = {
                str(deadline_result.get("scheduled_message_id") or "").strip(),
                str(job.get("message_id") or "").strip(),
            }
            legacy_source_ids.discard("")
            legacy_source_ids.discard(source_id)
            deadlines.append((source_id, deadline_result, legacy_source_ids))
    if not deadlines:
        return report

    from pct.notifications import NotificationService
    from pct.notifications.web_push import load_web_push_config
    from web.services.notifications_runtime import build_notification_repository_for_paths

    recipients = _notification_recipients(paths)
    report["recipients"] = len(recipients)
    if not recipients:
        return report
    config = current_app.config if has_app_context() else {}
    service = NotificationService(
        build_notification_repository_for_paths(
            paths,
            database=paths.get("_TENANT_DATABASE_CONFIG"),
            config=config,
        ),
        web_push_config=load_web_push_config(config),
    )
    tenant_id = str(paths.get("_TENANT_NOTIFICATION_ID") or _tenant_notification_id(tenant_label, paths))
    for message_id, deadline, legacy_source_ids in deadlines:
        source_id = message_id or str(deadline.get("deadline_id") or "")
        notification = build_pec_deadline_notification(
            deadline,
            source_id=source_id,
            automatic=True,
        )
        for user_id in recipients:
            try:
                _record, created, _summary = service.create_notification(
                    tenant_id=tenant_id,
                    user_id=user_id,
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
                report["created" if created else "duplicates"] += 1
                if legacy_source_ids:
                    report["expired_legacy_duplicates"] += service.repository.expire_notifications_by_source_ids(
                        tenant_id,
                        user_id,
                        source_type="pec_deadline",
                        source_ids=legacy_source_ids,
                    )
            except Exception:
                report["errors"] += 1
    return report


def _economic_control_enabled() -> bool:
    try:
        from web.services.feature_flags import is_feature_enabled

        config = current_app.config if has_app_context() else None
        return bool(is_feature_enabled("features.sentenzaEconomicControl", config))
    except Exception:
        return False


def _sentenza_ocr_text(detail: Mapping[str, Any]) -> tuple[str, str]:
    """Testo OCR del PDF provvedimento fra gli allegati (il più lungo), + suo sha256.

    Esclude ricevute/daticert/eml/tecnici: la sentenza arriva come atto/PDF. Il motore
    ri-estrae RG e importi dal testo, quindi basta il PDF principale.
    """

    best_text, best_hash = "", ""
    for att in list(detail.get("attachments") or []):
        if not isinstance(att, dict):
            continue
        classification = str(att.get("classification") or "").lower()
        if any(marker in classification for marker in ("daticert", "ricevut", "eml", "tecnic")):
            continue
        content_type = str(att.get("content_type") or "").lower()
        filename = str(att.get("filename") or "").lower()
        # Il PCT consegna il provvedimento dentro uno ZIP (`nome.pdf.zip`) o
        # firmato (`nome.pdf.p7m`): richiedere l'estensione `.pdf` secca faceva
        # scartare proprio la sentenza, e l'audit economico restava senza testo.
        # Il testo dentro lo ZIP e' gia' stato estratto dal job OCR.
        e_pdf = (
            content_type.startswith("application/pdf")
            or filename.endswith((".pdf", ".pdf.p7m", ".pdf.zip"))
            or (".pdf" in filename and filename.endswith(".zip"))
        )
        if not e_pdf:
            continue
        text = str(att.get("ocr_text") or "")
        if len(text) > len(best_text):
            best_text, best_hash = text, str(att.get("sha256") or "")
    return best_text, best_hash


def trigger_economic_audits_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    jobs: list[dict[str, Any]],
    pec_repo: PecAuditRepository,
) -> dict[str, Any]:
    """Auto-trigger del controllo economico su PEC di deposito sentenza (anteprima).

    Speculare a `notify_auto_deadlines_for_paths`: scorre i job `link` con fascicolo
    collegato e, se la PEC è classificata `deposito_sentenza` e il flag
    `features.sentenzaEconomicControl` è attivo, lancia l'audit economico in **sola
    anteprima** (audit/eventi `to_review`, mai definitivi). Il tenant per il repository
    economico è lo **slug minuscolo**, così coincide con ciò che legge la UI React.
    """

    report = {"triggered": 0, "skipped": 0, "errors": 0}
    if not _economic_control_enabled():
        return report
    pairs: list[tuple[str, str]] = []
    for job in jobs:
        if str(job.get("job_type") or "") != "link":
            continue
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        fascicolo_id = str(result.get("fascicolo_id") or "").strip()
        message_id = str(job.get("message_id") or "").strip()
        if fascicolo_id and message_id:
            pairs.append((message_id, fascicolo_id))
    if not pairs:
        return report

    from pct.sentenza_economic_repository import SentenzaEconomicRepository
    from pct.sentenza_economic_workflow import should_trigger_economic_audit
    from web.services.sentenza_economic_runtime import run_pec_economic_trigger

    tenant_id = str(tenant_label or "").strip().lower()
    se_db = _path_from_mapping(paths, "SENTENZA_ECONOMIC_DB", "./economico/sentenza_economic.db")
    try:
        se_repo = SentenzaEconomicRepository(se_db)
        fasc_manager = pec_repo._fascicoli_manager()  # noqa: SLF001 - stessa pipeline
    except Exception:
        report["errors"] += 1
        return report

    for message_id, fascicolo_id in pairs:
        try:
            detail = pec_repo.get_message_detail(message_id)
            parsed = detail.get("parsed") if isinstance(detail.get("parsed"), dict) else {}
            classification = parsed.get("legal_workflow") if isinstance(parsed.get("legal_workflow"), dict) else {}
            if not should_trigger_economic_audit(classification):
                report["skipped"] += 1
                continue
            fascicolo = fasc_manager.get(fascicolo_id) if fasc_manager else None
            if fascicolo is None:
                report["skipped"] += 1
                continue
            testo, doc_hash = _sentenza_ocr_text(detail)
            if not testo.strip():
                report["skipped"] += 1
                continue
            outcome = run_pec_economic_trigger(
                classification=classification,
                fascicolo=fascicolo,
                testo=testo,
                repo=se_repo,
                cu_tiers=None,
                tenant_id=tenant_id,
                message_id=message_id,
                document_hash_sha256=doc_hash,
            )
            report["triggered" if outcome.get("ok") else "skipped"] += 1
        except Exception:
            report["errors"] += 1
    return report


_SORT_KEY_MIN = "0000-00-00T00:00:00"
_LOCAL_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def _normalizza_data_locale(value: Any) -> str:
    """Riporta una data di posta a una chiave ordinabile e non avvelenabile.

    Il cursore dell'acquisizione automatica ordina l'archivio con questa chiave.
    Finché era la stringa grezza del messaggio, bastava una PEC con data in
    formato diverso o nel futuro per portarla in testa: il cursore si salvava su
    quel valore e da lì in poi ogni PEC nuova risultava "più vecchia", quindi il
    presidio smetteva di acquisire senza segnalare nulla. Qui la data viene
    normalizzata a ISO e le date non interpretabili o palesemente future
    finiscono in fondo, dove non possono bloccare il cursore.
    """

    raw = str(value or "").strip()
    if not raw:
        return _SORT_KEY_MIN
    candidate = raw.replace("Z", "+00:00")
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = None
    if parsed is None:
        testo = raw.split("+")[0].strip()
        for fmt in _LOCAL_DATE_FORMATS:
            try:
                parsed = datetime.strptime(testo, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            parsed = None
    if parsed is None:
        return _SORT_KEY_MIN
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(ROME_TZ).replace(tzinfo=None)
    # Una data nel futuro non è una data: non deve poter diventare il cursore.
    limite = datetime.now(ROME_TZ).replace(tzinfo=None) + timedelta(days=1)
    if parsed > limite:
        return _SORT_KEY_MIN
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def local_email_sort_key(email_obj: Any) -> str:
    for attributo in ("timestamp", "data", "ricevuta_il"):
        chiave = _normalizza_data_locale(getattr(email_obj, attributo, ""))
        if chiave != _SORT_KEY_MIN:
            return chiave
    return _SORT_KEY_MIN


def _local_email_cursor(email_obj: Any) -> dict[str, str]:
    return {
        "sort_key": local_email_sort_key(email_obj),
        "item_id": str(getattr(email_obj, "id", "") or ""),
    }


def _full_scan_enabled(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si"}


def _as_int_safe(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _archive_fingerprint(path: Path) -> str:
    """Impronta economica dell'archivio: dice se c'e' qualcosa di nuovo da leggere."""

    try:
        stat = path.stat()
    except OSError:
        return ""
    return f"{int(stat.st_mtime_ns)}:{int(stat.st_size)}"


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
        "scan_mode": "not_started",
        "archive_seen": 0,
        "scanned": 0,
        "relevant": 0,
        "ingested": 0,
        "duplicates": 0,
        "skipped_presided": 0,
        "missing_mime": 0,
        "errors": 0,
        "cursor_saved": False,
    }
    email_db = _path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json")
    archivio = Path(email_db)
    if not archivio.exists():
        return {**report, "skipped": True, "reason": "archivio email assente"}
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    cursor = repo.latest_local_acquire_cursor(origin="auto")
    full_scan = _full_scan_enabled(
        os.environ.get("IUSENTRA_PEC_AUTO_ACQUIRE_FULL_SCAN")
        or (current_app.config.get("IUSENTRA_PEC_AUTO_ACQUIRE_FULL_SCAN") if has_app_context() else "")
    )
    impronta = _archive_fingerprint(archivio)
    # Il presidio gira ogni 5 minuti, la casella viene riscritta ogni 15: senza
    # questo controllo l'archivio verrebbe riletto e riordinato per intero due
    # volte su tre a vuoto, che e' il costo CPU piu' alto del giro. Si salta solo
    # a lavoro chiuso: se il backlog non e' completo o il batch precedente si e'
    # esaurito, il cursore non porta l'impronta e il giro viene eseguito.
    if (
        not full_scan
        and impronta
        and cursor.get("archive_fingerprint") == impronta
        and cursor.get("backlog_complete")
    ):
        return {
            **report,
            "scan_mode": "incremental",
            "skipped": True,
            "reason": "archivio invariato dall'ultimo giro",
            "archive_fingerprint": impronta,
        }
    gestore = GestioneEmailRicevute(db_path=email_db)
    all_emails = sorted(
        gestore._carica().values(),  # noqa: SLF001 - presidio tenant-aware sulla casella locale
        key=lambda item: cursor_tuple(local_email_sort_key(item), getattr(item, "id", "")),
        reverse=True,
    )
    report["archive_seen"] = len(all_emails)
    if not all_emails:
        return report
    effective_scan_limit = max(1, int(scan_limit or 250))
    newest_cursor = _local_email_cursor(all_emails[0])
    selected_emails: list[Any] = []
    backlog_window: list[Any] = []
    backlog_attempted = False
    if full_scan or not cursor:
        selected_emails = all_emails[:effective_scan_limit]
        report["scan_mode"] = "full_scan" if full_scan else "bootstrap"
    else:
        report["scan_mode"] = "incremental"
        for item in all_emails:
            item_cursor = _local_email_cursor(item)
            if is_after_cursor(
                item_cursor.get("sort_key"),
                item_cursor.get("item_id"),
                cursor,
                include_boundary=True,
            ):
                selected_emails.append(item)
                if len(selected_emails) >= effective_scan_limit:
                    break
            else:
                break
        if not cursor.get("backlog_complete"):
            boundary = {
                "sort_key": cursor.get("backlog_sort_key") or cursor.get("sort_key"),
                "item_id": cursor.get("backlog_item_id") or cursor.get("item_id"),
            }
            boundary_tuple = cursor_tuple(boundary.get("sort_key"), boundary.get("item_id"))
            seen_ids = {str(getattr(item, "id", "") or "") for item in selected_emails}
            if len(selected_emails) < effective_scan_limit:
                backlog_attempted = True
                for item in all_emails:
                    email_id = str(getattr(item, "id", "") or "")
                    if email_id in seen_ids:
                        continue
                    if cursor_tuple(local_email_sort_key(item), email_id) < boundary_tuple:
                        backlog_window.append(item)
                        if len(selected_emails) + len(backlog_window) >= effective_scan_limit:
                            break
            selected_emails.extend(backlog_window)
            report["scan_mode"] = "incremental_backlog"
        if not selected_emails:
            # Sblocco automatico: se l'archivio e' cresciuto rispetto al giro in
            # cui il cursore e' stato salvato ma l'incrementale non seleziona
            # nulla, il cursore e' fermo su un valore che nessuna PEC nuova
            # supera. Invece di restare muti si rilegge la finestra piu' recente
            # e lo si segnala: la deduplica per Message-ID e mime_sha256 evita
            # comunque di ripresentare all'avvocato PEC gia' presidiate.
            archivio_precedente = _as_int_safe(cursor.get("archive_seen"))
            if archivio_precedente and report["archive_seen"] > archivio_precedente:
                selected_emails = all_emails[:effective_scan_limit]
                report["scan_mode"] = "incremental_recovery"
                report["cursor_recovered"] = True
                report["cursor_recovery_reason"] = (
                    f"cursore fermo: archivio passato da {archivio_precedente} a "
                    f"{report['archive_seen']} messaggi senza selezioni"
                )
    report["scanned"] = len(selected_emails)
    if cursor:
        report["cursor_sort_key"] = str(cursor.get("sort_key") or "")
        report["cursor_email_id"] = str(cursor.get("item_id") or "")
        report["backlog_complete"] = bool(cursor.get("backlog_complete"))
    report["newest_sort_key"] = newest_cursor.get("sort_key", "")
    report["newest_email_id"] = newest_cursor.get("item_id", "")

    def save_cursor_if_safe(*, batch_exhausted: bool) -> None:
        if batch_exhausted:
            return
        next_cursor = dict(cursor or {})
        if not cursor or cursor_tuple(newest_cursor.get("sort_key"), newest_cursor.get("item_id")) >= cursor_tuple(
            cursor.get("sort_key"),
            cursor.get("item_id"),
        ):
            next_cursor.update(newest_cursor)
        if report["scan_mode"] in {"bootstrap", "full_scan"}:
            boundary_items = selected_emails
        else:
            boundary_items = backlog_window
        if boundary_items:
            boundary = _local_email_cursor(boundary_items[-1])
            next_cursor["backlog_sort_key"] = boundary["sort_key"]
            next_cursor["backlog_item_id"] = boundary["item_id"]
            if report["scan_mode"] in {"bootstrap", "full_scan"}:
                next_cursor["backlog_complete"] = len(boundary_items) >= int(report.get("archive_seen") or 0)
            else:
                next_cursor["backlog_complete"] = len(boundary_items) < effective_scan_limit
        else:
            next_cursor["backlog_complete"] = bool(cursor.get("backlog_complete")) or backlog_attempted
        if report["scan_mode"] == "incremental_recovery":
            # Dopo uno sblocco il backlog va riaperto: la finestra riletta non
            # copre necessariamente tutto l'arretrato rimasto indietro.
            next_cursor["backlog_complete"] = False
        next_cursor["archive_seen"] = int(report.get("archive_seen") or 0)
        if impronta and next_cursor.get("backlog_complete"):
            next_cursor["archive_fingerprint"] = impronta
        else:
            next_cursor.pop("archive_fingerprint", None)
        next_cursor["generation"] = "pec_local_acquire_v2"
        try:
            repo.record_local_acquire_cursor(
                next_cursor,
                payload={
                    "tenant_label": tenant_label,
                    "scan_mode": report["scan_mode"],
                    "archive_seen": report["archive_seen"],
                    "scanned": report["scanned"],
                },
                actor="scheduler",
            )
            report["cursor_saved"] = True
        except Exception:
            report["cursor_saved"] = False

    if not selected_emails:
        save_cursor_if_safe(batch_exhausted=False)
        return report
    emails = selected_emails
    relevant = [item for item in emails if email_rilevante_per_presidio_pec(item)]
    report["relevant"] = len(relevant)
    if not relevant:
        save_cursor_if_safe(batch_exhausted=False)
        return report
    known_headers = repo.ids_by_header_message_ids(
        str(getattr(item, "message_id", "") or "").strip() for item in relevant
    )
    presided_ids = repo.presided_email_ids(
        str(getattr(item, "id", "") or "") for item in relevant
    )
    candidates: list[Any] = []
    skipped_presided_items: list[tuple[Any, str, str]] = []
    batch_exhausted = False
    for item in relevant:
        email_id = str(getattr(item, "id", "") or "")
        header = str(getattr(item, "message_id", "") or "").strip()
        if (header and header in known_headers) or (email_id and email_id in presided_ids):
            report["skipped_presided"] += 1
            skipped_presided_items.append(
                (
                    item,
                    known_headers.get(header, ""),
                    "message_id_header" if header and header in known_headers else "email_id",
                )
            )
            continue
        candidates.append(item)
        if len(candidates) >= max(1, int(batch_size or 10)):
            batch_exhausted = True
            break
    run_id = ""
    tracked_items = len(candidates) + len(skipped_presided_items)
    if tracked_items:
        try:
            run = repo.start_local_acquire_run(
                total_emails=tracked_items,
                batch_size=max(1, tracked_items),
                actor="scheduler",
            )
            run_id = str(run.get("id") or "")
        except Exception:
            run_id = ""
    if tracked_items and not run_id:
        # Senza run tracciabile non si ingerisce nulla: con le foreign key attive
        # gli esiti per email non sarebbero registrabili e le stesse PEC
        # verrebbero rilette dal disco a ogni giro del presidio.
        return {**report, "skipped": True, "reason": "registro presidio non disponibile"}
    for item, message_id, reason in skipped_presided_items:
        _record_auto_acquire_item(
            repo,
            run_id,
            email_id=str(getattr(item, "id", "") or ""),
            message_id=message_id,
            subject=str(getattr(item, "oggetto", "") or "")[:240],
            status="already_presided",
            detail={"origin": "auto", "reason": reason},
        )
    if not candidates:
        if run_id:
            try:
                repo.update_local_acquire_run(
                    run_id,
                    cursor_index=tracked_items,
                    total_emails=tracked_items,
                    batch_size=max(1, tracked_items),
                    deltas={},
                    status="completed",
                    payload={
                        "origin": "auto",
                        "tenant_label": tenant_label,
                        "scan_mode": report["scan_mode"],
                        "archive_seen": report["archive_seen"],
                        "scanned": report["scanned"],
                        "skipped_presided": int(report["skipped_presided"]),
                        "cursor": dict(cursor or newest_cursor),
                        "batch_exhausted": batch_exhausted,
                    },
                    actor="scheduler",
                )
            except Exception:
                pass
        save_cursor_if_safe(batch_exhausted=False)
        return report
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
                cursor_index=tracked_items,
                total_emails=tracked_items,
                batch_size=max(1, tracked_items),
                deltas={
                    "acquired": int(report["ingested"]) + int(report["duplicates"]),
                    "duplicates": int(report["duplicates"]),
                    "skipped_missing_mime": int(report["missing_mime"]),
                    "errors": int(report["errors"]),
                },
                status="completed",
                payload={
                    "origin": "auto",
                    "tenant_label": tenant_label,
                    "scan_mode": report["scan_mode"],
                    "archive_seen": report["archive_seen"],
                    "scanned": report["scanned"],
                    "skipped_presided": int(report["skipped_presided"]),
                    "cursor": dict(cursor or newest_cursor),
                    "batch_exhausted": batch_exhausted,
                },
                actor="scheduler",
            )
            if not batch_exhausted:
                save_cursor_if_safe(batch_exhausted=False)
        except Exception:
            pass
    return report

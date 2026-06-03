"""API REST per pipeline PEC audit-grade."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Response, g, jsonify, request

from pct.email_client import GestioneEmailRicevute
from pct.pec_pipeline import PecAuditRepository, ingest_synthetic_dataset, parse_pec_message
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
    return "default"


def _actor() -> str:
    user = g.get("utente_corrente")
    return str(getattr(user, "username", "") or getattr(user, "id", "") or "api")


def _runtime_path(key: str, default: str, *aliases: str, required: bool = True) -> str:
    return tenant_data_path(key, default, *aliases, require_tenant=required)


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
        raw_mime = gestore.leggi_eml_originale(email_obj)
        if not raw_mime:
            return _json_success(
                {
                    "ok": False,
                    "message": "MIME originale non disponibile: esegui la sincronizzazione PEC completa e riprova.",
                    "messaggio": "MIME originale non disponibile: esegui la sincronizzazione PEC completa e riprova.",
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
        deadline = _schedule_deadline_with_local_mime(
            repo,
            message_id=message_id,
            raw_mime=raw_mime,
            actor=_actor(),
        )
        try:
            worker = repo.run_pending_jobs(limit=80, actor=_actor())
        except Exception as exc:
            worker = {"processed": 0, "failed": 1, "jobs": [], "error": str(exc)[:180]}
        message = "MIME PEC acquisito: allegati, controllo qualità e presidio operativo aggiornati."
        return _json_success(
            {
                "ok": True,
                "message": message,
                "messaggio": message,
                "email_id": email_id,
                "pec_message_id": message_id,
                "duplicate": bool(result.get("duplicate")),
                "ingest": result,
                "deadline": deadline,
                "workers": worker,
            }
        )
    except TenantDataPathError:
        return _json_error(403)


def _email_rilevante_per_presidio_pec(email_obj: Any) -> bool:
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
    return bool(
        getattr(email_obj, "e_pst", False)
        or "posta certificata" in text
        or "giustiziacert" in text
        or "ptel.giustizia" in text
        or "deposito telematico" in text
        or "daticert" in text
        or "postacert" in text
    )


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


@pec_pipeline_api.post("/email/acquisisci-locali")
@_richiedi_auth
def pec_acquire_local_emails():
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
        message = (
            f"Presidio PEC eseguito su {acquired} MIME locali"
            f" ({duplicates} già presenti): "
            f"{deadline_report['created']} scadenze create, "
            f"{deadline_report['already_exists']} già presenti, "
            f"{deadline_report['expired']} scadute ignorate, "
            f"{deadline_report['agenda_linked']} collegate all'agenda. "
            f"{queued_repairs} controlli tecnici accodati."
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
                "deadline_report": {**deadline_report, "items": deadline_report["items"][:50]},
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
        report = _repo().run_pending_jobs(limit=int(request.args.get("limit", "200") or 200), actor=_actor())
        return _json_success({"ok": True, "report": report})
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

"""API REST per PEC Control Tower e integrazione Lex."""

from __future__ import annotations

import base64
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Response, g, jsonify, request

from pct.pec_control_tower import PecControlTowerRepository, build_synthetic_pec_eml
from web.services.security_redaction import redacted_json_response
from web.services.tenant_api_auth import api_key_valid_for_request
from web.services.tenant_paths import TenantDataPathError, tenant_data_path


pec_control_tower_api = Blueprint("pec_control_tower_api", __name__, url_prefix="/api")


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
        getattr(g, "auth_tenant_slug", ""),
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
    return tenant_data_path(key, default, *aliases, require_tenant=required)


def _repo() -> PecControlTowerRepository:
    email_db = Path(_runtime_path("EMAIL_CASELLA_DB", "./email/casella.json"))
    paths = getattr(g, "data_paths", {}) or {}
    configured = paths.get("PEC_CONTROL_TOWER_DB")
    db_path = Path(str(configured)) if configured else email_db.parent / "pec_control_tower.sqlite"
    return PecControlTowerRepository(
        db_path,
        tenant_id=_tenant_id(),
        fascicoli_db_path=_runtime_path("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_runtime_path("FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_runtime_path("SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_runtime_path("AGENDA_DB", "./agenda/appuntamenti.json"),
    )


def _json_success(payload: dict[str, Any], status: int = 200):
    return redacted_json_response({"ok": True, **payload}, status)


def _json_error(status: int = 400, message: str = "Operazione PEC Control Tower non completata."):
    return jsonify({"ok": False, "errore": message}), status


def _raw_eml_from_request() -> tuple[bytes, dict[str, Any]]:
    if request.mimetype in {"message/rfc822", "application/octet-stream"}:
        return request.get_data() or b"", {}
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return b"", {}
    if payload.get("eml_base64"):
        return base64.b64decode(str(payload.get("eml_base64") or "")), payload
    if payload.get("eml"):
        return str(payload.get("eml") or "").encode("utf-8"), payload
    if payload.get("demo_label"):
        label = str(payload.get("demo_label") or "cancelleria")
        if label == "mancata_consegna":
            raw = build_synthetic_pec_eml(
                subject="Avviso di mancata consegna PEC",
                body="La notifica verso controparte@example.pec.it non è stata consegnata.",
                sender="postmaster@pec.it",
                headers={"X-Ricevuta": "mancata-consegna", "X-Riferimento-Message-ID": "<demo-outbound@iusentra.test>"},
            )
        else:
            raw = build_synthetic_pec_eml(
                subject="Comunicazione di cancelleria RG 1234/2026 - deposito provvedimento",
                body="Si comunica il deposito di un provvedimento. Verificare eventuali termini.",
                sender="cancelleria@giustiziacert.it",
                attachments={"provvedimento.pdf.txt": "Provvedimento sintetico per test locale."},
            )
        return raw, payload
    return b"", payload


@pec_control_tower_api.post("/pec/ingest")
@_richiedi_auth
def pec_control_ingest():
    try:
        raw, payload = _raw_eml_from_request()
        if not raw:
            return _json_error(400, "MIME PEC mancante.")
        result = _repo().ingest_eml(
            raw,
            account_email=str(payload.get("account_email") or request.headers.get("X-IUSENTRA-PEC-ACCOUNT") or ""),
            folder=str(payload.get("folder") or request.headers.get("X-IUSENTRA-PEC-FOLDER") or "INBOX"),
            actor=_actor(),
        )
        return _json_success({"data": result.get("data"), "duplicate": bool(result.get("duplicate"))}, 201 if not result.get("duplicate") else 200)
    except TenantDataPathError:
        return _json_error(403, "Dati dello studio non disponibili per questa richiesta.")


@pec_control_tower_api.get("/communications")
@_richiedi_auth
def pec_control_communications():
    try:
        rows = _repo().list_communications(
            limit=int(request.args.get("limit", "100") or 100),
            query=request.args.get("q", "").strip(),
            legal_category=request.args.get("legal_category", "").strip(),
        )
        return _json_success({"data": rows, "count": len(rows)})
    except TenantDataPathError:
        return _json_error(403, "Dati dello studio non disponibili per questa richiesta.")


@pec_control_tower_api.get("/communications/<communication_id>")
@_richiedi_auth
def pec_control_communication_detail(communication_id: str):
    try:
        return _json_success({"data": _repo().get_communication(communication_id)})
    except KeyError:
        return _json_error(404, "Comunicazione PEC non trovata.")


@pec_control_tower_api.post("/communications/<communication_id>/classify")
@_richiedi_auth
def pec_control_classify(communication_id: str):
    try:
        communication = _repo().get_communication(communication_id)
        return _json_success({"data": communication})
    except KeyError:
        return _json_error(404, "Comunicazione PEC non trovata.")


@pec_control_tower_api.post("/communications/<communication_id>/confirm")
@_richiedi_auth
def pec_control_confirm_communication(communication_id: str):
    try:
        payload = request.get_json(silent=True) or {}
        status = str(payload.get("status") or "confirmed")
        return _json_success({"data": _repo().confirm_communication(communication_id, actor=_actor(), status=status)})
    except KeyError:
        return _json_error(404, "Comunicazione PEC non trovata.")


@pec_control_tower_api.get("/deadlines")
@_richiedi_auth
def pec_control_deadlines():
    try:
        rows = _repo().list_deadlines(
            status=request.args.get("status", "").strip(),
            limit=int(request.args.get("limit", "100") or 100),
        )
        return _json_success({"data": rows, "count": len(rows)})
    except TenantDataPathError:
        return _json_error(403, "Dati dello studio non disponibili per questa richiesta.")


@pec_control_tower_api.post("/deadlines/<deadline_id>/confirm")
@_richiedi_auth
def pec_control_confirm_deadline(deadline_id: str):
    try:
        payload = request.get_json(silent=True) or {}
        rule = str(payload.get("confirmation_rule") or payload.get("regola") or "").strip()
        if not rule:
            return _json_error(400, "Indica la regola di conferma del termine.")
        row = _repo().confirm_deadline(
            deadline_id,
            actor=_actor(),
            confirmation_rule=rule,
            due_at=str(payload.get("due_at") or payload.get("data_scadenza") or "").strip() or None,
        )
        return _json_success({"data": row})
    except KeyError:
        return _json_error(404, "Scadenza non trovata.")


@pec_control_tower_api.get("/agenda")
@_richiedi_auth
def pec_control_agenda():
    try:
        rows = _repo().list_agenda(limit=int(request.args.get("limit", "100") or 100))
        return _json_success({"data": rows, "count": len(rows)})
    except TenantDataPathError:
        return _json_error(403, "Dati dello studio non disponibili per questa richiesta.")


@pec_control_tower_api.post("/notifications/draft")
@_richiedi_auth
def pec_control_notification_draft():
    payload = request.get_json(silent=True) or {}
    communication_id = str(payload.get("communication_id") or "").strip()
    recipient = str(payload.get("recipient") or payload.get("destinatario") or "").strip()
    if not communication_id or not recipient:
        return _json_error(400, "Indica comunicazione e destinatario.")
    try:
        row = _repo().draft_notification(
            communication_id,
            recipient=recipient,
            title=str(payload.get("title") or payload.get("titolo") or ""),
            draft_text=str(payload.get("draft_text") or payload.get("testo_bozza") or ""),
            actor=_actor(),
        )
        return _json_success({"data": row}, 201)
    except KeyError:
        return _json_error(404, "Comunicazione PEC non trovata.")


@pec_control_tower_api.post("/notifications/<notification_id>/approve")
@_richiedi_auth
def pec_control_notification_approve(notification_id: str):
    try:
        return _json_success({"data": _repo().approve_notification(notification_id, actor=_actor())})
    except KeyError:
        return _json_error(404, "Notifica non trovata.")


@pec_control_tower_api.post("/notifications/<notification_id>/send")
@_richiedi_auth
def pec_control_notification_send(notification_id: str):
    payload = request.get_json(silent=True) or {}
    if not payload.get("manual_send_confirmed"):
        return _json_error(400, "Nessun invio automatico: registra solo un invio PEC gia' eseguito e confermato.")
    try:
        row = _repo().record_manual_send(
            notification_id,
            actor=_actor(),
            sent_at=str(payload.get("sent_at") or ""),
            proof_sha256=str(payload.get("proof_sha256") or ""),
            proof_filename=str(payload.get("proof_filename") or ""),
        )
        return _json_success({"data": row})
    except KeyError:
        return _json_error(404, "Notifica non trovata.")


@pec_control_tower_api.get("/notifications/<notification_id>/proofs")
@_richiedi_auth
def pec_control_notification_proofs(notification_id: str):
    try:
        return _json_success({"data": _repo().get_notification_proofs(notification_id)})
    except KeyError:
        return _json_error(404, "Notifica non trovata.")


@pec_control_tower_api.get("/audit/")
@pec_control_tower_api.get("/audit/<path:matter_id>")
@_richiedi_auth
def pec_control_audit(matter_id: str = ""):
    try:
        rows = _repo().list_audit(matter_id=matter_id, limit=int(request.args.get("limit", "100") or 100))
        return _json_success({"data": rows, "count": len(rows), "chain": _repo().verify_audit_chain()})
    except TenantDataPathError:
        return _json_error(403, "Dati dello studio non disponibili per questa richiesta.")


@pec_control_tower_api.get("/calendar/export.ics")
@_richiedi_auth
def pec_control_calendar_export():
    try:
        ics = _repo().export_ics()
    except TenantDataPathError:
        return _json_error(403, "Dati dello studio non disponibili per questa richiesta.")
    response = Response(ics, mimetype="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="iusentra-pec-control-tower.ics"'
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

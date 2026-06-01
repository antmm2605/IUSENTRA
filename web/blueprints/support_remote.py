from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from pct.notifications import NotificationServiceError
from pct.support_remote import (
    build_advanced_url,
    build_ice_servers,
    build_support_event_story,
    issue_operator_token,
    verify_operator_token,
)
from web.services.support_runtime import (
    audit_support_studio_action,
    audit_support_action,
    authorize_support_http,
    log_support_event,
    notify_support_request_to_superadmins,
    platform_push_status,
    register_platform_push_subscription,
    revoke_platform_push_subscription,
    send_platform_push_test,
    support_operator_identity_or_403,
    support_repository,
    support_session_payload,
    support_studio_identity_or_403,
)
from web.services.support_surface import build_support_console_payload
from web.services.support_surface import save_support_configuration


support_remote = Blueprint("support_remote", __name__)


def superadmin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        support_operator_identity_or_403()
        return fn(*args, **kwargs)

    return wrapper


def _json_error(message: str, status: int):
    return jsonify({"ok": False, "error": message, "message": message}), status


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


SUPPORT_SESSION_STATUSES = {
    "created",
    "waiting_operator",
    "waiting_client",
    "waiting_peer",
    "active",
    "closed",
}


@support_remote.get("/admin/supporto-remoto")
@superadmin_required
def support_console():
    payload = build_support_console_payload(
        selected_public_id=str(request.args.get("sessione") or "").strip(),
        status_filter=str(request.args.get("stato") or "").strip(),
        query=str(request.args.get("q") or "").strip(),
    )
    return render_template("admin/support_console.html", payload=payload)


@support_remote.get("/admin/supporto-remoto/api")
@superadmin_required
def support_console_api():
    return jsonify(
        build_support_console_payload(
            selected_public_id=str(request.args.get("sessione") or "").strip(),
            status_filter=str(request.args.get("stato") or "").strip(),
            query=str(request.args.get("q") or "").strip(),
        )
    )


@support_remote.get("/admin/supporto-remoto/notifiche-dispositivo")
@superadmin_required
def support_push_status():
    try:
        return jsonify(platform_push_status())
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Stato notifiche dispositivo assistenza non disponibile")
        return _json_error("Stato notifiche dispositivo non disponibile.", 500)


@support_remote.post("/admin/supporto-remoto/notifiche-dispositivo/subscribe")
@superadmin_required
def support_push_subscribe():
    try:
        return jsonify(register_platform_push_subscription(_json_payload(), user_agent=request.headers.get("User-Agent", "")))
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Attivazione notifiche dispositivo assistenza non completata")
        return _json_error("Attivazione notifiche dispositivo non completata.", 500)


@support_remote.delete("/admin/supporto-remoto/notifiche-dispositivo/subscribe")
@superadmin_required
def support_push_unsubscribe():
    try:
        return jsonify(revoke_platform_push_subscription(_json_payload()))
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Disattivazione notifiche dispositivo assistenza non completata")
        return _json_error("Disattivazione notifiche dispositivo non completata.", 500)


@support_remote.post("/admin/supporto-remoto/notifiche-dispositivo/test")
@superadmin_required
def support_push_test():
    try:
        return jsonify(send_platform_push_test())
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Test notifiche dispositivo assistenza non completato")
        return _json_error("Notifica di test non completata.", 500)


@support_remote.post("/admin/supporto-remoto/configurazione")
@superadmin_required
def save_support_config():
    try:
        save_support_configuration(request.form.to_dict())
    except Exception as exc:
        flash(f"Configurazione assistenza remota non salvata: {exc}", "danger")
        return redirect(url_for("support_remote.support_console"))
    flash("Configurazione assistenza remota aggiornata.", "success")
    return redirect(url_for("support_remote.support_console"))


@support_remote.post("/admin/supporto-remoto/<public_id>/stato")
@superadmin_required
def change_console_status(public_id: str):
    operator = support_operator_identity_or_403()
    next_status = str(request.form.get("status") or _json_payload().get("status") or "").strip()
    if next_status not in SUPPORT_SESSION_STATUSES:
        message = "Stato assistenza non valido."
        if request.is_json:
            return _json_error(message, 400)
        flash(message, "danger")
        return redirect(url_for("support_remote.support_console", sessione=public_id))
    repo = support_repository()
    if repo.get_session_by_public_id(public_id) is None:
        if request.is_json:
            return _json_error("Sessione assistenza non trovata.", 404)
        flash("Sessione assistenza non trovata.", "danger")
        return redirect(url_for("support_remote.support_console"))
    updated = repo.update_session(public_id, status=next_status) or {}
    log_support_event(
        public_id,
        event_type="status_changed",
        actor_role="operator",
        actor_name=operator["name"],
        payload={"status": next_status},
    )
    audit_support_action(
        "supporto_remoto.cambia_stato",
        public_id=public_id,
        details=f"{operator['name']} ha impostato lo stato assistenza a {next_status}.",
    )
    if request.is_json:
        return jsonify({"ok": True, "session": support_session_payload(updated)})
    flash("Stato assistenza aggiornato.", "success")
    return redirect(url_for("support_remote.support_console", sessione=public_id))


@support_remote.post("/admin/supporto-remoto/<public_id>/cancella")
@superadmin_required
def delete_from_console(public_id: str):
    operator = support_operator_identity_or_403()
    repo = support_repository()
    row = repo.get_session_by_public_id(public_id)
    if row is None:
        if request.is_json:
            return _json_error("Sessione assistenza non trovata.", 404)
        flash("Sessione assistenza non trovata.", "danger")
        return redirect(url_for("support_remote.support_console"))
    deleted = repo.delete_session(public_id)
    audit_support_action(
        "supporto_remoto.cancella_sessione",
        public_id=public_id,
        details=f"{operator['name']} ha cancellato la sessione assistenza {public_id}.",
    )
    if request.is_json:
        return jsonify({"ok": deleted, "deleted": 1 if deleted else 0})
    flash("Sessione assistenza cancellata." if deleted else "Sessione assistenza non cancellata.", "success" if deleted else "warning")
    return redirect(url_for("support_remote.support_console"))


@support_remote.post("/admin/supporto-remoto/prove/cancella")
@superadmin_required
def delete_test_sessions_from_console():
    operator = support_operator_identity_or_403()
    deleted = support_repository().delete_test_sessions()
    audit_support_action(
        "supporto_remoto.cancella_prove",
        details=f"{operator['name']} ha cancellato {deleted} sessioni di prova assistenza remota.",
    )
    if request.is_json:
        return jsonify({"ok": True, "deleted": deleted})
    flash(f"Sessioni di prova cancellate: {deleted}.", "success")
    return redirect(url_for("support_remote.support_console"))


@support_remote.post("/support/api/session")
@superadmin_required
def create_session_api():
    operator = support_operator_identity_or_403()
    payload = request.get_json(silent=True) or request.form.to_dict()
    request_tenant = getattr(g, "tenant", None)
    studio_slug = str(payload.get("studio_slug") or getattr(request_tenant, "slug", "") or "").strip().lower()
    studio_nome = str(payload.get("studio_nome") or getattr(request_tenant, "nome", "") or "").strip()

    repo = support_repository()
    row = repo.create_session(
        {
            "studio_slug": studio_slug,
            "studio_nome": studio_nome,
            "practice_id": str(payload.get("practice_id") or "").strip(),
            "practice_label": str(payload.get("practice_label") or "").strip(),
            "client_id": str(payload.get("client_id") or "").strip(),
            "customer_name": str(payload.get("customer_name") or "").strip(),
            "customer_email": str(payload.get("customer_email") or "").strip(),
            "created_by": operator["name"],
            "assigned_to": str(payload.get("assigned_to") or operator["name"]).strip(),
            "notes": str(payload.get("notes") or "").strip(),
            "status": "created",
        }
    )
    log_support_event(
        row["public_id"],
        event_type="session_created",
        actor_role="operator",
        actor_name=operator["name"],
        payload={
            "customer_name": row["customer_name"],
            "customer_email": row["customer_email"],
            "studio_nome": row["studio_nome"],
            "practice_label": row["practice_label"],
        },
    )
    audit_support_action(
        "supporto_remoto.crea_sessione",
        public_id=row["public_id"],
        details=build_support_event_story(
            "session_created",
            actor_role="operator",
            actor_name=operator["name"],
            payload={
                "customer_name": row["customer_name"],
                "studio_nome": row["studio_nome"],
                "practice_label": row["practice_label"],
            },
        ),
    )
    operator_token = issue_operator_token(row["public_id"], operator["name"], operator["id"])
    operator_url = url_for(
        "support_remote.operator_room",
        public_id=row["public_id"],
        token=operator_token,
        _external=True,
    )
    join_url = url_for("support_remote.customer_room", token=row["client_token"], _external=True)
    return jsonify(
        {
            "ok": True,
            "session": support_session_payload(row),
            "operator_url": operator_url,
            "join_url": join_url,
        }
    )


@support_remote.post("/support/studio/sessione")
def create_studio_session_api():
    requester = support_studio_identity_or_403()
    payload = request.get_json(silent=True) or request.form.to_dict()
    request_tenant = getattr(g, "tenant", None)
    studio_slug = str(requester.get("tenant_slug") or getattr(request_tenant, "slug", "") or "").strip().lower()
    studio_nome = str(requester.get("tenant_name") or getattr(request_tenant, "nome", "") or "").strip()
    customer_name = str(payload.get("customer_name") or requester["name"] or "").strip()
    customer_email = str(payload.get("customer_email") or requester.get("email", "") or "").strip()
    context_label = str(payload.get("practice_label") or payload.get("notes") or payload.get("context_label") or "").strip()

    repo = support_repository()
    row = repo.create_session(
        {
            "studio_slug": studio_slug,
            "studio_nome": studio_nome,
            "practice_id": str(payload.get("practice_id") or "").strip(),
            "practice_label": context_label,
            "client_id": str(payload.get("client_id") or requester["id"] or "").strip(),
            "customer_name": customer_name,
            "customer_email": customer_email,
            "created_by": requester["name"],
            "assigned_to": "SUPERADMIN",
            "notes": str(payload.get("notes") or "Richiesta aperta dallo studio.").strip(),
            "status": "created",
        }
    )
    log_support_event(
        row["public_id"],
        event_type="studio_support_requested",
        actor_role="client",
        actor_name=requester["name"],
        payload={
            "customer_name": row["customer_name"],
            "customer_email": row["customer_email"],
            "studio_nome": row["studio_nome"],
            "practice_label": row["practice_label"],
        },
    )
    audit_support_studio_action(
        "supporto_remoto.richiedi_sessione",
        public_id=row["public_id"],
        details=build_support_event_story(
            "studio_support_requested",
            actor_role="client",
            actor_name=requester["name"],
            payload={
                "studio_nome": row["studio_nome"],
                "practice_label": row["practice_label"],
            },
        ),
    )
    notification_result = notify_support_request_to_superadmins(row)
    join_url = url_for("support_remote.customer_room", token=row["client_token"], _external=True)
    return jsonify(
        {
            "ok": True,
            "customer_entry": True,
            "session": support_session_payload(row),
            "operator_url": "",
            "join_url": join_url,
            "notification": notification_result,
        }
    )


@support_remote.get("/support/join/<token>")
def customer_room(token: str):
    repo = support_repository()
    row = repo.get_session_by_client_token(token)
    if row is None:
        abort(404, description="Link cliente non valido.")
    if row["status"] == "created":
        row = repo.update_session(row["public_id"], status="waiting_operator") or row
    log_support_event(
        row["public_id"],
        event_type="customer_room_opened",
        actor_role="client",
        actor_name=row["customer_name"] or "Cliente",
        payload={"user_agent": request.headers.get("User-Agent", "")},
    )
    bootstrap = {
        "publicId": row["public_id"],
        "role": "client",
        "authToken": row["client_token"],
        "apiPrefix": f"/support/api/{row['public_id']}",
        "wsBase": "/support/ws",
        "localControlBase": str(current_app.config.get("SUPPORT_LOCAL_CONTROL_BASE") or "http://127.0.0.1:27273"),
        "customerName": row["customer_name"] or "",
        "status": row["status"],
        "closed": row["status"] == "closed",
    }
    return render_template(
        "support/customer_room.html",
        bootstrap=bootstrap,
        sessione=support_session_payload(row),
    )


@support_remote.get("/support/operatore/<public_id>")
def operator_room(public_id: str):
    row = support_repository().get_session_by_public_id(public_id)
    if row is None:
        abort(404, description="Sessione assistenza non trovata.")
    provided_token = str(request.args.get("token") or "").strip()
    token_payload = verify_operator_token(public_id, provided_token) if provided_token else None
    if token_payload:
        operator = {
            "id": str(token_payload.get("operator_id") or ""),
            "username": "",
            "name": str(token_payload.get("actor") or "Operatore"),
        }
        operator_token = provided_token
    else:
        if getattr(g, "utente_corrente", None) is None:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        operator = support_operator_identity_or_403()
        operator_token = issue_operator_token(row["public_id"], operator["name"], operator["id"])
    if row["status"] in {"created", "waiting_operator"}:
        row = support_repository().update_session(row["public_id"], status="waiting_client") or row
    log_support_event(
        row["public_id"],
        event_type="operator_room_opened",
        actor_role="operator",
        actor_name=operator["name"],
        payload={"user_agent": request.headers.get("User-Agent", "")},
    )
    bootstrap = {
        "publicId": row["public_id"],
        "role": "operator",
        "authToken": operator_token,
        "apiPrefix": f"/support/api/{row['public_id']}",
        "wsBase": "/support/ws",
        "customerJoinUrl": url_for("support_remote.customer_room", token=row["client_token"], _external=True),
        "customerName": row["customer_name"] or "",
        "advancedConfigured": True,
        "status": row["status"],
        "closed": row["status"] == "closed",
    }
    from web.blueprints.react_shell import _vite_entry

    return render_template(
        "support/operator_room.html",
        react_assets=_vite_entry(request.path),
        bootstrap=bootstrap,
        sessione=support_session_payload(row),
    )


@support_remote.get("/support/api/<public_id>/state")
def session_state_api(public_id: str):
    row, _, _ = authorize_support_http(public_id)
    payload = {
        "ok": True,
        "session": support_session_payload(row),
    }
    include_events = str(request.args.get("events") or "").strip().lower() in {"1", "true", "yes", "si", "sì"}
    if include_events:
        payload["events"] = support_repository().list_events(public_id, limit=80)
    return jsonify(payload)


@support_remote.get("/support/api/<public_id>/events")
@superadmin_required
def session_events_api(public_id: str):
    row = support_repository().get_session_by_public_id(public_id)
    if row is None:
        abort(404, description="Sessione assistenza non trovata.")
    return jsonify(
        {
            "ok": True,
            "session": support_session_payload(row),
            "events": support_repository().list_events(public_id, limit=300),
        }
    )


@support_remote.get("/support/api/<public_id>/webrtc-config")
def webrtc_config_api(public_id: str):
    row, role, _ = authorize_support_http(public_id)
    subject = f"{role}:{row['public_id']}"
    return jsonify(
        {
            "ok": True,
            "rtcConfiguration": {
                "iceServers": build_ice_servers(subject),
                "bundlePolicy": "balanced",
                "iceCandidatePoolSize": 4,
            },
        }
    )


@support_remote.post("/support/api/<public_id>/consent")
def consent_api(public_id: str):
    row, role, actor_name = authorize_support_http(public_id)
    if role != "client":
        abort(403, description="Solo il cliente può impostare i consensi iniziali.")
    updated = support_repository().update_session(
        public_id,
        consent_screen=bool((request.get_json(silent=True) or {}).get("consent_screen")),
        consent_audio=bool((request.get_json(silent=True) or {}).get("consent_audio")),
        consent_chat=bool((request.get_json(silent=True) or {}).get("consent_chat", True)),
    )
    if updated is None:
        abort(404)
    log_support_event(
        public_id,
        event_type="consent_updated",
        actor_role=role,
        actor_name=actor_name,
        payload={
            "consent_screen": updated["consent_screen"],
            "consent_audio": updated["consent_audio"],
            "consent_chat": updated["consent_chat"],
        },
    )
    return jsonify({"ok": True, "session": support_session_payload(updated)})


@support_remote.post("/support/api/<public_id>/start")
def start_api(public_id: str):
    row, role, actor_name = authorize_support_http(public_id)
    if role != "client":
        abort(403, description="Solo il cliente può avviare l'assistenza dopo il consenso.")
    updated = support_repository().update_session(
        public_id,
        status="active",
        started_at=row["started_at"] or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    if updated is None:
        abort(404)
    log_support_event(
        public_id,
        event_type="session_started",
        actor_role=role,
        actor_name=actor_name,
        payload={"started_at": updated["started_at"]},
    )
    return jsonify({"ok": True, "session": support_session_payload(updated)})


@support_remote.post("/support/api/<public_id>/escalation")
def escalation_api(public_id: str):
    row, role, actor_name = authorize_support_http(public_id)
    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action") or "").strip().lower()

    if role == "operator" and action == "request":
        updated = support_repository().update_session(public_id, advanced_control_requested=True)
        if updated is None:
            abort(404)
        log_support_event(public_id, event_type="advanced_control_requested", actor_role=role, actor_name=actor_name)
        audit_support_action(
            "supporto_remoto.richiedi_escalation",
            public_id=public_id,
            details=f"{actor_name} ha richiesto il controllo remoto del PC.",
        )
        return jsonify({"ok": True, "session": support_session_payload(updated)})

    if role == "client" and action == "approve":
        updated = support_repository().update_session(
            public_id,
            consent_advanced_control=True,
            advanced_control_requested=True,
            advanced_control_approved=True,
        )
        if updated is None:
            abort(404)
        log_support_event(public_id, event_type="advanced_control_approved", actor_role=role, actor_name=actor_name)
        return jsonify({"ok": True, "session": support_session_payload(updated), "advanced_url": build_advanced_url(public_id)})

    if role == "client" and action == "reject":
        updated = support_repository().update_session(
            public_id,
            consent_advanced_control=False,
            advanced_control_requested=False,
            advanced_control_approved=False,
        )
        if updated is None:
            abort(404)
        log_support_event(public_id, event_type="advanced_control_rejected", actor_role=role, actor_name=actor_name)
        return jsonify({"ok": True, "session": support_session_payload(updated)})

    if role == "operator" and action == "reset":
        updated = support_repository().update_session(
            public_id,
            consent_advanced_control=False,
            advanced_control_requested=False,
            advanced_control_approved=False,
        )
        if updated is None:
            abort(404)
        log_support_event(public_id, event_type="advanced_control_reset", actor_role=role, actor_name=actor_name)
        return jsonify({"ok": True, "session": support_session_payload(updated)})

    abort(400, description="Azione di escalation non valida.")


@support_remote.post("/support/api/<public_id>/note")
def note_api(public_id: str):
    row, role, actor_name = authorize_support_http(public_id)
    payload = request.get_json(silent=True) or {}
    note = str(payload.get("notes") or "").strip()
    if role != "operator":
        abort(403, description="Solo il SUPERADMIN può aggiornare le note operative.")
    updated = support_repository().update_session(public_id, notes=note)
    if updated is None:
        abort(404)
    log_support_event(public_id, event_type="note_updated", actor_role=role, actor_name=actor_name, payload={"has_notes": bool(note)})
    return jsonify({"ok": True, "session": support_session_payload(updated)})


@support_remote.post("/support/api/<public_id>/close")
def close_api(public_id: str):
    row, role, actor_name = authorize_support_http(public_id)
    payload = request.get_json(silent=True) or {}
    note = str(payload.get("notes") or row.get("notes") or "").strip()
    updated = support_repository().update_session(
        public_id,
        status="closed",
        ended_at=(
            str(payload.get("ended_at") or "").strip()
            or row["ended_at"]
            or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        ),
        notes=note,
    )
    if updated is None:
        abort(404)
    log_support_event(
        public_id,
        event_type="session_closed",
        actor_role=role,
        actor_name=actor_name,
        payload={"has_notes": bool(note)},
    )
    if role == "operator":
        audit_support_action(
            "supporto_remoto.chiudi_sessione",
            public_id=public_id,
            details=f"{actor_name} ha chiuso la sessione di assistenza remota.",
        )
    return jsonify({"ok": True, "session": support_session_payload(updated)})


@support_remote.post("/admin/supporto-remoto/<public_id>/chiudi")
@superadmin_required
def close_from_console(public_id: str):
    operator = support_operator_identity_or_403()
    updated = support_repository().update_session(
        public_id,
        status="closed",
        ended_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    if updated is None:
        flash("Sessione non trovata.", "warning")
        return redirect(url_for("support_remote.support_console"))
    log_support_event(public_id, event_type="session_closed", actor_role="operator", actor_name=operator["name"])
    flash("Sessione di assistenza chiusa.", "success")
    return redirect(url_for("support_remote.support_console", sessione=public_id))

from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from pct.support_remote import (
    build_advanced_url,
    build_ice_servers,
    build_support_event_story,
    issue_operator_token,
)
from web.services.support_runtime import (
    audit_support_studio_action,
    audit_support_action,
    authorize_support_http,
    log_support_event,
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
    operator_url = url_for("support_remote.operator_room", public_id=row["public_id"], _external=True)
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
    join_url = url_for("support_remote.customer_room", token=row["client_token"], _external=True)
    return jsonify(
        {
            "ok": True,
            "customer_entry": True,
            "session": support_session_payload(row),
            "operator_url": "",
            "join_url": join_url,
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
@superadmin_required
def operator_room(public_id: str):
    row = support_repository().get_session_by_public_id(public_id)
    if row is None:
        abort(404, description="Sessione assistenza non trovata.")
    operator = support_operator_identity_or_403()
    if row["status"] == "created":
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
        "authToken": issue_operator_token(row["public_id"], operator["name"], operator["id"]),
        "apiPrefix": f"/support/api/{row['public_id']}",
        "wsBase": "/support/ws",
        "customerJoinUrl": url_for("support_remote.customer_room", token=row["client_token"], _external=True),
        "customerName": row["customer_name"] or "",
        "advancedConfigured": bool(str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE") or "").strip()),
        "status": row["status"],
        "closed": row["status"] == "closed",
    }
    return render_template(
        "support/operator_room.html",
        bootstrap=bootstrap,
        sessione=support_session_payload(row),
    )


@support_remote.get("/support/api/<public_id>/state")
def session_state_api(public_id: str):
    row, _, _ = authorize_support_http(public_id)
    events = support_repository().list_events(public_id, limit=80)
    return jsonify(
        {
            "ok": True,
            "session": support_session_payload(row),
            "events": events,
        }
    )


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
    advanced_template = str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE") or "").strip()

    if role == "operator" and action == "request":
        if not advanced_template:
            abort(
                409,
                description=(
                    "Controllo remoto avanzato non configurato: imposta SUPPORT_ADVANCED_URL_TEMPLATE "
                    "prima di richiedere l'escalation."
                ),
            )
        updated = support_repository().update_session(public_id, advanced_control_requested=True)
        if updated is None:
            abort(404)
        log_support_event(public_id, event_type="advanced_control_requested", actor_role=role, actor_name=actor_name)
        audit_support_action(
            "supporto_remoto.richiedi_escalation",
            public_id=public_id,
            details=f"{actor_name} ha richiesto il controllo remoto avanzato.",
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

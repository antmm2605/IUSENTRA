"""Runtime, autenticazione e signaling per l'assistenza remota."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import abort, current_app, g, request, session

from pct.auth import GestioneUtenti
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.support_remote import (
    build_advanced_url,
    build_ice_servers,
    build_support_event_story,
    support_status_label,
    verify_operator_token,
)
from pct.support_repository import SupportRemoteRepository
from web.extensions import sock
from web.services.support_presence import (
    get_support_peer,
    register_support_peer,
    safe_support_send,
    support_presence,
    unregister_support_peer,
)


def support_repository() -> SupportRemoteRepository:
    cached = current_app.extensions.get("support_remote_repository")
    if isinstance(cached, SupportRemoteRepository):
        return cached
    postgres_dsn = resolve_runtime_postgres_dsn(
        config=current_app.config,
        env_url_keys=(
            "PCT_SUPPORT_POSTGRES_URL",
            "PCT_SUPPORT_POSTGRES_DSN",
        ),
    )
    repo = SupportRemoteRepository(
        str(current_app.config.get("SUPPORT_DB") or ""),
        postgres_dsn=postgres_dsn,
    )
    current_app.extensions["support_remote_repository"] = repo
    return repo


def _global_user_manager() -> GestioneUtenti:
    cached = getattr(g, "_support_global_user_manager", None)
    if isinstance(cached, GestioneUtenti):
        return cached
    manager = GestioneUtenti(
        db_path=str(current_app.config.get("AUTH_DB") or ""),
        audit_path=str(current_app.config.get("AUDIT_DB") or ""),
        secret_key=current_app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    g._support_global_user_manager = manager
    return manager


def support_operator_identity_or_403() -> dict[str, str]:
    utente = getattr(g, "utente_corrente", None)
    if utente is not None and getattr(utente, "is_superadmin", False):
        return {
            "id": str(getattr(utente, "id", "") or ""),
            "username": str(getattr(utente, "username", "") or ""),
            "name": str(
                getattr(utente, "nome_completo", None)
                or getattr(utente, "email", None)
                or getattr(utente, "username", None)
                or "SUPERADMIN"
            ),
        }

    superadmin_user_id = str(session.get("superadmin_user_id") or "").strip()
    if superadmin_user_id:
        manager = _global_user_manager()
        superadmin = manager.get(superadmin_user_id)
        if superadmin is not None and getattr(superadmin, "is_superadmin", False):
            return {
                "id": str(getattr(superadmin, "id", "") or ""),
                "username": str(getattr(superadmin, "username", "") or ""),
                "name": str(
                    getattr(superadmin, "nome_completo", None)
                    or getattr(superadmin, "email", None)
                    or getattr(superadmin, "username", None)
                    or "SUPERADMIN"
                ),
            }

    abort(403, description="Assistenza remota disponibile solo per il SUPERADMIN di piattaforma.")


def audit_support_action(
    action: str,
    *,
    public_id: str = "",
    details: str = "",
    esito: str = "OK",
) -> None:
    try:
        operator = support_operator_identity_or_403()
    except Exception:
        operator = {
            "id": "",
            "username": "sistema",
            "name": "Sistema",
        }

    _global_user_manager().registra_evento(
        azione=action,
        id_utente=operator["id"],
        username=operator["username"],
        risorsa_tipo="supporto_remoto",
        risorsa_id=str(public_id or ""),
        dettagli=details,
        ip=request.remote_addr or "",
        esito=esito,
    )


def support_session_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["status_label"] = support_status_label(payload.get("status", ""))
    payload["presence"] = support_presence(payload.get("public_id", ""))
    payload["advanced_url"] = (
        build_advanced_url(payload.get("public_id", ""))
        if payload.get("advanced_control_approved")
        else ""
    )
    payload["operator_url"] = f"/support/operatore/{payload.get('public_id', '')}"
    payload["join_path"] = f"/support/join/{payload.get('client_token', '')}"
    return payload


def authorize_support_http(public_id: str) -> tuple[dict[str, Any], str, str]:
    repo = support_repository()
    row = repo.get_session_by_public_id(public_id)
    if row is None:
        abort(404, description="Sessione assistenza non trovata.")

    payload = request.get_json(silent=True) or {}
    role = str(request.args.get("role") or payload.get("role") or "").strip().lower()
    token = str(
        request.args.get("token")
        or payload.get("token")
        or request.headers.get("X-Support-Token")
        or ""
    ).strip()

    if role == "client":
        if token and token == row.get("client_token", ""):
            actor_name = str(row.get("customer_name") or "Cliente")
            return row, role, actor_name
        abort(401, description="Token cliente non valido.")

    if role == "operator":
        data = verify_operator_token(public_id, token)
        if data:
            return row, role, str(data.get("actor") or "Operatore")
        operator = support_operator_identity_or_403()
        return row, role, operator["name"]

    abort(401, description="Autorizzazione assistenza remota non valida.")


def log_support_event(
    public_id: str,
    *,
    event_type: str,
    actor_role: str = "",
    actor_name: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    repo = support_repository()
    story = build_support_event_story(
        event_type,
        actor_role=actor_role,
        actor_name=actor_name,
        payload=payload,
    )
    return repo.append_event(
        public_id,
        event_type=event_type,
        actor_role=actor_role,
        actor_name=actor_name,
        story_line=story,
        payload=payload,
    )


def register_support_websocket(app) -> None:
    if app.extensions.get("support_remote_ws_registered"):
        return
    app.extensions["support_remote_ws_registered"] = True

    @sock.route("/support/ws/<public_id>")
    def support_ws(ws, public_id: str):
        repo = support_repository()
        row = repo.get_session_by_public_id(public_id)
        if row is None:
            safe_support_send(ws, {"type": "error", "message": "Sessione assistenza non trovata."})
            return

        role = str(request.args.get("role") or "").strip().lower()
        token = str(request.args.get("token") or "").strip()
        actor_name = ""

        if role == "client":
            if token != row.get("client_token", ""):
                safe_support_send(ws, {"type": "error", "message": "Token cliente non valido."})
                return
            actor_name = str(row.get("customer_name") or "Cliente")
        elif role == "operator":
            data = verify_operator_token(public_id, token)
            if not data:
                safe_support_send(ws, {"type": "error", "message": "Token operatore non valido."})
                return
            actor_name = str(data.get("actor") or "Operatore")
        else:
            safe_support_send(ws, {"type": "error", "message": "Ruolo di collegamento non valido."})
            return

        other_role = "client" if role == "operator" else "operator"
        other_ws = register_support_peer(public_id, role, ws)

        log_support_event(
            public_id,
            event_type="peer_connected",
            actor_role=role,
            actor_name=actor_name,
            payload={"presence": support_presence(public_id)},
        )

        safe_support_send(ws, {"type": "peer_state", "role": other_role, "connected": bool(other_ws)})
        if other_ws:
            safe_support_send(other_ws, {"type": "peer_state", "role": role, "connected": True})

        if support_presence(public_id)["operator"] and support_presence(public_id)["client"]:
            if not row.get("started_at"):
                repo.update_session(
                    public_id,
                    started_at=datetime.utcnow().replace(microsecond=0).isoformat(),
                )
            repo.update_session(public_id, status="active")
            target_ws = ws if role == "operator" else other_ws
            if target_ws:
                safe_support_send(target_ws, {"type": "start_offer"})

        try:
            while True:
                raw = ws.receive()
                if raw is None:
                    break

                try:
                    message = current_app.json.loads(raw)
                except Exception:
                    safe_support_send(ws, {"type": "error", "message": "Payload realtime non valido."})
                    continue

                msg_type = str(message.get("type") or "").strip().lower()
                target_ws = get_support_peer(public_id, other_role)

                if msg_type == "ping":
                    safe_support_send(ws, {"type": "pong"})
                    continue

                if msg_type in {"offer", "answer", "ice", "chat"}:
                    if target_ws:
                        safe_support_send(target_ws, message)
                    continue

                safe_support_send(
                    ws,
                    {"type": "error", "message": f"Messaggio realtime non supportato: {msg_type or 'sconosciuto'}."},
                )
        finally:
            other_ws = unregister_support_peer(public_id, role, ws)
            current_presence = support_presence(public_id)
            if row.get("status") != "closed":
                next_status = "waiting_peer"
                if role == "client" and not current_presence.get("operator"):
                    next_status = "waiting_operator"
                elif role == "operator" and not current_presence.get("client"):
                    next_status = "waiting_client"
                repo.update_session(public_id, status=next_status)

            log_support_event(
                public_id,
                event_type="peer_disconnected",
                actor_role=role,
                actor_name=actor_name,
                payload={"presence": current_presence},
            )

            if other_ws:
                safe_support_send(other_ws, {"type": "peer_state", "role": role, "connected": False})

"""Runtime, autenticazione e signaling per l'assistenza remota."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import abort, current_app, g, request, session

from pct.auth import GestioneUtenti
from pct.notifications import NotificationRepository, NotificationService, NotificationServiceError, PushDispatchSummary
from pct.notifications.web_push import load_web_push_config, web_push_config_diagnostics
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
    new_support_connection_id,
    publish_support_message,
    register_support_peer,
    safe_support_send,
    start_support_relay_listener,
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


def _platform_notification_repository() -> NotificationRepository:
    configured = str(current_app.config.get("NOTIFICATIONS_DB") or "").strip()
    if configured:
        db_path = configured
    else:
        fallback = Path(str(current_app.config.get("NOTIFICHE_LOG") or "./notifiche/log.json"))
        db_path = str(fallback.with_name("notifications.db"))
    postgres_dsn = resolve_runtime_postgres_dsn(
        config=current_app.config,
        env_url_keys=("IUSENTRA_NOTIFICATIONS_DATABASE_URL", "PCT_NOTIFICATIONS_DATABASE_URL"),
    )
    cache_key = f"{db_path}|{postgres_dsn}"
    cache = current_app.extensions.setdefault("support_platform_notification_repositories", {})
    repo = cache.get(cache_key)
    if isinstance(repo, NotificationRepository):
        return repo
    repo = NotificationRepository(db_path, postgres_dsn=postgres_dsn)
    cache[cache_key] = repo
    return repo


def _platform_notification_service() -> NotificationService:
    return NotificationService(
        _platform_notification_repository(),
        web_push_config=load_web_push_config(current_app.config),
    )


PLATFORM_NOTIFICATION_TENANT_ID = "default"


def _platform_notification_context(operator: dict[str, str] | None = None) -> tuple[str, str]:
    identity = operator or support_operator_identity_or_403()
    user_id = str(identity.get("id") or identity.get("username") or "").strip()
    if not user_id:
        raise NotificationServiceError("Utente SUPERADMIN non disponibile per le notifiche.", 403)
    return PLATFORM_NOTIFICATION_TENANT_ID, user_id


def platform_push_status(operator: dict[str, str] | None = None) -> dict[str, Any]:
    """Stato configurazione Web Push per il dispositivo del SUPERADMIN piattaforma."""
    service = _platform_notification_service()
    tenant_id, user_id = _platform_notification_context(operator)
    preferences = service.preferences(tenant_id, user_id)
    subscriptions = service.repository.list_active_subscriptions(tenant_id, user_id)
    diagnostics = web_push_config_diagnostics(service.web_push_config)
    configured = bool(diagnostics.get("configured"))
    if not configured:
        message = "Configura Web Push sul server, poi attiva questo telefono dalla cabina assistenza."
    elif subscriptions:
        message = "Notifiche cellulare attive per il SUPERADMIN."
    else:
        message = "Web Push pronto: attiva questo telefono per ricevere le richieste assistenza."
    return {
        "ok": True,
        "enabled": bool(diagnostics.get("enabled")),
        "configured": configured,
        "diagnostics": diagnostics,
        "publicKey": service.web_push_config.public_key if configured else "",
        "activeSubscriptions": len(subscriptions),
        "subscriptions": [
            {
                "id": item.id,
                "deviceLabel": item.device_label,
                "lastSeenAt": item.last_seen_at,
            }
            for item in subscriptions
        ],
        "preferences": {
            "pushEnabled": preferences.push_enabled,
            "notifyUrgent": preferences.notify_urgent,
            "notifyImportant": preferences.notify_important,
            "notifyNormal": preferences.notify_normal,
        },
        "message": message,
    }


def platform_support_notifications(operator: dict[str, str] | None = None) -> dict[str, Any]:
    service = _platform_notification_service()
    tenant_id, user_id = _platform_notification_context(operator)
    records = [
        record
        for record in service.repository.list_notifications(tenant_id, user_id, limit=50)
        if str(record.type or "") == "support_remote"
    ]
    unread = sum(1 for record in records if not record.read_at)
    return {
        "unread": unread,
        "items": [
            {
                "id": record.id,
                "title": record.title,
                "body": record.body,
                "href": record.href,
                "created_at": record.created_at,
                "read": bool(record.read_at),
            }
            for record in records[:8]
        ],
    }


def _subscription_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("subscription")
    return nested if isinstance(nested, dict) else payload


def register_platform_push_subscription(
    payload: dict[str, Any],
    *,
    user_agent: str = "",
) -> dict[str, Any]:
    operator = support_operator_identity_or_403()
    tenant_id, user_id = _platform_notification_context(operator)
    subscription = _subscription_payload(payload)
    keys = subscription.get("keys") if isinstance(subscription.get("keys"), dict) else {}
    record = _platform_notification_service().register_subscription(
        tenant_id=tenant_id,
        user_id=user_id,
        endpoint=str(subscription.get("endpoint") or ""),
        p256dh=str(keys.get("p256dh") or ""),
        auth=str(keys.get("auth") or ""),
        user_agent=user_agent,
        device_label=str(payload.get("deviceLabel") or payload.get("device_label") or ""),
    )
    return {
        "ok": True,
        "active": True,
        "subscriptionId": record.id,
        "message": "Notifiche assistenza attive su questo dispositivo.",
        "status": platform_push_status(operator),
    }


def revoke_platform_push_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    operator = support_operator_identity_or_403()
    tenant_id, user_id = _platform_notification_context(operator)
    subscription = _subscription_payload(payload)
    removed = _platform_notification_service().revoke_subscription(
        tenant_id=tenant_id,
        user_id=user_id,
        endpoint=str(subscription.get("endpoint") or ""),
        subscription_id=str(subscription.get("id") or subscription.get("subscriptionId") or ""),
    )
    return {
        "ok": True,
        "active": False,
        "revoked": removed,
        "message": "Notifiche assistenza disattivate su questo dispositivo.",
        "status": platform_push_status(operator),
    }


def send_platform_push_test() -> dict[str, Any]:
    operator = support_operator_identity_or_403()
    tenant_id, user_id = _platform_notification_context(operator)
    service = _platform_notification_service()
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _record, _created, summary = service.create_notification(
        tenant_id=tenant_id,
        user_id=user_id,
        type="support_remote",
        priority="urgent",
        title="Prova notifiche assistenza remota",
        body="Prova dispositivo SUPERADMIN per le richieste assistenza.",
        href="/admin/supporto-remoto",
        source_type="support_remote",
        source_id=f"support-push-test:{created_at}",
        dedupe_key=f"support-push-test:{user_id}:{created_at}",
        payload_json={
            "actionLabel": "Apri cabina",
            "createdAt": created_at,
            "studioName": "Studio test IUSENTRA",
            "supportPublicId": "",
        },
    )
    if summary.sent:
        message = "Notifica di test inviata al dispositivo."
    elif not summary.configured:
        message = "Notifica interna creata; Web Push non è ancora configurato sul server."
    elif not summary.attempted:
        message = "Notifica interna creata; nessun dispositivo SUPERADMIN attivo."
    else:
        message = "Notifica interna creata; il dispositivo non ha confermato la ricezione."
    return {
        "ok": True,
        "message": message,
        "pushConfigured": summary.configured,
        "attempted": summary.attempted,
        "sent": summary.sent,
        "disabled": summary.disabled,
        "status": platform_push_status(operator),
    }


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


def _platform_superadmin_users():
    return [
        user
        for user in _global_user_manager().tutti(solo_attivi=True)
        if getattr(user, "is_superadmin", False) and not str(getattr(user, "tenant_slug", "") or "").strip()
    ]


def notify_support_request_to_superadmins(row: dict[str, Any]) -> dict[str, Any]:
    """Crea la notifica piattaforma e tenta il Web Push sui dispositivi del SUPERADMIN."""
    result: dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "push_configured": False,
        "push_attempted": 0,
        "push_sent": 0,
        "push_disabled": 0,
    }
    try:
        service = _platform_notification_service()
        studio_name = str(row.get("studio_nome") or row.get("studio_slug") or "studio non indicato").strip()
        customer_name = str(row.get("customer_name") or "utente studio").strip()
        practice_label = str(row.get("practice_label") or "").strip()
        public_id = str(row.get("public_id") or "").strip()
        href = f"/admin/supporto-remoto?sessione={public_id}" if public_id else "/admin/supporto-remoto"
        body_parts = [f"{studio_name}: richiesta assistenza da {customer_name}."]
        if practice_label:
            body_parts.append(practice_label)
        summary = PushDispatchSummary(configured=service.web_push_config.configured)
        for user in _platform_superadmin_users():
            user_id = str(getattr(user, "id", "") or getattr(user, "username", "") or "").strip()
            if not user_id:
                continue
            _record, created, summary = service.create_notification(
                tenant_id="default",
                user_id=user_id,
                type="support_remote",
                priority="urgent",
                title="Richiesta assistenza remota",
                body=" ".join(body_parts),
                href=href,
                source_type="support_remote",
                source_id=public_id,
                dedupe_key=f"support_remote:{public_id}:superadmin:{user_id}",
                payload_json={
                    "actionLabel": "Apri cabina",
                    "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "studioName": studio_name,
                    "supportPublicId": public_id,
                },
            )
            result["created" if created else "updated"] += 1
            result["push_configured"] = bool(summary.configured)
            result["push_attempted"] += summary.attempted
            result["push_sent"] += summary.sent
            result["push_disabled"] += summary.disabled
    except Exception:
        current_app.logger.exception("Notifica SUPERADMIN assistenza remota non inviata")
        result["error"] = "notifica_superadmin_non_inviata"
    return result


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


def support_studio_identity_or_403() -> dict[str, str]:
    utente = getattr(g, "utente_corrente", None)
    if utente is None:
        abort(403, description="Accesso allo studio richiesto per aprire l'assistenza remota.")

    if (
        bool(getattr(g, "multi_tenant_enabled", False))
        and not getattr(utente, "is_superadmin", False)
        and bool(getattr(g, "tenant_context_missing", False))
    ):
        abort(409, description="Contesto studio non disponibile per aprire l'assistenza remota.")

    tenant = getattr(g, "tenant", None)
    tenant_slug = str(
        getattr(tenant, "slug", "")
        or getattr(utente, "tenant_slug", "")
        or session.get("tenant_slug", "")
        or session.get("auth_tenant_slug", "")
        or ""
    ).strip().lower()
    tenant_name = str(getattr(tenant, "nome", "") or tenant_slug or "").strip()

    if getattr(utente, "is_superadmin", False) and not session.get("superadmin_user_id") and not tenant_slug:
        abort(403, description="Usa la console piattaforma per aprire assistenza come SUPERADMIN.")

    name = str(
        getattr(utente, "nome_completo", None)
        or getattr(utente, "email", None)
        or getattr(utente, "username", None)
        or "Studio"
    ).strip()
    return {
        "id": str(getattr(utente, "id", "") or ""),
        "username": str(getattr(utente, "username", "") or ""),
        "name": name or "Studio",
        "email": str(getattr(utente, "email", "") or ""),
        "tenant_slug": tenant_slug,
        "tenant_name": tenant_name,
    }


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


def audit_support_studio_action(
    action: str,
    *,
    public_id: str = "",
    details: str = "",
    esito: str = "OK",
) -> None:
    try:
        actor = support_studio_identity_or_403()
    except Exception:
        actor = {
            "id": "",
            "username": "studio",
            "name": "Studio",
        }

    manager = getattr(g, "utente_auth_manager", None)
    if manager is None:
        manager = _global_user_manager()
    manager.registra_evento(
        azione=action,
        id_utente=actor["id"],
        username=actor["username"] or actor["name"],
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
        connection_id = new_support_connection_id()
        relay_stop = threading.Event()
        other_ws = register_support_peer(public_id, role, ws)
        relay_thread = start_support_relay_listener(
            public_id,
            role=role,
            ws=ws,
            connection_id=connection_id,
            stop_event=relay_stop,
        )

        log_support_event(
            public_id,
            event_type="peer_connected",
            actor_role=role,
            actor_name=actor_name,
            payload={"presence": support_presence(public_id)},
        )

        current_presence = support_presence(public_id)
        safe_support_send(ws, {"type": "peer_state", "role": other_role, "connected": bool(current_presence.get(other_role))})
        if other_ws:
            safe_support_send(other_ws, {"type": "peer_state", "role": role, "connected": True})
        else:
            publish_support_message(
                public_id,
                target_role=other_role,
                source_role=role,
                source_connection_id=connection_id,
                payload={"type": "peer_state", "role": role, "connected": True},
            )

        if support_presence(public_id)["operator"] and support_presence(public_id)["client"]:
            if not row.get("started_at"):
                repo.update_session(
                    public_id,
                    started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
            repo.update_session(public_id, status="active")
            if role == "operator":
                safe_support_send(ws, {"type": "start_offer"})
            elif other_ws:
                safe_support_send(other_ws, {"type": "start_offer"})
            else:
                publish_support_message(
                    public_id,
                    target_role="operator",
                    source_role=role,
                    source_connection_id=connection_id,
                    payload={"type": "start_offer"},
                )

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

                if msg_type in {"offer", "answer", "ice", "chat", "screen_frame", "remote_control", "remote_control_ack"}:
                    if target_ws:
                        safe_support_send(target_ws, message)
                    else:
                        publish_support_message(
                            public_id,
                            target_role=other_role,
                            source_role=role,
                            source_connection_id=connection_id,
                            payload=message,
                        )
                    continue

                safe_support_send(
                    ws,
                    {"type": "error", "message": f"Messaggio realtime non supportato: {msg_type or 'sconosciuto'}."},
                )
        finally:
            relay_stop.set()
            if relay_thread:
                relay_thread.join(timeout=1.5)
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
            else:
                publish_support_message(
                    public_id,
                    target_role=other_role,
                    source_role=role,
                    source_connection_id=connection_id,
                    payload={"type": "peer_state", "role": role, "connected": False},
                )

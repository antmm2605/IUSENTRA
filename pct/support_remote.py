"""Dominio e helper condivisi per l'assistenza remota cliente."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


SUPPORT_STATUS_LABELS: dict[str, str] = {
    "created": "Creata",
    "waiting_operator": "In attesa operatore",
    "waiting_client": "In attesa cliente",
    "waiting_peer": "In attesa dell'altra parte",
    "active": "Attiva",
    "closed": "Chiusa",
}
DEFAULT_SUPPORT_STUN_URLS: tuple[str, ...] = ("stun:stun.l.google.com:19302",)


def derive_support_repository_db_path(anchor_path: str) -> str:
    anchor = Path(str(anchor_path or "")).resolve()
    if anchor.suffix.lower() == ".json":
        root = anchor.parent.parent
    else:
        root = anchor.parent
    return str((root / "support" / "assistenza_remota.db").resolve())


def generate_support_public_id() -> str:
    return str(uuid4())


def generate_support_client_token() -> str:
    return secrets.token_urlsafe(32)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.secret_key,
        salt="support-room-operator-token",
    )


def issue_operator_token(public_id: str, actor_name: str, operator_id: str = "") -> str:
    return _serializer().dumps(
        {
            "public_id": str(public_id or ""),
            "role": "operator",
            "actor": str(actor_name or "Operatore"),
            "operator_id": str(operator_id or ""),
        }
    )


def verify_operator_token(public_id: str, token: str) -> dict[str, Any] | None:
    if not token:
        return None

    try:
        payload = _serializer().loads(
            token,
            max_age=int(current_app.config.get("SUPPORT_WS_TOKEN_MAX_AGE", 43200)),
        )
    except (BadSignature, SignatureExpired):
        return None

    if str(payload.get("public_id") or "") != str(public_id or ""):
        return None
    if str(payload.get("role") or "") != "operator":
        return None
    return dict(payload)


def normalize_ice_url_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace("\n", ",").split(",")
    else:
        raw_items = list(value or [])
    return [str(item).strip() for item in raw_items if str(item).strip()]


def default_support_stun_urls() -> list[str]:
    return list(DEFAULT_SUPPORT_STUN_URLS)


def build_ice_servers(subject: str) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = []
    stun_urls = normalize_ice_url_list(current_app.config.get("SUPPORT_STUN_URLS", [])) or default_support_stun_urls()
    for stun_url in stun_urls:
        servers.append({"urls": [str(stun_url)]})

    turn_urls = normalize_ice_url_list(current_app.config.get("SUPPORT_TURN_URLS", []))
    shared_secret = str(current_app.config.get("SUPPORT_TURN_SHARED_SECRET", "") or "").strip()
    ttl = int(current_app.config.get("SUPPORT_TURN_TTL_SECONDS", 3600) or 3600)
    if turn_urls and shared_secret:
        expiry = int(time.time()) + ttl
        username = f"{expiry}:{subject}"
        digest = hmac.new(
            shared_secret.encode("utf-8"),
            username.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        credential = base64.b64encode(digest).decode("utf-8")
        servers.append(
            {
                "urls": turn_urls,
                "username": username,
                "credential": credential,
            }
        )
    return servers


def build_advanced_url(public_id: str) -> str:
    template = str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE", "") or "").strip()
    if not template:
        return ""
    return template.format(public_id=public_id)


def support_status_label(status: str) -> str:
    normalized = str(status or "").strip().lower()
    return SUPPORT_STATUS_LABELS.get(normalized, normalized.replace("_", " ").title() or "Sconosciuta")


def safe_json_payload(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)


def parse_json_payload(payload_json: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(str(payload_json or "{}"))
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def build_support_event_story(
    event_type: str,
    *,
    actor_role: str = "",
    actor_name: str = "",
    payload: dict[str, Any] | None = None,
) -> str:
    data = payload or {}
    nome = str(actor_name or actor_role or "Sistema").strip() or "Sistema"
    event = str(event_type or "").strip().lower()

    if event == "session_created":
        studio_nome = str(data.get("studio_nome") or "").strip()
        practice_label = str(data.get("practice_label") or "").strip()
        customer_name = str(data.get("customer_name") or "").strip()
        parts = [f"{nome} ha aperto una nuova sessione di assistenza remota"]
        if customer_name:
            parts.append(f"per {customer_name}")
        if practice_label:
            parts.append(f"sulla pratica {practice_label}")
        elif studio_nome:
            parts.append(f"per lo studio {studio_nome}")
        return " ".join(parts).strip() + "."
    if event == "studio_support_requested":
        studio_nome = str(data.get("studio_nome") or "").strip()
        practice_label = str(data.get("practice_label") or "").strip()
        parts = [f"{nome} ha richiesto assistenza remota dallo studio"]
        if practice_label:
            parts.append(f"per {practice_label}")
        elif studio_nome:
            parts.append(f"{studio_nome}")
        return " ".join(parts).strip() + "."
    if event == "customer_room_opened":
        return f"{nome} ha aperto il link cliente e ha raggiunto la stanza di assistenza."
    if event == "operator_room_opened":
        return f"{nome} ha aperto la stanza operatore dalla cabina piattaforma."
    if event == "peer_connected":
        return f"{nome} si è collegato alla stanza WebRTC."
    if event == "peer_disconnected":
        return f"{nome} si è scollegato dalla stanza WebRTC."
    if event == "consent_updated":
        consensi: list[str] = []
        if data.get("consent_screen"):
            consensi.append("schermo")
        if data.get("consent_audio"):
            consensi.append("audio")
        if data.get("consent_chat"):
            consensi.append("chat")
        if not consensi:
            return f"{nome} ha revocato tutti i consensi iniziali della sessione."
        return f"{nome} ha autorizzato {', '.join(consensi)} per l'assistenza remota."
    if event == "session_started":
        return f"{nome} ha avviato la sessione operativa."
    if event == "advanced_control_requested":
        return f"{nome} ha richiesto l'escalation verso il controllo remoto avanzato."
    if event == "advanced_control_approved":
        return f"{nome} ha approvato il controllo remoto avanzato."
    if event == "advanced_control_rejected":
        return f"{nome} ha rifiutato il controllo remoto avanzato."
    if event == "advanced_control_reset":
        return f"{nome} ha azzerato la richiesta di controllo remoto avanzato."
    if event == "note_updated":
        return f"{nome} ha aggiornato le note finali della sessione."
    if event == "session_closed":
        return f"{nome} ha chiuso la sessione di assistenza remota."
    if event == "webrtc_error":
        detail = str(data.get("detail") or "").strip()
        if detail:
            return f"{nome} ha segnalato un errore WebRTC: {detail}."
        return f"{nome} ha segnalato un errore WebRTC."
    return f"{nome} ha eseguito l'azione {event_type}."

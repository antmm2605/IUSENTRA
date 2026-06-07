"""Bridge JSON React per Portale Cliente e Mini App Cliente."""

from __future__ import annotations

import base64
import hashlib
import hmac
import mimetypes
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, g, request, session
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from zoneinfo import ZoneInfo

from pct.client_portal import (
    ClientPortalError,
    ClientPortalRepository,
    DEFAULT_CLIENT_PORTAL_SETTINGS,
    json_loads,
    utc_now,
)
from pct.postgres_runtime_support import database_config_to_dsn, resolve_runtime_postgres_dsn
from pct.tenant import GestioneTenant
from web.services.feature_flags import is_feature_enabled
from web.services.tenant_paths import tenant_data_path


CLIENT_PORTAL_SESSION_TOKEN = "client_portal_token"
CLIENT_PORTAL_ENV_KEYS = ("IUSENTRA_CLIENT_PORTAL_DATABASE_URL", "CLIENT_PORTAL_DATABASE_URL")
ROME = ZoneInfo("Europe/Rome")
NON_OPERATIONAL_PORTAL_WORDS = ("demo", "sample", "mock")
CLIENT_PORTAL_PUBLIC_ERROR = "Accesso cliente non valido o non più disponibile."


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _invalid_invite_payload() -> dict[str, Any]:
    return {"ok": False, "code": "invalid_invite", "message": CLIENT_PORTAL_PUBLIC_ERROR}


def _is_non_operational_portal_text(*values: Any) -> bool:
    value = " ".join(_text(item).lower() for item in values)
    return any(re.search(rf"\b{re.escape(word)}\b", value) for word in NON_OPERATIONAL_PORTAL_WORDS)


def _core_runtime_func(name: str):
    func = (current_app.extensions.get("core_runtime", {}) or {}).get(name)
    return func if callable(func) else None


def _audit(action: str, resource_type: str = "", resource_id: str = "", details: str = "") -> None:
    audit_func = _core_runtime_func("audit")
    if callable(audit_func):
        audit_func(action, resource_type, resource_id, details)


def _actor_id() -> str:
    user = g.get("utente_corrente")
    return _text(getattr(user, "id", "")) or _text(getattr(user, "username", "")) or "operatore"


def _actor_label() -> str:
    user = g.get("utente_corrente")
    return _text(getattr(user, "nome_completo", "")) or _text(getattr(user, "username", "")) or "Operatore studio"


def _can(permission: str) -> bool:
    user = g.get("utente_corrente")
    return bool(user and getattr(user, "ha_permesso", lambda _permission: False)(permission))


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _token_secret() -> bytes:
    return _text(current_app.secret_key or current_app.config.get("SECRET_KEY") or "iusentra-client-portal").encode("utf-8")


def _tenant_locator() -> str:
    tenant = getattr(g, "tenant", None)
    return (
        _text(getattr(tenant, "slug", ""))
        or _text(getattr(g, "tenant_context_slug", ""))
        or _text(session.get("tenant_slug"))
        or "single-studio"
    )


def make_invite_token(tenant_locator: str) -> str:
    payload = _b64_encode(
        f"v=1;t={tenant_locator};iat={utc_now()}".encode("utf-8")
    )
    nonce = secrets.token_urlsafe(24)
    signed = f"{payload}.{nonce}".encode("utf-8")
    signature = _b64_encode(hmac.new(_token_secret(), signed, hashlib.sha256).digest())
    return f"cp1.{payload}.{signature}.{nonce}"


def tenant_locator_from_token(token: str) -> str:
    parts = _text(token).split(".")
    if len(parts) != 4 or parts[0] != "cp1":
        raise ClientPortalError("Invito non valido.")
    payload, signature, nonce = parts[1], parts[2], parts[3]
    expected = _b64_encode(hmac.new(_token_secret(), f"{payload}.{nonce}".encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ClientPortalError("Invito non valido.")
    decoded = _b64_decode(payload).decode("utf-8", errors="strict")
    data = dict(item.split("=", 1) for item in decoded.split(";") if "=" in item)
    tenant = _text(data.get("t"))
    if not tenant:
        raise ClientPortalError("Invito non valido.")
    return tenant


def _portal_root_from_clienti_path(clienti_path: str | Path) -> Path:
    anchor = Path(clienti_path).expanduser().resolve()
    parent = anchor.parent
    root = parent.parent if parent.name.lower() == "clienti" else parent
    return root / "client_portal"


def _repository_from_anchor(clienti_path: str | Path, *, postgres_dsn: str = "") -> ClientPortalRepository:
    root = _portal_root_from_clienti_path(clienti_path)
    root.mkdir(parents=True, exist_ok=True)
    return ClientPortalRepository(root / "client_portal.db", postgres_dsn=postgres_dsn)


def repository_for_current_request() -> ClientPortalRepository:
    clienti_path = tenant_data_path(
        "CLIENTI_DB",
        str(current_app.config.get("CLIENTI_DB") or "./data/clienti/anagrafica.json"),
        require_tenant=True,
    )
    dsn = resolve_runtime_postgres_dsn(config=current_app.config, env_url_keys=CLIENT_PORTAL_ENV_KEYS)
    return _repository_from_anchor(clienti_path, postgres_dsn=dsn)


def repository_for_token(token: str) -> ClientPortalRepository:
    locator = tenant_locator_from_token(token)
    if locator == "single-studio" or not current_app.config.get("MULTI_TENANT"):
        dsn = resolve_runtime_postgres_dsn(config=current_app.config, env_url_keys=CLIENT_PORTAL_ENV_KEYS)
        return _repository_from_anchor(
            str(current_app.config.get("CLIENTI_DB") or "./data/clienti/anagrafica.json"),
            postgres_dsn=dsn,
        )

    registry = _text(current_app.config.get("TENANTS_REGISTRY"))
    if not registry:
        raise ClientPortalError("Studio non disponibile per l'invito.")
    tenant_manager = GestioneTenant(registry_path=registry)
    studio = tenant_manager.get(locator)
    if studio is None:
        raise ClientPortalError("Studio non disponibile per l'invito.")
    paths = tenant_manager.percorsi_dati(locator, reconcile_aliases=False)
    dsn = (
        resolve_runtime_postgres_dsn(config=current_app.config, env_url_keys=CLIENT_PORTAL_ENV_KEYS)
        or database_config_to_dsn(studio.database)
    )
    return _repository_from_anchor(paths["CLIENTI_DB"], postgres_dsn=dsn)


def _current_tenant_id() -> str:
    return _tenant_locator()


def _clienti_manager():
    getter = _core_runtime_func("get_clienti")
    return getter() if callable(getter) else None


def _fascicoli_manager():
    getter = _core_runtime_func("get_fascicoli")
    return getter() if callable(getter) else None


def _cliente_by_id(client_id: str):
    manager = _clienti_manager()
    return manager.get(client_id) if manager is not None and client_id else None


def _fascicolo_by_id(fascicolo_id: str):
    manager = _fascicoli_manager()
    return manager.get(fascicolo_id) if manager is not None and fascicolo_id else None


def _is_non_operational_fascicolo(fascicolo: Any) -> bool:
    return _is_non_operational_portal_text(
        getattr(fascicolo, "titolo", ""),
        getattr(fascicolo, "numero", ""),
        getattr(fascicolo, "nome_cliente", ""),
        getattr(fascicolo, "controparte", ""),
    )


def _cliente_options() -> list[dict[str, str]]:
    manager = _clienti_manager()
    if manager is None:
        return []
    result = []
    for cliente in manager.tutti():
        result.append(
            {
                "id": _text(getattr(cliente, "id", "")),
                "label": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
                "email": _text(getattr(getattr(cliente, "recapiti", None), "email", "")),
                "phone": _text(getattr(getattr(cliente, "recapiti", None), "cellulare", "")) or _text(getattr(getattr(cliente, "recapiti", None), "telefono", "")),
                "fiscalCode": _text(getattr(cliente, "identificativo_fiscale", "")),
            }
        )
    return result


def _fascicolo_options() -> list[dict[str, str]]:
    manager = _fascicoli_manager()
    if manager is None:
        return []
    result = []
    for fascicolo in manager.tutti(archiviati=True):
        if _is_non_operational_fascicolo(fascicolo):
            continue
        stato = getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", ""))
        result.append(
            {
                "id": _text(getattr(fascicolo, "id", "")),
                "label": _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "numero", "")) or "Fascicolo",
                "number": _text(getattr(fascicolo, "numero", "")),
                "clientId": _text(getattr(fascicolo, "id_cliente", "")),
                "clientName": _text(getattr(fascicolo, "nome_cliente", "")),
                "status": _text(stato).lower(),
                "openedAt": _text(getattr(fascicolo, "data_apertura", "")),
            }
        )
    return result


def _profile_from_cliente(cliente: Any) -> dict[str, str]:
    recapiti = getattr(cliente, "recapiti", None)
    documento = getattr(cliente, "documento", None)
    return {
        "client_id": _text(getattr(cliente, "id", "")),
        "display_name": _text(getattr(cliente, "nome_completo", "")) or "Cliente",
        "email": _text(getattr(recapiti, "email", "")),
        "phone": _text(getattr(recapiti, "cellulare", "")) or _text(getattr(recapiti, "telefono", "")),
        "fiscal_code": _text(getattr(cliente, "identificativo_fiscale", "")),
        "identity_expires_at": _text(getattr(documento, "data_scadenza", "")),
    }


def _matter_from_fascicolo(fascicolo: Any) -> dict[str, Any]:
    stato = getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", ""))
    return {
        "client_id": _text(getattr(fascicolo, "id_cliente", "")),
        "fascicolo_id": _text(getattr(fascicolo, "id", "")),
        "title": _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "numero", "")) or "Pratica",
        "status": _text(stato).lower() or "attiva",
        "opened_at": _text(getattr(fascicolo, "data_apertura", "")),
        "data": {
            "number": _text(getattr(fascicolo, "numero", "")),
            "court": _text(getattr(fascicolo, "tribunale", "")),
            "registryNumber": _text(getattr(fascicolo, "numero_rg", "")),
            "year": _text(getattr(fascicolo, "anno_rg", "")),
            "counterparty": _text(getattr(fascicolo, "controparte", "")),
        },
    }


def _iso_to_rome_label(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local = parsed.astimezone(ROME)
        return local.strftime("%d/%m/%Y %H:%M")
    except Exception:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            y, m, d = text.split("-")
            return f"{d}/{m}/{y}"
        return text


def _public_row(row: dict[str, Any], *, include_private: bool = False) -> dict[str, Any]:
    cleaned = dict(row or {})
    for key in ("token_hash", "stored_name"):
        cleaned.pop(key, None)
    for key, value in list(cleaned.items()):
        if key.endswith("_json"):
            cleaned[key[:-5]] = json_loads(value, {} if value == "{}" else [])
            cleaned.pop(key, None)
    for key in ("created_at", "updated_at", "uploaded_at", "accepted_at", "expires_at", "starts_at", "ends_at", "submitted_at", "completed_at", "read_at"):
        if key in cleaned:
            cleaned[f"{key}_label"] = _iso_to_rome_label(cleaned.get(key))
    if not include_private:
        cleaned.pop("created_by", None)
        cleaned.pop("updated_by", None)
    return cleaned


def _public_rows(rows: list[dict[str, Any]], *, include_private: bool = False) -> list[dict[str, Any]]:
    return [_public_row(row, include_private=include_private) for row in rows]


def _features_payload() -> dict[str, bool]:
    keys = (
        "routes.appV2.clientPortal.enabled",
        "routes.appV2.clientPortal.notifications",
        "routes.appV2.clientPortal.webPush",
        "routes.appV2.clientPortal.videoCalls",
        "routes.appV2.clientPortal.signatures",
    )
    return {key: is_feature_enabled(key, current_app.config) for key in keys}


def _shape_dashboard(snapshot: dict[str, Any]) -> dict[str, Any]:
    profiles = {_text(row.get("client_id")): _public_row(row, include_private=True) for row in snapshot.get("profiles", [])}
    matters = []
    for matter in snapshot.get("matters", []):
        shaped = _public_row(matter, include_private=True)
        shaped["client"] = profiles.get(_text(matter.get("client_id")), {})
        matters.append(shaped)
    return {
        "summary": snapshot.get("summary", {}),
        "clients": list(profiles.values()),
        "matters": matters,
        "invites": _public_rows(snapshot.get("invites", []), include_private=True),
        "documentRequests": _public_rows(snapshot.get("documentRequests", []), include_private=True),
        "documents": _public_rows(snapshot.get("documents", []), include_private=True),
        "signatures": _public_rows(snapshot.get("signatures", []), include_private=True),
        "messages": _public_rows(snapshot.get("messages", []), include_private=True),
        "appointments": _public_rows(snapshot.get("appointments", []), include_private=True),
        "notifications": _public_rows(snapshot.get("notifications", []), include_private=True),
        "questionnaires": _public_rows(snapshot.get("questionnaires", []), include_private=True),
        "surveys": _public_rows(snapshot.get("surveys", []), include_private=True),
        "evidencePacks": _public_rows(snapshot.get("evidencePacks", []), include_private=True),
        "settings": snapshot.get("settings") or DEFAULT_CLIENT_PORTAL_SETTINGS,
    }


def build_studio_dashboard_payload() -> dict[str, Any]:
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    snapshot = _shape_dashboard(repo.dashboard_snapshot(tenant_id))
    return {
        "ok": True,
        "surface": "studio",
        "title": "Portale Clienti",
        "featureFlags": _features_payload(),
        "canWrite": _can("clienti.scrivi"),
        "clientOptions": _cliente_options(),
        "matterOptions": _fascicolo_options(),
        "actions": {
            "createInvite": "/api/v1/ui/client-portal/studio/invites",
            "sendMessage": "/api/v1/ui/client-portal/studio/messages",
            "documentRequest": "/api/v1/ui/client-portal/studio/document-requests",
            "signatureRequest": "/api/v1/ui/client-portal/studio/signature-requests",
            "appointment": "/api/v1/ui/client-portal/studio/appointments",
            "settings": "/api/v1/ui/client-portal/studio/settings",
        },
        **snapshot,
    }


def create_invite_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.scrivi richiesto."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    client_id = _text(payload.get("clientId"))
    fascicolo_id = _text(payload.get("matterId") or payload.get("fascicoloId"))
    cliente = _cliente_by_id(client_id)
    fascicolo = _fascicolo_by_id(fascicolo_id)
    if cliente is None:
        return {"ok": False, "code": "validation_error", "message": "Cliente non trovato."}
    if fascicolo is None:
        return {"ok": False, "code": "validation_error", "message": "Fascicolo non trovato."}
    if _is_non_operational_fascicolo(fascicolo):
        return {"ok": False, "code": "validation_error", "message": "Il fascicolo selezionato non è disponibile nel Portale Cliente."}
    if _text(getattr(fascicolo, "id_cliente", "")) and _text(getattr(fascicolo, "id_cliente", "")) != client_id:
        return {"ok": False, "code": "validation_error", "message": "Il fascicolo selezionato non è collegato al cliente."}
    profile = repo.ensure_profile(tenant_id, **_profile_from_cliente(cliente))
    matter_payload = _matter_from_fascicolo(fascicolo)
    matter_payload["client_id"] = client_id
    matter = repo.ensure_matter(tenant_id, **matter_payload)
    token = make_invite_token(_tenant_locator())
    created = repo.create_invite(
        tenant_id,
        client_id=client_id,
        matter_id=matter["id"],
        expires_days=int(payload.get("expiresDays") or repo.get_settings(tenant_id).get("inviteExpiresDays") or 14),
        channel=_text(payload.get("channel")) or "email",
        notes=_text(payload.get("message")),
        actor_id=_actor_id(),
        metadata={"matterTitle": matter.get("title"), "clientName": profile.get("display_name")},
        token_value=token,
    )
    invite_url = f"/portale-cliente/invito/{created['token']}"
    repo.add_notification(
        tenant_id,
        client_id=client_id,
        matter_id=matter["id"],
        title="Invito al portale disponibile",
        body="Lo studio ha predisposto l'accesso alla pratica.",
        kind="invito",
        href="/portale-cliente",
    )
    _audit("client_portal.invite.create", "portale_cliente", created["invite"]["id"], f"{_actor_label()} ha creato un invito cliente.")
    return {"ok": True, "message": "Invito creato.", "invite": _public_row(created["invite"], include_private=True), "inviteUrl": invite_url, "dashboard": build_studio_dashboard_payload()}


def revoke_invite(invite_id: str) -> dict[str, Any]:
    if not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.scrivi richiesto."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    row = repo.revoke_invite(tenant_id, invite_id, actor_id=_actor_id())
    _audit("client_portal.invite.revoke", "portale_cliente", invite_id, f"{_actor_label()} ha revocato un invito cliente.")
    return {"ok": True, "message": "Invito revocato.", "invite": _public_row(row, include_private=True), "dashboard": build_studio_dashboard_payload()}


def update_settings_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("admin.configura"):
        return {"ok": False, "code": "forbidden", "message": "Permesso admin.configura richiesto."}
    allowed: dict[str, Any] = {}
    for key in ("inviteExpiresDays", "maxUploadMb"):
        if key in payload:
            allowed[key] = int(payload.get(key) or 0)
    for key in ("notifications", "videoCalls", "signatures"):
        if isinstance(payload.get(key), dict):
            allowed[key] = dict(payload[key])
    repo = repository_for_current_request()
    settings = repo.update_settings(_current_tenant_id(), allowed, actor_id=_actor_id())
    _audit("client_portal.settings.update", "portale_cliente", _current_tenant_id(), "Impostazioni Portale Cliente aggiornate.")
    return {"ok": True, "message": "Impostazioni aggiornate.", "settings": settings}


def studio_add_message(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("messaggi.scrivi") and not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso messaggi.scrivi richiesto."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    matter_id = _text(payload.get("matterId"))
    matter = repo.get_matter(tenant_id, matter_id)
    if not matter:
        return {"ok": False, "code": "validation_error", "message": "Pratica portale non trovata."}
    message = repo.add_message(tenant_id, matter_id=matter_id, sender_type="studio", sender_id=_actor_id(), body=_text(payload.get("body")))
    repo.add_notification(tenant_id, client_id=_text(matter.get("client_id")), matter_id=matter_id, title="Nuovo messaggio dallo studio", body="Apri la chat della pratica.", kind="messaggio", href="/portale-cliente?tab=chat")
    return {"ok": True, "message": "Messaggio inviato.", "item": _public_row(message, include_private=True), "dashboard": build_studio_dashboard_payload()}


def studio_add_document_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.scrivi richiesto."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    matter_id = _text(payload.get("matterId"))
    matter = repo.get_matter(tenant_id, matter_id)
    if not matter:
        return {"ok": False, "code": "validation_error", "message": "Pratica portale non trovata."}
    item = repo.add_document_request(
        tenant_id,
        matter_id=matter_id,
        title=_text(payload.get("title")) or "Documento richiesto",
        description=_text(payload.get("description")),
        required=bool(payload.get("required", True)),
        due_at=_text(payload.get("dueAt")),
        accepted_types=[_text(item) for item in payload.get("acceptedTypes") or [] if _text(item)],
    )
    repo.add_notification(tenant_id, client_id=_text(matter.get("client_id")), matter_id=matter_id, title="Documento richiesto", body=_text(item.get("title")), kind="documento", href="/portale-cliente?tab=documenti")
    return {"ok": True, "message": "Richiesta documento aggiunta.", "item": _public_row(item, include_private=True), "dashboard": build_studio_dashboard_payload()}


def studio_add_signature_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not is_feature_enabled("routes.appV2.clientPortal.signatures", current_app.config):
        return {"ok": False, "code": "feature_disabled", "message": "Firma cliente non attiva per questo studio."}
    if not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.scrivi richiesto."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    matter_id = _text(payload.get("matterId"))
    matter = repo.get_matter(tenant_id, matter_id)
    if not matter:
        return {"ok": False, "code": "validation_error", "message": "Pratica portale non trovata."}
    item = repo.add_signature_request(
        tenant_id,
        matter_id=matter_id,
        title=_text(payload.get("title")) or "Documento da firmare",
        description=_text(payload.get("description")),
        document_id=_text(payload.get("documentId")),
        due_at=_text(payload.get("dueAt")),
    )
    repo.add_notification(tenant_id, client_id=_text(matter.get("client_id")), matter_id=matter_id, title="Firma richiesta", body=_text(item.get("title")), kind="firma", href="/portale-cliente?tab=firme")
    return {"ok": True, "message": "Richiesta firma aggiunta.", "item": _public_row(item, include_private=True), "dashboard": build_studio_dashboard_payload()}


def studio_add_appointment(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("agenda.scrivi") and not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso agenda.scrivi richiesto."}
    repo = repository_for_current_request()
    tenant_id = _current_tenant_id()
    matter_id = _text(payload.get("matterId"))
    matter = repo.get_matter(tenant_id, matter_id)
    if not matter:
        return {"ok": False, "code": "validation_error", "message": "Pratica portale non trovata."}
    video_url = _text(payload.get("videoUrl")) if is_feature_enabled("routes.appV2.clientPortal.videoCalls", current_app.config) else ""
    item = repo.add_appointment(
        tenant_id,
        matter_id=matter_id,
        title=_text(payload.get("title")) or "Appuntamento con lo studio",
        starts_at=_text(payload.get("startsAt")),
        ends_at=_text(payload.get("endsAt")),
        location=_text(payload.get("location")),
        video_url=video_url,
    )
    repo.add_notification(tenant_id, client_id=_text(matter.get("client_id")), matter_id=matter_id, title="Appuntamento proposto", body=_iso_to_rome_label(item.get("starts_at")), kind="appuntamento", href="/portale-cliente?tab=appuntamenti")
    return {"ok": True, "message": "Appuntamento proposto.", "item": _public_row(item, include_private=True), "dashboard": build_studio_dashboard_payload()}


def studio_create_evidence_pack(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("clienti.scrivi"):
        return {"ok": False, "code": "forbidden", "message": "Permesso clienti.scrivi richiesto."}
    repo = repository_for_current_request()
    item = repo.create_evidence_pack(_current_tenant_id(), matter_id=_text(payload.get("matterId")), actor_id=_actor_id())
    return {"ok": True, "message": "Pacchetto finale preparato.", "item": _public_row(item, include_private=True), "dashboard": build_studio_dashboard_payload()}


def export_conversation(matter_id: str, *, token: str = "") -> dict[str, Any]:
    if token:
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        if _text(invite.get("matter_id")) != matter_id:
            return {"ok": False, "code": "forbidden", "message": "Conversazione non disponibile."}
    else:
        if not _can("clienti.leggi"):
            return {"ok": False, "code": "forbidden", "message": "Permesso clienti.leggi richiesto."}
        repo = repository_for_current_request()
        tenant_id = _current_tenant_id()
    snapshot = repo.matter_snapshot(tenant_id, matter_id)
    messages = _public_rows(snapshot.get("messages", []), include_private=True)
    return {"ok": True, "matter": _public_row(snapshot.get("matter", {}), include_private=True), "messages": messages, "generatedAt": _iso_to_rome_label(utc_now())}


def _parse_datetime(value: str) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _invite_valid(invite: dict[str, Any], *, allow_accepted: bool = True) -> tuple[bool, str]:
    if not invite:
        return False, "Invito non valido."
    if _text(invite.get("revoked_at")) or _text(invite.get("status")) == "revocato":
        return False, "Invito revocato."
    status = _text(invite.get("status"))
    if status not in {"attivo", "accettato"} or (status == "accettato" and not allow_accepted):
        return False, "Invito già utilizzato."
    expires = _parse_datetime(_text(invite.get("expires_at")))
    if expires and expires < datetime.now(timezone.utc):
        return False, "Invito scaduto."
    return True, ""


def _invite_and_repo(token: str) -> tuple[dict[str, Any], ClientPortalRepository]:
    repo = repository_for_token(token)
    invite = repo.find_invite_by_token(token) or {}
    ok, message = _invite_valid(invite)
    if not ok:
        raise ClientPortalError(message)
    return invite, repo


def invite_preview_payload(token: str) -> dict[str, Any]:
    try:
        invite, repo = _invite_and_repo(token)
        snapshot = repo.client_snapshot_by_invite(invite)
        return {
            "ok": True,
            "surface": "invite",
            "invite": _public_row(invite),
            "client": _public_row(snapshot.get("profile", {})),
            "matter": _public_row(snapshot.get("matter", {})),
            "featureFlags": _features_payload(),
        }
    except ClientPortalError:
        return _invalid_invite_payload()


def accept_invite_token(token: str) -> dict[str, Any]:
    try:
        invite, repo = _invite_and_repo(token)
        accepted = repo.accept_invite(_text(invite.get("id")), actor_ip=_text(request.remote_addr))
        session[CLIENT_PORTAL_SESSION_TOKEN] = token
        return {"ok": True, "message": "Accesso cliente attivato.", "dashboard": client_dashboard_payload(token=token), "invite": _public_row(accepted)}
    except ClientPortalError:
        return _invalid_invite_payload()


def _current_client_token(explicit: str = "") -> str:
    return _text(explicit) or _text(request.headers.get("X-Client-Portal-Token")) or _text(session.get(CLIENT_PORTAL_SESSION_TOKEN))


def client_dashboard_payload(*, token: str = "") -> dict[str, Any]:
    resolved = _current_client_token(token)
    if not resolved:
        return {"ok": False, "code": "unauthorized", "message": "Accesso cliente richiesto."}
    try:
        invite, repo = _invite_and_repo(resolved)
        snapshot = repo.client_snapshot_by_invite(invite)
        matter_id = _text(invite.get("matter_id"))
        activity_count = (
            len(snapshot.get("documentRequests") or [])
            + len([item for item in snapshot.get("signatures") or [] if _text(item.get("status")) != "firmato"])
            + len([item for item in snapshot.get("consents") or [] if not int(item.get("accepted") or 0)])
            + len([item for item in snapshot.get("questionnaires") or [] if _text(item.get("status")) == "aperto"])
        )
        return {
            "ok": True,
            "surface": "client",
            "token": resolved,
            "featureFlags": _features_payload(),
            "activityCenter": {
                "openItems": activity_count,
                "nextAction": _text((snapshot.get("matter") or {}).get("next_action")) or "Controlla documenti, privacy e messaggi.",
            },
            "invite": _public_row(invite),
            "client": _public_row(snapshot.get("profile", {})),
            "matter": _public_row(snapshot.get("matter", {})),
            "steps": _public_rows(snapshot.get("steps", [])),
            "documentRequests": _public_rows(snapshot.get("documentRequests", [])),
            "documents": _public_rows(snapshot.get("documents", [])),
            "signatures": _public_rows(snapshot.get("signatures", [])),
            "consents": _public_rows(snapshot.get("consents", [])),
            "messages": _public_rows(snapshot.get("messages", [])),
            "appointments": _public_rows(snapshot.get("appointments", [])),
            "notifications": _public_rows(snapshot.get("notifications", [])),
            "questionnaires": _public_rows(snapshot.get("questionnaires", [])),
            "surveys": _public_rows(snapshot.get("surveys", [])),
            "evidencePacks": _public_rows(snapshot.get("evidencePacks", [])),
            "settings": snapshot.get("settings") or DEFAULT_CLIENT_PORTAL_SETTINGS,
            "actions": {
                "profile": "/api/v1/ui/client-portal/public/profile",
                "consent": "/api/v1/ui/client-portal/public/consents",
                "message": "/api/v1/ui/client-portal/public/messages",
                "upload": "/api/v1/ui/client-portal/public/documents",
                "signature": "/api/v1/ui/client-portal/public/signatures",
                "appointment": "/api/v1/ui/client-portal/public/appointments",
                "notification": "/api/v1/ui/client-portal/public/notifications",
                "questionnaire": "/api/v1/ui/client-portal/public/questionnaires",
                "survey": "/api/v1/ui/client-portal/public/surveys",
                "preferences": "/api/v1/ui/client-portal/public/preferences",
                "conversationExport": f"/api/v1/ui/client-portal/public/conversation-export?matterId={matter_id}",
            },
        }
    except ClientPortalError:
        return _invalid_invite_payload()


def client_update_profile(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        profile = repo.update_profile_fields(_text(invite.get("tenant_id")), client_id=_text(invite.get("client_id")), fields={
            "display_name": _text(payload.get("displayName")),
            "email": _text(payload.get("email")),
            "phone": _text(payload.get("phone")),
            "fiscal_code": _text(payload.get("fiscalCode")),
            "identity_expires_at": _text(payload.get("identityExpiresAt")),
        })
        return {"ok": True, "message": "Anagrafica aggiornata.", "client": _public_row(profile), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_update_preferences(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        profile = repo.update_preferences(_text(invite.get("tenant_id")), client_id=_text(invite.get("client_id")), preferences=dict(payload.get("preferences") or payload))
        return {"ok": True, "message": "Preferenze aggiornate.", "client": _public_row(profile), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_set_consent(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        consent = repo.set_consent(
            _text(invite.get("tenant_id")),
            client_id=_text(invite.get("client_id")),
            matter_id=_text(invite.get("matter_id")),
            consent_key=_text(payload.get("key")) or "privacy_portale_cliente",
            version=_text(payload.get("version")) or "1",
            accepted=bool(payload.get("accepted")),
            payload={"source": "portale_cliente"},
        )
        return {"ok": True, "message": "Consenso registrato.", "item": _public_row(consent), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_send_message(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        message = repo.add_message(
            _text(invite.get("tenant_id")),
            matter_id=_text(invite.get("matter_id")),
            sender_type="cliente",
            sender_id=_text(invite.get("client_id")),
            body=_text(payload.get("body")),
        )
        return {"ok": True, "message": "Messaggio inviato.", "item": _public_row(message), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def _safe_upload_name(filename: str) -> str:
    cleaned = secure_filename(filename or "")
    return cleaned or "documento_cliente"


def _resolved_upload_child(root: Path, *parts: str) -> Path:
    base = root.expanduser().resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ClientPortalError("Percorso documento non valido.") from exc
    return target


def client_upload_document(file: FileStorage, *, request_id: str = "") -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        tenant_id = _text(invite.get("tenant_id"))
        settings = repo.get_settings(tenant_id)
        allowed = set(settings.get("allowedUploadTypes") or DEFAULT_CLIENT_PORTAL_SETTINGS["allowedUploadTypes"])
        max_bytes = int(settings.get("maxUploadMb") or 20) * 1024 * 1024
        original_name = _safe_upload_name(file.filename or "")
        content_type = _text(file.mimetype) or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        if content_type not in allowed:
            return {"ok": False, "code": "validation_error", "message": "Tipo file non consentito."}
        data = file.read()
        if len(data) > max_bytes:
            return {"ok": False, "code": "validation_error", "message": "File troppo grande per le impostazioni dello studio."}
        digest = hashlib.sha256(data).hexdigest()
        matter_id = _text(invite.get("matter_id"))
        matter_dir = _safe_upload_name(matter_id)
        doc_id = hashlib.sha256(f"{digest}:{utc_now()}".encode("utf-8")).hexdigest()[:20]
        repo_for_path = repository_for_token(token)
        upload_root = repo_for_path.db_path.parent / "uploads"
        root = _resolved_upload_child(upload_root, matter_dir)
        root.mkdir(parents=True, exist_ok=True)
        stored_name = f"{doc_id}_{original_name}"
        target = _resolved_upload_child(root, stored_name)
        target.write_bytes(data)
        item = repo.add_document(
            tenant_id,
            matter_id=matter_id,
            request_id=_text(request_id),
            client_id=_text(invite.get("client_id")),
            filename=original_name,
            stored_name=f"{matter_dir}/{stored_name}",
            content_type=content_type,
            size_bytes=len(data),
            sha256=digest,
        )
        return {"ok": True, "message": "Documento caricato.", "item": _public_row(item), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_complete_signature(signature_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not is_feature_enabled("routes.appV2.clientPortal.signatures", current_app.config):
        return {"ok": False, "code": "feature_disabled", "message": "Firma cliente non attiva per questo studio."}
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        item = repo.complete_signature(
            _text(invite.get("tenant_id")),
            signature_id,
            client_id=_text(invite.get("client_id")),
            evidence={"declaration": _text(payload.get("declaration")) or "Firma semplice acquisita dal Portale Cliente.", "ip": _text(request.remote_addr)},
        )
        return {"ok": True, "message": "Firma registrata.", "item": _public_row(item), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_update_appointment(appointment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        status = _text(payload.get("status"))
        if status not in {"confermato", "annullato"}:
            return {"ok": False, "code": "validation_error", "message": "Stato appuntamento non valido."}
        item = repo.update_appointment_status(
            _text(invite.get("tenant_id")),
            appointment_id,
            status=status,
            actor_id=_text(invite.get("client_id")),
            actor_type="cliente",
        )
        return {"ok": True, "message": "Appuntamento aggiornato.", "item": _public_row(item), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_mark_notification(notification_id: str) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        item = repo.mark_notification_read(_text(invite.get("tenant_id")), notification_id, client_id=_text(invite.get("client_id")))
        return {"ok": True, "message": "Notifica aggiornata.", "item": _public_row(item), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_submit_questionnaire(questionnaire_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        item = repo.submit_questionnaire(
            _text(invite.get("tenant_id")),
            questionnaire_id,
            matter_id=_text(invite.get("matter_id")),
            responses=dict(payload.get("responses") or {}),
            client_id=_text(invite.get("client_id")),
        )
        return {"ok": True, "message": "Questionario inviato.", "item": _public_row(item), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()


def client_submit_survey(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        token = _current_client_token()
        invite, repo = _invite_and_repo(token)
        item = repo.submit_survey(
            _text(invite.get("tenant_id")),
            matter_id=_text(invite.get("matter_id")),
            rating=int(payload.get("rating") or 0),
            comment=_text(payload.get("comment")),
            client_id=_text(invite.get("client_id")),
        )
        return {"ok": True, "message": "Valutazione inviata.", "item": _public_row(item), "dashboard": client_dashboard_payload(token=token)}
    except ClientPortalError:
        return _invalid_invite_payload()

"""Bridge Calendari per la pagina React Impostazioni."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import requests
from flask import current_app, g, request

from pct.agenda import TipoAppuntamento
from pct.calendar_bindings import now_iso
from pct.calendar_credentials import CalendarCredentialError
from pct.calendar_sync_engine import CalendarSyncEngine, PRIVACY_BUSY, PRIVACY_COMPLETE, PRIVACY_REDUCED
from web.services.tenant_api_auth import api_key_valid_for_request


ALLOWED_CALENDAR_FIELDS = {"nome", "provider", "source_url", "default_tipo", "default_reminder_minuti"}
PROVIDER_LABELS = {
    "google": "Google Calendar",
    "microsoft": "Outlook / Microsoft 365",
    "outlook": "Microsoft Outlook",
    "apple": "Apple iCloud",
    "apple_caldav": "Apple iCloud",
    "webcal": "Altro calendario",
    "ics": "Altro calendario",
    "demo": "Ambiente prova locale",
    "generico": "Calendario esterno",
}
ROLE_LABELS = {
    "agenda": "Agenda",
    "scadenze": "Scadenziario",
    "completo": "Agenda e scadenziario",
    "import_only": "Solo acquisizione",
    "export_only": "Solo pubblicazione",
}
DIRECTION_LABELS = {
    "inbound": "Solo verso IUSENTRA",
    "outbound": "Solo verso il calendario",
    "bidirectional": "Bidirezionale",
}
PRIVACY_LABELS = {
    PRIVACY_COMPLETE: "Completo",
    PRIVACY_REDUCED: "Ridotto professionale",
    PRIVACY_BUSY: "Solo occupato",
}
ACCOUNT_STATUS_LABELS = {
    "active": ("Collegato", "success"),
    "needs_attention": ("Da verificare", "warning"),
    "disconnected": ("Scollegato", "neutral"),
    "error": ("Da verificare", "warning"),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


def _cfg_path(key: str, fallback: str = "") -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if paths and key in paths:
        return _text(paths[key], fallback)
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return _text(current_app.config.get(key), fallback)


def _can(permission: str) -> bool:
    if api_key_valid_for_request():
        return True
    user = g.get("utente_corrente")
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _cal_token_dir() -> str:
    agenda_db = _cfg_path("AGENDA_DB", "./data/agenda.json")
    return os.path.dirname(os.path.abspath(agenda_db))


def _tenant_id() -> str:
    studio = getattr(g, "tenant", None)
    slug = _text(getattr(studio, "slug", "")) or _text(getattr(g, "tenant_context_slug", ""))
    return slug or "default"


def _request_studio_db() -> Any:
    try:
        from web.services.storage_runtime import get_request_studio_db

        paths = getattr(g, "data_paths", {}) or {}
        anchor = paths.get("CLIENTI_DB") or current_app.config.get("CLIENTI_DB")
        return get_request_studio_db(anchor) if anchor else None
    except Exception:
        return None


def _engine() -> CalendarSyncEngine:
    return CalendarSyncEngine.from_paths(
        agenda_db=_cfg_path("AGENDA_DB", "./data/agenda.json"),
        scadenziario_db=_cfg_path("SCADENZIARIO_DB", "./data/scadenziario/scadenze.json"),
        sync_db=_cfg_path("CALENDAR_SYNC_DB", os.path.join(_cal_token_dir(), "calendar_sync.json")),
        tenant_id=_tenant_id(),
        studio_db=_request_studio_db(),
    )


def _base_url() -> str:
    configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
    if configured:
        return configured
    base = request.host_url.rstrip("/")
    return "https://" + base[len("http://") :] if base.startswith("http://") else base


def _provider_label(value: Any) -> str:
    key = _text(value, "generico").lower()
    return PROVIDER_LABELS.get(key, key.replace("_", " ").title() or "Calendario esterno")


def _role_label(value: Any) -> str:
    key = _text(value, "completo").lower()
    return ROLE_LABELS.get(key, "Agenda e scadenziario")


def _direction_label(value: Any) -> str:
    key = _text(value, "bidirectional").lower()
    return DIRECTION_LABELS.get(key, "Bidirezionale")


def _privacy_label(value: Any) -> str:
    key = _text(value, PRIVACY_REDUCED).lower()
    return PRIVACY_LABELS.get(key, PRIVACY_LABELS[PRIVACY_REDUCED])


def _account_status(value: Any) -> tuple[str, str]:
    return ACCOUNT_STATUS_LABELS.get(_text(value, "active").lower(), ("Da verificare", "warning"))


def _status_label(value: Any) -> tuple[str, str]:
    key = _text(value, "mai_eseguito").lower()
    if key == "ok":
        return "Sincronizzato", "success"
    if key == "errore":
        return "Da verificare", "warning"
    return "Mai sincronizzato", "neutral"


def _date_it(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "Mai"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return raw.replace("T", " ")[:16]


def _profile(item: dict[str, Any]) -> dict[str, Any]:
    status, tone = _status_label(item.get("last_status"))
    return {
        "id": _text(item.get("id")),
        "nome": _text(item.get("nome"), "Calendario esterno"),
        "provider": _text(item.get("provider"), "generico"),
        "provider_label": _provider_label(item.get("provider")),
        "source_url": _text(item.get("source_url")),
        "enabled": bool(item.get("enabled", True)),
        "status_label": status,
        "status_tone": tone,
        "last_sync_at": _date_it(item.get("last_sync_at")),
        "last_message": _text(item.get("last_message")),
        "created": int(item.get("last_created") or 0),
        "updated": int(item.get("last_updated") or 0),
        "skipped": int(item.get("last_skipped") or 0),
        "conflicts": int(item.get("last_conflicts") or 0),
    }


def _calendar_payload(item: dict[str, Any], account: dict[str, Any] | None = None) -> dict[str, Any]:
    account = account or {}
    status, tone = _account_status(item.get("status") or account.get("status"))
    return {
        "id": _text(item.get("id")),
        "account_id": _text(item.get("account_id")),
        "provider": _text(account.get("provider") or item.get("provider")),
        "provider_label": _provider_label(account.get("provider") or item.get("provider")),
        "account": _text(account.get("display_name"), "Account calendario"),
        "account_email": _text(account.get("email")),
        "name": _text(item.get("name"), "Calendario"),
        "role": _text(item.get("role"), "completo"),
        "role_label": _role_label(item.get("role")),
        "direction": _text(item.get("direction"), "bidirectional"),
        "direction_label": _direction_label(item.get("direction")),
        "enabled": bool(item.get("enabled", True)),
        "privacy_level": _text(item.get("privacy_level"), PRIVACY_REDUCED),
        "privacy_label": _privacy_label(item.get("privacy_level")),
        "last_sync_at": _date_it(item.get("last_sync_at")),
        "status_label": status if bool(item.get("enabled", True)) else "In pausa",
        "status_tone": tone if bool(item.get("enabled", True)) else "neutral",
        "last_error": _text(item.get("last_error")),
    }


def _account_payload(account: dict[str, Any], calendars: list[dict[str, Any]]) -> dict[str, Any]:
    status, tone = _account_status(account.get("status"))
    return {
        "id": _text(account.get("id")),
        "provider": _text(account.get("provider")),
        "provider_label": _provider_label(account.get("provider")),
        "display_name": _text(account.get("display_name"), "Account calendario"),
        "email": _text(account.get("email")),
        "auth_type": _text(account.get("auth_type")),
        "status": _text(account.get("status"), "active"),
        "status_label": status,
        "status_tone": tone,
        "calendar_count": len(calendars),
        "created_at": _date_it(account.get("created_at")),
        "updated_at": _date_it(account.get("updated_at")),
        "calendars": [_calendar_payload(item, account) for item in calendars],
    }


def _jobs_payload(items: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    rows = sorted(items, key=lambda item: _text(item.get("updated_at")), reverse=True)[:limit]
    return [
        {
            "id": _text(item.get("id")),
            "account_id": _text(item.get("account_id")),
            "action": _text(item.get("action")),
            "status": _text(item.get("status")),
            "status_label": {
                "queued": "In attesa",
                "running": "In corso",
                "success": "Completato",
                "failed": "Non riuscito",
            }.get(_text(item.get("status")), "Da verificare"),
            "attempts": int(item.get("attempts") or 0),
            "error": _text(item.get("error")),
            "updated_at": _date_it(item.get("updated_at")),
        }
        for item in rows
    ]


def _summary_from_snapshot(snapshot: Any, *, remote: bool = False) -> dict[str, Any]:
    item = snapshot if isinstance(snapshot, dict) else {}
    title = _text(item.get("titolo") or item.get("title") or item.get("summary"), "Elemento calendario")
    when = _text(item.get("data_ora") or item.get("data_scadenza") or item.get("start"))
    state = _text(item.get("stato") or item.get("status"), "da verificare")
    if remote and state == "cancelled":
        state = "annullato sul calendario esterno"
    return {
        "title": title,
        "when": _date_it(when) if "T" in when else when,
        "status": state,
        "note": _text(item.get("note") or item.get("description")),
    }


def _conflict_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(item.get("id")),
        "local_type": _text(item.get("local_type")),
        "local_label": "Scadenza" if item.get("local_type") == "scadenza" else "Agenda",
        "local_id": _text(item.get("local_id")),
        "provider": _text(item.get("provider")),
        "provider_label": _provider_label(item.get("provider")),
        "conflict_type": _text(item.get("conflict_type")),
        "conflict_label": {
            "modifica_concorrente": "Modifica contemporanea",
            "scadenza_perentoria_cancellata": "Scadenza perentoria da proteggere",
            "scadenza_perentoria_spostata": "Data perentoria modificata fuori studio",
        }.get(_text(item.get("conflict_type")), "Verifica richiesta"),
        "status": _text(item.get("status"), "open"),
        "local_summary": _summary_from_snapshot(item.get("local_snapshot")),
        "remote_summary": _summary_from_snapshot(item.get("remote_snapshot"), remote=True),
        "proposed_resolution": _text(item.get("proposed_resolution")),
        "created_at": _date_it(item.get("created_at")),
        "resolved_at": _date_it(item.get("resolved_at")),
    }


def _engine_payload() -> dict[str, Any]:
    engine = _engine()
    repo = engine.repository
    tenant = _tenant_id()
    accounts = repo.list_accounts(tenant)
    calendars = repo.list_calendars(tenant)
    by_account = {item.get("id"): item for item in accounts}
    calendars_by_account: dict[str, list[dict[str, Any]]] = {}
    for calendar in calendars:
        calendars_by_account.setdefault(_text(calendar.get("account_id")), []).append(calendar)
    account_rows = [_account_payload(account, calendars_by_account.get(_text(account.get("id")), [])) for account in accounts]
    calendar_rows = [_calendar_payload(calendar, by_account.get(calendar.get("account_id"))) for calendar in calendars]
    conflicts = [_conflict_payload(item) for item in engine.conflicts.list_conflicts(tenant, status="open")]
    jobs = _jobs_payload(repo.list_jobs(tenant))
    return {
        "accounts": account_rows,
        "connected_calendars": calendar_rows,
        "conflicts": conflicts,
        "sync_jobs": jobs,
        "engine_account_count": len(account_rows),
        "engine_calendar_count": len(calendar_rows),
        "open_conflict_count": len(conflicts),
    }


def _validate_calendar_url(value: str) -> str:
    raw = _text(value)
    if raw.lower().startswith("webcal://"):
        raw = "https://" + raw[len("webcal://") :]
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Inserisci un link calendario valido.")
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        raise ValueError("Il calendario deve provenire da un servizio esterno raggiungibile.")
    return raw


def _audit(action: str, resource_id: str, details: str) -> None:
    try:
        from web.helpers import get_utenti

        user = g.get("utente_corrente")
        get_utenti().registra_evento(
            action,
            id_utente=_text(getattr(user, "id", "")),
            username=_text(getattr(user, "username", "")),
            risorsa_tipo="calendario",
            risorsa_id=resource_id,
            dettagli=details,
            ip=request.remote_addr or "",
        )
    except Exception:
        return


def build_calendario_payload(*, get_calendar_sync: Any, get_agenda: Any, get_scadenziario: Any) -> dict[str, Any]:
    from pct.cal_token import get_token

    token_data = get_token(_cal_token_dir())
    token = token_data["token"]
    base = _base_url()
    feeds = {
        "agenda": f"{base}/cal/{token}/agenda.ics",
        "scadenze": f"{base}/cal/{token}/scadenze.ics",
        "completo": f"{base}/cal/{token}/completo.ics",
    }
    profiles = [_profile(item) for item in get_calendar_sync().list_profiles()]
    engine_payload = _engine_payload()
    engine_calendar_count = int(engine_payload.get("engine_calendar_count") or 0)
    return {
        "ok": True,
        "generated_at": _iso_now(),
        "feeds": feeds,
        "google_url": "https://calendar.google.com/calendar/r/settings/addbyurl"
        f"?url={quote(feeds['completo'], safe='')}",
        "token_created_at": _date_it(token_data.get("creato_il")),
        "profiles": profiles,
        "profile_count": len(profiles) + engine_calendar_count,
        "active_profiles": sum(1 for item in profiles if item.get("enabled"))
        + sum(1 for item in engine_payload.get("connected_calendars", []) if item.get("enabled")),
        "agenda_count": len(get_agenda().tutti()),
        "deadline_count": len(get_scadenziario().tutte()),
        "can_update": _can("admin.configura"),
        **engine_payload,
        "exports": {
            "agenda": "/agenda/export.ics",
            "scadenze": "/scadenziario/export.ics",
            "completo": "/calendario/completo/export.ics",
        },
    }


def create_calendar_profile(*, payload: dict[str, Any], get_calendar_sync: Any) -> dict[str, Any]:
    errors = {key: "Campo non previsto." for key in sorted(set(payload) - ALLOWED_CALENDAR_FIELDS)}
    nome = _text(payload.get("nome"), "Calendario esterno")
    provider = _text(payload.get("provider"), "webcal")
    source_url = _text(payload.get("source_url"))
    if not source_url:
        errors["source_url"] = "Inserisci il link del calendario."
    try:
        source_url = _validate_calendar_url(source_url)
    except ValueError as exc:
        errors["source_url"] = str(exc)
    try:
        reminder = max(int(payload.get("default_reminder_minuti") or 60), 0)
    except (TypeError, ValueError):
        reminder = 60
    default_tipo = _text(payload.get("default_tipo"), TipoAppuntamento.ALTRO.value)
    if default_tipo not in {item.value for item in TipoAppuntamento}:
        default_tipo = TipoAppuntamento.ALTRO.value
    if errors:
        return {"ok": False, "message": "Controlla i dati del calendario.", "errors": errors}
    manager = get_calendar_sync()
    preview = manager.preview_remote_calendar(source_url)
    profile = manager.create_profile(
        nome=nome,
        provider=provider,
        source_url=preview["source_url"],
        default_tipo=default_tipo,
        default_reminder_minuti=reminder,
        enabled=True,
    )
    _audit("calendario.profilo.crea", _text(profile.get("id")), f"nome={nome}")
    return {"ok": True, "message": "Calendario aggiunto.", "errors": {}, "profile": _profile(profile)}


def sync_calendar_profile(*, profile_id: str, get_calendar_sync: Any, get_agenda: Any) -> dict[str, Any]:
    manager = get_calendar_sync()
    try:
        report = manager.sync_profile(profile_id, agenda=get_agenda())
        _audit("calendario.profilo.sincronizza", profile_id, "sincronizzazione manuale")
        return {
            "ok": True,
            "message": "Calendario sincronizzato.",
            "errors": {},
            "report": report,
            "profile": _profile(report.get("profile") or {}),
        }
    except Exception as exc:
        try:
            manager.mark_sync_error(profile_id, str(exc))
        except Exception:
            pass
        return {"ok": False, "message": "Sincronizzazione non riuscita.", "errors": {"profile": str(exc)}}


def toggle_calendar_profile(*, profile_id: str, get_calendar_sync: Any) -> dict[str, Any]:
    manager = get_calendar_sync()
    profile = manager.get_profile(profile_id)
    if not profile:
        return {"ok": False, "message": "Calendario non trovato.", "errors": {"profile": "Non trovato."}}
    updated = manager.update_profile(profile_id, enabled=not bool(profile.get("enabled", True)))
    _audit("calendario.profilo.aggiorna", profile_id, "stato aggiornato")
    return {"ok": True, "message": "Calendario aggiornato.", "errors": {}, "profile": _profile(updated)}


def delete_calendar_profile(*, profile_id: str, get_calendar_sync: Any) -> dict[str, Any]:
    get_calendar_sync().delete_profile(profile_id)
    _audit("calendario.profilo.elimina", profile_id, "profilo eliminato")
    return {"ok": True, "message": "Calendario eliminato.", "errors": {}}


def regenerate_calendar_token() -> dict[str, Any]:
    from pct.cal_token import rigenera_token

    rigenera_token(_cal_token_dir())
    _audit("calendario.token.rigenera", "feed", "link calendario rigenerati")
    return {"ok": True, "message": "Link calendario aggiornati.", "errors": {}}


def list_calendar_accounts_payload() -> dict[str, Any]:
    return {"ok": True, "generated_at": _iso_now(), "can_update": _can("admin.configura"), **_engine_payload()}


def _safe_credentials_encrypt(engine: CalendarSyncEngine, value: dict[str, Any]) -> str:
    try:
        return engine.credentials.encrypt(value)
    except CalendarCredentialError:
        raise


def _find_calendar(repo: Any, *, tenant: str, account_id: str, provider_calendar_id: str) -> dict[str, Any] | None:
    for item in repo.list_calendars(tenant, account_id=account_id):
        if _text(item.get("provider_calendar_id")) == provider_calendar_id:
            return item
    return None


def _upsert_account_calendar(
    *,
    engine: CalendarSyncEngine,
    provider: str,
    display_name: str,
    email: str,
    auth_type: str,
    encrypted_credentials: str,
    scopes: list[str] | None,
    calendar_name: str,
    provider_calendar_id: str,
    role: str = "completo",
    direction: str = "bidirectional",
    privacy_level: str = PRIVACY_REDUCED,
    extra_account: dict[str, Any] | None = None,
    extra_calendar: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repo = engine.repository
    tenant = _tenant_id()
    account = repo.find_account(tenant_id=tenant, provider=provider, email=email, display_name=display_name)
    account_payload = {
        **(account or {}),
        "tenant_id": tenant,
        "provider": provider,
        "display_name": display_name,
        "email": email,
        "auth_type": auth_type,
        "encrypted_credentials": encrypted_credentials,
        "scopes": scopes or [],
        "status": "active",
        **(extra_account or {}),
    }
    account = repo.upsert_account(account_payload)
    calendar = _find_calendar(repo, tenant=tenant, account_id=account["id"], provider_calendar_id=provider_calendar_id)
    calendar_payload = {
        **(calendar or {}),
        "tenant_id": tenant,
        "account_id": account["id"],
        "provider": provider,
        "provider_calendar_id": provider_calendar_id,
        "name": calendar_name,
        "role": role,
        "direction": direction,
        "enabled": True,
        "privacy_level": privacy_level,
        **(extra_calendar or {}),
    }
    calendar = repo.upsert_calendar(calendar_payload)
    return account, calendar


def connect_demo_calendar_account(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    engine = _engine()
    encrypted = _safe_credentials_encrypt(engine, {"mode": "local_proof", "created_at": _iso_now()})
    display_name = _text((payload or {}).get("display_name"), "Ambiente prova locale")
    account, calendar = _upsert_account_calendar(
        engine=engine,
        provider="demo",
        display_name=display_name,
        email=_text((payload or {}).get("email"), "calendario-locale@iusentra.local"),
        auth_type="demo",
        encrypted_credentials=encrypted,
        scopes=["calendar.demo"],
        calendar_name=_text((payload or {}).get("calendar_name"), "Calendario prova locale"),
        provider_calendar_id="demo-primary",
        role=_text((payload or {}).get("role"), "completo"),
        direction=_text((payload or {}).get("direction"), "bidirectional"),
        privacy_level=_text((payload or {}).get("privacy_level"), PRIVACY_REDUCED),
    )
    _audit("calendario.account.crea", _text(account.get("id")), "ambiente prova locale")
    return {
        "ok": True,
        "message": "Calendario di prova locale collegato.",
        "errors": {},
        "account": _account_payload(account, [calendar]),
        **_engine_payload(),
    }


def connect_webcal_calendar_account(*, payload: dict[str, Any], get_calendar_sync: Any) -> dict[str, Any]:
    created = create_calendar_profile(payload=payload, get_calendar_sync=get_calendar_sync)
    if not created.get("ok"):
        return created
    profile = created.get("profile") or {}
    engine = _engine()
    source_url = _validate_calendar_url(_text(payload.get("source_url") or profile.get("source_url")))
    parsed = urlparse(source_url)
    encrypted = _safe_credentials_encrypt(engine, {"source_url": source_url})
    account, calendar = _upsert_account_calendar(
        engine=engine,
        provider="webcal",
        display_name=_text(payload.get("nome") or profile.get("nome"), "Calendario esterno"),
        email=parsed.hostname or "calendario-esterno",
        auth_type="webcal",
        encrypted_credentials=encrypted,
        scopes=["calendar.read"],
        calendar_name=_text(payload.get("nome") or profile.get("nome"), "Calendario esterno"),
        provider_calendar_id=source_url,
        role=_text(payload.get("role"), "agenda"),
        direction="inbound",
        privacy_level=_text(payload.get("privacy_level"), PRIVACY_REDUCED),
        extra_account={"source_url": source_url},
        extra_calendar={"source_url": source_url},
    )
    _audit("calendario.account.crea", _text(account.get("id")), "calendario esterno")
    return {
        "ok": True,
        "message": "Calendario esterno collegato.",
        "errors": {},
        "account": _account_payload(account, [calendar]),
        "profile": profile,
        **_engine_payload(),
    }


def connect_apple_calendar_account(payload: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, str] = {}
    server_url = _text(payload.get("server_url"))
    username = _text(payload.get("username"))
    password = _text(payload.get("password"))
    if not server_url:
        errors["server_url"] = "Inserisci l'indirizzo CalDAV."
    if not username:
        errors["username"] = "Inserisci l'utente iCloud."
    if not password:
        errors["password"] = "Inserisci la password per app."
    if errors:
        return {"ok": False, "message": "Controlla i dati dell'account.", "errors": errors}
    engine = _engine()
    encrypted = _safe_credentials_encrypt(
        engine,
        {"server_url": server_url.rstrip("/"), "username": username, "password": password},
    )
    account, calendar = _upsert_account_calendar(
        engine=engine,
        provider="apple_caldav",
        display_name=_text(payload.get("display_name"), "Apple iCloud"),
        email=username,
        auth_type="caldav",
        encrypted_credentials=encrypted,
        scopes=["calendar.caldav"],
        calendar_name=_text(payload.get("calendar_name"), "Calendario iCloud"),
        provider_calendar_id=_text(payload.get("calendar_url"), server_url.rstrip("/")),
        role=_text(payload.get("role"), "completo"),
        direction=_text(payload.get("direction"), "bidirectional"),
        privacy_level=_text(payload.get("privacy_level"), PRIVACY_REDUCED),
        extra_account={"server_url": server_url.rstrip("/")},
        extra_calendar={"calendar_url": _text(payload.get("calendar_url"), server_url.rstrip("/"))},
    )
    _audit("calendario.account.crea", _text(account.get("id")), "calendario iCloud")
    return {"ok": True, "message": "Account iCloud collegato.", "errors": {}, "account": _account_payload(account, [calendar]), **_engine_payload()}


def _oauth_redirect(provider: str) -> str:
    configured = os.getenv(f"{provider.upper()}_CALENDAR_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return f"{_base_url()}/api/v1/ui/calendari/{provider}/callback"


def calendar_oauth_connect(provider: str) -> dict[str, Any]:
    key = "google" if provider == "google" else "microsoft"
    if key == "google":
        client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
        if not client_id:
            return {"ok": False, "message": "Configurazione Google Calendar non completa.", "errors": {"account": "Credenziali applicazione mancanti."}}
        params = {
            "client_id": client_id,
            "redirect_uri": _oauth_redirect("google"),
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "state": secrets.token_urlsafe(18),
        }
        return {"ok": True, "message": "Collegamento pronto.", "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}
    client_id = os.getenv("MICROSOFT_CALENDAR_CLIENT_ID", "").strip()
    tenant = os.getenv("MICROSOFT_CALENDAR_TENANT", "common").strip() or "common"
    if not client_id:
        return {"ok": False, "message": "Configurazione Microsoft Calendar non completa.", "errors": {"account": "Credenziali applicazione mancanti."}}
    params = {
        "client_id": client_id,
        "redirect_uri": _oauth_redirect("microsoft"),
        "response_type": "code",
        "scope": "offline_access User.Read Calendars.ReadWrite",
        "response_mode": "query",
        "state": secrets.token_urlsafe(18),
    }
    return {
        "ok": True,
        "message": "Collegamento pronto.",
        "auth_url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?" + urlencode(params),
    }


def calendar_oauth_callback(provider: str, args: Any) -> dict[str, Any]:
    code = _text(args.get("code"))
    if not code:
        return {"ok": False, "message": "Autorizzazione non completata.", "errors": {"account": "Codice mancante."}}
    engine = _engine()
    if provider == "google":
        client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return {"ok": False, "message": "Configurazione Google Calendar non completa.", "errors": {"account": "Credenziali applicazione mancanti."}}
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _oauth_redirect("google"),
            },
            timeout=20,
        )
        if response.status_code >= 400:
            return {"ok": False, "message": "Collegamento Google non riuscito.", "errors": {"account": "Autorizzazione respinta."}}
        credentials = response.json()
        encrypted = _safe_credentials_encrypt(engine, credentials)
        account, calendar = _upsert_account_calendar(
            engine=engine,
            provider="google",
            display_name="Google Calendar",
            email=_text(credentials.get("email")),
            auth_type="oauth",
            encrypted_credentials=encrypted,
            scopes=["calendar.events", "calendar.readonly"],
            calendar_name="Calendario principale",
            provider_calendar_id="primary",
        )
    else:
        client_id = os.getenv("MICROSOFT_CALENDAR_CLIENT_ID", "").strip()
        client_secret = os.getenv("MICROSOFT_CALENDAR_CLIENT_SECRET", "").strip()
        tenant = os.getenv("MICROSOFT_CALENDAR_TENANT", "common").strip() or "common"
        if not client_id or not client_secret:
            return {"ok": False, "message": "Configurazione Microsoft Calendar non completa.", "errors": {"account": "Credenziali applicazione mancanti."}}
        response = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _oauth_redirect("microsoft"),
                "scope": "offline_access User.Read Calendars.ReadWrite",
            },
            timeout=20,
        )
        if response.status_code >= 400:
            return {"ok": False, "message": "Collegamento Microsoft non riuscito.", "errors": {"account": "Autorizzazione respinta."}}
        credentials = response.json()
        encrypted = _safe_credentials_encrypt(engine, credentials)
        account, calendar = _upsert_account_calendar(
            engine=engine,
            provider="microsoft",
            display_name="Outlook / Microsoft 365",
            email=_text(credentials.get("email")),
            auth_type="oauth",
            encrypted_credentials=encrypted,
            scopes=["Calendars.ReadWrite"],
            calendar_name="Calendario principale",
            provider_calendar_id="primary",
        )
    _audit("calendario.account.crea", _text(account.get("id")), _provider_label(provider))
    return {"ok": True, "message": "Account calendario collegato.", "errors": {}, "account": _account_payload(account, [calendar]), **_engine_payload()}


def sync_calendar_account(account_id: str) -> dict[str, Any]:
    engine = _engine()
    try:
        report = engine.sync_account(account_id)
        _audit("calendario.account.sincronizza", account_id, "allineamento manuale")
        return {"ok": True, "message": "Calendario allineato.", "errors": {}, "report": report, **_engine_payload()}
    except Exception as exc:
        current_app.logger.exception("Errore sync account calendario React: %s", exc)
        return {"ok": False, "message": "Allineamento non riuscito.", "errors": {"account": "Verifica il collegamento e riprova."}}


def disconnect_calendar_account(account_id: str) -> dict[str, Any]:
    engine = _engine()
    try:
        account = engine.repository.disconnect_account(account_id, _tenant_id())
        _audit("calendario.account.scollega", account_id, "account scollegato")
        return {"ok": True, "message": "Account calendario scollegato.", "errors": {}, "account": _account_payload(account, []), **_engine_payload()}
    except Exception:
        return {"ok": False, "message": "Account calendario non trovato.", "errors": {"account": "Non trovato."}}


def toggle_linked_calendar(calendar_id: str) -> dict[str, Any]:
    engine = _engine()
    calendar = engine.repository.get_calendar(calendar_id, _tenant_id())
    if not calendar:
        return {"ok": False, "message": "Calendario non trovato.", "errors": {"calendar": "Non trovato."}}
    calendar["enabled"] = not bool(calendar.get("enabled", True))
    updated = engine.repository.upsert_calendar(calendar)
    _audit("calendario.collegato.stato", calendar_id, "stato aggiornato")
    return {"ok": True, "message": "Calendario aggiornato.", "errors": {}, "calendar": _calendar_payload(updated), **_engine_payload()}


def list_calendar_conflicts_payload() -> dict[str, Any]:
    return {"ok": True, "conflicts": _engine_payload().get("conflicts", [])}


def resolve_calendar_conflict(conflict_id: str, strategy: str) -> dict[str, Any]:
    engine = _engine()
    try:
        result = engine.resolve_conflict(conflict_id, strategy)
        _audit("calendario.conflitto.risolvi", conflict_id, f"strategia={strategy}")
        return {"ok": True, "message": "Conflitto aggiornato.", "errors": {}, "result": result, **_engine_payload()}
    except Exception:
        return {"ok": False, "message": "Conflitto non aggiornato.", "errors": {"conflict": "Verifica richiesta."}}


def calendar_webhook_received(provider: str, headers: dict[str, Any] | None = None) -> dict[str, Any]:
    current_app.logger.info("Notifica calendario ricevuta: %s", provider)
    return {"ok": True, "message": "Notifica ricevuta.", "provider": provider, "received_at": now_iso()}

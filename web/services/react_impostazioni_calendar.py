"""Bridge Calendari per la pagina React Impostazioni."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

from flask import current_app, g, request

from pct.agenda import TipoAppuntamento


ALLOWED_CALENDAR_FIELDS = {"nome", "provider", "source_url", "default_tipo", "default_reminder_minuti"}
PROVIDER_LABELS = {
    "google": "Google Calendar",
    "outlook": "Microsoft Outlook",
    "apple": "Apple Calendar",
    "webcal": "Altro calendario",
    "generico": "Calendario esterno",
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
    api_key = str(current_app.config.get("API_KEY", "") or "")
    if api_key and request.headers.get("X-API-Key") == api_key:
        return True
    user = g.get("utente_corrente")
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _cal_token_dir() -> str:
    agenda_db = _cfg_path("AGENDA_DB", "./data/agenda.json")
    return os.path.dirname(os.path.abspath(agenda_db))


def _base_url() -> str:
    configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
    if configured:
        return configured
    base = request.host_url.rstrip("/")
    return "https://" + base[len("http://") :] if base.startswith("http://") else base


def _provider_label(value: Any) -> str:
    key = _text(value, "generico").lower()
    return PROVIDER_LABELS.get(key, key.replace("_", " ").title() or "Calendario esterno")


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
    return {
        "ok": True,
        "generated_at": _iso_now(),
        "feeds": feeds,
        "google_url": "https://calendar.google.com/calendar/r/settings/addbyurl"
        f"?url={quote(feeds['completo'], safe='')}",
        "token_created_at": _date_it(token_data.get("creato_il")),
        "profiles": profiles,
        "profile_count": len(profiles),
        "active_profiles": sum(1 for item in profiles if item.get("enabled")),
        "agenda_count": len(get_agenda().tutti()),
        "deadline_count": len(get_scadenziario().tutte()),
        "can_update": _can("admin.configura"),
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

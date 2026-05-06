"""Bridge read-only per gestione utenti React.

Il bridge espone solo dati amministrativi non segreti. Le scritture restano
form HTML verso le route Flask legacy gia' auditabili.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from pct.auth import DESCRIZIONI_RUOLI, RuoloUtente


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _role_value(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _role_description(ruolo: RuoloUtente) -> dict[str, str]:
    raw = DESCRIZIONI_RUOLI.get(ruolo, {}) or {}
    return {
        "description": _text(raw.get("descrizione")),
        "tone": _text(raw.get("colore")) or "neutral",
        "icon": _text(raw.get("icona")),
    }


def _manageable_roles() -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    for ruolo in RuoloUtente:
        if ruolo == RuoloUtente.SUPERADMIN:
            continue
        info = _role_description(ruolo)
        roles.append({
            "value": ruolo.value,
            "label": ruolo.value.replace("_", " ").title(),
            "description": info["description"],
            "tone": _tone_from_bootstrap(info["tone"]),
        })
    return roles


def _tone_from_bootstrap(value: str) -> str:
    mapping = {
        "danger": "danger",
        "success": "success",
        "warning": "warning",
        "info": "info",
        "primary": "primary",
        "secondary": "neutral",
        "dark": "neutral",
    }
    return mapping.get(_text(value).lower(), "neutral")


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _safe_user(user: Any) -> dict[str, Any]:
    ruolo = getattr(user, "ruolo", RuoloUtente.SEGRETERIA)
    role_value = _role_value(ruolo)
    try:
        role_enum = RuoloUtente(role_value)
    except ValueError:
        role_enum = RuoloUtente.SEGRETERIA
    role_info = _role_description(role_enum)
    user_id = _text(getattr(user, "id", ""))
    return {
        "id": user_id,
        "username": _text(getattr(user, "username", "")),
        "name": _text(getattr(user, "nome_completo", "")),
        "email": _text(getattr(user, "email", "")),
        "role": role_value,
        "roleLabel": role_value.replace("_", " ").title(),
        "roleDescription": role_info["description"],
        "roleTone": _tone_from_bootstrap(role_info["tone"]),
        "active": bool(getattr(user, "attivo", False)),
        "mustChangePassword": bool(getattr(user, "must_change_password", False)),
        "lastAccess": _text(getattr(user, "ultimo_accesso", "")),
        "hasOverride": bool(getattr(user, "ha_override", False)),
        "extraPermissionsCount": len(list(getattr(user, "permessi_extra", []) or [])),
        "deniedPermissionsCount": len(list(getattr(user, "permessi_negati", []) or [])),
        "twoFactorEnabled": bool(getattr(user, "totp_attivato", False)),
        "editHref": f"/utenti/{user_id}/modifica?_legacy=1" if user_id else "",
        "permissionsHref": f"/utenti/{user_id}/permessi?_legacy=1" if user_id else "",
    }


def _create_form(can_write: bool) -> list[dict[str, Any]]:
    if not can_write:
        return []
    return [
        {
            "id": "nuovo_utente",
            "title": "Nuovo utente",
            "description": "Invio standard verso la route legacy auditata.",
            "action": "/utenti/nuovo",
            "method": "POST",
            "csrfField": "_csrf_token",
            "submitLabel": "Crea utente",
            "fields": [
                {"name": "username", "label": "Username", "type": "text", "required": True, "autocomplete": "username"},
                {"name": "ruolo", "label": "Ruolo", "type": "select", "required": True, "options": _manageable_roles()},
                {"name": "nome_completo", "label": "Nome completo", "type": "text", "required": False, "autocomplete": "name"},
                {"name": "email", "label": "Email", "type": "email", "required": False, "autocomplete": "email"},
                {"name": "password", "label": "Password temporanea", "type": "password", "required": True, "minLength": 8, "autocomplete": "new-password"},
            ],
        }
    ]


def build_react_utenti_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    query: Any = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    manager = get_utenti()
    users = [_safe_user(user) for user in manager.tutti()]
    stats = manager.statistiche() if hasattr(manager, "statistiche") else {}
    by_role = Counter(user["role"] for user in users)
    active_count = sum(1 for user in users if user["active"])
    can_write = _can(current_user, "utenti.scrivi")
    view = _text(getattr(query, "get", lambda *_args, **_kwargs: "")("view", "")) if query is not None else ""

    if view == "nuovo" and not can_write:
        warnings.append({
            "code": "permesso_scrittura_richiesto",
            "message": "La creazione utente richiede il permesso utenti.scrivi; il POST resta sulla route legacy.",
        })

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/utenti.json",
        },
        "metrics": [
            {"id": "totale", "label": "Utenti totali", "value": int(stats.get("totale_utenti", len(users)) or 0), "note": "Account nello studio corrente", "tone": "primary"},
            {"id": "attivi", "label": "Attivi", "value": int(stats.get("attivi", active_count) or 0), "note": "Account abilitati", "tone": "success"},
            {"id": "disabilitati", "label": "Disabilitati", "value": max(len(users) - active_count, 0), "note": "Account non operativi", "tone": "warning" if len(users) != active_count else "neutral"},
            {"id": "override", "label": "Override permessi", "value": int(stats.get("con_override", sum(1 for user in users if user["hasOverride"])) or 0), "note": "Utenti con permessi personalizzati", "tone": "info"},
        ],
        "sections": [
            {
                "id": "ruoli",
                "title": "Distribuzione ruoli",
                "kind": "distribution",
                "items": [
                    {"id": f"ruolo-{role['value']}", "label": role["label"], "value": by_role.get(role["value"], 0), "note": role["description"], "tone": role["tone"]}
                    for role in _manageable_roles()
                ],
                "emptyMessage": "Nessun ruolo valorizzato sugli utenti reali.",
            },
            {
                "id": "permessi",
                "title": "Permessi operativi",
                "kind": "permissions",
                "items": [
                    {"id": "leggi", "label": "Visualizza utenti", "value": "abilitato" if _can(current_user, "utenti.leggi") else "non disponibile", "note": "Permesso utenti.leggi", "tone": "success" if _can(current_user, "utenti.leggi") else "warning"},
                    {"id": "scrivi", "label": "Crea e modifica", "value": "abilitato" if can_write else "solo legacy autorizzato", "note": "Permesso utenti.scrivi", "tone": "success" if can_write else "warning"},
                    {"id": "elimina", "label": "Elimina", "value": "abilitato" if _can(current_user, "utenti.elimina") else "non disponibile", "note": "POST legacy annidato", "tone": "danger" if _can(current_user, "utenti.elimina") else "neutral"},
                ],
                "emptyMessage": "Nessun permesso rilevato.",
            },
        ],
        "records": users,
        "actions": [
            {"id": "lista", "label": "Lista utenti", "href": "/utenti", "method": "GET", "tone": "primary"},
            {"id": "nuovo", "label": "Nuovo utente", "href": "/utenti/nuovo", "method": "GET", "tone": "success"},
            {"id": "profili", "label": "Ruoli e permessi", "href": "/profili", "method": "GET", "tone": "neutral"},
        ],
        "forms": _create_form(can_write),
        "warnings": warnings,
    }


def build_react_utenti_error_payload(message: str = "Gestione utenti non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/utenti.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [{"id": "legacy", "label": "Apri gestione utenti legacy", "href": "/utenti?_legacy=1", "method": "GET", "tone": "neutral"}],
        "forms": [],
        "warnings": [{"code": "utenti_errore_controllato", "message": message}],
    }

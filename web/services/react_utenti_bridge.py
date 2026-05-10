"""Bridge operativo per gestione utenti React."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from pct.auth import DESCRIZIONI_RUOLI, PERMESSI, RuoloUtente


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _role_value(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _role_enum(value: Any) -> RuoloUtente | None:
    try:
        return RuoloUtente(_role_value(value))
    except ValueError:
        return None


def _role_description(ruolo: RuoloUtente) -> dict[str, str]:
    raw = DESCRIZIONI_RUOLI.get(ruolo, {}) or {}
    return {
        "description": _text(raw.get("descrizione")),
        "tone": _text(raw.get("colore")) or "neutral",
        "icon": _text(raw.get("icona")),
    }


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


def _manageable_roles() -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    for ruolo in RuoloUtente:
        if ruolo == RuoloUtente.SUPERADMIN:
            continue
        info = _role_description(ruolo)
        roles.append(
            {
                "value": ruolo.value,
                "label": ruolo.value.replace("_", " ").title(),
                "description": info["description"],
                "tone": _tone_from_bootstrap(info["tone"]),
            }
        )
    return roles


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/utenti.json",
    }


def _current_user_id(current_user: Any) -> str:
    return _text(getattr(current_user, "id", ""))


def _actor_username(current_user: Any) -> str:
    return _text(getattr(current_user, "username", ""))


def _safe_user(user: Any, current_user: Any = None) -> dict[str, Any]:
    role_value = _role_value(getattr(user, "ruolo", RuoloUtente.SEGRETERIA))
    role_enum = _role_enum(role_value) or RuoloUtente.SEGRETERIA
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
        "mustChangeCredential": bool(getattr(user, "must_change_password", False)),
        "lastAccess": _text(getattr(user, "ultimo_accesso", "")),
        "hasOverride": bool(getattr(user, "ha_override", False)),
        "extraPermissionsCount": len(list(getattr(user, "permessi_extra", []) or [])),
        "deniedPermissionsCount": len(list(getattr(user, "permessi_negati", []) or [])),
        "twoFactorEnabled": bool(getattr(user, "totp_attivato", False)),
        "isCurrentUser": bool(user_id and user_id == _current_user_id(current_user)),
    }


def _all_safe_users(manager: Any, current_user: Any) -> list[dict[str, Any]]:
    current_tenant_slug = _text(getattr(current_user, "tenant_slug", "")).lower()
    users: list[dict[str, Any]] = []
    for user in manager.tutti():
        user_tenant_slug = _text(getattr(user, "tenant_slug", "")).lower()
        if current_tenant_slug and user_tenant_slug and user_tenant_slug != current_tenant_slug:
            continue
        if current_tenant_slug and _role_value(getattr(user, "ruolo", "")) == RuoloUtente.SUPERADMIN.value:
            continue
        users.append(_safe_user(user, current_user))
    return users


def _actions(can_read: bool, can_write: bool) -> dict[str, Any]:
    return {
        "canCreate": can_write,
        "canUpdate": can_write,
        "canDisable": can_write,
        "canResetPassword": can_write,
        "canChangeRole": can_write,
        "canUpdateProfile": can_write,
        "read": can_read,
        "create": "/utenti/nuovo" if can_write else "",
        "profiles": "/profili",
        "statusEndpoint": "/api/v1/ui/utenti/{id_utente}/stato",
        "roleEndpoint": "/api/v1/ui/utenti/{id_utente}/ruolo",
        "resetPasswordEndpoint": "/api/v1/ui/utenti/{id_utente}/reset-password",
        "profileEndpoint": "/api/v1/ui/utenti/{id_utente}/profilo",
        "rollback": {
            "label": "Percorso di recupero",
            "href": "/utenti?_legacy=1",
            "method": "GET",
        },
    }


def _payload_from_manager(manager: Any, current_user: Any, warnings: list[dict[str, str]] | None = None) -> dict[str, Any]:
    users = _all_safe_users(manager, current_user)
    stats = manager.statistiche() if hasattr(manager, "statistiche") else {}
    by_role = Counter(user["role"] for user in users)
    active_count = sum(1 for user in users if user["active"])
    can_read = _can(current_user, "utenti.leggi")
    can_write = _can(current_user, "utenti.scrivi")
    roles = _manageable_roles()
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "metrics": [
            {
                "id": "totale",
                "label": "Utenti totali",
                "value": int(stats.get("totale_utenti", len(users)) or 0),
                "note": "Account nello studio corrente",
                "tone": "primary",
            },
            {
                "id": "attivi",
                "label": "Attivi",
                "value": int(stats.get("attivi", active_count) or 0),
                "note": "Account abilitati",
                "tone": "success",
            },
            {
                "id": "disabilitati",
                "label": "Disabilitati",
                "value": max(len(users) - active_count, 0),
                "note": "Account non operativi",
                "tone": "warning" if len(users) != active_count else "neutral",
            },
            {
                "id": "override",
                "label": "Override permessi",
                "value": int(stats.get("con_override", sum(1 for user in users if user["hasOverride"])) or 0),
                "note": "Utenti con permessi personalizzati",
                "tone": "info",
            },
        ],
        "sections": [
            {
                "id": "ruoli",
                "title": "Distribuzione ruoli",
                "kind": "distribution",
                "items": [
                    {
                        "id": f"ruolo-{role['value']}",
                        "label": role["label"],
                        "value": by_role.get(role["value"], 0),
                        "note": role["description"],
                        "tone": role["tone"],
                    }
                    for role in roles
                ],
                "emptyMessage": "Nessun ruolo valorizzato sugli utenti reali.",
            },
            {
                "id": "permessi",
                "title": "Permessi operativi",
                "kind": "permissions",
                "items": [
                    {
                        "id": "leggi",
                        "label": "Visualizza utenti",
                        "value": "abilitato" if can_read else "non disponibile",
                        "note": "Permesso utenti.leggi",
                        "tone": "success" if can_read else "warning",
                    },
                    {
                        "id": "scrivi",
                        "label": "Modifica utenti",
                        "value": "abilitato" if can_write else "sola lettura",
                        "note": "Permesso utenti.scrivi",
                        "tone": "success" if can_write else "warning",
                    },
                ],
                "emptyMessage": "Nessun permesso rilevato.",
            },
        ],
        "users": users,
        "records": users,
        "actions": _actions(can_read, can_write),
        "createEndpoint": "/api/v1/ui/utenti/nuovo" if can_write else "",
        "roles": roles,
        "forms": [],
        "warnings": warnings or [],
    }


def build_react_utenti_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    query: Any = None,
) -> dict[str, Any]:
    manager = get_utenti()
    warnings: list[dict[str, str]] = []
    view = _text(getattr(query, "get", lambda *_args, **_kwargs: "")("view", "")) if query is not None else ""
    if view == "nuovo" and not _can(current_user, "utenti.scrivi"):
        warnings.append(
            {
                "code": "permesso_scrittura_richiesto",
                "message": "La creazione utente richiede il permesso utenti.scrivi.",
            }
        )
    return _payload_from_manager(manager, current_user, warnings)


def build_react_utenti_error_payload(message: str = "Gestione utenti non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "metrics": [],
        "sections": [],
        "users": [],
        "records": [],
        "actions": _actions(False, False),
        "createEndpoint": "",
        "roles": [],
        "forms": [],
        "warnings": [{"code": "utenti_errore_controllato", "message": message}],
    }


def _validation(message: str, errors: dict[str, str], *, manager: Any = None, current_user: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "message": message,
        "errors": errors,
        "user": None,
    }
    if manager is not None:
        result["payload"] = _payload_from_manager(manager, current_user, [])
    return result


def _permission_denied(manager: Any, current_user: Any) -> dict[str, Any]:
    return _validation(
        "Permesso utenti.scrivi richiesto.",
        {"permission": "Operazione non autorizzata."},
        manager=manager,
        current_user=current_user,
    )


def _target_user(manager: Any, user_id: str) -> Any:
    user = manager.get(_text(user_id))
    if user is None:
        raise ValueError("Utente non trovato.")
    return user


def _audit(manager: Any, current_user: Any, action: str, target: Any, details: dict[str, Any], ip: str) -> None:
    if not hasattr(manager, "registra_evento"):
        return
    manager.registra_evento(
        action,
        id_utente=_current_user_id(current_user),
        username=_actor_username(current_user),
        risorsa_tipo="utente",
        risorsa_id=_text(getattr(target, "id", "")),
        dettagli=json.dumps(details, ensure_ascii=False, sort_keys=True),
        ip=ip,
    )


def _updated_result(manager: Any, current_user: Any, target: Any, message: str) -> dict[str, Any]:
    return {
        "ok": True,
        "message": message,
        "errors": {},
        "user": _safe_user(target, current_user),
        "payload": _payload_from_manager(manager, current_user, []),
    }


def _active_admins(manager: Any) -> list[Any]:
    return [
        user
        for user in manager.tutti()
        if bool(getattr(user, "attivo", False)) and _role_value(getattr(user, "ruolo", "")) == RuoloUtente.AMMINISTRATORE.value
    ]


def _is_last_active_admin(manager: Any, target: Any) -> bool:
    if _role_value(getattr(target, "ruolo", "")) != RuoloUtente.AMMINISTRATORE.value:
        return False
    return bool(getattr(target, "attivo", False)) and len(_active_admins(manager)) <= 1


def _role_assignable(current_user: Any, target_role: RuoloUtente) -> bool:
    if getattr(current_user, "is_superadmin", False):
        return True
    current_permissions = set(getattr(current_user, "permessi_effettivi", []) or [])
    target_permissions = set(PERMESSI.get(target_role, []) or [])
    return target_permissions.issubset(current_permissions)


def _reject_unknown(payload: dict[str, Any], allowed: set[str]) -> dict[str, str]:
    unknown = sorted(set(payload) - allowed)
    if not unknown:
        return {}
    return {"payload": "Campi non ammessi: " + ", ".join(unknown)}


def update_react_utente_status(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    user_id: str,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    manager = get_utenti()
    if not _can(current_user, "utenti.scrivi"):
        return _permission_denied(manager, current_user)
    errors = _reject_unknown(payload, {"active"})
    if "active" not in payload or not isinstance(payload.get("active"), bool):
        errors["active"] = "Indica uno stato account valido."
    if errors:
        return _validation("Controlla i campi evidenziati.", errors, manager=manager, current_user=current_user)
    try:
        target = _target_user(manager, user_id)
    except ValueError as exc:
        return _validation(str(exc), {"id_utente": str(exc)}, manager=manager, current_user=current_user)
    if _role_value(getattr(target, "ruolo", "")) == RuoloUtente.SUPERADMIN.value:
        return _validation("SUPERADMIN non modificabile da questa superficie.", {"permission": "Usa il pannello piattaforma."}, manager=manager, current_user=current_user)
    requested_active = bool(payload["active"])
    if not requested_active and _text(getattr(target, "id", "")) == _current_user_id(current_user):
        return _validation("Non puoi disabilitare la sessione corrente.", {"active": "Auto-disabilitazione non consentita."}, manager=manager, current_user=current_user)
    if not requested_active and _is_last_active_admin(manager, target):
        return _validation("Ultimo amministratore attivo non disabilitabile.", {"active": "Mantieni almeno un amministratore attivo."}, manager=manager, current_user=current_user)
    try:
        updated = manager.aggiorna(target.id, attivo=requested_active)
        _audit(
            manager,
            current_user,
            "utenti.modifica_stato",
            updated,
            {"active": requested_active, "username": getattr(updated, "username", "")},
            ip,
        )
        return _updated_result(manager, current_user, updated, "Stato account aggiornato.")
    except ValueError as exc:
        return _validation(str(exc), {"active": str(exc)}, manager=manager, current_user=current_user)


def update_react_utente_role(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    user_id: str,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    manager = get_utenti()
    if not _can(current_user, "utenti.scrivi"):
        return _permission_denied(manager, current_user)
    errors = _reject_unknown(payload, {"role"})
    target_role = _role_enum(payload.get("role"))
    if target_role is None or target_role == RuoloUtente.SUPERADMIN:
        errors["role"] = "Seleziona un ruolo gestibile valido."
    if errors:
        return _validation("Controlla i campi evidenziati.", errors, manager=manager, current_user=current_user)
    assert target_role is not None
    try:
        target = _target_user(manager, user_id)
    except ValueError as exc:
        return _validation(str(exc), {"id_utente": str(exc)}, manager=manager, current_user=current_user)
    if _role_value(getattr(target, "ruolo", "")) == RuoloUtente.SUPERADMIN.value:
        return _validation("SUPERADMIN non modificabile da questa superficie.", {"permission": "Usa il pannello piattaforma."}, manager=manager, current_user=current_user)
    if _is_last_active_admin(manager, target) and target_role != RuoloUtente.AMMINISTRATORE:
        return _validation("Ultimo amministratore attivo non declassabile.", {"role": "Mantieni almeno un amministratore attivo."}, manager=manager, current_user=current_user)
    if not _role_assignable(current_user, target_role):
        return _validation("Ruolo non assegnabile dalla sessione corrente.", {"role": "Il ruolo richiede permessi superiori a quelli disponibili."}, manager=manager, current_user=current_user)
    try:
        previous_role = _role_value(getattr(target, "ruolo", ""))
        updated = manager.aggiorna(target.id, ruolo=target_role)
        _audit(
            manager,
            current_user,
            "utenti.modifica_ruolo",
            updated,
            {"from": previous_role, "to": target_role.value, "username": getattr(updated, "username", "")},
            ip,
        )
        return _updated_result(manager, current_user, updated, "Ruolo utente aggiornato.")
    except ValueError as exc:
        return _validation(str(exc), {"role": str(exc)}, manager=manager, current_user=current_user)


def reset_react_utente_password(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    user_id: str,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    manager = get_utenti()
    if not _can(current_user, "utenti.scrivi"):
        return _permission_denied(manager, current_user)
    errors = _reject_unknown(payload, {"temporaryPassword", "confirm"})
    temporary_credential = _text(payload.get("temporaryPassword"))
    if len(temporary_credential) < 8:
        errors["temporaryPassword"] = "La credenziale temporanea deve avere almeno 8 caratteri."
    if payload.get("confirm") is not True:
        errors["confirm"] = "Conferma esplicitamente la reimpostazione."
    if errors:
        return _validation("Controlla i campi evidenziati.", errors, manager=manager, current_user=current_user)
    try:
        target = _target_user(manager, user_id)
    except ValueError as exc:
        return _validation(str(exc), {"id_utente": str(exc)}, manager=manager, current_user=current_user)
    if _role_value(getattr(target, "ruolo", "")) == RuoloUtente.SUPERADMIN.value:
        return _validation("SUPERADMIN non modificabile da questa superficie.", {"permission": "Usa il pannello piattaforma."}, manager=manager, current_user=current_user)
    try:
        updated = manager.cambia_password(target.id, temporary_credential, must_change_password=True)
        _audit(
            manager,
            current_user,
            "utenti.reset_password",
            updated,
            {"username": getattr(updated, "username", ""), "one_shot": False},
            ip,
        )
        return _updated_result(manager, current_user, updated, "Credenziale temporanea reimpostata. Il valore non viene restituito dal server.")
    except ValueError as exc:
        return _validation(str(exc), {"temporaryPassword": str(exc)}, manager=manager, current_user=current_user)


def update_react_utente_profile(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    user_id: str,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    manager = get_utenti()
    if not _can(current_user, "utenti.scrivi"):
        return _permission_denied(manager, current_user)
    errors = _reject_unknown(payload, {"name", "nome_completo", "email"})
    name = _text(payload.get("name", payload.get("nome_completo", "")))
    email = _text(payload.get("email"))
    if email and "@" not in email:
        errors["email"] = "Inserisci un indirizzo email valido."
    if errors:
        return _validation("Controlla i campi evidenziati.", errors, manager=manager, current_user=current_user)
    try:
        target = _target_user(manager, user_id)
    except ValueError as exc:
        return _validation(str(exc), {"id_utente": str(exc)}, manager=manager, current_user=current_user)
    if _role_value(getattr(target, "ruolo", "")) == RuoloUtente.SUPERADMIN.value:
        return _validation("SUPERADMIN non modificabile da questa superficie.", {"permission": "Usa il pannello piattaforma."}, manager=manager, current_user=current_user)
    try:
        updated = manager.aggiorna(target.id, nome_completo=name, email=email)
        _audit(
            manager,
            current_user,
            "utenti.modifica_profilo",
            updated,
            {"username": getattr(updated, "username", ""), "fields": ["nome_completo", "email"]},
            ip,
        )
        return _updated_result(manager, current_user, updated, "Profilo utente aggiornato.")
    except ValueError as exc:
        return _validation(str(exc), {"_form": str(exc)}, manager=manager, current_user=current_user)

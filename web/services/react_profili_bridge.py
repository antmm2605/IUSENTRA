"""Bridge operativo per profili, matrice permessi e override utente React."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from pct.auth import DESCRIZIONI_RUOLI, PERMESSI, TUTTI_PERMESSI, RuoloUtente


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tone(value: str) -> str:
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


def _manageable_roles() -> list[RuoloUtente]:
    return [ruolo for ruolo in RuoloUtente if ruolo != RuoloUtente.SUPERADMIN]


def _role_value(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _user_label(user: Any) -> str:
    return (
        _text(getattr(user, "nome_completo", ""))
        or _text(getattr(user, "username", ""))
        or _text(getattr(user, "email", ""))
    )


def _safe_user_record(user: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(user, "id", "")),
        "username": _text(getattr(user, "username", "")),
        "label": _user_label(user),
        "role": _role_value(getattr(user, "ruolo", "")),
        "active": bool(getattr(user, "attivo", False)),
        "hasOverride": bool(getattr(user, "ha_override", False)),
    }


def _role_record(ruolo: RuoloUtente, users: list[Any]) -> dict[str, Any]:
    info = DESCRIZIONI_RUOLI.get(ruolo, {}) or {}
    role_permissions = sorted(set(PERMESSI.get(ruolo, [])))
    return {
        "id": ruolo.value,
        "role": ruolo.value,
        "label": ruolo.value.replace("_", " ").title(),
        "description": _text(info.get("descrizione")),
        "tone": _tone(_text(info.get("colore"))),
        "usersCount": len(users),
        "permissionsCount": len(role_permissions),
        "permissions": role_permissions,
        "users": [_safe_user_record(user) for user in users],
    }


def _permission_records() -> list[dict[str, Any]]:
    return [
        {
            "id": key,
            "category": _text(category),
            "permission": _text(key),
            "label": _text(label),
        }
        for category, key, label in TUTTI_PERMESSI
    ]


def _matrix_rows(roles: list[RuoloUtente]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, key, label in TUTTI_PERMESSI:
        rows.append(
            {
                "id": key,
                "category": _text(category),
                "permission": _text(key),
                "label": _text(label),
                "grants": [
                    {
                        "role": ruolo.value,
                        "granted": key in PERMESSI.get(ruolo, []),
                    }
                    for ruolo in roles
                ],
            }
        )
    return rows


def _permission_sections(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in matrix:
        grouped[_text(row.get("category"))].append(row)
    return [
        {
            "id": f"categoria-{index}",
            "title": category,
            "kind": "permissions",
            "items": [
                {
                    "id": _text(item.get("permission")),
                    "label": _text(item.get("label")),
                    "value": sum(1 for grant in item.get("grants", []) if grant.get("granted")),
                    "note": _text(item.get("permission")),
                    "tone": "primary",
                }
                for item in items
            ],
            "emptyMessage": "Nessun permesso nella categoria.",
        }
        for index, (category, items) in enumerate(grouped.items())
    ]


def _override_record(user: Any) -> dict[str, Any]:
    return {
        **_safe_user_record(user),
        "extraPermissions": sorted({_text(item) for item in (getattr(user, "permessi_extra", []) or []) if _text(item)}),
        "deniedPermissions": sorted({_text(item) for item in (getattr(user, "permessi_negati", []) or []) if _text(item)}),
        "effectivePermissions": sorted({_text(item) for item in (getattr(user, "permessi_effettivi", []) or []) if _text(item)}),
    }


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/profili.json",
    }


def _valid_permission_keys() -> set[str]:
    return {_text(key) for _, key, _ in TUTTI_PERMESSI}


def _normalise_permission_list(raw: Any, field: str, errors: dict[str, str]) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors[field] = "Il campo deve essere una lista di permessi."
        return []
    valid = _valid_permission_keys()
    output: list[str] = []
    for index, item in enumerate(raw):
        key = _text(item)
        if not key:
            continue
        if key not in valid:
            errors[f"{field}.{index}"] = f"Permesso non riconosciuto: {key}."
            continue
        if key not in output:
            output.append(key)
    return output


def _actor_details(user: Any) -> tuple[str, str]:
    return _text(getattr(user, "id", "")), _text(getattr(user, "username", ""))


def build_react_profili_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    manager = get_utenti()
    all_users = list(manager.tutti())
    roles_enum = _manageable_roles()
    users_by_role = {role: list(manager.per_ruolo(role)) for role in roles_enum}
    roles = [_role_record(role, users_by_role.get(role, [])) for role in roles_enum]
    permissions = _permission_records()
    matrix = _matrix_rows(roles_enum)
    override_users = [user for user in all_users if bool(getattr(user, "ha_override", False))]
    can_write = _can(current_user, "utenti.scrivi")

    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "roles": roles,
        "permissions": permissions,
        "matrix": matrix,
        "overrides": [_override_record(user) for user in override_users],
        "actions": {
            "canWrite": can_write,
            "read": "/api/v1/ui/profili",
            "save": "/api/v1/ui/profili",
            "users": "/utenti",
            "rollback": {
                "label": "Percorso di recupero",
                "href": "/profili?_legacy=1",
                "method": "GET",
                "legacy_fallback": True,
            },
        },
        "warnings": [] if can_write else [
            {
                "code": "permesso_scrittura_mancante",
                "message": "Puoi leggere la matrice profili, ma le modifiche richiedono il permesso utenti.scrivi.",
            }
        ],
        "metrics": [
            {
                "id": "ruoli",
                "label": "Ruoli gestibili",
                "value": len(roles),
                "note": "SUPERADMIN escluso dalla gestione studio",
                "tone": "primary",
            },
            {
                "id": "permessi",
                "label": "Permessi censiti",
                "value": len(permissions),
                "note": "Catalogo RBAC reale",
                "tone": "success",
            },
            {
                "id": "override",
                "label": "Utenti con override",
                "value": len(override_users),
                "note": "Eccezioni sui permessi base",
                "tone": "warning" if override_users else "neutral",
            },
            {
                "id": "utenti",
                "label": "Utenti collegati",
                "value": len(all_users),
                "note": "Account nell'archivio corrente",
                "tone": "info",
            },
        ],
        "sections": _permission_sections(matrix),
    }


def update_react_profili_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    if not _can(current_user, "utenti.scrivi"):
        return {
            "ok": False,
            "message": "Permesso utenti.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "updated": None,
        }

    allowed_fields = {"action", "userId", "extraPermissions", "deniedPermissions"}
    unknown_fields = sorted(set(payload) - allowed_fields)
    errors: dict[str, str] = {}
    if unknown_fields:
        errors["payload"] = f"Campi non ammessi: {', '.join(unknown_fields)}."

    action = _text(payload.get("action") or "update_user_override")
    if action not in {"update_user_override"}:
        errors["action"] = "Azione profili non supportata."

    user_id = _text(payload.get("userId"))
    if not user_id:
        errors["userId"] = "Seleziona un utente."

    extra = _normalise_permission_list(payload.get("extraPermissions"), "extraPermissions", errors)
    denied = _normalise_permission_list(payload.get("deniedPermissions"), "deniedPermissions", errors)
    conflicts = sorted(set(extra) & set(denied))
    if conflicts:
        errors["permissions"] = f"Un permesso non puo' essere insieme aggiunto e rimosso: {', '.join(conflicts)}."

    for permission in extra:
        if not _can(current_user, permission):
            errors[f"extraPermissions.{permission}"] = "Non puoi assegnare un permesso che non possiedi."

    manager = get_utenti()
    target = manager.get(user_id) if user_id else None
    if user_id and not target:
        errors["userId"] = "Utente non trovato."
    if target and getattr(target, "ruolo", None) == RuoloUtente.SUPERADMIN:
        errors["userId"] = "L'account SUPERADMIN si gestisce solo dal pannello piattaforma."

    if errors:
        return {
            "ok": False,
            "message": "Controlla i permessi selezionati.",
            "errors": errors,
            "updated": None,
        }

    updated = manager.aggiorna_permessi(user_id, extra, denied)
    actor_id, actor_username = _actor_details(current_user)
    manager.registra_evento(
        "utenti.aggiorna_permessi",
        id_utente=actor_id,
        username=actor_username,
        risorsa_tipo="utente",
        risorsa_id=user_id,
        dettagli=f"extra={extra} negati={denied}",
        ip=ip,
    )

    return {
        "ok": True,
        "message": f"Permessi di {_text(getattr(updated, 'username', 'utente'))} salvati.",
        "errors": {},
        "updated": _override_record(updated),
        "payload": build_react_profili_payload(get_utenti=get_utenti, current_user=current_user),
    }


def build_react_profili_error_payload(message: str = "Profili non disponibili.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "roles": [],
        "permissions": [],
        "matrix": [],
        "overrides": [],
        "actions": {
            "canWrite": False,
            "read": "/api/v1/ui/profili",
            "save": "",
            "users": "/utenti",
            "rollback": {
                "label": "Percorso di recupero",
                "href": "/profili?_legacy=1",
                "method": "GET",
                "legacy_fallback": True,
            },
        },
        "warnings": [{"code": "profili_errore_controllato", "message": message}],
        "metrics": [],
        "sections": [],
    }

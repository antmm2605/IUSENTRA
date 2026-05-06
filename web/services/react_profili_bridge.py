"""Bridge read-only per profili e matrice permessi React."""

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


def _user_label(user: Any) -> str:
    return _text(getattr(user, "nome_completo", "")) or _text(getattr(user, "username", "")) or _text(getattr(user, "email", ""))


def _safe_role_record(ruolo: RuoloUtente, users: list[Any]) -> dict[str, Any]:
    info = DESCRIZIONI_RUOLI.get(ruolo, {}) or {}
    role_permissions = set(PERMESSI.get(ruolo, []))
    return {
        "id": ruolo.value,
        "role": ruolo.value,
        "label": ruolo.value.replace("_", " ").title(),
        "description": _text(info.get("descrizione")),
        "tone": _tone(_text(info.get("colore"))),
        "usersCount": len(users),
        "permissionsCount": len(role_permissions),
        "users": [
            {
                "id": _text(getattr(user, "id", "")),
                "username": _text(getattr(user, "username", "")),
                "label": _user_label(user),
                "active": bool(getattr(user, "attivo", False)),
                "hasOverride": bool(getattr(user, "ha_override", False)),
                "permissionsHref": f"/utenti/{_text(getattr(user, 'id', ''))}/permessi?_legacy=1",
            }
            for user in users
        ],
    }


def _permission_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    roles = _manageable_roles()
    for category, key, label in TUTTI_PERMESSI:
        grants = [
            {
                "role": ruolo.value,
                "granted": key in PERMESSI.get(ruolo, []),
            }
            for ruolo in roles
        ]
        records.append({
            "id": key,
            "category": _text(category),
            "permission": _text(key),
            "label": _text(label),
            "grants": grants,
        })
    return records


def _permission_sections(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[_text(record.get("category"))].append(record)
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


def _override_forms(users: list[Any], can_write: bool) -> list[dict[str, Any]]:
    if not can_write:
        return []
    forms: list[dict[str, Any]] = []
    for user in users:
        if not bool(getattr(user, "ha_override", False)):
            continue
        user_id = _text(getattr(user, "id", ""))
        if not user_id:
            continue
        forms.append({
            "id": f"reset-{user_id}",
            "title": f"Ripristina standard per {_text(getattr(user, 'username', 'utente'))}",
            "description": "POST legacy senza fetch: azzera permessi extra e negati per questo utente.",
            "action": f"/utenti/{user_id}/permessi",
            "method": "POST",
            "csrfField": "_csrf_token",
            "submitLabel": "Ripristina standard",
            "fields": [],
        })
    return forms


def build_react_profili_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    manager = get_utenti()
    all_users = list(manager.tutti())
    users_by_role = {role: list(manager.per_ruolo(role)) for role in _manageable_roles()}
    role_records = [_safe_role_record(role, users_by_role.get(role, [])) for role in _manageable_roles()]
    permission_records = _permission_records()
    override_users = [user for user in all_users if bool(getattr(user, "ha_override", False))]
    can_write = _can(current_user, "utenti.scrivi")

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/profili.json",
        },
        "metrics": [
            {"id": "ruoli", "label": "Ruoli gestibili", "value": len(role_records), "note": "SUPERADMIN escluso dalla gestione studio", "tone": "primary"},
            {"id": "permessi", "label": "Permessi censiti", "value": len(permission_records), "note": "Matrice RBAC reale", "tone": "success"},
            {"id": "override", "label": "Utenti con override", "value": len(override_users), "note": "Permessi extra o rimossi", "tone": "warning" if override_users else "neutral"},
            {"id": "utenti", "label": "Utenti collegati", "value": len(all_users), "note": "Account nel repository corrente", "tone": "info"},
        ],
        "sections": _permission_sections(permission_records),
        "records": {
            "roles": role_records,
            "permissions": permission_records,
            "overrides": [
                {
                    "id": _text(getattr(user, "id", "")),
                    "username": _text(getattr(user, "username", "")),
                    "label": _user_label(user),
                    "role": _text(getattr(getattr(user, "ruolo", ""), "value", getattr(user, "ruolo", ""))),
                    "extraPermissions": list(getattr(user, "permessi_extra", []) or []),
                    "deniedPermissions": list(getattr(user, "permessi_negati", []) or []),
                    "permissionsHref": f"/utenti/{_text(getattr(user, 'id', ''))}/permessi?_legacy=1",
                }
                for user in override_users
            ],
        },
        "actions": [
            {"id": "profili", "label": "Aggiorna matrice", "href": "/profili", "method": "GET", "tone": "primary"},
            {"id": "utenti", "label": "Vai agli utenti", "href": "/utenti", "method": "GET", "tone": "neutral"},
        ],
        "forms": _override_forms(override_users, can_write),
        "warnings": [] if can_write else [{
            "code": "scritture_legacy_non_disponibili",
            "message": "Le modifiche ai permessi richiedono utenti.scrivi e restano sulle route legacy.",
        }],
    }


def build_react_profili_error_payload(message: str = "Profili non disponibili.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/profili.json",
        },
        "metrics": [],
        "sections": [],
        "records": {"roles": [], "permissions": [], "overrides": []},
        "actions": [{"id": "legacy", "label": "Apri profili legacy", "href": "/profili?_legacy=1", "method": "GET", "tone": "neutral"}],
        "forms": [],
        "warnings": [{"code": "profili_errore_controllato", "message": message}],
    }

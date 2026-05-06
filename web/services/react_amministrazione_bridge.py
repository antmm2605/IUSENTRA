"""Bridge read-only per lo hub React Amministrazione."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from pct.auth import PERMESSI, TUTTI_PERMESSI, RuoloUtente


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _safe_stats(manager: Any) -> dict[str, Any]:
    func = getattr(manager, "statistiche", None)
    if callable(func):
        data = func()
        return data if isinstance(data, dict) else {}
    return {}


def _all_users(manager: Any) -> list[Any]:
    func = getattr(manager, "tutti", None)
    if not callable(func):
        return []
    return list(func())


def _metric(mid: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _role_label(role: str) -> str:
    return role.replace("_", " ").title() if role else "Non indicato"


def _permission_sections() -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for category, key, label in TUTTI_PERMESSI:
        grouped[_text(category)].append((_text(key), _text(label)))
    roles = [role for role in RuoloUtente if role != RuoloUtente.SUPERADMIN]
    return [
        _section(
            f"categoria-{index}",
            category,
            "permissions",
            [
                _item(
                    key,
                    label,
                    sum(1 for role in roles if key in PERMESSI.get(role, [])),
                    key,
                    "primary",
                )
                for key, label in rows
            ],
            "Nessun permesso nella categoria.",
        )
        for index, (category, rows) in enumerate(grouped.items())
    ]


def _module_records() -> list[dict[str, Any]]:
    return [
        {"id": "utenti", "label": "Utenti", "href": "/utenti", "status": "React full", "tone": "success", "note": "Elenco e creazione GET gia' migrati; POST legacy."},
        {"id": "profili", "label": "Profili", "href": "/profili", "status": "React full", "tone": "success", "note": "Matrice ruoli e override in React con form legacy dove previsti."},
        {"id": "audit", "label": "Audit", "href": "/audit", "status": "React full", "tone": "success", "note": "Registro eventi amministrativi migrato."},
        {"id": "registro", "label": "Registro attivita", "href": "/registro-attivita", "status": "React full", "tone": "success", "note": "Alias operativo al registro audit."},
        {"id": "database", "label": "Database", "href": "/admin/database", "status": "React full", "tone": "success", "note": "Console tecnica gia' migrata."},
        {"id": "privacy", "label": "Privacy registro", "href": "/privacy/registro", "status": "React full", "tone": "success", "note": "Registro GDPR su superficie React."},
    ]


def build_react_amministrazione_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    manager = get_utenti()
    users = _all_users(manager)
    stats = _safe_stats(manager)
    role_counter = Counter(_enum(getattr(user, "ruolo", "")) for user in users)
    active_count = int(stats.get("attivi", 0) or 0)
    override_count = int(stats.get("con_override", 0) or 0)
    audit_count = int(stats.get("totale_eventi_audit", 0) or 0)
    inactive_count = max(len(users) - active_count, 0)
    two_factor_count = sum(1 for user in users if bool(getattr(user, "totp_attivato", False)))

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/amministrazione.json",
        },
        "metrics": [
            _metric("utenti", "Utenti", int(stats.get("totale_utenti", len(users)) or 0), "Account nel repository utenti", "primary"),
            _metric("attivi", "Utenti attivi", active_count, "Operatori abilitati", "success" if active_count else "warning"),
            _metric("profili", "Profili usati", len([role for role, count in role_counter.items() if role and count]), "Ruoli con almeno un operatore", "info"),
            _metric("audit", "Eventi audit", audit_count, "Eventi amministrativi registrati", "neutral"),
            _metric("override", "Override permessi", override_count, "Utenti con regole personalizzate", "warning" if override_count else "neutral"),
        ],
        "sections": [
            _section(
                "ruoli",
                "Distribuzione ruoli",
                "roles",
                [
                    _item(f"ruolo-{role}", _role_label(role), count, "Utenti per ruolo", "primary" if count else "neutral")
                    for role, count in sorted(role_counter.items())
                    if role
                ],
                "Nessun ruolo rilevato.",
            ),
            _section(
                "sicurezza",
                "Stato sicurezza aggregato",
                "security",
                [
                    _item("attivi", "Account attivi", active_count, "Utenti abilitati", "success" if active_count else "warning"),
                    _item("non-attivi", "Account non attivi", inactive_count, "Utenti non abilitati", "warning" if inactive_count else "neutral"),
                    _item("secondo-fattore", "Secondo fattore", two_factor_count, "Operatori con verifica aggiuntiva", "success" if two_factor_count else "neutral"),
                    _item("override", "Regole personalizzate", override_count, "Permessi extra o rimossi", "warning" if override_count else "neutral"),
                ],
                "Nessun indicatore disponibile.",
            ),
            *_permission_sections(),
        ],
        "records": _module_records(),
        "actions": [
            _action("utenti", "Apri utenti", "/utenti", "primary"),
            _action("profili", "Apri profili", "/profili", "neutral"),
            _action("audit", "Apri audit", "/audit", "neutral"),
            _action("registro", "Registro attivita", "/registro-attivita", "neutral"),
            _action("database", "Database", "/admin/database", "neutral"),
            _action("privacy", "Privacy registro", "/privacy/registro", "neutral"),
        ],
        "forms": [],
        "warnings": [
            {
                "code": "scritture_legacy",
                "message": "Modifiche utenti, profili e permessi restano sui POST legacy auditati.",
            }
        ],
        "currentUser": {
            "id": _text(getattr(current_user, "id", "")),
            "username": _text(getattr(current_user, "username", "")),
            "role": _enum(getattr(current_user, "ruolo", "")),
        },
    }


def build_react_amministrazione_error_payload(message: str = "Amministrazione non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/amministrazione.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("utenti", "Apri utenti", "/utenti", "neutral")],
        "forms": [],
        "warnings": [{"code": "amministrazione_errore_controllato", "message": message}],
        "currentUser": {},
    }

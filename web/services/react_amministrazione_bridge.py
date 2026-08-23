"""Dati consultabili per la pagina Amministrazione."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from pct import __version__
from pct.auth import PERMESSI, TUTTI_PERMESSI, RuoloUtente
from pct.capability_truth_registry import (
    build_capability_truth_registry,
    build_product_readiness_navigation,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


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


def _role_label(role: str) -> str:
    return role.replace("_", " ").title() if role else "Non indicato"


def _metric(metric_id: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": metric_id, "label": label, "value": value, "note": note, "tone": tone}


def _section_item(item_id: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": item_id, "label": label, "value": value, "note": note, "tone": tone}


def _section(section_id: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": section_id, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _module(module_id: str, label: str, href: str, area: str, note: str, *, status: str = "operativo", tone: str = "success") -> dict[str, Any]:
    return {
        "id": module_id,
        "label": label,
        "href": href,
        "area": area,
        "status": status,
        "tone": tone,
        "note": note,
    }


def _legacy(module_id: str, label: str, href: str, area: str, note: str) -> dict[str, Any]:
    return _module(module_id, label, href, area, note, status="area protetta", tone="warning")


def _action(action_id: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": action_id, "label": label, "href": href, "method": "GET", "tone": tone}


def _readiness_action() -> dict[str, Any]:
    navigation = build_product_readiness_navigation()
    return _action(
        navigation["id"],
        navigation["label"],
        navigation["href"],
        navigation["tone"],
    )


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "none",
        "route_owner": "react_shell",
        "operational": True,
        "sensitive_settings": "legacy_protected",
        "secrets_exposed": False,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/amministrazione.json",
    }


def _readiness_contracts() -> dict[str, Any]:
    return {
        "writes": "none",
        "sourceOfTruth": "catalogo Python versionato",
        "tenantScope": "nessun dato tenant nel payload",
        "providerCalls": False,
        "runtimeScans": False,
        "secretsExposed": False,
    }


def _permission_sections() -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for category, key, label in TUTTI_PERMESSI:
        grouped[_text(category)].append((_text(key), _text(label)))
    roles = [role for role in RuoloUtente if role != RuoloUtente.SUPERADMIN]
    sections: list[dict[str, Any]] = []
    for index, (category, rows) in enumerate(grouped.items()):
        sections.append(
            _section(
                f"permessi-{index}",
                category,
                "permissions",
                [
                    _section_item(
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
        )
    return sections


def build_react_amministrazione_payload(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    manager = get_utenti()
    users = _all_users(manager)
    stats = _safe_stats(manager)
    role_counter = Counter(_enum(getattr(user, "ruolo", "")) for user in users)
    total_users = int(stats.get("totale_utenti", len(users)) or 0)
    active_count = int(stats.get("attivi", 0) or 0)
    override_count = int(stats.get("con_override", 0) or 0)
    audit_count = int(stats.get("totale_eventi_audit", 0) or 0)
    inactive_count = max(total_users - active_count, 0)
    two_factor_count = sum(1 for user in users if bool(getattr(user, "totp_attivato", False)))
    operational_routes = [
        _module("utenti", "Utenti", "/utenti", "utenti", "Lista utenti e stato account operativo."),
        _module("utenti-nuovo", "Nuovo utente", "/utenti/nuovo", "utenti", "Creazione utente con validazioni e tracciamento."),
        _module("profili", "Profili", "/profili", "permessi", "Matrice ruoli, categorie e permessi personalizzati."),
        _module("audit", "Registro attivita", "/audit", "sicurezza", "Eventi di controllo e dettaglio consultabile."),
        _module("registro-attivita", "Registro attivita", "/registro-attivita", "sicurezza", "Superficie operativa del registro audit."),
        _module(
            "import-pratiche",
            "Importa pratiche",
            "/importa-pratiche",
            "fascicoli",
            "Percorso guidato per acquisire pratiche, ATTI, EMAILS e anagrafiche del cliente.",
        ),
        _module("backup", "Backup", "/backup", "governance", "Controllo backup disponibile nello stesso ambiente operativo."),
    ]
    if _can(current_user, "admin.configura"):
        operational_routes.append(
            _module(
                "consistenza-dati",
                "Coerenza dati",
                "/amministrazione?tab=consistenza-dati",
                "governance",
                "Lettura SQL dei domini P0, outbox e anomalie senza usare mirror JSON.",
            )
        )
    legacy_routes = [
        _legacy("impostazioni", "Impostazioni", "/impostazioni", "impostazioni sensibili", "Configurazioni riservate gestite nel percorso dedicato."),
        _legacy("impostazioni-studio", "Impostazioni studio", "/impostazioni-studio", "impostazioni sensibili", "Parametri studio e canali restano protetti."),
        _legacy("calendario", "Impostazioni calendario", "/impostazioni/calendario", "impostazioni sensibili", "Collegamenti calendario e sincronizzazioni restano protetti."),
        _legacy("pagamenti", "Impostazioni pagamenti", "/impostazioni/pagamenti", "impostazioni sensibili", "Canali di pagamento e conferme restano protetti."),
        _legacy("sync-calendari", "Sincronizzazione calendari", "/sincronizzazione-calendari", "impostazioni sensibili", "Pianificazione calendario protetta nel percorso dedicato."),
    ]
    security = {
        "canRead": _can(current_user, "utenti.leggi"),
        "canWriteUsers": _can(current_user, "utenti.scrivi"),
        "canReadAudit": _can(current_user, "audit.leggi"),
        "canConfigureAdmin": _can(current_user, "admin.configura"),
        "activeAccounts": active_count,
        "inactiveAccounts": inactive_count,
        "twoFactorEnabled": two_factor_count,
        "permissionOverrides": override_count,
        "status": "attenzione" if inactive_count or override_count else "presidiato",
        "tone": "warning" if inactive_count or override_count else "success",
    }
    users_summary = {
        "total": total_users,
        "active": active_count,
        "inactive": inactive_count,
        "twoFactorEnabled": two_factor_count,
        "permissionOverrides": override_count,
    }
    profiles_summary = {
        "roles": [
            {"id": f"ruolo-{role}", "label": _role_label(role), "count": count}
            for role, count in sorted(role_counter.items())
            if role
        ],
        "permissionCategories": len({category for category, _key, _label in TUTTI_PERMESSI}),
        "managedRoles": len([role for role in RuoloUtente if role != RuoloUtente.SUPERADMIN]),
    }
    audit_summary = {
        "events": audit_count,
        "canRead": _can(current_user, "audit.leggi"),
        "status": "visibile" if _can(current_user, "audit.leggi") else "permesso richiesto",
    }
    database_summary = {
        "status": "modulo separato",
        "href": "/admin/database",
        "note": "La manutenzione dati resta disponibile come azione amministrativa secondaria.",
    }
    warnings = [
        {
            "code": "impostazioni_legacy_protette",
            "message": "Impostazioni, calendario, pagamenti e sincronizzazioni restano in area protetta.",
        }
    ]
    if not _can(current_user, "audit.leggi"):
        warnings.append({"code": "permesso_audit_mancante", "message": "L'utente corrente non ha il permesso audit.leggi."})
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "security": security,
        "users": users_summary,
        "profiles": profiles_summary,
        "audit": audit_summary,
        "database": database_summary,
        "modules": operational_routes + legacy_routes,
        "operational_routes": operational_routes,
        "legacy_routes": legacy_routes,
        "metrics": [
            _metric("utenti", "Utenti", total_users, "Account nell'archivio utenti", "primary"),
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
                    _section_item(f"ruolo-{role}", _role_label(role), count, "Utenti per ruolo", "primary" if count else "neutral")
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
                    _section_item("attivi", "Account attivi", active_count, "Utenti abilitati", "success" if active_count else "warning"),
                    _section_item("non-attivi", "Account non attivi", inactive_count, "Utenti non abilitati", "warning" if inactive_count else "neutral"),
                    _section_item("secondo-fattore", "Secondo fattore", two_factor_count, "Operatori con verifica aggiuntiva", "success" if two_factor_count else "neutral"),
                    _section_item("override", "Regole personalizzate", override_count, "Permessi extra o rimossi", "warning" if override_count else "neutral"),
                ],
                "Nessun indicatore disponibile.",
            ),
            *_permission_sections(),
        ],
        "actions": [
            _readiness_action(),
            *(
                [_action("consistenza-dati", "Apri coerenza dati", "/amministrazione?tab=consistenza-dati", "neutral")]
                if _can(current_user, "admin.configura")
                else []
            ),
            _action("utenti", "Apri utenti", "/utenti", "primary"),
            _action("profili", "Apri profili", "/profili", "primary"),
            _action("audit", "Apri audit", "/audit", "neutral"),
            _action("registro", "Registro attivita", "/registro-attivita", "neutral"),
            _action("import-pratiche", "Importa pratiche", "/importa-pratiche", "primary"),
            _action("backup", "Apri backup", "/backup", "neutral"),
        ],
        "warnings": warnings,
        "currentUser": {
            "id": _text(getattr(current_user, "id", "")),
            "username": _text(getattr(current_user, "username", "")),
            "role": _enum(getattr(current_user, "ruolo", "")),
        },
    }


def build_product_readiness_payload(*, current_user: Any) -> dict[str, Any]:
    """Payload read-only della prontezza prodotto per l'area React studio."""

    payload = build_capability_truth_registry(application_version=__version__)
    payload["contracts"] = _readiness_contracts()
    payload["currentUser"] = {
        "id": _text(getattr(current_user, "id", "")),
        "username": _text(getattr(current_user, "username", "")),
        "role": _enum(getattr(current_user, "ruolo", "")),
    }
    return payload


def build_product_readiness_error_payload(message: str = "Prontezza prodotto non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "generatedAt": "",
        "registryVersion": "",
        "applicationVersion": __version__,
        "scope": "P0 — registro di prontezza",
        "contracts": _readiness_contracts(),
        "summary": {"total": 0, "verified": 0, "partial": 0, "pending": 0, "blocked": 0},
        "capabilities": [],
        "navigation": build_product_readiness_navigation(),
        "warnings": [{"code": "prontezza_prodotto_errore_controllato", "message": message}],
        "currentUser": {},
    }


def build_react_amministrazione_error_payload(message: str = "Amministrazione non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "security": {},
        "users": {},
        "profiles": {},
        "audit": {},
        "database": {},
        "modules": [],
        "operational_routes": [],
        "legacy_routes": [],
        "metrics": [],
        "sections": [],
        "actions": [],
        "warnings": [{"code": "amministrazione_errore_controllato", "message": message}],
        "currentUser": {},
    }

"""Bridge read-only per lo hub React Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _count(loader: Callable[[], Any], label: str, warnings: list[dict[str, str]]) -> int:
    try:
        manager = loader()
        stats = getattr(manager, "statistiche", None)
        if callable(stats):
            data = stats()
            if isinstance(data, dict):
                for key in ("totale", "totale_utenti", "attivi"):
                    if key in data:
                        return int(data.get(key) or 0)
        for name in ("tutti", "tutte", "lista"):
            func = getattr(manager, name, None)
            if callable(func):
                try:
                    return len(list(func()))
                except TypeError:
                    return len(list(func(False)))
    except Exception as exc:
        warnings.append({
            "code": f"{label}_non_disponibile",
            "message": f"Sorgente {label} non disponibile: {type(exc).__name__}.",
        })
    return 0


def _stats(loader: Callable[[], Any], label: str, warnings: list[dict[str, str]]) -> dict[str, Any]:
    try:
        manager = loader()
        func = getattr(manager, "statistiche", None)
        if callable(func):
            value = func()
            return value if isinstance(value, dict) else {}
    except Exception as exc:
        warnings.append({
            "code": f"{label}_non_disponibile",
            "message": f"Sorgente {label} non disponibile: {type(exc).__name__}.",
        })
    return {}


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _profile(user: Any) -> dict[str, Any]:
    role = getattr(user, "ruolo", "")
    return {
        "id": _text(getattr(user, "id", "")),
        "username": _text(getattr(user, "username", "")),
        "label": _text(getattr(user, "nome_completo", "")) or _text(getattr(user, "email", "")) or _text(getattr(user, "username", "")),
        "role": _enum(role),
        "active": bool(getattr(user, "attivo", False)),
    }


def _metric(mid: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _module_record(rid: str, label: str, href: str, migrated: bool, note: str) -> dict[str, Any]:
    return {
        "id": rid,
        "label": label,
        "href": href,
        "status": "React full" if migrated else "Legacy operativo",
        "tone": "success" if migrated else "warning",
        "note": note,
    }


def build_react_studio_payload(
    *,
    current_user: Any,
    studio_label: str,
    get_utenti: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    utenti_stats = _stats(get_utenti, "utenti", warnings)
    scadenze_stats = _stats(get_scadenziario, "scadenziario", warnings)
    clienti_count = _count(get_clienti, "clienti", warnings)
    fascicoli_count = _count(get_fascicoli, "fascicoli", warnings)
    active_users = int(utenti_stats.get("attivi", 0) or 0)
    urgent_terms = int(scadenze_stats.get("critiche", 0) or 0) + int(scadenze_stats.get("alte", 0) or 0)
    settings_href = "/impostazioni?_legacy=1"

    warnings.append({
        "code": "impostazioni_legacy",
        "message": "Impostazioni riservate, calendari e pagamenti restano sulle route legacy auditabili.",
    })

    records = [
        _module_record("backup", "Backup", "/backup", True, "Registro e stato copie in React; operazioni tecniche legacy."),
        _module_record("sito", "Sito Studio", "/sito-studio", True, "Dashboard contenuti e contatti gia' migrata."),
        _module_record("statistiche", "Statistiche", "/statistiche", True, "KPI e report letti dai repository reali."),
        _module_record("utenti", "Utenti", "/utenti", True, "Elenco operatori e nuovo utente gia' migrati."),
        _module_record("profili", "Profili", "/profili", True, "Matrice ruoli e permessi gia' migrata."),
        _module_record("audit", "Audit", "/audit", True, "Registro eventi amministrativi in React."),
        _module_record("registro", "Privacy registro", "/privacy/registro", True, "Registro GDPR esposto come superficie React."),
        _module_record("impostazioni", "Impostazioni sensibili", settings_href, False, "Configurazioni riservate preservate nel legacy."),
    ]

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/studio.json",
        },
        "metrics": [
            _metric("fascicoli", "Fascicoli", fascicoli_count, "Conteggio dal repository fascicoli", "primary"),
            _metric("clienti", "Clienti", clienti_count, "Anagrafica clienti reale", "info"),
            _metric("utenti", "Operatori attivi", active_users, "Account abilitati nel repository utenti", "success" if active_users else "warning"),
            _metric("presidi", "Scadenze prioritarie", urgent_terms, "Critiche e alte nello scadenziario", "warning" if urgent_terms else "neutral"),
        ],
        "sections": [
            _section(
                "profilo",
                "Profilo sessione",
                "session",
                [
                    _item("utente", "Operatore", _profile(current_user).get("label") or "non indicato", _profile(current_user).get("username", ""), "primary"),
                    _item("ruolo", "Ruolo", _profile(current_user).get("role") or "non indicato", "Profilo letto dalla sessione Flask", "neutral"),
                    _item("utenti", "Gestione utenti", "abilitata" if _can(current_user, "utenti.leggi") else "non abilitata", "Lettura hub amministrativi", "success" if _can(current_user, "utenti.leggi") else "warning"),
                    _item("audit", "Audit", "abilitato" if _can(current_user, "audit.leggi") else "non abilitato", "Registro attivita", "success" if _can(current_user, "audit.leggi") else "warning"),
                ],
                "Profilo sessione non disponibile.",
            ),
            _section(
                "canali",
                "Canali e impostazioni",
                "safe-status",
                [
                    _item("pec", "PEC", "gestione legacy", "Nessuna configurazione esposta nel payload React", "warning"),
                    _item("firma", "Firma digitale", "gestione legacy", "Flusso locale e configurazioni riservate restano nel legacy", "warning"),
                    _item("calendari", "Calendari", "gestione legacy", "Sincronizzazione e feed restano nel legacy", "warning"),
                    _item("pagamenti", "Pagamenti", "gestione legacy", "Provider e webhook restano nel legacy", "warning"),
                ],
                "Nessun canale esposto in React.",
            ),
        ],
        "records": records,
        "actions": [
            _action("backup", "Apri backup", "/backup", "primary"),
            _action("sito", "Apri Sito Studio", "/sito-studio", "neutral"),
            _action("statistiche", "Apri statistiche", "/statistiche", "neutral"),
            _action("utenti", "Apri utenti", "/utenti", "neutral"),
            _action("profili", "Apri profili", "/profili", "neutral"),
            _action("audit", "Apri audit", "/audit", "neutral"),
            _action("impostazioni", "Impostazioni legacy", settings_href, "warning"),
        ],
        "forms": [],
        "warnings": warnings,
        "studio": {
            "name": _text(studio_label) or "Studio",
            "profile": _profile(current_user),
        },
    }


def build_react_studio_error_payload(message: str = "Studio non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/studio.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("impostazioni", "Impostazioni legacy", "/impostazioni?_legacy=1", "warning")],
        "forms": [],
        "warnings": [{"code": "studio_errore_controllato", "message": message}],
        "studio": {"name": "Studio", "profile": {}},
    }

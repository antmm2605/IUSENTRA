"""Payload operativo read-only per la dashboard React Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


Loader = Callable[[], Any]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _profile(user: Any) -> dict[str, Any]:
    role = getattr(user, "ruolo", "")
    label = (
        _text(getattr(user, "nome_completo", ""))
        or _text(getattr(user, "email", ""))
        or _text(getattr(user, "username", ""))
    )
    return {
        "id": _text(getattr(user, "id", "")),
        "username": _text(getattr(user, "username", "")),
        "label": label,
        "role": _enum(role),
        "active": bool(getattr(user, "attivo", False)),
        "permissions": {
            "utenti.leggi": _can(user, "utenti.leggi"),
            "audit.leggi": _can(user, "audit.leggi"),
            "backup.leggi": _can(user, "backup.leggi"),
            "fatturazione.leggi": _can(user, "fatturazione.leggi"),
            "admin.configura": _can(user, "admin.configura"),
        },
    }


def _safe_stats(loader: Loader | None, label: str, warnings: list[dict[str, str]]) -> dict[str, Any]:
    if loader is None:
        warnings.append({"code": f"{label}_assente", "message": f"Sorgente {label} non configurata nel runtime."})
        return {}
    try:
        manager = loader()
        stats = getattr(manager, "statistiche", None)
        if callable(stats):
            data = stats()
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        warnings.append({"code": f"{label}_non_disponibile", "message": f"Sorgente {label} non disponibile: {type(exc).__name__}."})
    return {}


def _safe_count(loader: Loader | None, label: str, warnings: list[dict[str, str]]) -> int:
    if loader is None:
        warnings.append({"code": f"{label}_assente", "message": f"Sorgente {label} non configurata nel runtime."})
        return 0
    stats = _safe_stats(loader, label, warnings)
    for key in ("totale", "totale_utenti", "attivi", "totale_fascicoli"):
        if key in stats:
            try:
                return int(stats.get(key) or 0)
            except (TypeError, ValueError):
                return 0
    try:
        manager = loader()
        for name in ("tutti", "tutte", "lista", "elenco"):
            func = getattr(manager, name, None)
            if not callable(func):
                continue
            try:
                return len(list(func()))
            except TypeError:
                return len(list(func(False)))
    except Exception as exc:
        warnings.append({"code": f"{label}_conteggio_non_disponibile", "message": f"Conteggio {label} non disponibile: {type(exc).__name__}."})
    return 0


def _site_status(warnings: list[dict[str, str]]) -> dict[str, Any]:
    try:
        from web.services.studio_site_runtime import build_studio_site_dashboard_payload

        payload = build_studio_site_dashboard_payload()
        site = payload.get("site") or {}
        stats = payload.get("stats") or {}
        return {
            "id": "sito-studio",
            "label": "Sito Studio",
            "status": "pubblicato" if bool(site.get("is_published")) else "bozza",
            "tone": "success" if bool(site.get("is_published")) else "warning",
            "note": "Dashboard e contatti sono gestiti in React; builder e pubblicazione restano protetti.",
            "href": "/sito-studio",
            "metrics": {
                "pagine": int(stats.get("pages") or 0),
                "contatti": int(stats.get("contact_submissions") or 0),
                "prenotazioni_in_attesa": int(stats.get("pending_booking_requests") or 0),
            },
        }
    except Exception as exc:
        warnings.append({"code": "sito_studio_non_disponibile", "message": f"Stato Sito Studio non disponibile: {type(exc).__name__}."})
        return {
            "id": "sito-studio",
            "label": "Sito Studio",
            "status": "non disponibile",
            "tone": "warning",
            "note": "Il runtime sito non ha restituito aggregati sicuri.",
            "href": "/sito-studio",
            "metrics": {},
        }


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
    return _module(module_id, label, href, area, note, status="legacy protetto", tone="warning")


def _health(health_id: str, label: str, status: str, tone: str, note: str, value: Any = "") -> dict[str, Any]:
    return {
        "id": health_id,
        "label": label,
        "status": status,
        "tone": tone,
        "note": note,
        "value": value,
    }


def _metric(metric_id: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": metric_id, "label": label, "value": value, "note": note, "tone": tone}


def _action(action_id: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": action_id, "label": label, "href": href, "method": "GET", "tone": tone}


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "none",
        "route_owner": "react_shell",
        "operational": True,
        "sensitive_settings": "legacy_protected",
        "secrets_exposed": False,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/studio.json",
    }


def build_react_studio_payload(
    *,
    current_user: Any,
    studio_label: str,
    get_utenti: Loader,
    get_clienti: Loader,
    get_fascicoli: Loader,
    get_scadenziario: Loader,
    get_backup: Loader | None = None,
    get_fatturazione: Loader | None = None,
    get_preventivi: Loader | None = None,
    get_pagamenti: Loader | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    utenti_stats = _safe_stats(get_utenti, "utenti", warnings)
    scadenze_stats = _safe_stats(get_scadenziario, "scadenziario", warnings)
    backup_stats = _safe_stats(get_backup, "backup", warnings) if get_backup is not None else {}
    fatturazione_stats = _safe_stats(get_fatturazione, "fatturazione", warnings) if get_fatturazione is not None else {}
    preventivi_stats = _safe_stats(get_preventivi, "preventivi", warnings) if get_preventivi is not None else {}
    pagamenti_stats = _safe_stats(get_pagamenti, "pagamenti", warnings) if get_pagamenti is not None else {}
    clienti_count = _safe_count(get_clienti, "clienti", warnings)
    fascicoli_count = _safe_count(get_fascicoli, "fascicoli", warnings)
    active_users = int(utenti_stats.get("attivi", 0) or 0)
    urgent_terms = int(scadenze_stats.get("critiche", 0) or 0) + int(scadenze_stats.get("alte", 0) or 0)
    site_status = _site_status(warnings)
    backup_total = int(backup_stats.get("totale", backup_stats.get("totale_backup", 0)) or 0)
    open_quotes = int(preventivi_stats.get("aperti", preventivi_stats.get("in_attesa", 0)) or 0)
    unpaid = int(fatturazione_stats.get("non_pagati", fatturazione_stats.get("scadute", 0)) or 0)
    pending_payments = int(pagamenti_stats.get("in_attesa", pagamenti_stats.get("pendenti", 0)) or 0)

    operational_routes = [
        _module("utenti", "Utenti", "/utenti", "amministrazione", "Elenco e creazione utenti in React operativo."),
        _module("utenti-nuovo", "Nuovo utente", "/utenti/nuovo", "amministrazione", "Creazione utente JSON con permessi e audit."),
        _module("profili", "Profili", "/profili", "amministrazione", "Matrice ruoli e permessi in React operativo."),
        _module("audit", "Audit", "/audit", "sicurezza", "Registro audit consultabile via API JSON."),
        _module("registro-attivita", "Registro attivita", "/registro-attivita", "sicurezza", "Alias operativo del registro audit."),
        _module("backup", "Backup", "/backup", "governance", "Stato backup e verifiche in React operativo."),
        _module("fatturazione", "Fatturazione", "/fatturazione", "economico", "Documenti economici su dashboard React."),
        _module("fatturazione-nuova", "Nuova fattura", "/fatturazione/nuova", "economico", "Creazione fattura JSON già migrata."),
        _module("incassi", "Incassi e pagamenti", "/incassi-pagamenti", "economico", "Incassi, pagamenti e link pagamento via API JSON."),
        _module("preventivi", "Preventivi", "/preventivi", "mandato", "Lista preventivi e stati reali."),
        _module("preventivi-nuovo", "Nuovo preventivo", "/preventivi/nuovo", "mandato", "Creazione preventivo JSON già migrata."),
        _module("conferimento", "Nuovo conferimento", "/preventivi/conferimento/nuovo", "mandato", "Workflow conferimento già servito dalla shell."),
        _module("compensi", "Compensi forensi", "/compensi-forensi", "economico", "Calcolo compensi via API JSON."),
        _module("tariffario", "Tariffario", "/tariffario", "economico", "Motore tariffario operativo in React."),
        _module("sito-studio", "Sito Studio", "/sito-studio", "comunicazione", "Dashboard e contatti sito in React operativo."),
        _module("sito-contatti", "Contatti Sito Studio", "/sito-studio/contatti", "comunicazione", "Richieste contatto e prenotazioni su API JSON."),
    ]
    legacy_routes = [
        _legacy("impostazioni", "Impostazioni", "/impostazioni", "impostazioni sensibili", "Configurazioni riservate preservate nel legacy protetto."),
        _legacy("impostazioni-studio", "Impostazioni studio", "/impostazioni-studio", "impostazioni sensibili", "Dati configurativi dello studio non scritti da questa dashboard."),
        _legacy("calendario", "Impostazioni calendario", "/impostazioni/calendario", "impostazioni sensibili", "OAuth e feed calendario restano nel legacy protetto."),
        _legacy("pagamenti", "Impostazioni pagamenti", "/impostazioni/pagamenti", "impostazioni sensibili", "Provider e webhook non sono esposti nel payload React."),
        _legacy("sync-calendari", "Sincronizzazione calendari", "/sincronizzazione-calendari", "impostazioni sensibili", "Operazioni calendario protette fuori dallo hub."),
        _legacy("telematico", "Servizi telematici", "/servizi-telematici", "telematico", "Portali, firma e deposito restano su percorsi protetti."),
        _legacy("builder", "Builder Sito Studio", "/sito-studio/builder", "sito studio", "Editor e pubblicazione avanzata restano legacy protetti."),
    ]
    health = [
        _health("backup", "Backup", "presente" if backup_total else "da verificare", "success" if backup_total else "warning", "Conteggio registro backup sicuro.", backup_total),
        _health("sito", "Sito Studio", site_status["status"], site_status["tone"], site_status["note"], site_status.get("metrics", {}).get("contatti", "")),
        _health("utenti", "Utenti e profili", "presidiato" if active_users else "da verificare", "success" if active_users else "warning", "Account attivi letti dal repository utenti.", active_users),
        _health("audit", "Audit", "abilitato" if _can(current_user, "audit.leggi") else "permesso mancante", "success" if _can(current_user, "audit.leggi") else "warning", "Accesso registro eventi amministrativi."),
        _health("economico", "Economico e mandato", "attenzione" if (unpaid or pending_payments or open_quotes) else "allineato", "warning" if (unpaid or pending_payments or open_quotes) else "success", "Aggregati fatturazione, preventivi e pagamenti.", unpaid + pending_payments + open_quotes),
        _health("documentale", "Fascicoli e scadenze", "attenzione" if urgent_terms else "allineato", "warning" if urgent_terms else "success", "Fascicoli e scadenze prioritarie reali.", urgent_terms),
    ]
    warnings.extend(
        [
            {
                "code": "impostazioni_legacy_protette",
                "message": "Impostazioni riservate, calendari, pagamenti, PEC, firma digitale e provider restano nel legacy protetto.",
            },
            {
                "code": "telematico_legacy_protetto",
                "message": "PST, PDP, PAT, firma e portali telematici restano fuori da questa dashboard React.",
            },
        ]
    )
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "studio": {"name": _text(studio_label) or "Studio", "public_site": site_status},
        "session": _profile(current_user),
        "modules": operational_routes + legacy_routes,
        "operational_routes": operational_routes,
        "legacy_routes": legacy_routes,
        "health": health,
        "metrics": [
            _metric("fascicoli", "Fascicoli", fascicoli_count, "Conteggio dal repository fascicoli", "primary"),
            _metric("clienti", "Clienti", clienti_count, "Anagrafica clienti reale", "info"),
            _metric("utenti", "Operatori attivi", active_users, "Account abilitati nel repository utenti", "success" if active_users else "warning"),
            _metric("scadenze", "Scadenze prioritarie", urgent_terms, "Critiche e alte nello scadenziario", "warning" if urgent_terms else "neutral"),
            _metric("backup", "Backup registrati", backup_total, "Registro backup sicuro", "success" if backup_total else "warning"),
            _metric("economico", "Presidi economici", unpaid + pending_payments + open_quotes, "Scoperti, pagamenti pendenti e preventivi aperti", "warning" if (unpaid or pending_payments or open_quotes) else "success"),
        ],
        "actions": [
            _action("backup", "Apri backup", "/backup", "primary"),
            _action("contatti", "Apri contatti sito", "/sito-studio/contatti", "primary"),
            _action("utenti", "Apri utenti", "/utenti", "neutral"),
            _action("profili", "Apri profili", "/profili", "neutral"),
            _action("audit", "Apri audit", "/audit", "neutral"),
            _action("fatturazione", "Apri fatturazione", "/fatturazione", "neutral"),
            _action("preventivi", "Apri preventivi", "/preventivi", "neutral"),
            _action("incassi", "Apri incassi", "/incassi-pagamenti", "neutral"),
        ],
        "warnings": warnings,
    }


def build_react_studio_error_payload(message: str = "Studio non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "studio": {"name": "Studio", "public_site": {}},
        "session": {},
        "modules": [],
        "operational_routes": [],
        "legacy_routes": [],
        "health": [],
        "metrics": [],
        "actions": [],
        "warnings": [{"code": "studio_errore_controllato", "message": message}],
    }

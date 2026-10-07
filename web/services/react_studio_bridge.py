"""Dati consultabili per la pagina Studio."""

from __future__ import annotations

import logging

from datetime import datetime, timezone
from typing import Any, Callable


Loader = Callable[[], Any]


logger = logging.getLogger(__name__)

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
        warnings.append({"code": f"{label}_assente", "message": f"Dati {label} non configurati."})
        return {}
    try:
        manager = loader()
        stats = getattr(manager, "statistiche", None)
        if callable(stats):
            data = stats()
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Dati %s non disponibili: %s", label, exc)
        warnings.append({"code": f"{label}_non_disponibile", "message": f"Dati {label} non disponibili."})
    return {}


def _safe_count(loader: Loader | None, label: str, warnings: list[dict[str, str]]) -> int:
    if loader is None:
        warnings.append({"code": f"{label}_assente", "message": f"Dati {label} non configurati."})
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
        logger.warning("Conteggio %s non disponibile: %s", label, exc)
        warnings.append({"code": f"{label}_conteggio_non_disponibile", "message": f"Conteggio {label} non disponibile in questo momento."})
    return 0


def _safe_read(loader: Callable[[], Any], label: str, warnings: list[dict[str, str]], fallback: Any) -> Any:
    try:
        return loader()
    except Exception:
        logger.exception("Riepilogo Studio %s non disponibile", label)
        warnings.append({"code": f"{label}_non_disponibile", "message": f"Riepilogo {label.replace('_', ' ')} non disponibile: riprova."})
        return fallback


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
            "note": "Cruscotto e contatti sono gestiti nello spazio operativo; modifica e pubblicazione restano protette.",
            "href": "/sito-studio",
            "metrics": {
                "pagine": int(stats.get("pages") or 0),
                "contatti": int(stats.get("contact_submissions") or 0),
                "prenotazioni_in_attesa": int(stats.get("pending_booking_requests") or 0),
            },
        }
    except Exception as exc:
        logger.warning("Stato del sito dello studio non disponibile: %s", exc)
        warnings.append({"code": "sito_studio_non_disponibile", "message": "Stato del sito dello studio non disponibile in questo momento."})
        return {
            "id": "sito-studio",
            "label": "Sito Studio",
            "status": "non disponibile",
            "tone": "warning",
            "note": "Il sito non ha restituito aggregati sicuri.",
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
    return _module(module_id, label, href, area, note, status="protetto", tone="warning")


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
        "sensitive_settings": "protetto",
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
    backup_stats = _safe_stats(get_backup, "backup", warnings) if get_backup is not None else {}
    pagamenti_stats = _safe_stats(get_pagamenti, "pagamenti", warnings) if get_pagamenti is not None else {}
    clienti_count = _safe_count(get_clienti, "clienti", warnings)
    fascicoli_rows = _safe_read(lambda: list(get_fascicoli().tutti(archiviati=True)), "fascicoli", warnings, [])
    fascicoli_count = len(fascicoli_rows)
    fascicoli_archived = sum(_enum(getattr(item, "stato", "")) == "ARCHIVIATO" for item in fascicoli_rows)
    active_users = int(utenti_stats.get("attivi", 0) or 0)
    open_deadlines = _safe_read(lambda: [item for item in get_scadenziario().tutte(solo_aperte=False) if _enum(getattr(item, "stato", "")) == "APERTO"], "scadenze_prioritarie", warnings, [])
    critical = sum(_enum(getattr(item, "priorita", "")) == "CRITICA" for item in open_deadlines)
    high = sum(_enum(getattr(item, "priorita", "")) == "ALTA" for item in open_deadlines)
    urgent_terms = critical + high
    site_status = _site_status(warnings)
    backup_total = int(backup_stats.get("totale", backup_stats.get("totale_backup", 0)) or 0)
    open_quotes = _safe_read(lambda: sum(_enum(getattr(item, "stato", "")) in {"BOZZA", "GENERATO", "INVIATO", "APERTO"} for item in get_preventivi().tutti_preventivi()), "preventivi_aperti", warnings, 0) if get_preventivi else 0
    unpaid = _safe_read(lambda: int(get_fatturazione().crediti_aperti()["parcelle"]), "crediti_aperti", warnings, 0) if get_fatturazione else 0
    pending_payments = int(pagamenti_stats.get("attesi", 0) or 0)

    operational_routes = [
        _module("utenti", "Utenti", "/utenti", "amministrazione", "Elenco e creazione utenti operativi."),
        _module("utenti-nuovo", "Nuovo utente", "/utenti/nuovo", "amministrazione", "Creazione utente con permessi e registro."),
        _module("profili", "Profili", "/profili", "amministrazione", "Matrice ruoli e permessi operativa."),
        _module("registro", "Registro attività", "/audit", "sicurezza", "Registro consultabile dallo studio."),
        _module("registro-attivita", "Registro attività", "/registro-attivita", "sicurezza", "Percorso operativo del registro attività."),
        _module("backup", "Backup", "/backup", "governance", "Stato backup e verifiche operative."),
        _module("fatturazione", "Fatturazione", "/fatturazione", "economico", "Documenti economici nel cruscotto."),
        _module("fatturazione-nuova", "Nuova fattura", "/fatturazione/nuova", "economico", "Creazione fattura con controlli applicativi."),
        _module("incassi", "Incassi e pagamenti", "/incassi-pagamenti", "economico", "Incassi, pagamenti e link pagamento governati."),
        _module("preventivi", "Preventivi", "/preventivi", "mandato", "Lista preventivi e stati reali."),
        _module("preventivi-nuovo", "Nuovo preventivo", "/preventivi/nuovo", "mandato", "Creazione preventivo con controlli applicativi."),
        _module("conferimento", "Nuovo conferimento", "/preventivi/conferimento/nuovo", "mandato", "Percorso conferimento già servito dalla pagina."),
        _module("compensi", "Compensi forensi", "/compensi-forensi", "economico", "Calcolo compensi governato."),
        _module("tariffario", "Tariffario", "/tariffario", "economico", "Motore tariffario operativo."),
        _module("sito-studio", "Sito Studio", "/sito-studio", "comunicazione", "Cruscotto e contatti sito operativi."),
        _module("sito-contatti", "Contatti Sito Studio", "/sito-studio/contatti", "comunicazione", "Richieste contatto e prenotazioni governate."),
    ]
    legacy_routes = [
        _legacy("impostazioni", "Impostazioni", "/impostazioni", "impostazioni sensibili", "Configurazioni riservate presidiate nel percorso dedicato."),
        _legacy("impostazioni-studio", "Impostazioni studio", "/impostazioni-studio", "impostazioni sensibili", "Dati configurativi dello studio gestiti nel percorso dedicato."),
        _legacy("calendario", "Impostazioni calendario", "/impostazioni/calendario", "impostazioni sensibili", "Collegamenti calendario presidiati nel percorso dedicato."),
        _legacy("pagamenti", "Impostazioni pagamenti", "/impostazioni/pagamenti", "impostazioni sensibili", "Configurazioni di incasso presidiate e non esposte in chiaro."),
        _legacy("sync-calendari", "Sincronizzazione calendari", "/sincronizzazione-calendari", "impostazioni sensibili", "Operazioni calendario protette nel percorso dedicato."),
        _legacy("telematico", "Servizi telematici", "/servizi-telematici", "telematico", "Portali, firma e deposito restano su percorsi protetti."),
        _legacy("builder", "Editor Sito Studio", "/sito-studio/builder", "sito studio", "Modifica e pubblicazione avanzata restano protette nel percorso dedicato."),
    ]
    health = [
        _health("backup", "Backup", "presente" if backup_total else "da verificare", "success" if backup_total else "warning", "Conteggio registro backup sicuro.", backup_total),
        _health("sito", "Sito Studio", site_status["status"], site_status["tone"], site_status["note"], site_status.get("metrics", {}).get("contatti", "")),
        _health("utenti", "Utenti e profili", "presidiato" if active_users else "da verificare", "success" if active_users else "warning", "Account attivi letti dall'archivio utenti.", active_users),
        _health("registro", "Registro attività", "abilitato" if _can(current_user, "audit.leggi") else "permesso mancante", "success" if _can(current_user, "audit.leggi") else "warning", "Accesso registro eventi amministrativi."),
        _health("economico", "Economico e mandato", "attenzione" if (unpaid or pending_payments or open_quotes) else "allineato", "warning" if (unpaid or pending_payments or open_quotes) else "success", "Aggregati fatturazione, preventivi e pagamenti.", unpaid + pending_payments + open_quotes),
        _health("documentale", "Fascicoli e scadenze", "attenzione" if urgent_terms else "allineato", "warning" if urgent_terms else "success", "Fascicoli e scadenze prioritarie reali.", urgent_terms),
    ]
    warnings.extend(
        [
            {
                "code": "impostazioni_protette",
                "message": "Impostazioni riservate, calendari, pagamenti, PEC e firma digitale restano nel percorso protetto.",
            },
            {
                "code": "telematico_protetto",
                "message": "PST, PDP, PAT, firma e portali telematici restano nel percorso dedicato.",
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
        "metricContexts": {
            "fascicoli": [
                {"id": "operativi", "label": "Fascicoli non archiviati", "value": fascicoli_count - fascicoli_archived, "note": "Elenco di lavoro", "tone": "primary", "href": "/fascicoli"},
                {"id": "archiviati", "label": "Fascicoli archiviati", "value": fascicoli_archived, "note": "Archivio dello studio", "tone": "neutral", "href": "/fascicoli/archivio"},
            ],
            "scadenze": [
                {"id": "critiche", "label": "Scadenze critiche aperte", "value": critical, "note": "Massima priorità", "tone": "warning", "href": "/scadenziario?vista=critiche"},
                {"id": "alte", "label": "Scadenze ad alta priorità aperte", "value": high, "note": "Da presidiare", "tone": "warning", "href": "/scadenziario?vista=alte"},
            ],
            "economico": [
                {"id": "crediti", "label": "Parcelle da incassare", "value": unpaid, "note": "Emesse e scadute, tutti gli anni", "tone": "primary", "href": "/incassi-pagamenti?riepilogo=crediti"},
                {"id": "pagamenti", "label": "Link di pagamento attesi", "value": pending_payments, "note": "Collegamenti in attesa", "tone": "primary", "href": "/incassi-pagamenti?riepilogo=link_attesi"},
                {"id": "preventivi", "label": "Preventivi aperti", "value": open_quotes, "note": "Bozze, generati, inviati o aperti", "tone": "primary", "href": "/preventivi?metric=preventivi_aperti"},
            ],
        },
        "metrics": [
            _metric("fascicoli", "Fascicoli", fascicoli_count, "Conteggio dall'archivio fascicoli", "primary"),
            _metric("clienti", "Clienti", clienti_count, "Anagrafica clienti reale", "info"),
            _metric("utenti", "Operatori attivi", active_users, "Account abilitati nell'archivio utenti", "success" if active_users else "warning"),
            _metric("scadenze", "Scadenze prioritarie", urgent_terms, "Critiche e alte nello scadenziario", "warning" if urgent_terms else "neutral"),
            _metric("backup", "Backup registrati", backup_total, "Registro backup sicuro", "success" if backup_total else "warning"),
            _metric("economico", "Presidi economici", unpaid + pending_payments + open_quotes, "Scoperti, pagamenti pendenti e preventivi aperti", "warning" if (unpaid or pending_payments or open_quotes) else "success"),
        ],
        "actions": [
            _action("backup", "Apri backup", "/backup", "primary"),
            _action("contatti", "Apri contatti sito", "/sito-studio/contatti", "primary"),
            _action("utenti", "Apri utenti", "/utenti", "neutral"),
            _action("profili", "Apri profili", "/profili", "neutral"),
            _action("registro", "Apri registro", "/audit", "neutral"),
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

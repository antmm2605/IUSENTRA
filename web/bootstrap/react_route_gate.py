"""Gate centrale per servire la shell React sulle route GET migrate.

Le route Flask storiche restano disponibili con ``?_legacy=1`` e tutte le
scritture continuano a passare dai POST esistenti. Questo gate intercetta solo
GET HTML di aree migrate, evitando API, download e allegati.
"""

from __future__ import annotations

from flask import Flask, current_app, g, request

from web.blueprints.react_shell import render_react_shell_response


_REACT_PREFIXES = (
    "/",
    "/agenda",
    "/applicazioni",
    "/cartelle-condivise",
    "/checklist",
    "/clienti",
    "/deposito/checklist",
    "/email",
    "/email-ordinaria",
    "/fatturazione",
    "/fascicoli",
    "/giurisprudenza",
    "/global-search",
    "/guida/firma-digitale",
    "/impostazioni",
    "/legal-intelligence",
    "/messaggi",
    "/notifiche-legali",
    "/notifiche",
    "/pat",
    "/pdp",
    "/polisWeb",
    "/portali",
    "/portali/pat",
    "/portali/pdp",
    "/portali/pst",
    "/portali/ptt",
    "/portali/sigit",
    "/preventivi",
    "/privacy/registro",
    "/profili",
    "/redazione-atti",
    "/regia-operativa",
    "/registro-attivita",
    "/registro-gdpr",
    "/ricerca-studio",
    "/scadenziario",
    "/servizi-telematici",
    "/sigit",
    "/sigp",
    "/sigp-sync",
    "/sincronizzazione-calendari",
    "/soggetti",
    "/sito-studio",
    "/statistiche",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/studio",
    "/tariffario",
    "/telematico",
    "/template-atti",
    "/timesheet",
    "/tribunali",
    "/utenti",
    "/wizard-pro",
    "/workspace-intelligente",
)

_REACT_EXACT = {
    "/admin/database",
    "/amministrazione",
    "/audit",
    "/backup",
    "/cerca",
    "/compensi-forensi",
    "/documenti",
    "/fatturazione",
    "/fatturazione/nuova",
    "/giurisprudenza",
    "/impostazioni/pagamenti",
    "/impostazioni",
    "/impostazioni-studio",
    "/incassi-pagamenti",
    "/legal-intelligence",
    "/legal-intelligence/mediazione",
    "/legal-intelligence/news",
    "/notifiche",
    "/notifiche-legali",
    "/notifiche-whatsapp",
    "/privacy/registro",
    "/privacy/registro/nuovo",
    "/preventivi",
    "/preventivi/nuovo",
    "/preventivi/conferimento/nuovo",
    "/profili",
    "/redazione-atti",
    "/registro-attivita",
    "/ricerca-legale",
    "/sito-studio",
    "/sito-studio/builder",
    "/sito-studio/contatti",
    "/sito-studio/redazione-ai",
    "/statistiche",
    "/studio",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/template-atti",
    "/template-atti/catalogo",
    "/utenti",
    "/utenti/nuovo",
}

_EXCLUDED_PREFIXES = (
    "/api",
    "/app-v2",
    "/cal/",
    "/email/api",
    "/email-ordinaria/api",
    "/health",
    "/paga/",
    "/portale/",
    "/preventivi/ajax",
    "/static/",
    "/support/",
    "/sw.js",
    "/web/",
    "/webhooks/",
)

_EXCLUDED_SUFFIXES = (
    ".csv",
    ".css",
    ".docx",
    ".eml",
    ".ico",
    ".ics",
    ".js",
    ".json",
    ".pdf",
    ".png",
    ".svg",
    ".webmanifest",
    ".xml",
    ".zip",
)

_EXCLUDED_SEGMENTS = {
    "allegato",
    "download",
    "esporta",
    "export",
    "informativa.pdf",
    "pdf",
    "scarica",
    "static",
    "visualizza",
}

_LEGACY_OPERATIONAL_PREFIXES = (
    "/admin/osservabilita",
    "/applicazioni",
    "/checklist",
    "/database",
    "/guida/firma-digitale",
    "/pat",
    "/pdp",
    "/polisweb",
    "/portali",
    "/servizi-telematici",
    "/sigit",
    "/sigp",
    "/sigp-sync",
    "/telematico",
    "/tribunali",
)

_REACT_TELEMATICO_ACQUISITION_PATHS = {
    "/portali/pdp/acquisizione",
    "/portali/pat/acquisizione",
    "/portali/ptt/acquisizione",
    "/portali/sigit/acquisizione",
}

_CANONICAL_ALIAS_PATHS = {
    "/regia-operativa",
    "/ricerca-studio",
}

_SITO_STUDIO_REACT_SUBPATHS = {
    "/sito-studio/contatti",
    "/sito-studio/builder",
    "/sito-studio/redazione-ai",
}

_SCADENZIARIO_LEGACY_ACTIONS = {
    "bulk-completa",
    "calcola-termine",
    "completa",
    "elimina",
    "export",
    "pdf",
}


def _legacy_requested() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def _accepts_html() -> bool:
    best = request.accept_mimetypes.best_match(["text/html", "application/json"])
    return best in {None, "text/html"} or request.accept_mimetypes["text/html"] >= request.accept_mimetypes["application/json"]


def _normalise_path(path: str) -> str:
    clean = (path or "/").rstrip("/") or "/"
    return clean


def _scadenziario_react_allowed(lower: str) -> bool:
    if lower in {"/scadenziario", "/scadenziario/nuova"}:
        return True
    parts = [part for part in lower.strip("/").split("/") if part]
    if len(parts) == 2 and parts[0] == "scadenziario":
        ident = parts[1]
        return "." not in ident and ident not in _SCADENZIARIO_LEGACY_ACTIONS
    if len(parts) == 3 and parts[0] == "scadenziario" and parts[2] == "modifica":
        ident = parts[1]
        return "." not in ident and ident not in _SCADENZIARIO_LEGACY_ACTIONS
    return False


def _excluded(path: str) -> bool:
    lower = path.lower()
    if lower == "/scadenziario" or lower.startswith("/scadenziario/"):
        if not _scadenziario_react_allowed(lower):
            return True
    if lower.startswith("/utenti/") and lower != "/utenti/nuovo":
        return True
    if lower.startswith("/profili/"):
        return True
    if lower.startswith("/backup/"):
        return True
    if lower.startswith("/sito-studio/") and lower not in _SITO_STUDIO_REACT_SUBPATHS:
        return True
    if lower.startswith("/studio/"):
        return True
    if lower.startswith("/amministrazione/"):
        return True
    if lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova":
        return True
    if lower.startswith("/incassi-pagamenti/"):
        return True
    if lower.startswith("/impostazioni/pagamenti/"):
        return True
    if lower.startswith("/impostazioni/calendario/"):
        return True
    if lower.startswith("/sincronizzazione-calendari/"):
        return True
    if lower == "/template-atti/nuovo":
        return True
    if lower.startswith("/template-atti/compila/"):
        return False
    if lower.startswith("/template-atti/") and lower != "/template-atti/catalogo":
        return True
    if lower.startswith("/redazione-atti/"):
        return True
    if lower == "/checklist" or lower.startswith("/checklist/"):
        return True
    if lower.startswith("/deposito/checklist/"):
        return True
    if lower.startswith("/giurisprudenza/"):
        return True
    if lower.startswith("/legal-intelligence/") and lower not in {
        "/legal-intelligence/news",
        "/legal-intelligence/mediazione",
    }:
        return True
    if lower.startswith("/ricerca-legale/"):
        return True
    if lower in _REACT_TELEMATICO_ACQUISITION_PATHS:
        return False
    if any(lower == prefix or lower.startswith(f"{prefix}/") for prefix in _LEGACY_OPERATIONAL_PREFIXES):
        return True
    is_conferimento_detail = lower.startswith("/preventivi/conferimento/") and lower.count("/") == 3
    if lower.startswith("/preventivi/") and lower not in {
        "/preventivi/nuovo",
        "/preventivi/wizard",
        "/preventivi/conferimento/nuovo",
    } and not is_conferimento_detail:
        return True
    if lower.startswith("/compensi-forensi/"):
        return True
    if lower.startswith("/tariffario/"):
        return True
    if lower.startswith("/privacy/registro/") and lower != "/privacy/registro/nuovo":
        return True
    if lower.startswith("/clienti/") and lower.endswith("/collaboratori"):
        return True
    if lower.startswith("/wizard-pro/fascicolo/"):
        return True
    # I wizard deposito interni al fascicolo restano sui template operativi
    # finche' il relativo flusso React non copre l'intera procedura.
    if lower.startswith("/fascicoli/") and "/wizard/" in lower:
        return True
    if lower.startswith("/fascicoli/") and lower.endswith("/copertina"):
        return True
    if lower.startswith("/fascicoli/") and (
        "/deposito/" in lower
        or "/penale/pdp" in lower
    ):
        return True
    if lower.startswith("/fascicoli/") and "/documenti/" in lower and lower.endswith("/editor"):
        return True
    if any(lower == prefix or lower.startswith(prefix) for prefix in _EXCLUDED_PREFIXES):
        return True
    if lower.endswith(_EXCLUDED_SUFFIXES):
        return True
    segments = {segment for segment in lower.split("/") if segment}
    return bool(segments & _EXCLUDED_SEGMENTS)


def _is_react_route(path: str) -> bool:
    lower = path.lower()
    exact = {item.lower() for item in _REACT_EXACT}
    prefixes = tuple(item.lower() for item in _REACT_PREFIXES)
    if lower in exact:
        return True
    for prefix in prefixes:
        if prefix == "/":
            if lower == "/":
                return True
            continue
        if lower == prefix or lower.startswith(f"{prefix}/"):
            return True
    return False


def _react_bootstrap_texts_for_path(path: str) -> list[str]:
    lower = path.lower().rstrip("/") or "/"
    if lower in {"/sito-studio"}:
        return ["Sito Studio"]
    return []


def _preserve_react_route_side_effects(path: str) -> None:
    lower = path.lower().rstrip("/") or "/"
    if lower not in {"/sito-studio", "/sito-studio/contatti"}:
        return
    try:
        from web.services.studio_site_runtime import ensure_current_studio_site

        ensure_current_studio_site()
    except Exception as exc:
        current_app.logger.warning("Bootstrap Sito Studio React non completato: %s", exc)


def register_react_route_gate(app: Flask) -> None:
    """Intercetta le GET HTML migrate prima che cadano nei template Jinja."""

    @app.before_request
    def _react_route_gate():
        if request.method != "GET" or _legacy_requested() or not _accepts_html():
            return None
        if not g.get("utente_corrente"):
            return None
        raw_lower = (request.path or "/").lower()
        if raw_lower.rstrip("/") in _CANONICAL_ALIAS_PATHS:
            return None
        sito_path = raw_lower.rstrip("/") or "/"
        if raw_lower.startswith("/sito-studio/") and sito_path not in {"/sito-studio"} | _SITO_STUDIO_REACT_SUBPATHS:
            return None
        path = _normalise_path(request.path)
        if _excluded(path) or not _is_react_route(path):
            return None
        spa_path = "" if path == "/" else path.lstrip("/")
        _preserve_react_route_side_effects(path)
        return render_react_shell_response(spa_path, bootstrap_texts=_react_bootstrap_texts_for_path(path))

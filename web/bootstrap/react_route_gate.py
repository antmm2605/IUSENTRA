"""Gate centrale per servire la shell React sulle route GET migrate.

Le route Flask storiche restano disponibili con ``?_legacy=1`` e tutte le
scritture continuano a passare dai POST esistenti. Questo gate intercetta solo
GET HTML di aree migrate, evitando API, download e allegati.
"""

from __future__ import annotations

from flask import Flask, g, has_request_context, request

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
    "/admin/osservabilita",
    "/admin/osservabilita",
    "/amministrazione",
    "/audit",
    "/backup",
    "/cerca",
    "/compensi-forensi",
    "/database",
    "/fatturazione",
    "/fatturazione/nuova",
    "/giurisprudenza",
    "/giurisprudenza/nuova",
    "/impostazioni/calendario",
    "/impostazioni/pagamenti",
    "/impostazioni",
    "/impostazioni-studio",
    "/incassi-pagamenti",
    "/legal-intelligence",
    "/legal-intelligence/mediazione",
    "/legal-intelligence/news",
    "/notifiche",
    "/notifiche-whatsapp",
    "/privacy/registro",
    "/privacy/registro/nuovo",
    "/profili",
    "/redazione-atti",
    "/registro-attivita",
    "/registro-gdpr",
    "/ricerca-legale",
    "/servizi-telematici",
    "/sincronizzazione-calendari",
    "/sito-studio",
    "/sito-studio/builder",
    "/sito-studio/contatti",
    "/statistiche",
    "/studio",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/template-atti",
    "/template-atti/catalogo",
    "/template-atti/nuovo",
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
    "/admin/database",
    "/admin/osservabilita",
    "/amministrazione",
    "/applicazioni",
    "/audit",
    "/backup",
    "/checklist",
    "/compensi-forensi",
    "/database",
    "/deposito/checklist",
    "/fatturazione",
    "/giurisprudenza",
    "/guida/firma-digitale",
    "/impostazioni",
    "/impostazioni-studio",
    "/incassi-pagamenti",
    "/legal-intelligence",
    "/notifiche",
    "/notifiche-whatsapp",
    "/pat",
    "/pdp",
    "/polisweb",
    "/portali",
    "/preventivi",
    "/privacy/registro",
    "/profili",
    "/redazione-atti",
    "/registro-attivita",
    "/registro-gdpr",
    "/ricerca-legale",
    "/servizi-telematici",
    "/sigit",
    "/sigp",
    "/sigp-sync",
    "/sincronizzazione-calendari",
    "/sito-studio",
    "/statistiche",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/studio",
    "/tariffario",
    "/telematico",
    "/template-atti",
    "/tribunali",
    "/utenti",
)


def _legacy_requested() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def _accepts_html() -> bool:
    best = request.accept_mimetypes.best_match(["text/html", "application/json"])
    return best in {None, "text/html"} or request.accept_mimetypes["text/html"] >= request.accept_mimetypes["application/json"]


def _normalise_path(path: str) -> str:
    clean = (path or "/").rstrip("/") or "/"
    return clean


def _excluded(path: str) -> bool:
    lower = path.lower()
    if any(lower == prefix or lower.startswith(f"{prefix}/") for prefix in _LEGACY_OPERATIONAL_PREFIXES):
        return True
    # I preventivi hanno un wizard completo con tassonomia, sottobranche,
    # fonti, calcolo D.M. 55 e generazione tramite POST auditati. La shell
    # React riassuntiva non puo' sostituirlo finche' non replica l'intero
    # flusso operativo end-to-end.
    if lower == "/preventivi" or lower.startswith("/preventivi/"):
        return True
    # Il tariffario/compensi forensi contiene il motore di calcolo completo:
    # non deve essere mascherato da una card React non equivalente.
    if lower in {"/tariffario", "/compensi-forensi"}:
        return True
    if lower == "/impostazioni" and has_request_context():
        tab = (request.args.get("tab") or "").strip().lower()
        # Il tab Firma Digitale contiene ancora controlli browser-locali
        # completi (download Local Signer e verifica 127.0.0.1) non replicati
        # integralmente nella shell React: non va servito in React finche' il
        # flusso non e' realmente completo end-to-end.
        if tab in {"firma", "firma-digitale"}:
            return True
    # I wizard deposito interni al fascicolo restano sui template operativi
    # finche' il relativo flusso React non copre l'intera procedura.
    if lower.startswith("/fascicoli/") and "/wizard/" in lower:
        return True
    if lower.startswith("/fascicoli/") and (
        "/deposito/" in lower
        or "/penale/pdp" in lower
    ):
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


def register_react_route_gate(app: Flask) -> None:
    """Intercetta le GET HTML migrate prima che cadano nei template Jinja."""

    @app.before_request
    def _react_route_gate():
        if request.method != "GET" or _legacy_requested() or not _accepts_html():
            return None
        if not g.get("utente_corrente"):
            return None
        path = _normalise_path(request.path)
        if _excluded(path) or not _is_react_route(path):
            return None
        spa_path = "" if path == "/" else path.lstrip("/")
        return render_react_shell_response(spa_path)

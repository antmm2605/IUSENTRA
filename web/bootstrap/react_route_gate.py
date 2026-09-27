"""Gate centrale per servire la shell React sulle route GET migrate.

Le route Flask storiche restano disponibili con ``?_legacy=1`` e tutte le
scritture continuano a passare dai POST esistenti. Questo gate intercetta solo
GET HTML di aree migrate, evitando API, download e allegati.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

from flask import Flask, current_app, g, get_flashed_messages, redirect, request, url_for

from web.blueprints.react_shell import render_react_shell_response


_REACT_PREFIXES = (
    "/",
    "/agenda",
    "/applicazioni",
    "/backup",
    "/cartelle-condivise",
    "/checklist",
    "/clienti",
    "/deposito/checklist",
    "/editor-professionale",
    "/email",
    "/email-ordinaria",
    "/fatturazione",
    "/fascicoli",
    "/giurisprudenza",
    "/global-search",
    "/guida/firma-digitale",
    "/impostazioni",
    "/importa-pratiche",
    "/importa-pratiche-studio-telematico",
    "/import/quickorganizer",
    "/legal-skills",
    "/legal-intelligence",
    "/lex-apprendimento",
    "/procedure-completion",
    "/messaggi",
    "/ricerca-legale",
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
    "/regia-agentica",
    "/regia-operativa",
    "/registro-attivita",
    "/registro-gdpr",
    "/ricerca-studio",
    "/scadenziario",
    "/servizi-telematici",
    "/sigit",
    "/sincronizzazione-calendari",
    "/soggetti",
    "/sito-studio",
    "/statistiche",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/strumenti-documentali",
    "/studio",
    "/tariffario",
    "/telematico",
    "/template-atti",
    "/timesheet",
    "/tribunali",
    "/utenti",
    "/wizard-pro",
    "/workspace-intelligente",
    "/workflow-agents",
)

_REACT_EXACT = {
    "/admin/database",
    "/amministrazione",
    "/audit",
    "/backup",
    "/cerca",
    "/compensi-forensi",
    "/documenti",
    "/editor-professionale",
    "/fatturazione",
    "/fatturazione/nuova",
    "/giurisprudenza",
    "/impostazioni/pagamenti",
    "/impostazioni",
    "/impostazioni-studio",
    "/incassi-pagamenti",
    "/legal-skills",
    "/lex-operativo",
    "/procedure-completion",
    "/legal-intelligence",
    "/lex-apprendimento",
    "/legal-intelligence/mediazione",
    "/legal-intelligence/news",
    "/legal-intelligence/ricerca",
    "/notifiche",
    "/notifiche-legali",
    "/notifiche-whatsapp",
    "/oggi",
    "/privacy/registro",
    "/privacy/registro/nuovo",
    "/preventivi",
    "/preventivi/nuovo",
    "/preventivi/conferimento/nuovo",
    "/profilo",
    "/profili",
    "/redazione-atti",
    "/regia-agentica",
    "/registro-attivita",
    "/ricerca-legale",
    "/ricerca-legale/mediazione",
    "/ricerca-legale/news",
    "/ricerca-legale/ricerca",
    "/sito-studio",
    "/sito-studio/builder",
    "/sito-studio/contatti",
    "/sito-studio/redazione-ai",
    "/statistiche",
    "/studio",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/strumenti-documentali",
    "/template-atti",
    "/template-atti/catalogo",
    "/utenti",
    "/utenti/nuovo",
    "/workflow-agents",
    "/workflow-agents/approvals",
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
    "/telematico",
    "/tribunali",
)

_REACT_TELEMATICO_ACQUISITION_PATHS = {
    "/portali/pst/acquisizione",
    "/portali/pdp/acquisizione",
    "/portali/pat/acquisizione",
    "/portali/ptt/acquisizione",
    "/portali/sigit/acquisizione",
}

_REACT_TELEMATICO_GRAPHICAL_PATHS = {
    "/guida/firma-digitale",
    "/pat",
    "/pdp",
    "/polisweb",
    "/pst",
    "/servizi-telematici",
    "/sigit",
    "/telematico",
    "/telematici",
    "/tribunali",
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


# Indirizzi storici che la pagina React serve con un parametro: i moduli «nuovo
# per questo cliente» leggono `?id_cliente=` (bridge fatturazione e preventivi),
# la scheda parcella si apre da `?id_parcella=` (FatturazionePage).
_REDIRECT_CON_PARAMETRO = (
    (re.compile(r"^/fatturazione/nuova/([^/]+)$", re.IGNORECASE), "/fatturazione/nuova", "id_cliente"),
    (re.compile(r"^/preventivi/nuovo/([^/]+)$", re.IGNORECASE), "/preventivi/nuovo", "id_cliente"),
    (re.compile(r"^/preventivi/conferimento/nuovo/([^/]+)$", re.IGNORECASE), "/preventivi/conferimento/nuovo", "id_cliente"),
    (re.compile(r"^/fatturazione/(?!nuova$|da-preventivo$|ajax$)([^/]+)$", re.IGNORECASE), "/fatturazione", "id_parcella"),
    (re.compile(r"^/sito-studio/pagine/(\d+)/modifica$", re.IGNORECASE), "/sito-studio/builder", "page_id"),
)

# Viste del sito dello studio che il builder e i contatti React coprono già.
_REDIRECT_SITO = {
    "/sito-studio/pagine/nuova": "/sito-studio/builder",
    "/sito-studio/preview": "/sito-studio/builder",
    "/sito-studio/prenotazioni": "/sito-studio/contatti",
}


# Consultazione dai portali: l'acquisizione guidata React (`/portali/<portale>/acquisizione`)
# legge ufficio, numero e anno del ruolo. Il PDP non espone servizi ai gestionali
# (art. 111-bis c.p.p., D.M. 217/2023): anche la sua consultazione passa di lì.
_REDIRECT_PORTALI = {
    "/polisweb/documenti": "pst",
    "/polisweb/fascicolo-wizard": "pst",
    "/pdp/documenti": "pdp",
}
_PARAMETRI_PORTALI = (("codice_ufficio", "ufficio_codice"), ("numero_rg", "numero"), ("anno_rg", "anno"), ("id_fasc", "id_fasc"))


def _redirect_portale(path: str):
    portale = _REDIRECT_PORTALI.get(path.lower())
    if not portale:
        return None
    parametri = {nuovo: request.args.get(storico, "").strip() for storico, nuovo in _PARAMETRI_PORTALI}
    parametri = {chiave: valore for chiave, valore in parametri.items() if valore and valore != "0"}
    query = urlencode(parametri)
    return redirect(f"/portali/{portale}/acquisizione{'?' + query if query else ''}")


def _redirect_con_parametro(path: str):
    for pattern, target, parametro in _REDIRECT_CON_PARAMETRO:
        trovato = pattern.match(path)
        if trovato:
            parametri = request.args.to_dict(flat=True)
            parametri.setdefault(parametro, trovato.group(1))
            return redirect(f"{target}?{urlencode(parametri)}")
    return None


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


def _sito_studio_react_allowed(lower: str) -> bool:
    if lower in _SITO_STUDIO_REACT_SUBPATHS:
        return True
    parts = [part for part in lower.strip("/").split("/") if part]
    if len(parts) == 4 and parts[0] == "sito-studio" and parts[1] == "articoli" and parts[2].isdigit() and parts[3] == "modifica":
        return True
    return _contenuti_del_sito(lower)


def _contenuti_del_sito(lower: str) -> bool:
    """Servizi, professionisti, sedi, orari, impostazioni e nuovo articolo: SitoStudioContenutiPage React."""
    parts = [part for part in lower.strip("/").split("/") if part]
    if parts[:1] != ["sito-studio"] or len(parts) < 2:
        return False
    if parts[1:] in (["impostazioni"], ["articoli", "nuovo"]):
        return True
    if parts[1] not in {"servizi", "professionisti", "sedi", "regole-agenda"}:
        return False
    coda = parts[2:]
    return coda in ([], ["nuovo"], ["nuova"]) or (len(coda) == 2 and coda[0].isdigit() and coda[1] == "modifica")


def _modello_di_studio(lower: str) -> bool:
    parti = [parte for parte in lower.strip("/").split("/") if parte]
    if parti[:1] != ["template-atti"]:
        return False
    if parti == ["template-atti", "nuovo"]:
        return True
    if len(parti) == 3 and parti[1] == "scheda":
        return True
    return len(parti) == 3 and parti[2] in {"modifica", "usa"} and parti[1] not in {"compila", "catalogo", "editor", "scheda"}


def _scheda_ricerca_legale(lower: str) -> bool:
    """News, scheda della fonte e variazione rilevata: RicercaLegaleSchedaPage React."""
    parti = [parte for parte in lower.strip("/").split("/") if parte]
    if parti[:1] != ["ricerca-legale"]:
        return False
    if len(parti) == 3 and parti[1] in {"news", "fonte"}:
        return True
    return len(parti) == 5 and parti[1:3] == ["daily", "update"] and parti[3].isdigit() and parti[4] == "diff"


def _checklist_atti(lower: str) -> bool:
    """Checklist degli atti e percorso guidato del fascicolo: ChecklistAttiPage React."""
    parti = [parte for parte in lower.strip("/").split("/") if parte]
    if parti[:1] == ["checklist"]:
        return len(parti) <= 2
    if len(parti) >= 4 and parti[0] == "fascicoli" and parti[2] == "wizard":
        coda = parti[4:]
        return coda in ([], ["completa"]) or (len(coda) == 2 and coda[0] == "step" and coda[1].isdigit())
    return False


def _excluded(path: str) -> bool:
    lower = path.lower()
    if lower == "/scadenziario" or lower.startswith("/scadenziario/"):
        if not _scadenziario_react_allowed(lower):
            return True
    if lower.startswith("/utenti/") and lower != "/utenti/nuovo":
        # Modifica e permessi del singolo utente: UtentiPage React.
        parti = [parte for parte in lower.strip("/").split("/") if parte]
        return not (len(parti) == 3 and parti[2] in {"modifica", "permessi"})
    if lower.startswith("/profili/"):
        return True
    if lower.startswith("/backup/"):
        # Il ripristino di una copia è nella sezione Backup delle impostazioni React.
        parti = [parte for parte in lower.strip("/").split("/") if parte]
        return not (len(parti) == 3 and parti[2] == "ripristina")
    if lower.startswith("/sito-studio/") and not _sito_studio_react_allowed(lower):
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
    # Modelli di studio (nuovo, scheda, modifica, compilazione): TemplateStudioPage React.
    if _modello_di_studio(lower):
        return False
    if _scheda_ricerca_legale(lower):
        return False
    if _checklist_atti(lower):
        return False
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
    if lower.startswith("/giurisprudenza/") and lower != "/giurisprudenza/nuova":
        # Scheda e modifica di una sentenza: GiurisprudenzaPage React.
        parti = [parte for parte in lower.strip("/").split("/") if parte]
        return not (len(parti) == 2 or (len(parti) == 3 and parti[2] == "modifica"))
    if lower.startswith("/legal-intelligence/") and lower not in {
        "/legal-intelligence/mediazione",
        "/legal-intelligence/news",
        "/legal-intelligence/ricerca",
    }:
        return True
    # /legal-intelligence/fonte/<id>/scarica resta servito dal blueprint Flask
    # (download di file binari/testo, fuori dallo scope React shell).
    if lower.startswith("/legal-intelligence/fonte/") and lower.endswith("/scarica"):
        return True
    if lower.startswith("/ricerca-legale/fonte/") and lower.endswith("/scarica"):
        return True
    if lower.startswith("/ricerca-legale/") and lower not in {
        "/ricerca-legale/mediazione",
        "/ricerca-legale/news",
        "/ricerca-legale/ricerca",
    }:
        return True
    # /legal-intelligence/daily/update/<id>/diff resta legacy (rendering server-side).
    if lower.startswith("/legal-intelligence/daily/"):
        return True
    if lower.startswith("/ricerca-legale/daily/"):
        return True
    if lower in _REACT_TELEMATICO_GRAPHICAL_PATHS:
        return False
    if lower in _REACT_TELEMATICO_ACQUISITION_PATHS:
        return False
    if any(lower == prefix or lower.startswith(f"{prefix}/") for prefix in _LEGACY_OPERATIONAL_PREFIXES):
        return True
    is_conferimento_detail = lower.startswith("/preventivi/conferimento/") and lower.count("/") == 3
    # Scheda del preventivo: React (PreventiviPage apre il dettaglio con workflow e azioni).
    is_preventivo_detail = lower.startswith("/preventivi/p/") and lower.count("/") == 3
    if lower.startswith("/preventivi/") and lower not in {
        "/preventivi/nuovo",
        "/preventivi/wizard",
        "/preventivi/conferimento/nuovo",
    } and not is_conferimento_detail and not is_preventivo_detail:
        return True
    if lower.startswith("/compensi-forensi/"):
        return True
    if lower.startswith("/tariffario/"):
        return True
    if lower.startswith("/privacy/registro/") and lower != "/privacy/registro/nuovo":
        return True
    if lower.startswith("/wizard-pro/fascicolo/"):
        return True
    # I wizard deposito interni al fascicolo restano sui template operativi
    # finche' il relativo flusso React non copre l'intera procedura.
    if lower.startswith("/fascicoli/") and "/wizard/" in lower:
        return True
    # Copertine (fascicolo e faldone del cliente): documenti da stampare, non pagine.
    if lower.endswith("/copertina"):
        return True
    if lower.startswith("/fascicoli/") and lower.endswith("/deposito/prepara"):
        return False
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
    texts = [
        str(message)
        for _, message in get_flashed_messages(with_categories=True)
        if str(message or "").strip()
    ]
    if lower in {"/sito-studio"}:
        texts.append("Sito Studio")
    return texts


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
    def _legal_intelligence_canonical_redirect():
        # /legal-intelligence/* è alias storico: redirigi al canonico /ricerca-legale/*.
        # Si applica anche a POST per non spezzare integrazioni legacy.
        raw = request.path or "/"
        lower = raw.lower()
        if lower == "/legal-intelligence" or lower == "/legal-intelligence/":
            target = "/ricerca-legale"
            if request.query_string:
                target += "?" + request.query_string.decode("utf-8", errors="ignore")
            return redirect(target, code=301)
        if lower.startswith("/legal-intelligence/"):
            tail = raw[len("/legal-intelligence"):]
            target = "/ricerca-legale" + tail
            if request.query_string:
                target += ("&" if "?" in target else "?") + request.query_string.decode("utf-8", errors="ignore")
            return redirect(target, code=301)
        return None

    @app.before_request
    def _react_route_gate():
        if request.method != "GET" or _legacy_requested() or not _accepts_html():
            return None
        raw_lower = (request.path or "/").lower()
        path = _normalise_path(request.path)
        lower_path = path.lower()
        if not g.get("utente_corrente"):
            if lower_path in _REACT_TELEMATICO_ACQUISITION_PATHS:
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
            return None
        if raw_lower.rstrip("/") == "/profilo" and (
            request.args.get("password_obbligatoria")
            or bool(getattr(g.utente_corrente, "must_change_password", False))
        ):
            return None
        if raw_lower.rstrip("/") in _CANONICAL_ALIAS_PATHS:
            return None
        con_parametro = _redirect_con_parametro(path)
        if con_parametro is not None:
            return con_parametro
        portale = _redirect_portale(path)
        if portale is not None:
            return portale
        sito = _REDIRECT_SITO.get(path.lower())
        if sito is not None:
            return redirect(sito)
        sito_path = raw_lower.rstrip("/") or "/"
        if raw_lower.startswith("/sito-studio/") and not _sito_studio_react_allowed(sito_path):
            return None
        if _excluded(path) or not _is_react_route(path):
            return None
        spa_path = "" if path == "/" else path.lstrip("/")
        _preserve_react_route_side_effects(path)
        return render_react_shell_response(spa_path, bootstrap_texts=_react_bootstrap_texts_for_path(path))

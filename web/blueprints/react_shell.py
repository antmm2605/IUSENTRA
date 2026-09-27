"""Shell React progressiva per IUSENTRA.

La shell vive sotto ``/app-v2`` e governa le superfici già migrate mantenendo
separati i servizi Flask di scrittura, audit e validazione.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlencode, urlsplit

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, session, url_for

from web.services.feature_flags import (
    app_v2_route_flag_for_path,
    feature_flags_payload,
    is_feature_enabled,
)
from web.services.notification_presidia_runtime import (
    apply_legal_notification_presidia_effective_flags,
)

react_shell = Blueprint("react_shell", __name__)
_INLINE_ENTRY_CACHE: dict[str, tuple[int, str]] = {}
# Manifest Vite e grafo asset per route: invariati fino alla build successiva,
# quindi memorizzati per firma (mtime_ns, size) del manifest.
_MANIFEST_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}
_ROUTE_ASSETS_CACHE: dict[tuple[str, tuple[int, int], str], dict[str, list[str]]] = {}


_LEGACY_FIRST_PREFIXES = (
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


def _local_redirect_target(path: str, query: dict[str, str]) -> str:
    clean_path = str(path or "/").replace("\r", "").replace("\n", "")
    parsed = urlsplit(clean_path)
    if parsed.scheme or parsed.netloc or not clean_path.startswith("/") or clean_path.startswith("//"):
        clean_path = "/"
    clean_path = "/" + "/".join(
        quote(part, safe="-._~:@")
        for part in clean_path.split("/")
        if part
    )
    encoded = urlencode(query)
    return f"{clean_path}?{encoded}" if encoded else clean_path

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


def _react_static_dir() -> Path:
    return Path(current_app.static_folder or "web/static") / "react"


_ROUTE_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("/agenda/nuovo", "src/components/NuovoAppuntamentoPage.tsx"),
    ("/agenda", "src/components/AgendaPage.tsx"),
    ("/timesheet", "src/components/TimesheetPage.tsx"),
    ("/fascicoli/nuovo", "src/components/FascicoliPage.tsx"),
    ("/fascicoli/archivio", "src/components/FascicoliPage.tsx"),
    ("/fascicoli", "src/components/FascicoliPage.tsx"),
    ("/clienti/nuovo", "src/components/NuovoClientePage.tsx"),
    ("/clienti", "src/components/AnagraficaClientiPage.tsx"),
    ("/crm", "src/components/CrmPage.tsx"),
    ("/prima-nota", "src/components/PrimaNotaPage.tsx"),
    ("/cartelle-condivise", "src/components/CartelleCondivisePage.tsx"),
    ("/soggetti/nuovo", "src/components/NuovoClientePage.tsx"),
    ("/soggetti", "src/components/SoggettiPage.tsx"),
    ("/email-ordinaria", "src/components/EmailPecPage.tsx"),
    ("/email", "src/components/EmailPecPage.tsx"),
    ("/notifiche-legali", "src/components/NotificheLegaliPage.tsx"),
    ("/messaggi/nuovo", "src/components/MessaggiPage.tsx"),
    ("/messaggi", "src/components/MessaggiPage.tsx"),
    ("/scadenziario/nuova", "src/components/NuovaScadenzaPage.tsx"),
    ("/scadenziario", "src/components/ScadenziarioPage.tsx"),
    ("/wizard-pro", "src/components/WizardProPage.tsx"),
    ("/telematico", "src/components/TelematicoPage.tsx"),
    ("/servizi-telematici", "src/components/TelematicoPage.tsx"),
    ("/telematici", "src/components/TelematicoPage.tsx"),
    ("/polisweb", "src/components/TelematicoSurfacePage.tsx"),
    ("/pst", "src/components/TelematicoSurfacePage.tsx"),
    ("/pdp", "src/components/penalePdp/PdpPenalePage.tsx"),
    ("/pat", "src/components/TelematicoSurfacePage.tsx"),
    ("/sigit", "src/components/TelematicoSurfacePage.tsx"),
    ("/ptt", "src/components/TelematicoSurfacePage.tsx"),
    ("/tribunali", "src/components/TelematicoSurfacePage.tsx"),
    ("/guida/firma-digitale", "src/components/TelematicoSurfacePage.tsx"),
    ("/portali/pst/acquisizione", "src/components/TelematicoSurfacePage.tsx"),
    ("/portali/pdp/acquisizione", "src/components/penalePdp/PdpPenalePage.tsx"),
    ("/portali/pat/acquisizione", "src/components/TelematicoSurfacePage.tsx"),
    ("/portali/ptt/acquisizione", "src/components/TelematicoSurfacePage.tsx"),
    ("/portali/sigit/acquisizione", "src/components/TelematicoSurfacePage.tsx"),
    ("/deposito/checklist", "src/components/TelematicoSurfacePage.tsx"),
    ("/studio", "src/components/StudioPage.tsx"),
    ("/fatturazione", "src/components/FatturazionePage.tsx"),
    ("/preventivi/conferimento", "src/components/PreventiviPage.tsx"),
    ("/preventivi/nuovo", "src/components/PreventiviPage.tsx"),
    ("/preventivi", "src/components/PreventiviPage.tsx"),
    ("/compensi-forensi", "src/components/CompensiForensiPage.tsx"),
    ("/documenti", "src/components/StudioModulePage.tsx"),
    ("/editor-professionale", "src/components/EditorProfessionalePage.tsx"),
    ("/template-atti", "src/components/TemplateAttiPage.tsx"),
    ("/redazione-atti", "src/components/RedazioneAttiPage.tsx"),
    ("/statistiche", "src/components/StatistichePage.tsx"),
    ("/legal-skills/percorsi", "src/features/legal-skills/pages/PromptPathwaysPage.tsx"),
    ("/legal-skills/prompt", "src/features/legal-skills/pages/PromptLibraryPage.tsx"),
    ("/legal-skills", "src/features/legal-skills/pages/LegalSkillsCatalogPage.tsx"),
    ("/lex-apprendimento", "src/components/LexLearningPage.tsx"),
    ("/lex-operativo", "src/components/LexOperativoPage.tsx"),
    ("/procedure-completion", "src/features/procedure-completion/ProcedureCompletionPage.tsx"),
    ("/oggi", "src/pages/daily-plan/OggiPage.tsx"),
    ("/workflow-agents/approvals", "src/pages/workflow-agents/AgentApprovalQueue.tsx"),
    ("/workflow-agents/runs", "src/pages/workflow-agents/AgentRunDetail.tsx"),
    ("/workflow-agents", "src/pages/workflow-agents/WorkflowAgentsHome.tsx"),
    ("/regia-agentica", "src/pages/workflow-agents/WorkflowAgentsHome.tsx"),
    ("/app/portale-clienti", "src/components/ClientPortalPage.tsx"),
    ("/portale-cliente", "src/components/ClientPortalPage.tsx"),
    ("/ricerca-legale", "src/components/LegalIntelligencePage.tsx"),
    ("/giurisprudenza", "src/components/GiurisprudenzaPage.tsx"),
    ("/strumenti-legali", "src/components/StrumentiLegaliPage.tsx"),
    ("/strumenti-operativi", "src/components/StudioModulePage.tsx"),
    ("/strumenti-documentali", "src/components/DocumentToolsPage.tsx"),
    ("/sito-studio/redazione-ai", "src/components/SitoStudioRedazioneAiPage.tsx"),
    ("/sito-studio/builder", "src/components/SitoStudioBuilderPage.tsx"),
    ("/sito-studio", "src/components/SitoStudioPage.tsx"),
    ("/amministrazione", "src/components/AmministrazionePage.tsx"),
    ("/utenti", "src/components/UtentiPage.tsx"),
    ("/profili", "src/components/ProfiliPage.tsx"),
    ("/audit", "src/components/AuditPage.tsx"),
    ("/registro-attivita", "src/components/AuditPage.tsx"),
    ("/admin/database", "src/components/AdminDatabasePage.tsx"),
    ("/importa-pratiche", "src/components/QuickOrganizerImportPage.tsx"),
    ("/importa-pratiche-studio-telematico", "src/components/QuickOrganizerImportPage.tsx"),
    ("/import/quickorganizer", "src/components/QuickOrganizerImportPage.tsx"),
    ("/privacy/registro", "src/components/PrivacyRegistroPage.tsx"),
    ("/impostazioni", "src/components/ImpostazioniPage.tsx"),
    ("/impostazioni-studio", "src/components/ImpostazioniPage.tsx"),
    ("/notifiche", "src/components/ImpostazioniPage.tsx"),
    ("/notifiche-whatsapp", "src/components/ImpostazioniPage.tsx"),
    ("/backup", "src/components/ImpostazioniPage.tsx"),
    ("/sincronizzazione-calendari", "src/components/ImpostazioniPage.tsx"),
    ("/global-search", "src/components/RicercaStudioPage.tsx"),
    ("/workspace-intelligente", ""),
)


def _route_component_key(path: str) -> str:
    lower = (path or "/").rstrip("/").lower() or "/"
    if lower.startswith("/app-v2/"):
        lower = lower[len("/app-v2") :] or "/"
    if lower == "/":
        return ""
    if lower.startswith("/clienti/") and lower.endswith("/collaboratori"):
        return "src/components/ClientiCollaboratoriPage.tsx"
    if _modello_di_studio(lower):
        return "src/components/TemplateStudioPage.tsx"
    if _scheda_ricerca_legale(lower):
        return "src/components/RicercaLegaleSchedaPage.tsx"
    if _checklist_atti(lower):
        return "src/components/ChecklistAttiPage.tsx"
    if _applicazione_react(lower):
        return "src/components/ApplicazionePage.tsx"
    if _contenuti_del_sito(lower):
        return "src/components/SitoStudioContenutiPage.tsx"
    for prefix, component in _ROUTE_COMPONENTS:
        if lower == prefix or lower.startswith(f"{prefix}/"):
            return component
    return "src/components/StudioModulePage.tsx"


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


def _collect_manifest_assets(manifest: dict[str, Any], key: str) -> dict[str, list[str]]:
    seen: set[str] = set()
    js: list[str] = []
    css: list[str] = []

    def visit(entry_key: str) -> None:
        if not entry_key or entry_key in seen:
            return
        seen.add(entry_key)
        entry = manifest.get(entry_key) or {}
        file_name = entry.get("file")
        if file_name and entry_key != "index.html":
            js.append(f"/static/react/{file_name}")
        for css_file in entry.get("css", []) or []:
            css.append(f"/static/react/{css_file}")
        for import_key in entry.get("imports", []) or []:
            if import_key != "index.html":
                visit(import_key)

    visit(key)
    return {
        "js": list(dict.fromkeys(js)),
        "css": list(dict.fromkeys(css)),
    }


def _global_manifest_css(manifest: dict[str, Any], entry: dict[str, Any]) -> list[str]:
    css: list[str] = [str(path) for path in entry.get("css", []) or [] if path]
    style_entry = manifest.get("style.css") or {}
    style_file = style_entry.get("file")
    if style_file:
        css.append(str(style_file))
    return list(dict.fromkeys(css))


def _inline_react_entry_code(file_name: str) -> str:
    asset_path = _react_static_dir() / file_name
    try:
        stat = asset_path.stat()
        cached = _INLINE_ENTRY_CACHE.get(str(asset_path))
        if cached and cached[0] == stat.st_mtime_ns:
            return cached[1]
        code = asset_path.read_text(encoding="utf-8")
    except OSError as exc:
        current_app.logger.warning("Entry React inline non leggibile: %s", exc)
        return ""

    rewritten = (
        code
        .replace('from"./', 'from"/static/react/assets/')
        .replace("from'./", "from'/static/react/assets/")
        .replace('import("./', 'import("/static/react/assets/')
        .replace("import('./", "import('/static/react/assets/")
        # Vite 8 può emettere import differiti con template literal; senza
        # questa riscrittura l'entry inline li risolve dalla route corrente.
        .replace("import(`./", "import(`/static/react/assets/")
        .replace("</script", "<\\/script")
    )
    _INLINE_ENTRY_CACHE[str(asset_path)] = (stat.st_mtime_ns, rewritten)
    return rewritten


def _load_manifest(manifest_path: Path) -> dict[str, Any] | None:
    """Manifest Vite parsato una sola volta per build, invalidato sull'mtime.

    Il manifest supera i 45 kB e veniva riletto e riparsato ad ogni render della
    shell, cioe' ad ogni cambio pagina. Il file cambia solo con una nuova build
    frontend, quindi la chiave di cache e' `(mtime_ns, size)` come per l'entry
    inline: dopo un deploy la prima richiesta ricarica, le successive no.
    """

    try:
        stat = manifest_path.stat()
    except OSError:
        return None
    signature = (stat.st_mtime_ns, stat.st_size)
    cached = _MANIFEST_CACHE.get(str(manifest_path))
    if cached and cached[0] == signature:
        return cached[1]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        current_app.logger.exception("Manifest React non leggibile: %s", exc)
        return None
    _MANIFEST_CACHE[str(manifest_path)] = (signature, manifest)
    return manifest


def _cached_route_assets(manifest_path: Path, manifest: dict[str, Any], key: str) -> dict[str, list[str]]:
    """Grafo import per route, calcolato una volta per (build, componente)."""

    cached_manifest = _MANIFEST_CACHE.get(str(manifest_path))
    if cached_manifest is None:
        return _collect_manifest_assets(manifest, key)
    cache_key = (str(manifest_path), cached_manifest[0], key)
    assets = _ROUTE_ASSETS_CACHE.get(cache_key)
    if assets is None:
        assets = _collect_manifest_assets(manifest, key)
        # Le route sono un insieme chiuso e piccolo: si azzera solo al cambio build.
        if len(_ROUTE_ASSETS_CACHE) > 512:
            _ROUTE_ASSETS_CACHE.clear()
        _ROUTE_ASSETS_CACHE[cache_key] = assets
    return {"js": list(assets["js"]), "css": list(assets["css"])}


def _vite_entry(current_path: str = "") -> dict[str, Any]:
    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    if not manifest_path.exists():
        return {
            "ready": False,
            "js": [],
            "css": [],
            "preload_js": [],
            "page_css": [],
            "error": "Build React non trovata. Esegui: cd frontend; npm ci; npm run build",
        }

    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return {
            "ready": False,
            "js": [],
            "css": [],
            "preload_js": [],
            "page_css": [],
            "error": "Manifest React non leggibile. Rigenera la build frontend.",
        }

    entry = manifest.get("src/main.tsx") or next(
        (value for value in manifest.values() if value.get("isEntry")),
        None,
    )
    if not entry:
        return {
            "ready": False,
            "js": [],
            "css": [],
            "preload_js": [],
            "page_css": [],
            "error": "Manifest Vite presente ma entry src/main.tsx non trovata.",
        }

    route_assets = _cached_route_assets(manifest_path, manifest, _route_component_key(current_path))
    entry_file = f"/static/react/{entry['file']}"
    return {
        "ready": True,
        "js": [entry_file],
        "entry_file": entry_file,
        "inline_entry_code": _inline_react_entry_code(str(entry["file"])),
        "css": [f"/static/react/{path}" for path in _global_manifest_css(manifest, entry)],
        "preload_js": route_assets["js"],
        "page_css": route_assets["css"],
        "error": "",
    }


def _react_body_class_for_path(path: str) -> str:
    lower = ((path or "/").rstrip("/") or "/").lower()
    if lower.startswith("/portale-cliente"):
        return "react-shell-page--client-portal-public"
    if lower.startswith("/app/portale-clienti"):
        return "react-shell-page--client-portal-studio"
    return ""


@react_shell.get("/app-v2")
@react_shell.get("/app-v2/")
@react_shell.get("/app-v2/<path:spa_path>")
def react_app(spa_path: str = ""):
    """Serve la shell SPA React per le superfici migrate."""

    flag_key = app_v2_route_flag_for_path(spa_path)
    if flag_key and not is_feature_enabled(flag_key, current_app.config):
        response = make_response("Funzione non attiva per questo studio.", 403)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    return render_react_shell_response(spa_path)


def render_react_shell_response(spa_path: str = "", *, bootstrap_texts: Iterable[Any] | None = None):
    """Render condiviso per le superfici migrate a React.

    La shell React resta sempre disponibile sotto ``/app-v2``. Fuori da
    ``/app-v2`` le route operative storiche non vengono piu' promosse
    implicitamente: questo evita che una card React sostituisca un wizard
    completo non ancora ricostruito con parita' reale.
    """

    if _deve_mantenere_vista_classica():
        query = request.args.to_dict(flat=True)
        query["_legacy"] = "1"
        return redirect(_local_redirect_target(request.path, query), code=302)

    from core.security.headers import applica_nonce_documento_stabile, prepara_nonce_documento_stabile

    # Nonce CSP stabile per (documento, sessione): serve alla rivalidazione 304 qui sotto.
    prepara_nonce_documento_stabile()
    response = make_response(applica_nonce_documento_stabile(render_template(
        "react_shell.html",
        react_assets=_vite_entry(request.path),
        react_spa_path=spa_path,
        react_bootstrap=_react_bootstrap_payload(),
        react_runtime_flags=_react_runtime_flags(),
        react_bootstrap_texts=[str(item) for item in (bootstrap_texts or []) if str(item or "").strip()],
        react_body_class=_react_body_class_for_path(request.path),
    ), segreto=str(current_app.secret_key or ""), seme=str(session.get("_csrf_token") or session.get("user_id") or "")))
    # Rivalidazione condizionata invece di `no-store`.
    #
    # Il corpo della shell è deterministico per (rotta, utente, studio, versione)
    # e non contiene dati che cambiano fra una richiesta e l'altra: è quindi
    # confrontabile con un ETag calcolato sui byte effettivi della risposta. Se
    # il browser rimanda lo stesso ETag riceve un 304 e riusa il corpo che ha
    # già, risparmiando l'intero documento — 83 kB gzip, di cui il 93% è l'entry
    # React inline — ad ogni navigazione ripetuta.
    #
    # Le direttive scelte non allentano la freschezza: `no-cache` obbliga il
    # browser a rivalidare *prima di ogni uso*, quindi non può mai mostrare una
    # pagina senza aver chiesto al server; `private` vieta la memorizzazione a
    # proxy e cache condivise; `Vary: Cookie` lega la voce di cache alla
    # sessione, così una risposta non può essere riusata per un utente diverso.
    # Il 304 è corretto per costruzione: l'ETag è l'hash dei byte che avremmo
    # inviato, quindi combacia solo se il client ha già esattamente quel corpo.
    #
    # Contropartita accettata e mitigata: il documento può ora essere scritto
    # nella cache del browser dell'utente. Il logout emette `Clear-Site-Data`
    # per rimuoverlo (vedi `web/services/auth_runtime.py`).
    response.headers["Cache-Control"] = "private, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Cookie"
    response.add_etag()
    return response.make_conditional(request)


def _react_runtime_flags() -> dict[str, bool]:
    lower = ((request.path or "/").rstrip("/") or "/").lower()
    settings_surface = lower in {
        "/impostazioni",
        "/impostazioni-studio",
        "/impostazioni/sdi",
        "/impostazioni/pagamenti",
        "/notifiche",
        "/notifiche-whatsapp",
        "/backup",
        "/impostazioni/calendario",
        "/sincronizzazione-calendari",
    }
    signer_surface = settings_surface or lower.startswith("/app-v2/polisweb") or lower.startswith("/app-v2/pdp") or lower.startswith("/app-v2/pat") or lower.startswith("/app-v2/ptt")
    return {
        "settings_guards": settings_surface,
        "local_signer_monitor": signer_surface,
    }


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


def _applicazione_react(lower: str) -> bool:
    """Catalogo e singola funzione della ex cabina applicazioni: ApplicazionePage React."""
    parti = [parte for parte in lower.strip("/").split("/") if parte]
    return parti[:1] == ["applicazioni"] and len(parti) <= 2


def _deve_mantenere_vista_classica() -> bool:
    """Blocca promozioni React non validate fuori dalla shell progressiva."""

    path = (request.path or "").rstrip("/") or "/"
    if path == "/app-v2" or path.startswith("/app-v2/"):
        return False
    forced_react = (request.args.get("_react") or "").strip().lower()
    if forced_react in {"1", "true", "si", "yes", "on"}:
        return False
    enabled = current_app.config.get("REACT_PROMOTE_LEGACY_ROUTES", False)
    if enabled:
        return False
    lower = path.lower()
    # Checklist degli atti e raccolta guidata del fascicolo: ChecklistAttiPage React.
    if _checklist_atti(lower):
        return False
    # Catalogo e funzioni della ex cabina applicazioni: ApplicazionePage React.
    if _applicazione_react(lower):
        return False
    if lower.startswith("/fascicoli/") and lower.endswith("/copertina"):
        return True
    if lower.startswith("/fascicoli/") and lower.endswith("/deposito/prepara"):
        return False
    if lower.startswith("/fascicoli/") and (
        "/wizard/" in lower
        or "/deposito/" in lower
        or "/penale/pdp" in lower
    ):
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
    if lower == "/scadenziario" or lower.startswith("/scadenziario/"):
        if not _scadenziario_react_allowed(lower):
            return True
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
    # Modelli di studio (nuovo, scheda, modifica, compilazione): TemplateStudioPage React.
    if _modello_di_studio(lower):
        return False
    if _scheda_ricerca_legale(lower):
        return False
    if lower == "/template-atti/nuovo":
        return True
    if lower in {"/template-atti/editor", "/template-atti/editor-libero"}:
        return False
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
    # /legal-intelligence/fonte/<id>/scarica e /daily/ restano legacy (download file e rendering server-side).
    if lower.startswith("/legal-intelligence/") and lower not in {
        "/legal-intelligence/mediazione",
        "/legal-intelligence/news",
        "/legal-intelligence/ricerca",
    }:
        return True
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
    if lower.startswith("/legal-intelligence/daily/"):
        return True
    if lower.startswith("/ricerca-legale/daily/"):
        return True
    if lower in _REACT_TELEMATICO_GRAPHICAL_PATHS:
        return False
    if lower in _REACT_TELEMATICO_ACQUISITION_PATHS:
        return False
    return any(lower == prefix or lower.startswith(f"{prefix}/") for prefix in _LEGACY_FIRST_PREFIXES)


def _initials(value: str) -> str:
    parts = [part for part in str(value or "").replace(".", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper()


def _react_bootstrap_payload() -> dict[str, Any]:
    """Dati di sessione reali da usare nella shell React."""

    utente = getattr(g, "utente_corrente", None)
    if not utente:
        return {"user": None, "tenant": None, "permissions": [], "actions": {}}

    ruolo = getattr(getattr(utente, "ruolo", ""), "value", getattr(utente, "ruolo", ""))
    nome = str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or "").strip()
    username = str(getattr(utente, "username", "") or "").strip()
    email = str(getattr(utente, "email", "") or "").strip()
    source = username or nome
    tenant = getattr(g, "tenant", None)
    tenant_payload = None
    if tenant:
        tenant_payload = {
            "slug": str(getattr(tenant, "slug", "") or "").strip(),
            "name": str(getattr(tenant, "nome", "") or getattr(tenant, "name", "") or "").strip(),
        }
    permissions = sorted(
        {
            str(permission).strip()
            for permission in (getattr(utente, "permessi_effettivi", []) or [])
            if str(permission or "").strip()
        }
    )
    payload: dict[str, Any] = {
        "user": {
            "id": str(getattr(utente, "id", "") or ""),
            "username": username,
            "displayName": nome,
            "email": email,
            "role": str(ruolo or "").strip(),
            "initials": _initials(source),
        },
        "tenant": tenant_payload,
        "permissions": permissions,
        "actions": {
            "profile": url_for("profilo"),
            "logout": url_for("logout"),
        },
        "featureFlags": apply_legal_notification_presidia_effective_flags(
            feature_flags_payload(current_app.config)["flags"],
            config=current_app.config,
        ),
    }
    embedded_source = _embedded_source_bootstrap_payload()
    if embedded_source:
        payload["embeddedSourceDetail"] = embedded_source
    return payload


def _embedded_source_bootstrap_payload() -> dict[str, Any]:
    if (request.args.get("embed") or "").strip().lower() != "source":
        return {}
    path = (request.path or "").rstrip("/").lower() or "/"
    if path != "/email":
        return {}
    audit_id = (request.args.get("audit_id") or "").strip()
    if not audit_id:
        return {}
    try:
        from web.blueprints.pec_pipeline_api import _repo

        return {
            "mode": "pec",
            "sourceId": f"pec-audit:{audit_id}",
            "data": _repo().get_message_source_detail(audit_id),
        }
    except Exception as exc:  # pragma: no cover - bootstrap difensivo, la UI ha comunque fetch/errore controllato
        current_app.logger.warning("Fonte PEC embedded non precaricata: %s", exc)
        return {}

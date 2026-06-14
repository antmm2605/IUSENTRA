"""Shell React progressiva per IUSENTRA.

La shell vive sotto ``/app-v2`` e governa le superfici già migrate mantenendo
separati i servizi Flask di scrittura, audit e validazione.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlencode, urlsplit

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for

from web.services.feature_flags import (
    app_v2_route_flag_for_path,
    feature_flags_payload,
    is_feature_enabled,
)

react_shell = Blueprint("react_shell", __name__)


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
    ("/pdp", "src/components/TelematicoSurfacePage.tsx"),
    ("/pat", "src/components/TelematicoSurfacePage.tsx"),
    ("/sigit", "src/components/TelematicoSurfacePage.tsx"),
    ("/ptt", "src/components/TelematicoSurfacePage.tsx"),
    ("/tribunali", "src/components/TelematicoSurfacePage.tsx"),
    ("/guida/firma-digitale", "src/components/TelematicoSurfacePage.tsx"),
    ("/portali/pst/acquisizione", "src/components/TelematicoSurfacePage.tsx"),
    ("/portali/pdp/acquisizione", "src/components/TelematicoSurfacePage.tsx"),
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
    ("/template-atti", "src/components/TemplateAttiPage.tsx"),
    ("/redazione-atti", "src/components/RedazioneAttiPage.tsx"),
    ("/statistiche", "src/components/StatistichePage.tsx"),
    ("/legal-skills", "src/features/legal-skills/pages/LegalSkillsCatalogPage.tsx"),
    ("/procedure-completion", "src/features/procedure-completion/ProcedureCompletionPage.tsx"),
    ("/workflow-agents/approvals", "src/pages/workflow-agents/AgentApprovalQueue.tsx"),
    ("/workflow-agents/runs", "src/pages/workflow-agents/AgentRunDetail.tsx"),
    ("/workflow-agents", "src/pages/workflow-agents/WorkflowAgentsHome.tsx"),
    ("/regia-agentica", "src/pages/workflow-agents/WorkflowAgentsHome.tsx"),
    ("/app/portale-clienti", "src/components/ClientPortalPage.tsx"),
    ("/portale-cliente", "src/components/ClientPortalPage.tsx"),
    ("/ricerca-legale", "src/components/LegalIntelligencePage.tsx"),
    ("/giurisprudenza", "src/components/GiurisprudenzaPage.tsx"),
    ("/strumenti-legali", "src/components/StudioModulePage.tsx"),
    ("/strumenti-operativi", "src/components/StudioModulePage.tsx"),
    ("/sito-studio/redazione-ai", "src/components/SitoStudioRedazioneAiPage.tsx"),
    ("/sito-studio/builder", "src/components/SitoStudioBuilderPage.tsx"),
    ("/sito-studio", "src/components/SitoStudioPage.tsx"),
    ("/amministrazione", "src/components/AmministrazionePage.tsx"),
    ("/utenti", "src/components/UtentiPage.tsx"),
    ("/profili", "src/components/ProfiliPage.tsx"),
    ("/audit", "src/components/AuditPage.tsx"),
    ("/registro-attivita", "src/components/AuditPage.tsx"),
    ("/admin/database", "src/components/AdminDatabasePage.tsx"),
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
    return len(parts) == 4 and parts[0] == "sito-studio" and parts[1] == "articoli" and parts[2].isdigit() and parts[3] == "modifica"


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

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        current_app.logger.exception("Manifest React non leggibile: %s", exc)
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

    route_assets = _collect_manifest_assets(manifest, _route_component_key(current_path))
    return {
        "ready": True,
        "js": [f"/static/react/{entry['file']}"],
        "css": [f"/static/react/{path}" for path in entry.get("css", [])],
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

    response = make_response(render_template(
        "react_shell.html",
        react_assets=_vite_entry(request.path),
        react_spa_path=spa_path,
        react_bootstrap=_react_bootstrap_payload(),
        react_runtime_flags=_react_runtime_flags(),
        react_bootstrap_texts=[str(item) for item in (bootstrap_texts or []) if str(item or "").strip()],
        react_body_class=_react_body_class_for_path(request.path),
    ))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


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
        return True
    if lower.startswith("/profili/"):
        return True
    if lower.startswith("/backup/"):
        return True
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
        return True
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
    return {
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
        "featureFlags": feature_flags_payload(current_app.config)["flags"],
    }

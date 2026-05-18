from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"
APP_ROUTES_PATH = REPO_ROOT / "frontend" / "src" / "app" / "routes.ts"
REGISTRY_PATH = REPO_ROOT / "docs" / "app-v2-page-registry.md"
FRONTEND_PAGES_PATH = REPO_ROOT / "docs" / "frontend-app-v2-pages.md"
ROUTING_MAP_PATH = REPO_ROOT / "docs" / "legacy-to-app-v2-routing-map.md"
AREA_REQUIREMENTS_PATH = REPO_ROOT / "docs" / "app-v2-area-requirements.md"

STATUS_LABELS = {
    "legacy_operational": "legacy",
    "react_operational_partial": "parziale",
    "react_operational_full": "React completa",
    "react_shell": "parziale",
    "react_bridge": "parziale",
}

PHASE7_REQUIRED_STATES = "loading, empty, error, forbidden, not-found, flag-off, readonly/RBAC"
PHASE9_REQUIRED_STATES = "default, loading, empty, error, forbidden, flag-off, readonly, desktop/tablet/mobile"
PHASE10_TEST_COMMANDS = (
    r"python scripts\react-migration\generate_app_v2_test_docs.py --check",
    r"python scripts\smoke_app_v2_all.py --subset inventory",
    r"python scripts\smoke_app_v2_all.py --subset contracts",
    r"python -m pytest -q tests/test_app_v2_test_plan_phase10.py --tb=short",
)

FAMILY_API = {
    "panoramica": "/api/v1/ui/dashboard",
    "regia": "/api/v1/ui/dashboard, /api/workspace-intelligente",
    "agenda": "/api/v1/ui/agenda*, /api/v1/ui/timesheet*",
    "fascicoli": "/api/v1/ui/fascicoli*",
    "anagrafiche": "/api/v1/ui/clienti*, /api/v1/ui/soggetti*",
    "comunicazioni": "/api/v1/ui/messaggi*, /api/v1/ui/email*, /api/v1/ui/email-ordinaria*",
    "scadenze": "/api/v1/ui/scadenziario*, /api/v1/ui/wizard-pro*",
    "documenti": "/api/v1/ui/template-atti*, /api/v1/ui/studio-modules/*, /api/editor/*",
    "telematico": "/api/v1/ui/telematico*, /api/v1/ui/local-signer*",
    "studio": "/api/v1/ui/studio*, /api/v1/ui/studio-modules/*, /api/v1/ui/sito-studio*",
    "ricerca": "/api/v1/ui/legal-intelligence*, /api/v1/ui/giurisprudenza*",
    "mandato": "/api/v1/ui/preventivi*, /api/v1/ui/fatturazione*, /api/v1/ui/tariffario*",
    "economico": "/api/v1/ui/fatturazione*, /api/v1/ui/preventivi*, /api/v1/ui/pagamenti*",
    "amministrazione": "/api/v1/ui/amministrazione*, /api/v1/ui/utenti*, /api/v1/ui/profili*, /api/v1/ui/audit*, /api/v1/ui/admin/database, /api/v1/ui/privacy/registro",
    "impostazioni": "/api/v1/ui/impostazioni*, /api/v1/ui/calendari*, /api/v1/ui/backup*, /api/push/*",
}

FAMILY_STORAGE = {
    "panoramica": "dashboard cache, agenda, fascicoli, comunicazioni tenant-aware",
    "regia": "dashboard cache, workspace intelligente, fascicoli, agenda",
    "agenda": "AGENDA_DB, SCADENZIARIO_DB, timesheet repository",
    "fascicoli": "FASCICOLI_DB, FASCICOLI_DOCS, CLIENTI_DB, audit",
    "anagrafiche": "CLIENTI_DB, SOGGETTI_DB, PARTI_DB",
    "comunicazioni": "MESSAGGI_DB, EMAIL_CASELLA_DB, EMAIL_ORDINARIA_DB, NOTIFICATIONS_DB",
    "scadenze": "SCADENZIARIO_DB, fascicoli, agenda",
    "documenti": "TEMPLATE_ATTI_DB, FASCICOLI_DOCS, intelligence repository",
    "telematico": "TELEMATICO_DB, PDP_PENALE_DB, fascicoli, ricevute, Local Signer",
    "studio": "STUDIO_CONFIG, sito studio, applicazioni, moduli studio",
    "ricerca": "legal intelligence, giurisprudenza, fonti locali",
    "mandato": "PREVENTIVI_DB, FATTURAZIONE_DB, INCASSI_DB, CLIENTI_DB",
    "economico": "FATTURAZIONE_DB, PREVENTIVI_DB, PAGAMENTI_DB",
    "amministrazione": "AUTH_DB, AUDIT_DB, tenant registry, privacy registry, database runtime",
    "impostazioni": "STUDIO_CONFIG, integrazioni, notifiche, backup, calendari",
}

FAMILY_RBAC = {
    "panoramica": "sessione studio valida",
    "regia": "sessione studio valida",
    "agenda": "agenda.leggi / agenda.scrivi quando modifica",
    "fascicoli": "fascicoli.leggi / fascicoli.scrivi quando modifica",
    "anagrafiche": "anagrafiche.leggi / anagrafiche.scrivi quando modifica",
    "comunicazioni": "comunicazioni.leggi / comunicazioni.scrivi; segreti casella mai esposti",
    "scadenze": "scadenze.leggi / scadenze.scrivi",
    "documenti": "documenti.leggi / documenti.scrivi; download e generazione protetti",
    "telematico": "telematico.leggi / telematico.scrivi; Local Signer e portali fail-closed",
    "studio": "studio.leggi / studio.scrivi per configurazioni",
    "ricerca": "ricerca.leggi; fonti e citazioni governate",
    "mandato": "mandato.leggi / mandato.scrivi; calcoli backend",
    "economico": "fatturazione.leggi / fatturazione.scrivi; pagamenti protetti",
    "amministrazione": "admin o permessi utenti/profili/audit specifici",
    "impostazioni": "impostazioni.leggi / impostazioni.scrivi; segreti mascherati",
}

PII_FAMILIES = {
    "agenda",
    "fascicoli",
    "anagrafiche",
    "comunicazioni",
    "documenti",
    "telematico",
    "mandato",
    "economico",
    "amministrazione",
    "impostazioni",
}

@dataclass(frozen=True)
class AppRoute:
    path: str
    label: str
    family: str
    api: str
    feature_flag: str


@dataclass(frozen=True)
class FlaskRoute:
    path: str
    source: str
    owner: str
    methods: str
    templates: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_manifest() -> list[dict[str, object]]:
    payload = json.loads(_read_text(MANIFEST_PATH))
    routes = payload.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("route-manifest.json non contiene una lista routes")
    return [route for route in routes if isinstance(route, dict)]


def _ts_value(raw: str, key: str) -> str:
    match = re.search(rf"{key}:\s*'([^']*)'", raw)
    return match.group(1) if match else ""


def _parse_app_routes() -> tuple[list[AppRoute], dict[str, str]]:
    text = _read_text(APP_ROUTES_PATH)
    app_routes: list[AppRoute] = []
    for match in re.finditer(r"\{([^{}\n]*path:\s*'[^']+'[^{}\n]*)\}", text):
        raw = match.group(1)
        if "label:" not in raw or "family:" not in raw:
            continue
        app_routes.append(
            AppRoute(
                path=_ts_value(raw, "path"),
                label=_ts_value(raw, "label"),
                family=_ts_value(raw, "family"),
                api=_ts_value(raw, "api"),
                feature_flag=_ts_value(raw, "featureFlag"),
            )
        )

    legacy_targets: dict[str, str] = {}
    legacy_match = re.search(r"LEGACY_ROUTE_TARGETS:\s*Record<string,\s*string>\s*=\s*\{(?P<body>.*?)\n\}", text, re.S)
    if legacy_match:
        for key, value in re.findall(r"'([^']+)':\s*'([^']+)'", legacy_match.group("body")):
            legacy_targets[key] = value
    return app_routes, legacy_targets


def _parse_feature_flags() -> list[dict[str, str]]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from web.services.feature_flags import FEATURE_FLAG_DEFINITIONS

    return [
        {
            "key": definition.key,
            "env": definition.env_var,
            "description": definition.description,
            "default": "on" if definition.default else "off",
        }
        for definition in FEATURE_FLAG_DEFINITIONS
    ]


def _quote_route(path: str) -> str:
    return str(path or "/").replace("<", "{").replace(">", "}")


def _parse_flask_routes() -> list[FlaskRoute]:
    routes: list[FlaskRoute] = []
    for path in sorted((REPO_ROOT / "web").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = _read_text(path)
        blueprint_prefixes = {
            name: prefix
            for name, prefix in re.findall(
                r"(\w+)\s*=\s*Blueprint\([^)]*?url_prefix\s*=\s*['\"]([^'\"]+)['\"]",
                text,
                re.S,
            )
        }
        templates = ", ".join(sorted(set(re.findall(r"render_template\(\s*['\"]([^'\"]+)['\"]", text)))) or "non rilevato"
        for match in re.finditer(
            r"@(?P<owner>\w+)\.(?P<decorator>route|get|post)\(\s*['\"](?P<route>[^'\"]+)['\"](?P<args>[^)]*)\)",
            text,
        ):
            owner = match.group("owner")
            decorator = match.group("decorator")
            route = match.group("route")
            args = match.group("args")
            if decorator == "post":
                methods = "POST"
            elif decorator == "get":
                methods = "GET"
            else:
                methods_match = re.search(r"methods\s*=\s*\[([^\]]+)\]", args)
                methods = methods_match.group(1).replace("'", "").replace('"', "").replace(" ", "") if methods_match else "GET"
            prefix = "" if owner == "app" else blueprint_prefixes.get(owner, "")
            full_path = _quote_route((prefix.rstrip("/") + "/" + route.lstrip("/")).rstrip("/") or "/")
            routes.append(
                FlaskRoute(
                    path=full_path,
                    source=rel,
                    owner=owner,
                    methods=methods,
                    templates=templates,
                )
            )
    unique: dict[tuple[str, str, str], FlaskRoute] = {}
    for route in routes:
        unique[(route.path, route.methods, route.source)] = route
    return sorted(unique.values(), key=lambda item: (item.path, item.source, item.methods))


def _family_label(value: str) -> str:
    return str(value or "generale").replace("_", " ")


def _page_name(route: dict[str, object]) -> str:
    raw = str(route.get("route") or "/")
    if raw == "/":
        return "Panoramica"
    cleaned = raw.strip("/").replace("*", "dettaglio").replace("<", "").replace(">", "")
    cleaned = re.sub(r"[:{}]", "", cleaned)
    parts = [part for part in re.split(r"[-_/]+", cleaned) if part]
    return " ".join(part.capitalize() for part in parts[:5]) or "Pagina"


def _priority(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    risk = str(route.get("risk") or "medium")
    if risk == "critical" or (risk == "high" and status != "react_operational_full"):
        return "P0"
    if risk == "high" or (risk == "medium" and status != "react_operational_full"):
        return "P1"
    if risk == "medium":
        return "P2"
    return "P3"


def _tenant_risk(route: dict[str, object]) -> str:
    risk = str(route.get("risk") or "medium")
    family = str(route.get("family") or "")
    if risk == "critical" or family in {"telematico", "comunicazioni", "amministrazione"}:
        return "alto"
    if risk == "high" or family in PII_FAMILIES:
        return "medio-alto"
    return "medio"


def _pii_risk(route: dict[str, object]) -> str:
    family = str(route.get("family") or "")
    risk = str(route.get("risk") or "medium")
    if family in {"comunicazioni", "telematico", "fascicoli", "anagrafiche"}:
        return "alto"
    if family in PII_FAMILIES or risk in {"high", "critical"}:
        return "medio-alto"
    return "medio"


def _feature_flag(route: dict[str, object]) -> str:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from web.services.feature_flags import app_v2_route_flag_for_path

    status = str(route.get("status") or "")
    workspace = str(route.get("workspaceTarget") or "")
    for candidate in (str(route.get("route") or ""), workspace):
        flag = app_v2_route_flag_for_path(candidate)
        if flag:
            return flag
    if status == "react_operational_full" and route.get("unlockFromGate") is True:
        return "da assegnare se entra nella shell App V2"
    if status == "react_operational_partial":
        return "da assegnare prima della promozione a full"
    return "legacy protetto; flag richiesto se promosso in App V2"


def _feature_flag_default(route: dict[str, object]) -> str:
    flag = _feature_flag(route)
    if flag.startswith("routes.appV2."):
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from web.services.feature_flags import FEATURE_FLAGS_BY_KEY

        definition = FEATURE_FLAGS_BY_KEY.get(flag)
        return "on" if definition and definition.default else "off"
    return "non applicabile"


def _flag_off_fallback(route: dict[str, object]) -> str:
    flag = _feature_flag(route)
    if flag.startswith("routes.appV2."):
        return "pagina bloccata con messaggio operativo; nessuna lettura dati"
    return "resta nel percorso governato dal manifest o nel backlog"


def _frontend_protection(route: dict[str, object]) -> str:
    flag = _feature_flag(route)
    if flag.startswith("routes.appV2."):
        return "appV2FeatureFlagForPath + menu nascosto + fetch sospesi"
    return "route non esposta nella shell sperimentale"


def _backend_protection(route: dict[str, object]) -> str:
    flag = _feature_flag(route)
    if flag.startswith("routes.appV2."):
        return "react_shell.app_v2_route_flag_for_path fail-closed"
    return "route gate/contratto legacy conservativo"


def _flag_tests(route: dict[str, object]) -> str:
    flag = _feature_flag(route)
    if flag.startswith("routes.appV2."):
        return "tests/test_feature_flags.py + tests/test_app_v2_feature_flags.py + tests/test_app_v2_routing.py"
    return "da aggiungere prima della promozione"


def _template_for(route_path: str, flask_routes: list[FlaskRoute]) -> str:
    clean = route_path.replace("/*", "")
    matches = [route for route in flask_routes if route.path == clean or (clean != "/" and route.path.startswith(clean + "/"))]
    if not matches:
        return "non rilevato automaticamente"
    templates = []
    for item in matches[:4]:
        templates.append(f"{item.templates} ({item.source})")
    return "; ".join(dict.fromkeys(templates))


def _tests_present(route: dict[str, object]) -> str:
    pieces = ["route-manifest", "check-route-gate"]
    contract = str(route.get("legacyContract") or "")
    if contract:
        pieces.append(contract)
    status = str(route.get("status") or "")
    if status == "react_operational_full":
        pieces.append("check-full-react-route-contract")
    if status == "legacy_operational":
        pieces.append("contratto legacy conservativo")
    return ", ".join(pieces)


def _tests_missing(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    if status == "react_operational_full":
        return "smoke browser tenant A/B e VRT sistematica da estendere"
    if status == "react_operational_partial":
        return "flag on/off, azioni JSON mancanti, browser desktop/tablet/mobile"
    return "feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione"


def _notes(route: dict[str, object]) -> str:
    values = route.get("mustPreserve") or []
    if isinstance(values, list):
        return "; ".join(str(item) for item in values[:5])
    return str(values or "")


def _final_state(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    if status == "react_operational_full":
        return "mantenuta React completa nella fase 3; flag e gate non devono regredire"
    if status == "react_operational_partial":
        return "registrata come parziale e bloccata fino a copertura API/test"
    return "registrata come legacy/backlog; non promossa senza parita reale"


def _app_v2_redirect_target(route: dict[str, object]) -> str:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from web.services.app_v2_routing import build_app_v2_path

    legacy = str(route.get("route") or "")
    if "*" in legacy or ":" in legacy or "{" in legacy:
        return "non attivato; deep link parametrico resta fallback legacy finche' non ha pattern dedicato"
    target = build_app_v2_path(legacy)
    if target:
        return target
    workspace = str(route.get("workspaceTarget") or "")
    if workspace and workspace.startswith("/app"):
        return "candidato shell; mapping esplicito da completare"
    return "nessun target App V2 sicuro"


def _redirect_strategy(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    target = _app_v2_redirect_target(route)
    if target.startswith("/app-v2") and status == "react_operational_full" and route.get("unlockFromGate") is True:
        return "ready_when_flag_on; redirect live non attivo in fase 4"
    if target.startswith("/app-v2") and status == "react_operational_partial":
        return "test_only; flag on solo per verifica controllata"
    if target.startswith("/app-v2"):
        return "no; fallback legacy mantenuto"
    return "pending; mapping esplicito mancante"


def _deep_link_support(route: dict[str, object]) -> str:
    legacy = str(route.get("route") or "")
    if "*" in legacy:
        return "deep link legacy protetto; App V2 richiede pattern dedicato"
    if ":" in legacy or "{" in legacy:
        return "path param preservato solo via helper con segmenti validati"
    return "refresh diretto e query whitelistati; nessun next/return_url"


def _query_support() -> str:
    return "preserva page,q,search,filter,sort,tab,view,from,to,status,drawer,section,focus; blocca next,return_url,redirect,tenant_id,user_id,token"


def _template_classification(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    if status == "react_operational_full":
        return "keep_fallback; rimozione non prevista in fase 4"
    if status == "react_operational_partial":
        return "app_v2_shell_candidate; fallback obbligatorio"
    return "keep_fallback o blocked secondo rischio"


def _routing_test_state(route: dict[str, object]) -> str:
    flag = _feature_flag(route)
    if flag.startswith("routes.appV2."):
        return "routing helper + flag off/on + no open redirect"
    return "inventario; test prima della promozione"


def _phase4_final_state(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    redirect = _redirect_strategy(route)
    if status == "react_operational_full" and redirect.startswith("ready_when_flag_on"):
        return "App V2 redirect ready"
    if status == "react_operational_partial":
        return "App V2 gated"
    if status == "legacy_operational":
        return "legacy fallback"
    return "pending"


def _phase7_frontend_status(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    priority = _priority(route)
    if status == "react_operational_full":
        return "complete_tested" if priority in {"P0", "P1"} else "complete_unverified"
    if status in {"react_operational_partial", "react_shell", "react_bridge"}:
        return "partial"
    return "pending"


def _phase7_ui_states(route: dict[str, object]) -> str:
    phase_status = _phase7_frontend_status(route)
    if phase_status in {"complete_tested", "complete_unverified"}:
        return f"{PHASE7_REQUIRED_STATES}, success se mutazione"
    if phase_status == "partial":
        return "loading/error presenti; completare empty, forbidden, not-found, success; flag-off governato"
    return "fallback legacy o modulo non attivo; nessuna fetch App V2 finche' resta pending"


def _phase7_tests(route: dict[str, object]) -> str:
    phase_status = _phase7_frontend_status(route)
    if phase_status == "complete_tested":
        return "npm test, check-app-v2-frontend, route/flag/backend gates, build Vite"
    if phase_status == "complete_unverified":
        return "gate statici presenti; smoke browser e VRT da estendere"
    if phase_status == "partial":
        return "test flag on/off presenti; test mutazioni e browser da completare"
    return "test da aggiungere prima della promozione App V2"


def _phase7_responsive(route: dict[str, object]) -> str:
    if _phase7_frontend_status(route) == "pending":
        return "pending"
    return "base desktop/tablet/mobile nel design system; smoke browser sistematico da estendere"


def _phase7_accessibility(route: dict[str, object]) -> str:
    if _phase7_frontend_status(route) == "pending":
        return "pending"
    return "heading, button semantici, focus e stati errore governati; axe dedicato non presente"


def _phase7_note(route: dict[str, object]) -> str:
    phase_status = _phase7_frontend_status(route)
    if phase_status == "complete_tested":
        return "Fase 7: guard flag/RBAC, 404 sicura App V2 e no-fetch flag-off coperti dal gate comune."
    if phase_status == "partial":
        return "Fase 7: resta parziale; non promuovere finche' mutazioni, browser e documentazione specifica non sono chiusi."
    return "Fase 7: pending governato; legacy fallback resta attivo e sicuro."


def _phase7_rows(routes: list[dict[str, object]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for route in sorted(routes, key=lambda item: (_priority(item), str(item.get("family") or ""), str(item.get("route") or ""))):
        family = str(route.get("family") or "")
        rows.append(
            [
                _family_label(family),
                str(route.get("route") or ""),
                str(route.get("workspaceTarget") or ""),
                str(route.get("route") or ""),
                str(route.get("targetComponent") or "non assegnato"),
                _feature_flag(route),
                FAMILY_API.get(family, "da censire"),
                "docs/openapi.yaml" if _feature_flag(route).startswith("routes.appV2.") else "gap da contrattualizzare",
                FAMILY_RBAC.get(family, "sessione studio valida"),
                _phase7_ui_states(route),
                _phase7_tests(route),
                _phase7_frontend_status(route),
            ]
        )
    return rows


def _phase9_storybook_state(route: dict[str, object]) -> str:
    if str(route.get("status") or "") == "react_operational_full" and _priority(route) in {"P0", "P1"}:
        return "presente: infrastruttura non bloccante; alternativa leggera validata"
    return "presente: non applicabile finché la pagina resta pending/partial"


def _phase9_component_test(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    priority = _priority(route)
    if status == "react_operational_full" and priority in {"P0", "P1"}:
        return "si: validate_ui_coverage + check-app-v2-frontend"
    if status == "react_operational_full":
        return "parziale: gate statici; estendere prima della priorita P0/P1"
    return "no: test UI prima della promozione"


def _phase9_vrt_state(route: dict[str, object]) -> str:
    if str(route.get("status") or "") == "react_operational_full" and _priority(route) in {"P0", "P1"}:
        return "no: VRT non attivo; gap documentato"
    return "no: pending"


def _phase9_a11y_state(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    priority = _priority(route)
    if status == "react_operational_full" and priority in {"P0", "P1"}:
        return "contratto minimo: heading, bottoni nominati, label input, errori sicuri"
    if status == "react_operational_full":
        return "da estendere se promossa P0/P1"
    return "pending"


def _phase9_final_state(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    priority = _priority(route)
    if status == "react_operational_full" and priority in {"P0", "P1"}:
        return "ui_tested"
    if status == "react_operational_full":
        return "partial"
    if status == "react_operational_partial":
        return "partial"
    if str(route.get("family") or "") == "telematico":
        return "blocked"
    return "pending"


def _phase9_rows(routes: list[dict[str, object]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for route in sorted(routes, key=lambda item: (_priority(item), str(item.get("family") or ""), str(item.get("route") or ""))):
        family = str(route.get("family") or "")
        rows.append(
            [
                _family_label(family),
                str(route.get("route") or ""),
                _priority(route),
                str(route.get("targetComponent") or "non assegnato"),
                _phase9_storybook_state(route),
                _phase9_component_test(route),
                _phase9_vrt_state(route),
                PHASE9_REQUIRED_STATES if _phase9_final_state(route) == "ui_tested" else "pending",
                "desktop, tablet, mobile documentati; browser smoke da estendere" if _phase9_final_state(route) == "ui_tested" else "pending",
                _phase9_a11y_state(route),
                _phase9_final_state(route),
            ]
        )
    return rows


def _phase10_test_state(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    if status == "react_operational_full" and _priority(route) in {"P0", "P1"}:
        return "tested"
    if status in {"react_operational_full", "react_operational_partial"}:
        return "partial"
    if str(route.get("family") or "") == "telematico":
        return "blocked"
    return "pending"


def _phase10_cell(route: dict[str, object], kind: str) -> str:
    state = _phase10_test_state(route)
    if state == "tested":
        values = {
            "backend": "yes: pytest/API + security comuni",
            "frontend": "yes: npm test, typecheck, build e UI coverage",
            "rbac": "yes: permessi e readonly governati",
            "tenant": "yes: tenant isolation comune",
            "flag": "yes: flag off/on e no-fetch flag-off",
            "contract": "yes: OpenAPI/provider map",
            "smoke": "yes: smoke inventory; browser/HTTP se credenziali presenti",
        }
        return values[kind]
    if state == "partial":
        return "partial: gate comuni presenti, casi pagina da estendere"
    if state == "blocked":
        return "blocked: workflow o credenziali esterne non parificati"
    return "pending: test pagina richiesto prima della promozione"


def _phase10_rows(routes: list[dict[str, object]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for route in sorted(routes, key=lambda item: (_priority(item), str(item.get("family") or ""), str(item.get("route") or ""))):
        family = str(route.get("family") or "")
        rows.append(
            [
                _family_label(family),
                str(route.get("route") or ""),
                _priority(route),
                _phase10_cell(route, "backend"),
                _phase10_cell(route, "frontend"),
                _phase10_cell(route, "rbac"),
                _phase10_cell(route, "tenant"),
                _phase10_cell(route, "flag"),
                _phase10_cell(route, "contract"),
                _phase10_cell(route, "smoke"),
                _phase10_test_state(route),
            ]
        )
    return rows


def _md(value: object) -> str:
    text = str(value if value is not None else "").strip()
    text = text.replace("\n", " ").replace("|", "\\|")
    return text or "n.d."


def _registry_rows(routes: list[dict[str, object]], flask_routes: list[FlaskRoute]) -> list[list[str]]:
    rows: list[list[str]] = []
    for route in sorted(routes, key=lambda item: (str(item.get("family") or ""), str(item.get("route") or ""))):
        family = str(route.get("family") or "")
        rows.append(
            [
                _page_name(route),
                str(route.get("route") or ""),
                str(route.get("workspaceTarget") or ""),
                _template_for(str(route.get("route") or ""), flask_routes),
                str(route.get("targetComponent") or "non assegnato"),
                FAMILY_API.get(family, "da censire"),
                FAMILY_STORAGE.get(family, "da censire"),
                STATUS_LABELS.get(str(route.get("status") or ""), str(route.get("status") or "")),
                _feature_flag(route),
                _feature_flag_default(route),
                _flag_off_fallback(route),
                _frontend_protection(route),
                _backend_protection(route),
                _flag_tests(route),
                FAMILY_RBAC.get(family, "sessione studio valida"),
                _tenant_risk(route),
                _pii_risk(route),
                _tests_present(route),
                _tests_missing(route),
                _priority(route),
                _notes(route),
                _redirect_strategy(route),
                _deep_link_support(route),
                _query_support(),
                _routing_test_state(route),
                _template_classification(route),
                _phase4_final_state(route),
                _final_state(route),
            ]
        )
    return rows


def _table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_values = list(headers)
    lines = [
        "| " + " | ".join(_md(header) for header in header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md(cell) for cell in row) + " |")
    return "\n".join(lines)


def _route_in_manifest(path: str, manifest_routes: set[str]) -> bool:
    if path in manifest_routes:
        return True
    for route in manifest_routes:
        if route.endswith("/*") and path.startswith(route[:-1]):
            return True
    return False


def _registry_doc(
    routes: list[dict[str, object]],
    app_routes: list[AppRoute],
    legacy_targets: dict[str, str],
    feature_flags: list[dict[str, str]],
    flask_routes: list[FlaskRoute],
) -> str:
    status_counts = Counter(str(route.get("status") or "") for route in routes)
    risk_counts = Counter(str(route.get("risk") or "") for route in routes)
    priority_counts = Counter(_priority(route) for route in routes)
    family_counts = Counter(str(route.get("family") or "") for route in routes)
    manifest_routes = {str(route.get("route") or "") for route in routes}
    flask_get_pages = [
        route for route in flask_routes
        if "GET" in route.methods and not route.path.startswith("/api") and not _route_in_manifest(route.path, manifest_routes)
    ]

    lines = [
        "# Registro pagine App V2 e migrazione React",
        "",
        "Aggiornato: 2026-05-14, fase 10 `fasereact`.",
        "",
        "Questo registro è generato da `scripts/react-migration/generate_app_v2_page_registry.py` a partire da manifest React, route App V2, feature flag, mapping routing sicuro e discovery Flask. La fase 10 collega il registro alla matrice test end-to-end, mantenendo la copertura UI fase 9 senza dichiarare Storybook come gate visuale completo o VRT attiva.",
        "",
        "## Sintesi discovery",
        "",
        f"- Route nel manifest governato: {len(routes)}.",
        f"- Route React complete: {status_counts.get('react_operational_full', 0)}.",
        f"- Route React parziali: {status_counts.get('react_operational_partial', 0)}.",
        f"- Route legacy operative: {status_counts.get('legacy_operational', 0)}.",
        f"- Route App V2 dichiarate in frontend: {len(app_routes)}.",
        f"- Alias legacy verso App V2 in frontend: {len(legacy_targets)}.",
        f"- Route Flask GET candidate rilevate fuori manifest: {len(flask_get_pages)}.",
        "",
        "### Distribuzione rischio",
        "",
        _table(["Rischio", "Conteggio"], sorted(risk_counts.items())),
        "",
        "### Distribuzione priorita",
        "",
        _table(["Priorita", "Conteggio"], sorted(priority_counts.items())),
        "",
        "### Distribuzione famiglia",
        "",
        _table(["Famiglia", "Conteggio"], sorted(family_counts.items())),
        "",
        "## Stato frontend fase 7",
        "",
        "- Le route P0/P1 gia' `react_operational_full` sono marcate `complete_tested` per il batch fase 7: il gate comune verifica flag, RBAC UI, navigazione, no-fetch flag-off e 404 sicura App V2.",
        "- Le route `legacy_operational` o `react_operational_partial` restano `pending` o `partial`: il fallback legacy resta il percorso sicuro finche' API, mutazioni e smoke browser non sono parificati.",
        "- La 404 sicura App V2 blocca percorsi `/app-v2/*` non censiti senza caricare dashboard o dati riservati.",
        "",
        _table(
            ["Area", "Pagina", "App V2 URL", "Legacy URL", "Component", "Flag", "API", "OpenAPI", "RBAC UI", "Stati UI", "Test", "Stato"],
            _phase7_rows(routes),
        ),
        "",
        "## Requisiti specifici fase 8",
        "",
        "Il registro area/workflow e' generato separatamente in `docs/app-v2-area-requirements.md`. La fase 8 usa quello stato per distinguere aree `complete_tested`, `partial`, `pending` e `blocked`, senza promuovere route legacy/parziali solo perche' il gate frontend comune e' verde.",
        "",
        "## Copertura UI fase 9",
        "",
        "Storybook è presente come infrastruttura frontend, ma non è dichiarato copertura visuale completa né gate VRT. La copertura minima fase 9 usa fixture sicure isolate, `scripts/validate_ui_coverage.py`, `pnpm --filter @iusentra/studio test` e la build Vite. VRT resta gap documentato: nessuna riga viene marcata pronta per regressione visuale senza un comando reale eseguito.",
        "",
        _table(
            ["Area", "Pagina", "Priorita", "Component", "Storybook story", "Component test", "VRT", "Stati coperti", "Responsive", "A11y", "Stato finale"],
            _phase9_rows(routes),
        ),
        "",
        "## Matrice test fase 10",
        "",
        "`docs/test-plan-app-v2.md`, `docs/test-inventory.md` e `docs/test-matrix-app-v2.md` sono generati da `scripts/react-migration/generate_app_v2_test_docs.py`. Lo smoke unico e' `scripts/smoke_app_v2_all.py`; senza credenziali resta inventario o controlli anonimi e non dichiara passati profili autenticati mancanti.",
        "",
        _table(
            ["Area", "Pagina", "Priorita", "Backend", "Frontend", "RBAC", "Tenant", "Feature flag", "Contract", "E2E/Smoke", "Stato test"],
            _phase10_rows(routes),
        ),
        "",
        "## Feature flag censiti",
        "",
        _table(
            ["Flag", "Variabile", "Descrizione", "Default"],
            [[flag["key"], flag["env"], flag["description"], flag["default"]] for flag in feature_flags],
        ),
        "",
        "## Registro ufficiale pagine",
        "",
        _table(
            [
                "Nome pagina",
                "URL legacy",
                "URL React/App V2",
                "Template Jinja",
                "Componente React",
                "Endpoint API",
                "Tabelle/modelli backend",
                "Stato migrazione",
                "Feature flag",
                "Default flag",
                "Fallback flag off",
                "Protezione frontend",
                "Protezione backend",
                "Test flag on/off",
                "Permessi RBAC",
                "Rischio tenant",
                "Rischio PII",
                "Test presenti",
                "Test mancanti",
                "Priorita",
                "Note tecniche",
                "Redirect strategy",
                "Deep link support",
                "Query params support",
                "Stato test routing",
                "Classificazione template legacy",
                "Stato finale fase 4",
                "Nota stato precedente",
            ],
            _registry_rows(routes, flask_routes),
        ),
        "",
        "## Route Flask candidate fuori manifest",
        "",
        "Queste route non vengono promosse dalla fase 3. Sono censite per impedire che restino invisibili nelle prossime fasi: vanno confermate come pagina utente, API/azione tecnica o fallback classico prima di qualsiasi promozione.",
        "",
        _table(
            ["URL", "Metodi", "File", "Template rilevati"],
            [[route.path, route.methods, route.source, route.templates] for route in flask_get_pages[:160]],
        ),
        "",
        "## Regola operativa fase 4",
        "",
        "- P0: route critiche o legacy/parziali ad alto rischio, da chiudere prima del rollout ampio.",
        "- P1: route ad alto rischio gia' React o route legacy/parziali a rischio medio.",
        "- P2: route React complete a rischio medio e backlog governato.",
        "- P3: route a rischio basso o solo di servizio, da trattare dopo le superfici studio principali.",
        "- I flag `routes.appV2.*` delle superfici operative restano attivi di default e spegnibili per rollback; quelli non parificati restano default-off. Se spento, la shell mostra uno stato operativo e non esegue chiamate dati della pagina.",
        "- Ogni redirect legacy -> App V2 deve passare da `web.services.app_v2_routing` e restare spento finche' il flag pagina non e' attivo.",
        "",
    ]
    return "\n".join(lines)


def _frontend_doc(
    routes: list[dict[str, object]],
    app_routes: list[AppRoute],
    legacy_targets: dict[str, str],
) -> str:
    backlog_by_priority: dict[str, list[dict[str, object]]] = defaultdict(list)
    for route in routes:
        if str(route.get("status") or "") != "react_operational_full":
            backlog_by_priority[_priority(route)].append(route)

    lines = [
        "# Pagine frontend App V2",
        "",
        "Aggiornato: 2026-05-14, fase 10 `fasereact`.",
        "",
        "Questo documento e' il riepilogo operativo del registro completo in `docs/app-v2-page-registry.md`. La fase 10 aggiunge piano, inventario, matrice test e smoke orchestrato; la copertura UI fase 9 resta sostenibile con fixture sicure, gate statici e nessuna dichiarazione falsa di Storybook o VRT.",
        "",
        "## Shell App V2",
        "",
        _table(
            ["Path", "Etichetta", "Famiglia", "API", "Feature flag"],
            [[route.path, route.label, route.family, route.api or "nessuna API dedicata", route.feature_flag or "da assegnare"] for route in app_routes],
        ),
        "",
        "## Alias legacy verso App V2",
        "",
        _table(["Legacy", "Target App V2"], sorted(legacy_targets.items())),
        "",
        "## Stato frontend fase 7",
        "",
        "La tabella riporta il batch comune fase 7. `complete_tested` indica route P0/P1 gia' React full coperte dal gate comune; `partial` e `pending` non sono promosse.",
        "",
        _table(
            ["Area", "Pagina", "App V2 URL", "Legacy URL", "Component", "Flag", "API", "OpenAPI", "RBAC UI", "Stati UI", "Test", "Stato"],
            _phase7_rows(routes),
        ),
        "",
        "## Copertura UI fase 9",
        "",
        "La tabella espone Storybook, test UI, VRT, responsive e accessibilita per ogni route. `ui_tested` e' ammesso solo per P0/P1 gia' `react_operational_full` e coperti dal gate `scripts/validate_ui_coverage.py`; VRT resta `no` finche' non esiste un comando reale eseguito.",
        "",
        _table(
            ["Area", "Pagina", "Priorita", "Component", "Storybook story", "Component test", "VRT", "Stati coperti", "Responsive", "A11y", "Stato finale"],
            _phase9_rows(routes),
        ),
        "",
        "## Matrice test fase 10",
        "",
        "Piano, inventario e matrice sono in `docs/test-plan-app-v2.md`, `docs/test-inventory.md` e `docs/test-matrix-app-v2.md`. Il comando `python scripts\\smoke_app_v2_all.py --subset inventory` resta eseguibile senza credenziali; i profili autenticati non configurati non sono marcati verdi.",
        "",
        _table(
            ["Area", "Pagina", "Priorita", "Backend", "Frontend", "RBAC", "Tenant", "Feature flag", "Contract", "E2E/Smoke", "Stato test"],
            _phase10_rows(routes),
        ),
        "",
        "## Backlog per priorita",
        "",
    ]
    for priority in ["P0", "P1", "P2", "P3"]:
        bucket = sorted(backlog_by_priority.get(priority, []), key=lambda item: str(item.get("route") or ""))
        lines.append(f"### {priority}")
        lines.append("")
        if bucket:
            lines.append(
                _table(
                    ["Route", "Famiglia", "Stato", "Rischio", "Target React", "Blocco principale"],
                    [
                        [
                            route.get("route", ""),
                            _family_label(str(route.get("family") or "")),
                            STATUS_LABELS.get(str(route.get("status") or ""), str(route.get("status") or "")),
                            route.get("risk", ""),
                            route.get("workspaceTarget", ""),
                            _tests_missing(route),
                        ]
                        for route in bucket
                    ],
                )
            )
        else:
            lines.append("Nessuna route pendente in questa priorita.")
        lines.append("")

    lines.extend(
        [
            "## Smoke e gate fase 7",
            "",
            "Comandi introdotti o governati dalla fase 7:",
            "",
            "```powershell",
            "python scripts\\react-migration\\generate_app_v2_page_registry.py --check",
            "pnpm --filter @iusentra/studio test:app-v2",
            "pnpm --filter @iusentra/studio test",
            "pnpm --filter @iusentra/studio typecheck",
            "pnpm --filter @iusentra/studio build",
            "python scripts\\smoke_app_v2_pages.py --list",
            "python scripts\\smoke_app_v2_routing.py --list",
            "python scripts\\smoke_app_v2_workflows.py --list",
            "python scripts\\validate_ui_coverage.py",
            "python scripts\\react-migration\\generate_app_v2_test_docs.py --check",
            "python scripts\\smoke_app_v2_all.py --subset inventory",
            "python scripts\\smoke_app_v2_all.py --subset contracts",
            "python scripts\\react-migration\\generate_app_v2_area_requirements.py --check",
            "python -m pytest -q tests/test_app_v2_frontend_phase7.py --tb=short",
            "python -m pytest -q tests/test_app_v2_area_requirements_phase8.py --tb=short",
            "python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short",
            "python -m pytest -q tests/test_app_v2_test_plan_phase10.py --tb=short",
            "python -m pytest -q tests/test_app_v2_page_registry.py --tb=short",
            "python -m pytest -q tests/test_feature_flags.py tests/test_app_v2_feature_flags.py tests/test_app_v2_routing.py --tb=short",
            "```",
            "",
            "Per smoke autenticati usare variabili ambiente, senza credenziali nel repository:",
            "",
            "```powershell",
            "$env:IUSENTRA_BASE_URL='https://app.iusentra.it'",
            "$env:IUSENTRA_SMOKE_USERNAME='<utente>'",
            "$env:IUSENTRA_SMOKE_PASSWORD='<password>'",
            "python scripts\\smoke_app_v2_routing.py --require-credentials",
            "```",
            "",
            "## Requisiti specifici fase 8",
            "",
            "Il file `docs/app-v2-area-requirements.md` e' il registro vincolante per workflow, RBAC, tenant isolation, PII e stato finale per area. Lo smoke `scripts/smoke_app_v2_workflows.py` resta in modalita inventario se mancano le credenziali ambiente e non dichiara passati i profili non configurati.",
            "",
            "## Copertura UI fase 9",
            "",
            "`docs/ui-regression-and-storybook.md` documenta stato Storybook, test UI, fixture sicure, VRT, accessibilita e gap residui. Storybook e VRT non sono dichiarati attivi: il gate minimo e' `python scripts\\validate_ui_coverage.py`, integrato in `pnpm --filter @iusentra/studio test` e nella CI App V2.",
            "",
            "## Piano test fase 10",
            "",
            "La fase 10 rende espliciti inventario, matrice e piano test con `docs/test-plan-app-v2.md`, `docs/test-inventory.md`, `docs/test-matrix-app-v2.md` e `scripts/smoke_app_v2_all.py`. Le righe `tested` indicano gate reali gia' presenti; `partial`, `pending` e `blocked` restano vincoli aperti.",
            "",
            "## Stato fase 7",
            "",
            "La fase 7 chiude il batch comune frontend: le route App V2 non censite mostrano 404 sicura, la navigazione sperimentale nasconde pagine con flag spento o permesso mancante, e lo stato flag-off resta senza chiamate dati della pagina. Le route legacy/parziali restano esplicitamente pendenti.",
            "",
        ]
    )
    return "\n".join(lines)


def _routing_map_doc(
    routes: list[dict[str, object]],
    app_routes: list[AppRoute],
    legacy_targets: dict[str, str],
    flask_routes: list[FlaskRoute],
) -> str:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from web.services.app_v2_routing import LEGACY_TO_APP_V2_TARGETS, SAFE_QUERY_PARAMS, UNSAFE_QUERY_PARAMS

    rows = []
    for route in sorted(routes, key=lambda item: (str(item.get("family") or ""), str(item.get("route") or ""))):
        legacy = str(route.get("route") or "")
        rows.append(
            [
                _family_label(str(route.get("family") or "")),
                legacy,
                _template_for(legacy, flask_routes),
                _app_v2_redirect_target(route),
                str(route.get("targetComponent") or "non assegnato"),
                _feature_flag(route),
                _redirect_strategy(route),
                _flag_off_fallback(route),
                "path params espliciti; wildcard solo legacy" if "*" in legacy else "path diretto",
                ", ".join(sorted(SAFE_QUERY_PARAMS)),
                ", ".join(sorted(UNSAFE_QUERY_PARAMS)),
                _routing_test_state(route),
                _phase4_final_state(route),
                _notes(route),
            ]
        )

    app_route_rows = [
        [route.path, route.label, route.family, route.api or "nessuna API dedicata", route.feature_flag or "da assegnare"]
        for route in app_routes
    ]
    legacy_alias_rows = [
        [legacy, target, LEGACY_TO_APP_V2_TARGETS.get(legacy, "solo normalizzazione frontend")]
        for legacy, target in sorted(legacy_targets.items())
    ]

    lines = [
        "# Mappa routing legacy -> App V2",
        "",
        "Aggiornato: 2026-05-13, fase 4 `fasereact`.",
        "",
        "La fase 4 prepara redirect e fallback senza attivare redirect globali. Ogni passaggio legacy -> App V2 deve usare `web.services.app_v2_routing`, che accetta solo target interni `/app-v2`, blocca query autorizzative o esterne e richiede feature flag pagina acceso.",
        "",
        "## Sintesi",
        "",
        f"- Route manifest analizzate: {len(routes)}.",
        f"- Route App V2 frontend analizzate: {len(app_routes)}.",
        f"- Alias legacy frontend censiti: {len(legacy_targets)}.",
        f"- Mapping backend sicuri censiti: {len(LEGACY_TO_APP_V2_TARGETS)}.",
        "- Redirect attivati live in fase 4: 0.",
        "- Fallback legacy/template: mantenuti per tutte le route non promosse o non abilitate.",
        "",
        "## Query params",
        "",
        f"- Preservati: {', '.join(sorted(SAFE_QUERY_PARAMS))}.",
        f"- Bloccati: {', '.join(sorted(UNSAFE_QUERY_PARAMS))}.",
        "- I parametri `next`, `return_url`, `redirect`, `tenant_id`, `user_id`, `role`, `permission` e token non vengono mai propagati verso App V2.",
        "",
        "## Route App V2 frontend",
        "",
        _table(["Path", "Etichetta", "Famiglia", "API", "Feature flag"], app_route_rows),
        "",
        "## Alias legacy frontend",
        "",
        _table(["Legacy", "Target router frontend", "Target backend sicuro"], legacy_alias_rows),
        "",
        "## Mapping completo manifest",
        "",
        _table(
            [
                "Area",
                "Legacy URL",
                "Template",
                "App V2 URL",
                "Componente React",
                "Flag",
                "Redirect",
                "Fallback",
                "Params",
                "Query preservate",
                "Query bloccate",
                "Test",
                "Stato finale",
                "Note",
            ],
            rows,
        ),
        "",
        "## Attivazione controllata",
        "",
        "1. Accendere solo il flag della pagina interessata.",
        "2. Verificare `should_redirect_to_app_v2(...)` in test con flag off e flag on.",
        "3. Abilitare il redirect nella route legacy specifica, non nel catch-all.",
        "4. Eseguire `python scripts\\smoke_app_v2_routing.py --require-credentials` nell'ambiente target.",
        "5. Spegnere il flag per rollback immediato; il template legacy resta fallback.",
        "",
    ]
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def generate() -> dict[Path, str]:
    routes = _load_manifest()
    app_routes, legacy_targets = _parse_app_routes()
    feature_flags = _parse_feature_flags()
    flask_routes = _parse_flask_routes()
    return {
        REGISTRY_PATH: _registry_doc(routes, app_routes, legacy_targets, feature_flags, flask_routes),
        FRONTEND_PAGES_PATH: _frontend_doc(routes, app_routes, legacy_targets),
        ROUTING_MAP_PATH: _routing_map_doc(routes, app_routes, legacy_targets, flask_routes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera il registro pagine App V2 e React.")
    parser.add_argument("--check", action="store_true", help="Verifica che i documenti siano aggiornati.")
    args = parser.parse_args(argv)
    targets = generate()
    if args.check:
        dirty = [
            str(path.relative_to(REPO_ROOT))
            for path, expected in targets.items()
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if dirty:
            print("Registro App V2 non aggiornato: " + ", ".join(dirty), file=sys.stderr)
            return 1
        print("Registro App V2 aggiornato.")
        return 0

    changed = [path.relative_to(REPO_ROOT).as_posix() for path, content in targets.items() if _write_if_changed(path, content)]
    if changed:
        print("Aggiornati: " + ", ".join(changed))
    else:
        print("Registro App V2 gia' aggiornato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

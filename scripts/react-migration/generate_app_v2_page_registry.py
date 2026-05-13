from __future__ import annotations

import argparse
import ast
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
FEATURE_FLAGS_PATH = REPO_ROOT / "web" / "services" / "feature_flags.py"
REGISTRY_PATH = REPO_ROOT / "docs" / "app-v2-page-registry.md"
FRONTEND_PAGES_PATH = REPO_ROOT / "docs" / "frontend-app-v2-pages.md"

STATUS_LABELS = {
    "legacy_operational": "legacy",
    "react_operational_partial": "parziale",
    "react_operational_full": "React completa",
    "react_shell": "parziale",
    "react_bridge": "parziale",
}

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

APP_V2_AREA_FLAGS = {
    "documenti": "routes.appV2.docsPanel",
    "comunicazioni": "routes.appV2.commsDeposits",
    "agenda": "routes.appV2.agenda",
    "scadenziario": "routes.appV2.deadlines",
    "fascicoli": "routes.appV2.caseFiles",
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
    tree = ast.parse(_read_text(FEATURE_FLAGS_PATH))
    definitions: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "")
        if name != "FeatureFlagDefinition" or len(node.args) < 3:
            continue
        values = []
        for arg in node.args[:3]:
            values.append(arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else "")
        definitions.append({"key": values[0], "env": values[1], "description": values[2]})
    return definitions


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
    status = str(route.get("status") or "")
    workspace = str(route.get("workspaceTarget") or "")
    if workspace.startswith("/app-v2/"):
        segment = workspace.removeprefix("/app-v2/").split("/", 1)[0].split("?", 1)[0]
        return APP_V2_AREA_FLAGS.get(segment, "da assegnare prima del rollout")
    if status == "react_operational_full" and route.get("unlockFromGate") is True:
        return "manifest gate: unlockFromGate=true"
    if status == "react_operational_partial":
        return "da assegnare prima della promozione a full"
    return "legacy protetto; flag richiesto se promosso in App V2"


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
        return "mantenuta React completa nella fase 2; nessuna regressione ammessa"
    if status == "react_operational_partial":
        return "registrata come parziale e bloccata fino a copertura API/test"
    return "registrata come legacy/backlog; non promossa senza parita reale"


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
                FAMILY_RBAC.get(family, "sessione studio valida"),
                _tenant_risk(route),
                _pii_risk(route),
                _tests_present(route),
                _tests_missing(route),
                _priority(route),
                _notes(route),
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
        "Aggiornato: 2026-05-13, fase 2 `fasereact`.",
        "",
        "Questo registro e' generato da `scripts/react-migration/generate_app_v2_page_registry.py` a partire da manifest React, route App V2, feature flag e discovery Flask. Non dichiara migrata una pagina che il manifest non considera gia' `react_operational_full`.",
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
        "## Feature flag censiti",
        "",
        _table(
            ["Flag", "Variabile", "Descrizione", "Default"],
            [[flag["key"], flag["env"], flag["description"], "off"] for flag in feature_flags],
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
                "Permessi RBAC",
                "Rischio tenant",
                "Rischio PII",
                "Test presenti",
                "Test mancanti",
                "Priorita",
                "Note tecniche",
                "Stato finale fase 2",
            ],
            _registry_rows(routes, flask_routes),
        ),
        "",
        "## Route Flask candidate fuori manifest",
        "",
        "Queste route non vengono promosse dalla fase 2. Sono censite per impedire che restino invisibili nelle prossime fasi: vanno confermate come pagina utente, API/azione tecnica o fallback classico prima di qualsiasi promozione.",
        "",
        _table(
            ["URL", "Metodi", "File", "Template rilevati"],
            [[route.path, route.methods, route.source, route.templates] for route in flask_get_pages[:160]],
        ),
        "",
        "## Regola operativa fase 2",
        "",
        "- P0: route critiche o legacy/parziali ad alto rischio, da chiudere prima del rollout ampio.",
        "- P1: route ad alto rischio gia' React o route legacy/parziali a rischio medio.",
        "- P2: route React complete a rischio medio e backlog governato.",
        "- P3: route a rischio basso o solo di servizio, da trattare dopo le superfici studio principali.",
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
        "Aggiornato: 2026-05-13, fase 2 `fasereact`.",
        "",
        "Questo documento e' il riepilogo operativo del registro completo in `docs/app-v2-page-registry.md`. Le route sperimentali App V2 restano sotto feature flag default-off; le route ufficiali gia' React restano governate dal manifest e dal route gate.",
        "",
        "## Shell App V2",
        "",
        _table(
            ["Path", "Etichetta", "Famiglia", "API", "Feature flag"],
            [[route.path, route.label, route.family, route.api or "nessuna API dedicata", route.feature_flag or "nessuno"] for route in app_routes],
        ),
        "",
        "## Alias legacy verso App V2",
        "",
        _table(["Legacy", "Target App V2"], sorted(legacy_targets.items())),
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
            "## Smoke e gate fase 2",
            "",
            "Comandi introdotti o governati dalla fase 2:",
            "",
            "```powershell",
            "python scripts\\react-migration\\generate_app_v2_page_registry.py --check",
            "python scripts\\smoke_app_v2_pages.py --list",
            "python -m pytest -q tests/test_app_v2_page_registry.py --tb=short",
            "```",
            "",
            "Per smoke autenticati usare variabili ambiente, senza credenziali nel repository:",
            "",
            "```powershell",
            "$env:IUSENTRA_BASE_URL='https://app.iusentra.it'",
            "$env:IUSENTRA_SMOKE_USERNAME='<utente>'",
            "$env:IUSENTRA_SMOKE_PASSWORD='<password>'",
            "python scripts\\smoke_app_v2_pages.py --require-credentials",
            "```",
            "",
            "## Stato fase 2",
            "",
            "La fase 2 completa il censimento, la priorizzazione e i gate documentali/smoke. Le route non full restano esplicitamente backlog: non vengono dichiarate complete e saranno trattate nelle fasi successive solo dopo API reali, RBAC, tenant isolation, test e browser verification.",
            "",
        ]
    )
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

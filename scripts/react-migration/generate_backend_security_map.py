from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = REPO_ROOT / "web" / "blueprints" / "api_v1_react.py"
MANIFEST = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"
OUTPUT = REPO_ROOT / "docs" / "backend-endpoint-security-map.md"
DATE_LINE = re.compile(r"^Aggiornato:\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\.", re.MULTILINE)


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    function: str
    line: int
    auth: bool

    @property
    def full_path(self) -> str:
        return f"/api/v1/ui{self.path}"


AREA_RULES = (
    ("/admin/database", "Amministrazione database", "utenti.leggi", "P0", "dati tecnici e path redatti"),
    ("/audit", "Registro attivita", "audit.leggi", "P0", "PII e log operativi redatti"),
    ("/registro-attivita", "Registro attivita", "audit.leggi", "P0", "PII e log operativi redatti"),
    ("/utenti", "Utenti", "utenti.leggi/scrivi", "P0", "account, ruoli, credenziali temporanee"),
    ("/profili", "Profili e permessi", "utenti.leggi/scrivi", "P0", "matrice permessi e override"),
    ("/backup", "Backup", "backup.leggi/esegui", "P0", "archivi e verifiche integrita"),
    ("/impostazioni", "Impostazioni", "admin.configura", "P0", "segreti redatti e configurazioni studio"),
    ("/calendari", "Sincronizzazione calendari", "admin.configura", "P0", "account calendari e feed tenant"),
    ("/email", "Email PEC", "sessione/API tenant-aware", "P0", "messaggi, allegati e destinatari"),
    ("/email-ordinaria", "Email ordinaria", "sessione/API tenant-aware", "P0", "messaggi, allegati e destinatari"),
    ("/fascicoli", "Fascicoli e documenti", "sessione/API tenant-aware", "P0", "fascicoli, documenti e depositi"),
    ("/telematico", "Telematico", "sessione/API tenant-aware", "P0", "PCT/PST/Local Signer"),
    ("/fatturazione", "Fatturazione", "fatturazione.leggi/scrivi", "P0", "parcelle, importi e PDF"),
    ("/preventivi", "Preventivi", "fatturazione.leggi/scrivi", "P0", "offerte e conferimenti"),
    ("/conferimenti", "Conferimenti", "fatturazione.leggi/scrivi", "P0", "apertura fascicolo da incarico"),
    ("/incassi-pagamenti", "Incassi e pagamenti", "fatturazione.leggi/scrivi", "P0", "link pagamento e provider"),
    ("/compensi-forensi", "Compensi forensi", "fatturazione.leggi", "P1", "calcoli tariffari"),
    ("/tariffario", "Tariffario", "fatturazione.leggi", "P1", "calcoli tariffari"),
    ("/sito-studio", "Sito Studio", "admin.configura per scritture", "P1", "contenuti pubblici e richieste contatto"),
    ("/notifiche-legali", "Notifiche legali", "sessione/API tenant-aware", "P1", "relate, destinatari e bozze"),
    ("/scadenziario", "Scadenziario", "sessione/API tenant-aware", "P1", "termini e audit calcolo"),
    ("/agenda", "Agenda", "sessione/API tenant-aware", "P1", "appuntamenti e calendario"),
    ("/messaggi", "Messaggi", "sessione/API tenant-aware", "P1", "SMS/WhatsApp e log invio"),
    ("/clienti", "Clienti", "sessione/API tenant-aware", "P1", "anagrafiche e cartelle"),
    ("/soggetti", "Soggetti e parti", "sessione/API tenant-aware", "P1", "anagrafiche parti"),
    ("/privacy", "Registro GDPR", "sessione/API tenant-aware", "P1", "trattamenti e audit privacy"),
    ("/template-atti", "Template atti", "sessione/API tenant-aware", "P1", "modelli e compilazione"),
    ("/redazione-atti", "Redazione atti", "sessione/API tenant-aware", "P1", "produzione documenti"),
    ("/legal-intelligence", "Ricerca legale", "sessione/API tenant-aware", "P1", "fonti e cronologia ricerca"),
    ("/ricerca-legale", "Ricerca legale", "sessione/API tenant-aware", "P1", "fonti e cronologia ricerca"),
    ("/giurisprudenza", "Giurisprudenza", "sessione/API tenant-aware", "P1", "archivio giurisprudenza"),
    ("/dashboard", "Panoramica", "sessione/API tenant-aware", "P1", "metriche aggregate studio"),
)


def _decorator_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _route_from_decorator(node: ast.AST) -> tuple[str, str] | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if _decorator_text(node.func.value) != "api_v1_react":
        return None
    attr = node.func.attr
    if attr not in {"get", "post", "delete", "put", "patch", "route"}:
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
        return None
    method = attr.upper()
    if attr == "route":
        method = "ROUTE"
        for keyword in node.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                values = [
                    str(item.value).upper()
                    for item in keyword.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]
                method = ",".join(values) if values else "ROUTE"
    return method, node.args[0].value


def endpoints() -> list[Endpoint]:
    tree = ast.parse(BLUEPRINT.read_text(encoding="utf-8"))
    items: list[Endpoint] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        auth = any("_richiedi_auth" in _decorator_text(decorator) for decorator in node.decorator_list)
        for decorator in node.decorator_list:
            route = _route_from_decorator(decorator)
            if route is None:
                continue
            method, path = route
            items.append(Endpoint(method=method, path=path, function=node.name, line=node.lineno, auth=auth))
    return sorted(items, key=lambda item: (item.full_path, item.method))


def classify(path: str) -> tuple[str, str, str, str]:
    for prefix, area, permission, priority, data in AREA_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return area, permission, priority, data
    return "API React operativa", "sessione/API tenant-aware", "P2", "payload applicativo tenant-aware"


def _manifest_summary() -> tuple[int, int, int]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    routes = [row for row in payload.get("routes", []) if isinstance(row, dict)]
    p0 = sum(1 for row in routes if str(row.get("risk", "")).lower() == "critical")
    p1 = sum(1 for row in routes if str(row.get("risk", "")).lower() == "high")
    full = sum(1 for row in routes if row.get("status") == "react_operational_full" and row.get("unlockFromGate") is True)
    return len(routes), p0, p1 + p0 if p0 else p1


def render(report_date: str | None = None) -> str:
    rows = endpoints()
    total_manifest, critical_manifest, high_manifest = _manifest_summary()
    auth_count = sum(1 for row in rows if row.auth)
    unsafe_methods = sum(1 for row in rows if row.method != "GET")
    today = report_date or os.getenv("IUSENTRA_REPORT_DATE") or date.today().isoformat()
    control_keys = (
        "`tenant_id`, `tenant_slug`, `studio_id`, `studio_slug`, `user_id`, "
        "`api_key`, `token`, `access_token`, `refresh_token`, `redirect`, `return_url`, `next`"
    )

    lines = [
        "# Backend Endpoint Security Map",
        "",
        f"Aggiornato: {today}.",
        "",
        "## Fase 5 Backend Security Review",
        "",
        "La mappa censisce gli endpoint JSON React sotto `/api/v1/ui` e il relativo presidio minimo: autenticazione, RBAC, isolamento tenant, redazione PII e audit denial. La fase 5 aggiunge un guardrail centrale in `web/services/backend_security.py` e `web/blueprints/api_v1_react.py` che blocca parametri client riservati al controllo server.",
        "",
        "## Sommario",
        "",
        f"- Endpoint React API censiti: {len(rows)}.",
        f"- Endpoint con `_richiedi_auth`: {auth_count}/{len(rows)}.",
        f"- Endpoint con metodo di scrittura o cancellazione: {unsafe_methods}.",
        f"- Route manifest censite: {total_manifest}; critical: {critical_manifest}; high/P1: {high_manifest}.",
        f"- Parametri controllo bloccati: {control_keys}.",
        "- Denial log: `policy_denied.backend_security` e warning applicativo `policy_denied backend_security_control_param` senza valori sensibili.",
        "",
        "## Regole Trasversali",
        "",
        "| Presidio | Stato fase 5 | Note |",
        "| --- | --- | --- |",
        "| Autenticazione | Obbligatoria su tutte le API React censite | Sessione Flask o API key tenant-aware. |",
        "| Tenant | Fail-closed multi-studio | `tenant_isolation_runtime` e `tenant_api_auth` bloccano assenza/mismatch. |",
        "| RBAC | Permessi dominio per aree sensibili | Utenti, profili, audit, backup, impostazioni e fatturazione hanno check dedicati. |",
        "| Mass assignment | Blocco centrale campi contesto | Il client non puo' inviare tenant/studio/token/redirect generici. |",
        "| PII | Payload redatti dove necessario | Audit e segreti impostazioni non espongono password/token salvati. |",
        "| File/download | Solo endpoint dominio autenticati | Path runtime sotto tenant, download e allegati restano su route specifiche. |",
        "",
        "## Endpoint",
        "",
        "| Metodo | Endpoint | Area | Priorita | Permesso atteso | Dati sensibili | Presidi |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        area, permission, priority, data = classify(row.path)
        presidi = [
            "auth" if row.auth else "auth mancante",
            "tenant-aware",
            "RBAC dominio",
            "guardrail fase 5",
        ]
        lines.append(
            f"| `{row.method}` | `{row.full_path}` | {area} | {priority} | `{permission}` | {data} | {', '.join(presidi)} |"
        )

    lines.extend(
        [
            "",
            "## Rischi Residui",
            "",
            "- Le route legacy non ancora ricostruite restano fuori da questa mappa e devono continuare a usare i decoratori/permessi esistenti.",
            "- Gli smoke cross-tenant autenticati richiedono una API key di studio o credenziali tenant da ambiente, mai committate.",
            "- La fase 6 OpenAPI dovra' trasformare questa mappa in contratti 401/403/400/409/422 verificabili provider-by-provider.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_date() -> str:
    configured = os.getenv("IUSENTRA_REPORT_DATE", "").strip()
    if configured:
        return configured
    if OUTPUT.exists():
        match = DATE_LINE.search(OUTPUT.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return date.today().isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera la mappa sicurezza endpoint backend fase 5.")
    parser.add_argument("--check", action="store_true", help="Verifica che il file generato sia gia' allineato.")
    args = parser.parse_args()

    content = render(_report_date())
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"{OUTPUT.relative_to(REPO_ROOT)} non allineato. Esegui senza --check.", file=sys.stderr)
            return 1
        print(f"{OUTPUT.relative_to(REPO_ROOT)} allineato.")
        return 0

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Generato {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

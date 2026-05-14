from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "app-v2-area-requirements.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class AreaPolicy:
    label: str
    pii: str
    workflows: tuple[str, ...]
    requirements: tuple[str, ...]
    required_tests: tuple[str, ...]


AREA_API = {
    "panoramica": "/api/v1/ui/dashboard",
    "regia": "/api/v1/ui/dashboard, /api/workspace-intelligente",
    "agenda": "/api/v1/ui/agenda*, /api/v1/ui/timesheet*",
    "fascicoli": "/api/v1/ui/fascicoli*",
    "anagrafiche": "/api/v1/ui/clienti*, /api/v1/ui/soggetti*",
    "comunicazioni": "/api/v1/ui/messaggi*, /api/v1/ui/email*, /api/v1/ui/email-ordinaria*, /api/v1/ui/notifiche-legali*",
    "scadenze": "/api/v1/ui/scadenziario*, /api/v1/ui/wizard-pro*",
    "documenti": "/api/v1/ui/template-atti*, /api/v1/ui/redazione-atti*, /api/v1/ui/studio-modules/*, /api/editor/*",
    "telematico": "/api/v1/ui/telematico*, /api/v1/ui/local-signer*",
    "studio": "/api/v1/ui/studio*, /api/v1/ui/studio-modules/*, /api/v1/ui/sito-studio*",
    "ricerca": "/api/v1/ui/legal-intelligence*, /api/v1/ui/giurisprudenza*, /api/v1/ui/ricerca-legale*",
    "mandato": "/api/v1/ui/preventivi*, /api/v1/ui/fatturazione*, /api/v1/ui/tariffario*",
    "economico": "/api/v1/ui/fatturazione*, /api/v1/ui/preventivi*, /api/v1/ui/pagamenti*, /api/v1/ui/incassi-pagamenti*",
    "amministrazione": "/api/v1/ui/amministrazione*, /api/v1/ui/utenti*, /api/v1/ui/profili*, /api/v1/ui/audit*, /api/v1/ui/admin/database, /api/v1/ui/privacy/registro",
    "impostazioni": "/api/v1/ui/impostazioni*, /api/v1/ui/calendari*, /api/v1/ui/backup*, /api/push/*",
}

AREA_RBAC = {
    "panoramica": "sessione studio valida",
    "regia": "sessione studio valida",
    "agenda": "agenda.leggi / agenda.scrivi quando modifica",
    "fascicoli": "fascicoli.leggi / fascicoli.scrivi quando modifica",
    "anagrafiche": "anagrafiche.leggi / anagrafiche.scrivi quando modifica",
    "comunicazioni": "comunicazioni.leggi / comunicazioni.scrivi; segreti casella mai esposti",
    "scadenze": "scadenze.leggi / scadenze.scrivi",
    "documenti": "documenti.leggi / documenti.scrivi; download e generazione protetti",
    "telematico": "telematico.leggi / telematico.scrivi; Local Signer e portali fail-closed",
    "studio": "studio.leggi / studio.scrivi; admin.configura per sito e pubblicazione",
    "ricerca": "ricerca.leggi; fonti e citazioni governate",
    "mandato": "mandato.leggi / mandato.scrivi; calcoli backend",
    "economico": "fatturazione.leggi / fatturazione.scrivi; pagamenti protetti",
    "amministrazione": "admin o permessi utenti/profili/audit specifici",
    "impostazioni": "impostazioni.leggi / impostazioni.scrivi; segreti mascherati",
}

AREA_POLICIES: dict[str, AreaPolicy] = {
    "panoramica": AreaPolicy(
        "Panoramica",
        "metriche aggregate; evitare PII non necessaria",
        ("dashboard tenant-safe", "widget abilitati da flag/RBAC", "azioni verso pagine permesse"),
        ("nessun conteggio globale", "empty/loading/error state", "nessuna fetch se flag App V2 spento"),
        ("dashboard con dati/empty/error", "link nascosti se flag o permesso mancanti", "conteggi tenant-safe"),
    ),
    "regia": AreaPolicy(
        "Regia operativa",
        "metriche e suggerimenti su fascicoli/agenda",
        ("regia studio", "sincronizzazione mailbox", "azioni operative consentite"),
        ("dati solo tenant corrente", "azioni governate da permessi", "nessun dato stale dopo cambio utente"),
        ("render regia", "sync negata senza permesso", "flag off senza API dati"),
    ),
    "agenda": AreaPolicy(
        "Agenda ed eventi",
        "appuntamenti, udienze, riferimenti fascicolo",
        ("calendario", "nuovo appuntamento", "timesheet"),
        ("filtri data validati", "nessun tenant_id dal client", "readonly senza mutazioni", "date in formato italiano"),
        ("calendario con dati/empty", "filtro data invalido", "creazione negata senza permesso", "form non invia tenant_id"),
    ),
    "fascicoli": AreaPolicy(
        "Fascicoli",
        "parti, controparti, documenti, timeline e scadenze",
        ("lista fascicoli", "dettaglio fascicolo", "documenti/scadenze collegati"),
        ("deep link protetto", "collegamenti solo stesso tenant/fascicolo", "azioni create/update/archive protette"),
        ("lista tenant A", "dettaglio cross-tenant negato", "timeline senza leakage", "readonly non muta"),
    ),
    "anagrafiche": AreaPolicy(
        "Clienti e anagrafiche",
        "dati identificativi, fiscali e recapiti",
        ("clienti", "soggetti", "cartelle condivise"),
        ("PII minima nelle liste", "ricerca tenant-safe", "nessun tenant_id/studio_id dal client", "form validati"),
        ("lista clienti tenant A", "cliente tenant B negato", "ricerca senza cross-tenant", "form non invia tenant_id"),
    ),
    "comunicazioni": AreaPolicy(
        "Comunicazioni, PEC e notifiche legali",
        "messaggi, allegati, destinatari, ricevute e segreti casella redatti",
        ("PEC", "email ordinaria", "messaggi", "notifiche legali"),
        ("allegati protetti", "readonly senza invio", "segreti non esposti", "layout responsive due colonne quando previsto"),
        ("dettaglio messaggio tenant-safe", "allegato cross-tenant negato", "invio senza permesso 403", "flag off senza API dati"),
    ),
    "scadenze": AreaPolicy(
        "Scadenze e termini",
        "termini, reminder e collegamenti a fascicolo",
        ("scadenziario", "nuova scadenza", "termini guidati"),
        ("stato completata coerente", "filtri validati", "reminder senza leakage", "audit su modifiche rilevanti"),
        ("lista tenant A", "scadenza tenant B negata", "filtro invalido gestito", "readonly non muta"),
    ),
    "documenti": AreaPolicy(
        "Documenti, redazione e ricerca legale",
        "atti, template, contenuti documento e allegati",
        ("redazione atti", "template", "giurisprudenza", "upload/classificazione", "editor"),
        ("download/upload protetti", "nessun path interno", "MIME e nomi file governati", "fallback sicuro se editor non disponibile"),
        ("preview/download cross-tenant negati", "upload invalido 400/422", "editor nascosto senza permesso", "path traversal negato"),
    ),
    "telematico": AreaPolicy(
        "Servizi telematici",
        "buste, ricevute, allegati, dati ministeriali e Local Signer",
        ("controlli atti", "centro telematico", "PST/PDP/PAT/PTT/SIGP/POLISWEB dove presenti"),
        ("workflow ministeriali non parificati restano fallback", "Local Signer fail-closed", "nessuna credenziale portale cloud", "download/allegati protetti"),
        ("controlli atti React", "portali non parificati pending", "download senza permesso 403", "flag off senza API dati"),
    ),
    "studio": AreaPolicy(
        "Studio e sito studio",
        "configurazioni, contenuti pubblici, richieste contatto e prenotazioni",
        ("studio", "statistiche", "sito studio", "builder", "redazione AI"),
        ("azioni pubblicazione protette", "asset/upload governati", "empty state reali", "nessun dato demo"),
        ("builder con dati/empty", "asset upload senza permesso 403", "contatti tenant-safe", "mobile senza overflow"),
    ),
    "ricerca": AreaPolicy(
        "Ricerca studio e Lex",
        "query, fonti, risultati e cronologia ricerca",
        ("ricerca globale", "ricerca legale", "giurisprudenza"),
        ("risultati filtrati da tenant/RBAC", "nessun leakage tramite conteggi", "query param validati", "fonti citabili"),
        ("query vuota", "query senza risultati", "tenant B zero risultati", "filtro invalido gestito"),
    ),
    "mandato": AreaPolicy(
        "Mandato, preventivi e compensi",
        "offerte, conferimenti, tariffe e dati economici",
        ("preventivi", "wizard", "conferimenti", "compensi", "tariffario"),
        ("calcoli backend", "importi validati", "apertura fascicolo protetta", "readonly senza mutazioni"),
        ("lista preventivi tenant A", "modifica senza permesso 403", "importo invalido 400/422", "apri fascicolo auditato se previsto"),
    ),
    "economico": AreaPolicy(
        "Fatturazione e pagamenti",
        "fatture, parcelle, incassi, provider pagamento e dati fiscali",
        ("fatture", "parcelle", "pagamenti", "export/download"),
        ("download/export protetti", "filtri data/stato validati", "PII fiscale minima", "audit su modifiche economiche"),
        ("fattura tenant B negata", "export senza permesso 403", "download tenant B negato", "importo invalido 400/422"),
    ),
    "amministrazione": AreaPolicy(
        "Amministrazione, utenti e permessi",
        "utenti, ruoli, audit, registro GDPR e database runtime",
        ("utenti", "profili", "audit log", "database", "registro GDPR"),
        ("solo admin autorizzato", "niente auto-escalation", "password hash/token mai in UI", "azioni distruttive confermate"),
        ("non-admin 403", "admin tenant A non vede tenant B", "assegnazione ruolo non autorizzata negata", "audit solo con permesso"),
    ),
    "impostazioni": AreaPolicy(
        "Impostazioni e integrazioni",
        "configurazioni studio, PEC/SMTP, notifiche, backup, calendari e segreti redatti",
        ("dati studio", "PEC/SMTP", "pagamenti", "notifiche", "backup", "calendari"),
        ("segreti mai restituiti in chiaro", "update secret non ritorna secret", "form validati", "readonly non muta"),
        ("non autorizzato 403", "tenant A non vede settings B", "secret mascherato", "form invalido 400/422"),
    ),
}


def _read_manifest() -> list[dict[str, object]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    routes = payload.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("route-manifest.json non contiene una lista routes")
    return [route for route in routes if isinstance(route, dict)]


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


def _feature_flag(route: dict[str, object]) -> str:
    from web.services.feature_flags import app_v2_route_flag_for_path

    for candidate in (str(route.get("route") or ""), str(route.get("workspaceTarget") or "")):
        flag = app_v2_route_flag_for_path(candidate)
        if flag:
            return flag
    return "legacy protetto; flag da assegnare prima della promozione"


def _area_for_route(route: dict[str, object]) -> str:
    family = str(route.get("family") or "generale")
    legacy = str(route.get("route") or "")
    workspace = str(route.get("workspaceTarget") or "")
    flag = _feature_flag(route)
    if (
        flag.startswith("routes.appV2.settings.")
        or legacy.startswith("/impostazioni")
        or legacy in {"/backup", "/notifiche", "/notifiche-whatsapp", "/sincronizzazione-calendari"}
        or workspace.startswith("/app/impostazioni")
    ):
        return "impostazioni"
    return family


def _area_status(area: str, routes: list[dict[str, object]]) -> str:
    if not routes:
        return "not_present"
    statuses = {str(route.get("status") or "") for route in routes}
    if statuses == {"react_operational_full"}:
        priorities = {_priority(route) for route in routes}
        if priorities & {"P0", "P1"}:
            return "complete_tested"
        return "complete_unverified"
    if area == "telematico" and statuses <= {"legacy_operational", "react_operational_full"}:
        return "blocked"
    if "react_operational_full" in statuses or "react_operational_partial" in statuses:
        return "partial"
    return "pending"


def _tests_present(area: str, status: str) -> str:
    common = "tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list"
    if status == "complete_tested":
        return common + "; gate fase 7; provider verification P0/P1; build Vite"
    if status == "complete_unverified":
        return common + "; gate statici; smoke browser dedicato da estendere"
    if area == "telematico":
        return common + "; controlli atti React; workflow ministeriali non parificati marcati blocked"
    return common + "; test specifici da completare prima della promozione"


def _status_note(status: str) -> str:
    return {
        "complete_tested": "area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8",
        "complete_unverified": "area React full senza P0/P1; smoke workflow autenticato da estendere",
        "partial": "area mista: alcune route sono React full, altre parziali o legacy",
        "pending": "area presente ma ancora senza parita React/App V2 completa",
        "blocked": "presente ma bloccata da workflow non parificati o rimandati esplicitamente",
        "not_present": "area non rilevata nel manifest corrente",
    }[status]


def _md(value: object) -> str:
    text = str(value if value is not None else "").strip()
    text = text.replace("\n", " ").replace("|", "\\|")
    return text or "n.d."


def _table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_values = list(headers)
    lines = [
        "| " + " | ".join(_md(header) for header in header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md(cell) for cell in row) + " |")
    return "\n".join(lines)


def _join(values: Iterable[object], *, limit: int | None = None) -> str:
    items = [str(value) for value in values if str(value).strip()]
    if limit is not None and len(items) > limit:
        visible = items[:limit]
        visible.append(f"+{len(items) - limit} altre")
        return "; ".join(visible)
    return "; ".join(items) if items else "n.d."


def build_doc(routes: list[dict[str, object]]) -> str:
    routes_by_area: dict[str, list[dict[str, object]]] = defaultdict(list)
    for route in routes:
        routes_by_area[_area_for_route(route)].append(route)

    all_areas = sorted(set(AREA_POLICIES) | set(routes_by_area))
    status_counts = Counter(_area_status(area, routes_by_area.get(area, [])) for area in all_areas)
    priority_counts = Counter(_priority(route) for route in routes)

    area_rows: list[list[str]] = []
    detail_sections: list[str] = []
    for area in all_areas:
        policy = AREA_POLICIES.get(
            area,
            AreaPolicy(
                area.replace("_", " ").title(),
                "da censire",
                ("workflow presente nel manifest",),
                ("tenant-safe", "RBAC", "stati UI completi"),
                ("test area da censire",),
            ),
        )
        area_routes = sorted(routes_by_area.get(area, []), key=lambda item: (_priority(item), str(item.get("route") or "")))
        status = _area_status(area, area_routes)
        flags = sorted({_feature_flag(route) for route in area_routes}) if area_routes else []
        pages = [str(route.get("route") or "") for route in area_routes]
        app_urls = [str(route.get("workspaceTarget") or "") for route in area_routes]
        priorities = sorted({_priority(route) for route in area_routes}) if area_routes else []
        route_statuses = Counter(str(route.get("status") or "") for route in area_routes)
        tests_present = _tests_present(area, status)

        area_rows.append(
            [
                policy.label,
                _join(pages, limit=8),
                _join(app_urls, limit=6),
                _join(flags, limit=6),
                AREA_RBAC.get(area, "sessione studio valida"),
                policy.pii,
                _join(policy.workflows),
                _join(policy.required_tests),
                tests_present,
                _join(priorities),
                status,
            ]
        )

        detail_sections.extend(
            [
                f"### {policy.label}",
                "",
                f"- Stato: `{status}` ({_status_note(status)}).",
                f"- Route censite: {len(area_routes)}; priorita: {_join(priorities) if priorities else 'n.d.'}; migrazione: {_join(f'{key}={value}' for key, value in sorted(route_statuses.items())) if route_statuses else 'n.d.'}.",
                f"- URL legacy principali: {_join(pages, limit=12)}.",
                f"- URL App V2: {_join(app_urls, limit=12)}.",
                f"- Endpoint API: {AREA_API.get(area, 'da censire')}.",
                f"- Feature flag: {_join(flags, limit=12)}.",
                f"- RBAC: {AREA_RBAC.get(area, 'sessione studio valida')}.",
                f"- PII: {policy.pii}.",
                f"- Workflow principali: {_join(policy.workflows)}.",
                f"- Requisiti specifici verificati o governati: {_join(policy.requirements)}.",
                f"- Test richiesti: {_join(policy.required_tests)}.",
                f"- Test presenti fase 8: {tests_present}.",
                f"- Rischio residuo: {'nessuna promozione ulteriore senza smoke autenticato area-specifico' if status != 'complete_tested' else 'estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente'}.",
                "",
            ]
        )

    lines = [
        "# Requisiti specifici App V2 per area",
        "",
        "Aggiornato: 2026-05-13, fase 8 `fasereact` con collegamento fase 9 e fase 10.",
        "",
        "Questo registro e' generato da `scripts/react-migration/generate_app_v2_area_requirements.py` a partire dal manifest React e dai gate di sicurezza/API gia' censiti. Serve a impedire promozioni generiche: ogni area deve dichiarare workflow, RBAC, tenant isolation, PII, test presenti e test mancanti prima di passare alle fasi visuali successive.",
        "",
        "## Sintesi",
        "",
        f"- Aree rilevate o governate: {len(all_areas)}.",
        f"- Route nel manifest: {len(routes)}.",
        f"- Priorita route: {_join(f'{key}={value}' for key, value in sorted(priority_counts.items()))}.",
        f"- Stato aree: {_join(f'{key}={value}' for key, value in sorted(status_counts.items()))}.",
        "- `complete_tested` non viene assegnato a un'area con route legacy/parziali o senza gate fase 8.",
        "- Le aree non parificate restano `partial`, `pending` o `blocked` e non devono essere esposte come complete nella shell App V2.",
        "",
        "## Registro requisiti",
        "",
        _table(
            ["Area", "Pagine", "URL App V2", "Flag", "RBAC", "PII", "Workflow", "Test richiesti", "Test presenti", "Priorita", "Stato"],
            area_rows,
        ),
        "",
        "## Dettaglio aree",
        "",
        *detail_sections,
        "## Collegamento UI regression fase 9",
        "",
        "La copertura visuale e di regressione e' documentata in `docs/ui-regression-and-storybook.md` e nella sezione `Copertura UI fase 9` di `docs/frontend-app-v2-pages.md` e `docs/app-v2-page-registry.md`. Storybook e VRT restano non attivi finche' non esiste un comando reale; le aree con route `partial`, `pending` o `blocked` non possono essere promosse a `ui_tested`.",
        "",
        "Gate fase 9:",
        "",
        "```powershell",
        "python scripts\\validate_ui_coverage.py",
        "python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short",
        "npm --prefix frontend run test",
        "```",
        "",
        "## Collegamento test plan fase 10",
        "",
        "La fase 10 collega ogni area al piano test App V2 senza promuovere automaticamente pagine incomplete. La matrice di dettaglio e' in `docs/test-matrix-app-v2.md`, l'inventario in `docs/test-inventory.md` e il piano operativo in `docs/test-plan-app-v2.md`.",
        "",
        "Gate fase 10:",
        "",
        "```powershell",
        "python scripts\\react-migration\\generate_app_v2_test_docs.py --check",
        "python scripts\\smoke_app_v2_all.py --subset inventory",
        "python -m pytest -q tests/test_app_v2_test_plan_phase10.py --tb=short",
        "```",
        "",
        "## Smoke workflow fase 8",
        "",
        "Lo smoke autenticato e' in `scripts/smoke_app_v2_workflows.py`. Senza le variabili ambiente richieste esegue solo inventario e lo dichiara esplicitamente; con `--require-credentials` fallisce se le credenziali non sono presenti.",
        "",
        "```powershell",
        "python scripts\\smoke_app_v2_workflows.py --list",
        "$env:IUSENTRA_BASE_URL='https://app.iusentra.it'",
        "$env:IUSENTRA_ADMIN_USER='<utente-admin>'",
        "$env:IUSENTRA_ADMIN_PASSWORD='<password-admin>'",
        "$env:IUSENTRA_TENANT_A_USER='<utente-tenant-a>'",
        "$env:IUSENTRA_TENANT_A_PASSWORD='<password-tenant-a>'",
        "$env:IUSENTRA_TENANT_B_USER='<utente-tenant-b>'",
        "$env:IUSENTRA_TENANT_B_PASSWORD='<password-tenant-b>'",
        "$env:IUSENTRA_READONLY_USER='<utente-sola-lettura>'",
        "$env:IUSENTRA_READONLY_PASSWORD='<password-sola-lettura>'",
        "python scripts\\smoke_app_v2_workflows.py --require-credentials",
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera il registro requisiti area App V2 fase 8.")
    parser.add_argument("--check", action="store_true", help="Verifica che docs/app-v2-area-requirements.md sia aggiornato.")
    args = parser.parse_args(argv)

    content = build_doc(_read_manifest())
    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != content:
            print(f"{OUTPUT_PATH.relative_to(REPO_ROOT)} non aggiornato: eseguire senza --check.", file=sys.stderr)
            return 1
        print(f"{OUTPUT_PATH.relative_to(REPO_ROOT)} aggiornato.")
        return 0
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Scritto {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

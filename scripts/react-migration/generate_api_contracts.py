from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = REPO_ROOT / "web" / "blueprints" / "api_v1_react.py"
FRONTEND_PAGES = REPO_ROOT / "docs" / "frontend-app-v2-pages.md"
OPENAPI_OUTPUT = REPO_ROOT / "docs" / "openapi.yaml"
CONTRACT_MAP_OUTPUT = REPO_ROOT / "docs" / "api-endpoint-contract-map.md"
API_CONTRACTS_OUTPUT = REPO_ROOT / "docs" / "api-contracts.md"
DATE_LINE = re.compile(r"^Aggiornato:\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\.", re.MULTILINE)
PROJECT_VERSION_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def _project_version() -> str:
    init_file = REPO_ROOT / "pct" / "__init__.py"
    match = PROJECT_VERSION_RE.search(init_file.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError("Versione progetto non trovata in pct/__init__.py")
    return match.group(1)


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

    @property
    def openapi_path(self) -> str:
        return _flask_path_to_openapi(self.full_path)


@dataclass(frozen=True)
class ContractInfo:
    area: str
    permission: str
    priority: str
    data: str
    response_schema: str
    tag: str


AREA_RULES: tuple[tuple[str, ContractInfo], ...] = (
    (
        "/admin/database",
        ContractInfo("Amministrazione database", "utenti.leggi", "P0", "dati tecnici redatti", "AdminDatabaseResponse", "Admin"),
    ),
    ("/audit", ContractInfo("Registro attivita", "audit.leggi", "P0", "eventi audit redatti", "AuditLogResponse", "Admin")),
    ("/registro-attivita", ContractInfo("Registro attivita", "audit.leggi", "P0", "eventi audit redatti", "AuditLogResponse", "Admin")),
    ("/utenti", ContractInfo("Utenti", "utenti.leggi/scrivi", "P0", "account e ruoli", "UsersResponse", "Admin")),
    ("/profili", ContractInfo("Profili e permessi", "utenti.leggi/scrivi", "P0", "matrice permessi", "RolesResponse", "Admin")),
    ("/backup", ContractInfo("Backup", "backup.leggi/esegui", "P0", "archivi e verifiche", "BackupResponse", "Admin")),
    ("/impostazioni", ContractInfo("Impostazioni", "admin.configura", "P0", "configurazioni e segreti redatti", "SettingsResponse", "Settings")),
    ("/calendari", ContractInfo("Sincronizzazione calendari", "admin.configura", "P0", "account calendario tenant", "CalendarSyncResponse", "Settings")),
    ("/email-ordinaria", ContractInfo("Email ordinaria", "sessione/API tenant-aware", "P0", "messaggi e allegati", "EmailResponse", "Comunicazioni")),
    ("/email", ContractInfo("Email PEC", "sessione/API tenant-aware", "P0", "messaggi e allegati", "EmailResponse", "Comunicazioni")),
    ("/fascicoli", ContractInfo("Fascicoli e documenti", "sessione/API tenant-aware", "P0", "fascicoli e documenti", "CaseFilesResponse", "Fascicoli")),
    ("/telematico", ContractInfo("Telematico", "sessione/API tenant-aware", "P0", "PCT/PST/Local Signer", "TelematicoResponse", "Telematico")),
    ("/fatturazione", ContractInfo("Fatturazione", "fatturazione.leggi/scrivi", "P0", "parcelle e importi", "BillingResponse", "Mandato")),
    ("/preventivi", ContractInfo("Preventivi", "fatturazione.leggi/scrivi", "P0", "preventivi e conferimenti", "QuoteResponse", "Mandato")),
    ("/conferimenti", ContractInfo("Conferimenti", "fatturazione.leggi/scrivi", "P0", "incarichi e fascicoli", "QuoteResponse", "Mandato")),
    ("/incassi-pagamenti", ContractInfo("Incassi e pagamenti", "fatturazione.leggi/scrivi", "P0", "pagamenti e provider", "PaymentResponse", "Mandato")),
    ("/compensi-forensi", ContractInfo("Compensi forensi", "fatturazione.leggi", "P1", "calcoli tariffari", "FeeResponse", "Mandato")),
    ("/tariffario", ContractInfo("Tariffario", "fatturazione.leggi", "P1", "voci e calcoli", "FeeResponse", "Mandato")),
    ("/sito-studio", ContractInfo("Sito Studio", "admin.configura per scritture", "P1", "contenuti pubblici e richieste", "StudioSiteResponse", "Studio")),
    ("/notifiche-legali", ContractInfo("Notifiche legali", "sessione/API tenant-aware", "P1", "relate e destinatari", "LegalNotificationResponse", "Comunicazioni")),
    ("/scadenziario", ContractInfo("Scadenziario", "sessione/API tenant-aware", "P1", "termini e audit calcolo", "DeadlineResponse", "Agenda")),
    ("/agenda", ContractInfo("Agenda", "sessione/API tenant-aware", "P1", "appuntamenti e calendario", "AgendaResponse", "Agenda")),
    ("/messaggi", ContractInfo("Messaggi", "sessione/API tenant-aware", "P1", "SMS/WhatsApp", "MessageResponse", "Comunicazioni")),
    ("/clienti", ContractInfo("Clienti", "sessione/API tenant-aware", "P1", "anagrafiche e cartelle", "ClientResponse", "Anagrafiche")),
    ("/soggetti", ContractInfo("Soggetti e parti", "sessione/API tenant-aware", "P1", "parti e contatti", "ContactResponse", "Anagrafiche")),
    ("/privacy", ContractInfo("Registro GDPR", "sessione/API tenant-aware", "P1", "trattamenti privacy", "PrivacyRegistryResponse", "Admin")),
    ("/template-atti", ContractInfo("Template atti", "sessione/API tenant-aware", "P1", "modelli e compilazione", "TemplateResponse", "Documenti")),
    ("/redazione-atti", ContractInfo("Redazione atti", "sessione/API tenant-aware", "P1", "produzione documenti", "DocumentDraftingResponse", "Documenti")),
    ("/legal-intelligence", ContractInfo("Ricerca legale", "sessione/API tenant-aware", "P1", "fonti e news", "LegalResearchResponse", "Lex")),
    ("/ricerca-legale", ContractInfo("Ricerca legale", "sessione/API tenant-aware", "P1", "fonti e news", "LegalResearchResponse", "Lex")),
    ("/giurisprudenza", ContractInfo("Giurisprudenza", "sessione/API tenant-aware", "P1", "archivio giurisprudenza", "CaseLawResponse", "Lex")),
    ("/dashboard", ContractInfo("Panoramica", "sessione/API tenant-aware", "P1", "metriche aggregate", "DashboardResponse", "Dashboard")),
    ("/global-search", ContractInfo("Ricerca globale", "sessione/API tenant-aware", "P1", "risultati tenant-aware", "SearchResponse", "Ricerca")),
    ("/bootstrap", ContractInfo("Bootstrap React", "sessione/API tenant-aware", "P1", "sessione e navigazione", "BootstrapResponse", "Sistema")),
    ("/feature-flags", ContractInfo("Feature flags", "sessione/API tenant-aware", "P1", "flag route", "FeatureFlagsResponse", "Sistema")),
)

SUCCESS_PROVIDER_SAMPLES = {
    "/api/v1/ui/feature-flags",
    "/api/v1/ui/bootstrap",
    "/api/v1/ui/dashboard",
    "/api/v1/ui/fascicoli",
    "/api/v1/ui/clienti",
    "/api/v1/ui/soggetti",
    "/api/v1/ui/agenda",
    "/api/v1/ui/scadenziario",
    "/api/v1/ui/messaggi",
    "/api/v1/ui/email",
    "/api/v1/ui/email-ordinaria",
    "/api/v1/ui/template-atti",
    "/api/v1/ui/impostazioni",
    "/api/v1/ui/admin/database",
    "/api/v1/ui/audit",
    "/api/v1/ui/utenti",
    "/api/v1/ui/profili",
    "/api/v1/ui/studio",
    "/api/v1/ui/telematico",
    "/api/v1/ui/legal-intelligence",
    "/api/v1/ui/giurisprudenza",
    "/api/v1/ui/ricerca-legale",
    "/api/v1/ui/fatturazione",
    "/api/v1/ui/preventivi",
    "/api/v1/ui/incassi-pagamenti",
    "/api/v1/ui/compensi-forensi",
    "/api/v1/ui/tariffario",
}


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
    if attr == "route":
        methods: list[str] = []
        for keyword in node.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                methods = [
                    str(item.value).upper()
                    for item in keyword.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]
        return ",".join(methods or ["GET"]), node.args[0].value
    return attr.upper(), node.args[0].value


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
            methods, path = route
            for method in methods.split(","):
                items.append(Endpoint(method=method, path=path, function=node.name, line=node.lineno, auth=auth))
    return sorted(items, key=lambda item: (item.full_path, item.method))


def classify(path: str) -> ContractInfo:
    for prefix, info in AREA_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return info
    return ContractInfo(
        "API React operativa",
        "sessione/API tenant-aware",
        "P2",
        "payload applicativo tenant-aware",
        "UiOperationResponse",
        "Sistema",
    )


def _flask_path_to_openapi(path: str) -> str:
    return re.sub(r"<(?:(?:int|string|path|uuid):)?([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", path)


def _path_parameters(path: str) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    for match in re.finditer(r"<(?:(int|string|path|uuid):)?([A-Za-z_][A-Za-z0-9_]*)>", path):
        converter, name = match.groups()
        schema: dict[str, Any] = {"type": "integer" if converter == "int" else "string"}
        if converter == "uuid":
            schema["format"] = "uuid"
        params.append(
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": schema,
                "description": "Parametro interno della risorsa, risolto nel tenant corrente.",
            }
        )
    return params


def _common_query_parameters(endpoint: Endpoint) -> list[dict[str, Any]]:
    if endpoint.method != "GET":
        return []
    if any(token in endpoint.path for token in ("/callback", "/preview", "/status")):
        return []
    return [
        {"$ref": "#/components/parameters/PageParam"},
        {"$ref": "#/components/parameters/PageSizeParam"},
        {"$ref": "#/components/parameters/SearchParam"},
        {"$ref": "#/components/parameters/StatusParam"},
    ]


def _read_frontend_api_links() -> dict[str, tuple[str, str]]:
    if not FRONTEND_PAGES.exists():
        return {}
    links: dict[str, tuple[str, str]] = {}
    table_started = False
    for raw_line in FRONTEND_PAGES.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## Shell App V2"):
            table_started = True
            continue
        if table_started and line.startswith("## "):
            break
        if not table_started or not line.startswith("| ") or line.startswith("| ---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 5 or parts[0] == "Path":
            continue
        page_path, label, _family, api_path, flag = parts[:5]
        if api_path.startswith("/api/"):
            links[api_path.replace(":id", "{id}")] = (f"{label} ({page_path})", flag)
    return links


def _schema_ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _response_ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/responses/{name}"}


def _operation(endpoint: Endpoint, frontend_links: dict[str, tuple[str, str]]) -> dict[str, Any]:
    info = classify(endpoint.path)
    frontend = frontend_links.get(endpoint.openapi_path) or frontend_links.get(endpoint.full_path)
    page = frontend[0] if frontend else info.area
    flag = frontend[1] if frontend else "non applicabile o governato dalla route collegata"
    provider = "success+auth-error" if endpoint.full_path in SUCCESS_PROVIDER_SAMPLES else "auth-error"

    operation: dict[str, Any] = {
        "tags": [info.tag],
        "summary": f"{info.area}: {endpoint.method} {endpoint.openapi_path}",
        "description": (
            f"Contratto fase 6 derivato da `{endpoint.function}` in `web/blueprints/api_v1_react.py:{endpoint.line}`. "
            f"Pagina/area collegata: {page}. I dati sono sempre nel tenant corrente; il client non puo' forzare tenant/studio/user."
        ),
        "operationId": f"reactUi_{endpoint.function}_{endpoint.method.lower()}",
        "security": [{"cookieSession": []}, {"apiKeyAuth": []}],
        "parameters": _path_parameters(endpoint.full_path) + _common_query_parameters(endpoint),
        "responses": {
            "200": {
                "description": f"Payload operativo {info.area} nel tenant corrente.",
                "content": {"application/json": {"schema": _schema_ref(info.response_schema)}},
            },
            "400": _response_ref("BadRequest"),
            "401": _response_ref("Unauthorized"),
            "403": _response_ref("Forbidden"),
            "404": _response_ref("NotFound"),
            "409": _response_ref("Conflict"),
            "422": _response_ref("ValidationError"),
            "429": _response_ref("RateLimited"),
            "500": _response_ref("ServerError"),
        },
        "x-priority": info.priority,
        "x-rbac-permission": info.permission,
        "x-feature-flag": flag,
        "x-tenant-scope": "current_tenant",
        "x-pii-policy": "no tenant_id/studio_id, token, secret o path filesystem in chiaro salvo campo funzionale redatto.",
        "x-provider-verification": provider,
        "x-contract-status": "verified" if provider == "success+auth-error" else "complete",
    }
    if endpoint.method in {"POST", "PUT", "PATCH", "DELETE"}:
        media_type = "multipart/form-data" if "upload" in endpoint.path else "application/json"
        schema = "DocumentUploadRequest" if media_type == "multipart/form-data" else "MutationRequest"
        operation["requestBody"] = {
            "required": endpoint.method in {"POST", "PUT", "PATCH"},
            "content": {media_type: {"schema": _schema_ref(schema)}},
            "description": "Payload validato dal dominio; campi di controllo server vietati dal guardrail fase 5.",
        }
        if media_type == "multipart/form-data":
            operation["responses"]["413"] = _response_ref("PayloadTooLarge")
            operation["responses"]["415"] = _response_ref("UnsupportedMediaType")
    return operation


def _domain_response_schema(title: str, item_schema: str | None = None) -> dict[str, Any]:
    item_ref = _schema_ref(item_schema or "DomainRecord")
    return {
        "type": "object",
        "description": title,
        "properties": {
            "ok": {"type": "boolean"},
            "data": _schema_ref("DomainRecord"),
            "items": {"type": "array", "items": item_ref},
            "record": item_ref,
            "summary": _schema_ref("DomainRecord"),
            "actions": {"type": "array", "items": _schema_ref("ActionLink")},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "pagination": _schema_ref("PaginationMeta"),
            "meta": _schema_ref("DomainRecord"),
            "message": {"type": "string"},
        },
        "additionalProperties": True,
    }


def _components() -> dict[str, Any]:
    schemas: dict[str, Any] = {
        "DomainRecord": {
            "type": "object",
            "description": "Oggetto di dominio tenant-aware. Non contiene segreti o path filesystem interni.",
            "additionalProperties": True,
        },
        "ActionLink": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "href": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                "enabled": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
        "PaginationMeta": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "minimum": 1},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                "total": {"type": "integer", "minimum": 0},
                "total_pages": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": True,
        },
        "MutationRequest": {
            "type": "object",
            "description": "Payload JSON di scrittura. Sono vietati tenant_id/studio_id/user_id/token/redirect generici.",
            "additionalProperties": True,
            "not": {
                "anyOf": [
                    {"required": ["tenant_id"]},
                    {"required": ["studio_id"]},
                    {"required": ["user_id"]},
                    {"required": ["token"]},
                    {"required": ["api_key"]},
                    {"required": ["redirect"]},
                    {"required": ["return_url"]},
                ]
            },
        },
        "DocumentUploadRequest": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "format": "binary"},
                "filename": {"type": "string"},
                "metadata": _schema_ref("DomainRecord"),
            },
            "required": ["file"],
            "additionalProperties": True,
        },
        "ErrorResponse": {
            "type": "object",
            "description": "Errore API normalizzato. I campi `errore`/`codice` restano documentati per compatibilita legacy.",
            "properties": {
                "ok": {"type": "boolean", "example": False},
                "error": {"type": "string", "example": "forbidden"},
                "errore": {"type": "string", "example": "Operazione non consentita."},
                "message": {"type": "string", "example": "Operazione non consentita."},
                "code": {"type": "string", "example": "forbidden"},
                "codice": {"oneOf": [{"type": "string"}, {"type": "integer"}], "example": 403},
                "request_id": {"type": "string", "nullable": True},
                "details": {"type": "object", "nullable": True, "additionalProperties": True},
                "errors": {"type": "object", "additionalProperties": True},
                "violations": {"type": "array", "items": _schema_ref("DomainRecord")},
            },
            "additionalProperties": True,
        },
        "ValidationErrorResponse": {
            "allOf": [
                _schema_ref("ErrorResponse"),
                {
                    "type": "object",
                    "properties": {
                        "errors": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        }
                    },
                },
            ]
        },
        "UserSummary": _domain_response_schema("Utente senza password hash o segreti."),
        "CurrentUser": _domain_response_schema("Profilo utente corrente letto da sessione o API autenticata."),
        "Role": _domain_response_schema("Ruolo e permessi senza escalation client-side."),
        "Permission": _domain_response_schema("Permesso applicativo."),
        "StudioSummary": _domain_response_schema("Studio corrente senza identificativi cross-tenant esposti."),
        "CaseFileSummary": _domain_response_schema("Sintesi fascicolo."),
        "CaseFileDetail": _domain_response_schema("Dettaglio fascicolo con sezioni richieste."),
        "DocumentSummary": _domain_response_schema("Sintesi documento senza path filesystem."),
        "DocumentDetail": _domain_response_schema("Dettaglio documento senza path filesystem."),
        "CommunicationSummary": _domain_response_schema("Sintesi comunicazione."),
        "CommunicationDetail": _domain_response_schema("Dettaglio comunicazione."),
        "PecMessageSummary": _domain_response_schema("Sintesi messaggio PEC."),
        "PecMessageDetail": _domain_response_schema("Dettaglio messaggio PEC con allegati redatti."),
        "DepositSummary": _domain_response_schema("Deposito o predeposito."),
        "DeadlineSummary": _domain_response_schema("Sintesi scadenza."),
        "DeadlineDetail": _domain_response_schema("Dettaglio scadenza."),
        "AgendaEventSummary": _domain_response_schema("Evento agenda."),
        "AgendaEventDetail": _domain_response_schema("Dettaglio evento agenda."),
        "TaskSummary": _domain_response_schema("Attivita operativa."),
        "TaskDetail": _domain_response_schema("Dettaglio attivita operativa."),
        "ClientSummary": _domain_response_schema("Cliente senza dati non necessari."),
        "ClientDetail": _domain_response_schema("Dettaglio cliente tenant-aware."),
        "ContactSummary": _domain_response_schema("Soggetto o parte."),
        "ContactDetail": _domain_response_schema("Dettaglio soggetto o parte."),
        "NotificationSummary": _domain_response_schema("Notifica operativa."),
        "NotificationPreference": _domain_response_schema("Preferenza notifiche con segreti redatti."),
        "AuditLogEntry": _domain_response_schema("Evento audit con PII redatta."),
        "BillingInvoiceSummary": _domain_response_schema("Documento economico."),
        "ReportExportResponse": _domain_response_schema("Export o report protetto."),
    }
    for name, title, item in (
        ("UiOperationResponse", "Payload operativo React.", "DomainRecord"),
        ("AdminDatabaseResponse", "Stato database e manutenzione con path redatti.", "DomainRecord"),
        ("AuditLogResponse", "Registro attivita e dettagli audit redatti.", "AuditLogEntry"),
        ("UsersResponse", "Utenti, ruoli e azioni account senza password hash.", "UserSummary"),
        ("RolesResponse", "Profili e matrice permessi.", "Role"),
        ("BackupResponse", "Backup, verifiche e azioni protette.", "DomainRecord"),
        ("SettingsResponse", "Impostazioni studio con segreti mascherati.", "NotificationPreference"),
        ("CalendarSyncResponse", "Account, calendari e conflitti tenant-aware.", "AgendaEventSummary"),
        ("EmailResponse", "Mailbox, messaggi e allegati senza path interni.", "PecMessageSummary"),
        ("CaseFilesResponse", "Fascicoli, documenti, depositi e regia.", "CaseFileSummary"),
        ("TelematicoResponse", "Superfici telematiche e Local Signer.", "DocumentSummary"),
        ("BillingResponse", "Fatturazione e documenti economici.", "BillingInvoiceSummary"),
        ("QuoteResponse", "Preventivi, incarichi e wizard.", "BillingInvoiceSummary"),
        ("PaymentResponse", "Incassi e link pagamento con provider redatti.", "BillingInvoiceSummary"),
        ("FeeResponse", "Tariffario e compensi forensi.", "BillingInvoiceSummary"),
        ("StudioSiteResponse", "Sito studio, contatti e builder.", "DomainRecord"),
        ("LegalNotificationResponse", "Notifiche legali, relate e prove deposito.", "CommunicationDetail"),
        ("DeadlineResponse", "Scadenziario e termini processuali.", "DeadlineSummary"),
        ("AgendaResponse", "Agenda e timesheet.", "AgendaEventSummary"),
        ("MessageResponse", "Messaggi SMS/WhatsApp.", "CommunicationSummary"),
        ("ClientResponse", "Clienti e cartelle.", "ClientSummary"),
        ("ContactResponse", "Soggetti e parti.", "ContactSummary"),
        ("PrivacyRegistryResponse", "Registro GDPR.", "DomainRecord"),
        ("TemplateResponse", "Template atti e compilatore.", "DocumentSummary"),
        ("DocumentDraftingResponse", "Produzione e redazione atti.", "DocumentDetail"),
        ("LegalResearchResponse", "Ricerca legale e news disponibili.", "DomainRecord"),
        ("CaseLawResponse", "Archivio giurisprudenza.", "DomainRecord"),
        ("DashboardResponse", "Panoramica, regia e metriche studio.", "DomainRecord"),
        ("SearchResponse", "Ricerca globale tenant-aware.", "DomainRecord"),
        ("BootstrapResponse", "Bootstrap shell React, profilo e navigazione.", "CurrentUser"),
        ("FeatureFlagsResponse", "Feature flag risolti per lo studio corrente.", "DomainRecord"),
    ):
        schemas[name] = _domain_response_schema(title, item)

    return {
        "securitySchemes": {
            "cookieSession": {
                "type": "apiKey",
                "in": "cookie",
                "name": "session",
                "description": "Sessione Flask autenticata.",
            },
            "apiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key tenant-aware. Non accetta chiavi globali in multi-studio.",
            },
            "csrfToken": {
                "type": "apiKey",
                "in": "header",
                "name": "X-CSRFToken",
                "description": "Token CSRF richiesto per scritture da sessione browser.",
            },
        },
        "parameters": {
            "PageParam": {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1}},
            "PageSizeParam": {
                "name": "page_size",
                "in": "query",
                "schema": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "SearchParam": {"name": "q", "in": "query", "schema": {"type": "string", "maxLength": 120}},
            "StatusParam": {"name": "status", "in": "query", "schema": {"type": "string", "maxLength": 40}},
        },
        "responses": {
            "BadRequest": {
                "description": "Richiesta non valida o parametro di controllo server bloccato.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "Unauthorized": {
                "description": "Autenticazione richiesta.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "Forbidden": {
                "description": "Permesso insufficiente senza rivelare dati della risorsa.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "NotFound": {
                "description": "Risorsa non trovata o non visibile nel tenant corrente.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "Conflict": {
                "description": "Conflitto di stato o contesto tenant mancante.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "ValidationError": {
                "description": "Validazione dominio non superata.",
                "content": {"application/json": {"schema": _schema_ref("ValidationErrorResponse")}},
            },
            "RateLimited": {
                "description": "Limite richieste applicato.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "PayloadTooLarge": {
                "description": "File oltre limite accettato.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "UnsupportedMediaType": {
                "description": "Formato file o content-type non supportato.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
            "ServerError": {
                "description": "Errore interno senza dettagli sensibili.",
                "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
            },
        },
        "schemas": schemas,
    }


def build_openapi(report_date: str) -> dict[str, Any]:
    frontend_links = _read_frontend_api_links()
    paths: dict[str, Any] = {}
    tags: dict[str, dict[str, str]] = {}
    for endpoint in endpoints():
        info = classify(endpoint.path)
        tags.setdefault(info.tag, {"name": info.tag, "description": f"Contratti API {info.tag}."})
        path_item = paths.setdefault(endpoint.openapi_path, {})
        path_item[endpoint.method.lower()] = _operation(endpoint, frontend_links)
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "IUSENTRA API Contracts",
            "version": _project_version(),
            "description": f"Contratti API fase 6 generati da endpoint Flask reali. Aggiornato: {report_date}.",
        },
        "servers": [
            {"url": "https://app.iusentra.it", "description": "Produzione Hetzner"},
            {"url": "http://127.0.0.1:8080", "description": "Docker locale"},
        ],
        "tags": list(tags.values()),
        "security": [{"cookieSession": []}, {"apiKeyAuth": []}],
        "paths": paths,
        "components": _components(),
    }


def _status_for(endpoint: Endpoint) -> tuple[str, str, str]:
    provider = "success+auth-error" if endpoint.full_path in SUCCESS_PROVIDER_SAMPLES else "auth-error"
    openapi_status = "verified" if provider == "success+auth-error" else "complete"
    test = "tests/test_openapi_contracts_phase6.py + scripts/verify_openapi_provider.py"
    return openapi_status, provider, test


def render_contract_map(report_date: str) -> str:
    frontend_links = _read_frontend_api_links()
    rows = endpoints()
    p0_p1 = sum(1 for endpoint in rows if classify(endpoint.path).priority in {"P0", "P1"})
    verified = sum(1 for endpoint in rows if endpoint.full_path in SUCCESS_PROVIDER_SAMPLES)
    lines = [
        "# API Endpoint Contract Map",
        "",
        f"Aggiornato: {report_date}.",
        "",
        "## Fase 6 API Contract Review",
        "",
        "La mappa collega endpoint Flask reali, pagine App V2 e contratti OpenAPI. Gli endpoint P0/P1 sono documentati in `docs/openapi.yaml`; la provider verification copre tutti con errore 401 reale e un campione 200 per le aree operative principali.",
        "",
        "## Sommario",
        "",
        f"- Endpoint React API contrattualizzati: {len(rows)}.",
        f"- Endpoint P0/P1 contrattualizzati: {p0_p1}.",
        f"- Endpoint con provider verification 200 rappresentativa: {verified}.",
        f"- Endpoint con provider verification auth-error: {len(rows)}.",
        "- Endpoint P2/P3: mappati e completi per autenticazione/errori; success-body da raffinare quando la pagina passa a priorita superiore.",
        "",
        "| Area | Endpoint | Metodo | Pagina | Priorita | OpenAPI | Provider Test | RBAC | Flag | Tenant | Stato |",
        "|------|----------|--------|--------|----------|---------|---------------|------|------|--------|-------|",
    ]
    for endpoint in rows:
        info = classify(endpoint.path)
        frontend = frontend_links.get(endpoint.openapi_path) or frontend_links.get(endpoint.full_path)
        page = frontend[0] if frontend else info.area
        flag = frontend[1] if frontend else "n/a"
        openapi_status, provider, _test = _status_for(endpoint)
        state = "verified" if provider == "success+auth-error" else "complete-auth-error"
        lines.append(
            f"| {info.area} | `{endpoint.openapi_path}` | `{endpoint.method}` | {page} | {info.priority} | {openapi_status} | {provider} | `{info.permission}` | `{flag}` | current_tenant | {state} |"
        )
    lines.extend(
        [
            "",
            "## Note provider verification",
            "",
            "- `auth-error` significa che l'endpoint e' invocato dal Flask test client senza credenziali e deve rispondere con errore controllato conforme allo schema errori.",
            "- `success+auth-error` aggiunge una chiamata autenticata 200 su endpoint statici rappresentativi di P0/P1 e delle aree principali.",
            "- Gli endpoint con path parametrici o mutazioni distruttive restano verificati sul contratto di autenticazione/errori e richiedono fixture dominio dedicate prima della promozione a provider success full.",
            "",
        ]
    )
    return "\n".join(lines)


def _phase6_section(report_date: str, rows: list[Endpoint]) -> str:
    p0_p1 = sum(1 for endpoint in rows if classify(endpoint.path).priority in {"P0", "P1"})
    verified = sum(1 for endpoint in rows if endpoint.full_path in SUCCESS_PROVIDER_SAMPLES)
    return f"""## Fase 6 API Contract Review

Aggiornato: {report_date}.

OpenAPI di riferimento: `docs/openapi.yaml`.

Comandi gate:

```powershell
python scripts\\react-migration\\generate_api_contracts.py --check
python scripts\\validate_openapi.py docs\\openapi.yaml
python scripts\\verify_openapi_provider.py
python -m pytest -q tests\\test_openapi_contracts_phase6.py --tb=short
```

Risultato di mappatura:

- Endpoint React API contrattualizzati: {len(rows)}.
- Endpoint P0/P1 con contratto OpenAPI: {p0_p1}.
- Endpoint con provider verification rappresentativa non-auth-error: {verified} totali, includendo success-body autenticati e il controllo backend-security.
- Endpoint con provider verification 401 reale: {len(rows)}.

Standard error schema:

- `ErrorResponse` documenta il formato normalizzato (`ok`, `error`, `message`, `code`, `request_id`, `details`) e i campi legacy reali (`errore`, `codice`) per compatibilita.
- 400, 401, 403, 404, 409, 422, 429 e 500 sono referenziati su ogni operazione; upload aggiunge 413 e 415.
- Il codice `backend_security_control_param` resta lo standard per parametri client riservati al controllo server.

Standard pagination/filtering:

- Liste GET documentano `page`, `page_size`, `q` e `status` come parametri tenant-safe.
- Il client non puo' inviare `tenant_id`, `studio_id`, `user_id`, token o redirect liberi.

Regole operative per nuovi endpoint:

1. Aggiungere l'endpoint Flask con autenticazione e permessi dominio.
2. Eseguire `generate_api_contracts.py` per aggiornare OpenAPI e mappa.
3. Aggiungere fixture provider verification se l'endpoint e' P0/P1 o gestisce file/segreti.
4. Eseguire `validate_openapi.py` e `verify_openapi_provider.py`.
5. Aggiornare documentazione e test collegati prima di promuovere la pagina.

Protezioni sicurezza contrattualizzate:

- RBAC: ogni operazione ha `x-rbac-permission`.
- Tenant: ogni operazione ha `x-tenant-scope: current_tenant`.
- Feature flag: le pagine App V2 riportano `x-feature-flag`; gli altri endpoint indicano `n/a` o route collegata.
- PII/segreti: schemi e descrizioni vietano password hash, token, segreti provider e path filesystem in chiaro.

## Checklist nuovo endpoint

- [ ] Auth sessione/API key tenant-aware.
- [ ] Permesso RBAC dominio.
- [ ] Tenant context server-side, fail-closed in multi-studio.
- [ ] Input validation e blocco parametri server-controlled.
- [ ] Response schema e `ErrorResponse`.
- [ ] OpenAPI e mappa endpoint aggiornate.
- [ ] Provider verification o limite documentato per endpoint parametrico/upload.
- [ ] Test 401/403/400/422/success path.
- [ ] PII review e audit se legge/scrive dati sensibili.
"""


def update_api_contracts_doc(report_date: str, rows: list[Endpoint]) -> str:
    current = API_CONTRACTS_OUTPUT.read_text(encoding="utf-8") if API_CONTRACTS_OUTPUT.exists() else "# Contratti API App V2\n"
    marker = "## Fase 6 API Contract Review"
    section = _phase6_section(report_date, rows)
    if marker in current:
        current = current[: current.index(marker)].rstrip() + "\n\n" + section
    else:
        current = current.rstrip() + "\n\n" + section
    return current.rstrip() + "\n"


def _report_date(*outputs: Path) -> str:
    configured = os.getenv("IUSENTRA_REPORT_DATE", "").strip()
    if configured:
        return configured
    for output in outputs:
        if output.exists():
            match = DATE_LINE.search(output.read_text(encoding="utf-8"))
            if match:
                return match.group(1)
    return date.today().isoformat()


def render_all(report_date: str) -> dict[Path, str]:
    rows = endpoints()
    openapi = yaml.safe_dump(build_openapi(report_date), sort_keys=False, allow_unicode=False, width=120)
    return {
        OPENAPI_OUTPUT: openapi,
        CONTRACT_MAP_OUTPUT: render_contract_map(report_date),
        API_CONTRACTS_OUTPUT: update_api_contracts_doc(report_date, rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera OpenAPI e mappa contratti API fase 6.")
    parser.add_argument("--check", action="store_true", help="Verifica che gli artefatti siano gia' allineati.")
    args = parser.parse_args()

    outputs = render_all(_report_date(CONTRACT_MAP_OUTPUT, API_CONTRACTS_OUTPUT))
    if args.check:
        mismatches = [path for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if mismatches:
            for path in mismatches:
                print(f"{path.relative_to(REPO_ROOT)} non allineato. Esegui senza --check.", file=sys.stderr)
            return 1
        print("Contratti API fase 6 allineati.")
        return 0

    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        print(f"Generato {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

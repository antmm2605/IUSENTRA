"""Feature flag governati per la migrazione React/App V2.

Le superfici App V2 gia' promosse come operative sono attive di default e
restano spegnibili via config/env per rollback controllato. Le capability non
parificate, come i workflow telematici ancora protetti e Web Push, restano
default-off e fail-closed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Mapping

from flask import current_app, g, jsonify, request


@dataclass(frozen=True, slots=True)
class FeatureFlagDefinition:
    key: str
    env_var: str
    description: str
    public: bool = True
    default: bool = False


APP_V2_DEFAULT_OFF_FLAGS = frozenset(
    {
        "routes.appV2.telematico.center",
        "routes.appV2.telematico.surface",
        "routes.appV2.notifications.mobilePush",
        "lex.legalSkills.trustLayer",
        "lex.legalSkills.customSkills",
        "lex.legalSkills.scheduledAgents",
    }
)

APP_V2_DEFAULT_ON_FLAGS = frozenset(
    {
        "lex.legalSkills.enabled",
        "routes.appV2.dashboard.home",
        "routes.appV2.dashboard.regia",
        "routes.appV2.search.global",
        "routes.appV2.cases.list",
        "routes.appV2.cases.detail",
        "routes.appV2.cases.create",
        "routes.appV2.clients.list",
        "routes.appV2.clients.create",
        "routes.appV2.clients.detail",
        "routes.appV2.contacts.list",
        "routes.appV2.contacts.create",
        "routes.appV2.comms.deposits",
        "routes.appV2.comms.pec",
        "routes.appV2.comms.ordinaryMail",
        "routes.appV2.comms.messages",
        "routes.appV2.comms.newMessage",
        "routes.appV2.agenda.calendar",
        "routes.appV2.agenda.create",
        "routes.appV2.agenda.timesheet",
        "routes.appV2.deadlines.list",
        "routes.appV2.deadlines.create",
        "routes.appV2.deadlines.detail",
        "routes.appV2.deadlines.hearingWizard",
        "routes.appV2.documents.list",
        "routes.appV2.documents.templates",
        "routes.appV2.documents.templateEditor",
        "routes.appV2.documents.drafting",
        "routes.appV2.documents.editor",
        "routes.appV2.documents.uploadClassification",
        "routes.appV2.documents.checklist",
        "routes.appV2.legalResearch.home",
        "routes.appV2.legalResearch.giurisprudenza",
        "routes.appV2.studio.home",
        "routes.appV2.studio.statistics",
        "routes.appV2.studio.modules",
        "routes.appV2.studio.site",
        "routes.appV2.studio.siteBuilder",
        "routes.appV2.studio.siteDrafting",
        "routes.appV2.admin.home",
        "routes.appV2.admin.users",
        "routes.appV2.admin.roles",
        "routes.appV2.admin.auditLogs",
        "routes.appV2.admin.database",
        "routes.appV2.admin.privacyRegistry",
        "routes.appV2.settings.studio",
        "routes.appV2.settings.payments",
        "routes.appV2.settings.notifications",
        "routes.appV2.settings.backup",
        "routes.appV2.settings.calendarSync",
        "routes.appV2.billing.invoices",
        "routes.appV2.billing.payments",
        "routes.appV2.billing.quotes",
        "routes.appV2.billing.compensi",
        "routes.appV2.billing.tariffario",
        "routes.appV2.legalSkills.catalog",
        "routes.appV2.legalSkills.profile",
        "routes.appV2.legalSkills.run",
        "routes.appV2.legalSkills.reviewQueue",
    }
)


def _env_var(flag_key: str) -> str:
    return "IUSENTRA_FF_" + re.sub(r"[^A-Z0-9]+", "_", flag_key.upper()).strip("_")


def _flag(key: str, description: str) -> FeatureFlagDefinition:
    return FeatureFlagDefinition(key, _env_var(key), description, default=key in APP_V2_DEFAULT_ON_FLAGS)


FEATURE_FLAG_DEFINITIONS: tuple[FeatureFlagDefinition, ...] = (
    _flag("routes.appV2.dashboard.home", "Panoramica nella shell App V2 sperimentale."),
    _flag("routes.appV2.dashboard.regia", "Regia operativa nella shell App V2 sperimentale."),
    _flag("routes.appV2.search.global", "Ricerca globale nella shell App V2 sperimentale."),
    _flag("routes.appV2.cases.list", "Fascicoli nella shell App V2 sperimentale."),
    _flag("routes.appV2.cases.detail", "Dettaglio fascicolo nella shell App V2 sperimentale."),
    _flag("routes.appV2.cases.create", "Creazione fascicolo nella shell App V2 sperimentale."),
    _flag("routes.appV2.clients.list", "Clienti nella shell App V2 sperimentale."),
    _flag("routes.appV2.clients.create", "Nuovo cliente nella shell App V2 sperimentale."),
    _flag("routes.appV2.clients.detail", "Cartella cliente nella shell App V2 sperimentale."),
    _flag("routes.appV2.contacts.list", "Soggetti e parti nella shell App V2 sperimentale."),
    _flag("routes.appV2.contacts.create", "Nuovo soggetto nella shell App V2 sperimentale."),
    _flag("routes.appV2.comms.deposits", "Workspace comunicazioni e depositi nella shell App V2 sperimentale."),
    _flag("routes.appV2.comms.pec", "Email PEC nella shell App V2 sperimentale."),
    _flag("routes.appV2.comms.ordinaryMail", "Email ordinaria nella shell App V2 sperimentale."),
    _flag("routes.appV2.comms.messages", "Messaggi nella shell App V2 sperimentale."),
    _flag("routes.appV2.comms.newMessage", "Nuovo messaggio nella shell App V2 sperimentale."),
    _flag("routes.appV2.agenda.calendar", "Agenda nella shell App V2 sperimentale."),
    _flag("routes.appV2.agenda.create", "Nuovo appuntamento nella shell App V2 sperimentale."),
    _flag("routes.appV2.agenda.timesheet", "Timesheet nella shell App V2 sperimentale."),
    _flag("routes.appV2.deadlines.list", "Scadenziario nella shell App V2 sperimentale."),
    _flag("routes.appV2.deadlines.create", "Nuova scadenza nella shell App V2 sperimentale."),
    _flag("routes.appV2.deadlines.detail", "Dettaglio scadenza nella shell App V2 sperimentale."),
    _flag("routes.appV2.deadlines.hearingWizard", "Preparazione udienza guidata nella shell App V2 sperimentale."),
    _flag("routes.appV2.documents.list", "Documenti nella shell App V2 sperimentale."),
    _flag("routes.appV2.documents.templates", "Template atti nella shell App V2 sperimentale."),
    _flag("routes.appV2.documents.templateEditor", "Editor template atti nella shell App V2 sperimentale."),
    _flag("routes.appV2.documents.drafting", "Redazione atti nella shell App V2 sperimentale."),
    _flag("routes.appV2.documents.editor", "Editor documento fascicolo nella shell App V2 sperimentale."),
    _flag("routes.appV2.documents.uploadClassification", "Upload multiplo e classificazione documenti nella shell App V2."),
    _flag("routes.appV2.documents.checklist", "Controlli atti nella shell App V2 sperimentale."),
    _flag("routes.appV2.legalResearch.home", "Ricerca legale nella shell App V2 sperimentale."),
    _flag("routes.appV2.legalResearch.giurisprudenza", "Archivio giurisprudenza nella shell App V2 sperimentale."),
    _flag("routes.appV2.telematico.center", "Centro telematico nella shell App V2 sperimentale."),
    _flag("routes.appV2.telematico.surface", "Superfici telematiche assistite nella shell App V2 sperimentale."),
    _flag("routes.appV2.studio.home", "Studio nella shell App V2 sperimentale."),
    _flag("routes.appV2.studio.statistics", "Statistiche nella shell App V2 sperimentale."),
    _flag("routes.appV2.studio.modules", "Moduli studio nella shell App V2 sperimentale."),
    _flag("routes.appV2.studio.site", "Sito Studio nella shell App V2 sperimentale."),
    _flag("routes.appV2.studio.siteBuilder", "Builder Sito Studio nella shell App V2 sperimentale."),
    _flag("routes.appV2.studio.siteDrafting", "Redazione Sito Studio nella shell App V2 sperimentale."),
    _flag("routes.appV2.admin.home", "Amministrazione nella shell App V2 sperimentale."),
    _flag("routes.appV2.admin.users", "Utenti nella shell App V2 sperimentale."),
    _flag("routes.appV2.admin.roles", "Profili e permessi nella shell App V2 sperimentale."),
    _flag("routes.appV2.admin.auditLogs", "Registro attivita nella shell App V2 sperimentale."),
    _flag("routes.appV2.admin.database", "Database nella shell App V2 sperimentale."),
    _flag("routes.appV2.admin.privacyRegistry", "Registro GDPR nella shell App V2 sperimentale."),
    _flag("routes.appV2.settings.studio", "Impostazioni studio nella shell App V2 sperimentale."),
    _flag("routes.appV2.settings.payments", "Pagamenti nelle impostazioni App V2 sperimentale."),
    _flag("routes.appV2.settings.notifications", "Notifiche nelle impostazioni App V2 sperimentale."),
    _flag("routes.appV2.settings.backup", "Backup nelle impostazioni App V2 sperimentale."),
    _flag("routes.appV2.settings.calendarSync", "Sincronizzazione calendari nella shell App V2 sperimentale."),
    _flag("routes.appV2.billing.invoices", "Parcelle e fatture nella shell App V2 sperimentale."),
    _flag("routes.appV2.billing.payments", "Incassi e pagamenti nella shell App V2 sperimentale."),
    _flag("routes.appV2.billing.quotes", "Preventivi e incarichi nella shell App V2 sperimentale."),
    _flag("routes.appV2.billing.compensi", "Compensi forensi nella shell App V2 sperimentale."),
    _flag("routes.appV2.billing.tariffario", "Tariffario nella shell App V2 sperimentale."),
    _flag("routes.appV2.notifications.mobilePush", "Notifiche Web Push su dispositivo mobile/tablet."),
    _flag("lex.legalSkills.enabled", "Legal Skills Engine governato per Lex."),
    _flag("lex.legalSkills.trustLayer", "Controllo di fiducia per skill legali custom."),
    _flag("lex.legalSkills.customSkills", "Installazione skill Legal Skills custom."),
    _flag("lex.legalSkills.scheduledAgents", "Agenti Legal Skills schedulati read-only."),
    _flag("routes.appV2.legalSkills.catalog", "Catalogo Legal Skills nella shell App V2."),
    _flag("routes.appV2.legalSkills.profile", "Profilo Legal Skills nella shell App V2."),
    _flag("routes.appV2.legalSkills.run", "Esecuzione Legal Skills nella shell App V2."),
    _flag("routes.appV2.legalSkills.reviewQueue", "Revisione risultati Legal Skills nella shell App V2."),
    FeatureFlagDefinition(
        "routes.appV2.docsPanel",
        "IUSENTRA_FF_ROUTES_APPV2_DOCS_PANEL",
        "Alias compatibilita fase 1 per routes.appV2.documents.list.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.commsDeposits",
        "IUSENTRA_FF_ROUTES_APPV2_COMMS_DEPOSITS",
        "Alias compatibilita fase 1 per routes.appV2.comms.deposits.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.uploadClassification",
        "IUSENTRA_FF_ROUTES_APPV2_UPLOAD_CLASSIFICATION",
        "Alias compatibilita fase 1 per routes.appV2.documents.uploadClassification.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.deadlines",
        "IUSENTRA_FF_ROUTES_APPV2_DEADLINES",
        "Alias compatibilita fase 1 per routes.appV2.deadlines.list.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.agenda",
        "IUSENTRA_FF_ROUTES_APPV2_AGENDA",
        "Alias compatibilita fase 1 per routes.appV2.agenda.calendar.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.caseFiles",
        "IUSENTRA_FF_ROUTES_APPV2_CASE_FILES",
        "Alias compatibilita fase 1 per routes.appV2.cases.list.",
    ),
    FeatureFlagDefinition(
        "notifications.mobilePush",
        "IUSENTRA_FF_NOTIFICATIONS_MOBILE_PUSH",
        "Alias compatibilita fase 1 per routes.appV2.notifications.mobilePush.",
    ),
)

FEATURE_FLAG_KEYS = frozenset(definition.key for definition in FEATURE_FLAG_DEFINITIONS)
FEATURE_FLAGS_BY_KEY = {definition.key: definition for definition in FEATURE_FLAG_DEFINITIONS}
FEATURE_FLAGS_BY_ENV = {definition.env_var: definition for definition in FEATURE_FLAG_DEFINITIONS}

FEATURE_FLAG_ALIASES: dict[str, tuple[str, ...]] = {
    "routes.appV2.documents.list": ("routes.appV2.docsPanel",),
    "routes.appV2.comms.deposits": ("routes.appV2.commsDeposits",),
    "routes.appV2.documents.uploadClassification": ("routes.appV2.uploadClassification",),
    "routes.appV2.deadlines.list": ("routes.appV2.deadlines",),
    "routes.appV2.agenda.calendar": ("routes.appV2.agenda",),
    "routes.appV2.cases.list": ("routes.appV2.caseFiles",),
    "routes.appV2.notifications.mobilePush": ("notifications.mobilePush",),
}

FEATURE_FLAG_CANONICAL_BY_ALIAS = {
    alias: canonical
    for canonical, aliases in FEATURE_FLAG_ALIASES.items()
    for alias in aliases
}

APP_V2_ROUTE_FLAGS: tuple[tuple[str, str], ...] = (
    ("/fascicoli/{id}/documenti/{id_doc}/editor", "routes.appV2.documents.editor"),
    ("/fascicoli/*/documenti/*/editor", "routes.appV2.documents.editor"),
    ("/fascicoli/nuovo", "routes.appV2.cases.create"),
    ("/fascicoli/archivio", "routes.appV2.cases.list"),
    ("/fascicoli/", "routes.appV2.cases.detail"),
    ("/fascicoli", "routes.appV2.cases.list"),
    ("/clienti/nuovo", "routes.appV2.clients.create"),
    ("/clienti/*/modifica", "routes.appV2.clients.create"),
    ("/clienti/", "routes.appV2.clients.detail"),
    ("/clienti", "routes.appV2.clients.list"),
    ("/soggetti/nuovo", "routes.appV2.contacts.create"),
    ("/soggetti/*/modifica", "routes.appV2.contacts.create"),
    ("/soggetti", "routes.appV2.contacts.list"),
    ("/cartelle-condivise", "routes.appV2.clients.detail"),
    ("/email-ordinaria/scrivi", "routes.appV2.comms.ordinaryMail"),
    ("/email-ordinaria", "routes.appV2.comms.ordinaryMail"),
    ("/email/scrivi", "routes.appV2.comms.pec"),
    ("/email", "routes.appV2.comms.pec"),
    ("/notifiche-legali", "routes.appV2.comms.pec"),
    ("/messaggi/nuovo", "routes.appV2.comms.newMessage"),
    ("/messaggi", "routes.appV2.comms.messages"),
    ("/comunicazioni", "routes.appV2.comms.deposits"),
    ("/agenda/nuovo", "routes.appV2.agenda.create"),
    ("/agenda/", "routes.appV2.agenda.calendar"),
    ("/agenda", "routes.appV2.agenda.calendar"),
    ("/timesheet", "routes.appV2.agenda.timesheet"),
    ("/scadenziario/nuova", "routes.appV2.deadlines.create"),
    ("/scadenziario/*/modifica", "routes.appV2.deadlines.detail"),
    ("/scadenziario/", "routes.appV2.deadlines.detail"),
    ("/scadenziario", "routes.appV2.deadlines.list"),
    ("/wizard-pro", "routes.appV2.deadlines.hearingWizard"),
    ("/documenti", "routes.appV2.documents.list"),
    ("/template-atti/nuovo", "routes.appV2.documents.templateEditor"),
    ("/template-atti/", "routes.appV2.documents.templates"),
    ("/template-atti", "routes.appV2.documents.templates"),
    ("/redazione-atti", "routes.appV2.documents.drafting"),
    ("/checklist", "routes.appV2.documents.checklist"),
    ("/deposito/checklist", "routes.appV2.documents.checklist"),
    ("/giurisprudenza", "routes.appV2.legalResearch.giurisprudenza"),
    ("/legal-intelligence", "routes.appV2.legalResearch.home"),
    ("/ricerca-legale", "routes.appV2.legalResearch.home"),
    ("/global-search", "routes.appV2.search.global"),
    ("/ricerca-studio", "routes.appV2.search.global"),
    ("/cerca", "routes.appV2.search.global"),
    ("/telematico", "routes.appV2.telematico.center"),
    ("/servizi-telematici", "routes.appV2.telematico.center"),
    ("/polisweb", "routes.appV2.telematico.surface"),
    ("/pst", "routes.appV2.telematico.surface"),
    ("/pdp", "routes.appV2.telematico.surface"),
    ("/pat", "routes.appV2.telematico.surface"),
    ("/ptt", "routes.appV2.telematico.surface"),
    ("/sigit", "routes.appV2.telematico.surface"),
    ("/tribunali", "routes.appV2.telematico.surface"),
    ("/guida/firma-digitale", "routes.appV2.telematico.surface"),
    ("/portali", "routes.appV2.telematico.surface"),
    ("/studio", "routes.appV2.studio.home"),
    ("/statistiche", "routes.appV2.studio.statistics"),
    ("/strumenti-legali", "routes.appV2.studio.modules"),
    ("/strumenti-operativi", "routes.appV2.studio.modules"),
    ("/applicazioni", "routes.appV2.studio.modules"),
    ("/sito-studio/builder", "routes.appV2.studio.siteBuilder"),
    ("/sito-studio/redazione-ai", "routes.appV2.studio.siteDrafting"),
    ("/sito-studio", "routes.appV2.studio.site"),
    ("/amministrazione", "routes.appV2.admin.home"),
    ("/utenti", "routes.appV2.admin.users"),
    ("/profili", "routes.appV2.admin.roles"),
    ("/audit", "routes.appV2.admin.auditLogs"),
    ("/registro-attivita", "routes.appV2.admin.auditLogs"),
    ("/admin/database", "routes.appV2.admin.database"),
    ("/database", "routes.appV2.admin.database"),
    ("/privacy/registro", "routes.appV2.admin.privacyRegistry"),
    ("/registro-gdpr", "routes.appV2.admin.privacyRegistry"),
    ("/impostazioni/pagamenti", "routes.appV2.settings.payments"),
    ("/notifiche-whatsapp", "routes.appV2.settings.notifications"),
    ("/notifiche", "routes.appV2.settings.notifications"),
    ("/backup", "routes.appV2.settings.backup"),
    ("/impostazioni/calendario", "routes.appV2.settings.calendarSync"),
    ("/sincronizzazione-calendari", "routes.appV2.settings.calendarSync"),
    ("/impostazioni", "routes.appV2.settings.studio"),
    ("/impostazioni-studio", "routes.appV2.settings.studio"),
    ("/fatturazione", "routes.appV2.billing.invoices"),
    ("/incassi-pagamenti", "routes.appV2.billing.payments"),
    ("/preventivi/wizard", "routes.appV2.billing.quotes"),
    ("/preventivi", "routes.appV2.billing.quotes"),
    ("/compensi-forensi", "routes.appV2.billing.compensi"),
    ("/tariffario", "routes.appV2.billing.tariffario"),
    ("/legal-skills/packs/", "routes.appV2.legalSkills.run"),
    ("/legal-skills/profile", "routes.appV2.legalSkills.profile"),
    ("/legal-skills/run", "routes.appV2.legalSkills.run"),
    ("/legal-skills/runs/", "routes.appV2.legalSkills.reviewQueue"),
    ("/legal-skills/review", "routes.appV2.legalSkills.reviewQueue"),
    ("/legal-skills", "routes.appV2.legalSkills.catalog"),
    ("/app/legal-skills", "routes.appV2.legalSkills.catalog"),
    ("/workspace-intelligente", "routes.appV2.dashboard.regia"),
    ("/regia-operativa", "routes.appV2.dashboard.regia"),
    ("/app", "routes.appV2.dashboard.home"),
    ("/", "routes.appV2.dashboard.home"),
)

TRUE_VALUES = {"1", "true", "yes", "y", "on", "si", "s"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "none", "null", ""}


def _config_key(flag_key: str) -> str:
    return "FEATURE_FLAG_" + re.sub(r"[^A-Z0-9]+", "_", flag_key.upper()).strip("_")


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def _mapping_from_raw(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): raw for key, raw in value.items()}
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, Mapping):
            return {str(key): raw for key, raw in parsed.items()}
    return {}


def _propagate_feature_flag_aliases(
    resolved: dict[str, bool],
    explicit: Mapping[str, bool] | None = None,
) -> dict[str, bool]:
    """Mantiene equivalenti i flag fase 1 e i nuovi flag canonici."""

    explicit = explicit or {}
    for canonical, aliases in FEATURE_FLAG_ALIASES.items():
        explicit_values = [
            bool(explicit[key])
            for key in (canonical, *aliases)
            if key in explicit
        ]
        if explicit_values:
            active = any(explicit_values)
        else:
            active = bool(resolved.get(canonical, False) or any(resolved.get(alias, False) for alias in aliases))
        resolved[canonical] = active
        for alias in aliases:
            resolved[alias] = active
    return resolved


def resolve_feature_flags(config: Mapping[str, Any] | None = None) -> dict[str, bool]:
    """Risolve tutti i flag noti, applicando rollout operativo e rollback."""

    source = config if config is not None else getattr(current_app, "config", {})
    resolved = {definition.key: bool(definition.default) for definition in FEATURE_FLAG_DEFINITIONS}
    explicit: dict[str, bool] = {}
    bulk_sources = (
        _mapping_from_raw(source.get("FEATURE_FLAGS") if source else None),
        _mapping_from_raw(os.getenv("IUSENTRA_FEATURE_FLAGS", "")),
    )
    for raw_flags in bulk_sources:
        for raw_key, raw_value in raw_flags.items():
            definition = FEATURE_FLAGS_BY_KEY.get(raw_key) or FEATURE_FLAGS_BY_ENV.get(raw_key)
            if definition:
                value = _coerce_bool(raw_value, default=definition.default)
                resolved[definition.key] = value
                explicit[definition.key] = value

    for definition in FEATURE_FLAG_DEFINITIONS:
        config_key = _config_key(definition.key)
        for raw_value in (
            source.get(definition.env_var) if source else None,
            source.get(config_key) if source else None,
            os.getenv(definition.env_var),
        ):
            if raw_value is not None:
                value = _coerce_bool(raw_value, default=definition.default)
                resolved[definition.key] = value
                explicit[definition.key] = value
    return _propagate_feature_flag_aliases(resolved, explicit)


def feature_flags_payload(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    flags = resolve_feature_flags(config)
    return {
        "ok": True,
        "flags": flags,
        "defaults": {definition.key: bool(definition.default) for definition in FEATURE_FLAG_DEFINITIONS},
    }


def is_feature_enabled(flag_key: str, config: Mapping[str, Any] | None = None) -> bool:
    canonical = FEATURE_FLAG_CANONICAL_BY_ALIAS.get(flag_key, flag_key)
    if canonical not in FEATURE_FLAG_KEYS:
        return False
    return bool(resolve_feature_flags(config).get(canonical, False))


def _normalise_app_v2_path(path: str) -> str:
    clean = str(path or "").split("?", 1)[0].split("#", 1)[0].strip()
    if not clean:
        return "/"
    clean = "/" + clean.strip("/")
    lower = clean.lower()
    if lower == "/app-v2":
        return "/"
    if lower.startswith("/app-v2/"):
        return lower.removeprefix("/app-v2").rstrip("/") or "/"
    return lower.rstrip("/") or "/"


def _app_v2_route_rule_matches(rule: str, path: str) -> bool:
    raw_rule = str(rule or "/").strip().lower()
    prefix_only = raw_rule.endswith("/") and raw_rule.strip("/") != ""
    normalised_rule = "/" + raw_rule.strip("/")
    if normalised_rule == "//":
        normalised_rule = "/"
    if prefix_only:
        prefix = normalised_rule.rstrip("/")
        return path.startswith(prefix + "/")
    if "*" in normalised_rule or "{" in normalised_rule or ":" in normalised_rule:
        rule_parts = [part for part in normalised_rule.strip("/").split("/") if part]
        path_parts = [part for part in path.strip("/").split("/") if part]
        if len(rule_parts) != len(path_parts):
            return False
        for rule_part, path_part in zip(rule_parts, path_parts):
            if rule_part == "*" or rule_part.startswith("{") or rule_part.startswith(":"):
                continue
            if rule_part != path_part:
                return False
        return True
    if normalised_rule == "/":
        return path == "/"
    return path == normalised_rule or path.startswith(normalised_rule + "/")


def app_v2_route_flag_for_path(path: str) -> str:
    clean = _normalise_app_v2_path(path)
    for rule, flag_key in APP_V2_ROUTE_FLAGS:
        if _app_v2_route_rule_matches(rule, clean):
            return flag_key
    return ""


def set_feature_flag(
    config: dict[str, Any],
    flag_key: str,
    enabled: bool,
    *,
    actor: str = "",
    audit: Callable[[str, str, str, str], Any] | None = None,
) -> dict[str, bool]:
    """Aggiorna un flag in memoria e registra l'evento se il chiamante fornisce audit."""

    if flag_key not in FEATURE_FLAG_KEYS:
        raise ValueError(f"Feature flag non riconosciuto: {flag_key}")
    current = dict(resolve_feature_flags(config))
    canonical = FEATURE_FLAG_CANONICAL_BY_ALIAS.get(flag_key, flag_key)
    current[canonical] = bool(enabled)
    for alias in FEATURE_FLAG_ALIASES.get(canonical, ()):
        current[alias] = bool(enabled)
    config["FEATURE_FLAGS"] = current
    if callable(audit):
        details = f"{actor or 'sistema'} ha impostato il flag a {'attivo' if enabled else 'spento'}."
        audit("feature_flag_toggled", "feature_flag", flag_key, details)
    return current


def _audit_denial(flag_key: str) -> None:
    details = f"Accesso bloccato per flag spento: {flag_key}"
    try:
        current_app.logger.warning(
            "policy_denied feature_flag=%s path=%s user=%s",
            flag_key,
            request.path,
            getattr(g.get("utente_corrente"), "username", ""),
        )
        audit = (current_app.extensions.get("core_runtime", {}) or {}).get("audit")
        if callable(audit):
            audit("policy_denied", "feature_flag", flag_key, details)
    except Exception:
        current_app.logger.debug("Audit denial feature flag non registrato.", exc_info=True)


def feature_disabled_response(flag_key: str, *, status: int = 403):
    _audit_denial(flag_key)
    return jsonify(
        {
            "ok": False,
            "code": "feature_disabled",
            "message": "Funzione non attiva per questo studio.",
        }
    ), status


def require_feature_flag(flag_key: str):
    """Decoratore Flask JSON per bloccare funzioni sperimentali flag-off."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if is_feature_enabled(flag_key):
                return func(*args, **kwargs)
            return feature_disabled_response(flag_key)

        return wrapper

    return decorator

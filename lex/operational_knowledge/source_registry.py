"""Central registry for operational sources available to Lex."""

from __future__ import annotations

from .models import OperationalSourceDefinition


def _src(
    source_id: str,
    display_name: str,
    source_type: str,
    category: str,
    *,
    tenant_keys: tuple[str, ...],
    permissions: tuple[str, ...],
    repository_module: str,
    api_surface: str = "",
    tools: tuple[str, ...] = (),
    sensitive: bool = True,
    document_retrieval: bool = False,
    official_public_source: bool = False,
    notes: str = "",
) -> OperationalSourceDefinition:
    return OperationalSourceDefinition(
        source_id=source_id,
        display_name=display_name,
        source_type=source_type,
        category=category,
        tenant_keys=tenant_keys,
        required_permissions=permissions,
        repository_module=repository_module,
        api_surface=api_surface,
        deterministic_tools=tools,
        sensitive=sensitive,
        document_retrieval=document_retrieval,
        official_public_source=official_public_source,
        notes=notes,
    )


DEFAULT_SOURCE_DEFINITIONS: tuple[OperationalSourceDefinition, ...] = (
    _src(
        "clienti",
        "Clienti",
        "cliente",
        "anagrafica",
        tenant_keys=("CLIENTI_DB",),
        permissions=("clienti.leggi",),
        repository_module="pct.clienti.GestioneClienti",
        api_surface="web.helpers.get_clienti",
        tools=("search_clienti", "get_cliente_by_id"),
    ),
    _src(
        "soggetti",
        "Soggetti e parti",
        "soggetto",
        "anagrafica",
        tenant_keys=("SOGGETTI_DB", "SOGGETTI_PARTI_DB"),
        permissions=("clienti.leggi",),
        repository_module="pct.soggetti.GestioneSoggetti",
        api_surface="web.helpers.get_soggetti",
        tools=("search_soggetti", "get_soggetto"),
    ),
    _src(
        "fascicoli",
        "Fascicoli",
        "fascicolo",
        "pratiche",
        tenant_keys=("FASCICOLI_DB", "FASCICOLI_DOCS", "FASCICOLI_ARCH"),
        permissions=("fascicoli.leggi",),
        repository_module="pct.fascicoli.GestioneFascicoli",
        api_surface="web.helpers.get_fascicoli",
        tools=("search_fascicoli", "get_fascicolo"),
    ),
    _src(
        "agenda",
        "Agenda",
        "agenda",
        "operativo",
        tenant_keys=("AGENDA_DB",),
        permissions=("agenda.leggi",),
        repository_module="pct.agenda.Agenda",
        api_surface="web.helpers.get_agenda",
        tools=("get_agenda_range",),
    ),
    _src(
        "scadenziario",
        "Scadenziario",
        "scadenza",
        "operativo",
        tenant_keys=("SCADENZIARIO_DB",),
        permissions=("scadenziario.leggi",),
        repository_module="pct.scadenziario.GestioneScadenziario",
        api_surface="web.helpers.get_scadenziario",
        tools=("get_scadenze_by_fascicolo", "get_scadenze_by_cliente"),
    ),
    _src(
        "preventivi",
        "Preventivi",
        "preventivo",
        "economico",
        tenant_keys=("PREVENTIVI_DB",),
        permissions=("fatturazione.leggi",),
        repository_module="pct.preventivi.GestionePreventivi",
        api_surface="web.helpers.get_preventivi",
        tools=("get_preventivo", "search_preventivi"),
    ),
    _src(
        "conferimenti",
        "Conferimenti incarico",
        "conferimento",
        "economico",
        tenant_keys=("PREVENTIVI_DB",),
        permissions=("fatturazione.leggi",),
        repository_module="pct.preventivi.GestionePreventivi",
        api_surface="web.helpers.get_preventivi",
        tools=("get_conferimento", "search_conferimenti"),
    ),
    _src(
        "tariffario",
        "Tariffario forense",
        "tariffario",
        "economico",
        tenant_keys=(),
        permissions=("fatturazione.leggi",),
        repository_module="pct.tariffario",
        tools=("get_tariffario_result",),
        sensitive=False,
    ),
    _src(
        "fatturazione",
        "Parcelle e fatturazione",
        "parcella",
        "economico",
        tenant_keys=("FATTURAZIONE_DB",),
        permissions=("fatturazione.leggi",),
        repository_module="pct.fatturazione.GestioneFatturazione",
        api_surface="web.helpers.get_fatturazione",
        tools=("get_parcelle_by_cliente", "get_parcelle_by_fascicolo"),
    ),
    _src(
        "timesheet",
        "Attivita' e timesheet",
        "attivita",
        "economico",
        tenant_keys=("TIMESHEET_DB",),
        permissions=("fatturazione.leggi",),
        repository_module="pct.timesheet.GestioneTimesheet",
        api_surface="web.helpers.get_timesheet",
        tools=("get_attivita_by_cliente", "get_attivita_by_fascicolo"),
    ),
    _src(
        "documenti_fascicolo",
        "Documenti fascicolo",
        "documento",
        "documentale",
        tenant_keys=("FASCICOLI_DB", "FASCICOLI_DOCS"),
        permissions=("fascicoli.leggi",),
        repository_module="pct.document_intelligence",
        api_surface="DocumentAIRepository.from_fascicoli_db",
        tools=("get_documenti_fascicolo", "search_documenti_fascicolo"),
        document_retrieval=True,
    ),
    _src(
        "messaggi",
        "Messaggi, PEC ed email",
        "messaggio",
        "comunicazioni",
        tenant_keys=("MESSAGGI_DB", "EMAIL_CASELLA_DB", "EMAIL_ORDINARIA_DB"),
        permissions=("messaggi.leggi",),
        repository_module="pct.messaggi / pct.email_client",
        tools=("get_messaggi_by_cliente", "get_messaggi_by_fascicolo"),
    ),
    _src(
        "notifiche",
        "Notifiche",
        "notifica",
        "operativo",
        tenant_keys=("NOTIFICATIONS_DB",),
        permissions=(),
        repository_module="pct.notifications.NotificationRepository",
        api_surface="web.services.notifications_runtime",
        tools=("get_notifiche_utente",),
    ),
    _src(
        "telematico",
        "Portali e telematico",
        "telematico",
        "portali",
        tenant_keys=("TELEMATICO_DB", "PDP_PENALE_DB", "PORTALE_DB"),
        permissions=("telematico.leggi",),
        repository_module="web.services.pdp_penale_runtime / pct.*",
        tools=("get_telematico_status",),
    ),
    _src(
        "template_atti",
        "Template atti",
        "template_atto",
        "documentale",
        tenant_keys=("TEMPLATE_ATTI_DB",),
        permissions=("fascicoli.leggi",),
        repository_module="pct.template_atti.GestioneTemplateAtti",
        tools=("search_template_atti",),
        sensitive=False,
    ),
    _src(
        "legal_intelligence",
        "Legal intelligence",
        "legal_intelligence",
        "fonti_pubbliche",
        tenant_keys=("LEGAL_INTELLIGENCE_DB", "NORMATIVE_TABLES_DB"),
        permissions=(),
        repository_module="pct.legal_intelligence.GestioneLegalIntelligence",
        api_surface="web.helpers.get_legal_intelligence",
        tools=("get_legal_intelligence_items",),
        sensitive=False,
        official_public_source=True,
    ),
    _src(
        "update_intelligence",
        "Update intelligence",
        "update_intelligence",
        "fonti_pubbliche",
        tenant_keys=("LEGAL_INTELLIGENCE_DB",),
        permissions=(),
        repository_module="pct.legal_update_repository.LegalUpdateRepository",
        api_surface="web.helpers.get_legal_update_pipeline",
        tools=("get_update_intelligence_items",),
        sensitive=False,
        official_public_source=True,
    ),
    _src(
        "fonti_ufficiali",
        "Fonti ufficiali",
        "fonte_ufficiale",
        "fonti_pubbliche",
        tenant_keys=("IUSENTRA_LEGAL_SOURCES_DATA_DIR", "IUSENTRA_LEGAL_SOURCES_INDEX_DIR"),
        permissions=(),
        repository_module="lex.legal_sources",
        tools=("search_legal_sources",),
        sensitive=False,
        official_public_source=True,
    ),
    _src(
        "audit",
        "Registro attivita'",
        "audit",
        "governance",
        tenant_keys=("AUDIT_DB",),
        permissions=("ai.audit",),
        repository_module="pct.auth.GestioneUtenti",
        api_surface="web.helpers.get_utenti",
        tools=("get_audit_events",),
    ),
)


class OperationalSourceRegistry:
    def __init__(self, sources: tuple[OperationalSourceDefinition, ...] | None = None) -> None:
        self._sources = {source.source_id: source for source in (sources or DEFAULT_SOURCE_DEFINITIONS)}

    def all(self) -> list[OperationalSourceDefinition]:
        return list(self._sources.values())

    def get(self, source_id: str) -> OperationalSourceDefinition | None:
        return self._sources.get(str(source_id or "").strip())

    def by_category(self, category: str) -> list[OperationalSourceDefinition]:
        key = str(category or "").strip()
        return [source for source in self.all() if source.category == key]

    def enabled(self) -> list[OperationalSourceDefinition]:
        return [source for source in self.all() if source.enabled_by_default]

    def to_report(self) -> list[dict[str, object]]:
        return [source.to_dict() for source in self.all()]


def build_default_registry() -> OperationalSourceRegistry:
    return OperationalSourceRegistry()

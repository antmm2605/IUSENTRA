"""Read-only delegated agents for Lex operational knowledge."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import OperationalRoute
from .serializers import clean_spaces


@dataclass(frozen=True, slots=True)
class OperationalAgentDefinition:
    agent_id: str
    display_name: str
    category: str
    source_ids: tuple[str, ...]
    tools: tuple[str, ...]
    required_permissions: tuple[str, ...]
    self_check: tuple[str, ...]
    failure_policy: str = "Da verificare: registra motivo, lacune e prossima azione senza inventare dati."

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEFAULT_OPERATIONAL_AGENTS: tuple[OperationalAgentDefinition, ...] = (
    OperationalAgentDefinition(
        "cliente_soggetti",
        "Clienti, soggetti e parti",
        "anagrafica",
        ("clienti", "soggetti", "fascicoli"),
        (
            "search_clienti",
            "get_cliente_by_id",
            "search_soggetti",
            "get_soggetto",
            "search_fascicoli",
            "get_fascicolo",
        ),
        ("ai.usa", "clienti.leggi", "fascicoli.leggi"),
        (
            "Verifica tenant e permessi prima di leggere.",
            "Segnala ambiguita' tra clienti o soggetti omonimi.",
            "Non esporre path o dati di tenant diverso.",
        ),
    ),
    OperationalAgentDefinition(
        "scadenziario_agenda",
        "Scadenziario e agenda",
        "operativo",
        ("scadenziario", "agenda", "fascicoli"),
        ("get_scadenze_by_fascicolo", "get_scadenze_by_cliente", "get_agenda_range"),
        ("ai.usa", "scadenziario.leggi", "agenda.leggi"),
        (
            "Controlla date e periodo richiesto.",
            "Distingui scadenze da appuntamenti.",
            "Rimanda al modulo originale prima di azioni dispositive.",
        ),
    ),
    OperationalAgentDefinition(
        "preventivi_parcelle_tariffario",
        "Preventivi, parcelle e tariffario",
        "economico",
        ("preventivi", "conferimenti", "fatturazione", "tariffario", "timesheet"),
        (
            "search_preventivi",
            "search_conferimenti",
            "get_parcelle_by_cliente",
            "get_parcelle_by_fascicolo",
            "get_tariffario_result",
        ),
        ("ai.usa", "fatturazione.leggi"),
        (
            "Non inventare importi o scaglioni mancanti.",
            "Segnala parametri tariffari mancanti.",
            "Distingui preventivo, conferimento, parcella e attivita'.",
        ),
    ),
    OperationalAgentDefinition(
        "email_pec",
        "Email PEC",
        "comunicazioni",
        ("email_pec", "pec_audit", "messaggi", "fascicoli"),
        ("list_pec_messages", "get_pec_message", "list_pec_attachments", "get_pec_audit_for_email"),
        ("ai.usa", "messaggi.leggi"),
        (
            "Leggi solo inventario e dettaglio autorizzato.",
            "Usa il lettore allegati compatibile zip/file sciolti solo per metadati sicuri.",
            "Consulta il controllo PEC audit-grade quando la domanda riguarda validita', allegati mancanti, firme, confidence, MIME o collegamento al fascicolo.",
            "Non esporre credenziali, UID IMAP, path allegati o contenuto MIME integrale in risposta.",
        ),
    ),
    OperationalAgentDefinition(
        "pec_audit_controlli",
        "Controlli PEC audit-grade",
        "comunicazioni",
        ("pec_audit", "email_pec", "fascicoli", "scadenziario"),
        ("list_pec_audit_messages", "get_pec_audit_message", "get_pec_audit_for_email"),
        ("ai.usa", "messaggi.leggi"),
        (
            "Distingui dato certo dal MIME originale, dato estratto con confidence, anomalia non bloccante e decisione dell'avvocato.",
            "Quando il testo richiama Giudice di Pace, D.L. 179/2012, cancelleria, L. 53/1994, UNEP, PAT, PTT, SNT o PDP, attiva la matrice di contesto processuale e formula prima le domande operative.",
            "Per le ricevute PEC usa DPR 68/2005, CAD, regole tecniche PEC, D.L. 179/2012, D.M. 44/2011 e specifiche DGSIA come quadro di riferimento.",
            "Per notifiche in proprio verifica formula L. 53/1994, atto, relata, attestazioni, ricevute e pubblico elenco prima di proporre una scadenza.",
            "Per PAT, PTT e penale distingue giurisdizione, ufficio, portale/canale e tipo atto; se la base normativa non e' certa, segnala Da verificare.",
            "Per firme CAdES/PAdES usa CAD, eIDAS e linee guida AgID; segnala esiti non verificati o non validi senza sostituirti al verificatore ufficiale.",
            "Per deposito telematico segnala matrice atto/procura/ricevute come controllo professionale non bloccante, salvo blocchi tecnici reali del canale.",
            "Dopo un deposito PCT presidia la sequenza attesa: accettazione PEC, avvenuta consegna, esito controlli deposito e accettazione/rifiuto deposito; non comunicare deposito definitivamente accettato finche' manca la PEC finale.",
            "Registra o descrivi presidi operativi automatici quando previsti; non redigere, inviare, depositare o assumere termini legali conclusivi senza validazione dell'avvocato.",
        ),
    ),
    OperationalAgentDefinition(
        "email_ordinaria",
        "Email ordinaria",
        "comunicazioni",
        ("email_ordinaria", "messaggi", "fascicoli"),
        ("list_ordinary_email_messages", "get_ordinary_email_message", "list_ordinary_email_attachments"),
        ("ai.usa", "messaggi.leggi"),
        (
            "Leggi solo la casella del tenant corrente.",
            "Non avviare sincronizzazioni IMAP da Lex.",
            "Non esporre credenziali, UID IMAP o path allegati.",
        ),
    ),
    OperationalAgentDefinition(
        "documenti_fascicolo",
        "Documenti e atti fascicolo",
        "documentale",
        ("documenti_fascicolo", "template_atti", "fascicoli"),
        ("get_documenti_fascicolo", "search_documenti_fascicolo", "search_template_atti"),
        ("ai.usa", "fascicoli.leggi"),
        (
            "Mostra solo metadati o testo indicizzato citabile.",
            "Non esporre percorsi fisici.",
            "Segnala documenti non indicizzati invece di riassumerli a memoria.",
        ),
    ),
    OperationalAgentDefinition(
        "fascicoli_documenti_timeline",
        "Fascicoli, documenti e timeline",
        "pratiche",
        ("fascicoli", "documenti_fascicolo", "ricerca_studio"),
        ("search_fascicoli", "get_fascicolo", "get_documenti_fascicolo", "search_documenti_fascicolo"),
        ("ai.usa", "fascicoli.leggi"),
        (
            "Controlla fascicoli aperti, documenti e indice ricerca studio.",
            "Non esporre percorsi fisici o allegati non autorizzati.",
            "Segnala documenti non indicizzati, scollegati o non citabili.",
        ),
    ),
    OperationalAgentDefinition(
        "redazione_atti_editor",
        "Redazione atti, editor e copilota Lex",
        "documentale",
        ("editor_ai", "chat_lex_editor", "template_atti", "documenti_fascicolo", "contratti_pareri"),
        (
            "list_template_atti",
            "read_template_atto",
            "collect_fascicolo_context",
            "generate_editor_draft",
            "read_editor_document",
            "propose_editor_edits",
            "export_editor_document",
        ),
        ("ai.usa", "fascicoli.leggi"),
        (
            "Verifica che editor normale/professionale usino documento reale del fascicolo.",
            "Controlla che chat Lex proponga modifiche pending, non applicazioni automatiche.",
            "Segnala assenza di template, documenti indicizzati o fonti citabili.",
        ),
    ),
    OperationalAgentDefinition(
        "giurisprudenza_cassazione",
        "Citazioni verificate e ricerca giurisprudenziale",
        "fonti_pubbliche",
        ("citazioni_cassazione", "legal_intelligence", "update_intelligence", "fonti_ufficiali"),
        ("search_legal_sources", "get_legal_intelligence_items", "get_update_intelligence_items"),
        ("ai.usa",),
        (
            "Usa Cassazione ufficiale/corpus verificato per massime e citazioni.",
            "Mantieni Da verificare se mancano testo integrale o riferimento esatto.",
            "Non inventare numero, sezione, data o principio di diritto.",
        ),
        failure_policy="Da verificare: cercare fonte ufficiale alternativa o lasciare la citazione non pubblicabile.",
    ),
    OperationalAgentDefinition(
        "pct_depositi_telematici",
        "PCT, depositi e ricevute",
        "telematico",
        ("telematico", "uffici_giudiziari", "email_pec", "pec_audit", "pdf_manager", "firma_digitale"),
        ("get_telematico_status", "lookup_uffici_giudiziari", "list_pec_messages", "list_pec_audit_messages"),
        ("ai.usa", "telematico.leggi"),
        (
            "Verifica prerequisiti busta, PDF/A, allegati, firma ed esiti PEC.",
            "Non salva credenziali e non deposita automaticamente.",
            "Segnala mapping ufficio/registro/codice oggetto non pronti.",
        ),
    ),
    OperationalAgentDefinition(
        "backup_storage_database",
        "Backup, spazio e database studio",
        "manutenzione",
        ("backup_storage", "database", "email_pec", "email_ordinaria"),
        ("get_storage_status", "get_database_status", "list_pec_attachments", "list_ordinary_email_attachments"),
        ("ai.usa", "ai.audit"),
        (
            "Verifica retention massima dei backup operativi.",
            "Distingue dati studio, posta, database e cache rigenerabile.",
            "Non elimina dati e segnala spazio anomalo come Da verificare.",
        ),
        failure_policy="Da verificare: registrare area pesante, archivi mancanti e prossima manutenzione sicura.",
    ),
    OperationalAgentDefinition(
        "sito_studio_portale",
        "Sito studio e portale cliente",
        "pubblicazione",
        ("sito_studio", "client_portal", "notifiche", "audit"),
        ("get_sito_studio_status", "get_client_portal_status", "get_notifiche_utente", "get_audit_events"),
        ("ai.usa", "clienti.leggi", "fascicoli.leggi"),
        (
            "Controlla richieste pubbliche, prenotazioni e accessi cliente.",
            "Non mostra dati dimostrativi se non ci sono ingressi reali.",
            "Segnala configurazioni o token mancanti senza crearli da solo.",
        ),
    ),
    OperationalAgentDefinition(
        "fatturazione_pagamenti_sdi",
        "Fatturazione, pagamenti e SDI",
        "economico",
        ("fatturazione", "pagamenti", "fatturazione_elettronica_sdi", "timesheet"),
        ("get_parcelle_by_cliente", "get_attivita_by_cliente"),
        ("ai.usa", "fatturazione.leggi"),
        (
            "Verifica parcelle, link pagamento, notifiche SDI e attivita' valorizzate.",
            "Non invia fatture o solleciti senza azione esplicita dell'utente.",
            "Segnala importi o collegamenti mancanti invece di stimarli.",
        ),
    ),
    OperationalAgentDefinition(
        "portal_compliance_security",
        "Portale cliente, GDPR e antiriciclaggio",
        "governance",
        ("client_portal", "privacy_gdpr", "antiriciclaggio", "audit"),
        ("get_client_portal_status", "get_privacy_registry_status", "get_aml_status"),
        ("ai.usa", "clienti.leggi", "fascicoli.leggi", "ai.audit"),
        (
            "Verifica consensi, audit, accessi token e lacune GDPR/AML.",
            "Non esporta dati personali se non richiesto da workflow autorizzato.",
            "Mantiene separati stato compliance e certificazione professionale.",
        ),
    ),
    OperationalAgentDefinition(
        "ai_locale_rag_runtime",
        "AI locale, RAG e modelli",
        "lex",
        ("ai_locale", "documenti_fascicolo", "fonti_ufficiali"),
        ("get_ai_local_status", "search_documenti_fascicolo", "search_legal_sources"),
        ("ai.usa", "fascicoli.leggi"),
        (
            "Controlla modello Ollama scelto in base alle risorse locali.",
            "Verifica indicizzazione documentale senza inviare fascicoli a training esterno.",
            "Segnala mismatch embedding o reindicizzazione richiesta.",
        ),
    ),
    OperationalAgentDefinition(
        "integrazioni_native",
        "Integrazioni native e automazioni",
        "operativo",
        ("integrazioni_native", "rest_api_webhooks", "sito_studio", "notifiche"),
        ("get_integrations_status", "get_api_status", "get_sito_studio_status", "get_notifiche_utente"),
        ("ai.usa",),
        (
            "Verifica configurazioni Google, Microsoft, SDI, provider firma, notifiche e sito studio.",
            "Non mostra token o credenziali.",
            "Segnala integrazioni solo censite ma non ancora operative.",
        ),
    ),
    OperationalAgentDefinition(
        "fonti_legal_update",
        "Normativa, sentenze e fonti ufficiali",
        "fonti_pubbliche",
        ("fonti_ufficiali", "legal_intelligence", "update_intelligence"),
        ("search_legal_sources", "get_legal_intelligence_items", "get_update_intelligence_items"),
        ("ai.usa",),
        (
            "Distingui fonte ufficiale, archivio locale e ricerca web governata.",
            "Se mancano due conferme, mantieni Da verificare.",
            "Non usare dati dello studio per ricerche pubbliche.",
        ),
        failure_policy="Da verificare: cercare fonte alternativa ufficiale o registrare handoff motivato.",
    ),
)


class OperationalAgentRegistry:
    def __init__(self, agents: tuple[OperationalAgentDefinition, ...] | None = None) -> None:
        self._agents = {agent.agent_id: agent for agent in (agents or DEFAULT_OPERATIONAL_AGENTS)}

    def all(self) -> list[OperationalAgentDefinition]:
        return list(self._agents.values())

    def for_source_ids(self, source_ids: tuple[str, ...] | list[str] | set[str]) -> list[OperationalAgentDefinition]:
        wanted = {clean_spaces(source_id) for source_id in source_ids if clean_spaces(source_id)}
        if not wanted:
            return []
        return [
            agent
            for agent in self._agents.values()
            if wanted.intersection(agent.source_ids)
        ]

    def for_route(self, route: OperationalRoute | None) -> list[OperationalAgentDefinition]:
        if route is None:
            return []
        return self.for_source_ids(route.source_ids)


def build_default_agent_registry() -> OperationalAgentRegistry:
    return OperationalAgentRegistry()


__all__ = [
    "DEFAULT_OPERATIONAL_AGENTS",
    "OperationalAgentDefinition",
    "OperationalAgentRegistry",
    "build_default_agent_registry",
]

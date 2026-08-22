from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "artifacts" / "react-migration" / "audit-menu-funzioni-studio-telematico.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "react-migration" / "audit-parita-funzionale-comandi.json"
DEFAULT_MARKDOWN = ROOT / "artifacts" / "react-migration" / "audit-parita-funzionale-comandi.md"
DEFAULT_REAL_PROOFS = ROOT / "artifacts" / "react-migration" / "prove-reali-parita-funzionale.json"


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def _contract(
    capability_id: str,
    pattern: str,
    *,
    route: str,
    component: str,
    code_checks: tuple[tuple[str, str], ...],
    api: str = "",
    persistence: str = "",
    tests: tuple[str, ...] = (),
    surface_pattern: str = "",
    source_path_pattern: str = "",
    kind: str = "",
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "pattern": re.compile(pattern),
        "surface_pattern": re.compile(surface_pattern) if surface_pattern else None,
        "source_path_pattern": re.compile(source_path_pattern) if source_path_pattern else None,
        "kind": kind,
        "route": route,
        "component": component,
        "api": api,
        "persistence": persistence,
        "tests": list(tests),
        "code_checks": code_checks,
    }


def _surface_contract(
    capability_id: str,
    surface_pattern: str,
    *,
    route: str,
    component: str,
    code_checks: tuple[tuple[str, str], ...],
    api: str = "",
    persistence: str = "",
    tests: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Collega i comandi interni di una finestra al relativo flusso operativo."""
    return _contract(
        capability_id,
        r".*",
        route=route,
        component=component,
        code_checks=code_checks,
        api=api,
        persistence=persistence,
        tests=tests,
        surface_pattern=surface_pattern,
    )


# La corrispondenza e' intenzionalmente esplicita. Una pagina affine non prova
# l'equivalenza di una funzione e non viene usata per promuovere lo stato.
CONTRACTS: tuple[dict[str, Any], ...] = (
    _contract(
        "fascicoli_elenco_attivi",
        r"(?:^|_)(?:pratiche_attive|elenco_pratiche|rubrica_pratiche)(?:_|$)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="pct.fascicoli",
        code_checks=(("frontend/src/App.tsx", "isFascicoliPage"), ("frontend/src/components/FascicoliPage.tsx", "FascicoliTable")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_archivio",
        r"(?:^|_)(?:pratiche_archiviate|archivio_pratiche|archivia_pratica)(?:_|$)",
        route="/fascicoli/archivio",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="pct.fascicoli",
        code_checks=(("frontend/src/App.tsx", "isFascicoliPage"), ("frontend/src/components/FascicoliPage.tsx", "kind: 'archive'")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_nuovo",
        r"(?:^|_)(?:nuova_pratica|nuovo_fascicolo|menuitem_aggiungi_pratica)(?:_|$)",
        route="/fascicoli/nuovo",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="pct.fascicoli",
        code_checks=(("frontend/src/App.tsx", "'/fascicoli/nuovo'"), ("frontend/src/components/FascicoliPage.tsx", "Nuovo fascicolo")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_gruppi",
        r"(?:^|_)(?:faldoni|gruppi_pratiche|filtra_pratiche_per_gruppo|nomegruppo)(?:_|$)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli?group_by=gruppo",
        persistence="pct.fascicoli.nome_gruppo",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "Raggruppa"), ("web/services/react_fascicoli_bridge.py", "_group_list_items")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_ricerca_filtri",
        r"(?:^|_)(?:trova_pratiche|filtra_rubrica_per|ricerca_pratiche|filtra_rubrica|trova_rubrica_sx)(?:_|$)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli?f_*=",
        persistence="preferenze filtri tenant-aware",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "practiceFieldFilters"), ("web/blueprints/api_v1_react.py", "_fascicoli_request_field_filters")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "agenda_nuovo_evento",
        r"(?:^|_)(?:aggiungi_udienza|aggiungi_adempimento|aggiungi_appuntamento|aggiungi_memorandum|aggiungi_scadenza|nuova_udienza|nuovo_adempimento|nuovo_appuntamento|nuovo_memorandum|nuova_scadenza)(?:_|$)",
        route="/agenda/nuovo",
        component="NuovoAppuntamentoPage",
        api="/api/v1/ui/agenda",
        persistence="agenda tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isNewAppointmentPage"),
            ("frontend/src/components/NuovoAppuntamentoPage.tsx", "NuovoAppuntamentoPage"),
            ("frontend/src/components/AgendaPage.tsx", "NewAgendaMenu"),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _contract(
        "agenda_viste",
        r"^(?:giorno_giorno|settimana_settimana|mese_mese|timelineagenda_timelineagenda)$",
        route="/agenda",
        component="AgendaPage",
        api="/api/v1/ui/agenda",
        persistence="agenda tenant-aware",
        code_checks=(
            ("frontend/src/components/AgendaPage.tsx", "timeline: 'Cronologia'"),
            ("frontend/src/components/AgendaPage.tsx", "AgendaTimeline"),
            ("frontend/src/agendaData.ts", "view === 'timeline'"),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _contract(
        "agenda_gestione_evento",
        r"(?:^|_)(?:elimina_agenda_elimina_agenda|modifica_agenda_modifica_agenda|rinvia_agenda_rinvia_agenda)(?:_|$)",
        route="/agenda/:id",
        component="AgendaPage",
        api="/agenda/:id/modifica, /agenda/:id/elimina",
        persistence="agenda tenant-aware",
        code_checks=(
            ("frontend/src/components/AgendaPage.tsx", "AgendaDeleteAction"),
            ("frontend/src/components/AgendaPage.tsx", "<CalendarClock size={15}/>Rinvia"),
            ("web/bootstrap/dashboard_routes.py", 'message = "Voce eliminata dall\'agenda."'),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _contract(
        "anagrafica_nuovo_soggetto",
        r"(?:^|_)(?:aggiungi_cliente|aggiungi_controparte|aggiungi_testimone|aggiungi_terzo|aggiungi_corrispondente|aggiungi_socio|nuovo_cliente|nuovo_soggetto)(?:_|$)",
        route="/soggetti/nuovo",
        component="SoggettoFormPage",
        api="/api/v1/ui/soggetti",
        persistence="clienti e soggetti tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isNewSubjectPage"), ("frontend/src/components/SoggettoFormPage.tsx", "SoggettoFormPage")),
        tests=("tests/test_react_soggetti_api.py",),
    ),
    _contract(
        "documenti_archivio",
        r"^videoscrittura_btnvideoscrittura(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="/api/v1/ui/editor-professionale",
        persistence="documenti dei fascicoli tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isEditorProfessionalePage"),
            ("frontend/src/components/EditorProfessionalePage.tsx", "EditorProfessionalePage"),
            ("web/services/react_document_archive_bridge.py", '"source": "fascicoli_tenant"'),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "documenti_nuovo",
        r"(?:^|_)aggiungi_videoscrittura(?:_|$)",
        route="/template-atti/editor",
        component="TemplateAttiPage",
        api="salvataggio documento nel fascicolo",
        persistence="documenti dei fascicoli tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "Nuovo documento"),
            ("web/services/react_document_archive_bridge.py", '"newDocument": "/template-atti/editor"'),
            ("frontend/src/components/TemplateAttiPage.tsx", "saveCurrentDraft"),
        ),
        tests=("tests/test_react_document_archive.py", "tests/test_template_atti_react.py"),
    ),
    _contract(
        "documenti_ricerca_filtri",
        r"(?:^|_)(?:elimina_filtro_videoscrittura|filtra_videoscrittura|trova_videoscrittura_sx)(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="/api/v1/ui/editor-professionale?q=&tipo=&formato=&fascicolo=",
        persistence="filtri applicati ai documenti dei fascicoli",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "resetFilters"),
            ("frontend/src/components/EditorProfessionalePage.tsx", "iu-editor-pro-filters"),
            ("web/services/react_document_archive_bridge.py", "type_filter"),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "documenti_modifica",
        r"(?:^|_)modifica_videoscrittura(?:_|$)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="documento reale del fascicolo",
        persistence="documento aggiornato nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "row.actions.edit"),
            ("frontend/src/App.tsx", "isDocumentEditorPage"),
            ("frontend/src/components/DocumentEditorPage.tsx", "DocumentEditorPage"),
        ),
        tests=("tests/test_react_document_archive.py", "tests/test_fascicolo_detail_ux.py"),
    ),
    _contract(
        "documenti_cestino",
        r"(?:^|_)elimina_videoscrittura(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="spostamento, ripristino ed eliminazione definitiva",
        persistence="documenti_cestino del fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "kind: 'trash'"),
            ("web/services/react_document_archive_bridge.py", "permanentDelete"),
            ("pct/fascicoli.py", "documenti_cestino"),
        ),
        tests=("tests/test_react_document_archive.py", "tests/test_fascicoli.py"),
    ),
    _contract(
        "documenti_esporta",
        r"(?:^|_)esporta_semplice_videoscrittura(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="download degli originali senza rinomina",
        persistence="nessuna modifica ai documenti sorgente",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "exportOriginals"),
            ("frontend/src/components/EditorProfessionalePage.tsx", "showDirectoryPicker"),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "documenti_editor_rapido",
        r"^quick_word_btnquickword(?:_|$)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="documento reale del fascicolo",
        persistence="documento aggiornato nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isDocumentEditorPage"),
            ("frontend/src/components/DocumentEditorPage.tsx", "DocumentEditorPage"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "documenti_firma_digitale",
        r"(?:^|_)(?:firma_digitale|firma_pades|firma_cades)(?:_|$)",
        route="/guida/firma-digitale",
        component="TelematicoPage",
        api="Local Signer sul PC in uso",
        persistence="documenti firmati nel fascicolo",
        code_checks=(("frontend/src/App.tsx", "'/guida/firma-digitale'"), ("web", "")),
        tests=("tests/test_local_signer_contract.py",),
    ),
    _contract(
        "email_nuovo_messaggio",
        r"(?:^|_)(?:nuova_email|scrivi_email|email_vuota|menuitem_aggiungi_email)(?:_|$)",
        route="/email/scrivi",
        component="EmailComposePage",
        api="/api/v1/ui/email",
        persistence="messaggi tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isEmailComposePage"), ("frontend/src/components/EmailComposePage.tsx", "EmailComposePage")),
        tests=("tests/test_react_email_api.py",),
    ),
    _contract(
        "notifica_pec",
        r"(?:^|_)(?:notifica_mezzo_pec|notificamezzopec|notifica_a_mezzo_pec)(?:_|$)",
        route="/notifiche-legali",
        component="NotificheLegaliPage",
        api="invio dal PC locale",
        persistence="notifica e documenti nel fascicolo",
        code_checks=(("frontend/src/App.tsx", "isNotificheLegaliPage"), ("frontend/src/components/NotificheLegaliPage.tsx", "NotificheLegaliPage")),
        tests=("tests/test_notifiche_legali_react.py",),
    ),
    _contract(
        "deposito_civile",
        r"(?:^|_)(?:depositi_telematici_civile|depositi_in_materia_civile|deposito_telematico_civile)(?:_|$)",
        route="/deposito/checklist",
        component="FascicoloDepositoPage",
        api="preparazione server e invio dal PC locale",
        persistence="deposito e ricevute nel fascicolo",
        code_checks=(("frontend/src/App.tsx", "'/deposito/checklist'"), ("frontend/src/components/FascicoloDepositoPage.tsx", "Invia deposito reale")),
        tests=("tests/test_deposito_reale_contract.py",),
    ),
    _contract(
        "impostazioni_pec",
        r"(?:^|_)(?:configurazione_pec|configurazione_della_pec)(?:_|$)",
        route="/impostazioni?tab=pec",
        component="ImpostazioniPage",
        api="/api/v1/ui/impostazioni",
        persistence="configurazione tenant-aware; password sul dispositivo locale",
        code_checks=(("frontend/src/App.tsx", "isImpostazioniPage"), ("frontend/src/components/ImpostazioniPage.tsx", "ImpostazioniPage")),
        tests=("tests/test_react_impostazioni_api.py",),
    ),
    _contract(
        "backup",
        r"(?:^|_)(?:backup|esegui_backup|ripristina_backup)(?:_|$)",
        route="/backup",
        component="BackupPage",
        api="/api/v1/ui/backup",
        persistence="archivio tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isBackupPage"), ("frontend/src/components/BackupPage.tsx", "BackupPage")),
        tests=("tests/test_react_backup_api.py",),
    ),
    _surface_contract(
        "deposito_preparazione_e_invio",
        r"^(?:FormSentMailBee|FormDepositaConSoftwareEsterno|FormMotivoRicorsoCassazione|FormQualeAllegato|FormQualeScarico|FormEstremiMatrimonio|FormEstremiPagamentoBollettinoPostale|FormEstremiPagamentoF23|FormEstremiPagamentoRicevutaTelematica|FormEstremiPagamentosingolaMarca|PoliswebRole|UfficioRegistroRuolo|LicenzaUsoDepostoTelematico)$",
        route="/fascicoli/:id/deposito/prepara",
        component="FascicoloDepositoPage",
        api="/fascicoli/:id/deposito/*",
        persistence="deposito, classificazioni, firme, busta e ricevute tenant-aware",
        code_checks=(
            ("frontend/src/components/FascicoloDepositoPage.tsx", "Invia deposito reale"),
            ("web/bootstrap/deposito_routes.py", "register_deposito_routes"),
            ("pct/busta.py", "class BustaTelematica"),
        ),
        tests=("tests/test_deposito.py", "tests/test_deposito_reale_contract.py"),
    ),
    _surface_contract(
        "notifica_legale",
        r"^(?:SchedaNotifica|NotificaEsito)$",
        route="/notifiche-legali",
        component="NotificheLegaliPage",
        api="/api/v1/ui/notifiche-legali",
        persistence="notifica, relata, attestazione, destinatari e ricevute nel fascicolo",
        code_checks=(
            ("frontend/src/components/NotificheLegaliPage.tsx", "NotificheLegaliPage"),
            ("web/services/react_notifiche_legali_bridge.py", "build_react_notifiche_legali_payload"),
        ),
        tests=("tests/test_notifiche_legali_react.py", "tests/test_notifiche_legali.py"),
    ),
    _surface_contract(
        "richieste_unep",
        r"^(?:FormTipoNotificaUNEP|SchedaBeneImmobile|SchedaBeneMobile|SchedaDatiTavolari|SchedaIpoteca|SchedaTitolo)$",
        route="/fascicoli/:id/deposito/prepara",
        component="FascicoloDepositoPage",
        api="/fascicoli/:id/deposito/*",
        persistence="dati UNEP e DatiAtto.xml tenant-aware",
        code_checks=(
            ("frontend/src/components/FascicoloDepositoPage.tsx", "unepDestinationParties"),
            ("pct/datiatto_unep.py", "build_unep_datiatto"),
        ),
        tests=("tests/test_datiatto_unep.py", "tests/test_deposito.py"),
    ),
    _surface_contract(
        "fascicolo_dettaglio",
        r"^(?:SchedaPratica|SchedaAppunti|FormAltriDifensori|FormQualificaGiudiziale|frmFaldoni|frmPraticheBook)$",
        route="/fascicoli/:id",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli/:id",
        persistence="fascicoli, gruppi, note e parti tenant-aware",
        code_checks=(
            ("frontend/src/components/FascicoliPage.tsx", "Parti già collegate al fascicolo"),
            ("web/services/react_fascicoli_bridge.py", "build_react_fascicolo_detail_payload"),
        ),
        tests=("tests/test_fascicoli.py", "tests/test_fascicolo_detail_ux.py"),
    ),
    _surface_contract(
        "anagrafica_gestione",
        r"^(?:SchedaAnagrafica|SchedaDomicilio|frmAddressBook|frmEmailBook|frmRubricaTelefonica)$",
        route="/soggetti",
        component="SoggettiPage",
        api="/api/v1/ui/soggetti",
        persistence="clienti, soggetti e recapiti tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isSoggettiPage"),
            ("frontend/src/components/SoggettiPage.tsx", "SoggettiPage"),
        ),
        tests=("tests/test_react_soggetti_api.py",),
    ),
    _surface_contract(
        "profilo_utenti",
        r"^(?:SchedaAnagraficaUtente|FormModificaCredenziali)$",
        route="/profilo",
        component="ProfiloPage",
        api="/api/v1/ui/profilo",
        persistence="profilo e credenziali tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isProfiloPage"), ("frontend/src/components/ProfiloPage.tsx", "ProfiloPage")),
        tests=("tests/test_react_shell.py",),
    ),
    _surface_contract(
        "agenda_eventi",
        r"^(?:SchedaAgenda|SchedaAllarme|DataRinvioDialog|FindDateDialog|WizardRinvia)$",
        route="/agenda",
        component="AgendaPage",
        api="/api/v1/ui/agenda",
        persistence="agenda e scadenze tenant-aware",
        code_checks=(
            ("frontend/src/components/AgendaPage.tsx", "AgendaPage"),
            ("frontend/src/components/NuovoAppuntamentoPage.tsx", "NuovoAppuntamentoPage"),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _surface_contract(
        "email_pec_gestione",
        r"^(?:SchedaEmailRicevute|frmAccountSettings|frmMittenteSettings)$",
        route="/email",
        component="EmailPecPage",
        api="/api/v1/ui/email",
        persistence="messaggi e configurazione PEC tenant-aware; password solo locale",
        code_checks=(
            ("frontend/src/components/EmailPecPage.tsx", "EmailPecPage"),
            ("frontend/src/features/impostazioni/components/SettingsActions.tsx", "Verifiche PEC"),
        ),
        tests=("tests/test_react_email_api.py", "tests/test_react_impostazioni_api.py"),
    ),
    _surface_contract(
        "contabilita_e_fatturazione",
        r"^(?:FattureAcquisto|SchedaOnorari|SchedaParcella|SchedaPrestazioneSingola|SchedaPrestazioniUpDown|SchedaPrimaNotaCassa|SchedaIncassi|SchedaResoconto|SchedaRecuperaVociDaPrecedenteParcella|SchedaRecuperaVociDaPrimaNotaCassa|SchedaRecuperaVociDalTariffario|SchedaRecuperaVociDallaPratica|QualeModificaContabilit.|QualeParcella|QualeParcellaNotaSpese|ParametriParcella|NuovoTariffarioPersonale|ParametriNuovoTariffario|SchedaSingolavoceNuovoTariffario)$",
        route="/fatturazione",
        component="FatturazionePage",
        api="/api/v1/ui/fatturazione",
        persistence="fatture, parcelle, movimenti e tariffario tenant-aware",
        code_checks=(
            ("frontend/src/components/FatturazionePage.tsx", "FatturazionePage"),
            ("frontend/src/components/IncassiPagamentiPage.tsx", "IncassiPagamentiPage"),
            ("frontend/src/components/TariffarioPage.tsx", "TariffarioPage"),
        ),
        tests=("tests/test_fatturazione.py", "tests/test_incassi_pagamenti.py"),
    ),
    _surface_contract(
        "documenti_gestione",
        r"^(?:DocumentiBook|SchedaDocumento|QualeSchedario|QualeVideoscrittura)$",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="/api/v1/ui/editor-professionale",
        persistence="documenti dei fascicoli tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "EditorProfessionalePage"),
            ("web/services/react_document_archive_bridge.py", "build_react_document_archive_payload"),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _surface_contract(
        "template_e_macro",
        r"^(?:SchedaSviluppoMacro|frmParametriMacro|FormSostituzioneMetadati|FormularioBook)$",
        route="/template-atti/editor",
        component="TemplateAttiPage",
        api="/template-atti/api/*",
        persistence="template e bozze tenant-aware",
        code_checks=(
            ("frontend/src/components/TemplateAttiPage.tsx", "Compilazione multipla"),
            ("frontend/src/components/TemplateAttiPage.tsx", "Campi variabili"),
        ),
        tests=("tests/test_template_atti_react.py",),
    ),
    _surface_contract(
        "firma_digitale_verifica",
        r"^(?:QualifiedCertificate|FormFirmaAllegato|FormVerificaFirmeDigitali)$",
        route="/guida/firma-digitale",
        component="FascicoliPage",
        api="Local Signer sul PC in uso",
        persistence="documenti firmati e verifiche nel fascicolo",
        code_checks=(
            ("frontend/src/components/FascicoliPage.tsx", "Verifica firma"),
            ("tools/local_signer.py", "def _info_token"),
        ),
        tests=("tests/test_local_signer_contract.py",),
    ),
    _surface_contract(
        "strumenti_calcolo",
        r"^(?:FormCodiceFiscale|FormComputoTermini|FormScorporo|FormHash|FormCountDown)$",
        route="/strumenti-legali",
        component="StrumentiLegaliPage",
        api="/api/v1/ui/strumenti-legali",
        persistence="nessun dato persistente salvo scelta esplicita",
        code_checks=(
            ("frontend/src/components/StrumentiLegaliPage.tsx", "StrumentiLegaliPage"),
            ("pct/applicazioni_catalogo.py", "calcolo_codice_fiscale"),
        ),
        tests=("tests/test_strumenti_legali.py", "tests/test_applicazioni_runtime.py"),
    ),
    _surface_contract(
        "privacy_registro",
        r"^Privacy$",
        route="/privacy/registro",
        component="PrivacyRegistroPage",
        api="/api/v1/ui/privacy",
        persistence="registro privacy tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isPrivacyRegistroPage"), ("frontend/src/components/PrivacyRegistroPage.tsx", "PrivacyRegistroPage")),
        tests=("tests/test_react_privacy_api.py",),
    ),
    _surface_contract(
        "amministrazione_archivi",
        r"^(?:Backup|Restore|Compattazione|DatabasePath)$",
        route="/backup",
        component="BackupPage",
        api="/api/v1/ui/backup",
        persistence="database SQL e backup tenant-aware",
        code_checks=(("frontend/src/components/BackupPage.tsx", "BackupPage"), ("frontend/src/components/AdminDatabasePage.tsx", "AdminDatabasePage")),
        tests=("tests/test_react_backup_api.py", "tests/test_database.py"),
    ),
    _surface_contract(
        "sincronizzazione_calendari",
        r"^GoogleCalendar$",
        route="/impostazioni/calendario",
        component="ImpostazioniPage",
        api="/api/v1/ui/impostazioni/calendario",
        persistence="profili calendario tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isAgendaImportPage"), ("pct/calendar_sync_engine.py", "class CalendarSyncEngine")),
        tests=("tests/test_calendar_sync.py",),
    ),
    _surface_contract(
        "lettore_interno",
        r"^BrowserForm$",
        route="/fascicoli/:id/documenti/:id",
        component="EmbeddedDocumentViewer",
        api="lettore documenti interno",
        persistence="nessuna modifica al documento sorgente",
        code_checks=(("frontend/src/App.tsx", "embeddedViewer"), ("web/services/signed_attachment_preview.py", "preview")),
        tests=("tests/test_document_viewer_formats.py",),
    ),
    _contract(
        "editor_file_export",
        r"(?:^|_)(?:new|open|save|save_as|print|print_preview|quick_print|esporta_formato_pdf|esporta_formato_doc|invia_formato_pdf|invia_formato_rtf|invia_come_allegato_semplice)(?:_|$)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="salvataggio, importazione ed export documento reale",
        persistence="documento del fascicolo tenant-aware",
        surface_pattern=r"^(?:QuickWordMain|FormularioBook)$",
        code_checks=(
            ("frontend/src/components/DocumentEditorPage.tsx", "exportFile"),
            ("frontend/src/components/TemplateAttiPage.tsx", "Esporta RTF"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py", "tests/test_template_atti_react.py"),
    ),
    _contract(
        "editor_formattazione",
        r"(?:bold|italic|underline|strike|grassetto|corsivo|sottolineato|barrato|font|carattere|paragrafo|justify|align|allinea|elenco|list|indent|outdent|evidenzia|colore_testo|interlinea)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="editor documento reale",
        persistence="contenuto e stile del documento",
        surface_pattern=r"^QuickWordMain$",
        code_checks=(
            ("frontend/src/components/DocumentEditorPage.tsx", "Barra strumenti editor"),
            ("frontend/src/components/DocumentEditorPage.tsx", "insertOrderedList"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "editor_cerca_sostituisci",
        r"(?:find|replace|trova|cerca|sostituisci|goto|vai_a)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="ricerca locale nel documento aperto",
        persistence="contenuto modificato solo dopo salvataggio",
        surface_pattern=r"^(?:QuickWordMain|frmFindReplace|GoToDialog)$",
        code_checks=(
            ("frontend/src/components/DocumentEditorPage.tsx", "Cerca e sostituisci"),
            ("frontend/src/components/DocumentEditorPage.tsx", "replaceSelection"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "editor_conteggio_documento",
        r".*",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="conteggio locale del documento aperto",
        persistence="nessuna",
        surface_pattern=r"^(?:FormWordCount)$",
        code_checks=(
            ("frontend/src/components/DocumentEditorPage.tsx", "stats.words"),
            ("frontend/src/components/DocumentEditorPage.tsx", "stats.chars"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "editor_dettatura",
        r"(?:dictation|speechnotes|talktype|dettatura|microfono)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="Web Speech sul PC in uso",
        persistence="solo testo trascritto nel documento",
        surface_pattern=r"^QuickWordMain$",
        code_checks=(
            ("frontend/src/components/DocumentEditorPage.tsx", "startEditorDictation"),
            ("frontend/src/components/DocumentEditorPage.tsx", "IusentraVoiceInput"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "editor_tabelle_collegamenti",
        r"(?:table|tabella|hyperlink|collegamento)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="editor documento reale",
        persistence="contenuto del documento",
        surface_pattern=r"^(?:QuickWordMain|InsertHyperlinkDialog)$",
        code_checks=(
            ("frontend/src/components/DocumentEditorPage.tsx", "insertTable"),
            ("frontend/src/components/DocumentEditorPage.tsx", "insertLink"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "editor_metadati_fascicolo",
        r"(?:metadato|metadata|dataodierna|nomepratica|oggettopratica|riferimentocartaceo|tipopratica|nomedifensore)",
        route="/template-atti/editor",
        component="TemplateAttiPage",
        api="/template-atti/api/*",
        persistence="bozza e campi del fascicolo",
        surface_pattern=r"^QuickWordMain$",
        code_checks=(
            ("frontend/src/components/TemplateAttiPage.tsx", "Campi variabili"),
            ("frontend/src/components/TemplateAttiPage.tsx", "replaceFieldPlaceholderInHtml"),
        ),
        tests=("tests/test_template_atti_react.py",),
    ),
    _contract(
        "documenti_scanner_locale",
        r"(?:scanner|acquisisci)",
        route="/strumenti-documentali?modo=multipage",
        component="DocumentToolsPage",
        api="Local Signer sul PC in uso",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        surface_pattern=r"^(?:FormUnisciPDF|FormComprimiFiles|DotNetTwain|UserControlStrumenti)$",
        code_checks=(
            ("frontend/src/components/DocumentToolsPage.tsx", "acquireFromLocalScanner"),
            ("tools/local_signer.py", '"/scanner/acquire"'),
        ),
        tests=("tests/test_document_tools.py", "tests/test_local_signer.py"),
    ),
    _surface_contract(
        "documenti_unione_pdf",
        r"^FormUnisciPDF$",
        route="/strumenti-documentali?modo=merge",
        component="DocumentToolsPage",
        api="/api/v1/ui/document-tools/merge",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/DocumentToolsPage.tsx", "Unisci documenti PDF"),
            ("web/services/document_tools.py", "def merge_pdfs"),
            ("web/blueprints/api_v1_document_tools.py", 'post("/merge")'),
        ),
        tests=("tests/test_document_tools.py",),
    ),
    _contract(
        "documenti_unione_pdf",
        r"(?:unisci_pdf|unione_pdf)",
        route="/strumenti-documentali?modo=merge",
        component="DocumentToolsPage",
        api="/api/v1/ui/document-tools/merge",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(
            ("frontend/src/components/DocumentToolsPage.tsx", "Unisci documenti PDF"),
            ("web/services/document_tools.py", "def merge_pdfs"),
        ),
        tests=("tests/test_document_tools.py",),
    ),
    _surface_contract(
        "documenti_archivio_zip",
        r"^FormComprimiFiles$",
        route="/strumenti-documentali?modo=zip",
        component="DocumentToolsPage",
        api="/api/v1/ui/document-tools/zip",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/DocumentToolsPage.tsx", "Crea un archivio ZIP"),
            ("web/services/document_tools.py", "def create_zip"),
            ("web/blueprints/api_v1_document_tools.py", 'post("/zip")'),
        ),
        tests=("tests/test_document_tools.py",),
    ),
    _surface_contract(
        "documenti_multipagina",
        r"^DotNetTwain$",
        route="/strumenti-documentali?modo=multipage",
        component="DocumentToolsPage",
        api="/api/v1/ui/document-tools/multipage",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/DocumentToolsPage.tsx", "Crea un PDF multipagina"),
            ("web/services/document_tools.py", "def images_to_pdf"),
        ),
        tests=("tests/test_document_tools.py",),
    ),
    _contract(
        "home_agenda",
        r"^agenda_",
        route="/agenda",
        component="AgendaPage",
        api="/api/v1/ui/agenda",
        persistence="agenda tenant-aware",
        surface_pattern=r"^UserControlHome$",
        code_checks=(("frontend/src/App.tsx", "isAgendaPage"), ("frontend/src/components/AgendaPage.tsx", "AgendaPage")),
        tests=("tests/test_agenda.py",),
    ),
    _contract(
        "home_notiziario_fonti",
        r"^(?:albo_avvocati_cnf|cassa_forense|fatture_corrispettivi|gazzetta_ufficiale|notiziario)_",
        route="/",
        component="NotiziarioPanel",
        api="/api/v1/ui/notiziario",
        persistence="interazioni Notiziario tenant-aware",
        surface_pattern=r"^UserControlHome$",
        code_checks=(
            ("frontend/src/components/NotiziarioPanel.tsx", "NotiziarioPanel"),
            ("web/blueprints/api_v1_react.py", "_NOTIZIARIO_QUICK_SOURCES"),
        ),
        tests=("tests/test_notiziario_react.py",),
    ),
    _contract(
        "home_anagrafiche",
        r"^(?:anagrafica|rubrica)_",
        route="/clienti",
        component="AnagraficaClientiPage",
        api="/api/v1/ui/clienti",
        persistence="clienti e soggetti tenant-aware",
        surface_pattern=r"^UserControlHome$",
        code_checks=(("frontend/src/App.tsx", "isClientiPage"), ("frontend/src/components/AnagraficaClientiPage.tsx", "AnagraficaClientiPage")),
        tests=("tests/test_react_clienti_api.py",),
    ),
    _contract(
        "home_email",
        r"^email_",
        route="/email",
        component="EmailPecPage",
        api="/api/v1/ui/email",
        persistence="messaggi tenant-aware",
        surface_pattern=r"^UserControlHome$",
        code_checks=(("frontend/src/App.tsx", "isEmailPage"), ("frontend/src/components/EmailPecPage.tsx", "EmailPecPage")),
        tests=("tests/test_react_email_api.py",),
    ),
    _contract(
        "home_fatturazione",
        r"^fatture_",
        route="/fatturazione",
        component="FatturazionePage",
        api="/api/v1/ui/fatturazione",
        persistence="documenti contabili tenant-aware",
        surface_pattern=r"^UserControlHome$",
        code_checks=(("frontend/src/App.tsx", "isFatturazionePage"), ("frontend/src/components/FatturazionePage.tsx", "FatturazionePage")),
        tests=("tests/test_fatturazione.py",),
    ),
    _contract(
        "home_movimenti",
        r"^movimenti_",
        route="/incassi-pagamenti",
        component="IncassiPagamentiPage",
        api="/api/v1/ui/incassi-pagamenti",
        persistence="movimenti tenant-aware",
        surface_pattern=r"^UserControlHome$",
        code_checks=(("frontend/src/App.tsx", "isIncassiPagamentiPage"), ("frontend/src/components/IncassiPagamentiPage.tsx", "IncassiPagamentiPage")),
        tests=("tests/test_incassi_pagamenti.py",),
    ),
    _contract(
        "home_strumenti",
        r"^strumenti_",
        route="/strumenti-operativi",
        component="StudioModulePage",
        api="/api/v1/ui/studio-module/strumenti-operativi",
        persistence="nessuna",
        surface_pattern=r"^UserControlHome$",
        code_checks=(("frontend/src/studioModuleData.ts", "strumenti-operativi"), ("frontend/src/components/StudioModulePage.tsx", "setRecordLimit((current) => current + 24)")),
        tests=("tests/test_functional_parity_audit.py",),
    ),
    _contract(
        "strumenti_aggiornamento_pct",
        r"^aggiornamento_pct_",
        route="/telematico",
        component="TelematicoPage",
        api="/api/v1/ui/telematico",
        persistence="cataloghi e stato servizi telematici",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/components/TelematicoPage.tsx", "TelematicoPage"), ("web/services/react_telematico_bridge.py", "build_react_telematico_payload")),
        tests=("tests/test_react_telematico_api.py",),
    ),
    _contract(
        "strumenti_calcoli_fiscali",
        r"^(?:calcolo_codice_fiscale|scorporo_dell_imposta)_",
        route="/strumenti-legali",
        component="StrumentiLegaliPage",
        api="/strumenti-legali/api/*",
        persistence="risultato collegabile al fascicolo",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("web/blueprints/strumenti_legali.py", "api_codice_fiscale"), ("web/blueprints/strumenti_legali.py", "api_scorporo_iva")),
        tests=("tests/test_strumenti_lotto2a.py", "tests/test_strumenti_legali.py"),
    ),
    _contract(
        "strumenti_archivi",
        r"^(?:compattazione_degli_archivi|ripristino_dati_restore)_",
        route="/backup",
        component="BackupPage",
        api="/api/v1/ui/backup",
        persistence="backup tenant-aware e manutenzione governata",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/components/BackupPage.tsx", "BackupPage"), ("web/services/react_backup_bridge.py", "build_react_backup_payload")),
        tests=("tests/test_backup.py", "tests/test_react_backup_api.py"),
    ),
    _contract(
        "strumenti_computo_termini",
        r"^computo_dei_termini_",
        route="/scadenziario/calcola-termini",
        component="CalcolaTerminiPage",
        api="/api/v1/ui/scadenziario/calcola-termini",
        persistence="risultato collegabile a scadenza e fascicolo",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/App.tsx", "isCalculatorPage"), ("frontend/src/components/ScadenziarioPage.tsx", "CalcolaTerminiPage")),
        tests=("tests/test_scadenziario_react.py",),
    ),
    _contract(
        "strumenti_impostazioni_interfaccia",
        r"^(?:configurazione_di_rete|interfaccia_del_programma|scelta_wp)_",
        route="/impostazioni",
        component="ImpostazioniPage",
        api="/api/v1/ui/impostazioni",
        persistence="impostazioni tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/App.tsx", "isImpostazioniPage"), ("frontend/src/features/impostazioni/ImpostazioniPage.tsx", "ImpostazioniPage")),
        tests=("tests/test_react_impostazioni_api.py",),
    ),
    _contract(
        "strumenti_google_calendar",
        r"^google_calendar_",
        route="/impostazioni?tab=calendario",
        component="CalendarSettingsPanel",
        api="/api/v1/ui/impostazioni/calendario",
        persistence="profili calendario tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/features/impostazioni/components/CalendarSettingsPanel.tsx", "Collega Google Calendar"),),
        tests=("tests/test_calendar_credentials.py",),
    ),
    _contract(
        "strumenti_manutenzione_posta",
        r"^manutenzione_posta_in_arrivo_",
        route="/email",
        component="EmailPecPage",
        api="/api/v1/ui/email/sync",
        persistence="messaggi e stato sincronizzazione tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/components/EmailPecPage.tsx", "EmailPecPage"),),
        tests=("tests/test_react_email_api.py",),
    ),
    _contract(
        "strumenti_privacy",
        r"^privacy_",
        route="/privacy/registro",
        component="PrivacyRegistroPage",
        api="/api/v1/ui/privacy",
        persistence="registro privacy tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/App.tsx", "isPrivacyRegistroPage"), ("frontend/src/components/PrivacyRegistroPage.tsx", "PrivacyRegistroPage")),
        tests=("tests/test_privacy_registry.py",),
    ),
    _contract(
        "strumenti_profilo",
        r"^profilo_utente_",
        route="/profilo",
        component="ProfiloPage",
        api="/api/v1/ui/profilo",
        persistence="profilo utente e studio",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/App.tsx", "isProfiloPage"), ("frontend/src/components/ProfiloPage.tsx", "ProfiloPage")),
        tests=("tests/test_react_shell.py",),
    ),
    _contract(
        "strumenti_macro",
        r"^programmaz_macro_",
        route="/template-atti",
        component="TemplateAttiPage",
        api="/template-atti/api/*",
        persistence="modelli e variabili tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/components/TemplateAttiPage.tsx", "Campi variabili"),),
        tests=("tests/test_template_atti_react.py",),
    ),
    _contract(
        "strumenti_tariffario",
        r"^tariffario_personale_",
        route="/tariffario",
        component="TariffarioPage",
        api="/api/v1/ui/tariffario",
        persistence="tariffario tenant-aware",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("frontend/src/App.tsx", "isTariffarioPage"), ("frontend/src/components/TariffarioPage.tsx", "TariffarioPage")),
        tests=("tests/test_tariffario.py",),
    ),
    _contract(
        "strumenti_smart_card",
        r"^test_della_smart_card_",
        route="/impostazioni?tab=firma",
        component="ImpostazioniPage",
        api="Local Signer sul PC in uso",
        persistence="configurazione firma; il PIN non viene salvato",
        surface_pattern=r"^UserControlStrumenti$",
        code_checks=(("tools/local_signer.py", '"/firma"'), ("frontend/src/features/impostazioni/constants.ts", "Firma Digitale")),
        tests=("tests/test_local_signer.py",),
    ),
    _surface_contract(
        "notifiche_attestazione_conformita",
        r"^FormAttetazioniConformit",
        route="/notifiche-legali",
        component="NotificheLegaliPage",
        api="/api/v1/ui/notifiche-legali/bozze-attestazione",
        persistence="bozza e PDF nel fascicolo tenant-aware",
        code_checks=(("frontend/src/components/NotificheLegaliPage.tsx", "Attestazione di conformità.pdf"), ("frontend/src/notificheLegaliData.ts", "bozzaAttestazione")),
        tests=("tests/test_notifiche_legali_react.py",),
    ),
    _surface_contract(
        "filtri_elenco",
        r"^FormFilterComboDialog$",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli?f_*=",
        persistence="preferenze filtri tenant-aware",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "practiceFieldFilters"),),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _surface_contract(
        "editor_riferimenti_normativi",
        r"^FormRiferimentoNorme$",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="editor documento reale e ricerca normativa",
        persistence="contenuto del documento",
        code_checks=(("frontend/src/components/DocumentEditorPage.tsx", "insertLink"), ("frontend/src/components/LegalIntelligencePage.tsx", "Gazzetta Ufficiale")),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _surface_contract(
        "fascicoli_codice_oggetto_pst",
        r"^FormSearchCodiceOggetto$",
        route="/fascicoli/nuovo",
        component="CodiceOggettoPstSearch",
        api="/api/v1/ui/fascicoli/codici-oggetto",
        persistence="classificazione del fascicolo",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "CodiceOggettoPstSearch"), ("frontend/src/components/CodiceOggettoPstSearch.tsx", "Mostra tutti")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _surface_contract(
        "ricerca_studio_navigazione",
        r"^FormSearchInfo$",
        route="/global-search",
        component="RicercaStudioPage",
        api="/api/v1/ui/global-search",
        persistence="nessuna",
        code_checks=(("frontend/src/components/RicercaStudioPage.tsx", "RicercaStudioPage"),),
        tests=("tests/test_react_global_search_api.py",),
    ),
    _surface_contract(
        "redazione_verbale_campi",
        r"^FormVerbale$",
        route="/template-atti/editor",
        component="TemplateAttiPage",
        api="/template-atti/api/*",
        persistence="modello e campi del fascicolo",
        code_checks=(("frontend/src/components/TemplateAttiPage.tsx", "Campi variabili"),),
        tests=("tests/test_template_atti_react.py",),
    ),
    _surface_contract(
        "stato_operativo_globale",
        r"^InfragisticsStatusBar$",
        route="/",
        component="TopBar",
        api="/api/v1/ui/topbar/*",
        persistence="notifiche, timer e attività recenti tenant-aware",
        code_checks=(("frontend/src/components/layout/TopBar.tsx", "TopBarNotifications"), ("frontend/src/components/layout/TopBar.tsx", "TopBarTimeTracker")),
        tests=("tests/test_react_shell.py",),
    ),
    _surface_contract(
        "documenti_rotazione",
        r"^RotateForm$",
        route="/strumenti-documentali?modo=multipage",
        component="DocumentToolsPage",
        api="/api/v1/ui/document-tools/multipage",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        code_checks=(("frontend/src/components/DocumentToolsPage.tsx", "Ruota a destra"), ("web/services/document_tools.py", "rotations")),
        tests=("tests/test_document_tools.py",),
    ),
    _surface_contract(
        "editor_zoom",
        r"^ZoomForm$",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="controllo locale dell’editor",
        persistence="preferenza della sessione",
        code_checks=(("frontend/src/components/DocumentEditorPage.tsx", "setZoom"),),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _surface_contract(
        "documenti_ricampionamento",
        r"^ResampleForm$",
        route="/strumenti-documentali?modo=multipage",
        component="DocumentToolsPage",
        api="/api/v1/ui/document-tools/multipage",
        persistence="salvataggio esplicito nel fascicolo tenant-aware",
        code_checks=(("frontend/src/components/DocumentToolsPage.tsx", "__ricampionamento_immagine_da_completare__"),),
        tests=("tests/test_document_tools.py",),
    ),
    _surface_contract(
        "fascicoli_dati_immigrazione",
        r"^SchedaImmigrazione$",
        route="/fascicoli/:id",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli/:id",
        persistence="dati del fascicolo tenant-aware",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "__scheda_immigrazione_da_completare__"),),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _surface_contract(
        "importazione_stato_avanzamento",
        r"^SplashScreenQuickOrganizer$",
        route="/importa-pratiche",
        component="QuickOrganizerImportPage",
        api="/api/v1/ui/importa-pratiche/*",
        persistence="staging e import tenant-aware",
        code_checks=(("frontend/src/components/QuickOrganizerImportPage.tsx", "Progress"),),
        tests=("tests/test_quickorganizer_import.py",),
    ),
    _surface_contract(
        "importazione_pratiche_polisweb",
        r"^WizardImportaPraticheDaPolisWeb$",
        route="/importa-pratiche",
        component="QuickOrganizerImportPage",
        api="/api/v1/ui/importa-pratiche/*",
        persistence="fascicoli, soggetti e documenti tenant-aware",
        code_checks=(("frontend/src/components/QuickOrganizerImportPage.tsx", "QuickOrganizerImportPage"), ("web/services/quickorganizer_import.py", "import_quickorganizer_package")),
        tests=("tests/test_quickorganizer_import.py",),
    ),
    _surface_contract(
        "editor_cerca_sostituisci_dialogo",
        r"^frmFindReplace$",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="ricerca locale nel documento aperto",
        persistence="contenuto modificato solo dopo salvataggio",
        code_checks=(("frontend/src/components/DocumentEditorPage.tsx", "Cerca e sostituisci"), ("frontend/src/components/DocumentEditorPage.tsx", "replaceSelection")),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _surface_contract(
        "editor_vai_a",
        r"^GoToDialog$",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="navigazione locale nel documento aperto",
        persistence="nessuna",
        code_checks=(("frontend/src/components/DocumentEditorPage.tsx", "Cerca e sostituisci"),),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _surface_contract(
        "editor_collegamenti_dialogo",
        r"^InsertHyperlinkDialog$",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="editor documento reale",
        persistence="contenuto del documento",
        code_checks=(("frontend/src/components/DocumentEditorPage.tsx", "insertLink"),),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _surface_contract(
        "supporto_errori_telematici",
        r"^frmSoapError$",
        route="/supporto",
        component="VoceStudioControl",
        api="/api/v1/ui/supporto/*",
        persistence="diagnostica redatta e audit tenant-aware",
        code_checks=(("web/services/support_runtime.py", "supporto_remoto"),),
        tests=("tests/test_support_remote.py",),
    ),
    _surface_contract(
        "editor_comandi_da_completare",
        r"^(?:QuickWordMain|FormInsertBreak|OtherSymbolsDialog|FrmMaxRowsPreview)$",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="editor documento reale",
        persistence="documento del fascicolo",
        code_checks=(("frontend/src/components/DocumentEditorPage.tsx", "__parita_editor_completa__"),),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "polisweb_consultazione",
        r"(?:agenda_polisweb|fascicolo_telematico|fascicolo_ufficio|consultazione_fascicoli_cassazione|ricerca_rg|archivio_giurisprudenza_nazionale|notifiche_non_perfezionate)",
        route="/polisweb",
        component="TelematicoPage",
        api="/api/v1/ui/telematico",
        persistence="consultazioni e fascicoli acquisiti tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/TelematicoPage.tsx", "TelematicoPage"), ("web/services/react_telematico_bridge.py", "build_react_telematico_payload")),
        tests=("tests/test_polisweb.py", "tests/test_react_telematico_api.py"),
    ),
    _contract(
        "polisweb_acquisizione",
        r"(?:cerca_eventi_polisweb|scarica_documenti_polisweb|scarica_udienze_scadenze_polisweb|importa_pratiche_polisweb|sincronizza_fascicolo_ufficio|acquisisci_verbale_udienza)",
        route="/portali/pst/acquisizione",
        component="TelematicoSurfacePage",
        api="/portali/pst/acquisizione/*",
        persistence="documenti, eventi e fascicoli tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/App.tsx", "isTelematicoSurfacePage"), ("web/bootstrap/portali_acquisizione_routes.py", "register_portali_acquisizione_routes")),
        tests=("tests/test_polisweb.py",),
    ),
    _contract(
        "registri_pec_pubblici",
        r"(?:registroindirizzielettronici|registropubblicheamministrazioni|registro_imprese|pec_pubbliche_amministrazioni)",
        route="/tribunali",
        component="StudioModulePage",
        api="/api/v1/ui/uffici",
        persistence="cataloghi locali versionati",
        surface_pattern=r"^FormMain$",
        code_checks=(("web/services/react_telematico_bridge.py", "build_react_tribunali_payload"), ("pct/uffici_competenti.py", "PEC_TERRITORIO_DATA")),
        tests=("tests/test_uffici_competenti.py",),
    ),
    _contract(
        "depositi_telematici_canali",
        r"(?:depositi_telematici_amministrativi|depositi_telematici_penali|depositi_telematici_tributari|portale_amministrativo_telematico|portale_depositoattipenali|portale_tributario_telematico|esportafileper_deposito|esportatileper_processotributario|atto_enc_esterno)",
        route="/telematico",
        component="TelematicoPage",
        api="/api/v1/ui/telematico",
        persistence="pacchetti e ricevute tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/TelematicoPage.tsx", "TelematicoPage"), ("frontend/src/telematicoData.ts", "channels")),
        tests=("tests/test_react_telematico_api.py",),
    ),
    _contract(
        "unep_menu_richieste",
        r"(?:atto_civile|atto_penale|richiesta_pignoramento|pagamento_richiesta_notifica|richiesta_restituzione_somme|richiesta_ricerca_beni|notificheedaltrerichiesteunep)",
        route="/telematico/unep",
        component="FascicoloDepositoPage",
        api="/fascicoli/:id/deposito/*",
        persistence="richiesta UNEP e DatiAtto.xml",
        surface_pattern=r"^FormMain$",
        code_checks=(("pct/datiatto_unep.py", "build_unep_datiatto"), ("frontend/src/components/FascicoloDepositoPage.tsx", "UNEP")),
        tests=("tests/test_datiatto_unep.py",),
    ),
    _contract(
        "fatturazione_menu",
        r"(?:fattura|parcella|notaspese|nota_credito|notacredito|preavviso|preventivo|contabilita|volumeaffari|recupera_voci|tariffario_personale|prestazioni)",
        route="/fatturazione",
        component="FatturazionePage",
        api="/api/v1/ui/fatturazione",
        persistence="documenti contabili e movimenti tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/FatturazionePage.tsx", "FatturazionePage"), ("frontend/src/components/TariffarioPage.tsx", "TariffarioPage")),
        tests=("tests/test_fatturazione.py",),
    ),
    _contract(
        "movimenti_menu",
        r"(?:movimentazioni|entrat|uscit|prima_nota|incassi|cassa)",
        route="/incassi-pagamenti",
        component="IncassiPagamentiPage",
        api="/api/v1/ui/incassi-pagamenti",
        persistence="movimenti tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/IncassiPagamentiPage.tsx", "IncassiPagamentiPage"),),
        tests=("tests/test_incassi_pagamenti.py",),
    ),
    _contract(
        "email_menu",
        r"(?:email|connetti_and_ricevi|posta_in_arrivo|posta_inviata|richiamaemaildalcestino|segna_comenonletta)",
        route="/email",
        component="EmailPecPage",
        api="/api/v1/ui/email",
        persistence="messaggi tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/EmailPecPage.tsx", "EmailPecPage"),),
        tests=("tests/test_react_email_api.py",),
    ),
    _contract(
        "agenda_menu",
        r"(?:agenda|udienza|adempimento|appuntamento|memorandum|scadenza|allarme|timeline|colore_)",
        route="/agenda",
        component="AgendaPage",
        api="/api/v1/ui/agenda",
        persistence="agenda e preferenze tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/AgendaPage.tsx", "AgendaPage"),),
        tests=("tests/test_agenda.py",),
    ),
    _contract(
        "fascicoli_menu",
        r"(?:pratica|rubrica|cliente|controparte|faldon|grupp|schedario|appunti)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="fascicoli, soggetti e gruppi tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "FascicoliPage"),),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "documenti_menu",
        r"(?:videoscrittura|quick_word|document|apricon|formulario|esporta_formato|invia_formato|scanner)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="/api/v1/ui/editor-professionale",
        persistence="documenti tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/EditorProfessionalePage.tsx", "EditorProfessionalePage"),),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "impostazioni_menu",
        r"(?:configurazione|settings|anagrafica_utente|privacy|backup|restore|compattazione|databasepath|google_calendar|testsmartcard|colore_programma|scelta_wordprocessor|aggiorna_servizi_telematici)",
        route="/impostazioni",
        component="ImpostazioniPage",
        api="/api/v1/ui/impostazioni",
        persistence="preferenze e configurazioni tenant-aware",
        surface_pattern=r"^FormMain$",
        code_checks=(("frontend/src/components/ImpostazioniPage.tsx", "ImpostazioniPage"),),
        tests=("tests/test_react_impostazioni_api.py",),
    ),
    _surface_contract(
        "comandi_principali_da_completare",
        r"^FormMain$",
        route="/",
        component="App",
        api="da verificare comando per comando",
        persistence="da verificare comando per comando",
        code_checks=(("frontend/src/App.tsx", "__parita_form_main_completa__"),),
        tests=("tests/test_functional_parity_audit.py",),
    ),
)


def _entry_text(row: dict[str, Any]) -> str:
    # Il percorso del menu e' contesto, non identita' funzionale: usarlo qui
    # promuoverebbe ogni azione figlia al contratto del contenitore padre.
    parts = [
        row.get("key"),
        row.get("caption"),
        row.get("variable"),
        row.get("handler"),
    ]
    normalized = _normalize(" ".join(str(part or "") for part in parts))
    return normalized or _normalize(
        row.get("surface_path_label") or row.get("surface") or ""
    )


def _code_check(path_value: str, expected: str) -> dict[str, Any]:
    path = ROOT / path_value
    if path.is_dir():
        return {"file": path_value, "expected": expected, "ok": True}
    source = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {"file": path_value, "expected": expected, "ok": bool(source and (not expected or expected in source))}


def _entry_id(row: dict[str, Any], kind: str) -> str:
    source = "|".join(
        str(value or "")
        for value in (
            kind,
            row.get("source_file"),
            row.get("surface_path_label"),
            row.get("key") or row.get("variable"),
            row.get("event"),
            row.get("handler"),
        )
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]


def _canonical_id(normalized: str, kind: str) -> str:
    """Identifica l'azione logica senza contare piu' volte i percorsi duplicati."""
    source = f"{kind}|{normalized}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]


def _contract_matches(contract: dict[str, Any], row: dict[str, Any], kind: str, normalized: str) -> bool:
    if contract["kind"] and contract["kind"] != kind:
        return False
    surface_pattern = contract["surface_pattern"]
    if surface_pattern is not None and not surface_pattern.search(str(row.get("surface") or "")):
        return False
    source_path_pattern = contract["source_path_pattern"]
    if source_path_pattern is not None and not source_path_pattern.search(_normalize(row.get("surface_path_label") or "")):
        return False
    return bool(contract["pattern"].search(normalized))


def _map_entry(row: dict[str, Any], kind: str, real_proofs: dict[str, Any]) -> dict[str, Any]:
    normalized = _entry_text(row)
    contract = next((item for item in CONTRACTS if _contract_matches(item, row, kind, normalized)), None)
    result = {
        "id": _entry_id(row, kind),
        "canonical_id": _canonical_id(normalized, kind),
        "kind": kind,
        "surface": row.get("surface", ""),
        "source_file": row.get("source_file", ""),
        "source_path": row.get("surface_path_label", ""),
        "source_key": row.get("key") or row.get("variable") or "",
        "source_event": row.get("event", ""),
        "source_handler": row.get("handler", ""),
        "normalized": normalized,
        "capability_id": "",
        "status": "da_mappare",
        "route": "",
        "component": "",
        "api": "",
        "persistence": "",
        "tests": [],
        "code_checks": [],
        "real_proof": [],
    }
    if contract is None:
        return result
    checks = [_code_check(path, expected) for path, expected in contract["code_checks"]]
    proof = real_proofs.get(contract["id"], {})
    evidence = proof.get("evidence", []) if isinstance(proof, dict) else []
    verified = bool(proof.get("status") == "verificata" and evidence and all(check["ok"] for check in checks))
    result.update(
        {
            "capability_id": contract["id"],
            "status": "verificata" if verified else "presente_da_provare" if all(check["ok"] for check in checks) else "parziale",
            "route": contract["route"],
            "component": contract["component"],
            "api": contract["api"],
            "persistence": contract["persistence"],
            "tests": contract["tests"],
            "code_checks": checks,
            "real_proof": evidence if verified else [],
        }
    )
    return result


def build_audit(inventory_path: Path, real_proofs_path: Path = DEFAULT_REAL_PROOFS) -> dict[str, Any]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    real_proofs_payload = json.loads(real_proofs_path.read_text(encoding="utf-8")) if real_proofs_path.is_file() else {}
    real_proofs = real_proofs_payload.get("capabilities", {}) if isinstance(real_proofs_payload, dict) else {}
    entries = [
        *(_map_entry(row, "menu_action", real_proofs) for row in inventory.get("action_paths", [])),
        *(_map_entry(row, "interactive_control", real_proofs) for row in inventory.get("interactive_controls", [])),
    ]
    statuses = Counter(str(row["status"]) for row in entries)
    capabilities = Counter(str(row["capability_id"]) for row in entries if row["capability_id"])
    canonical_groups: dict[str, list[dict[str, Any]]] = {}
    for row in entries:
        canonical_groups.setdefault(str(row["canonical_id"]), []).append(row)
    status_priority = {"da_mappare": 0, "parziale": 1, "presente_da_provare": 2, "verificata": 3}
    canonical_statuses = Counter(
        min(
            (str(row["status"]) for row in rows),
            key=lambda status: status_priority[status],
        )
        for rows in canonical_groups.values()
    )
    for rows in canonical_groups.values():
        duplicate_count = len(rows)
        for row in rows:
            row["source_path_count"] = duplicate_count
    return {
        "schema_version": 3,
        "generated_at": datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
        "inventory": {
            "path": str(inventory_path),
            "sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            "functional_entries": int(inventory.get("counts", {}).get("functional_entries", 0)),
        },
        "real_proofs": {
            "path": str(real_proofs_path),
            "sha256": hashlib.sha256(real_proofs_path.read_bytes()).hexdigest() if real_proofs_path.is_file() else "",
        },
        "counts": {
            "functional_entries": len(entries),
            "unique_source_actions": len(canonical_groups),
            "duplicate_source_paths": len(entries) - len(canonical_groups),
            "mapped_entries": len(entries) - statuses.get("da_mappare", 0),
            "verified_entries": statuses.get("verificata", 0),
            "present_to_test_entries": statuses.get("presente_da_provare", 0),
            "partial_entries": statuses.get("parziale", 0),
            "unmapped_entries": statuses.get("da_mappare", 0),
            "capability_contracts": len(CONTRACTS),
            "capabilities_detected": len(capabilities),
        },
        "status_counts": dict(sorted(statuses.items())),
        "unique_status_counts": dict(sorted(canonical_statuses.items())),
        "capability_counts": dict(sorted(capabilities.items())),
        "entries": entries,
        "policy": {
            "verified_rule": "Una funzione e' verificata solo con contratto puntuale, controlli codice, test e prova materiale sulla copia reale.",
            "current_state": "Le sole voci verificate sono collegate a una prova materiale registrata sulla copia reale.",
        },
    }


def _markdown(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    lines = [
        "# Matrice di parità funzionale",
        "",
        f"Generata: {audit['generated_at']} (Europe/Rome).",
        "",
        "## Stato",
        "",
        f"- Voci censite: {counts['functional_entries']}",
        f"- Azioni sorgente uniche: {counts['unique_source_actions']}",
        f"- Percorsi duplicati conservati come prova: {counts['duplicate_source_paths']}",
        f"- Voci con contratto puntuale: {counts['mapped_entries']}",
        f"- Presenti da provare sulla copia reale: {counts['present_to_test_entries']}",
        f"- Parziali: {counts['partial_entries']}",
        f"- Da mappare: {counts['unmapped_entries']}",
        f"- Verificate materialmente: {counts['verified_entries']}",
        "",
        "Nessuna voce viene considerata equivalente sulla sola base di una categoria o di una pagina affine.",
        "",
        "## Contratti rilevati",
        "",
    ]
    for capability, total in audit["capability_counts"].items():
        lines.append(f"- `{capability}`: {total} percorsi")
    verified = sorted({row["capability_id"] for row in audit["entries"] if row["status"] == "verificata"})
    lines.extend(["", "## Funzioni verificate materialmente", ""])
    if verified:
        lines.extend(f"- `{capability}`" for capability in verified)
    else:
        lines.append("- Nessuna")
    lines.extend(["", "## Voci ancora da mappare", ""])
    unmapped_by_action: dict[str, dict[str, Any]] = {}
    for row in audit["entries"]:
        if row["status"] == "da_mappare":
            unmapped_by_action.setdefault(row["canonical_id"], row)
    unmapped = sorted(unmapped_by_action.values(), key=lambda row: (row["surface"], row["source_path"]))
    for row in unmapped:
        lines.append(f"- `{row['id']}`: {row['source_path']}")
    lines.extend(["", "## Regola di chiusura", "", audit["policy"]["verified_rule"], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce la matrice puntuale delle funzioni")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--real-proofs", type=Path, default=DEFAULT_REAL_PROOFS)
    args = parser.parse_args()
    audit = build_audit(args.inventory, args.real_proofs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(_markdown(audit), encoding="utf-8")
    print(json.dumps(audit["counts"], ensure_ascii=False))
    return 0 if audit["counts"]["functional_entries"] == audit["inventory"]["functional_entries"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

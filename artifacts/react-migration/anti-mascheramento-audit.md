# Audit anti-mascheramento React

Generato: 2026-05-09T17:12:51.475Z

## Regole operative Parte 12A

- `react_operational_full` richiede pagina React, dati JSON, azioni principali JSON, CSRF/sessione/permessi, stati loading/error/success e nessuna CTA primaria legacy.
- `react_bridge` identifica superfici React con lettura reale ma scritture, dettagli o CTA principali ancora legacy.
- `react_shell` identifica superfici solo riepilogative o di navigazione, senza flusso operativo completo.
- `legacy_operational` resta il livello corretto quando il template Flask e il POST storico sono ancora il prodotto reale.
- `react_full` e deprecato: non va usato per pagine che delegano il flusso principale al legacy.

## Sintesi

- Route censite: 84
- Link `?_legacy=1`: 73
- LegacyPostForm: 0
- Form POST HTML React: 0
- Bridge con scritture legacy: 0
- Status react_full deprecati: 0
- API JSON di salvataggio mancanti: 2

## Tabella route

| route | componente | data client | bridge | stato manifest | link legacy presenti | form legacy presenti | scritture JSON presenti | problemi | livello reale |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| / | frontend/src/App.tsx | frontend/src/data.ts | web/services/react_dashboard_cache.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /admin/database | frontend/src/components/AdminDatabasePage.tsx | frontend/src/adminDatabaseData.ts | web/services/react_admin_database_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /agenda | frontend/src/components/AgendaPage.tsx | frontend/src/agendaData.ts | web/services/react_agenda_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /agenda/nuovo | frontend/src/components/NuovoAppuntamentoPage.tsx | frontend/src/agendaData.ts | web/services/react_agenda_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /amministrazione | frontend/src/components/AmministrazionePage.tsx | frontend/src/amministrazioneData.ts | web/services/react_amministrazione_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /audit | frontend/src/components/AuditPage.tsx | frontend/src/auditData.ts | web/services/react_audit_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /backup | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /cartelle-condivise | frontend/src/components/CartelleCondivisePage.tsx | frontend/src/cartelleCondiviseData.ts | web/services/react_condivisioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /checklist | frontend/src/components/ChecklistPage.tsx | frontend/src/checklistData.ts | web/services/react_checklist_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /clienti | frontend/src/components/AnagraficaClientiPage.tsx | frontend/src/clientiData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /clienti/nuovo | frontend/src/components/NuovoClientePage.tsx | frontend/src/clientiNuovoData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /compensi-forensi | frontend/src/components/CompensiForensiPage.tsx | frontend/src/compensiForensiData.ts | web/services/react_compensi_forensi_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /compensi-forensi/* | frontend/src/components/CompensiForensiPage.tsx | frontend/src/compensiForensiData.ts | web/services/react_compensi_forensi_bridge.py | legacy_operational | 2 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /deposito/checklist | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /email | frontend/src/components/EmailPecPage.tsx | frontend/src/emailData.ts | web/services/react_email_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /email-ordinaria | frontend/src/components/EmailPecPage.tsx | frontend/src/emailData.ts | web/services/react_email_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /fascicoli | frontend/src/components/FascicoliPage.tsx | frontend/src/fascicoliData.ts | web/services/react_fascicoli_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fascicoli/archivio | frontend/src/components/FascicoliPage.tsx | frontend/src/fascicoliData.ts | web/services/react_fascicoli_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fascicoli/nuovo | frontend/src/components/FascicoliPage.tsx | frontend/src/fascicoliData.ts | web/services/react_fascicoli_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fatturazione | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /fatturazione/* | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | legacy_operational | 5 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /fatturazione/nuova | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /giurisprudenza | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /giurisprudenza/* | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | legacy_operational | 0 | 0 | no | gestione successo non rilevata | legacy_operational |
| /giurisprudenza/nuova | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | legacy_operational | 0 | 0 | no | API JSON di salvataggio mancante; gestione successo non rilevata | legacy_operational |
| /global-search | frontend/src/components/RicercaStudioPage.tsx | frontend/src/searchData.ts | web/blueprints/global_search.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /impostazioni | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni-studio | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni/calendario | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni/pagamenti | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /incassi-pagamenti | frontend/src/components/IncassiPagamentiPage.tsx | frontend/src/incassiPagamentiData.ts | web/services/react_incassi_pagamenti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /legal-intelligence | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /legal-intelligence/* | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | legacy_operational | 0 | 0 | no | gestione successo non rilevata | legacy_operational |
| /legal-intelligence/mediazione | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /legal-intelligence/news | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /messaggi | frontend/src/components/MessaggiPage.tsx | frontend/src/messaggiData.ts | web/services/react_messaggi_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /messaggi/nuovo | frontend/src/components/MessaggiPage.tsx | frontend/src/messaggiData.ts | web/services/react_messaggi_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /notifiche | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /notifiche-whatsapp | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /pat | frontend/src/components/PatPage.tsx | frontend/src/patData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /pdp | frontend/src/components/PdpPage.tsx | frontend/src/pdpData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /polisWeb | frontend/src/components/PolisWebPage.tsx | frontend/src/polisWebData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /portali/* | frontend/src/components/PortaliPage.tsx | frontend/src/portaliData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /preventivi | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/* | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | legacy_operational | 8 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /preventivi/conferimento/nuovo | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/nuovo | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/wizard | frontend/src/components/PreventivoWizardPage.tsx | frontend/src/preventivoWizardData.ts | web/services/react_preventivo_wizard_bridge.py | react_operational_partial | 4 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /privacy/registro | frontend/src/components/PrivacyRegistroPage.tsx | frontend/src/privacyRegistroData.ts | web/services/react_privacy_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /privacy/registro/nuovo | frontend/src/components/PrivacyRegistroPage.tsx | frontend/src/privacyRegistroData.ts | web/services/react_privacy_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /profili | frontend/src/components/ProfiliPage.tsx | frontend/src/profiliData.ts | web/services/react_profili_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /redazione-atti | frontend/src/components/RedazioneAttiPage.tsx | frontend/src/redazioneAttiData.ts | web/services/react_redazione_atti_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /redazione-atti/* | frontend/src/components/RedazioneAttiPage.tsx | frontend/src/redazioneAttiData.ts | web/services/react_redazione_atti_bridge.py | legacy_operational | 0 | 0 | no | gestione successo non rilevata | legacy_operational |
| /regia-operativa | frontend/src/App.tsx | frontend/src/data.ts | web/services/react_dashboard_cache.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /registro-attivita | frontend/src/components/AuditPage.tsx | frontend/src/auditData.ts | web/services/react_audit_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /registro-gdpr | frontend/src/components/PrivacyRegistroPage.tsx | frontend/src/privacyRegistroData.ts | web/services/react_privacy_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /ricerca-legale | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /ricerca-legale/* | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | legacy_operational | 0 | 0 | no | gestione successo non rilevata | legacy_operational |
| /ricerca-studio | frontend/src/components/RicercaStudioPage.tsx | frontend/src/searchData.ts | web/blueprints/global_search.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /scadenziario | frontend/src/components/ScadenziarioPage.tsx | frontend/src/scadenziarioData.ts | web/services/react_scadenziario_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /scadenziario/nuova | frontend/src/components/NuovaScadenzaPage.tsx | frontend/src/scadenziarioData.ts | web/services/react_scadenziario_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /sigit | frontend/src/components/SigitPage.tsx | frontend/src/sigitData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /sigp | frontend/src/components/SigpPage.tsx | frontend/src/sigpData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /sincronizzazione-calendari | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /sito-studio | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /sito-studio/builder | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | legacy_operational | 2 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /sito-studio/contatti | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /soggetti | frontend/src/components/SoggettiPage.tsx | frontend/src/soggettiData.ts | web/services/react_soggetti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /soggetti/nuovo | frontend/src/components/NuovoClientePage.tsx | frontend/src/clientiNuovoData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /statistiche | frontend/src/components/StatistichePage.tsx | frontend/src/statisticheData.ts | web/services/react_statistiche_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /strumenti-legali | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /strumenti-operativi | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /studio | frontend/src/components/StudioPage.tsx | frontend/src/studioData.ts | web/services/react_studio_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /tariffario | frontend/src/components/TariffarioPage.tsx | frontend/src/tariffarioData.ts | web/services/react_tariffario_bridge.py | react_operational_full | 3 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /tariffario/* | frontend/src/components/TariffarioPage.tsx | frontend/src/tariffarioData.ts | web/services/react_tariffario_bridge.py | legacy_operational | 3 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /template-atti | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /template-atti/* | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | legacy_operational | 0 | 0 | no | gestione successo non rilevata | legacy_operational |
| /template-atti/catalogo | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /template-atti/nuovo | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | legacy_operational | 0 | 0 | no | API JSON di salvataggio mancante; gestione successo non rilevata | legacy_operational |
| /timesheet | frontend/src/components/TimesheetPage.tsx | frontend/src/timesheetData.ts | web/services/react_timesheet_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /utenti | frontend/src/components/UtentiPage.tsx | frontend/src/utentiData.ts | web/services/react_utenti_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /utenti/nuovo | frontend/src/components/UtentiPage.tsx | frontend/src/utentiData.ts | web/services/react_utenti_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /wizard-pro | frontend/src/components/WizardProPage.tsx | frontend/src/wizardProData.ts | web/services/react_wizard_pro_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /workspace-intelligente | frontend/src/App.tsx | frontend/src/data.ts | web/services/react_dashboard_cache.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |

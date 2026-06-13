# Audit anti-mascheramento React

Generato: 2026-06-02T14:15:11.421Z

## Aggiornamento assistente vocale Studio 2.253.1 - 2026-06-12

Il pannello vocale non è un mascheramento UI: i comandi di navigazione puntano a
rotte reali, la ricerca compone `/global-search?q=...`, Lex usa l'evento
applicativo corrente e il nuovo cliente guidato salva via API React reale con
permesso `clienti.scrivi`, audit, sincronizzazione e validazioni dominio.
Restano da registrare le prove browser su Docker reale prima della chiusura.

## Aggiornamento Template Atti 2.249.15 - 2026-06-04

La superficie `/template-atti/compila/<codice>` resta governata come React
operational effettiva: il giro finale ha verificato che le azioni richieste non
siano solo pulsanti visibili. Toolbar selezione, collegamento cliente/fascicolo,
timbro, import, export, copia, salvataggio, compilazione multipla, firma e Lex
diff producono effetti osservabili nel browser reale.

Prova registrata: `template-editor-browser-2.249.15.json`, 74/74 controlli OK su
Docker reale `127.0.0.1:8080`, più Browser integrato Codex con nessun overflow
pagina/pannello/card e toolbar sticky.

## Aggiornamento Template Atti 2.249.14 - 2026-06-04

La superficie `/template-atti/compila/<codice>` resta censita come React
operational, ma la regressione corretta in 2.249.14 chiarisce il requisito:
non è sufficiente mostrare campi e toolbar. Il fascicolo deve alimentare davvero
cliente/mittente, controparte/destinatario, ufficio giudiziario, R.G., materia e
dati pratica; cambio modello, Guida Pratica, font, allineamenti, Lex, import,
compilazione multipla, export e firma devono produrre effetti osservabili nel
browser reale.

Prova registrata: `template-editor-browser-2.249.14.json`, 73/73 controlli OK su
Docker reale `127.0.0.1:8080`, senza fallback demo, senza CTA legacy primaria e
senza modifiche Lex automatiche non accettate.

## Regole operative Parte 12A

- `react_operational_full` richiede pagina React, dati JSON, azioni principali JSON, CSRF/sessione/permessi, stati loading/error/success e nessuna CTA primaria legacy.
- `react_bridge` identifica superfici React con lettura reale ma scritture, dettagli o CTA principali ancora legacy.
- `react_shell` identifica superfici solo riepilogative o di navigazione, senza flusso operativo completo.
- `legacy_operational` resta il livello corretto quando il template Flask e il POST storico sono ancora il prodotto reale.
- `react_full` e deprecato: non va usato per pagine che delegano il flusso principale al legacy.

## Sintesi

- Route censite: 109
- Link `?_legacy=1`: 86
- LegacyPostForm: 0
- Form POST HTML React: 0
- Bridge con scritture legacy: 0
- Status react_full deprecati: 0
- API JSON di salvataggio mancanti: 0

## Tabella route

| route | componente | data client | bridge | stato manifest | link legacy presenti | form legacy presenti | scritture JSON presenti | problemi | livello reale |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| / | frontend/src/App.tsx | frontend/src/data.ts | web/services/react_dashboard_cache.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /admin/database | frontend/src/components/AdminDatabasePage.tsx | frontend/src/adminDatabaseData.ts | web/services/react_admin_database_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /importa-pratiche-studio-telematico | frontend/src/components/QuickOrganizerImportPage.tsx | frontend/src/quickOrganizerImportData.ts | web/services/quickorganizer_import.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /agenda | frontend/src/components/AgendaPage.tsx | frontend/src/agendaData.ts | web/services/react_agenda_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /agenda/nuovo | frontend/src/components/NuovoAppuntamentoPage.tsx | frontend/src/agendaData.ts | web/services/react_agenda_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /agenda/importa | frontend/src/components/AgendaImportPage.tsx | frontend/src/agendaData.ts | web/bootstrap/dashboard_routes.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /amministrazione | frontend/src/components/AmministrazionePage.tsx | frontend/src/amministrazioneData.ts | web/services/react_amministrazione_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /audit | frontend/src/components/AuditPage.tsx | frontend/src/auditData.ts | web/services/react_audit_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /backup | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /cartelle-condivise | frontend/src/components/CartelleCondivisePage.tsx | frontend/src/cartelleCondiviseData.ts | web/services/react_condivisioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /checklist | frontend/src/components/ChecklistPage.tsx | frontend/src/checklistData.ts | web/services/react_checklist_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /clienti | frontend/src/components/AnagraficaClientiPage.tsx | frontend/src/clientiData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /clienti/:id/cartella | frontend/src/components/CartellaClientePage.tsx | frontend/src/clientiCartellaData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /clienti/nuovo | frontend/src/components/NuovoClientePage.tsx | frontend/src/clientiNuovoData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /compensi-forensi | frontend/src/components/CompensiForensiPage.tsx | frontend/src/compensiForensiData.ts | web/services/react_compensi_forensi_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /documenti | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /compensi-forensi/* | frontend/src/components/CompensiForensiPage.tsx | frontend/src/compensiForensiData.ts | web/services/react_compensi_forensi_bridge.py | legacy_operational | 2 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /deposito/checklist | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /email | frontend/src/components/EmailPecPage.tsx | frontend/src/emailData.ts | web/services/react_email_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /email-ordinaria | frontend/src/components/EmailPecPage.tsx | frontend/src/emailData.ts | web/services/react_email_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /notifiche-legali | frontend/src/components/NotificheLegaliPage.tsx | frontend/src/notificheLegaliData.ts | web/services/react_notifiche_legali_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fascicoli | frontend/src/components/FascicoliPage.tsx | frontend/src/fascicoliData.ts | web/services/react_fascicoli_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fascicoli/archivio | frontend/src/components/FascicoliPage.tsx | frontend/src/fascicoliData.ts | web/services/react_fascicoli_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fascicoli/nuovo | frontend/src/components/FascicoliPage.tsx | frontend/src/fascicoliData.ts | web/services/react_fascicoli_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /fatturazione | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /fatturazione/* | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | legacy_operational | 5 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /fatturazione/nuova | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /giurisprudenza | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /giurisprudenza/* | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | legacy_operational | 0 | 0 | si | nessuno | legacy_operational |
| /giurisprudenza/nuova | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /global-search | frontend/src/components/RicercaStudioPage.tsx | frontend/src/searchData.ts | web/blueprints/global_search.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /impostazioni | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni-studio | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni/calendario | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni/pagamenti | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /impostazioni/sdi | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /incassi-pagamenti | frontend/src/components/IncassiPagamentiPage.tsx | frontend/src/incassiPagamentiData.ts | web/services/react_incassi_pagamenti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /legal-intelligence | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /legal-intelligence/* | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /legal-intelligence/mediazione | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /legal-intelligence/news | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /messaggi | frontend/src/components/MessaggiPage.tsx | frontend/src/messaggiData.ts | web/services/react_messaggi_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /messaggi/nuovo | frontend/src/components/MessaggiPage.tsx | frontend/src/messaggiData.ts | web/services/react_messaggi_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /notifiche | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /notifiche-whatsapp | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /pat | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /pdp | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /polisWeb | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /portali/pst/acquisizione | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /portali/pdp/acquisizione | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /portali/pat/acquisizione | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /portali/ptt/acquisizione | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /portali/sigit/acquisizione | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /portali/* | frontend/src/components/PortaliPage.tsx | frontend/src/portaliData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /telematico | frontend/src/components/TelematicoPage.tsx | frontend/src/telematicoData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /servizi-telematici | frontend/src/components/TelematicoPage.tsx | frontend/src/telematicoData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /sigp-sync | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /tribunali | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /guida/firma-digitale | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /admin/osservabilita | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /database | frontend/src/components/AdminDatabasePage.tsx | frontend/src/adminDatabaseData.ts | web/services/react_admin_database_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /applicazioni | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /preventivi | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/* | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | legacy_operational | 8 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /preventivi/conferimento/nuovo | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/conferimento/:id | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/nuovo | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/wizard | frontend/src/components/PreventivoWizardPage.tsx | frontend/src/preventivoWizardData.ts | web/services/react_preventivo_wizard_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /privacy/registro | frontend/src/components/PrivacyRegistroPage.tsx | frontend/src/privacyRegistroData.ts | web/services/react_privacy_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /privacy/registro/nuovo | frontend/src/components/PrivacyRegistroPage.tsx | frontend/src/privacyRegistroData.ts | web/services/react_privacy_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /profilo | frontend/src/components/ProfiloPage.tsx | web/blueprints/api_v1_react.py | web/bootstrap/auth_management_routes.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /profili | frontend/src/components/ProfiliPage.tsx | frontend/src/profiliData.ts | web/services/react_profili_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /redazione-atti | frontend/src/components/RedazioneAttiPage.tsx | frontend/src/redazioneAttiData.ts | web/services/react_redazione_atti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /redazione-atti/* | frontend/src/components/RedazioneAttiPage.tsx | frontend/src/redazioneAttiData.ts | web/services/react_redazione_atti_bridge.py | legacy_operational | 0 | 0 | si | nessuno | legacy_operational |
| /regia-operativa | frontend/src/App.tsx | frontend/src/data.ts | web/services/react_dashboard_cache.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /registro-attivita | frontend/src/components/AuditPage.tsx | frontend/src/auditData.ts | web/services/react_audit_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /registro-gdpr | frontend/src/components/PrivacyRegistroPage.tsx | frontend/src/privacyRegistroData.ts | web/services/react_privacy_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /ricerca-legale | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /ricerca-legale/* | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /ricerca-studio | frontend/src/components/RicercaStudioPage.tsx | frontend/src/searchData.ts | web/blueprints/global_search.py | react_operational_full | 0 | 0 | no | gestione successo non rilevata | react_operational_full |
| /scadenziario | frontend/src/components/ScadenziarioPage.tsx | frontend/src/scadenziarioData.ts | web/services/react_scadenziario_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /scadenziario/nuova | frontend/src/components/NuovaScadenzaPage.tsx | frontend/src/scadenziarioData.ts | web/services/react_scadenziario_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /scadenziario/:id | frontend/src/components/ScadenziarioPage.tsx | frontend/src/scadenziarioData.ts | web/services/react_scadenziario_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /scadenziario/:id/modifica | frontend/src/components/NuovaScadenzaPage.tsx | frontend/src/scadenziarioData.ts | web/services/react_scadenziario_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /sigit | frontend/src/components/TelematicoSurfacePage.tsx | frontend/src/telematicoSurfacesData.ts | web/services/react_telematico_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /sigp | frontend/src/components/SigpPage.tsx | frontend/src/sigpData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /sincronizzazione-calendari | frontend/src/features/impostazioni/ImpostazioniPage.tsx | frontend/src/features/impostazioni/api.ts | web/services/react_impostazioni_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /sito-studio | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /sito-studio/builder | frontend/src/components/SitoStudioBuilderPage.tsx | frontend/src/sitoStudioBuilderData.ts | web/services/react_sito_studio_builder_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /sito-studio/redazione-ai | frontend/src/components/SitoStudioRedazioneAiPage.tsx | frontend/src/sitoStudioAiData.ts | web/services/react_sito_studio_ai_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /sito-studio/articoli/:id/modifica | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /sito-studio/contatti | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /soggetti | frontend/src/components/SoggettiPage.tsx | frontend/src/soggettiData.ts | web/services/react_soggetti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /soggetti/nuovo | frontend/src/components/NuovoClientePage.tsx | frontend/src/clientiNuovoData.ts | web/services/react_clienti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /statistiche | frontend/src/components/StatistichePage.tsx | frontend/src/statisticheData.ts | web/services/react_statistiche_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /strumenti-legali | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /strumenti-operativi | frontend/src/components/StudioModulePage.tsx | frontend/src/studioModuleData.ts | web/services/react_studio_module_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /studio | frontend/src/components/StudioPage.tsx | frontend/src/studioData.ts | web/services/react_studio_bridge.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |
| /tariffario | frontend/src/components/TariffarioPage.tsx | frontend/src/tariffarioData.ts | web/services/react_tariffario_bridge.py | react_operational_full | 3 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /tariffario/* | frontend/src/components/TariffarioPage.tsx | frontend/src/tariffarioData.ts | web/services/react_tariffario_bridge.py | legacy_operational | 3 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /template-atti | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /template-atti/* | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | legacy_operational | 0 | 0 | si | nessuno | legacy_operational |
| /template-atti/catalogo | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /template-atti/nuovo | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | legacy_operational | 0 | 0 | si | nessuno | legacy_operational |
| /timesheet | frontend/src/components/TimesheetPage.tsx | frontend/src/timesheetData.ts | web/services/react_timesheet_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /utenti | frontend/src/components/UtentiPage.tsx | frontend/src/utentiData.ts | web/services/react_utenti_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /utenti/nuovo | frontend/src/components/UtentiPage.tsx | frontend/src/utentiData.ts | web/services/react_utenti_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /wizard-pro | frontend/src/components/WizardProPage.tsx | frontend/src/wizardProData.ts | web/services/react_wizard_pro_bridge.py | react_operational_full | 0 | 0 | si | nessuno | react_operational_full |
| /workspace-intelligente | frontend/src/App.tsx | frontend/src/data.ts | web/services/react_dashboard_cache.py | react_operational_full | 0 | 0 | no | nessuno | react_operational_full |

## Aggiornamento 2.253.1 - 2026-06-12

L'assistente vocale Studio è stato verificato contro superfici reali e non come pannello dimostrativo:

- il catalogo da 330 frasi apre 59 destinazioni reali della shell React o delle route operative esistenti;
- `Studio cerca Rossi` apre davvero `/global-search?q=rossi`;
- `Studio apri Lex` usa l'evento applicativo Lex nel contesto corrente;
- `Studio nuovo cliente` invoca `POST /api/v1/ui/clienti/voce/crea`, con permesso `clienti.scrivi`, repository clienti, audit e sincronizzazione;
- l'audit CDP ha confermato voce/PIN, ascolto, disattivazione, cliente guidato, navigazione e responsive su Docker reale `127.0.0.1:8080`.

Esito: zero fallback mock, zero CTA primaria verso vista classica, zero testo tecnico vietato e zero failure browser.

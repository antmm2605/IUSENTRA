# Audit anti-mascheramento React

Generato: 2026-05-07T19:41:41.776Z

## Regole operative Parte 12A

- `react_operational_full` richiede pagina React, dati JSON, azioni principali JSON, CSRF/sessione/permessi, stati loading/error/success e nessuna CTA primaria legacy.
- `react_bridge` identifica superfici React con lettura reale ma scritture, dettagli o CTA principali ancora legacy.
- `react_shell` identifica superfici solo riepilogative o di navigazione, senza flusso operativo completo.
- `legacy_operational` resta il livello corretto quando il template Flask e il POST storico sono ancora il prodotto reale.
- `react_full` e deprecato: non va usato per pagine che delegano il flusso principale al legacy.

## Sintesi

- Route censite: 53
- Link `?_legacy=1`: 241
- LegacyPostForm: 9
- Form POST HTML React: 0
- Bridge con scritture legacy: 27
- Status react_full deprecati: 0
- API JSON di salvataggio mancanti: 4

## Tabella route

| route | componente | data client | bridge | stato manifest | link legacy presenti | form legacy presenti | scritture JSON presenti | problemi | livello reale |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| /utenti | frontend/src/components/UtentiPage.tsx | frontend/src/utentiData.ts | web/services/react_utenti_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /utenti/nuovo | frontend/src/components/UtentiPage.tsx | frontend/src/utentiData.ts | web/services/react_utenti_bridge.py | react_operational_full | 1 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /profili | frontend/src/components/ProfiliPage.tsx | frontend/src/profiliData.ts | web/services/react_profili_bridge.py | react_operational_full | 2 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /audit | frontend/src/components/AuditPage.tsx | frontend/src/auditData.ts | web/services/react_audit_bridge.py | react_operational_partial | 1 | 0 | no | 1 link ?_legacy=1 primari o non governati | react_bridge |
| /registro-attivita | frontend/src/components/AuditPage.tsx | frontend/src/auditData.ts | web/services/react_audit_bridge.py | react_operational_partial | 1 | 0 | no | 1 link ?_legacy=1 primari o non governati | react_bridge |
| /studio | frontend/src/components/StudioPage.tsx | frontend/src/studioData.ts | web/services/react_studio_bridge.py | react_bridge | 4 | 0 | no | 4 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /amministrazione | frontend/src/components/AmministrazionePage.tsx | frontend/src/amministrazioneData.ts | web/services/react_amministrazione_bridge.py | react_bridge | 0 | 0 | no | bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /impostazioni | frontend/src/components/ImpostazioniPage.tsx | frontend/src/impostazioniData.ts | web/services/react_impostazioni_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /impostazioni-studio | frontend/src/components/ImpostazioniPage.tsx | frontend/src/impostazioniData.ts | web/services/react_impostazioni_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /impostazioni/calendario | frontend/src/components/ImpostazioniPage.tsx | frontend/src/impostazioniData.ts | web/services/react_impostazioni_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /impostazioni/pagamenti | frontend/src/components/ImpostazioniPage.tsx | frontend/src/impostazioniData.ts | web/services/react_impostazioni_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /sincronizzazione-calendari | frontend/src/components/ImpostazioniPage.tsx | frontend/src/impostazioniData.ts | web/services/react_impostazioni_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /backup | frontend/src/components/BackupPage.tsx | frontend/src/backupData.ts | web/services/react_backup_bridge.py | react_operational_full | 5 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /sito-studio | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_bridge | 16 | 1 | no | 16 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes | react_bridge |
| /sito-studio/contatti | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | react_bridge | 16 | 1 | no | 16 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes; API JSON di salvataggio mancante | react_bridge |
| /sito-studio/builder | frontend/src/components/SitoStudioPage.tsx | frontend/src/sitoStudioData.ts | web/services/react_sito_studio_bridge.py | legacy_operational | 16 | 1 | no | 16 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes | legacy_operational |
| /statistiche | frontend/src/components/StatistichePage.tsx | frontend/src/statisticheData.ts | web/services/react_statistiche_bridge.py | react_operational_partial | 1 | 0 | no | 1 link ?_legacy=1 primari o non governati | react_bridge |
| /fatturazione | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | react_bridge | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /fatturazione/nuova | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | react_operational_full | 8 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /fatturazione/* | frontend/src/components/FatturazionePage.tsx | frontend/src/fatturazioneData.ts | web/services/react_fatturazione_bridge.py | legacy_operational | 8 | 0 | si | fallback legacy tecnico non primario | legacy_operational |
| /incassi-pagamenti | frontend/src/components/IncassiPagamentiPage.tsx | frontend/src/incassiPagamentiData.ts | web/services/react_incassi_pagamenti_bridge.py | react_bridge | 5 | 0 | no | 5 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes | react_bridge |
| /preventivi | frontend/src/components/PreventivoWizardPage.tsx | frontend/src/preventivoWizardData.ts | web/services/react_preventivo_wizard_bridge.py | react_bridge | 4 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/nuovo | frontend/src/components/PreventivoWizardPage.tsx | frontend/src/preventivoWizardData.ts | web/services/react_preventivo_wizard_bridge.py | react_bridge | 4 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /preventivi/conferimento/nuovo | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | react_bridge | 8 | 1 | no | 8 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes; API JSON di salvataggio mancante | react_bridge |
| /preventivi/* | frontend/src/components/PreventiviPage.tsx | frontend/src/preventiviData.ts | web/services/react_preventivi_bridge.py | legacy_operational | 8 | 1 | no | 8 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes | legacy_operational |
| /preventivi/wizard | frontend/src/components/PreventivoWizardPage.tsx | frontend/src/preventivoWizardData.ts | web/services/react_preventivo_wizard_bridge.py | react_operational_partial | 4 | 0 | si | fallback legacy tecnico non primario | react_operational_full |
| /compensi-forensi | frontend/src/components/CompensiForensiPage.tsx | frontend/src/compensiForensiData.ts | web/services/react_compensi_forensi_bridge.py | react_bridge | 3 | 1 | no | 3 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /compensi-forensi/* | frontend/src/components/CompensiForensiPage.tsx | frontend/src/compensiForensiData.ts | web/services/react_compensi_forensi_bridge.py | legacy_operational | 3 | 1 | no | 3 link ?_legacy=1 primari o non governati; LegacyPostForm presente; bridge writes=legacy_routes; gestione successo non rilevata | legacy_operational |
| /tariffario | frontend/src/components/TariffarioPage.tsx | frontend/src/tariffarioData.ts | web/services/react_tariffario_bridge.py | react_operational_partial | 3 | 1 | si | fallback legacy tecnico non primario; LegacyPostForm presente; bridge writes=legacy_routes | react_operational_partial |
| /tariffario/* | frontend/src/components/TariffarioPage.tsx | frontend/src/tariffarioData.ts | web/services/react_tariffario_bridge.py | legacy_operational | 3 | 1 | si | fallback legacy tecnico non primario; LegacyPostForm presente; bridge writes=legacy_routes | legacy_operational |
| /template-atti | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | react_bridge | 10 | 0 | no | 10 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /template-atti/catalogo | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | react_bridge | 10 | 0 | no | 10 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /template-atti/nuovo | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | legacy_operational | 10 | 0 | no | 10 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; API JSON di salvataggio mancante; gestione successo non rilevata | legacy_operational |
| /template-atti/* | frontend/src/components/TemplateAttiPage.tsx | frontend/src/templateAttiData.ts | web/services/react_template_atti_bridge.py | legacy_operational | 10 | 0 | no | 10 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | legacy_operational |
| /redazione-atti | frontend/src/components/RedazioneAttiPage.tsx | frontend/src/redazioneAttiData.ts | web/services/react_redazione_atti_bridge.py | react_bridge | 7 | 0 | no | 7 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /redazione-atti/* | frontend/src/components/RedazioneAttiPage.tsx | frontend/src/redazioneAttiData.ts | web/services/react_redazione_atti_bridge.py | legacy_operational | 7 | 0 | no | 7 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | legacy_operational |
| /checklist | frontend/src/components/ChecklistPage.tsx | frontend/src/checklistData.ts | web/services/react_checklist_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /giurisprudenza | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | react_bridge | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /giurisprudenza/nuova | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | legacy_operational | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; API JSON di salvataggio mancante; gestione successo non rilevata | legacy_operational |
| /giurisprudenza/* | frontend/src/components/GiurisprudenzaPage.tsx | frontend/src/giurisprudenzaData.ts | web/services/react_giurisprudenza_bridge.py | legacy_operational | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | legacy_operational |
| /legal-intelligence | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_bridge | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /legal-intelligence/news | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_bridge | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /legal-intelligence/mediazione | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_bridge | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /legal-intelligence/* | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | legacy_operational | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | legacy_operational |
| /ricerca-legale | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | react_bridge | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | react_bridge |
| /ricerca-legale/* | frontend/src/components/LegalIntelligencePage.tsx | frontend/src/legalIntelligenceData.ts | web/services/react_legal_intelligence_bridge.py | legacy_operational | 6 | 0 | no | 6 link ?_legacy=1 primari o non governati; bridge writes=legacy_routes; gestione successo non rilevata | legacy_operational |
| /deposito/checklist | frontend/src/components/DepositoChecklistPage.tsx | frontend/src/depositoChecklistData.ts | web/services/react_deposito_checklist_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /polisWeb | frontend/src/components/PolisWebPage.tsx | frontend/src/polisWebData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /pdp | frontend/src/components/PdpPage.tsx | frontend/src/pdpData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /pat | frontend/src/components/PatPage.tsx | frontend/src/patData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /sigit | frontend/src/components/SigitPage.tsx | frontend/src/sigitData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /sigp | frontend/src/components/SigpPage.tsx | frontend/src/sigpData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |
| /portali/* | frontend/src/components/PortaliPage.tsx | frontend/src/portaliData.ts | web/services/react_telematico_bridge.py | legacy_operational | 0 | 0 | no | nessuno | legacy_operational |

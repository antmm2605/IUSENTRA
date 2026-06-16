# Requisiti specifici App V2 per area

Aggiornato: 2026-05-13, fase 8 `fasereact` con collegamento fase 9 e fase 10.

Questo registro e' generato da `scripts/react-migration/generate_app_v2_area_requirements.py` a partire dal manifest React e dai gate di sicurezza/API gia' censiti. Serve a impedire promozioni generiche: ogni area deve dichiarare workflow, RBAC, tenant isolation, PII, test presenti e test mancanti prima di passare alle fasi visuali successive.

## Sintesi

- Aree rilevate o governate: 17.
- Route nel manifest: 116.
- Priorita route: P0=31; P1=45; P2=40.
- Stato aree: blocked=1; complete_tested=8; complete_unverified=4; partial=4.
- `complete_tested` non viene assegnato a un'area con route legacy/parziali o senza gate fase 8.
- Le aree non parificate restano `partial`, `pending` o `blocked` e non devono essere esposte come complete nella shell App V2.

## Registro requisiti

| Area | Pagine | URL App V2 | Flag | RBAC | PII | Workflow | Test richiesti | Test presenti | Priorita | Stato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Agenda ed eventi | /agenda/nuovo; /agenda; /agenda/importa; /timesheet | /app/agenda/nuovo; /app/agenda; /app/agenda/importa; /app/timesheet | routes.appV2.agenda.calendar; routes.appV2.agenda.create; routes.appV2.agenda.timesheet | agenda.leggi / agenda.scrivi quando modifica | appuntamenti, udienze, riferimenti fascicolo | calendario; nuovo appuntamento; timesheet | calendario con dati/empty; filtro data invalido; creazione negata senza permesso; form non invia tenant_id | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1; P2 | complete_tested |
| Amministrazione, utenti e permessi | /admin/osservabilita; /database; /applicazioni; /importa-pratiche-studio-telematico; /privacy/registro/nuovo; /admin/database; /amministrazione; /audit; +7 altre | /app/amministrazione; /app/amministrazione; /app/amministrazione; /app/importa-pratiche-studio-telematico; /app/privacy/registro/nuovo; /app/admin/database; +9 altre | routes.appV2.admin.auditLogs; routes.appV2.admin.database; routes.appV2.admin.home; routes.appV2.admin.privacyRegistry; routes.appV2.admin.roles; routes.appV2.admin.users; +2 altre | admin o permessi utenti/profili/audit specifici | utenti, ruoli, audit, registro GDPR e database runtime | utenti; profili; audit log; database; registro GDPR | non-admin 403; admin tenant A non vede tenant B; assegnazione ruolo non autorizzata negata; audit solo con permesso | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione | P0; P1; P2 | partial |
| Clienti e anagrafiche | /clienti/:id/cartella; /clienti/nuovo; /soggetti/nuovo; /cartelle-condivise; /clienti; /soggetti | /app/clienti/:id/cartella; /app/clienti/nuovo; /app/soggetti/nuovo; /app/cartelle-condivise; /app/clienti; /app/soggetti | routes.appV2.clients.create; routes.appV2.clients.detail; routes.appV2.clients.list; routes.appV2.contacts.create; routes.appV2.contacts.list | anagrafiche.leggi / anagrafiche.scrivi quando modifica | dati identificativi, fiscali e recapiti | clienti; soggetti; cartelle condivise | lista clienti tenant A; cliente tenant B negato; ricerca senza cross-tenant; form non invia tenant_id | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1; P2 | complete_tested |
| Comunicazioni, PEC e notifiche legali | /notifiche-legali; /messaggi/nuovo; /email; /email-ordinaria; /messaggi | /app/notifiche-legali; /app/messaggi/nuovo; /app/email; /app/email-ordinaria; /app/messaggi | routes.appV2.comms.messages; routes.appV2.comms.newMessage; routes.appV2.comms.ordinaryMail; routes.appV2.comms.pec | comunicazioni.leggi / comunicazioni.scrivi; segreti casella mai esposti | messaggi, allegati, destinatari, ricevute e segreti casella redatti | PEC; email ordinaria; messaggi; notifiche legali | dettaglio messaggio tenant-safe; allegato cross-tenant negato; invio senza permesso 403; flag off senza API dati | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P0; P1; P2 | complete_tested |
| Documenti, redazione e ricerca legale | /checklist; /giurisprudenza/*; /legal-intelligence/*; /redazione-atti/*; /ricerca-legale/*; /template-atti/*; /template-atti/nuovo; /giurisprudenza; +10 altre | /app; /app/lex; /app/lex; /app/documenti?tab=redazione; /app/lex; /app/documenti?tab=template; +12 altre | routes.appV2.dashboard.home; routes.appV2.documents.checklist; routes.appV2.documents.drafting; routes.appV2.documents.list; routes.appV2.documents.templateEditor; routes.appV2.documents.templates; +2 altre | documenti.leggi / documenti.scrivi; download e generazione protetti | atti, template, contenuti documento e allegati | redazione atti; template; giurisprudenza; upload/classificazione; editor | preview/download cross-tenant negati; upload invalido 400/422; editor nascosto senza permesso; path traversal negato | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione | P0; P1; P2 | partial |
| Fatturazione e pagamenti | /fatturazione/*; /fatturazione; /fatturazione/nuova; /incassi-pagamenti | /app/mandato?tab=fatturazione; /app/mandato?tab=fatturazione; /app/mandato?tab=fatturazione&drawer=nuova; /app/mandato?tab=incassi | routes.appV2.billing.invoices; routes.appV2.billing.payments | fatturazione.leggi / fatturazione.scrivi; pagamenti protetti | fatture, parcelle, incassi, provider pagamento e dati fiscali | fatture; parcelle; pagamenti; export/download | fattura tenant B negata; export senza permesso 403; download tenant B negato; importo invalido 400/422 | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione | P0; P1 | partial |
| Fascicoli | /fascicoli/:id/deposito/prepara; /fascicoli; /fascicoli/archivio; /fascicoli/nuovo | /app/fascicoli/:id/deposito/prepara; /app/fascicoli; /app/fascicoli/archivio; /app/fascicoli/nuovo | routes.appV2.cases.create; routes.appV2.cases.detail; routes.appV2.cases.list | fascicoli.leggi / fascicoli.scrivi quando modifica | parti, controparti, documenti, timeline e scadenze | lista fascicoli; dettaglio fascicolo; documenti/scadenze collegati | lista tenant A; dettaglio cross-tenant negato; timeline senza leakage; readonly non muta | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1; P2 | complete_tested |
| Impostazioni e integrazioni | /impostazioni; /impostazioni-studio; /impostazioni/calendario; /impostazioni/pagamenti; /impostazioni/sdi; /notifiche; /notifiche-whatsapp; /sincronizzazione-calendari; +2 altre | /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; +4 altre | routes.appV2.settings.backup; routes.appV2.settings.calendarSync; routes.appV2.settings.notifications; routes.appV2.settings.payments; routes.appV2.settings.sdi; routes.appV2.settings.studio; +1 altre | impostazioni.leggi / impostazioni.scrivi; segreti mascherati | configurazioni studio, PEC/SMTP, notifiche, backup, calendari e segreti redatti | dati studio; PEC/SMTP; pagamenti; notifiche; backup; calendari | non autorizzato 403; tenant A non vede settings B; secret mascherato; form invalido 400/422 | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1; P2 | complete_tested |
| Lex | /procedure-completion | /app/procedure-completion | routes.appV2.dashboard.home | sessione studio valida | da censire | workflow presente nel manifest | test area da censire | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere | P2 | complete_unverified |
| Mandato, preventivi e compensi | /compensi-forensi/*; /preventivi/*; /tariffario/*; /compensi-forensi; /preventivi; /preventivi/conferimento/:id; /preventivi/conferimento/nuovo; /preventivi/nuovo; +2 altre | /app/mandato?tab=compensi; /app/mandato?tab=preventivi; /app/mandato?tab=tariffario; /app/mandato?tab=compensi; /app/mandato?tab=preventivi; /app/mandato?tab=conferimenti; +4 altre | routes.appV2.billing.compensi; routes.appV2.billing.quotes; routes.appV2.billing.tariffario | mandato.leggi / mandato.scrivi; calcoli backend | offerte, conferimenti, tariffe e dati economici | preventivi; wizard; conferimenti; compensi; tariffario | lista preventivi tenant A; modifica senza permesso 403; importo invalido 400/422; apri fascicolo auditato se previsto | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione | P0; P1 | partial |
| Panoramica | / | /app | routes.appV2.dashboard.home | sessione studio valida | metriche aggregate; evitare PII non necessaria | dashboard tenant-safe; widget abilitati da flag/RBAC; azioni verso pagine permesse | dashboard con dati/empty/error; link nascosti se flag o permesso mancanti; conteggi tenant-safe | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere | P2 | complete_unverified |
| Portale Cliente | /app/portale-clienti; /portale-cliente | /app/portale-clienti; /portale-cliente | routes.appV2.clientPortal.enabled | clienti.leggi / clienti.scrivi per studio; token cliente firmato e hashato per vista cliente | anagrafica cliente, pratica, documenti, consensi, messaggi e token invito | dashboard studio; invito sicuro; vista cliente; upload documenti; firme semplici; chat; appuntamenti | repository SQLite/PostgreSQL; API studio 401/400/success; API cliente con token valido/non valido; browser desktop/tablet/mobile | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1 | complete_tested |
| Regia operativa | /regia-operativa; /workspace-intelligente | /app/regia-operativa; /app/workspace-intelligente | routes.appV2.dashboard.regia | sessione studio valida | metriche e suggerimenti su fascicoli/agenda | regia studio; sincronizzazione mailbox; azioni operative consentite | render regia; sync negata senza permesso; flag off senza API dati | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere | P2 | complete_unverified |
| Ricerca studio e Lex | /global-search; /ricerca-studio | /app/global-search; /app/ricerca-studio | routes.appV2.search.global | ricerca.leggi; fonti e citazioni governate | query, fonti, risultati e cronologia ricerca | ricerca globale; ricerca legale; giurisprudenza | query vuota; query senza risultati; tenant B zero risultati; filtro invalido gestito | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere | P2 | complete_unverified |
| Scadenze e termini | /scadenziario/:id/modifica; /scadenziario/nuova; /scadenziario; /scadenziario/:id; /wizard-pro | /app/scadenziario/:id/modifica; /app/scadenziario/nuova; /app/scadenziario; /app/scadenziario/:id; /app/wizard-pro | routes.appV2.deadlines.create; routes.appV2.deadlines.detail; routes.appV2.deadlines.hearingWizard; routes.appV2.deadlines.list | scadenze.leggi / scadenze.scrivi | termini, reminder e collegamenti a fascicolo | scadenziario; nuova scadenza; termini guidati | lista tenant A; scadenza tenant B negata; filtro invalido gestito; readonly non muta | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1; P2 | complete_tested |
| Studio e sito studio | /sito-studio/articoli/:id/modifica; /sito-studio/builder; /sito-studio/redazione-ai; /strumenti-legali; /workflow-agents; /legal-skills; /sito-studio; /sito-studio/contatti; +2 altre | /app/amministrazione?tab=studio-redazione-ai; /app/amministrazione?tab=studio; /app/amministrazione?tab=studio-redazione-ai; /app/studio; /app/workflow-agents; /app/legal-skills; +4 altre | routes.appV2.legalSkills.catalog; routes.appV2.studio.modules; routes.appV2.studio.site; routes.appV2.studio.siteBuilder; routes.appV2.studio.siteDrafting; routes.appV2.studio.statistics; +1 altre | studio.leggi / studio.scrivi; admin.configura per sito e pubblicazione | configurazioni, contenuti pubblici, richieste contatto e prenotazioni | studio; statistiche; sito studio; builder; redazione AI | builder con dati/empty; asset upload senza permesso 403; contatti tenant-safe; mobile senza overflow | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite | P1; P2 | complete_tested |
| Servizi telematici | /deposito/checklist; /guida/firma-digitale; /pat; /pdp; /polisWeb; /portali/*; /portali/pat/acquisizione; /portali/pdp/acquisizione; +9 altre | /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; +11 altre | routes.appV2.dashboard.home; routes.appV2.documents.checklist; routes.appV2.telematico.center; routes.appV2.telematico.surface | telematico.leggi / telematico.scrivi; Local Signer e portali fail-closed | buste, ricevute, allegati, dati ministeriali e Local Signer | controlli atti; centro telematico; PST/PDP/PAT/PTT/SIGP/POLISWEB dove presenti | controlli atti React; portali non parificati pending; download senza permesso 403; flag off senza API dati | tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; controlli atti React; workflow ministeriali non parificati marcati blocked | P0 | blocked |

## Dettaglio aree

### Agenda ed eventi

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 4; priorita: P1; P2; migrazione: react_operational_full=4.
- URL legacy principali: /agenda/nuovo; /agenda; /agenda/importa; /timesheet.
- URL App V2: /app/agenda/nuovo; /app/agenda; /app/agenda/importa; /app/timesheet.
- Endpoint API: /api/v1/ui/agenda*, /api/v1/ui/timesheet*.
- Feature flag: routes.appV2.agenda.calendar; routes.appV2.agenda.create; routes.appV2.agenda.timesheet.
- RBAC: agenda.leggi / agenda.scrivi quando modifica.
- PII: appuntamenti, udienze, riferimenti fascicolo.
- Workflow principali: calendario; nuovo appuntamento; timesheet.
- Requisiti specifici verificati o governati: filtri data validati; nessun tenant_id dal client; readonly senza mutazioni; date in formato italiano.
- Test richiesti: calendario con dati/empty; filtro data invalido; creazione negata senza permesso; form non invia tenant_id.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Amministrazione, utenti e permessi

- Stato: `partial` (area mista: alcune route sono React full, altre parziali o legacy).
- Route censite: 15; priorita: P0; P1; P2; migrazione: legacy_operational=3; react_operational_full=12.
- URL legacy principali: /admin/osservabilita; /database; /applicazioni; /importa-pratiche-studio-telematico; /privacy/registro/nuovo; /admin/database; /amministrazione; /audit; /privacy/registro; /profili; /profilo; /registro-attivita; +3 altre.
- URL App V2: /app/amministrazione; /app/amministrazione; /app/amministrazione; /app/importa-pratiche-studio-telematico; /app/privacy/registro/nuovo; /app/admin/database; /app/amministrazione; /app/amministrazione?tab=audit; /app/privacy/registro; /app/amministrazione?tab=profili; /app/profilo; /app/amministrazione?tab=audit; +3 altre.
- Endpoint API: /api/v1/ui/amministrazione*, /api/v1/ui/utenti*, /api/v1/ui/profili*, /api/v1/ui/audit*, /api/v1/ui/admin/database, /api/v1/ui/privacy/registro.
- Feature flag: routes.appV2.admin.auditLogs; routes.appV2.admin.database; routes.appV2.admin.home; routes.appV2.admin.privacyRegistry; routes.appV2.admin.roles; routes.appV2.admin.users; routes.appV2.dashboard.home; routes.appV2.studio.modules.
- RBAC: admin o permessi utenti/profili/audit specifici.
- PII: utenti, ruoli, audit, registro GDPR e database runtime.
- Workflow principali: utenti; profili; audit log; database; registro GDPR.
- Requisiti specifici verificati o governati: solo admin autorizzato; niente auto-escalation; password hash/token mai in UI; azioni distruttive confermate.
- Test richiesti: non-admin 403; admin tenant A non vede tenant B; assegnazione ruolo non autorizzata negata; audit solo con permesso.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Clienti e anagrafiche

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 6; priorita: P1; P2; migrazione: react_operational_full=6.
- URL legacy principali: /clienti/:id/cartella; /clienti/nuovo; /soggetti/nuovo; /cartelle-condivise; /clienti; /soggetti.
- URL App V2: /app/clienti/:id/cartella; /app/clienti/nuovo; /app/soggetti/nuovo; /app/cartelle-condivise; /app/clienti; /app/soggetti.
- Endpoint API: /api/v1/ui/clienti*, /api/v1/ui/soggetti*.
- Feature flag: routes.appV2.clients.create; routes.appV2.clients.detail; routes.appV2.clients.list; routes.appV2.contacts.create; routes.appV2.contacts.list.
- RBAC: anagrafiche.leggi / anagrafiche.scrivi quando modifica.
- PII: dati identificativi, fiscali e recapiti.
- Workflow principali: clienti; soggetti; cartelle condivise.
- Requisiti specifici verificati o governati: PII minima nelle liste; ricerca tenant-safe; nessun tenant_id/studio_id dal client; form validati.
- Test richiesti: lista clienti tenant A; cliente tenant B negato; ricerca senza cross-tenant; form non invia tenant_id.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Comunicazioni, PEC e notifiche legali

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 5; priorita: P0; P1; P2; migrazione: react_operational_full=5.
- URL legacy principali: /notifiche-legali; /messaggi/nuovo; /email; /email-ordinaria; /messaggi.
- URL App V2: /app/notifiche-legali; /app/messaggi/nuovo; /app/email; /app/email-ordinaria; /app/messaggi.
- Endpoint API: /api/v1/ui/messaggi*, /api/v1/ui/email*, /api/v1/ui/email-ordinaria*, /api/v1/ui/notifiche-legali*.
- Feature flag: routes.appV2.comms.messages; routes.appV2.comms.newMessage; routes.appV2.comms.ordinaryMail; routes.appV2.comms.pec.
- RBAC: comunicazioni.leggi / comunicazioni.scrivi; segreti casella mai esposti.
- PII: messaggi, allegati, destinatari, ricevute e segreti casella redatti.
- Workflow principali: PEC; email ordinaria; messaggi; notifiche legali.
- Requisiti specifici verificati o governati: allegati protetti; readonly senza invio; segreti non esposti; layout responsive due colonne quando previsto.
- Test richiesti: dettaglio messaggio tenant-safe; allegato cross-tenant negato; invio senza permesso 403; flag off senza API dati.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Documenti, redazione e ricerca legale

- Stato: `partial` (area mista: alcune route sono React full, altre parziali o legacy).
- Route censite: 18; priorita: P0; P1; P2; migrazione: legacy_operational=7; react_operational_full=11.
- URL legacy principali: /checklist; /giurisprudenza/*; /legal-intelligence/*; /redazione-atti/*; /ricerca-legale/*; /template-atti/*; /template-atti/nuovo; /giurisprudenza; /giurisprudenza/nuova; /legal-intelligence; /legal-intelligence/mediazione; /legal-intelligence/news; +6 altre.
- URL App V2: /app; /app/lex; /app/lex; /app/documenti?tab=redazione; /app/lex; /app/documenti?tab=template; /app/documenti?tab=template; /app/lex; /app/lex; /app/lex; /app/lex; /app/lex; +6 altre.
- Endpoint API: /api/v1/ui/template-atti*, /api/v1/ui/redazione-atti*, /api/v1/ui/studio-modules/*, /api/editor/*.
- Feature flag: routes.appV2.dashboard.home; routes.appV2.documents.checklist; routes.appV2.documents.drafting; routes.appV2.documents.list; routes.appV2.documents.templateEditor; routes.appV2.documents.templates; routes.appV2.legalResearch.giurisprudenza; routes.appV2.legalResearch.home.
- RBAC: documenti.leggi / documenti.scrivi; download e generazione protetti.
- PII: atti, template, contenuti documento e allegati.
- Workflow principali: redazione atti; template; giurisprudenza; upload/classificazione; editor.
- Requisiti specifici verificati o governati: download/upload protetti; nessun path interno; MIME e nomi file governati; fallback sicuro se editor non disponibile.
- Test richiesti: preview/download cross-tenant negati; upload invalido 400/422; editor nascosto senza permesso; path traversal negato.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Fatturazione e pagamenti

- Stato: `partial` (area mista: alcune route sono React full, altre parziali o legacy).
- Route censite: 4; priorita: P0; P1; migrazione: legacy_operational=1; react_operational_full=3.
- URL legacy principali: /fatturazione/*; /fatturazione; /fatturazione/nuova; /incassi-pagamenti.
- URL App V2: /app/mandato?tab=fatturazione; /app/mandato?tab=fatturazione; /app/mandato?tab=fatturazione&drawer=nuova; /app/mandato?tab=incassi.
- Endpoint API: /api/v1/ui/fatturazione*, /api/v1/ui/preventivi*, /api/v1/ui/pagamenti*, /api/v1/ui/incassi-pagamenti*.
- Feature flag: routes.appV2.billing.invoices; routes.appV2.billing.payments.
- RBAC: fatturazione.leggi / fatturazione.scrivi; pagamenti protetti.
- PII: fatture, parcelle, incassi, provider pagamento e dati fiscali.
- Workflow principali: fatture; parcelle; pagamenti; export/download.
- Requisiti specifici verificati o governati: download/export protetti; filtri data/stato validati; PII fiscale minima; audit su modifiche economiche.
- Test richiesti: fattura tenant B negata; export senza permesso 403; download tenant B negato; importo invalido 400/422.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Fascicoli

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 4; priorita: P1; P2; migrazione: react_operational_full=4.
- URL legacy principali: /fascicoli/:id/deposito/prepara; /fascicoli; /fascicoli/archivio; /fascicoli/nuovo.
- URL App V2: /app/fascicoli/:id/deposito/prepara; /app/fascicoli; /app/fascicoli/archivio; /app/fascicoli/nuovo.
- Endpoint API: /api/v1/ui/fascicoli*.
- Feature flag: routes.appV2.cases.create; routes.appV2.cases.detail; routes.appV2.cases.list.
- RBAC: fascicoli.leggi / fascicoli.scrivi quando modifica.
- PII: parti, controparti, documenti, timeline e scadenze.
- Workflow principali: lista fascicoli; dettaglio fascicolo; documenti/scadenze collegati.
- Requisiti specifici verificati o governati: deep link protetto; collegamenti solo stesso tenant/fascicolo; azioni create/update/archive protette.
- Test richiesti: lista tenant A; dettaglio cross-tenant negato; timeline senza leakage; readonly non muta.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Impostazioni e integrazioni

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 10; priorita: P1; P2; migrazione: react_operational_full=10.
- URL legacy principali: /impostazioni; /impostazioni-studio; /impostazioni/calendario; /impostazioni/pagamenti; /impostazioni/sdi; /notifiche; /notifiche-whatsapp; /sincronizzazione-calendari; /backup; /studio.
- URL App V2: /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni; /app/impostazioni.
- Endpoint API: /api/v1/ui/impostazioni*, /api/v1/ui/calendari*, /api/v1/ui/backup*, /api/push/*.
- Feature flag: routes.appV2.settings.backup; routes.appV2.settings.calendarSync; routes.appV2.settings.notifications; routes.appV2.settings.payments; routes.appV2.settings.sdi; routes.appV2.settings.studio; routes.appV2.studio.home.
- RBAC: impostazioni.leggi / impostazioni.scrivi; segreti mascherati.
- PII: configurazioni studio, PEC/SMTP, notifiche, backup, calendari e segreti redatti.
- Workflow principali: dati studio; PEC/SMTP; pagamenti; notifiche; backup; calendari.
- Requisiti specifici verificati o governati: segreti mai restituiti in chiaro; update secret non ritorna secret; form validati; readonly non muta.
- Test richiesti: non autorizzato 403; tenant A non vede settings B; secret mascherato; form invalido 400/422.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Lex

- Stato: `complete_unverified` (area React full senza P0/P1; smoke workflow autenticato da estendere).
- Route censite: 1; priorita: P2; migrazione: react_operational_full=1.
- URL legacy principali: /procedure-completion.
- URL App V2: /app/procedure-completion.
- Endpoint API: da censire.
- Feature flag: routes.appV2.dashboard.home.
- RBAC: sessione studio valida.
- PII: da censire.
- Workflow principali: workflow presente nel manifest.
- Requisiti specifici verificati o governati: tenant-safe; RBAC; stati UI completi.
- Test richiesti: test area da censire.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Mandato, preventivi e compensi

- Stato: `partial` (area mista: alcune route sono React full, altre parziali o legacy).
- Route censite: 10; priorita: P0; P1; migrazione: legacy_operational=3; react_operational_full=7.
- URL legacy principali: /compensi-forensi/*; /preventivi/*; /tariffario/*; /compensi-forensi; /preventivi; /preventivi/conferimento/:id; /preventivi/conferimento/nuovo; /preventivi/nuovo; /preventivi/wizard; /tariffario.
- URL App V2: /app/mandato?tab=compensi; /app/mandato?tab=preventivi; /app/mandato?tab=tariffario; /app/mandato?tab=compensi; /app/mandato?tab=preventivi; /app/mandato?tab=conferimenti; /app/mandato?tab=conferimenti; /app/mandato?tab=preventivi; /app/mandato?tab=wizard; /app/mandato?tab=tariffario.
- Endpoint API: /api/v1/ui/preventivi*, /api/v1/ui/fatturazione*, /api/v1/ui/tariffario*.
- Feature flag: routes.appV2.billing.compensi; routes.appV2.billing.quotes; routes.appV2.billing.tariffario.
- RBAC: mandato.leggi / mandato.scrivi; calcoli backend.
- PII: offerte, conferimenti, tariffe e dati economici.
- Workflow principali: preventivi; wizard; conferimenti; compensi; tariffario.
- Requisiti specifici verificati o governati: calcoli backend; importi validati; apertura fascicolo protetta; readonly senza mutazioni.
- Test richiesti: lista preventivi tenant A; modifica senza permesso 403; importo invalido 400/422; apri fascicolo auditato se previsto.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; test specifici da completare prima della promozione.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Panoramica

- Stato: `complete_unverified` (area React full senza P0/P1; smoke workflow autenticato da estendere).
- Route censite: 1; priorita: P2; migrazione: react_operational_full=1.
- URL legacy principali: /.
- URL App V2: /app.
- Endpoint API: /api/v1/ui/dashboard.
- Feature flag: routes.appV2.dashboard.home.
- RBAC: sessione studio valida.
- PII: metriche aggregate; evitare PII non necessaria.
- Workflow principali: dashboard tenant-safe; widget abilitati da flag/RBAC; azioni verso pagine permesse.
- Requisiti specifici verificati o governati: nessun conteggio globale; empty/loading/error state; nessuna fetch se flag App V2 spento.
- Test richiesti: dashboard con dati/empty/error; link nascosti se flag o permesso mancanti; conteggi tenant-safe.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Portale Cliente

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 2; priorita: P1; migrazione: react_operational_full=2.
- URL legacy principali: /app/portale-clienti; /portale-cliente.
- URL App V2: /app/portale-clienti; /portale-cliente.
- Endpoint API: /api/v1/ui/client-portal*, /portale-cliente.
- Feature flag: routes.appV2.clientPortal.enabled.
- RBAC: clienti.leggi / clienti.scrivi per studio; token cliente firmato e hashato per vista cliente.
- PII: anagrafica cliente, pratica, documenti, consensi, messaggi e token invito.
- Workflow principali: dashboard studio; invito sicuro; vista cliente; upload documenti; firme semplici; chat; appuntamenti.
- Requisiti specifici verificati o governati: token mai salvato in chiaro; tenant risolto solo server-side; SQLite e PostgreSQL equivalenti; upload senza path esposti; privacy e consensi auditati.
- Test richiesti: repository SQLite/PostgreSQL; API studio 401/400/success; API cliente con token valido/non valido; browser desktop/tablet/mobile.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Regia operativa

- Stato: `complete_unverified` (area React full senza P0/P1; smoke workflow autenticato da estendere).
- Route censite: 2; priorita: P2; migrazione: react_operational_full=2.
- URL legacy principali: /regia-operativa; /workspace-intelligente.
- URL App V2: /app/regia-operativa; /app/workspace-intelligente.
- Endpoint API: /api/v1/ui/dashboard, /api/workspace-intelligente.
- Feature flag: routes.appV2.dashboard.regia.
- RBAC: sessione studio valida.
- PII: metriche e suggerimenti su fascicoli/agenda.
- Workflow principali: regia studio; sincronizzazione mailbox; azioni operative consentite.
- Requisiti specifici verificati o governati: dati solo tenant corrente; azioni governate da permessi; nessun dato stale dopo cambio utente.
- Test richiesti: render regia; sync negata senza permesso; flag off senza API dati.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Ricerca studio e Lex

- Stato: `complete_unverified` (area React full senza P0/P1; smoke workflow autenticato da estendere).
- Route censite: 2; priorita: P2; migrazione: react_operational_full=2.
- URL legacy principali: /global-search; /ricerca-studio.
- URL App V2: /app/global-search; /app/ricerca-studio.
- Endpoint API: /api/v1/ui/legal-intelligence*, /api/v1/ui/giurisprudenza*, /api/v1/ui/ricerca-legale*.
- Feature flag: routes.appV2.search.global.
- RBAC: ricerca.leggi; fonti e citazioni governate.
- PII: query, fonti, risultati e cronologia ricerca.
- Workflow principali: ricerca globale; ricerca legale; giurisprudenza.
- Requisiti specifici verificati o governati: risultati filtrati da tenant/RBAC; nessun leakage tramite conteggi; query param validati; fonti citabili.
- Test richiesti: query vuota; query senza risultati; tenant B zero risultati; filtro invalido gestito.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate statici; smoke browser dedicato da estendere.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

### Scadenze e termini

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 5; priorita: P1; P2; migrazione: react_operational_full=5.
- URL legacy principali: /scadenziario/:id/modifica; /scadenziario/nuova; /scadenziario; /scadenziario/:id; /wizard-pro.
- URL App V2: /app/scadenziario/:id/modifica; /app/scadenziario/nuova; /app/scadenziario; /app/scadenziario/:id; /app/wizard-pro.
- Endpoint API: /api/v1/ui/scadenziario*, /api/v1/ui/wizard-pro*.
- Feature flag: routes.appV2.deadlines.create; routes.appV2.deadlines.detail; routes.appV2.deadlines.hearingWizard; routes.appV2.deadlines.list.
- RBAC: scadenze.leggi / scadenze.scrivi.
- PII: termini, reminder e collegamenti a fascicolo.
- Workflow principali: scadenziario; nuova scadenza; termini guidati.
- Requisiti specifici verificati o governati: stato completata coerente; filtri validati; reminder senza leakage; audit su modifiche rilevanti.
- Test richiesti: lista tenant A; scadenza tenant B negata; filtro invalido gestito; readonly non muta.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Studio e sito studio

- Stato: `complete_tested` (area senza route pendenti/parziali e con P0/P1 coperti dai gate comuni piu' registro fase 8).
- Route censite: 10; priorita: P1; P2; migrazione: react_operational_full=10.
- URL legacy principali: /sito-studio/articoli/:id/modifica; /sito-studio/builder; /sito-studio/redazione-ai; /strumenti-legali; /workflow-agents; /legal-skills; /sito-studio; /sito-studio/contatti; /statistiche; /strumenti-operativi.
- URL App V2: /app/amministrazione?tab=studio-redazione-ai; /app/amministrazione?tab=studio; /app/amministrazione?tab=studio-redazione-ai; /app/studio; /app/workflow-agents; /app/legal-skills; /app/amministrazione?tab=studio; /app/amministrazione?tab=studio; /app/regia?tab=statistiche; /app/studio.
- Endpoint API: /api/v1/ui/studio*, /api/v1/ui/studio-modules/*, /api/v1/ui/sito-studio*.
- Feature flag: routes.appV2.legalSkills.catalog; routes.appV2.studio.modules; routes.appV2.studio.site; routes.appV2.studio.siteBuilder; routes.appV2.studio.siteDrafting; routes.appV2.studio.statistics; routes.appV2.workflowAgents.home.
- RBAC: studio.leggi / studio.scrivi; admin.configura per sito e pubblicazione.
- PII: configurazioni, contenuti pubblici, richieste contatto e prenotazioni.
- Workflow principali: studio; statistiche; sito studio; builder; redazione AI.
- Requisiti specifici verificati o governati: azioni pubblicazione protette; asset/upload governati; empty state reali; nessun dato demo.
- Test richiesti: builder con dati/empty; asset upload senza permesso 403; contatti tenant-safe; mobile senza overflow.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; gate fase 7; provider verification P0/P1; build Vite.
- Rischio residuo: estendere smoke autenticato tenant A/B quando sono disponibili credenziali ambiente.

### Servizi telematici

- Stato: `blocked` (presente ma bloccata da workflow non parificati o rimandati esplicitamente).
- Route censite: 17; priorita: P0; migrazione: legacy_operational=3; react_operational_full=14.
- URL legacy principali: /deposito/checklist; /guida/firma-digitale; /pat; /pdp; /polisWeb; /portali/*; /portali/pat/acquisizione; /portali/pdp/acquisizione; /portali/pst/acquisizione; /portali/ptt/acquisizione; /portali/sigit/acquisizione; /servizi-telematici; +5 altre.
- URL App V2: /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; /app/telematico; +5 altre.
- Endpoint API: /api/v1/ui/telematico*, /api/v1/ui/local-signer*.
- Feature flag: routes.appV2.dashboard.home; routes.appV2.documents.checklist; routes.appV2.telematico.center; routes.appV2.telematico.surface.
- RBAC: telematico.leggi / telematico.scrivi; Local Signer e portali fail-closed.
- PII: buste, ricevute, allegati, dati ministeriali e Local Signer.
- Workflow principali: controlli atti; centro telematico; PST/PDP/PAT/PTT/SIGP/POLISWEB dove presenti.
- Requisiti specifici verificati o governati: workflow ministeriali non parificati restano fallback; Local Signer fail-closed; nessuna credenziale portale cloud; download/allegati protetti.
- Test richiesti: controlli atti React; portali non parificati pending; download senza permesso 403; flag off senza API dati.
- Test presenti fase 8: tests/test_app_v2_area_requirements_phase8.py; scripts/smoke_app_v2_workflows.py --list; controlli atti React; workflow ministeriali non parificati marcati blocked.
- Rischio residuo: nessuna promozione ulteriore senza smoke autenticato area-specifico.

## Collegamento UI regression fase 9

La copertura visuale e di regressione e' documentata in `docs/ui-regression-and-storybook.md` e nella sezione `Copertura UI fase 9` di `docs/frontend-app-v2-pages.md` e `docs/app-v2-page-registry.md`. Storybook e VRT restano non attivi finche' non esiste un comando reale; le aree con route `partial`, `pending` o `blocked` non possono essere promosse a `ui_tested`.

Gate fase 9:

```powershell
python scripts\validate_ui_coverage.py
python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short
pnpm --filter @iusentra/studio test
```

## Collegamento test plan fase 10

La fase 10 collega ogni area al piano test App V2 senza promuovere automaticamente pagine incomplete. La matrice di dettaglio e' in `docs/test-matrix-app-v2.md`, l'inventario in `docs/test-inventory.md` e il piano operativo in `docs/test-plan-app-v2.md`.

Gate fase 10:

```powershell
python scripts\react-migration\generate_app_v2_test_docs.py --check
python scripts\smoke_app_v2_all.py --subset inventory
python -m pytest -q tests/test_app_v2_test_plan_phase10.py --tb=short
```

## Smoke workflow fase 8

Lo smoke autenticato e' in `scripts/smoke_app_v2_workflows.py`. Senza le variabili ambiente richieste esegue solo inventario e lo dichiara esplicitamente; con `--require-credentials` fallisce se le credenziali non sono presenti.

```powershell
python scripts\smoke_app_v2_workflows.py --list
$env:IUSENTRA_BASE_URL='https://app.iusentra.it'
$env:IUSENTRA_ADMIN_USER='<utente-admin>'
$env:IUSENTRA_ADMIN_PASSWORD='<password-admin>'
$env:IUSENTRA_TENANT_A_USER='<utente-tenant-a>'
$env:IUSENTRA_TENANT_A_PASSWORD='<password-tenant-a>'
$env:IUSENTRA_TENANT_B_USER='<utente-tenant-b>'
$env:IUSENTRA_TENANT_B_PASSWORD='<password-tenant-b>'
$env:IUSENTRA_READONLY_USER='<utente-sola-lettura>'
$env:IUSENTRA_READONLY_PASSWORD='<password-sola-lettura>'
python scripts\smoke_app_v2_workflows.py --require-credentials
```

# Backend Endpoint Security Map

Aggiornato: 2026-05-13.

## Fase 5 Backend Security Review

La mappa censisce gli endpoint JSON React sotto `/api/v1/ui` e il relativo presidio minimo: autenticazione, RBAC, isolamento tenant, redazione PII e audit denial. La fase 5 aggiunge un guardrail centrale in `web/services/backend_security.py`, applicato dal runtime tenant a tutto il prefisso `/api/v1/ui/*`, che blocca parametri client riservati al controllo server.

## Sommario

- Endpoint React API censiti: 217.
- Endpoint con `_richiedi_auth`: 217/217.
- Endpoint con metodo di scrittura o cancellazione: 107.
- Endpoint con superficie file/upload/download/export/evidence: 9.
- Route manifest censite: 108; critical: 18; high/P1: 70.
- Parametri controllo bloccati: `tenant_id`, `tenant_slug`, `studio_id`, `studio_slug`, `user_id`, `api_key`, `token`, `access_token`, `refresh_token`, `redirect`, `redirect_url`, `return_url`, `next`, path filesystem.
- Denial log: `policy_denied.backend_security` e warning applicativo `policy_denied backend_security_control_param` senza valori sensibili.

## Regole Trasversali

| Presidio | Stato fase 5 | Note |
| --- | --- | --- |
| Autenticazione | Obbligatoria su tutte le API React censite | Sessione Flask o API key tenant-aware. |
| Tenant | Fail-closed multi-studio | `tenant_isolation_runtime` e `tenant_api_auth` bloccano assenza/mismatch. |
| RBAC | Permessi dominio per aree sensibili | Utenti, profili, audit, backup, impostazioni e fatturazione hanno check dedicati. |
| Mass assignment | Blocco centrale campi contesto | Il client non puo' inviare tenant/studio/token/redirect generici. |
| PII | Payload redatti dove necessario | Audit e segreti impostazioni non espongono password/token salvati. |
| File/download | Solo endpoint dominio autenticati | Path runtime sotto tenant, download e allegati restano su route specifiche. |

## Matrice Esecutiva Fase 1

| Caso | Perimetro | Esito atteso | Gate |
| --- | --- | --- | --- |
| 401 senza sessione o API key | Tutti gli endpoint `/api/v1/ui/*` registrati da Flask. | 401 JSON senza valori sensibili. | `tests/test_ui_api_security_matrix.py::test_all_ui_api_endpoints_enforce_auth_tenant_denials_and_forbidden_context_keys` |
| 403 API key di altro studio | Tutti gli endpoint `/api/v1/ui/*` con API key valida ma slug non corrispondente. | 403 fail-closed, senza eco di chiavi o path runtime. | `tests/test_ui_api_security_matrix.py::test_all_ui_api_endpoints_enforce_auth_tenant_denials_and_forbidden_context_keys` |
| 404 cross-tenant su risorsa | Dettaglio fascicolo richiesto da un altro tenant. | 404 con `notFound=true`, senza titolo o dati della pratica esterna. | `tests/test_ui_api_security_matrix.py::test_ui_api_security_matrix_copre_auth_tenant_cross_tenant_success_e_audit_denial` |
| 400 tenant_id o contesto forzato | Tutti gli endpoint `/api/v1/ui/*` con tenant/studio/user/token/redirect/root/path filesystem. | 400 `backend_security_control_param` e audit `policy_denied.backend_security`. | `tests/test_backend_security_phase5.py; tests/test_ui_api_security_matrix.py` |
| 200 success con tenant valido | Lista e dettaglio fascicoli con API key e slug coerenti. | Payload reale del tenant attivo, nessun mock/fallback cross-studio. | `tests/test_ui_api_security_matrix.py::test_ui_api_security_matrix_copre_auth_tenant_cross_tenant_success_e_audit_denial` |
| Upload/download tenant-safe | Endpoint di upload/export/evidence pack e allegati serviti da backend. | Nessun path/root accettato dal client; file route autenticate e tenant-aware. | `tests/test_ui_api_security_matrix.py; fase 2 file security` |

## Endpoint

| Metodo | Endpoint | Area | Priorita | Permesso atteso | Dati sensibili | Presidi |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/ui/admin/database` | Amministrazione database | P0 | `utenti.leggi` | dati tecnici e path redatti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/agenda` | Agenda | P1 | `sessione/API tenant-aware` | appuntamenti e calendario | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/agenda/importa` | Agenda | P1 | `sessione/API tenant-aware` | appuntamenti e calendario | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/agenda/nuovo/defaults` | Agenda | P1 | `sessione/API tenant-aware` | appuntamenti e calendario | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/amministrazione` | Amministrazione | P0 | `utenti.leggi` | riepilogo governance studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/audit` | Registro attivita | P0 | `audit.leggi` | PII e log operativi redatti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/audit/<id_evento>` | Registro attivita | P0 | `audit.leggi` | PII e log operativi redatti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/backup` | Backup | P0 | `backup.leggi/esegui` | archivi e verifiche integrita | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/backup/crea` | Backup | P0 | `backup.leggi/esegui` | archivi e verifiche integrita | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/backup/verifica` | Backup | P0 | `backup.leggi/esegui` | archivi e verifiche integrita | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/bootstrap` | Bootstrap React | P0 | `sessione/API tenant-aware` | menu, feature flag e contesto studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/calendari/accounts` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/accounts/<account_id>/disconnect` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/accounts/<account_id>/sync` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/apple/connect` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/calendars/<calendar_id>/toggle` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/calendari/conflicts` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/conflicts/<conflict_id>/resolve` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/demo/connect` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/calendari/google/callback` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/google/connect` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/calendari/microsoft/callback` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/microsoft/connect` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/calendari/webcal/connect` | Sincronizzazione calendari | P0 | `admin.configura` | account calendari e feed tenant | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/cartelle-condivise` | Cartelle condivise | P1 | `sessione/API tenant-aware` | condivisioni cliente e permessi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/clienti` | Clienti | P1 | `sessione/API tenant-aware` | anagrafiche e cartelle | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/clienti/<id_cliente>/cartella` | Clienti | P1 | `sessione/API tenant-aware` | anagrafiche e cartelle | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/clienti/<id_cliente>/modifica` | Clienti | P1 | `sessione/API tenant-aware` | anagrafiche e cartelle | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/clienti/delete` | Clienti | P1 | `sessione/API tenant-aware` | anagrafiche e cartelle | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/clienti/nuovo` | Clienti | P1 | `sessione/API tenant-aware` | anagrafiche e cartelle | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/clienti/nuovo/documento/leggi` | Clienti | P1 | `sessione/API tenant-aware` | anagrafiche e cartelle | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/compensi-forensi` | Compensi forensi | P1 | `fatturazione.leggi` | calcoli tariffari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/compensi-forensi/calcola` | Compensi forensi | P1 | `fatturazione.leggi` | calcoli tariffari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/conferimenti/<conferimento_id>/apri-fascicolo` | Conferimenti | P0 | `fatturazione.leggi/scrivi` | apertura fascicolo da incarico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/dashboard` | Panoramica | P1 | `sessione/API tenant-aware` | metriche aggregate studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/dashboard/sync-mailboxes` | Panoramica | P1 | `sessione/API tenant-aware` | metriche aggregate studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/email` | Email PEC | P0 | `sessione/API tenant-aware` | messaggi, allegati e destinatari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/email-ordinaria` | Email ordinaria | P0 | `sessione/API tenant-aware` | messaggi, allegati e destinatari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/email-ordinaria/bulk-action` | Email ordinaria | P0 | `sessione/API tenant-aware` | messaggi, allegati e destinatari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/email-ordinaria/messaggio/<id_email>` | Email ordinaria | P0 | `sessione/API tenant-aware` | messaggi, allegati e destinatari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/email/bulk-action` | Email PEC | P0 | `sessione/API tenant-aware` | messaggi, allegati e destinatari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/email/messaggio/<id_email>` | Email PEC | P0 | `sessione/API tenant-aware` | messaggi, allegati e destinatari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/attivita` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/checklist` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/depositi` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/depositi/<deposito_id>/evidence-pack` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/depositi/<deposito_id>/importa-ricevuta` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/depositi/<deposito_id>/timeline` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/depositi/invia` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/depositi/prepara` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/document-slots` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/document-slots/<slot_key>/link` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/document-slots/<slot_key>/validate` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/documenti` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/documenti/<id_doc>/editor` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/modifica` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/predeposito/check` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/regia` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/regia/applica-profilo` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fascicoli/<id_fasc>/regia/ricalcola` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/<id_fasc>/scadenze` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/archivio` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/export` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fascicoli/nuovo` | Fascicoli e documenti | P0 | `sessione/API tenant-aware` | fascicoli, documenti e depositi | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fatturazione` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fatturazione/<id_documento>` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fatturazione/<id_documento>/annulla` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fatturazione/<id_documento>/segna-pagata` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fatturazione/<id_documento>/stato` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/fatturazione/nuova` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/fatturazione/nuova` | Fatturazione | P0 | `fatturazione.leggi/scrivi` | parcelle, importi e PDF | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/feature-flags` | Feature flag | P0 | `sessione/API tenant-aware` | capability studio e abilitazioni | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/giurisprudenza` | Giurisprudenza | P1 | `sessione/API tenant-aware` | archivio giurisprudenza | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/giurisprudenza/nuova` | Giurisprudenza | P1 | `sessione/API tenant-aware` | archivio giurisprudenza | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/giurisprudenza/nuova` | Giurisprudenza | P1 | `sessione/API tenant-aware` | archivio giurisprudenza | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/global-search` | Ricerca Studio | P1 | `sessione/API tenant-aware` | indici ricerca tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/import/quickorganizer` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/import/quickorganizer/preparazione` | Import Studio Telematico | P2 | `admin.configura oppure fascicoli.scrivi+clienti.scrivi` | sessione preparazione tenant-aware | auth, RBAC dominio, sessione tokenizzata |
| `GET` | `/api/v1/ui/import/quickorganizer/preparazione/<session_id>` | Import Studio Telematico | P2 | `admin.configura oppure fascicoli.scrivi+clienti.scrivi` | stato preparazione senza token né path filesystem | auth, RBAC dominio, sessione tokenizzata |
| `GET` | `/api/v1/ui/import/quickorganizer/preparazione/<session_id>/avviatore.cmd` | Import Studio Telematico | P2 | `admin.configura oppure fascicoli.scrivi+clienti.scrivi` | avviatore locale sessione preparazione | auth, RBAC dominio, token operativo a scadenza |
| `POST` | `/api/v1/ui/import/quickorganizer/preparazione/<session_id>/stato` | Import Studio Telematico | P2 | `sessione tokenizzata preparazione Studio Telematico` | avanzamento preparatore locale | header tokenizzato, digest server-side, nessun tenant_id client |
| `POST` | `/api/v1/ui/import/quickorganizer/preparazione/<session_id>/upload-session` | Import Studio Telematico | P2 | `sessione tokenizzata preparazione Studio Telematico` | sessione upload automatico tenant-aware | header tokenizzato, digest server-side, limite dimensione |
| `POST` | `/api/v1/ui/import/quickorganizer/preparazione/<session_id>/upload-session/<upload_id>/chunk` | Import Studio Telematico | P2 | `sessione tokenizzata preparazione Studio Telematico` | blocco binario pacchetto import | header tokenizzato, digest server-side, path staging confinato |
| `POST` | `/api/v1/ui/import/quickorganizer/preparazione/<session_id>/upload-session/<upload_id>/completa` | Import Studio Telematico | P2 | `sessione tokenizzata preparazione Studio Telematico` | ricomposizione e controllo pacchetto import | header tokenizzato, staging tenant-aware, audit anteprima |
| `POST` | `/api/v1/ui/import/quickorganizer/anteprima` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/import/quickorganizer/esegui` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/import/quickorganizer/upload-session` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/import/quickorganizer/upload-session/<upload_id>/chunk` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/import/quickorganizer/upload-session/<upload_id>/completa` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/impostazioni` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/impostazioni-studio` | Impostazioni | P0 | `admin.configura` | configurazioni studio redatte | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/<section>` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/ai/bootstrap` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/impostazioni/ai/lex-dataset` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/impostazioni/ai/lex-dataset/review` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/ai/lex-dataset/review/<qa_id>` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/impostazioni/ai/status` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/calendari/profili` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/calendari/profili/<profile_id>/elimina` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/calendari/profili/<profile_id>/sincronizza` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/calendari/profili/<profile_id>/stato` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/calendari/rigenera-link` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/notifiche/invia` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/notifiche/link` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/notifiche/promemoria-domani` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/impostazioni/test/<test_id>` | Impostazioni | P0 | `admin.configura` | segreti redatti e configurazioni studio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/incassi-pagamenti` | Incassi e pagamenti | P0 | `fatturazione.leggi/scrivi` | link pagamento e provider | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/incassi-pagamenti/<id_pagamento>/collega` | Incassi e pagamenti | P0 | `fatturazione.leggi/scrivi` | link pagamento e provider | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/incassi-pagamenti/<id_pagamento>/link-pagamento` | Incassi e pagamenti | P0 | `fatturazione.leggi/scrivi` | link pagamento e provider | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/incassi-pagamenti/<id_pagamento>/stato` | Incassi e pagamenti | P0 | `fatturazione.leggi/scrivi` | link pagamento e provider | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/incassi-pagamenti/incasso` | Incassi e pagamenti | P0 | `fatturazione.leggi/scrivi` | link pagamento e provider | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/legal-intelligence` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/legal-intelligence/mediazione` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/legal-intelligence/news` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/local-signer/diagnostics` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/local-signer/diagnostics/latest` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/messaggi` | Messaggi | P1 | `sessione/API tenant-aware` | SMS/WhatsApp e log invio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/messaggi/nuovo` | Messaggi | P1 | `sessione/API tenant-aware` | SMS/WhatsApp e log invio | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/notifiche-legali` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/anteprima-relata` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/area-web-pst` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/bozze-relata` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/comunicazione-cliente` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/modelli-relata` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/notifica` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/notifiche-legali/prova-deposito` | Notifiche legali | P1 | `sessione/API tenant-aware` | relate, destinatari e bozze | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi/<id_preventivo>` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/<id_preventivo>/stato` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/<preventivo_id>/apri-fascicolo` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi/conferimento/<id_conferimento>` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/conferimento/<id_conferimento>/stato` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi/conferimento/nuovo` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/conferimento/nuovo` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi/nuovo` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/nuovo` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi/wizard` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/preventivi/wizard/bootstrap` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/wizard/calculate` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/preventivi/wizard/create` | Preventivi | P0 | `fatturazione.leggi/scrivi` | offerte e conferimenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/privacy/registro` | Registro GDPR | P1 | `sessione/API tenant-aware` | trattamenti e audit privacy | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/profili` | Profili e permessi | P0 | `utenti.leggi/scrivi` | matrice permessi e override | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/profili` | Profili e permessi | P0 | `utenti.leggi/scrivi` | matrice permessi e override | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/profilo` | Profilo utente | P1 | `sessione/API tenant-aware` | dati profilo e permessi correnti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/redazione-atti` | Redazione atti | P1 | `sessione/API tenant-aware` | produzione documenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/redazione-atti/produci` | Redazione atti | P1 | `sessione/API tenant-aware` | produzione documenti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/registro-attivita` | Registro attivita | P0 | `audit.leggi` | PII e log operativi redatti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/ricerca-legale` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/ricerca-legale/mediazione` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/ricerca-legale/news` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/ricerca-legale/ricerca` | Ricerca legale | P1 | `sessione/API tenant-aware` | fonti e cronologia ricerca | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/scadenziario` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/scadenziario/nuova` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/scadenziario/termini/audit` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/scadenziario/termini/calculate` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/scadenziario/termini/crea-scadenza` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/scadenziario/termini/explain` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/scadenziario/termini/override` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/scadenziario/termini/templates` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/scadenziario/termini/validate` | Scadenziario | P1 | `sessione/API tenant-aware` | termini e audit calcolo | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/sito-studio` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/sito-studio/articoli/<int:article_id>/modifica` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/articoli/<int:article_id>/modifica` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/sito-studio/builder` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `DELETE` | `/api/v1/ui/sito-studio/builder/assets/<int:asset_id>` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/assets/upload` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/design` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/genera` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/pages` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `DELETE` | `/api/v1/ui/sito-studio/builder/pages/<int:page_id>` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/pages/<int:page_id>/blocks` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/pages/<int:page_id>/duplicate` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/pages/<int:page_id>/publish` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/pages/<int:page_id>/settings` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/revisions/<int:revision_id>/restore` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/site` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/template` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/builder/valida` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/sito-studio/contatti` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/contatti/<id_contatto>/collega` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/prenotazioni/<id_prenotazione>/stato` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/sito-studio/redazione-ai` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/redazione-ai/articoli/<int:article_id>/genera-immagine` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/redazione-ai/articoli/<int:article_id>/pubblica` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/redazione-ai/articolo/genera` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/sito-studio/redazione-ai/jobs/<int:job_id>/crea-bozza` | Sito Studio | P1 | `admin.configura per scritture` | contenuti pubblici e richieste contatto | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/soggetti` | Soggetti e parti | P1 | `sessione/API tenant-aware` | anagrafiche parti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/soggetti/<id_soggetto>/modifica` | Soggetti e parti | P1 | `sessione/API tenant-aware` | anagrafiche parti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/soggetti/delete` | Soggetti e parti | P1 | `sessione/API tenant-aware` | anagrafiche parti | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/statistiche` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/strumenti-legali/<tool_id>` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/studio` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/studio-modules/<module_id>` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/studio/timbro` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/studio/timbro` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/studio/timbro/preview` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/tariffario` | Tariffario | P1 | `fatturazione.leggi` | calcoli tariffari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/tariffario/<id_voce>` | Tariffario | P1 | `fatturazione.leggi` | calcoli tariffari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/tariffario/calcola` | Tariffario | P1 | `fatturazione.leggi` | calcoli tariffari | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/telematico` | Telematico | P0 | `sessione/API tenant-aware` | PCT/PST/Local Signer | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/telematico/surface/<surface>` | Telematico | P0 | `sessione/API tenant-aware` | PCT/PST/Local Signer | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/template-atti` | Template atti | P1 | `sessione/API tenant-aware` | modelli e compilazione | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/template-atti/catalogo` | Template atti | P1 | `sessione/API tenant-aware` | modelli e compilazione | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/template-atti/compila/<model_code>` | Template atti | P1 | `sessione/API tenant-aware` | modelli e compilazione | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/territorio/comuni` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/timesheet` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/utenti` | Utenti | P0 | `utenti.leggi/scrivi` | account, ruoli, credenziali temporanee | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/utenti/<id_utente>/profilo` | Utenti | P0 | `utenti.leggi/scrivi` | account, ruoli, credenziali temporanee | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/utenti/<id_utente>/reset-password` | Utenti | P0 | `utenti.leggi/scrivi` | account, ruoli, credenziali temporanee | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/utenti/<id_utente>/ruolo` | Utenti | P0 | `utenti.leggi/scrivi` | account, ruoli, credenziali temporanee | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/utenti/<id_utente>/stato` | Utenti | P0 | `utenti.leggi/scrivi` | account, ruoli, credenziali temporanee | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/utenti/nuovo` | Utenti | P0 | `utenti.leggi/scrivi` | account, ruoli, credenziali temporanee | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/wizard-pro` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/wizard-pro/session/<id_sessione>/completo` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/wizard-pro/session/<id_sessione>/step/<int:n>` | API React operativa | P2 | `sessione/API tenant-aware` | payload applicativo tenant-aware | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/workflow-agents` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/workflow-agents/approvals` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/workflow-agents/metrics` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/workflow-agents/preview` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `GET` | `/api/v1/ui/workflow-agents/runs/<run_id>` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/workflow-agents/runs/<run_id>/approve` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |
| `POST` | `/api/v1/ui/workflow-agents/runs/<run_id>/reject` | Regia Agentica | P1 | `permesso agentico dedicato` | piani, approvazioni e audit agentico | auth, tenant-aware, RBAC dominio, guardrail fase 5 |

## Rischi Residui

- Le route legacy non ancora ricostruite restano fuori da questa mappa e devono continuare a usare i decoratori/permessi esistenti.
- Gli smoke cross-tenant autenticati richiedono una API key di studio o credenziali tenant da ambiente, mai committate.
- La fase 6 OpenAPI dovra' trasformare questa mappa in contratti 401/403/400/409/422 verificabili provider-by-provider.

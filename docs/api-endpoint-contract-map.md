# API Endpoint Contract Map

Aggiornato: 2026-05-18.

## Fase 6 API Contract Review

La mappa collega endpoint Flask reali, pagine App V2 e contratti OpenAPI. Gli endpoint P0/P1 sono documentati in `docs/openapi.yaml`; la provider verification copre tutti con errore 401 reale e un campione 200 per le aree operative principali.

## Sommario

- Endpoint React API contrattualizzati: 276.
- Endpoint P0/P1 contrattualizzati: 245.
- Endpoint con provider verification 200 rappresentativa: 31.
- Endpoint con provider verification auth-error: 261.
- Endpoint pubblici Portale Cliente verificati con errore sicuro senza token valido: 15.
- Endpoint P2/P3: mappati e completi per autenticazione/errori; success-body da raffinare quando la pagina passa a priorita superiore.

| Area | Endpoint | Metodo | Pagina | Priorita | OpenAPI | Provider Test | RBAC | Flag | Tenant | Stato |
|------|----------|--------|--------|----------|---------|---------------|------|------|--------|-------|
| Amministrazione database | `/api/v1/ui/admin/database` | `GET` | Amministrazione database | P0 | verified | success+auth-error | `utenti.leggi` | `n/a` | current_tenant | verified |
| Agenda | `/api/v1/ui/agenda` | `GET` | Agenda (/app/agenda) | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.agenda.calendar` | current_tenant | verified |
| Agenda | `/api/v1/ui/agenda/importa` | `GET` | Agenda | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Agenda | `/api/v1/ui/agenda/nuovo/defaults` | `GET` | Agenda | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/amministrazione` | `GET` | Amministrazione (/app/amministrazione) | P2 | complete | auth-error | `sessione/API tenant-aware` | `routes.appV2.admin.home` | current_tenant | complete-auth-error |
| Registro attivita | `/api/v1/ui/audit` | `GET` | Registro attivita | P0 | verified | success+auth-error | `audit.leggi` | `n/a` | current_tenant | verified |
| Registro attivita | `/api/v1/ui/audit/{id_evento}` | `GET` | Registro attivita | P0 | complete | auth-error | `audit.leggi` | `n/a` | current_tenant | complete-auth-error |
| Backup | `/api/v1/ui/backup` | `GET` | Backup | P0 | complete | auth-error | `backup.leggi/esegui` | `n/a` | current_tenant | complete-auth-error |
| Backup | `/api/v1/ui/backup/crea` | `POST` | Backup | P0 | complete | auth-error | `backup.leggi/esegui` | `n/a` | current_tenant | complete-auth-error |
| Backup | `/api/v1/ui/backup/verifica` | `POST` | Backup | P0 | complete | auth-error | `backup.leggi/esegui` | `n/a` | current_tenant | complete-auth-error |
| Bootstrap React | `/api/v1/ui/bootstrap` | `GET` | Bootstrap React | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Sincronizzazione calendari | `/api/v1/ui/calendari/accounts` | `GET` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/accounts/{account_id}/disconnect` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/accounts/{account_id}/sync` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/apple/connect` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/calendars/{calendar_id}/toggle` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/conflicts` | `GET` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/conflicts/{conflict_id}/resolve` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/demo/connect` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/google/callback` | `GET` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/google/connect` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/microsoft/callback` | `GET` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/microsoft/connect` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Sincronizzazione calendari | `/api/v1/ui/calendari/webcal/connect` | `POST` | Sincronizzazione calendari | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/cartelle-condivise` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/dashboard` | `GET` | Portale Clienti (/app/portale-clienti) | P1 | verified | success+auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `routes.appV2.clientPortal.enabled` | current_tenant | verified |
| Portale Cliente | `/api/v1/ui/client-portal/public/appointments/{appointment_id}` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/consents` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/conversation-export` | `GET` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/dashboard` | `GET` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/documents` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/documents/{document_id}/download` | `GET` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/invites/{token}` | `GET` | Portale Cliente | P1 | complete | public-safe-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-public-safe-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/invites/{token}/accept` | `POST` | Portale Cliente | P1 | complete | public-safe-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-public-safe-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/messages` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/notifications/{notification_id}/read` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/preferences` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/profile` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/questionnaires/{questionnaire_id}` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/signatures/{signature_id}/complete` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/public/surveys` | `POST` | Portale Cliente | P1 | complete | client-token-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-client-token-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/appointments` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/conversation-export` | `GET` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/dashboard` | `GET` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/document-requests` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/documents/{document_id}/download` | `GET` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/evidence-packs` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/invites` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/invites/{invite_id}/revoke` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/messages` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/settings` | `GET` | Portale Cliente | P1 | verified | success+auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | verified |
| Portale Cliente | `/api/v1/ui/client-portal/studio/settings` | `POST` | Portale Cliente | P1 | verified | success+auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | verified |
| Portale Cliente | `/api/v1/ui/client-portal/studio/signature-requests` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Portale Cliente | `/api/v1/ui/client-portal/studio/signature-requests/upload` | `POST` | Portale Cliente | P1 | complete | auth-error | `clienti.leggi/scrivi oppure invito cliente valido` | `n/a` | current_tenant | complete-auth-error |
| Clienti | `/api/v1/ui/clienti` | `GET` | Clienti (/app/anagrafiche) | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.clients.list` | current_tenant | verified |
| Clienti | `/api/v1/ui/clienti/{id_cliente}/cartella` | `GET` | Clienti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Clienti | `/api/v1/ui/clienti/{id_cliente}/modifica` | `GET` | Clienti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Clienti | `/api/v1/ui/clienti/delete` | `POST` | Clienti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Clienti | `/api/v1/ui/clienti/nuovo` | `GET` | Clienti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Clienti | `/api/v1/ui/clienti/nuovo/documento/leggi` | `POST` | Clienti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Clienti | `/api/v1/ui/clienti/voce/crea` | `POST` | Clienti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Compensi forensi | `/api/v1/ui/compensi-forensi` | `GET` | Compensi forensi | P1 | verified | success+auth-error | `fatturazione.leggi` | `n/a` | current_tenant | verified |
| Compensi forensi | `/api/v1/ui/compensi-forensi/calcola` | `POST` | Compensi forensi | P1 | complete | auth-error | `fatturazione.leggi` | `n/a` | current_tenant | complete-auth-error |
| Conferimenti | `/api/v1/ui/conferimenti/{conferimento_id}/apri-fascicolo` | `POST` | Conferimenti | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Panoramica | `/api/v1/ui/dashboard` | `GET` | Regia (/app/regia) | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.dashboard.regia` | current_tenant | verified |
| Panoramica | `/api/v1/ui/dashboard/sync-mailboxes` | `POST` | Panoramica | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Email PEC | `/api/v1/ui/email` | `GET` | Email PEC | P0 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Email ordinaria | `/api/v1/ui/email-ordinaria` | `GET` | Email ordinaria | P0 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Email ordinaria | `/api/v1/ui/email-ordinaria/bulk-action` | `POST` | Email ordinaria | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Email ordinaria | `/api/v1/ui/email-ordinaria/messaggio/{id_email}` | `GET` | Email ordinaria | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Email PEC | `/api/v1/ui/email/bulk-action` | `POST` | Email PEC | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Email PEC | `/api/v1/ui/email/messaggio/{id_email}` | `GET` | Email PEC | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli` | `GET` | Fascicoli (/app/fascicoli) | P0 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.cases.list` | current_tenant | verified |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/attivita` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/audit` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/checklist` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/depositi` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/depositi/{deposito_id}/evidence-pack` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/depositi/{deposito_id}/importa-ricevuta` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/depositi/{deposito_id}/timeline` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/depositi/invia` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/depositi/prepara` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/document-slots` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/document-slots/{slot_key}/link` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/document-slots/{slot_key}/validate` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/documenti` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/documenti/{id_doc}/editor` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/lex` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/modifica` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/pagamenti/{kind}` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/predeposito/check` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/regia` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/regia/applica-profilo` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/regia/ricalcola` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/relata` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/scadenze` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/{id_fasc}/stato` | `POST` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/archivio` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/export` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fascicoli e documenti | `/api/v1/ui/fascicoli/nuovo` | `GET` | Fascicoli e documenti | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Fatturazione | `/api/v1/ui/fatturazione` | `GET` | Fatturazione | P0 | verified | success+auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | verified |
| Fatturazione | `/api/v1/ui/fatturazione/{id_documento}` | `GET` | Fatturazione | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Fatturazione | `/api/v1/ui/fatturazione/{id_documento}/annulla` | `POST` | Fatturazione | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Fatturazione | `/api/v1/ui/fatturazione/{id_documento}/segna-pagata` | `POST` | Fatturazione | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Fatturazione | `/api/v1/ui/fatturazione/{id_documento}/stato` | `POST` | Fatturazione | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Fatturazione | `/api/v1/ui/fatturazione/nuova` | `GET` | Fatturazione | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Fatturazione | `/api/v1/ui/fatturazione/nuova` | `POST` | Fatturazione | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Feature flags | `/api/v1/ui/feature-flags` | `GET` | Feature flags | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Giurisprudenza | `/api/v1/ui/giurisprudenza` | `GET` | Giurisprudenza | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Giurisprudenza | `/api/v1/ui/giurisprudenza/nuova` | `GET` | Giurisprudenza | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Giurisprudenza | `/api/v1/ui/giurisprudenza/nuova` | `POST` | Giurisprudenza | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Ricerca globale | `/api/v1/ui/global-search` | `GET` | Ricerca globale | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/anteprima` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/esegui` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione/{session_id}` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione/{session_id}/avviatore.cmd` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione/{session_id}/stato` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione/{session_id}/upload-session` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione/{session_id}/upload-session/{upload_id}/chunk` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/preparazione/{session_id}/upload-session/{upload_id}/completa` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/upload-session` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/upload-session/{upload_id}/chunk` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/import/quickorganizer/upload-session/{upload_id}/completa` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni` | `GET` | Impostazioni | P0 | verified | success+auth-error | `admin.configura` | `n/a` | current_tenant | verified |
| API React operativa | `/api/v1/ui/impostazioni-studio` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/{section}` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/ai/bootstrap` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/ai/lex-dataset` | `GET` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/ai/lex-dataset/review` | `GET` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/ai/lex-dataset/review/{qa_id}` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/ai/status` | `GET` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/calendari/profili` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/calendari/profili/{profile_id}/elimina` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/calendari/profili/{profile_id}/sincronizza` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/calendari/profili/{profile_id}/stato` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/calendari/rigenera-link` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/notifiche/invia` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/notifiche/link` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/notifiche/promemoria-domani` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Impostazioni | `/api/v1/ui/impostazioni/test/{test_id}` | `POST` | Impostazioni | P0 | complete | auth-error | `admin.configura` | `n/a` | current_tenant | complete-auth-error |
| Incassi e pagamenti | `/api/v1/ui/incassi-pagamenti` | `GET` | Incassi e pagamenti | P0 | verified | success+auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | verified |
| Incassi e pagamenti | `/api/v1/ui/incassi-pagamenti/{id_pagamento}/collega` | `POST` | Incassi e pagamenti | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Incassi e pagamenti | `/api/v1/ui/incassi-pagamenti/{id_pagamento}/link-pagamento` | `POST` | Incassi e pagamenti | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Incassi e pagamenti | `/api/v1/ui/incassi-pagamenti/{id_pagamento}/stato` | `POST` | Incassi e pagamenti | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Incassi e pagamenti | `/api/v1/ui/incassi-pagamenti/incasso` | `POST` | Incassi e pagamenti | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Ricerca legale | `/api/v1/ui/legal-intelligence` | `GET` | Lex (/app/lex) | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.legalResearch.home` | current_tenant | verified |
| Ricerca legale | `/api/v1/ui/legal-intelligence/mediazione` | `GET` | Ricerca legale | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Ricerca legale | `/api/v1/ui/legal-intelligence/news` | `GET` | Ricerca legale | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/local-signer/diagnostics` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/local-signer/diagnostics/latest` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Messaggi | `/api/v1/ui/messaggi` | `GET` | Comunicazioni (/app/comunicazioni) | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.comms.deposits` | current_tenant | verified |
| Messaggi | `/api/v1/ui/messaggi/nuovo` | `GET` | Messaggi | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali` | `GET` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/anteprima-relata` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/area-web-pst` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/bozze-relata` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/comunicazione-cliente` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/modelli-relata` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/notifica` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/pratiche/{id_fascicolo}/documenti` | `GET` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Notifiche legali | `/api/v1/ui/notifiche-legali/prova-deposito` | `POST` | Notifiche legali | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi` | `GET` | Mandato (/app/mandato) | P0 | verified | success+auth-error | `fatturazione.leggi/scrivi` | `routes.appV2.billing.quotes` | current_tenant | verified |
| Preventivi | `/api/v1/ui/preventivi/{id_preventivo}` | `GET` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/{id_preventivo}/stato` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/{preventivo_id}/apri-fascicolo` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/conferimento/{id_conferimento}` | `GET` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/conferimento/{id_conferimento}/stato` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/conferimento/nuovo` | `GET` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/conferimento/nuovo` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/nuovo` | `GET` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/nuovo` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/wizard` | `GET` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/wizard/bootstrap` | `GET` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/wizard/calculate` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Preventivi | `/api/v1/ui/preventivi/wizard/create` | `POST` | Preventivi | P0 | complete | auth-error | `fatturazione.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Registro GDPR | `/api/v1/ui/privacy/registro` | `GET` | Registro GDPR | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion` | `GET` | Schede procedura (/app/procedure-completion) | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `routes.appV2.procedureCompletion.home` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion/cards/{card_id}` | `GET` | Procedure Completion Engine | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `n/a` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion/cards/{card_id}/approve` | `POST` | Procedure Completion Engine | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `n/a` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion/cards/{card_id}/publish` | `POST` | Procedure Completion Engine | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `n/a` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion/cards/{card_id}/submit-review` | `POST` | Procedure Completion Engine | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `n/a` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion/gaps` | `GET` | Procedure Completion Engine | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `n/a` | current_tenant | complete-auth-error |
| Procedure Completion Engine | `/api/v1/ui/procedure-completion/preview` | `POST` | Procedure Completion Engine | P1 | complete | auth-error | `procedure_completion.leggi/esegui/approva/pubblica` | `n/a` | current_tenant | complete-auth-error |
| Profili e permessi | `/api/v1/ui/profili` | `GET` | Profili e permessi | P0 | verified | success+auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | verified |
| Profili e permessi | `/api/v1/ui/profili` | `POST` | Profili e permessi | P0 | verified | success+auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | verified |
| API React operativa | `/api/v1/ui/profilo` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti` | `GET` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/anteprima/{model_code}` | `GET` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/clienti` | `GET` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/clienti/{id_cliente}/fascicoli` | `GET` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/fascicoli/{id_fascicolo}/contesto` | `GET` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/genera` | `POST` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/normativa` | `POST` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/normativa/{model_code}` | `GET` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Redazione atti | `/api/v1/ui/redazione-atti/produci` | `POST` | Redazione atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Registro attivita | `/api/v1/ui/registro-attivita` | `GET` | Registro attivita | P0 | complete | auth-error | `audit.leggi` | `n/a` | current_tenant | complete-auth-error |
| Ricerca legale | `/api/v1/ui/ricerca-legale` | `GET` | Ricerca legale | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Ricerca legale | `/api/v1/ui/ricerca-legale/mediazione` | `GET` | Ricerca legale | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Ricerca legale | `/api/v1/ui/ricerca-legale/news` | `GET` | Ricerca legale | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Ricerca legale | `/api/v1/ui/ricerca-legale/ricerca` | `GET` | Ricerca legale | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario` | `GET` | Scadenziario | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Scadenziario | `/api/v1/ui/scadenziario/nuova` | `GET` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/pdf-scadenze/anteprima` | `GET` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/pdf-scadenze/importa` | `POST` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/audit` | `GET` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/calculate` | `POST` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/crea-scadenza` | `POST` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/explain` | `POST` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/override` | `POST` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/templates` | `GET` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Scadenziario | `/api/v1/ui/scadenziario/termini/validate` | `POST` | Scadenziario | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio` | `GET` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/articoli/{article_id}/modifica` | `GET` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/articoli/{article_id}/modifica` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder` | `GET` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/assets/{asset_id}` | `DELETE` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/assets/upload` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/design` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/genera` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/pages` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/pages/{page_id}` | `DELETE` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/pages/{page_id}/blocks` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/pages/{page_id}/duplicate` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/pages/{page_id}/publish` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/pages/{page_id}/settings` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/revisions/{revision_id}/restore` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/site` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/template` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/builder/valida` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/contatti` | `GET` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/contatti/{id_contatto}/collega` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/prenotazioni/{id_prenotazione}/stato` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/redazione-ai` | `GET` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/redazione-ai/articoli/{article_id}/genera-immagine` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/redazione-ai/articoli/{article_id}/pubblica` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/redazione-ai/articolo/genera` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Sito Studio | `/api/v1/ui/sito-studio/redazione-ai/jobs/{job_id}/crea-bozza` | `POST` | Sito Studio | P1 | complete | auth-error | `admin.configura per scritture` | `n/a` | current_tenant | complete-auth-error |
| Soggetti e parti | `/api/v1/ui/soggetti` | `GET` | Soggetti e parti | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| Soggetti e parti | `/api/v1/ui/soggetti/{id_soggetto}/modifica` | `GET` | Soggetti e parti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Soggetti e parti | `/api/v1/ui/soggetti/delete` | `POST` | Soggetti e parti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/statistiche` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/strumenti-legali/{tool_id}` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/studio` | `GET` | API React operativa | P2 | verified | success+auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | verified |
| API React operativa | `/api/v1/ui/studio-modules/{module_id}` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/studio/timbro` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/studio/timbro` | `POST` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/studio/timbro/preview` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Tariffario | `/api/v1/ui/tariffario` | `GET` | Tariffario | P1 | verified | success+auth-error | `fatturazione.leggi` | `n/a` | current_tenant | verified |
| Tariffario | `/api/v1/ui/tariffario/{id_voce}` | `GET` | Tariffario | P1 | complete | auth-error | `fatturazione.leggi` | `n/a` | current_tenant | complete-auth-error |
| Tariffario | `/api/v1/ui/tariffario/calcola` | `POST` | Tariffario | P1 | complete | auth-error | `fatturazione.leggi` | `n/a` | current_tenant | complete-auth-error |
| Telematico | `/api/v1/ui/telematico` | `GET` | Telematico (/app/telematico) | P0 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.telematico.center` | current_tenant | verified |
| Telematico | `/api/v1/ui/telematico/surface/{surface}` | `GET` | Telematico | P0 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Template atti | `/api/v1/ui/template-atti` | `GET` | Documenti (/app/documenti) | P1 | verified | success+auth-error | `sessione/API tenant-aware` | `routes.appV2.documents.list` | current_tenant | verified |
| Template atti | `/api/v1/ui/template-atti/catalogo` | `GET` | Template atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Template atti | `/api/v1/ui/template-atti/compila/{model_code}` | `GET` | Template atti | P1 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/territorio/comuni` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/timesheet` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Utenti | `/api/v1/ui/utenti` | `GET` | Utenti | P0 | verified | success+auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | verified |
| Utenti | `/api/v1/ui/utenti/{id_utente}/profilo` | `POST` | Utenti | P0 | complete | auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Utenti | `/api/v1/ui/utenti/{id_utente}/reset-password` | `POST` | Utenti | P0 | complete | auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Utenti | `/api/v1/ui/utenti/{id_utente}/ruolo` | `POST` | Utenti | P0 | complete | auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Utenti | `/api/v1/ui/utenti/{id_utente}/stato` | `POST` | Utenti | P0 | complete | auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| Utenti | `/api/v1/ui/utenti/nuovo` | `POST` | Utenti | P0 | complete | auth-error | `utenti.leggi/scrivi` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/wizard-pro` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/wizard-pro/session/{id_sessione}/completo` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| API React operativa | `/api/v1/ui/wizard-pro/session/{id_sessione}/step/{n}` | `GET` | API React operativa | P2 | complete | auth-error | `sessione/API tenant-aware` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents` | `GET` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents/approvals` | `GET` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents/metrics` | `GET` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents/preview` | `POST` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents/runs/{run_id}` | `GET` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents/runs/{run_id}/approve` | `POST` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |
| Regia Agentica Studio | `/api/v1/ui/workflow-agents/runs/{run_id}/reject` | `POST` | Regia Agentica Studio | P1 | complete | auth-error | `ai.usa/legal_skills.leggi + permessi azione` | `n/a` | current_tenant | complete-auth-error |

## Note provider verification

- `auth-error` significa che l'endpoint e' invocato dal Flask test client senza credenziali e deve rispondere con errore controllato conforme allo schema errori.
- `success+auth-error` aggiunge una chiamata autenticata 200 su endpoint statici rappresentativi di P0/P1 e delle aree principali.
- `client-token-error` e `public-safe-error` coprono il Portale Cliente: senza token valido l'endpoint deve restare in errore sicuro, senza rivelare tenant, pratica o token.
- Gli endpoint con path parametrici o mutazioni distruttive restano verificati sul contratto di autenticazione/errori e richiedono fixture dominio dedicate prima della promozione a provider success full.

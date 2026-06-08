# Portale Cliente

Aggiornato: 2026-06-08.

Il Portale Cliente espone una console studio in React su `/app/portale-clienti` e una vista cliente pubblica in React su `/portale-cliente`. Le API sono sotto `/api/v1/ui/client-portal/*` e usano dati reali di clienti e fascicoli, senza dati dimostrativi.

## Flussi principali

Studio:

- apre la dashboard Portale Cliente dalla sezione Clienti;
- ricerca il cliente mentre digita nel form invito;
- crea un invito per cliente e pratica;
- quando sceglie il cliente vede solo i fascicoli collegati a quel cliente, con selezione automatica se il fascicolo collegato è unico;
- copia il link sicuro cliente;
- può aprire WhatsApp Web con testo già predisposto e link cliente, senza salvare credenziali WhatsApp nel backend;
- invia messaggi, richieste documento, richieste firma semplice, appuntamenti e pacchetti conclusivi;
- consulta attività, firme, documenti caricati, notifiche e conversazione esportabile.

Cliente:

- apre il link invito;
- accetta privacy e accesso al portale;
- vede la propria pratica, cosa deve fare ora, timeline e notifiche;
- aggiorna anagrafica e preferenze;
- carica documenti;
- completa firme semplici quando abilitate;
- scrive allo studio, risponde ad appuntamenti, questionari e survey.

## Sicurezza

- Il token invito è generato server-side, non è scelto dal client e viene salvato solo come hash SHA-256.
- Il token cliente opaco è firmato e risolto server-side nel tenant corretto.
- Il client non può inviare `tenant_id`, `studio_id`, path filesystem, ruoli o permessi.
- Gli endpoint studio richiedono sessione/API key tenant-aware.
- Gli endpoint cliente richiedono token valido tramite header `X-Client-Portal-Token`, sessione cliente o token invito dove previsto.
- Gli errori pubblici su token non valido restano sicuri e non rivelano tenant, cliente o pratica.
- Upload: MIME consentiti, dimensione massima configurata, nome normalizzato, SHA-256 e storage tenant-aware.
- Le firme sono firme semplici con evidenza auditabile; non vengono presentate come firma qualificata, PAdES o FEQ.

## Persistenza

Schemi:

- SQLite: `pct/sql/20260607_client_portal.sql`;
- PostgreSQL: `pct/sql/20260607_client_portal_postgres.sql`.

Repository:

- `pct/client_portal.py`;
- `ClientPortalRepository` usa SQLite locale o PostgreSQL se configurato;
- DSN PostgreSQL da `IUSENTRA_CLIENT_PORTAL_DATABASE_URL` o `CLIENT_PORTAL_DATABASE_URL`.

Ogni tabella include `tenant_id`. I file caricati sono salvati sotto storage tenant-aware e il payload API non espone percorsi interni.

## Feature Flag

- `routes.appV2.clientPortal.enabled`: abilita console studio e vista cliente, default `on`;
- `routes.appV2.clientPortal.notifications`: notifiche in-app, default `on`;
- `routes.appV2.clientPortal.signatures`: firma semplice con evidenza, default `on`;
- `routes.appV2.clientPortal.webPush`: Web Push cliente, default `off`;
- `routes.appV2.clientPortal.videoCalls`: link videocall governati, default `on`.

## Contratti e UI

- Console studio: `frontend/src/components/ClientPortalPage.tsx` in modalità `studio`;
- vista cliente: lo stesso componente in modalità `client`, senza sidebar studio;
- link cliente: il collegamento completo viene mostrato subito dopo la generazione o rigenerazione dell'invito; nel database resta solo l'hash del token;
- WhatsApp Web: la UI apre `web.whatsapp.com` dal browser dello studio con messaggio precompilato, senza invio automatico server-side;
- videocall: lo studio inserisce un link `http/https` nell'appuntamento e il cliente vede il pulsante `Apri videocall`;
- orari appuntamento: il valore scelto dal browser dello studio viene interpretato in ora italiana, normalizzato in UTC nel salvataggio e mostrato al cliente in formato italiano senza slittamenti;
- client dati: `frontend/src/clientPortalData.ts`;
- bridge applicativo: `web/services/react_client_portal_bridge.py`;
- API blueprint: `web/blueprints/api_v1_client_portal.py`;
- shell: `web/blueprints/client_portal.py`.

Il mockup approvato è in `artifacts/client-portal/2026-06-07-portale-cliente-ui-mockup.html` e la vista cliente completa in `artifacts/client-portal/2026-06-07-portale-cliente-vista-cliente.html`.

## Test Minimi

```powershell
python -m pytest tests/test_client_portal_repository.py tests/test_client_portal_api.py -q --tb=short
python -m pytest tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py tests/test_feature_flags.py tests/test_app_v2_feature_flags.py -q --tb=short
python scripts/react-migration/generate_api_contracts.py --check
python scripts/validate_openapi.py docs/openapi.yaml
python scripts/verify_openapi_provider.py
pnpm --filter @iusentra/studio test
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
```

La verifica finale di prodotto resta sulla copia reale `http://127.0.0.1:8080`, con browser desktop, tablet e mobile.

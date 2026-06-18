# Contratti API App V2

Aggiornato: 2026-05-14, fase 12 `fasereact`.

## Stato

I contratti API App V2 sono ora governati da OpenAPI, mappa endpoint e provider
verification. La fase 1 ha introdotto `GET /api/v1/ui/feature-flags`; le fasi
successive hanno collegato route, flag, RBAC, tenant scope, error schema,
provider verification e CI gate. La fonte runtime resta il codice Flask reale:
non si inventano endpoint non presenti.

Documenti collegati:

- [openapi.yaml](openapi.yaml)
- [api-endpoint-contract-map](api-endpoint-contract-map.md)
- [backend-endpoint-security-map](backend-endpoint-security-map.md)
- [ci-cd-gates](ci-cd-gates.md)
- [PEC audit pipeline](PEC_AUDIT_PIPELINE.md)

## PEC audit-grade

Gli endpoint `/api/pec/*` espongono il controllo automatico PEC end-to-end. Sono autenticati con sessione web oppure API key tenant-aware e non accettano tenant, path o credenziali scelti dal client.

Contratti principali:

- `GET /api/pec/messages`: lista messaggi audit-grade, semaforo qualità, stato firme, validation report sintetico e collegamento fascicolo.
- `GET /api/pec/messages/{message_id}`: dettaglio con MIME hash, parsed JSON corrente, allegati, OCR, firme, confidence per campo, matrice validazione e candidati fascicolo.
- `GET /api/pec/messages/{message_id}/mime`: restituisce il MIME originale come `message/rfc822` senza modificarlo.
- `POST /api/pec/fetch`: ingest IMAP idempotente con dedup `Message-ID` + hash MIME e avvio worker.
- `POST /api/pec/workers/run`: esecuzione controllata dei job `parse/classify/ocr/signcheck/validate/link/digest`.
- `GET /api/pec/digest` e `POST /api/pec/digest/run`: digest giornaliero con nuovi messaggi, fascicoli toccati, anomalie e link diretti.
- `POST /api/pec/messages/{message_id}/salva-fascicolo`, `/richiedi-allegato-mancante`, `/schedula-scadenza`: azioni auditabili. La scadenza è automatica quando `deadline_proposal.auto_create=true` e resta un presidio operativo, non un termine legale conclusivo.
- `POST /api/pec/demo/ingest`: dataset sintetico pubblico per demo locale, senza dati di studio.

Le risposte non includono credenziali IMAP, UID tecnici non necessari, path filesystem o contenuto MIME nel JSON. Il MIME si apre solo dall'endpoint dedicato e ogni azione scrive `pec_audit_log`.

## Endpoint fase 1

### `GET /api/v1/ui/feature-flags`

Autenticazione: sessione web o API key valida dove ammessa dalle API React.

Risposta 200:

```json
{
  "ok": true,
  "flags": {
    "routes.appV2.documents.list": false,
    "routes.appV2.comms.deposits": false,
    "routes.appV2.agenda.calendar": false,
    "routes.appV2.cases.list": false,
    "routes.appV2.settings.studio": false,
    "routes.appV2.notifications.mobilePush": false,
    "routes.appV2.docsPanel": false,
    "notifications.mobilePush": false
  },
  "defaults": {
    "routes.appV2.documents.list": false
  }
}
```

Risposta 401: sessione mancante.

### `POST /api/push/subscribe`

Protetto da `routes.appV2.notifications.mobilePush`; l'alias
`notifications.mobilePush` resta accettato per compatibilita.

Se flag off:

```json
{
  "ok": false,
  "code": "feature_disabled",
  "message": "Funzione non attiva per questo studio."
}
```

## Provider verification

Per ora la verifica e' pytest mirata. La fase OpenAPI dovra' aggiungere:

- schema request/response per fascicoli, documenti, upload, comunicazioni/depositi, scadenze, agenda e notifiche;
- validatore CLI eseguibile;
- job CI che fallisce su drift tra payload reale e schema.

## Legal Skills Engine

Gli endpoint `/api/v1/legal-skills/*` sono registrati in OpenAPI con tag
`Legal Skills`, sicurezza sessione/API key, tenant corrente, RBAC e provider
verification anonima 401. Le API sono dietro `lex.legalSkills.enabled` e
flag specifici per trust layer, custom skill, agenti schedulati e route React.

Contratti principali:

- `GET /api/v1/legal-skills/packs`
- `GET /api/v1/legal-skills/profile`
- `POST /api/v1/legal-skills/profile/cold-start`
- `POST /api/v1/legal-skills/run`
- `GET/POST /api/v1/legal-skills/runs/{run_id}/*`
- `POST /api/v1/legal-skills/trust/check`
- `GET/POST /api/v1/legal-skills/scheduled*`

Il client non puo inviare `tenant_id`, `studio_id`, token o path. Il risultato
espone bozza, note di revisione, citazioni, confidenza e blocco export quando
la base informativa non e' sufficiente.

## Smoke fase 3

`scripts/smoke_app_v2_pages.py` verifica in modo parametrico:

- `GET /api/v1/ui/feature-flags`;
- `GET /app-v2/documenti`, ammesso come 403 flag-off o 200 se il flag e'
  abilitato nello studio;
- `GET /app-v2`, ammesso come 403 flag-off o 200 se la panoramica App V2 e'
  abilitata nello studio.

Le credenziali non sono mai hardcoded: usare `IUSENTRA_BASE_URL`,
`IUSENTRA_SMOKE_USERNAME` e `IUSENTRA_SMOKE_PASSWORD`.

## Routing fase 4

La fase 4 non introduce nuovi endpoint pubblici, ma aggiunge un contratto di
routing interno:

- `build_app_v2_path(...)` costruisce solo target interni `/app-v2`;
- `should_redirect_to_app_v2(...)` permette redirect solo se il feature flag
  pagina e' acceso;
- `get_legacy_fallback_path(...)` mantiene fallback legacy ripulendo query non
  sicure.

`scripts/smoke_app_v2_routing.py` verifica mapping, no-open-redirect, route
legacy accessibili, `/app-v2` flag-off e assenza di redirect esterni. Senza
credenziali puo' eseguire inventario/static checks; con credenziali da env
esegue smoke HTTP autenticato.

## Backend security fase 5

Le API React sotto `/api/v1/ui` applicano un guardrail centrale sui parametri
di controllo server. Dopo autenticazione, query/JSON/form non possono inviare
tenant/studio/user selezionati dal client, token generici, API key o redirect
liberi.

Esempio risposta 400:

```json
{
  "ok": false,
  "message": "Richiesta non consentita.",
  "errors": {
    "security": "La richiesta contiene parametri riservati al controllo server. Rimuovili e ripeti l'operazione."
  },
  "code": "backend_security_control_param",
  "violations": [
    {"source": "query", "key": "tenant_id", "path": "tenant_id"}
  ]
}
```

La risposta non deve contenere valori ricevuti dal client. Le scritture
amministrative legittime restano validate dagli endpoint di dominio e dai loro
permessi, non dal filtro trasversale.

## Fase 6 API Contract Review

Aggiornato: 2026-05-18.

OpenAPI di riferimento: `docs/openapi.yaml`.

Comandi gate:

```powershell
python scripts\react-migration\generate_api_contracts.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
python -m pytest -q tests\test_openapi_contracts_phase6.py --tb=short
```

Risultato di mappatura:

- Endpoint React API contrattualizzati: 282.
- Endpoint P0/P1 con contratto OpenAPI: 247.
- Endpoint con provider verification rappresentativa non-auth-error: 31 totali, includendo success-body autenticati e il controllo backend-security.
- Endpoint con provider verification 401 reale o errore pubblico sicuro: 282.
- Endpoint pubblici Portale Cliente verificati senza token valido: 15.

Standard error schema:

- `ErrorResponse` documenta il formato normalizzato (`ok`, `error`, `message`, `code`, `request_id`, `details`) e i campi legacy reali (`errore`, `codice`) per compatibilita.
- 400, 401, 403, 404, 409, 422, 429 e 500 sono referenziati su ogni operazione; upload aggiunge 413 e 415.
- Il codice `backend_security_control_param` resta lo standard per parametri client riservati al controllo server.

Standard pagination/filtering:

- Liste GET documentano `page`, `page_size`, `q` e `status` come parametri tenant-safe.
- Il client non puo' inviare `tenant_id`, `studio_id`, `user_id`, token o redirect liberi.

Regole operative per nuovi endpoint:

1. Aggiungere l'endpoint Flask con autenticazione e permessi dominio.
2. Eseguire `generate_api_contracts.py` per aggiornare OpenAPI e mappa.
3. Aggiungere fixture provider verification se l'endpoint e' P0/P1 o gestisce file/segreti.
4. Eseguire `validate_openapi.py` e `verify_openapi_provider.py`.
5. Aggiornare documentazione e test collegati prima di promuovere la pagina.

Protezioni sicurezza contrattualizzate:

- RBAC: ogni operazione ha `x-rbac-permission`.
- Tenant: ogni operazione ha `x-tenant-scope: current_tenant`.
- Feature flag: le pagine App V2 riportano `x-feature-flag`; gli altri endpoint indicano `n/a` o route collegata.
- PII/segreti: schemi e descrizioni vietano password hash, token, segreti provider e path filesystem in chiaro.

## Checklist nuovo endpoint

- [ ] Auth sessione/API key tenant-aware.
- [ ] Permesso RBAC dominio.
- [ ] Tenant context server-side, fail-closed in multi-studio.
- [ ] Input validation e blocco parametri server-controlled.
- [ ] Response schema e `ErrorResponse`.
- [ ] OpenAPI e mappa endpoint aggiornate.
- [ ] Provider verification o limite documentato per endpoint parametrico/upload.
- [ ] Test 401/403/400/422/success path.
- [ ] PII review e audit se legge/scrive dati sensibili.

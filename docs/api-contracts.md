# Contratti API App V2

Aggiornato: 2026-05-13.

## Stato

La fase 1 aggiunge il contratto leggero `GET /api/v1/ui/feature-flags`. La fase
2 non introduce nuovi endpoint applicativi: censisce le API gia' collegate alle
route in `docs/app-v2-page-registry.md` e aggiunge uno smoke script
parametrico. La specifica OpenAPI completa verra' estesa nelle fasi dedicate,
senza inventare endpoint non presenti.

## Endpoint fase 1

### `GET /api/v1/ui/feature-flags`

Autenticazione: sessione web o API key valida dove ammessa dalle API React.

Risposta 200:

```json
{
  "ok": true,
  "flags": {
    "routes.appV2.docsPanel": false,
    "routes.appV2.commsDeposits": false,
    "routes.appV2.uploadClassification": false,
    "routes.appV2.deadlines": false,
    "routes.appV2.agenda": false,
    "routes.appV2.caseFiles": false,
    "notifications.mobilePush": false
  },
  "defaults": {
    "routes.appV2.docsPanel": false
  }
}
```

Risposta 401: sessione mancante.

### `POST /api/push/subscribe`

Protetto da `notifications.mobilePush`.

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

## Smoke fase 2

`scripts/smoke_app_v2_pages.py` verifica in modo parametrico:

- `GET /api/v1/ui/feature-flags`;
- `GET /app-v2/documenti`, ammesso come 403 flag-off o 200 se il flag e'
  abilitato nello studio;
- `GET /app-v2`.

Le credenziali non sono mai hardcoded: usare `IUSENTRA_BASE_URL`,
`IUSENTRA_SMOKE_USERNAME` e `IUSENTRA_SMOKE_PASSWORD`.

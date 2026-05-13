# Contratti API App V2

Aggiornato: 2026-05-13.

## Stato

La fase 1 aggiunge il contratto leggero `GET /api/v1/ui/feature-flags`. La fase
2 censisce le API gia' collegate alle route in
`docs/app-v2-page-registry.md`. La fase 3 estende quel contratto con flag
canonici `routes.appV2.<area>.<pagina>` default-off, usati sia dal backend
`/app-v2` sia dalla shell frontend per bloccare menu, pagina e chiamate dati.
La specifica OpenAPI completa verra' estesa nelle fasi dedicate, senza
inventare endpoint non presenti.

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

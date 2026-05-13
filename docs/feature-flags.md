# Feature flag IUSENTRA

Aggiornato: 2026-05-13.

## Principio

I flag della migrazione React/App V2 sono default-off. Servono a introdurre capability nuove o sperimentali senza spegnere le superfici React gia' promosse come operative nel manifest.

## Flag attivi nelle fasi 1-2

| Flag | Variabile env | Default | Ambito |
| --- | --- | --- | --- |
| `routes.appV2.docsPanel` | `IUSENTRA_FF_ROUTES_APPV2_DOCS_PANEL` | off | `/app-v2/documenti` |
| `routes.appV2.commsDeposits` | `IUSENTRA_FF_ROUTES_APPV2_COMMS_DEPOSITS` | off | `/app-v2/comunicazioni` |
| `routes.appV2.uploadClassification` | `IUSENTRA_FF_ROUTES_APPV2_UPLOAD_CLASSIFICATION` | off | upload/classificazione documenti App V2 |
| `routes.appV2.deadlines` | `IUSENTRA_FF_ROUTES_APPV2_DEADLINES` | off | `/app-v2/scadenziario` |
| `routes.appV2.agenda` | `IUSENTRA_FF_ROUTES_APPV2_AGENDA` | off | `/app-v2/agenda` |
| `routes.appV2.caseFiles` | `IUSENTRA_FF_ROUTES_APPV2_CASE_FILES` | off | `/app-v2/fascicoli` |
| `notifications.mobilePush` | `IUSENTRA_FF_NOTIFICATIONS_MOBILE_PUSH` | off | Web Push dispositivo |

## Configurazione

Si puo' usare una variabile per singolo flag:

```bash
IUSENTRA_FF_NOTIFICATIONS_MOBILE_PUSH=1
```

Oppure un JSON unico:

```bash
IUSENTRA_FEATURE_FLAGS='{"routes.appV2.docsPanel":true,"notifications.mobilePush":true}'
```

Valori accettati per `true`: `1`, `true`, `yes`, `on`, `si`.
Valori accettati per `false`: `0`, `false`, `no`, `off`.

## API e bootstrap

`GET /api/v1/ui/feature-flags` restituisce lo stato pubblico dei flag per la sessione autenticata.

La shell React riceve gli stessi flag nel bootstrap `iusentra-react-bootstrap`, cosi' il frontend puo' nascondere le superfici non abilitate senza chiamare API sperimentali.

## Comportamento flag-off

- route sperimentali `/app-v2/<area>`: HTTP 403 con messaggio operativo;
- Web Push: il frontend mostra che il canale non e' attivo e non chiama `/api/push/public-key`, `/api/push/subscribe` o `/api/push/test`;
- backend: le azioni sensibili protette da flag restituiscono `403` e registrano `policy_denied`;
- toggle governati: `set_feature_flag(...)` registra `feature_flag_toggled` quando viene fornito il gestore audit.

## Rollback rapido

Spegnere il flag via env o JSON, riavviare app e worker web. Non serve migrazione dati.

## Registro fase 2

Il mapping pagina/flag e' ora censito in `docs/app-v2-page-registry.md` e
generato da `scripts/react-migration/generate_app_v2_page_registry.py`. Le
route sperimentali App V2 con flag restano default-off; le route ufficiali gia'
`react_operational_full` restano governate dal manifest e dal route gate, non
da un flag di rollout separato.

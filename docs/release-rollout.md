# Release rollout App V2

Aggiornato: 2026-05-13.

## Strategia

Le nuove capability App V2 partono con flag spento. Ogni rollout richiede metriche di salute, smoke mirato e possibilita di spegnimento entro 2 ore.

## Percentuali

| Step | Azione | Osservare |
| --- | --- | --- |
| 1% | abilita su uno studio interno o tenant pilota | errori 4xx/5xx, tempi route, console browser |
| 10% | abilita su pochi studi operativi | ticket utente, denial RBAC, payload incompleti |
| 50% | abilita su studi rappresentativi | carico API, latenza bootstrap, worker e notifiche |
| 100% | abilita come comportamento ordinario | regressioni, fallback legacy, tempi post-deploy |

## Metriche

- `/api/pronto` 200 e versione attesa;
- container app, worker, Redis, Caddy/Nginx healthy;
- tempi route rappresentative sotto baseline documentata;
- nessun errore console sulle pagine toccate;
- nessun testo tecnico vietato nella UI;
- nessun accesso cross-tenant nei log/test.

## Alert

Aprire incidente se compaiono:

- 500 su API App V2;
- 403 inattesi per ruoli ammessi;
- payload con dati di altro tenant;
- chiamate Web Push quando `notifications.mobilePush` e' spento;
- peggioramento evidente del primo contenuto React su percorsi caldi.

## Rollback entro 2 ore

1. Spegnere il flag env o `IUSENTRA_FEATURE_FLAGS`.
2. Riavviare app e worker web.
3. Verificare `/api/v1/ui/feature-flags`.
4. Ripetere smoke browser sulla pagina interessata.
5. Se il bug riguarda codice non isolabile da flag, revertire il commit della fase e ridistribuire.

## Smoke post deploy

Comandi minimi:

```bash
curl -fsS https://app.iusentra.it/api/pronto
curl -fsS https://app.iusentra.it/api/v1/ui/feature-flags
```

Per Web Push, autenticarsi con sessione tenant e verificare che `/api/push/public-key` non esponga mai private key.

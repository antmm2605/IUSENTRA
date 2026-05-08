# Tranche 26a - Studio / Amministrazione operational report

Generato: 2026-05-08

## Route convertite

- `/studio`
- `/amministrazione`

## Stato prima

- Entrambe erano `react_bridge`.
- `/studio` esponeva ancora CTA primaria verso impostazioni legacy.
- I bridge dichiaravano `writes=legacy_routes`.

## Stato dopo

- Entrambe sono `react_operational_full`.
- Payload JSON read-only con `writes=none`, `operational=true`, `mock_fallback=false`, `secrets_exposed=false`.
- UI con KPI reali, salute sistema, permessi/sessione, moduli React operativi e moduli legacy protetti.

## Endpoint JSON creati o consolidati

- `GET /api/v1/ui/studio`
- `GET /api/v1/ui/amministrazione`

## LegacyPostForm rimossi

- Nessun `LegacyPostForm` presente in `StudioPage`.
- Nessun `LegacyPostForm` presente in `AmministrazionePage`.

## Link legacy rimasti e perché

- `/impostazioni`, `/impostazioni-studio`, `/impostazioni/calendario`, `/impostazioni/pagamenti`, `/sincronizzazione-calendari`: impostazioni sensibili legacy protette.
- `/servizi-telematici`: telematico protetto fuori dallo hub.
- `/sito-studio/builder`: builder legacy protetto.

## Impostazioni lasciate legacy

- PEC/SMTP.
- Firma digitale.
- Calendari/OAuth.
- Provider pagamenti e webhook.
- Scheduler/sincronizzazioni.

## Telematico lasciato legacy

- PST/PDP/PAT, portali, firme, deposito e servizi telematici non sono stati sbloccati.

## Dati sensibili protetti

- Nessun payload serializza password, hash, token, chiavi API, provider secret, webhook secret, OAuth, PEC/SMTP, path assoluti o stack trace.

## Moduli operativi mostrati

- Utenti, nuovo utente, profili, audit, registro attivita, backup.
- Fatturazione, nuova fattura, incassi/pagamenti.
- Preventivi, nuovo preventivo, conferimento, compensi forensi, tariffario.
- Sito Studio e contatti sito.

## Moduli legacy mostrati

- Impostazioni sensibili e canali protetti.
- Sincronizzazione calendari.
- Servizi telematici.
- Builder Sito Studio.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-26a-studio-amministrazione-operational.mjs`
- `node scripts/react-migration/check-tranche-26a-no-settings-secret-leak.mjs`
- `python scripts/react-migration/check-tranche-26a-studio-amministrazione-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

Esito: tutti verdi.

## Rischi residui

- La pagina aggrega solo indicatori sicuri; le impostazioni operative restano volutamente legacy.
- Lo stato backup dipende dal runtime backup disponibile nello studio.

## Rollback

- Reimpostare `/studio` e `/amministrazione` a `react_bridge` nel manifest.
- Ripristinare i bridge/data client/componenti precedenti dalla commit precedente.
- Il gate protegge già `/studio/*`, `/amministrazione/*` e impostazioni.

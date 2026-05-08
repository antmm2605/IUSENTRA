# Tranche 27a - Sito Studio operational report

Generato: 2026-05-08

## Route convertite

- `/sito-studio`
- `/sito-studio/contatti`

## Stato prima

- Entrambe erano `react_bridge`.
- `SitoStudioPage` usava `LegacyPostForm` per azioni contatti/prenotazioni.
- Builder/dashboard legacy erano CTA primarie.

## Stato dopo

- Entrambe sono `react_operational_full`.
- `/sito-studio` legge dashboard, contenuti pubblici sicuri, KPI e anteprima via JSON read-only.
- `/sito-studio/contatti` legge contatti/prenotazioni reali e usa API JSON per le azioni legacy supportate.

## Endpoint JSON creati

- `GET /api/v1/ui/sito-studio`
- `GET /api/v1/ui/sito-studio/contatti`
- `POST /api/v1/ui/sito-studio/contatti/<id_contatto>/collega`
- `POST /api/v1/ui/sito-studio/prenotazioni/<id_prenotazione>/stato`

## LegacyPostForm rimossi

- Rimosso dal flusso principale `SitoStudioPage`.

## Link legacy rimasti e perché

- `/sito-studio/builder`: builder/editor/pubblicazione avanzata restano legacy protetti.
- `/sito-studio?_legacy=1` e `/sito-studio/contatti?_legacy=1`: solo sezione `Rollback tecnico`.

## Builder lasciato legacy

- Nessuna modifica a builder, editor contenuti o pubblicazione avanzata.
- `/sito-studio/builder` resta `legacy_operational` e `unlockFromGate=false`.

## Invii/notifiche non introdotti

- Nessun invio email/SMS/WhatsApp.
- Nessuna automazione o scheduler introdotti.

## Dati sensibili protetti

- Nessun payload serializza password, token, chiavi API, provider secret, webhook secret, SMTP/PEC, path assoluti, IP/raw headers o stack trace.

## Azioni contatti convertite

- Collegamento a cliente esistente.
- Creazione cliente potenziale da richiesta contatto, riusando il servizio legacy.
- Approvazione/rifiuto prenotazione, riusando il servizio legacy con audit.

Azioni non supportate dal backend legacy e quindi non inventate:

- Cambio stato contatto.
- Archiviazione contatto.
- Nota interna.
- Assegnazione operatore.
- Collegamento fascicolo.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-27a-sito-studio-operational.mjs`
- `node scripts/react-migration/check-tranche-27a-no-sito-secret-leak.mjs`
- `python scripts/react-migration/check-tranche-27a-sito-studio-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

Esito: tutti verdi.

## Rischi residui

- Stato contatto, note, archiviazione, assegnazione e collegamento fascicolo richiedono estensione reale del repository legacy prima di diventare azioni JSON.
- Builder/pubblicazione avanzata restano legacy protetti.

## Rollback

- Reimpostare `/sito-studio` e `/sito-studio/contatti` a `react_bridge` nel manifest.
- Ripristinare il precedente `SitoStudioPage` e il bridge dalla commit precedente.
- Il gate protegge già `/sito-studio/builder` e gli altri subpath.

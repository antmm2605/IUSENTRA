# Tranche 24A - Tariffario React operativo full

## Route convertita

- `/tariffario`

## Stato prima

- `react_operational_partial` / `react_bridge`
- `/tariffario/*` legacy/protetto

## Stato dopo

- `/tariffario`: `react_operational_full`
- `/tariffario/*`: legacy/protetto

## LegacyPostForm rimossi

- Nessun `LegacyPostForm` nel flusso principale.
- Il calcolo usa `calculateTariffario()` e `apiPostJson`.

## Link legacy rimasti e perche

- `?_legacy=1` resta solo rollback tecnico.

## Endpoint JSON creati

- `GET /api/v1/ui/tariffario`
- `GET /api/v1/ui/tariffario/<id_voce>`
- `POST /api/v1/ui/tariffario/calcola`

## Permessi controllati

- `_richiedi_auth` e controllo lettura/calcolo prima di payload e simulazione.

## Audit preservato

- Il calcolo resta instradato al backend Python e registra audit quando supportato.

## UI state implementati

- Loading, calculating, saving, success, error, validation e empty state.

## Voci tariffarie backend

- Versioni, aree, procedimenti, fasi, voci e metadati arrivano dal bridge backend.

## Scaglioni backend

- Gli scaglioni sono solo renderizzati se arrivano dal backend.

## Calcolo backend preservato

- React invia input e mostra il risultato restituito dal backend.

## DM55 backend preservato

- Nessuna formula DM55 o tabella canonica in React.

## Risultato backend mostrato

- Riepilogo e risultato usano la risposta JSON backend.

## Collegamento compensi/preventivi

- Link operativi a `/compensi-forensi` e `/preventivi/nuovo`; azioni mutative restano supportate solo se il backend le espone.

## PDF/DOCX non introdotti

- Nessuna generazione PDF/DOCX in React.

## Nessuna formula hardcoded

- Guardrail 24A vieta formule, scaglioni e coefficienti frontend.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-24a-tariffario-operational.mjs`
- `node scripts/react-migration/check-tranche-24a-no-tariffario-frontend-calculation.mjs`
- `python scripts/react-migration/check-tranche-24a-tariffario-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Rischi residui

- Harness Flask autenticato non disponibile negli script statici.

## Rollback

- `GET /tariffario?_legacy=1` resta disponibile come rollback tecnico.

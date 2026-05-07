# Tranche 23A - Audit compensi forensi

## Route legacy
- `/compensi-forensi`: superficie di accesso ai parametri forensi e al motore economico.
- `/tariffario`: catalogo tariffario backend collegato.
- `/preventivi` e `/preventivi/nuovo`: flusso mandato collegabile ma non modificato impropriamente.

## Contratto legacy rilevato
- Capture non autenticata: redirect a login, coerente con sessione obbligatoria.
- Handler Flask/tariffario: dati da tabelle normative e servizi backend esistenti.
- Template legacy: non rimosso.
- POST legacy/servizi: calcolo compensi tramite backend tariffario; creazione preventivo diretta non esposta come nuova azione React se non supportata.

## Strutture dati
- Parametri: area, procedimento/regola, fase, valore controversia, complessita, opzioni fiscali come input.
- Aree/procedimenti/fasi: lette da tabelle normative/backend.
- Log calcoli: audit tariffario/backend presente come fonte, salvataggio dedicato non esposto se non supportato.
- Calcolo DM55/compensi: backend canonico, nessuna formula React.

## Gap per react_operational_full
- GET JSON `/api/v1/ui/compensi-forensi`.
- POST JSON `/api/v1/ui/compensi-forensi/calcola`.
- UI form operativo con risultato backend.
- Check anti-calcolo frontend.
- Manifest/report/validazione.

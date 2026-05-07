# Tranche 25A - Audit registro audit e attivita

## Route legacy
- `/audit`: registro audit applicativo.
- `/registro-attivita`: vista registro attivita collegata all'audit.

## Contratto legacy rilevato
- Capture non autenticata: redirect a login, coerente con sessione obbligatoria.
- Handler legacy: gestione audit utenti in `pct/auth.py` e superfici Flask amministrative.
- Template legacy: non rimosso.
- Permessi richiesti: `audit.leggi`; export CSV preservato come backend.
- POST legacy: azioni letto/risolto/nota non risultano esposte come mutazioni legacy generali.

## Struttura evento
- Evento: id, timestamp, utente, azione, risorsa, dettagli, IP, esito.
- Campi sensibili possibili nei dettagli: credenziali, token, hash, secret, stack trace; vanno redatti lato backend.
- Payload raw: non deve essere renderizzato in React se non sanificato.
- Export: `/audit/esporta.csv` come link backend sicuro.

## Gap per react_operational_full
- GET JSON `/api/v1/ui/audit`.
- GET JSON `/api/v1/ui/registro-attivita`.
- GET JSON dettaglio `/api/v1/ui/audit/<id_evento>`.
- Bridge con redazione payload.
- UI dettaglio evento senza HTML raw.
- Check anti-leak.

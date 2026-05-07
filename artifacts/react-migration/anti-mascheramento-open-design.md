# Parte 12A - Open Design pilota utenti

Generato: 2026-05-07

## Prima: legacy-masked

- `/utenti/nuovo` era servita in React solo come superficie di ingresso.
- Il flusso principale passava da `LegacyPostForm` e POST Flask legacy.
- Il link `?_legacy=1` era presente nel perimetro operativo e non distingueva in modo netto rollback tecnico e azione primaria.
- Loading, successo, errore di validazione, errore permessi e errore server non erano governati dalla UI React del modulo pilota.

## Dopo: operational React

- `/utenti/nuovo` usa un form React dedicato, senza `LegacyPostForm` nel flusso principale.
- Il salvataggio passa da `apiPostJson` verso `POST /api/v1/ui/utenti/nuovo`.
- I campi non sensibili sono controllati nello stato React; la password resta in input ref e viene svuotata dopo submit o successo.
- Il fallback legacy resta visibile solo in sezione `Rollback tecnico`, non come CTA primaria.

## Token e stile

- Layout, superfici, input, pulsanti e alert usano classi del modulo `UtentiPage.css`.
- I colori passano da token CSS esistenti (`--iu-*`, `--iu-od-*`, variabili semantic/alert) e non da nuovi valori hardcoded.
- Nessuna dipendenza nuova, nessun Bootstrap nel modulo pilota, nessuno stile inline.

## Stati UI

- `idle`: form modificabile, CTA primaria attiva.
- `loading`: submit disabilitato e testo di invio in corso.
- `success`: messaggio conferma, azione verso `/utenti`, refresh dati.
- `validation error`: errori campo mostrati vicino ai campi e riepilogo generale.
- `permission error`: alert dedicato per permesso mancante.
- `server error`: alert dedicato senza stack trace o dettagli sensibili.

## Accessibilita

- Focus ring visibile su input, select e bottoni.
- Campi obbligatori con `required`, `aria-invalid` e messaggi collegati.
- Alert con `role="status"` o `role="alert"` secondo criticita.
- Griglia responsive desktop/tablet/mobile senza sovrapposizione testo.


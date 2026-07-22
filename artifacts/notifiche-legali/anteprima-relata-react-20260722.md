# Anteprima relata React — allineamento e destinatari

Data: 22/07/2026  
Perimetro: `Notifiche legali` lato studio, fase `Relata e invio controllato`.

## Difetto analizzato

Il cambio di modello, caso di notifica, destinatari o documenti poteva lasciare visibile una risposta precedente dell'API di anteprima. La chiave di aggiornamento osservava gli identificativi dei documenti, ma non l'intero payload realmente trasmesso; inoltre una richiesta più lenta poteva arrivare dopo quella nuova e sovrascriverla. Una bozza manuale poteva quindi apparire ancora valida dopo la modifica di un dato giuridicamente rilevante.

## Correzione applicata

- La chiave dell'anteprima deriva ora dal payload controllato completo usato dalla notifica: pratica, modello, caso, campi, destinatari reali e documenti reali.
- Ogni nuova richiesta annulla quella precedente tramite `AbortController`; un identificativo progressivo impedisce a una risposta superata di aggiornare lo stato.
- Il debounce è ridotto a 250 ms e la UI mostra subito `Ricalcolo in corso`, senza esporre il testo della precedente anteprima.
- Modello e caso effettivamente applicati sono indicati accanto all'anteprima compilata.
- Se cambia un input giuridicamente rilevante, anteprima e bozza vengono svuotate e riallineate. Una bozza manuale precedente viene esclusa con messaggio esplicito; non viene persa o presentata silenziosamente come valida.
- La stessa chiave completa presidia l'invalidazione della firma della relata già esistente.
- Il riepilogo mostra tutti i destinatari trasmessi al controllo, il ruolo, la fonte PEC, l'eventuale parte rappresentata e il numero di indirizzi PEC distinti.
- Il testo legale e le regole del backend non sono stati modificati.

## File interessati

- `frontend/src/components/NotificheLegaliPage.tsx`
- `frontend/src/components/NotificheLegaliPage.css`
- `frontend/src/notificheLegaliData.ts`
- `tests/test_notifiche_legali_preview_ui.py`

## Verifiche

- `npm --prefix frontend run typecheck`: superato.
- `python -m pytest -q tests/test_notifiche_legali_preview_ui.py`: superato, 3 test.
- `python -m pytest -q tests/test_notifiche_legali.py -k "ui_notifiche_legali"`: superato, 6 test.
- `python -m pytest -q tests/test_utf8_integrity.py`: superato, 4 test.
- `node frontend/scripts/check-react-contracts.mjs`: superato.
- `git diff --check` sui cinque file della tranche: superato.
- `python tools/codex_harness/run_codex_quality_gate.py --mode ui-support`: non superato nello scope check perché la worktree condivisa contiene numerosi file e asset preesistenti fuori dal perimetro `ui-support`; il gate non ha segnalato un errore specifico nei file di questa tranche.
- Prova nel browser reale su `127.0.0.1:8080`: non verificata in questa tranche concorrente; resta obbligatoria prima di dichiarare il flusso completato.

## Limiti e sicurezza

Nessuna PEC è stata inviata, nessuna firma è stata prodotta e nessun dato del tenant è stato modificato. Questa tranche riguarda esclusivamente coordinamento e presentazione del payload React già governato dal backend.

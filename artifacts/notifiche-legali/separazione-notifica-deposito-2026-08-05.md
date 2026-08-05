# Separazione notifica e deposito - 05/08/2026

## Perimetro

Questa nota riguarda solo la creazione della relata, l'attestazione di conformità e l'invio PEC della notifica L. 53/1994 dal PC locale dell'avvocato.

Il deposito telematico è un flusso distinto: non viene usato per decidere se la notifica può essere inviata e non riceve controlli sugli allegati della PEC di notifica.

## Regola applicata agli allegati della notifica

Gli allegati selezionati o inseriti dall'avvocato nella notifica non sono sottoposti a blocco per confronto di impronta con dati precedenti del form.

Durante la preparazione della PEC locale il software:

- legge il file reale salvato nel fascicolo;
- allega quel contenuto alla PEC locale;
- calcola l'impronta SHA-256 del contenuto effettivamente allegato;
- non blocca l'invio per una vecchia impronta diversa presente nel payload.

Il vecchio blocco sull'impronta diversa degli allegati è stato rimosso dal perimetro notifiche.

## Stato test

Guardrail mirato: la preparazione PEC locale viene provata con impronte stale volutamente diverse dal contenuto reale, e deve comunque produrre gli allegati effettivi del fascicolo.

## Aggiornamento 05/08/2026 - separazione definitiva UI/API

Perimetro corretto dopo confronto con il decompilato Studio Telematico:

- `FormSentMailBee.CreateRelataNotifica` genera la relata, la firma sul PC e la aggiunge agli allegati del messaggio.
- `FormSentMailBee.buttonSendMail_Click` prepara e invia la PEC dal client locale, non dal server IUSENTRA.
- I rami `IsNotificaMezzoPEC` e `IsDepositoTelematico` restano separati: la notifica non eredita controlli del deposito.

Modifica applicata:

- `/notifiche-legali` non espone più tab, card, step, azioni o contratti di deposito.
- Il bridge React non pubblica più `provaDeposito`, `depositoChecklist` o `depositProofWithOriginalReceipts`.
- La rotta `/api/v1/ui/notifiche-legali/prova-deposito` è stata rimossa.
- Il catalogo modelli Notifiche non contiene più il workflow `workflow_deposito_area_web_pst` né testi di deposito nella nota di mancata consegna.
- Il validatore della prova successiva alla notifica è stato spostato in `pct.prova_deposito_notifica`, fuori dal motore `pct.notifiche_legali`.
- Il contratto dati della pagina Notifiche usa `provvedimento.data_rilascio`, `provvedimentoDataRilascio`, `dataRilascio`, `rilascioId` e `idRilascioEsterno`; non usa più campi `deposito` per relata o attestazione.
- `Invia PEC` resta nel perimetro notifica: firma la relata corrente, allega la relata firmata, aggiunge l'attestazione quando richiesta e poi chiede la password PEC per l'invio locale.

Test eseguiti:

- `python -m pytest tests/test_notifiche_legali.py -q`
- `python -m pytest tests/test_telematic_registry_fail_closed.py -q`
- `python -m pytest tests/test_regia_ui_react.py -q`

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
- Il pulsante `Invia PEC` non mostra più la descrizione tecnica lunga del flusso locale; all'avvocato resta visibile solo l'azione operativa.

Test eseguiti:

- `python -m pytest tests/test_notifiche_legali.py -q`
- `python -m pytest tests/test_telematic_registry_fail_closed.py -q`
- `python -m pytest tests/test_regia_ui_react.py -q`

## Aggiornamento 06/08/2026 - conferma invio PEC locale

Perimetro: solo notifica L. 53/1994 e invio PEC locale tramite IUSENTRA Local Signer.

Correzione applicata:

- la password PEC digitata dall'avvocato nella conferma `Invia PEC` non viene più tagliata o normalizzata prima della chiamata locale a `127.0.0.1:27272/pec/send`;
- resta bloccato soltanto il campo vuoto;
- il riepilogo di conferma mostra i dati realmente passati al Local Signer: mittente PEC, username PEC e server SMTP con porta;
- nessun invio SMTP viene eseguito dal server IUSENTRA.

Controllo dati locale:

- Local Signer raggiungibile su `127.0.0.1:27272`;
- configurazione PEC tenant `tenant-8bf98719c459`: mittente `roberto.montagnese@coapalmi.legalmail.it`, SMTP `sendm.cert.legalmail.it:465`, password presente;
- il messaggio di errore visto dall'utente verso `smtps.pec.aruba.it:465` non coincide con la configurazione PEC tenant-aware locale e va quindi ricondotto a bundle/sessione non aggiornati o a una diversa configurazione caricata nella pagina.

Verifica aggiuntiva sul PC dell'avvocato:

- Local Signer installato aggiornato e riavviato a `1.6.104`;
- test con SMTP finto: la password arriva al login esattamente come digitata, senza `trim`;
- test SMTP reale senza invio PEC: il Local Signer usa `sendm.cert.legalmail.it:465`, quindi non usa Aruba; il provider risponde però `Autenticazione SMTP PEC locale non riuscita`, da trattare come combinazione username/password/mittente non accettata da Legalmail;
- pacchetti Local Signer rigenerati per Windows, macOS e Linux: `SetupLocalSigner-1.6.104.exe`, `InstallaLocalSigner-1.6.104.command`, `InstallaLocalSigner-1.6.104.run`.

Test eseguiti dopo la correzione:

- `python -m pytest tests/test_local_pec_bridge.py -q`
- `python -m pytest tests/test_local_signer.py::test_endpoint_pec_locale_viene_dispatchato_dal_local_signer -q`
- `python -m pytest tests/test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q`
- `python -m pytest tests/test_notifiche_legali.py::test_api_react_notifiche_legali_invio_locale_usa_allegati_reali_message_id_e_presidio -q`
- `npm --prefix frontend run typecheck`
- `npm --prefix frontend run test:notifiche-legali-presidi:bundle`
- `npm --prefix frontend run build:vite`

# Prova reale server deposito fascicolo E5AE4668

Data incarico: 16 giugno 2026.

Questo file è la traccia operativa dell'incarico corrente e va riletto dopo ogni compattazione prima di proseguire sul deposito.

## Incarico ricevuto

- Ambiente di prova reale: `https://app.iusentra.it`.
- Fascicolo da usare: `E5AE4668`.
- Riferimento visibile: `2026/330`.
- Fascicolo: `Marchetti c. MIM`.
- Materia/oggetto: `Carta docente`.
- Area: civile/lavoro secondo il profilo deposito risolto dal software.
- Cliente: `Marchetti Lucia`.
- Accesso: credenziali fornite dall'utente per la sola prova; non vengono salvate in questo file.
- Interfaccia: React, senza percorsi legacy o fallback `?_legacy=1`.
- Vincolo esplicito: nessun backup per questa attività.
- Vincolo esplicito: nessun invio PEC reale e nessun deposito reale.

## Cosa deve essere verificato

1. Aprire sul server la pagina React del fascicolo e il percorso `Prepara deposito`.
2. Eseguire prova visiva reale con browser visibile: pagina iniziale, scroll completo, fasi deposito, pannelli, pulsanti, testi, card, responsive se il flusso richiede adattamenti.
   - Il controllo visivo deve includere card, testi, formattazione, layout, visibilità, bottoni, select, checkbox, stati di caricamento, stati di errore/successo e leggibilità completa dei campi.
   - Se un pannello è troppo denso o poco intuitivo, va corretto prima del report e riverificato nel browser.
   - Per il deposito la UI deve lavorare a fasi, con un pannello operativo alla volta, e il pannello documenti deve permettere di visualizzare tutti i documenti del fascicolo, selezionare quelli da inviare oppure inviarli tutti, classificarli come atto principale/procura/allegato/prova/fuori busta e indicare quelli da firmare.
3. Generare il pacchetto/busta di prova fermandosi prima dell'invio.
   - La prova deve comportarsi come deposito reale fino alla generazione busta, ma non deve procedere all'invio PEC reale.
   - La busta/pacchetto generato deve essere scaricato o ispezionato realmente, non solo dedotto dalla UI.
   - Il contenuto generato deve essere confrontato con i campioni reali e la normativa già acquisiti: ordine documenti, atto principale, procura, allegati/prove, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, oggetto/contenuto email e presenza/assenza di `Atto.enc`.
4. Verificare che siano generati o mostrati:
   - proposta documenti;
   - atto principale;
   - allegati;
   - `DatiAtto.xml` o equivalente firmato se la firma avviene;
   - `IndiceDocumentiDepositati.PDF`;
   - contenuto/oggetto email di deposito se previsto dal flusso;
   - eventuale `Atto.enc` solo se realmente prodotto dall'adapter ministeriale.
5. Verificare che il flusso non registri un deposito come valido se manca `Atto.enc` AES256 ministeriale.
6. Verificare Local Signer su macchina reale:
   - rilevazione da pagina server;
   - versione e token;
   - comportamento di aggiornamento automatico;
   - firma multipla reale solo se è disponibile il PIN/token necessario, senza simulare esiti.
7. Documentare con esito onesto cosa è stato visto, cosa è stato generato, cosa coincide con i depositi reali allegati dall'utente e cosa resta bloccante.

## Regole operative durante la prova

- Non salvare password, PIN, token o dati segreti in report, screenshot o file committati.
- Non cliccare comandi di invio PEC/deposito reale.
- Non creare backup e non cancellare dati applicativi.
- Se il server o la UI mostrano un problema, il problema prevale sui test automatici.
- Se la firma multipla non viene eseguita con PIN reale e salvataggio di più `.p7m`, non va dichiarata funzionante.
- Se il pacchetto prodotto è solo di controllo, va chiamato pacchetto di controllo e non busta ministeriale valida.

## Stato iniziale

- Incarico scritto.
- Prova server ancora da eseguire.
- Audit busta ancora da eseguire.
- Verifica multifirma ancora da eseguire.

## Aggiornamento codice 2.253.26 - 16 giugno 2026

Obiettivo dell'intervento: rendere il deposito più semplice, veloce, intuitivo e funzionale, con un percorso operativo a pannelli e con documenti gestiti in un unico slot documentale.

Modifiche applicate:

- la pagina React `Prepara deposito` usa una barra fasi e mantiene aperto un solo pannello alla volta;
- `Documenti da inviare` mostra l'intero fascicolo utile al deposito, non solo la proposta automatica;
- l'avvocato può selezionare singoli documenti, usare `Invia tutto`, correggere la classificazione e salvare prima del comando finale;
- la classificazione copre atto principale, procura, allegati, prove, prove di notifica e documenti fuori busta;
- il comando finale salva prima la classificazione visibile, poi avvia la firma multipla dei documenti realmente da firmare, poi prepara il pacchetto;
- lo stato `Firmato` non è più modificabile dalla UI: deriva solo dal documento reale o da un esito di firma salvato dal sistema;
- aggiunto endpoint protetto `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti` collegato ai dati reali del fascicolo e agli slot deposito.

Guardrail già eseguiti:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m pytest tests/test_regia_api_payloads.py tests/test_regia_ui_react.py tests/test_security_headers.py -q`;
- `pnpm --filter @iusentra/studio test`;
- `pnpm --filter @iusentra/studio build`;
- `python tools\sync_packaging_files.py --check`;
- `python scripts\react-migration\generate_api_contracts.py` e `--check`;
- `python scripts\validate_openapi.py docs\openapi.yaml`;
- `python scripts\verify_openapi_provider.py`;
- `python -m pytest tests\test_openapi_contracts_phase6.py -q --tb=short`;
- `python -m pytest tests\test_utf8_integrity.py -q --tb=short`.

Nota prestazionale: la build resta riuscita, ma segnala ancora il chunk principale React sopra 500 kB. Non blocca la correzione deposito, però resta debito da affrontare con una tranche di code splitting e baseline reale.

Chiarimento operativo dell'utente:

- la macchina locale deve essere aggiornata e deve rispondere su `127.0.0.1:8080/api/pronto`;
- la prova visiva con click, scroll completo e responsive deve essere svolta solo sul server reale `https://app.iusentra.it`, non sulla copia locale.

Stato non chiuso:

- versione `2.253.26` ancora da committare, pushare e distribuire;
- server `app.iusentra.it` ancora da verificare dopo deploy;
- macchina locale reale `127.0.0.1:8080` ancora da ricostruire e verificare tramite `/api/pronto`;
- busta/pacchetto dry-run ancora da generare e ispezionare senza invio PEC;
- firma multipla ancora da provare con PIN/token reale e salvataggio di più `.p7m`;
- nessun invio PEC reale deve essere eseguito durante la prova.

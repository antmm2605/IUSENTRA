# Lavori da eseguire - Fascicoli, pannello rapido e PagoPA

Data: 20/08/2026
Ambito: pagina Fascicoli React, vista compatta, pannello rapido fascicolo, collegamento PagoPA PST e ricevuta pagamento.

## Perimetro confermato

- Restare dentro il flusso fascicoli/PagoPA già esistente in IUSENTRA.
- Non aggiungere collegamenti esterni inventati o alternativi se esiste già il flusso interno.
- Non modificare deposito, notifiche o Local Signer in questa correzione.
- Non spegnere il PC: non richiesto nella richiesta corrente.

## Lavori

1. Pannello rapido fascicolo
   - Problema: il pannello rapido in vista compatta può aprirsi troppo in basso e non si vede per intero.
   - Correzione da fare: calcolare la posizione nel viewport reale e limitare altezza/scroll interno, senza tagliare le voci operative.
   - Verifica richiesta: aprire il pannello rapido su `http://127.0.0.1:8080/fascicoli?visualizzazione=compatta` e controllare che tutte le voci siano leggibili e cliccabili.
   - Stato: da fare.

2. Registro su portale servizi
   - Problema: il collegamento apriva la vecchia rotta `/polisweb`, non il wizard operativo di acquisizione PST.
   - Correzione applicata: il pannello rapido ora apre `/portali/pst/acquisizione#wizard-acquisizione` passando `fascicolo_id`, `numero`, `anno`, `ufficio` quando presente e i parametri di tabella ministeriale/registro dedotti dal fascicolo (`schema`, `tabella_ministeriale`, `servizio_pst_preferito`, `registro_portale`).
   - Verifica richiesta: dal pannello rapido aprire `Registro su portale servizi` e controllare che la pagina `Acquisizione PST` mostri Ufficio giudiziario, Numero, Anno e Tabella ministeriale precompilati quando il fascicolo contiene questi dati.
   - Stato: implementato nel codice, verifica reale da eseguire dopo rebuild locale.

3. PagoPA dal pannello rapido
   - Problema: la voce `Paga contributo su pagoPA` punta al collegamento sbagliato.
   - Correzione da fare: usare lo stesso flusso interno già presente nel fascicolo, cioè il proxy IUSENTRA `pagopa_nuovarich.wp` con `iusentra_fascicolo`, non il link generico errato.
   - Verifica richiesta: dal pannello rapido aprire PagoPA e vedere la schermata `Nuovo pagamento PagoPA PST` dentro IUSENTRA.
   - Stato: da fare.

4. Ricevuta pagamento RT dopo `Paga subito`
   - Problema da controllare: dopo il pagamento il software deve individuare la ricevuta e scaricarla nel fascicolo.
   - Controllo da fare: verificare backend, proxy PagoPA, upload/archiviazione RT e presenza del documento nel fascicolo.
   - Verifica richiesta: se il pagamento reale non può essere completato in test, dichiarare precisamente quale parte è verificata e quale dipende dall'esito reale del portale.
   - Stato: da fare.

5. CTU e perizie
   - Problema da controllare: nel pannello `CTU e perizie` oggi viene scritto che le date vengono dall'ordinanza del giudice e che il software non le calcola.
   - Fonte normativa da usare: art. 195 c.3 c.p.c. su Gazzetta Ufficiale, secondo cui i termini per trasmissione bozza, osservazioni delle parti e deposito della relazione sono fissati dal giudice con ordinanza.
   - Controllo da fare: verificare che IUSENTRA non inventi termini standard, ma proponga automaticamente le date quando l'ordinanza contiene decorrenza e giorni o date espresse.
   - Correzione da fare: aggiungere un calcolo assistito che usa solo i dati dell'ordinanza; se non ci sono dati sufficienti, chiedere decorrenza/termini senza testo fuorviante e lasciando le date modificabili prima del salvataggio.
   - Verifica richiesta: aprire il fascicolo reale, sezione CTU/perizie, controllare testi, campi e comportamento di salvataggio.
   - Stato: inserito nel perimetro lavori, da implementare e verificare.

6. Test e verifica reale
   - Test tecnici: typecheck frontend e test mirati collegati a fascicoli/PagoPA.
   - Prova reale obbligatoria: browser reale su `127.0.0.1:8080`, click sul pannello rapido, link portale, link PagoPA, lettura completa del pannello e controllo CTU/perizie.
   - Stato: da fare.

7. Chiusura tecnica
   - Aggiornare versione se cambia codice.
   - Commit e push sui branch `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`.
   - Deploy Hetzner e verifica `https://app.iusentra.it/api/pronto`.
   - Stato: da fare.

## Controllo finale

- [ ] Tutte le voci operative del pannello rapido sono visibili.
- [ ] Il portale servizi riceve RG e ufficio quando disponibili.
- [ ] PagoPA usa il flusso interno IUSENTRA già esistente.
- [ ] La gestione della ricevuta RT è controllata sul codice reale.
- [ ] CTU/perizie è verificato su fonte ufficiale e il testo non esclude automatismi possibili.
- [ ] La UI è verificata su `127.0.0.1:8080`.
- [ ] I test mirati sono eseguiti.
- [ ] Commit, push e deploy sono conclusi.

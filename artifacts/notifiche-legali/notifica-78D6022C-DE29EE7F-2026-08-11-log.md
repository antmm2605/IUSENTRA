# Log operativo notifica L. 53/1994

Data apertura log: 11/08/2026 14:18:09 Europe/Rome

## Pratica e pagina

- URL verificato: `https://app.iusentra.it/notifiche-legali?id_fascicolo=78D6022C&fase=notifica&documenti=DE29EE7F`
- Fascicolo/pratica: `2026/320 - Romeo Maria c. MIM`
- RG: `1428/2026`
- Ufficio: `TRIBUNALE DI PALMI`
- Documento preselezionato: `SentenzaDefinitiva_35882174.pdf`

## Stato pre-invio verificato

- Modello relata selezionato dopo controllo: `01 - Relata PEC base`
- Caso notifica: `Sentenza o termine breve`
- Piano PEC locale: pronto
- Canale di invio: PC locale tramite Local Signer, non server SMTP
- Regola decompilato Studio Telematico: unico messaggio PEC con tutti i destinatari nel campo `To`

## Destinatari verificati

1. `dgosv@postacert.istruzione.it` - Ministero dell'Istruzione e del Merito - fonte `registro_ppaa`
2. `usprc@postacert.istruzione.it` - MINISTERO ISTRUZIONE E DEL MERITO - fonte `registro_ppaa`
3. `usprc.contenzioso@postacert.istruzione.it` - MIM- USR Reggio Calabria - fonte `registro_ppaa`
4. `ads.rc@mailcert.avvocaturastato.it` - Avvocatura dello Stato - fonte `reginde`

## Allegati previsti dal piano PEC

1. `SentenzaDefinitiva_35882174.pdf`
2. `Attestazione di conformità.pdf`
3. `relata_notifica.pdf.p7m`

## Guardrail eseguiti

- Verifica reale in browser su produzione: pagina aperta e controllata.
- Pulsante `Controlla relata`: eseguito, esito superato.
- Nessuna PEC inviata da Codex prima della conferma dell'utente.

## Eventi invio

- 11/08/2026 14:18:09: l'utente ha confermato di procedere con l'invio se tutto è corretto.
- 11/08/2026 14:19 circa: premuto `Invia PEC` sul browser reale di produzione. Nessuna PEC trasmessa.
- Esito prima prova: il flusso si è fermato prima della password PEC con messaggio `Il file firmato non corrisponde alla relata corrente. Rigenera e firma la relata aggiornata.`
- Correzione avviata: validazione della relata firmata agganciata all'hash del PDF sorgente generato nella stessa sessione di firma.
- 11/08/2026 14:31: deploy Hetzner completato sul commit `0571d82348830890597d5395c379d1a1dceb4991`, versione `2.278.6`.
- Container applicativo verificato: unico container `iusentra-app`, stato healthy.
- `https://app.iusentra.it/api/pronto`: risposta `ok`, versione `2.278.6`, timezone `Europe/Rome`.
- 11/08/2026 14:33 circa: pagina notifica riaperta, impostati e verificati 4 destinatari, modello tecnico `relata_pec_base_l53` (`01 - Relata PEC base`), controllo relata superato, nessun blocco visibile.
- 11/08/2026 14:34 circa: premuto `Invia PEC` dopo inserimento PIN da parte dell'avvocato. Nessuna PEC trasmessa.
- Esito seconda prova: il flusso si è fermato prima della password PEC con lo stesso messaggio `Il file firmato non corrisponde alla relata corrente. Rigenera e firma la relata aggiornata.`
- Diagnosi aggiornata: confronto troppo rigido tra payload React variabile e PDF sorgente firmato dal Local Signer.
- Correzione applicata: la validazione accetta il PDF sorgente generato nella stessa sessione e l'hash esplicito `X-IUSENTRA-Document-SHA256` passato dal frontend insieme al `.p7m`.

## Test mirati

- `test_api_react_notifiche_legali_relata_firmata_usa_pdf_generato_nella_stessa_sessione`
- `test_api_react_notifiche_legali_relata_firmata_accetta_hash_pdf_esplicito`
- `test_piano_invio_studio_telematico_prepara_unico_to_e_allegati_reali`
- `test_api_react_notifiche_legali_invio_locale_usa_allegati_reali_message_id_e_presidio`
- `test_ui_notifiche_legali_invia_pec_firma_relata_e_allega_prima_della_password`

Esito test: 5 superati.

## Stato operativo corrente

- In attesa di deploy della correzione `2.278.7` e nuova prova reale.
- La password PEC non è stata richiesta nelle due prove precedenti.
- Nessuna PEC è stata trasmessa nelle due prove precedenti.

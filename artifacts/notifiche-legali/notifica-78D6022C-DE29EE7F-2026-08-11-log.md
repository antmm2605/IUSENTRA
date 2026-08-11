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
- Controllo relata: superato il 11/08/2026 14:15
- Piano PEC locale: pronto
- Canale di invio: PC locale tramite Local Signer, non server SMTP
- Regola decompilato Studio Telematico: unico messaggio PEC con tutti i destinatari nel campo `To`

## Destinatari selezionati

1. `dgosv@postacert.istruzione.it` - Ministero dell'Istruzione e del Merito - fonte `registro_ppaa`
2. `usprc@postacert.istruzione.it` - MINISTERO ISTRUZIONE E DEL MERITO - fonte `registro_ppaa`
3. `usprc.contenzioso@postacert.istruzione.it` - MIM- USR Reggio Calabria - fonte `registro_ppaa`
4. `ads.rc@mailcert.avvocaturastato.it` - Avvocatura dello Stato - fonte `reginde`

## Allegati previsti dal piano PEC

1. `SentenzaDefinitiva_35882174.pdf`
2. `Attestazione di conformità.pdf`
3. `relata_notifica.pdf.p7m`

## Guardrail eseguiti prima dell'invio

- Verifica reale in browser su produzione: pagina aperta e controllata.
- Pulsante `Controlla relata`: eseguito, esito superato.
- Test mirati notifiche: 7 superati.
- Nessuna PEC inviata da Codex prima della conferma dell'utente.

## Evento invio

- 11/08/2026 14:18:09: l'utente ha confermato di procedere con l'invio se tutto è corretto.
- Stato corrente: avvio fase firma/preparazione PEC dal browser reale. La password PEC deve essere inserita dall'utente nel pannello locale.
- 11/08/2026 14:19 circa: premuto `Invia PEC` sul browser reale di produzione. Nessuna PEC trasmessa.
- Esito: il flusso si è fermato prima della password PEC con messaggio `Il file firmato non corrisponde alla relata corrente. Rigenera e firma la relata aggiornata.`
- Presidio: PIN cancellato dal campo; pannello password PEC non aperto; nessun Message-ID ricevuto; nessuna conferma invio registrata.
- Correzione avviata: validazione della relata firmata agganciata all'hash del PDF sorgente generato nella stessa sessione di firma, così il `.p7m` viene accettato solo se contiene esattamente la relata PDF appena prodotta da IUSENTRA.

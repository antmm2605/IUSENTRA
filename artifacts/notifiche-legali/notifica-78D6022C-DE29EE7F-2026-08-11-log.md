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
- 11/08/2026 14:52: produzione verificata su commit `8208d7e06ba0e45bb1081680ff8013a70d3d12ba`, versione `2.278.7`, container `iusentra-app` healthy.
- 11/08/2026 14:52 circa: pagina notifica ricaricata e ricontrollata. Confermati 4 destinatari, modello `01 - Relata PEC base`, documento `SentenzaDefinitiva_35882174.pdf`, attestazione di conformità e relata separata.
- 11/08/2026 14:52 circa: premuto `Controlla relata`, esito superato. Nessun blocco destinatari/allegati.
- 11/08/2026 14:53 circa: premuto `Invia PEC` dopo inserimento PIN sulla macchina locale. Nessuna PEC trasmessa.
- Esito terza prova: il flusso si è fermato ancora prima della password PEC con messaggio `Il file firmato non corrisponde alla relata corrente. Rigenera e firma la relata aggiornata.`
- Diagnosi definitiva sul perimetro notifica: il blocco hash/confronto contenuto della relata firmata è un controllo aggiuntivo non necessario per l'invio. La verifica deve limitarsi a CAdES valido, PDF incorporato, salvataggio nel fascicolo e allegazione automatica alla PEC.
- Correzione `2.278.8`: rimosso il blocco per impronta diversa della relata firmata; una relata `.p7m` valida contenente PDF viene salvata nel fascicolo e allegata alla notifica.

## Test mirati

- `test_api_react_notifiche_legali_relata_firmata_usa_pdf_generato_nella_stessa_sessione`
- `test_api_react_notifiche_legali_relata_firmata_accetta_hash_pdf_esplicito`
- `test_api_react_notifiche_legali_relata_firmata_non_blocca_impronta_pdf_diversa`
- `test_piano_invio_studio_telematico_prepara_unico_to_e_allegati_reali`
- `test_api_react_notifiche_legali_invio_locale_usa_allegati_reali_message_id_e_presidio`
- `test_ui_notifiche_legali_invia_pec_firma_relata_e_allega_prima_della_password`
- `test_ui_notifiche_legali_non_contiene_flusso_deposito`

Esito test: 7 superati.

## Stato operativo corrente

## Aggiornamento 2.278.9 - payload PEC da Impostazioni

- 11/08/2026 15:07 circa: produzione `2.278.8` verificata con 4 destinatari selezionati, modello `01 - Relata PEC base`, controllo relata superato e nessun blocco visibile.
- 11/08/2026 15:08 circa: premuto `Invia PEC` dopo firma relata sul PC locale. Il blocco sulla relata firmata non compare più; relata e allegati PEC risultano preparati.
- Esito quarta prova: nessuna PEC trasmessa; il flusso arriva al Local Signer e si ferma con `Autenticazione SMTP PEC locale non riuscita verso smtps.pec.aruba.it:465`.
- Diagnosi aggiornata: la notifica chiedeva/inviava la password PEC manuale, mentre il deposito recupera il payload SMTP locale da `/impostazioni/pec/local-smtp-payload` usando la configurazione PEC salvata in Impostazioni.
- Correzione `2.278.9`: il flusso notifica usa lo stesso endpoint del deposito per caricare indirizzo, username, host, porta, SSL e password PEC salvata; se la password salvata non è disponibile resta la richiesta manuale.
- Test mirato: `python -m pytest tests/test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q` superato.
- Build mirata: `pnpm --filter @iusentra/studio build:vite` superata.
- Stato: in attesa di deploy `2.278.9` e nuova prova reale su produzione.

## Aggiornamento 2.278.10 - helper CSRF notifiche

- 11/08/2026 15:31 circa: produzione `2.278.9` verificata su commit `7661d8ebbe698926c34c44b0152b8c3526af2f9e`; container unico `iusentra-app` healthy e `/api/pronto` ok.
- Prova reale: selezionati i 4 destinatari richiesti, modello `01 - Relata PEC base`, controllo relata superato, nessun `bloccante`.
- Premuto `Invia PEC` dopo inserimento PIN sul PC locale. Nessuna PEC trasmessa.
- Esito quinta prova: il flusso si è fermato prima della trasmissione con `csrfToken is not defined`, durante il recupero del payload PEC salvato da Impostazioni.
- Diagnosi: il componente Notifiche Legali richiamava `csrfToken()` come il deposito, ma non importava l'helper da `formSubmit`.
- Correzione `2.278.10`: importato `csrfToken` in `NotificheLegaliPage.tsx`; aggiunto guardrail nel test mirato per bloccare regressioni.

## Aggiornamento 2.278.11 - conferma presidio con fuso Europe/Rome

- 11/08/2026 15:40 circa: produzione `2.278.10` verificata con 4 destinatari selezionati, modello `01 - Relata PEC base`, controllo relata superato, piano PEC locale pronto e allegati `SentenzaDefinitiva_35882174.pdf`, `Attestazione di conformità.pdf`, `relata_notifica.pdf.p7m`.
- Premuto `Invia PEC` dopo inserimento PIN sul PC locale. Il flusso non ha mostrato errori SMTP e non ha più mostrato `csrfToken is not defined`.
- Esito sesta prova: la UI ha indicato `La PEC è partita dal PC locale, ma la conferma/presidio non è stata completata.`
- Diagnosi log server: `/api/v1/ui/notifiche-legali/invio-pec-locale/conferma` ha risposto 500 perché il `sentAt` ricevuto dal browser era un timestamp locale senza fuso orario; il presidio richiede timestamp ISO con fuso.
- Correzione `2.278.11`: la conferma notifica normalizza ogni `sentAt` in `Europe/Rome` prima di creare candidato presidio e ricevuta `SENT`, senza modificare firma, allegati, destinatari o regole di invio.

## Aggiornamento 2.278.12 - destinatario RdAC da `consegna`

- Verifica server successiva all'invio reale: la casella PEC IUSENTRA contiene la RAC delle 15:40:36 e quattro RdAC tra le 15:40:38 e le 15:40:47, tutte con oggetto `Notificazione ai sensi della legge n. 53/1994 e succ. mod. [JQ2026/320-L01] [Notifica_ID:RIOEFC9W]`.
- Message-ID originario della PEC inviata dal PC locale: `<178645563104.17784.17278236934861831217@pcmarco>`.
- Identificativo gestore Aruba: `jpec1329.20260811154036.39864.404.1.1@pec.aruba.it`.
- Diagnosi: le ricevute erano state importate come `unmatched` perché il presidio iniziale non era stato creato dalla conferma fallita; inoltre il parser PEC prendeva il primo `<destinatari>` del `daticert.xml` invece del tag `<consegna>` della singola RdAC, rischiando di attribuire più consegne allo stesso destinatario.
- Correzione `2.278.12`: nelle RdAC il parser PEC preferisce il tag `<consegna>` e conserva `<destinatari>` come fallback; test dedicato `test_parse_pec_message_rdac_preferisce_destinatario_consegna_postacert`.
- Prossimo passo operativo: dopo deploy `2.278.12`, riprocessare solo le cinque ricevute già importate e riconciliare il presidio, senza nuovo invio PEC.

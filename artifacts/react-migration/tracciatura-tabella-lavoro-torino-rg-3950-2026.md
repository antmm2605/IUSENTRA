# Tracciatura tabella lavoro PST Torino RG 3950/2026

Data intervento: 2026-06-18.

## Fascicolo

- Ufficio: Tribunale di Torino.
- Registro: LAV.
- Numero: RG 3950/2026.
- Oggetto: lavoro, pubblico impiego, retribuzione.
- Fascicolo IUSENTRA aggiornato: `9B9DF2A1`, `Spagnolo Sara c. MIM`.
- Fonte operativa: Portale Servizi Telematici ufficiale, sezione `lav_infofascicolo.wp`, letto con browser autenticato dell'utente.

## Scarico fascicolo

Scarico reale eseguito dal PST ufficiale tramite link `downloadDocumentoSemplice.action`, senza usare credenziali o PIN nei log.

- Documenti individuati: 29.
- Documenti scaricati: 29.
- Errori download: 0.
- Dimensione complessiva: 7.380.295 byte.
- Manifest tecnico temporaneo: salvato fuori repository sotto `C:\Users\antmm\AppData\Local\Temp\iusentra-rg3950-2026-lavoro-download`.

Documenti principali e allegati PST tracciati:

- `Ricorso.PDF`;
- `Nota d'iscrizione a ruolo.PDF`;
- `20260512121012914.xml`;
- `Procura.PDF`;
- `Sentenza_Tribunale_Vicenza_20-04-2023.PDF`;
- `Sentenza Cassazione.PDF`;
- `Lettera di diffida Carta Docenti Spagnolo Sara.PDF`;
- `Contratto 25-26 per interesse ad agire.PDF`;
- `Contratto 24-25.PDF`;
- `Contratto 22-23.PDF`;
- due ricevute `.eml` del 17/03/2026;
- `IndiceDocumentiDepositati.PDF`;
- `DatiAtto.xml.p7m`;
- `26830376s.pdf` e `26830376.xml.p7m`;
- `20200029s.pdf` e `20200029.xml.p7m`;
- `Ricorso (originale notificato).pdf`;
- `Relata di notifica.pdf.pdf`;
- tre ricevute notifica `.eml`;
- `Attestazione di conformità (originale notificato).pdf`;
- `Decreto fissazione udienza (originale notificato).pdf`;
- `Procura (originale notificato).pdf`;
- secondo `IndiceDocumentiDepositati.PDF`;
- secondo `DatiAtto.xml.p7m`.

## Import IUSENTRA

Import eseguito su `https://app.iusentra.it` nella sessione autenticata già aperta dall'utente.

- Modalità risolta: aggiornamento fascicolo esistente.
- Fascicolo aggiornato: `9B9DF2A1`.
- Log import produzione: `PST-20260618085430-C4891C`.
- Documenti reali importati: 29/29.
- Documenti mancanti: 0.
- Documenti senza contenuto: 0.
- Documenti scartati: 0.
- Depositi ricostruiti: 4.
- Eventi generati: 5.
- Comunicazioni generate: 3.
- Albero originale salvato: sì.
- Download parziale portale: no.

Prova visiva su server:

- pagina aperta: `https://app.iusentra.it/fascicoli/9B9DF2A1#documenti`;
- contatore `Documenti e atti`: 52;
- indice Lex: 52 totali, 52 pronti;
- visibili `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `26830376s.pdf` e `20200029s.pdf` con origine PST ufficiale e date portale.

## Correzione software

La struttura della tabella lavoro PST è stata trattata come quella civile:

- riga documento principale;
- blocco `Allegati:`;
- nuova riga documento principale;
- paginazione PST con pagina 1 e pagina 2.

Il parser Local Signer ora riconosce `lav_infofascicolo.wp`, mantiene la sezione reale del link, marca solo gli elementi sotto `Allegati:` come allegati e non trascina la sezione allegati sulle righe principali successive. Per i link `downloadDocumentoSemplice.action` usa il download diretto del portale autenticato, conservando `id_documento`, nome file, data, tipo atto, depositante e relazione padre/allegato.

Guardrail aggiunti:

- test su HTML LAV con riga principale, allegati e seconda riga principale;
- test su download diretto `downloadDocumentoSemplice` senza fallback SOAP;
- controllo che il registro LAV usi `lav_infofascicolo.wp`, mentre il civile resta su `sicid_infofascicolo.wp`.

## Local Signer

- Versione sorgente aggiornata: `1.6.78`.
- Versione installata in AppData sulla macchina reale: `1.6.78`.
- Pacchetti rigenerati: Windows `.exe`, macOS `.command`, Linux `.run`.
- Avvio Windows riallineato a processo nascosto, preservando il processo padre/figlio del virtualenv che mantiene vivo il servizio in ascolto su `127.0.0.1:27272`.
- Certificato PST auto-selezionato nel test reale: ArubaPEC EU Authentication Certificates CA G1, CF `MNTGPP94L01G791A`, scadenza 02/03/2029.
- Certificati Adobe, intermedi o scaduti: esclusi dall'auto-selezione PST; in modalita' automatica non viene piu' aperta la finestra generica di selezione certificato Windows.

## Timeout anteprima PST

Difetto riprodotto su `https://app.iusentra.it` il 18/06/2026: dopo `Cerca fascicolo`, il server trovava `RG 3950/2026` e abilitava `Carica anteprima`, ma l'anteprima restava bloccata su `Timeout connessione a ext.processotelematico.giustizia.it (90s)`.

Correzione `2.253.63`:

- la ricerca PST React salva sempre uno snapshot minimo del fascicolo trovato;
- `Carica anteprima` usa subito lo snapshot gia' restituito dalla ricerca, anche quando il catalogo documenti completo non e' ancora presente nel payload;
- il refresh esterno verso `ext.processotelematico.giustizia.it` resta un arricchimento e non blocca la visualizzazione dell'anteprima;
- test React aggiornato per verificare il ramo `hasSearchSnapshotPayload` e impedire la regressione al blocco sui soli documenti scaricabili.

Prova reale prima del deploy:

- server `https://app.iusentra.it` ancora su versione `2.253.60`: timeout ancora visibile perche' il bundle vecchio e' in produzione;
- Local Signer reale aggiornato e stabile: `ping?auto=1` risponde `1.6.78` e seleziona ArubaPEC Authentication;
- da ripetere subito dopo deploy Hetzner dello stesso commit `2.253.63`: ricerca, anteprima, controllo documenti/eventi e assenza finestra Adobe.

## Stato residuo

Il fascicolo è stato scaricato e importato sul server reale. Restano da chiudere, prima del report finale di release:

- test mirati finali;
- build React e retention asset;
- Docker locale reale su `127.0.0.1:8080`;
- prova visiva locale post-rebuild;
- commit e push dei branch gemelli;
- controlli GitHub/CodeQL sullo SHA corrente;
- deploy Hetzner dello stesso commit;
- igiene repository finale.

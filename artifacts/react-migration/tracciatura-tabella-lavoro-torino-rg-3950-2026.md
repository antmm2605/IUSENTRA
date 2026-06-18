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
- deploy Hetzner `2.253.63` eseguito sul commit `646ad9cf`, container healthy e `/api/pronto` aggiornato;
- prova reale su Google Chrome collegato al PC dell'utente: ricerca `RG 3950/2026` su `https://app.iusentra.it` completata dopo circa 72 secondi con certificato confermato e senza selezione Adobe;
- click reale `Carica anteprima`: Step 3 aperto in circa 2,5 secondi senza `Timeout connessione a ext.processotelematico.giustizia.it`;
- residuo rilevato in prova: l'anteprima mostrava 4 documenti principali, mentre il fascicolo locale già importato espone 28/29+ documenti governati. La correzione `2.253.64` arricchisce la preview PST dal catalogo completo del fascicolo locale esistente e conserva gli allegati senza id forte.

## Aggiornamento 2.253.64 - completezza anteprima documenti

Correzione applicata:

- `_build_portale_preview` unisce allo snapshot PST parziale il catalogo documenti del fascicolo locale esatto quando RG, anno e ufficio coincidono;
- la deduplica considera anche `id_deposito`/busta, così documenti omonimi in depositi diversi non si oscurano;
- gli allegati reali senza identificatore forte non vengono scartati se nome, data, tipo e deposito permettono una chiave contenuto stabile;
- lato React la deduplica visuale include la busta nella chiave contenuto.

Guardrail:

- `tests/test_polisweb.py::test_api_portale_acquisizione_preview_pst_arricchisce_catalogo_da_fascicolo_locale` verifica uno snapshot con un solo documento e un fascicolo PST locale con `29/29` documenti, incluso un allegato senza id portale forte.

Prova reale server dopo deploy `2.253.64`:

- deploy Hetzner eseguito sul commit `93de6fb7`; `/api/pronto` risponde `versione=2.253.64`, container `app`, `scheduler-worker` e `ocr-worker` healthy, cache Docker rigenerabile prunata e `/opt/iusentra/tmp-backup-snapshot` assente;
- Google Chrome reale collegato al PC dell'utente su `https://app.iusentra.it/portali/pst/acquisizione?...RG3950...`: bundle caricato `TelematicoSurfacePage-B2_fCC4h.js`;
- `Cerca fascicolo` ha completato la lettura PST e mostrato `1 risultati trovati`, `RG 3950/2026`, `Tribunale di Torino - SPAGNOLO SARA`, senza finestra Adobe e senza timeout;
- `Carica anteprima` ha aperto Step 3 in circa 1 secondo, con messaggio `Anteprima caricata: verifica dati, parti, eventi e documenti`;
- anteprima visibile: `Parti 2`, `Documenti 31`, `7 buste o gruppi`, `Eventi 1`, `R.G. 3950`, `RITO LAVORO 1 GRADO`, `ATTESA ESITO UDIENZA DI DISCUSSIONE`, `QUINTA SEZIONE LAVORO`, oggetto `retribuzione`;
- documenti visibili in anteprima, tra gli altri: `Ricorso (originale notificato).pdf`, `Relata di notifica.pdf.pdf`, `Procura (originale notificato).pdf`, `IndiceDocumentiDepositati.PDF`, `DatiAtto.xml.p7m`, ricevute `CONSEGNA` e `ACCETTAZIONE`, `Decreto_173140769.pdf`, `AssegnazioneSezioneGiudice_172453268.pdf`, `Ricorso_172365050.pdf`, `Nota d'iscrizione a ruolo.PDF`, `Lettera di diffida Carta Docenti Spagnolo Sara.PDF`, `Contratto 25-26 per interesse ad agire.PDF`, `Contratto 24-25.PDF`;
- non è comparso `Timeout connessione a ext.processotelematico.giustizia.it (90s)`.

## Stato residuo

Il fascicolo è stato scaricato e importato sul server reale. Restano da chiudere, prima del report finale di release:

- test mirati finali;
- build React e retention asset;
- Docker locale reale su `127.0.0.1:8080`;
- prova visiva locale post-rebuild;
- controlli GitHub/CodeQL sullo SHA corrente;
- igiene repository finale.

## Aggiornamento 2.253.65 - chiarezza Step 4 e redirect Step 7

Richiesta utente del 18/06/2026 dopo prova reale server: il flusso funziona, ma gli step risultavano poco intuitivi, in particolare:

- Step 4 mescolava selezione documenti, formato scarico, file manuali e destinazione;
- Step 7 mostrava ancora `Importa nel gestionale`, report numerico e `Import completato`, lasciando l'utente nella pagina di acquisizione anche quando il fascicolo era già importato.

Correzione UI applicata:

- Step 4 rinominato in `Scarico`, con pannello `Step 4 - Cosa scaricare`;
- separati visivamente `Dati da portare nel fascicolo`, `Formato dei documenti PST`, lista `Documenti da scaricare` e `File già raccolti`;
- rimossa dallo Step 4 la scelta duplicata del fascicolo interno: la destinazione resta nello Step 5;
- Step 7 rinominato in `Registra`, con titolo `Step 7 - Importa nel fascicolo`;
- il pulsante finale ora è `Importa nel fascicolo selezionato` oppure `Crea pratica e importa`;
- quando il backend restituisce `fascicolo_url`, `redirect_url` o `url` interno, IUSENTRA apre automaticamente il fascicolo importato invece di lasciare l'utente nello Step 7;
- il fallback dello Step 7 mostra `Fascicolo importato` e link `Apri fascicolo` solo se il redirect non è disponibile.

Guardrail locali prima del deploy server:

- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- `python -m pytest tests/test_utf8_integrity.py -q --tb=short`;
- `python tools/sync_packaging_files.py --check`;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short`;
- `git diff --check` sul perimetro UI/versione/manifest.

Prova reale server dopo deploy `2.253.65`:

- commit server verificato: `718ae2a241f3e9e1ec9200e2873f3fd463427f2b`; `/api/pronto` risponde `versione=2.253.65`;
- Google Chrome reale sul PC dell'utente collegato a `https://app.iusentra.it/portali/pst/acquisizione?...RG3950...`; il browser integrato Codex non è stato usato per Local Signer perché blocca `127.0.0.1:27272`;
- Local Signer reale raggiunto da Chrome: `/ping?light=1` versione `1.6.78`, `/ping?auto=1` con certificato ArubaPEC Authentication del codice fiscale `MNTGPP94L01G791A`, `/diagnosi` senza blocchi e senza finestra Adobe;
- controllo PST live: `ext.processotelematico.giustizia.it` raggiungibile da `/pst/status`, mentre `pda.processotelematico.giustizia.it` risultava lento; la ricerca `Cerca fascicolo` è rimasta in attesa fino a `attesa 360s` e ha poi mostrato il messaggio guidato `Consultazione PST ancora in attesa...`;
- dopo ricarica cache-bust della pagina server, lo stepper mostra `4 Scarico - Documenti e dati`, `5 Destinazione - Fascicolo interno`, `7 Registra - Import nel fascicolo`;
- click reale su Step 4: visibili `Step 4 - Cosa scaricare`, `Scarico separato dall'importazione finale`, `Dati da portare nel fascicolo`, `Documenti del fascicolo`, `Eventi di cancelleria`, `Scadenziario`, `Parti`, `Formato dei documenti PST`, `Originale portale`, `Struttura originale`, `File già raccolti` e pulsante `Vai alla destinazione`;
- click reale su `Vai alla destinazione`: Step 5 apre `Step 5 - Destinazione`, con `Crea nuova pratica`, `Usa pratica esistente` e selettore `FASCICOLO LOCALE`;
- click reale su Step 7: visibili `Step 7 - Importa nel fascicolo`, card `DESTINAZIONE`, `DOCUMENTI`, `DATI COLLEGATI`, nota `Non avvia uno scarico nascosto dal portale`, pulsanti `Crea pratica e importa` e `Correggi destinazione`;
- stringhe vecchie assenti nella pagina server: `Step 4 - Selezione`, `Importa nel gestionale`, `Import completato`, `Importazione completata o presa in carico dal gestionale operativo`;
- il redirect automatico al fascicolo importato è implementato quando il backend restituisce `fascicolo_url`, `redirect_url` o `url` interno ed è coperto dal guardrail React; non è stato cliccato `Crea pratica e importa` nella prova live perché la ricerca PST non ha restituito dati in quella sessione e importare `0/0` documenti avrebbe rischiato una pratica vuota o duplicata.

## Aggiornamento 2.253.66 - redirect Step 7 verso documenti fascicolo

Richiesta utente del 18/06/2026: dopo il messaggio `Importazione completata. Fascicolo registrato nel gestionale.`, lo Step 7 non deve restare nella pagina di acquisizione, ma deve aprire direttamente il fascicolo dove sono stati scaricati o importati i documenti.

Correzione applicata:

- l'API di import PST ora restituisce sempre `fascicolo_url`, `redirect_url` e `documenti_url` quando la pratica interna è stata risolta;
- `redirect_url` punta alla sezione documenti del fascicolo: `/fascicoli/<id>#sezione-documenti-fascicolo`;
- la risposta `summary` contiene gli stessi collegamenti, così anche le viste annidate e il link `Apri fascicolo` restano coerenti;
- il wizard React dello Step 7 usa un helper unico che legge `redirect_url`, `documenti_url`, `fascicolo_url`, `dettaglio_url`, campi annidati in `result`/`summary` e infine costruisce il link dal solo `id_fascicolo`;
- il vecchio fallback `Importazione completata. Fascicolo registrato nel gestionale.` è stato rimosso dal sorgente React. Se in futuro l'API non restituisse alcun collegamento, la UI segnala esplicitamente che manca il link al fascicolo.

Guardrail eseguiti prima del deploy:

- `python -m pytest tests/test_react_shell.py::test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero -q`;
- `python tools/sync_packaging_files.py --check`;
- `pnpm --filter @iusentra/studio build`.

Stato: codice e test locali pronti per commit, push, deploy Hetzner e prova visiva server reale su `https://app.iusentra.it`.

## Aggiornamento 2.253.67 - comando PagoPA fascicolo

Richiesta utente del 18/06/2026: aggiungere nel dettaglio fascicolo `https://app.iusentra.it/fascicoli/9B9DF2A1` l'icona PagoPA sotto/accanto al PDF, con apertura del portale `https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp` dentro una finestra sovrapposta al fascicolo.

Correzione applicata:

- asset PagoPA fornito dall'utente inserito in `frontend/public/pagopa-removebg-preview.png`;
- dettaglio fascicolo React esteso con `PagoPaActionButton` vicino a `PDF` e nel pannello `Gestione fascicolo`;
- click PagoPA apre `PagoPaPortalModal`, con iframe PST, chiusura dalla modale, chiusura con `Esc` e fallback `Apri fuori`;
- nessuna modifica a PIN, Local Signer, invio PEC, firma digitale o dati pagamento.

Guardrail locali:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_fascicoli_page_collegata_nav_api_e_lex tests/test_react_shell.py::test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero -q --tb=short`;
- `pnpm --filter @iusentra/studio build`;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short`;
- `python -m pytest tests/test_utf8_integrity.py -q --tb=short`;
- `python tools/sync_packaging_files.py --check`.

Stato: da portare su branch gemelli, deployare su Hetzner e verificare visivamente su produzione.

## Aggiornamento 2.253.68 - PagoPA dentro fascicolo e ricevuta PDF

Richiesta utente del 18/06/2026: il riquadro PagoPA non deve restare vuoto e non deve limitarsi a `Apri fuori`. La compilazione deve avvenire direttamente dentro il fascicolo; la ricevuta PDF non arriva con link automatico, ma va richiesta dall'utente nel portale.

Correzione applicata:

- il comando PagoPA del fascicolo `9B9DF2A1` apre una modale interna con iframe verso il bridge IUSENTRA `/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp?iusentra_fascicolo=<id>`;
- il bridge scarica dal PST ministeriale `servizipst.giustizia.it`, riscrive link, form, asset e redirect sotto `/PST/`, e mantiene la navigazione dentro la modale del fascicolo;
- i POST dei form PagoPA sono inoltrati al PST senza leggere prima il corpo della richiesta;
- quando l'utente chiede la ricevuta PDF nel portale, il PDF viene intercettato dal bridge, mostrato/scaricato dal browser e salvato nei documenti del fascicolo come `RICEVUTA_PAGOPA`;
- Cliente e Soggetti non aprono più una scheda separata: si aprono in overlay sopra il fascicolo, con gli stessi comandi `Apri fuori` e `Chiudi`.

Guardrail locali:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m pytest tests/test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf -q --tb=short`;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf tests/test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf -q --tb=short`;
- `pnpm --filter @iusentra/studio build`;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short`;
- `python tools/sync_packaging_files.py --check`.

Stato: codice locale pronto per commit, push branch gemelli, deploy Hetzner e prova visiva server reale sul fascicolo `9B9DF2A1`.

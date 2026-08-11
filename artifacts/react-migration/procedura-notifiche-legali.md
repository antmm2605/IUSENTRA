# Procedura notifiche legali

## Aggiornamento 30/07/2026 - Attestazione modificabile e allegata alla PEC

Correzione limitata al perimetro notifica L. 53/1994, senza modifiche al deposito:

- l'attestazione di conformità nella pagina React `/notifiche-legali` è modificabile integralmente dall'avvocato;
- il salvataggio conserva la bozza dell'attestazione per la notifica corrente e aggiorna subito l'anteprima visibile;
- il PDF dell'attestazione non viene proposto come download operativo dalla UI notifiche: viene generato e salvato direttamente nei documenti del fascicolo tramite `salva_documento_fascicolo`;
- quando la notifica richiede attestazione, il piano PEC locale inserisce automaticamente il PDF salvato tra gli allegati della PEC insieme alla relata firmata e ai documenti da notificare;
- il testo modificato dall'avvocato viene rispettato anche dal generatore PDF, mantenendo le interruzioni di riga del testo salvato.
- i campi tecnici del modello già coperti dal flusso guidato (`avvocato`, `procedimento`, `RG`, `tipo provvedimento`, date e oggetto PEC) non vengono più mostrati come `Dati del modello scelto`;
- gli stessi campi vengono filtrati anche dal payload `template_fields`, così valori vuoti o duplicati non possono sovrascrivere i dati reali di fascicolo, notifica e documenti.

Guardrail eseguiti senza invio PEC reale:

- `python -m pytest tests/test_notifiche_legali.py -q`;
- `python -m pytest tests/test_regia_ui_react.py -q`;
- `python -m pytest tests/test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q`;
- `npm --prefix frontend run build`.

Verifica reale locale su `127.0.0.1:8080`:

- pratica `2026/002`, destinatari manuali Codex già presenti nella notifica;
- documenti selezionati: `SentenzaDefinitiva_33581101.pdf` e `VerbaleUdienza_33393309.pdf`;
- click su `Salva nel fascicolo` ha prodotto `Attestazione_di_conformita_1025_2026.pdf` dentro il fascicolo;
- dopo reload e selezione dei documenti, il blocco `Dati del modello scelto` non è ricomparso;
- click su `Salva nel fascicolo` ha confermato l'attestazione nel fascicolo;
- click su `Controlla relata` e poi `Invia PEC` ha generato solo il `PIANO PEC LOCALE PRONTO`, senza invio PEC reale e senza SMTP server-side;
- il piano contiene `relata_notifica.pdf.p7m`, sentenza, verbale udienza e attestazione di conformità come allegati;
- nessun blocco `Invio PEC bloccato`, `bloccante` o `mancante` visibile nel piano PEC locale;
- la relata indica `Sentenza` per `SentenzaDefinitiva_33581101.pdf` e `Verbale di udienza` per `VerbaleUdienza_33393309.pdf`, senza trasformare il verbale in sentenza;
- l'attestazione contiene la dichiarazione cumulativa con `Sentenza, emessa dal Tribunale di Palmi Sez. CIVILE in data 08/01/2026` e `Verbale di udienza, estratto dal fascicolo informatico del Tribunale di Palmi Sez. CIVILE in data 16/12/2025`;
- audit visibile con data italiana `30/07/2026 23:04`, senza timestamp UTC raw.

## Aggiornamento 04/08/2026 - Notifica PEC L. 53: flusso distinto dal deposito e allineato a Studio Telematico

Questo aggiornamento riguarda l'invio delle notifiche PEC L. 53, non il deposito telematico. Il deposito resta un flusso separato.

Contratto derivato dal decompilato `D:\QuickOrganizer\QuickOrganizer.exe`, `FormSentMailBee`:

- `CreateRelataNotifica` genera la relata e prepara gli allegati aggiungendo prima atto principale/allegati e poi la relata firmata come ultimo allegato;
- il campo `To` è unico e contiene tutti i destinatari, con commento `codice fiscale:` e `pubblico elenco:`;
- `Cc` e `Bcc` sono vuoti;
- oggetto ordinario: `Notificazione ai sensi della legge n. 53/1994 e succ. mod.` con `[Notifica_ID:...]`;
- il corpo contiene il riferimento da citare nella risposta e la pratica;
- IUSENTRA non registra la notifica come inviata senza `Message-ID` reale restituito dal Local Signer;
- il presidio post-invio è distinto dal deposito: allegati non relata come `(originale notificato)`, relata come relata, pubblicazione verso Agenda, Scadenziario, top bar e Web Push quando attivo.

Implementazione 04/08/2026:

- nuove rotte React/API dedicate: `/api/v1/ui/notifiche-legali/invio-pec-locale` e `/api/v1/ui/notifiche-legali/invio-pec-locale/conferma`;
- frontend React: `Invia PEC` avvia l'invio reale via Local Signer locale, chiede la password PEC solo sul PC e mostra barra di avanzamento per piano PEC, Local Signer, password, invio SMTP, Message-ID e presidio;
- backend: gli allegati vengono letti dai documenti reali del fascicolo; documenti manuali non salvati nel fascicolo non vengono inviati come allegati reali;
- conferma: se manca il `Message-ID`, il backend risponde errore e non crea presidio.

Guardrail script eseguiti:

- `python -m pytest tests/test_notifiche_legali.py` (`126 passed`);
- `python -m pytest tests/test_regia_ui_react.py -k "ui_notifiche_relata_firma_solo_con_prova_tecnica"`;
- `python -m py_compile web/blueprints/api_v1_react.py pct/notifiche_legali.py`;
- `pnpm --filter @iusentra/studio typecheck`.

Stato prova reale: la verifica materiale completa su browser reale `127.0.0.1:8080` e l'invio SMTP effettivo restano da eseguire dopo rebuild Docker locale, con Local Signer attivo e password PEC inserita dall'avvocato sul PC locale.


## Migrazione 11/08/2026 - Blocchi storici notifiche rimossi dal diario deposito



Questi blocchi erano stati scritti in `procedura-deposito-telematico.md`; sono stati spostati qui per mantenere separate le procedure di deposito e notifiche.



### Aggiornamento 22/07/2026 - decisione notifica modificabile prima dell'invio

Il presidio notifiche consente ora di correggere una conferma selezionata per errore senza cancellare o riscrivere la storia. La mutazione `revise-decision` è disponibile soltanto da `NOTIFICATION_CONFIRMED`, richiede una motivazione di almeno 12 caratteri e può riportare il presidio a `NEEDS_REVIEW` oppure chiuderlo come `NOT_REQUIRED`.

La transizione registra autore, data/ora, motivazione e metadati `previous_decision`/`target_decision` nella catena audit. La stessa mutazione viene rifiutata quando sono già presenti destinatari con invio/RAC/consegna/fallimento o documenti `sent_pec`, `rac`, `rdac`, `delivery_failure`, `proof_deposit_receipt`: una notifica già inviata o provata non può quindi essere riaperta dal semplice pannello decisionale.

Guardrail aggiornati: test di dominio sulla catena hash, test API della correzione e del blocco post-invio, payload dell'azione, contratto TypeScript, stati hover/focus/disabled/loading, typecheck e UTF-8. La prova visiva reale resta obbligatoria nella campagna finale su `127.0.0.1:8080` e, dopo deploy dello stesso commit, sul tenant di produzione.

### Aggiornamento 22/07/2026 - criterio PST rigoroso per presidi e relata

Il flusso Presidio notifiche → acquisizione originale → relata non deve considerare come originale PST un documento storico interno solo perché contiene “sentenza” nel nome. Il caso Romeo Maria ha confermato che nel fascicolo possono convivere:

- copie PEC di cancelleria, utili come fonte dell’evento ma non come originale da notificare;
- documenti QuickOrganizer/testi o import storici, utili nel fascicolo ma non autorevoli per la riconciliazione PST automatica;
- documenti PolisWeb/PST veri, con origine ministeriale e identificativo portale numerico o metadati `pst`/`polisweb`.

Regola anti-regressione: la relata può proporre automaticamente l’originale già acquisito solo quando il documento proviene da PST/PolisWeb o da un identificativo portale ministeriale coerente. Sono escluse fonti `quickorganizer:`, `documenti_ai:`, `manual:` e `upload:`. In caso di ambiguità reale, il software non deve scegliere un documento casuale: deve mantenere il presidio aperto e guidare l’avvocato verso acquisizione/collegamento verificabile.

Test collegati: `tests/test_pst_original_presidio_runtime.py::test_presidio_riconosce_provvedimento_pst_gia_presente_nel_fascicolo` include espressamente due false sentenze QuickOrganizer nello stesso fascicolo e verifica che venga collegata solo `SentenzaDefinitiva_35882174.pdf`.

### Aggiornamento 22/07/2026 - visualizzazione dell'originale PST dentro IUSENTRA

Nel percorso Presidio notifiche → originale PST → relata, il documento ministeriale collegato non deve uscire dal software e non deve aprire una schermata vuota. La prova sul caso Romeo Maria ha confermato che `SentenzaDefinitiva_35882174.pdf` è presente nel fascicolo come documento PST (`DE29EE7F`) e che il lettore diretto `/fascicoli/78D6022C/documenti/DE29EE7F/visualizza?viewer=mobile` renderizza la sentenza. Il problema residuo era limitato alla modale che incorporava il lettore in iframe.

Correzione applicata alla UI comune delle fonti:

- `SourceDocumentModal` usa `allow-same-origin` anche per i lettori interni dei documenti del fascicolo;
- la regola resta tenant-aware perché non cambia la URL risolta dal backend: rende soltanto visibile, dentro IUSENTRA, il documento già autorizzato;
- il testo di errore resta in italiano e indica `Apri originale` o `Scarica` solo come recupero quando il formato non è renderizzabile, non come percorso primario.

Prove automatiche mirate: test React della pagina Agenda/lettore e gruppo Agenda/PEC/fonti/notifiche superati; build React superata. Prova reale finale da ripetere dopo deploy.

### Aggiornamento 22/07/2026 - download verificabile dall'originale collegato

Il percorso Presidio notifiche → originale PST → relata richiede che l'avvocato possa anche scaricare il documento collegato senza uscire dalla pratica. Dopo il test reale, la rotta storica `/scarica` è stata mantenuta come compatibilità, ma il dettaglio Presidi ora preferisce il download dallo stesso viewer interno con `?download=1`. Questa scelta tiene unificati visualizzazione e scaricamento: il documento che si vede nel lettore è lo stesso che viene scaricato.

### Aggiornamento 24/07/2026 - automatismo RAC/RdAC notifiche L. 53/1994

Richiesta utente: completare il generatore notifiche legali con comportamento allineato al decompilato Studio Telematico/QuickOrganizer, senza usare il nome file per decidere il tipo documento, e agganciare automaticamente accettazione e consegna PEC al fascicolo e ai `Presidi notifiche`.

Fonte tecnica controllata sul decompilato locale: `%TEMP%\quickorganizer_decompiled_full\FormSentMailBee.cs`.

Comportamento implementato:

- il piano di invio usa l'oggetto Studio Telematico `Notificazione ai sensi della legge n. 53 - 1994 e succ. mod.` con riferimento pratica `[JQ...]` e `[Notifica_ID:...]`;
- la UI mostra le ricevute attese `ACCETTAZIONE:`, `CONSEGNA:` e `AVVISO DI MANCATA CONSEGNA:` con lo stesso oggetto della PEC inviata;
- dopo l'invio locale il piano prevede archiviazione degli atti notificati con suffisso `(originale notificato)`, lasciando la relata come relata;
- la pipeline PEC legge da header/XML `Message-ID` originario, destinatario e tipo ricevuta, riconcilia RAC/RdAC/mancata consegna nel repository `pec_legal_notification_*`, aggiorna lo stato del presidio e salva l'EML originale nel fascicolo come documento `NOTIFICA`;
- nel fascicolo vengono create attività `NOTIFICA` standard con marcatori in nota, senza aggiungere campi arbitrari ai JSON storici; il controllo prova completa sa leggere quei marcatori;
- l'invio effettivo resta sempre dal PC dell'avvocato tramite canale locale/Local Signer: nessuna rotta abilita SMTP server-side per notifiche legali.

Guardrail eseguiti in questa fase:

- `python -m py_compile pct\notifiche_legali.py pct\pec_pipeline.py pct\pec_notification_presidio\repository_receipts.py`;
- `python -m pytest -q tests\test_notifiche_legali.py tests\test_pec_notification_presidio.py`.

Stato da chiudere prima del report finale: typecheck/build React, integrità UTF-8, rebuild Docker locale, prova visiva reale su `http://127.0.0.1:8080/notifiche-legali` e successivo commit/push/deploy. Nessuna PEC reale è stata inviata durante questi test.

### Aggiornamento 24/07/2026 - prova visuale simulata e blocco anti-race registro PEC

Completata la parte UI collegata all'automatismo RAC/RdAC:

- il controllo relata restituisce il piano di invio anche quando il flusso resta bloccato, marcandolo come simulazione visibile e non come invio pronto;
- il pannello risultato mostra `Invio PEC previsto`, oggetto Studio Telematico con `[JQ...]` e `[Notifica_ID:...]`, ricevute attese `ACCETTAZIONE:`, `CONSEGNA:` e `AVVISO DI MANCATA CONSEGNA:`, archivio automatico nel fascicolo e `Presidio notifiche collegato`;
- il documento notificato viene mostrato come `decreto_fissazione_udienza (originale notificato).pdf`, mentre la relata resta `relata_notifica.pdf.p7m`;
- durante `Conferma soggetto e PEC`, i comandi `Controlla relata` e `Invia PEC` restano disabilitati finche' la prova del pubblico elenco non e' salvata, evitando che il payload parta senza data/ora destinatario;
- il blocco finale rimasto nella prova reale e' solo `Il controllo automatico non ha verificato la PEC del notificante nel pubblico elenco`, perche' la verifica ReGIndE/firma dipende dal dispositivo locale e non e' stata completata in questa simulazione senza invio.

Prova reale locale eseguita su `http://127.0.0.1:8080/notifiche-legali` dopo rebuild Docker:

- container `iusentra-app` healthy e `/api/pronto` `ok=true`, timezone `Europe/Rome`, versione `2.258.1`;
- selezionata pratica `2026/010 - Collaudo automatico post deposito RG 771/2025`;
- selezionato destinatario `Ministero dell'Istruzione e del Merito` con PEC `dgosv@postacert.istruzione.it`;
- compilato allegato manuale `decreto_fissazione_udienza.pdf` con descrizione `Decreto di fissazione udienza da notificare`;
- aperto `Registro PP.AA.`, confermata la consultazione e verificato messaggio di prova salvata nel fascicolo;
- controllata la relata: presente `RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994 E SUCC. MOD.`, assente il vecchio titolo `RELAZIONE DI NOTIFICAZIONE A MEZZO POSTA ELETTRONICA CERTIFICATA`;
- verificato pannello `Invio PEC previsto` con `Notifica_ID`, ricevute attese, archiviazione `(originale notificato)`, presidio notifiche e avviso `Invio effettivo sempre dal PC dell'avvocato`;
- responsive controllato con viewport desktop, tablet `820x1100` e mobile `390x844`: le sezioni `Invio PEC previsto`, `Ricevute attese dal presidio PEC` e `Presidio notifiche collegato` restano nel viewport senza overflow documentale.

Guardrail aggiuntivi eseguiti:

- `python -m pytest -q tests\test_notifiche_legali.py tests\test_pec_notification_presidio.py tests\test_notifiche_legali_preview_ui.py`;
- `npm --prefix frontend run typecheck`;
- `python -m py_compile pct\notifiche_legali.py pct\pec_pipeline.py pct\pec_notification_presidio\repository_receipts.py`;
- `npm --prefix frontend run build`;
- `docker compose build app && docker compose up -d`;
- `Invoke-RestMethod http://127.0.0.1:8080/api/pronto`.

Nessuna PEC reale e' stata inviata e nessuna firma valida e' stata prodotta in questa simulazione: il software ha mostrato correttamente il blocco sul notificante finche' la verifica ReGIndE/firma locale non viene completata sul PC dell'avvocato.
Confronto esempi DOCX utente:

- `modello da seguire realata.docx` usa lo stesso impianto ora generato: titolo `RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994 E SUCC. MOD.`, blocco `HO NOTIFICATO A`, elenco atti con `Natura del documento` e `Contenuto del documento`, chiusura `DICHIARO`/`ATTESTO`, riferimento `[JQ...] [Notifica_ID:...]`;
- `Attestazione di conformità decreto fissazione .docx` conferma che l'attestazione deve essere unica e includere nello stesso testo tutti i documenti conformi estratti dal fascicolo informatico, come ricorso, procura e decreto di fissazione udienza.

### Aggiornamento 24/07/2026 - controllo finale post rebuild RAC/RdAC

Dopo la normalizzazione del fallback data ricevuta PEC e la rimozione dei tag vuoti sui documenti salvati nel fascicolo, la copia Docker locale è stata ricostruita e riavviata su `127.0.0.1:8080`.

Prova visuale reale sulla pagina `Notifiche legali`:

- selezionata la pratica `2026/010 - Collaudo automatico post deposito RG 771/2025`;
- selezionato il destinatario `Ministero dell'Istruzione e del Merito` con PEC `dgosv@postacert.istruzione.it`;
- confermata la verifica su `Registro PP.AA. / PST`, con messaggio visibile di prova salvata nel fascicolo il 24/07/2026 alle ore 16:28;
- ricontrollata la relata: non sono più presenti `Data verifica PEC` o `Ora verifica PEC` mancanti per il destinatario;
- il blocco residuo è solo sulla PEC del notificante/firma locale, perché la verifica ReGIndE del notificante richiede dispositivo/PIN e non è stata completata nella simulazione senza invio;
- portate in viewport e lette le sezioni `Ricevute attese dal presidio PEC`, `Archivio automatico nel fascicolo` e `Presidio notifiche collegato`, con oggetti `ACCETTAZIONE:`, `CONSEGNA:`, `AVVISO DI MANCATA CONSEGNA:`, suffisso `(originale notificato)` e avviso `Invio effettivo sempre dal PC dell'avvocato`.

Guardrail finale eseguito nello stesso giro: py_compile dei moduli notifiche/PEC, pytest mirati notifiche-presidi-UTF8, test confine Local Signer/PEC locale, build React, rebuild Docker locale, `/api/pronto` `ok=true` con timezone `Europe/Rome`.

### Aggiornamento 24/07/2026 - riallineamento ReGIndE silenzioso da decompilato

Richiesta utente: ricontrollare senza inventare passaggi se Studio Telematico esegue la verifica ReGIndE in silenzio e se IUSENTRA deve comportarsi allo stesso modo nel generatore notifiche.

Fonti decompilate controllate in `%TEMP%\quickorganizer_decompiled_full`:

- `QuickOrganizer\PCT.cs`, metodo `RicercaSoggettoExRegInde`: costruisce SOAP `ricercaSoggettoEx` con `codiceFiscale`, chiama `ServiziInterrogazioneRegindeExt/ServiziInterrogazioneSoggetto` con `_WebCertificate` e restituisce la prima PEC trovata;
- `QuickOrganizer\WizardImportaPraticheDaPolisWeb.cs`: durante l'import PolisWeb, se l'avvocato ha codice fiscale e non è già in anagrafica, richiama `RicercaSoggettoExRegInde`, salva `PEC` e `PubblicoElenco = RegInde`;
- `QuickOrganizer\SchedaAnagrafica.cs`: il campo `PubblicoElenco` è anagrafico e contiene `INIPEC-professionisti`, `RegistroImprese`, `RegInde`, `IPA`, `altro`;
- `QuickOrganizer\FormMain.cs` e `QuickOrganizer\BrowserForm.cs`: i comandi ReGIndE e Registro PP.AA. aprono l'area PST autenticata e poi navigano rispettivamente verso `pst_2_2.wp` e `pst_2_8.wp`;
- `FormSentMailBee.cs`: prima della notifica blocca se destinatario, PEC o pubblico elenco mancano; compone ogni destinatario con commento `codice fiscale: ... pubblico elenco: ...`; genera `Relata di notifica.pdf`, la firma con `PCT.SignPDF_WithDigitalSignatureSoftware`, imposta l'oggetto della notifica, salva gli allegati non relata come `(originale notificato)` e carica RAC/RdAC/MDC cercando `Notifica_ID` negli oggetti email.

Correzione applicata solo sul punto divergente:

- IUSENTRA non blocca più la verifica ReGIndE solo perché il campo PIN della firma relata è vuoto;
- il Local Signer prova la chiamata ReGIndE con il certificato Windows/PST selezionato, lasciando al middleware/certificato la richiesta del PIN se necessaria;
- se l'avvocato inserisce il PIN nel comando firma, il wrapper Windows continua a usarlo per autenticare esplicitamente il CSP;
- la firma della relata resta separata e obbligatoria: questa modifica riguarda solo la verifica ReGIndE, non autorizza invio PEC senza relata firmata;
- Registro PP.AA. resta flusso PST/anagrafica come da decompilato: nessuno scraping o conferma inventata viene introdotta nel generatore.

Guardrail eseguiti:

- `python -m py_compile tools\local_signer.py`;
- `python -m pytest -q tests\test_local_signer.py -k reginde`;
- `python -m py_compile pct\notifiche_legali.py pct\pec_pipeline.py pct\pec_notification_presidio\repository_receipts.py tools\local_signer.py`;
- `python -m pytest -q tests\test_notifiche_legali.py tests\test_pec_notification_presidio.py tests\test_local_signer.py -k "notifiche or notifica or reginde or receipt or ricevut or originale or attestazione or relata"`;
- `npm --prefix frontend run build`;
- `python tools\build_dist.py`, con pacchetti Local Signer `1.6.103` Windows/macOS/Linux rigenerati e wrapper `local_signer_windows_http.ps1` incluso nei file di supporto.

Esempi DOCX utente controllati leggendo il contenuto OOXML dei file, non il nome file:

- `Attestazione di conformità decreto fissazione .docx`: attestazione unica con ricorso, procura e decreto di fissazione udienza nello stesso attestato;
- `Attestazione di conformità sentenza.docx`: attestazione singola per sentenza estratta dal fascicolo informatico;
- `modello da seguire realata.docx` e `modello da seguire realata sentenza.docx`: stesso impianto Studio Telematico `RELATA DI NOTIFICA EX ART. 3-BIS...`, destinatari numerati, atti A/B/C, attestazioni per natura del documento, `DICHIARO`, `ATTESTO`, riferimento `[JQ...] [Notifica_ID:...]`.

Nota QA DOCX: il render PNG dei DOCX con la skill documenti non è stato completato perché in questa macchina manca l'eseguibile di conversione LibreOffice/soffice richiesto; il confronto è quindi testuale/strutturale sul contenuto OOXML, mentre la prova visuale finale riguarda la UI IUSENTRA reale.

Stato prova reale: da ripetere sulla copia Docker reale `127.0.0.1:8080` dopo rebuild del commit corrente. Nessuna PEC reale è stata inviata in questa fase.

### Aggiornamento 24/07/2026 - matrice casi notifica e attestazione PDF

Richiesta utente: confrontare tutti i casi di notifica in base al documento da notificare con decompilato Studio Telematico, database reale Montagnese e fonti, senza decidere dal solo nome file.

Fonti incrociate:

- decompilato `%TEMP%\quickorganizer_decompiled_full\FormSentMailBee.cs`: natura documento `OriginalePredispostoAvvocato`, `DuplicatoInformatico`, `AcquisizioneScanner`, `CopiaEstrattaFascicoloInformatico`, generazione `Relata di notifica.pdf`, firma digitale della relata, oggetto con `[Notifica_ID:...]`, archiviazione `(originale notificato)` e recupero `ACCETTAZIONE`/`CONSEGNA`/`AVVISO DI MANCATA CONSEGNA`;
- DB reale produzione Montagnese: `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/studio.db` con `334` fascicoli e `pec_audit.sqlite` con `1.377` PEC e `4.690` allegati; il DB locale `tenant-8bf98719c459` contiene solo `10` fascicoli e non è il campione completo dello studio;
- fascicoli produzione: `11.645` documenti censiti, `1.948` con `(originale notificato)`, `66` gruppi `[Notifica_ID:...]`;
- esempi DOCX utente: relata con titolo `RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994 E SUCC. MOD.` e attestazione unica con ricorso, procura e decreto nello stesso attestato;
- fonti: L. 53/1994 art. 3-bis, DM 48/2013 art. 18/DM 44/2011, specifiche PST 7 agosto 2024 e artt. 196-octies/196-undecies disp. att. c.p.c.

Decisione tecnica applicata:

- il tipo di notifica è guidato da contenuto/metadati del documento; il nome file resta solo recupero debole quando non è disponibile testo leggibile;
- la relata conserva il testo Studio Telematico e cambia per caso processuale tramite il catalogo modelli già presente;
- l'attestazione non viene più prodotta come DOCX finale: l'endpoint React genera `Attestazione_di_conformita.pdf`;
- la UI mostra materialmente `Relata di notifica.pdf` e, quando dovuta, `Attestazione di conformità.pdf`, con pulsante `Scarica PDF`;
- il PDF dell'attestazione è unico per tutti i documenti conformi allegati alla stessa notifica, come da modello Montagnese ricorso/procura/decreto;
- la matrice completa è stata salvata in `artifacts/notifiche-legali/matrice-casi-notifica-montagnese-2026-07-24.md`.

Guardrail mirati eseguiti prima di questa annotazione:

- `python -m py_compile pct\notifiche_legali.py web\services\react_notifiche_legali_bridge.py web\blueprints\api_v1_react.py`;
- `python -m pytest -q tests\test_notifiche_legali.py -k "attestazione_conformita_pdf or matrice_casi_notifica or api_react_notifiche_legali"`;
- `python -m pytest -q tests\test_regia_ui_react.py -k notifiche`.

Stato da chiudere prima del report finale: render visuale del PDF prodotto, build React completa, rebuild Docker reale su `127.0.0.1:8080`, prova visiva materiale in UI, commit/push dei branch gemelli e deploy Hetzner. Nessuna PEC reale è stata inviata.

### Aggiornamento 24/07/2026 - correzione elenco atti relata e firma finale

Durante la revisione utente è emerso un difetto concreto nella relata: l'attestazione PDF prodotta dal software non compariva nell'elenco `I seguenti atti`, gli allegati aggiunti dovevano essere visibili nello stesso elenco finale e la chiusura mostrava una doppia formula `F.to digitalmente da` / `Firmato digitalmente`.

Correzione applicata:

- `_document_rows()` ora elenca tutti i documenti selezionati o aggiunti manualmente;
- se almeno un documento richiede conformità, aggiunge `Attestazione di conformità` come atto autonomo prima della relata;
- `Relata di notifica` resta l'ultima voce dell'elenco;
- la relata renderizzata e la preview modello non aggiungono più la riga `Firmato digitalmente` dopo il nome avvocato;
- la UI mostra un unico `Elenco finale atti della relata`, con lettere A/B/C, così l'avvocato vede subito se l'allegato manuale entrerà nel testo;
- il vecchio riquadro separato `Documenti prodotti dal software` è stato rimosso per ridurre complessità e doppioni.

Guardrail aggiunto:

- `test_relata_elenca_tutti_documenti_attestazione_e_relata_senza_firma_doppia` verifica allegati multipli, attestazione autonoma, ordine dell'elenco e assenza del doppione `Firmato digitalmente` nella relata.

Nessuna PEC reale è stata inviata. Il PIN del certificato comunicato dall'utente deve essere usato solo nell'eventuale prova di firma reale tramite Local Signer, senza salvarlo in file, log o report.

### Aggiornamento 24/07/2026 - distill UI e controlli non inventati

Riesame effettuato sul decompilato `%TEMP%\quickorganizer_decompiled_full\FormSentMailBee.cs`: Studio Telematico non blocca la preparazione della notifica per assenza di una verifica live automatica di ogni PEC, né pretende nel generatore ordinario campi come `Parte rappresentata`, ufficio, numero RG o anno RG quando non sono già disponibili.

Correzione applicata:

- la validazione IUSENTRA non genera più blocker o avvisi visibili per verifica PEC live mancante, dati procedimento vuoti o `Parte rappresentata` non compilata;
- il modello `A difensore costituito` usa `Parte rappresentata` solo se presente, senza renderla campo obbligatorio;
- l'anteprima non elenca più `Data verifica PEC` e `Ora verifica PEC` come dati mancanti;
- la UI Notifiche legali rimuove dal percorso principale il riquadro `Verifica automatica delle PEC`;
- il PIN viene presentato solo come PIN di firma della relata, non come verifica PEC;
- l'avvocato vede subito relata prodotta, elenco atti, attestazione PDF quando dovuta e comando di firma/invio, con la modifica manuale della bozza chiusa in un dettaglio opzionale.

Guardrail mirati eseguiti:

- `python -m py_compile pct\notifiche_legali.py`;
- `npm --prefix frontend run typecheck`;
- `python -m pytest -q tests\test_notifiche_legali.py -k "pec_coerenti or pubblico_elenco_manomessa or studio_telematico_non_blocca or attestazione_automatica or api_react_notifiche_legali or automatici_i_controlli"`.

La prova browser reale su `127.0.0.1:8080`, il rebuild Docker, commit/push e deploy Hetzner restano da completare prima del report finale.

### Aggiornamento 25/07/2026 - tre ingressi documenti per relata/notifica

Chiarimento utente: il flusso Notifiche legali deve gestire solo i tre casi utili all'avvocato, senza wizard o controlli non presenti nel decompilato Studio Telematico:

1. apertura dal fascicolo con documenti già selezionati;
2. apertura dal presidio notifiche, che porta automaticamente il documento da notificare;
3. apertura manuale, in cui l'avvocato vede i documenti del fascicolo e spunta quali importare.

Correzione applicata:

- i link del presidio relata prodotti dal fascicolo ora passano anche `documenti=<id_documento>` e `ingresso=presidio`;
- la pagina `/notifiche-legali` distingue la provenienza dal parametro `ingresso`: `Fascicolo/documenti selezionati`, `Presidio/porta il documento`, `Manuale/vedi e spunta`;
- l'ingresso manuale non seleziona nulla in automatico, ma mostra i documenti del fascicolo e inserisce in relata solo quelli spuntati;
- l'attestazione di conformità PDF viene generata solo se uno dei documenti inclusi la richiede, ed è una sola attestazione cumulativa per tutti i documenti conformi;
- l'elenco finale atti resta unico: documenti selezionati, eventuale `Attestazione di conformità.pdf`, poi `Relata di notifica.pdf`;
- il vecchio presidio visibile di verifica automatica PEC non è stato reintrodotto.

Prova reale locale eseguita su Docker `127.0.0.1:8080`, container `iusentra-app` healthy, `/api/pronto` `ok=true`, `versione=2.258.2`, fuso `Europe/Rome`, dopo rebuild completo del bundle React:

- caso fascicolo: `DD242366` aperto con `documenti=BB94330C`; modalità visibile `Fascicolo documenti selezionati`, `Ordinanza_32473463.pdf` spuntata, elenco finale con documento, `Attestazione di conformità.pdf` e `Relata di notifica.pdf`;
- caso presidio: `DD242366` aperto con `documenti=BB94330C&ingresso=presidio`; modalità visibile `Presidio porta il documento`, documento già incluso dal presidio notifiche, stesso elenco finale conforme;
- caso manuale: `DD242366` aperto senza `documenti`; modalità visibile `Manuale vedi e spunta`, 13 documenti del fascicolo visibili, zero selezioni iniziali, poi `Ordinanza_32473463.pdf` inserita solo dopo click reale sulla spunta;
- `Vedi attestazione` apre l'anteprima dell'`Attestazione di conformità.pdf`; `Scarica PDF` resta disponibile;
- `Controlla relata` esegue la simulazione senza invio; `Invio PEC` resta bloccato perché firma relata e approvazione finale non sono state acquisite.

Il fascicolo temporaneo `CODXPRSD` della prova intermedia è stato rimosso da SQLite, mirror JSON, scadenziario, audit tecnico, documenti fisici e dati OCR/AI; il controllo finale non trova più quel marker nel tenant locale. Nessuna PEC reale è stata inviata, nessun PIN è stato usato o salvato e il campo PIN visibile nella sessione browser è stato svuotato.

### Aggiornamento 25/07/2026 - ReGIndE locale consultabile in Notifiche legali

È stata aggiunta la base governata per avere ReGIndE utilizzabile dentro IUSENTRA senza copiare dati nel repository o sul server pubblico:

- `tools/reginde_sync_cache.py` sincronizza i soggetti ReGIndE tramite Local Signer/certificato, pagina per pagina, in `data/local/reginde/`;
- la cache locale produce pagine JSONL, SQLite deduplicato, stato di ripresa e manifest, tutti esclusi da Git;
- il tool crea, quando disponibile, un indice FTS5 per ricerca rapida sul registro completo;
- `GET /api/v1/ui/notifiche-legali/reginde` legge la cache in sola lettura e restituisce al massimo i destinatari richiesti dalla ricerca;
- la pagina React `/notifiche-legali` usa lo stesso campo `Cerca indirizzo o soggetto` per includere anche risultati ReGIndE locali con badge dedicato;
- la verifica finale utile alla notifica resta quella puntuale e certificata tramite Local Signer/PST, salvata nel fascicolo con data/ora ed evidenza.

Prove eseguite senza invio PEC:

- esportazione pagina PST `pst_2_2.wp`: 11.726 enti e 7 ruoli;
- prova certificata ReGIndE su Avvocatura dello Stato di Milano: PEC `ads.mi@mailcert.avvocaturastato.it`, `verified=true`;
- metodo WSDL `elencoPaginatoSoggetti`: `da=1,count=1` HTTP 200;
- prima tranche reale sync: 5 pagine, 250 soggetti distinti, prossimo indice 251;
- prova reale UI locale su `127.0.0.1:8080`: login tenant `studio-montagnese`, ricerca `Marta Barsotti`, risultato `MARTA BARSOTTI` con PEC `barsotti.marta@ordineavvocatiasti.eu`, badge `ReGIndE`, selezione con click reale e riepilogo `Fonte PEC: reginde`;
- verifica API autenticata `GET /api/v1/ui/notifiche-legali/reginde?q=Marta%20Barsotti&limit=5`: HTTP 200, `ok=true`, primo risultato ReGIndE coerente;
- verifica visiva pagina Notifiche: focus ricerca, hover card selezionata, scroll completo, responsive desktop/tablet/mobile senza overflow orizzontale di pagina;
- `python -m pytest tests\test_reginde.py tests\test_reginde_cache_search.py tests\test_reginde_sync_cache.py -q`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`.

Nota operativa: la cache completa può essere popolata progressivamente con `--full` o a tranche controllate. Il PIN del certificato non viene scritto in file, stato, manifest, log o report.

### Aggiornamento 25/07/2026 - Registro PP.AA. locale per notifiche

È stato verificato sul PST il percorso `Registro PP.AA.`: la pagina ufficiale `pst_2_8.wp` apre il modulo `pst_2_8_2.wp`, con ricerca per `denominazione`, `pec` e `codFiscale`. Non è emerso un export JSON completo o una paginazione totale del registro; il dato utile va quindi acquisito tramite consultazioni puntuali/autenticate e salvato in cache locale governata.

Correzione applicata:

- aggiunto `tools/registro_ppaa_sync_cache.py` per alimentare `data/local/registro_ppaa/registro_ppaa_cache.sqlite`;
- aggiunto `GET /api/v1/ui/notifiche-legali/registro-ppaa`, autenticato e read-only;
- la pagina React `/notifiche-legali` cerca nello stesso campo sia ReGIndE sia Registro PP.AA.;
- i risultati PP.AA. entrano come destinatari selezionabili con `fontePecSuggerita=registro_ppaa`, ruolo `pa` e badge `Registro PP.AA.`;
- la verifica automatica tramite Local Signer tratta `registro_ppaa` come servizio autenticato con certificato, senza conferma manuale inventata;
- i file SQLite, manifest e pagine importate restano runtime locali ed esclusi da Git.

Guardrail eseguiti senza invio PEC:

- `python -m pytest tests\test_reginde_cache_search.py tests\test_reginde_sync_cache.py tests\test_registro_ppaa_sync_cache.py tests\test_notifiche_legali.py -q`;
- `python -m compileall tools\reginde_sync_cache.py tools\registro_ppaa_sync_cache.py web\services\reginde_cache_search.py web\blueprints\api_v1_react.py pct\notifiche_legali.py`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`.

### Aggiornamento 26/07/2026 - Registro PP.AA. provato nella UI reale

Dopo rebuild Docker locale della copia reale `127.0.0.1:8080`, container `iusentra-app` healthy e `/api/pronto` `ok=true`, è stata ripetuta la prova materiale della pagina React `/notifiche-legali`:

- record PP.AA. locale usato: `AVVOCATURA DELLO STATO DI MILANO`, CF `97021490152`, PEC `ads.mi@mailcert.avvocaturastato.it`;
- ricerca `Avvocatura Milano`: risultato PP.AA. visibile con badge `Registro PP.AA.`;
- click reale sul risultato: destinatario selezionato e riepilogo con `Fonte PEC: registro_ppaa`;
- click su stato selezionato e secondo click di ripristino: il controllo resta coerente e la fonte non viene persa;
- scroll fino al fondo pagina: restano presenti `Invia PEC`, `Fonti operative`, `Presidi` e `Relata`;
- mobile `390x844` e tablet `768x1024`: risultato cliccabile, riepilogo leggibile e nessun overflow orizzontale;
- nessun invio PEC, nessun PIN usato, nessuna ricevuta artificiale registrata.

È stato corretto anche il microcopy del motore di ricerca registri: la UI non espone più frasi del tipo `nella elenco locale`, ma usa testi operativi come `Ricerca nel Registro PP.AA. locale...` e `Nessun soggetto trovato in ReGIndE locale.`.

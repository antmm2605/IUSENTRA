# Audit integrale documenti, scadenze, agenda e flusso economico

Data di apertura: 13/07/2026
Studio verificato: Studio Legale Giuseppe Montagnese
Fonte operativa dati: SQLite tenant-aware sul server di produzione
Stato complessivo: **APERTO**

Questo documento è il registro unico dei requisiti richiesti. Lo stato può diventare `CHIUSO 100%` soltanto quando ogni controllo obbligatorio è completato con prova automatica, prova reale locale e prova reale in produzione. Un test sintetico non sostituisce il click reale.

## 1. Lettura autonoma di tutti i documenti

- [x] Ogni documento del fascicolo riceve identificativo, impronta e stato persistente.
- [x] Un documento invariato con testo già estratto non viene riletto dal file.
- [x] Un vecchio record dichiarato pronto ma privo di testo viene rigenerato una sola volta.
- [x] Il secondo ciclo sullo stesso documento riparato esegue zero nuove letture.
- [x] I documenti generici non vengono più chiusi usando soltanto i metadati: vengono estratti e classificati una volta.
- [x] I documenti tecnici vengono letti e classificati, ma non producono false scadenze senza un segnale processuale autonomo.
- [x] Le scansioni con foglio centrale e ampi margini vengono ritagliate prima dell'OCR: i tre PDF reali prima vuoti producono ora 5.381, 5.860 e 1.497 caratteri.
- [x] Le vecchie versioni indicizzate senza testo non generano più un falso errore quando la stessa impronta ha una versione successiva leggibile.
- [x] L'audit conclusivo esamina tutti i documenti, non soltanto quelli già classificati come operativi.
- [x] Il riepilogo di ruolo con importo CU esplicito non viene più scambiato per esenzione a causa di una semplice etichetta vuota; le esenzioni motivate restano prioritarie.
- [ ] Inventario produzione: zero documenti fisicamente disponibili senza testo estraibile o classificazione governata.
- [ ] File assenti, cifrati, corrotti o non decodificabili: zero casi irrisolti; ogni causa deve essere esplicita e verificata.
- [ ] Secondo ciclo globale di produzione: `processed_new_documents=0` e `indexed_documents=0`.

Formati obbligatori: PDF nativo, PDF scansionato/OCR, PDF firmato P7M, EML, MSG, XML, TXT, DOC/DOCX, ODT/RTF, XLS/XLSX/CSV, immagini, ZIP e contenuti annidati supportati.

## 2. ZIP e allegati ricevuti via PEC

- [x] Estrazione ricorsiva del contenuto ZIP già disponibile nel motore documentale.
- [x] Test automatico: decreto di fissazione udienza dentro ZIP, data consolidata e secondo ciclo senza rilettura.
- [ ] Prova reale con ZIP proveniente da PEC dello studio.
- [ ] Deduplicazione verificata quando lo stesso atto compare nello ZIP e come allegato separato.
- [ ] P7M o immagine dentro ZIP verificati su contenuto reale.

## 3. Scadenze, udienze e modalità

- [x] Parsing di date numeriche e date italiane testuali.
- [x] Distinzione tra udienza e termine per deposito note.
- [x] Eliminato il falso doppione causato dalla parola `deposito` nella frase precedente.
- [x] Modalità in presenza, da remoto/audiovisiva e trattazione scritta persistite quando presenti.
- [x] Link audiovisivo e fonte documentale conservati nel dettaglio operativo.
- [x] Date trascorse non vengono esposte come prossima scadenza futura.
- [ ] Tutti i fascicoli attivi con evidenza futura devono mostrare la data in UI e nello scadenziario.
- [ ] `RG 1084/2026` deve restare senza data soltanto finché non arriva una comunicazione contenente la prossima attività.
- [ ] Audit produzione finale: nessuna data futura estratta ma non consolidata.
- [ ] Audit visivo dell’elenco fascicoli: nessun `n.d.` dovuto a un documento non letto.

Baseline del 13/07/2026 prima del recupero completo: 137 fascicoli attivi, 34 con data futura consolidata, 103 senza data visibile; 70 dei 103 avevano almeno un documento non indicizzato, per 1.678 documenti mancanti complessivi. Una data futura già recuperabile era presente in `RG 143/2026` (`31/08/2026`).

## 4. Contributo unificato, liquidazioni e proforma

- [x] Ricevuta PagoPA: importo del contributo distinto da commissione e totale addebitato.
- [x] Avviso PagoPA/CBILL: precedenza alla ricevuta pagata quando presente.
- [x] Liquidazione del giudice estratta e consolidata dai documenti compatibili.
- [x] Secondo ciclo economico non richiama il parser su un documento invariato.
- [ ] Inventario produzione finale: contributi estratti uguali ai contributi consolidati.
- [ ] Inventario produzione finale: liquidazioni estratte uguali alle liquidazioni consolidate.
- [x] Generazione automatica di una sola proforma quando maturano i requisiti economici, coperta da test con importo fascicolo e sentenza fisica non indicizzata.
- [x] Conferma esplicita dell’avvocato prima della fattura definitiva: la UI chiede conferma e l'API rifiuta la conversione priva del relativo consenso.
- [x] Nessuna proforma o fattura duplicata al secondo ciclo automatico.
- [x] Impostazioni Fatturazione full React con regime, opzioni fiscali, spese generali, pagamento, scadenza e BIC/SWIFT tenant-aware.
- [x] Caso reale locale `Alessi Robertino`: campi separati `Nome: Robertino` e `Cognome: Alessi`, senza duplicazione nel form o nell'XML.
- [x] CAP dello studio `89029` ricavato dai dati territoriali; nessun CAP inventato per il destinatario privo di comune e indirizzo.
- [x] Click reale del comando `Nuova proforma` in produzione e prova responsive completa del form e delle impostazioni, senza creare o emettere documenti.
- [ ] Click reale: proforma, conferma, successiva fattura e collegamento al fascicolo.

## 5. Apprendimento governato e fonti

- [ ] Coda diagnostica automatica per documento non riconosciuto: fascicolo, documento, impronta, testo disponibile, campo atteso, motivo e versione parser.
- [ ] Ricerca limitata a fonti ufficiali e cataloghi governati per proporre nuove regole.
- [ ] Ogni nuova regola deve avere fonte, versione, test su corpus storico e controllo regressioni.
- [ ] Nessuna regola legale può auto-attivarsi da una fonte web generica o non verificata.
- [ ] Payload e procedure di riconoscimento documentati e richiamabili.

## 6. Planner Agenda

- [x] Planner spostato prima delle metriche per essere visibile subito.
- [x] Comando icona per ingresso e uscita dalla modalità tutto schermo reale.
- [x] Ripiego in-app governato quando il browser nega il fullscreen nativo.
- [x] Evento con gerarchia: orario, tipo legale, parte/fascicolo, ufficio o luogo.
- [x] Breakpoint notebook: calendario a larghezza piena e rail sotto il planner.
- [x] Typecheck, build React e contratto statico Agenda superati.
- [x] L'evento evidenziato espone subito attività legale, RG, parte/cliente e orizzonte temporale.
- [x] Click reale Agenda → Scadenziario eseguito su `127.0.0.1:8080`: il dettaglio selezionato resta nella prima schermata con attività, parte, RG, ufficio, scadenza, priorità e responsabile.
- [x] Navigazione interna senza ricaricamento della shell verificata sul click reale.
- [x] Primo payload del dettaglio ridotto a 7.008 byte; il payload completo da 597.917 byte viene caricato in secondo piano e ripristina tutte le 180 righe.
- [x] Verifica reale a 1366x768: nessun taglio o sovrapposizione nel riepilogo della scadenza selezionata.
- [x] Scroll materiale completo dello Scadenziario collegato, dall'inizio al centro, fino al fondo e ritorno in alto.
- [x] Guardrail mirati Agenda/Scadenziario: 22 test superati; typecheck e build React superati.
- [x] Click reali su Giorno, Settimana e Mese: l'attività mantiene titolo legale, RG, parte e orizzonte temporale in tutte le viste.
- [x] Click reali su periodo precedente, successivo e Oggi: giugno, luglio e agosto 2026 vengono attraversati e Oggi ripristina il periodo corrente con i dati reali.
- [x] Ricerca e filtro reali: corrispondenza per parte, filtro Scadenze e stato vuoto Udienze verificati.
- [x] Tutto schermo reale aperto e chiuso: il planner occupa la superficie disponibile e conserva attività e comandi.
- [x] Apertura reale dell'attività dalle viste Giorno e Mese: entrambe raggiungono lo stesso dettaglio Scadenziario corretto.
- [x] Ritorno browser dal dettaglio: vista, data, ricerca e filtro Agenda vengono conservati nell'indirizzo e ripristinati materialmente.
- [x] La timeline del fascicolo non scarta più le attività `UDIENZA`: note e collegamenti audiovisivi restano disponibili anche fuori dalle sezioni Agenda e Scadenziario.
- [x] Agenda e Scadenziario espongono il collegamento audiovisivo strutturato e il relativo stato di verifica.
- [x] Centro notifiche e Web Push ricevono lo stesso evento senza duplicarlo; il link esterno è azionabile dal dispositivo soltanto quando supera la validazione del dominio.
- [x] Arricchimento incrementale presidiato: una notifica già creata senza link viene aggiornata quando il PDF/ZIP aggiunge il collegamento, torna non letta e genera un nuovo push una sola volta; i duplicati invariati non rispondono.
- [x] Guardrail automatici rieseguiti il 17/07/2026: 86 test mirati su PEC, comprensione udienze, piano giornaliero, timeline fascicolo, Agenda, Scadenziario, notifiche e Web Push; contratto React, copertura UI, service worker, conservazione asset e UTF-8.
- [x] Sicurezza collegamento: l'azione esterna accetta solo domini audiovisivi ammessi con corrispondenza esatta o sottodominio e link verificato; un dominio somigliante viene respinto.
- [x] Budget build: chunk JavaScript massimo `369,24 kB`, nessun JavaScript o CSS oltre `500 kB`.
- [x] Test reale locale su desktop ampio.
- [x] Test reale locale su notebook 14 pollici, viewport 1366x768, limitato al passaggio Agenda → dettaglio Scadenziario.
- [x] Test reale locale su mobile per lo Scadenziario; Agenda verificata su desktop e notebook.
- [ ] Test reale produzione sugli stessi viewport.
- [x] Hover, selezione, assenza di errori e contrasto del dettaglio audiovisivo verificati; focus completo dell'intera pagina resta nel controllo trasversale.
- [x] Scroll completo dall’inizio al fondo della pagina e ritorno in alto.

Click obbligatori: giorno, settimana, mese, periodo precedente, oggi, periodo successivo, ricerca, filtro, aggiorna, tutto schermo, esci da tutto schermo, nuova attività da fascia oraria, drag and drop, apertura evento, modifica, origine, preferenze, calendari, importazione, esportazione, promemoria, scadenza collegata, timesheet e Lex.

Limite aperto del 13/07/2026: il controllo viewport del browser integrato ha accettato il comando mobile ma non ha modificato il viewport effettivo, rimasto a 1366x768. La prova mobile non è quindi considerata valida e resta aperta; l'override temporaneo è stato ripristinato.

## 7. Visualizzatore documenti mobile

- [x] Individuate le due superfici React del fascicolo che usano il lettore mobile: dettaglio fascicolo e preparazione deposito.
- [x] Pinch-to-zoom governato nel contenuto mobile.
- [x] Pulsanti riduci, adatta e ingrandisci con tooltip e nomi accessibili.
- [x] Pan bidimensionale del documento ingrandito senza spostare il modal React.
- [x] Limiti minimi e massimi stabili dal 75% al 300%, con passi pulsante del 25%.
- [x] Stato zoom preservato durante la lettura e ripristinato caricando un altro documento.
- [x] Documento reale locale `ScrittiDifensivi_29334341.pdf.p7m` aperto nel lettore a pagine: entrambe le pagine risultano visibili e leggibili.
- [x] Click reali su Ingrandisci, Riduci e Adatta: verificati 150%, massimo 300%, minimo 75% e ripristino 100%; i comandi si disattivano ai limiti.
- [x] Apertura e chiusura dell'anteprima verificate sia dal fascicolo `DD242366` sia dalla fase Documenti del deposito dello stesso fascicolo.
- [x] Le due superfici React usano lo stesso URL documento e lo stesso collegamento di scaricamento, senza duplicare il file.
- [x] Test mirati del lettore mobile PDF superati: 2 test.
- [ ] Test reale locale e produzione su viewport mobile con documento leggibile.
- [ ] Nessuna sovrapposizione tra documento, toolbar, navigazione mobile e assistente.

## 8. Coerenza grafica e DESIGN.md

- [x] Creato `DESIGN.md` dalla grafica e dai token reali del prodotto.
- [x] Creato `.impeccable/design.json` con estensioni per elevazione, motion, breakpoint e sette componenti reali.
- [x] Documentati colori, tipografia, spaziatura, raggi, elevazione, componenti, stati e responsive.
- [ ] Preservare il linguaggio visivo IUSENTRA e correggere soltanto incoerenze dimostrate.
- [x] Vietati nel sistema di design testi o riferimenti tecnici a prodotti terzi nella UI.
- [x] Ricaricato il contesto di design; il planner mantiene il linguaggio visivo IUSENTRA.

North Star proposta: **Il Registro Operativo**. La pagina deve sembrare uno strumento di lavoro legale affidabile, denso e leggibile, non una dashboard SaaS generica né una superficie marketing.

## 9. Prestazioni e idempotenza

- [x] Salvataggi attività documentali raggruppati in una transazione per lotto.
- [x] Recupero storico: mirror JSON rigenerato una sola volta alla fine; SQL resta la fonte operativa.
- [x] Primo confronto produzione: 25 documenti da 64 secondi a 18 secondi dopo l’ottimizzazione.
- [ ] Misura finale del recupero completo e del secondo ciclo vuoto.
- [ ] Nessuna regressione sul caricamento Agenda, Fascicoli e Documenti.
- [ ] Nessun job duplicato, nessun secondo servizio Local Signer, nessun processo app parallelo.

## 10. Accettazione, deploy e chiusura

- [ ] Test mirati backend e frontend tutti verdi.
- [ ] UTF-8, italiano, date `Europe/Rome` e accessibilità verificati.
- [ ] Docker locale reale ricostruito e healthy su `127.0.0.1:8080`.
- [ ] Prova reale locale completa con click e dati osservabili.
- [ ] Commit e push sui due branch gemelli allo stesso SHA.
- [ ] Tutti i check GitHub completati, zero failure e CodeQL verde.
- [ ] Deploy Hetzner sullo stesso SHA.
- [ ] Un solo container applicativo `iusentra-app`, healthy.
- [ ] Scheduler riattivato e job incrementali osservati.
- [ ] `https://app.iusentra.it/api/pronto` corretto.
- [ ] Prova reale produzione completa con click e dati osservabili.
- [ ] Audit finale eseguito due volte: primo ciclo completo, secondo ciclo senza riletture.
- [ ] Repository pulito, branch e worktree conformi.
- [ ] Stato del presente documento aggiornato a `CHIUSO 100%` soltanto dopo tutte le prove.

## Evidenze già prodotte

- `artifacts/react-migration/deadline-coverage-production-raw.json`
- `artifacts/react-migration/document-presidio-production-batch.json`
- `artifacts/react-migration/document-presidio-production-profile.txt`
- `artifacts/react-migration/document-presidio-production-profile-batched.txt`
- `artifacts/react-migration/document-presidio-production-batch-optimized.json`
- `artifacts/react-migration/presidio-scadenze-documenti-fascicolo-2026-07-12.md`
- `artifacts/react-migration/procedura-deposito-telematico.md`
- `artifacts/react-migration/fatturazione-proforma-impostazioni-2026-07-13.md`
- `artifacts/react-migration/pec-agenda-scadenziario-visual-audit.json`
- `artifacts/react-migration/pec-agenda-scadenziario-visual/agenda-controlled-hover.png`
- `artifacts/react-migration/pec-agenda-scadenziario-visual/agenda-controlled-source-modal.png`
- `artifacts/react-migration/pec-agenda-scadenziario-visual/scadenziario-controlled-desktop.png`

## Regola di report finale

Il report finale deve riportare numeri, click eseguiti, pagine aperte, stati osservati, tempi, errori risolti e limiti residui. Se anche una sola riga obbligatoria resta aperta, il lavoro non può essere dichiarato completato, funzionante, verde o conforme al 100%.

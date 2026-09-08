# Catalogazione unica e acquisizione PST — 06/09/2026

Stato: intervento aperto. L'aggiornamento seguente sostituisce lo stato storico descritto nelle sezioni successive.

## Aggiornamento operativo: OCR integrato e catalogo v23

pdf-inspector 1.17.0 è ora installato nelle immagini Docker locali di app, scheduler e worker OCR. Modelli PP-OCRv6, PDFium e ONNX Runtime sono predisposti con verifica SHA-256. Ogni documento è letto con `offline=True`; Tesseract resta lo specialista dei campi brevi nei riquadri. Nessun documento privato inviato a Firecrawl o ad altri OCR esterni.

- Causa accertata del testo inutilizzabile: 13 file con estensione PDF erano contenitori CAdES. Ora viene letto il PDF incapsulato; un errore non produce testo binario indicizzato come pronto. Originali invariati.
- Classificazione e prove salvate insieme mediante savepoint. Il catalogo è aggiornato senza attivare automazioni estranee di sentenza, calendario o adempimenti. Conteggi da SQL, non assunti pronti.
- Intestazioni prima delle citazioni: sentenza, attestazione, provvedimento generico, atti di parte, procura, modulo, verbale/accordo di mediazione, ricevute PEC, proforma e documento fiscale distinti.
- XML FatturaPA: tutti i corpi del lotto, numero con zeri iniziali, data italiana, valuta e totale in euro quando dichiarato EUR. RG citati separati dai dati della pratica. I dettagli hanno posizione, impronta e peso zero: non aumentano artificialmente la confidenza.
- Eliminato il limite di 32 riquadri; un timeout su un riquadro segnala la posizione da verificare senza eliminare la lettura degli altri. Test con 40 riquadri.
- Ricerca ufficiale e limiti: `docs/specs/ministero/CATALOGAZIONE_DOCUMENTALE_MATRICE_20260906.md`.

Prova materiale eseguita nella scheda di collaudo del browser integrato su `http://127.0.0.1:8080/fascicoli/DD242366#documenti`: aggiornamento catalogo, successo osservabile, prova della sentenza con RG letto 1025/2024, originale di sette pagine aperto nel lettore e pulsante Stampa presente. Numero della pratica non riscritto. Le righe solo censite dal portale mostrano «Da acquisire».

Caricato dalla UI un XML controllato privo di dati personali, documento `2F4FD8D3`, marcato «COLLAUDO TECNICO LOCALE»: osservati entrambi i numeri `0005/COLLAUDO` e `0006/COLLAUDO`, date 06/09/2026 e importi € 1.234,56 e € 45,67. Preview XML interna aperta anche a larghezza 390 px. Nessun invio, pagamento, firma o deposito eseguito.

Al termine del collaudo il solo XML artificiale è stato eliminato tramite «Elimina» e «Conferma» nella UI. Verificati nuovamente 16 documenti del fascicolo e assenza del file di collaudo dall'elenco. Nessun originale dello studio eliminato; la sorgente XML controllata resta nella cartella temporanea locale ed è riutilizzabile.

La verifica visiva v22 ha intercettato una regressione su `procura-speciale-sostanziale-per-la-mediazione-civile.docx` (`060B5CB7`): il modulo non ha titolo e inizia direttamente con la dichiarazione di conferimento. La regola v23 richiede congiuntamente apertura «Il sottoscritto», formula di conferimento e organismo di mediazione; i campi vuoti lo distinguono da una procura compilata. Aggiornamento v23 cliccato realmente sulla copia 8080: osservati «Modulo di procura speciale per la mediazione», formula probatoria, sette riferimenti e avvertenza che non prova una procura conferita. Aperto il DOCX nel lettore e scorso fino alla firma e alle istruzioni finali. Conferma professionale, firma e invio non azionati.

Nel lettore DOCX è emersa una diagnostica inglese del convertitore. Sostituita con avvertenza italiana sulle differenze di impaginazione, distinta dall'avvertenza per altri elementi non riprodotti. Il documento e i controlli di sicurezza della conversione non cambiano. Messaggio italiano osservato materialmente dopo ricostruzione locale; 31 test lettore/UTF-8 superati in 1,62 secondi. Non presentare una preview Word come riproduzione tipografica certificata dell'originale.

Verifica finale della scheda reale: 16 documenti, 16 catalogati/proposti, zero confermati dall'avvocato, zero in attesa indice e zero richieste di revisione su questo campione. Le righe censite senza file restano separate «Da acquisire»: questi numeri non dimostrano una nuova acquisizione dei 51 documenti di produzione. Lettore Word controllato desktop, tablet 900 px e mobile 390 px, scroll fino al fondo, avviso leggibile e focus da tastiera sul controllo Scarica senza azionarlo. Nessun overflow orizzontale osservato a 900 px; a 390 px pagina 375 px entro viewport. La Performance API non è esposta dal canale browser: nessun nuovo dato di velocità di navigazione viene dedotto da quella richiesta fallita. Resta valido soltanto il benchmark OCR documentato separatamente.

Prova PostgreSQL viva: `scripts/verify_document_catalog_postgres.py` sul servizio locale, schema casuale temporaneo rimosso in `finally`, nessuna tabella preesistente modificata. Verificati pipeline, dettaglio numero, filtro tenant, rollback atomico e riutilizzo della connessione. Il primo assert sull'ordine delle prove a pari peso/data è stato corretto confrontando ID e contenuto: SQL non garantisce l'ordine delle parità.

Test mirati nei report Pytest: ultimi 66 test identità, dettagli e pipeline superati in 11,85 secondi sulla v23; Ruff mirato superato. Typecheck e build locale superati. Accettazione complessiva, gate di rilascio, riallineamento asset, commit/push e deploy Hetzner ancora aperti. Il collaudo PIN dei sette provvedimenti esclusi è separato e non risulta eseguito da questa attività. Le sezioni successive conservano la cronologia: gli stati iniziali non sostituiscono questo aggiornamento.

## Aggiornamento acquisizione da dispositivo — 06/09/2026

Il controllo per acquisire documenti da scanner Windows, webcam o fotocamera di dispositivo mobile è stato portato all'inizio della sezione `Documenti e atti`, sopra il form `Carica documenti`, con etichetta visibile `Acquisizione da dispositivo` e pulsante `Scanner / webcam / fotocamera`. Il salvataggio usa lo stesso endpoint governato del caricamento documenti del fascicolo, con `classificazione_modalita=automatica`, anteprima obbligatoria e conferma esplicita prima della persistenza.

La modifica non tocca la logica PST/PolisWeb, il Wizard, il Local Signer, la firma, la firma multipla, le notifiche o il deposito telematico. Il canale scanner continua a passare dal servizio locale dell'avvocato; webcam e fotocamera usano le API browser e restano soggette ai permessi del dispositivo.

Prova reale locale dopo rebuild Docker e refresh della shell React: aperta una nuova scheda del browser integrato su `http://127.0.0.1:8080/fascicoli/DD242366?scanner_check=202609061905#documenti`. Osservato il riquadro prima di `Carica documenti`; cliccato `Scanner / webcam / fotocamera`; osservati titolo `Acquisisci documenti`, canali `Scanner Windows`, `Webcam / fotocamera`, `Scatta dal telefono`, destinazione `RG 1025/2026` e messaggio che le pagine entrano in `Documenti e atti` solo dopo conferma. Non sono stati avviati scanner, fotocamera o salvataggi reali in questo passaggio.

Fonti PST di perimetro riconsultate il 06/09/2026:

- Portale Servizi Telematici, sezione servizi e consultazione registri: `https://pst.giustizia.it/PST/it/scopri_di_piu.page`.
- Specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento 7 agosto 2024: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429`.
- Documentazione servizi web PCT v1.66: `https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.66.pdf`.

Test mirati eseguiti dopo l'aggiornamento UI: contratti acquisizione e strumenti documentali, test JavaScript del canale scanner/camera, typecheck React, build Vite e suite catalogo/documenti. Il primo reload del browser integrato conservava asset React vecchi; la scheda pulita ha caricato `2.280.0` e il controllo è risultato visibile. La prova PIN PST resta demandata al collaudo con l'avvocato perché richiede token e finestra nativa.

## Diagnosi sul dato reale

Fonte di verità: SQLite tenant-aware, non mirror JSON. Il collaudo riguarda il fascicolo di produzione 010701E9, R.G. 1025/2024, Tribunale di Palmi. L'importazione ha registrato 35 nuovi documenti e 9 aggiornamenti; sette provvedimenti sono stati esclusi dall'opzione inviata dalla UI. Il fascicolo contiene 51 record e 51 file fisici verificati nella diagnosi precedente. L'aggiornamento dei sette esclusi richiede un nuovo collaudo PST: non si presume eseguito.

La catalogazione mostrava anche assegnazioni di hash precedenti: l'ordinamento decrescente era annullato dalla sovrascrittura nel dizionario per document_id. Il contesto strutturato non usava l'oggetto del fascicolo e i dati annidati del profilo. La corrispondenza esatta «Vendita di cose immobili» esiste nel catalogo ministeriale PST, codice 140011, famiglia «Contratti e obbligazioni varie».

La lettura del PDF reale Documento_33584995.pdf identifica una ricevuta PEC di avvenuta consegna, con messaggio inoltrato per la registrazione della sentenza. Il PDF Ordinanza_32473463.pdf reca nel piè di pagina «Decreto di fissazione udienza»: titolo portale, contenuto e richiami ad altri provvedimenti non vanno confusi.

## Modifiche in corso

- Importazione dell'intera selezione, compresi i provvedimenti; ricalcolo dei presenti dai documenti restituiti dopo l'importazione, senza mutare trasporto PST, PIN, Local Signer o firma.
- Catalogo SQL unico alimentato dopo l'indicizzazione, confrontato con l'hash del contenuto corrente. Storico conservato; correzioni manuali sullo stesso contenuto preservate.
- Contesto documentale derivato da corrispondenza esatta e univoca con gli XSD PST, con codice, schema e impronta del catalogo. Nessuna modifica automatica al profilo del deposito.
- Una sola lista React con le azioni originali dei documenti e la relativa prova di catalogazione. Fonti normative e documentali aggiunte senza aumentare artificialmente la confidenza.
- Nessuna nuova tabella: repository SQL già comune a SQLite e PostgreSQL. Parità e regressioni ancora da verificare.

## Fonti ufficiali

- Ministero della Giustizia, schemi XSD e codici oggetto: https://pst.giustizia.it/PST/it/download.page ; catalogo locale governato da pct.pratiche_collegate_catalog.
- AgID, Allegato 5 alle linee guida documentali: https://www.agid.gov.it/sites/default/files/repository_files/all.5_metadati.pdf . Metadati e aggregazioni, non certificazione automatica di conformità o conservazione.
- D.P.R. 68/2005, art. 6, testo ufficiale MEF: ricevute PEC di accettazione e avvenuta consegna.
- D.M. 2 novembre 2005, Gazzetta Ufficiale 15/11/2005, codice redazionale 05A10742: regole tecniche PEC.
- Norme di settore già nel registro versionato: collegate al profilo pertinente, senza inventare precedenti giurisprudenziali.

## Verifiche e rilascio

- Typecheck React eseguito prima delle ultime integrazioni: superato; da ripetere.
- Backup strutturato pre-hotfix verificato il 06/09/2026: due database SQLite, quick_check ok; conservato un backup strutturato secondo la retention, sostituito il precedente dopo la validazione.
- Prova visiva produzione e locale 127.0.0.1:8080: non ancora eseguita sulle modifiche.
- Test mirati, commit, push dei branch gemelli, deploy definitivo e allineamento dello stesso commit: ancora da eseguire.
- Non è dimostrata una catalogazione perfetta universale: la confidenza esprime la forza delle prove del singolo documento e non viene fissata al 95% per nascondere informazioni mancanti.

## Valutazione della proposta pdf-inspector — 06/09/2026

Aggiornamento successivo: la prova comparativa richiesta dall'utente è ora documentata in `prova-comparativa-pdf-inspector-2026-09-06.md`: 12 PDF reali, 25 pagine, vantaggio di velocità e qualità su alcuni campi, ma difetti residui documentati. La valutazione iniziale sotto resta storica; nessuna integrazione operativa è stata eseguita.

Richiesta: valutare la repository Firecrawl come componente OCR. Esame documentale e del codice pubblico, senza installazione, sostituzione del motore o invio di documenti dello studio a servizi esterni. Riferimento esaminato: commit `636ca1a58bdc1af4cd3fc20b8c1f549a1121cca7`; versione dichiarata e pubblicata su PyPI al controllo: `1.17.0`.

La versione esaminata comprende estrazione nativa e OCR selettivo locale tramite PP-OCRv6 Small, PDFium e ONNX Runtime, con API Python anche da byte e provenienza del testo per pagina. La modalità offline richiede modelli predisposti e versionati; le raccomandazioni di elaborazione esterna non autorizzano l'invio del contenuto. Per IUSENTRA l'eventuale integrazione dovrebbe mantenere l'elaborazione sul server controllato, isolamento tra studi, limiti di risorse, file originali e impronte invariati.

Distinzioni essenziali: la classificazione della libreria riguarda PDF testuali, scansioni, immagini e documenti misti, non natura giuridica, area, branca o sottofamiglia. La confidenza di quel rilevamento e la confidenza OCR non sono la confidenza del catalogo. Il benchmark pubblicato nel README esclude l'OCR e non dimostra accuratezza sui fascicoli italiani. La guida dichiara il percorso OCR completo collaudato in CI su Linux x64; le dipendenze esterne su Windows e macOS sono indicate come preview.

Conclusione tecnica: componente candidato per migliorare lettura e selezione delle pagine da riconoscere, non sostituzione automatica dell'unico catalogo giuridico. Prima dell'adozione occorre un confronto controllato con l'estrattore attuale sui casi già emersi: corpo scansionato con solo timbro testuale, procura, relata, ricevute, PDF misti e documenti con tabelle; misurare pagine restituite, testo utile, nomi/date/importi, errori, memoria e tempi. Nessun collaudo della libreria sul dato reale è stato eseguito: non verificato su macchina reale. I fix e i collaudi del catalogo già aperti non sono dichiarati conclusi da questa valutazione.

Fonti consultate:

- https://github.com/firecrawl/pdf-inspector
- https://github.com/firecrawl/pdf-inspector/blob/main/docs/python.md
- https://github.com/firecrawl/pdf-inspector/blob/main/docs/ocr-runtime.md
- https://github.com/firecrawl/pdf-inspector/blob/636ca1a58bdc1af4cd3fc20b8c1f549a1121cca7/src/vision/routing.rs
- https://pypi.org/pypi/pdf-inspector/json

## Aggiornamento soglia verbali d’udienza, 08/09/2026

Nel collaudo reale locale su `http://127.0.0.1:8080/fascicoli/DD242366#documenti` la catalogazione dei verbali d’udienza era corretta come profilo documentale, ma restava a confidenza 94%, sotto la soglia operativa richiesta per i casi in cui il titolo portale e il contenuto testuale coincidono chiaramente. La regola forte `verbale` più `udienza` è stata alzata a confidenza 97% nel resolver unico, con versione catalogo `2026.09.08.catalogo-fascicolo.v24`; il classificatore storico compatibile è stato allineato a 96% per evitare regressioni nei percorsi che lo interrogano ancora come supporto.

La modifica non tocca Wizard, deposito telematico, notifiche, PEC, firma o firma multipla. Non simula la certezza universale al 95%: aumenta soltanto la confidenza quando le evidenze minime sono effettivamente presenti e coerenti, lasciando i casi deboli in revisione.

Prova materiale eseguita sulla copia Docker reale dell’utente, `127.0.0.1:8080`, versione `2.280.1`: cliccato `Aggiorna catalogazione`; osservato il messaggio `Indice e catalogazione aggiornati`; verificati i documenti `VerbaleUdienza_33393309.pdf.p7m`, `VerbaleUdienza_32970605.pdf.p7m`, `VerbaleUdienza_32392386.pdf.p7m` e `VerbaleUdienza_29740536.pdf.p7m` con profilo `Verbale d’udienza` e `confidenza 97%`. Nella stessa sessione è stato aperto e richiuso il pannello `Acquisisci documenti`, confermando la presenza dei canali `Scanner Windows`, `Webcam / fotocamera` e `Scatta dal telefono`, senza avviare acquisizioni reali.

Gate mirati superati prima del rilascio: `tests/test_document_catalog_fields.py`, pipeline catalogo persistente, contratti API catalogo documenti, contratti acquisizione scanner/camera, test JavaScript del canale acquisizione, typecheck React, packaging consistency, UTF-8 integrity e release readiness. La prova PIN PST e Wizard resta da eseguire insieme all’avvocato perché richiede token e finestra nativa.

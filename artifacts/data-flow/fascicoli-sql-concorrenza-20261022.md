# Fascicoli: salvataggi concorrenti e conservazione delle fonti — 22/10/2026

Stato: candidata2.447.3 accettata nei percorsi descritti su8080; commit e rilascio remoto in preparazione.
La funzionalità completa offline/PC-online rimane aperta e disabilitata.

## Risultato richiesto

Un modulo o processo aperto su dati precedenti non deve cancellare una modifica
SQL già confermata. In caso di conflitto la bozza deve rimanere disponibile; il
file e lo storico documentale devono restare coerenti con SQL.

## Sottografo con evidenze EXTRACTED

- `web/services/react_fascicoli_bridge.py::_form_fascicolo_payload` espone la
  revisione dei soli campi modificabili. `pct/fascicolo_edit_revision.py` esclude
  documenti e metadati delle lavorazioni in background.
- `frontend/src/components/FascicoliPage.tsx::FascicoloFormPage/JsonPostForm`
  trasmette `base_revision`; il conflitto mantiene il modulo e consente il
  confronto con una scheda aggiornata separata.
- `web/bootstrap/fascicoli_management_routes.py::modifica_fascicolo` verifica
  la revisione prima di scrivere soggetti o collegamenti e restituisce 409.
  Permessi, tenant e audit rimangono nelle procedure proprietarie.
- `pct/fascicoli.py::_salva_sql_changes` usa il confronto della riga letta in
  `pct/fascicoli_sql_writer.py::save_changes`, nella transazione nativa di
  `pct/storage.py` oppure `pct/storage_postgres.py`. Non sostituisce l'archivio.
- `pct/fascicoli_document_transaction.py::serialized_documents` riusa il lock
  condiviso governato per le mutazioni fisiche del medesimo fascicolo.
  `sostituisci_documento` recupera i byte in memoria anche nel percorso compatto,
  senza richiedere una seconda copia su disco. Non cambia regole di firma/invio.
- `pct/fascicoli_sql_mirror.py` accoda in `_meta` solo gli ID cambiati, nella
  medesima transazione. Il mirror legge quelle righe SQL; i token impediscono
  di confermare una consegna più recente durante un salvataggio precedente.
  Errori di mirror rimangono pendenti e registrati, senza falso rollback di SQL.
- La cattura `pct/offline_capture.py` è inattiva senza contesto interno esplicito.
  Nessuna associazione PC, chiave privata o trasferimento reale viene attivato.

Il grafo AST è un indice, non prova di esecuzione. Il grafo WIP esterno contiene
34 sorgenti selezionati, 1493 nodi e 4449 collegamenti prima dell'ultima modifica
ai test. Non contiene dati dello studio, allegati o segreti.

## Verifiche tecniche e limiti

- Riprodotta perdita di una nota SQL con due GestioneFascicoli prima del fix.
  Dopo il fix il salvataggio obsoleto viene respinto e la nota resta conservata;
  una nuova lettura consente la modifica intenzionale senza perderla.
- Prove di errore dopo scrittura, sostituzione normale/compatta, storico,
  rinomina, idratazione parziale, cancellazione e rollback del registro.
- Prova con due connessioni/thread e scrittura sul medesimo PDF: il recupero del
  secondo comando non sovrascrive i byte già confermati dal primo.
- Mirror: altro fascicolo rimasto obsoleto in memoria, comando parziale, disco
  indisponibile e nuova consegna durante il salvataggio. Nessuna scansione PDF.
- 74 casi su PostgreSQL16 controllato superati; il container temporaneo tmpfs
  viene rimosso senza creare volumi. Inizialmente due query di test con percento
  letterale non erano portabili in psycopg2: corrette con parametri e riprovate.
- 54 guardrail deposito/firma/modifica fascicolo superati. Avvio governato
  globale escluso nel processo di test mirato: il primo avvio dei test legacy
  usava il registro tenant predefinito invece del banco temporaneo e incontrava
  un backup ricevute discordante. Nessun controllo del prodotto è stato rimosso.
- Typecheck e bundle pubblicato: 753 sorgenti e 296 asset concordanti.

Da eseguire: prove visive reali su8080 con due schede, salvataggio/riapertura PDF,
responsive e tempi; commit/push, tutti i gate remoti, deploy, stessa revisione su
PC/server e pulizia verificata. Non equivale al completamento della replica.

## Accettazione materiale su8080 — 22/10/2026

Copia Docker reale2.447.3, app/OCR/scheduler healthy e /api/pronto positivo.
Fascicolo controllato C729BD2B (Collaudo Editor Alfa), due moduli reali aperti.
Il primo salva una nota; il secondo riceve409, conserva titolo e nota della
bozza e apre la scheda aggiornata in un nuovo tab. Nella nuova scheda la prima
nota è presente; un nuovo titolo viene salvato e riaperto senza perderla.
Ripristinati poi titolo originario e note vuote con lo stesso modulo normale.

Verifica sulla finestra Windows realmente visibile, selezionando i tab nella
barra nativa e ridimensionando il riquadro reale: larghezze CSS400 e800, entrambe
con scrollWidth uguale a clientWidth; testo, bozza, pulsanti e focus da tastiera
osservati e conservati. Disposizione iniziale della finestra ripristinata.
Nessuna emulazione CDP o browser headless usata come accettazione.

PDF controllato FB132C61, due pagine: testo nativo «verificato» modificato in
«verificato SQL», salvataggio confermato, versione precedente conservata e
ritorno al lettore con nuovo testo persistito. Immagini, cerchio, freccia e
impaginazione della prima pagina restano visibili; seconda pagina invariata.
Vista materialmente anche nella finestra Windows attiva, con scroll delle pagine.
Prove locali: fascicolo-conflitto-bozza-8080.png, fascicolo-conflitto-mobile-400.png,
fascicolo-conflitto-tablet-800.png, pdf-writer-visibile-riaperto-8080.png nella
cartella tecnica esterna di questa lavorazione. Nessun invio/firma/PEC eseguito.

Ulteriori guardrail: tutti i test frontend e sicurezza dipendenze passano;
packaging14casi dopo rigenerazione OpenAPI, callback atomica SQLite/PG2casi.
Il primo controllo packaging ha correttamente segnalato OpenAPI ancora2.447.2:
rigenerato con il generatore proprietario, ripetuto senza indebolire il test.

Il comando harness di supporto provato in modo code non è un gate applicativo:
segnala setup.py protetto anche se cambia solo il commento di versione imposto
per il rilascio; il suo cercatore .git non supporta l'export pulito esterno.
Nessuna regola del checker modificata o abbassata. Restano registrati l'esito e
il motivo di non applicabilità al lavoro prodotto; packaging, dipendenze runtime,
contratti UI, design governance, lint, test e gate CI rimangono obbligatori.

Da concludere: CI/gate sul commit, deploy, prova produzione, confronto locale e
server sulla medesima revisione, pulizia governata. L'incarico offline completo
rimane aperto e disabilitato; queste prove non certificano la replica PC-online.

Preparazione Git: lock indice vuoto del21/10ore23:12, non aperto e con soli processi status, preservato fuori da.git dopo verifica; nessuna cancellazione o interruzione di Git. Whitespace dei nuovi test corretto dal controllo pre-commit.

22/10/2026 — CI principale a0faa positiva; CodeQL ha fermato correttamente il deploy per eco HTML non protetta nel solo endpoint fittizio del test. Sostituita con risposta application/json e aggiunto guardrail con identificativo HTML ostile: sei casi del modulo passano. Nessuna deroga o modifica al gate. Nuovo commit e intera catena richiesti prima della prova produzione; il rilascio non è chiuso.

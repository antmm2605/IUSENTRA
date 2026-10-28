# Lettura integrale biblioteca — sottografo pertinente

## EXTRACTED

- `lex/normativa/biblioteca/fabbisogno.py:21`, `norm_articolo`: normalizzazione conservativa degli identificatori degli articoli.
- `lex/normativa/biblioteca/lettura.py`, `leggi_articoli`: nuovo lettore in sola lettura. Ingresso: percorso DB configurato dal chiamante, chiave collezione censita, articolo, edizione e impronta attesa opzionali.
- Repository: SQLite `normative_documents` (identita/edizione/provenienza archivio), `normative_articles` (testo intero). Selezione SQL parametrizzata per collezione, poi documento. Nessuna scrittura o migrazione.
- Uscita: testo archiviato senza abbreviazioni, SHA-256, document/article ID e metadati della fonte. Edizioni ambigue o hash modificati producono errore; nessun ripiego su un atto diverso.
- Consumatore effettivo della verifica: script CPU nel dossier locale `work/ricerca_norme/protocollo-v2-20261025/completamento-fonti-v1`, con risultati in `verifica-lettura-integrale.json`. Sono stati letti 215 testi distinti, corrispondenti a289 riferimenti caso-norma.
- Test: `tests/test_biblioteca_lettura.py`: distinzione atto/articolo, edizioni multiple, lettura lunga senza troncamento, bis, hash cambiato, invariabilita DB.
- I testi diagnostici sono ricavati da riferimenti del banco: restano esclusi dagli input di una nuova prova di retrieval. Nessun miglioramento di recall viene attribuito a questa esportazione.

## INFERRED / non ancora collegato

- Il lettore puo servire una futura richiesta di lettura del modello. Non e registrato come tool di produzione e non e chiamato automaticamente dal runtime Lex in questa modifica.
- Nessuna UI, API, job, autorizzazione tenant, configurazione modelli o deposito viene modificata.
- L'applicabilita al fascicolo resta da verificare separatamente. Una lettura riuscita non approva la Fonte e non elimina il gate di provenienza/versione.


## Integrazione della consegna 2.454.0 — 25/10/2026

- EXTRACTED: `web.services.redazione_lex_runtime.stesura` costruisce la richiesta
  con modello, parte assistita e ruolo e chiama `biblioteca.ricerca_fonti.integra_fonti`.
- EXTRACTED: `integra_fonti` ottiene fino a 50 risultati con testi integrali dai
  cataloghi indicizzati e li combina con i riferimenti proposti e acquisiti.
  `leggi_scelta` accetta solo JSON completo, interi entro l'elenco, senza bool,
  float, stringhe numeriche o numeri estratti dal testo libero.
- EXTRACTED: la scheda resta per prima, poi scelte valide e classifica fino a 20;
  le omissioni sono contate. Il numero non è una certificazione di pertinenza.
- EXTRACTED: la configurazione vettoriale supporta il percorso storico della
  biblioteca; due variabili esplicite discordanti sono respinte.
- EXTRACTED: `lettura_fonti.prepara_letture` conserva gli originali, legge parti
  contigue, verifica citazioni letterali e collega SHA del messaggio e uso
  restituito dal gateway. Questo dimostra il contenuto trasmesso, non comprensione.
- EXTRACTED: l'importatore non filtra articoli per rilevanza quando viene
  richiesto l'archivio completo. La riconciliazione candidata salta SHA XML già
  presenti per preservare testi e rubriche precedentemente corretti.
- INFERRED / DA VERIFICARE: qualità con 35B reale e indice aggiornato, caricamento
  CPU/GPU, copertura temporale delle fonti del procedimento, UI reale, CI e deploy.
  Nessuna delle metriche simulate è accettazione del percorso di produzione.


## Acquisizione multiversione e trasporto ufficiale — 26 ottobre 2026

- EXTRACTED: `normattiva_client.download_export` conserva ZIP originale, SHA-256 e ricezione UTC. Il manifest AKN è separato da quello NIR: un file AKN non viene passato al parser NIR.
- EXTRACTED: `normattiva_akn_importer.decodifica_xml_akn` accetta XML oppure un solo livello Base64 canonico contenente XML. `parse_akn` verifica identità principale FRBRWork, partizioni e data FRBRExpression; conserva SHA del payload ricevuto e dell'XML decodificato separatamente.
- EXTRACTED: `versioni_akn.importa_multiversione` scrive catene atomiche nell'archivio storico separato, con provenienza ZIP/XML, ordinali ufficiali e intervalli formali dei fotogrammi. Una catena rifiutata non viene promossa a completa; il rapporto d'errore e i file originali restano disponibili.
- EXTRACTED: `versioni_akn.leggi_versione` legge solo una catena completa e un'edizione univoca, verifica SHA del testo e richiede la partizione quando i numeri degli articoli sono ambigui. La copertura non supera il giorno di acquisizione.
- EXTRACTED: `biblioteca.acquisizione._righe_normattiva` consulta questa cache prima dell'acquisizione puntuale ufficiale. Una versione formalmente presente non approva le disposizioni transitorie del caso.
- INFERRED, DA VERIFICARE: riuso effettivo della cache completa in stesura, beneficio della ricerca con tutti i nuovi dati, applicazione locale/server della medesima versione. Non sono dimostrati dal solo import né da AST valida.
- INFERRED, DA VERIFICARE: aggiornamento del ponte privato e conteggio token identico tra preflight, ricezione del modello e traccia di stesura; il sorgente preparato non prova l'installazione del servizio.

## Consolidamento 26 ottobre: trasferimenti e mount

- EXTRACTED: `lex/normativa/normattiva_client.py:NormattivaClient.download_collection` chiama `lex/normativa/trasferimento.py:riprendi_download_zip` soltanto dopo un'interruzione di rete della stessa risposta pubblica. Range 206, byte e totale riscontrati; massimo tre errori di rete; 403/429 non vengono ritentati. Lo ZIP ripreso richiede CRC integrale e SHA prima della promozione. I parziali preesistenti sono conservati con nome distinto.
- EXTRACTED: `deploy/normativa/iusentra-normativa-image.service` avvia `mount_data_image.py` usando la configurazione locale amministrata. Il lettore verifica backing file loop, UUID e filesystem; non crea immagini, non formatta e non smonta archivi.
- EXTRACTED: `web/services/redazione_lex_runtime.py:stesura` rifiuta una biblioteca assente prima di leggere schede o chiamare il modello; non crea implicitamente un archivio vuoto sotto un mount mancante.
- INFERRED/DA PROVARE: riavvio completo di WSL/Windows non eseguito durante acquisizioni e migrazione attive. Il mount corrente e il servizio enabled/active sono riscontrati nel dossier pubblico `mount-persistente-predisposto.json`; questo non equivale a una prova di riavvio.
- DA PROVARE DOPO I DATI: test dedicati `test_normattiva_ripresa_zip.py` e `test_stesura_biblioteca_mancante.py` predisposti, non eseguiti. I risultati precedenti non attestano queste modifiche.

## Qualificazione puntuale dei lettori — 26 ottobre 2026

- EXTRACTED: `lex/normativa/lettori_attestati.py:politica_lettori` accetta un manifesto soltanto da configurazione operatore con SHA atteso; verifica sorgenti dei sei moduli e rapporto tecnico. Non legge il payload del modello e non approva applicabilità.
- EXTRACTED: `lex/normativa/riconvalida_akn.py:ArchivioRiscontrato` rilegge lo ZIP intero e confronta SHA, poi ne controlla la stabilità; `riconvalida_catena` confronta tutti i fotogrammi e gli articoli SQL con una nuova lettura XML, inclusi identità, corpo, ordine, partizione, struttura e impronte. Soltanto il confronto completo scrive la prova e le due colonne di qualificazione.
- PREDISPOSTO, NON APPLICATO: la proposta isolata `versioni_akn-provenienza-e-lettori.py` aggiunge le colonne e richiede qualificazione puntuale prima di leggere catene di un vecchio lettore attestato. I sei sorgenti usati dall'importatore v10 attivo sono ancora congelati: il modulo di riconvalida non è ancora stato eseguito né integrato in un comando pubblico.
- PREDISPOSTO, NON APPLICATO: il nuovo parser confronta il numero/data dell'intestazione documentale con NIR. Fonte reale: export 26G00056 contiene una variante NIR38 con intestazione39; non è una prova di equivalenza tra i due atti. Numeri storici `314/2`, `82/2` e allegati `III a)` sono mantenuti secondo il testo XML.
- DA VERIFICARE DOPO I DATI: regressioni `test_riconvalida_akn.py`, `test_normativa_akn_identita_numeri.py`, qualificazione dell'intero archivio candidato, runtime e deploy. Nessun esito positivo viene dedotto dall'AST o da queste relazioni estratte.


## Sessione di lettura GU esatta — 26/10/2026

EXTRACTED: `biblioteca/normattiva_akn.py:scarica(identita_gu=...)` apre nella stessa sessione la pagina di dettaglio per data GU e codice redazionale, verifica il collegamento AKN corrispondente, poi controlla URN, pubblicazione, data e numero nell’XML. La via non usa N2Ls, che nelle risposte archiviate ha restituito atti omonimi con date diverse. Le risposte HTML errore delle richieste dirette precedenti sono conservate.

INFERRED, da verificare sulla fonte: la pagina di dettaglio inizializza il contesto necessario al download AKN; il recupero corretto è governato da un solo job successivo al lotto precedente, con arresto dopo tre errori consecutivi. Test di regressione predisposti, non eseguiti prima del completamento dati. Nessuna prova di applicabilità giuridica deriva da questa sequenza HTTP.

EXTRACTED 26/10/2026: sei risposte primarie già archiviate hanno docNumber XCIX/CCXC/DVII/CLXXVII/CCCCLXI/XXXIII, rispettivamente 99/290/507/177/461/33 nel catalogo e nel NIR. Riconciliate offline con SHA, senza HTTP, in riconciliazione-sei-numeri-romani.json. La normalizzazione riguarda soltanto il numero dell’atto; suffissi bis e numerazioni di articoli/partizioni restano distinti. La medesima regola è predisposta nella proposta del parser congelato, non ancora applicata.


### Revisione tecnica 26 ottobre, 17:40 UTC

- EXTRACTED: `tools/riconvalida_cache_akn.py::riqualifica_metadati` conserva stato e journal precedenti, azzera solo le due attestazioni (stringhe vuote secondo lo schema NOT NULL), riusa la copia SHA verificata e richiede un nuovo controllo integrale quando cambia il lettore. Articoli e testi non vengono riscritti. `checkpoint` controlla fingerprint e richiesta di arresto tra edizioni e blocchi di articoli.
- EXTRACTED: `normattiva_akn_importer.py::parse_akn` tratta l'annotazione ufficiale «Raccolta YYYY» separatamente dal numero, verificando YYYY rispetto alla data Work/pubblicazione. Non equipara 408 e 408-bis. Riscontro primario in `riscontro-intestazione-numero-raccolta-2012.json`.
- EXTRACTED: `identita_documento.py::urn_documento` ricostruisce l'identita NIR mancante dal percorso tipizzato e da numero/data concordanti. Il confronto diretto di `normative_documents.urn` non basta quando la fonte conserva soltanto `urn:`. Inventario dei 773 membri primari: 121 atti con corpo completo e identita target esatta gia disponibili. Questa prova non dimostra applicabilita o storia multivigente.
- INFERRED, da verificare dopo i dati: recuperi selettivi dei 68 errori di confezione/etichette/anno con i nuovi lettori; proiezione nel catalogo, applicabilita e trasmissione reale a Lex. Nessun test applicativo o benchmark eseguito durante questa fase.


### Coordinatore parallelo e provenienza dei recuperi

- EXTRACTED: `tools/riconvalida_cache_akn_parallela.py::main` mantiene un solo writer SQL. `init_worker` imposta `query_only=ON`; `confronta` chiama il medesimo `riconvalida_catena` con `attesta_sql=False`. Il coordinatore rilegge SHA dell'intero ZIP, delega percorso/stat/identita ai worker, poi registra i risultati dopo commit e fsync del journal. I worker controllano SHA dei singoli XML, tutti i campi e gli intervalli, senza modificare i corpi SQL.
- EXTRACTED: `ArchivioDelegato` rifiuta un primario cambiato rispetto alla rilettura del coordinatore; non e una nuova fonte o una deroga al controllo SHA. Nuove regressioni RO e modifica primaria scritte in `tests/test_riconvalida_akn.py`, non ancora eseguite.
- EXTRACTED: `recupera-parser-dopo-qualificazione.py` e `prepara-gate-cache-qualificata.py` sono strumenti operativi esterni preparati, con gate finale reale e lock; la regia corrente52452 attende il sigillo finale della qualificazione55256 senza aprire DB. Il gate per la proiezione deve usare lo SHA della copia qualificata finale, mai quello dell'originale v10.
- INFERRED/pendente: prestazioni definitive della modalita parallela, fine delle catene e recuperi68; nessuna conclusione dal solo numero di processi attivi.


### Riscontri generali di identita e date, 26 ottobre 20:00 UTC

- EXTRACTED: `identita_akn_riscontrata.py::riscontra_suffisso` richiede intestazione, catalogo tipizzato, data e GU concordanti; conserva XML originale e C14N del corpo. Il descrittore interno derivato non diventa alias ufficiale: la citazione resta ELI/GU. `verifica_riga_pacchetto` rilegge fisicamente XML e pagina di catalogo, rigenera le impronte e confronta articolo, partizione, localizzatore, rubrica e testo prima dell'importazione nativa.
- EXTRACTED: il tool operativo `importa-identita-suffissi-generale.py` ha preparato 100 identita, 285 edizioni e 206 file, con tre ricevute esistenti riusate; nessun errore di preparazione. L'importazione generale attende la fine della qualificazione. I primi tre casi sono gia nel solo candidato, cinque articoli con ID nuovi258-260, backup e sincronizzazione FTS nativi: non sono una prova di rilascio o applicabilita odierna.
- EXTRACTED: `consultazione.py::importa_fonti` conserva data effettiva dell'edizione distinta dalla ricezione e dalla consultazione richiesta; metadati fonte/provenienza sono oggetti JSON. `_stessa_fonte_archiviata` riusa ID e chiavi tecniche soltanto a parita di pacchetto, testi, identita, edizione e provenienza, includendo vecchie impronte salate con la data. Cambiare URL, versione, data di acquisizione o corpo non diventa un riuso equivalente.
- EXTRACTED: `provenienza_edizione.py::riscontro_alla_data` distingue copertura dell'edizione e applicabilita giuridica. `biblioteca/identita.py::risolvi_articolo` separa `data_riferimento` dall'edizione letterale e non sceglie tra versioni sovrapposte. `ricerca_fonti.py::integra_fonti` registra le edizioni certamente fuori data nei dettagli, mantenendo pendente la diversa valutazione giuridica.
- EXTRACTED: `atomic` ritenta brevemente solo PermissionError nella sostituzione del checkpoint, preservando destinazione e temporaneo se la negazione persiste. Il journal SQL/fsync rimane la base della ripresa, non il contatore UI.
- INFERRED/da provare dopo i dati: regressioni dedicate, applicabilita/transitorie effettivamente governate, proiezione integrale, corpus e indice finale, uso reale del35B, flusso React e parita server. Nessun test o CI verde e dichiarato da queste relazioni.


### Registro temporale e fonti congiunte

- EXTRACTED: `regole_applicabilita.py::carica_registro` usa soltanto percorso e SHA atteso della configurazione di distribuzione. Ogni approvazione punta all'impronta originale della regola; non vengono create approvazioni normalizzando una regola dopo la firma. Le identità NIR conservano la data completa. Nessun registro o approvazione è stato attivato in questa fase.
- EXTRACTED: `valuta_fonte_registrata` usa l'evento dichiarato dalla regola, non quello suggerito dal piano AI, e limita la regola agli articoli/partizioni espliciti. `riscontro_fonte_cache` rilegge la fonte con `versioni_akn.leggi_versione`: testo, URL e intera provenienza dell'edizione devono coincidere. Tutte le `fonti_congiunte` devono essere riscontrate. Versione acquisita e applicabilità restano controlli distinti.
- EXTRACTED: `biblioteca/ricerca_fonti.py::integra_fonti` controlla le regole di scheda prima del piano modello e quelle delle candidate prima della selezione chiusa. Registra esclusioni, impronte e motivi. Una regola negativa provata sulla base normativa della scheda ferma la richiesta senza cambiare la scheda. Le norme effettivamente aggiunte prive di applicabilità provata mantengono la pendenza; candidate non inviate non generano una pendenza artificiale.
- INFERRED/pendente: regressioni del registro e della stesura, approvazione professionale delle regole concrete su fonti finali, eventi reali e prova completa di prodotto. Il manifesto non è configurato e nessuna applicazione al singolo caso è dichiarata approvata.


### Collegamenti selezionati e rettifiche tecniche, 26 ottobre 21:46 UTC

- EXTRACTED: `versioni_importazione.conserva_versione` archivia lo snapshot e indicizza ID articolo/chunk in `normative_import_legacy_refs`, senza duplicare i corpi. `riferimenti_importazione.leggi_riferimenti_precedenti` fa un lookup indicizzato e rilegge SHA dello snapshot e del testo; non enumera lo storico nella GET.
- EXTRACTED: `consultazione.dettagli_precedenti` alimenta soltanto la consultazione archivistica del lettore, non `dettaglio` corrente o il retrieval di nuove Fonti. La lettura rettificata resta marcata non utilizzabile come Fonte corrente. Il proiettore prepara l'indice pregresso soltanto dopo il backup nativo.
- EXTRACTED: `normative_article_reader.risolvi` richiede concordanza di tutti i selettori presenti (ID, chiave atto, articolo e URL). `_fonte_uguale` verifica anche allegato, articolo ed edizione esplicitamente indicati: il medesimo atto padre non autorizza a sostituire una partizione.
- INFERRED, da provare dopo i dati: apertura reale dei vecchi collegamenti, regressioni del lettore e API, browser localhost8080, parita integrale degli ID server dopo la proiezione. Il campione precedente non dimostra la parita complessiva. Gli strumenti Graphify nei percorsi indicati da AGENTS.md e il grafo repository non sono presenti in questa macchina; le relazioni qui riportate sono estratte dai sorgenti indicati, non da un grafo dichiarato aggiornato.


### Proiezione riproducibile e acquisizione documentata, 26 ottobre 22:45 UTC

- EXTRACTED: il proprietario della proiezione offline è ora `tools/proietta_cache_akn.py::main`; il comando operativo nel dossier è un richiamo a questo modulo, non una seconda implementazione. Backup, SHA dell'intero archivio, confronto XML/articoli/partizioni, metadati JSON ed FTS restano nativi.
- EXTRACTED: la proiezione valuta le parti separatamente: un avviso di abrogazione in una disposizione non scarta le altre disposizioni integrali dell'edizione. I frammenti privi di corpo sono marcati `consultazione_senza_testo` e con la qualità effettiva; non vengono promossi a Fonti integrali. Un'edizione composta soltanto da avvisi resta esclusa dalla proiezione attiva.
- EXTRACTED: `normative_article_reader.numero_articolo` accetta le numerazioni native, compreso un punto finale tipografico, numeri storici con barra e romani canonici. Non equipara I e 1; `destinazione_ufficiale` non inventa collegamenti puntuali per numerazioni esterne non riscontrate.
- EXTRACTED: `provenienza_edizione.data_acquisizione_documentata` usa solo la ricezione documentata o la data dichiarata nella fonte, con Europe/Rome per i timestamp dotati di fuso. `imported_at` non sostituisce l'acquisizione. Le ricevute del manifest NIR hanno impronte distinte e non dichiarano vigenza.
- INFERRED / da eseguire dopo i dati: tre regressioni native di proiezione, FTS e lettore in `tests/test_proiezione_cache_akn.py`, regressioni sulle numerazioni e sulle date; nessun esito positivo da queste sole relazioni o dall'AST. Il recupero19pacchetti è terminato, i gate di integrità/SHA sono ancora in corso.


### Lettura puntuale e proiezione, revisione del 27/10/2026

Risultato richiesto: recuperare gli articoli realmente acquisiti senza perdere gli allegati o scartare gli articoli validi perché una diversa disposizione è abrogata. Le acquisizioni non attribuiscono da sole applicabilità al fascicolo.

- EXTRACTED `lex/normativa/metadati_akn_riscontrati.py:27` — `normalizza_metadati`.
- EXTRACTED `lex/normativa/metadati_akn_riscontrati.py:68` — `leggi_documento`.
- EXTRACTED `lex/normativa/metadati_akn_riscontrati.py:83` — `verifica_riga_puntuale`.
- EXTRACTED `lex/normativa/metadati_akn_riscontrati.py:173` — `verifica_cache_puntuali`.
- EXTRACTED `lex/normativa/biblioteca/normattiva_akn.py:68` — `scarica`.
- EXTRACTED `lex/normativa/biblioteca/normattiva_akn.py:141` — `converti`.
- EXTRACTED `lex/normativa/biblioteca/acquisizione.py:43` — `_righe_normattiva`.
- EXTRACTED `lex/normativa/biblioteca/acquisizione.py:152` — `acquisisci`.
- EXTRACTED `lex/normativa/consultazione.py:200` — `importa_fonti`.
- EXTRACTED `lex/normativa/consultazione.py:476` — `main`.
- EXTRACTED `tools/proietta_cache_akn.py:23` — `main`.

- EXTRACTED: `scarica` riscontra insieme NIR, pubblicazione ed ELI della GU diretta. `converti` usa `leggi_documento` e il lettore AKN nativo, mantiene i testi dei corpi, separa le chiavi delle parti e conserva espressione letterale e data richiesta.
- EXTRACTED: `normalizza_metadati` interviene solo su attributi tecnici con riscontri nel corpo ufficiale; conserva SHA del payload originale, del derivato, dei corpi canonici e del testo visibile. La firma della Costituzione e l'ELI sono necessari per interpretare i metadati non datati.
- EXTRACTED: `acquisisci` conserva la fonte XML fisica deduplicata per SHA. `importa_fonti` ripete i riscontri su fonte, identità, partizione, localizzatore, testo, rubrica, struttura e provenienza prima della scrittura; conferma che i file non siano cambiati prima del backup e prima del commit SQL.
- EXTRACTED: `tools/proietta_cache_akn.py` proietta solo catene riscontrate; valuta ogni articolo e componente, mantiene gli avvisi di abrogazione distinguendoli dai testi integrali e non elimina per questo gli altri articoli dello stesso atto. La cache sorgente resta in sola lettura.
- INFERRED, da provare: assenza di regressioni nella pipeline completa, qualità e tempi della ricerca, testi realmente ricevuti e letti dal 35B, persistenza e visualizzazione su localhost:8080 e produzione. I test scritti e il solo riscontro dei file non costituiscono accettazione utente.


## Consumatore notturno: riallineamento testuale precedente (27/10/2026)

- EXTRACTED — `pct/scheduler.py:692` avvia `tools/normattiva_riallinea.py:27`, che usa `lex.normativa.riallinea_articoli.riallinea`. Il vecchio correttore poteva riesaminare anche le nuove fonti XML.
- EXTRACTED — `lex/normativa/normattiva_importer.py:192` conserva il localizzatore fisico e la partizione del nodo NIR; `insert_articles_and_chunks` li registra nei metadati dei chunk quando presenti. Gli articoli testuali precedenti non ricevono un localizzatore inventato.
- EXTRACTED — `lex/normativa/riallinea_articoli.py:183` controlla la struttura e i metadati prima di analizzare il corpo. Provenienza registrata, localizzatori e numerazioni non appartenenti alla grammatica del vecchio correttore impediscono una riscrittura euristica. Metadati illeggibili restano segnalati, conservando le righe.
- EXTRACTED — i test `test_riallinea_articoli_normattiva.py` e `test_normativa_partizioni_versionate.py` confrontano righe e ID prima/dopo e mantengono la correzione idempotente del vero archivio testuale precedente.
- INFERRED — la conservazione nel job installato va riscontrata dopo il rilascio, su una selezione controllata di fonti e senza avviare una scansione generale aggiuntiva. I test non attestano l'esecuzione del job sul server.


## Controlli del 27 ottobre: selezione delle Fonti e confine della stesura

EXTRACTED: `pct/schede_fonti/verifica.py:verifica_schede` sceglie fra le edizioni
con `lex/normativa/provenienza_edizione.py:priorita_edizione_archiviata`: riscontro
alla data richiesta, ricezione documentata e data letterale dell'edizione restano
campi distinti. `imported_at` non diventa una data di acquisizione. Il numero
XML dell'articolo passa dalla stessa espressione SQL del lettore esatto; «Art. 1.»
non scompare rispetto alla richiesta «1». Le partizioni omonime restano ambigue.

EXTRACTED: `lex/procedura_atti/stesura_blocchi.py:scrivi_blocchi` invoca
`provenienza.verifica_provenienza` prima di qualsiasi lettura o generazione con
il modello. Provenienza mancante, testo alterato e decisione senza integrale
bloccano quel confine, senza consumare inferenze. Test negativi e percorso normale
in `tests/test_redazione_lex.py`; 67 verifiche mirate positive nel dossier 48.

EXTRACTED: acquisizione da cache e conversione AKN condividono la mappa in
`biblioteca/riferimenti.py:PARTIZIONI_CODICI`. La partizione delle preleggi deriva
da «Disposizioni sulla legge in generale» nell'XML del codice civile, non dalla
numerazione. Riscontro SQL su edizione 518534: 31 righe in questa partizione,
3249 in «CODICE CIVILE», senza numeri duplicati dentro le singole partizioni.

INFERRED/DA PROVARE: il completamento delle vecchie fonti prive di ricezione deve
ancora essere verificato sul database candidato; i test tecnici non certificano
il recupero effettivo, la lettura del 35B, il browser o il rilascio.


EXTRACTED (27 ottobre): `metadati_akn_riscontrati.verifica_riga_puntuale` mantiene
in cache la rilettura per file/SHA/URN/data/provenienza; il link di consultazione
per articolo non cambia i contenuti prodotti da `converti` e non causa una nuova
conversione integrale. Il link di acquisizione rimane in chiave. Il test con URL
diversi verifica una sola conversione e rifiuta comunque testo alterato sul cache
hit (`tests/test_metadati_akn_riscontrati.py`). L'impronta dei sei lettori congelati
e quella AST del normalizzatore non cambiano per questa ottimizzazione.

EXTRACTED (dati candidati, non rilascio): dopo gli import nativi di 44 e 77 atti,
la biblioteca contiene 885 documenti, 68.131 articoli e 101.935 chunk. Inventario di
tutte le 641 chiavi alla data 26/10/2026: nessuna edizione scelta senza ricezione
documentata. Testi e ricevute erano già presenti; nessun nuovo HTTP. Questi dati
non certificano l'applicabilità professionale, la qualità del recupero o la lettura
del 35B: tali prove restano distinte nel protocollo operativo.


Correzione del conteggio FTS (27/10): EXTRACTED, `tools/proietta_cache_akn.py` chiama
`sincronizza_fts(dst)` senza callback. In `lex/ricerca_giuridica/indice_fts.py`
il conteggio preliminare dei chunk pendenti serve soltanto alla callback;
il piano SQLite osservato usa una scansione dell'indice dei documenti e lookup
correlati sulla chiave FTS. Senza callback questo conteggio viene evitato,
con inserimenti incrementali e controlli degli orfani invariati. Il processo
750443, già avviato, conserva il modulo caricato: nessun riavvio o beneficio
retroattivo dichiarato. Le prove SQL controllano risultato completo,
idempotenza e totale esatto quando il chiamante richiede l'avanzamento.


## Aggiornamento 27 ottobre: riscontro ID e distribuzione

EXTRACTED: `lex/ricerca_giuridica/indice_fts.py:sincronizza_fts`
materializza nella tabella temporanea della connessione la differenza fra
`normative_chunks.id` e `normative_fts_info.chunk_id`. Solo tali ID richiedono
lettura del testo e inserimento FTS. La differenza inversa conta gli orfani.
Il piano reale usa due indici covering; il riscontro sul catalogo candidato
ha verificato 2496541 ID preesistenti, zero nuovi e zero orfani in 94.56 s.
Questo non sostituisce integrity/FK/uguaglianza completa degli insiemi del
verificatore finale, né prova applicabilita giuridica.

EXTRACTED: `.github/workflows/deploy-hetzner.yml` esegue il backup prima di
`deploy/hetzner/deploy.sh`. Il percorso opzionale
`deploy/hetzner/load_verified_release_image.py:load` verifica budget fisici,
SHA del tar e revisione dell’immagine senza avviare container. La build
tradizionale resta il default quando non e configurata un’origine precostruita.
I verificatori `verifica_fonti_lex.py` e `verifica_schede_fonti.py` risolvono
la biblioteca con `lex/retrieval/normativa_catalog.py:library_path` e il DB
generale dall’ambiente del container, evitando di provare un vecchio archivio.
INFERRED, da provare al rilascio: disponibilita dell’origine privata, caricamento
sul server dopo backup e parita SHA dei file distribuiti. I test isolati non
certificano tali eventi reali.

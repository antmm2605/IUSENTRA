# Lettura documento e salvataggio cliente — 14 ottobre 2026

Il comando normale deve applicare i dati leggibili anche quando la MRZ non supera i controlli, conservando l'avviso e senza attribuire a quella MRZ valori verificati. Il nuovo cliente deve essere salvato nel repository SQL e ritrovato nella scheda riaperta. Il preventivo iniziale è facoltativo e disattivato per default.

## Causa e correzione

Nel primo PDF sintetico la fonte nativa univa le due righe TD3, ciascuna di 44 caratteri, separandole con uno spazio. Il parser riconosceva soltanto le righe separate e perdeva numero del documento e nazionalità verificati. La correzione riconosce i confini esatti e riusa i controlli esistenti. Due passaporti differenti impediscono l'applicazione automatica; ripetizioni identiche non creano una falsa discordanza.

Il valore iniziale React del preventivo è ora false; rimosso checked anche nel modulo storico. Il DTO server era già coerente. Le bozze e le scelte esplicite non vengono cancellate.

## Prova materiale locale

Browser reale sulla copia Docker dell'utente, porta 8080, con documenti sintetici privati che non rappresentano persone reali:

- MRZ valida: lettura, applicazione di otto dati, Salva cliente, cartella AF8D97AC, riapertura tramite Modifica anagrafica. Nome, cognome, sesso, nascita, nazionalità, passaporto TSTSQ0001 e scadenza conservati.
- MRZ non valida: avviso visibile, sette dati leggibili applicati dal documento, Salva cliente, cartella B6118222 e riapertura. Passaporto TSTOCR002 e scadenza conservati. Nessuna trascrizione manuale dei dati riconosciuti.
- Nuovo modulo isolato: preventivo inizialmente deselezionato; attivazione e disattivazione manuali provate. Nel secondo salvataggio è rimasto deselezionato senza intervento.
- Lettura SQL in sola consultazione: entrambi i record corrispondono ai dati attesi; 33 clienti precedenti identici al backup coerente, collegamenti soggetti_parti invariati, campi non dimostrati vuoti.

41 guardrail del lettore superati; typecheck, build e suite frontend superati. Il contatore di completezza misura gruppi integralmente compilati: zero è coerente con la mancanza di codice fiscale, recapiti, indirizzo, ente e data di rilascio dei documenti sintetici.

Queste prove non attestano ogni documento possibile né il PostgreSQL operativo. Commit, gate GitHub, riallineamento locale esatto e deploy sono ancora da eseguire. L'incarico generale resta aperto.

## Correzione del gate CI

Lo shard core-04.01-4 del primo push ha evidenziato un test PEC non deterministico: sceglieva il primo messaggio pct_deposito fra tre fonti sintetiche della stessa data con stati differenti. Il risultato accettazione_deposito apparteneva a un'altra fixture, senza collegamento con il lettore anagrafico. Il test ora individua esattamente la ricevuta di avvenuta consegna RG 1234/2026 e richiede lo stato consegna_pec; esegue anche l'ordine inverso. Non sono modificati motore PEC, deposito, firma o invio. Il rilascio resta aperto fino ai nuovi gate e alle verifiche dello stesso commit.

Il push successivo ha evidenziato un difetto della scelta della baseline critica: un workflow terminato con successo per commit superato aveva saltato il deploy e veniva considerato distribuito. Il gate ora richiede, nel medesimo job/tentativo, esecuzione del deploy, riscontro del commit remoto, container healthy e controlli HTTPS eseguiti positivamente. Esamina anche i tentativi precedenti e ordina le prove per completamento reale, senza confondere un rerun tardivo con un nuovo rilascio. 25 test della configurazione/gate positivi; consultazione reale GitHub seleziona 6604cad0a98b459233f4b3184fc0206863e84dec con deploy 38509343639 e CI 38509343661, coincidente con HEAD server osservato via SSH. Soglie, perimetro, artefatti dei dodici shard e confronto omogeneo non vengono attenuati. Nuovo rilascio ancora in verifica.

## Rilascio verificato — 14 ottobre, ore 19:49 italiane

Versione 2.437.30, commit 0c3f385b8328ef6adfe78780f8086abe9510f06a su origin/main. CI 38605245469 e CI Required Gates 38605245480 riusciti; 89 controlli del registro più il gate complessivo richiesto positivi. Deploy 38605245542 riuscito. Report riproducibile: baseline 6604cad0a98b459233f4b3184fc0206863e84dec e candidata hanno entrambe 27.592 linee coperte su 33.996, 81,16248970467113%, perimetro omogeneo e nessun calo registrato.
Copia locale ricostruita senza cache sul commit esatto, app/scheduler/OCR healthy, api/pronto versione 2.437.30. Guard SQL ripetuto: due record controllati persistiti, 33 clienti precedenti e collegamenti soggetti_parti invariati. Browser reale 8080 a caricamento concluso: opzione inizialmente deselezionata; screenshot default-preventivo-release30-real.png nel dossier privato.
Verifica SSH personale: HEAD server esatto, repository pulito, unica applicazione iusentra-app healthy; app, scheduler, OCR e asset sullo stesso SHA. Profilo Hetzner e API pubblica verificati. Pulizia nativa ripetuta senza dati/volumi: rimosse 0 immagini obsolete, conservata 1, cache 0 B. Browser reale autenticato di produzione: nuova scheda vuota in contesto di collaudo, caricamento concluso e preventivo deselezionato; screenshot privato default-preventivo-release30-production-real.png. Nessun cliente creato dal collaudo di produzione.
Questo punto e le correzioni dei gate che ne impedivano il rilascio sono distribuiti. L'incarico generale, prestazioni globali, catalogo cliente/soggetti e interventi economici ancora in collaudo restano aperti.

## Tranche SQL anagrafica e parti — candidata 2.437.31, 14/10/2026

Risultato richiesto: il salvataggio anagrafico deve modificare soltanto il soggetto interessato, preservare gli altri dati e i collegamenti, rifiutare una scheda React obsoleta e confermare la persistenza. La cartella cliente deve consultare il catalogo SQL indicizzato del proprio studio, senza ricostruire tutti i fascicoli né avviare letture documentali.

Gli archivi clienti/soggetti/parti erano già SQL primari; le ancore JSON storiche non dimostrano uso operativo del file. La correzione elimina la sostituzione integrale di soggetti e parti: scritture puntuali, confronto con il valore SQL precedente, conservazione dei campi storici e UPSERT che non cancella relazioni PostgreSQL. Due richieste per lo stesso soggetto/fascicolo/ruolo sono serializzate e restituiscono la stessa associazione. Il soggetto collegato non viene eliminato cancellando implicitamente le sue parti.

Il modulo React trasporta la revisione della scheda: il server rifiuta il POST obsoleto e quello JSON senza revisione, prima di scrivere. La bozza resta nel modulo; il live mostra i valori in conflitto e Salva è disabilitato finché non sono confrontati. La modifica conserva collegamento cliente, fax e sito non mostrati nel modulo. Il redirect conserva la finestra di lavoro tramite il resolver nativo; corretta la concordanza 1 soggetto.

Il catalogo cliente v2 conserva i candidati dei metadati SQL, anche storici, senza riscrivere l'associazione proprietaria; il modello nativo decide la corrispondenza finale. Metadati invalidi del fascicolo richiesto producono errore esplicito, non una cartella vuota confermata. Trigger SQLite/PostgreSQL aggiornano il catalogo nella transazione del fascicolo. Preparazione esplicita nel rilascio/provisioning, con backup SQLite coerenti; nessuna preparazione dalla GET. Stato Definito rimane distinto dall'archiviazione effettiva.

### Riscontri materialmente osservati

Copia Docker reale8080, candidata diagnostica v3: soggetto sintetico dc0b611b-548 modificato con un clic su Salva, riaperto con la nota prevista e ripristinato. SQL: altri68 soggetti e16 parti precedenti invariati. Collegata dal comando normale una sola controparte sintetica al fascicolo controllato4235FC10: una nuova associazione, seconda selezione mostra Già collegata disabilitato; 35 clienti e23 fascicoli invariati durante il comando. Fonte, documenti e valori del fascicolo non riscritti da tale collegamento.

Due schede reali dello stesso soggetto: la prima salva, la seconda conserva la propria nota e mostra il valore persistito; sulla v3 Salva è realmente disabilitato durante il conflitto. Scelta esplicita Usa valore salvato e ripristino della nota originale salvati; gli altri68 soggetti e16 parti originali restano identici. Le foto private del primo conflitto non inquadravano il banner: la prova di disabilitazione è nello stato accessibile osservato, senza presentare quelle immagini come confronto completo.

Cartella del cliente controllato aperta dal menu/anagrafica: 1 fascicolo attivo in stato Definito,8 documenti,3 comunicazioni, fondo Timeline raggiunto. Il comando viewport non ridimensionava effettivamente il browser: non contato come prova mobile. Ridimensionati invece i bordi della finestra reale; larghezze del contenuto409 e768 pixel, nessuna eccedenza orizzontale del main, comandi iniziali e fondo materialmente osservati. Ripristinata larghezza1223 pixel e chiusa soltanto la finestra di collaudo.

### Guardrail e limiti di chiusura

42 casi catalogo/anagrafica/parti/stato archivio positivi sul contesto selezionato, SQLite/PostgreSQL reali isolati, nessuno skip. Dopo la richiesta della revisione obbligatoria JSON,21 casi soggetti/route ripetuti positivi. Altri25 casi controparti/route reali di test positivi. 341 JavaScript positivi, TypeScript/Vite positivi, Ruff critico e Flake8 mirati positivi. Gate locale finale26/26, comprese101 prove Storybook. Parità PostgreSQL provata nei guardrail isolati; la prova materiale dell'interfaccia riguarda la copia localeSQLite dello studio.

Fallimenti conservati: fixture PostgreSQL priva del cliente genitore corretta creando il genitore; test amministrativo con impostazioni ereditate dall'immagine riprodotto anche sul rilascio30 e passato nell'ambiente previsto; copia frontend iniziale con percorso relativo errato ripetuta con percorsi assoluti. Storybook non si avviava: mancavano i collegamenti delle dipendenze packages/ui nel contesto privato. Ripristinati gli stessi collegamenti installati; la cache preparata quando mancavano è stata spostata entro il perimetro verificato e conservata. Il solo comando clearCache Vitest non bastava; preparazione Storybook ripetuta,101 positive, poi gate completo26 positive. Nessuna dipendenza del prodotto o controllo attenuato.

La candidata non comprende il comando di rinomina o gli altri interventi prestazionali/economici ancora WIP. Il database locale mantiene le anomalie preesistenti registrate nel punto dedicato: nessuna pulizia di dati reali, nessuna riparazione di produzione. Gate GitHub, commit definitivo locale e deploy ancora da confermare; l'incarico generale e gli altri punti restano aperti.

# Prestazioni e comandi mirati — 14/10/2026

Incarico aperto. Nessun commit o deploy di questa candidata ancora verificato.
Baseline attuale distribuita: 2.437.34, `87fee39398189cac01f2b047f5bffea0048cddec`.
Le osservazioni iniziali riportate sotto provengono dalla precedente 2.437.27;
non vanno confuse con i confronti omogenei successivi sulla baseline34.
Prove materiali eseguite sulla copia Docker reale `127.0.0.1:8080`.

## Risultati attesi

Caricare la struttura comune e la pagina richiesta, inizializzare i pannelli
secondari alla loro apertura, consultare soltanto i repository necessari al
comando. Conservare tenant, permessi, provenienza, bozze, decisioni manuali,
sincronizzazione SQL e il flusso congelato di firma/deposito/invio PEC.

## Cause accertate e interventi della candidata

- Le statistiche idratavano i cataloghi PEC/email completi per contarli.
  Il conteggio SQL usa ora tenant e tipo casella, senza payload MIME,
  importazione o inizializzazione di un catalogo mancante. L'errore resta
  esplicito. La compatibilità con studi configurati JSON resta distinta.
- Il dettaglio del singolo fascicolo costruiva ripetutamente gestori e
  caricava l'intero archivio. Riutilizzo entro la sola richiesta, lettura
  mirata nativa e snapshot consultivo dei fatti dello stesso fascicolo.
  Nessuna cache dei dati tra richieste o tenant.
- La validazione dei percorsi ripeteva le verifiche dei prefissi fisici.
  Il batch conserva verifica di confine, symlink e nuova verifica per ogni
  richiesta. Nessuna deroga alle protezioni tenant.
- Il refresh esplicito richiedeva anche sezioni mai aperte, incluso il
  catalogo dei depositi. Ora conserva le sezioni non richieste e aggiorna
  quelle già caricate; resta da collaudare l'intera matrice dei comandi.
- Pannelli chiusi del fascicolo montavano comunque i figli, inizializzando
  anche CTU. La candidata li monta alla prima apertura e li conserva dopo
  la chiusura per preservare le bozze. Prova materiale: apertura CTU dalla
  navigazione del fascicolo, prima richiesta incarichi, nuova bozza, testo
  inserito nel nome CTU, chiusura e riapertura conservano il testo. Annullata
  la sola bozza, nessun incarico registrato. Altri pannelli ancora da provare.
- Una rinomina riavviava il ciclo di lettura della fonte invariata.
  Il percorso normale aggiorna solo il nome nel registro se l'oggetto
  presente conserva la medesima impronta del file archiviato. Fonte nuova,
  impronta mancante o diversa conservano il recupero governato esistente.
- L'indicatore comune è centrato; il proprietario del caricamento inline
  evita la seconda finestra globale, senza cancellare richieste concorrenti.
- La build controlla il grafo emesso: un modulo dinamico raggiungibile
  mediante import iniziali blocca la compilazione. Non basta trovare
  `lazy()` nel codice sorgente.

## Prove osservate

Statistiche: apertura dal menu Studio, filtro PEC, comando Aggiorna e
conservazione del filtro con 376 messaggi. Azzera filtri ripristina dieci
riepiloghi e 41 voci. Osservati in pagina 33 clienti, 23 fascicoli, 18 attivi,
14 scadenze aperte e 2.092 email ordinarie. Confronto del payload prima/dopo:
identico escluso `generated_at`, 10.934 byte. Scroll osservato nella parte
centrale e inferiore; controllo completo fino al fondo ancora da terminare.

Fascicolo controllato 4235FC10, documento sintetico 5FFD3873: rinomina tramite
interfaccia, riapertura con il nome persistito e ripristino tramite lo stesso
comando. Lettore interno aperto: intestazioni, data italiana, testo e accenti
conservati. Due snapshot SQL consultivi prima/dopo il ripristino della seconda
prova coincidono per tutte le letture e i fatti: 33 letture, 11 fatti,
impronta `db083946d050cb638de1fe856fb91da56a35f9883e7359b29a3b790bdd9df288`.
Undici oggetti presenti; nessuna scrittura SQL manuale.

Il primo tentativo del gruppo tecnico indicava un nome test inesistente
(`test_ctu_integrity.py`) e non ha eseguito la suite. Corretta la selezione
al file reale `test_ctu_routes_integrity.py`: 94 test positivi nel contesto
pulito della baseline più i soli interventi prestazionali, SQLite e
PostgreSQL controllato, senza skip. Successivamente 25 test del registro e
snapshot positivi, inclusa rinomina ripetuta, impronte differenti/mancanti
e conservazione dei fatti sui due backend. Quattro guardrail del grafo
bundle positivi; build e controllo TypeScript positivi.

Tempi diagnostici, non accettazione globale: nuova matrice di dieci API in
tre giri completata. Nel terzo giro statistiche 814,2 ms, dettaglio documenti
1.221,6 ms, CTU 251,7 ms, agenda 633,5 ms, scadenziario 776,2 ms, editor
280,1 ms e impostazioni 973,3 ms. Non sono percentuali di miglioramento:
il confronto integrale omogeneo con la release accettata resta necessario.

## Controlli ancora necessari

Editor standalone, copia reale aggiornata v9: aperto Modelli in modalità
Salva modello personale, nome vuoto, nessuna lettura dei due cataloghi nei
log del periodo osservato. Passaggio reale a Usa modello: osservato un solo
indicatore centrale sopra la finestra, poi sette modelli e selettore dei
fascicoli con filtro cliente e ricerca R.G.; due sole GET pertinenti nei log,
entrambe 200. Chiusura, riapertura e chiusura durante il nuovo caricamento:
nessun indicatore residuo. Bozza ancora vuota, Nessuna modifica pendente.
Nessun modello compilato o salvato per questa prova. Dal comando Documenti
è stata aperta la funzione nella finestra di lavoro, con elenco 1–50 di 314;
chiusa, ritorno all'editor. Non è prova della navigazione con bozza modificata.
Prima selezione del link Documenti ambigua (menu e comandi editor): nessun
click eseguito; selezione ristretta alla navigazione Azioni documento.

Cartella cliente, difetto osservato durante il collaudo: il fascicolo nativo
DEFINITO/Da archiviare era contato come già archiviato. Corretto il bridge:
lo stato ARCHIVIATO conferma l'archiviazione; DEFINITO conserva la preparazione
e resta nelle pratiche non archiviate. Nessuno stato SQL modificato. Guardrail
DTO e collegamenti Agenda: 13 positivi. Nella copia reale aggiornata, stessa
cartella aperta dal fascicolo: osservato un fascicolo attivo, card Definito,
nessuna sezione di archiviati per quel caso; otto documenti e tre comunicazioni
conservati. Scroll fino a Economia e Timeline, ritorno/chiusura effettuati.
Il tentativo di tastiera nel body iframe era scaduto: usato lo scroll reale
del browser e verificato il fondo, senza attribuire un esito al tentativo fallito.

Cataloghi editor: la modalità Salva modello non legge più l'elenco dei
modelli. Selezione del fascicolo avviata solo dalla modalità Usa modello,
campi collegati o salvataggio della nuova bozza; chiusura/interruzione
annullano la richiesta e tolgono lo stato di caricamento. Il catalogo SQL
dei fascicoli accede ora al backend senza idratare l'intero archivio tramite
il factory. Guardrail nativi snapshot/nuovo documento/modelli: 36 positivi;
build, 347 test frontend, sette dipendenze e gli ulteriori controlli frontend
positivi nella ripetizione v9. Accettazione reale dei pannelli in corso.

Rinomina primaria SQL: il metodo storico rinomina_documento richiamava il
salvataggio integrale, incluso riallineamento di stati e mirror. Aggiornato
lo stesso metodo con lettura per chiave, transazione del backend nativo e
confronto dello snapshot prima della scrittura delle sole colonne documenti,
metadati e timestamp del fascicolo richiesto. Campi concorrenti, altri
documenti, decisioni, pagamenti e altri fascicoli preservati; errore o fonte
cambiata ripristinano il file. La modalità JSON storica resta invariata.
Il factory usa il gestore mirato solo nella route POST di rinomina SQL.

Guardrail nativi della rinomina: 14 casi positivi SQLite/PostgreSQL,
compreso un aggiornamento da connessione indipendente tra SELECT e UPDATE.
SQLite ne governa la serializzazione; PostgreSQL rifiuta il confronto
discordante, conserva la modifica concorrente e ripristina il file. Primo
tentativo fermato nella fixture (tipo fascicolo obbligatorio omesso e
percentuali letterali nel DDL PostgreSQL): corrette le fixture senza
indebolire il vincolo, poi suite ripetuta. Gruppo dei test esistenti del
gestore, UX e snapshot positivo. Nuovo file aggiunto ai target core/critici,
gate canonico e remoto ancora necessari.

Prova materiale: rinominato 5FFD3873 dal comando Salva nome, risposta 200,
conferma Nome documento aggiornato, nuovo nome presente dopo reload e
lettore EML aperto mentre il nome è modificato. Osservati oggetto, mittente,
destinatario, Message-ID, data italiana e corpo con accenti della fixture.
Ripristinato il nome originale. Controllo SQL in sola lettura su tutti i 23
fascicoli locali: impronta dei campi protetti (esclusi soltanto nome/percorso
del file richiesto, tag di personalizzazione e timestamp pertinenti)
2948d0873528177bdc77e1992e8bba7a9803db20f4bc8c8376e20725043eb5b2
identica prima, durante e dopo. Byte originali del file con impronta
469b414353a4e875a57b96d5f9a0556d45a37060f70094131a8c8606747e2b72
identica. Letture 33, fatti 11, oggetti 11; impronta di letture/fatti
db083946d050cb638de1fe856fb91da56a35f9883e7359b29a3b790bdd9df288
immutata. Non è riconvalida o modifica di dati economici reali.

Restano due richieste successive al salvataggio osservate nei log: refresh
esplicito della sezione e invalidazione live. Non eliminate senza dimostrare
che la prima risposta copra la revisione confermata del secondo segnale;
questa prova di freschezza e il coordinamento dei refresh sono ancora aperti.

Riprova v6 sulla copia reale healthy, immagine locale
`d1d0bb01124f02c61992946d56d346e60a01879d733f349b06f4d27bf2b2f5ed`:
il comando Compila modulo PDF mostra un indicatore centrale visibile sopra
la finestra del lettore; fotografia conservata. Il comando Tutto schermo
del modulo porta alla vista espansa e il cambio alla terza pagina mostra
un solo indicatore centrale; terminata l'attesa è presente Pagina 3 di 3.
Ritorno alla vista normale e chiusura osservati, nessun campo modificato o
documento salvato. L'ispezione DOM del browser non conferma il flag del
fullscreen nativo: si documenta la vista espansa effettivamente vista,
non una conferma tecnica dell'API nativa. Restano gli altri caricamenti,
salvataggi e prove del perimetro globale.

Nel collaudo del lettore PDF controllato è emerso un difetto materiale della
nuova presentazione condivisa: il portale a livello 20000 restava dietro la
finestra gestita, osservata a livello 30004. Non interpretata la vista vuota
come esito positivo. Correzione della regia grafica a livello 100020, sopra
finestre e relativi menu, senza intercettare input; mantenuto il portale nel
contenitore fullscreen nativo. Integrati inoltre i caricamenti di campi e
pagina del PdfModulo e il tracciamento del suo salvataggio. Nessuna modifica
al PDF o alla compilazione/scrittura del dominio. Build e 36 guardrail lettore,
finestre, annullamento e richieste positivi; riprova materiale necessaria.

Gate frontend esteso: 347 casi JavaScript positivi e sette verifiche delle
dipendenze positive, seguiti da controllo hook, contratti React, notifiche,
preset, design system, voce, competenze legali e copertura delle superfici.
Il primo tentativo si fermava su un contratto storico che imponeva l'import
iniziale del supporto operatore. Aggiornato per imporre invece l'import
condizionale e mantenere esplicito il divieto di ciclo con il bootstrap;
il grafo emesso resta soggetto al guardrail di build. Non è accettazione
materiale del supporto operatore né della copertura globale.

Nuova prova diretta `#ctu`: pannello aperto, comando Nuovo incarico e form
presenti; chiusura/riapertura conservano il nome sintetico della bozza,
successivamente annullata senza registrazione. Aprendo Documenti dalla stessa
pagina è emerso un indicatore locale ancora separato: sostituito con il
componente condiviso nel caricamento del catalogo e nel confine dinamico
degli strumenti d'ufficio. Nuova build positiva; riprova materiale in corso.
Corretta inoltre la conservazione del catalogo deposito nelle risposte live
parziali e il suo aggiornamento quando la sezione competente viene richiesta.
Il flusso operativo congelato non è modificato.

Aggiornamento del collaudo del 14 ottobre: 14 guardrail JavaScript positivi,
inclusa alternanza dei proprietari dell'unico indicatore senza cancellare
operazioni concorrenti. Build TypeScript/Vite positiva; candidata locale
aggiornata, container applicativo healthy. Nel browser reale visibile sono
stati osservati un solo indicatore centrale nel fascicolo su desktop,
390×844 e 820×1180, seguito dal caricamento dei contenuti. Dimensioni
ripristinate. Navigazione reale a Impostazioni e Aggiorna in modalità senza
riepilogo: un solo indicatore centrale, poi anagrafica presente. Questa
modalità non attiva il fullscreen nativo: il relativo portale resta da
provare nel lettore/editor. Screenshot privati conservati.

Ulteriori guardrail nativi: 13 casi impostazioni positivi dopo il controllo
dello stato dataset mediante i flag della configurazione corrente; 12 casi
normalizzazione catalogo uffici/isolamento/comuni positivi. Il primo test
catalogo usava una sede reale presente anche nella fonte istituzionale:
aspettativa errata, sostituita con sedi sintetiche senza cambiare il resolver.
La normalizzazione memorizzata riguarda solo stringhe pubbliche del catalogo,
non identità del procedimento o risultati di attribuzione. Profilo caldo
diagnostico del dettaglio: 1.409 ms, con costo residuo di accessi ai percorsi
e query SQL; non dimostra miglioramento globale né assenza di regressioni.

- Apertura e riapertura dei pannelli differiti, bozze, scroll, tastiera,
  responsive e richieste effettive nella copia reale aggiornata.
- Coordinamento fra refresh del comando e invalidazione live dello stesso
  fatto senza perdere modifiche concorrenti. Non eliminare il live per
  far sparire una richiesta.
- Censimento globale di letture/scritture, indici SQL, produttori, code,
  moduli ancora legati a JSON e recuperi puntuali; matrice di salvataggi,
  modifiche, errori, concorrenza e ripresa della connessione.
- Le impostazioni includono ancora sezioni operative e stato dataset non
  richiesti dalla scheda iniziale: analizzare e governare il caricamento.
- Gate, inventario test, copertura canonica, commit/push main, allineamento
  locale sullo SHA finale, deploy Hetzner e pulizia prevista. Tutti aperti.

Le prove private restano nella directory `application-latency-20261014`
dei contesti preservati dell'utente. Gli interventi economici non rilasciati
restano separati e preservati; nessuna riconvalida massiva o modifica
economica in produzione eseguita per questa diagnosi.

14/10/2026 — Ottimizzazione dei profili di configurazione SQL nella sola richiesta: ancore alternate conservate separatamente; controllo del percorso fisico ripetuto anche su cache hit, invalidazione per tenant, modalità e disponibilità del backend PostgreSQL. Gruppo test_archivio_fatti_request_snapshot: 17 casi positivi, compresi cambio modalità, tenant, connessione e destinazione del collegamento simbolico. Suite estesa storage_strategy inizialmente con quattro errori: ambiente pec-guard imponeva PCT_MULTI_TENANT=1 e PCT_PRACTICE_ENGINE_DB globale a fixture isolate. I quattro casi ripetuti rimuovendo soltanto queste due imposizioni ambientali sono positivi; nessun indebolimento dei controlli applicativi. Aggiornamento diagnostico della copia reale e misura in corso; non costituisce chiusura globale o rilascio.

14/10/2026 — Riscontro dopo aggiornamento diagnostico healthy: il primo profilo non riduceva le ricostruzioni perché Tenant.database restituisce un nuovo DatabaseConfig a ogni accesso. Eliminata l'identità dell'oggetto dalla chiave, mantenendo tenant, percorso fisico e valori effettivi; esteso il test con configurazione ricreata a ogni accesso. Gruppo 17 ripetuto positivo. Profilo caldo successivo: 99 risoluzioni di percorso contro 120 precedenti, costo get_request_storage_runtime 137–143 ms contro 197 ms del precedente campione. Tempi complessivi 1.345–1.374 ms: campioni diagnostici, non prova di miglioramento globale né confronto statistico omogeneo. Browser reale: ricaricamento normale del fascicolo controllato 4235FC10, sezione Documenti e atti con 8 documenti presente, nessun errore/avviso console, prova profili-sql-richiesta-v11-real.png. Restano collaudo globale, concorrenza refresh/live, gate e rilascio.

14/10/2026 — Coordinamento dei refresh del fascicolo: comando e invalidazione live ora usano la medesima coda finita. Richieste pendenti prima dell'avvio condividono una lettura; un evento ricevuto durante la lettura conserva un passaggio successivo, senza sovrapposizione. L'intento distingue il comando mirato dalle sezioni già aperte richieste dal live; errori conservano il perimetro per il retry, risposte di un fascicolo precedente non vengono applicate alla nuova vista. Guardrail coda/bozze: 17 positivi; frontend completo 349 positivi, 7 dipendenze positivi, compilazione TypeScript/Vite e contratti positivi. Prova materiale dopo installazione in corso: non dimostra ancora deduplicazione delle richieste osservate né accettazione globale.

14/10/2026 — Prova reale della coda comune: rinomina del documento sintetico 5FFD3873 in COLLAUDO coda refresh mirata.eml e ripristino dal comando Salva nome. Nome aggiornato osservato nella lista, prova rinomina-coda-condivisa-v14-real.png. Due GET dettaglio ancora presenti: 1.082,5 ms e 1.454,8 ms, distanziati; l'invalidazione live arriva dopo la prima risposta. La coda conserva l'evento e non dimostra eliminazione del doppio refresh. Resta necessario attestare la revisione SQL coperta dalla risposta, senza scartare eventi concorrenti. Impronte protette dei 23 fascicoli immediatamente prima/dopo la prova identiche 8df5679ab8a26ac1a4df94619ee142e63b2a6d7b7fee8c6ef7f78a8d7839d55b; bytes originali 469b414353a4e875a57b96d5f9a0556d45a37060f70094131a8c8606747e2b72; 33 letture/11 fatti/11 oggetti, impronta letture/fatti db083946d050cb638de1fe856fb91da56a35f9883e7359b29a3b790bdd9df288. Il vecchio campione primario 2948d087 appartiene a un momento precedente: un altro fascicolo A1FB22FE reca modifica 14:58:06, esterna alla rinomina controllata. Non presentare le due fotografie temporali come identiche. Produzione non aggiornata; incarico aperto.

14/10/2026 — Prova di revisione in sviluppo: richiesta solo dai refresh tramite confirm_revision=1, senza contatori aggiuntivi nell'apertura iniziale. Vettore delle revisioni prima/dopo l'intera proiezione e contesto opaco di studio/utente/repository; una variazione impedisce la conferma. Polling e dettaglio riusano il lettore condiviso dei soli contatori SQL filtrati per permessi, senza letture documentali. Nuovi guardrail nativi: prima selezione 16 positivi; gruppo esteso successivo 41 positivi e un negativo dovuto all'aspettativa JSON esatta precedente del polling. Adeguato il contratto del test per controllare il nuovo contesto oltre agli stessi contatori e permessi, riprova puntuale in corso. Frontend 351 casi positivi più 7 dipendenze; 8 guardrail della coda/prova positivi. Prova materiale e confronto dei costi aggiunti ancora necessari: non dichiarare eliminazione del doppio refresh.

14/10/2026 — Collaudo multi-finestra: rilevata una regressione della candidata v15, poiché i messaggi delle finestre precedenti non contenevano revisionContext e venivano interpretati come cambio proprietario, causando letture ripetute. v16 non interpreta l'assenza del contesto come cambio tenant; v17 accetta dal canale condiviso soltanto contatori con contesto verificabile, lasciando attivo il polling autorevole del server per i messaggi precedenti non certificabili. Guardrail dedicato e frontend ripetuti: v17 353 positivi + 7 dipendenze, compilazione/contratti positivi; Ruff critico e Flake8 dei due nuovi moduli/test positivi sul runtime Python locale. Nel contenitore di test Ruff non era installato: quella chiamata non è una verifica positiva.
Prova v16 sul documento controllato: una lettura dopo la rinomina (1.371,1 ms), nessun'altra lettura di dettaglio nei quattro minuti seguenti; lista e lettore EML riaperto mostrano il nome persistito e il corpo originale con data e accenti italiani. Nel ripristino sono ancora emerse due letture (1.151,5/1.210,0 ms): la compatibilità dei messaggi privi di contesto resta da provare materialmente sulla v17. Impronte protette immediatamente prima/dopo rinomina e ripristino identiche: primario 23 fascicoli bab543e145b2d93cfc1a85066e7c22677d2440d9ffae4d5cf3bef4120ac57452, originale 469b414353a4e875a57b96d5f9a0556d45a37060f70094131a8c8606747e2b72, 33 letture/11 fatti/11 oggetti 9509bbf62b0a2197d4515162204d1007bd30ec809103affe540be4abaa967b55. Le impronte di momenti precedenti sono diverse: non assimilare aggiornamenti intervenuti fra i campioni alla conservazione verificata nella singola prova. Prove rinomina-revisione-refresh-unico-v16-real.png e lettore-dopo-refresh-unico-v16-real.png. Generale, CI/rilascio e collaudo globale aperti.

14/10/2026 — Protezione delle letture parziali: gli errori intercettati dal riepilogo Fascicoli vengono raccolti nella sola proiezione che richiede conferma. Non ricevono readRevision; il refresh React rifiuta i valori vuoti sostitutivi, conserva la vista precedente e segnala il recupero non confermato con retry finito. Guardrail nativi revisione + dettaglio: 31 positivi, SQLite/PostgreSQL senza skip; frontend 353 + 7 positivi, TypeScript/Vite/contratti e Ruff critico/Flake8 dei due nuovi moduli/test positivi.
Copia reale healthy v18: rinomina di 5FFD3873 e ripristino dal comando normale, una GET dettaglio per ciascun comando (1.409,2 / 1.219,4 ms). Nome aggiornato visto nella lista, ripristino in corso di conferma visiva finale; nessun errore di lettura della proiezione nei log osservati. Primario protetto dei 23 fascicoli prima/durante/dopo identico 669ff8a378d7881e1dc936deb6074cf3e72f8095d87b556f2c9b26d3045374db; originale 469b414353a4e875a57b96d5f9a0556d45a37060f70094131a8c8606747e2b72; 33 letture/11 fatti/11 oggetti invariati, impronta 9a05285c2a413e7a93a2634301370bdd17b36fd53461b9899e28ef6ac1e1f470. Prova rinomina-letture-complete-v18-real.png. L'errore di proiezione è stato provato nei guardrail controllati, non indotto sul database reale: non presentarlo come accettazione visiva di quel guasto.
Diagnosi del catalogo cliente: la cartella carica tutti i fascicoli prima del filtro; il modello ricostruisce l'associazione dal dati_json SQL, mentre esiste anche la colonna relazionale id_cliente. Controllo esplicito dei 23 record locali: quattro differenze None/stringa vuota, equivalenti per un cliente identificato; nessuna discordanza di associazione non vuota. Non basta per attestare tutti i database/studi, né autorizza un filtro indicizzato che perda righe storiche. Strategia di lettura puntuale e relativi guardrail ancora aperti; nessuna modifica di associazioni eseguita. Globalità, inventario/gate/copertura, commit/push e deploy restano aperti.

14/10/2026 — Direttiva SQL cartella cliente/anagrafica/soggetti/parti: ricostruito il percorso esistente. Clienti, soggetti e soggetti_parti hanno già repository SQL SQLite/PostgreSQL; i nomi anagrafica.json/parti.json sono anche ancore storiche per il resolver del database dello studio, non prova di lettura operativa JSON. Rilevato full-replace nei salvataggi soggetti/parti: candidata aggiornata per sole righe cambiate, controllo della revisione precedente, conservazione dei campi storici e dei collegamenti durante UPDATE tramite UPSERT. Letture corrotte non rappresentate come archivio vuoto. Catalogo cliente SQL derivato dai metadati, preparazione esplicita e trigger nella stessa transazione, senza rilettura documenti o riscrittura associazioni. Guardrail catalogo: 8 positivi SQLite/PostgreSQL; gruppo concorrenza soggetti/parti e clienti + catalogo: 17 positivi prima dell'estensione campi storici/corruzione; estensione in ripetizione. Primo avvio dei test soggetti fallito per nome metodo fixture nuovo anziché crea: corretto il test, nessuna modifica del contratto prodotto. Modifiche non installate nella copia reale v18, non verificate su macchina reale; preparazione operativa, collaudo, CI e rilascio ancora aperti.

14/10/2026 — Preparazione reale del catalogo cliente fermata dal controllo d'integrità: database locale studio-montagnese danneggiato nella tabella moduli_json_records (rootpage 174), mentre clienti/fascicoli/soggetti/soggetti_parti passano i controlli dedicati. Preservato snapshot originale 364.552.192 byte, SHA256 2a1c27eeae835fbb4f4b741754775af99a47f6c767f4dd81e54d1d407d850cf2. Recupero generico SQLite ufficiale 3.54.0 tentato soltanto offline: modifiche/differenze e record mancanti, escluso dall'installazione. Individuato backup SQL precedente integro SHA256 bd5db0a4e4811556b340824010e6c223957aef424ec977e1437f3f7ccd200aa6 con stesse 8.457 chiavi, metadati identici e tutte le 6.730 righe leggibili identiche. Riutilizzato tools/repair_sqlite_module_table.py, aggiunta verifica esplicita della versione del backup; 6 guardrail positivi. Candidata conserva integralmente le altre 146 tabelle, sequenze, viste, indici, trigger e quattro violazioni FK già esistenti; conserva 414 anomalie di conteggio modulari preesistenti, che restano da diagnosticare e non sono dichiarate risolte. Originali main/WAL/SHM, snapshot aggiornato, candidata e report sono preservati in /data/backup/sqlite-structural-repair-20261014/20261014T153823454941Z. Riparazione applicata solo in locale dopo arresto dei tre produttori; nessun intervento sui dati di produzione. Copia reale v19 e tre servizi healthy; quick_check ok, 8.457 record modulari leggibili, catalogo cliente 23 collegamenti. Preparazione ripetuta sui tre studi locali: changed=false, nessun lavoro ripetuto.
Browser reale v19: anagrafica clienti aperta dal menu, cartella 8D14BC9E aperta dal comando normale; 1 fascicolo attivo (stato Definito), 8 documenti e 3 comunicazioni, scroll completo visto fino alla timeline. Nessun errore/avviso console osservato. Prove cartella-cliente-sql-v19-real.png e cartella-cliente-sql-v19-bottom-real.png. Salvataggi soggetti/parti, prestazioni omogenee e copertura globale ancora in collaudo; nessun commit/push/CI/deploy né conclusione generale.

### Opzione preventivo iniziale e prima persistenza MRZ — 14 ottobre
Direttiva utente: nuovi inserimenti con preventivo iniziale disattivato. Modificati il valore iniziale React e la checkbox della superficie storica; il DTO server già restituisce false. Typecheck e build riusciti; 11 guardrail di salvataggio/bozze riusciti. Copia locale Docker diagnostica refresh21 healthy. Nel browser reale 8080, nuovo contesto isolato collaudo-default-preventivo-20261014: checkbox inizialmente non selezionata, attivazione e disattivazione facoltative osservate. Screenshot privato default-preventivo-disattivato-real.png. Le bozze precedenti non sono state cancellate.
Il precedente documento sintetico con MRZ valida è stato salvato dal pulsante normale: cliente AF8D97AC, cartella aperta dopo il salvataggio; lettura SQL in sola consultazione conferma nome, cognome, sesso, nascita, nazionalità, tipo e numero passaporto TSTSQ0001 e scadenza 2030-01-01. Restano da provare riapertura del modulo e caso MRZ non valida con OCR visibile, preservazione comparativa degli altri record, gate CI e rilascio. Nessuna chiusura dell'incarico generale o dichiarazione di deploy.

Seconda prova reale eseguita: PDF sintetico con cifra di controllo MRZ discordante, lettura normale applica sette valori visibili e conserva l'avviso di MRZ non validata. Nessun dato riconosciuto è stato trascritto manualmente dall'agente. Salva cliente crea B6118222, riapertura tramite Modifica anagrafica mostra Lettura Ocr, Collaudo Invalido, F, nascita 12/08/1974, Passaporto TSTOCR002 e scadenza 01/01/2030. Anche AF8D97AC riaperto conserva gli otto valori della prima prova. Guard SQL in sola lettura confrontato con backup coerente: 33 clienti precedenti identici, collegamenti soggetti_parti identici, entrambi i nuovi clienti con valori attesi, campi non dimostrati vuoti. Preventivo iniziale deselezionato senza intervento manuale nel secondo inserimento. Prove locali controllate, non generalizzate a ogni documento o database PostgreSQL operativo. CI, commit e deploy restano da eseguire.
Riscontro UI da correggere nel perimetro anagrafico: il contatore Completezza dei campi rimane 0 e segnala dati identificativi/documento incompleti anche con nome/cognome/numero/scadenza presenti. Non confondere questo difetto della rappresentazione con mancata persistenza SQL, che è stata verificata separatamente.
Rettifica del riscontro sul contatore: analizzato registryCompleteness.ts, il numero indica gruppi integralmente compilati, non singoli campi. Nei due casi sintetici mancano CF, recapiti, indirizzo, ente e data di rilascio; pertanto zero gruppi completi è coerente con le regole attuali. Nessun requisito viene rimosso e nessun dato viene completato artificialmente. La formulazione generica Completezza dei campi può essere resa più chiara, ma non dimostra un difetto di aggiornamento o persistenza.

15/10/2026 — Lavoro2 prestazioni in corso, candidata privata performance-release35-context derivata dal commit accettato34,65 percorsi selezionati; codice economico futuro e riparazione SQLite residua esclusi. Profilo diagnostico34 sul caso controllato4235FC10 include=documenti:4144/3587/3552ms sotto cProfile,32 aperture del registro e24 letture dei fatti per richiesta; non confrontare questi tempi strumentati con tempi del browser. Prova reale successiva:3276ms lato server, documenti aperti e CTU chiusa, ma richiesta GET CTU447ms osservata. Foto performance-baseline34-visible-real.png. Candidata differisce il montaggio dei figli dei pannelli alla prima apertura e conserva quelli già visitati; il contenitore padre IusentraRoutePresetFrame è già key=routeKey, quindi nessuna nuova chiave arbitraria aggiunta al dettaglio.
Guardia di cambio configurazione PostgreSQL nella stessa richiesta riproduce riuso del backend precedente; correzione con impronta privata di host/database/utente/password/porta/SSL, mai credenziali nei report. Sei configurazioni sintetiche provate, non un incidente reale di assegnazione fra studi. Gruppo richieste/percorsi/revisioni44 positivi; gruppo SQL/posta/rinomina iniziale83 eseguiti e17 skip della sola classe unittest base astratta (non backend assenti). Ripetizione esplicita delle due classi SQLiteMailboxChecks/PostgreSQLMailboxChecks e degli altri moduli:83 positivi, nessuno skip. Frontend436 positivi, nessuno skip; TypeScript e Vite positivi, guardia effettiva del bundle lazy positiva; Storybook102 positivi. Entry applicativa da375,91kB a370,70kB, non prova di velocità globale.
Immagine performance35-diagnostic-not-released costruita dalla base34 con sorgenti selezionati e bundle; installazione della sola app sulla copia reale8080 in corso, lavoratori lasciati34 per preservare le lavorazioni locali. API/versione34 dell’immagine diagnostica non è una release35. Confronto dei valori persistiti, prova reale, matrice globale, causa dell’avvio iniziale fallito, CI e rilascio ancora necessari. Nessuna chiusura del lavoro2.

15/10/2026 — Prima prova materiale candidata diagnostica: apertura normale documenti4235FC10, dettaglio1480,2ms lato server contro3276ms del campione34; confronto strumentato con lo stesso helper2051/1337/1261ms contro4144/3587/3552ms. Campioni limitati, non reattività globale. Payload prima/dopo identico nei valori funzionali: cambiano generatedAt, operationalPresidio.generatedAt e i tempiMs. Nessuna richiesta CTU dopo il caricamento dei documenti in questa nuova scheda fino alla prima apertura volontaria; il log precedente00:44:31 appartiene a una scheda col codice precedente ancora aperta. CTU aperta dal pulsante normale: caricamento riuscito; bozza sintetica conservata dopo chiusura/riapertura, poi annullata senza Registra. Prova performance35-ctu-draft-preserved-real.png.
Rinomina9B87BFC0 tramiteUI: bytes originali69106405ee9fbe6abf81ac2ed3801ecbc3d3fc5fd7e88f8d17f883a5f1613de3 preservati; nel caso4235 cambiano soltanto nome/percorso/tag del documento e modifica della pratica. AncheA1FB22FE cambia timestamp della pratica e presidio_documentale.updated_at nel periodo della prova: causa ancora da dimostrare, non attribuita automaticamente alla rinomina e non presentata come conservazione di tutti23 record. Nome del documento ripristinato conSave. Dopo la rinomina una CTU già visitata ma chiusa è stata ancora richiesta: difetto reale aggiuntivo. Correzione nuova: componente conserva la bozza, marca le invalidazioni ricevute da chiuso e legge quando riaperto; GET CTU riusa get_fascicoli_mirato esistente. Guardia API15 positivi. Nuova storia sul componente reale prova nessun fetch da inattivo, invalidazione elaborata senza lettura nascosta e recupero/bozza alla riapertura. Prima esecuzione negativa per contrasto del testo della nota CTU, non per le asserzioni del ciclo; colore da94a3b8 a64748b e dimensione12px, riprova positiva. Nessuna esclusione del controllo accessibilità.
Cache nella richiesta: due guardie ulteriori negative prima del fix, indice attivo restava sulla seconda ancora dopo cache-hit della prima e il resolver dei link pubblici non azzerava i due nuovi cache-key. Aggiornati i due consumatori esistenti. Gruppo47 con un negativo di una fixture Satispay a studio singolo sotto PCT_MULTI_TENANT/PCT_PRACTICE_ENGINE_DB imposti dall’immagine; stesso negativo riprodotto sul commit accettato34. Ripetizione rimuovendo solo le due imposizioni ambientali:47 positivi. Protocollo pagamenti e fixture invariati, nessun pagamento reale eseguito. Seconda immagine diagnostica in costruzione; questi ultimi fix non sono ancora materialmente provati su8080. Lavoro2 e incarico generale aperti.

15/10/2026 ore01:26 — Riprova materiale sulla seconda candidata diagnostica8080: CTU caricata soltanto alla prima apertura (270,7ms), bozza sintetica inserita e pannello chiuso. Rinomina controllata9B87BFC0 confermata, una GET dettaglio1237,9ms e nessuna GET CTU da chiusa; riapertura esplicita CTU genera la lettura274,9ms e conserva COLLAUDO BOZZA CTU MIRATA. Bozza annullata senza Registra; nome originale ripristinato dal comando normale, una GET dettaglio1189,6ms e nessuna ulteriore GET CTU da chiusa. Foto privata performance35-ctu-closed-rename-restored-real.png. Storybook completo103 positivi su20 file; prima invocazione errata dal node_modules superiore non trova Vitest, percorso frontend corretto e ripetizione completa positiva. Diagnosi in sola lettura anche nel container scheduler34: markerA1FB22FE corrente, impronte documenti/fatti/versione concordanti, nessun tentativo di salva_tabella(fascicoli) nella GET protetta. Questo non dimostra ancora la causa dell’aggiornamento periodico osservato. Matrice globale, avvio iniziale, causa delle invalidazioni residue, CI e rilascio restano aperti.

15/10/2026 ore08:23 — Elenco fascicoli, istantanea cumulativa: la precedente memoria serviva solo categoria singola canonica, mentre i consumatori economici richiedono fatti grezzi e filtri più specifici. Nuova prova sintetica negativa prima del fix su entrambi i backend. Il precarico esistente ora conserva fatti grezzi delle sole categorie dichiarate, tenant e percorso proprietario; applica gli stessi filtri e canonicalizzazione del repository, restituendo copie indipendenti. Errore SQL cumulativo esplicito anziché raffica di letture di ripiego. Gruppo27 positivo SQLite/PostgreSQL. Prima ripetizione con PostgreSQL non raggiungibile: container controllato arrestato dopo riavvio dell’ambiente; riavviato solo iusentra-cu-test-postgres, ripetizione positiva, nessuna modifica del dato studio.
Immagine diagnostica3 healthy sulla sola app8080, lavoratori34 preservati. Browser reale: elenco23, filtroCOLLAUDO12 e ricercaAnastasi con pratica44EBA24A osservati. Confronto diagnostico omogeneo nello stesso processo, cache consultive disabilitate soltanto nel sottoprocesso di diagnosi: interrogazioni fatti134→19. Tempi elenco2612→1083ms, COLLAUDO1969→1066ms, Anastasi1962→1113ms; tutti i valori JSON identici salvo generatedAt. Le19 interrogazioni residue sono12 richieste senza categoria e7 perruolo: non sono le115 ripetizioni importo/evento eliminate. Prima versione dell’helper aveva sostituito il solo produttore ma non il consumatore della memoria, generando KeyError nel sottoprocesso; corretta la strumentazione sostituendo insieme entrambe le funzioni, ripetizione positiva. Nessuna modifica server da questo helper, nessuna scrittura di dati economici. Foto privata performance35-list-after-real.png. Campioni limitati, lavoro2 globale e rilascio ancora aperti.

15/10/2026 — Verifiche dei consumatori dell’elenco: primo gruppo esteso negativo in cinque casi. Un caso usava il dato predefinito /app/data non scrivibile nel contenitore diagnostico; due verificavano cache condivisa su instance_path non scrivibile. Contesto isolato corretto con directory temporanee in memoria e modalità a studio singolo richiesta dalle fixture, senza modificare dati o protezioni prodotto. Guardia CSS cercava una griglia non presente neppure nel CSS accettato34: ora verifica ricerca a tutta larghezza e griglia responsive effettiva. Guardia economica distingue le richieste importo/evento da categorie differenti e confronta le stesse righe disattivando soltanto la memoria nel test di riferimento; non richiede più un errore del database come via normale. Errore reale della lettura cumulativa provato separatamente con rifiuto della proiezione. Cinque casi ripetuti positivi; gruppo completo paginazione/snapshot/revisioni/CTU95 positivi, nessuno skip. Nuovi test entrano nella suite critica della candidata privata, preservate le aggiunte future separate presenti nel runner della copia di lavoro.
Browser8080: navigazione Agenda, scroll; Scadenziario, ricercaAnastasi poi ripristino filtro,5 scadenze aperte mostrate. Editor professionale avviato dal menu, Nessuna modifica pendente. Modelli in modalitàSalva non richiede cataloghi; Usa richiede cataloghi, caricamento osservato, poi modelli e fascicoli disponibili. Chiusura durante caricamento in editor espanso: nessun indicatore residuo e bozza vuota preservata. Successiva prova di bozza modificata in corso; nessun documento o modello salvato da queste prove. Immagini private performance35-agenda-real.png, performance35-scadenziario-loaded-real.png, performance35-editor-expanded-clean-real.png. Nessuna chiusura o rilascio globale.

15/10/2026 — Navigazione editor con bozza modificata: inserita nell’editor vuoto la sola frase sintetica COLLAUDO navigazione con bozza: nessun dato reale. Dal comandoDocumenti aperta la finestra gestita e osservati ricerca, selettore fascicolo ed elenco; finestra chiusa con il comando normale. La stessa frase e Modifiche non salvate risultano ancora nell’editor: nessun obbligo di restare nel solo pannello e nessuna perdita della bozza in questa prova. Foto privata performance35-editor-draft-navigation-real.png. Rimosso poi soltanto il testo sintetico; l’editor vuoto resta marcato modificato, nessun Salva bozza DOCX eseguito, nessun documento reale sovrascritto. Il comportamento del conteggio di bozza dopo ritorno al contenuto iniziale resta da confrontare con lo storico dell’editor, senza simulare un salvataggio non richiesto.

15/10/2026 — Causa delle riscritture periodicheA1FB22FE dimostrata in diagnosi consultiva: entrambi i loader vedono31 documenti, marker corrente, stessa versione e impronte documenti/fatti concordanti, ma26 documenti non ancora coperti dalle letture del marker; needs_cu=true e nessun unresolvedKinds. Il ramo precedente riproiettava l’archivio invariato e risalvava updated_at a ogni giro. Nuovi guardrail negativi prima del fix, sia attesa invariata sia arrivo di fatti con impronta nuova. La candidata confronta anche l’impronta dei fatti SQL: in attesa invariata restituisce waiting_for_reading, analysisUpdated=false, readComplete=false e gli identificativi pendenti, senza nuova proiezione/salvataggio; nuovi fatti forzano la proiezione nativa esistente. Nessuna modifica alle regole di attribuzione degli importi o al flusso d’incasso.
Prova diagnostica sul medesimo modello reale in un sottoprocesso con scritture/proiezione/avvio lettori vietati: stato waiting_for_reading,26 documenti pendenti, pagamenti identici. Non è accettazione finale del ciclo scheduler: i lavoratori reali restano34 finché il rilascio candidato non è verificato. Gruppo tecnico dopo fix segnala un vecchio test che richiedeva la riproiezione senza nuove prove: riallineato per verificare prima nessuna scrittura, poi nuova evidenza SQL, aggiornamento e tentativo ripetuto. Riprova in corso; nessuna dichiarazione di chiusura globale. Gate prima di quest’ultimo fix26/26 positivo,103 Storybook; rigenerazione documenti/gate e nuova accettazione necessari dopo il fix.

15/10/2026 — Candidata prestazioni35, ancora non rilasciata: guardrail finali26/26 positivi,103 Storybook. Gruppo snapshot richieste e paginazione64 positivi dopo correzione dell’attesa economica, nessuno skip. La prova di nuova evidenza SQL conserva importo precedente durante attesa, applica il valore dopo il nuovo fatto e non lo riapplica al tentativo ripetuto. Versione35 allineata in pct,setup,frontend,Dockerfile e railway; nessun rilascio dichiarato da questo bump. Resta necessaria la costruzione sul commit definitivo, accettazione reale del ciclo automatico e CI/deploy. Il primo avvio intermittente segnalato34 resta non riprodotto nelle aperture successive e di causa non dimostrata; non presentato come guasto risolto.

15/10/2026 — Correzione della diagnosi dopo confronto personale nella UI realeA1FB22FE, sezioneLettura: il registro centrale dichiara31 documenti/PEC letti, mentre il readDocuments del solo presidio economico contiene5 righe. Le26 differenze non dimostrano letture pendenti: la prima candidata waiting_for_reading è stata scartata prima del commit. L’inventario economico non sostituisce quello del motore centrale. Nuova uscita per proiezione invariata: existing e analysisUpdated=false, senza readComplete o documentIds dedotti da quel sottoinsieme. Nessun messaggio o fonte nascosto; le informazioni sulle letture restano del registro centrale. Nuove prove SQL continuano ad attivare la proiezione nativa. Riprova dei64 guardrail dopo questa correzione in corso, candidata diagnostica4 da aggiornare: non usare il suo precedente esito di attesa come prova corretta. Nessun push/deploy35 eseguito.

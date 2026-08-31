# PolisWeb/PST: procedura interoperabile e registro prove

Aggiornato il 26/08/2026, fuso orario Europe/Rome.

## Perimetro clean-room

IUSENTRA implementa un flusso proprio, basato su documentazione PST ufficiale,
propri modelli dati, log autorizzati dello studio e comportamento osservabile
del prodotto di riferimento indicato dall'utente. Non vengono letti,
decompilati, trascritti, inclusi o derivati codici proprietari di terzi.

La fonte funzionale di confronto è il comportamento operativo osservato: il
codice pratica già presente determina silenziosamente il registro corretto;
l'avvocato non deve scegliere la tabella ministeriale né compilare oggetto o
materia per una ricerca esatta R.G./anno.

Fonti ammesse:

- Documentazione ufficiale PST e pagina servizi del Ministero della Giustizia:
  `Documentazione_servizi_web_v1.69.pdf` — *Documentazione servizi web esposti (versione 1.69)* —
  <https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571>
  — e catalogo WSDL/XSD associato.
- Catalogo ministeriale degli uffici e dei servizi disponibili.
- Dati SQL tenant-aware dello studio già autorizzati.
- Risposte, stati e log del Local Signer generati durante prove autorizzate.
- Codice e test di IUSENTRA.

## Selezione automatica della tabella

Prima di trasmettere una ricerca al PST, IUSENTRA effettua soltanto una
deduzione locale, senza chiamate esterne:

1. Cerca il fascicolo locale indicato dal collegamento oppure il fascicolo con
   stesso ufficio, R.G. e anno.
2. Ricava il profilo ministeriale dal tipo procedimento e dal registro
   operativo persistito.
3. Converte il profilo nella tabella e nel servizio PST corretti.
4. Invia una sola ricerca autenticata sul servizio risolto.

La deduzione non usa cache generiche di ricerche precedenti e non prova
silenziosamente registri alternativi. Se non esiste un fascicolo locale
compatibile, il flusso invia una sola ricerca sul servizio ufficialmente
compatibile con l'ufficio, mantenendo l'esito esplicito.

| Tabella visibile internamente | Registro | Servizio PST |
| --- | --- | --- |
| Civile ordinario | CC | JPW_SICID |
| Lavoro e previdenza | LAV | JPW_SIL_DISTR o JPW_SILP_DISTR |
| Volontaria giurisdizione | VG | JPW_SIVG |
| Minorenni | MIN | JPW_MIN o JPW_SIMIN |
| Esecuzioni mobiliari | ESM | JPW_SIECIC |
| Esecuzioni immobiliari | ESIM | JPW_SIECIC |
| Procedure concorsuali | FALL | JPW_SIECIC |
| Giudice di Pace | GDP | JPW_SIGP |
| Cassazione civile | CASSCI | JPW_CASSCI |
| Cassazione penale | CASSPE | JPW_CASSPE |

Le tabelle sono una regola tecnica interna: la UI non espone selettori,
codici JPW o altre scelte non necessarie all'avvocato.

## Sessione, PIN e singolo lotto

- Il PIN resta esclusivamente nella finestra nativa del provider del
  certificato. IUSENTRA non lo legge, non lo registra e non lo trasmette.
- La ricerca e la visualizzazione usano una sessione `view` riusabile per
  evitare richieste PIN ripetute.
- La visualizzazione completa usa un unico processo curl autenticato con un
  lotto di richieste correlate: dati, catalogo e sezioni arrivano nello stesso
  risultato e l'anteprima non apre un job aggiuntivo.
- Lo scarico selezionato usa un job locale per
  `/pst/download-documenti-batch`: una sola operazione curl per il lotto,
  senza scarichi singoli concorrenti. Il job pubblica un avanzamento soltanto
  quando curl ha concluso una risposta documentale, quindi la barra e il
  documento corrente non sono una stima temporale.
- Copia e originale restano proprietà di ciascun documento selezionato; il
  batch deve importare nel fascicolo soltanto i file effettivamente scelti.
- Il Local Signer tenta di portare in primo piano il dialogo PIN del provider
  per tutta la durata della richiesta. Questa parte richiede sempre prova
  materiale sul PC che ospita token e browser.

## Consultazione dal fascicolo interno

Il pannello `Fascicolo d’ufficio` non apre più una scheda del Portale Servizi
né richiede all’avvocato un download manuale. Il comando del fascicolo e il
pulsante `Visualizza fascicolo` avviano entrambi lo snapshot completo del
Local Signer (`/pst/fascicolo-snapshot-job`): oltre al primo catalogo SOAP,
questa procedura legge le pagine documentali ufficiali, gli allegati e la
paginazione necessaria a ricostruire il medesimo elenco usato
dall’acquisizione. La sessione `view` valida viene riutilizzata quando
presente; l’elenco, lo stato di acquisizione e la scelta copia/originale
restano nella superficie React di IUSENTRA.

Se la sessione non è disponibile o è scaduta, il provider può chiedere il PIN
nel suo dialogo nativo; IUSENTRA non apre il sito esterno e non conserva il
PIN. Dopo l’elenco, l’acquisizione selettiva resta un unico batch
`/pst/download-documenti-batch` con importazione SQL nel fascicolo corrente.

### Ripristino della sessione scaduta

Il 26/08/2026 una sessione `view` memorizzata dal Local Signer era ancora
marcata come autenticata, ma il cookie PST non era più accettato dal gateway.
La richiesta cookie-only restava quindi in attesa fino al timeout di 90
secondi, senza poter aprire il dialogo PIN. La correzione invalida quel cookie
e ripete una sola volta la medesima chiamata con il certificato: il provider
può così mostrare il PIN nativo. Un timeout della successiva chiamata con
certificato resta invece un errore esplicito del PST, senza ulteriori retry o
ulteriori finestre PIN. La regola si applica in modo uniforme alle chiamate
SOAP singole, raw e batch, quindi a tutte le tabelle ministeriali.

## Persistenza e importazione

Il risultato del PST conserva registro, ufficio, ruolo, identificativi del
fascicolo, eventuale subprocedimento e identificativi documento. La
destinazione primaria è il fascicolo SQL tenant-aware; JSON può essere solo
mirror. Documenti, eventi, parti e scadenze sono deduplicati prima della
registrazione e l'audit memorizza origine, modalità copia/originale ed esito.
Per i documenti PST, la deduplicazione usa prima gli identificativi
ministeriali (`id_documento`, `id_cat`, `id_repeatto`, `msg_id`): due PDF con
lo stesso nome e tipo, ma identificativi ufficiali diversi, restano due
documenti distinti. Il registro separa i documenti nuovi, quelli riusati e
quelli complessivamente registrati, così il conteggio visibile è
riconducibile ai file selezionati.

## Prove eseguite il 26/08/2026

- Guardrail superati: typecheck React, controlli del resolver locale e delle
  dieci tabelle, download batch Local Signer, progresso per risposta e
  deduplicazione di documenti con stesso nome ma identificativi PST distinti.
- Copia Docker locale ricostruita e riavviata; `http://127.0.0.1:8080/api/pronto`
  ha risposto correttamente con applicazione healthy. Nella UI reale sono stati
  verificati il wizard, i sette passi, l'assenza del selettore delle tabelle e
  l'assenza del campo oggetto/materia per la ricerca esatta.
- In una consultazione reale autorizzata, con PIN digitato esclusivamente
  dall'utente nel dialogo nativo, il resolver ha scelto in modo silenzioso una
  sola tabella, ha restituito anteprima, parti, eventi e 30 documenti. Tutti i
  documenti erano selezionati in modalità copia prima dell'avvio del lotto.
- Il lotto ha usato un'unica operazione autenticata, pubblicando avanzamento
  documento per documento. Il PST ha restituito un errore HTTP 502 per un solo
  documento; gli altri 29 sono stati importati nel fascicolo e il conteggio
  locale è rimasto coerente con i file realmente ricevuti. IUSENTRA non ha
  creato file vuoti, duplicati o sostituzioni.
- Il tentativo successivo di ripresa su uno storico precedente, privo
  dell'identificativo ufficiale del documento fallito, ha dimostrato un difetto:
  la UI poteva preselezionare un candidato non dimostrato. Il PST non ha
  completato tale richiesta entro il limite di 300 secondi. Il dettaglio è
  stato conservato solo come diagnosi del canale esterno, senza modificare i
  documenti già registrati.
- Dopo il riscontro del timeout senza PIN, sono stati aggiornati i sorgenti
  effettivamente in esecuzione del Local Signer tramite il suo hot-update
  locale: la copia attiva è stata confrontata per impronta con il sorgente
  validato. Sono stati rigenerati i pacchetti Windows, macOS e Linux della
  stessa versione. Nessun certificato, PIN, cookie o dato di studio è incluso
  nei pacchetti o nel backup della procedura.

## Correzione della ripresa mirata

Ogni nuovo errore di download persiste ora, nel registro locale della
procedura, il tipo di ripresa, la modalità copia/originale e gli identificativi
ministeriali del solo documento non ricevuto. Il collegamento di ripresa passa
un identificativo del registro, non il nome del file. Dopo una nuova
anteprima, IUSENTRA seleziona esclusivamente un documento con corrispondenza
univoca di identificativo ufficiale; una corrispondenza per nome, data o tipo
non è sufficiente.

Se uno storico precedente non contiene l'identificativo o se il documento non
è più presente nell'anteprima, la ripresa non preseleziona alcun documento e
la UI lo dichiara esplicitamente. L'avvocato può verificare e scegliere
manualmente, ma il software non sostituisce mai il documento. I log locali
disponibili sono stati esaminati solo in forma aggregata: non contengono
l'identificativo necessario per riparare in sicurezza il vecchio storico.

## Audit selezione tabella e avanzamento — 26/08/2026

L’audit corrente ha separato il default generico dell’ufficio dalla tabella
specifica del fascicolo. Il codice ufficio identifica il canale ministeriale,
ma non può sostituire il profilo esatto già persistito per R.G., procedimento,
materia e codice oggetto. Per il fascicolo controllato il profilo strutturato
è Lavoro: la selezione `JPW_SIL_DISTR` è pertanto coerente ed è la stessa
riscontrata nelle consultazioni reali riuscite. `JPW_SICID` resta il default
ufficiale da usare solo quando manca un profilo del fascicolo compatibile.

Il pannello diretto ora chiede al resolver server-side la tabella del
fascicolo prima della chiamata e non consente a valori storici della snapshot
di prevalere. Riusa inoltre la sessione `view` ancora valida, come il wizard
di acquisizione; se il PST la dichiara scaduta, il Local Signer ricrea solo il
canale necessario. Non viene forzata una nuova sessione a ogni click e non
vengono duplicati il PIN o il processo curl.

Il nuovo job di consultazione non è un secondo percorso PST: avvia il lotto
unico `ricerca-snapshot` e pubblica solo gli stati materialmente raggiunti:

1. risoluzione di ufficio e tabella;
2. apertura o riuso del canale certificato;
3. risposte del lotto PST effettivamente ricevute;
4. elaborazione di fascicolo, catalogo e sezioni;
5. esito finale.

Il polling del browser raggiunge soltanto il Local Signer in loopback; non
genera ulteriori richieste al PST. Il contatore e la barra di avanzamento
sono esposti solo dopo che il lotto comunica il numero reale delle risposte,
quindi non rappresentano percentuali stimate.

Verifiche automatiche eseguite dopo la correzione:

- matrice decisionale completa delle dieci tabelle: profilo → schema →
  tabella → servizio Local Signer, incluse esecuzioni mobiliari, immobiliari
  e procedure concorsuali;
- preservazione del codice oggetto come dato del fascicolo, senza che possa
  sovrascrivere una procedura esatta già risolta;
- job `ricerca-snapshot` con pubblicazione di fase, contatori e risultato
  del medesimo lotto;
- dispatch HTTP del job, typecheck React, compilazione Python e controllo
  diff senza errori;
- ricostruzione della copia Docker reale `127.0.0.1:8080` e allineamento del
  Local Signer installato alle sorgenti aggiornate.

La suite estesa `tests/test_local_signer.py` + `tests/test_react_shell.py`
è stata rieseguita integralmente dopo gli aggiornamenti e si è conclusa senza
failure. Ha riallineato tre guardrail obsoleti: la condizione di caricamento
del suggerimento tabella, la precedente apertura esterna del portale e il
vecchio test che cercava campi generici anziché la ricerca esatta già risolta.
Resta distinta e ancora necessaria la prova materiale con PIN nel browser
reale.

## Verifica reale ancora richiesta

La copia Docker locale è stata ricostruita e il Local Signer attivo è stato
riallineato al sorgente corretto. Resta aperta la prova reale del nuovo
pulsante `Visualizza fascicolo`: il PST deve restituire l’anteprima nella
stessa pagina, senza aprire il sito esterno, e il provider deve proporre il
PIN nativo quando il cookie precedente non è utilizzabile. Non viene avviato
alcun nuovo tentativo automatico né alcun invio del PIN da IUSENTRA;
l’avvocato lo digita nel dialogo nativo. La verifica conclusiva deve
osservare: un solo dialogo PIN nativo per la consultazione, riuso della stessa
sessione per le letture correlate, selezione esatta, modalità copia/originale
preservata, avanzamento, esito e conteggio del fascicolo.

## Correzione catalogo completo e selezione manuale — 26/08/2026

Durante la verifica reale del pannello diretto il catalogo aveva esposto solo
cinque atti principali, mentre l’acquisizione completa del medesimo fascicolo
aveva restituito trenta documenti. La causa era circoscritta: il pannello
usava `ricerca-snapshot-job`, che pubblica il primo catalogo SOAP e le sezioni
del fascicolo, ma non la lettura delle pagine documentali ufficiali e della
loro paginazione. Non è stata modificata la ricerca guidata già verificata.

Il pannello diretto ora usa `fascicolo-snapshot-job`, già governato per il
catalogo completo. Il job riusa la sessione `view`, non forza una nuova
sessione e pubblica gli stati reali: tabella selezionata, autenticazione,
catalogo iniziale, pagine e allegati, dati del fascicolo ed elaborazione
finale. Il componente React unisce le sorgenti `documenti`, `catalogo`,
`sezioni.documenti_fascicolo` e gli eventuali depositi prima della
deduplicazione per identificativo ministeriale.

L’elenco espone inoltre i comandi `Tutti`, `Nessuno` e la modalità collettiva
`Copia` o `Originale`; resta disponibile la scelta per singolo documento. I
documenti già registrati nel fascicolo restano visibili con lo stato
`Acquisito`, ma non sono riscaricati automaticamente né duplicati. Al download
il servizio, il registro e la tabella provengono dallo snapshot appena risolto,
non da valori storici del fascicolo.

Guardrail eseguiti dopo la modifica: compilazione Python, typecheck React,
controllo diff, test del resolver delle dieci tabelle, test del catalogo
completo e test dei controlli di selezione. La copia locale è stata ricostruita
ed è healthy su `http://127.0.0.1:8080/api/pronto`; resta necessaria la prova
materiale con PIN nel browser reale per confermare il conteggio completo sul
PST e l’assenza di richieste PIN ripetute.

## Audit di riallineamento al backup positivo — 26/08/2026

Il controllo più recente ha corretto una deviazione introdotta nel pannello
`Documenti e atti`: la ricerca diretta era stata instradata a
`ricerca-snapshot-job`, che restituisce il solo catalogo SOAP iniziale. Il
percorso ora è di nuovo `fascicolo-snapshot-job`, lo stesso percorso presente
nel backup della prova positiva. Tale job completa il catalogo con le pagine
ufficiali di InfoFascicolo e con il recupero master/dettaglio degli allegati;
non viene aggiunto un secondo lotto PST dal browser.

Il pannello usa ora la medesima priorità del wizard per tabella, servizio e
registro: prima il resolver server-side calcolato dal fascicolo (compresi
procedura, materia e codice oggetto), poi lo snapshot storico solo se il
resolver non può decidere. Il risultato del job unisce tutte le raccolte
documentali previste prima della deduplicazione, così una posizione non resta
invisibile perché esposta in `catalogo`, `sezioni` o `depositi` anziché nel
primo campo `documenti`.

Il confronto completo fra `tools/local_signer.py` e
`local-signer-procedura-final-20260826-115150.zip` evidenzia due sole
variazioni deliberate: il limite esterno del processo curl viene portato al
massimo configurabile di 10.800 secondi e il timeout del processo usa il
minimo tra il limite configurato e quello richiesto dal lotto. I timeout delle
singole chiamate PST non sono stati ampliati. Il codice di
`_pst_fascicolo_snapshot`, il suo job e la selezione della tabella sono
invariati rispetto al backup. Il pacchetto distribuito e il processo Local
Signer attivo corrispondono allo stesso sorgente.

La matrice delle dieci tabelle e il catalogo dei codici oggetto sono stati
ricontrollati: 1.018 codici univoci, nessun duplicato e nessun codice non
risolto. Questo è un controllo di regole e dati; non sostituisce la prossima
prova reale con PIN. Dopo il ripristino non è ancora stata osservata nel
browser reale l’intera consultazione del pannello diretto: il lavoro resta
aperto finché il PST non espone il catalogo completo e l’avvocato non verifica
selezione, modalità copia/originale e una sola richiesta PIN per operazione.

Guardrail eseguiti nell’audit: 6 test Local Signer mirati, 35 test della
matrice PST/cataloghi, test del contratto React del pannello, typecheck React,
compilazione Python e controllo diff. È stata ricostruita la copia Docker
locale e verificata la risposta `pronto`; la pagina reale del fascicolo è
stata ricaricata senza avviare una consultazione. Il test PIN/PST resta quindi
esplicitamente non verificato su macchina reale dopo questo riallineamento.

### Regressione certificato rilevata nella prova reale

La prima pressione di `Visualizza fascicolo` ha confermato una regressione del
pannello: `ensureCertificate` produceva un valore vuoto quando il certificato
non era già presente nella memoria della scheda. Il Local Signer bloccava
correttamente la richiesta prima del PST, ma l’avvocato riceveva un errore
anziché il dialogo nativo. Il pannello ora ripete la sequenza del wizard:
rilevamento del certificato compatibile, quindi selezione nativa CNS/CIE se
necessaria; solo dopo trasmette il singolo lotto di consultazione. Il PIN non
è letto né salvato da IUSENTRA.

Il dialogo nativo CNS/CIE riceve come owner la finestra Windows in primo piano
al momento della richiesta. In questo modo resta modale sopra IUSENTRA invece
di comparire solo nella barra delle applicazioni; il pump già presente continua
a portare in primo piano anche l’eventuale dialogo PIN del provider.

### Verifica materiale del prompt PIN sopra IUSENTRA — 26/08/2026

La diagnosi sul computer reale ha identificato il contenitore usato da Windows
per il token Bit4id: `CredentialUIBroker.exe`, classe
`Credential Dialog Xaml Host`. Il precedente monitor riconosceva il processo,
ma provava ad attivare soltanto il primo handle enumerato; il vero popup poteva
restare legato a un owner o root-owner distinto e comparire solo nella barra.

Il Local Signer `1.6.118` ora:

- usa firme Win32 pointer-safe per tutti gli HWND coinvolti;
- percorre owner, root-owner e ultimo popup attivo del broker credenziali;
- ripristina la catena e porta TOPMOST il popup effettivo senza modificare
  posizione o dimensione;
- considera stabile l’esito finché il popup resta visibile, non minimizzato e
  non cloaked, evitando pressioni tecniche di attivazione ripetute;
- distingue le finestre nate durante il curl da quelle preesistenti, così il
  cleanup può chiudere soltanto prompt appartenenti all’operazione corrente;
- non legge, compila, registra o trasmette il PIN.

La prova isolata finale è stata eseguita sul Local Signer realmente installato,
con una sola richiesta locale `/pst/preflight-auth`, senza download e senza
inserire il PIN. Alle 22:16:26 Windows ha mostrato materialmente sopra la pagina
IUSENTRA la finestra `Sicurezza di Windows · Smart card · Immettere il PIN`.
Il log ha registrato un solo passaggio effettivo a primo piano; non vi sono state
riattivazioni nei successivi 36 secondi. Alla scadenza intenzionale della prova,
il processo curl e il prompt sono stati chiusi senza registrare download.

Evidenza visiva:
`artifacts/ui-checks/pin-foreground-final-20260826-221645.png`.

Guardrail eseguiti: compilazione Python e cinque test mirati relativi a
rilevamento del prompt, catena owner/root-owner, riuso del dialogo, console
silenziosa e timeout del lotto. La prova completa dal pulsante React
`Visualizza fascicolo`, con inserimento del PIN da parte dell’avvocato e risposta
reale del PST, resta distinta: la verifica non può essere dichiarata conclusa
finché tale click non conferma lo stesso comportamento e il catalogo completo.
L’analisi è clean-room su sorgenti, log e backup IUSENTRA; non è stato trascritto
o copiato codice proprietario decompilato.

## Esito reale positivo wizard e Fascicolo ufficio - 27/08/2026

L'avvocato ha confermato in persona entrambi i percorsi sulla copia Docker reale `http://localhost:8080`:

- Wizard `Importa pratica da PST / PolisWeb`: consultazione del fascicolo, anteprima e acquisizione del lotto documentale con la procedura Local Signer positiva.
- `Fascicolo d'ufficio` in `Documenti e atti`: consultazione autenticata, selezione di tutti, nessuno o documenti singoli, scelta `Copia` o `Originale`, lotto unico e avanzamento per documento. I documenti acquisiti restano non selezionabili per evitare duplicati.
- Local Signer in uso: `1.6.116`. Il PIN non e' stato registrato nel repository, nei log applicativi o nel backup.

Il backup verificato della procedura e del runtime associato e' `artifacts/local-signer-procedure-backups/pst-wizard-office-documents-positive-20260827-020909.zip`, SHA-256 `ED9668FFDF1FA57027A9BF9145247C55526B1CDF11F81119A15CEC982B4AA7BD`. Include sorgenti React, Local Signer, bundle Git, patch della worktree e copia del runtime installato; esclude PIN, cookie, sessioni PST, documenti e dati dello studio.
## Riallineamento pannello Fascicolo d’ufficio — 27/08/2026

Durante la verifica successiva, il pannello ha ricevuto soltanto cinque atti
principali già acquisiti. L’origine non era nei controlli di selezione: essi
escludono correttamente i documenti già presenti nel fascicolo per evitare
una nuova importazione duplicata. Il log del Local Signer ha invece mostrato
che il pannello era stato deviato dalla procedura positiva e aveva avviato un
recupero master-detail cookie-only aggiuntivo; il PST lo ha rifiutato con HTTP
401. Tale percorso aggiuntivo è stato rimosso.

Il job `fascicolo-snapshot` è stato riallineato al percorso diretto conservato
nel backup positivo. Il Wizard continua a usare il proprio lotto interattivo
unico senza un recupero cookie-only successivo. La UI conserva seleziona tutto,
deseleziona tutto, formato copia/originale e avanzamento per documento; il job
di consultazione pubblica quattro stati reali: apertura canale, connessione,
catalogo e dati del fascicolo.

Verifiche tecniche eseguite: compilazione di `tools/local_signer.py`, sei test
mirati Local Signer, test React mirati del pannello, typecheck React e
`check_local_signer_boundaries.py`. La copia reale `localhost:8080` risponde
con versione `2.278.82`; il Local Signer `1.6.124` installato ha impronta
SHA-256 identica al sorgente. Non è stata eseguita una nuova consultazione
reale con PIN dopo questo riallineamento: il risultato sul catalogo completo,
la selezione di documenti non acquisiti e l’unico prompt PIN restano da
verificare materialmente nel browser reale prima di commit, deploy o
classificazione positiva.
## Correzione del pannello Fascicolo d’ufficio — 28/08/2026

L’osservazione reale di cinque richieste PIN ha invalidato il precedente riallineamento al job diretto fascicolo-snapshot: quel job esegue ulteriori recuperi autenticati e non è equivalente al lotto unico del Wizard.

Il pannello React ora invoca direttamente POST /pst/ricerca-snapshot con include_full_snapshot: true e single_interactive_batch: true, omettendo identificativi locali non necessari nella ricerca iniziale. Questo è lo stesso percorso di consultazione usato dal Wizard, con un solo lotto PST per la visualizzazione. Lo scarico resta una seconda operazione separata, sempre con un solo lotto per tutti i documenti selezionati.

La UI distingue ora:

- Acquisito: stato informativo, non più un divieto di selezione;
- Seleziona tutto, Seleziona non acquisiti e Deseleziona tutto;
- Scarica: riscarica i selezionati, inclusi gli acquisiti, in copia o originale senza modificare il fascicolo;
- Acquisisci nuovi: importa soltanto i documenti non ancora acquisiti, preservando il presidio anti-duplicato.

Sono passati typecheck React e i due contratti automatici mirati. La nuova prova materiale su http://localhost:8080 con una sola richiesta PIN per la consultazione e una sola per l’eventuale lotto di scarico resta necessaria e non è ancora stata eseguita per questa correzione.
## Catalogo completo e parità batch Wizard / Fascicolo d’ufficio — 28/08/2026

Il pannello `Fascicolo d’ufficio` usa lo stesso endpoint interattivo del Wizard,
`POST /pst/ricerca-snapshot`, con un singolo batch autenticato. Per una pratica
già identificata aggiunge al medesimo contratto `id_fascicolo`, utilizzando
esclusivamente il riferimento ministeriale memorizzato nel fascicolo; non avvia
un job aggiuntivo e non effettua recuperi cookie-only.

La risposta può riportare lo stesso catalogo nei rami `documenti`, `catalogo`,
`documents` e `sezioni.documenti_fascicolo`. Il pannello ricompone tali rami per
identificativo del documento prima della UI: un sommario parziale non può più
nascondere record presenti nella stessa risposta autenticata. La regola è
generica e vale per tutte le tabelle ministeriali, senza eccezioni per ufficio,
numero R.G. o materia.

Guardrail automatici: typecheck React; test dello snapshot completo; test di
parità tra richiesta del Wizard e richiesta del pannello (endpoint, ufficio,
numero/anno, certificato/sessione, finalità `view`, tabella/servizio,
`include_full_snapshot` e `single_interactive_batch`). La prova reale con
certificato/PIN non è stata eseguita per questa correzione: non va considerata
verificata finché la UI locale non mostra il catalogo completo ricevuto dal PST.

## Verifica catalogo incompleto e correzione cookie-only — 28/08/2026

La prova reale sul fascicolo del Tribunale di Vicenza, R.G. 1084/2026, ha dato esito non accettabile: dopo il solo PIN inserito dall’avvocato, il pannello ha visualizzato “Nessun nuovo documento disponibile”. Il log del Local Signer ha confermato che il codice ufficio operativo era corretto: identificativo studio `0640011`, codice ministeriale `0241160092`, servizio `JPW_SICID`. La causa non è quindi la tabella ministeriale né il codice ufficio.

Il lotto SOAP iniziale ha restituito soltanto il sommario/atti principali e una risposta di sezione non bloccante con SOAP Fault `IDATTO`. Nel ramo `single_interactive_batch` mancava però la lettura della pagina ministeriale autenticata del fascicolo, che espone allegati e pagine successive del catalogo. Il risultato parziale veniva pertanto trasformato impropriamente in elenco vuoto.

Correzione applicata a `tools/local_signer.py` e al Local Signer realmente installato `1.6.124`: dopo il lotto iniziale, il catalogo viene completato dalla pagina ministeriale usando **solo** il cookie della sessione già autenticata. Non vengono passati certificato, thumbprint o retry mTLS all’arricchimento: la correzione non può quindi richiedere un secondo PIN. Se la pagina non restituisce documenti, resta il recupero master-detail cookie-only, anch’esso senza certificato o retry.

Verifiche tecniche eseguite: compilazione Python della sorgente e del runtime installato; sette test mirati Local Signer (parità Wizard/pannello, catalogo completo, allegati/paginazione, servizi e schema); riavvio silenzioso del solo Local Signer e risposta positiva `/ping?light=1` su processo avviato alle 13:48 del 28/08/2026. La nuova prova materiale su `http://localhost:8080` non è stata eseguita in questa sessione per non richiedere all’avvocato un ulteriore PIN; il comportamento reale del catalogo completo resta quindi **non verificato su macchina reale** e non va classificato come risolto.

## Correzione lotto unico catalogo completo — 29/08/2026

### Causa confermata dal confronto con il backup IUSENTRA

Il backup con esito positivo conserva la stessa fonte del catalogo completo: la pagina ministeriale autenticata `documentiFascicolo`, che contiene allegati oltre ai cinque atti principali restituiti dal solo SOAP. Nel codice corrente il Wizard e il pannello erano stati portati sullo stesso job, ma il catalogo esteso veniva richiesto dopo il batch iniziale tramite più recuperi solo-cookie. Se il cookie non era sufficiente, il risultato rimaneva fermo ai cinque atti principali; inoltre il batch iniziale includeva cinque sezioni accessorie, facendo crescere il tempo della consultazione oltre il comportamento osservato di circa 45 secondi.

### Correzione applicata

- `registroRicerca` viene normalizzato ai codici brevi ministeriali per tutte le dieci tabelle (`CC`, `LAV`, `VG`, `MIN`, `ESM`, `ESIM`, `FALL`, `GDP`, `CASSCI`, `CASSPE`), senza riutilizzare il nome tecnico della tabella.
- Il percorso comune `POST /pst/ricerca-snapshot` ora compone un unico processo `curl` autenticato con tre trasferimenti SOAP (ricerca, profilo, sommario) e, quando il registro espone la pagina, due trasferimenti GET in sequenza (scheda e catalogo allegati). Lo stesso certificato e lo stesso cookie jar restano nel processo: non esiste un secondo processo solo-cookie nel ramo interattivo.
- Eventi, comunicazioni, udienze e scadenze non sono più aggiunti al lotto iniziale; non ritardano il catalogo selezionabile. Le tabelle senza pagina InfoFascicolo mantengono il loro catalogo SOAP senza essere bloccate.
- La UI Wizard e Fascicolo d’ufficio restano sul medesimo endpoint e sul medesimo contratto; il download selezionato resta un secondo lotto separato.

### Controlli tecnici eseguiti

- Compilazione Python della sorgente e del runtime installato: superata.
- Sei test mirati Local Signer: superati. Coprono lotto `curl` unico SOAP/HTML, catalogo, parità Wizard/pannello, normalizzazione delle dieci tabelle e compatibilità del job.
- `GET /api/pronto` su `127.0.0.1:8080`: applicazione pronta, versione `2.278.83`.
- `GET /ping?light=1` su `127.0.0.1:27272`: Local Signer `1.6.124` pronto dopo riavvio silenzioso.

### Stato di accettazione

Non è stata ancora eseguita la nuova prova materiale PST dopo questa correzione. La connessione automatica alla scheda browser integrata non è disponibile in questa sessione; pertanto servono ancora click reale su `Visualizza fascicolo`, una sola richiesta PIN inserita dall’avvocato e osservazione nella UI di 30 documenti, del tempo di consultazione e dell’assenza di un secondo prompt. Fino a tale prova, la correzione è **non verificata su macchina reale**.
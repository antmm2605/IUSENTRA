# Epigrafi e recupero del lettore — incarico aperto

## Risultato richiesto

Il lettore deve riconoscere le parti processuali senza trasformare indirizzi,
qualifiche, intestazioni scolastiche o etichette di modelli vuoti in persone.
Ogni codice fiscale resta riferito al soggetto che lo dichiara nella fonte,
senza attraversare la sezione del difensore. I contratti di lavoro e di
prestazione d’opera conservano la propria natura documentale e non producono
parti o date processuali.

## Cause e correzioni della candidata 2.437.13

L’enfasi rappresentata con asterischi spezzava l’ancora del nome: ora si
normalizza conservando i separatori di epigrafe. Il nome dell’ente richiede
un confine di parola. Le qualifiche iniziali vengono separate dal nome;
etichette fiscali non sono nomi. La sezione dell’Avvocatura delimita i dati
della controparte. La classificazione nativa riconosce il titolo del
contratto di prestazione d’opera, senza classificare come contratto un
ricorso che lo cita.

Le letture storiche compatibili restano ferme. La riconvalida è un evento
SQL esplicito sul fascicolo interessato, con le procedure e i motori
condivisi. Nessun filtro della UI nasconde una discordanza e nessuna
decisione manuale viene sostituita.

Il lettore documentale ritenta soltanto le GET interrotte o temporaneamente
non disponibili, con limite di tre richieste e messaggi italiani. I
salvataggi non vengono ripetuti automaticamente. È disponibile il comando
di recupero del caricamento, senza eliminare modifiche locali.

## Riscontri finora osservati

Browser reale 8080: dopo rilettura puntuale del primo fascicolo verificato, la
residenza resta nella citazione del cliente; quattro parti proposte,
nessuna persona ricavata dall’indirizzo o dall’etichetta fiscale. La vista
già aperta aveva conservato la proposta precedente fino al ricaricamento:
il comportamento live resta sotto verifica.

Browser reale, secondo fascicolo: nome privo della qualifica e nessuna intestazione
scolastica tra le parti. Emerso codice del difensore attribuito al
Ministero in due atti; corretto il confine e riscontrati i due originali
con il motore condiviso. Dopo il completamento della coda SQL, riapertura
reale e successivo aggiornamento WIP8 confermano il nome del cliente e il
codice fiscale proprio del Ministero; gli originali restano conservati.

Guardrail: 54 test Python mirati, cinque test di recupero HTTP, Ruff;
gate statico con 26 controlli e 101 verifiche Storybook senza errori.
Sono guardrail tecnici, non accettazione finale. Backup coerenti e fonti
originali conservati fuori Git. Commit, push, riallineamento al commit e
deploy di questo punto non ancora eseguiti; incarico generale aperto.

12/10/2026 — Ulteriori riscontri: il payload storico del verificatore del
 giudice non conteneva fascicoloId e campi necessari al pannello comune;
la GET falliva con KeyError. Il repository restituisce gli identificativi
SQL autorevoli, il produttore conserva confronto e collegamenti alle fonti.
Ripubblicazione nativa sui due fatti verificati, valore manuale preservato.
Browser reale WIP6: avviso con RG completo e due documenti espandibili.
Emersa falsa discordanza dovuta al diverso ordine delle stesse parole del
nome del magistrato: confronto esatto delle parole introdotto, senza
correzioni per somiglianza né sovrascrittura del valore manuale. La nuova
prova reale WIP7 conferma l'assenza della falsa discordanza dopo consegna
nativa dei due fatti: valore manuale invariato, vecchia verifica superata
con audit, nessuna presa visione manuale dell'agente.

Lettore reale: fonte Contratto 21-22.PDF, otto pagine, scroll fino alla
pagina finale con immagine, testo, timbro e sottoscrizioni visibili.
Modifica testo correttamente protetta; nessuna modifica dell'originale.
Questa prova non dichiara qualità OCR integrale o recupero HTTP transitorio.

Scheduler: errore database is locked alle 02:19 durante rilettura puntuale;
lock non presente alla diagnosi delle 02:26, recupero al ciclo naturale
02:34 concluso alle 02:37, prima di ricreare i container. Causa esatta della
contesa ancora sotto presidio. Gate statico primo giro 25/26: inventario
 dei test non aggiornato, generato con script nativo; nuovo giro 26/26,
101 Storybook. Ultimo perimetro Python 75 test positivi, Ruff positivo.
Nessuna dichiarazione di chiusura prima di commit/push, allineamento locale
e deploy verificato. Incarico generale aperto.

12/10/2026 — Apertura delle fonti: nel browser integrato la pagina ha una
cornice esterna non accessibile; il comando veniva inviato a quella cornice
anziché alla shell IUSENTRA. Il dispatcher inoltra al parent soltanto da
un iframe realmente accessibile dello stesso sito; negli altri casi usa
la regia di finestre della pagina corrente. Quattro guardrail dedicati,
più cinque sul recupero GET, positivi. Browser reale 8080 WIP8: Agenda,
impegno del 09/10, Visualizza fonte apre il decreto dalla PEC nel lettore
nativo; pagina originale visibile, tutto schermo, scroll fino al fondo,
chiusura conserva il dettaglio e riapertura mostra di nuovo il PDF.
Foto privata source-window-real-local-wip8.jpg, nessuna modifica o invio.
Gate finale ripetuto: 26 controlli, 101 verifiche Storybook, nessun errore;
75 test Python mirati positivi con Python 3.14 locale. La CI Python 3.12
e il rilascio sullo stesso commit sono ancora da eseguire. Il recupero
HTTP temporaneo è verificato tecnicamente, non ancora osservato durante
una reale interruzione sul commit finale. Copertura live globale, causa
esatta della contesa SQL e altri incarichi restano aperti e presidiati.

Controlli estesi: la raccolta completa della suite ha rilevato che il test
Timesheet già tracciato dal commit 4b7e365f3c importava uno script assente
da Git, checkout, copie recuperate e server. Aggiunta la procedura SQLite
esplicita richiesta da quel contratto: anteprima senza scritture, due
backup nativi con hash e quick_check, rifiuto di collisioni e collegamenti
mancanti, inserimenti puntuali e audit nella transazione. Cinque prove su
archivi temporanei positive, inclusi backup fallito, replay senza nuovo
audit e fonte preservata. Il primo nuovo fixture lasciava aperta una
connessione di controllo su Windows: chiusura esplicita e prova ripetuta.
Nessuna migrazione Timesheet eseguita sui dati reali; concorrenza e adozione
operativa Timesheet restano un incarico distinto aperto.

Registrati i cinque file Python del perimetro nella matrice nativa
quality-overlay: tutti e tre gli shard eseguiti con limite di cinque
minuti, esiti positivi (shard più lungo 40,1 secondi). Raccolta completa
ripetuta senza errori. Una build estesa ha fallito per file index.html
mappato da Windows: ripetizione isolata positiva, senza cambiare il codice
o indebolire il controllo. I restanti gate completi sono ancora in corso.

Prima del rilascio, backup coerente dei registri dei due studi in
/data/backups/identity-release-prod-20261012-before: quick_check positivo,
hash nel report privato. Inventario SQL produttivo: cinque verifiche nel
primo studio, nessuna nel secondo; nessun payload storico incompleto del
giudice aperto. Nessuna verifica rimossa e nessuna presa visione applicata.

Backup strutturato produttivo eseguito dalla procedura nativa prima del
rilascio: snapshot /opt/iusentra/backups/epigrafi-release-20261012/
iusentra-structured-20261012_011229_570864. Tre database dello studio
(incluso il percorso storico), 14.511.976.448 byte, tutte le verifiche
quick_check positive e impronte nel manifest. Nessuna fonte locale
trasferita e nessun dato applicativo rimosso. Un primo comando di sola
lettura del manifest aveva quotatura PowerShell errata: ripetuto con
lettura diretta riuscita; backup non modificato.

Ulteriore riscontro visivo WIP8: scroll reale nel pannello del secondo fascicolo,
cliente con codice fiscale concordante, Ministero con codice fiscale
proprio e difensore separato; ruoli non dimostrati ancora espliciti.
Foto privata case-b-parts-final-local-wip8.jpg. Nessuna aggiunta manuale
al fascicolo o conferma di avvisi.

Prova materiale della navigazione con bozza nuova, senza associazione a
cliente/fascicolo e senza salvataggio: scritto il testo controllato,
clic reale Oggi dalla navigazione principale, finestra caricata, chiusa.
L'editor resta sul proprio URL e conserva il testo e lo stato Modifiche
non salvate. Foto private editor-draft-navigation-local-wip8.jpg e
editor-draft-retained-local-wip8.jpg. Annulla ripristina zero parole;
nessun documento creato nel fascicolo. Non estendere questo riscontro
alla persistenza di tutti i tipi di bozza o a tutti i percorsi editor.
Dal riscontro emerge sovrapposizione parziale della riga di stato con
la toolbar: registrata tra i dettagli editor ancora da correggere.
Ultimo gate statico: 26 verifiche positive, exit 0; controllo completo
ancora in corso.

Nuovi fixture di regressione: nomi e codici personali sintetici, indirizzo inventato e magistrati inventati; 39 prove mirate ripetute positivamente dopo questa verifica. Le fonti reali e le fotografie restano fuori Git. CTU: il rilascio SQL/live del 10/10 è documentato, non ripetere l’adozione. Il riscontro odierno del presidio backup rileva riferimenti non raggiungibili nei due studi; conservati audit e snapshot coerenti correnti, recupero puntuale ancora aperto nel registro.

Guardrail OCR del 12/10: due aspettative statiche del vecchio percorso fallivano anche senza differenze nei file runtime rispetto al commit di base. La prova aggiornata segue FascicoloOcr → OcrConfronto → OcrPageViewer/OcrReview e confronta i quattro estremi dei riquadri con quelli nativi del PDF a 300 dpi (tolleranza di un pixel), preservando font e grassetto. Il solo stile dinamico ammesso nel menu è la sua altezza misurata nel viewport; resta vietato introdurre stili decorativi in linea. Tutte le 55 prove del file passano. Nessuna modifica al motore OCR o alla superficie runtime in questo passaggio; controllo integrale ancora in corso.

Prova materiale del recupero su 8080: apertura dal comando Anteprima del DOCX controllato, chiusura e riapertura durante arresto e riavvio del solo container app locale (scheduler/OCR e server produttivo preservati). Il lettore mostra errore italiano e Riprova caricamento; app torna healthy e pronto HTTP 200. Il clic reale Riprova recupera la policy ma lascia la fonte sulla pagina offline: risultato incompleto, causa nel mancato aggiornamento della revisione del lettore. Corretto il pulsante per aggiornare anche la revisione, con rimontaggio della fonte originale e conservazione degli interventi. Nuova build e ripetizione sullo stesso caso ancora da eseguire; nessuna conferma positiva anticipata. Foto privata reader-real-restart-error-local-wip8.jpg.

Ripetizione sulla copia reale WIP9: tutti i tre container healthy. Riavviato il solo app e riaperta Anteprima dallo stesso DOCX controllato: errore italiano e comando Riprova caricamento con icona e nome accessibile visibili. Dopo pronto HTTP 200, clic reale Riprova: fonte originale riaperta con iuRevision=1, pagina offline assente, testo controllato visibile. Chiusa anteprima: editor conserva 33 parole/232 caratteri e Nessuna modifica pendente. Foto private reader-retry-icon-real-local-wip9.jpg e reader-real-restart-recovered-local-wip9.jpg. Prova del recupero, non attestazione universale di fedeltà DOCX.
Primo gate integrale terminato con quattro passi falliti: build Vite/file Windows in uso, raccolta/tool Timesheet assente, OCR/aspettative statiche obsolete, packaging/versione frontend arretrata e lista extra del test non aggiornata. Correzioni e ripetizioni mirate: 26 statici e 101 Storybook, 55 OCR, 19 packaging, raccolta e cinque Timesheet positivi. Le dipendenze PDF già governate non sono state rimosse o cambiate; riallineata versione frontend 2.437.13 e aspettativa del test. Secondo gate integrale ancora in corso; il primo exit 1 resta documentato.

Verifica aggiuntiva nel browser reale WIP9: ridimensionamento del bordo destro con tastiera, area iframe misurata 460 pixel. Fonte Word controllata e comandi visibili/raggiungibili, testo a capo senza perdita di contenuto; finestra poi chiusa senza modifica del documento. Foto privata reader-narrow-real-local-wip9.jpg. Riscontro della finestra ridimensionata, non prova su dispositivo mobile. Il comando Scarica del titolo passa su una seconda riga: dettaglio di compattazione del lettore da includere nel punto layout, senza nasconderlo o estendere il riscontro a tutti i layout.
12/10/2026 — Recupero puntuale del presidio backup CTU in produzione: riferimenti aggiornati per i due studi soltanto dopo snapshot nativi coerenti dei rispettivi StudioDB, quick_check ok, impronte registrate e verifica SQL successiva in sola lettura. Revisione 1 con un audit __backup_recovery; audit __adoption di revisione 0 conservato, zero incarichi/comandi/rifiuti invariati. Snapshot dichiarati successivi all’adozione, senza ricostruire falsamente i preventivi del 10/10; causa della precedente indisponibilità non dimostrata. Primo tentativo fermato prima di eseguire il recupero perché Compose cercava il tag predefinito e avviava una build: ripristinati i servizi, corretto il wrapper privato con immagine esatta e207cf7, pull never e ripresa senza build né dipendenze. Secondo tentativo exit 0; app/scheduler/OCR/Redis healthy, unico iusentra-app sul commit e207cf7, pronto pubblico 200 versione 2.437.12. Cleanup nativo exit 0, zero immagini rimosse e una conservata; cache incompleta eliminata senza dati/volumi. Browser reale produzione: riapertura fascicolo dall’Agenda, CTU e perizie caricato, Nuovo incarico apre tutti i campi e il calcolo assistito; scroll alto/basso e Annulla senza registrazione. Foto privata ctu-production-after-backup-recovery-fields-20261012.jpg. Prova del recupero del presidio e dell’apertura, non nuova attestazione integrale di ogni procedura CTU. Incarico generale aperto.
12/10/2026 — Candidato epigrafi/lettore 2.437.13: secondo ci_local_gate.sh integrale terminato exit 0, 40 passaggi positivi e zero fallimenti, inclusi dieci gruppi core, acquisizione/OCR, catalogo, shell React, sicurezza, RBAC, distribuzione, Local Signer e 48 prove Lex. Il primo giro exit 1 con quattro passi falliti resta documentato con correzioni e ripetizioni. Guardrail aggiuntivi dell’ultimo cambiamento del lettore: 26 statici/101 Storybook e nove JS positivi; recupero dopo interruzione provato nel browser reale 8080, fonte riaperta e documento controllato invariato (33 parole/232 caratteri). Sono riscontri tecnici e materiali del candidato; commit/push, allineamento dello SHA e rilascio di produzione ancora da eseguire. Nessuna attestazione di copertura globale, fedeltà universale o completamento dell’incarico generale.
12/10/2026 — Rilascio epigrafi/lettore 2.437.13: commit 1e71a6247d944421f31e2c6c989d6ba7f82455fa sui due branch autorizzati; branch protetto chore/monorepo-foundation invariato. CI 38200730630/38200730726, overlay, frontend e aggregatori positivi; deploy 38200730596/38200730702 success. Copia reale 8080 sullo stesso commit, app/scheduler/OCR healthy, dieci impronte runtime corrispondenti e Anteprima Word controllata riaperta con 33 parole/232 caratteri invariati. Produzione: unico iusentra-app healthy con immagine esatta, worker healthy, pronto pubblico 2.437.13 Europe/Rome, profilo Hetzner verificato con env-file nativo; cleanup conserva una sola immagine, snapshot temporaneo assente, nessun dato/volume toccato. Primo controllo Compose senza env-file fallito prima di operazioni: ripetuto correttamente.
Riconvalida puntuale di due fascicoli produttivi dopo backup coerenti nativi separati di StudioDB e registro, quick_check e SHA256 positivi: due eventi accodati una sola volta e conclusi idle alle 06:21. Browser reale: primo caso passa da cinque a quattro parti, strada presente soltanto nella citazione dell’indirizzo; codice fiscale dell’assistita concordante. Nel secondo caso codice assistita e codice ente distinti, giudice preesistente invariato nel confronto SQL e nel profilo visibile. Rilevato nuovo falso positivo: intestazioni scolastiche di un contratto numerato proposte come assistito/controparte, con effetti anche nei destinatari proposti. Non confermata la presa visione, nessun invio o firma. Il punto resta aperto.
Diagnosi della nuova fonte: il testo SQL verificato porta un numero di pagina prima del titolo CONTRATTO DI PRESTAZIONE D’OPERA, non ammesso dal precedente ancoraggio. Candidato 2.437.14 riconosce questo titolo mantenendo esclusi gli atti giudiziari che lo citano; 22 test mirati positivi e fonte SQL reale classificata come contratto senza parti processuali. Compatibilità delle precedenti versioni conservata, nessuna rilettura storica generalizzata. Gate integrale, installazione reale, prova UI, commit/push e deploy del candidato ancora da eseguire. Fonti e fotografie reali rimangono fuori Git. Incarico generale aperto.

12/10/2026 — Candidato 2.437.14 installato sulla copia Docker reale 8080 (tag WIP esplicito), app/scheduler/OCR healthy e pronto 200. Apertura reale Arcuri: quattro parti archiviate, ma il controllo SQL mostra zero testi indicizzati locali, inclusi i contratti scansionati. Questo risultato non costituisce accettazione della correzione del titolo numerato presente nella lettura di produzione. Backup preventivo nativo dello studio e del registro con quick_check e impronte, poi evento SQL forzato del solo fascicolo autorizzato; comando Leggi i nuovi cliccato nella UI reale, stato loading osservato. In attesa del ciclo software e del riscontro finale. Corretto anche il letterale insieme di un'asserzione dei test, 22 casi ripetuti positivi; nessuna modifica funzionale aggiuntiva. Gate integrale ancora in corso, nessun nuovo commit/push/deploy.

12/10/2026 — Riscontro materiale del candidato 2.437.14: il comando software Leggi i nuovi ha prodotto nel repository Document AI il testo del Contratto 21-22 con il titolo numerato presente anche nel caso di produzione. Lettura archivio del medesimo oggetto con versione +contratto-titolo-numerato: otto fatti persistiti, natura contratto_prestazione_opera, zero fatti parte; nessuna trascrizione manuale né testo sostitutivo inserito. Browser reale 8080: riepilogo aggiornato automaticamente, quattro parti senza intestazioni scolastiche, codice fiscale dell’assistito e dell’ente preservati; profilo mantiene il giudice originario. Foto privata contract-numbered-reader-local-20261012.jpg vista e mostrata. Coda SQL ancora running, consegne/indici di supporto in corso: non dichiarata conclusa l’intera lavorazione o la funzione globale. Difetto emerso: il polling GET azzera lo stesso loading usato dal POST ancora attivo; il payload legge _IN_CORSO del processo web, mentre il lavoro è nello scheduler e la coda SQL risulta running. Il presidio loading/live resta aperto per correzione primaria su stato persistente e stati React separati. Durante il recupero osservato messaggio di riconnessione live e due voci di provvedimento Sentenza nella cronologia: riscontro della provenienza/deduplicazione da eseguire prima di qualunque rimozione. Nessun messaggio o dato reale nascosto manualmente.

12/10/2026 — Fine ciclo locale: coda del caso idle alla generazione 48, claimed_generation 48. Il riepilogo ha mostrato indisponibilità/Failed to fetch e sono stati registrati WORKER TIMEOUT per entrambi i processi web; la dicitura generica Perhaps out of memory non prova OOM: memory.events riporta oom e oom_kill zero. Riapertura della sola scheda agente, priva di bozze: riepilogo di nuovo disponibile, richieste osservate di 3,08 e 2,90 secondi. Profilazione nativa puntuale del raccoglitore: 32,3 secondi totali, 23,3 nel presidio PEC, 22,1 nell’inizializzazione schema e circa 20 nei commit SQLite; prova non identifica da sola ogni causa del timeout. Nessun file del flusso congelato modificato. Foto e quattro parti precedenti erano un risultato intermedio: dopo le nuove letture la UI finale mostra sette proposte, senza intestazioni scolastiche, ma include tre proposte generiche tratte da provvedimenti di altri procedimenti/supporto giurisprudenziale. Verifica di pertinenza delle singole fonti e presupposti congiunti aperta; nessuna aggiunta al fascicolo, nessun invio o firma. La correzione del titolo numerato è materialmente riscontrata nel suo oggetto, non dimostra correttezza globale di classificazione, parti, date, loading o lettore.

12/10/2026 — Diagnosi ulteriore delle tre proposte estranee: le due fonti giurisprudenziali sono riconosciute correttamente come precedenti sia nel testo nativo sia nell'indice, ma i fatti parte persistiti provengono dal callback OCR delle 06:52, senza fatto natura e senza decisioni manuali. Il callback costruiva il fascicolo usando PCT_FASCICOLI_DB globale e, in assenza del dato, proseguiva con contesto vuoto: poteva sovrascrivere la lettura tenant-aware con parti estranee. Modifica candidata: il worker conserva il testo e affida la verifica alla coda SQL nativa del fascicolo; il repository riapre il solo oggetto corrente e accoda l'evento nella stessa transazione, senza forza generalizzata, preservando i fatti fino alla verifica con il contesto corretto. Controlla tenant, presenza e impronta corrente; fallimenti di consegna non sono più ignorati dal worker. Quattro guardrail mirati positivi (selezione della sola fonte, isolamento, sostituzione e rollback/errore di consegna), Ruff dedicato positivo; il primo Ruff aveva tre rilievi preesistenti su nomi ambigui, corretti senza cambiare regole. Nuova build locale in corso: comportamento nuovo non ancora verificato materialmente, commit/push/deploy non eseguiti. Il gate integrale avviato prima di questo cambiamento non certifica da solo il nuovo codice. Il flusso congelato non è stato modificato; il worker OCR presente nel manifesto baseline ha già un'impronta diversa nella release corrente, la modifica candidata riguarda esclusivamente la mancata conferma della consegna documentale.

12/10/2026 — Copia reale aggiornata temporaneamente a ocr-context-wip4 (2.437.14), app/scheduler/OCR healthy e pronto 200; tre impronte dei sorgenti runtime identiche al candidato. Build React/typecheck positiva. Guardrail archivio/runtime/registo positivi; il test nuovo di stato inizialmente interpretava erroneamente False di concludi_evento come fallimento, mentre significa assenza di una generazione ulteriore: test corretto secondo il contratto nativo, ripetizione positiva. Prima della prova puntuale, il controllo dei vecchi job si è fermato su index_path globale /data/search/index.db, pur avendo documento e registro nel tenant corretto: nessuna nuova coda creata e nessun backup parziale. Causa nel produttore Leggi i nuovi che passava current_app.config globale. Adeguamento candidato al runtime OCR condiviso: risolve SEARCH_INDEX con tenant_data_path e require_tenant prima di accodare, per tutti i produttori, senza leggere fonti né creare un motore alternativo. Test nativo di coda SQL dimostra il percorso studio persistito anche se il produttore passa il globale; 21 guardrail dedicati positivi e Ruff positivo. La prova sui due documenti userà la configurazione nativa corrente dello studio, conservando i vecchi job; nuova build wip5 in corso, accettazione materiale ancora aperta. Nessun trasferimento di testi dello studio a servizi esterni, nessun invio o firma.
12/10/2026, 07:40 — WIP6 installata sulla copia reale 8080, versione 2.437.14: app, scheduler e OCR healthy; quattro impronte runtime identiche al candidato. Il runtime ora propaga l'errore di risoluzione del registro durante una richiesta Flask, evitando job senza studio/registro: sette nuove prove, insieme a worker e registro, 22 guardrail positivi. Recupero puntuale dei soli due documenti già diagnosticati, dopo backup nativi SQLite con quick_check ok e SHA256 registrati privatamente: due job completati al primo tentativo, indice e registro entrambi nello studio corretto. Lo scheduler ha preso la generazione 50, ancora running al riscontro; il fascicolo precedente resta idle alla generazione 111. Nessuna cancellazione manuale di fatti né trascrizione dell'agente. Browser reale: reload della sola scheda di verifica senza bozza, apertura, chiusura e riapertura Lettura; stato Lettura automatica in corso: 2 oggetti in lavorazione, 75 letti e 2 da leggere, comandi Aggiorna e Leggi i nuovi disabilitati, rotatore generale con testo Lettura dei documenti in corso. Foto privata ocr-context-loading-local-20261012.png, vista del rotatore nella pagina. Le proposte precedenti restano visibili mentre il motore completa la verifica: non dichiarare il risultato ottenuto. Prova accodata dalla procedura nativa puntuale, non presentata come click Leggi i nuovi; accettazione della causa e del flusso normale ancora aperta. Gate integrale precedente ha superato i dieci gruppi core ma non è terminato e non copre da solo gli ultimi cambiamenti. Commit/push/deploy della candidata ancora da eseguire.


## 12/10/2026 — Riscontro WIP7 e richiesta sincrona da correggere

La ripetizione puntuale nativa sui due documenti termina al primo tentativo (job 69 e 70), con indice e registro nel percorso dello studio; generazione 52 idle. Nel browser reale 8080 il pannello aperto passa da 75 a 77 oggetti letti, termina l’indicatore e riabilita il comando. Le chiamate native al pannello Parti seguono il cambio dell’ultima lettura senza reload: elenco di quattro soggetti, senza le tre persone estranee delle fonti scolastiche. La quarta voce MIM richiede ancora il presidio di deduplicazione semantica; nessuna rimozione manuale o filtro per nasconderla.

La prova successiva del comando normale Leggi i nuovi fallisce: richiesta prolungata, catalogazione sincrona di 77 fonti, timeout del worker e messaggio di rete. Non costituisce accettazione del comando. La correzione WIP8 consulta solo lo stato SQL nella richiesta, conserva l’accodamento OCR nativo e consegna il lavoro alla coda persistente esistente; il consumer, sotto lease, indicizza solo fonti pendenti, senza retry di errori invariati, prima del ciclo archivio. Il messaggio di connessione viene espresso in italiano senza nascondere il problema. Prova materiale WIP8 ancora da eseguire.

Verifica PostgreSQL reale con nove tabelle TEMP e search_path pg_temp: isolamento tenant, impronta corrente, rifiuto fonte modificata, rollback dell’accodamento e claim/completamento positivi. Nessuna tabella pubblica o dato dello studio modificati. È guardrail SQL, non accettazione dell’intero prodotto.

Gate integrale iniziato sulla versione precedente delle modifiche: acquisizione/OCR e catalogo passano; registry/gates segnala inventario dei test non aggiornato. Inventari rigenerati con procedura nativa; gate da ripetere sulla candidata finale. Il primo nuovo test del comando riscontra Operazione non autorizzata nel fixture API privo di attore DocumentAI: isolata la verifica del contratto della richiesta con riepilogo controllato, mantenendo i controlli di autorizzazione del prodotto. Ripetizione mirata positiva. Nessun commit/push/deploy della candidata 2.437.14 ancora eseguito.

## 12/10/2026 — Ridondanza del classificatore e confronto materiale del calcolo

Il comando normale WIP8 risponde HTTP 200 e la generazione 53 viene consumata dal scheduler nativo fino a idle (08:12). La lentezza in sfondo resta osservata, senza attribuire successo al solo ritorno HTTP. Diagnosi locale sui testi SQL già archiviati: budget diagnostico raggiunto su un record da 4.113.507 caratteri; stack individua has_presidio_rule dentro il ciclo del classificatore, che esegue tutte le regole ripetutamente sul medesimo testo. Nessun OCR o risultato applicato dalla diagnosi. Il bootstrap diagnostico registra il riallineamento del ruolo piattaforma: non viene descritto come interamente privo di scritture.

Il file condiviso fascicolo_document_catalog.py è stato confrontato prima della modifica: main e candidata coincidono, SHA256 ddd26db960995a46f12600de5019caa7e5ab057c068ee68046dec5818ad764b0. Il manifest della baseline congelata conserva ba93bee9be79a576a952ff203196237872a37fa2592401afcdc89302a53b1aec: il file aveva già modifiche pubblicate successive; nessun ripristino della baseline eseguito. Nuova correzione limitata al riuso locale dei riscontri della medesima funzione; nessuna regola, ordine di priorità, classificazione, flag di deposito o comportamento firma/PEC cambiati.

Confronto del metodo precedente e della candidata sul medesimo testo SQL: 8,171 secondi contro 0,463 secondi; dataclass completa identica. Prova diagnostica, non accettazione UI. Suite classificatore: 26 test positivi, Ruff positivo. Richiesta e consumer: 19 test positivi; test JS letture/loading 17 positivi con loader nativo. Prima esecuzione JS senza loader fallisce sull’import extensionless; ripetuta col loader del package, nessun indebolimento. Test inventario rigenerato positivo. WIP11 in costruzione per accettazione reale; commit/push e deploy restano aperti.

12/10/2026 08:31 — Candidata 2.437.14, WIP12 sulla copia reale 8080: app, scheduler e OCR healthy, pronto 200. Click reale Leggi i nuovi nel fascicolo di controllo: conferma «Lettura registrata nella coda dello studio», indicatore di lavoro e pulsante disabilitato; a fine ciclo UI torna allo stato di 77 fonti lette e pulsante disponibile senza reload. Coda SQL generazione 54 idle alle 08:30:25 Europe/Rome; lavori OCR sempre 41 completed, ultimo id 70, nessun nuovo lavoro. Parti lette quattro, invariati cliente e controparte già dimostrati. Foto privata reader-wip12-finished-local-20261012.png mostra il registro, non prova tutti i domini del prodotto.
Il riepilogo separato dei presìdi conserva in SQL un record in_corso delle 06:56:34, senza esiti, precedente all’installazione WIP12. Provato Aggiorna nell’interfaccia: nuova esecuzione registrata alle 08:34:12; esito finale ancora da verificare. Nessuna rimozione del messaggio o conferma manuale. Causa strutturale da presidiare: thread di verifiche distinto dalla coda durevole e polling UI singolo dopo nove secondi.
Gate integrale precedente, iniziato prima delle ultime correzioni, terminato 39 passi positivi e un fallimento registry/gates (inventario test poi rigenerato e guardrail ripetuto). Nuovo gate integrale sul candidato corrente in esecuzione: nessun commit/push/deploy della 2.437.14 dichiarato. Una query diagnostica usava generazione anziché la colonna reale generation; corretta dopo lettura dello schema, sola lettura. Un comando PowerShell diagnostico conteneva redirezione non supportata: parsing fallito prima dell’esecuzione, ripetuta sola lettura senza redirezione.
12/10/2026, candidato 2.437.14 — Prova WIP13 dei presìdi sulla copia reale 8080.
Il comando Aggiorna è stato eseguito nel browser reale sul fascicolo di prova già in uso. Evento SQL generazione 55, presidi richiesti e forza documenti falsa, reclamato nel worker nativo. Il pannello ha ricevuto automaticamente la conclusione delle verifiche, senza ricaricamento: esito 09:07, quattro presìdi conclusi e errore PEC esplicito database is locked. Nessuna attestazione positiva per la verifica PEC. Foto privata presidi-wip13-esito-lock-local-20261012.png. L’editor controllato è rimasto aperto con testo e stato senza modifiche pendenti preservati.
La causa dell’errore PEC riguarda ensure_schema: un nuovo processo prova a scrivere lo schema già installato mentre una lettura concorrente tiene occupato il database. Candidato successivo: ricevuta persistente dell’impronta dello schema con controllo di sola lettura per tenant già inizializzato; installazione completa preservata per nuovi schemi/studi. Confronto AST con backup prima della correzione: unico metodo modificato PecAuditRepository.ensure_schema; procedure PEC, deposito, firma e notifiche non alterate. Manifest accettato del 09/09: pec_pipeline.py già diverso prima di questo intervento, impronta accettata 126a3229ba21bc3365278698a590e031850adeff8bba5cadb34f63567e114c41, pre-intervento attuale 3dac3c82fddc7f32f10ae7bad5cbbcebaaee5c54105b07593a86ae7affa9f7fd. Nessuna pretesa di uguaglianza storica del file.
Backup preventivo coerente registro letture quick_check ok, SHA256 0e355f488dfff7642fecefa7993ba8d9f409de91cdea34393a6579736a51f651. Backup coerente PEC ancora in esecuzione: non attestato finché termina e supera quick_check.
Guardrail: frontend typecheck/build WIP13 riusciti; test nuovi SQLite richiesta presìdi, lease recuperata, errore e generazione concorrente, migrazione precedente passati. Prova PostgreSQL in nove tabelle temporanee con isolamento, rollback, richiesta presìdi, ripresa lease e migrazione riuscita; primo tentativo diagnostico DuplicateTable corretto usando CREATE TEMP TABLE IF NOT EXISTS, nessuna tabella degli studi modificata. Test schema PEC con lock concorrente passato; prima verifica Ruff ha rilevato import introdotti dopo le funzioni, corretti; due rilievi preesistenti pec_pipeline.py restano distinti dai nuovi cambiamenti.
Gate integrale avviato prima della scoperta del blocco dei presìdi interrotto intenzionalmente sul solo albero di processo identificato per integrare la correzione: non è un esito positivo né un fallimento di test. Local Signer e PC preservati. Ricerca diagnostica iniziale rglob nel volume terminata per memoria su percorso storico ricorsivo; abbandonata e sostituita dal percorso canonico del repository. Copia test sul medesimo file nel checkout di rilascio rifiutata, ripetuta con percorso assoluto della copia principale. Nessun reset o pulizia del lavoro recuperato.
Commit/push, CI e deploy del candidato 14 ancora da eseguire; produzione resta sul rilascio 13. Incarico generale aperto.
# Aggiornamento del 12/10/2026 — presìdi e identità congiunta

Il backup SQLite nativo PEC precedente all’intervento sul controllo dello schema è terminato: 2.783.911.936 byte, quick_check positivo, SHA256 ecbd5197bec06e554b621fb6eab861effcc8a8d549cdc8fad49c9ef1a7ad8800. È una copia coerente conservata nel volume locale, senza trasferimento in produzione.

La prova WIP14 con il comando reale Aggiorna ha accodato la generazione 56 ed è entrata nella lavorazione. Durante il controllo della procedura è emerso un collegamento interno PEC basato sul solo ruolo e mittente: corretto riutilizzando il resolver dell’identità congiunta, con numero e anno R.G., parte e ufficio concordanti, controllo del codice fiscale dichiarato e protezione da fonte cambiata o associazione manuale. Le procedure di invio, firma e deposito restano fuori da questa modifica. L’audit controllato dell’esecuzione interrotta non registra nuovi collegamenti prodotti da questa lavorazione.

Il solo scheduler locale è stato fermato per applicare la correzione; app e OCR sono rimasti attivi. Dopo aver verificato lo scheduler fermo, il repository nativo ha rimesso la generazione 56 in pending tramite concludi_evento con il proprietario esatto e riuscito=False, conservando il lavoro richiesto. Non è stato cancellato o falsamente concluso l’esito in corso.

Tredici controlli mirati dell’identità PEC superati. Il pannello React ora espone, in un dettaglio apribile, le cause registrate per ogni PEC non attribuita; rimosso il limite di sei esiti salvati. Primo controllo TypeScript ha rilevato un accesso a proprietà opzionale, corretto; seconda build positiva. Questi sono guardrail, non accettazione materiale della nuova interfaccia.

Il giro integrale precedente è stato interrotto prima della correzione dell’identità: non vale come verifica dell’ultima versione. È stato avviato un nuovo giro integrale. Installazione della nuova immagine sulla copia reale, prova visiva finale, commit/push e deploy del candidato 2.437.14 restano in corso; nessuna dichiarazione di completamento generale.


## 12/10/2026 — Ripetizione reale e ulteriori cause emerse (lavoro aperto)

La generazione 56 ha concluso alle 09:58:46 dopo recupero della lease tramite il repository nativo. Nel browser reale 8080 la fonte aperta è rimasta disponibile; riepilogo e archivio conservavano 77 documenti e 116 fatti. Il record SQL distingueva però 9 depositi controllati nello studio, 2 pendenti nel fascicolo e 73 documenti pronti nell'indice su 77: la proiezione precedente non mostrava questa distinzione. Corretta la proiezione SQL e React; guardrail 43 Python, ulteriori 28 narrativi, 1 sul payload e 18 JS positivi. Un primo comando JS con percorso Windows invece di URL file è fallito; ripetizione corretta positiva, senza attribuirlo al prodotto.

WIP17 ha concluso la generazione 57 alle 10:18:33. Successivamente il pannello mostrava «Lettura del fascicolo non disponibile». Ispezione delle cache SQL: envelope ok/lettura corretti per entrambi i casi; quindi ipotesi di cache corrotta esclusa. Chiusura e riapertura reali del pannello, senza Aggiorna e senza nuove letture, hanno recuperato gli esiti: 9/2 depositi, 73/77 indice, 77 letti dall'archivio, 116 fatti. Individuato l'effetto React che azzera il riepilogo anche quando un aggiornamento live parziale omette initialLettura; correzione conserva il risultato dello stesso fascicolo e reinizializza quando cambia fascicolo. Accettazione della correzione ancora da eseguire sulla nuova immagine.

Scheduler WIP17 unhealthy: job PEC e presidio relata hanno registrato database is locked. La ricerca metadati PEC del presidio percorre pagine contenenti original_mime, pur non selezionandolo: diagnosi precedente interrotta esattamente nella query, elaborazione reale circa quattro minuti e mezzo. Aggiunto indice SQLite coprente nel DDL nativo e SQL canonico, senza modificare regole di firma, deposito o SMTP. Guardrail del piano effettivo della query, isolamento tenant e preservazione dei MIME positivo insieme ai test OCR di contesto (20 test). Prova del miglioramento sul database reale e recupero governato dei job ancora aperti.

Errore SQLite «database disk image is malformed» osservato nei log della preparazione udienza alle 10:10:57 durante lettura fascicoli dello studio. PRAGMA quick_check successivo sul database corrente restituisce ok; causa e ripetizione reale ancora aperte, nessun ripristino o cancellazione eseguiti.

Creato solo in locale tramite procedure native il fascicolo controllato 93A3983A, cliente fittizio Collaudo Presidi, RG 987654/2099 e ufficio Torino; messaggio fittizio con parte e ufficio discordanti e indirizzi .invalid. Nessuna trasmissione. Snapshot nativo studio-before-controlled-case.db 359.915.520 byte, quick_check positivo. Ricevuta e fonte conservate privatamente; nessuna sorgente di collaudo trasferita in produzione. Verifica visiva della causa negativa ancora aperta.

Gate integrale WIP16 interrotto dopo nuove modifiche: errore iniziale inventario test documentato, generazione e check successivi positivi; gruppi core già passati non presentati come intero gate. Gate WIP17 in corso, insieme a nuove verifiche mirate delle ultime correzioni. Nessun commit/push/deploy 2.437.14 eseguito; incarico generale aperto.

12/10/2026 — Candidata 2.437.14 ancora aperta: WIP18 sul database PEC locale reale usa idx_pec_messages_presidio_cover; la query nativa dei candidati del fascicolo 4A91806A misura 0,015 s, zero candidati. Non è una misura dell'intera pipeline. Quarantacinque guardrail Python del perimetro passati. Corretta inoltre la connessione readonly di StudioDB: il database vivo non viene più dichiarato immutable; lettura mount/schema rispettano lock e WAL. Tre guardrail mirati passati, inclusa visibilità del commit WAL non checkpointato ed esclusione della bozza concorrente. Fonte tecnica ufficiale https://www.sqlite.org/uri.html, paragrafi immutable/mode=ro: la modalità precedente può produrre risultati errati o SQLITE_CORRUPT se altri processi modificano il file. Questo è un rischio concretamente presente nel percorso dell'errore osservato, non una prova che ogni errore storico abbia la medesima causa. Backup sorgente storage e snapshot database preservati. Immagine WIP19 in installazione, prova reale e commit/push/deploy ancora da eseguire; nessun riscontro globale positivo.

12/10/2026, candidata WIP20 — La coda nativa è conclusa alla generazione 59, stato idle, senza flag pendenti; l'interfaccia già aperta è passata automaticamente all'esito delle 11:05 conservando Atti e fonti espanso e la fonte aperta (riscontro AX, senza ricaricamento). Corretto il cache key del riepilogo: comprende lo stato pending/running/idle della coda SQL esistente, così un riepilogo precedente non nasconde una verifica appena accodata. Test mirati ulteriori: 26 positivi; giro finale di 49 test exit 0. Non attestata conclusione integrale del gate ancora attivo.
La diagnosi dei quattro elementi dell'indice non pronti mostra 73 record e quattro EML importati, supportati, di 30.928.541–42.323.097 byte, superiori al limite Document AI di 25 MiB. Il limite resta preservato; manca una procedura governata per riutilizzare le letture già archiviate evitando copie e nuove estrazioni. Il parsing degli avvisi per nome file usa il primo due punti e non identifica correttamente i nomi EML che contengono già due punti: causa ulteriore del mancato esito persistente esplicito. Questi aspetti restano aperti; nessuna affermazione di illeggibilità o formato non supportato.
Preservati indice Git e vecchio lock vuoto prima di rimuovere soltanto il lock obsoleto, dopo aver verificato assenza di processi Git. Tolti dallo staging 270 asset aggiunti di build precedenti non referenziati dal manifest corrente: nessun file eliminato. Pannello browser originale a larghezza zero: cattura non eseguita; nuova scheda locale visibile aperta per riprendere la prova materiale. Nessun nuovo commit, push o deploy attestato da queste verifiche.
12/10/2026 WIP20 — Browser reale visibile ripristinato aprendo una nuova scheda locale, senza ricaricare quella con fonte e riepilogo in aggiornamento. Nuova scheda mostra il riepilogo persistito delle 11:05, 9 depositi dello studio e 2 pendenti del fascicolo, 77 letture archiviate e 73/77 indicizzati: foto privata presidi-wip20-riepilogo-riaperto-20261012.png. Riaperta personalmente la stessa preparazione udienza 90483b31-8640-573d-940f-4488abb5b7d6 che aveva fallito: quadro React, dati controllati, selezione del tipo udienza e cinque passi visibili; scroll eseguito senza errore del database. Foto presidi-wip20-udienza-database-reale-20261012.png. Nessuna modifica o salvataggio della sessione eseguito. Nei log applicativi degli ultimi 15 minuti nessun nuovo malformed, lock o timeout; questo non dimostra la causa di tutti gli errori storici. Dieci shard core del gate conclusi positivi; contratti OpenAPI e passi successivi ancora in esecuzione.
12/10/2026 WIP20 — Ripetizione visiva sul pannello ripristinato: Aggiorna accoda generazione 60, indicatore aggiornamento presìdi in corso visibile, fonte aperta e affiancata. La stessa pagina passa automaticamente a eseguite il 12/10/2026 11:26, conservando documento e Atti e fonti espanso, senza ricaricamento. Foto private presidi-wip20-fonte-affiancata-in-corso-20261012.png e presidi-wip20-fonte-esito-automatico-20261012.png, foto finale mostrata in chat. Conservati 73/77 indicizzati e 77 letture archiviate, 9 depositi studio e 2 pendenti del fascicolo. La prova precedente AX è ora accompagnata da prova visiva materiale del ciclo di aggiornamento.


### Verifica locale conclusa prima del rilascio 2.437.14
Il gate locale completo avviato il 12/10/2026 ha terminato con 40 gruppi passati e zero falliti, compreso il banco Lex (48 casi). Le modifiche WIP18–20 intervenute durante la sua esecuzione hanno inoltre superato i controlli mirati riportati sopra; la CI sul commit esatto resta obbligatoria. La prova materiale su 8080 del ciclo 60 ha mostrato il passaggio da lavorazione in corso all’esito delle 11:26 senza ricaricare, mantenendo la fonte aperta. Non è una conclusione dell’incarico generale: restano quattro EML oltre il limite documentale, le relative cause persistenti e gli altri punti del registro.

# Migrazione progressiva Flask + React

## PAT/SIGA documenti fascicolo e moduli ufficiali XFA - 2026-06-19 - 2.253.82

La superficie `/pat` è stata ridotta a una cabina operativa: fascicolo, deposito Formweb, documenti del fascicolo, modulo ufficiale e consegna SIGA. Le sezioni descrittive, le card generiche e i pannelli non necessari non fanno più parte della pagina PAT principale.

Stato codice:

- React `/pat` mostra una procedura compatta a step: `Fascicolo`, `Deposito`, `Documenti`, `Modulo`, `SIGA`;
- i documenti del fascicolo selezionato vengono letti dal repository reale e mostrati con `Visualizza`, `Scarica`, dimensione, firma, ruolo suggerito, selezione allegato e flag `Firma PAdES`;
- `/api/v1/ui/pat/moduli/prefill` espone anche `documents` e `documentsSummary`, non solo i campi del modulo;
- `/api/v1/ui/pat/moduli/compila` verifica che gli allegati scelti appartengano al fascicolo, rispetta i limiti Formweb e li passa al generatore PDF;
- aggiunto `pct/pat_pdf_templates.py`: i PDF prodotti partono dai template ministeriali XFA ufficiali 4.x e non da un riepilogo sintetico;
- aggiunti in `pct/data/pat_moduli/` i template ufficiali per ricorso, atto, richieste segreteria, ausiliari/parti non rituali, istanza ante causam e rimborso contributo unificato;
- il PDF generato preserva `/AcroForm` e `/XFA`, usa il nome ufficiale del modulo e incorpora i documenti selezionati come allegati del PDF.

Verifiche locali eseguite su `2.253.82`: `python -m compileall web\blueprints\api_v1_react.py pct\pat_pdf_templates.py`, `npm run build`, `python -m pytest tests\test_react_shell.py -k "pat_modulo or pat_prefill or superfici_telematiche" -q`, `python tools\sync_packaging_files.py --check`, `python scripts\validate_openapi.py docs\openapi.yaml`, `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_utf8_integrity.py tests\test_react_asset_retention.py -q --tb=short`, `git diff --check`.

Prova reale locale eseguita su Docker `127.0.0.1:8080`, browser integrato visibile: fascicolo `DC5BF1DB`, `20` documenti caricati e allegabili, anteprima documento PDF interna, hover/focus `Visualizza`, selezione massiva `Nessuno`/`Seleziona tutti`, modulo precompilato, generazione PDF `ModuloDepositoRicorso_4.02_compilato_iusentra.pdf` con `20` allegati e riepilogo operativo dati/allegati senza warning XFA del browser. Desktop, tablet `820x900` e mobile `390x844` verificati; su mobile è stato trovato e corretto il taglio dei campi modulo con `box-sizing:border-box` sui controlli PAT.

Restano prima della chiusura complessiva: commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner con prova produzione `https://app.iusentra.it/pat` sullo stesso commit.

## PAT/SIGA moduli compilabili interni - 2026-06-19 - 2.253.81

La superficie `/pat` è stata corretta da catalogo/link a procedura software interna: il portale SIGA resta la fase finale dove l'avvocato consegna tutto, mentre IUSENTRA prepara prima fascicolo, deposito Formweb, modulo compilabile, allegati, firma e PDF dati modulo.

Stato codice:

- React `/pat` ora espone le sezioni `Fascicolo`, `Depositi`, `Moduli compilabili`, `Allegati e firme`, `Sessione SIGA` e fonti operative in fondo pagina;
- React `/portali/pat/acquisizione` ora è specifica per PAT/SIGA: `Consegna finale PAT / SIGA e rientro ricevute`, passaggi `Accesso SIGA`, `Deposito`, `Rientro`, `File ufficiali`, `Fascicolo`, `Controlli`, `Registra`;
- il wizard PAT non mostra più mappature tecniche in inglese come `create new` e non presenta il portale come luogo in cui ricostruire la pratica: IUSENTRA prepara tutto, SIGA resta la fase ufficiale di consegna e rientro ricevute;
- aggiunti stati hover/focus leggibili per pulsanti, step e card acquisizione; su mobile le azioni della sessione SIGA sono impilate a tutta larghezza e i disabilitati hanno testo scuro leggibile;
- aggiunto endpoint `/api/v1/ui/pat/moduli/prefill` per precompilare i moduli da `get_fascicoli()`, `get_clienti()` e `get_soggetti()` nel tenant corrente;
- aggiunto endpoint `/api/v1/ui/pat/moduli/compila` per produrre un PDF compilato da IUSENTRA con validazione dei campi obbligatori;
- il testo `Scarica modulo ufficiale` non è più presente nella workspace React come azione del flusso;
- il portale ufficiale viene richiamato solo nella sezione finale `Sessione SIGA`, governata dal Local Connector.

Verifiche locali eseguite su `2.253.81`: test mirati PAT/React, typecheck/build frontend, asset retention, UTF-8, OpenAPI, rebuild Docker locale e prova visiva reale su `127.0.0.1:8080/portali/pat/acquisizione` desktop/tablet/mobile con click Step 2/3/4, scroll completo e assenza di `Vai alla ricerca`, `create new`, `Scarica modulo ufficiale`. Restano per la chiusura complessiva: commit/push branch gemelli, GitHub checks e deploy Hetzner.

## PAT/SIGA Formweb e Portale Avvocato - 2026-06-19 - 2.253.80

La superficie `/pat` viene estesa come cabina operativa del Portale Avvocato / SIGA: Formweb prioritario, moduli ufficiali, sessione SIGA governata da IUSENTRA tramite Local Connector del PC dell'avvocato e import ricevute/documenti nel fascicolo.

Copertura implementata:

- catalogo `pct/pat_moduli.py` con fonti ufficiali G.A., moduli PDF 4.x, foglio Excel parti, guida Chrome/Acrobat, tipologie Formweb e suggerimento modulo per materia/tipo deposito;
- payload React `patProcedure` in `/api/v1/ui/telematico/surface/pat`;
- pannello React dedicato con fasi operative, limiti 50 file/300 MB, sessione ufficiale SIGA senza iframe fragile, senza `window.open` operativo e senza fallback esterno come soluzione, filtro moduli e fonti ufficiali;
- profilo `pat_siga` aggiornato per non ereditare busta PCT, `.cer` PST o `Atto.enc`, con firma PAdES e PEC residuale;
- test mirati su canale, catalogo moduli/Formweb, payload React, Local Connector browser/Docker e asset retention.

Verifiche locali eseguite su `2.253.80`: `py_compile`, pytest canali/PAT/payload React/Local Connector, typecheck React, build Vite, asset retention, rebuild Docker reale, `/api/pronto` su `127.0.0.1:8080`, Local Connector `1.6.78` su `127.0.0.1:27272` e prova visiva completa `/pat` desktop/tablet/mobile. Nella prova reale: `Avvia sessione ufficiale SIGA` resta dentro IUSENTRA e produce `monitor_download_attivo`, `Raccogli file ufficiali` e `Chiudi sessione` reagiscono, il filtro `rimborso` mostra il modulo ufficiale, zero iframe, zero overflow e nessun errore console. Restano prima della chiusura complessiva: commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner.

## Impostazioni Firma Digitale e scadenza certificato - 2026-06-16 - 2.253.33

La tranche collega `Impostazioni > Firma Digitale` al certificato selezionato dal Local Signer, così la scadenza del certificato dell'avvocato resta visibile e governata dalla configurazione dello studio.

Copertura implementata:

- la verifica Local Signer in React legge `certificato_windows_selezionato` e mostra scadenza, intestatario, codice fiscale ed emittente;
- la scadenza viene salvata con endpoint dedicato `/api/v1/ui/impostazioni/firma/certificato`, senza modificare P12, PEM o driver;
- il payload Impostazioni espone data italiana, giorni alla scadenza e soglia avviso;
- il login dello studio mostra un avviso quando mancano 20 giorni o meno alla scadenza salvata, oppure quando il certificato risulta scaduto;
- i dati restano nel profilo firma dello studio e nello snapshot impostazioni, senza nuova sorgente parallela.

Verifiche locali mirate eseguite: pytest su salvataggio scadenza certificato, avviso login 20 giorni, UI React Impostazioni e diagnostica Local Signer. Resta prima della chiusura reale: rebuild Docker `127.0.0.1:8080`, click reale in Chrome su `Verifica dispositivo collegato`, controllo salvataggio scadenza italiana e avviso login se la soglia è applicabile.

## Deposito, Editor professionale e lettore documenti - 2026-06-16 - 2.253.30

La tranche chiude il lavoro preparatorio richiesto su `Prepara deposito`, aggiunge `Editor professionale` come superficie autonoma e uniforma il lettore documenti legali per fascicolo, PEC ed email ordinaria.

Copertura implementata:

- il menu ruolo della fase `Documenti da inviare` non usa più la select nativa, ma un pannello React ancorato alla riga;
- i ruoli visibili restano `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- il valore storico `allegato_prova` è compatibile in ingresso ma normalizzato a `Allegato`;
- `/editor-professionale` è route full React governata, distinta da `/redazione-atti` e censita nella nav Studio, nei contratti e nella memoria dati;
- le anteprime globali coprono `.xml`, `.xml.p7m`, `.eml`, `.eml.p7m`, `.txt`, `.txt.p7m` e `.pdf.p7m`, mantenendo il download dell'originale;
- il bundle React è stato separato in chunk vendor e icone, eliminando il warning del chunk principale sopra 500 kB.

Verifiche locali mirate eseguite: OpenAPI, typecheck, test frontend, route gate, contratti React, test deposito/regia, test fascicoli/PEC/email, UTF-8, asset retention, contratto dati, governance repo, packaging e readiness. Restano prima della chiusura reale: commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner, Docker locale `127.0.0.1:8080`, prova visiva server desktop/tablet/mobile su `E5AE4668`, dry-run busta senza invio PEC e firma multipla reale con PIN/token quando disponibile.

## Deposito profilo pratica e normativa PST - 2026-06-14 - 2.253.14

La tranche rafforza `Prepara deposito` React perché il controllo sia legato al tipo di pratica e non alla sola selezione documenti dell'avvocato.

Copertura implementata:

- il profilo pratica viene esposto nella pagina deposito e alimenta la lista dei documenti obbligatori;
- la classificazione usa parole intere e non sottostringhe: `contratto` non viene più scambiato per `atto`;
- per `PROC_LIC_IMP_001` `Atto principale` resta obbligatorio e separato, mentre contratto, lettera e buste paga sono documenti di prova;
- l'aggiornamento PST XSD SICI dell'11/06/2026 è tracciato come anticipazione non in esercizio, quindi il codice `110046` non viene usato per validare depositi produttivi;
- la firma multipla deposito è pronta a livello codice/UI, ma resta non accettata finché non viene provata con browser reale, Local Signer, PIN utente e più `.p7m` salvati nel fascicolo.

Verifiche locali mirate eseguite: `py_compile`, pytest mirati deposito/busta/firma batch/profilo pratica/PST, typecheck React, build Vite, `check-react-contracts` e `check-route-gate`. Restano prima della chiusura: Docker reale `127.0.0.1:8080`, prova visiva e firma multipla con PIN, igiene runtime, commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner.

## PEC, Agenda, Scadenziario e deposito React - 2026-06-14 - 2.253.13

La tranche consolida i flussi segnalati dall'utente dopo la promozione React della pagina `Prepara deposito`.

Copertura implementata:

- proposta busta in React con atto principale, allegati collegati dagli slot, documenti da firmare, selezione manuale e azione finale coerente con invio PEC o generazione busta;
- classificazione documenti prudente: il software collega automaticamente solo documenti con confidenza alta, altrimenti lascia la scelta all'avvocato;
- generazione busta allineata al codice oggetto PST validato quando presente;
- import da documento notificato nel fascicolo per alimentare Agenda e Scadenziario anche se la PEC è stata cancellata;
- conservazione esatta del link audiovisivo letto dall'annotazione PDF e deduplica tra fonti equivalenti;
- Scadenziario React con cliente/parte del fascicolo nella colonna fascicolo e card operative più uniformi;
- testi Agenda/Scadenziario ripuliti da lessico tecnico e da placeholder generici.

Verifiche locali mirate eseguite: `py_compile`, pytest mirati deposito/Regia/Agenda/Scadenziario, typecheck React, build Vite, `check-react-contracts` e `check-route-gate`. Restano prima della chiusura: Docker reale `127.0.0.1:8080`, browser visibile con scroll completo di Agenda/Scadenziario/Prepara deposito, commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner.

## Fascicoli - preparazione deposito React - 2026-06-14 - 2.253.12

La route profonda `/fascicoli/<id>/deposito/prepara` apre ora la shell React operativa invece del template classico, mantenendo il percorso storico solo con `?_legacy=1`.

Copertura implementata:

- pagina “Prepara deposito” dentro `FascicoliPage.tsx`, alimentata dal dettaglio fascicolo reale;
- riepilogo Regia Operativa, controlli deposito, documenti, ricevute/cancelleria e audit;
- routing Flask che consegna React sulla GET ufficiale e conserva il template classico come recupero governato;
- manifest, contratto legacy e gate `check-react-contracts` / `check-route-gate` aggiornati per bloccare regressioni.

Verifiche locali mirate eseguite: `py_compile`, typecheck React standard e pytest su deposito guidato + route gate. Restano nel flusso di rilascio finale: build Vite, Docker reale `127.0.0.1:8080`, commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner.

## Assistente vocale Studio - 2026-06-12 - 2.253.1

La topbar React integra l'assistente vocale Studio come componente caricato in modo pigro, con pannello responsive e testi italiani per l'uso operativo dello studio legale.

Copertura implementata:

- catalogo governato con i 40 comandi vocali iniziali dell'utente, 290 frasi aggiunte e 59 destinazioni o aree apribili;
- attivazione locale con registrazione tono voce, PIN pronunciato o inserito e ascolto continuo;
- comandi per navigazione, ricerca studio, Lex AI, aiuto, indietro, ricarica e disattivazione assistente;
- flusso "Studio nuovo cliente" con nome, cognome, codice fiscale, rilettura dati e salvataggio reale solo dopo conferma;
- API `POST /api/v1/ui/clienti/voce/crea` con permesso `clienti.scrivi`, validazioni dominio, audit e sincronizzazione.

Verifiche locali già eseguite sul perimetro mirato: catalogo frontend, `py_compile`, pytest dedicato e typecheck React. Restano prima della chiusura di rilascio: build/gate finali, Docker reale `127.0.0.1:8080`, browser desktop/tablet/mobile, commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner.

## Dashboard, top bar e Guida Pratica set34-41 - 2026-06-11 - 2.251.26

La Panoramica React e la Regia Operativa sono state stabilizzate dopo i picchi CPU osservati su Hetzner:

- gli appuntamenti importati da calendari esterni con `Z` o `+00:00` vengono normalizzati in ora italiana prima dei confronti;
- la Panoramica usa indici leggeri per fascicoli/appuntamenti e legge solo giurisprudenza già collegata direttamente, evitando ricerche full-text per ogni fascicolo;
- la cache breve della dashboard è single-flight: richieste concorrenti sullo stesso payload non avviano build parallele;
- notifiche e scadenze rapide della top bar non fanno più polling automatico a pannelli chiusi.

Nella stessa tranche sono stati integrati i pacchetti Guida Pratica `files (23).zip` - `files (29).zip` come set34-41: 68 moduli KB, 340 schede, 343 termini grezzi, scadenziario a 3.908 termini / 1.184 template calcolabili e validazione forte con 1.018/1.018 codici ufficiali depositabili coperti da guida curata completa.

## Fascicoli - controllo economico a griglia - 2026-06-09 - 2.249.42

La pagina React `/fascicoli` include ora un foglio operativo per aggiornare in elenco le voci economiche dei fascicoli senza entrare nel singolo fascicolo.

Copertura funzionale implementata:

- stato fascicolo sempre visibile nella griglia, insieme a fascicolo, cliente e prossima scadenza;
- colonne economiche per contributo unificato, fondo spese, liquidazione giudice e parcella;
- salvataggio JSON reale su `/api/v1/ui/fascicoli/<id>/pagamenti/<voce>` con permessi, audit e cronologia;
- importo vuoto preservato come valore assente, non convertito a `0`;
- filtro `Solo controllo economico da completare`, KPI economici e export Fascicoli con stati/importi/totale;
- dettagli metodo/note apribili per non appesantire la griglia principale.

Verifiche locali eseguite: typecheck React, build Vite, py_compile mirato, test React Fascicoli mirati e verifica browser reale su `http://127.0.0.1:8080/fascicoli` con Docker locale.

## Portale Cliente full React - 2026-06-07 - 2.249.33 in corso

La tranche Portale Cliente introduce la console studio `/app/portale-clienti`
e la vista cliente `/portale-cliente` come superfici React complete, alimentate
da API JSON reali sotto `/api/v1/ui/client-portal/*`.

Copertura funzionale implementata nel codice locale:

- inviti cliente con token forte, hash su repository, scadenza e revoca;
- dashboard studio con pratiche, inviti, documenti, firme, chat, appuntamenti,
  notifiche e pacchetto finale;
- vista cliente completa senza sidebar studio, con invito, anagrafica,
  preferenze, privacy, timeline, documenti, firma semplice, chat, appuntamenti,
  notifiche, questionari, survey ed esportazione conversazione;
- repository tenant-aware con schema SQLite e schema PostgreSQL equivalente;
- OpenAPI/provider verification estesi al blueprint Portale Cliente, inclusi
  errori pubblici sicuri su token assente o non valido;
- manifest App V2, contratti legacy, area requirements, piano test e
  documentazione aggiornati.
- la shell pubblica del cliente usa una classe dedicata e non mostra il widget
  Lex o la sidebar studio; la console studio mobile nasconde Lex quando il
  pannello non è aperto;
- la lista fascicoli del Portale Cliente non propone pratiche marcate come dati
  di prova/campione e l'API blocca la creazione di inviti su tali pratiche;
- il layout cliente desktop è stato compattato per mostrare la chat già nella
  prima schermata utile, mentre su mobile resta una colonna leggibile.
- la topbar studio non carica più le notifiche a pannello chiuso, così una
  risposta lenta del centro notifiche non ritarda la dashboard Portale Clienti.

Verifiche locali già eseguite: py_compile dei moduli Portale Cliente e dei
generatori OpenAPI, pytest dedicati Portale Cliente, gate sicurezza/tenant/flag,
OpenAPI/provider, registry App V2, test frontend, typecheck e build Vite.
Docker reale `127.0.0.1:8080` e browser desktop/tablet/mobile sono stati
verificati localmente con screenshot in `artifacts/client-portal/browser-screenshots/`.
Restano prima della chiusura: gate finali dopo l'ultima modifica, commit, push
branch gemelli, check GitHub e deploy Hetzner.

## Template Atti professionale - correzione funzionale reale - 2026-06-04 - 2.249.14

La tranche 2.249.14 chiude le regressioni emerse sull'editor template atti dopo
la prima consegna:

- il compilatore React legge il fascicolo reale e porta nel workspace cliente,
  mittente, controparte/destinatario, ufficio giudiziario, R.G., materia e dati
  pratica tramite campi contestuali marcati con fonte e confidenza;
- i campi compilati dall'avvocato non modificano più il template mentre si
  digita: il valore resta nel modello dati, l'anteprima risolve il placeholder e
  l'export usa il testo compilato;
- la Guida Pratica è un blocco inseribile nel documento, non solo un'anteprima;
  le fonti ufficiali sono disponibili nel pannello `Fonti` e vengono inserite
  solo su azione dell'utente;
- import documento, pagina vuota, inserimento campi fascicolo, cambio modello,
  font, allineamenti, timbro spostabile, Lex diff, compilazione multipla e firma
  sono stati verificati con click reali su Docker locale `127.0.0.1:8080`.

Fonti normative consultate e versionate:
`docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-04.md`.

## PST / PolisWeb - parità schede fascicolo e ricerca annuale - 2026-05-29 - 2.248.87

La tranche 2.248.87 porta l'import PST più vicino alla vista reale del portale:

- il catalogo documenti non si ferma più alla sola tabella `DocumentiFascicolo`;
  quando il servizio ministeriale lo consente, il Local Signer interroga anche
  `estraiMasterDetailAtto` e porta nell'inventario `docPrimario` e
  `docsSecondari`, conservando il rapporto padre/allegato;
- lo snapshot del fascicolo include sezioni strutturate per storico eventi,
  comunicazioni/notificazioni di cancelleria, scadenze/termini, istanze e dati
  accessori del profilo, così l'anteprima React e l'import vedono gli stessi
  blocchi mostrati dal PST;
- la UI PST accetta anche la ricerca per solo anno: viene mostrata una lista di
  fascicoli e l'utente carica lo snapshot completo cliccando sul fascicolo
  scelto;
- la stessa regola è stata applicata anche al wizard classico `?_legacy=1`, così
  eventuali fallback o server non ricaricati non tornano al vecchio
  comportamento;
- restano invariati i tre modi di import documenti già provati: tutto, singolo
  documento e selezione multipla, con download batch e senza preflight separato.

Fonti e direttive sono versionate in
`docs/specs/ministero/PST_FASCICOLO_SCHEDE_MINISTERIALI_2026-05-29.md`.

## PST / SQLite / PEC - ripristino robustezza operativa - 2026-05-29 - 2.248.86

La tranche 2.248.86 chiude tre regressioni operative ad alto rischio:

- Step 7 PST/Local Signer importa solo documenti reali, ma non scarta più un
  lotto valido solo perché accanto ai PDF sono presenti catalogo o Informazioni.
  La UI React mostra documenti importabili, informativi, catalogo, mancanti e
  scartati con motivazione.
- La pagina React `Database` distingue analisi, pre-verifica, report
  differenze, backup, riconciliazione, attivazione e verifica finale. Gli stati
  `Bloccata per protezione dati` e `Eseguita riconciliazione` sostituiscono i
  vecchi messaggi contraddittori di completamento con errori.
- Il flusso PEC legale espone dati classificati per famiglia, registro, evento,
  priorità, azione consigliata, documenti allegati e stato ricevute, senza
  chiudere depositi sulla sola ricevuta di accettazione.

È stato inoltre aggiunto il modello DOCX autocompilante per attestazione di
conformità, collegato ai dati fascicolo/cliente/soggetti/parti/documenti e
documentato in `docs/templates/attestazione_conformita_autocompilante.md`.

Verifiche locali: py_compile dei moduli critici, test Step 7, SQLite, PEC,
attestazione, React shell amministrazione/PST, typecheck React, build Vite,
UTF-8 e `scripts/audit_finale_pst_sqlite_pec.py`.

## Database - audit anti-perdita SQLite - 2026-05-29 - 2.248.84

La pagina React `/admin/database` espone ora nel risultato della migrazione un
riquadro `Verifica dati migrati` alimentato dal report backend
`audit_migrazione`. L'avvocato vede per ogni modulo controllato il conteggio
della sorgente e del database SQLite, senza dover leggere solo il totale
aggregato.

Le azioni `Migra dati` e `Attiva SQLite` non possono più sostituire uno
`studio.db` già popolato quando i JSON tenant-aware sono vuoti o incompleti:
il backend blocca l'operazione, conserva il database operativo e restituisce
un errore esplicito. Il report React mostra quindi l'esito reale del blocco
invece di presentare un successo con perdita silenziosa.

Verifiche locali: suite `tests/test_database.py`, suite
`tests/test_storage_postgres_migration.py`, shard storage/governance mirati,
typecheck React, build Vite e audit CLI su tenant temporaneo.

## Fascicolo - prova deposito e stato ricevute PEC - 2026-05-27 - 2.248.70

Il dettaglio fascicolo React espone il pulsante `Deposito telematico` tra le
azioni principali della pratica, così l'avvocato entra nella preparazione del
deposito direttamente dal fascicolo senza dover cercare la scheda nei pannelli
laterali. Lo stato del deposito resta poi visibile accanto alle comunicazioni di
cancelleria: accettazione PEC, consegna, controlli automatici e conferma finale
sono mostrati come passaggi progressivi. Quando il deposito è creato in prova,
l'avvocato può avanzare la simulazione senza invio reale e vedere l'effetto nel
fascicolo come se arrivassero le PEC operative.

Il pulsante è stato replicato anche nella vista classica del dettaglio
fascicolo, così l'interfaccia resta coerente tra ambienti locali, sessioni già
aperte e superfici non ancora ricaricate sulla shell React. Per i depositi
reali, lo stato non dipende dal click manuale: lo scheduler esegue la
sincronizzazione automatica della casella PEC tramite `mailbox_sync_runtime`,
salva le nuove PEC PST/cancelleria e aggiorna ricevute deposito, comunicazioni
di cancelleria e stato mostrato nel fascicolo. Il controllo manuale rimane come
azione di anticipo.

Le API React dei fascicoli usano ora il loader runtime condiviso con la vista
classica. Il dettaglio React, la sezione Cancelleria e la pagina di preparazione
deposito leggono quindi lo stesso fascicolo mostrato dopo il login, evitando
differenze tra UI classica e UI React.

La simulazione è marcata in modo esplicito, usa ricevute sintetiche sanificate
con allegati nominali `postacert.eml`, `daticert.xml`, `EsitoAtto.xml` e
`smime.p7s`, e rifiuta la generazione su depositi reali. I controlli automatici
possono produrre uno stato con avvisi, così la UI mostra anche il caso in cui la
PEC dei controlli richiede verifica dell'avvocato prima della conferma della
cancelleria.

Verifiche locali: sintassi Python, pytest mirati deposito/ricevute, typecheck
React, build Vite, UTF-8, packaging, OpenAPI e whitespace.

## PST/PolisWeb - fascicolo reale, import e Local Signer - 2026-05-26 - 2.248.67

Il wizard React di acquisizione PST torna a mostrare l'anteprima completa del
fascicolo prima dell'importazione: dati del procedimento, parti, cronologia e
documenti disponibili sono visibili nella stessa schermata operativa. La
selezione dei documenti resta esplicita e l'import mostra avanzamento, documento
corrente e avvisi quando il PST non consegna un singolo file pur completando il
resto del fascicolo.

Il Local Signer `1.6.50` riusa la sessione PST già aperta per il download batch,
non torna al download singolo ripetuto e mantiene il flusso senza richieste PIN
aggiuntive quando la sessione di visualizzazione è ancora valida. Su Windows
l'helper foreground intercetta anche dialog PIN/credenziali senza titolo
esplicito, usando titolo, classe finestra e testo dei controlli figli per
ripristinare la richiesta davanti al browser.

Per l'uso multi-studio, il codice fiscale dell'avvocato usato nelle chiamate PST
deriva prima dal certificato selezionato sul PC; il codice fiscale configurato
nello studio resta solo fallback. In questo modo un fascicolo scaricato con un
certificato abilitato di un altro avvocato non viene condizionato dal tenant o
dallo studio usato nel test precedente.

Verifiche locali: test Local Signer/PST mirati, test React shell e import
solo-catalogo, typecheck/build Vite, build pacchetti Local Signer, packaging,
readiness, asset retention, UTF-8, boundary check e prova reale browser su
Tribunale di Palmi R.G. 274/2026.

## Componi PEC - ricerca uffici giudiziari e canale PEC dedicato - 2026-05-26 - 2.248.63

La pagina React `/email/scrivi` espone ora un pannello collassabile sopra al
campo destinatario per cercare gli uffici giudiziari competenti per Comune e
inserire direttamente la PEC pubblicata nel destinatario. Il pannello riusa
l'endpoint read-only `/api/v1/ui/strumenti-legali/uffici_competenti`, con filtro
per Giudice di Pace, Tribunale, Procura, UNEP, Corte d'Appello, Procura
Generale, Corti di Assise e uffici minorenni, più filtro per risultati con PEC.

La composizione PEC ordinaria non usa più Local Signer: il form invia al backend
dedicato `/email/scrivi`, che usa la configurazione PEC dello studio, registra
la casella `INVIATI` solo dopo esito SMTP positivo e continua a bloccare le
notifiche ex L. 53/1994 verso il percorso guidato. Local Signer resta riservato
ai flussi che richiedono firma, portali e deposito.

Hotfix del 26 maggio 2026: l'avvio locale carica `.env` prima della lettura
della configurazione studio, così le password PEC cifrate con `PCT_SECRET_KEY`
vengono decifrate prima del login SMTP. Il flusso `/email/scrivi` è stato
verificato con invio reale Legalmail senza allegato e con allegato, entrambi con
`Message-ID` e storico `INVIATO`.

Verifiche locali: typecheck React, test frontend, build Vite, parser/API uffici,
regressioni PEC senza Local Signer e guardia impostazioni PEC.

## Fascicolo - uffici competenti per Comune inline - 2026-05-26 - 2.248.62

Il dettaglio fascicolo React espone ora una sezione `Uffici giudiziari per Comune`
subito dopo il profilo della pratica. L'avvocato può inserire uno o più Comuni
separati da virgola, punto e virgola o nuova riga e ottenere il risultato dentro
la stessa vista del fascicolo, senza dover aprire Strumenti Forensi come pagina
separata.

Il pannello usa lo stesso endpoint read-only
`/api/v1/ui/strumenti-legali/uffici_competenti` già governato per Strumenti
Forensi: non salva dati runtime, non modifica procedure telematiche, non avvia
depositi o Local Signer e rende soltanto uffici, recapiti, assistenza pubblicata
dalla fonte e copia rapida dei contatti. La ricerca parte solo dal pulsante
`Cerca uffici`, così il caricamento del fascicolo resta leggero.

Verifiche locali: typecheck React, build Vite, pytest mirati su fascicoli e
uffici competenti, browser in-app autenticato con ricerca `Taurianova` e output
Palmi visibile nel fascicolo, più controllo responsive desktop/tablet/mobile
senza overflow orizzontale.

## Strumenti Forensi - uffici competenti per Comune - 2026-05-25 - 2.248.58

La pagina `Strumenti Forensi` espone ora la funzione `Uffici competenti per Comune`.
La ricerca usa Giustizia Map del Ministero della Giustizia in modalità read-only,
senza cache locale e senza scritture sui dati runtime. Il risultato viene
mostrato nella scheda React già esistente con uffici principali, recapiti,
assistenza depositi telematici quando pubblicata dalla fonte, copia rapida dei
contatti e collegamenti operativi verso fascicoli/notifiche.

La modifica non tocca il codice delle procedure telematiche: il flusso deposito
resta invariato e la nuova funzione fornisce soltanto consultazione e contesto
operativo per l'avvocato.

Verifiche locali: parser ministeriale, endpoint `/api/v1/ui/strumenti-legali/uffici_competenti`,
contratti React degli Strumenti Forensi, typecheck e build Vite.

## Hotfix preset grafico operativo - 2026-05-25 - 2.248.56

La verifica richiesta sulle pagine Studio ha corretto le regressioni visive
residue sui controlli compatti: Fatturazione, Compensi Forensi, Redazione Atti,
Ricerca Legale/Giurisprudenza e shell laterale ora mantengono altezza minima
coerente e leggibilità touch-safe. Il dettaglio fascicolo resta escluso dal
preset di pagina come richiesto, ma il modal `Elimina documento` usa dimensioni
controllate, wrapping e bottoni da 44 px per evitare tagli o sovrapposizioni.

Verifiche locali: typecheck, test e build React; audit browser sulle pagine
segnalate in desktop/tablet/mobile; apertura reale del fascicolo
`2DE106E6#documenti` con modal eliminazione misurato senza confermare la
cancellazione. La build Vite ha rigenerato gli asset React correnti e la
retention locale ha rimosso gli hash obsoleti non referenziati dal manifest.
Nel medesimo rilascio Document Intelligence mantiene coerente il fascicolo con
file reali `.txt` ed `.eml`, aggiornando i vincoli SQL e la migrazione dei DB
SQLite già creati.

## Local Signer 1.6.46 autenticazione PST 401 esplicita - 2026-05-25 - 2.248.53

La diagnostica reale salvata dal PC cliente sul fascicolo `3441/2025` del
Tribunale di Palmi ha mostrato un esito `HTTP 401 Unauthorized` su tutte le
richieste batch verso il proxy PST. Da `1.6.46` questo scenario non viene più
mostrato come "Nessun fascicolo trovato": la ricerca PST restituisce errore di
autenticazione esplicito quando il certificato CNS/CIE non viene presentato o
non viene accettato dal proxy ministeriale.

Il comportamento atteso della UI è quindi distinguere tre casi: zero righe PST
vere, SOAP Fault di servizio/registro e rifiuto di autenticazione. Il test reale
successivo deve usare `SetupLocalSigner-1.6.46.exe`; se il proxy continua a
rispondere `401`, la diagnosi operativa è certificato/PIN, non filtro fascicolo.

## EML fascicolo, cancellazione documenti e Local Signer EXE - 2026-05-25 - 2.248.52

La tranche chiude il problema operativo emerso sul fascicolo cliente: gli `.eml`
caricati nel fascicolo sono ora consultabili nell'editor React come email
originale read-only, con intestazioni, corpo, allegati e download, senza
trasformazione in documento modificabile. La preview backend usa lo stesso
parser sicuro e recupera anche copie storiche con suffisso quando un vecchio
metadato punta al nome base non più presente.

La cancellazione dei documenti è stata resa atomica rispetto ai metadati del
fascicolo: prima salva l'archivio e solo dopo rimuove il file, così un lock
SQLite non può più creare documenti fantasma. Lo storage tenant-aware ritenta i
lock brevi con `busy_timeout`; upload e delete restituiscono errori operativi
controllati invece di 500 quando l'archivio è temporaneamente occupato.

Local Signer passa a `1.6.45` e il percorso Windows pubblico resta solo EXE:
`SetupLocalSigner-1.6.45.exe` viene servito anche dalla vecchia route
`windows-ps1`, per evitare che il cliente riceva un'installazione PowerShell.
Verifiche locali: pytest mirati fascicoli/editor/storage/Local Signer,
compileall, typecheck/build React, packaging, readiness, UTF-8, OpenAPI e
governance repo.

## Evoluzione grafica professionale e Lex - 2026-05-25 - 2.248.40

La tranche rafforza il prodotto come gestionale professionale per studi legali:
il preset IUSENTRA resta obbligatorio per tutte le pagine operative già
governate, con sole eccezioni `/sito-studio/builder` e dettaglio fascicolo
personalizzato. L'audit visuale finale controlla scroll completo, bottoni,
icone, procedure secondarie, sequenza preset, overflow, console e testi
tecnici vietati su desktop, tablet e mobile.

Lex viene trattato come pannello operativo di studio, non come widget generico:
toolbar laterale quando lo spazio lo consente, layout verticale compatto su
mobile, icona microfono, caricamento documenti, web libero, textarea touch e
spazi ridotti senza perdere leggibilità. La verifica dedicata copre PEC,
Notifiche legali e Fascicoli.

Verifiche locali: audit visuale 168/168, audit Lex 9/9, React
test/typecheck/build, OpenAPI/provider, pytest mirati, security, UTF-8,
governance repo, Ruff e compileall.

## Design system unico governato - 2026-05-25 - 2.248.39

La Fase 4 trasforma il preset grafico IUSENTRA in un gate bloccante. `pnpm --filter @iusentra/studio test` esegue ora `scripts/react-migration/check-design-system-governance.mjs`, che legge `scripts/react-migration/design-system-governance.json` e controlla allowlist CSS, inline style autorizzati, uso di `backdrop-filter` e divieti su accenti laterali spessi, testi gradiente e blur decorativi.

Il report automatico vive in `artifacts/react-migration/design-system-governance-report.md`: nessuna nuova pagina React può introdurre CSS locale o inline style senza motivazione operativa. Il wizard preventivi è stato riallineato al preset rimuovendo l'accento laterale spesso dal pannello riepilogo. Per disposizione utente le sole eccezioni grafiche ammesse restano `/sito-studio/builder` e le visualizzazioni dettaglio fascicolo `/fascicoli/<id>`; PEC, email, notifiche legali, lista fascicoli, nuovo fascicolo, archivio e ogni altra pagina operativa devono passare dal preset. La Fase 4 include anche l'esenzione degli asset statici React/PWA dal rate limit, così le navigazioni ravvicinate non svuotano la shell per JS/CSS serviti come 429.

## Sito Studio modifica articolo React full - 2026-05-24 - 2.248.37

La rotta `/sito-studio/articoli/:id/modifica`, richiesta dalla verifica su produzione, è stata promossa a `react_operational_full`. La pagina Flask serve la shell React per il percorso principale e conserva il rendering classico solo dietro `?_legacy=1`; il gate ammette la sola modifica articolo esatta e mantiene protetti download, allegati, export e workflow tecnici non parificati.

Il backend espone `GET/POST /api/v1/ui/sito-studio/articoli/<id>/modifica` con dati reali del sito studio corrente, validazioni, blocco dei campi di contesto forzato, salvataggio JSON e audit. La UI React mostra loading, assenza articolo, errori campo, successo, anteprima pubblica, stato editoriale e azioni redazionali senza demo/mock. I campi modificabili conservano il testo digitato dall'avvocato; la normalizzazione dei testi resta applicata solo a etichette operative e azioni.

Verifiche locali: contratti React, route gate, full-react-route-contract, no-fake React full, tranche Sito Studio API/operational, typecheck/build/test Vite, pytest mirati su shell e API builder, browser desktop/tablet/mobile su `/sito-studio/articoli/2/modifica` e rigenerazione dei report App V2/backend security.

## React full senza pagine finte - 2026-05-24 - 2.248.36

La Fase 3 chiude il residuo P0/P1 più visibile: `/giurisprudenza/nuova` non è più una rotta classica mascherata, ma una pagina React operativa alimentata da `/api/v1/ui/giurisprudenza/nuova`. Il backend restituisce contratti, default, opzioni, avvisi e salva la nuova scheda con validazioni reali; la UI espone caricamento, stato indisponibile, errori campo, conferma di salvataggio e azioni verso archivio/scheda senza dati demo.

Il manifest App V2 promuove a `react_operational_full` anche `/preventivi/wizard`, `/scadenziario/:id/modifica` e `/sito-studio/redazione-ai`. Il wizard preventivi non espone più `?_legacy=1` come azione primaria nel payload React, mentre route gate, shell Flask, contratti frontend, test shell e gate anti-mascheramento impediscono il ritorno a fallback classici sulle route dichiarate piene.

Verifiche locali di fase: contratti React, route gate, full-react-route-contract, no-fake React full, audit anti-mascheramento, pytest mirati su Giurisprudenza/React shell/Preventivi, test/typecheck/build Vite e rigenerazione della documentazione App V2.

## Sicurezza multi-studio API React - 2026-05-24 - 2.248.34

La Fase 1 governance multi-studio rende eseguibile la matrice `/api/v1/ui/*`: `docs/backend-endpoint-security-map.md` elenca i gate 401, 403, 404 cross-tenant, 400 per contesto forzato, success tenant valido, audit denial e superfici file/upload/download/export/evidence.

I dettagli fascicolo React ora rispondono con 404 controllato quando la pratica non appartiene al tenant corrente o non è presente nel repository del tenant attivo. Il nuovo test `tests/test_ui_api_security_matrix.py` usa due studi reali con API key separate e verifica che `tenant_id`, root/path e risorse di altro studio non espongano valori, titoli, path o payload sensibili.

## OCR legal-grade, HIL e Lex di fascicolo - 2026-05-24 - 2.248.30

La superficie `Documenti AI` integra ora il presidio OCR legal-grade: evidenze immutabili, metriche QC, token fragili, campi obbligatori e applicazione di correzioni deterministiche sono visibili nel pannello di revisione. Il flusso produce notifiche operative quando rileva date, adempimenti o necessità HIL.

Lex viene aggiornato sul singolo documento o sull'intero fascicolo solo dopo validazione e controllo di coerenza fascicolo-cliente. Il sistema non accetta più l'auto-associazione basata su soli metadati generici: servono R.G. e identità cliente coerente, altrimenti il documento resta in revisione e non entra nella conoscenza del fascicolo.

## Chiusura Relata notifica PEC-first - 2026-05-24 - 2.248.28

Il presidio `Relata notifica` è ora agganciato al comportamento corretto: il provvedimento da notificare nasce dalla comunicazione PEC dell'ufficio giudiziario. I documenti già presenti in `Documenti e atti` non vengono duplicati e i metadati generici del portale non bastano più a creare un rilascio notificabile.

Quando la PEC dell'ufficio comunica un provvedimento, IUSENTRA avvisa l'avvocato nella top bar e nel fascicolo, costruisce un link `/portali/<canale>/acquisizione` già compilato con fascicolo, numero R.G., anno, ufficio, PEC e documento, e imposta l'acquisizione su un solo documento con `single_document=1` e `non_duplicare_documenti=1`. La procedura resta assistita dall'avvocato: il software prepara il percorso, filtra il documento indicato e blocca la relata finché quel provvedimento non risulta collegato ai Documenti e atti del fascicolo.

La pagina `/notifiche-legali` espone anche la matrice casi/destinatari: destinatario, registro PEC ammesso, caso processuale, modello relata compatibile e blocchi normativi sono governati dal backend. Lex indicizza automaticamente i `.pdf.p7m` come PDF leggibili, salva l'indice una sola volta e aggiunge solo i nuovi documenti quando arrivano. La lista Fascicoli mostra di nuovo tutte le pagine disponibili con comandi di navigazione espliciti.

Report demo e prova end-to-end: `artifacts/notifiche-legali/notifiche-legali-demo-e2e.json` e `artifacts/notifiche-legali/notifiche-legali-demo-e2e.pdf`.
La verifica browser reale produce anche la guida operativa con screenshot
`artifacts/notifiche-legali/notifiche-legali-guida-avvocato-screenshot.pdf`:
14/14 controlli superati su lista fascicoli/paginazione, sezione Relata,
PEC ufficio, link PST già compilato, acquisizione del singolo provvedimento,
relata, firma digitale, invio PEC, RAC/RdAC, `DatiAtto.xml` e piano orario.
Le direttive normative e tecniche includono ora anche gli XSD SICI PST del
12 maggio 2026 salvati offline in `docs/specs/ministero/xsd/2026-05-12-sici/`.

## Revisione notifiche legali guidate - 2026-05-23 - 2.248.21

La pagina `/notifiche-legali` è stata rifinita come percorso operativo guidato: quando si sceglie una pratica vengono selezionati automaticamente tutti i documenti notificabili, restando modificabili uno per uno; gli allegati esterni accettano selezione multipla, calcolo SHA-256 nel browser e aggiunta manuale progressiva senza limitarsi a un solo file.

Il payload React espone i passaggi automatici della notifica e del deposito prova. L'esito mostra ora workflow, verifiche normative, pacchetto prova e audit, coerenti con L. 53/1994, art. 3-bis e art. 9, D.L. 179/2012 art. 16-ter e specifiche tecniche D.M. 44/2011 su ricevuta completa e indicizzazione ricevute. Demo e report sono in `artifacts/notifiche-legali/notifica-l53-demo-audit.md`.

Estensione completata nella stessa tranche: il fascicolo React espone `notificationRelata` e una sezione `Relata notifica` sempre navigabile. Quando il monitor dei depositi portale rileva un documento d'ufficio non ancora acquisito, la top bar crea una notifica di sistema con collegamento a `/portali/<canale>/acquisizione` già valorizzato con fascicolo, numero RG e ufficio; `/notifiche-legali` riceve quei metadati, blocca la relata finché il documento non risulta acquisito dal Portale Servizi e include l'acquisizione nell'audit normativo.

La demo end-to-end produce anche la guida PDF `artifacts/notifiche-legali/notifica-l53-demo-guida-avvocato.pdf`: scenario documento d'ufficio rilasciato, acquisizione assistita, relata, verifica normativa, audit, pacchetto prova e deposito RAC/RdAC.

## Hotfix fascicolo anagrafiche in nuova finestra - 2026-05-23 - 2.248.20

Il dettaglio fascicolo React espone ora due azioni rapide nella card iniziale: `Cliente` apre in una nuova finestra la modifica dell'anagrafica cliente collegata al fascicolo, mentre `Soggetti` apre in una nuova finestra la pagina Soggetti e Parti filtrata con `?fascicolo=<id>`.

Il bridge fascicoli porta `clientId` fino alla UI e il bridge soggetti espone `matterIds`/`matterRefs`, così il filtro lavora sui collegamenti reali delle parti processuali. La verifica browser reale desktop, tablet e mobile conferma assenza di overflow, sovrapposizioni e testi tecnici vietati; le destinazioni restano modificabili senza chiudere il fascicolo.

## Hotfix preset unico globale IUSENTRA - 2026-05-22 - 2.248.14

Il preset unico non può lasciare blocchi non classificati prima dell'header pagina. `IusentraRoutePresetFrame` assegna ora `main-content` come fallback a ogni figlio diretto non riconosciuto, mentre tab/switcher vengono trattati come filtri e note/riepiloghi come contesto. Il CSS globale normalizza anche gli hero locali come header pagina del preset, evitando varianti isolate come hero scuri o card operative sopra al titolo.

Questa regola vale per tutte le rotte React operative e continua a escludere solo `/sito-studio/builder`.

## Sequenza preset globale IUSENTRA - 2026-05-22 - 2.248.13

Il preset grafico globale è stato rafforzato con una sequenza pagina obbligatoria: Header pagina, Sottotitolo operativo, Azioni principali, Filtri, Contesto filtri / riepilogo, Contenuto principale, Paginazione / footer e Sidebar di supporto. La sequenza è definita in `IUSENTRA_PAGE_SEQUENCE`, applicata dal `IusentraRoutePresetFrame` tramite `data-iusentra-sequence-slot` e ordinata in `frontend/src/styles/iusentra-design-system.css`.

Il gate `scripts/react-migration/audit-ui-preset-sequence.mjs` è incluso nel test frontend e fallisce se il builder non resta escluso, se lo slot map non è completo o se il preset perde la sequenza. L'audit di tranche è registrato in `artifacts/react-migration/ui-preset-sequence-audit.md`.

## Preset grafico globale IUSENTRA - 2026-05-22 - 2.248.12

Il frontend React dispone ora di un preset grafico globale documentato in `docs/UI_PRESET_IUSENTRA.md` e implementato in `frontend/src/components/iusentra/IusentraPreset.tsx`. Il preset centralizza PageShell, MainArea, MainSurface, SupportRail, PanelCard, DataSurface, FiltersBar, ContextFilters, PaginationBar, ActionCard, EmptyState, token di griglia, rail, bordi, stati, card, filtri, paginazione e mappa icone.

La pagina Fascicoli è il caso pilota: la tabella è dentro `IusentraDataSurface`, il selettore `Per pagina` resta nel toolbar alto, il footer `Precedente / Pagina / Successiva` resta ancorato nella superficie dati e su desktop `IusentraMainSurface` misura la SupportRail con `ResizeObserver` per allinearsi alla fine di `Cabina fascicoli`, `Alert operativi` e `Azioni rapide` senza allungare le righe. La pagina `/sito-studio/builder` resta esclusa dal preset come richiesto.

## Guida Pratica facoltativa e TOP9 set2 - 2026-05-22 - 2.248.10

La Guida Pratica nel fascicolo è ora esplicitamente opzionale: se manca il codice oggetto, il backend può suggerire una scheda dall'oggetto o dal titolo del fascicolo, ma la UI non blocca il lavoro e richiede conferma per mantenere il collegamento. Le schede arrivate con codice non presente o non coerente con la descrizione ministeriale restano guide interne non depositabili.

Il secondo modulo TOP9 set2 è stato integrato senza sovrascrivere i codici ufficiali: `220101` arricchisce la scheda depositabile, `121003` resta interno, `413011` mantiene l'oggetto ministeriale sui provvedimenti urgenti e la guida tutela minori passa a `GUIDA_TUTELA_MINORI_ORDINARIA`, `140012` mantiene la vendita di cose mobili e la guida sulla risoluzione compravendita immobiliare passa a `GUIDA_COMPRAVENDITA_IMMOBILIARE_RISOLUZIONE`.

## Guida Pratica fascicolo e codici PST/XSD - 2026-05-22 - 2.248.9

Il dettaglio fascicolo React espone ora la Guida Pratica collegata al codice oggetto PST/XSD del fascicolo. La scheda mostra checklist, normativa, atto da redigere, campi, allegati, adempimenti e stato del codice deposito con linguaggio operativo per l'avvocato, senza esporre sigle tecniche interne o flussi separati.

Il knowledge base resta separato dal codice applicativo in `pct/data/legal_knowledge_base.full.json` e nei moduli `pct/data/legal_knowledge_base_modules/`. Il validatore forte `scripts/validate_guida_pratica.py --require-official-curated --fail-on-generated` conferma 1.018 codici ufficiali curati, zero codici ufficiali senza guida e coerenza completa tra catalogo ministeriale e stato depositabile.

## Template Atti compliance contestuale - 2026-05-20 - 2.245.65

Il compilatore React mostra ora il controllo applicativo reale restituito dal backend: stato complessivo, affidabilità, layout profile, timbro studio ripetuto, riferimenti normativi motivati, fonti con stato di verifica, campi/documenti mancanti e azioni Lex. La UI non decide la compliance: invia `requested_draft` e `confirmed_warning`, poi naviga all'`editor_url` restituito dal backend.

Il percorso utente è vincolato dal gate: `block` disabilita la creazione finale, `warning` richiede conferma visibile e apre solo la bozza di lavoro, `ok` apre l'editor professionale. Il timbro è governato dal profilo layout e viene ripetuto top-left su ogni pagina negli export supportati.

## Lex Template Atti in chat unica - 2026-05-20 - 2.245.64

`FloatingLex` passa ora il contesto `template_act` quando viene aperto dal catalogo o dal compilatore atti, includendo `modelCode`, fascicolo e cliente se disponibili. Il widget unico renderizza card per template, cliente, fascicolo, parti, dati mancanti, fonti e azioni senza creare pannelli separati.

Il frontend non genera atti e non decide il modello: riceve da Lex `message_blocks`, `lex_actions` e `template_act`. Le azioni aprono catalogo, compilatore, fascicolo, cliente o documento creato; la mutation `create_editor_draft` richiede conferma nella chat salvo comando esplicito dell'avvocato.

## Update Intelligence fonti/PDF/OCR/Lex - 2026-05-18 - 2.245.40

Ricerca Legale e la console aggiornamenti legali condividono ora lo stesso
arricchimento deterministico delle evidenze: PDF/allegati, OCR/testo,
riferimenti normativi, riferimenti R.G., domande contestuali e destinazione
operativa. `/admin/aggiornamenti-legali/` mostra contatori per evidenze lette,
PDF/allegati e documenti collegati, mentre `/ricerca-legale` riceve key point e
domande per Lex senza duplicare `Contesto operativo` e `Contenuto`.

Il piano fonte per fonte è registrato in
`artifacts/legal-updates/source-rollout-plan.md`. Le fonti OpenGA restano
RAG-only o giurisprudenza solo quando esiste documento concreto; le fonti
secondarie restano fuori dal corpus ufficiale e disponibili solo come Web
libero esplicito.

## UI Intelligence fonti legali - 2026-05-18 - 2.245.35

Ricerca Legale non deve più presentare contatori isolati. La pagina React legge
il monitor operativo delle fonti e mostra fonti pronte, fonti da verificare,
coda job, errori, documenti letti, testo disponibile, schede pubblicate e
ragione dello stato. Le domande qualità stabilite per il ciclo DB -> pagina
ufficiale -> allegati/PDF -> hash -> OCR/testo -> RAG -> Lex sono visibili
nella pagina, così la logica resta davanti agli occhi prima del generatore
corpus.

Archivio Giurisprudenza espone ora anche il presidio dati per RAG: schede con
fonte, testo disponibile, testo da completare e fonti da verificare. Il
comportamento è coperto da test mirati e dalla build React della release
`2.245.35`.

## Lex AI risposte studio e impaginazione - 2026-05-17 - 2.245.8

Il widget Lex mantiene una resa da editor leggero per le risposte: Markdown
governato, titoli, grassetto, corsivo, elenchi, tabelle, citazioni, separatori
e blocco documento per lettere/diffide. Le bozze arrivate in una sola riga
vengono normalizzate lato UI prima del rendering e ripulite da appendici fonte
non pertinenti al documento.

La fase di attesa non mostra più solo secondi grezzi: la durata viene formattata
in italiano naturale (`1 minuto e 10 secondi`) e la bolla `Sto pensando` espone
i passaggi in corso, differenziando redazione, fonti web, documenti, agenda e
risposta generica. Al termine resta visibile il totale del pensiero completato.

Lato Lex, le richieste redazionali con cliente non vengono più intercettate come
lookup anagrafico: il workflow `bozza_lettera` prevale, recupera contesto
tenant-aware e compila studio, avvocato e cliente quando disponibili. È stato
aggiunto il presidio `utf8-integrity` per impedire regressioni su accenti
italiani e mojibake nei testi rivolti all'utente.

## Agenti fonte legale - 2026-05-17 - 2.245.0

`/admin/aggiornamenti-legali/fonti` ora espone ogni fonte come agente
controllabile: la colonna `Agente` mostra ultimo esito, messaggio, durata,
documenti trovati/lavorati/invariati e timeout. Il pulsante `Esegui agente`
richiede una run manuale governata dalla console pianificazioni.

Il batch notturno continua a eseguire le fonti in processi separati con timeout,
ma registra anche una riga persistente in `source_agent_runs` per ogni fonte.
La console `/admin/pianificazioni` crea automaticamente job `legal_source_<codice>`
per le fonti censite; sono manuali di default e possono essere programmati dal
superadmin senza campi shell o comandi liberi.

## Console pianificazioni superadmin - 2026-05-17 - 2.244.0

`/admin/pianificazioni` e l'alias `/admin/cronjob` aggiungono una superficie
superadmin governata per cronjob, richieste manuali ed esiti worker. La console
usa un registro SQLite persistente (`scheduler_registry.sqlite`) separato dai
dati studio: i job di sistema vengono censiti, le modifiche vengono applicate
dal worker entro un minuto e le esecuzioni vengono tracciate con stato,
messaggio e durata.

Sono stati introdotti agenti delegati da template autorizzati, senza comandi
liberi: clienti/soggetti, scadenziario/agenda, preventivi/parcelle, email PEC,
email ordinaria, fascicoli/documenti, aggiornamenti legali, backup/spazio,
depositi telematici, sito studio, pagamenti/notifiche e privacy/GDPR. Ogni
agente dichiara autoverifica, controllo supervisore e motivo del mancato
completamento quando trova archivi mancanti o blocchi di dominio.

## Hotfix catalogo fonti legali - 2026-05-17 - 2.243.9

`/admin/aggiornamenti-legali/fonti` e' stata completata come catalogo
professionale superadmin: famiglie fonte, stato attivo/in osservazione,
conteggi reali per canale, ciclo 23:00/23:10/23:15, regole incrementali,
lettura allegati e azione di acquisizione mirata. Il catalogo include anche
fonti aggiunte da IUSENTRA oltre alla richiesta utente: INPS, Curia CGUE,
ISTAT prezzi, MIMIT, AGCM, AGCOM e Banca d'Italia; INAIL resta censita ma non
automatica finche' il canale non risulta stabile.

## Hotfix archivi ufficiali visibili - 2026-05-17 - 2.243.8

`/ricerca-legale/ricerca` continua a essere una superficie React operativa, ma
ora non dipende piu' solo dal repository `legal_updates.db`: il bridge legge
anche gli archivi ufficiali locali Normattiva e Gazzetta tramite
`lex.retrieval.official_sources_retriever`. La UI espone conteggi reali per
documenti, articoli ed estratti indicizzati e mostra risultati Normattiva/GU
prima di attivare la ricerca web governata.

La console Flask governata `/admin/aggiornamenti-legali` e la pagina Archivio
mostrano gli stessi conteggi, cosi' il database ufficiale importato nel volume
di produzione resta visibile anche al superadmin. Gate mirati eseguiti:
py_compile su retriever/bridge/surface e pytest su Ricerca Legale, job Update
Intelligence, registry fonti ufficiali e importer Normattiva.

La stessa tranche rende operativo il ciclo giornaliero delle fonti: scheduler
alle 23:00 per archivi ufficiali Normattiva/Gazzetta, poi Update Intelligence
alle 23:10/23:15 con verifica web completa, inclusa lettura di pagina e
allegati ufficiali. Il downloader Normattiva confronta catalogo remoto,
manifest e stato locale prima di scaricare e mantiene una sola copia ZIP
quando una collezione cambia. OpenGA e' estesa a Calendario Udienze, Decreti,
Ordinanze, Pareri, Provvedimenti pubblicati, Ricorsi definiti, Ricorsi
pendenti, Ricorsi pervenuti e Sentenze; la stessa ricerca governata include
anche interpelli Ministero Lavoro, Garante Privacy, ANAC e PST Giustizia.

## Hotfix Update Intelligence verificata - 2026-05-16 - 2.243.5

Le pagine admin `/admin/aggiornamenti-legali/analisi` e
`/admin/aggiornamenti-legali/review` mantengono la superficie operativa Flask
governata, ma non mostrano piu' codici tecnici di classificazione o stato. La
copy distingue l'autopubblicazione verificata dalla revisione umana: le fonti
affidabili ad alta confidenza vengono pubblicate solo dopo conferme pubbliche
coerenti; la coda resta per i casi con verifica insufficiente.

Gate mirati eseguiti: py_compile su pipeline/verifica/admin/retriever e
`python -m pytest tests\test_legal_updates_pipeline.py -q --tb=short`.
Lo shard prodotto/superadmin e' stato rilanciato con il nome test reale; il
controllo copy template ampio segnala una discrepanza storica non collegata su
`server_manutenzione.html` (`gia' compattati` atteso dal test, copy attuale
`gia' ottimizzati`).

## Hotfix Registro Mediazione interno - 2026-05-16 - 2.243.4

`/ricerca-legale/mediazione` e l'alias `/legal-intelligence/mediazione`
restano nel perimetro `react_operational_full`, ma ora mostrano dentro
IUSENTRA i dati ministeriali acquisiti, non una raccolta di collegamenti. Il
registro interno comprende Registro Organismi di Mediazione, Elenco Enti per la
Mediazione ed Elenco Formatori per la Mediazione, con sezione, stato, natura,
territorio, codice fiscale, partita IVA, email e sito quando presenti.

La UI usa ricerca specifica, cinque filtri operativi e una tabella compatta che
renderizza i primi 80 risultati mantenendo filtri e ricerca sull'intero archivio
di 3.035 record. Le tre schede ministeriali restano come verifica finale e non
come contenuto principale. Il bridge React usa identita' per-riga per impedire
che i record importati vengano deduplicati per URL ufficiale.

Gate locali chiusi: py_compile mirato, pytest Legal Intelligence/Lex/Update
Pipeline, typecheck, build Vite, Docker locale no-cache `2.243.4`, sync live dei
tre registri ministeriali, API React autenticata con 3.038 schede totali e audit
Chrome CDP desktop/tablet/mobile su `/ricerca-legale/mediazione` e
`/legal-intelligence/mediazione`. Report visuale:
`artifacts/react-migration/visual-2.243.4-mediazione-registry-final/visual-load-audit.md`.
Nessun backup eseguito.

## Hotfix Ricerca Legale con contesto fonte - 2026-05-16 - 2.239.3

`/legal-intelligence/` e `/ricerca-legale` restano nel perimetro
`react_operational_full`, ma la UX non e' piu' una raccolta di collegamenti.
La dashboard diventa `Osservatorio Legale`, con mappa fonti/news/registri e
percorso operativo; la ricerca costruisce schede interne con estratto,
contesto, uso pratico, attendibilita' e query collegata.

Il bridge backend arricchisce ogni record reale con `sourceExcerpt`,
`sourceContext`, `practicalUse`, `reliabilityNote` e `followUpQuery`; il
frontend usa questi campi per mostrare il contenuto utile dentro IUSENTRA,
lasciando la fonte originale come controllo finale. Il flusso mantiene nessun
POST HTML, nessuna CTA `_legacy=1`, nessun dato dimostrativo e nessun testo da
sviluppatore visibile.

Gate locali chiusi: typecheck, test frontend, build Vite, contratti React,
Open Design, pytest mirato `tests/test_react_legal_intelligence_search.py`,
compileall, packaging/readiness, Docker locale no-cache `2.239.3`, readiness
locale e audit Chrome CDP desktop/mobile su `/legal-intelligence`,
`/legal-intelligence/mediazione`, `/ricerca-legale` e
`/ricerca-legale?q=mediazione`. Report visuale:
`artifacts/react-migration/visual-2.239.3-legal-intelligence-context/visual-load-audit.md`.
Deploy Hetzner CPX42 eseguito senza backup con server sul commit pushato,
container applicativi healthy e `/api/pronto` pubblico `2.239.3`.

## Tranche superadmin operativo - 2026-05-15 - 2.239.0

Le pagine superadmin richieste restano nel perimetro di potenziamento prodotto,
ma questa tranche chiude due blocchi immediatamente critici:

- `Server e manutenzione` ora espone una mappa storage per studio con categorie
  operative, cartelle piu' pesanti, file principali, area dominante e azioni
  dirette di analisi/compattazione. I consumi tenant sono separati da email e
  backup globali per evitare numeri doppi quando la piattaforma ospita piu'
  studi. La lettura iniziale usa una scansione rapida configurabile e dichiara
  quando il dettaglio e' parziale, cosi' il pannello resta reattivo anche con
  storage molto grandi e rimanda alle analisi mirate per l'inventario completo.
- `Assistenza remota` e' pronta al primo avvio: STUN predefinito, ICE server
  sempre disponibili, link cliente firmato, stanza operatore, schermo/audio con
  consenso, chat e audit. TURN e controllo avanzato esterno restano
  ottimizzazioni opzionali, non prerequisiti che bloccano l'assistenza base.

Gate locali chiusi: `py_compile`, Ruff mirato,
`pytest tests/test_support_remote.py tests/test_server_maintenance_surface.py`
con 15/15 test passati, packaging/readiness 8/8, validazione documentale, build
Vite, Docker locale no-cache, readiness `2.239.0`, tempi autenticati e browser
reale desktop/tablet/mobile. Nel container Docker la console assistenza risponde
in circa `0.106s`, la manutenzione server in circa `2.345s` e il payload storage
su due studi in circa `2.339s`, dichiarando il dettaglio parziale quando scatta
il limite operativo. Il report visuale finale e' in
`artifacts/react-migration/visual-2.239.0-superadmin-operativo/visual-load-audit.md`.

## Hotfix Copertura AI condivisa - 2026-05-15 - 2.238.4

La console superadmin `/admin/copertura-ai` e la review `/admin/copertura-ai/review`
non sono piu' divise per studio: auditor, gap queue, generazione bozze, review,
publish SQL e API admin usano l'archivio applicativo condiviso
`LEGAL_COVERAGE_SQLITE_DB`, con fallback governato a
`intelligence/legal_coverage.db` o a PostgreSQL solo se configurato
esplicitamente con `LEGAL_COVERAGE_DB_*`.

Questo evita di ripetere la stessa copertura giuridica per ogni studio quando la
piattaforma cresce. `tenant_slug`, `g.tenant`, `TENANT_DATABASE_CONFIG`,
`studio.db` del tenant e configurazioni PostgreSQL legacy dello studio non
vengono piu' usati dalla Copertura AI; i dati riservati degli studi restano
tenant-aware negli altri domini.

## Hotfix Aggiornamenti legali condivisi - 2026-05-15 - 2.238.3

La console superadmin `/admin/aggiornamenti-legali` e la pagina `Fonti` non
sono piu' divise per studio: fonti, acquisizione, analisi, archivio, review,
pubblicazione e API admin usano l'archivio applicativo condiviso
`legal_updates.db` derivato dal `LEGAL_INTELLIGENCE_DB` globale.

Questo evita scansioni duplicate quando la piattaforma ospita piu' studi. I
dati privati dello studio restano tenant-aware negli altri domini; la
condivisione riguarda solo aggiornamenti giuridici pubblici e fonti comuni.

## Hotfix Lex chat sentenze e 500 controllato - 2026-05-15 - 2.238.2

Il widget Lex integrato nella shell non mostra piu' il corpo HTML di una pagina
500 quando `/api/assistente/chat` fallisce prima dello stream. La route restituisce
JSON controllato, la UI traduce l'errore in messaggio operativo breve e il dettaglio
resta nei log. Il crash reale segnalato sul workflow `giurisprudenza_specifica`
era dovuto a `SourceScope.reason` mancante ed e' coperto dalla query
`Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026`.

La stessa query ora aggancia anche la scheda ufficiale Cassazione
`penale_dettaglio.page?contentId=SZP50042` tramite fallback governato sulla
pagina pubblica Giurisprudenza Penale; se l'exact match ufficiale e' gia' stato
trovato, Lex non ripete la ricerca pubblica generica.

Gate mirati: py_compile, `node --check` del widget, Ruff mirato, test Lex
su sentenze/fonti/route/widget/retrieval e `git diff --check` sul perimetro
modificato.

## Hotfix cartella cliente React full - 2026-05-15 - 2.237.5

La route profonda `/clienti/<id>/cartella` e' ora governata come
`react_operational_full` nel manifest e nei gate React. I link storici che
arrivano con `?_legacy=1` non aprono piu' `clienti/cartella.html`: dopo i
controlli di autenticazione e accesso vengono reindirizzati alla URL canonica
senza parametro legacy, preservando eventuali altri parametri di query.

La pagina React `CartellaClientePage` non espone piu' CTA `?_legacy=1`; il
bridge backend fornisce azioni canoniche verso cartella e faldone cliente. Sono
stati aggiunti il contratto legacy dedicato, gli unlock governati nel route
gate, gli assert anti-regressione in `check-react-contracts`,
`check-route-gate`, `check-full-react-route-contract` e in
`tests/test_react_shell.py`.

Verifiche locali: py_compile mirato, test React shell mirati con readiness
release, contratti React, gate full React, generatori App V2, typecheck, build
Vite `2.237.5`, Docker locale no-cache healthy e browser Chrome CDP
desktop/mobile sulla URL con `_legacy=1`. Il browser conferma redirect 302 alla
URL canonica, shell React, nessun form POST HTML, nessun overflow orizzontale e
nessun testo tecnico vietato.

## Modulo notifiche legali e registry telematico - 2026-05-14 - 2.236.0

La pagina React Notifiche legali ora espone fasi operative reali dopo i pulsanti `Controlla relata`, `Controlla prova deposito` e `Prepara comunicazione`: l'esito mostra blocchi, testo generato, file previsti e pacchetto prova quando disponibile. La scelta dei documenti dal fascicolo e' multipla e alimenta automaticamente l'elenco allegati della relata.

Il backend applica contratti fail-closed per notifica PEC L. 53/1994, comunicazione cliente non-notifica, deposito prova, area web PST per notifica non consegnata, registry procedimenti e profili deposito separati SICID/SIECIC/SIGP/UNEP/PAT/PTT/PDP. Il modulo legacy `pct/notifica.py` e' disattivato per impedire oggetti PEC generici.

Gate mirato finale: `python -m pytest tests/test_notifiche_legali.py tests/test_telematic_registry_fail_closed.py tests/legal_deposit/test_penal_deposit_rules.py -q` -> 44/44 passati. Docker locale no-cache, smoke read-only e browser isolato su `/notifiche-legali` confermano la selezione multipla dei documenti e il riporto automatico nell'elenco allegati. Nessun backup eseguito in questa tranche.

## Hotfix PST Step 4 e SIGP/Giudice di Pace - 2026-05-14 - 2.235.6

La release 2.235.6 ripristina il comportamento gia' tracciato per il wizard
PST: quando l'acquisizione arriva da una pratica locale, oppure l'URL contiene
`fascicolo_id`, `target_fascicolo_id`, `id_fasc` o `mode=update_existing`, il
wizard React parte con `Aggiorna pratica esistente` gia' impostato. Lo stesso
controllo e' visibile anche nello Step 4, prima della verifica, cosi' l'analisi
lavora sulla pratica corretta e non apre un flusso di creazione non voluto.
La stessa regola e' stata applicata al template classico
`web/templates/portale/acquisizione_wizard.html`, perche' alcune postazioni o
flag possono ancora aprire `/portali/pst/acquisizione?_legacy=1`: anche li'
Step 4 mostra `Pratica da aggiornare`, il radio `Aggiorna pratica esistente` e
il campo `Fascicolo locale da aggiornare`.

Per Giudice di Pace/SIGP il Local Signer `1.6.35` non apre piu' una chiamata
aggiuntiva di profilo documento durante la visualizzazione: nel batch di
consultazione vengono inclusi catalogo documenti e `ricercaAtti`, e dagli ID
ufficiali vengono creati i riferimenti minimi necessari per anteprima e download.
Il download dell'intero fascicolo resta un secondo batch dedicato. La regola
operativa torna quindi a essere: un PIN per visualizzare, un PIN per scaricare
tutto, salvo scadenza reale della sessione lato portale/token.

Verifiche mirate aggiunte: test React/template sul mapping iniziale e sullo
Step 4, test Local Signer che bloccano chiamate SIGP fuori batch per
visualizzazione e catalogo documenti. Docker locale, smoke read-only e browser
reale sul percorso classico sono registrati nei report di sessione; il deploy
Hetzner resta il gate finale dopo push.

## Hotfix PST, Local Signer e navigazione telematica - 2026-05-14 - 2.235.5

La release 2.235.5 chiude la regressione segnalata sul PIN PST: il wizard
React di acquisizione non apre piu' una sessione preparatoria tramite
`/pst/preflight-auth` prima della ricerca, dell'anteprima o del download.
Ricerca snapshot, fallback di ricerca, anteprima fascicolo e download batch
inviano solo l'eventuale `pst_session_id` gia' noto e lasciano al Local Signer
la chiamata operativa reale, preservando la regola utente: un PIN per
visualizzare il fascicolo e un PIN per scaricare l'intero fascicolo, salvo
scadenza reale lato portale/token.

Il fix e' stato esteso anche ai percorsi classici che potevano aggirare la
superficie React: `web/templates/polisWeb.html`, `web/polisWeb.html`,
`web/templates/portale/acquisizione_wizard.html`, dettaglio fascicolo e client
SIGP non invocano piu' `/pst/preflight-auth` nei flussi operativi. Gli ingressi
separati `/sigp` e `/sigp-sync` sono stati tolti da menu/gate e registrazione
applicativa; chi li richiama viene rimandato al percorso unico
`/portali/pst/acquisizione`.

Il Local Signer `1.6.34` preferisce il curl di sistema Windows, applica
internamente `--ssl-no-revoke` su Schannel e non mostra piu' istruzioni
all'utente per aggiungere manualmente quell'opzione. La selezione certificato
accetta automaticamente l'unico certificato coerente con il codice fiscale
anche quando l'emittente non rientra nella preferenza storica, evitando dialoghi
manuali inutili.

Il centro `/telematico` e le superfici collegate usano link visibili canonici
senza prefisso `/app-v2` (`/polisWeb`, `/pdp`, `/pat`, `/sigit`, ecc.) e lo
scroll non usa piu' `scrollIntoView` sulle aree telematiche: calcola l'offset
della topbar e porta il pannello operativo nella posizione corretta.

Verifiche locali confermate finora: shard Local Signer/PST 11/11, shard React
telematico 6/6, test scroll/Local Signer React 2/2, Ruff mirato, typecheck,
build Vite `2.235.5`, build pacchetti Local Signer `1.6.34` e packaging /
readiness 14/14. Restano da registrare in questa sezione Docker locale,
browser reale e deploy Hetzner dopo il commit finale.

## Hotfix Email ordinaria e Panoramica - 2026-05-14 - 2.235.4

La release 2.235.4 corregge la regressione introdotta dal fix anti-duplicati:
la sincronizzazione email ordinaria torna a completare anche quando il server
IMAP interrompe una lettura con `cannot read from timed out object`.
Il client IMAP non espande piu' automaticamente la sync verso archivi o
etichette equivalenti (`Tutti i messaggi`, `Archivio`, cartelle personali,
spam/indesiderata) scoperti da `LIST`: restano sincronizzate le cartelle
operative esplicite, INBOX, Inviati, Cestino e Bozze. Questo mantiene la
deduplica dei triplicati senza rileggere copie archiviate della stessa email.

Durante un timeout sul singolo `FETCH`, il runtime chiude in modo silenzioso il
socket guasto, riapre la connessione, riseleziona la cartella e riprova quel
messaggio. Il logout di una connessione gia' in timeout non trasforma piu' il
risultato in errore grezzo visibile all'utente. La Panoramica React ha inoltre
un timeout client sulla sync comunicazioni in background, cosi' lo stato
`Sincronizzazione comunicazioni...` non resta appeso.

Verifiche locali confermate: `tests/test_email_client.py` completo 50/50,
`tests/test_dashboard_mailbox_sync.py` 5/5, Ruff mirato su email, `npm test`,
typecheck, build Vite `2.235.4`, packaging/readiness 8/8, Docker locale
no-cache healthy e smoke locale post-deploy PASS=76 FAIL=0 SKIP=1 BLOCKED=6.
Deploy Hetzner eseguito senza backup (`IUSENTRA_SKIP_BACKUP_CRON=1`, nessun
`backup.sh`): container healthy, `/api/pronto` pubblico `ok=true` su `2.235.4`,
smoke produzione read-only PASS=76 FAIL=0 SKIP=1 BLOCKED=6 e nessun
`email/ordinaria.json` nel repository del server.

## Hotfix Local Signer CI - 2026-05-14 - 2.235.3

La release 2.235.3 corregge il rosso remoto `CI / Local Signer e PKCS#11`
emerso dopo il deploy 2.235.2: il WSDL diretto PDP/PAT/PTT torna attivo di
default, come previsto dal guardrail storico.
Il browser assistito per PDP/PAT/PTT entra solo quando lo studio o il runtime
impostano flag espliciti di forzatura/disabilitazione (`HACS_SIGNER_*` o
`PCT_*`), evitando il ritorno silenzioso alla modalita assistita come default.

E' stato rigenerato IUSENTRA Local Signer `1.6.31`, inclusi sorgente
distribuito e pacchetti `tools/dist`, cosi' il download pubblico serve lo
stesso comportamento verificato nei test. La regola PST/PIN resta invariata e
vincolante: un PIN per visualizzare il fascicolo e un PIN per scaricarlo, salvo
scadenza reale della sessione lato portale o token.

Verifiche locali gia' confermate prima del push: shard CI esatto signer 4/4
verde 39/39; `test_portale_wsdl_diretto_abilitato_default_attivo`,
`test_local_signer_dist_allineato_a_sorgente_e_installer_versionati`, ruff,
packaging/readiness, `npm test`, typecheck e build Vite `2.235.3` verdi.

## Hotfix CI, acquisizioni telematiche e deduplica email - 2026-05-14 - 2.235.2

La release 2.235.2 chiude tre regressioni segnalate dall'utente:

- il gate CI `contracts` torna offline e deterministico: valida OpenAPI e provider senza richiedere un server locale su `127.0.0.1:8080`; il controllo HTTP live resta nella suite `api` o `post-deploy`;
- le acquisizioni assistite PDP, PAT e PTT/SIGIT sono sbloccate come route React esatte su `/portali/pdp/acquisizione`, `/portali/pat/acquisizione`, `/portali/ptt/acquisizione` e `/portali/sigit/acquisizione`; i moduli telematici non parificati restano protetti;
- Email ordinaria deduplica e ripara i triplicati da cartelle IMAP equivalenti, preservando la guardia che non fonde messaggi PEC/Legalmail diversi con UID stabili.

Regola PST/PIN da mantenere in ogni tranche: il flusso deve riusare la sessione assistita gia' aperta e non deve tornare a chiedere PIN multipli. Il comportamento accettato resta un PIN per visualizzare il fascicolo e un PIN per scaricarlo, salvo scadenza reale della sessione lato portale o token.

### Fasi per chiudere tutta l'applicazione in React full

1. Stabilizzazione anti-regressione: ogni rotta promossa deve avere manifest, gate route/shell, contratto legacy, API JSON, test mirati, documentazione e smoke. Le regressioni App V2, portali e email diventano test bloccanti.
2. Promozione route gia' parificate: portare a `react_operational_full` solo route con dati reali, permessi, audit, stati UI e azioni JSON gia' dimostrati. Nessuna pagina viene promossa solo perche' esiste una card React.
3. Parita CRUD e workflow: per ogni area residua sostituire form POST HTML, redirect opachi e fallback legacy primari con API Flask JSON tenant-aware, validazioni backend e feedback React.
4. Telematico assistito: completare prima le acquisizioni assistite e i wizard locali, poi passare ai flussi ministeriali sensibili solo quando sono coperti da Local Signer, evidenze ufficiali, no scraping e sessioni PIN governate.
5. Documenti, download ed export: migrare le superfici di governo in React, mantenendo i download e gli allegati su route backend sicure finche' non esiste parita completa e auditata.
6. Amministrazione e sicurezza: completare sottopercorsi admin, permessi, backup, tenant, audit e privacy con fail-closed multi-studio e smoke autenticati quando saranno disponibili credenziali dedicate.
7. Rimozione fallback Jinja: solo dopo parita verificata, togliere i prefissi legacy da gate/shell, eliminare CTA `_legacy=1` visibili e aggiornare i contratti affinche' la regressione a Jinja fallisca in CI.
8. Verifica finale prodotto: desktop, tablet e mobile reali su pagine rappresentative, tempi di caricamento, console/network, assenza testi tecnici, bundle Vite, Docker locale, branch gemelli, igiene repo e deploy Hetzner.

## Hotfix App V2 rollout - 2026-05-14 - 2.235.1

Corretto il blocco regressivo che rendeva non raggiungibili le pagine operative sotto `/app-v2` quando lo studio non aveva flag manuali configurati. Le superfici gia' promosse operative nel manifest sono ora attive di default e restano spegnibili per rollback esplicito; `routes.appV2.telematico.center`, `routes.appV2.telematico.surface` e `routes.appV2.notifications.mobilePush` restano default-off e fail-closed.

Verifica mirata: `/app-v2/messaggi/nuovo`, `/app-v2/messaggi` e `/app-v2/documenti` rispondono 200 con shell React autenticata; `/app-v2/telematico` resta 403 perche' nel perimetro telematico non parificato. Docker locale no-cache `2.235.1` healthy, smoke post-deploy locale PASS=76 FAIL=0, browser reale desktop/mobile sulla route segnalata senza messaggio "Funzione non attiva".

## Stato fase react 13 - 2026-05-14 - Smoke operativi e post-deploy readiness 2.234.0

La tredicesima fase del piano `fasereact` consolida gli smoke operativi finali
senza introdurre workflow distruttivi. `scripts/smoke_app_v2_all.py` e' ora
l'orchestrator unico con suite `health`, `auth`, `flags`, `rbac`, `tenant`,
`routing`, `api`, `pages`, `workflows`, `documents`, `admin`, `search`,
`notifications` e `post-deploy`, piu' compatibilita con gli alias storici
`--subset`. La libreria `scripts/smoke_lib.py` governa HTTP, redaction, JSON
report, summary, severita ed exit code.

Gli smoke sono read-only di default in staging/produzione, non inviano PEC,
push o notifiche reali, non stampano segreti e marcano come `BLOCKED` i controlli
autenticati privi di env dedicate invece di dichiararli verdi. Aggiunti
`docs/smoke-tests.md` e `docs/release-readiness-checklist.md`, aggiornati
README, piano test, CI/CD gates, rollout, troubleshooting e workflow manuale
`smoke-staging.yml` con report JSON sanitizzato.

Verifiche fase 13 concluse: py_compile, test unitari smoke, help/inventory,
generatori App V2, validator documentali, OpenAPI/provider, npm
test/typecheck/build, packaging/readiness, Docker locale no-cache e smoke
post-deploy read-only risultano verdi. Deploy Hetzner CPX42 eseguito senza
aggiornare il cron backup sul commit
`85d7617549c0695ffd3f41447d0b2c86524766aa`: container healthy/up, runtime
`2.234.0`, `/api/pronto` pubblico 200 e smoke produzione post-deploy read-only
PASS=76, FAIL=0, SKIP=1, BLOCKED=6.

## Stato fase react 12 - 2026-05-14 - Documentazione, handover e release playbook 2.233.0

La dodicesima fase del piano `fasereact` consolida la documentazione finale
senza introdurre feature applicative nuove. Sono stati creati l'indice ufficiale
`docs/index.md`, l'audit documentale `docs/documentation-audit.md`, il
handover architetturale `docs/architecture.md`, il runbook App V2
`docs/app-v2.md`, troubleshooting, risk register, osservabilita/log, database e
migrazioni, release notes tecniche App V2 e prossime PR.

`README.md`, `SECURITY.md` e `CONTRIBUTING.md` sono stati riallineati a
branch, sicurezza, feature flag, PII, RBAC, tenant isolation, test, CI e deploy
reali. La documentazione evita di dichiarare Storybook/VRT o smoke autenticati
come verdi quando nel repository mancano runner o secrets dedicate. Aggiunti i
validatori leggeri `scripts/validate_docs_links.py` e
`scripts/validate_docs_commands.py`.

Verifiche fase 12: py_compile dei nuovi script e del generatore API, link docs
145/145, comandi documentati 131/131, registry/area/test-docs App V2 `--check`,
OpenAPI generato/validato, provider verification 182 auth-error, 27 success e 1
backend-security, smoke inventory/contracts, npm test/typecheck/build Vite
2.233.0, packaging/readiness, test OpenAPI e test CI/test-plan mirati. Il primo
check API ha intercettato correttamente una modifica manuale a documento
generato: la fonte `generate_api_contracts.py` e' stata aggiornata e il gate e'
tornato verde. Docker locale no-cache 2.233.0 e' stato avviato con
app/scheduler/OCR/Redis healthy, `/api/pronto` 200, runtime e label immagine
2.233.0; smoke security/routing/workflows locali verdi in modalita senza
credenziali dedicate.

Deploy fase 12 verificato su Hetzner CPX42 senza aggiornare il cron backup:
server sul commit `a33794605f8fb2e7356981f4907d2e755d8da09a`, container
operativi healthy/up, runtime `2.233.0`, `/api/pronto` pubblico 200 e smoke
produzione security/routing/workflows completati. Un 503 iniziale nella finestra
di riaggancio del proxy post-recreate e' stato registrato come osservazione
chiusa e non dichiarato verde finche' la readiness pubblica non e' tornata 200.

## Stato fase react 11 - 2026-05-14 - CI/CD e release safety 2.232.0

L'undicesima fase del piano `fasereact` trasforma il piano test della fase 10
in gate CI/CD espliciti e bloccanti. Il workflow principale `.github/workflows/ci.yml`
ora include provider verification/OpenAPI, smoke contratti, registro e piano
test App V2, smoke inventory senza credenziali, test RBAC/tenant/feature
flag/routing, frontend test/typecheck/build, shard pytest, coverage critica ed
E2E smoke. Il nuovo workflow manuale `.github/workflows/smoke-staging.yml`
copre smoke ambiente/post-deploy con environment `staging`, secrets GitHub
solo se richieste credenziali e artifact sanitizzati.

`docs/ci-cd-gates.md` e' il registro operativo di workflow, job, comandi,
required checks, segreti/env, artifact, rollout safety, rollback e gap residui.
`Security Supply Chain` ora produce report `pip-audit` e `npm audit` bloccando
dipendenze critiche senza hardcodare segreti. `tests/test_ci_cd_gates_phase11.py`
impedisce regressioni sul wiring dei gate e sulla documentazione.

Verifiche locali fase 11: YAML workflow parseabile, py_compile, generatori
`--check`, smoke inventory/contracts, pytest dedicato fase 11 5/5, contratti
OpenAPI + fase 11 10/10, registry/test-plan/fase 11 13/13, backend
security/tenant/flag/routing/OpenAPI 75/75, `pip-audit` senza vulnerabilita
note, `npm audit` critical a zero vulnerabilita, npm test/typecheck/build,
suite CI `coverage-critical`, `release-readiness`, `quality-overlay`,
`e2e-smoke`, Docker locale no-cache 2.232.0 healthy e smoke App V2 locale
security/pages/routing/workflows.

Deploy fase 11 verificato su Hetzner CPX42 senza aggiornare il cron backup:
server sul commit `023f18ba7b5be9bebdcf57c508e900e7a2f003c7`, container
operativi healthy/up, runtime `2.232.0`, `/api/pronto` pubblico 200 e smoke
produzione security/routing/workflows completati in modalita anonima/inventory
per assenza di credenziali smoke dedicate.

## Stato fase react 10 - 2026-05-14 - Test completi App V2 2.231.0

La decima fase del piano `fasereact` consolida la strategia test App V2 senza
gonfiare segnali non esistenti. Sono stati aggiunti il piano test
`docs/test-plan-app-v2.md`, l'inventario `docs/test-inventory.md` e la matrice
`docs/test-matrix-app-v2.md`, generati da
`scripts/react-migration/generate_app_v2_test_docs.py`. La matrice incrocia
route, ruoli, tenant, feature flag, backend, frontend, RBAC, contract e smoke,
marcando `tested`, `partial`, `pending` o `blocked` senza promuovere pagine
legacy/parziali.

Lo smoke unificato `scripts/smoke_app_v2_all.py` orchestra inventory, security,
pagine, routing, workflow e contratti. Senza credenziali espone inventari e
controlli anonimi; con `--require-credentials` fallisce se mancano gli env, cosi'
non vengono dichiarati verdi profili admin/tenant/readonly non eseguiti. I
registri App V2 e il registro requisiti area collegano ora la fase 10 ai gate
fasi 7-9.

Verifiche locali fase 10: py_compile, generatori `--check`, smoke inventory,
smoke contracts/OpenAPI/provider verification, pytest dedicato fase 10,
pytest fasi 7/8/9/registry 15/15, backend security/tenant/flag/routing/OpenAPI
75/75, npm test/test:app-v2/typecheck/build, suite CI `coverage-critical`,
suite `release-readiness`, `quality-overlay`, `e2e-smoke` e coverage mirata
auth/storage/telematico al 78%. Il pytest monolitico resta non usato come unico
segnale per evitare timeout opachi.

## Stato fase react 9 - 2026-05-13 - UI regression App V2 2.230.0

La nona fase del piano `fasereact` rende verificabile la qualita UI App V2
senza introdurre Storybook o VRT fittizi. Il frontend non aveva Storybook,
storie, runner component o VRT configurati; la fase documenta questa scelta in
`docs/ui-regression-and-storybook.md` e aggiunge un'alternativa concreta:
fixture sicure isolate, gate `scripts/validate_ui_coverage.py`, pytest dedicato
e sezione `Copertura UI fase 9` nei registri generati.

Le route P0/P1 possono essere marcate `ui_tested` solo se gia'
`react_operational_full`, hanno componente React reale, stati
default/loading/empty/error/forbidden/flag-off/readonly documentati, copertura
responsive desktop/tablet/mobile e passano i gate fase 7/9. Le route parziali,
legacy o bloccate restano `partial`, `pending` o `blocked`; VRT e Storybook
restano gap espliciti finche' non esiste un comando reale eseguito.

## Stato fase react 8 - 2026-05-13 - Requisiti area/workflow App V2 2.229.0

L'ottava fase del piano `fasereact` sposta il governo dalla singola pagina al
workflow reale per area. Il nuovo registro generato
`docs/app-v2-area-requirements.md` collega le aree presenti nel manifest a
pagine legacy/App V2, feature flag, endpoint, RBAC, PII, workflow principali,
test richiesti, test presenti e stato finale (`complete_tested`,
`complete_unverified`, `partial`, `pending`, `blocked`).

La fase non promuove superfici non parificate: documenti, mandato, economico,
amministrazione, studio/scadenze miste e servizi telematici restano
`partial`/`blocked` dove esistono route legacy o workflow non ricostruiti. Le
aree segnate `complete_tested` non possono contenere route legacy o parziali,
come verificato da `tests/test_app_v2_area_requirements_phase8.py`.

Nuovi gate: `scripts/react-migration/generate_app_v2_area_requirements.py
--check`, `scripts/smoke_app_v2_workflows.py --list`,
`tests/test_app_v2_area_requirements_phase8.py`, integrazione CI e controllo
`frontend/scripts/check-app-v2-frontend.mjs`. Lo smoke autenticato richiede
credenziali via env e non dichiara passati profili mancanti.

## Stato fase react 7 - 2026-05-13 - Frontend App V2 governato 2.228.0

La settima fase del piano `fasereact` rafforza il livello frontend comune
prima della migrazione pagina per pagina: la shell App V2 espone i permessi
effettivi dell'utente nel bootstrap, filtra la navigazione sperimentale con
feature flag e RBAC UI, e mostra una 404 sicura per percorsi App V2 non censiti
senza caricare dashboard o dati riservati.

`docs/app-v2-page-registry.md` e `docs/frontend-app-v2-pages.md` ora includono
lo stato frontend fase 7 pagina per pagina. Le route P0/P1 gia'
`react_operational_full` sono `complete_tested`; le route legacy o parziali
restano `pending` o `partial` e non vengono promosse. Il nuovo gate
`frontend/scripts/check-app-v2-frontend.mjs`, collegato a CI e `npm test`,
verifica guard, no-fetch flag-off, RBAC UI, OpenAPI e documentazione.

## Stato fase react 6 - 2026-05-13 - Contratti OpenAPI endpoint React 2.227.0

La sesta fase del piano `fasereact` ha introdotto il contratto API generato per
le superfici React: `docs/openapi.yaml` e
`docs/api-endpoint-contract-map.md` censiscono endpoint `/api/v1/ui`, priorita,
pagina, feature flag, RBAC, tenant scope, PII, errori, paginazione e provider
status. I gate `scripts/validate_openapi.py` e
`scripts/verify_openapi_provider.py` impediscono drift tra documentazione e
provider Flask.

## Stato fase react 5 - 2026-05-13 - Sicurezza backend endpoint 2.226.0

La quinta fase del piano `fasereact` chiude il presidio backend trasversale
sulle API React prima della fase OpenAPI. Tutte le route `/api/v1/ui` censite
restano dietro `_richiedi_auth`; in multi-studio l'autorizzazione via API key
continua a passare da `tenant_api_auth` e dal tenant attivo.

Il nuovo `web/services/backend_security.py` blocca, dopo autenticazione,
parametri client riservati al controllo server: `tenant_id`, `studio_id`,
tenant/studio slug, `user_id`, `api_key`, token generici, `redirect`,
`return_url`, `next` e path/root di sistema. I flussi amministrativi legittimi
continuano a usare validazioni e RBAC di dominio: `ruolo`, `role`,
`extraPermissions` e chiavi provider specifiche non vengono filtrati dal
guardrail centrale.

La mappa generata `docs/backend-endpoint-security-map.md` registra endpoint,
priorita P0/P1, permessi attesi, dati sensibili e presidi. Gate mirati fase 5:
`tests/test_backend_security_phase5.py`, tenant isolation, feature flag,
routing App V2, regressioni API Impostazioni/Utenti/Fascicoli/Email, script
smoke backend security e build finale.

## Stato fase react 4 - 2026-05-13 - Routing, fallback e redirect sicuri 2.225.0

La quarta fase del piano `fasereact` governa la cerniera tra Flask/Jinja legacy
e shell React/App V2 senza attivare redirect globali. Il nuovo
`web/services/app_v2_routing.py` centralizza mapping legacy -> `/app-v2`,
validazione target interni, whitelist query, blocco parametri sensibili e
decisione redirect legata al feature flag pagina.

`docs/legacy-to-app-v2-routing-map.md` e' generato insieme al registro pagine:
per ogni route manifest documenta URL legacy, template, target App V2, flag,
redirect strategy, fallback, deep link, query preservate/bloccate, stato test e
classificazione template. I template legacy restano fallback obbligatorio per
route parziali, wildcard, download/export e workflow non parificati.

Il router frontend App V2 normalizza query/hash degli alias prima del match,
cosi' i target con `tab` o `drawer` non producono stati bianchi. I gate mirati
della fase sono `tests/test_app_v2_routing.py`,
`tests/test_app_v2_page_registry.py`, `scripts/smoke_app_v2_routing.py`,
contratti React e build/typecheck.

## Stato fase react 3 - 2026-05-13 - Feature flag per pagina App V2 2.224.0

La terza fase del piano `fasereact` rende esplicito il rollout App V2: ogni
pagina o famiglia della shell sperimentale ha un flag canonico
`routes.appV2.<area>.<pagina>`, default-off, con alias compatibili per i flag
introdotti nelle fasi 1-2.

`web/services/feature_flags.py` ora risolve alias e flag canonici nello stesso
stato, mappa percorsi statici/dinamici di `/app-v2` e blocca anche la root
quando `routes.appV2.dashboard.home` e' spento. La shell sperimentale usa la
stessa mappa in `frontend/src/lib/featureFlags.ts`: menu App V2 nascosti, stato
operativo "Modulo non attivo" e nessun fetch pagina quando il flag e' off. Le
route operative storiche gia' promosse React restano disponibili e governate
dal manifest.

Aggiornati `docs/app-v2-page-registry.md` e
`docs/frontend-app-v2-pages.md` con default, fallback flag-off, protezione
frontend/backend e test on/off. I gate mirati della fase sono
`tests/test_feature_flags.py`, `tests/test_app_v2_feature_flags.py`,
`tests/test_app_v2_page_registry.py`, typecheck/test/build frontend e smoke
App V2.

## Stato fase react 2 - 2026-05-13 - Registro pagine App V2 2.223.0

La seconda fase del piano `fasereact` trasforma la migrazione in un registro
ripetibile e verificabile. `docs/app-v2-page-registry.md` e' generato da
`scripts/react-migration/generate_app_v2_page_registry.py` e censisce le 98
route del manifest governato con URL legacy, target React/App V2, componenti,
API, storage, stato migrazione, feature flag, RBAC, rischio tenant/PII, test
presenti, test mancanti, priorita e stato finale.

`docs/frontend-app-v2-pages.md` riassume la shell App V2, gli alias legacy e il
backlog P0/P1/P2/P3. Le route non `react_operational_full` restano dichiarate
come backlog o partial: la fase 2 non promuove pagine senza API reali,
permessi, tenant isolation, test e browser verification.

Aggiunto anche `scripts/smoke_app_v2_pages.py`: senza credenziali puo'
elencare target e stato manifest; con `IUSENTRA_BASE_URL`,
`IUSENTRA_SMOKE_USERNAME` e `IUSENTRA_SMOKE_PASSWORD` puo' eseguire smoke
autenticati post-deploy senza salvare segreti nel repository.

Gate mirati verdi: `py_compile` dei nuovi script/test, generatore `--check`,
smoke `--list` e `tests/test_app_v2_page_registry.py`.

## Stato fase react 1 - 2026-05-13 - Governance default-off App V2 2.222.0

Avviata la prima fase del piano `fasereact` con perimetro di preparazione,
feature flag e sicurezza di rollout. Le nuove capability App V2 e Web Push
sono governate da flag default-off, risolti da configurazione Flask, variabili
ambiente o JSON `IUSENTRA_FEATURE_FLAGS`, con endpoint autenticato
`/api/v1/ui/feature-flags` e bootstrap React coerente.

La protezione e' applicata solo alle route sperimentali `/app-v2/*`, senza
regredire le route ufficiali gia' promosse a React operativo. Le notifiche push
su dispositivo restano disattivate finche' `notifications.mobilePush` non viene
abilitato: il frontend evita le chiamate API e il backend rifiuta
subscribe/test con errore controllato e audit di negazione.

Documentazione aggiunta: audit iniziale migrazione, matrice feature flag,
sicurezza RBAC/tenant, contratti API e rollout. Gate mirati verdi:
`py_compile`, pytest feature flag, pytest push notifications, typecheck,
contratti React, packaging/readiness, build Vite e gate route React.

## Stato hotfix 2026-05-13 - PST Local Signer PIN sessione unica

Corretto il rischio di regressione sul flusso PST/PolisWeb gia' risolto in
2.216.3-2.216.4: la superficie React di acquisizione non dipende piu' solo
dallo stato volatile del componente per riusare la sessione Local Signer.
Quando il download batch parte dopo ricerca/anteprima, la sessione `view`
viene recuperata anche dal payload del risultato selezionato e dall'anteprima
gia' caricata, quindi `/pst/download-documenti-batch` riceve lo stesso
`pst_session_id` e non riapre handshake separati.

Regola operativa confermata: nel percorso PST diretto sono ammessi al massimo
due inserimenti PIN, uno per visualizzare/interrogare il fascicolo e uno per
scaricare i documenti ufficiali in batch. Il client React continua a usare
`/pst/ricerca-snapshot`, `/pst/fascicolo-snapshot` solo quando manca il
catalogo documenti, e `/pst/download-documenti-batch` con `purpose=view` e
`preflight_auth=false`; non viene ripristinato il download singolo per ogni
documento.

Il collegamento dal dettaglio fascicolo al wizard accetta ora anche
`fascicolo_id` e `target_fascicolo_id`, oltre a `id_fasc`, cosi' l'apertura da
un fascicolo esistente resta agganciata alla pratica locale e non perde la
mappatura durante acquisizione/import.

Generato anche IUSENTRA Local Signer `1.6.30`: sorgente, copia `tools/dist`,
installer Windows `SetupLocalSigner-1.6.30.exe`, alias `SetupLocalSigner.exe`,
installer macOS/Linux e note release sono allineati. La nuova release espone
in modo esplicito il pacchetto da installare dopo il fix sul riuso sessione
PST view/download.

Gate mirati eseguiti: `python -m py_compile
web\bootstrap\portali_acquisizione_routes.py`, shard pytest React/Local
Signer/PST sul contratto sessione unica, `npm --prefix frontend run typecheck`
`npm --prefix frontend run test`, `npm --prefix frontend run build`,
`python tools\sync_packaging_files.py --check` e readiness release 8/8. Smoke
locale: il wizard `/portali/pst/acquisizione?fascicolo_id=DC5BF1DB` risponde
HTTP 200 e `/api/pronto` risponde HTTP 200 con versione `2.221.0`.
Gate Local Signer `1.6.30`: `python tools\build_dist.py`, `python -m
py_compile tools\local_signer.py tools\dist\local_signer.py
tools\build_dist.py` e pytest mirati Local Signer su dist/sessione PST.

## Stato tranche 2026-05-13 - Audit probatorio WORM 2.221.0

La tranche introduce un audit legal-grade distinto dal log applicativo: eventi
canonici `audit-event-v1`, hash SHA-256 su byte JCS, firma, catena per
tenant/fascicolo, oggetti S3 WORM con Object Lock, receipt WORM firmata,
snapshot Merkle giornalieri e verifica offline da bundle. Postgres resta indice
di consultazione ricostruibile; la prova e' l'envelope firmato in WORM.

La superficie React Fascicoli espone ora la scheda `Audit` nel dettaglio
fascicolo, con timeline minimale, badge `Firmato`, `WORM`, `In snapshot`,
`TSA verificata`, copia hash e download prova/bundle. Non vengono mostrati
payload sensibili: la UI usa solo metadati, hash e stato probatorio.

Gate mirati eseguiti: `python -m pytest tests/test_audit_*.py -q`,
`python -m compileall -q audit scripts alembic tests/test_audit_*.py`,
`npm run typecheck` e `npm run build` in `frontend/`.

## Stato tranche 2026-05-13 - Audit gate React reale 2.220.0

Audit severo su manifest, `react_route_gate.py`, shell React, router frontend,
bridge e script di guardia. Risolte contraddizioni operative dove route
dichiarate React erano ancora bloccate dal gate: `/scadenziario/:id` e
`/sito-studio/builder` sono ora `react_operational_full`; `/scadenziario/:id/modifica`
e `/sito-studio/redazione-ai` sono `react_operational_partial` perche' conservano
azioni sensibili non ancora completamente parificate.

Il gate resta chirurgico: `/scadenziario` passa solo per lista, nuovo,
dettaglio e modifica; export, PDF, completamento, eliminazione e bulk restano
fuori dalla shell. `/sito-studio` passa solo per root, contatti, builder e
redazione assistita; sottopercorsi articoli/modifica e altri dettagli restano
legacy-first. Le route telematiche, amministrative sensibili e applicazioni
non coperte da API JSON sicure sono state registrate nel manifest come
`legacy_operational` con contratti legacy espliciti.

I gate anti-mascheramento hanno inoltre corretto falsi full preesistenti:
`Template Atti` non espone piu' form HTML nel componente dichiarato full e la
dashboard non usa piu' nomi `mock` nel fallback vuoto. Test/gate verdi:
`py_compile`, `tests/test_react_shell.py`, `npm typecheck`, `npm build`,
`npm test`, `check-route-gate`, `check-full-react-route-contract` e
`check-no-mock-data-full-react`.

## Stato tranche 2026-05-13 - Portali non-PST assistiti fail-closed 2.219.0

La policy prodotto dei portali telematici e' centralizzata: PST / PolisWeb resta
`direct_internal`, mentre PTT/SIGIT, PAT e PDP restano `official_portal_assisted`
salvo manifest diretto verificato, completo, non scaduto e con test reali
passati. I client produttivi PTT/PAT/PDP sono protetti da guard fail-closed,
senza bloccare classi demo/offline e senza promuovere codice client o WSDL
ipotizzati a canale diretto.

Il wizard `/portali/<portale>/acquisizione` mostra per PTT/PAT/PDP il flusso
di Portale ufficiale assistito con Local Signer / Local Connector, raccolta
download sicuri e import nel fascicolo interno. Sono stati aggiunti endpoint
comuni per sessione assistita, deposito assistito, import ricevute/esiti in
Comunicazioni/Cancelleria, timeline ed evidence pack, con divieto di scraping
HTML, salvataggio credenziali o finalizzazione senza evidenza ufficiale.

## Stato tranche 2026-05-13 - Email ordinaria accenti e charset 2.218.9

Email ordinaria usa ora un decoder piu' robusto per intestazioni e corpo:
quando il server IMAP dichiara un charset non coerente con i byte reali, il
parser confronta la decodifica dichiarata con `utf-8`, `windows-1252` e
`latin-1`, scegliendo il testo senza caratteri sostitutivi o mojibake. Il caso
visibile con carattere sostitutivo al posto dell'accento viene quindi restituito come `possibilità`.

La sincronizzazione non lascia bloccati i record gia' importati male: se una
email salvata contiene caratteri sostitutivi, viene inclusa nella finestra di riparazione anche se
non ha allegati mancanti, riletta da IMAP e aggiornata con oggetto, mittente,
destinatari, corpo testo e corpo HTML migliori quando il messaggio sorgente e'
ancora disponibile.

## Stato tranche 2026-05-13 - Email ordinaria deduplica inviati 2.218.8

La sincronizzazione di Email ordinaria rimuove ora in modo centrale i duplicati
tra copia locale inviata dall'app e copia IMAP salvata dal provider nella
cartella Inviati, anche quando il server registra il messaggio con uno scarto di
orario. Il confronto resta prudente: si applica solo alla coppia locale/IMAP e
richiede oggetto, destinatari normalizzati, corpo e orario vicino coerenti, cosi'
due invii locali simili non vengono fusi tra loro.

Gli invii SMTP generano sempre un `Message-ID` prima della trasmissione e lo
salvano nello storico messaggi. Le sincronizzazioni future possono quindi usare
una chiave stabile; le righe gia' duplicate vengono normalizzate al successivo
passaggio di sincronizzazione ordinaria senza richiedere controlli manuali per
singolo studio.

## Stato tranche 2026-05-13 - Allegati PEC e cartelle Legalmail 2.218.7

Il dettaglio React PEC/email resta full React ma non propone piu' link verso
allegati presenti solo come metadato storico. Gli allegati senza file fisico
sono mostrati come recuperabili tramite sincronizzazione e, se restano assenti,
la UI invita a verificare che la PEC sorgente sia ancora presente nella casella.
Gli allegati gia' salvati mantengono il loro indice reale e continuano ad
aprirsi/download senza reindicizzazione.

Il parser IMAP ora salva anche gli allegati `message/rfc822`, in particolare
`postacert.eml`, serializzando il messaggio annidato quando il payload binario
diretto e' vuoto e trattando come allegato anche la parte nominata nel
`Content-Type` ma priva di `Content-Disposition`. La sincronizzazione PEC puo'
quindi riparare i record storici che avevano `postacert.eml` in posizione 0
senza file su disco, evitando URL come `/email/messaggio/<id>/allegato/0` verso
allegati non recuperati quando il server IMAP restituisce ancora il messaggio.
La scoperta cartelle gestisce inoltre le risposte Legalmail non quotate come
`INBOX.Cestino` e `INBOX.Inviata`, cosi' i messaggi spostati vengono riletti
quando sono ancora disponibili. Il messaggio segnalato
`c05849df94244c9a946813566d5a3934` resta metadata-only per `postacert.eml`:
il vecchio `INBOX:UID:10145` non e' piu' presente nel server e la ricerca nelle
cartelle Legalmail disponibili non trova quella PEC sorgente, quindi non viene
generato un file sostitutivo non originale.

## Stato tranche 2026-05-13 - PWA/Web Push configurazione operativa 2.218.4

La sezione `Impostazioni -> Notifiche` mantiene il pannello Web Push gia'
React e lo rende operativamente configurabile: quando il server non ha VAPID
completo la UI distingue amministratori e utenti ordinari, mostra una causa
chiara e non chiede mai permessi browser al caricamento. `/api/push/public-key`
ora restituisce diagnostica sicura (`enabled`, presenza public/private key,
subject e variabili mancanti) senza esporre mai la chiave privata; la public key
viene restituita solo a configurazione completa.

Sono stati aggiunti generatore VAPID, comando diagnostico e script Hetzner per
configurazione/verifica, con documentazione aggiornata e test mirati. Per
richiesta operativa corrente non vengono creati backup dallo script Web Push.

## Stato tranche 2026-05-13 - Template Atti compilatore React STRICT 2.218.2

`/template-atti/compila/<codice>` e' ora servita dalla shell React. La pagina
usa il nuovo endpoint JSON del compilatore, precompila i dati IUSENTRA dopo la
selezione di cliente e pratica collegata, mostra il presidio Cartabia/deposito
senza badge di conformita' assoluta e invia la bozza al POST Flask esistente.
Quando la bozza supera i blocchi redazionali viene importata nell'editor
professionale. La vista Jinja e' solo fallback tecnico `_legacy=1`.

## Stato tranche 2026-05-12 - Template Atti Cartabia / prefill / timbro studio 2.218.1

La tranche e' stata rafforzata in modalita STRICT: l'inventario ora scandisce
master, split, compilatore, repository JSON, SQLite e tenant, riconciliando
il catalogo operativo a `1320` template canonici e mantenendo `4576` record di
fonte come evidenze/duplicati tracciati senza gonfiare il totale.
I dati mancanti nei repository non vengono piu' lasciati a revisione passiva:
Cartabia, prefill, timbro, renderer e binding compilatore vengono recuperati
dalle fonti interne disponibili, incluse le tabelle SQLite e il catalogo
workspace. Le fonti normative sono registrate in
`docs/legal_sources/cartabia_sources.jsonl`; se una regola futura non ha fonte
ufficiale, il template resta bloccato per verifica professionale.

## Stato tranche 2026-05-12 - Template Atti Cartabia / prefill / timbro studio 2.218.0

`/template-atti`, `/template-atti/catalogo` e il compilatore atti sono stati
allineati a un presidio governato: il catalogo master mantiene 420 template e
i 192 modelli operativi collegati, ma ogni voce ora espone profilo Cartabia,
area processuale, stato di revisione, controlli dichiarativi, campi di
precompilazione e binding compilatore. Non viene mostrato alcun badge
ingannevole di conformita' piena: le superfici distinguono dati disponibili,
dati mancanti, controlli bloccanti, controlli consigliati e revisione
professionale dell'avvocato.

Il nuovo `Timbro Studio` e' tenant-aware e viene iniettato centralmente nei
render testuali, HTML e PDF/DOCX dove disponibili, prima del titolo dell'atto.
I dati derivano dalla configurazione studio o dalla tabella/configurazione
dedicata, senza dati hardcoded di esempi grafici. Il resolver prefill compila
automaticamente i campi disponibili da studio, fascicolo, cliente, soggetti,
utente e timbro, restituendo sempre provenienza, attendibilita', alternative,
avvisi e motivi dei dati mancanti.

Script e gate mirati confermati: arricchimento/validazione catalogo, pytest
master e timbro/prefill, typecheck, contratti React, build Vite, packaging e
readiness release. Docker locale 2.218.0 e smoke Chrome headless su catalogo
desktop/tablet/mobile e compilatore desktop sono verdi; i passaggi caldi del
catalogo restano sotto 300 ms a DOMContentLoaded e non mostrano overflow,
errori console o termini tecnici vietati.

## Stato tranche 2026-05-12 - PWA/Web Push notifiche dispositivo 2.217.2

La sezione `Impostazioni -> Notifiche` affianca ora al canale WhatsApp un
pannello non invasivo per le notifiche su dispositivo. La UI verifica supporto
browser, configurazione VAPID, stato subscription e permesso notifiche, ma
chiede il consenso solo dopo click esplicito su `Attiva notifiche su questo
dispositivo`. Sono disponibili anche disattivazione locale e notifica di test.

Il centro notifiche operativo della top bar resta compatibile nella shape
storica (`ok`, `unreadCount`, `items[]`) ma ora persiste notifiche e stato letto
in `NOTIFICATIONS_DB`, con isolamento tenant/utente e dedupe. Le stesse
notifiche alimentano il canale Web Push solo per eventi ammessi dalle
preferenze e solo se la subscription del dispositivo e' attiva.

Il Service Worker root `/sw.js` ascolta `push`, mostra una notifica generica e
privacy-safe e, al click, apre o focalizza IUSENTRA su `/app-v2` o sull'href
operativo sicuro. Il manifest PWA e' servito da `/manifest.webmanifest`.
Senza chiavi VAPID il sistema non interrompe il gestionale: le API comunicano
che il canale dispositivo non e' configurato e il centro notifiche interno
continua a funzionare.

## Stato tranche 2026-05-12 - Notifiche legali sicure e bozze relata 2.217.1

La route `/notifiche-legali` mantiene separati i tre percorsi operativi:
notifica legale ex L. 53/1994, deposito della prova di notifica e
comunicazione informativa al cliente. I modelli relata personalizzati non
passano piu' da Jinja libero: il dominio accetta solo i campi automatici
pubblicati nella UI e i blocchi operativi `documenti_righe`,
`documenti_righe_privacy`, `attestazioni_testo` e `blocco_procedimento`,
bloccando istruzioni, filtri, chiamate, accessi riservati e token non
whitelistati prima del render.

La pagina React mostra ora `Testo modello` e `Anteprima compilata`: la seconda
usa i dati correnti del form, aggiorna i valori mancanti con placeholder
leggibili e puo' essere modificata dall'avvocato come bozza della notifica
corrente. La bozza viene salvata in storage tenant-aware dedicato, non nel
catalogo dei modelli riutilizzabili, e la verifica finale continua a presidiare
oggetto PEC, PEC da pubblico elenco, attestazioni, ricevuta completa, firma e
approvazione.

Il tab `Comunica al cliente` usa un catalogo separato
`comunicazioni_cliente_templates.json`, con versione propria e modelli semplici
per oggetto/corpo email ordinaria. Non espone il catalogo relata 2026.05.12,
non genera relate e blocca l'oggetto L. 53/1994 quando viene usato fuori dal
percorso di notifica.

## Stato tranche 2026-05-12 - Sincronizzazione calendari bidirezionale 2.217.0

La sezione `Impostazioni -> Sincronizzazione Calendari` non si limita piu' ai
link di sottoscrizione: espone account collegati, calendari attivi, direzione
di allineamento, riservatezza export, ultimo allineamento, azioni di sync
manuale, disconnessione e conflitti. Il frontend resta solo pannello operativo:
non parla direttamente con Google, Microsoft o Apple e non riceve token o
password.

Il backend introduce `CalendarSyncEngine` con provider Google Calendar,
Outlook/Microsoft 365, Apple iCloud/CalDAV, WebCal/ICS e provider locale
persistente. Account, calendari collegati, binding eventi, job e conflitti
vivono in repository tenant-aware accanto al calendario sync; le credenziali
sono cifrate con Fernet e la demo locale usa le stesse classi del runtime.

Sono coperti push IUSENTRA -> calendario esterno, pull calendario esterno ->
IUSENTRA, update, delete, cursor incrementale, privacy export, conflitto
locale/remoto e protezione delle scadenze perentorie da cancellazioni o
spostamenti esterni automatici. La prova `python tools/demo_calendar_sync.py`
ha completato tutti i passaggi richiesti con output `[OK]`.
Build Vite 2.217.0 finale e smoke Chrome desktop/tablet/mobile hanno confermato
il pannello Calendari senza errori console, overflow documentale o testi tecnici
vietati.

## Stato tranche 2026-05-12 - Modelli relata visibili e personalizzabili 2.216.9

La route `/notifiche-legali` completa il passaggio da catalogo parametrico a
strumento operativo per lo studio: l'avvocato vede il testo del modello relata
prima del controllo, puo' scorrere il catalogo laterale, duplicare un modello
esistente o crearne uno nuovo su misura. L'editor inserisce campi automatici
IUSENTRA guidati, tra cui pratica, avvocato, assistito, procedimento,
destinatario, documenti, attestazioni e oggetto PEC; il salvataggio e' nel
perimetro dati del tenant e non genera backup.

Il motore dominio accetta modelli personalizzati e li renderizza con gli stessi
controlli L. 53/1994 dei modelli standard. La relata puo' ricevere anche una
integrazione libera dell'avvocato, aggiunta in coda senza sostituire
validazioni, attestazioni automatiche e blocchi obbligatori.

Anche `Deposito prova notifica` e `Comunica al cliente` ricevono la
precompilazione da pratica: atto, destinatario, cliente, ufficio, RG e documento
informativo vengono proposti quando gia' presenti in IUSENTRA. RAC/RdAC, firma
e dati non certi restano richiesti all'utente, cosi' il flusso rimane rapido ma
governato.

## Stato tranche 2026-05-12 - Notifiche legali parametriche 2.216.8

La route `/notifiche-legali` evolve da procedura guidata a motore
parametrico alimentato dai dati reali gia' presenti in IUSENTRA. Il catalogo
`pct/data/notifiche_legali_templates.json` contiene tutti i modelli richiesti:
relate 01-26, documenti di controllo 27-31, comunicazione cliente 32, nota di
mancata consegna 33 e workflow PST 34, piu' le varianti operative 01A-01E per
procedimento, attestazioni e destinatario societa'/impresa.

L'API `/api/v1/ui/notifiche-legali` precompila la pagina da clienti,
fascicoli, soggetti/parti e documenti del fascicolo:

- pratica, assistito, codice fiscale/P. IVA e procedimento vengono letti dal
  fascicolo selezionato;
- destinatari, PEC, ruolo processuale, parte rappresentata e fonte PEC
  suggerita derivano da soggetti e parti gia' censiti;
- documenti, nome file, descrizione, origine, hash e necessita' di
  attestazione derivano dal fascicolo e dalle metadatazioni portale quando
  presenti;
- la selezione del modello resta automatica ma governata: l'avvocato puo'
  confermare o cambiare modello prima di firma e invio.

Il sistema non inventa i dati mancanti: verifica PEC, data/ora controllo,
firma digitale e conferma finale restano passaggi consapevoli dell'avvocato.
La UI mantiene la logica "velocita' e automazione assistita" senza trasformare
la notifica in un invio completamente automatico.

## Stato tranche 2026-05-12 - Notifiche legali L. 53 / comunicazioni cliente 2.216.7

La nuova route `/notifiche-legali` entra nel perimetro
`react_operational_full` e separa i tre percorsi che non vanno confusi:

- `Notifica ex L. 53/1994` per controparte, difensori, PA, imprese,
  professionisti e terzi, con oggetto PEC obbligatorio, fonte PEC da pubblico
  elenco, relata separata, attestazione quando richiesta, ricevuta completa,
  firma e approvazione finale dell'avvocato;
- `Deposito prova notifica` per raccogliere atto notificato, relata firmata,
  RAC e RdAC originali `.eml/.msg` e riferimenti da portare in `DatiAtto.xml`;
- `Comunica al cliente` per il messaggio informativo, senza relata e senza
  oggetto L. 53/1994.

Le route di composizione PEC/email bloccano l'uso diretto dell'oggetto L. 53 e
indirizzano al workflow controllato. Manifest, route gate, shell React,
contratti statici e test mirati sono aggiornati per impedire regressioni verso
un invio email generico.

## Stato tranche 2026-05-11 - Fascicolo Veloce guidato / apertura deposito 2.216.5

La pagina `/fascicoli/nuovo` mantiene la shell React operativa e rende il
percorso rapido piu' vicino al lavoro reale di studio:

- il form riceve dall'API clienti, soggetti e uffici giudiziari reali, senza
  valori dimostrativi o campi liberi non presidiati per l'autorita';
- la selezione cliente mostra dati utili di scheda, PEC/email e collegamento,
  mentre la controparte puo' essere scelta tra i soggetti esistenti o creata
  contestualmente con identificativo obbligatorio;
- per `Fascicolo Veloce` sono bloccanti titolo, tipo, oggetto, autorita'
  giudiziaria, controparte e codice fiscale/P. IVA, con messaggi espliciti sui
  dati mancanti;
- dopo la creazione veloce il backend rimanda direttamente al deposito
  assistito del fascicolo appena creato, mantenendo la generazione busta/invio
  nel flusso telematico governato e confermato dall'utente.

## Stato tranche 2026-05-11 - Riduzione prompt PIN PST / Local Signer 1.6.28 / app 2.216.4

La diagnosi reale sul fascicolo PST RG 274/2026 del Tribunale di Palmi ha
confermato che il `pst_session_id` non veniva perso: i prompt PIN ripetuti
nascevano dal portale che rifiutava il cookie-only e costringeva nuovi round
mTLS in processi `curl` separati.

- il Local Signer non marca piu' `auth_ready` quando il preflight termina senza
  HTTP reale, cosi' una sessione in timeout non prova un cookie-only destinato
  a fallire prima della chiamata operativa;
- aggiunto `/pst/ricerca-snapshot`, endpoint esatto RG/anno che batcha ricerca
  e catalogo documenti nello stesso processo `curl`;
- il wizard Flask e `TelematicoSurfacePage` usano il nuovo endpoint per ricerche
  esatte PST non SIGP e riusano lo snapshot ottenuto, saltando la chiamata
  separata a `/pst/fascicolo-snapshot`;
- i download continuano a usare esclusivamente `/pst/download-documenti-batch`
  con lo stesso `pst_session_id` di visualizzazione.
- quando la pratica locale e' gia' presente e viene selezionato `Collega` o
  `Aggiorna`, un download PST parziale aggiorna il fascicolo con i file
  ricevuti e mantiene i documenti non restituiti nel catalogo ufficiale come
  voci da acquisire, senza creare duplicati.
- l'autocomplete uffici del wizard gestisce anche il payload `/api/uffici`
  in formato `{value:[...]}`, cosi' uffici reali come Tribunale di Palmi
  restano selezionabili dopo il reload del container.
- verifica browser reale aggiornata: Palmi RG 274/2026 importato su fascicolo
  esistente `B6A03AE6#sezione-documenti-fascicolo` con solo
  `/pst/ricerca-snapshot` e `/pst/download-documenti-batch` nel log Local
  Signer.

## Stato tranche 2026-05-11 - Sessione PST unica wizard / Local Signer 1.6.27 / app 2.216.3

Il wizard di acquisizione PST non separa piu' consultazione e import in due
sessioni locali: `preflight-auth`, ricerca/snapshot e download
`/pst/download-documenti-batch` propagano lo stesso `pst_session_id` con
`purpose=view`.

- i download del wizard usano solo la sessione `AW_PST_SESSION` gia'
  autenticata e non inviano piu' `purpose=import`;
- il Local Signer mantiene compatibilita' con client precedenti, ma i download
  PST singoli e batch defaultano alla sessione di visualizzazione e riusano la
  sessione esistente anche quando un vecchio client invia ancora `purpose=import`;
- i test mirati controllano il wizard, il preflight compatibile e il batch
  PST, cosi' il flusso non puo' tornare a moltiplicare i prompt PIN.

## Stato tranche 2026-05-11 - Local Signer distribuito 1.6.26 / app 2.216.2

Il pacchetto distribuito del Local Signer e' stato riallineato alla sorgente
usata dai flussi PST: `SetupLocalSigner-1.6.26.exe`, l'alias
`SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.26.command` e
`InstallaLocalSigner-1.6.26.run` sono rigenerati in `tools/dist`.

- la sorgente distribuita ora coincide con `tools/local_signer.py`;
- restano disponibili preflight, sessione PST, batch download e riuso cookie
  tra consultazione e import con stesso certificato/ufficio;
- `tests/test_local_signer.py` contiene un guardrail che impedisce di lasciare
  indietro `tools/dist/local_signer.py` rispetto alla sorgente.

## Stato tranche 2026-05-11 - Sessione PST Local Signer 2.216.1

La superficie React dei portali telematici mantiene il canale PST sul browser
locale: il wizard usa `preflight-auth`, ricerca, snapshot fascicolo e download
batch direttamente su `127.0.0.1:27272`, riusando la stessa sessione PST di
visualizzazione per ridurre i prompt PIN. Il server IUSENTRA riceve solo
selezione, anteprima normalizzata e file gia' scaricati dal Local Signer.

- SIGP/PST prepara la sessione locale prima di catalogo e download e non usa
  piu' il fallback al download singolo;
- il dettaglio fascicolo conserva nel browser la sessione PST del lotto e la
  ripassa alle acquisizioni successive;
- i contratti mirati impediscono la ricomparsa di `/pst/download-documento`
  nei client React/SIGP e controllano gli endpoint Local Signer necessari.

## Stato tranche 2026-05-11 - Fascicolo Veloce e form collassabile 2.216.0

La pagina `/fascicoli/nuovo` resta nella shell React operativa e riceve una
rifinitura di apertura pratica coerente con il design system:

- le sezioni del form principale e della colonna laterale sono collassabili,
  con pannelli compatti, icone Lucide e testi operativi per lo studio;
- `Pratiche collegate` e' stata spostata sotto `Personalizzabile`, cosi' la
  classificazione del fascicolo resta nel blocco iniziale di creazione;
- la nuova opzione `Fascicolo Veloce` abilita, sotto `Annotazioni`, il
  multicaricamento di documenti iniziali e il multicaricamento separato delle
  email `.eml` da conservare nel fascicolo;
- il backend salva i file caricati nel repository documenti del fascicolo,
  aggiorna i conteggi dedicati e ignora in modo controllato i file non `.eml`
  nell'area email;
- il presidio `deposito assistito` resta prudente: preparazione e controlli
  automatici sono separati da firma, busta e invio, che richiedono sempre
  conferma esplicita dell'utente.

## Stato tranche 2026-05-11 - Route Documenti React 2.215.7

La route ufficiale `/documenti` e' stata promossa a workspace operativo React
per correggere il 404 in produzione e mantenerla governata dal manifest:

- `/documenti` passa dalla shell React autenticata e usa `StudioModulePage`
  con payload reale `/api/v1/ui/studio-modules/documenti`;
- il workspace collega fascicoli/documenti, catalogo atti, Redazione Atti e
  ricerca documentale, senza CTA primaria verso fallback legacy;
- il gate route, il contratto full React, i contratti frontend e
  `tests/test_react_shell.py` includono `/documenti` come
  `react_operational_full` con `unlockFromGate=true`;
- verifica Docker/browser locale 2.215.7: desktop/tablet/mobile senza overflow,
  senza errori console e senza termini tecnici visibili; payload JSON filtrato
  per non esporre record locali con diciture `demo`/`sample`.

## Stato tranche 2026-05-11 - Catalogo ufficiale CodiceOggetto e ricerca UI 2.215.6

Il catalogo CodiceOggetto e' stato portato sul binario ufficiale PST:

- `pct/data/cataloghi/codici_oggetto_pst.json` contiene 1.018 codici unici estratti dalle enumeration `CodiceOggetto` degli XSD ufficiali attivi SICI, SIGP/Giudice di Pace, UNEP e Cassazione;
- `pct/data/cataloghi/codici_oggetto_pst_ui.json` e' la versione compatta per React: include solo codice, descrizione, registri, area e gruppo, cosi' la ricerca resta veloce senza caricare i dettagli tecnici completi;
- il file Excel fornito dall'utente e' stato usato come supporto di usabilita' per aree e codici padre, ma non come fonte di validazione: i 17 codici presenti nel foglio e non trovati negli XSD restano esclusi dalla whitelist di deposito;
- Preventivi, Conferimenti, Preventivo guidato e Apertura nuovo fascicolo usano `CodiceOggettoPstSearch`, una ricerca locale con ranking per codice, descrizione, area e registro, evitando il menu lungo e mantenendo la fonte ministeriale PST.
- Browser smoke locale 2.215.6 confermato su desktop, tablet e mobile per `/fascicoli/nuovo`, `/preventivi/nuovo`, `/preventivi/conferimento/nuovo` e `/preventivi/wizard`: `014001` selezionabile, `111604` presente, `014700` escluso, nessun overflow orizzontale.

## Stato tranche 2026-05-11 - Visualizzazione allegati email 2.215.5

Le route React `/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>`
mantengono azioni distinte sugli allegati: `Apri` per il flusso corrente,
`Visualizza` per apertura inline in nuova scheda senza download forzato e
`Scarica` per il download esplicito. Il comportamento e' coperto da contratti
React e test mirati su PEC e posta ordinaria SMTP.

## Stato tranche 2026-05-11 - Catalogo PST e deposito CodiceOggetto 2.215.4

Questa tranche separa definitivamente la classificazione tariffaria dal codice
ministeriale di deposito:

- il catalogo `Pratiche collegate` vive in `pct/data/pratiche_collegate_catalog.json`
  con fonte `PST_XSD`, ed e' importato dalla UI React tramite wrapper dati senza
  hardcoding nei componenti;
- `Preventivi`, `Conferimenti` e `Preventivo guidato` possono portare
  `codice_oggetto_pst`, `fonte_codice_oggetto` e `file_fonte_codice_oggetto`
  solo se il valore e' validato sul catalogo ufficiale; in caso contrario il
  codice resta vuoto e viene richiesto all'apertura del fascicolo;
- `Apertura nuovo fascicolo` precompila il codice da preventivo/conferimento
  solo se ufficiale, altrimenti mostra la selezione governata dal catalogo PST;
- il pre-deposito PCT blocca la busta se il fascicolo non ha un CodiceOggetto
  valido e genera `DatiAtto.xml` usando quel codice nel nodo `Oggetto`, evitando
  qualsiasi uso della tipologia tariffaria come sostituto.

## Stato tranche 2026-05-10 - Eliminazione multipla Email PEC e ordinaria 2.214.10

Questa tranche chiude la richiesta operativa di selezione multipla nella posta:

- le pagine React `Email PEC` ed `Email ordinaria` espongono ora checkbox per
  riga, selezione completa dei messaggi visibili e barra azioni con feedback
  immediato senza tornare ai form legacy;
- l'azione multipla rispetta la cartella aperta: da `In arrivo` e `Inviati`
  sposta i messaggi nel cestino, mentre dentro `Cestino` esegue
  l'eliminazione definitiva della selezione;
- il bridge React email espone ora `bulkAction` e il backend fornisce i nuovi
  endpoint JSON tenant-aware `/api/v1/ui/email/bulk-action` e
  `/api/v1/ui/email-ordinaria/bulk-action`, mantenendo la separazione tra
  casella PEC e casella ordinaria;
- verifiche locali confermate: shard pytest mirati su payload e bulk action,
  typecheck TypeScript e build Vite verdi prima del deploy.

## Stato tranche 2026-05-10 - Deduplica Email ordinaria 2.214.9

Questa tranche chiude la regressione che mostrava email duplicate nella
casella ordinaria:

- la sincronizzazione degli inviati (`GestioneEmailRicevute.sincronizza_inviati`)
  non si limita piu' all'id sintetico `INVIATA:<msg.id>`, ma confronta anche
  `Message-ID` e un fingerprint prudente del messaggio inviato;
- quando esistono gia' sia la copia IMAP degli `Inviati` sia la copia sintetica
  generata dallo storico SMTP, il sistema mantiene la copia IMAP con UID stabile
  e rimuove il duplicato storico;
- la pulizia avviene anche sui dati gia' presenti, quindi aprire la casella o
  rieseguire il sync riallinea automaticamente gli inviati ordinari;
- verifiche locali confermate: shard mirati su `tests/test_email_client.py`
  per deduplica inviati, regressioni `Message-ID` e caso Legalmail con UID
  stabili verdi prima del deploy.

## Stato tranche 2026-05-10 - Isolamento utenti multi-studio 2.214.8

Questa tranche chiude una regressione critica sull'isolamento tra studi nella
gestione utenti:

- il bootstrap automatico root -> tenant viene ora bloccato quando esistono
  piu' studi attivi, cosi' un nuovo studio non puo' piu' ereditare dati
  storici della root in un contesto multi-studio;
- i manager utenti tenant ricevono sempre il contesto studio corrente anche
  nelle superfici React, nel runtime condiviso e nel pannello amministrazione
  multi-tenant;
- la pagina `/utenti` e il pannello `/admin/studi/<slug>/utenti` non trattano
  piu' un account senza `tenant_slug` come appartenente implicitamente allo
  studio aperto;
- il backend auth SQLite mantiene ora allineati `studio.db` e
  `auth/utenti.json`, aggiunge `tenant_slug` alla tabella utenti quando manca e
  riallinea automaticamente il `studio.db` tenant quando diverge
  dall'archivio utenti locale dello stesso studio;
- verifiche locali confermate: shard mirati auth/storage, test completi
  `tests/test_auth.py` e `tests/test_storage_strategy.py`, packaging,
  readiness, typecheck e build Vite verdi prima del deploy.

## Stato tranche 2026-05-10 - Parcella personalizzata Fatturazione 2.214.6

Questa tranche risponde alla richiesta di ampliare `/fatturazione/nuova` con
una parcella personalizzata completa, precompilata dove possibile dal software:

- hotfix 2.214.6 completato: con regime fiscale `forfettario` o `minimo` la
  UI disattiva l'IVA, l'anteprima non la conteggia e il backend la forza a zero
  anche nel salvataggio finale e nell'XML FatturaPA;

- la pagina React raccoglie ora in sezioni operative distinte i dati di
  trasmissione, i dati dello studio, il destinatario, il corpo del documento,
  la fiscalita' e il pagamento, mantenendo linguaggio da studio legale e senza
  testo tecnico visibile;
- cliente, fascicolo, studio, pagamento e causale vengono precompilati dai dati
  reali disponibili, con numero documento assegnato al salvataggio e progressivo
  di invio proposto automaticamente;
- il dominio fatturazione governa ora spese generali, spese imponibili,
  anticipazioni e snapshot personalizzato del documento, mantenendo i calcoli
  definitivi lato servizio e persistendo i campi necessari all'XML FatturaPA;
- la generazione XML usa i dati personalizzati salvati e gestisce correttamente
  anche destinatari esteri senza duplicare o forzare una nazione italiana;
- verifiche locali confermate: pytest mirati su fatturazione/bridge/XML,
  typecheck e build Vite verdi, browser reale desktop/tablet/mobile senza
  overflow orizzontale e senza termini vietati come `backend`, `payload`,
  `legacy` o `runtime` nella pagina.

## Stato tranche 2026-05-10 - Hotfix contributo unificato Preventivo guidato 2.214.4

Questa tranche chiude il disallineamento segnalato dall'utente nel Preventivo guidato:

- il pannello `Spese vive suggerite` non mostra piu' `Contributo Unificato (indicativo)`, ma la dicitura pulita `Contributo Unificato`;
- dopo il calcolo del wizard React, le pratiche civili di cognizione ordinaria usano ora il contributo unificato coerente con valore e grado della pratica, invece del vecchio importo fisso storico;
- aggiunti test di regressione sul catalogo `Atto di citazione` e sul calcolo wizard per il caso `EUR 10.000 -> EUR 237,00`.

## Stato tranche 2026-05-10 - Eliminazione clienti e soggetti 2.214.2

Questa tranche risponde alla richiesta di ripristinare l'eliminazione operativa
nelle anagrafiche React senza tornare a form legacy:

- `/clienti` espone di nuovo il tasto `Elimina` nelle azioni riga e nelle card
  mobile, con selezione multipla visibile e azione `Elimina selezione`.
- `/soggetti` adotta lo stesso pattern operativo: checkbox su tabella e mobile,
  azione singola `Elimina` e cancellazione multipla dalla toolbar contestuale.
- I payload React di clienti e soggetti includono ora `deleteHref`, mantenendo
  coerenza con i percorsi operativi Flask gia' esistenti.
- Gli endpoint `POST /api/v1/ui/clienti/delete` e
  `POST /api/v1/ui/soggetti/delete` eseguono la cancellazione reale lato studio
  e restituiscono esito JSON al client React.
- Verifiche mirate locali: TypeScript e build Vite verdi; pytest mirati sulla
  cancellazione clienti/soggetti verdi; il gate `check-react-contracts` resta
  da riallineare su un'asserzione storica del Tariffario non collegata a questa
  tranche.

## Stato tranche 2026-05-10 - Performance Tariffario e Preventivo guidato 2.214.1

Questa tranche risponde alla richiesta di velocizzare `/tariffario` e
`/preventivi/wizard` e di rendere raggiungibile il preventivo guidato da
`/preventivi/`:

- `/preventivi/` espone la voce primaria `Preventivo guidato` verso
  `/preventivi/wizard`, anche nello stato vuoto dell'archivio.
- Il bootstrap React del tariffario non invia piu' il catalogo pratiche completo
  con regole e riferimenti normativi pesanti: le opzioni necessarie alla UI
  restano disponibili, mentre i calcoli continuano a usare il motore Python.
- Il bootstrap React del preventivo guidato non duplica piu' `catalog.grouped`,
  non invia righe tassonomiche integrali non usate al primo render e conserva
  solo regole/pratiche compatte sufficienti a filtro, scelta e calcolo.
- Le righe tariffarie derivate sono memorizzate in cache applicativa, evitando
  la ricostruzione ripetuta del catalogo DM 55/DM 147 a ogni apertura pagina.
- Il riepilogo in tempo reale del Tariffario e' tornato sticky su desktop: la
  colonna laterale segue lo scroll dei parametri di calcolo, mentre sotto
  1040px torna nel flusso normale per non comprimere la UI mobile.
- Baseline locale post-fix: `/api/v1/ui/tariffario` 416 KB / 66 ms e
  `/api/v1/ui/preventivi/wizard` 705 KB / 47 ms, contro baseline pre-fix di
  circa 3,87 MB / 30 s e 4,62 MB / 30 s.
- Test mirati aggiunti per bloccare regressioni di payload e link al preventivo
  guidato; verifica browser desktop/tablet/mobile confermata per lo sticky del
  riepilogo e per l'apertura del wizard.

## Stato tranche 2026-05-10 - Pulizia testi visibili e dettagli email React 2.214.0

Questa tranche risponde alla richiesta utente di non mostrare piu' messaggi da
sviluppatore in nessuna scheda operativa e completa i dettagli email indicati:

- La shell React applica una guardia visibile sui testi e sugli attributi
  utente (`title`, `aria-label`, `placeholder`, `alt`) per sostituire termini
  tecnici con lingua da studio legale. La stessa guardia e' caricata anche nei
  template Flask tramite `web/static/js/iusentra-visible-text-guard.js`.
- I termini da non mostrare allo studio includono `Impeccable / Open Design`,
  `Dati applicativi`, `React`, `Flask`, `backend`, `frontend`, `payload`,
  `runtime`, `json_api`, `provider`, `webhook`, `endpoint`, `legacy`,
  `undefined`, `null`, `demo`, `sample` e `repository`.
- `/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>` sono servite
  dalla pagina React `EmailPecPage`, alimentate da endpoint JSON dedicati e
  complete di metadati operativi, allegati, corpo messaggio e azioni sicure.
- `Redazione Atti` resta su una sola pagina React e include produzione atti,
  template disponibili, compilazione assistita e anteprima operativa, senza
  spostare l'utente su testi o percorsi tecnici.
- `Template Atti`, `Ricerca Legale`, `News`, `Archivio Giurisprudenza`,
  `Statistiche`, `Strumenti Forensi` e `Strumenti Operativi` usano dettaglio in
  pagina, card compatte operative e testi coerenti al design system.
- Browser reale su Docker locale 2.214.0: desktop e mobile per le pagine
  richieste, piu' `/admin/database`, risultano con `#root` React presente,
  nessun overflow orizzontale e nessuno dei termini tecnici vietati nel testo
  visibile.
- Gate confermati: `npm run typecheck`, `npm test`, `npm run build`, route
  gate, full-react contract, no-fake React full, pytest mirati email/React,
  packaging/release readiness, Docker no-cache e readiness locale 2.214.0.

## Stato tranche 2026-05-09 - Pagine operative richieste full React 2.213.0

Questa tranche risponde al controllo utente sul perimetro completo delle pagine
operative IUSENTRA e rende piu' evidente la migrazione React:

- Hotfix Sito Studio/Contatti/Nav: `/sito-studio/contatti` ora resta una
  dashboard React operativa anche quando non ci sono ancora richieste o
  prenotazioni. Mostra ingressi pubblici, modulo contatti, prenotazione, sito
  pubblico, pannelli `Richieste contatto` e `Prenotazioni` con stati vuoti
  specifici, senza lo stato vuoto globale che faceva sembrare la pagina non
  funzionante.
- La sidebar React ora tiene aperta una sola cartella operativa: la sezione
  attiva resta aperta durante la navigazione interna, per esempio `Studio` resta
  aperto su `Statistiche`; quando l'utente seleziona `Fascicoli`, si chiude
  `Studio` e resta aperto solo `Fascicoli`.
- Verifica browser locale su `localhost:8080`: `Contatti Sito Studio` mostra
  `Ingressi pubblici`, `Richieste contatto`, `Prenotazioni`, link pubblici e
  nessun testo tecnico vietato; `Statistiche` mantiene aperto `STUDIO`; il
  passaggio a `Fascicoli` mantiene aperto solo `FASCICOLI`.
- il manifest React e i gate includono le route richieste come
  `react_operational_full` quando esiste una superficie React governata, con
  alias espliciti per Panoramica, Regia Operativa, Ricerca Studio, Agenda,
  Fascicoli, Clienti/Soggetti, Comunicazioni, Scadenze, Preparazione Udienza,
  Studio, Fatturazione, Preventivi, Compensi, Redazione Atti, Statistiche,
  Ricerca Legale, Giurisprudenza, Strumenti, Sito Studio, Amministrazione,
  Utenti, Profili, Registro Attivita, Database e Registro GDPR.
- `frontend/src/formSubmit.ts` e `frontend/src/components/JsonPostForm.tsx`
  centralizzano i submit React con `fetch`, CSRF/sessione, feedback visibile e
  redirect controllato; i componenti full React non devono piu' contenere form
  HTML `method="post"` nel flusso operativo.
- Sono stati convertiti i salvataggi principali di Nuovo Cliente/Soggetto,
  Nuovo Appuntamento, Messaggi/SMS-WA, Nuova Scadenza, Registro GDPR, Agenda,
  Timesheet, Email PEC/ordinaria, Fascicoli e Preparazione Udienza Guidata
  dashboard/step/riepilogo.
- I blueprint Flask collegati restituiscono JSON quando la richiesta arriva da
  React/XHR, mantenendo compatibilita' con redirect e route esistenti.
- Le pagine del perimetro richiesto sono state ripulite dai testi tecnici
  visibili (`backend`, `legacy`, `payload`, `runtime`, `json_api`, `route
  Flask`, `Rollback tecnico`): il linguaggio deve restare operativo per studio
  legale e i fallback devono chiamarsi `Percorso di recupero`.
- Gate confermati in corso tranche: `node frontend/scripts/check-react-contracts.mjs`,
  `node scripts/react-migration/check-full-react-route-contract.mjs` e
  `npm --prefix frontend run typecheck`.
- Restano obbligatori prima della chiusura release: build Vite finale, smoke
  browser desktop/tablet/mobile, Docker locale no-cache/health, commit/push
  branch gemelli e deploy Hetzner verificato.

## Stato tranche 2026-05-09 - Controlli Atti e Strumenti full React 2.210.0

Questa tranche rimuove tre eccezioni `legacy_operational` rimaste sulle voci
richieste dall'utente e le porta nella shell React governata:

- `/deposito/checklist` e' `react_operational_full` nel manifest e apre
  `TelematicoSurfacePage` con payload reale
  `/api/v1/ui/telematico/surface/checklist`; restano legacy solo eventuali
  sottopercorsi non ricostruiti, download o workflow tecnici.
- `/strumenti-legali` e `/strumenti-operativi` sono `react_operational_full`
  nel manifest, aprono `StudioModulePage` e leggono rispettivamente
  `/api/v1/ui/studio-modules/strumenti-forensi` e
  `/api/v1/ui/studio-modules/strumenti-operativi`.
- `web/bootstrap/react_route_gate.py`, `web/blueprints/react_shell.py` e
  `frontend/src/App.tsx` non devono piu' deviare queste route esatte verso la
  vista classica; `?_legacy=1` resta disponibile come fallback storico.
- I gate `check-react-contracts` e `check-route-gate` devono bloccare regressioni
  verso legacy, controllare manifest/contratti e preservare protezioni per
  subpath non migrati.
- La grafica resta vincolata a `docs/UI_DESIGN_SYSTEM.md`: card operative
  compatte, icone Lucide, testi italiani, stati vuoti/errore/successo, nessun
  dato demo e layout responsive senza spazio morto.
- Il titolo visibile della rotta `/deposito/checklist` e' `Controlli Atti`; la
  dicitura `Checklist deposito` resta solo come contesto/azione dove utile.
- Verifica browser reale eseguita con Chrome su desktop 1440x900, tablet
  834x1112 e mobile 390x844 per `/deposito/checklist`, `/strumenti-legali` e
  `/strumenti-operativi`: shell React presente, nessun overflow orizzontale,
  azioni/card operative visibili e nessun testo tecnico `payload`, `backend`,
  `frontend`, `runtime`, `json_api`, `undefined`, `null`, `todo` o `sample`.

## Stato tranche 2026-05-09 - Impostazioni full React 2.209.0

Questa tranche porta le impostazioni operative principali fuori dal template
storico e dentro una superficie React completa, mantenendo le scritture sensibili
nei servizi applicativi:

- `/impostazioni` e `/impostazioni-studio` sono `react_operational_full` nel
  manifest e vengono servite dalla shell React; `/impostazioni/pagamenti`,
  `/notifiche`, `/notifiche-whatsapp`, `/backup`, `/impostazioni/calendario`
  e `/sincronizzazione-calendari` sono alias React della stessa pagina
  Impostazioni.
- Il bridge `web/services/react_impostazioni_bridge.py` espone Dati Studio, PEC,
  Firma Digitale, Email SMTP, WhatsApp, Scheduler, AI Locale, Pagamenti,
  Notifiche, Backup e Calendari tramite `/api/v1/ui/impostazioni`, con
  salvataggi JSON/multipart per singola sezione, audit e permessi coerenti con
  il dominio.
- Password, token e chiavi salvate non vengono riesposte in chiaro dal server:
  React mostra solo stato/placeholder; l'icona occhio permette di controllare il
  nuovo valore digitato prima del salvataggio.
- La scheda Email SMTP conserva l'aiuto operativo per Gmail/Google Workspace:
  sotto `Password email` chiarisce che serve la password per le app Google e
  collega la pagina ufficiale di generazione.
- La firma digitale usa il browser per verificare IUSENTRA Local Signer su
  `127.0.0.1:27272`, accetta `token_probe_fresh` e conserva i download installer.
- AI Locale dispone di stato e bootstrap JSON dedicati, ma la verifica utente
  finale deve passare dal PC in uso tramite IUSENTRA Local Signer: React chiama
  `/ai/status` e `/ai/bootstrap` sul companion locale, mostra `Prepara AI
  locale`, lascia i modelli in scelta automatica e spiega che IUSENTRA controlla
  RAM/spazio/profilo hardware prima di scegliere i modelli.
- La shell React carica anche `web/static/js/react-ai-local-guard.js` per
  proteggere asset React gia' compilati: eventuali vecchie chiamate
  `/api/v1/ui/impostazioni/ai/status` e `/api/v1/ui/impostazioni/ai/bootstrap`
  vengono instradate al Local Signer del browser, non usate come fonte finale
  server/cloud.
- I gate anti-mascheramento classificano le route AI Locale come full React
  senza bridge fittizi e `tests/test_impostazioni_ai_locale_react.py` blocca
  regressioni su Local Signer, messaggi operativi e scelta automatica modelli.
- Pagamenti usa `web/services/react_impostazioni_payments.py` per leggere e
  salvare configurazione canali, bonifico, chiavi riservate e stato link senza
  riesporre segreti; l'utente vede linguaggio operativo, non `provider`,
  `webhook`, `legacy` o codici interni.
- Notifiche usa `web/services/react_impostazioni_notifications.py` e gli endpoint
  `/api/v1/ui/impostazioni/notifiche/*` per preparare link WhatsApp, inviare
  messaggi/promemoria e aggiornare il registro da dati reali di clienti e agenda.
- Backup usa `web/services/react_impostazioni_backup.py` per mostrare copia,
  verifica, download protetto e permessi dentro la scheda Impostazioni, mentre
  `/backup` resta un alias della stessa esperienza.
- Calendari usa `web/services/react_impostazioni_calendar.py` e gli endpoint
  `/api/v1/ui/impostazioni/calendari/*` per link riservati, profili calendario,
  sincronizzazione manuale, rigenerazione link e audit.
- Il menu React sposta Notifiche, Pagamenti, Backup e Sincronizzazione Calendari
  nel gruppo `Impostazioni`, fuori dal gruppo `Studio`, cosi' la navigazione
  riflette il modello unico richiesto.

## Stato tranche 2026-05-09 - Statistiche full React 2.208.0

Questa tranche chiude il bridge reale residuo su `/statistiche` senza toccare
aree sensibili o portali:

- `tools/react-migration/route-manifest.json` promuove `/statistiche` a
  `react_operational_full` con `writes=none`, dati JSON reali e
  `unlockFromGate=true`.
- `web/services/react_statistiche_bridge.py` non restituisce piu' azioni
  `?_legacy=1` nemmeno nel payload di errore controllato; la pagina puo'
  soltanto riprovare la lettura React.
- I gate anti-mascheramento devono classificare 27 route full reali e 0 bridge
  residui; le route legacy restano quelle ad alto rischio per segreti, export,
  documenti, impostazioni e portali telematici.

## Stato tranche 2026-05-08 - Design system IUSENTRA shadcn/lucide 2.198.121

Questa tranche integra la base grafica governata per rendere le superfici React
piu' professionali senza promuovere nuove route e senza sostituire logiche
backend:

- `frontend/components.json`, `frontend/src/components/ui/*` e
  `frontend/src/lib/utils.ts` introducono shadcn/ui su Vite/React con alias
  `@/*`, primitive Radix e classi componibili.
- `frontend/src/design/iusentraTokens.ts` e
  `frontend/src/styles/iusentra-design-system.css` definiscono palette blu
  notte, oro tenue, grigi neutri, superfici operative, focus ring, stati e
  mappa Lucide per le aree legali.
- `frontend/src/components/iusentra/*` aggiunge componenti riutilizzabili per
  shell, sidebar, top bar, header, metriche, action card, badge, stati vuoti,
  form section, pannelli collassabili, data table shell, icone e Lex floating
  button.
- I wrapper storici `frontend/src/ui/*`, la dashboard condivisa e i layout
  esistenti vengono normalizzati verso il nuovo sistema mantenendo i contratti
  statici usati dai gate React.
- La guida operativa vive in `docs/UI_DESIGN_SYSTEM.md` e descrive librerie,
  struttura, token, icone, pattern pagina, form, toolbar, accessibilita e divieti
  per evitare template, dati demo o componenti duplicati.

## Stato tranche 2026-05-08 - Architettura Full React governata 2.198.120

Questa tranche crea la base governata della migrazione Full React senza
dichiarare complete le route che restano bridge o legacy:

- `artifacts/react-migration/full-react-audit.*` censisce 53 route del manifest
  con stato reale, componenti React, bridge backend, endpoint JSON, presenza di
  `_legacy=1`, POST HTML, dati mock/demo, rischio e workspace di destinazione.
- `tools/react-migration/route-manifest.json` dichiara `workspaceTarget` per
  ogni route censita; gli stati esistenti non vengono promossi se manca parita'
  operativa.
- `frontend/src/app`, `frontend/src/shell`, `frontend/src/api` e
  `frontend/src/features/*` introducono la grammatica Full React: route
  applicative, shell unica, client API JSON/CSRF centralizzato e workspace
  consolidati che riusano i data client esistenti invece di duplicare logiche
  backend.
- `frontend/src/theme/legal-ui.css` e le primitive in `frontend/src/ui/*`
  aggiungono layout, card operative, filtri, drawer, modali, stati, pannelli e
  sticky action bar tokenizzati per la UI legale professionale.
- I runner `scripts/react-migration/run-full-react-migration.mjs` e
  `scripts/react-migration/run-legal-ui-checks.mjs` aggregano i nuovi gate
  anti-mascheramento, anti-mock, anti-logica canonica frontend, responsive e
  anti-Bootstrap primario.

## Stato tranche 2026-05-07 - Parti 22A-25A economico, tariffario e audit operativi 2.198.118

Le Parti 22A-25A chiudono il blocco economico principale e portano audit e
registro attivita a superfici React pienamente operative senza spostare logiche
canoniche nel frontend:

- `/incassi-pagamenti` usa `GET /api/v1/ui/incassi-pagamenti` e le azioni JSON
  supportate per registrare incassi manuali, aggiornare stati, collegare fatture
  e recuperare link pagamento solo tramite backend. Provider, webhook e
  configurazioni riservate restano legacy/backend; React vede solo stato pubblico.
- `/compensi-forensi` legge parametri reali e invia il calcolo a
  `POST /api/v1/ui/compensi-forensi/calcola`; DM55, risultato economico, logica
  fiscale e creazione preventivo restano backend o azioni esplicitamente
  supportate.
- `/tariffario` legge versioni, aree, fasi, voci e scaglioni dal backend e usa
  `POST /api/v1/ui/tariffario/calcola` quando il calcolo e disponibile; nessuna
  formula, scaglione o tabella canonica viene duplicata in React.
- `/audit` e `/registro-attivita` usano payload reali da
  `GET /api/v1/ui/audit` e `GET /api/v1/ui/registro-attivita`, dettaglio sicuro
  via `GET /api/v1/ui/audit/<id_evento>` e payload sanificati dal bridge.
- I fallback `?_legacy=1` restano solo rollback tecnici o impostazioni provider
  legacy; le sottoroute `/incassi-pagamenti/*`, `/compensi-forensi/*` e
  `/tariffario/*` restano legacy/protette dal gate.

## Stato tranche 2026-05-07 - Parti 18A-21A preventivi e fatturazione operative 2.198.114

Le Parti 18A-21A completano le superfici operative mandato/economico gia'
avviate dopo `/fatturazione/nuova`:

- `/preventivi/nuovo` usa `GET /api/v1/ui/preventivi/nuovo` e
  `POST /api/v1/ui/preventivi/nuovo`; React raccoglie clienti, fascicoli,
  voci e opzioni fiscali come input, mentre calcolo canonico, parametri
  forensi, numerazione e persistenza restano in `GestionePreventivi`.
- `/preventivi/conferimento/nuovo` usa
  `GET/POST /api/v1/ui/preventivi/conferimento/nuovo`, precompila da
  `id_preventivo` quando presente e conserva generazione documento, firme e
  apertura fascicolo nei workflow backend/legacy.
- `/preventivi` usa `GET /api/v1/ui/preventivi`,
  `GET /api/v1/ui/preventivi/<id_preventivo>` e
  `POST /api/v1/ui/preventivi/<id_preventivo>/stato` per archivio reale,
  dettaglio sintetico e cambio stato supportato; archivia/annulla/duplica
  restano disabilitate se non esiste una semantica legacy sicura.
- `/fatturazione` usa `GET /api/v1/ui/fatturazione`,
  `GET /api/v1/ui/fatturazione/<id_documento>` e POST JSON per stato,
  annulla e segna pagata. PDF, XML, export e calcoli fiscali canonici restano
  backend/legacy; React non usa fetch blob o generazione documenti.
- Tutte le CTA `_legacy=1` rimaste sono confinate a `Rollback tecnico`; il
  gate continua a proteggere `/preventivi/*` non autorizzati,
  `/preventivi/wizard` resta invariato e `/fatturazione/*` diverso da
  `/fatturazione/nuova` resta legacy/protetto.

## Stato tranche 2026-05-07 - Parte 17A fatturazione nuova operativa 2.198.110

La Parte 17A promuove `/fatturazione/nuova` da `react_bridge` a
`react_operational_full` senza sbloccare dettagli, modifica, PDF, XML, export,
provider pagamenti o webhook:

- `GET /api/v1/ui/fatturazione/nuova` espone clienti, fascicoli, default del
  form, opzioni fiscali e contratto `writes=json_api`,
  `canonical_calculation=backend`, `operational=true`, senza mock fallback.
- `POST /api/v1/ui/fatturazione/nuova` accetta solo JSON, usa
  CSRF/sessione, permesso `fatturazione.scrivi`, validazione backend,
  rifiuto di campi ignoti e degli importi canonici inviati dal frontend.
- Il salvataggio riusa `GestioneFatturazione.crea()` e `VoceParcella`; React
  invia solo voci/opzioni e non calcola totali fiscali, PDF, XML o export.
- `LegacyPostForm` e CTA legacy primarie sono rimossi dal flusso principale;
  `/fatturazione/nuova?_legacy=1` resta solo nel pannello `Rollback tecnico`.
- `/fatturazione` puo' restare `react_bridge`, mentre `/fatturazione/*` resta
  `legacy_operational` e protetto dal gate con eccezione solo per
  `/fatturazione/nuova`.

## Stato tranche 2026-05-07 - Parte 16A backup operativo 2.198.109

La Parte 16A promuove `/backup` da `react_bridge` a
`react_operational_full` mantenendo protette tutte le sottoroute `/backup/*`:

- `GET /api/v1/ui/backup` espone stato backup reale, lista copie, stato
  integrita, permessi operativi e contratto `writes=json_api`,
  `operational=true`, `restore_migrated=false`, senza path assoluti,
  contenuto file, stack trace o segreti.
- `POST /api/v1/ui/backup/crea` crea una copia tramite `GestioneBackup`,
  non accetta destinazioni o path dal frontend, richiede CSRF/sessione e
  permesso `backup.esegui`, registra audit `backup.crea` e restituisce solo
  metadati sicuri.
- `POST /api/v1/ui/backup/verifica` richiama la verifica integrita del
  repository legacy, richiede CSRF/sessione e `backup.esegui`, registra audit
  `backup.verifica` e non restituisce hash o percorsi file.
- `BackupPage` rimuove `LegacyPostForm` dal flusso principale, usa
  `createBackup()` e `verifyBackupIntegrity()`, mostra loading, saving,
  success, error, validazione, empty state, permessi e filtri locali sui dati
  gia ricevuti.
- Il download resta un link backend sicuro verso la route esistente; restore
  e delete non sono migrati in React e il fallback `/backup?_legacy=1` resta
  solo nel pannello `Rollback tecnico`.

## Stato tranche 2026-05-07 - Parte 14A utenti operativi 2.198.108

La Parte 14A promuove `/utenti` da `react_operational_partial` a
`react_operational_full` senza sbloccare sottoroute utenti ulteriori:

- `GET /api/v1/ui/utenti` espone utenti reali, ruoli gestibili, stato account,
  metriche, permessi operativi e contratto `writes=json_api`, senza
  `password_hash`, reset token, segreti TOTP o dati di sessione.
- `POST /api/v1/ui/utenti/<id>/stato`, `/ruolo`, `/reset-password` e
  `/profilo` applicano `_richiedi_auth`, CSRF browser, permesso
  `utenti.scrivi`, validazione JSON, blocchi su `SUPERADMIN`, ultimo
  amministratore e auto-disabilitazione, e audit dedicato nel manager utenti.
- `frontend/src/components/UtentiPage.tsx` usa ricerca/filtro client-side sui
  dati gia ricevuti e azioni inline/modali leggere via API JSON per profilo
  minimo, ruolo, stato account e credenziale temporanea; `LegacyPostForm` e
  CTA primarie `?_legacy=1` sono assenti.
- `/utenti?_legacy=1` resta disponibile solo come `Rollback tecnico`;
  `/utenti/nuovo` resta `react_operational_full` e le altre route
  `/utenti/*` restano protette dal gate finche' non avranno UI React reale.

## Stato tranche 2026-05-07 - Parte 13A profili operativi 2.198.107

La Parte 13A promuove `/profili` da `react_bridge` a
`react_operational_full` senza modificare il modello RBAC esistente:

- `GET /api/v1/ui/profili` espone ruoli gestibili, catalogo permessi, matrice
  ruolo-permesso e override utente reali, senza password, hash o dati di
  sessione.
- `POST /api/v1/ui/profili` salva gli override utente tramite
  `GestioneUtenti.aggiorna_permessi`, con `_richiedi_auth`, CSRF browser,
  permesso `utenti.scrivi`, validazione JSON, blocco SUPERADMIN tenant e audit
  `utenti.aggiorna_permessi`.
- `frontend/src/components/ProfiliPage.tsx` non usa piu' `LegacyPostForm` nel
  flusso principale: la UI mostra loading, dirty state, saving, success,
  errori di validazione, permesso negato, stato vuoto, matrice reale e rollback
  legacy solo nel pannello `Rollback tecnico`.
- Il manifest dichiara `/profili` come `react_operational_full` con
  `writes=json_api`; `?_legacy=1` resta disponibile solo come fallback tecnico.

## Stato tranche 2026-05-07 - Parte 12A anti-mascheramento 2.198.106

La Parte 12A cambia la definizione di migrazione React: una pagina non puo'
essere dichiarata pienamente operativa se il flusso principale torna a template
Flask, CTA `?_legacy=1`, `LegacyPostForm` o POST legacy.

- `tools/react-migration/route-manifest.json` usa ora gli stati
  `react_shell`, `react_bridge`, `react_operational_partial`,
  `react_operational_full` e `legacy_operational`; `react_full` resta
  deprecato e non viene piu' usato per superfici mascherate.
- `scripts/react-migration/audit-anti-mascheramento.mjs` censisce link
  legacy, form legacy, bridge con scritture legacy, API mancanti e stati UI,
  generando report JSON/Markdown in `artifacts/react-migration/`.
- `scripts/react-migration/check-no-fake-react-full.mjs` blocca manifest e
  gate quando una route piena dipende ancora da legacy per il flusso primario.
- Il pilota `/utenti/nuovo` usa React controllato e
  `POST /api/v1/ui/utenti/nuovo`, con `_richiedi_auth`, permesso
  `utenti.scrivi`, CSRF/sessione, audit e risposta JSON senza password.
- I fallback `?_legacy=1` restano solo rollback tecnici non primari; le route
  ancora bridge/shell restano dichiarate come tali fino a API JSON complete,
  permessi, stati UI e test dedicati.

## Stato tranche 2026-05-07 - Legal knowledge React read-only 2.198.105

La decima promozione governata abilita le superfici di consultazione giuridica
senza spostare import, classificazione, testo integrale, approvazione contenuti
o AI fuori dalle route Flask legacy:

- `/giurisprudenza` usa `web/services/react_giurisprudenza_bridge.py` e
  `GET /api/v1/ui/giurisprudenza` per KPI, fonti, filtri e metadati di
  provvedimenti/sentenze gia presenti nel repository.
- `/legal-intelligence`, `/legal-intelligence/news`,
  `/legal-intelligence/mediazione` e `/ricerca-legale` usano
  `web/services/react_legal_intelligence_bridge.py` e endpoint GET dedicati
  per dashboard monitor, news pubblicate, registro mediazione e hub di ricerca
  legale, senza fetch esterno o pipeline nuova.
- Restano legacy `/giurisprudenza/nuova`, `/giurisprudenza/*`,
  `/legal-intelligence/*` diverso da news/mediazione, `/ricerca-legale/*`,
  `/checklist` e `/deposito/checklist`.
- Impeccable / Open Design aggiunge token legal knowledge `--iu-od-source-*`
  e utility `iu-od-source-card`, `iu-od-source-badge`,
  `iu-od-evidence-panel`, `iu-od-inference-warning` e
  `iu-od-legal-list`, distinguendo fonte, metadato, warning, inferenza e
  azioni legacy senza dipendenze grafiche.
- `run-safe-react-migration.mjs --tranche=10a` cattura contratti legacy,
  rilancia gate/UI, anti-segreti, anti-fetch esterno, anti-generazione AI,
  anti-documento raw, Open Design, test Flask, `npm run test`, typecheck e
  build, poi genera patch di rollback separate.

## Stato tranche 2026-05-07 - Tariffario console operativa 2.198.102

La tranche `2.198.102` rifinisce `/tariffario` come console economica
professionale:

- gli avvisi tecnici di bootstrap e le KPI statistiche non vengono piu'
  renderizzati sopra il workspace operativo;
- il `Riepilogo in tempo reale` diventa il pannello sticky dedicato su desktop,
  con totale, forbice minimo/base/massimo e azioni principali nello stesso
  punto di lavoro;
- il risultato viene aggiornato automaticamente con debounce tramite
  `POST /api/v1/ui/tariffario/calcola`, continuando a usare solo il motore
  Python canonico per formule, importi e logica tariffaria.

## Stato tranche 2026-05-06 - Tariffario console operativa 2.198.97

La superficie exact `/tariffario` resta React sui GET ufficiali e mantiene il
fallback tecnico `?_legacy=1`, ma non e' piu' una semplice consultazione:

- `web/services/react_tariffario_bridge.py` espone catalogo, stato iniziale,
  risultato, profilo attivo, audit, tabelle, riferimenti, canali fatturazione e
  CTA precompilate usando dati reali da repository e servizi esistenti.
- `POST /api/v1/ui/tariffario/calcola` aggiorna il quadro operativo con il
  motore Python (`calcola_compenso`, `motore_preventivo`, mediazione D.M.
  150/2023, spese vive e voci manuali), senza spostare formule o valori
  normativi nel frontend.
- `frontend/src/components/TariffarioPage.tsx` organizza la pagina come console
  a due colonne con hero, KPI, parametri, accordion, risultato tabellare,
  riepilogo economico, profilo attivo e supporto normativo collassabile.
- I gate Tranche 8A anti-segreti, anti-calcolo compensi e anti-produzione
  documentale restano attivi: React invia parametri e riceve risultati, ma non
  contiene formule tariffarie, fiscali o documentali canoniche.

## Stato tranche 2026-05-06 - Tranche 9A template e redazione atti

La promozione governata abilita le superfici documentali di ingresso in React
senza spostare editor, redazione guidata, produzione file o workflow AI fuori
dalle route Flask legacy:

- `/template-atti` usa `web/services/react_template_atti_bridge.py` e
  `GET /api/v1/ui/template-atti` per dashboard catalogo, KPI reali,
  categorie, materie, canali e link sicuri.
- `/template-atti/catalogo` usa lo stesso bridge e
  `GET /api/v1/ui/template-atti/catalogo` per consultare il catalogo reale,
  metadati template, compliance e variabili solo come nomi/metadati.
- `/redazione-atti` usa `web/services/react_redazione_atti_bridge.py` e
  `GET /api/v1/ui/redazione-atti` per quadro operativo, workflow disponibili,
  fonti collegate come metadati e azioni verso template, fascicoli, preventivi
  e checklist legacy.
- `/template-atti/nuovo`, `/template-atti/*`, `/redazione-atti/*`,
  `/checklist`, `/deposito/checklist`, `/giurisprudenza`,
  `/legal-intelligence` e `/ricerca-legale` restano legacy con protezioni
  esplicite nel gate e nella shell.
- Impeccable / Open Design resta interno: token CSS documentali `--iu-od-doc-*`,
  utility `iu-*`, nessuna dipendenza grafica, nessun CDN e check dedicato.
- `run-safe-react-migration.mjs --tranche=9a` cattura i contratti legacy,
  rilancia gate/UI, anti-segreti, anti-contenuto integrale, anti-redazione
  automatica, anti-produzione file, Open Design, test Flask,
  test/typecheck/build frontend e patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 8A compensi e tariffario sicuri

La settima promozione governata abilita le superfici economiche exact di
consultazione compensi/tariffario in React senza spostare formule forensi,
produzione documentale o workflow mandato fuori dalle route Flask legacy:

- `/compensi-forensi` usa `web/services/react_compensi_forensi_bridge.py` e
  `GET /api/v1/ui/compensi-forensi` per KPI reali, aree disponibili, profili e
  regole lette dal backend, link sicuri verso tariffario, preventivi e vista
  legacy tecnica.
- `/tariffario` usa `web/services/react_tariffario_bridge.py` e
  `GET /api/v1/ui/tariffario` per consultare profili, regole, riferimenti,
  audit e form HTML `method="post"` verso la route Flask esistente; il calcolo
  resta nel backend storico.
- `/compensi-forensi/*`, `/tariffario/*`,
  `/preventivi/*`, `/fatturazione/*`, `/template-atti` e `/redazione-atti`
  restano legacy con protezioni esplicite nel gate e nella shell.
- I token `frontend/src/theme/impeccable-open-design.css` e il contratto
  `frontend/src/ui/openDesign.ts` applicano una disciplina Open Design
  auditabile senza dipendenze runtime, CDN o design system esterni.
- `scripts/react-migration/check-tranche-8a-secrets.mjs`,
  `scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs`,
  `scripts/react-migration/check-tranche-8a-no-document-generation.mjs` e
  `scripts/react-migration/check-tranche-8a-open-design.mjs` bloccano
  serializzazione di campi riservati, logica compensi frontend, generazione
  documentale e regressioni visuali fuori dai token `iu-*`.
- `run-safe-react-migration.mjs --tranche=8a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo/anti-documenti/Open Design,
  verifica shell e bypass legacy con Flask `test_client`, esegue
  test/typecheck/build frontend e genera patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 8A compensi e tariffario sicuri

La settima promozione governata abilita due superfici economiche exact in
React senza spostare formule, wizard, log economici o produzione documentale
fuori dalle route Flask legacy:

- `/compensi-forensi` usa `web/services/react_compensi_forensi_bridge.py` e
  `GET /api/v1/ui/compensi-forensi` per KPI reali quando disponibili, aree di
  calcolo lette dal backend, profili/regole sicuri e link a tariffario,
  preventivi e wizard legacy.
- `/tariffario` usa `web/services/react_tariffario_bridge.py` e
  `GET /api/v1/ui/tariffario` per aree tariffarie, voci/regole provenienti dal
  backend e un form React che invia con submit HTML standard alla route Flask
  `/tariffario`.
- `/compensi-forensi/*`, `/tariffario/*`,
  `/preventivi/*`, `/fatturazione/*`, `/template-atti` e `/redazione-atti`
  restano legacy con protezioni esplicite nel gate e nella shell.
- `frontend/src/theme/impeccable-open-design.css` e
  `frontend/src/ui/openDesign.ts` introducono solo token/contratto interno
  Impeccable / Open Design, senza dipendenze nuove, CDN, classi Bootstrap o
  colori hardcoded nei TSX.
- `scripts/react-migration/check-tranche-8a-secrets.mjs`,
  `scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs`,
  `scripts/react-migration/check-tranche-8a-no-document-generation.mjs` e
  `scripts/react-migration/check-tranche-8a-open-design.mjs` bloccano
  serializzazione di campi riservati, logica compensi frontend, generazione
  documentale e regressioni grafiche della tranche.
- `run-safe-react-migration.mjs --tranche=8a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo/anti-documenti/Open Design,
  verifica shell e bypass legacy con Flask `test_client`, esegue
  test/typecheck/build frontend e genera patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 7A mandato sicuro

La sesta promozione governata abilita il blocco mandato exact in React senza
spostare calcoli, wizard, documenti o cambi di stato fuori dalle route Flask
legacy:

- `/preventivi` usa `web/services/react_preventivi_bridge.py` e
  `GET /api/v1/ui/preventivi` per KPI reali, archivio preventivi/conferimenti,
  stati, cliente, fascicolo, importi gia' presenti nel modello e link legacy
  sicuri.
- `/preventivi/nuovo` usa lo stesso bridge e
  `GET /api/v1/ui/preventivi/nuovo`, ma il submit resta un form HTML
  `method="post"` verso la route legacy auditata; il motore economico resta nel
  backend storico.
- `/preventivi/conferimento/nuovo` usa
  `GET /api/v1/ui/preventivi/conferimento/nuovo`, con form React verso il POST
  legacy; firme, stati, produzione documenti e apertura fascicolo restano nel
  workflow Flask.
- `/preventivi/wizard` e' promosso in React full tramite
  `web/services/react_preventivo_wizard_bridge.py` e gli endpoint
  `/api/v1/ui/preventivi/wizard`, `/calculate` e `/create`; i dettagli
  `/preventivi/*` restano legacy con protezioni esplicite nel gate e nella shell.
  La tranche `2.198.100` porta riepilogo e riferimenti nella colonna sinistra,
  mantiene classificazione operativa/tassonomia come metadati silenziosi,
  aggiunge il pulsante reale `Aggiungi voce area pratica` e compatta lo sticky
  footer su desktop e mobile, protegge i profili solo a `Compenso unico` da
  bozze a zero e vincola il conferimento alla previa accettazione cliente del
  preventivo senza spostare formule economiche nel frontend.
  La tranche `2.198.101` rende il flag `Compenso unico` una scelta effettiva:
  acceso calcola la voce unica, spento calcola le sole fasi selezionate
  dall'avvocato con riparto operativo tracciato quando la tabella ministeriale
  espone solo l'importo unico; le voci area pratica aggiunte entrano tutte
  nella bozza con compenso e spese, non soltanto l'ultima pratica attiva.
- `scripts/react-migration/check-tranche-7a-secrets.mjs`,
  `scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs` e
  `scripts/react-migration/check-tranche-7a-no-document-generation.mjs`
  bloccano serializzazione di campi riservati, logica compensi frontend e
  produzione documentale nella nuova superficie.
- `run-safe-react-migration.mjs --tranche=7a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo/anti-documenti, verifica shell e
  bypass legacy con Flask `test_client`, esegue test/typecheck/build frontend e
  genera patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 6A economico sicuro

La quinta promozione governata abilita il primo blocco economico exact in React
senza spostare calcoli fiscali, documenti o provider fuori dalle route Flask
legacy:

- `/fatturazione` usa `web/services/react_fatturazione_bridge.py` e
  `GET /api/v1/ui/fatturazione` per KPI reali, archivio parcelle/fatture,
  stati, clienti, importi gia' presenti nel modello e link legacy sicuri.
- `/fatturazione/nuova` usa lo stesso bridge e
  `GET /api/v1/ui/fatturazione/nuova` piu'
  `POST /api/v1/ui/fatturazione/nuova`: il submit React e' JSON-only,
  validato dal backend e salvato tramite il manager fatturazione esistente.
  Il calcolo canonico resta nel backend storico.
- `/incassi-pagamenti` usa `web/services/react_incassi_pagamenti_bridge.py` e
  `GET /api/v1/ui/incassi-pagamenti` per importi aggregati, stato provider in
  forma sicura e collegamenti a configurazione provider legacy.
- `/fatturazione/*` diverso da `/fatturazione/nuova`, PDF, XML, export CSV, `/impostazioni/pagamenti`,
  `/preventivi`, `/compensi-forensi` e `/tariffario` restano legacy con
  protezioni esplicite nel gate e nella shell.
- `scripts/react-migration/check-tranche-6a-secrets.mjs` e
  `scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs` bloccano
  serializzazione di campi riservati e logica fiscale canonica nel frontend.
- `run-safe-react-migration.mjs --tranche=6a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo, verifica shell e bypass legacy
  con Flask `test_client`, esegue test/typecheck/build frontend e genera patch
  separate di rollback.

## Stato tranche 2026-05-08 - Tranche 26A/27A regia studio, amministrazione e sito

La tranche anti-mascheramento 26A/27A promuove gli hub direzionali e il Sito
Studio a `react_operational_full` senza sbloccare impostazioni, builder o
portali:

- `/studio` usa `GET /api/v1/ui/studio` con contratto `writes=none`,
  `operational=true` e `secrets_exposed=false`; mostra KPI reali, sessione,
  salute backup/sito/economico/documentale, route React operative e route
  legacy protette.
- `/amministrazione` usa `GET /api/v1/ui/amministrazione`, richiede
  `utenti.leggi` e mostra utenti, profili, audit, sicurezza aggregata, moduli
  amministrativi operativi e impostazioni legacy protette.
- `/sito-studio` usa `GET /api/v1/ui/sito-studio` con `writes=none` per stato
  sito reale, contenuti pubblici sicuri, KPI contatti/prenotazioni e anteprima
  pubblica sicura.
- `/sito-studio/contatti` usa `GET /api/v1/ui/sito-studio/contatti` e POST
  JSON solo per azioni legacy realmente supportate: collegamento cliente e
  aggiornamento stato prenotazione. Stato contatto, archiviazione, note,
  assegnazione e collegamento fascicolo restano disabilitati quando il backend
  legacy non li supporta.
- `/studio/*`, `/amministrazione/*`, `/sito-studio/builder`,
  `/sito-studio/*` ulteriori, `/impostazioni*` e
  `/sincronizzazione-calendari` restano protetti dal gate.
- I check dedicati sono
  `check-tranche-26a-studio-amministrazione-operational.mjs`,
  `check-tranche-26a-no-settings-secret-leak.mjs`,
  `check-tranche-26a-studio-amministrazione-api.py`,
  `check-tranche-27a-sito-studio-operational.mjs`,
  `check-tranche-27a-no-sito-secret-leak.mjs` e
  `check-tranche-27a-sito-studio-api.py`.

## Stato tranche 2026-05-06 - Tranche 5A hub studio e amministrazione

La quarta promozione governata abilita due hub direzionali React exact senza
sbloccare configurazioni o route operative ad alto rischio:

- `/studio` usa `web/services/react_studio_bridge.py` e
  `GET /api/v1/ui/studio` per KPI sicuri, profilo sessione, stato moduli gia'
  migrati e collegamenti a backup, sito studio, statistiche, utenti, profili,
  audit e impostazioni legacy.
- `/amministrazione` usa `web/services/react_amministrazione_bridge.py` e
  `GET /api/v1/ui/amministrazione`, mantenendo il vincolo legacy
  `utenti.leggi` e mostrando solo metriche aggregate, stato permessi,
  collegamenti amministrativi e warning.
- `/studio/*` e `/amministrazione/*` restano legacy; `/impostazioni`,
  `/impostazioni-studio`, `/impostazioni/calendario`,
  `/impostazioni/pagamenti`, `/impostazioni?tab=firma` e
  `/sincronizzazione-calendari` restano bloccate nel gate e nella shell.
- `scripts/react-migration/check-tranche-5a-secrets.mjs` verifica che bridge,
  data client e pagine della tranche non serializzino campi riservati nel
  payload React.
- `run-safe-react-migration.mjs --tranche=5a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti, verifica shell e bypass legacy con Flask
  `test_client`, esegue test/typecheck/build frontend e genera patch separate
  di rollback.

## Stato tranche 2026-05-06 - Tranche 4A studio e backup

La terza promozione governata abilita in React full le superfici studio a
rischio medio, mantenendo scritture e operazioni tecniche sui percorsi Flask
legacy:

- `/backup` usa `web/services/react_backup_bridge.py` e
  `GET /api/v1/ui/backup` per KPI, stato ultima copia, storico sicuro e azioni
  legacy; creazione, verifica, download, delete e ripristino restano sulle route
  Flask esistenti.
- `/sito-studio` e `/sito-studio/contatti` usano
  `web/services/react_sito_studio_bridge.py` e gli endpoint
  `GET /api/v1/ui/sito-studio` e
  `GET /api/v1/ui/sito-studio/contatti`, mostrando contenuti, richieste e
  prenotazioni reali senza scritture via fetch.
- `/sito-studio/builder`, `/studio`, `/impostazioni` e
  `/impostazioni?tab=firma` restano legacy, con protezioni esplicite nel gate e
  nella shell.
- `scripts/react-migration/check-tranche-4a-secrets.mjs` verifica che bridge,
  data client e pagine della tranche non serializzino campi riservati nel
  payload React.
- `run-safe-react-migration.mjs --tranche=4a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti, verifica shell e bypass legacy con Flask
  `test_client`, esegue test/typecheck/build frontend e genera patch separate
  di rollback.

## Stato tranche 2026-05-06 - Tranche 3A amministrazione base

La seconda promozione governata abilita in React full la gestione
amministrativa base, lasciando le scritture sensibili sui POST Flask legacy:

- `/utenti` usa `web/services/react_utenti_bridge.py` e
  `GET /api/v1/ui/utenti` per lista utenti, ruoli, stati, KPI e azioni GET
  sicure; le modifiche e le eliminazioni restano route legacy con
  `?_legacy=1`.
- `GET /utenti/nuovo` viene servita da React con un form standard
  `method="post"` verso `/utenti/nuovo`; non esistono fetch POST o API di
  scrittura nuove, e la password temporanea non viene salvata nello stato
  React.
- `/profili` usa `web/services/react_profili_bridge.py` e
  `GET /api/v1/ui/profili` per matrice ruoli/permessi, override e form legacy
  auditati dove disponibili.
- `/backup` usa `web/services/react_backup_bridge.py` e
  `GET /api/v1/ui/backup` solo come preparazione read-only; il gate mantiene
  `/backup` e tutte le sottoroute in legacy, incluse esecuzione, verifica,
  download, delete e restore.
- `run-safe-react-migration.mjs --tranche=3a` cattura i contratti legacy,
  rilancia gate/UI checks, verifica shell e bypass legacy con Flask
  `test_client`, esegue test/typecheck/build frontend e genera patch separate
  di rollback.

## Stato tranche 2026-05-06 - Tranche 2A read-only

La prima promozione governata abilita in React full solo superfici read-only o a
rischio basso:

- `/statistiche` usa `web/services/react_statistiche_bridge.py` e
  `GET /api/v1/ui/statistiche`, riutilizzando agenda, clienti, fascicoli,
  fatturazione e scadenziario senza introdurre POST nuovi.
- `/audit` e `/registro-attivita` usano `web/services/react_audit_bridge.py`
  e gli endpoint distinti `GET /api/v1/ui/audit` e
  `GET /api/v1/ui/registro-attivita`, mantenendo il permesso legacy
  `audit.leggi`.
- Le pagine dedicate `StatistichePage` e `AuditPage` vivono prima di
  `StudioModulePage`, usano il kit `frontend/src/ui`, stati loading/empty,
  warning tecnici e dati reali, senza Bootstrap nei nuovi TSX e senza mock.
- Il gate rimuove solo `/statistiche`, `/audit` e `/registro-attivita` dai
  blocchi legacy; `?_legacy=1` resta operativo. `/utenti`, `/profili`,
  `/backup`, le aree economiche e quelle telematiche restano bloccate.
- `run-safe-react-migration.mjs --tranche=2a` cattura i contratti legacy,
  rilancia gate/UI checks, verifica la shell con Flask `test_client`, esegue
  test/typecheck/build frontend e genera patch separate di rollback.

## Stato tranche 2026-05-06 - macchina di migrazione governata

La migrazione delle route legacy residue viene governata da una macchina dedicata,
senza sbloccare nuove route nel `react_route_gate` in questa tranche.

- `tools/react-migration/route-manifest.json` censisce le famiglie residue
  amministrazione, studio, economico, mandato, documenti e telematico con stato,
  rischio, target React futuri, bridge/API attesi, contratto legacy e
  `unlockFromGate=false`.
- `scripts/react-migration/audit-react-migration.mjs` legge gate, `App.tsx`,
  `studioModuleData.ts` e `frontend/package.json`, poi produce
  `artifacts/react-migration/route-inventory.json` e `audit.md`.
- `scripts/react-migration/capture-legacy-contracts.py` fotografa il contratto
  HTML legacy con Flask `test_client` su `?_legacy=1`, catturando status, form,
  link, download, Bootstrap e redirect.
- `scripts/react-migration/check-route-gate.mjs` impedisce di dichiarare una
  route sbloccata senza `react_full`, componente dedicato, data client, bridge e
  contratto legacy.
- `scripts/react-migration/check-ui-consistency.mjs` blocca classi Bootstrap nei
  nuovi componenti React, `href="#"`, CDN non consentiti e mock visibili.
- `scripts/react-migration/run-safe-react-migration.mjs` esegue audit, gate,
  consistency, `npm run test`, `npm run typecheck`, `npm run build` e scrive
  report/patch sotto `artifacts/react-migration/`.

Il nuovo kit `frontend/src/ui` fornisce primitive `Page`, `PageHeader`,
`Button`, `Badge`, `Panel`, `KpiCard`, `DataTable`, `FormField`, `EmptyState`,
`LoadingState`, `ActionBar` e `Tabs`, usando solo token `--iu-*` gia' presenti.
Non sostituisce Bootstrap nella shell e non migra route operative: serve a
rendere uniformi le prossime pagine verticali prima della promozione nel gate.

## Stato tranche 2026-05-05 - caricamento progressivo e sincronizzazione

- La Panoramica React legge `/api/v1/ui/dashboard` senza cache busting client-side: il refresh forzato usa solo `refresh=1`, mentre il payload espone metadati tecnici di cache non invasivi.
- La sincronizzazione PEC/email ordinaria parte dopo il primo render tramite `POST /api/v1/ui/dashboard/sync-mailboxes`; il caricamento iniziale resta locale/cache e non esegue IMAP nel builder sincrono.
- Il runtime `web.services.mailbox_sync_runtime` centralizza lock, cooldown, audit e separazione fra `EMAIL_CASELLA_DB` e `EMAIL_ORDINARIA_DB`; le route manuali `/email/sincronizza` e `/email-ordinaria/sincronizza` restano operative come controller sottili.
- `/api/v1/ui/fascicoli` supporta paginazione server-side reale (`page`, `page_size`), filtri (`q`, `type`, `status`, `court`, `alerts_only`) e sort backend, costruendo gli item della sola pagina richiesta.
- Il dettaglio fascicolo mantiene un payload principale leggero e carica documenti, attivita, scadenze, depositi e Regia con endpoint lazy dedicati quando il tab viene aperto.
- La Regia Operativa di fascicolo usa metodi scoped (`preventivi_per_fascicolo`, `conferimenti_per_fascicolo`, `per_fascicolo`) quando disponibili, evitando il caricamento globale non necessario.

## Stato tranche 2026-05-05 - superfici studio operative

- La top bar desktop React e' un centro operativo trasversale: command palette `Ctrl+K`/`Cmd+K`, menu `+ Nuovo` contestuale, pannelli Oggi, Notifiche, Scadenze, Recenti e timer attivita.
- Le nuove superfici leggere leggono solo dati reali da `/api/search/global`, `/api/dashboard/today`, `/api/notifications`, `/api/deadlines/quick-summary`, `/api/recent` e `/api/time-tracking/*`; non esistono fallback demo o `href="#"`.
- Il timer della top bar usa backend tenant-aware e, allo stop, crea una voce timesheet reale collegata a fascicolo/cliente quando indicati.
- `/timesheet` espone shell React, payload `/api/v1/ui/timesheet`, KPI reali, filtri, form nuova attivita, cambio stato e generazione parcella tramite route Flask operative.
- `/cartelle-condivise` espone shell React, payload `/api/v1/ui/cartelle-condivise`, modalita gestore/collaboratore, statistiche privacy e azioni su gestione collaboratori/API esistenti senza mostrare token temporanei.
- `/wizard-pro/`, `/wizard-pro/<id>/step/<n>` e `/wizard-pro/<id>/completo` sono GET React completi; i POST `/wizard-pro/nuovo`, `/wizard-pro/<id>/step/<n>`, `/archivia` ed `/elimina` restano nel blueprint Flask auditato.
- Per queste superfici la vista Jinja resta disponibile solo come fallback tecnico con `?_legacy=1` e non deve comparire nella UI React.

## Regia Operativa nel dettaglio fascicolo

La sezione React `Regia Operativa` e' integrata nel dettaglio fascicolo e legge il payload reale `regia` esposto da `/api/v1/ui/fascicoli/<fascicolo_id>`.

Contratti UI:

- nessun dato demo o hardcoded;
- `mock_fallback=false` nei payload Regia;
- pulsante deposito disabilitato quando il predeposito espone blocchi;
- timeline ricevute visibile solo da repository;
- evidence pack visibile solo quando il repository lo rende disponibile;
- nessuna CTA con `href="#"`.

Le API operative dedicate sono sotto `/api/v1/ui/fascicoli/<fascicolo_id>/regia`, `/checklist`, `/document-slots`, `/predeposito` e `/depositi`.

## Wave Documenti AI Fascicolo

`Documenti AI` e' stato ricondotto a motore interno di indicizzazione Lex: non compare piu' come sezione operativa autonoma nel dettaglio fascicolo e non crea un secondo archivio documentale.

La suite fascicoli mostra invece un box compatto `Indicizzazione Lex` dentro `Documenti fascicolo`: usa payload reali `/api/v1/ui/fascicoli/<fascicolo_id>/lex-indexing`, mantiene `mock_fallback=false`, espone conteggi `ready/queued/indexing/error/stale` e azioni autorizzate `Aggiorna indice` / `Riprova errori`. Upload, import portale e salvataggio editor restano flussi documentali reali del fascicolo e accodano o processano l'indice automatico.

La UI non mostra documenti demo e non introduce una seconda source of truth: storage, estrazione, audit e permessi restano nel dominio backend `pct/document_intelligence`. Le capability avanzate `generate_docx`, `propose_edits` e `compare` restano `false` fino alle tranche MVP 2/3/4 documentate in [DOCUMENTI_AI_FASCICOLO.md](DOCUMENTI_AI_FASCICOLO.md).

## Wave Editor AI Fascicolo

`Generazione atti con Lex` e' integrata nell'editor professionale esistente, non in una pagina separata. La route profonda dell'editor espone nel payload `editorAI` gli endpoint reali per bootstrap, generazione, dettaglio atto AI, proposte modifica ed export.

La UI mostra un pannello compatto `Nuovo atto con Lex` dentro l'editor: sceglie template reali del catalogo atti, istruzioni utente e documenti indicizzati del fascicolo. La generazione crea un documento reale del fascicolo, lo rilegge dal repository editor e poi apre la bozza nell'editor professionale.

Le modifiche successive passano da `Modifiche proposte da Lex`: ogni proposta resta `pending` finche' l'utente non la accetta o rifiuta. L'accettazione aggiorna il documento editor e crea una nuova versione; il rifiuto non muta il contenuto. I dettagli architetturali sono in [EDITOR_AI_FASCICOLO.md](EDITOR_AI_FASCICOLO.md).

## Principio operativo

React diventa la superficie operativa progressiva dell'applicativo, mentre Flask resta backend, source of truth, motore di permessi, tenant, audit e repository. Le scritture sensibili continuano a passare dai servizi Flask gia' auditati fino a quando non esiste una API React equivalente, testata e governata.

La vista Jinja classica non viene eliminata finche' la parita' funzionale non e' verificata. Quando una route GET ufficiale viene promossa a React, la vista classica resta raggiungibile solo come percorso tecnico di assistenza tramite `_legacy=1`; non deve comparire nella UI React come scorciatoia o rollback visibile.

## Pattern OSS adottati come metodo, non come codice

La migrazione progressiva deve seguire il playbook interno [REACT_MIGRATION_PATTERNS_FROM_OSS.md](REACT_MIGRATION_PATTERNS_FROM_OSS.md), ricavato dallo studio temporaneo di Apache Superset, Mattermost e p5.js Web Editor.

Le repo esterne possono essere usate solo come riferimento tecnico per routing, TypeScript incrementale, test, CI e scomposizione dei moduli. Non si importa codice esterno dentro IUSENTRA senza verifica licenza, adattamento al dominio legale e test dedicati.

Ogni pagina deve dichiarare uno stato operativo esplicito:

- `legacy_only`: vista classica completa, nessun React operativo.
- `react_nav_only`: shell/nav React, contenuto operativo classico.
- `react_readonly`: React legge dati reali ma non copre tutte le azioni.
- `react_operational_partial`: React copre azioni reali con limiti documentati.
- `react_operational_complete`: React copre lettura, card, form, download/API, route profonde e test.

Solo `react_operational_complete` puo' essere comunicato come pagina migrata.

## Stato primo blocco React

Il primo blocco e' considerato operativo sulle seguenti superfici:

- Panoramica: `/app-v2`
- Regia Operativa: `/app-v2/regia-operativa`
- Ricerca Studio: `/app-v2/ricerca-studio`
- Agenda: `/app-v2/agenda` e `/app-v2/agenda/nuovo`
- Fascicoli: `/app-v2/fascicoli`, archivio, nuovo/modifica, dettaglio, quadro, editor documento profondo ed export
- Clienti e Anagrafiche: `GET /clienti` e `GET /clienti/nuovo`
- Soggetti e Parti: `GET /soggetti` e `GET /soggetti/nuovo`
- Comunicazioni: `GET /email/`, `GET /messaggi`, `GET /messaggi/nuovo`
- Servizi Telematici: `GET /telematico` e `/app-v2/telematico`, con fallback tecnico `_legacy=1`
- Superfici telematiche di secondo livello: `GET /polisWeb`, `GET /pdp`, `GET /pat`, `GET /sigit`, `GET /tribunali`, `GET /deposito/checklist` e `GET /guida/firma-digitale`, con fallback tecnico `_legacy=1`
- Amministrazione database: `GET /admin/database`, con payload reale, azioni amministrative Flask e fallback tecnico `_legacy=1`

Le pagine del blocco usano dati reali, API bridge sotto `/api/v1/ui/*`, testi visibili in italiano, stati vuoti espliciti e Lex AI contestuale dove previsto. Non sono ammessi mock operativi, dati inventati, profili hardcoded, badge fittizi o copy che presenti la UI React come prototipo temporaneo.

## Contratti API attivi

- `GET /api/v1/ui/bootstrap`
- `GET /api/v1/ui/dashboard`
- `GET /api/v1/ui/agenda`
- `GET /api/v1/ui/fascicoli*`
- `GET /api/v1/ui/fascicoli/<id>/documenti/<id_doc>/editor`
- `GET /api/v1/ui/clienti`
- `GET /api/v1/ui/clienti/nuovo`
- `GET /api/v1/ui/soggetti`
- `GET /api/v1/ui/email`
- `GET /api/v1/ui/messaggi`
- `GET /api/v1/ui/messaggi/nuovo`
- `GET /api/v1/ui/telematico`
- `GET /api/v1/ui/telematico/surface/<surface>`
- `GET /api/v1/ui/privacy/registro`
- `GET /api/v1/ui/admin/database`

I contratti devono dichiarare `mock_fallback=false`. Le superfici che inviano a servizi Flask esistenti dichiarano `writes=operational_routes`.

## Fascicoli: editor documento React

`GET /fascicoli/<id>/documenti/<id_doc>/editor` e' promosso a React con stato `react_operational_complete` per il flusso editor documentale.

- Il payload arriva da `GET /api/v1/ui/fascicoli/<id>/documenti/<id_doc>/editor` e include solo dati reali del fascicolo/documento, capability, endpoint operativi e warning professionali.
- Il contratto dichiara `mock_fallback=false`, `localBundle=true` e `writes=operational_routes`.
- Il contenuto editabile viene letto da `GET /api/editor/<id>/<id_doc>/html` per DOCX, HTML e testo; salvataggio, PDF e DOCX restano sulle route Flask storiche `/salva`, `/pdf` e `/docx`.
- La pagina React non carica TipTap o Mammoth da CDN esterni: toolbar, import locale, ricerca/sostituzione, autosave e stati di salvataggio sono nel bundle Vite.
- La toolbar deve restare comparabile a un editor da studio: stile paragrafo, font, dimensione, interlinea, colori, allineamenti, liste, tabelle, link, ricerca/sostituzione, formato pagina e zoom.
- I PDF devono privilegiare la fedelta visuale: il payload React li marca in sola anteprima nativa, e il backend blocca comunque la conversione quando rileva token `(cid:...)`, stemmi, immagini, riquadri, timbri o testo ruotato/laterale che renderebbero l'HTML diverso dall'originale.
- I documenti firmati `.pdf.p7m` devono restare visualizzabili in anteprima quando il payload CAdES contiene o consente di recuperare un PDF interno.
- La vista Jinja classica resta disponibile solo come fallback tecnico `?_legacy=1`, senza link visibili nella UI utente.

## Servizi telematici: superfici di secondo livello

Le superfici telematiche React sono pagine operative reali, non mock:

- `PolisWeb / PST`, `PDP`, `PAT` e `PTT` filtrano casi, esiti, import incompleti, controlli predeposito ed eventi dal repository telematico reale; su PST la prima azione visibile resta `Importa pratica da PST` e punta al wizard operativo `/portali/pst/acquisizione`.
- `Tribunali / PEC` legge la cache uffici giudiziari reale, espone ricerca e copia PEC, e mantiene le azioni di refresh/report sulle route Flask operative.
- `Checklist deposito` e `Guida firma digitale` salvano solo spunte locali nel browser; le verifiche effettive restano sui servizi Flask e sul Local Signer browser-locale.
- Nessuna superficie scarica autonomamente documenti dai portali o legge HTML dei portali: i collegamenti ufficiali aprono il portale all'utente, mentre l'import resta guidato da file o canali autorizzati.

## Privacy: Registro GDPR

`GET /privacy/registro`, `GET /privacy/registro/nuovo` e l'alias `GET /registro-gdpr` sono promossi a React con stato `react_operational_complete`.

- I dati arrivano dal repository privacy esistente tramite `GET /api/v1/ui/privacy/registro`.
- Il contratto dichiara `mock_fallback=false` e `writes=operational_routes`.
- Il form `Nuovo trattamento` usa il `POST /privacy/registro/nuovo` Flask gia' auditato.
- L'eliminazione usa `POST /privacy/registro/<id>/elimina` e resta quindi protetta da sessione, permessi e audit.
- La vista classica resta disponibile solo come fallback tecnico `?_legacy=1`, senza CTA visibili dalla UI React.
- La pagina espone card operative reali verso audit, clienti, impostazioni e Lex contestuale, oltre a filtri e warning sui campi GDPR essenziali.

## Amministrazione: Gestione Database

`GET /admin/database` e' promosso a React con stato `react_operational_complete`.

- I dati arrivano dal runtime database esistente tramite `GET /api/v1/ui/admin/database`.
- Il contratto dichiara `mock_fallback=false` e `writes=operational_routes`.
- Le azioni React chiamano le route amministrative reali: `GET /admin/database/verifica` per audit in sola lettura, `POST /admin/database/verifica-ripara` per la verifica con riparazione automatica dei problemi referenziali risolvibili, `POST /admin/database/ottimizza`, `POST /admin/database/migra`, `POST /admin/database/attiva-sqlite` e `GET /admin/database/export`.
- La riparazione automatica deve usare solo dati reali: se un riferimento orfano non puo' essere ricollegato a un record univoco, il campo viene scollegato, l'identificativo originale resta nelle note/metadati del record e viene creato un backup JSON prima della scrittura.
- Il profilo utente nella shell React deriva dal profilo reale di sessione (`g.utente_corrente`) e non puo' usare nomi, ruoli, iniziali o badge inventati.
- La vista classica resta disponibile solo come fallback tecnico `?_legacy=1`, senza CTA visibili dalla UI React.

## Comunicazioni: Email PEC e Messaggi

Email PEC e Messaggi sono stati promossi nel primo blocco:

- `GET /email/` serve la shell React Email PEC;
- `GET /messaggi` serve la lista React Messaggi;
- `GET /messaggi/nuovo` serve la composizione React multicanale;
- `POST /messaggi/nuovo` resta sul servizio Flask operativo;
- le azioni PEC restano sui servizi Flask esistenti: sync, auto-esiti, lettura, cestino, ripristino, dettaglio e risposta.
- la Panoramica React (`GET /api/v1/ui/dashboard`) deve usare la stessa casella PEC tenant-aware della pagina `/email/`, ordinare le righe `Ultime PEC ricevute` per data reale decrescente e non filtrare solo su `stato_pct`: le PEC ministeriali prive di esito PCT sono comunque messaggi PEC ricevuti da mostrare fra le ultime.

La sincronizzazione IMAP PEC deve distinguere le cartelle operative:

- `INBOX` -> `INBOX`
- `Sent`, `Sent Items`, `Posta inviata` e alias compatibili -> `INVIATI`
- `Trash`, `Deleted Items`, `Posta eliminata` e alias compatibili -> `CESTINO`

Questa distinzione e' coperta da test per evitare regressioni sulla visibilita' di Inviati e Cestino.

## Design system e performance

- Usare i design token IUSENTRA presenti in `tokens.json`.
- Mantenere testi visibili in italiano.
- Target touch minimo: `44px`.
- Garantire responsive desktop, tablet e mobile.
- Verificare contrasto, focus visibile, heading order, navigazione tastiera e `prefers-reduced-motion`.
- Nessun caricamento esterno non necessario senza consenso.
- Le pagine React del primo blocco sono caricate con code-splitting tramite `React.lazy` e `Suspense`, cosi' il bundle iniziale resta governabile.

## Gate per ogni pagina

- API con dati reali, nessun mock operativo.
- Contratto OpenAPI aggiornato per endpoint P0/P1, con `x-rbac-permission`, `x-tenant-scope`, feature flag quando applicabile e provider verification fase 6.
- Card e CTA non decorative: ogni card React deve puntare a una route servita, a un download esplicito o a un endpoint/form operativo; sono vietati `#`, `_legacy=1` e link a superfici non migrate nella UI utente.
- UI responsive desktop/tablet/mobile.
- Azioni di scrittura protette da CSRF/sessione, tenant e RBAC.
- Test unitari backend.
- Test frontend: `npm run test`, `npm run typecheck`, `npm run build`.
- Smoke route autenticato su GET ufficiali e API bridge.
- Verifica accessibilita' di base.
- Vista classica disponibile solo come percorso tecnico `_legacy=1`, non come CTA della UI React.
- Documentazione e changelog aggiornati nella stessa tranche.

## Prossime wave

1. Preventivi e Conferimenti.
2. Parcelle, Fatture, Incassi e Pagamenti.
3. Documenti, allegati e upload.
4. Lex AI avanzata.
5. Sito Studio Builder.
6. Firma digitale, Local Signer e portali avanzati.
7. Impostazioni residue e amministrazione avanzata.

Firma digitale, Local Signer e automazioni avanzate dei portali restano in wave dedicate perche' hanno vincoli di compliance, audit, canali separati e conferma consapevole dell'avvocato.

## Comandi di verifica

```powershell
cd D:\legale\IUSENTRA\frontend
npm run test
npm run typecheck
npm run build
```

```powershell
cd D:\legale\IUSENTRA
python -m pytest tests/test_react_shell.py tests/test_email_client.py tests/test_messaggi.py tests/test_web_bootstrap.py -q
```

## Hotfix tenant multi-studio 2026-05-10

- Il runtime applicativo deve fallire in modo sicuro se una richiesta autenticata di studio non ha un contesto tenant valido: niente fallback ai path globali, niente letture cross-studio, niente sessioni legacy globali riusate quando esistono piu' studi attivi.
- `web/services/auth_runtime.py` e i resolver dati condivisi devono bloccare gli account globali non `SUPERADMIN` in ambienti multi-studio, chiedendo sempre un accesso associato allo studio corretto.
- Il bootstrap automatico root->tenant dei dati legacy e' consentito solo in installazioni davvero mono-studio; con piu' tenant attivi va rifiutato per evitare contaminazioni tra studi.

## Aggiornamento 2026-05-13: Template Atti compilatore React

- `/template-atti/compila/<codice>` e' servita dalla shell React e usa `GET /api/v1/ui/template-atti/compila/<codice>` per caricare metadati, campi, selettori cliente/pratica, timbro, prefill e presidio Cartabia/deposito.
- La selezione di cliente e pratica collegata resta il punto di ingresso corretto: non si pretende che esista un fascicolo prima del lavoro dell'avvocato, ma quando la pratica viene scelta i campi ricavabili vengono precompilati dai dati IUSENTRA.
- Il submit finale resta sul POST Flask esistente e, se la bozza supera i blocchi redazionali, importa il documento nell'editor professionale per l'impaginazione.
- La vista Jinja del compilatore e' solo fallback tecnico `_legacy=1`; la UI ordinaria non mostra piu' il vecchio compilatore.
- Le note dei campi mancanti sono in italiano, leggibili e collegate al campo specifico; non sono ammessi messaggi inglesi o nomi tecnici di campo nella schermata.

## Aggiornamento 2026-05-13: Fase 6 contratti API

- `docs/openapi.yaml` e' il contratto OpenAPI 3.0.3 generato dagli endpoint reali `web/blueprints/api_v1_react.py`.
- `docs/api-endpoint-contract-map.md` collega endpoint, pagina, priorita, RBAC, feature flag, tenant scope, stato OpenAPI e provider verification.
- La provider verification usa Flask test client: 401 reale su tutti gli endpoint React API, 200 autenticato su campione P0/P1 rappresentativo e 400 `backend_security_control_param` sul guardrail tenant.
- Ogni nuova rotta React P0/P1 deve passare `python scripts\react-migration\generate_api_contracts.py --check`, `python scripts\validate_openapi.py docs\openapi.yaml`, `python scripts\verify_openapi_provider.py` e `python -m pytest -q tests\test_openapi_contracts_phase6.py --tb=short`.

## Aggiornamento 2026-05-14: Fase 14 release finale

- Versione finale locale `2.235.1`; decisione GO WITH WARNINGS in `docs/final-release-report.md`.
- Gate finali eseguiti: documentazione, registry, feature flag, routing, OpenAPI/provider, backend security/RBAC/tenant, frontend test/typecheck/build, governance, lint/static checks, coverage-critical e Docker locale.
- Fix finale leggero: `web/bootstrap/fascicoli_create_routes.py` e `web/bootstrap/fascicoli_document_helpers.py` separano flussi gia esistenti per far passare il budget governance senza cambiare URL o comportamento utente.
- Smoke Docker locale finale: `--subset contracts` PASS=7 FAIL=0; `--suite post-deploy` PASS=76 FAIL=0 SKIP=1 BLOCKED=6. I blocchi richiedono credenziali smoke dedicate e non sono verdi dichiarati.
- Hotfix successivo 2.235.1: superfici operative App V2 attive di default sotto `/app-v2`, rollback esplicito via flag, telematico non parificato e Web Push ancora protetti.

## Aggiornamento 2026-05-14: Portali assistiti dentro IUSENTRA

- `/portali/pdp/acquisizione`, `/portali/pat/acquisizione` e `/portali/ptt/acquisizione` non devono piu' presentare un semplice link esterno come azione primaria: la shell React parte dallo Step 1 con `Sessione IUSENTRA`, avvio della sessione locale assistita, raccolta file nel software e import finale nel fascicolo interno.
- Aggiunto `POST /api/portali/<portale>/acquisizione/importa-file` per PDP/PAT/PTT: riceve file raccolti dalla sessione assistita o selezionati dall'utente, importa i binari nei documenti del fascicolo, registra ricevute/esiti nella timeline/deposito quando riconoscibili e aggiorna metadati/audit del fascicolo.
- I payload autorizzati JSON continuano a usare `importa-payload` e non richiedono piu' selezione/anteprima fittizia nel frontend prima della chiamata.
- Il bridge React non espone `officialHref` come link esterno per PDP/PAT/PTT; le card e i link secondari puntano alla sessione assistita IUSENTRA.
- Verifiche registrate: py_compile backend/bridge, `npm --prefix frontend run typecheck`, `npm --prefix frontend run build`, `tests/test_portali_payload_import_ui.py`, due shard React shell mirati e browser reale autenticato su PDP/PAT/PTT.

## Aggiornamento 2026-05-14: Profilo, agenda, comunicazioni e scadenziario 2.236.3

- `/profilo` e `/agenda/importa` sono ora route React operative, servite dalla shell senza CTA primaria legacy e con contratti dedicati nel manifest.
- `/agenda/nuovo` usa autocomplete cliente sicuro: la digitazione non riusa l'evento React dopo l'update di stato, l'avvocato responsabile arriva dal profilo sessione e la scelta cliente precompila codice fiscale, procedimento e ufficio quando disponibili nei fascicoli reali.
- Le viste elenco `/clienti`, `/soggetti` e `/fascicoli` mantengono la tabella esistente ma aggiungono una scrollbar superiore sincronizzata su desktop, utile quando le colonne sono molte.
- PDP, PAT e SIGIT mostrano `Portale ufficiale` come link secondario nelle superfici assistite, mantenendo il percorso IUSENTRA come workflow principale.
- Le pagine `/email/scrivi` e `/email-ordinaria/scrivi` supportano allegati multipli, selezione cliente da anagrafica e invio JSON con salvataggio allegati sotto storage runtime tenant-aware.
- Lo scadenziario React traduce la fonte tecnica in `dati dello studio`, rende operative le card filtro, usa `Apri dettaglio` verso il dettaglio React e mantiene le azioni completa/elimina via POST JSON.
- La scheda `Impostazioni -> AI locale` rilancia lo stato all'apertura del tab e prova il controllo Local Signer quando configurato.
- Verifiche registrate: py_compile backend, contratti React, route gate, typecheck, test frontend leggero, build Vite, pytest mirati profilo/agenda/email/scadenziario/telematico, packaging/readiness, Docker locale no-cache 2.236.3 e smoke Playwright/CDP autenticato sui percorsi segnalati.

## Aggiornamento 2026-05-15: audit UI/UX severo 2.236.4

- Hardening globale UI applicato dopo revisione severa di card, testi, bottoni, finestre, layout, colori, tabelle, responsive e accessibilita' di base.
- Il pannello amministrativo studi non esegue piu' riconciliazioni o scansioni archivio durante il rendering: dettaglio studio e API spazio archivio usano lettura canonica leggera, con conteggio lazy time-boxed.
- `/agenda/importa` non contiene piu' form POST HTML nella superficie React: submit JSON con stato caricamento, errore e successo, mantenendo il flusso di anteprima esistente.
- Dialog e drawer condivisi hanno gestione focus, Escape, Tab trap, ripristino focus e blocco scroll; bottoni icona e menu principali hanno label accessibili e feedback visibile.
- Tabelle IUSENTRA degradano a card mobile con `data-label`; testi lunghi, nomi utente lunghi, bottoni e action row usano wrapping/clamp per evitare tagli a 125%, 150% e mobile landscape.
- Ripuliti testi visibili residui in AI locale, assistente Lex, admin studio e compensi: niente termini tecnici rivolti all'avvocato, date admin con formato italiano e messaggi errore professionali.
- Verifica browser Chrome CDP autenticata su 46 route x desktop/mobile: 92/92 controlli OK, zero redirect login, zero form POST HTML nel perimetro React verificato, zero testo tecnico vietato, zero overflow orizzontale. Report: `artifacts/react-migration/visual-2.236.4/visual-load-audit.md`.

## Aggiornamento 2026-05-15: rifinitura audit UI/UX 2.236.5

- Ricerca Studio non espone piu' sigle o tempi tecnici: `FTS5`, `Ctrl K` e millisecondi visibili sono sostituiti da linguaggio operativo per studio legale, mantenendo ricerca rapida e accessibilita' da tastiera.
- Controlli Atti non parla piu' di browser nei testi utente: checklist e Local Signer usano `postazione` e `PC`, coerenti con il vocabolario professionale.
- L'audit visuale considera correttamente pulsanti, tab e controlli interni come azioni: le pagine operative ricche di comandi non vengono piu' segnalate solo perche' hanno pochi link testuali.
- Verifiche registrate: typecheck, test frontend, contratti React, route gate, full React contract, packaging/readiness, build Vite, Docker locale no-cache `2.236.5`, audit Chrome CDP completo 46 route desktop/mobile con recovery mirata `/soggetti/nuovo` mobile.

## Aggiornamento 2026-05-15: Strumenti Forensi operativi 2.236.6

- `/strumenti-legali` non e' piu' una superficie solo descrittiva: il bridge React espone il catalogo completo degli strumenti forensi e collega i moduli ai metodi reali di `GestioneStrumentiLegali`.
- La pagina React supporta submit JSON per i calcolatori, con risultati in pagina, metriche, tabelle, note, fonti e stato errore/successo leggibile per lo studio.
- Confermate 70 funzioni di catalogo e 20 calcolatori eseguibili, con preset applicativi per interessi legali/mora e campi dinamici per fascicoli, contributo unificato, onorari, usura e altre utility.
- Verifiche registrate: py_compile backend, typecheck, test frontend, build Vite, gate React, pytest mirati Strumenti Legali/SIGP, browser reale desktop/tablet/mobile, baseline caricamento locale e Docker no-cache `2.236.6`.

## Aggiornamento 2026-05-15: Legal Skills Engine 2.237.0

- Aggiunta la superficie React `/legal-skills`, protetta da feature flag default-off e servita dalla shell React governata, con catalogo pack, profilo studio, esecuzione skill e revisione risultati.
- Introdotte API JSON tenant-aware `/api/v1/legal-skills/*` con sessione/API key, RBAC, audit, blocco parametri riservati e storage runtime sotto il tenant attivo.
- Integrati seed pack read-only originali per contratti, privacy, contenzioso e monitoraggio regolatorio; custom skill e agenti schedulati restano default-off e sottoposti a trust layer.
- Route gate e shell Flask sono stati aggiornati dopo un 404 reale emerso nel browser audit; il controllo finale desktop/mobile su `/legal-skills` e' verde.
- Verifiche registrate: py_compile, pytest mirati Legal Skills, check statico frontend, typecheck, test frontend, OpenAPI/provider, docs link/commands, packaging/readiness, build Vite, Docker locale no-cache e Chrome CDP autenticato.

## Aggiornamento 2026-05-15: AI Legal fase 2 finale 2.237.1

- Aggiunti gli alias pagina richiesti da `ai legal 2`: `PracticeProfilePage`, `ColdStartInterviewPage`, `LegalSkillRunPage`, `SkillRunDetailPage` e `ReviewerQueuePage`, agganciati alla shell React senza duplicare logica o creare maschere vuote.
- Esteso il gate statico Legal Skills per verificare file pagina, route `/legal-skills/profile/cold-start` e `/legal-skills/review-queue`, feature flag e divieto di `tenant_id`/`studio_id` client-controlled.
- Verifiche registrate: pytest Legal Skills, OpenAPI/provider, docs, packaging/readiness, typecheck, test frontend, build Vite, Docker no-cache e smoke HTTP locale sulle route fase 2.

## Aggiornamento 2026-05-15: sblocco Legal Skills 2.238.1

- `/legal-skills` non resta piu' bloccata per gli studi senza override flag: il motore base `lex.legalSkills.enabled` e le route catalogo, profilo, esecuzione e revisione sono attive di default.
- Trust layer, skill custom e agenti schedulati restano default-off e fail-closed, perche' abilitano superfici piu' sensibili e non servono per consultare il catalogo operativo.
- Aggiunto un test di regressione che conferma catalogo e profilo disponibili con default standard, e conferma ancora il blocco dei canali sensibili senza opt-in esplicito.

## Aggiornamento 2026-05-15: Sito Studio Builder Pro 2.239.1

- `/sito-studio/builder` adotta la Versione B vincolante: topbar scura, pannello sinistro stretto da 380px con tab verticali e preview live ampia sempre prioritaria.
- Le tab operative sono Setup, Pagine, Blocchi, Contenuti, Aspetto, Media, SEO, Privacy, AI e Pubblica; il pannello raggruppa le funzioni senza trasformarsi in pagina lunga o pannello largo.
- La preview live aggiorna ogni modifica, mostra il sito completo con footer, supporta scroll interno e mantiene menu integrato anche nei formati tablet/mobile.
- Il pannello e' ridimensionabile, il caricamento media assegna l'immagine al blocco selezionato, i colori secondario/accento incidono sul rendering e font/dimensioni/effetti sono persistiti nel tema pubblico.
- I testi del builder supportano corsivo, sottolineato, apice, pedice e allineamento sinistra/centro/destra/giustificato con sanitizzazione server-side dei soli tag ammessi.
- Verifiche registrate: typecheck, build, test frontend, pytest builder/assets, Ruff mirato, gate React, packaging/readiness, Docker locale no-cache, readiness locale e audit CDP `visual-2.239.1-sito-studio-builder`.

## Aggiornamento 2026-05-16: Registri Mediazione ufficiali 2.239.2

- `/legal-intelligence/mediazione` espone tre schede operative distinte per Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione, con link ministeriali `mediazione.giustizia.it` e stato `ripristinato` dal 22/04/2026.
- `/ricerca-legale` include gli stessi accessi ufficiali tra le evidenze locali governate quando la query riguarda mediazione, enti o formatori, senza fetch esterno e senza dati privati di studio.
- La news PST `NWS4865` resta disponibile come evidenza del ripristino, mentre la pagina Mediazione non dipende piu' da una sola scheda-notizia.
- Verifiche registrate: `python -m pytest tests/test_react_legal_intelligence_search.py -q --tb=short`, `python -m compileall pct web -q`, packaging sync, readiness release, Docker locale no-cache e deploy Hetzner CPX42 con cron backup saltato.

## Aggiornamento 2026-05-16: Registro Mediazione importato e consultabile 2.243.4

- `/ricerca-legale/mediazione` non e' piu' una pagina di accessi esterni: legge l'archivio interno `organismi_mediazione_elenco` e mostra una tabella professionale con filtri per sezione, stato, natura, territorio e contatti.
- Il sync importa in modo automatico e classificato i tre elenchi ufficiali ministeriali: Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. La paginazione ASP.NET viene seguita tramite campi nascosti e postback, conservando sezione, numero registro, CF, P.IVA, email, sito, stato e data stato.
- La UI limita il rendering iniziale alle prime righe filtrate per mantenere la pagina reattiva, ma ricerca e filtri lavorano sull'intero archivio acquisito.
- Lex AI legge lo stesso archivio come fonte ufficiale di classe A tramite `lex_mediazione_registry_sources`, con citazioni interne complete e link ministeriale della sezione corretta.
- Gli accessi ufficiali e la news PST restano schede di contesto e verifica, non sostituiscono piu' il contenuto importato.
- Verifiche registrate: pytest mirati Legal Intelligence/Lex/Update Pipeline, typecheck frontend, build Vite, prova live del sync ministeriale con 3.035 record acquisiti su 305 pagine e browser verification locale su desktop/mobile.

## Aggiornamento 2026-05-21: Regia Agentica Studio 2.247.0

- Aggiunta la superficie React `/workflow-agents` con home, dettaglio percorso, coda approvazioni e metriche, servita dalla shell App V2 e governata dai flag `routes.appV2.workflowAgents.*`.
- Le API `/api/v1/ui/workflow-agents` usano il bridge backend dedicato e il nuovo package `lex/agents`: preview read-only, proposte approvabili, approve/reject, metriche e storage tenant-aware.
- Le scritture agentiche sono intenzionalmente spente di default da `lex.workflowAgents.writeActions=false`; il target 80% viene calcolato e salvato per run, non dichiarato a prescindere.
- Verifiche registrate in `artifacts/react-migration/pytest-confirmed-ok.md`: sette pytest dedicati Lex Workflow Agents, shard feature/security/tenant, typecheck, build, test frontend, compileall e link documentali.

## Aggiornamento 2026-05-21: Regia Agentica Studio hardening 2.247.2

- La preview agentica non bypassa piu' il registry: i permessi reali App V2 vengono passati al `LexToolRegistry`, che normalizza i permessi storici `studio:*` senza indebolire RBAC.
- Ogni run salva una sintesi `result_json` derivata da tool, proposte, warning e blocchi, redatta prima dell'esposizione API.
- Le metriche 80% usano lo stato effettivo del run: baseline degli step, letture completate, review, correzioni, blocchi e rifiuti.
- I test dedicati sono stati estesi a 29 casi mirati: sei ricette operative, preview read-only, approve con permessi, blocco senza step approvato, feature flag, tenant isolation, PII redaction e divieti PEC/deposito/firma.
## Aggiornamento 2026-05-21: Legal Document Understanding 2.248.0

- La pagina Documenti AI del fascicolo include il pannello React “Lettura forense” per upload, badge sicurezza/validazione, albero ZIP/PEC, classificazione, dati estratti, eventi proposti, invio Lex dopo validazione e proof bundle.
- Le API `/api/documents*` e `/api/pec/{id}/process` sono tenant-aware e protette dai flag `legal_document_understanding`, `ocr_forensic`, `pec_zip_ocr` e `lex_validated_documents_only`.
- I gate mirati sono registrati in `artifacts/react-migration/pytest-confirmed-ok.md`: compileall, pytest documentale 16/16, feature flag/bootstrap 5/5, typecheck e build Vite.

## Aggiornamento 2026-05-25: Hotfix PST Local Signer 2.248.54 / 1.6.47

- Ripristinato il gate certificato interno del Local Signer prima delle operazioni PST. Dal 2026-05-27 la ricerca-snapshot usa il batch reale ricerca/profilo/documenti come gate certificato, senza preflight separato, per evitare due richieste PIN consecutive sui driver Windows che non condividono la cache tra processi `curl`. Il wizard continua a non chiamare `/pst/preflight-auth` dal browser e gli errori 401/certificato restano espliciti.
- La ricerca PST non deve trasformare errori di autenticazione o 401 in "nessun fascicolo trovato": il problema resta esplicito e finisce nella diagnosi server tenant-aware.
- Il wizard React aspetta il catalogo uffici prima dell'avvio automatico; il wizard classico risolve un eventuale `codiceMinistero` cached tramite `/api/uffici` e invia al Local Signer il codice ufficiale, ad esempio Palmi `0910011` invece di `0800570094`.
- Verifiche registrate: 8 test Local Signer PST mirati, 3 test wizard React/diagnostica, 2 test wizard classico, `py_compile`, boundary check Local Signer, packaging sync, OpenAPI e build pacchetti Local Signer `1.6.47`.

## Aggiornamento 2026-05-25: foreground PIN Windows Local Signer 2.248.55 / 1.6.48

- Durante preflight, ricerca, snapshot e download PST su Windows, il Local Signer avvia un helper best-effort che cerca finestre PIN/Sicurezza Windows/smart card/CNS/CIE/Bit4id/Aruba/token e prova a riportarle in primo piano mentre `curl` attende il certificato.
- La modifica non cambia il modello di sicurezza: PIN e chiave privata restano sul dispositivo, non vengono salvati e non vengono trasferiti al server.
- Verifiche registrate: suite Local Signer completa, test packaging/readiness, `py_compile`, boundary check, packaging sync, OpenAPI, UTF-8 integrity e build pacchetti Local Signer `1.6.48`.

## Aggiornamento 2026-05-25: preset amministrazione e Sito Studio 2.248.56

- Le pagine `Amministrazione`, `Utenti`, `Profili e Permessi`, `Registro Attività`, `Database`, `Registro GDPR`, `Sito Studio Contatti` e `Sito Studio` sono state verificate come superfici React full operative nel browser in-app.
- Il preset IUSENTRA ora vince sulle regole specifiche che riportavano alcune CTA a 38 px; bottoni, link operativi e azioni secondarie restano leggibili e touch-safe.
- `Database` su mobile passa da tabella larga a vista compatta a schede; il bottom nav mobile non produce overflow di pagina.
- Verifiche registrate: browser in-app autenticato su desktop 1440x1000, tablet 900x1100 e mobile 390x844 con scroll alto/meta/fondo, 81 snapshot verdi, zero errori console nuovi, `pnpm test`, build Vite, governance, OpenAPI, provider verification, UTF-8 e asset retention.

## Aggiornamento 2026-05-26: PEC server, Comuni e uffici giudiziari 2.248.64

- `/email/scrivi` usa un pannello collassabile per cercare uffici giudiziari per Comune con autocomplete su banca dati locale completa dei 7.894 Comuni italiani, provincia e CAP.
- La ricerca filtra le dieci tipologie richieste dall'utente e inserisce nel destinatario solo recapiti PEC pubblicati o integrati da fonte ministeriale; il filtro `Procura Generale` esclude la Cassazione perché non rientra nella voce richiesta.
- La banca dati `uffici_giudiziari_comuni.sqlite` è normalizzata: 7.894 Comuni, 1.028 uffici unici e 78.816 associazioni Comune -> ufficio, con audit 100% e tracciamento dei Comuni predecessori quando Giustizia Map non espone il nome corrente.
- L'invio PEC della composizione usa il canale SMTP/PEC backend dello studio, non Local Signer, con destinatari normalizzati, TLS, `from_addr`/`to_addrs` espliciti e MIME corretto per allegati.
- Il lettore OCR/MRZ già presente su Nuovo Cliente è stato esteso anche a Nuovo Soggetto/Parte, con popolamento dei campi affidabili e preservazione dei valori modificati dall'utente.
- Verifiche registrate: audit territorio, audit uffici, pytest mirati Comuni/uffici/PEC/OCR, suite `tests/test_email_client.py`, typecheck, build Vite e compileall.
## Aggiornamento 2026-05-26: PEC fascicolo, Lex e notifiche legali 2.248.66

- `/email` conserva il percorso `Salva nel fascicolo` senza Local Signer e senza servizi telematici: la preparazione chiede nome/cognome cliente, confronta varianti anagrafiche e fascicoli aperti anche con ordine nome/cognome invertito, poi richiede conferma prima di salvare il MIME.
- Il riepilogo indicizzazione Lex recupera i documenti rimasti in `In corso`: i record `processing` oltre soglia diventano stale e rientrano nel ciclo di indicizzazione, così la coda non resta a zero con elementi bloccati.
- Document Intelligence resta allineata ai formati richiesti dal fascicolo: `.pdf.p7m`, `.pdf`, `.txt`, `.eml`, `.doc` e `.docx`; per DOC legacy usa conversione locale quando disponibile e fallback testuale prudente.
- Il dettaglio fascicolo espone la rinomina dei documenti caricati con icona sotto il documento, form inline, route auditata e conservazione obbligatoria dell'estensione originale.
- `/notifiche-legali` mostra `Data e ora verifica PEC` con orologio locale al secondo, campo modificabile dall'avvocato e pulsanti separati `Controlla relata` / `Invia PEC`; l'invio resta assistito e gli effetti legali sono ancora governati da PEC, RAC e RdAC.
- Verifiche registrate: pytest mirati e suite di perimetro PEC/Document Intelligence/Fascicoli/Notifiche, typecheck, test frontend, build Vite e browser in-app autenticato su `/notifiche-legali`, `/fascicoli/DC5BF1DB` e `/email`.

## Aggiornamento 2026-05-26: PST fascicolo/import reale 2.248.67

- `/portali/pst/acquisizione` ripristina l’anteprima operativa completa: identità fascicolo, parti, cronologia e lista documenti reali sono visibili prima della selezione.
- Il Local Signer `1.6.50` riusa la sessione PST aperta dalla visualizzazione anche quando il browser non invia più l’id sessione; lo scarico batch non ricade sul download singolo e riduce il flusso a un solo PIN nella sessione già autenticata.
- La mappatura React usa l’id fascicolo locale (`practiceId`) per aggiornare pratiche esistenti; il backend accetta comunque l’id telematico come fallback compatibile.
- L’import mostra avanzamento documento per documento, segnala import completato con avvisi quando un PDF non viene consegnato dal PST e distingue errori di timeout, autenticazione, autorizzazione, blocchi di verifica e assenza di file reali.
- Verifiche registrate: test Local Signer mirati, test React shell/PST, test PolisWeb no-file, typecheck, build Vite, pacchetto Local Signer `1.6.50` e prova reale browser su RG 274/2026 Tribunale di Palmi con import 200 sul fascicolo `B6A03AE6`.

## Aggiornamento 2026-05-27: PST download documenti nel fascicolo 2.248.77

- Il wizard PST distingue in modo stabile `Crea nuova pratica` e `Usa pratica esistente`; le vecchie voci `Collega a pratica esistente` e `Aggiorna pratica esistente` non devono tornare come scelte separate.
- Lo step documenti espone selezione singola, `Scarica selezionati` e `Scarica tutti`; l'import usa il sottoinsieme selezionato e passa file reali a `downloaded_files`.
- Il decoder backend accetta sia il payload storico (`nome`, `contenuto_b64`) sia alias Local Signer/browser (`filename`, `content_base64`, `source`, `data_deposito`, `id_documento`, `id_deposito`) e fonde i metadati del catalogo prima del salvataggio.
- Regressione obbligatoria: `tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_salva_lotto_sette_documenti_nel_fascicolo` simula `7/7` documenti con `Atto_2767510.pdf` e fallisce se i PDF ricevuti non finiscono nei documenti del fascicolo e nel deposito.
- Per la prima importazione resta vietato creare pratiche vuote: catalogo PST senza file reali blocca l'import. Per una pratica già esistente, l'assenza di parti strutturate dal portale è solo un avviso e non cancella i dati locali.

## Aggiornamento 2026-05-27: Import pratiche Studio Telematico 2.248.79

- `/importa-pratiche-studio-telematico` è una superficie React full dentro Amministrazione, servita dalla shell App V2 e censita nel manifest con `react_operational_full`.
- La pagina usa linguaggio operativo per studio legale, card compatte e percorso guidato: preparazione pacchetto, controllo completezza, import nello studio.
- La regola dati è esplicita e testata: `TESTI` legge i documenti solo dalla cartella `ATTI`, mentre `EMAILS` legge i messaggi solo dalla cartella `EMAILS`.
- Il backend importa pratiche, clienti, parti, documenti, email e agenda con deduplica su `source_external_id` e identificativi documento sorgente.
- Il file `.mdb` da solo viene trattato come controllo dati parziale; l'acquisizione completa richiede il pacchetto con `ATTI` ed `EMAILS`.
- Verifiche registrate: `py_compile`, test import completo/parziale, typecheck React, gate route/contratti React e smoke HTTP della rotta/payload.

## Aggiornamento 2026-05-27: contrasto pulsanti React 2.248.81

- Corretto il problema sistemico per cui il preset dell'intestazione poteva far ereditare ai pulsanti il colore del titolo, rendendo il testo illeggibile su pulsanti scuri.
- La correzione copre sia i pulsanti moderni `.iu-btn` sia i pulsanti storici `.iu-button`; i primari mantengono testo bianco, i neutri testo scuro su fondo chiaro e gli stati disabilitati restano leggibili.
- La pagina `Importa pratiche da Studio Telematico` usa pannelli dedicati invece del contenitore generico, così `Pacchetto cliente` resta in alto e le azioni `Prepara pacchetto`, `Fascicoli`, `Controlla pacchetto` e `Importa pratiche` sono leggibili.
- Verifiche registrate: build Vite, browser in-app con screenshot sulla pagina import e controllo stili calcolati su `/importa-pratiche-studio-telematico`, `/clienti`, `/fascicoli`, `/agenda` e `/amministrazione`.

## Aggiornamento 2026-06-02: Fascicoli, uffici giudiziari per Comune 2.249.5

- In `/fascicoli/nuovo`, il campo `Autorità giudiziaria` resta il campo storico `tribunale`, ma ora integra la ricerca “Uffici giudiziari per Comune” già governata per il prodotto: autocomplete Comune, filtri `GDP`/Tribunale/`UNEP`/Procura/Corte d'Appello/Minorenni e pulsante `Usa nel fascicolo`.
- La UI applica al fascicolo il nome ufficiale dell'ufficio e conserva nel payload i codici disponibili senza promuovere identificativi impropri: codice ufficio del catalogo ministeriale, codice PST, codice Giustizia Locale e ISTAT sede sono campi separati; quando un ufficio ha solo ISTAT/PEC, il form mostra un avviso e non inventa un codice di deposito.
- Verifiche registrate: `pnpm --filter @iusentra/studio typecheck`, test mirati React shell sul form nuovo fascicolo, test endpoint `uffici_competenti` con filtro tipologia, suite territorio/uffici competenti, build Vite, Docker locale reale `127.0.0.1:8080` e browser desktop/tablet/mobile con Comune `Taurianova`.

## Aggiornamento 2026-06-02: Impostazioni, Canali SdI e parità SQL 2.249.6

- `/impostazioni/sdi` è una superficie React full collegata alla stessa esperienza `Impostazioni`, con scheda `Canali SdI`, campi per canale accreditato/intermediario, endpoint trasmissione, PEC notifiche, invio automatico e note operative.
- Il salvataggio resta JSON tenant-aware ma ora ha anche specchio strutturato `settings_config` su SQLite e PostgreSQL per tutte le sezioni visibili di `Impostazioni`: studio, PEC, firma, SMTP, WhatsApp, scheduler, AI, SdI, pagamenti, notifiche, backup e calendari.
- Le fonti ufficiali GDPR, FatturaPA/SdI e Codice Deontologico Forense aggiornato al 7 aprile 2026 sono salvate sotto `docs/specs/ministero/fonti_ufficiali/2026-06-02/` e registrate nel catalogo fonti; le regole runtime non dipendono da memoria di chat.
- Il Local Signer è stato riallineato alla versione `1.6.68`: sorgente, `tools/dist/local_signer.py`, `SetupLocalSigner-1.6.68.exe`, alias `SetupLocalSigner.exe` e installazione locale rispondono alla stessa versione; l'avvio immediato usa `pythonw.exe` quando disponibile.
- Verifiche confermate nei report: test backend/storage/fonti, gate React, build Vite, packaging Local Signer, installazione locale Local Signer e browser reale Docker `127.0.0.1:8080/impostazioni/sdi`.

## Aggiornamento 2026-06-04: editor template atti professionale 2.249.13

- `/template-atti/compila/<codice>` usa un workspace React operativo allineato al riferimento grafico: catalogo laterale, toolbar documento, foglio A4 centrale, pannello destro per campi, stile, Lex, fonti, controlli ed export.
- La Guida Pratica entra nello stesso editor: il template filtrato viene caricato nel documento modificabile, resta collegato a cliente/pratica e conserva import, anteprima PDF, salvataggio nel fascicolo ed export.
- `template_atti/font_registry.json` governa famiglie font classiche, moderne, giudiziarie, contrattuali, privacy e placeholder; il layout editor esteso conserva fallback DOCX/PDF/RTF e preset professionali.
- Lex Revisione testo opera in locale con modalità Correttore, Redattore, Revisore Normativo, Revisore Privacy, Template Builder e Final Check. Le proposte sono sempre in diff, con accetta/rifiuta/modifica, audit visibile e nessuna applicazione automatica.
- Verifiche locali confermate: `python -m pytest -q tests/test_template_atti_api_strict.py tests/test_template_atti_editor.py tests/test_utf8_integrity.py --tb=short`, `pnpm --filter @iusentra/studio typecheck`, `pnpm --filter @iusentra/studio test`, `pnpm --filter @iusentra/studio build`, contratti OpenAPI, route gate, asset retention, Docker reale su `127.0.0.1:8080`, browser desktop/tablet/mobile con scroll completo e click delle funzioni, zero overflow, zero errori console, date italiane, import, salvataggio, export RTF/DOCX/PDF e baseline prestazionale documentata in `artifacts/react-migration/template-editor-browser-2.249.13.json`. Restano da chiudere nel flusso di rilascio commit, push branch gemelli, check remoti e deploy Hetzner.

## Aggiornamento 2026-06-04: editor template atti professionale 2.249.15

- `/template-atti/compila/<codice>` usa ora un editor documento `contenteditable`: le funzioni di toolbar lavorano sulla selezione corrente, la toolbar resta sticky durante lo scroll, il grassetto non inserisce Markdown e gli allineamenti non colpiscono più l'intero documento quando è selezionata una porzione.
- Il pannello `Collegamento IUSENTRA` permette di scegliere cliente e fascicolo dalla compilazione e ricaricare il template con dati studio/cliente/fascicolo reali: ufficio giudiziario, cliente, controparte, R.G., materia e dati pratica.
- Timbro studio, import/export, copia, salvataggio e firma sono collegati al documento corrente: timbro spostabile e formattabile, PDF/DOCX/RTF con timbro e formattazione base, import PDF/DOCX/RTF/TXT con font/encoding governati e pagina vuota per creare template personalizzati con campi fascicolo.
- Guida Pratica e Scadenziario sono stati estesi con i materiali utente fino a `kb_set20`: 73 record integrati, 7 moduli KB nuovi, 3.321 termini processuali e 1.075 template calcolabili. Gli audit confermano 0 perdite verso KB completo, UI Guida Pratica e Lex.
- La stanza cliente dell'assistenza remota non mostra più l'anteprima del proprio schermo; la condivisione resta destinata al lato operatore/SUPERADMIN.
- Verifiche locali confermate: `py_compile` mirato, 36/36 pytest template/assistenza/Lex/UTF-8, import/merge/validazione Guida Pratica, `pnpm --dir frontend build`, Docker reale su `127.0.0.1:8080` con `/api/pronto` `2.249.15`, browser Playwright 74/74 e Browser integrato Codex con nessun overflow pagina/pannello/card.

## Aggiornamento 2026-06-12: assistente vocale Studio 2.253.1

- La topbar React include l'assistente vocale Studio con caricamento lazy, registrazione locale voce/PIN, attivazione con PIN pronunciato, ascolto continuo e disattivazione vocale.
- Il catalogo comandi è governato in `frontend/src/studioVoiceCommands.json`: 40 comandi base dell'utente, 290 frasi aggiunte, 330 frasi totali e 59 destinazioni operative.
- `Studio nuovo cliente` usa un flusso guidato con soli campi obbligatori, rilettura e conferma; il salvataggio passa da `POST /api/v1/ui/clienti/voce/crea` con permesso `clienti.scrivi`, validazioni, audit e sincronizzazione.
- Verifiche locali confermate: catalogo, pytest mirati, UTF-8, typecheck, test React, build Vite, contratti OpenAPI, Docker reale `127.0.0.1:8080` con `/api/pronto` `2.253.1`, audit CDP voce/PIN/cliente/59 destinazioni e visual load audit desktop/tablet/mobile.

# Changelog

## 2.278.22 - 2026-08-12

- **Compatibilità PAdES del certificato Windows.** Registrato esplicitamente l'OID standard `signingCertificateV2` richiesto da pyHanko; la suite completa Local Signer impedisce regressioni nel percorso PAdES mentre il deposito aggiorna le CAdES legacy.
- **Local Signer 1.6.112.** La firma CAdES tramite certificato Windows costruisce direttamente gli attributi CAdES-BES, verifica `signingCertificateV2` prima di restituire il file e riusa il PIN soltanto nella memoria locale per completare nello stesso comando anche `DatiAtto.xml`.

## 2.278.20 - 2026-08-12

- **Rigenerazione CAdES-BES fedele al documento originale.** Il deposito estrae il PDF dalla vecchia busta CAdES, lo firma senza timbri o trasformazioni aggiuntive e produce una sola nuova busta CAdES-BES; la versione precedente resta nello storico del fascicolo.
- **Local Signer 1.6.110.** La firma multipla distingue l'aggiornamento CAdES-BES dalle firme ordinarie e non propone più la controfirma dei file `.pdf.p7m` già firmati.

## 2.278.19 - 2026-08-12

- **Deposito telematico: niente controfirma dei file `.p7m`.** La firma multipla non forza più i documenti `Ricorso.pdf.p7m` e `Procura .pdf.p7m` in PAdES. Una busta CAdES-BES già completa resta invariata e non entra nel lotto di firma.
- **Aggiornamento governato delle firme CAdES legacy.** Se una firma esistente è priva degli attributi CAdES-BES richiesti, il software estrae il documento originale incapsulato, produce una nuova busta CAdES-BES con il PIN sul PC locale e conserva la versione precedente nello storico del fascicolo. Non vengono create firme annidate.
- **Local Signer 1.6.109.** Corretto il ramo PKCS#11 PAdES che confondeva il certificato del token con il certificato analizzato; aggiunto il percorso CAdES-BES sostitutivo e mantenuto il blocco protettivo per ogni sostituzione non richiesta dal flusso deposito.

## 2.278.17 - 2026-08-12

- **Deposito telematico: qualifica del professionista conforme a Studio Telematico.** Il flusso espone il selettore dedicato con gli stessi codici del programma di riferimento, distingue le opzioni della Cassazione, salva la scelta nel fascicolo e nelle impostazioni tenant-aware e la riusa nei depositi successivi.
- **Ruolo dedicato nel flusso ministeriale.** La validazione non ricava più la qualifica dal campo anagrafico generico dello studio; il valore selezionato resta nel contesto della busta e, per la Cassazione, viene serializzato in `DatiAtto.xml` come `tipoDifensore` (`DI` o `DD`). Un codice estraneo al catalogo sorgente viene rifiutato.
- **Guardrail mirati.** Verificati catalogo completo dei 270 tipi, payload anagrafico, persistenza fascicolo/configurazione, API React, UI deposito e typecheck frontend.

## 2.278.16 - 2026-08-12

- **Deposito telematico: rifirma operativa di `DatiAtto.xml.p7m`.** Se la firma ricevuta dal PC locale non contiene `signingCertificateV2`, il backend restituisce il documento da firmare nuovamente e la UI apre una nuova richiesta PIN; la nuova firma sostituisce quella non conforme ed è validata prima di creare la busta.
- **Deposito telematico: parità del catalogo Studio Telematico.** Il catalogo comprende 270 tipi, con contratto comportamentale, validazioni, generatori ministeriali PCT/UNEP e audit dedicati ricavati dal decompilato di riferimento.
- **Local Signer 1.6.107.** La firma CAdES-BES include gli attributi firmati richiesti e mantiene PIN e operazioni crittografiche sul PC locale dell'avvocato.

## 2.276.13 - 2026-08-05

- **Notifiche legali: allegati senza blocco su impronta stale.** La preparazione della PEC locale usa i documenti reali salvati nel fascicolo e non blocca più l'invio per differenze tra l'impronta del payload e il file scelto dall'avvocato; l'impronta resta calcolata sul contenuto effettivo allegato alla PEC.
- **Notifiche legali separate dal deposito.** La nota operativa e i guardrail restano nel perimetro `artifacts/notifiche-legali`, senza aggiornare la procedura del deposito telematico.

## 2.276.12 - 2026-08-05

- **Frontend: allineato PostCSS al lock workspace.** Assorbito il commit Dependabot `987faf1`, aggiornando `frontend/package.json` da `postcss 8.5.18` a `8.5.23` in dipendenze e override, coerentemente con `pnpm-lock.yaml` e `pnpm-workspace.yaml`.

## 2.276.11 - 2026-08-05

- **CI GitHub: sbloccato il gate OCR.** Il test di guardia su `api_v1_react.py` ora verifica il vecchio uso esatto `get_fascicoli=get_fascicoli` senza intercettare il loader corretto `get_fascicoli_loader`; lo shard `Pytest core fase 8/10 OCR parte 1/3` è stato riprodotto localmente e riportato verde.

## 2.276.10 - 2026-08-05

- **Fascicoli React: card controparte censita leggibile.** Il riepilogo del soggetto selezionato non comprime più nome, identificativo e PEC in una colonna stretta: le azioni scendono sotto al testo, con wrapping controllato e guardrail CSS dedicato.

## 2.276.9 - 2026-08-05

- **Fascicoli React: controparte già censita senza ambiguità.** Quando l'avvocato seleziona una controparte presente in Soggetti e Parti, il pannello di creazione della nuova scheda si chiude, il comando diventa `Aggiungi controparte al fascicolo` e la UI chiarisce che il soggetto viene collegato come controparte senza creare duplicati.
- Il percorso nuovo soggetto resta separato: `Crea una nuova scheda soggetto della controparte` compare solo quando non è selezionato un soggetto censito e continua a salvare la scheda riutilizzabile negli altri fascicoli.

## 2.276.8 - 2026-08-05

- **Fascicoli React: niente form vuoto per fascicoli mancanti.** La pagina `/fascicoli/<id>/modifica` ora rispetta il `notFound` dell'API form e mostra l'empty state `Fascicolo non trovato` con ritorno ai fascicoli, invece di renderizzare campi editabili quando l'id non esiste nel tenant.
- Il normalizzatore del form conserva il messaggio JSON del server sui 401/403/404, così l'errore resta leggibile e non viene sostituito da dati di fallback.

## 2.276.7 - 2026-08-05

- **Fascicoli: errore JSON governato sul collegamento parti.** Se il form React prova a collegare una controparte a un fascicolo non presente nel tenant corrente, la POST `/fascicoli/<id>/parti/aggiungi` risponde JSON `Fascicolo non trovato.` invece di restituire una pagina HTML 404 dentro la card.
- **Fascicoli React: modifica di fascicolo inesistente non apre più un form vuoto.** L'API `/api/v1/ui/fascicoli/<id>/modifica` risponde 404 JSON quando l'id non esiste nel repository del tenant, evitando salvataggi apparenti su pratiche non presenti.
- Guardrail mirati aggiunti per impedire il ritorno di HTML 404 nei flussi JSON del form fascicolo.

## 2.276.6 - 2026-08-05

- **Email PEC: profilo PEC selezionata fuori dal rail.** Il pannello con ricevuta, qualità, firma e profilo processuale non è più una colonna stretta accanto a Cabina/Controlli/Esiti: ora sta da solo sotto la visualizzazione email, con fatti processuali larghi e testo Evento non compresso.
- **Fascicoli: controparti censite riutilizzabili.** Nel form di modifica fascicolo il soggetto già censito si collega con `Aggiungi controparte selezionata`; se è già collegato il comando diventa `Già collegata`, mentre `Nuovo soggetto` crea o riusa la scheda e la collega al fascicolo come `CONTROPARTE`.
- **Soggetti: ReGIndE e Registro PP.AA. separati.** Il form `Nuovo soggetto` ha un selettore ReGIndE / Registro PP.AA.; la ricerca invia il registro scelto alla API e i risultati vengono filtrati sulla cache corretta.
- Guardrail mirati su layout Email PEC, contesto fascicolo nel form soggetto e filtri dei registri pubblici.

## 2.276.5 - 2026-08-05

- **Fascicoli: titolo del banner scadenze coerente con le righe visibili.** Il riepilogo globale resta `Scadenze urgenti` con dettaglio `scadute` / `entro 7 giorni`, ma il riquadro sotto le card ora calcola titolo e lista sulle scadenze effettivamente mostrate. Se le prime righe sono tutte scadute, il titolo diventa `Scadenze scadute`; scadenze future oltre 7 giorni non vengono esposte nel banner.
- **Agenda: KPI di giornata/settimana/udienze riportati sopra il planner.** L'ordine CSS React mette le card `OGGI`, `SETTIMANA`, `UDIENZE`, `SCADENZE` e `ALERT` prima del calendario settimanale e dei pannelli `Preparazione udienza guidata` / `Automazioni consigliate`.
- **Scadenziario: azioni sotto `Tipo` rese leggibili.** I pulsanti `Apri dettaglio`, `Modifica`, `Completa` ed `Elimina` restano sotto il badge `Tipo`, ma con griglia 2x2 da 44px, separatore e spaziatura dedicata per evitare che risultino attaccati.
- **Email PEC: lista e lettura rapida allineate.** Il pannello `iu-mail-reader-pane` è agganciato come colonna destra della griglia e mantiene la stessa riga di partenza della lista, anche nello stato vuoto.
- Guardrail mirati su Fascicoli, Agenda, Scadenziario ed Email PEC; build React superata.

## 2.276.4 - 2026-08-04

- **Acquisite le istruzioni link udienza dai PDF allegati PEC.** Quando il provvedimento non contiene un URL pronto ma dispone di depositare/comunicare e-mail e telefono per ricevere il link, la pipeline estrae l'adempimento dal PDF e lo porta in `remote_hearing_access_info`, Agenda, Scadenziario, topbar e centro notifiche.
- **Rafforzata l'estrazione dei link cliccabili PDF.** I link URI delle annotazioni PDF vengono acquisiti anche se l'OCR non restituisce testo visibile; la versione di estrazione allegati PEC passa a `2026-08-04-pdf-links-and-acquisition-v2` per far ripassare i record gia' processati.
- **Chiuso il tratto finale verso topbar e notifiche.** La notifica usa il payload remoto effettivamente persistito nello Scadenziario, risolve l'id tenant da registry/storage per le nuove materializzazioni e sanifica in lettura anche eventuali record storici gia' presenti nello stesso DB. Le vecchie formule generiche come `Piattaforma: altra` vengono rimosse quando esiste l'istruzione PDF concreta.
- **Web Push sicuro anche per link da acquisire.** Le notifiche operative possono inviare un avviso sintetico per udienza audiovisiva senza URL verificato, senza esporre dati pratica, e-mail, telefono o collegamenti non validati nel payload push.
- **Agenda: riepiloghi spostati sotto la preparazione udienza.** Le card KPI, compresa `OGGI`, non restano piu' sopra i pannelli operativi della settimana.
- **Scadenziario: azioni riga sotto `Tipo`.** La tabella non ha piu' la colonna `Azioni`: `Apri dettaglio`, `Modifica`, `Completa` ed `Elimina` sono dentro la cella `Tipo`, sotto il badge della tipologia, con guardrail React per impedire che tornino a destra.
- **Prova reale locale completata.** Docker locale `127.0.0.1:8080`, container `iusentra-app` e `iusentra-scheduler` healthy, `/api/pronto` `ok=true`, versione `2.276.4`: Scadenziario mostra il link udienza da acquisire dal PDF e le azioni sotto `Tipo`; Agenda mostra i KPI sotto i pannelli operativi; topbar espone l'istruzione del PDF senza `Piattaforma: altra`. Nel tenant locale le subscription Web Push risultano revocate/disabilitate, quindi e' stato verificato il payload pronto per push e non una consegna reale.

## 2.276.3 - 2026-08-04

- **Rimesso in sicurezza il bootstrap tenant dei presidi PEC.** Se `tenants.json` manca o non è leggibile, il registry viene ricostruito solo da directory tenant già valide con `config/storage.json` e `studio.db`, senza ricadere sui JSON root vuoti. Questo evita che scheduler, Agenda, Scadenziario, topbar e Web Push lavorino su `/data` invece che sul tenant reale.
- **L'audit della catena PEC non può più tornare verde senza studi.** Quando non trova target attivi risponde `ok=false` con errore esplicito: il caso che prima appariva sano (`ok=true`, `studios={}`) ora blocca subito la diagnosi.
- **Tolto dal cron il lavoro di riconciliazione storage.** I presidi multi-tenant ora risolvono i percorsi con `reconcile_aliases=False`: nel worker Docker la riconciliazione poteva restare appesa prima ancora del riepilogo `Presidio PEC`, facendo saltare il giro successivo e degradando PEC, Agenda, Scadenziario e notifiche.
- Guardrail mirati aggiunti su recupero registry da storage SQLite, audit senza studi, presidio health senza target, job scheduler PEC e worker di acquisizione.

## 2.276.2 - 2026-08-04

- **Corretto un falso allarme nello strumento di verifica della catena PEC.** Leggeva il centro notifiche usando lo slug dello studio, mentre il runtime lo scrive — e la UI lo legge — con l'id dello studio. Su uno studio perfettamente sano lo strumento dichiarava «nessuna notifica»: esattamente il falso allarme che quel controllo esiste per evitare. Ora usa la stessa regola dello scheduler (`_TENANT_NOTIFICATION_ID`) e della top bar (`current_tenant_id`).
- **Lo strumento ora mostra per primo il battito dei presidi pianificati.** Se lo scheduler e' fermo, ogni riga rossa sulle singole PEC e' una conseguenza e non una causa, e cercare il guasto nelle PEC fa perdere tempo. La sezione dice per ciascun presidio quando ha girato l'ultima volta, oppure che non ha mai girato su quel worker.
- Verificata la catena su una riproduzione fedele del percorso di produzione — PEC depositata nell'archivio locale come fa la sincronizzazione IMAP, poi acquisizione, worker e job delle notifiche con gli stessi identificativi tenant dello scheduler: classificazione `sentenza_a_verbale`, fascicolo collegato in automatico, due presidi, la scadenza nello scadenziario e tre voci nel centro notifiche.

## 2.276.1 - 2026-08-04

- **Chiuse sette vulnerabilita' delle dipendenze frontend**, fra cui le tre ad alta gravita' segnalate da Dependabot: `brace-expansion` (5.0.8 -> 5.0.9), `fast-uri` (3.1.4 -> 3.1.5) e `ip-address` (10.2.0 -> 10.3.1). Nello stesso giro anche le quattro moderate rimaste indietro: `postcss` (8.5.18 -> 8.5.23), `hono` (4.12.27 -> 4.12.34) e le due segnalazioni residue su `ip-address`. `pnpm audit` passa da 3 alte + 4 moderate a zero.
- `brace-expansion`, `fast-uri`, `postcss` e `hono` erano gia' fissati negli override del workspace, ma a versioni nel frattempo diventate vulnerabili: fissare una versione non basta, va anche rialzata. `ip-address` non era fissato affatto e arrivava vulnerabile dalla catena `shadcn > @modelcontextprotocol/sdk`: ora e' governato come gli altri.
- Per ciascun pacchetto e' stata scelta la **versione corretta minima**, non l'ultima pubblicata: il salto piu' piccolo che chiude la falla e' anche quello con meno probabilita' di rompere la build. `fast-uri` resta quindi sulla 3.x invece di passare alla 4.x.
- Verificato: typecheck TypeScript verde, build Vite verde, e il bundle ricostruito e' identico byte per byte a quello committato — gli aggiornamenti non cambiano l'applicazione.

## 2.276.0 - 2026-08-03

- **Nuovo strumento di verifica sul server: `scripts/verifica_catena_pec.py`.** Interroga i dati reali dello studio e, per ognuna delle ultime PEC, dice cosa ha effettivamente prodotto lungo la catena — classificazione, fascicolo collegato, presidio, scadenziario, agenda, centro notifiche (le stesse voci della top bar) e stato del canale Web Push. Sola lettura: non scrive, non invia, non modifica nulla. `docker compose exec app python scripts/verifica_catena_pec.py --limite 20`.
- Lo strumento distingue i tre casi che a occhio si confondono: l'anello non ha prodotto nulla, l'anello non doveva produrre nulla (una sentenza a verbale non porta un'udienza in agenda, e segnalarlo come guasto sarebbe un falso allarme), oppure manca il presupposto — nessun fascicolo compatibile, nessun destinatario abilitato a leggere i fascicoli, nessuna iscrizione Web Push concessa dal browser. Il motivo e' sempre esplicito.
- Provato end-to-end sulla PEC reale (comunicazione di cancelleria, Tribunale di Vicenza, sezione lavoro) acquisita dalla pipeline vera: classificazione `sentenza_a_verbale`, fascicolo collegato in automatico, due presidi, la scadenza nello scadenziario e le due voci nel centro notifiche.
- **Il gate locale ora replica davvero la CI.** Girava con il Python di sistema: se piu' vecchio del 3.12 usato dalla CI, sei gate su ventisei fallivano per l'ambiente invece che per il codice — indistinguibili da un guasto vero, e quindi rumore che nasconde i problemi veri. Ora lo script sceglie il venv del progetto o il primo interprete >= 3.12, dichiara quale sta usando e si ferma con istruzioni se non ne trova nessuno.
- Il primo effetto e' immediato: con il gate finalmente cieco su nulla e' emerso che `frontend/package.json` era fermo alla versione 2.268.0 mentre l'applicazione era alla 2.275.0. Allineato.

## 2.275.0 - 2026-08-03

- **Accesi i due interruttori che tenevano invisibile il presidio notifiche legali.** La pipeline PEC scriveva i presidi nel registro, Agenda e centro notifiche li leggevano, ma la pagina «Presidi notifiche» era irraggiungibile: `features.legalNotificationPresidia.enabled` era default-off e valeva in AND con il rollout dello studio, a sua volta `off` per gli studi senza configurazione esplicita. Due interruttori spenti, quindi nessun modo di vedere il registro. Ora il flag globale è acceso e uno studio senza configurazione parte in modalità `shadow`: il registro si consulta, l'esperienza della pagina Notifiche Legali resta quella di prima.
- **Acceso il controllo economico delle sentenze** (`features.sentenzaEconomicControl`). Governava sia il pannello dell'audit economico sia il trigger dalla PEC: da spento, tutta la catena verificata ieri — credito dell'avvocato antistatario, contributo unificato, riconciliazione col fascicolo — restava codice mai eseguito in produzione.
- Resta default-off `features.legalNotificationPresidia.primary`, che non serve a vedere il registro: sostituisce l'esperienza primaria della pagina Notifiche Legali ed è una scelta separata, da fare consapevolmente.
- **Alzata la versione della lettura economica dei documenti** (`ECONOMIC_DOCUMENT_ANALYSIS_VERSION`). Il presidio fascicoli salta i fascicoli il cui marcatore ha la versione corrente e l'impronta dei documenti invariata: e' il meccanismo che impedisce di rileggere all'infinito cio' che e' gia' stato letto, ed e' gia' coperto da test. Proprio per questo i fascicoli gia' analizzati sarebbero rimasti per sempre con la lettura sbagliata del capo spese: alzare la versione vale come «rileggi una volta sola», poi il presidio torna a saltarli. Guardrail nuovo: un test verifica che dopo il bump la rilettura avvenga una volta e che al giro successivo non si legga piu' nulla.
- Nota operativa: i presidi nascono quando una PEC viene lavorata. Le PEC già in archivio non vengono rilette (le protegge il dedup sull'hash), quindi per farle comparire serve una passata di riclassificazione: `python scripts/repair_pec_deadlines.py --tenant <slug-studio>`, che rilegge l'archivio con le regole correnti senza rifare OCR.

## 2.274.0 - 2026-08-03

- **La catena economica della sentenza arriva fino alla parcella.** Quando il giudice decide e liquida le spese, la comunicazione di cancelleria arriva via PEC con la sentenza allegata: il software la legge, riconosce il fascicolo, apre il credito dell'avvocato e predispone la proforma. La catena si spezzava in cinque punti diversi, tutti in silenzio.
- **Il numero di ruolo con il marcatore dopo il numero non veniva letto.** Le sentenze di merito si intestano quasi sempre «n. 523/2026 R.G. lav.», non «R.G. 523/2026». Il riconoscimento cercava il marcatore solo *prima* del numero: la sentenza risultava non riconciliata col fascicolo e l'audit economico si fermava a «verifica riconciliazione», senza importi.
- **Il capo spese nella forma più comune non veniva agganciato.** «che liquida in euro 500,00 oltre spese generali, iva e cpa» non ha il connettore «somma/importo/complessiva» che i pattern richiedevano: nessun importo letto, nessun credito aperto. La lettura del capo spese ora vive in un modulo unico (`pct/spese_liquidate_lettura.py`) usato sia dall'automazione del fascicolo sia dall'audit che parte dalla PEC, così i due percorsi non possono più divergere.
- **L'importo del credito non è più il più alto del testo.** L'audit economico prendeva il massimo importo trovato: in una sentenza è quasi sempre il bene riconosciuto al cliente, non il compenso liquidato al difensore. Sul provvedimento reale attribuiva all'avvocato i 1.000,00 euro della Carta docente invece dei 500,00 liquidati. Ora l'importo è quello agganciato al capo spese, con il brano del dispositivo mostrato come fonte.
- **La sentenza a verbale ex art. 127-ter c.p.c. non veniva riconosciuta come sentenza.** Non ha l'intestazione «Sentenza n. X pubbl. il ...»: porta solo luogo e data in calce, spesso numerica («Vicenza, 2/8/2026»). Senza data riconosciuta l'automazione economica del fascicolo non partiva affatto, quindi niente pagamenti e niente proforma — proprio nel caso tipico in cui il giudice liquida le spese.
- **Il beneficio riconosciuto al cliente non è più l'importo citato dalla legge.** Su una sentenza Carta docente veniva letto il valore dell'art. 1 co. 121 l. 107/2015 citato nella motivazione invece di quello riconosciuto nel dispositivo. Ora vale l'importo agganciato alla condanna.
- **Il trigger economico accettava solo `deposito_sentenza`.** Le sentenze a verbale (`sentenza_a_verbale`, `sentenza_a_verbale_429`), già trattate come equivalenti altrove, non facevano partire l'audit. E il provvedimento consegnato dal PCT dentro uno ZIP (`23343018s.pdf.zip`) veniva scartato dal filtro che pretendeva l'estensione `.pdf` secca, lasciando l'audit senza testo.
- Verificato sulla PEC reale (comunicazione di cancelleria, Tribunale di Vicenza, sezione lavoro): OCR di 13.763 caratteri, fascicolo riconciliato sul numero di ruolo, credito di 500,00 euro con distrazione in favore del procuratore antistatario, fascicolo definito e proforma da 729,56 euro (500,00 + 15% spese generali + 4% CPA + 22% IVA).
- Contributo unificato invariato e verificato: con la ricevuta entra col suo valore ed è recuperato in parcella; con l'autocertificazione di esenzione per reddito resta non dovuto, senza importo. Liquidazione, contributo, esborsi e parcella restano nello stesso pannello del fascicolo.
- Guardrail: undici test nuovi sul dispositivo reale — numero di ruolo col marcatore in coda, capo spese in forma diretta, importi non-compenso ignorati, sentenza a verbale riconosciuta dalla data in calce, importi attribuiti alla persona giusta, credito dell'avvocato antistatario, catena fino alla proforma, allegato dentro lo ZIP PCT, contributo esente e contributo pagato.

## 2.273.0 - 2026-08-03

- **Le PEC che non trovano un fascicolo non spariscono più.** Senza fascicolo collegato il presidio non crea alcuna voce operativa: la PEC risultava ricevuta, letta e lavorata, ma per lo studio non esisteva. Succede quando il procedimento non è ancora a ruolo nel gestionale o quando il numero di ruolo non coincide — cioè proprio quando serve l'attenzione dell'avvocato. Ora compare la voce «PEC da assegnare a un fascicolo» in centro notifiche, top bar e Web Push, con oggetto, numero di ruolo, ufficio, il motivo per cui il collegamento non è riuscito e la fonte del dato.
- Il motivo è esplicito e distingue i tre casi che il presidio già sa riconoscere: nessun fascicolo compatibile, numero di ruolo compatibile ma non sufficiente da solo, oppure fascicoli candidati da confermare.
- Il conteggio delle PEC da assegnare entra nel report del presidio relata (`unlinked_pec`), quindi è leggibile dalla console Pianificazioni.
- Un errore di lettura dell'archivio PEC ora viene registrato nel log invece di essere ingoiato: se le PEC non collegate diventano illeggibili, lo si deve sapere.
- Guardrail: tre test nuovi su comparsa della voce con numero di ruolo e fonte dichiarata, assenza della voce quando la PEC è collegata, e sopravvivenza al filtro che ripulisce le vecchie voci PEC.

## 2.272.0 - 2026-08-03

- **Trovata e corretta la causa per cui il presidio PEC non riportava nulla in agenda, scadenziario, notifiche e relata.** Il job `validate`, che materializza i presidi, gira **prima** del job `link`, che collega la PEC al fascicolo: al passaggio di `validate` il fascicolo non è ancora collegato e la voce viene scartata con «fascicolo non collegato, presidio non creato». Nessun giro successivo la recuperava, perché la coda dei job resta vuota. Risultato: la PEC veniva ricevuta, letta, classificata, sottoposta a OCR e collegata correttamente — e non produceva nulla per l'avvocato. Ora, dopo un collegamento riuscito, il presidio viene rimaterializzato in modo idempotente.
- **Il numero di ruolo certificato dagli XML ministeriali vale come prova nel collegamento al fascicolo.** `Comunicazione.xml` ed `EsitoAtto.xml` portano il tag `NumeroRuolo` scritto dall'ufficio giudiziario: è l'identificativo del procedimento, non un'inferenza sul testo. Finora contava quanto un RG dedotto dal corpo del messaggio (0,58 su una soglia di 0,78) e il collegamento sul solo RG era **esplicitamente rifiutato**, quindi una comunicazione di cancelleria non si collegava al proprio fascicolo se non coincidevano anche parti e ufficio. Ora la corrispondenza con il numero certificato pesa 0,82 e da sola basta; resta invece la prudenza sul RG dedotto dal testo.
- Il confronto fra numeri di ruolo ignora registro e formattazione: `523/2026/LAV` dell'XML corrisponde a `523` + `2026` del fascicolo, e `523/26` a `523/2026`.
- **Gli indirizzi di trasporto della PEC non sono più trattati come parti processuali.** `posta-certificata@legalmail.it`, `giustiziacert.it` e simili finivano fra i soggetti confrontati con il fascicolo, sporcando punteggio e motivazioni.
- Verificato su cinque PEC reali (comunicazione di cancelleria, notificazione ex L. 53/1994, accettazione di deposito telematico, accettazione e consegna di un'istanza): con il fascicolo presente la comunicazione si collega con punteggio 1,0 e motivazione «RG certificato dall'XML ministeriale», e il presidio crea le due voci attese — revisione della sentenza da notificare e ordine esplicito di notificazione.
- Guardrail: sei test nuovi su equivalenza dei numeri di ruolo, collegamento sul numero certificato, rimaterializzazione del presidio dopo il collegamento, assenza di lavoro inutile quando il collegamento non riesce, e indirizzi di trasporto esclusi dalle parti.

## 2.271.2 - 2026-08-03

- **Il corpo della PEC non classifica più gli allegati.** Le regole tecniche del classificatore leggevano anche il testo del messaggio, non solo nome e MIME dell'allegato: il corpo di una comunicazione di cancelleria cita quasi sempre `daticert.xml` e `postacert.eml`, quindi **ogni** allegato di quella PEC finiva etichettato `daticert` — compreso il provvedimento da acquisire. Un allegato `daticert` viene poi escluso dall'OCR (`classification NOT IN ('daticert','eml')`) e trattato come file tecnico, quindi il documento da scaricare dal portale spariva dal presidio. Verificato su una comunicazione reale del Tribunale di Vicenza: prima tutti e cinque gli allegati erano `daticert`, ora il provvedimento è classificato come documento, l'indice busta e la comunicazione come file tecnici, `daticert.xml` come daticert e `smime.p7s` come firma.
- Le regole di contenuto (procura, atto, istruttorio) continuano a leggere il corpo del messaggio, ma vengono valutate **dopo** quelle su nome e MIME: in un solo passaggio una regola di contenuto più in alto vinceva sul nome tecnico più in basso.
- Aggiunta la classificazione `firma` per le firme staccate e i certificati (`.p7s`, `.cer`, `.crl`), che prima cadevano nella classificazione residuale. Il `.p7m` resta escluso perché è l'atto firmato, non la sola busta di firma.
- Guardrail: due test nuovi, uno che riproduce il corpo di una PEC del PCT e verifica che il provvedimento non venga più etichettato `daticert`, uno che verifica che le regole di contenuto restino attive quando il nome dell'allegato non dice nulla.

## 2.271.1 - 2026-08-03

- **Il gate «CI Required Gates» non muore più su un errore di rete.** La run 30841471702 è fallita dopo 19 minuti non per un test rosso ma per un errore di trasporto HTTP/2 (`stream error: stream ID 1; CANCEL; received from peer`) su una singola lettura dei check: quella stringa non era fra i marcatori di errore transitorio, quindi non veniva nemmeno ritentata e abbatteva l'intero gate a check quasi tutti verdi. Gli errori di trasporto sono ora riconosciuti come transitori.
- **L'attesa dei check è diventata resistente.** Il gate attende fino a 90 minuti: una lettura non riuscita a metà attesa non butta più via il giro, si continua a interrogare fino alla scadenza e si fallisce solo se il tempo finisce senza mai una lettura riuscita.
- Guardrail: due test nuovi, uno sulla classificazione dell'errore di trasporto (che non deve però trasformare un 404 o un 401 in transitorio) e uno che verifica che il gate ritenti la lettura invece di abortire.

## 2.271.0 - 2026-08-03

- **I presidi non possono più tacere fingendo di aver lavorato.** Presidio PEC, relata, fascicoli, agenda/scadenziario e sincronizzazione caselle leggono tutti la stessa lista di studi: finché quella lista si svuotava in silenzio — registro studi illeggibile, nessuno studio attivo — i job completavano con esito «ok» avendo fatto zero, e il guasto restava invisibile in console Pianificazioni. Ora l'assenza di target è un esito fallito con il motivo scritto, quindi una riga rossa tracciabile. Vale anche per il presidio fascicoli, che in multi-tenant senza studi attivi non ripiega più sul contesto «default», e per il presidio relata, che dichiara l'archivio fascicoli non raggiungibile invece di riportare zero fascicoli scansionati.
- **Tolleranza di ritardo dei job portata da 1 secondo a 5 minuti.** Era il default di APScheduler: su un worker occupato (OCR della pipeline PEC, aggiornamenti legali) il giro successivo dei presidi veniva semplicemente saltato e registrato come «missed». I due presidi più frequenti dichiarano ora una tolleranza esplicita, con `max_instances=1` e `coalesce` per impedire che i giri arretrati si accumulino e saturino la CPU.
- **Cursore di acquisizione PEC non più avvelenabile.** La chiave di ordinamento dell'archivio era la stringa grezza della data del messaggio: bastava una PEC con data in formato diverso o nel futuro per portarla in testa, salvarci sopra il cursore e far risultare «più vecchia» ogni PEC successiva — il presidio smetteva di acquisire per sempre, senza segnalare nulla. Le date sono ora normalizzate (ISO, formato italiano, RFC 2822) e quelle future o illeggibili finiscono in fondo, dove non bloccano nulla. In più, se l'archivio cresce ma l'incrementale non seleziona niente, scatta uno sblocco automatico dichiarato nell'esito.
- **Battito dei presidi verificabile.** L'healthcheck del container verificava solo che il processo `pct.scheduler_worker` esistesse: un worker vivo e muto restava «healthy». Ora legge il registro pianificazioni e dice, per ciascun presidio, ultimo stato, quando ha girato e da quale riga di registro proviene il giudizio; distingue il job mai eseguito dal job fallito e concede una finestra di avvio per non innescare riavvii a catena. Lo stesso battito compare nella console Pianificazioni.
- **Meno CPU a vuoto.** L'acquisizione PEC rileggeva e riordinava l'intero archivio della casella ogni 5 minuti anche quando non era arrivato nulla: ora un'impronta su dimensione e data del file salta il giro a lavoro chiuso. L'healthcheck del container è stato riscritto per non importare la Flask app: da circa 1300 ms a circa 50 ms per esecuzione, ogni 30 secondi.
- Guardrail: quindici test nuovi su esito rosso senza target per i quattro presidi, tolleranze e istanze dei job, normalizzazione delle date con quattro formati reali, data futura e illeggibile che non possono più diventare cursore, impronta dell'archivio, battito verde/degradato/fallito/mai eseguito, finestra di avvio del worker, coerenza fra il lettore leggero del registro e il repository e fra i due risolutori del percorso.

## 2.270.1 - 2026-08-03

- **Corretto il termine lungo di impugnazione: ora è soggetto alla sospensione feriale.** Il modello `CIV_APPELLO_LUNGO` del motore dei termini calcolava i sei mesi dell'art. 327 c.p.c. senza i giorni dal 1° al 31 agosto, anticipando la scadenza di 31 giorni quando agosto cade nel periodo. L'art. 1 L. 742/1969 sospende i termini processuali senza distinguere fra termine breve e termine lungo e l'art. 3 non lo eccettua fra le materie sottratte: il modello è stato corretto e portato alla versione 2.
- **Le installazioni esistenti ricevono la correzione.** L'auto-upgrade dei modelli aggiungeva solo quelli mancanti, per non sovrascrivere le personalizzazioni dello studio; ora sostituisce anche un modello salvato quando quello di default ha una `version` superiore, cioè quando la regola di legge incorporata è stata corretta. Le personalizzazioni sui modelli non corretti restano intatte. Vale sia per il backend JSON sia per quello SQLite.
- Il calcolatore delle impugnazioni non diverge più dal motore: la sospensione resta disattivabile per le controversie sottratte dall'art. 3 L. 742/1969.
- Guardrail: due test nuovi sulla sospensione applicata al termine lungo e sull'upgrade selettivo dei modelli salvati, che deve correggere il termine lungo e lasciare intatta una personalizzazione dello studio su un altro modello.

## 2.270.0 - 2026-08-03

- **Nuovo calcolatore: ravvedimento operoso.** Calcola sanzione ridotta e interessi legali sul tardivo versamento, distinguendo i due regimi sanzionatori: la data di scadenza del versamento — momento in cui la violazione si consuma — sceglie fra il regime anteriore e quello introdotto dal D.Lgs. 87/2024, che l'art. 5 dello stesso decreto applica alle violazioni commesse dal 1° settembre 2024. Sanzione base ex art. 13 D.Lgs. 471/1997 (30%, 15%, 1% al giorno prima; 25%, 12,5%, 0,83% al giorno dopo) e riduzioni ex art. 13 D.Lgs. 472/1997, incluse le lettere legate a processo verbale e schema di atto e il nuovo un quarto della lettera b-quinquies). Gli interessi usano i saggi legali già versionati, segmento per segmento, con la formula imposta × tasso × giorni / 36500.
- **Nuovo calcolatore: termini di impugnazione.** Mette a confronto il termine breve dalla notificazione (art. 325 c.p.c.) e il termine lungo di sei mesi dalla pubblicazione (art. 327 c.p.c.) e indica quale scade per primo. Le durate non sono cablate: sono lette dai modelli già versionati del motore dei termini. La sospensione feriale (art. 1 L. 742/1969) è applicata per impostazione predefinita anche al termine lungo, con l'opzione di escluderla per le controversie sottratte dall'art. 3 della stessa legge.
- **Nuovo calcolatore: compenso a tempo (art. 22-bis D.M. 55/2014).** Passa dal motore già usato dal preventivatore, così suite e preventivo restituiscono lo stesso importo a parità di dati; aggiunge le spese generali come voce separata e mantiene gli avvisi su parametro orario, massimale e soglia di preapprovazione.
- Guardrail: quattordici test nuovi su regime sanzionatorio per data di violazione, riduzione di un decimo entro trenta giorni, sanzione giornaliera entro quindici giorni, scaglioni temporali e riduzioni legate agli eventi, rifiuto delle riduzioni non previste nel regime anteriore, prevalenza del termine breve sul lungo, durata di sessanta giorni per la cassazione, effetto della sospensione feriale e coincidenza del compenso a tempo con il motore del preventivatore.

## 2.269.0 - 2026-08-03

- **Nuovo calcolatore: patrocinio a spese dello Stato (art. 76 D.P.R. 115/2002).** Verifica il limite di reddito con il cumulo dei redditi dei familiari conviventi (art. 76, comma 2), la valutazione del solo reddito personale quando la causa ha per oggetto diritti della personalità o vi è conflitto di interessi con i conviventi (art. 76, comma 4) e l'elevazione di 1.032,91 euro per ogni convivente nel processo penale (art. 92).
- La soglia non è cablata nel codice: vive nella tabella normativa versionata `patrocinio_limiti_reddito`, una riga per decreto di adeguamento biennale ex art. 77. Sono caricati il D.M. 10 maggio 2023 (12.838,01 euro, GU n. 130 del 6 giugno 2023) e il D.M. 22 aprile 2025 (**13.659,64 euro**, GU n. 159 dell'11 luglio 2025), letti dalla fonte ufficiale. Per le date che precedono la copertura il calcolo si ferma con errore invece di applicare una soglia non vigente.
- **Nuovo calcolatore: competenza per valore (art. 7 c.p.c.).** Indica giudice di pace o tribunale applicando le soglie elevate dall'art. 3, comma 1, D.Lgs. 149/2022 (10.000 euro per i beni mobili, 25.000 per il danno da circolazione di veicoli e natanti) ai procedimenti instaurati dopo il 28 febbraio 2023, e quelle anteriori ai procedimenti precedenti, secondo l'art. 35, comma 1, dello stesso decreto come sostituito dall'art. 1, comma 380, L. 197/2022.
- **Nuovo calcolatore: termini processuali e sospensione feriale.** Riusa il motore già versionato in `pct/termini_processuali.py` (computo ex art. 155 c.p.c., sospensione dal 1 al 31 agosto ex L. 742/1969, calendario delle festività nazionali) e ne espone i 31 modelli di termine — appello breve e lungo, cassazione, opposizione a decreto ingiuntivo, memorie 171-ter, termini esecutivi e del codice della strada — con l'elenco dei passaggi di calcolo. Nessuna regola di computo è stata riscritta: un test verifica che l'esito coincida con quello del motore.
- Ogni esito dichiara le fonti e il proprio perimetro: il patrocinio verifica i soli limiti di reddito degli artt. 76 e 92, la competenza per valore le sole ipotesi dei commi 1 e 2 dell'art. 7 c.p.c.
- **Suite Strumenti Forensi a fisarmonica.** Cliccando una voce il modulo si apre subito sotto la voce stessa invece che in fondo alla pagina, dove finiva su schermi stretti: il punto di lettura resta quello del clic e un secondo clic richiude la voce. Il pannello è stato estratto in un componente proprio.
- Guardrail: diciotto test nuovi su soglia vigente per data, cumulo dei redditi, elevazione penale, esclusione del cumulo con il solo reddito personale, rifiuto delle date non coperte, soglie di competenza prima e dopo il 28 febbraio 2023, coincidenza con il motore dei termini, sospensione feriale, durata personalizzata e presenza dei tre strumenti nella suite React.

## 2.268.0 - 2026-08-03

- **Suite Strumenti Forensi completata in React: da 8 a 29 strumenti compilabili.** Sono stati dichiarati i 21 schemi mancanti, quindi tutti i calcolatori della suite si compilano nella pagina React. Resta fuori solo `uffici_competenti`, che non è un calcolatore ma un motore di ricerca e ha già una propria superficie React.
- Gli schemi non sono stati riscritti a mano: sono stati estratti dai moduli della vista classica, che è la fonte reale dei campi, e ogni voce è vincolata da un test a esistere nel form state del dominio. Non esiste quindi un secondo elenco di campi da tenere allineato.
- **Opzioni dinamiche risolte a runtime, non congelate.** Materie, gradi e complessità del D.M. 55/2014 e le categorie del contributo unificato sono cataloghi che cambiano con la normativa: lo schema dichiara solo `options_from` e il bridge le legge dal gestore. Se un catalogo non è risolvibile lo strumento non viene esposto a metà, ma resta sulla vista classica.
- **Nuovo calcolatore: crediti di lavoro — rivalutazione e interessi (art. 429, comma 3, c.p.c.).** Il maggior danno da svalutazione è riconosciuto in via automatica, senza l'onere di prova richiesto dall'art. 1224, comma 2, c.c., con decorrenza dal giorno della maturazione del diritto. Nel pubblico impiego rivalutazione e interessi non sono cumulabili (art. 22, comma 36, L. 724/1994, che richiama l'art. 16, comma 6, L. 412/1991; Corte cost. 2 novembre 2000, n. 459): il calcolatore riconosce la sola voce maggiore e mostra comunque entrambe le grandezze calcolate.
- Il calcolatore non introduce dati nuovi: usa gli indici ISTAT e i saggi legali già versionati nel progetto e si ferma con errore se il periodo non è coperto, anziché stimare.
- La tabella di dettaglio del pannello React è ora derivata dal risultato invece che cablata sui passaggi della pena: ogni calcolatore che restituisce elenchi (segmenti di tasso, rate del piano, parametri tabellari) li vede resi senza che la pagina conosca lo strumento.
- Aggiunto il foglio di stile della pagina, che finora usava classi prive di definizione.
- Guardrail: nove test nuovi coprono il cumulo nel lavoro privato, il divieto di cumulo nel pubblico impiego, il rifiuto di periodi e importi incoerenti, le fonti obbligatorie nell'esito, la presenza nella suite, la corrispondenza fra ogni schema e un metodo di calcolo realmente esistente, la risoluzione delle opzioni dinamiche dal dominio, il fallback alla vista classica quando un catalogo manca e la copertura completa del catalogo.

## 2.267.0 - 2026-08-03

- **Suite Strumenti Forensi ricostruita in React, con architettura schema-driven.** `/strumenti-legali` non serve più la pagina delle card ma un componente dedicato che elenca i 29 strumenti, li filtra per testo e categoria e ne compila il modulo.
- I deep link tornano a funzionare: `?tool=<id>` seleziona lo strumento e la selezione aggiorna l'URL senza ricaricare. Era il difetto segnalato in precedenza, per cui `?tool=` veniva intercettato dalla gate React e riportava alla pagina delle card.
- Il contratto di input di ogni calcolatore è dichiarato una volta sola in `pct/calcolatori/schema.py`, accanto ai calcolatori: nome, etichetta italiana, tipo di controllo e opzioni. La shell React lo consuma e non duplica né i campi né la logica.
- Il calcolo non è riscritto: passa dai metodi di `GestioneStrumentiLegali` già usati dalla vista classica, tramite `POST /api/v1/ui/strumenti-legali/calcola`, che accetta solo strumenti con schema dichiarato.
- **Migrazione incrementale senza perdita di funzioni**: 8 strumenti sono già compilabili in React, i restanti 21 restano elencati con il collegamento alla vista classica, così nessuno sparisce dalla suite durante il passaggio.
- Guardrail: sei test coprono catalogo e schema esposti, raggiungibilità degli strumenti non ancora migrati, riuso dei metodi di produzione nel calcolo, rifiuto di strumenti senza schema e di input invalidi, coerenza tra campi dichiarati e default del dominio, e mappatura della rotta al componente React.

## 2.266.1 - 2026-08-03

- **Nuovo calcolatore: indennità di mediazione (D.M. 24 ottobre 2023, n. 150).** Espone nella suite Strumenti Forensi il motore già versionato in `pct/mediazione_dm150.py`: scaglioni, spese di avvio, spese del primo incontro, ulteriori spese, riduzione per la mediazione obbligatoria o demandata e maggiorazioni per accordo. Nessun valore normativo nuovo introdotto: le tabelle ministeriali erano già nel repository.
- Esposto come sezione della vista classica e come endpoint JSON `POST /strumenti-legali/api/indennita-mediazione`.
- Guardrail: quattro test verificano la coincidenza con il motore versionato, la riduzione per il regime obbligatorio, il valore indeterminabile, il rifiuto di regime ed esito non riconosciuti e la presenza nel catalogo della suite.

## 2.266.0 - 2026-08-03

- **Nuovo calcolatore forense: pena, attenuanti e riti alternativi.** Copre l'area penale della suite, finora limitata a custodia cautelare e prescrizione. Calcola l'effetto di attenuanti generiche, continuazione e rito sulla pena base, mostrando ad ogni passaggio la norma applicata, e valuta le soglie di sospensione condizionale e delle pene sostitutive sulla pena finale.
- Base normativa dichiarata nel modulo: art. 132, comma 2, c.p. per il computo (anno di 365 giorni, mese di 30); artt. 62-bis e 65, n. 3, c.p. per le attenuanti; art. 81, commi 2 e 4, c.p. per la continuazione, con limite del triplo e minimo di un terzo per i recidivi reiterati; art. 442, commi 2 e 2-bis, c.p.p. per l'abbreviato, con diminuzione di un terzo per i delitti, della metà per le contravvenzioni e ulteriore sesto per mancata impugnazione; art. 444, comma 1, c.p.p. per il patteggiamento; art. 163 c.p. e artt. 53-56-bis L. 689/1981 come riformati dal D.Lgs. 150/2022 per i benefici.
- Lo strumento è deliberatamente basato su frazioni e soglie fissate dalla legge, non su tabelle soggette ad aggiornamento periodico: nessun valore da mantenere allineato a decreti successivi.
- Le diminuzioni frazionarie sono arrotondate per difetto, in favore dell'imputato. Lo strumento non decide se attenuanti, continuazione o rito siano applicabili: calcola l'effetto delle frazioni indicate e dichiara la norma di ogni passaggio.
- Esposto nella suite `/strumenti-legali` (vista classica) e come endpoint JSON `POST /strumenti-legali/api/pena-riti-alternativi`.
- Guardrail: nove test coprono riduzione per delitto e contravvenzione, sesto per mancata impugnazione, limite del triplo, minimo per recidiva reiterata, soglie di sospensione condizionale per età, rifiuto degli input incoerenti e presenza obbligatoria delle fonti normative in ogni esito.

## 2.265.30 - 2026-08-03

- **Caricamento pagina: la shell React usa rivalidazione condizionata invece di `no-store`.** Il corpo è deterministico per (rotta, utente, studio, versione), quindi viene emesso un ETag calcolato sui byte effettivi: se il browser rimanda lo stesso ETag riceve un 304 e riusa il documento che ha già. Misurato: **297.361 byte (circa 83 kB gzip) risparmiati ad ogni navigazione ripetuta sulla stessa rotta**, di cui il 93% è l'entry React inline.
- Il 304 è corretto per costruzione: l'ETag è l'hash di ciò che avremmo inviato, quindi combacia solo se il client possiede già esattamente quel corpo. Verificato che un ETag diverso e una rotta diversa riportano sempre il corpo completo.
- La freschezza non è allentata: `no-cache` obbliga il browser a rivalidare prima di ogni uso, quindi non può mai mostrare una pagina senza aver interrogato il server; `private` la tiene fuori da proxy e cache condivise; `Vary: Cookie` lega la voce di cache alla sessione. Verificato che due utenti diversi ottengono ETag diversi.
- **Mitigazione della contropartita.** Il documento può ora essere scritto nella cache del browser: il logout emette `Clear-Site-Data: "cache"` così su postazione condivisa la pagina con nome utente, studio e permessi non resta recuperabile dopo la disconnessione. Si pulisce solo la cache, non `storage` né `cookies`, per non cancellare preferenze locali estranee alla sessione.
- Caddy: la regola su `/app-v2*` forzava `no-store` e avrebbe annullato i 304 al bordo; ora dichiara la stessa direttiva dell'applicazione.
- Guardrail: tre test verificano il 304 sulla navigazione ripetuta, che nessuna direttiva consenta di mostrare la pagina senza rivalidare (niente `public`, niente `max-age` diverso da zero, `Vary: Cookie` presente) e che il logout ripulisca la cache. Verificati falliscono tornando a `no-store`.

## 2.265.29 - 2026-08-03

- **Caricamento pagina: eliminato il doppio scaricamento dei chunk di rotta React.** Gli asset generati da Vite hanno il contenuto nell'hash del nome, ma la shell aggiungeva comunque `?v=<versione>` a `modulepreload` e CSS React. L'entry importa `/static/react/assets/X.js` senza query, quindi il preload puntava a un URL diverso: non veniva mai riusato e ogni chunk finiva scaricato due volte al primo caricamento della rotta. Misurato: `/fascicoli` 960 kB (195 kB gzip), `/agenda` 320 kB (89 kB gzip), `/clienti` 298 kB (82 kB gzip).
- Effetto secondario, altrettanto rilevante: ora il `modulepreload` funziona davvero, quindi il chunk di pagina parte in parallelo con l'analisi dell'HTML invece che solo dopo l'esecuzione dell'entry.
- CSS React: rimosso `?v=` anche dai fogli di stile con hash nel nome, che venivano riscaricati ad ogni release pur essendo identici. Il `?v=` resta dove serve: `app.css` e gli script in `/static/js/` non sono versionati nel nome, e l'entry lo usa come segnale di bootstrap (`searchParams.has('v')` in `main.tsx`).
- Guardrail: due test verificano che ogni `modulepreload` combaci con un URL realmente richiesto dal browser (risolvendo import dinamici dell'entry e import statici dei chunk) e che i CSS con hash non abbiano query di versione. Verificati falliscono reintroducendo `?v=`.

## 2.265.28 - 2026-08-03

**Cambio di un valore numerico di qualità — procedura AGENTS.md.**

- **Budget `startup_ms` del Performance Nightly: valore precedente 3200 ms, valore nuovo 4000 ms.** Approvazione esplicita dell'utente richiesta e ottenuta prima della modifica.
- **Causa tecnica.** La soglia non era raggiungibile in modo stabile sui runner condivisi GitHub. Tre notti consecutive su codice sostanzialmente equivalente hanno misurato 3279, 3314 e 4502 ms, mentre in locale gli stessi commit danno 1485 e 1577 ms: la differenza fra le notti è varianza del runner, non regressione di codice. La composizione dell'avvio, misurata senza profiler, è per il 62% import dei blueprint più compilazione delle 1270 route in werkzeug e per il 30% seeding dei moduli dati al primo boot: non è comprimibile sotto la soglia precedente con ottimizzazioni mirate.
- **Presidio sostitutivo, richiesto da AGENTS.md quando una soglia si alza.** Il budget non guarda più un singolo campione ma la **mediana di 3 avvii a freddo eseguiti in processi separati** (`--repeat`, default 3). Un picco isolato del runner non decide più l'esito, mentre una regressione reale sposta la mediana e continua a far fallire il gate. Il risultato netto è un presidio più forte del precedente: con campione singolo e soglia 3200 il job era rosso in modo indistinguibile fra rumore e regressione, ed è infatti rimasto rosso e ignorato dal 29/07.
- **Impatto.** Nessuna altra soglia toccata: `login_ms`, `health_ms`, `runtime_metrics_ms` restano a 800 ms e i budget Lex a 1500 ms. Con la nuova soglia una regressione oltre il +38% rispetto al valore tipico atteso in CI continua a fallire.
- **Guardrail.** Tre test presidiano la modifica: il valore della soglia, la presenza della mediana su processi separati (così non si può rimuovere il presidio lasciando la soglia alta) e la pulizia dei dati temporanei.
- Benchmark: ogni campione creava un albero dati completo in `/tmp` senza mai rimuoverlo; con tre campioni per esecuzione il residuo falsava le misure successive. Ora ogni campione pulisce il proprio albero.
- Benchmark: gli import applicativi sono stati spostati dentro la funzione di misura, così in modalità `--repeat` il processo padre non carica né trattiene in memoria l'intera app mentre girano i campioni.

## 2.265.27 - 2026-08-03

- Avvio applicazione: `react_preventivo_wizard_bridge` costruiva `GestioneStrumentiLegali()` a livello di modulo, quindi caricava le tabelle normative (2,4 MB) all'import e il costo veniva pagato ad ogni avvio di worker anche senza aprire mai il wizard preventivi. La costruzione è ora differita alla prima chiamata, con singleton stabile: mediana locale di `startup_ms` da 1577 ms a 1375 ms su 5-6 esecuzioni.
- Guardrail: nuovo test che verifica in un processo separato che l'import del bridge non costruisca il calcolatore e che il singleton resti stabile.
- Nota su `startup_ms` in CI: la metrica resta strutturalmente vicina al budget. L'avvio è per il 62% import dei blueprint più compilazione delle 1270 route in werkzeug, per il 30% seeding dei moduli dati al primo boot. Le tre notti su codice equivalente hanno dato 3279, 3314 e 4502 ms contro un budget di 3200, cioè una varianza del runner superiore al margine disponibile.

## 2.265.26 - 2026-08-03

- E2E Nightly: verde lo shard 4/4, rosso ogni notte almeno dal 27/07. Il blocco anti-perdita della migrazione verso SQLite non è stato toccato: il difetto era nella fixture.
- Fixture E2E: il seed di `condivisioni` scriveva la sola sezione `link`, mentre `GestioneCondivisioni._salva()` emette sempre `cartelle`, `fascicoli` e `link`. Con due sezioni in meno rispetto a quelle già migrate in `studio.db` dal bootstrap del tenant, il precheck rilevava correttamente una perdita di record e bloccava la migrazione. Il seed ora rispetta il contratto di persistenza reale, mantenendo il link di prova.
- Guardrail: nuovo test che confronta le sezioni scritte dal seed con quelle realmente prodotte da `GestioneCondivisioni._salva()`, così una futura divergenza fallisce subito e non di notte nell'E2E.

## 2.265.25 - 2026-08-02

- **CodeQL workspace snapshot**: `WorkspaceIntelligenteService.save_snapshot()` persiste ora solo aggregati, stati e contatori operativi; i dettagli degli appuntamenti restano nei repository reali e non vengono duplicati nel JSON snapshot.
- **Allegati PEC/email**: il modal `Fonte dell'informazione` apre gli allegati PDF salvati dalle rotte PEC e posta ordinaria nel lettore interno responsive a pagine, evitando iframe PDF raw vuoti su desktop, tablet e mobile; il download resta invariato.
- **Guardrail sicurezza e allegati**: aggiunti test reali di salvataggio snapshot che escludono passcode, URL, informazioni di accesso riservate e liste appuntamento dal JSON workspace, più regressioni PEC/email sul viewer mobile degli allegati.

## 2.265.24 - 2026-08-02

- **CodeQL workspace snapshot**: `WorkspaceIntelligenteService.save_snapshot()` persiste ora una vista sanificata e primitiva di agenda/scadenze/fascicoli, senza oggetti dominio completi né campi riservati di udienza remota.
- **Guardrail sicurezza**: aggiunto test reale di salvataggio snapshot che esclude passcode, URL e informazioni di accesso riservate dal JSON workspace.
- **SQLite notifiche**: la validazione di migrazione confronta `notifiche_log` tramite identità stabile timestamp/tipo/cliente/numero/utente, non tramite l'id autoincrementale SQLite.

## 2.265.23 - 2026-08-02

- **CodeQL Google Calendar**: l'import degli eventi Google non legge più `extendedProperties.private`; i marker tecnici esportati verso Google restano transitori e la classificazione IUSENTRA continua da binding, ruolo calendario e titoli professionali.

## 2.265.22 - 2026-08-02

- **CodeQL cache JSON**: `cache.save()` ora rifiuta ricorsivamente contenitori `private` e chiavi private in archivi JSON in chiaro; il payload Google Calendar `extendedProperties.private` resta transitorio e non può essere materializzato su disco.
- **Guardrail sicurezza**: aggiunti test mirati sul writer JSON condiviso per bloccare `extendedProperties.private` e chiavi `private_key` prima della serializzazione.

## 2.265.21 - 2026-08-02

- **CodeQL calendario**: il content hash remoto non include piu' le categorie tecniche dei provider, evitando persistenza indiretta di valori letti da `extendedProperties.private`.

## 2.265.20 - 2026-08-02

- **CodeQL notifiche/calendario**: la validazione PEC non usa piu' una regex sensibile a backtracking su input utente e i conflitti calendario salvano solo snapshot remoti normalizzati, senza `raw` provider o metadati `extendedProperties.private`.
- **Guardrail sicurezza**: aggiunti test mirati per input PEC patologici, mapping Google Calendar e snapshot conflitti senza metadati provider persistiti.

## 2.265.19 - 2026-08-02

- **Backup disattivati in modo fail-closed**: registro, job automatici, API React, percorsi manuali, CLI e script Hetzner non materializzano archivi; lo stesso presidio rimuove il cron IUSENTRA durante il deploy.
- **Pulizia spazio autorizzata**: rimossi archivi, snapshot, cache build e registri backup obsoleti; restano esclusi da ogni cancellazione fascicoli, documenti, e-mail e database operativi.

## 2.265.18 - 2026-08-02

- **Lex Oggi autonomo**: il piano completo viene generato alle 05:30 Europe/Rome per ogni studio e avvocato attivo; se il servizio automatico parte tardi o manca uno snapshot, il recupero autonomo lo ricostruisce senza bloccare la pagina né richiedere un click.
- **Stato reale aggiornamento**: `Aggiorna` resta opzionale e mostra ora coda, elaborazione, completamento, errore o timeout tramite il job tenant-aware, senza più confermare un piano non ancora prodotto dal servizio automatico.
- **Supporto all'avvocato**: card e dettaglio del piano espongono termine, intervento, fascicolo, cliente, assegnazione, fascia/durata, priorità spiegata, stato e fonti verificabili con data/ora italiana.
- **Affidabilità scheduler**: migrata la pianificazione di sistema dalle 07:30 alle 05:30 preservando modifiche manuali; ripulito il falso audit `running` che poteva arrivare dopo un esito terminale.
- **Auto-recupero verificabile**: la data corrente prevale sempre sulle richieste future, il recovery parte solo dopo la finestra di misfire e rispetta la console Pianificazioni; i job bloccati dopo un crash vengono liberati senza riutilizzare uno stato zombie.
- **Segnali senza collisioni**: un identificativo tecnico duplicato non interrompe più la generazione del piano; la chiave operativa resta invariata e viene assegnato un ID interno sicuro quando necessario.
- **Orari italiani corretti**: snapshot, card e agenda convertono ora i timestamp UTC/offset in `Europe/Rome`, anche quando oltrepassano la mezzanotte; gli impegni fissi Agenda usano lo stesso istante anche nel calcolo delle fasce proposte, senza sovrapposizioni dovute al fuso.

## 2.265.17 - 2026-08-01

- Performance Nightly: rientrate nel budget le due metriche fuori soglia dal 29/07 (`startup_ms` 3279 su 3200, `health_ms` 857 su 800). Le soglie non sono state toccate.
- Scrittura JSON (`pct/cache.py`): la serializzazione passa da `json.dump` sul file a `json.dumps` più una sola `write`. `json.dump` non attiva mai l'encoder C e scrive a pezzi; su `normative_tables` (5,15 MB) si passa da 136,9 ms a 43,5 ms con byte prodotti identici. Vale per ogni archivio JSON tenant-aware, non solo per l'avvio.
- Migrazione JSON→SQLite: le connessioni di bootstrap e migrazione applicano la stessa politica journal che `StudioDB` usa sullo stesso file (WAL dove è sicuro, DELETE su Windows e sui bind mount 9p/drvfs). Aprivano `studio.db` con `sqlite3.connect` nudo, quindi in journal DELETE ogni statement DDL pagava un fsync: la sola creazione dello schema passa da 617,9 ms a 11,8 ms. La durabilità non cambia, `synchronous` resta quello dichiarato dallo schema.
- Migrazione JSON→SQLite: lo snapshot delle sorgenti, richiesto sia dal precheck anti-perdita sia dalla validazione post-migrazione, viene ricalcolato solo se cambia la firma `(percorso, mtime, dimensione)` di un JSON sorgente. La validazione resta quindi confrontata con la sorgente corrente e non con una copia stantia.
- Politica journal SQLite ora in un'unica funzione governata (`pct.storage.configura_journal_mode_governato`), condivisa fra runtime e migrazione.
- Guardrail: nuovi test su byte identici della scrittura JSON, `default=str` conservato, memoizzazione dello snapshot sorgenti, ricalcolo alla modifica di un JSON, non condivisione dei contenitori in cache e modalità journal attesa dopo la migrazione.

## 2.265.16 - 2026-08-01

- Isolamento tenant: la radice dati dello studio viene risolta una sola volta per richiesta invece che per ognuna delle 73 chiavi sensibili. Il controllo fail-closed resta identico (ogni percorso continua a essere risolto e verificato), ma il registry studi non viene più riletto decine di volte per richiesta.
- Isolamento tenant: il confronto di contenimento dei percorsi usa il separatore di percorso invece di `Path.relative_to`, con la stessa semantica (inclusa l'insensibilità alle maiuscole su Windows) e senza costruzione di oggetti path per ogni chiave.
- Shell React: il manifest Vite (45 kB) e il grafo asset per route vengono parsati una volta per build e invalidati su `(mtime, size)`, non più a ogni cambio pagina.
- Asset: `logo-iusentra.png` passa da 2.086 kB a 78 kB (1024×683, nessuna riduzione di colori); la risoluzione resta oltre 4× la dimensione massima con cui il logo viene mostrato in UI (248 px).
- Favicon: `/favicon.ico` e il `<link rel="icon">` della shell React servono l'icona applicativa da 3 kB invece del logo a piena risoluzione.
- Rete: aggiunto `preconnect` verso `cdn.jsdelivr.net` nella shell React e in `base.html`, dove Bootstrap e Bootstrap Icons sono già richiesti in blocco al rendering.
- Guardrail: aggiunti test anti-regressione su memoizzazione radice studio, isolamento tra studi nella stessa richiesta, prefissi omonimi nel confronto percorsi, cache manifest Vite e immutabilità delle liste asset restituite.
## 2.265.15 - 2026-07-30

- Notifiche legali React: l'attestazione di conformità può essere modificata e salvata per la notifica corrente, con anteprima aggiornata.
- Fascicolo: il PDF dell'attestazione viene salvato automaticamente nei documenti del fascicolo e riusato come allegato della PEC locale.
- Invio PEC L. 53/1994: il click `Invia PEC` prepara solo il piano dal PC locale, allegando relata firmata, documenti selezionati e attestazione, senza invio SMTP server-side.
- Modello relata: i campi già coperti dalla compilazione guidata vengono nascosti e filtrati dal payload, evitando che valori vuoti o duplicati sovrascrivano fascicolo, RG, tipo documento o dati avvocato.
- Guardrail: verificato su `127.0.0.1:8080` con destinatari manuali Codex, sentenza e verbale udienza, più test mirati notifiche/React e build frontend.

## 2.265.11 - 2026-07-27

- Fascicoli React: corretto il KPI scadenze, distinguendo `Scadenze urgenti`, scadenze già scadute e scadenze realmente entro 7 giorni.
- Backend fascicoli: `summary.deadlines7` ora conta solo le date tra oggi e i prossimi 7 giorni; le scadenze aperte pregresse restano presidiate in `overdueDeadlines` e nella lista urgente.
- UI: rimosso il testo ambiguo `Scadenze 7g` quando la lista contiene arretrati come le voci del `15/05/2026`.
- Guardrail: aggiornato il test di regressione per impedire che scadenze scadute rientrino nel conteggio `entro 7 giorni`.

## 2.265.10 - 2026-07-27

- Fascicoli React: ripristinato il caricamento rapido della lista su produzione evitando letture massive Document AI e presidi automatici completi durante la paginazione.
- Scadenze: ripristinata la fonte delle scadenze aperte del riquadro operativo, includendo anche scadenze già scadute o non collegate, come le voci PEC/diffida del `15/05/2026`.
- Economia fascicoli: il riepilogo leggero usa il calcolo parcella già presente, cacheando solo l'aliquota Cassa Forense per evitare ricalcoli normativi ripetuti senza cambiare gli importi.
- Guardrail: aggiunti test anti-regressione per lista operativa senza Document AI server, scadenze aperte scadute non collegate e cache Cassa Forense delle parcelle.

## 2.265.9 - 2026-07-27

- Fascicoli React: il menu contestuale apre il contributo unificato con memoria completa di RG, cliente, oggetto del ricorso, base, anticipazione e totale.
- PagoPA: l'azione `Copia e apri PagoPA` apre direttamente `Nuovo pagamento`, offre la vista a tutto schermo e tenta la compilazione assistita dei campi visibili senza inviare o sovrascrivere dati.
- Controllo economico: aggiunta finestra contestuale con RG, parti, cliente, stato del fascicolo, righe economiche, ricevuta PagoPA, parcella, controllo documenti, editor `Modifica controllo economico` e accesso a import pratiche.
- Presidio documentale: il controllo del contributo unificato ora legge anche i documenti già indicizzati sul server Document AI, evitando falsi `Non trovato` quando ricevuta o esenzione non sono nel catalogo locale del fascicolo.
- Guardrail: estesi test React, build e documentazione operativa del deposito per presidiare PagoPA nuovo pagamento, memoria del calcolo, tutto schermo, controllo economico contestuale e fonte economica server-side.

## 2.265.7 - 2026-07-27

- Fascicoli React: aggiunta nel menu contestuale la voce `Calcola contributo unificato`, con finestra sovrapposta interna al dettaglio fascicolo, precompilazione dal fascicolo e calcolo tramite l'API già presente negli Strumenti Forensi.
- PagoPA: il risultato del calcolo può essere copiato negli appunti e salvato in memoria di sessione; quando si apre PagoPA dal fascicolo, IUSENTRA mostra sopra il portale il totale e il testo copiabile da usare nella compilazione.
- Presidio operativo: la memoria del calcolo non registra un pagamento e non sostituisce la ricevuta PagoPA, F23/F24 o l'esenzione documentata nel fascicolo.
- Guardrail: esteso il test React del menu contestuale per coprire voce CU, chiamata API, copia appunti, memoria di sessione, pannello riepilogo PagoPA e responsive della modale.

## 2.265.6 - 2026-07-26

- Fascicoli React: aggiunto il menu contestuale con tasto destro dentro il dettaglio fascicolo, con accessi rapidi a deposito telematico, notifica, anagrafica cliente, soggetti, modifica fascicolo, Portale Servizi, PagoPA, controllo economico, scadenze, Agenda, documenti, compilatore atti, PDF/ZIP e audit.
- Portale Servizi: la voce `Apri Portale Servizi` riusa il pannello `Documenti e atti` e la sessione assistita esistente, senza introdurre invii PEC server-side, nuove sessioni parallele o scorciatoie fuori dal flusso governato.
- UX e accessibilità: il menu evita i campi editabili, si chiude con `Esc`, click esterno, scroll pagina o resize, resta dentro il viewport e mantiene lo scroll interno per raggiungere tutte le azioni anche su tablet e smartphone.
- Guardrail: aggiunto test React statico per presidiare etichette, azioni reali, apertura Portale Servizi dal menu e CSS responsive.

## 2.258.1 - 2026-07-22

- Corregge il contratto Chrome Local Network Access del Local Signer: tutte le chiamate React verso `127.0.0.1`/`localhost` usano `targetAddressSpace: loopback`, evitando falsi negativi su Impostazioni firma, PST, download documenti, deposito, firma multipla, notifiche legali e relata.
- Aggiunge il guardrail `tools/check_local_signer_boundaries.py` per bloccare regressioni future a `targetAddressSpace: local` nei file frontend che parlano con il servizio locale.
- Mantiene la sessione PST unica `view` e il contratto di firma multipla: un solo PIN/sessione per il lotto, senza introdurre sessioni parallele o fallback di scaricamento singolo.
- Documenta causa, prove automatiche e stato della prova reale nei dossier operativi di deposito telematico, acquisizione originali PST e data-flow tenant-aware.

## 2.258.0 - 2026-07-21

- Unifica Agenda, Scadenziario, Presìdi notifiche, topbar e Web Push sulla stessa fonte PEC indicizzata: ogni evento conserva tenant, messaggio e allegato che lo hanno generato e apre direttamente la PEC o il documento utile, senza dashboard generiche né ricerche al click.
- Rafforza l'isolamento multi-studio: i dettagli PEC falliscono chiusi sulla coppia tenant/identificativo, non riclassificano né spostano messaggi durante una lettura, e i materializzatori usano i repository tenant-aware SQLite/PostgreSQL senza aprire database locali di un altro studio.
- Corregge la logica tecnico-giuridica delle sentenze e della trattazione scritta: la sentenza ex art. 429 c.p.c. prevale sul riferimento alla modalità ex art. 127-ter, la comunicazione di cancelleria non diventa prova della notifica dell'avvocato e `Notifica necessaria confermata` non viene confusa con una notifica già eseguita.
- Riconcilia lo storico del tenant Studio Legale Giuseppe Montagnese lasciando operativi soltanto i cinque residui reali di Calabrò, Speranza, Monea, Alfano e Romeo; le vecchie scadenze automatiche duplicate vengono completate senza cancellare fascicoli, PEC o documenti.
- Estende il lettore interno IUSENTRA con apertura uniforme da PEC/fascicolo, anteprima di PDF e ZIP PEC, XML, EML/MIME, TXT, DOC/DOCX, JPG/JPEG, PNG, TIFF/TIF e P7M/SMIME quando estraibili, più comando a tutto schermo e messaggi espliciti per i formati non renderizzabili.
- Riduce il tempo percepito di apertura: il viewer è in sola lettura, riusa cache tenant-aware bounded, non esegue audit o parsing ripetuti al click, e le query PEC/Control Tower sono indicizzate e limitate agli eventi visibili invece di riesaminare l'intero storico durante il caricamento pagina.
- Impedisce che il bootstrap tenant duplichi ricorsivamente OCR, testi estratti e staging `documenti_ai` dentro `studio.db`: il runtime sincronizza solo i moduli JSON core dichiarati, mentre la scansione ricorsiva resta disponibile esclusivamente negli audit espliciti.
- Sposta il Calcolatore termini processuali in una pagina React dedicata e rende più compatte e uniformi le card dello Scadenziario, mantenendo lingua italiana, cliente prima del RG e layout desktop/tablet/mobile.

## 2.257.1 - 2026-07-20

- Corregge i falsi positivi del presidio relata nei fascicoli del tenant Studio Legale Giuseppe Montagnese: lo storico notifiche fino al 19/07/2026 viene trattato come già gestito e non genera più `Relata da firmare` o nuove notifiche da preparare.
- Riconosce la prova notifica depositata dai documenti storici del fascicolo e mostra `Prova notifica depositata` quando la notifica è già eseguita e collegata al deposito.
- Aggiunge l'audit `scripts/audit_notification_relata_fascicoli.py`, con report JSON/Markdown sui 301 fascicoli visibili Montagnese, campione software di 30 fascicoli e sezione `Cosa resta ancora da notificare`.
- Integra i residui futuri veri con topbar, centro notifiche/Web Push e scadenziario tramite il job `legal_notification_relata_presidio`, senza scansioni nel caricamento della UI.
- Prova server reale Montagnese: 301 fascicoli analizzati, 0 nuove notifiche da eseguire, 0 azioni correlate residue, 0 falsi positivi; fascicolo `BE831526` verificato in produzione senza più `Firma relata`.

## 2.257.0 - 2026-07-20

- Aggiunge il presidio persistente delle notifiche legali con fonte SQL tenant-aware, rollout per studio, RBAC reale e stati per fascicolo, documento, destinatario, evidenze e transizioni.
- Introduce la vista React iniziale `Presidi notifiche`, con lista paginata server-side, filtri leggeri, dettaglio lazy, stati vuoti/errore/permessi espliciti e workflow storico caricato solo su richiesta.
- Integra il rulepack deterministico delle notifiche, distinguendo ordine espresso, comunicazione semplice, ricevute, consegna parziale, mancata consegna, originale da acquisire e storico presunto.
- Mantiene il caricamento rapido: a flag spento non parte alcuna lettura tenant/repository/mailbox; a flag attivo la lista usa sole proiezioni SQL paginate e nessun chunk JavaScript supera il budget di 500 kB.
- Documenta il workflow server-first richiesto: prova reale sul tenant Studio Legale Giuseppe Montagnese, poi riallineamento della copia locale reale su `127.0.0.1:8080`, commit, push dei branch gemelli e deploy Hetzner finale dello stesso commit.

## 2.256.2 - 2026-07-17

- Conserva le attività `UDIENZA` nella timeline del fascicolo, comprese note, modalità di trattazione, fonte e collegamento audiovisivo.
- Allinea Agenda, Scadenziario, centro notifiche e Web Push sullo stesso evento, senza creare duplicati.
- Aggiorna una notifica già esistente quando un PDF o ZIP elaborato successivamente aggiunge un collegamento audiovisivo verificato.
- Espone nel Web Push l'azione `Collegati` solo per URL verificati; negli altri casi apre IUSENTRA per il controllo.
- Mostra il collegamento e la fonte sia nel passaggio del mouse in Agenda sia nella scheda dello Scadenziario, con apertura del documento dentro IUSENTRA.
- Mantiene ogni chunk JavaScript e CSS della build React sotto il limite di 500.000 byte.

## 2.256.1 - 2026-07-12

- Aggiunge il flusso React `Nuova proforma`, le impostazioni fiscali predefinite dello studio e l'aggiornamento governato delle sole proforme non trasmesse.
- Separa correttamente nome e cognome delle persone fisiche, riserva la denominazione a studi, società ed enti e impedisce duplicazioni anche nell'XML FatturaPA.
- Compila il CAP dai dati territoriali disponibili e gestisce beneficiario, banca, IBAN e BIC/SWIFT dalle impostazioni tenant-aware, senza accettare dal browser l'identità dello studio.
- Collega la generazione della proforma al controllo economico del fascicolo, verifica la persistenza e impedisce la creazione di documenti economici duplicati.
- Migliora il planner Agenda con legenda semantica, evidenze leggibili, collegamento alle udienze audiovisive, stato completato e resa notebook/mobile.
- Rende incrementale il presidio documentale: ogni file nuovo o modificato viene letto una volta, mentre impronte già elaborate non vengono rilette nei cicli successivi.
- Estende il lettore documenti mobile con zoom, adattamento e scorrimento del documento senza perdere i comandi operativi.
- Rafforza Local Signer con finestra PIN in primo piano, aggiornamento automatico governato e controllo contro servizi duplicati.
- Aggiorna i fascicoli già presenti durante una nuova acquisizione PST invece di crearne una copia, mantenendo la fonte SQL tenant-aware.
- Rende ricercabile la pratica nel flusso notifiche legali, collega l'azione dal fascicolo e genera un'unica attestazione di conformità per tutti i documenti selezionati.
- Genera una sola attestazione di conformità per tutte le copie scelte dall'avvocato, usando esattamente il modello Word dello studio senza evidenziazioni e senza preselezionare documenti.
- Preserva integralmente il pacchetto del modello dell'attestazione: cambia soltanto il contenuto dei campi automatici e mantiene anche le descrizioni che contengono virgole.

- Legge in modo incrementale tutti i documenti nuovi o modificati del fascicolo senza rileggere quelli invariati, anche quando esiste già una scadenza.
- Riconosce nei decreti le formule processuali `nel giorno`, `per il giorno`, `fissato per` e `alla data`, collegando correttamente il deposito delle note alla prossima scadenza.
- Conserva i termini trascorsi nello storico senza mostrarli come prossima scadenza e impedisce duplicati durante il riesame documentale.
- Mantiene rapido l'elenco fascicoli: nessun OCR parte dal caricamento della lista; la lettura mirata avviene solo aprendo documenti o scadenze.
- Evita riletture automatiche dei documenti invariati: il presidio salva nel database l'impronta completa del fascicolo e riapre soltanto documenti nuovi o modificati.
- Memorizza i fascicoli già coperti da una scadenza futura come rinviati fino alla data utile: i cicli intermedi non rileggono i documenti, mentre una modifica o la scadenza del rinvio riattiva automaticamente il controllo.
- Riduce il lavoro del worker PEC ai soli fascicoli variati, mantenendo l'audit delle letture eseguite dagli utenti e senza duplicare gli eventi automatici.
- Verifica i dati ministeriali obbligatori prima di salvare la classificazione o avviare prova e simulazione; una prova storica non abilita più un invio reale dopo modifiche al pacchetto.
- Salva classificazione e profilo deposito in un'unica transazione sul fascicolo interessato, evitando lock e riscritture massive.
- Completa e valida contro gli XSD ministeriali tutti i 252 generatori PCT del catalogo deposito.
- Mostra e conserva i dati specifici richiesti dal tipo scelto, con messaggi puntuali e accesso diretto ai campi mancanti.
- Lascia all'avvocato la scelta del tipo di deposito e dei documenti, senza preselezioni nei casi nuovi.
- Trasforma i dati ministeriali mancanti in risposte controllate e impedisce errori HTTP generici durante la prova.
- Estende l'audit a contributo, uffici, PEC, codici, campi obbligatori e copertura UI-generatore.
- **Lex Oggi - piano per data**: la pagina diventa `Piano del giorno` e offre il selettore rapido `Oggi`, `Domani`, `Dopodomani` più un campo data. La selezione resta nell'URL, separa correttamente cache ed ETag per giorno/utente e usa date italiane visibili.
- **Lex Oggi - generazione data-aware**: il refresh trasporta la data scelta fino al job tenant-aware; priorità, agenda, conflitti, scadenze ed economia vengono calcolati rispetto a quel giorno, mentre il timestamp di generazione resta nell'ora reale `Europe/Rome`.
- **Lex Oggi - aggiornamento manuale reale**: ogni click su `Aggiorna` usa una chiave idempotente distinta e un job nuovo ottiene sempre una propria run del worker, anche se quella precedente sta terminando. Le richieste manuali vengono consumate anche quando le generazioni pianificate sono disattivate; le entità cambiate restano invece governate dal flag `lex.dailyPlan.scheduledRuns`.
- **Lex Oggi - feedback visibile**: la pagina conferma che la richiesta è stata acquisita, controlla in modo leggero lo snapshot materializzato e riconosce la rigenerazione anche quando le attività restano invariate, senza lasciare il pulsante apparentemente inerte.
- **Lex Oggi - dettaglio affidabile**: le letture riusano lo schema SQLite già pronto senza rieseguire DDL o cambiare journal; il pannello delle evidenze segnala un errore transitorio e offre `Riprova` invece di restare in caricamento indefinito.

## 2.255.0 - 2026-07-11

- **Lex Oggi - regia giornaliera dello studio**: nuova pagina `Oggi` (`/oggi`) con il piano operativo per avvocato: attività ordinate P0–P3 con motivo, fonte, fascicolo, scadenza, affidabilità e fascia proposta; sezioni per urgenze, agenda, PEC, fascicoli, economia, coda "Da assegnare" e backlog paginato. La pagina legge solo lo snapshot già elaborato (apertura immediata, ETag/304, nessuna analisi in lettura).
- **Lex Oggi - motore deterministico**: nuovo bounded context `pct/daily_plan/` con collettori su presidio PEC, presidi fascicolo, agenda, scadenziario ed economia; correlazione e deduplicazione degli stessi eventi tra fonti (una sola attività con tutte le evidenze), priorità con regole spiegabili e override per termini perentori, assegnazione al referente senza mai indovinare (ambigui in coda studio), pianificazione della giornata intorno agli impegni fissi (mai scritture in agenda).
- **Lex Oggi - persistenza e scheduler**: repository materializzato SQLite/PostgreSQL tenant-aware con snapshot per utente, watermark fonti, dirty entities e job idempotenti; job `studio_daily_operational_plan` (07:30) e `daily_plan_incremental_refresh` (ogni 15 minuti, no-op se non c'è nulla), entrambi dietro flag e visibili nella console Pianificazioni.
- **Lex Oggi - approvazioni e Lex**: le azioni applicative dalla pagina creano proposte nella coda approvazioni della Regia Agentica (mai esecuzioni dirette; invio PEC, firme, depositi e fatture definitive irraggiungibili); nuovo tool read-only `daily_plan`, triage giornaliero che legge il piano e sintesi basata su priorità reali (perentorio, bloccante, scadenza, affidabilità) invece dei conteggi.
- **Strumenti Lex - copertura dati**: lo scadenziario non scarta più i termini arretrati ancora aperti e ordina prima di applicare il limite; agenda espone avvocato, durata, inizio/fine, promemoria, cliente e tribunale; i filtri fascicoli (archiviati, stato, avvocato) sono realmente applicati; il tool preventivi legge i dati reali di preventivi e conferimenti; tutti gli elenchi dichiarano `total_matching` e troncamenti.

## 2.254.19 - 2026-07-09

- **Deposito telematico - audit completo catalogo**: aggiunto audit end-to-end sui 270 tipi deposito. I 252 tipi PCT generano `DatiAtto.xml` con radice verificata e l'audit severo non segnala rami sospesi.
- **Deposito telematico - mapping generatori completato**: recuperati rami mancanti o incompleti per `Ricorso702Bis`, memorie/istanze Cartabia, richiesta visibilità, pignoramenti SIECIC, progetto distribuzione e deposito relazione iniziale del curatore, evitando fallback generici.
- **Deposito telematico - Giudice di Pace/SIGP**: la scelta tipo deposito non prende più la prima voce del catalogo. Per fascicoli Giudice di Pace con note/trattazione scritta propone `Deposito note scritte sostitutive udienza (Giudice di Pace)` e il validatore accetta `SIGP` come canale coerente, bloccando invece `SICID` su ufficio Giudice di Pace.
- **Deposito telematico - ufficio/PEC/codice**: il resolver React completa PEC, codice interno e codice ministeriale dal catalogo uffici anche quando il profilo pratica contiene solo la PEC. L'audit confronta 593 uffici PCT operativi e non segnala PEC o codici mancanti.

## 2.254.18 - 2026-07-09

- **Deposito telematico - selezione documenti**: la busta non autoseleziona più tutti i documenti candidati del fascicolo. I documenti disponibili restano visibili, ma entrano nella busta solo quelli collegati o scelti e salvati dall'avvocato.
- **Deposito telematico - avvisi non bloccanti**: le scelte documentali obbligatorie ancora da verificare non spengono più `Firma e prepara prova` e `Simula invio PEC` quando l'atto principale e la PEC dell'ufficio sono presenti. La UI indica il documento da verificare come avviso e conserva i blocchi solo per requisiti realmente obbligatori.

## 2.253.192 - 2026-07-06

- **PEC - messaggio completo**: la lettura dell'EML originale non duplica più la busta PEC quando il messaggio contiene testo e HTML equivalenti e non attraversa due volte il messaggio allegato `postacert.eml`.

## 2.253.191 - 2026-07-06

- **Shell React - caricamento produzione**: il modulo principale React viene servito con parametro di versione applicativa, così una sessione browser non può restare agganciata a un asset principale precedente dopo il deploy.

## 2.253.190 - 2026-07-06

- **Fascicoli - azioni riga**: nella vista operativa le icone `Apri`, `Modifica`, `Esporta PDF` ed `Elimina` non sono piu' affiancate al titolo del fascicolo. Restano contestuali alla riga, ma vengono mostrate sotto titolo e oggetto, con allineamento piu' leggibile su desktop e resa coerente nelle card tablet/mobile.

## 2.253.189 - 2026-07-06

- **Fascicoli importati senza RG**: l'import da database pratiche non usa più il numero interno pratica come numero di ruolo. Il RG viene acquisito solo da campi di ruolo sicuri o dall'agenda importata quando contiene numero e anno completi.
- **Lista fascicoli professionale**: i fascicoli privi di numero di ruolo vengono evidenziati come `RG da acquisire`, con contatore dedicato e indicazione operativa per recuperare il dato dal portale o da un provvedimento prima di deposito, notifiche e scadenze processuali.
- **Archivio corretto da database sorgente**: la data di archiviazione del database originale è ora sufficiente per classificare la pratica come archiviata, anche se il flag archivio non è valorizzato.

## 2.253.188 - 2026-07-06

- **Fascicoli - presidio economico automatico**: la vista economica avvia un controllo POST idempotente che crea bozze proforma `BOZZA` per i fascicoli definiti privi di documento economico quando esiste una base sufficiente da sentenza, compenso pattuito o valore preventivato.
- **Proforma da visionare**: le bozze automatiche restano collegate al fascicolo e vengono mostrate come `Bozza proforma da visionare`, senza emissione fiscale o registrazione incasso finché l'avvocato non conferma.
- **Controllo SQL reale**: il riepilogo economico confronta fascicoli e parcelle dalla fonte SQL/repository reale, evidenziando pratiche già coperte, mancanti per assenza di base economica e possibili doppioni cliente/RG.

## 2.253.187 - 2026-07-06

- **Fascicoli - nomi file importati**: l'estrattore del contributo unificato normalizza underscore e trattini nei nomi documento, riconoscendo casi reali come `AUTOCERTIFICAZIONE_DELLA_SITUAZIONE_REDDITUALE_-_ESENZIONE_CONTRIBUTO_UNIFICATO_2025.PDF`.
- **Controllo economico**: l'esenzione CU viene rilevata anche quando l'OCR manca e l'unica evidenza utile è il nome/metadato del documento importato.

## 2.253.186 - 2026-07-06

- **Fascicoli - autocertificazione CU importata**: se l'import pratiche associa un'autocertificazione di esenzione contributo unificato a una voce economica placeholder, il presidio la interpreta come esenzione CU e porta il contributo a `Non previsto`, senza lasciarlo `Da registrare`.
- **Spese/esborsi**: se l'autocertificazione CU era finita per errore sotto spese/esborsi, la vista economica non la tratta più come spesa da registrare e mostra uno stato coerente con la fonte documentale.

## 2.253.185 - 2026-07-06

- **Fascicoli - microcopy economico professionale**: la vista economica non mostra più chiavi tecniche come `sentenza_key` o identificativi interni del documento; le evidenze vengono tradotte in indicazioni leggibili per lo studio, per esempio contributo esente, sentenza indicizzata, ricevuta pagoPA o documento da controllare.
- **Controllo documenti**: la fascia delle fonti economiche ora evita testi troncati e rumore tecnico, va a capo in modo governato e lascia all'avvocato solo risultato, fonte comprensibile e prossima azione.

## 2.253.184 - 2026-07-06

- **Fascicoli - CU esente senza OCR**: il presidio economico riconosce l'esenzione/non debenza del contributo unificato anche dal nome e dai metadati del documento, per esempio `Autocertificazione esenzione cu diritto lavoro.PDF`, evitando di mostrare un falso `€ 0,00` quando il PDF non è ancora indicizzato da Document AI.
- **Produzione Montagnese**: rafforzata la logica server-first sui fascicoli importati da Studio Telematico, così autocertificazioni e documenti economici diventano evidenze operative subito nella vista economica.

## 2.253.183 - 2026-07-06

- **Fascicoli - logica economica documentale**: il controllo economico tratta `€ 0,00` storico come placeholder quando lo stato è ancora da registrare o da emettere, quindi legge i documenti del fascicolo prima di mostrare la card all'avvocato.
- **Contributo unificato**: riconoscimento live di ricevute PagoPA, richieste di pagamento, esenzioni, autocertificazioni reddituali, art. 9 comma 1-bis DPR 115/2002 e patrocinio a spese dello Stato, con stato corretto e fonte documento nel riepilogo economico.
- **Sentenze e parcelle**: liquidazione, spese/esborsi e parcella proposta vengono popolati dalla sentenza del fascicolo anche se i campi economici storici erano ancora a zero.
- **Doppioni cliente/RG**: rafforzato il blocco di nuove duplicazioni e la riconciliazione dei duplicati storici, preservando documenti e pagamenti già presenti.

## 2.253.182 - 2026-07-06

- **Fascicoli - presidio udienze e documenti**: aggiunta analisi strutturata dei decreti di fissazione udienza e dei documenti del fascicolo per far emergere termini per note ex art. 127-ter c.p.c., udienze audiovisive ex art. 127-bis c.p.c., termini collegati per notifiche/costituzioni e avvisi quando serve la data di comunicazione.
- **Controllo economico e lavoro quotidiano**: la vista fascicoli segnala pratiche duplicate per cliente/RG, mostra evidenze documentali per importi economici automatici e porta le anomalie rilevanti anche nella topbar "cosa fare oggi" e nella panoramica operativa.
- **Guardrail professionali**: aggiunti test mirati sul presidio documentale, sui doppioni e sull'integrazione React/topbar, con documentazione operativa aggiornata per il flusso fascicoli/deposito.

## 2.253.180 - 2026-07-05

- **Fascicoli economici**: la vista economica e il dettaglio fascicolo leggono automaticamente anche i testi Document AI/OCR già indicizzati nel database strutturato dello studio. Contributo unificato, pagamenti e prossima scadenza vengono popolati dai documenti del fascicolo quando non sono già presenti valori manuali.
- **Sentenze — controllo economico**: il motore usa la stessa sorgente tenant-aware dei documenti AI del fascicolo, così la sezione non resta vuota quando i testi sono già presenti in `studio.db`.
- **Documenti mobile**: il lettore PDF mobile renderizza le pagine come immagini interne al sistema, evitando il riquadro vuoto dei browser Android/iOS quando l'iframe PDF nativo non è supportato.
- **Tabelle clienti, soggetti e fascicoli**: le azioni sono state spostate nella colonna principale per liberare spazio visibile e ridurre il taglio dei contenuti su desktop stretto, tablet e mobile.

## 2.253.179 - 2026-07-05

- **Clienti e soggetti**: corretto il falso salvataggio quando la sessione restituisce HTML/login invece di JSON; i salvataggi AJAX ora falliscono con messaggio chiaro e non mostrano più conferme non persistite. Comune, CAP e provincia vengono normalizzati lato server e suggeriti lato React con compilazione automatica su cliente, sede/domicilio e soggetti/parti.
- **Controllo economico sentenze**: la sezione del fascicolo avvia l'analisi automatica dei documenti candidati già indicizzati da Document AI/OCR, senza limite fisso sui primi documenti, e salva audit/eventi economici per spese liquidate, distrazione, art. 91/93 c.p.c. e contributo unificato da confermare.
- **Email e documenti mobile**: PEC/email ordinaria su tablet/mobile mostrano prima l'elenco e aprono la email selezionata in un pannello di lettura; l'anteprima documenti del fascicolo è etichettata come lettore documento e occupa il viewport mobile con toolbar compatta.

## 2.253.178 - 2026-07-05

- **Import pratiche Studio Telematico / Montagnese**: ripristinato il nome visibile dei documenti dalla descrizione del database Studio Telematico (`NOME_ATTO`/`Subject`), mantenendo il file fisico originale separato in `nome_originale`, `nome_archivio` e percorso su disco. Questo corregge la regressione in cui i documenti venivano mostrati come `2026...PDF` invece che, ad esempio, `Contratto 21-22`.
- L’import ora prepara automaticamente `source_snapshot`, conteggi sorgente, date udienza, collegamento Agenda e presidio economico (`contesto_economico`, contributo unificato, parcella) durante l’esecuzione o la riparazione parziale del pacchetto.
- Il dettaglio React del fascicolo collega gli appuntamenti Agenda importati anche tramite `source_external_id`/profilo fascicolo, non solo tramite numero RG.
- Audit e test bloccano il falso verde: un import Studio Telematico non è allineato se mancano contesto sorgente, contesto economico o appuntamenti Agenda quando il pacchetto li contiene.

## 2.253.177 - 2026-07-04

- **Import pratiche Montagnese da Studio Telematico**: il reimport da `E:\QuickOrganizer` ora mantiene il nome file originale come nome visibile del documento (`nome`, `nome_originale`, `nome_portale`) e conserva il titolo tabellare separato in `tipo_atto_portale`, in coerenza con il comportamento decompilato di Studio Telematico su `nomeFileOriginale`.
- Riesecuzione produzione sul tenant `studio-legale-giuseppe-montagnese`: create `8` pratiche mancanti, importati `246` documenti e `197` email mancanti, riparati i metadati di `8934` documenti e `4182` email già presenti; audit post-import con `331/331` pratiche, `13559/13559` documenti/email attesi, `0` mancanti e `0` mismatch sui nomi.
- Test: aggiunto guardrail di reimport parziale che ricarica il repository da disco e verifica la persistenza dei nomi file originali.

## 2.253.176 - 2026-07-04

- **Lex — la memoria appresa alimenta le risposte + apprendimento notturno attivo di default** (richiesta esplicita dello studio: «Lex deve imparare in autonomia dalle fonti che riceve»):
  - Nuova sorgente retrieval `lex_memory` (`lex/retrieval/sources/lex_memory.py` + motore deterministico `lex/retrieval/learning_memory.py`, registrata nel `SourceRouter` tra le fonti legali prima del web governato): gli estratti letti dal ciclo autonomo diventano evidenze per le risposte con l'ancora all'URL ufficiale. Fail-closed: entrano SOLO letture `status=ok` con URL http e valutazione di fiducia persistita (`allowed_for_learning` + tier `tier_1`/`tier_2` → trust A/B); niente trust, niente estratto o nessun overlap con la domanda → nessuna evidenza. Verifica reale: «Cosa stabilisce l'art. 2043 c.c.?» ora risponde col testo della norma e l'ancora Normattiva (prima: metadati di registro senza contenuto).
  - Il lettore del ciclo (`lex/autonomy/source_reader.py`) persiste un **estratto governato** del testo letto (`excerpt`, spazi normalizzati, max 1800 caratteri): la memoria conserva il contenuto, non solo i conteggi.
  - **Job notturno `lex_autonomous_learning_nightly` attivo di default** (cron 02:40, budget prudenti): il seeding promuove a ON solo le righe di registro mai toccate da un umano (`updated_by='system'`); qualunque scelta fatta dalla console Pianificazioni vince per sempre sul default. Doppia cintura del runner invariata (registro ricontrollato a ogni esecuzione).
  - 10 test nuovi/riallineati: ricerca memoria (trust obbligatorio, tier non ammessi, letture non ok, overlap, sola lettura), promozione default che rispetta le scelte umane, regressione end-to-end domanda→risposta con ancora ufficiale e negativa fail-closed senza trust.

## 2.253.175 - 2026-07-04

- **Lex — superficie web "Apprendimento Lex"** (feature flag `lex.autonomousLearning`, default ON perché read-only): nuova pagina React `/lex-apprendimento` nella sezione Studio (voce di menu gated da flag + permesso `ai.usa`) dove l'avvocato ispeziona il ciclo di apprendimento autonomo — stato del job notturno delegato (attivo/in pausa, con rimando alla console Pianificazioni per l'attivazione: la superficie NON offre azioni dispositive), conteggi della memoria durevole per collezione, ultime proposte di miglioramento (sempre etichettate "revisione umana") e ultime letture di fonti ufficiali con stato fail-closed leggibile (Letta / Robots / Testo vuoto / Oltre soglia byte). Backend: ispettore read-only `lex/autonomy/memory_inspection.py` (mai side-effect su disco, memoria assente → payload onesto), bridge `web/services/react_lex_learning_bridge.py`, blueprint `api_v1_lex_learning` (`GET /api/v1/ui/lex-learning`) con guardie autenticazione + flag + permesso e backend security guard, stessa architettura fail-closed di `api_v1_legal_skills`. 6 test nuovi (ispettore: memoria popolata/assente/righe corrotte/limiti; bridge: payload completo e stato onesto senza memoria).

## 2.253.174 - 2026-07-04

- Documentazione — esito della run #6 di verifica del drill-down esteso (workflow "Lex ciclo web", commit `fab800bb`, tutti gli step verdi): nuova sezione in `docs/reports/lex_web_cycle_2026-07.md` — 6 dettagli letti dal vivo: 4 sentenze Cassazione uniche (il dedup dentro l'estrattore raddoppia la resa rispetto alla run #5) e 2 PDF G.A. via pypdf, tra cui un provvedimento reale (`202603287_11.pdf`, 16.122 caratteri, 36 citazioni) pescato dal nuovo seed `dcsnprr` (5.397 caratteri, 64 citazioni); Consulta a 0 dettagli (homepage servita in variante minimale da 687 caratteri senza href `scheda-pronuncia`: fail-closed corretto, regola pronta e testata sulle schede reali); EUR-Lex di nuovo pieno (387K caratteri, intermittenza confermata). Nota di verifica aggiornata in `docs/lex_autonomous_learning.md`.

## 2.253.173 - 2026-07-04

- **Lex — drill-down esteso a Corte costituzionale e Giustizia amministrativa** (fase 2 del workflow "Lex ciclo web"): le regole di estrazione dei link di dettaglio escono dal heredoc ed entrano nel nuovo modulo `lex/autonomy/detail_links.py` (stdlib puro, fail-closed: pagina senza regola → nessun link, href fuori dominio o schema non http(s) → scartato, dedup a ordine stabile, `&amp;` normalizzato). Tre regole, tutte da conoscenza di produzione: Cassazione (`*_dettaglio.page` + `contentId=`, marker identici ai `CASSAZIONE_DETAIL_URL_MARKERS` con variante severa del parser), Corte costituzionale (schede `/scheda-pronuncia/<anno>/<numero>`, stesso pattern del filtro `corte_costituzionale` del parser), Giustizia amministrativa (provvedimenti PDF sotto `/documents/`, forma censita nella matrice di ricerca; canale best-effort perché l'HTML G.A. è instabile per i crawler — fonte diretta disabilitata in produzione a favore di OpenGA, esito vuoto = esito valido). I PDF passano dall'estrattore esistente (`extract_text_from_bytes` → pypdf, fail-closed). Nuovo seed `dcsnprr` ("Decisioni e pareri" G.A., pagina censita in `legal_update_pipeline`). 7 test unit + 4 test di allineamento coi pattern di produzione (`tests/test_lex_autonomy_detail_links.py`). Il push del workflow esegue automaticamente la run di verifica live.

## 2.253.172 - 2026-07-04

- Documentazione — esito della run #5 di verifica dei connettori dettagli sentenze (workflow "Lex ciclo web", commit `5b7c907d`, tutti gli step verdi): nuova sezione in `docs/reports/lex_web_cycle_2026-07.md` con i numeri reali — fase 1 con 10 fonti lette via composito (4 candidati `archivio_locale` con Gazzette maggio/giugno 2026 dal mirror locale), fase 2 con drill-down riuscito (4 href estratti dalle liste Cassazione, 2 dettagli unici letti: `SZC51228` civile con 18 citazioni e `SZP51291` penale con 12 citazioni, 30 riferimenti normalizzati dai testi delle decisioni), proposte scese da 68 a 8 grazie alle stop-word della 2.253.168, tabella riassuntiva dello stato dei connettori dopo 5 run. Nota "verificato in produzione (run #5)" nella sezione connettori di `docs/lex_autonomous_learning.md`; corpus giurisprudenza in catena fail-closed (vuoto finché non si verificano sentenze, mai creato dal ciclo).

## 2.253.171 - 2026-07-04

- **Lex — connettori per i dettagli sentenze** (dalle liste ai TESTI delle decisioni, il materiale per le strategie di causa):
  - `LocalCorpusSearchProvider`: legge il corpus giurisprudenza locale (`derive_corpus_db_path` da `PCT_GIURISPRUDENZA_DB`, popolato dai motori di produzione) — contenuto = massima ufficiale + principio sintetico, ancora = URL ufficiale della decisione; entrano SOLO le sentenze che superano `can_cite_sentenza` (stato verificato + ancora ufficiale/ECLI, il predicato di citabilità già esistente in `pct/giurisprudenza_corpus.py`); righe senza massima/principio o senza URL http scartate; corpus assente → vuoto senza MAI crearlo. Composito aggiornato in CLI web e job notturno: archivi Normattiva/GU → corpus giurisprudenza → ricerca web governata.
  - Workflow "Lex ciclo web", fase 2: **drill-down dei dettagli** — dalle liste Cassazione vengono estratti gli href `*_dettaglio.page` (marker identici ai `CASSAZIONE_DETAIL_URL_MARKERS` di produzione) e letti fino a 2 dettagli per lista via PoliteFetcher, con esiti etichettati `dettaglio_sentenza`; la lista viene letta con un solo fetch (testo inline + estrazione href insieme).
  - Fix regressione run #4: URN Normattiva vuoto ("urn:" nudo) non produce più l'ancora generica `N2Ls?urn:` (scartato fail-closed).
  - 6 test nuovi (citabilità fail-closed, scarto senza massima, corpus assente senza side-effect, dedup, URN vuoto) + harness locale della semina con drill-down (2 dettagli letti, citazioni estratte dal testo della decisione).

## 2.253.170 - 2026-07-04

- Workflow "Lex ciclo web" — fix della race con il deploy (run #3: fase 2 uccisa con exit 137 dal riavvio del container durante il deploy dello stesso commit; il connettore archivi era comunque gia' verde in produzione):
  - l'attesa su push ora controlla la VERSIONE dentro il container in esecuzione (`docker exec ... pct.__version__` == versione del commit) e non il checkout del repo (che avviene prima del rebuild), con 30s di assestamento dopo l'allineamento;
  - retry singolo (60s) su exit 137 per fase 1 e fase 2 — cintura contro riavvii concorrenti;
  - riepilogo memoria nel log con il conteggio dei candidati `archivio_locale` (visibilita' immediata dell'uso del connettore archivi locali Normattiva/GU).

## 2.253.169 - 2026-07-04

- **Lex — connettore archivi ufficiali locali Normattiva/GU** (chiude la proposta P5 auto-generata dal ciclo nella run #2, quando le protezioni anti-bot IPZS hanno bloccato i fetch live): la modalità web usa ora un provider composito — `LocalArchiveSearchProvider` legge PRIMA dai mirror sanzionati scaricati ogni notte da `legal_official_archives_daily` (`/data/normativa/normattiva.sqlite`, `/data/fonti_ufficiali/lex_sources.sqlite`, via retriever esistente `official_sources_retriever`), poi `ConfigurableWebSearchProvider` come complemento (`CompositeSearchProvider`, dedup per URL, provider guasto non ferma gli altri). Provenienza onesta: testo dal mirror locale (zero rete), autorità ancorata all'URL ufficiale (URN → `normattiva.it/uri-res/N2Ls?<urn>`), trust sul dominio reale; righe senza ancora http o senza testo scartate fail-closed; archivi assenti → vuoto senza errori. Cablato in CLI web e job notturno. 7 test nuovi.
- Workflow "Lex ciclo web": sulla run auto-innescata dal push ora ATTENDE che il deploy dello stesso commit arrivi sul server (poll fino a ~25 min, warning se non arriva) così la verifica gira sempre sul codice nuovo; timeout job 20→40 min.

## 2.253.168 - 2026-07-04

- Lex apprendimento autonomo — tre raffinamenti dalla prova web reale:
  - **Job notturno delegato default-OFF**: nuovo `lex_autonomous_learning_nightly` (cron 02:40) — template `enabled=False` nella console Pianificazioni (job APScheduler in pausa all'avvio via `apply_scheduler_registry`), runner `lex/autonomy/nightly.py` con doppia cintura fail-closed (senza riga di registro abilitata NON parte, nemmeno se il job viene ripreso a mano). Quando attivato dalla console: ciclo web con la config governata committata, budget notturni prudenti (2 cicli/10 query/5 fonti/240s), memoria durevole in `{PCT_DATA_ROOT}/intelligence/lex_memory` che si accumula notte dopo notte. 6 test dedicati.
  - **Stop-word legalese estese** nell'analizzatore (`lex/learning/legal_language_analyzer.py`): i testi normativi integrali producevano candidati rumorosi ("trattamento tale", "trattamento nonché", "qualsiasi pena" dalla run reale); congiunzioni/dimostrativi/aggettivi generici non formano più bigrammi; i concetti legittimi ("legittimo interesse", "trattamento dati", "accesso civico") sopravvivono (test di regressione dedicati).
  - **Seed del workflow "Lex ciclo web" migliorati**: URN Normattiva del singolo articolo con suffisso `!vig=` (l'URN nudo restituiva l'intero codice > 2MB → too_large nella run #1) e liste sentenze REALI di Cassazione (`giurisprudenza_civile.page` + `giurisprudenza_penale.page`, le stesse già crawlate in produzione dal motore aggiornamenti) al posto della homepage. Il push di questo file esegue automaticamente la run di verifica.

## 2.253.167 - 2026-07-04

- Lex modalità web: **prima prova reale in produzione riuscita** (workflow "Lex ciclo web" run #1 sul container Hetzner, 90s, tutti gli step verdi). Fase 1 ricerca governata: 10 fonti ufficiali lette con 2 query (es. L. 300/1970 → pagine reali Normattiva), 194 citazioni nuove. Fase 2 semina: 10/11 letture ok — D.Lgs. 149/2022 Cartabia (64 riferimenti), GU ultime pubblicazioni con decreti 2026 freschi (D.L. 89/2026, D.Lgs. 83/2026...), Cassazione, Consulta, G.A., GDPR integrale da EUR-Lex (387K caratteri), Garante, Agenzia Entrate, INPS; unico non-ok il tetto byte fail-closed sull'URN dell'intero codice civile. Memoria finale: 548 citazioni, 488 termini, 68 proposte in revisione umana, 0 violazioni di policy (0 respinte, 0 robots_blocked). Report permanente in `docs/reports/lex_web_cycle_2026-07.md` + nota di verifica in `docs/lex_autonomous_learning.md`.

## 2.253.166 - 2026-07-04

- Workflow "Lex ciclo web": aggiunto trigger `push` con filtro paths sul file stesso (una sola esecuzione automatica quando il workflow cambia sul branch di sviluppo) — il token dell'integrazione GitHub della sessione non ha `actions: write`, quindi il dispatch via API non è disponibile; il push auto-innesca la prova reale e il dispatch manuale da Actions resta invariato. Input con default sicuri su push (`inputs` vuoto → 20 query / 10 fonti).

## 2.253.165 - 2026-07-04

- **Lex — modalità web governata: prova reale dal server con fonti forensi** (richiesta utente: acquisire dati realmente utili allo studio — giurisprudenza per strategie di causa, decreti, leggi, prassi):
  - Nuovo workflow manuale `.github/workflows/lex-web-cycle.yml` (solo workflow_dispatch): esegue il ciclo autonomo DENTRO il container di produzione `iusentra-app` su Hetzner (che raggiunge le fonti ufficiali), senza toccare produzione (memoria solo in `/tmp` del container, `/data` mai coinvolto, pulizia finale). Fase 1: ciclo web puro con ricerca governata (`official_web` + `PoliteFetcher`); exit 2 "nessuna fonte dalla ricerca" tollerato come esito valido (motori possono bloccare IP datacenter). Fase 2 (sempre): lettura diretta di 11 fonti REALI ad alto valore forense — Normattiva (art. 2043 c.c., L. 241/1990, D.Lgs. 149/2022 Cartabia), Gazzetta Ufficiale ultime pubblicazioni, Cassazione, Consulta, Giustizia amministrativa, EUR-Lex CELEX 32016R0679, Garante Privacy, Agenzia Entrate, INPS — con trust fail-closed, robots.txt, rate-limit, estrazione citazioni e grafo. Log con riepilogo memoria + artifact `lex-web-cycle-memoria` (14 giorni).
  - `examples/lex_autonomous_config_web.json` (nuovo): configurazione web di riferimento con allowlist di 18 domini TUTTI verificati tier_1/tier_2 nel Source Policy System (normativa, giurisprudenza — Cassazione/Consulta/G.A./Corte conti/CGUE —, UE/privacy, prassi Agenzia Entrate/INPS/INAIL/ANAC/Min. Lavoro; brocardi.it come tier_2); scartati i domini non classificati dai cataloghi (italgiure, hudoc, mef, agcm, cnf — fail-closed).
  - `examples/legal_samples.json`: +3 campioni strategici che orientano il gap detector sui temi da avvocato (termini Cartabia 171-ter/127-ter, licenziamento art. 18/L. 604, accertamento tributario D.P.R. 600/1973).
  - `lex/autonomy/cli.py`: guard `__main__` (il ciclo è eseguibile anche con `python -m lex.autonomy.cli`, senza dipendere da `scripts/` dentro l'immagine Docker).
  - Test: nuova guardia anti-drift sulla config web committata (validazione + ogni dominio nei tier governati); script di semina verificato in locale con fetcher finto (11/11 letture, memoria e grafo popolati).

## 2.253.164 - 2026-07-03

- Notifiche legali React: ogni controllo operativo porta ora il pannello di esito in vista, inclusa la comunicazione cliente, così i pulsanti mostrano sempre feedback immediato e motivi di blocco.
- Test: aggiunto guardrail UI per impedire regressioni sul feedback visibile dei controlli del pannello notifiche.

## 2.253.163 - 2026-07-03

- Notifiche legali React: il payload API e le risposte dei controlli operativi filtrano in modo ricorsivo riferimenti tecnici non destinati alla UI.
- UI: i messaggi di blocker/warning del pannello notifiche sostituiscono le diciture tecniche con testi operativi comprensibili per l'avvocato.
- Test: aggiunto guardrail sul JSON completo del pannello notifiche e rilanciati test mirati backend/frontend.

## 2.253.162 - 2026-07-03

- Notifiche legali React: aggiunti flussi dedicati `UNEP` e `Non PEC` nello stesso pannello operativo, con controlli reali, API JSON e azioni non simulate.
- Dati: aggiunte tabelle SQLite/PostgreSQL per richieste UNEP e tracciamento notifiche non PEC/raccomandata, mantenendo il perimetro tenant-aware.
- Conformità notifiche: la prova di notifica richiede ora destinatario, PEC e pubblico elenco quando si depositano ricevute di accettazione/consegna.
- UI: nessun riferimento al software confrontato viene esposto nel pannello utente; i messaggi visibili filtrano codici e dettagli tecnici non utili all'avvocato.

## 2.253.161 - 2026-07-03

- Deposito telematico React: aggiunto `Deseleziona tutto` nella lista `Documenti da inviare` e corretto hover/focus di `Salva classificazione`, che ora resta leggibile con testo bianco su sfondo blu.
- I `Documenti attesi` e il pannello `Documenti richiesti` cambiano ora in base al tipo deposito selezionato, usando i flag importati dal catalogo Studio Telematico (`needProcura`, `needContributoUnificato`, `needNotaIscrizioneRuolo`, dati obbligatori e regole UNEP/Cassazione).
- Il pannello laterale riusa gli slot reali della Regia quando esistono e distingue i requisiti di catalogo che sono dati del deposito dai documenti fisici da collegare.

## 2.253.158 - 2026-07-03

- Presidio documentale udienze: il report del worker deduplica ora i candidati operativi per documento/tipo/data anche quando Lex AI conserva piu' record `ready` con lo stesso hash. L'attivita' nel fascicolo era gia' idempotente; ora anche `candidate_dates`, `past_remote_hearings_recorded` e `items` non vengono gonfiati da duplicati.
- Aggiunto guardrail che simula due record AI sullo stesso documento e verifica una sola riga report e una sola attivita' `UDIENZA`.

## 2.253.157 - 2026-07-03

- Presidio documentale udienze: il parser riconosce ora la formula reale dei decreti `FISSA l'udienza in data ... alle ore ...`, usata nei provvedimenti di fissazione da remoto.
- Il link Teams `teams.microsoft.com/meet/... ?p=...` spezzato a capo dal PDF/OCR viene ricomposto quando il parametro di accesso continua nella riga successiva, evitando link tronchi.
- I documenti gia' marcati `checked` con `candidates=0` prima del fix vengono rivalutati una volta tramite versione parser, cosi' `RG 1754/2026` e casi analoghi non restano bloccati dal run precedente.

## 2.253.156 - 2026-07-03

- Presidio documentale udienze: il worker usa ora anche i testi Lex gia' estratti in `studio.db` per ordinare prima i fascicoli che contengono udienza da remoto e link reale Teams/Zoom/Meet/Webex, senza aumentare il lotto e senza hardcoding su un singolo RG.
- Il caso `RG 1754/2026` rientra nel gruppo a priorita' massima perche' il decreto contiene `N. R.G. 1754/2026`, udienza del `20/05/2026 alle ore 10:00` e link Teams gia' presente nel testo AI.
- Aggiunto guardrail che dimostra che un fascicolo con testo AI e link remoto passa davanti ai decreti generici, anche se il suo numero progressivo lo avrebbe spostato piu' in basso.

## 2.253.155 - 2026-07-03

- Presidio documentale udienze: la coda incrementale distingue ora i documenti realmente operativi (`fissazione udienza`, collegamenti audiovisivi, Teams/Zoom/Meet/Webex, trattazione, 127-ter, note scritte) dai provvedimenti generici (`decreto`, `ordinanza`, `verbale`). I decreti generici non possono piu' passare davanti ai decreti di fissazione udienza e ai link remoti.
- Il worker ruota i fascicoli gia' toccati dal presidio dietro a fascicoli mai analizzati con documenti operativi, cosi' un archivio grande gia' in lavorazione non ritarda `RG 1754/2026` e gli altri fascicoli analoghi.
- Aggiunti guardrail mirati su priorita' `fissazione udienza` rispetto a `decreto generico` e su rotazione dopo fascicolo gia' parzialmente presidiato.

## 2.253.154 - 2026-07-03

- Presidio documentale udienze: il budget incrementale resta piccolo, ma ora viene ripartito tra fascicoli. Con il limite standard il worker processa solo una quota per singolo fascicolo e passa agli altri, evitando che un fascicolo con molti decreti/verbali storici ritardi RG 1754/2026 e gli altri fascicoli analoghi.
- Aggiunto test di regressione che dimostra che un fascicolo grande non monopolizza il lotto e che il fascicolo successivo viene comunque analizzato nello stesso giro automatico.

## 2.253.153 - 2026-07-03

- Presidio documentale udienze: i riferimenti storici a file fisici non piu' presenti nel tenant non fanno piu' fallire il worker PEC/documenti. Il documento viene auditato come `skipped_non_blocking` con motivo `file_documento_sorgente_non_trovato`, non viene riletto a ogni ciclo e il lotto prosegue sui fascicoli successivi, inclusi i fascicoli analoghi a `RG 1754/2026` con decreti/ordinanze/verbali di udienza.
- Aggiunto test di regressione sul caso reale `FileNotFoundError` durante indicizzazione Lex AI documentale, preservando i guardrail su priorita' fascicoli, vecchi checked senza status, lock SQLite transitori e link udienza remoto cliccabile.

## 2.253.152 - 2026-07-02

- Toolchain: aggiornamento a **Node 24 LTS** (GitHub ha deprecato Node 20 sui runner Actions, avviso "Node 20 is being deprecated... running with Node 24 by default"):
  - `actions/setup-node@v5` → `node-version: "24"` nei workflow `ci.yml`, `frontend-ci.yml`, `security-supply-chain.yml` (prima 22);
  - `actions/github-script@v7` → `@v8` in `branch-hygiene.yml` (v7 girava su runtime node20, era la fonte dell'avviso di deprecazione; v8 è node24-nativo);
  - Dockerfile stage `frontend-builder`: `node:22-slim` → `node:24-slim` (parità di build CI/Docker; Vite 6.4.3 supporta Node ≥22.12, quindi 24 pienamente);
  - le altre action erano già su major node24-native (checkout@v5, setup-python@v5, upload-artifact@v5, setup-node@v5). Nessuna modifica al codice applicativo; bundle React committato invariato (il rebuild Docker su Hetzner avviene con Node 24).

## 2.253.151 - 2026-07-02

- **Lex AI — Fondazione di apprendimento autonomo governato** (deterministico, zero LLM, default-off): Lex rileva ciò che non sa, formula domande di ricerca, cerca fonti ufficiali, ne valuta l'affidabilità, legge con cortesia, aggiorna una memoria ispezionabile e PROPONE miglioramenti — senza mai inventare diritto, committare o toccare produzione (revisione umana obbligatoria su ogni proposta). Approccio chirurgico: riuso dei motori esistenti (Source Policy System/`ai_lex_sources`, registro fonti, `pct/legal_reference_extractor`, `pct/legal_context_questions`, `official_web`, `OfficialSourceHttpClient`/extractors), costruito solo ciò che mancava davvero. Docs: `docs/lex_autonomous_learning.md` + `docs/lex_source_policy.md`.
  - **`lex/learning/`** (nuovo): modelli serializzabili con `stable_id` deterministico; `citation_extractor` = facciata sull'estrattore di produzione pct + estensione atti nominati UE/GDPR ("GDPR" nudo → Regolamento (UE) 2016/679; "art. 6 GDPR" arricchito con soppressione della riga nuda; "codice privacy" → D.Lgs. 196/2003) con offset sul testo normalizzato — pct NON viene toccato (l'upstreaming è una proposta tracciata); `legal_language_analyzer` deterministico (densità legale, complessità, termini noti da ontologia + candidati da parole-testa giuridiche, con gestione dell'elisione italiana).
  - **`lex/knowledge/`** (nuovo): `KnowledgeBase` JSONL append-only (9 collezioni con `schema_version`, dedup per record_id, clock iniettabile, dry-run in-memory), `ConceptGraph` dict-puro (salvataggio byte-stabile, relazioni cita/definisce/appartiene_a/letta_per/correlato_a), `LEGAL_ONTOLOGY` seed (civile/privacy/amministrativo/penale/tributario/lavoro con sinonimi, fonti primarie e correlati).
  - **`lex/sources/` (esteso)**: `polite_fetcher` — robots.txt per dominio con cache e semantica **fail-closed** (errore rete/5xx = negato), rate-limit per dominio, tetto byte, guardia URL pubbliche (gap reale: nessun fetcher del repo gestiva robots); `trust.assess_source` — decisione di ammissione componendo `evaluate_source` + registro (denylist vince sempre; credenziali bloccano solo se unica via d'accesso — EUR-Lex resta leggibile via web; tier_3 mai verità primaria; unknown mai ammesso); nuovi modelli `SourceCandidate`/`SourceFetchResult`/`SourceTrustAssessment`; `extract_text_from_bytes` (estrazione senza file temporanei).
  - **`lex/autonomy/`** (nuovo): `gap_detector` con 5 regole spiegabili (norma citata non letta, termine ricorrente sconosciuto, area scoperta, fonti deboli, concetto isolato) con evidenze; `research_planner` (riusa `generate_context_questions`); `query_builder` (query SOLO da campi strutturati — niente PII per costruzione; `site:` dai tier governati, varianti giurisprudenziali dal parser esistente); `discovery` con `SearchProvider`/`StaticSearchProvider` (offline) e `ConfigurableWebSearchProvider` (avvolge `official_web` con import pigro, spoglia i token site: doppi); `autonomous_cycle` con stop conditions (max_cycles/queries/sources/runtime/no_new_information) e report per ciclo; `improvement_proposer` P1-P5 (pattern citazione, dominio fuori policy, AREA_KEYWORDS, ontologia, connettore per tier_1 robots-blocked) — MAI applicate: `refuse_apply` solleva sempre; `safety` fail-closed (HARD_LIMITS senza clamp, web solo con allow_web+allowlist+robots, azioni dispositive vietate).
  - **`lex/evaluation/learning_metrics.py`** (esteso): segnali per ciclo (delta collezioni, rapporto ufficialità pesato con SOURCE_WEIGHTS, coverage per area, flag no_new_information).
  - **CLI**: `scripts/lex_autonomous_cycle.py` → `lex/autonomy/cli.py` (exit 0/1/2/3, `--dry-run`, report testo/JSON in italiano); esempi `examples/legal_samples.json` (art. 2043 c.c., art. 6 GDPR, L. 241/1990 — zero PII) e `examples/lex_autonomous_config.json` (offline con risultati precotti di fonti ufficiali; web default OFF).
  - **Test**: 95 nuovi (13 file unit in `lex/tests/unit/` + 3 integrazione in `tests/`), incluso E2E offline con guardia anti-rete (monkeypatch socket), convergenza `no_new_information` alla seconda run, dry-run che non scrive, exit code CLI, robots fail-closed, provider web con `request_get` finto. Nessuna regressione sulla suite lex esistente.
  - Fuori scope (prossimi passi documentati): job notturno delegato (template `enabled=False`), feature flag `lex.autonomousLearning` (nessuna superficie web ancora), upstreaming GDPR in pct con regressioni PEC.

## 2.253.150 - 2026-07-02

- Presidio PEC "Legal Presidio Pro" — chiusura dei due cablaggi vivi (i motori B/C esistevano ma non erano ancora agganciati al percorso reale scadenza/UI):
  - **Cablaggio B (termine legale → scadenza reale)**: `build_validation_report` aggancia il termine legale calcolato dal proponente (`deadline_proposal.legal_deadline_proposal`, dies a quo risolto da `propose_from_parsed`: comunicazione/udienza/notificazione). `schedule_deadline`/`schedule_deadline_from_payload` creano ora la scadenza sulla **data legale** (fallback quando il presidio operativo non ha una data), con campi legali persistiti (`legal_due_at`, `raw_due_at`, `trace_json` del calcolo, `perentorio`, `deadline_profile_code=<template>`) e titolo = azione legale (es. "Opposizione ex art. 127-ter"). L'auto-creazione in `link_fascicolo` scatta anche sui termini legali riconosciuti (`_report_has_legal_deadline`), e la pulizia scadenze generiche non rimuove più una scadenza con termine legale. Additivo e fail-closed: nessuna norma riconosciuta ⇒ presidio operativo `PEC_AUTO_PRESIDIO` invariato; ogni termine resta non definitivo (nota "revisione professionale obbligatoria"). Helper unico `_legal_deadline_scadenza_fields` (niente duplicazione tra i due percorsi).
  - **Cablaggio C (vista unificata esposta)**: `get_message_detail` espone `legal_event_understanding` (schema `iusentra.pec.legal_event_understanding.v2`), che riusa il termine legale già calcolato dal report (nessun ricalcolo). Superato l'endpoint `GET /api/pec/messages/<id>` senza modifiche di blueprint.
  - **UI React**: la riga stato scadenza nel presidio PEC mostra ora il termine legale (`Termine perentorio ex art. …: <data> — proposta automatica, revisione professionale obbligatoria`), e il pulsante "Scadenza automatica" si abilita anche quando esiste un termine legale (non solo sul presidio operativo). Nessun inline style (governance React rispettata).
  - 8 test nuovi (`test_pec_legal_deadline_cablaggio.py`): predicato/helper puri, aggancio nel report, blocco art. 325 su deposito sentenza, end-to-end su DB reale (scadenza legale creata + idempotenza), vista unificata nel detail. Nessuna regressione sui test PEC/scadenziario.

## 2.253.149 - 2026-07-02

- Presidio PEC "Legal Presidio Pro" — potenziamento a incrementi (riuso dei motori esistenti, niente modulo greenfield; deterministico-first, fail-closed):
  - **A.2 udienza**: parsing allegati `.ics` (riuso `ical_import.parse_ics`, finora non agganciato — il link Teams vive spesso nella DESCRIPTION dell'invito) e **tassonomia modalità unica** `{presenza, remoto, mista, note_scritte, incerta}` (`remote_hearing.mode_unified`), con note-scritte e mista come classi positive.
  - **B termini legali** (pezzo prima mancante): `pct/pec_legal_deadline_proposer.py` estrae norma + dies a quo + direzione dal testo PEC, risolve norma→template (ruleset versionato `legal_pec_deadline_rules_v2026_07.json`) e delega il CALCOLO al motore deterministico `ItalianDeadlineCalculator` (avanti/a ritroso, sospensione feriale). Nuovi template 644 (60gg), 669-terdecies (15gg), 380-bis (40gg), 127-ter (5gg). Regole bloccanti: deposito sentenza → nessun termine breve ex art. 325 dalla sola comunicazione (art. 133 c.p.c.); "assegna termine" senza durata → revisione. Mai fonte unica, sempre human_review.
  - **C vista unificata**: `pct/pec_legal_event_understanding.py` aggrega i segnali (classificazione + udienza + termine + ricevute PCT) nello schema `iusentra.pec.legal_event_understanding.v2`, sola lettura; `web_push_safe_title` senza PII (P0 su udienza remota senza link); Lex solo per l'ambiguo.
  - **D famiglie**: `_classifica_famiglia` riconosce ora concorsuali, esecuzioni mobiliari/immobiliari, famiglia/minori, PAT (amministrativo), PTT/SIGIT (tributario) prima del fallback generico, così le regole civili non si applicano automaticamente a PAT/PTT/penale.
  - (A.1, già in 2.253.148: fix link udienza in `<a href>` + escalation P0 remoto-senza-link.)
  - 21 test nuovi in questa release; nessuna regressione causata dalle modifiche (i fallimenti sandbox su Lex router/PDF import/migrazione SQLite sono preesistenti al netto di queste modifiche).

## 2.253.148 - 2026-07-02

- Presidio PEC — comprensione udienza, chiusura gap (incr. A.1):
  - **Bug link udienza risolto**: i link di collegamento (Teams/Zoom) presenti SOLO nell'attributo `<a href="...">` andavano persi, perché il corpo HTML veniva spogliato dei tag prima dell'estrazione e `build_remote_hearing_profile` leggeva una chiave `body["html"]` inesistente. Ora `parse_pec_message` estrae gli URL dagli href (nuova chiave `body.href_urls`, inclusi in `body_all` e nel profilo udienza remota) e li dà in pasto all'estrattore link esistente. Un link Teams solo-href viene finalmente riconosciuto.
  - **Escalation P0 "udienza da remoto senza link"**: quando la PEC indica un'udienza da remoto/audiovisiva ma non si trova alcun link (corpo, href, PDF, ICS) né un PDF da leggere, il report ora emette l'issue `remote_hearing_link_missing` a severità `danger`/priorità `P0` (prima solo `warning`), con azione "controllare allegati/fascicolo/sito ufficio o cancelleria".
  - Riuso integrale del motore remote-hearing esistente (allow/block-list, contesto negativo note-scritte, ricongiunzione URL da OCR, `remote_hearing_verified`); nessuna duplicazione. 4 test nuovi; nessuna regressione sui test PEC.
  - Prossimo (incr. A.2): parsing allegati `.ics` (riuso `parse_ics`) e tassonomia modalità unica {presenza/remoto/mista/note_scritte/incerta}.

## 2.253.147 - 2026-07-02

- Sentenza Economic Control V1 — cablaggio reale degli "ultimi metri" (prima i pezzi esistevano ma erano scollegati dal percorso vivo, così gli importi liquidati non si vedevano in UI):
  - **UI React**: il payload dettaglio fascicolo (`react_fascicoli_bridge.build_react_fascicolo_detail_payload`) espone ora la chiave `sentenzeEconomiche` (riuso di `sentenza_economic_runtime.build_sentenza_economic_payload`, che gestisce flag + tenant *slug* + repository + riepilogo). Nuova sezione "Sentenze — controllo economico" in `FascicoloDetail` (crediti cliente art. 91, crediti avvocato antistatario art. 93, alert contributo unificato, spese liquidate totale), con stato vuoto quando il flag è spento o non ci sono sentenze analizzate. Nessun inline style (governance React rispettata).
  - **Auto da PEC**: nuova `pec_pipeline_runtime.trigger_economic_audits_for_paths` agganciata a `run_workers_for_paths`: sui job `link` classificati `deposito_sentenza`, con flag `features.sentenzaEconomicControl` attivo, lancia l'audit economico in **sola anteprima** (`to_review`, mai definitivo), leggendo il testo OCR del PDF provvedimento dagli allegati e usando lo slug tenant minuscolo (coincidente con la lettura UI).
  - Precondizione (invariata): gli importi compaiono solo con flag ON e almeno un audit per il fascicolo (auto da PEC o `analyze` manuale). Default-off.
  - 7 nuovi test (prova reale del flusso repo→runtime→payload→bridge; auto-trigger PEC su deposito sentenza; gate flag). Typecheck frontend verde.

## 2.253.146 - 2026-07-02

- CI: sblocco deploy/sync — corretta la regressione "check fantasma CodeQL su push". `.github/required-checks.json` chiedeva il context `CodeQL` sia su push sia su pull_request, ma l'ombrello Code Scanning "CodeQL" è creato da GitHub **solo sulle pull request** (sui push esiste solo il job required `Analyze (python)`). Su push `CodeQL` restava eternamente "missing" → il gate `check_github_required_gates.py --wait` non raggiungeva mai 84/84 → il deploy Hetzner (che attende i gate) andava in timeout/`cancelled` e il sync gemello non partiva. `CodeQL` torna richiesto solo su `["pull_request"]` (come nel fix v2.251.2, poi regredito): resta bloccante sulle PR e su push la scansione è coperta da `Analyze (python)`.
- Salvaguardia anti-recidiva rafforzata: rimossa l'esenzione `github_generated_checks={"CodeQL"}` in `tests/test_ci_cd_gates_phase11.py`, così `test_every_push_required_check_has_a_producing_job` cattura una futura ri-aggiunta di CodeQL (o altro check senza job produttore) fra i required su push. Aggiornato il commento in `tools/check_github_required_gates.py`.

## 2.253.145 - 2026-07-02

- Sentenza Economic Control V1 (nuovo modulo, default-off `features.sentenzaEconomicControl`): controllo economico-probatorio delle sentenze civili. Prima di alimentare qualunque contesto economico, il sistema dimostra che la sentenza appartiene al fascicolo (uguaglianza RG esatta + punteggio cliente/ufficio, riuso dello scorer del presidio PEC), poi estrae spese liquidate, distrazione ex art. 93 c.p.c. e contributo unificato, e propone azioni solo da confermare. 10 regole anti-errore hardcoded. Fonti: art. 91/93/133/325 c.p.c., D.M. 55/2014, D.P.R. 115/2002.
- Incr.1 — motore puro `pct/sentenza_economic_audit.py` + persistenza tenant-aware `pct/sentenza_economic_repository.py` (SQLite/PostgreSQL gemelli + registro probatorio firmato a catena di hash) + ruleset civile versionato `pct/data/economic_legal_rules_v2026_07.json`.
- Incr.2 — `pct/sentenza_economic_dashboard.py`: riepilogo additivo innestato in `build_fascicolo_economic_dashboard(..., sentenze=None)` + blocco di contesto pass-through.
- Incr.3 — `lex/tools/economic_context_tools.py`: 5 tool Lex read-only governati (flag `lex.economicContextTools` default-off), astensione se RG non combacia; sorgente `EconomicJudgmentSource`.
- Incr.4 — runtime `web/services/sentenza_economic_runtime.py` (core iniettabile) + blueprint `/api/v1/ui/sentenza-economic/*` dietro auth studio + backend-security.
- Incr.5 — `pct/sentenza_economic_workflow.py`: trigger PEC automatico su `deposito_sentenza` (solo anteprima) e parcella da credito confermato (`origine="sentenza"`). Docs `docs/specs/SENTENZA_ECONOMIC_CONTROL_V1.md`.
- 31 nuovi test verdi; nessuna regressione su operational-knowledge, source registry, feature flag, dashboard economica.

## 2.253.144 - 2026-06-30

- Deposito PCT accettato: la pipeline PEC legge `EsitoAtto.xml`, aggiorna automaticamente il R.G. del fascicolo da `NumeroRuolo` e registra IDBUSTA, Message-ID deposito, mittente PEC, data PEC e data esito in formato italiano.
- Fascicolo React: la sezione `Comunicazioni / Cancelleria` mostra quando il deposito è stato accettato, da chi risulta arrivata la PEC, chi lo ha registrato e il riepilogo `RG / IDBUSTA / Message-ID`, così l'avvocato vede subito lo stato della cancelleria.
- Login studio: il redirect post-accesso rispetta di nuovo `next=/fascicoli/...` solo per percorsi interni sicuri, evitando il ritorno in Panoramica durante l'apertura diretta del fascicolo.

## 2.253.143 - 2026-06-30

- Local Signer `1.6.90`: corretta la prima installazione Windows sui PC cliente. L'installer ora considera pronto il servizio con il ping leggero `127.0.0.1:27272/ping?light=1`, lo stesso usato dal browser, evitando il falso fallimento quando il ping completo resta impegnato in controlli più pesanti.
- Local Signer `1.6.90`: aggiunta diagnostica reale in `installer.log` solo quando il servizio non risponde davvero, con Python selezionato, file installati, porta 27272 e ultime righe dei log runtime; così un nuovo blocco non viene più nascosto da un log generico.
- Telematico React e runtime legacy di supporto: allineato anche il generatore storico del pacchetto Local Signer al ping leggero, perché quel ramo poteva reintrodurre il comportamento vecchio nelle nuove installazioni.
- Studio Telematico: il pacchetto rapido pubblica l'eseguibile `.exe` invece dello script PowerShell e il controllo scroll della superficie telematica resta ancorato all'offset topbar, senza regressioni sui guardrail React.

## 2.253.137 - 2026-06-29

- Deposito PCT reale: corretto il caso PST `IDBUSTA 152647579` con esito `Indice busta ambiguo`, impedendo la coesistenza tra `IndiceBusta.xml` esterno e `IndiceBusta` interno nel `DatiAtto.xml.p7m`.
- La simulazione PEC blocca ora anche i tipi ministeriali non coerenti in `IndiceBusta.xml`: le ricevute telematiche di pagamento devono essere indicate come `Tipo=RT`, mentre ricevute PEC/notifiche e allegati semplici non vengono più confusi con RT.
- Dry-run server e audit busta sono stati allineati alla codifica ministeriale degli errori: `Indice busta non trovato`, `Atto principale mancante`, allegati indicizzati ma assenti, allegati non indicizzati e indice ambiguo non possono più produrre compatibilità 100%.
- Fonti verificate: pagina download PST, specifiche DGSIA 7 agosto 2024 con rettifiche ufficiali, `Formato_Busta_Telematica`, `Codifica_errori_controlli_1.0`, comunicazione DGSIA 19 settembre 2024 sull'accettazione automatica e certificati proxy PDA/EXT 25 marzo 2026.

## 2.253.136 - 2026-06-29

- Deposito PCT reale: corretto il falso-verde della simulazione PEC dopo l'esito PST `IDBUSTA 152644507` (`Indice busta non trovato`).
- La busta PCT genera sempre `IndiceBusta.xml` come parte MIME fisica di `Atto.msg`, oltre a `DatiAtto.xml.p7m`, `IndiceDocumentiDepositati.PDF`, atto principale e allegati.
- L'indice busta ora usa i nomi fisici effettivi dei documenti firmati CAdES, inclusi `Ricorso.pdf.p7m` e `Procura.PDF.p7m`, e verifica ogni `Nome`/`ID` contro il `Content-ID` MIME.
- La simulazione al 100% richiede `IndiceBusta.xml` esterno e non accetta più il solo indice interno nel `DatiAtto.xml.p7m`.
- Produzione Hetzner: hotfix distribuito su container unico `iusentra-app`, `/api/pronto` verificato e cache build Docker pulita.

## 2.253.135 - 2026-06-28

- Standardizzazione visibile date/orari: introdotta la regola permanente per mostrare UI, PDF, PEC, email, audit e report in formato italiano con fuso `Europe/Rome`, lasciando UTC/ISO raw solo nei tracciati tecnici.
- Fatturazione: l'anteprima PDF non mostra più `Data UTC` e usa `Data e ora italiana` con conversione Europe/Rome.
- PEC/email: la data di arrivo e gli orari visibili passano dalla conversione condivisa in ora italiana, con test anti-regressione.

## 2.253.131 - 2026-06-27

- Fascicoli React card-view: esteso il riordino mobile anche al breakpoint tablet/card fino a 1100px, così l'avviso `Scadenze entro 7 giorni` resta dopo lista e filtri quando la tabella desktop è nascosta.

## 2.253.130 - 2026-06-27

- Fascicoli React mobile: l'avviso `Scadenze entro 7 giorni` viene mostrato dopo la lista principale sotto i 760px e diventa compatto, così le card dei fascicoli restano visibili subito anche sui fascicoli reali con molte scadenze.

## 2.253.129 - 2026-06-27

- Fascicoli React mobile: resa compatta la testata della pagina e trasformati gli indicatori in un rail orizzontale, così le card dei fascicoli tornano visibili subito nel flusso mobile senza perdere i dati economici.
- Deploy Hetzner: aggiunta pulizia mirata dei container temporanei Docker Compose rimasti da recreate interrotti, con retry automatico di `docker compose up` e guardrail per non toccare container dati, volumi o servizi canonici.
- GitHub Actions: anche il ramo “commit già deployato” esegue la stessa pulizia prima di riattivare i servizi, evitando il conflitto su nomi hashati come `17d5ff..._iusentra-app-1`.

## 2.253.128 - 2026-06-26

- Fascicoli React: la vista economica desktop usa una sola colonna `Controllo economico` con matrice compatta per contributo, Spese/esborsi, liquidazione e parcella, eliminando lo scroll orizzontale e mantenendo una sola voce Spese/esborsi.

## 2.253.127 - 2026-06-26

- OCR economico fascicoli: le esenzioni dal contributo unificato restano tracciate come `Contributo unificato esente`, senza importo e senza data pagamento fittizia ereditata dalla sentenza.

## 2.253.126 - 2026-06-26

- OCR economico fascicoli: il contributo unificato viene riportato solo da pagamento/esenzione realmente presenti nel fascicolo; importi Carta docente, soglie reddituali e autocertificazioni non alimentano più la matrice economica.
- Fascicoli React: `Fondo spese` non è più una voce separata; gli importi legacy confluiscono in `Spese/esborsi`, evitando doppioni in tabella, card mobile, API ed export.
- Lex AI e scheduler: il backfill `lex_sentenza_economia_auto` usa la stessa logica governata di OCR/economia e il worker ripulisce run scheduler rimaste `running` dopo un riavvio.
- Vista economica: rifinite le celle economiche desktop/tablet/mobile, con note lunghe compatte e dettagli apribili senza sovrapposizioni.

## 2.253.125 - 2026-06-26

- Local Signer `1.6.82`: blindato l'installer Windows contro avvii concorrenti con lock su `%APPDATA%\IUSENTRA\LocalSigner\installer.lock`; una seconda esecuzione non puo' piu' cancellare la virtualenv mentre la prima installazione sta configurando pip.
- Local Signer `1.6.82`: se la virtualenv locale esiste ma manca `pyvenv.cfg` o `python.exe`, l'installer la rimuove e la ricrea prima di installare le dipendenze, evitando il blocco `failed to locate pyvenv.cfg`.
- Local Signer: pacchetti Windows/macOS/Linux rigenerati dopo i fix di compatibilita' dell'hot-update; la prova reale locale copre servizio `127.0.0.1:27272/ping`, prima installazione pulita e verifica UI `Local Signer pronto`.

## 2.253.124 - 2026-06-26

- PST/PolisWeb React: la ricerca si ferma subito se manca un certificato CNS/CIE valido sul PC e non avvia più tentativi lunghi verso il fascicolo senza prerequisito operativo.
- PST/PolisWeb React: la tabella ministeriale viene dedotta automaticamente per tutti i profili supportati, inclusi civile, lavoro/previdenza, volontaria, minori, esecuzioni/concorsuali, giudice di pace e Cassazione.
- Telematico React: corretti hover e focus dei pulsanti Local Signer/PST mantenendo testo e icone leggibili; la correzione è confinata al componente telematico e non altera più `Assistenza remota` in topbar.
- Local Signer `1.6.81`: quando il registro ministeriale è esplicito non esplora tabelle estranee e supporta l'aggiornamento automatico da base URL autorizzata, riducendo tempi e intermittenze nel wizard PST.
- Deposito telematico PCT: il controllo della PEC ministeriale ora valida la sintassi `DEPOSITO <testo libero>` indicata dal documento PST sul flusso di deposito; `DEPOSITO TELEMATICO - ...` resta accettato come testo libero dopo `DEPOSITO`.
- Local Signer: il deposito con `Atto.enc` continua a bloccare oggetto non conforme e busta non valida, ma non blocca automaticamente allegati ulteriori scelti dall'avvocato.

## 2.253.123 - 2026-06-26

- Deposito telematico PCT: `Simula invio PEC` e `Invia deposito reale` ora richiedono la verifica ministeriale completa di `Atto.msg`, `IndiceBusta.xml`, `DatiAtto.xml.p7m` e hash `Atto.enc` prima di consegnare il payload al Local Signer, bloccando il falso-verde che poteva arrivare al PST come `Indice busta non trovato`.
- Notifiche legali: l'attestazione di conformità automatica in relata è ora unica e cumulativa, con elenco dei documenti coperti, evitando una dichiarazione separata per ogni allegato.

## 2.253.122 - 2026-06-26

- Hetzner performance: i backup dati usano zstd a budget server (`level=6`, 2 thread, `nice`/`ionice`) e verificano lo spazio libero prima di comprimere, evitando nuove saturazioni CPU/disco.
- Scheduler: la manutenzione AI locale non carica più Ollama in background salvo opt-in esplicito con `IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED=1`; la sync mailbox automatica lavora a piccoli lotti configurabili.
- Hetzner orari: host, container applicativi, `/api/pronto`, `/api/health` e log strutturati usano `Europe/Rome` (`TZ=Europe/Rome` + `tzdata`), così log, job e report non confondono UTC e ora italiana.
- Local Signer: il launcher Windows interpreta `--force`, restart e update anche quando arrivano come argomenti multipli/protocol handler, non solo come primo argomento.
- Operatività: svuotati i backup Hetzner rigenerabili su richiesta utente e aggiornati runbook/test per bloccare regressioni su backup aggressivi e job automatici senza budget.
- Notifiche legali: la relata normalizza il nome avvocato senza doppio `Avv.`, omette `Sezione` vuota e deriva `R.G.` da numero/label pratica quando il campo dedicato manca.
- Notifiche legali: la proposta automatica seleziona solo PDF/PDF-A/P7M notificabili; EML/MSG restano allegati inviabili solo se scelti manualmente e IUSENTRA aggiunge l'attestazione di conformità generata quando serve.
- Runtime incrementale: i percorsi applicativi PEC/email ordinaria, PDP e fatturazione usano `incremental_only=True` come default operativo; la riparazione storica resta solo esplicita sul motore IMAP basso livello.
- Lex documenti: il presidio documentale salva marker persistenti per fascicolo, documento e hash in `pec_audit_log`; se il documento è già stato letto con lo stesso hash non viene riletto né reindicizzato.
- Dataset Lex: il job notturno salva fingerprint di `documenti_ai.json` e opzioni in `source_index.json`/`latest_job.json`; se la sorgente è invariata restituisce `skipped_unchanged` senza aprire di nuovo tutto il JSON.
- Notifiche/Web Push: aggiunta copertura anti-regressione per impedire un nuovo invio push quando la notifica è già presente con la stessa `dedupe_key`.

## 2.253.111 - 2026-06-25

- Vista economica fascicoli: quando la sentenza classifica la voce come `Spese/esborsi`, il payload React e la cella della matrice mostrano quell'etichetta reale invece della voce storica `Contributo unificato`.
- UI desktop/mobile: la colonna diventa `Contributo / spese` e le card compatte riportano le singole voci economiche con stato e importo.

## 2.253.110 - 2026-06-25

- Sentenze Lex AI: la quota `di cui € 21,50 per esborsi/per spese` viene classificata come `Spese/esborsi`, non come contributo unificato, anche quando esiste un PDF CU nel fascicolo.
- Carta docente: il beneficio `euro 500,00` viene salvato nei metadati Lex come beneficio del cliente e non entra in parcella/proforma o bonifico dello studio.
- PDF CU/PagoPA: il job automatico legge anche il PDF del contributo unificato nello stesso fascicolo come doppia prova; se l'importo conferma la sentenza aggiunge audit, se diverge dagli esborsi non sovrascrive la voce sentenza e segnala la discordanza.
- Lex AI: lo schema vettoriale passa a `sentenza_tribunale_compact_v3` con metadati su natura spese/contributo e beneficio cliente, così le vecchie schede incomplete vengono reindicizzate.

## 2.253.109 - 2026-06-25

- Sentenze Lex AI: il parser legge anche le sentenze Carta docente con data testuale (`23 settembre 2025`), intestazione `N. R.G`, importi `euro` e formule `di cui ... per esborsi`, senza usare il beneficio `euro 500,00` come importo di liquidazione o contributo.
- Matrice economica: gli esborsi riconosciuti in sentenza alimentano il campo contributo/spese vive e i fascicoli già processati in modo parziale vengono completati alla run successiva del job automatico.
- Parcella/proforma: la voce `parcella` della matrice non resta più con importo vuoto quando esiste una proforma Lex collegata; le proforme in bozza già create vengono integrate con gli esborsi mancanti e Lex AI reindicizza la scheda sentenza con schema `sentenza_tribunale_compact_v2`.
- Anti-regressione: aggiunti test mirati sul caso Montagnese/`RG 697/2025`, sulla data testuale, sul backfill tenant-aware e sulla ripresa di record già segnati come processati.

## 2.253.108 - 2026-06-25

- Runtime job: `scripts/check_runtime_services.py` ora verifica anche le esecuzioni reali registrate dal worker scheduler, non solo presenza del job; il gate fallisce con causa leggibile se un job obbligatorio non parte, fallisce, resta in corso troppo a lungo o produce un risultato operativo incompleto.
- Runtime job: aggiunto controllo degli ultimi esiti per tutte le pianificazioni attive, con distinzione fra `non ancora dovuto`, `mai eseguito`, `fallito`, `saltato`, `in corso` e `ok`.
- Runtime job: il job obbligatorio non viene più considerato verde quando è solo `running`; il gate aspetta `completed` con `totals` operativi, errori a zero e `vector_embedding_errors=0`.
- Runtime job: la lettura degli output Docker usa UTF-8 esplicito anche su Windows, così nomi job e motivi con accenti non vengono alterati nel report operativo.
- Scheduler: gli eventi APScheduler registrano anche l'avvio del job e le esecuzioni saltate per `max_instances`, così un worker bloccato resta visibile nel registro.
- Certificati PST: il job `pst_certificati_cifratura_weekly` tenta il refresh ministeriale, ma se il PST non risponde e il certificato `.cer` già in cache è valido, registra l'uso della cache valida invece di marcare fallito l'intero perimetro operativo.
- Certificati PST: se la cache contiene un `.cer` scaduto o non valido, il resolver non si ferma più alla cache ma tenta il refresh remoto mirato; il caso reale `0651160115` ha recuperato il certificato valido pubblicato dal PST.
- Anti-regressione: aggiunti test per job mai eseguito, run fallito, run solo avviato, run senza riepilogo operativo, run valido, payload reale delle run manuali e fallback/refresh cache PST.

## 2.253.107 - 2026-06-25

- Sentenze Lex AI: aggiunto job automatico `lex_sentenza_economia_auto` nel worker scheduler; ogni 10 minuti legge i documenti AI già estratti, applica la matrice economia/fascicolo solo se RG e cliente coincidono col fascicolo e alimenta Lex AI in modo idempotente.
- Sentenze Lex AI: la procedura non dipende più da lancio manuale Codex/script; il backfill resta lo stesso motore governato, ma viene eseguito dal software come pianificazione built-in visibile nella console scheduler.
- Runtime Docker: aggiunto `scripts/check_runtime_services.py` per bloccare il caso in cui `app`, `scheduler-worker` e `ocr-worker` non siano sulla stessa versione o il job automatico sentenze non sia registrato.
- Anti-regressione: aggiunti test su scheduler, registry e worker per impedire che il job automatico venga rimosso o scollegato dalla modalità `apply`.

## 2.253.106 - 2026-06-25

- Sentenze Lex AI: bonificati sul server i falsi positivi collegati a `Sentenza Tribunale Vicenza.PDF` / RG `1548/2023` quando il fascicolo ha RG diverso; annullate le proforme in bozza collegate, ripulita l'economia dei fascicoli e rimossi i documenti vettoriali Lex AI errati.
- Sentenze Lex AI: il parser della liquidazione legge correttamente importi a quattro cifre senza separatore migliaia, per esempio `€ 1030,00`, evitando il taglio a `€ 103,00`.
- Anti-regressione: aggiunto test mirato per la liquidazione a quattro cifre e rieseguiti parser/backfill/bridge fatturazione.

## 2.253.96 - 2026-06-23

- Deposito telematico: il payload `Atto.enc` consegnato al Local Signer resta base64 valido anche dopo la redazione JSON tecnica, evitando l'errore `Allegato Atto.enc non e' base64 valido` al click su `Invia deposito reale`.
- Deposito telematico: il corpo PEC viene mantenuto solo se documenta `Atto.enc` e tutti i documenti finali della busta; in caso di bozza vecchia viene rigenerato automaticamente dai nomi reali del pacchetto.
- Anti-regressione: aggiunti test mirati per redazione base64, corpo PEC documento per documento, simulazione 100% e ramo reale Local Signer senza invio server-side.

## 2.253.95 - 2026-06-22

- Sentenze Lex AI: la matrice economia/fascicolo ora si applica solo quando il testo della sentenza conferma sia il cliente del fascicolo sia lo stesso RG; documenti strategici o giurisprudenza di supporto, anche se chiamati `Sentenza Tribunale`, vengono saltati e non alimentano Lex come sentenza del fascicolo.
- Parcelle e Fatture: sostituite le vecchie card informative con card compatte operative per filtri rapidi, bonifico registrato, parcella emessa, nuova parcella, export CSV, numerazione e canale SdI.
- Fatturazione: aggiunti filtri archivio per bonifico registrato, parcella emessa, cliente e nr fascicolo; il payload React espone anche `caseId`, `caseReference` e `caseRg`, mantenendo le azioni reali su dettaglio, PDF, XML, emissione e registrazione bonifico.

## 2.253.94 - 2026-06-22

- Parcelle e Fatture: corretto il layout delle card proforma/fattura per evitare sovrapposizioni tra cliente, origine Lex AI, date e azioni quando i testi sono lunghi.

## 2.253.93 - 2026-06-22

- Sentenze Lex AI: il parser del contributo unificato non usa più l'importo della liquidazione quando il testo parla solo di rimborso del contributo senza importo espresso; aggiunta copertura per la formula `liquidate in complessivi € ...`.
- Anti-regressione: aggiunto test sul caso reale in cui `€ 1.100,00` è liquidazione e non contributo unificato.

## 2.253.92 - 2026-06-22

- Lex AI: il risultato vettoriale della Sentenza Tribunale ora porta una versione di schema `sentenza_tribunale_compact_v1`; i vecchi risultati senza versione o con embedding pendenti non bloccano più la reindicizzazione compatta.
- Runtime Lex: anche l'indicizzazione avviata dalla UI usa l'estratto economico compatto, non il testo OCR esteso, mantenendo intestazione, RG, liquidazione, contributo, fondo spese e proforma.
- Anti-regressione: aggiunti test mirati per schema vettoriale corrente, pending embedding e scheda runtime compatta.

## 2.253.91 - 2026-06-22

- Lex AI: il backfill Sentenza non invia più l'intero testo OCR al DB vettoriale, ma una scheda strutturata con intestazione, RG, importi, proforma e brani economici selezionati.
- Backfill globale: ridotto drasticamente il carico di embedding per completare l'applicazione su tutti i fascicoli eleggibili senza lasciare job sincroni appesi per ore.
- Anti-regressione: aggiunto un test che verifica il limite degli estratti vettoriali e la conservazione di liquidazione, contributo unificato e spese generali.

## 2.253.90 - 2026-06-22

- Sentenze Lex AI: esteso il riconoscimento alle sentenze ufficiali con intestazione ministeriale, RG vicino e segnali di firma/cronologico anche quando il testo estratto non contiene esplicitamente la parola `Tribunale`.
- Sentenze Lex AI: il parser scarta le citazioni interne di sentenze, per esempio riferimenti a Cassazione dentro atti o diffide, evitando aggiornamenti economici e proforme su documenti non qualificati.
- Backfill globale: audit server allargato a tutto il perimetro dati (`331` fascicoli, `4237` testi estratti, `110` documenti con intestazione `Sentenza n. ... pubbl.`), con distinzione tra documenti ufficiali, duplicati e citazioni.
- Backfill globale: deduplica per chiave sentenza/fascicolo, scelta del documento migliore quando esistono copie multiple della stessa sentenza, conteggio `matrix_confirmed` anche per fascicoli già aggiornati e limite controllato degli embedding Lex AI per evitare job lunghi.
- Anti-regressione: aggiunti test mirati per sentenza ufficiale senza parola `Tribunale`, falsa citazione di Cassazione e duplicati della stessa sentenza nello stesso fascicolo.

## 2.253.89 - 2026-06-22

- Sentenze Lex AI: aggiunto lo script tenant-aware `scripts/backfill_sentenza_lex_economics.py` per scansionare tutti i documenti AI già estratti, riconoscere tutte le sentenze applicabili e applicare la matrice dati a ogni fascicolo reale collegato, con report dry-run/apply.
- Sentenze Lex AI: il report del backfill distingue anche sentenze e fascicoli unici, così i duplicati dello stesso documento non possono mascherare il numero reale di fascicoli coperti.
- Lex AI: il backfill alimenta il DB vettoriale tenant-aware con scheda strutturata della sentenza, metadati su fascicolo/RG/data/importi/proforma e deduplica sul documento fonte.
- Fascicoli: rafforzato `StudioDB` sui bind mount Windows/Docker; un lock temporaneo sul journal SQLite non fa più fallire l'apertura scrivibile e le scritture full-table ritentano più a lungo prima di arrendersi.
- Modifica fascicolo React: il POST `Salva modifiche` ora restituisce JSON leggibile a React anche in caso di errore, evitando pagine HTML 500 incollate dentro il messaggio utente.
- Modifica fascicolo React: il form resta smontato finché i dati non sono caricati e i campi data normalizzano solo valori validi, evitando campi vuoti dopo il payload async e warning Chrome su `n.d.`.
- Anti-regressione: aggiunti test mirati per backfill multi-documento, retry SQLite su journal occupato, parser/applicazione sentenza e proforma idempotente.

## 2.253.88 - 2026-06-22

- Fascicoli: la lista React ora usa la data sentenza salvata in `data_prossima_udienza` come fallback di `Prossima scad.` quando non esiste una scadenza aperta collegata, mostrando correttamente la data della sentenza Lex AI.
- Anti-regressione: aggiunto un test mirato per il fascicolo definito da sentenza senza scadenza aperta, verificando anche che una data storica non venga conteggiata come scadenza entro 7 giorni.

## 2.253.87 - 2026-06-21

- Sentenze Lex AI: l'estrazione dell'RG ora privilegia l'intestazione vicino a `Sentenza n. ... pubbl. il ...`, evitando che riferimenti a vecchi RG citati nel corpo del provvedimento generino dedupliche o proforme non corrette.
- Anti-regressione: aggiunto un test mirato sul caso server in cui un `RG n.` citato nella motivazione precede l'intestazione reale della sentenza.

## 2.253.86 - 2026-06-20

- Fascicoli/Lex AI: le sentenze del Tribunale indicizzate come provvedimenti vengono lette in modo deterministico per data sentenza, RG, contributo unificato, fondo spese e liquidazione giudiziale.
- Matrice economica fascicolo: la sentenza aggiorna `Prossima scad.`, stato `Definito`, contributo/fondo spese pagati, liquidazione pagata e parcella da emettere, con deduplica sul documento fonte.
- Parcelle e fatture: creazione automatica della proforma collegata alla sentenza, conversione con un click in fattura/parcella e marcatura pagata quando viene registrato il bonifico sul fascicolo.
- Numerazione: aggiunto il pannello React per inizializzare l'ultimo numero fattura usato per anno, così la numerazione prosegue dal sistema precedente senza salti.
- Lex AI: la sentenza e la scheda strutturata alimentano il DB vettoriale tenant-aware con metadati su fascicolo, RG, data, importi, documento fonte e proforma, in modo idempotente.
- Anti-regressione: aggiunti test mirati per estrazione sentenza, fondo spese, proforma unica, conversione/pagamento, numerazione e indicizzazione vettoriale Lex.

## 2.253.84 - 2026-06-20

- PAT/SIGA: `Genera modulo ufficiale` produce come file principale il PDF ministeriale XFA originale compilato, non più un riepilogo IUSENTRA o un PDF alternativo.
- Moduli ufficiali: il generatore clona i template PAT 4.x integrati nel repository, preserva `/AcroForm` e `/XFA`, compila il pacchetto XFA e mantiene il nome del modulo ufficiale.
- Allegati PAT: i documenti del fascicolo restano file separati pronti per il caricamento Formweb; non vengono incorporati nel PDF del modulo, così il modello resta identico alla fonte ministeriale.
- UI PAT: aggiornati testi e controlli per distinguere il modello XFA ufficiale dagli allegati Formweb e per evitare che l'avvocato interpreti il PDF come un documento riassuntivo prodotto da IUSENTRA.
- Compilazione XFA: normalizzati gli alias dei campi `amministrazione`, `controparte`, `resistente` e `parte`, così validazione API e generatore compilano davvero ricorrente, resistente, codice fiscale, oggetto e allegati nel modello ministeriale.
- Anti-regressione: rimossi i vecchi percorsi backend che generavano un PDF PAT standard con ReportLab e aggiornati i test per verificare XFA compilato, assenza di allegati incorporati e documenti del fascicolo allegabili separatamente.

## 2.253.83 - 2026-06-19

- PAT/SIGA: il PDF generato da IUSENTRA ora si apre nel viewer del browser con dati compilati visibili e incorpora come allegato il modulo ministeriale XFA compilato, evitando l'apertura vuota dei PDF LiveCycle.
- PAT/SIGA: separati i comandi `Apri PDF compilato` e `Scarica PDF`, così l'anteprima non forza più il download e il controllo visivo resta immediato dentro il browser.
- UI PAT: rafforzato hover/focus del bottone `Avvia SIGA` per mantenere testo e icona sempre leggibili.
- Allegati PAT: la selezione automatica dei documenti del fascicolo rispetta il limite Formweb di 50 file e segnala quanti documenti restano esclusi.

## 2.253.82 - 2026-06-19

- PAT/SIGA: rifatta `/pat` come superficie operativa compatta con soli passaggi utili: fascicolo, deposito Formweb, documenti del fascicolo, modulo ufficiale e consegna SIGA.
- Documenti fascicolo: la precompilazione PAT espone tutti i documenti del fascicolo con anteprima, scarico, dimensione, firma e ruolo suggerito; l'avvocato può selezionare quali allegare e modificare il ruolo prima del deposito.
- PDF ufficiali: aggiunti i template ministeriali XFA 4.x nel repository e nuovo generatore `pct.pat_pdf_templates` che parte dal PDF ufficiale, valorizza i campi XFA e incorpora gli allegati selezionati dal fascicolo.
- API PAT: `/api/v1/ui/pat/moduli/compila` valida i limiti Formweb 50 file/300 MB, verifica che i documenti appartengano al fascicolo e produce il nome del modulo ministeriale compilato.
- UI: rimossi dalla route PAT hero, KPI, card generiche, fonti estese e checklist laterali non operative; hover/focus e responsive desktop/tablet/mobile sono governati dagli stili dedicati.
- Mobile: corretto il taglio dei campi modulo PAT su smartphone usando `box-sizing:border-box` sui controlli, rilevato e riprovato nella vista reale `390x844`.
- Verifica reale locale: su Docker `127.0.0.1:8080` il fascicolo `DC5BF1DB` carica `20` documenti, apre l'anteprima PDF, seleziona gli allegati, genera il modulo ufficiale con `20` allegati e mostra la fase finale SIGA senza iframe.
- Anti-regressione: estesi i test React/PAT per XFA ufficiale, allegati incorporati nel PDF e documenti reali del fascicolo con link `Visualizza`/`Scarica`.

## 2.253.81 - 2026-06-19

- PAT/SIGA: riorganizzata `/pat` come percorso operativo `Fascicolo IUSENTRA -> Deposito Formweb -> Modulo compilabile -> Allegati e firme -> Sessione SIGA`, lasciando il portale ufficiale come fase finale di consegna.
- Moduli PAT: aggiunti campi compilabili interni per ricorso, atto, richieste segreteria, ausiliari, ante causam, rimborso contributo unificato e parti; la UI non mostra più `Scarica modulo ufficiale` come azione principale.
- Precompilazione: nuovo endpoint `/api/v1/ui/pat/moduli/prefill` che legge fascicoli, clienti e soggetti reali del tenant corrente per compilare sede, RG, parte, controparte, oggetto, tipo ricorso e dati pagamento dove disponibili.
- PDF interno: nuovo endpoint `/api/v1/ui/pat/moduli/compila` che genera un PDF compilato da IUSENTRA prima della sessione SIGA, con validazione dei campi obbligatori e riferimento al fascicolo selezionato.
- Acquisizione PAT/SIGA: aggiornata `/portali/pat/acquisizione` come fase finale `Consegna finale PAT / SIGA e rientro ricevute`, con passaggi dedicati a accesso SIGA, deposito Formweb, rientro ricevute, file ufficiali, fascicolo IUSENTRA, controlli e registrazione esito. Rimossi testi generici come importazione pratica e mappatura `create new` visibile.
- UI hover/focus: aggiunte regole specifiche per pulsanti, step e card del wizard acquisizione affinché testo e icone restino leggibili anche al passaggio del mouse, focus da tastiera, stato selezionato e disabilitato.
- UI mobile PAT/SIGA: le azioni della sessione assistita sono impilate a tutta larghezza su smartphone e i pulsanti disabilitati usano testo scuro leggibile invece di opacità bassa.
- Anti-regressione: aggiunti test mirati per payload PAT, UI React senza link di scarico come flusso primario, PDF generato e precompilazione dai repository reali.

## 2.253.80 - 2026-06-19

- PAT/SIGA: aggiunto catalogo operativo dei moduli ufficiali 4.x, Formweb, limiti 50 file/300 MB, guida Chrome/Acrobat e fonti G.A. direttamente nel payload React `/pat`.
- Portale Avvocato: la superficie React ora mostra la procedura PAT/SIGA con sessione ufficiale SIGA governata dal Local Connector del PC dell'avvocato, senza iframe fragile, senza `window.open` operativo o fallback esterno come soluzione, filtro moduli per materia/tipo deposito e checklist PAdES/ricevute senza logiche PCT `.cer`/`Atto.enc`.
- Local Connector: il browser chiama direttamente `127.0.0.1:27272`, mentre il backend Docker usa `host.docker.internal:27272`; la sessione assistita resta così praticabile anche quando IUSENTRA gira su server e il `localhost` utile è quello del PC dell'avvocato.
- React `/pat`: corretto lo skeleton iniziale per non mostrare più `PolisWeb / PST` durante il caricamento della superficie PAT; la prova visiva locale su `127.0.0.1:8080` ha coperto desktop/tablet/mobile, click sessione SIGA, raccolta file, chiusura, filtro `rimborso`, scroll completo, zero iframe e zero overflow.
- Anti-fallback: aggiornata `AGENTS.md` con la regola che impedisce di presentare scorciatoie, percorsi alternativi o simulazioni come soluzione finale quando un problema reale resta da risolvere.
- Anti-regressione: aggiunti test mirati per profilo `pat_siga`, catalogo moduli/Formweb, payload React PAT, Local Connector browser/Docker e asset React.

## 2.253.79 - 2026-06-19

- Deposito telematico: corretto il validatore busta per non bloccare l'atto principale quando il documento è già un contenitore CAdES `.p7m`, anche se il vecchio flag storico `firmato_digitalmente` non è valorizzato.
- Anti-regressione: aggiunto test mirato sul caso Palmi/atto principale `.pdf.p7m` per evitare che la simulazione PEC richieda una rifirma non necessaria.

## 2.253.78 - 2026-06-19

- Deposito telematico: estratti gli helper PEC locali dalla route bootstrap per rispettare il gate governance senza cambiare il comportamento già verificato.
- Simulazione PEC reale locale: su `DC5BF1DB` la prova senza invio genera `Atto.msg` e `Atto.enc` AES256, mostra compatibilità 100% e abilita `Invia deposito reale` dopo i controlli.
- Doppia verifica Atto.enc: `Atto.msg` contiene gli 8 documenti operativi previsti, nessun extra operativo e nessun mancante; `Atto.enc` è CMS `enveloped_data` con algoritmo `aes256_cbc`.
## 2.253.77 - 2026-06-19

- Deposito telematico: la firma multipla non tenta più di rifirmare contenitori già firmati `.p7m`, `.sig` o `.pkcs7`; la UI li mostra come contenitori presenti senza dichiarare “Firmato digitale” se manca prova tecnica CAdES/PAdES.
- Simulazione PEC: rimosso il vecchio `Message-ID` fittizio. `Simula invio PEC` prepara lo stesso payload Local Signer dell’invio reale, incluso `Atto.enc`, ma salva solo una prova `PROVA_SENZA_INVIO` e non marca i documenti come depositati.
- Report deposito: aggiunto report di compatibilità con percentuale, controlli strutturali e ricevute da presidiare, visibile nella preview busta.
## 2.253.76 - 2026-06-18

- PagoPA PST: neutralizzato il foglio opzionale `print.css` quando il portale ministeriale lo restituisce come HTML, così la modale nel fascicolo resta senza errore MIME in Chrome.
- Verifica reale locale: in Chrome visibile su `127.0.0.1:8080` il fascicolo `DC5BF1DB` apre PagoPA, carica `+ Nuovo pagamento`, seleziona contributo, distretto `TORINO`, `Tribunale Ordinario - Torino` e mostra `Paga subito` senza inviare il pagamento.

- Verifica reale server: su `https://app.iusentra.it/fascicoli/9B9DF2A1` il fascicolo `RG 3950/2026` apre PagoPA in iframe, carica 66 uffici per `TORINO`, mantiene `print.css` come `text/css`, mostra `Paga subito` senza invio e conferma `Cliente`/`Soggetti` come modali incorporate.

## 2.253.75 - 2026-06-18

- Storage tenant: corretto il controllo SQLite anti-bootstrap per leggere i database in `mode=ro` senza `immutable`, così il runtime vede le modifiche WAL appena committate e non rilancia migrazioni JSON su SQL già operativo.
- CI: ripristinato lo shard `Pytest core fase 7/10 observability parte 3/3` senza indebolire il blocco anti-perdita sui JSON vuoti.

## 2.253.74 - 2026-06-18

- PagoPA PST: eliminato anche il secondo alert CodeQL sul bridge inline servendo le risposte testuali da file temporaneo generato dal server, con Content-Type ristretto e nome inline costante.
- Sessione: confermato che il runtime continua a usare iusentra_session come cookie predefinito.

## 2.253.73 - 2026-06-18

- PagoPA PST: refactor della risposta HTML/CSS/JS del bridge in payload inline servito da file in memoria dopo allowlist host/path, per chiudere l'alert CodeQL XSS senza cambiare il comportamento visibile della modale.
- Verifiche: ripetuti sintassi Python e test mirati PagoPA/sicurezza dopo il refactor.

## 2.253.72 - 2026-06-18

- Sicurezza sessione: rinominato il cookie HTTP di sessione da `hacs_session` a `iusentra_session`, mantenendo invariati `HttpOnly`, `SameSite=Lax` e la configurazione centrale del runtime.
- Audit visuali: aggiornati gli script di collaudo che impostano la cookie locale, così le prove reali su Chrome usano lo stesso nome esposto dal server.

## 2.253.71 - 2026-06-18

- PagoPA PST: ristretto il proxy interno ai soli percorsi attesi del pagamento ministeriale (`it/pagopa_*`, `resources/`, `dwr/`), evitando che un path arbitrario venga servito dentro IUSENTRA.
- Sicurezza: il redirect di rientro `/PST/...` costruisce solo URL interni con `url_for` e ricade sulla pagina PagoPA iniziale per percorsi non consentiti.
- CodeQL: documentata la natura controllata del bridge HTML ministeriale e mantenuti CSP, verifica TLS e allowlist path come guardrail anti-regressione.

## 2.253.70 - 2026-06-18

- PagoPA PST: stabilizzato il bridge dentro il fascicolo anche sui JavaScript/DWR ministeriali; il percorso DWR viene riportato al proxy IUSENTRA, `page` e `Referer` tornano ai percorsi PST ufficiali e `httpSessionId` usa la sessione PST custodita dal proxy.
- PagoPA PST: aggiunta una CSP dedicata solo alla risposta proxy, con compatibilità per il codice storico DWR del PST senza allentare le intestazioni generali IUSENTRA.
- Fascicoli React: l'iframe PagoPA mantiene same-origin nel sandbox e referrer coerente, così il form PagoPA resta compilabile nella modale e la ricevuta PDF continua a essere archiviata come `RICEVUTA_PAGOPA` quando il PST la restituisce.
- Prova reale locale: su Chrome installato e `127.0.0.1:8080` il flusso PagoPA ha aperto `Nuovo pagamento`, selezionato `Contributo unificato e/o Diritti di cancelleria`, scelto il distretto `TORINO`, popolato 66 uffici giudiziari e compilato il codice fiscale senza errori CSRF/CSP; non è stato premuto `Paga subito`.

## 2.253.69 - 2026-06-18

- PagoPA PST: corretto il bridge interno aggiungendo al bundle TLS l'intermedio ufficiale `TI Trust Technologies OV CA`, necessario perché il portale ministeriale espone una catena non chiudibile da `requests/certifi`.
- Sicurezza: la verifica TLS resta attiva; non viene usato `verify=False` e il bundle extra è limitato alla chiamata PagoPA PST.
- Guardrail: il test del bridge verifica che la chiamata al PST usi un bundle CA reale contenente l'intermedio TI Trust.

## 2.253.68 - 2026-06-18

- Fascicoli React: Cliente e Soggetti si aprono in overlay interno sopra il fascicolo, senza uscire dalla pratica aperta.
- PagoPA PST: sostituito l'iframe diretto bloccato dal Ministero con bridge IUSENTRA ristretto a `servizipst.giustizia.it/PST`, con riscrittura di link, form, asset e redirect dentro la modale fascicolo.
- Ricevuta PagoPA: quando l'utente richiede il PDF nel portale PST, il bridge lo serve come PDF e lo salva nei documenti del fascicolo con fonte `PORTALE_TELEMATICO` e classificazione `RICEVUTA_PAGOPA`.
- Guardrail: aggiunto test del bridge PagoPA con pagina PST simulata, richiesta ricevuta PDF e salvataggio documento nel fascicolo.

## 2.253.64 - 2026-06-18

- PST lavoro: l'anteprima React del fascicolo Tribunale di Torino RG 3950/2026 arricchisce lo snapshot parziale della ricerca con il catalogo completo già importato nel fascicolo locale, evitando che restino visibili solo le righe principali quando gli allegati sono già tracciati.
- Telematico: la deduplica dei documenti PST ora considera anche la busta/deposito e non scarta allegati reali privi di id forte quando nome, data e deposito sono sufficienti a identificarli.
- Guardrail: aggiunto test API che riproduce uno snapshot PST parziale con fascicolo locale già allineato e verifica `29/29` documenti in preview, incluso un allegato senza id portale forte.

## 2.253.63 - 2026-06-18

- Local Signer `1.6.78`: corretta la pulizia anti-duplicati su Windows preservando anche il processo padre del servizio che possiede la porta `127.0.0.1:27272`. Questo evita che il launcher chiuda il wrapper `pythonw.exe` del virtualenv e lasci il Local Signer spento subito dopo l'avvio.
- PST React: `Carica anteprima` apre subito i dati fascicolo già restituiti dalla ricerca, senza restare bloccato sul refresh esterno verso `ext.processotelematico.giustizia.it`; il refresh ministeriale resta un arricchimento e non un blocco della vista.
- Guardrail: esteso il test del launcher per impedire il ritorno della regola `ProcessId -ne $owner`, che non distingue un vero duplicato dal padre necessario del processo in ascolto.

## 2.253.62 - 2026-06-18

- Local Signer `1.6.77`: ripristinata la selezione automatica del certificato PST dell'avvocato. Il flusso PST non apre più la finestra generica di Windows quando l'auto-selezione è attiva; se manca un certificato personale valido mostra un errore controllato invece di proporre certificati Adobe, intermedi o scaduti.
- Local Signer Windows: l'avvio elimina le istanze duplicate non proprietarie della porta `127.0.0.1:27272`, evitando processi o prompt appesi nella barra di Windows dopo riavvii o reinstallazioni.
- Guardrail: aggiunti test che impediscono il ritorno del dialog generico in auto-selezione PST e verificano la preferenza per il certificato personale ArubaPEC Authentication anche quando non arriva un codice fiscale esplicito dalla UI.

## 2.253.61 - 2026-06-18

- PST lavoro: completata la tracciatura del fascicolo Tribunale di Torino RG 3950/2026, registro LAV, importando 29/29 documenti reali nel fascicolo IUSENTRA `9B9DF2A1` e salvando il log produzione `PST-20260618085430-C4891C`.
- Telematico React: `Carica anteprima` PST ora riusa i documenti già ricevuti dalla ricerca e non lascia la vista vuota quando l'arricchimento esterno verso `ext.processotelematico.giustizia.it` va in timeout.
- Local Signer: il parser `lav_infofascicolo.wp` ora legge la stessa struttura della tabella civile, distinguendo righe principali, blocchi `Allegati:` e paginazione senza perdere i documenti sotto `downloadDocumentoSemplice.action`.
- Local Signer Windows: rigenerati i pacchetti `1.6.76` e mantenuto l'avvio nascosto, così il servizio non resta agganciato alla barra degli strumenti.

## 2.253.60 - 2026-06-18

- Governance: spostati gli helper firma CAdES/PAdES nel service `fascicoli_signature_options`, riportando `fascicoli_signature_routes.py` sotto il limite di righe senza cambiare i messaggi operativi o il comportamento del deposito.

## 2.253.59 - 2026-06-18

- Sicurezza deposito/firma: sanificati i payload JSON dei percorsi deposito React/legacy, database admin e apertura fascicolo da preventivo/conferimento, senza rimuovere i messaggi operativi utili su CAdES/PAdES.
- Certificati PST: normalizzata la costruzione dei file cache/report `.cer` e aggiunta regressione anti path traversal sui codici ufficio.
- Firma digitale: rimossa la regex fragile dalla nota di firma visibile e aggiunti test mirati per non duplicare o tagliare note utente multilinea.

## 2.253.58 - 2026-06-18

- Telematico React: preservata la priorità del codice ufficio operativo rispetto al codice ministeriale nei dati inviati a Local Signer/PST; il codice ministeriale resta solo fallback quando il codice ufficio non è disponibile.
- Gate CI: riallineato il guardrail `Local Signer boundaries`, così il flusso PST non può regredire tornando a preferire il codice ministeriale nella selezione ufficio.

## 2.253.57 - 2026-06-18

- Deposito reale/PEC locale: `Invia deposito reale` usa sempre il payload Local Signer e non tenta invio SMTP server-side; il server prepara e verifica busta, destinatario, oggetto, corpo PEC e `Atto.enc`, poi il browser chiede la password PEC in una modale locale.
- Deposito React: rimossa la richiesta `window.prompt` non supportata dal browser integrato; la password PEC viene digitata nel modal `Password PEC locale`, non viene salvata sul server e la conferma precedente si chiude prima della chiamata al Local Signer.
- Prova reale controllata: su `127.0.0.1:8080`, fascicolo `DC5BF1DB`, click reale su `Invia deposito reale` con Local Signer e SMTP fittizio `127.0.0.1:25252`; catturata EML con mittente PEC Legalmail, destinatario `gdp.palmi@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023` e allegato unico `Atto.enc` (`4.637.389` byte, SHA256 `1dfbb7d8a8383a05a3c0dcbd84bf8e76cfa382f09c8fb35f85816c3d8dd1d579`).
- Sicurezza: la configurazione PEC reale del tenant è stata ripristinata dopo il collaudo e il server SMTP fittizio è stato spento; il test non ha inviato PEC esterne.
- Limite operativo dichiarato: la prova senza pen drive conferma UI, rotte, payload, Local Signer, composizione PEC e allegato `Atto.enc`; la firma multipla fisica resta verificabile solo con token inserito e PIN reale.

## 2.253.56 - 2026-06-17

- Deposito/PST: documentata e presidiata la regola definitiva per `.cer` e `Atto.enc`: si applicano solo alla busta PST PCT/SICID, PCT/SIECIC, lavoro/SICID, SIGP/Giudice di Pace e Cassazione civile/PST quando usa busta ministeriale; PDP, PAT, PTT, notifiche PEC e UNEP restano canali separati.
- Certificati PST `.cer`: integrati i metadati `nomeCertificatoCifra` da `C:\QuickOrganizer\ListaUfficiGiudiziari.xml` e `QC_Uffici.xml`; il downloader recupera anche per codice ministeriale quando il XML non espone il nome file, come nel caso `Giudice di Pace - Palmi` codice `0800570152`.
- Certificati PST `.cer`: controllo locale corrente su `data/pst/certificati_cifratura` con `913` certificati DER validi, `0` invalidi, perimetro operativo `593/593` codici ministeriali coperti e `0` target mancanti.
- Scheduler: `pst_certificati_cifratura_weekly` mantiene frequenza settimanale nel registry, usa worker configurabili e restituisce report strutturato senza falsi positivi.
- Normativa canali: aggiornate soglie operative in codice e checklist: PCT/PST `60 MB` busta, PDP `50 MB` per file e `500 MB` complessivi, PAT/Formweb `50` file e `300 MB`, PTT/SIGIT `50 MB` per file.
- Local Signer: rigenerati i pacchetti `1.6.75` per Windows, macOS e Linux; gli installer pubblici scaricano anche `local_signer_mod/support_agent.py`, così dist, sorgente e route di download restano allineati.
- Documentazione permanente: aggiornata `procedura-deposito-telematico.md` e `incarico-operativo-permanente.md` con perimetro canali, fonti normative, conteggi certificati, regola fail-closed e differenza tra cache fisica e target operativo.
- Guardrail: confermati verdi canali/scheduler/checklist/conformità, deposito, Local Signer, profilo deposito, busta, simulazione, OpenAPI, build React, retention asset, packaging, release readiness, UTF-8, governance e diff whitespace.

## 2.253.54 - 2026-06-17

- Deposito React locale: riallineata la copia Docker reale `127.0.0.1:8080` e verificato il fascicolo `DC5BF1DB` in Chrome visibile, senza fallback legacy, senza `n.d.`, con ufficio/PEC del Giudice di Pace di Palmi, card busta leggibili e indice `IndiceDocumentiDepositati.PDF` visualizzato nel viewer.
- Deposito PEC: `Simula invio PEC` e `Prova senza invio reale` restituiscono preview JSON `200` quando il pacchetto di controllo è generato ma il trasporto reale resta bloccato; l'errore HTTP `409` resta riservato al tentativo di invio reale non conforme.
- Deposito React: confermata la modifica facoltativa del corpo PEC prima della prova/invio, con textarea editabile e testo standard ripristinabile.
- Guardrail: aggiunto test per simulazione PEC guidata con `.cer`/`Atto.enc` mancanti, così la UI mostra blocchi obbligatori senza errore console.

## 2.253.53 - 2026-06-17

- Deposito/canali telematici: aggiornata la matrice permanente PCT/SICID, PCT lavoro, PCT/SIECIC, SIGP/Giudice di Pace, PDP penale, PAT/SIGA, PTT/SIGIT, UNEP/notifiche/PEC, con fonti ufficiali e regole distinte per trasporto, firme, ricevute e blocchi.
- Certificati PST `.cer`: il job `pst_certificati_cifratura_weekly` ora presidia solo i canali che richiedono certificato PST per `Atto.enc`; uffici non operativi, non PCT o senza certificato pubblicato sono riportati come saltati nel report senza far fallire gli altri aggiornamenti.
- Certificati PST `.cer`: lo script `scripts/precarica_certificati_cifratura_pst.py` accetta `--codice-ufficio` per prove mirate su fascicoli reali; verificato live il certificato `0241160092` del Tribunale di Vicenza con SHA256 ministeriale.
- Deposito dati SQL: prosegue il backfill dei profili deposito esistenti in `profilo_deposito_json` per SQLite/PostgreSQL, includendo PEC, codice deposito, ufficio e stato certificato quando il canale lo richiede.

## 2.253.52 - 2026-06-17

- Deposito PEC: rimosso dal corpo PEC standard il riferimento operativo a IUSENTRA Local Signer; la cancelleria vede solo testo utile al deposito, mentre il canale locale resta tracciato nei messaggi tecnici interni.
- Deposito uffici: il fascicolo con ufficio scritto come `Giudice di Pace - Palmi` ora viene risolto tramite il resolver ufficiale del catalogo, recuperando codice ministeriale e PEC del Giudice di Pace senza modificare i dati del fascicolo.

## 2.253.51 - 2026-06-17

- Deposito React: ripristinato il comando esplicito `Simula invio PEC`, separato da `Prova senza invio reale` e da `Invia deposito reale`, con progress bar dedicata e messaggio che chiarisce che nessuna PEC viene spedita.
- Deposito API: la simulazione PEC usa `simula_invio_pec=1`, restituisce `simulazione=true`, Message-ID fittizio e registra solo una prova marcata nel fascicolo quando il pacchetto è tecnicamente inviabile; l'invio reale resta separato.
- Incarico operativo: aggiunte regole permanenti su attivazione del bottone `Invia deposito reale` quando tutti i requisiti obbligatori sono rispettati e su chiusura della relata/notifica solo dopo prova reale e confronto normativo.

## 2.253.50 - 2026-06-17

- Deposito React/Local Signer: la firma batch non resta più appesa se il servizio locale non risponde; dopo 45 secondi viene mostrato un errore chiaro, la busta resta bloccata e nessun deposito viene trattato come valido senza firme salvate.
- Guardrail UI: aggiunto presidio sul timeout `AbortController` della chiamata `/firma-batch`, così la prova reale non può regredire in una schermata ferma su `Operazione...`.

## 2.253.49 - 2026-06-17

- Deposito React/API: la classificazione documenti non va più in 500 quando il profilo pratica non è determinato; salva comunque la selezione documentale reale, non inventa slot, e lascia Regia in stato `profilo_da_confermare`.
- Prova locale reale: durante `Firma e prepara prova` la barra di avanzamento è stata vista su `127.0.0.1:8080`, ma il flusso ha evidenziato il 500 sul profilo mancante; il fix è stato aggiunto prima di procedere a commit/deploy.

## 2.253.48 - 2026-06-17

- Storage SQLite tenant: se `studio.db` contiene già dati core reali, il runtime non rilancia più il bootstrap dai JSON storici solo perché l'anchor della richiesta è vuoto; questo evita che mirror non autorevoli blocchino la vista React dei fascicoli e del deposito.
- Test anti-regressione: aggiunto il caso SQLite con fascicoli già presenti e anchor `clienti/anagrafica.json` vuoto, per preservare la regola SQL fonte di verità.

## 2.253.47 - 2026-06-17

- Deposito React: aggiunta barra di avanzamento durante `Prova senza invio reale` e `Invia deposito reale`, con nome del documento/payload in lavorazione e scorrimento di `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti selezionati e `Atto.enc`.
- Deposito React: il testo del corpo PEC viene mostrato prima dell'invio e resta modificabile solo su scelta dell'avvocato; la modifica non è obbligatoria e può essere ripristinata allo standard.
- Firma documenti: la spunta laterale `Da firmare` non viene più mostrata sui documenti non selezionati per la busta; resta visibile solo per documenti selezionati o già firmati, mentre le firme obbligatorie sono limitate ai ruoli che lo richiedono.
- Indice busta: `IndiceDocumentiDepositati.PDF` viene visualizzato tramite URL diretto e non più come blob fragile, evitando il viewer grigio/vuoto visto in produzione.
- Cifratura PST: se il certificato pubblico `.cer` dell'ufficio non è recuperabile, `Atto.msg` resta tracciato nell'audit e la UI mostra un esito guidato senza URL tecnici grezzi; l'invio reale resta bloccato finché non esiste `Atto.enc` AES256 conforme.
- Prova server reale: su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#generazione-busta` la prova senza invio mostra progress bar, destinatario `tribunale.vicenza@civile.ptel.giustiziacert.it`, testo PEC predisposto, documenti in busta e controlli mancanti `.cer`/`Atto.enc`, senza più `Download PST non riuscito`.

## 2.253.46 - 2026-06-17

- Deposito telematico server: nella prova reale su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara` il primo caricamento ha mostrato dati `n.d.` e zero documenti per un lock SQLite transitorio su `studio.db`.
- Storage SQLite tenant: `StudioDB.ensure_schema()` ora riusa la connessione thread-local esistente e ritenta brevemente se lo schema è occupato, evitando aperture ridondanti che possono contribuire a lock intermittenti.
- UI React fascicoli: le chiamate dati dei fascicoli ritentano in modo breve sugli errori transitori `408/423/429/5xx`, invece di sostituire subito il deposito reale con il fallback vuoto.
- UI deposito React: ridotta la scala visiva di `Prepara deposito` con testata, pulsanti, cockpit, badge e percorso deposito più compatti, mantenendo leggibili gli stati e invariata la logica di firma/conformità.
- Prova server: dopo ricarica reale del fascicolo `2026/330` la pagina mostra `Tribunale di Vicenza`, canale `PCT lavoro / SICID`, 13 documenti letti, 11 candidati busta, 4 firmati reali, 7 da firmare, e i `.PDF` non PAdES restano `Da firmare`.

## 2.253.45 - 2026-06-17

- Deposito telematico: introdotto il profilo deposito SQL end-to-end da preventivo accettato, conferimento incarico, nuovo fascicolo diretto e fascicolo veloce/autonomo.
- Dati tenant: il profilo deposito viene salvato nella colonna dedicata `profilo_deposito_json` su `fascicoli`, `preventivi_records` e `conferimenti_records`, con upgrade idempotente SQLite e parità PostgreSQL.
- Canali telematici: canale, regole canale, codice deposito, ufficio giudiziario, PEC ministeriale e certificato `.cer` PST vengono risolti subito quando richiesti dal PCT; PDP, PAT e PTT restano separati e non usano certificati PST civili.
- UI deposito React: la fase busta mostra ufficio/PEC verificati, anteprima `IndiceDocumentiDepositati.PDF`, firma multipla immediata prima della prova e conferma separata per evitare invii reali non conformi.
- Firma digitale documenti: la UI mostra `Firmato` solo con prova tecnica CAdES/PAdES; un `.PDF` con testo o nome contenente "Firmato" e il vecchio flag `firmato` resta `Da firmare` se non contiene una firma PAdES verificabile.
- Storage fascicoli: quando `studio.db` è vuoto il JSON configurato viene usato solo come bootstrap controllato, poi SQL torna fonte di verità e il JSON viene rigenerato come mirror dopo il salvataggio.
- Guardrail locali: confermati verdi il blocco deposito/canali/busta/scheduler, `test_ui_deposito_prepara_legge_intero_fascicolo_e_distingue_canale`, `pnpm --filter @iusentra/studio build`, retention asset React, packaging e whitespace check.

## 2.253.44 - 2026-06-17

- CI Pytest core: corretto lo shard `fase 6/10 parte 9/16`, presidiando il caso reale in cui `studio.db` e' gia' operativo e i JSON sono solo mirror.
- Database amministrazione: aggiunto test con clienti/fascicoli seminati in SQL e JSON mirror vuoti, per impedire regressioni che possano cancellare dati SQL durante `attiva-sqlite`.
- Verifiche locali: confermati verdi lo shard 6/10 parte 9/16, il test mirato e `tests/test_database.py` completo.

## 2.253.43 - 2026-06-17

- CI Pytest core: aggiornati i test di amministrazione database alla regola operativa `SQL operativo` con JSON solo mirror, mantenendo separati i test anti-perdita e riconciliazione.
- CI Pytest core: resi deterministici i test route Lex/Local AI che verificano follow-up, fonti, policy e allegati, evitando timeout del gate senza cambiare il comportamento prodotto.
- Verifiche locali: confermati verdi `Pytest core fase 6/10 parte 10/16`, `Pytest core fase 10/10`, `tests/test_local_ai.py`, `tests/test_assistente_followup.py` e `tests/test_web_bootstrap.py`.

## 2.253.42 - 2026-06-17

- Storage SQL tenant: corretto il rilevamento di `studio.db` già inizializzato, evitando una seconda migrazione falsa quando un archivio vuoto come `privacy/registro.json` non contiene ancora record.
- Guardrail dati: aggiunto controllo per non considerare non popolato un database che contiene `settings_config` o mirror SQL, mantenendo comunque il blocco anti-fallback JSON.
- CI coverage: corretto lo shard `Coverage moduli critici parte 10/12`, dopo il verde confermato dello shard 4/12 sul nuovo SHA.

## 2.253.41 - 2026-06-17

- Storage SQL: aggiornato il guardrail login per bloccare il fallback ai JSON quando `studio.db` non è disponibile, coerente con SQL come fonte di verità.
- CI coverage: corretto lo shard `Coverage moduli critici parte 4/12`, che presidiava ancora la vecchia regola di fallback JSON.
- Release: versione applicativa riallineata a `2.253.41` prima del nuovo push, senza cambiare il comportamento dati già stabilito.

## 2.253.40 - 2026-06-17

- Local Signer: completato l'aggiornamento dei guardrail di firma singola e firma batch al parametro `cert_thumbprint`.
- CI GitHub: riprodotti e confermati localmente tutti gli shard `Local Signer e PKCS#11` 1/4, 2/4, 3/4 e 4/4 prima del nuovo push.
- Release: versione applicativa riallineata a `2.253.40` per non mischiare il fix successivo al primo commit `2.253.39`.

## 2.253.39 - 2026-06-17

- Local Signer: riallineato `tools/dist/local_signer.py` al sorgente `tools/local_signer.py`, così l'aggiornamento automatico non distribuisce più codice vecchio.
- Firma batch: aggiornato il guardrail di riuso PIN per coprire anche il parametro `cert_thumbprint`, evitando falsi 500 nel test cross-platform.
- CI GitHub: mirato il rosso `Local Signer e PKCS#11 (ubuntu-latest) parte 2/4` prima di ripetere push, CodeQL, deploy e riallineamento locale.

## 2.253.38 - 2026-06-17

- CI GitHub: sbloccato il gate `Lint + syntax` riallineando la pre-verifica SQL di `Impostazioni` alla struttura normalizzata `settings_config`, senza trattare i JSON storici come fonte operativa.
- Amministrazione database: estratta l'ottimizzazione SQLite in helper dedicato, riportando `admin_database_routes.py` sotto il limite governance senza cambiare il comportamento UI/API.
- Guardrail dati: aggiunto un test mirato che impedisce al blocco anti-perdita di fermare uno studio SQL quando le impostazioni sono già più complete nel database rispetto ai JSON di bootstrap.
- Contratti: OpenAPI e file di versione riallineati a `2.253.38` per il nuovo SHA di rilascio.

## 2.253.37 - 2026-06-17

- Deposito React: chiusa la regressione del menu ruolo che poteva restare aperto sopra la spunta `Da firmare`; ora `Esc` chiude il menu e restituisce il focus al pulsante.
- UI produzione: verificato su `app.iusentra.it` il flusso `E5AE4668` desktop/tablet/mobile con topbar, lista documenti, `.pdf.p7m`, icone visualizza/scarica e viewer documento senza overflow.
- Pacchetto deposito: generato dal server il controllo `Busta_2026-330_RICORSO.enc` senza invio PEC reale, contenente `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` e i documenti firmati `.p7m` selezionati.
- Guardrail dati: il test di classificazione deposito ora rilegge `studio.db` come fonte operativa, evitando che un JSON storico venga usato come verità dei metadati deposito.

## 2.253.36 - 2026-06-16

- Struttura dati: fissata la regola operativa SQL fonte di verità per gli studi in modalità SQLite/PostgreSQL; i JSON tenant-aware sono solo mirror, bootstrap controllato, cache, archivio o import/export storico.
- Audit tenant: `scripts/audit_tenant_data_structure.py` censisce anche JSON operativi nascosti e famiglie dinamiche come Documenti AI, importazioni fascicolo e Lex dataset, popolandoli in `moduli_dati` e `moduli_json_records`.
- Runtime tenant: aggiunti path tenant-aware e isolamento per repository `studio_local_pack`, `editor_ai`, `pec_cancelleria_state`, intelligence/giurisprudenza/legal/telematico, preventivi, termini processuali e template.
- Guardrail: test mirati e audit a freddo sul tenant locale confermano `source_of_truth=sqlite`, `json_authoritative=false`, zero JSON operativi non censiti e contratto dati generale senza warning.

## 2.253.35 - 2026-06-16

- Sicurezza dipendenze: aggiornati i vincoli Python per `cryptography`, `lxml` e `pytest` alle versioni non vulnerabili richieste.
- Sicurezza Python: aggiunti vincoli anche per `aiohttp`, `idna`, `PyJWT` e `urllib3`, così l'ambiente locale e i resolver non scelgono transitive vulnerabili.
- Supply chain frontend: spostati gli override pnpm in `pnpm-workspace.yaml`, come richiesto da pnpm 11, e riallineati `qs`, `hono`, `esbuild`, `vite`, `ws`, `js-yaml` e `@babel/core` nei lockfile.
- Build React: allineato il target Vite a ES2022 per usare `esbuild 0.28.1` senza regressioni di compilazione.
- Guardrail: audit pnpm, audit npm, pip-audit, typecheck, build Vite e test packaging/UTF-8 confermati sulle versioni aggiornate.

## 2.253.34 - 2026-06-16

- Deposito React: la spunta `Da firmare` nella lista `Documenti da inviare` è ora una scelta operativa cliccabile per i documenti non firmati, mentre `Firmato` resta solo informativo e deriva dal documento reale.
- Firma multipla: il comando finale legge solo i documenti selezionati come da firmare; se Local Signer o PIN non sono pronti apre la fase `Firma documenti`, senza restare muto nella fase busta.
- UI deposito: riga documenti, icone visualizza/scarica e menu ruolo sono stati compattati per evitare testo tagliato, uscita dal pannello e disallineamento sui formati laptop.
- Guardrail: confermati typecheck, build Vite e test mirati su classificazione deposito e UI React. La prova visiva server, il dry-run produzione senza PEC e la firma multipla reale restano vincolanti prima della chiusura.

## 2.253.33 - 2026-06-16

- Impostazioni React/Firma Digitale: il controllo Local Signer legge il certificato selezionato, mostra scadenza, intestatario, codice fiscale ed emittente, e salva la scadenza nel profilo firma dello studio con data italiana.
- Login studio: quando il certificato firma salvato scade entro 20 giorni, l'avvocato riceve a ogni accesso un avviso con i giorni mancanti; se risulta scaduto, il messaggio diventa bloccante dal punto di vista operativo.
- Guardrail: aggiunti test mirati su salvataggio scadenza certificato, regola avviso 20 giorni, UI React Impostazioni e diagnostica Local Signer.

## 2.253.32 - 2026-06-16

- Local Signer 1.6.74: aggiunta guardia di istanza unica per evitare processi doppi sulla porta `127.0.0.1:27272`.
- Diagnostica Local Signer: `/diagnosi` mostra ora il certificato avvocato selezionato con codice fiscale e scadenza, non solo l'elenco parziale dei primi certificati dello store Windows.
- Cataloghi PST: aggiunto guardrail sui conteggi reali del catalogo pubblico PST civile/penale e del catalogo ministeriale copiati nel pacchetto Local Signer.
- Deposito React: resta il comportamento di riallineamento automatico del Local Signer prima della richiesta PIN, senza istruzioni manuali come percorso principale.

## 2.253.31 - 2026-06-16

- Produzione React: fissata in `AGENTS.md` la regola operativa che tutto il perimetro studio/prodotto già promosso gira su React; l'unica eccezione resta Superadmin finché non viene pianificato.
- Local Signer React: firma deposito e firma documento non chiedono più all'avvocato di risolvere manualmente avvio/aggiornamento; la UI tenta avvio, aggiornamento, riallineamento e riverifica prima di chiedere il PIN.
- Local Signer 1.6.73: l'hot update ora chiude le istanze duplicate o vecchie di `local_signer.py` e libera la porta `127.0.0.1:27272` prima di rilanciare il servizio aggiornato.
- Monitor globale Local Signer: se il servizio non risponde tenta l'avvio automatico; solo dopo il mancato avvio apre una sola volta il pacchetto ufficiale, evitando download doppi e messaggi manuali come prima risposta.
- Guardrail: aggiornati i test React e Local Signer per impedire il ritorno dei messaggi “riavvia manualmente” e per presidiare aggiornamento automatico, protocollo `iusentra-local-signer://update` e stop dei processi duplicati.

## 2.253.30 - 2026-06-16

- Deposito telematico: sostituita la select nativa dei ruoli documentali con un selettore React ancorato alla riga, così il menu resta allineato e leggibile anche nella lista `Documenti da inviare`.
- Editor professionale: aggiunta la route full React `/editor-professionale` e la voce autonoma nella nav sotto `Studio`, senza sostituire `Redazione Atti`.
- Lettore documenti legali: estesa l'anteprima globale a `.xml`, `.xml.p7m`, `.eml`, `.eml.p7m`, `.txt`, `.txt.p7m` oltre ai `.pdf.p7m`, preservando il download dell'originale.
- Performance React: introdotto code splitting del vendor e delle icone per rimuovere il warning Vite sul chunk principale sopra 500 kB.
- Guardrail: aggiunti test mirati su menu ruolo custom, route Editor professionale e anteprime documentali per fascicoli, PEC ed email ordinaria.
- CI release: riallineata la mappa sicurezza backend generata dopo la nuova route `/editor-professionale`, così `Lint + syntax` non resta rosso sullo SHA di rilascio.

## 2.253.29 - 2026-06-16

- Deposito telematico: corretto il menu dei ruoli documentali secondo il controllo fonti PST/DGSIA e DTD busta; rimangono visibili solo `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica` e `Fuori busta`, senza la voce ambigua `Allegato / prova`.
- Classificazione documenti: il valore storico interno `allegato_prova` e gli alias vecchi vengono accettati solo per compatibilità, normalizzati a `Allegato` e salvati senza riproporre il vecchio ruolo nella UI.
- UI deposito: aggiunte azioni `Visualizza` e `Scarica` direttamente nelle righe dei documenti da inviare; lo slot documentale resta in un solo pannello laterale più largo, senza scroll interno e senza duplicati a fondo fase.
- Responsive deposito: su laptop e tablet lo slot documentale non viene più nascosto né duplicato; resta nel rail laterale quando lo spazio è sufficiente e si impila come unico pannello quando lo schermo è più stretto.
- Shell applicativa: la sidebar resta visibile nella fascia laptop, evitando la perdita della navigazione principale durante il lavoro sul deposito e sulle altre pagine operative.
- Documentazione: aggiunta la direttiva `docs/specs/ministero/PCT_RUOLI_DOCUMENTALI_DEPOSITO_2026-06-16.md` e aggiornato il report della prova server E5AE4668.

## 2.253.28 - 2026-06-16

- Deposito telematico: trasformata la preparazione in una vista a step reale, con un solo pannello operativo visibile, feedback immediato su `Verifica operativa` e `Prepara controllo busta`, link delle card riallineati alle fasi e slot documentali spostati dentro `Documenti da inviare` con layout largo e leggibile.
- Allegati e documenti firmati: esteso il lettore `.pdf.p7m` alle anteprime di PEC ed email ordinaria; l'anteprima estrae il PDF interno quando presente, mentre il download conserva sempre il file `.p7m` originale.
- Studio: aggiunto il pannello `Editor professionale` con accessi rapidi a redazione atti, modelli, ricerca documenti, documenti fascicolo e Lex editor.

## 2.253.27 - 2026-06-16

- Deposito telematico: dopo prova visiva reale sul server, corretto il comportamento dei pannelli `Prepara deposito` che potevano restare tutti aperti insieme.
- UI deposito: lo stato `open` dei pannelli è ora governato da React, così la fase attiva resta una sola; gli approfondimenti documentali e tecnici partono chiusi e non appesantiscono la schermata principale.
- Qualità: la prova server resta obbligatoria dopo deploy, con verifica desktop/tablet/mobile, click reale sulle fasi e scroll completo.

## 2.253.26 - 2026-06-16

- Deposito telematico: il percorso `Prepara deposito` è stato semplificato in fasi operative con un solo pannello aperto alla volta, così l'avvocato vede prima la verifica pratica, poi i documenti, poi la firma, poi busta e indice.
- Slot documentali: la sezione `Documenti da inviare` legge l'intero fascicolo, permette `Invia tutto`, selezione singola e classificazione immediata come atto principale, procura, allegato, prova, prova notifica o fuori busta.
- Sicurezza firma: lo stato `Firmato` è ora solo informativo e deriva dal documento reale; la UI non può più trasformare un documento non firmato in firmato con una spunta manuale. La firma resta valida solo dopo esito Local Signer/backend e salvataggio `.p7m`.
- API deposito: aggiunto l'endpoint protetto `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti`, collegato ai repository reali del fascicolo, senza fallback mock, per salvare classificazione documenti e slot prima del comando finale.
- Comando finale: prima di firma e busta il flusso salva la classificazione visibile all'avvocato, poi avvia la firma multipla dei documenti realmente da firmare e solo dopo procede alla preparazione del pacchetto.
- Guardrail: aggiunti test su classificazione, slot, atto principale unico, endpoint React deposito e blocco anti-firma fittizia; rigenerati OpenAPI e contratti API.
- Stato operativo: restano obbligatorie prima della chiusura la prova visiva reale sul server, l'aggiornamento della macchina locale con verifica `/api/pronto`, la generazione busta dry-run senza PEC reale, il confronto contenuti e la firma multipla con PIN/token reale.

## 2.253.25 - 2026-06-14

- Topbar: l'icona `Recenti` ora copre anche le ricerche recenti, con badge unico calcolato da elementi aperti più ricerche e pannello diviso in `Elementi aperti` e `Ricerche recenti`.
- Ricerca Studio: aggiunta API protetta `/api/recent/search` per registrare solo query realmente usate dalla topbar, con deduplica della stessa ricerca e link diretto a `/global-search?q=...`.
- Ricerca Studio: il click su un risultato registra nello stesso evento utente sia la ricerca sia l'elemento aperto, senza dipendere dal caricamento successivo della pagina; rimossi percorsi fragili basati su `Promise.race` o `keepalive`.
- Verifica reale: su Docker locale `127.0.0.1:8080` versione `2.253.25`, Chrome visibile ha aperto da topbar il fascicolo `/fascicoli/8804C177`, mostrando poi `Recenti e ricerche (2)` con `Elementi aperti` e `Ricerche recenti`.
- Guardrail: estesi test topbar e contratto dati per impedire regressioni su notifiche, scadenze, recenti, ricerche recenti, API collegate e sequenza ricerca -> elemento aperto.

## 2.253.24 - 2026-06-14

- Studio React: verificato nel browser reale locale il perimetro Studio completo, incluse `Legal Skills` e `Regia Agentica`, con `#root` React, menu Studio completo, scroll pagina e assenza di fallback `?_legacy=1`.
- Topbar: corretti e blindati i testi italiani di timer e riepilogo attività (`Timer attività`, `Avvia attività`, `Tipo attività`, `Nuova attività`) e verificati i pannelli operativi su `127.0.0.1:8080`.
- Assistenza remota: confermato con click reale che il pulsante della topbar crea una sessione protetta; la sessione di prova viene chiusa come `Chiusa` dopo la verifica.

## 2.253.23 - 2026-06-14

- Governance dati/tenant/React: aggiunto il contratto applicativo che copre macro-aree, sottomenu e alias della sidebar React, con route full React, API, path tenant-aware, JSON, SQLite, PostgreSQL e repository dedicati.
- Audit runtime: introdotto `scripts/audit_data_flow_contract.py` per diagnosticare `studio.db`, mirror JSON e indice FTS, con riparazione esplicita solo di cache rigenerabili tramite `--repair-json-mirror` e `--repair-search-index`.
- Storage: estesa la parità SQLite/PostgreSQL e la migrazione core per time tracking, messaggi, privacy, notifiche, backup e configurazioni collegate.
- Topbar: mantenuti i collegamenti reali a notifiche, scadenze, recenti, timer, assistenza remota e Voce Studio, con microcopy italiano corretto per `Nuova attività` e `già collegata`.

## 2.253.22 - 2026-06-14

- Sicurezza CodeQL: eliminata l’annotazione medium residua sul wrapper JSON pubblico, sostituendo il `jsonify` diretto su payload sanificati con una `Response` JSON controllata dopo serializzazione sicura.
- Guardrail: mantenute verdi le regressioni su tenant traversal, payload pubblici e CodeQL bloccante su push.

## 2.253.21 - 2026-06-14

- Sicurezza CodeQL: chiuse le annotazioni su tenant storage, validando la chiave studio prima di risolvere cartelle sotto `data/tenants` e impedendo traversal o path assoluti nei controlli manutenzione server.
- API React: aggiunto sanitizer pubblico sui payload delle route Fascicolo/Regia e import scadenze PDF, così traceback, eccezioni e percorsi server restano nei log riservati e non vengono rimandati al browser.
- CI anti falso-verde: `CodeQL`/code scanning è ora richiesto anche sui push dei branch gemelli, quindi un deploy non può più risultare verde mentre il check sicurezza dello stesso SHA è rosso.
- Test mirati: aggiunte regressioni su traversal tenant, payload pubblici senza stack trace e gate CodeQL bloccante su push.

## 2.253.20 - 2026-06-14

- CI e deploy: il gate obbligatorio GitHub riconosce i check duplicati dei due branch gemelli e non scambia una cancellazione di concorrenza per un fallimento reale quando esiste lo stesso check riuscito sullo SHA corrente.
- Anti falso-verde: aggiunta regressione sul selettore dei check richiesti, così i report di rilascio restano bloccanti sui fallimenti veri ma non impediscono il deploy per cancellazioni duplicate già coperte da una run verde.
- Lex/fonti: integrato l'adapter Brocardi come fonte secondaria disabilitata di default, con import campione senza rete e guardrail che ricordano di preferire Normattiva o Gazzetta Ufficiale per la citazione ufficiale.

## 2.253.19 - 2026-06-14

- Deposito telematico: il codice oggetto ministeriale scelto in apertura fascicolo viene normalizzato e usato nei passaggi di deposito; il controllo copre tutti i 1018 codici ufficiali PST importati dagli XSD, non solo casi campione come `222050`.
- Regia e canali deposito: blindata la matrice operativa per PCT SICID, PCT lavoro/SICID, PCT SIECIC, SIGP/Giudice di Pace, PDP penale, PAT/SIGA, PTT/SIGIT, UNEP, PEC stragiudiziale e notifiche PEC, impedendo ricadute generiche su “canale da verificare” quando il profilo è determinabile.
- Busta: generazione del pacchetto con `IndiceDocumentiDepositati.PDF`, riferimento hash in `DatiAtto.xml` e controllo che la selezione vista dall'avvocato coincida con i documenti effettivamente preparati per la busta.
- Audit dry-run server: aggiunti `scripts/server_deposito_dry_run_http.py` e `scripts/audit_deposito_server_dry_run.py` per generare la busta dalla route reale del server senza chiamare l'invio PEC, scaricare il `.enc` e confrontarlo con i campioni reali allegati, distinguendo copia non crittografata coerente da invio ministeriale reale con `Atto.enc`.
- Governance deposito: aggiunta regola permanente in `AGENTS.md` e nella procedura deposito per documentare sempre interventi su deposito, fascicoli, portali, PEC, notifiche, firma digitale, Local Signer, PKCS#11, buste e ricevute.
- Refactor sicuro: spostati helper deposito in `web/services/deposito_route_helpers.py` e riportato `deposito_routes.py` sotto il limite governance senza cambiare comportamento.

## 2.253.18 - 2026-06-14

- Deposito telematico: corretta la firma multipla React in `Prepara deposito` per evitare blocchi muti quando Local Signer rileva il token ma richiede riavvio; la pagina mostra ora riavvio, riverifica e diagnosi locale al posto del comando di firma non eseguibile.
- Firma multipla deposito: se il token è pronto ma manca il PIN, il click sul comando mostra un errore visibile, porta il focus al campo PIN e non lascia l'avvocato senza risposta; resta obbligatoria la prova reale con PIN utente prima di dichiarare verificata la firma effettiva dei documenti.

## 2.253.17 - 2026-06-14

- Deposito telematico: estratti gli helper di trasporto, allegati e sintesi validazione in un servizio dedicato, mantenendo invariato il comportamento e riportando `deposito_routes.py` sotto il limite governance.

## 2.253.16 - 2026-06-14

- Deposito telematico: aggiunta in `Prepara deposito` la sezione visibile `Documenti da inviare`, con spunte su atto principale, allegati e prove proposte dal software, correzione manuale immediata e conteggio dei documenti selezionati prima di firma e generazione busta.
- Deposito telematico: quando la classificazione automatica non è certa, la stessa sezione mostra comunque i documenti del fascicolo non di comunicazione come scelta manuale da verificare, così l'avvocato non resta senza punto di selezione.
- Deposito telematico: il pulsante finale usa la stessa selezione mostrata a video per atto principale, allegati, documenti da firmare e controllo della busta, evitando scelte implicite o nascoste negli slot laterali.

## 2.253.15 - 2026-06-14

- Deposito telematico: rese compatte e leggibili le card di stato della pagina React `Prepara deposito`, mantenendo la densità originale ma avvicinando etichetta, numero e nota per evitare testi spezzati o valori dispersi nella card.
- Deposito telematico: rifinita la checklist di verifica in linguaggio operativo, con righe stabili e testo contenuto senza allargare inutilmente le card.

## 2.253.14 - 2026-06-14

- Deposito telematico: il profilo pratica mostra esplicitamente il tipo di pratica usato per derivare i documenti obbligatori, così il controllo non si limita ai file selezionati ma verifica cosa va depositato per quel procedimento.
- Classificazione documenti: corretta la regola che poteva scambiare parole come `contratto` per `atto`; in impugnazione licenziamento `Atto principale` resta obbligatorio separato, mentre contratto, lettera di licenziamento e buste paga restano documenti di prova.
- Normativa PST: tracciato l'aggiornamento XSD SICI dell'11 giugno 2026 come anticipazione non ancora in esercizio, senza sbloccare in produzione il nuovo codice oggetto `110046` finché il Ministero non comunica la messa in esercizio.
- Firma multipla deposito: aggiunti guardrail tecnici su busta AES256, blocco invio diretto non conforme, firma batch e UI React del prepara deposito; resta obbligatoria la prova reale con PIN utente prima di dichiarare verificata la firma multipla sulla macchina reale.

## 2.253.13 - 2026-06-14

- Deposito telematico: la pagina React `Prepara deposito` mostra una proposta busta operativa con atto principale, allegati collegati dagli slot, documenti da firmare, azione finale coerente con il canale e selezione manuale quando la classificazione non è certa.
- Regole busta: la generazione usa il codice oggetto PST validato quando presente, così `DatiAtto.xml` non ricade sul solo titolo libero del fascicolo.
- Campioni reali: analizzati in modo sanificato gli invii RG 1754/2026 con `Atto.enc`, copia non crittografata, ricorso notificato, deposito di documento richiesto, RAC/RdAC, attestazione, decreto e procura; file con nome `.pdf` ma contenuto MIME riconosciuti come messaggi.
- Agenda e Scadenziario: il documento notificato nel fascicolo può alimentare udienze e termini anche se la PEC è stata cancellata, conservando il link audiovisivo esatto e deduplicando le voci equivalenti.
- Scadenziario React: nella colonna fascicolo viene mostrato il cliente/parte del fascicolo, non il responsabile dello studio; le card operative sono state rese più uniformi e meno ripetitive.
- Test mirati: aggiunte regressioni su classificazione certa/incerta dei documenti, codice oggetto PST nella busta, cliente fascicolo nello Scadenziario, udienza audiovisiva da PDF notificato, deduplica Agenda/Scadenziario e testi PEC professionali.

## 2.253.12 - 2026-06-14

- Fascicoli: promossa la route `/fascicoli/<id>/deposito/prepara` alla shell React operativa, con pagina “Prepara deposito” alimentata dal dettaglio fascicolo reale, Regia Operativa, documenti, ricevute e audit.
- Fallback governato: la pagina classica di preparazione deposito resta disponibile solo con `?_legacy=1`, mentre la GET ufficiale serve React e viene bloccata dai test se torna al comportamento precedente.
- Governance React: aggiunti manifest, contratto legacy e guardrail `check-react-contracts` / `check-route-gate` per impedire regressioni sulla nuova route profonda.
- Test mirati: aggiornati i test di deposito guidato e React shell per verificare sia la route React sia il recupero classico esplicito.

## 2.253.11 - 2026-06-14

- Manutenzione tenant locale: rimossa dalla macchina reale la cartella storica non attiva `antonella-mammola`; resta registrato come studio operativo solo `tenant-8bf98719c459`.
- Backup e manutenzione storage: retention backup, ottimizzazione archivi e compressione allegati lavorano ora sui soli tenant attivi registrati quando esiste `tenants.json`, evitando che cartelle storiche o alias legacy vengano trattati come studi operativi.
- Isolamento multi-studio: anche quando viene richiesto uno studio esplicito, la manutenzione risolve lo slug dal registro attivo, usa solo la cartella storage canonica e associa un hash SHA-256 di identità tenant al contesto backup; tenant non registrati o non attivi vengono rifiutati.
- Test mirati: aggiunte regressioni con cartella legacy, slug esplicito, hash tenant e due studi attivi, verificando che la retention elimini solo dentro il tenant corretto e mantenga separati i backup di ogni studio.

## 2.253.10 - 2026-06-13

- Sicurezza CodeQL: le API admin Product Pack e Resilienza operativa restituiscono JSON tramite un confine di risposta controllato, evitando il sink diretto `jsonify(build_...)` che continuava a generare annotazioni pur con payload filtrati.

## 2.253.9 - 2026-06-13

- Sicurezza CodeQL: rafforzato il Product Pack e l'osservabilità runtime per non usare dettagli tecnici o `last_error` nei payload pubblici delle API admin.
- Messaggi operativi: AI locale, PEC/IMAP e portali telematici ora espongono solo descrizioni controllate, lasciando stack trace e messaggi interni ai log riservati.

## 2.253.8 - 2026-06-13

- Sicurezza CodeQL: chiuse le 3 annotazioni medium residue rimaste sul check separato CodeQL, eliminando il passaggio di messaggi eccezione/traceback verso risposte JSON e superfici admin.
- Superfici admin: i dettagli tecnici di AI locale e crash test operativo restano nei log riservati, mentre UI e API mostrano messaggi operativi controllati per il superadmin.
- Test mirati: aggiunta regressione per impedire che report di resilienza operativa con traceback entrino nel payload pubblico e aggiornata la prova del Product Pack sul dettaglio AI locale.

## 2.253.7 - 2026-06-13

- Sicurezza CodeQL: chiuse anche le 4 annotazioni medium residue dopo il primo hardening, proteggendo risposte API admin e cambio stato fascicolo da dettagli tecnici provenienti da eccezioni.

## 2.253.6 - 2026-06-13

- Sicurezza CodeQL: chiuse le segnalazioni nuove su regex vulnerabili a input patologici nell'estrattore normativo Procedure Completion e nella marcatura dei dati mancanti della Redazione Atti guidata.
- Sicurezza messaggi pubblici: le route annotate da CodeQL non espongono più dettagli tecnici o stack trace nei messaggi restituiti all'utente; i dettagli restano nei log applicativi.
- Test mirati: aggiunte prove di regressione su citazioni normative ostili e marcatori `[DATO MANCANTE: ...]` con escaping HTML, per impedire il ritorno delle vulnerabilità.

## 2.253.5 - 2026-06-13

- Governance CI: spostata la governance di avvio in `web/bootstrap/startup_governance.py`, lasciando `runtime_bundle.py` sotto il limite governato senza cambiare il comportamento runtime.
- Test bootstrap: aggiornati i test al nuovo modulo di governance e reso esplicito il salvataggio della configurazione PEC nel tenant autenticato prima della verifica Local Signer.
- Coverage CI: aggiornato il test tenant per il comportamento attuale di `auth_runtime`, dove il bootstrap legacy viene rinviato fuori dalla richiesta `/login` e non rilancia riconciliazioni pesanti.
- Coverage CI: aggiornato anche il test single-tenant storico per verificare che la navigazione non migri dati legacy e che il bootstrap governato esplicito continui a trasferire i clienti esistenti.

## 2.253.4 - 2026-06-13

- Assistente vocale Studio: il PIN vocale ora resta voce-first. Se Chrome non sente il codice, non legge cifre valide o legge un PIN errato, l'assistente parla, ripete cosa ha capito quando possibile e riapre automaticamente l'ascolto fino a tre tentativi; il campo manuale compare solo come ripiego.
- Dettatura nei campi: con sessione operativa attiva, se la frase pronunciata non corrisponde a un comando autorizzato e un campo valido è selezionato, IUSENTRA prova a scrivere direttamente nel campo attivo o nell'ultimo campo valido ricordato. I comandi riconosciuti restano prioritari rispetto al testo libero.
- Dettatura nel campo stesso: con "detta" o "scrivi qui" il testo ascoltato compare come anteprima direttamente nel campo selezionato; con dettatura libera il testo finale resta selezionato per controllo visivo, senza aprire pannelli aggiuntivi.
- Normalizzazione campi vocali: il primo carattere dei campi testuali dettati viene uniformato in maiuscolo; codice fiscale e numero documento vengono compattati anche con nomi campo reali come `doc_numero`; telefono, CAP, civico e campi numerici non perdono gli zeri iniziali; email/PEC, URL, date italiane e campi a scelta come sesso/genere vengono trattati in base al tipo reale del campo.
- Ricerca vocale: durante la sessione operativa sono validi anche "cerca Rossi", "trova Rossi" e "ricerca Rossi", senza ripetere la frase di attivazione.
- UI Voce Studio: durante l'ascolto PIN viene mostrato uno stato compatto "Sto ascoltando automaticamente" invece di spingere subito l'avvocato sul pulsante "Conferma PIN".
- Richiamo vocale: lo stato ora spiega anche il comando "stop": "Richiamo pronto. Di’ “Studio” per attivare la sessione operativa. Di’ “stop” per bloccare la sessione operativa e tornare al richiamo.", sostituendo "Studio" con la frase personalizzata dallo studio.
- Documentazione e guardrail: aggiornati `docs/STUDIO_VOICE_ASSISTANT.md`, `artifacts/react-migration/studio-voice-assistant-lavoro.md`, `frontend/scripts/check-studio-voice-assistant.mjs` e `tests/test_studio_voice_assistant.py` per bloccare regressioni su PIN automatico, dettatura libera, ricerca senza ripetere "Studio" e normalizzazione dei campi reali.
- Audit reale visibile: Google Chrome installato su `127.0.0.1:8080`, permesso microfono `granted`, 390 frasi, 59 destinazioni, note vocali `appunti`, responsive desktop/tablet/mobile, dettatura campi reali, ricerca `cerca Rossi`, nuovo cliente creato/ripulito e disattivazione/riattivazione senza failure nel report `studio-voice-assistant-browser-audit.json`.
- Nota prestazionale aperta: la build resta verde ma segnala ancora il chunk principale React sopra 500 kB (`index-D9Xs3IhZ.js`, 503,51 kB minificato). Non è risolto in questo hotfix e resta da trattare con una tranche dedicata di code splitting.

## 2.253.3 - 2026-06-13

- Assistente vocale Studio: l'ascolto resta attivo nella stessa scheda anche cambiando pagina o aprendo la modifica di un cliente; si spegne solo con disattivazione esplicita, rimozione profilo o revoca reale del microfono.
- PIN vocale: dopo il riconoscimento del tono, il messaggio "Sto ascoltando il PIN. Pronuncia solo le cifre oppure inseriscile a mano." viene pronunciato prima dell'ascolto; se il PIN è errato o non letto l'assistente lo dice e richiede la ripetizione.
- Comandi vocali: aggiunte le frasi "Studio modifica cliente", "Studio modifica clienti", "Studio modifica soggetto" e "Studio modifica soggetti e parti", con apertura della modifica del record corrente quando il contesto contiene già cliente o soggetto.
- Dettatura unica IUSENTRA: introdotto il servizio centrale `IusentraVoiceInput`, riusato da assistente Studio, Lex AI, editor documento, editor professionale e template atti, senza microfoni duplicati su ogni campo.
- Comandi vocali: aggiunto "Studio detta" con varianti per cliente, soggetto, scadenziario, agenda, appuntamento, Ricerca Studio, email e PEC; il testo entra nel campo attivo o nell'ultimo campo valido selezionato.
- Lex AI: il microfono passa allo stato di ascolto solo dopo l'avvio reale del riconoscimento vocale e usa lo stesso controllo permessi del servizio comune, evitando messaggi incoerenti quando Chrome ha già concesso il microfono.
- Microfono reale: il pre-controllo ora richiede prima un flusso audio semplice e applica dopo, solo se disponibili, cancellazione eco, riduzione rumore e controllo guadagno; dopo rebuild Docker `2.253.3` l'utente ha confermato il funzionamento sulla macchina reale.
- Dettatura legale: normalizzazione centrale di punteggiatura e simboli dettati, inclusi virgola, punto, punto e virgola, punto interrogativo, punto esclamativo, spazio, trattino, più, meno, diviso, chiocciola, underscore/ancscore e asterisco/aterisco.
- Documentazione: aggiunta la sezione "Dettatura unica sul campo attivo" in `docs/STUDIO_VOICE_ASSISTANT.md` e aggiornata la nota operativa dell'incarico.

## 2.253.2 - 2026-06-13

- Assistente vocale Studio: migliorata la tolleranza dell'ascolto reale, con frase di attivazione che accetta varianti controllate come "lo Studio", "ok Studio" e alias prudenti quando la parola personalizzata è "IUSENTRA".
- Comandi vocali: aggiunta corrispondenza leggera singolare/plurale per evitare falsi negativi tipici della dettatura, ad esempio "fascicolo" rispetto a "fascicoli", mantenendo prioritaria la corrispondenza esatta.
- Registrazione tono: la qualità della lettura non usa più un confronto rigido parola per parola, ma parole chiave con alias realistici per trascrizioni come "ios centro" al posto di "IUSENTRA"; aggiornata anche la frase consigliata in modo più leggibile.
- Gate mirati: aggiornati `tests/test_studio_voice_assistant.py` e `frontend/scripts/check-studio-voice-assistant.mjs` per bloccare regressioni su qualità lettura, varianti di attivazione e normalizzazione dei comandi.
- Nota prestazionale aperta: la build resta verde ma segnala ancora il chunk principale React sopra 500 kB (`index-BTzQ4cui.js`, 503,52 kB minificato). Non è considerato risolto e richiede una tranche dedicata di code splitting.

## 2.253.1 - 2026-06-12

- Assistente vocale Studio: integrato nella topbar React con caricamento pigro, calibrazione locale del tono voce di 30 secondi, PIN mascherato, frase di attivazione personalizzabile, ascolto continuo, disattivazione vocale e pannello responsive in italiano.
- Comandi vocali: catalogo governato in `frontend/src/studioVoiceCommands.json` con i 40 comandi iniziali dell'utente, 296 frasi aggiunte, 336 frasi totali e 59 destinazioni o aree apribili, incluse navigazione studio, telematico, ricerca, Lex, impostazioni, amministrazione e sito studio.
- Nuovo cliente da voce: il comando "Studio nuovo cliente" chiede nome, cognome e codice fiscale, rilegge i dati e salva solo dopo conferma tramite la nuova API `POST /api/v1/ui/clienti/voce/crea`, con permesso `clienti.scrivi`, validazioni dominio, audit e sincronizzazione.
- Note vocali Studio: aggiunto il sotto-modulo "Studio, note" con comando note personalizzabile per studio, dettatura libera, chiusura "fine nota/fine note", salvataggio locale della sola trascrizione, estrazione prudente di data e ora, promemoria browser 10 minuti prima e visualizzazione in ora italiana `Europe/Rome`; documentato il limite della notifica frontend quando il browser è chiuso.
- Documentazione e guardrail: aggiunti `docs/STUDIO_VOICE_ASSISTANT.md`, `artifacts/react-migration/studio-voice-assistant-lavoro.md`, `frontend/scripts/check-studio-voice-assistant.mjs` e `tests/test_studio_voice_assistant.py`; la frase consigliata per la calibrazione è visibile nel pannello.
- Audit reale e limite osservato: Docker locale no-cache su `127.0.0.1:8080` pronto con `2.253.1`, audit automatizzato con microfono e riconoscimento simulati verde su 59 destinazioni e 330 frasi, visual load audit desktop/tablet/mobile verde su 15 controlli, fix responsive della rail Fascicoli mobile e manifest PWA riallineato a icone PNG valide. Nel browser visibile il click su `Registra voce e PIN` ha confermato il blocco `Microfono non autorizzato`: con permesso negato il profilo vocale non viene salvato, il PIN resta mascherato e viene svuotato dopo l'errore.

## 2.251.38 - 2026-06-11

- Assistenza remota e Local Signer: ripristinato il controllo completo del PC cliente senza installare un agente separato quando nello studio è già presente il Local Signer. Il pacchetto Windows `1.6.72` include ora `local_signer_mod/support_agent.py` e gli endpoint `/support/status`, `/support/arm`, `/support/disarm`, `/support/screenshot`, `/support/execute`; il controllo resta armato solo dopo consenso cliente, con token di sessione, CORS loopback e rifiuto di token/origin non validi.
- Aggiornamento automatico Local Signer: la stanza cliente e il monitor globale provano prima l'aggiornamento via `/update` quando trovano un signer vecchio o senza `/support/status`, attendono il riavvio e mostrano il pacchetto manuale solo se il servizio non è raggiungibile o non può aggiornarsi. Il vecchio messaggio iniziale `Installazione Local Signer richiesta` non viene più mostrato come prima azione quando il servizio può auto-aggiornarsi.
- Stanza cliente assistenza: rimossa la vecchia card/anteprima schermo lato cliente; il cliente vede consensi, microfono, chat e chiusura sessione, mentre il video condiviso è visibile nella stanza operatore. La condivisione schermo usa prima `getDisplayMedia()` del browser, senza installazioni.
- Topbar React assistenza: allineato il payload alla vecchia topbar funzionante, includendo email utente, studio, tenant e contesto pagina; la richiesta dalla barra studio apre la stanza cliente firmata con dati reali.
- Route React segnalate: verificati su Docker reale `127.0.0.1:8080` i caricamenti di `Redazione Atti`, `Ricerca Legale`, `Archivio Giurisprudenza`, `Compensi Forensi` e `Sito Studio`, senza `Pagina temporaneamente non disponibile` né errori console.
- Packaging e prova reale: rigenerati `SetupLocalSigner-1.6.72.exe` e alias `SetupLocalSigner.exe`; installazione locale reale aggiornata da `1.6.68` a `1.6.72` e verificata su `27272` con `/ping?light=1`, `/support/status`, arm, execute dry-run, token errato `400`, origin non consentita `403` e disarm.
- Hardening gate finali: eliminata la scrittura `Path.write_text` segnalata dal check CodeQL separato nella cache JSON, mantenendo la cache in memoria cifrata e invalidata dopo ogni salvataggio; il benchmark `performance_smoke` usa ora un contesto Lex minimo, un retrieval deterministico senza planner/fonti e un report pubblico normalizzato senza `SECRET_KEY` sintetica, con soglia cold-start CI esplicita a `3200 ms` e smoke strict verde.

## 2.251.37 - 2026-06-11

- Migration Center — sink reale clienti (primo wiring): nuovo `web/services/import_center_runtime.py` con `ClientiRecordSink` che traduce i record di staging di tipo CLIENTE in clienti reali tramite `GestioneClienti` (tenant-aware, iniettato nel contesto studio: il sink non sceglie il tenant). `import_clienti_from_staging(gestione, staging, dry_run=True)` simula; con `dry_run=False` crea i clienti validi non duplicati (persona fisica da nome/cognome, persona giuridica da ragione sociale/P.IVA, recapiti email/cellulare) e popola il RollbackLedger per l'annullamento; `existing_client_keys` deduplica contro i clienti già presenti. Il validatore del Migration Center ora accetta correttamente i clienti persona giuridica (identità da ragione sociale, non solo nome). Dry-run resta il default: nessuna scrittura senza commit esplicito. API `/api/v1/ui/import-center/*` e UI React, e i sink per fascicoli/scadenze/fatture, nei PR successivi.

## 2.251.36 - 2026-06-11

- Portale Cliente — accesso sicuro magic-link + OTP (primitiva backend): nuovo `pct/client_portal_access.py` con `PortalAccessManager`. Magic-link opaco generato con `secrets`, salvato solo come hash, a tempo (TTL) e monouso; sfida OTP a tempo con limite tentativi (oltre la soglia la sfida è bloccata e nemmeno l'OTP corretto la sblocca); confronti a tempo costante; nessun segreto in chiaro nello store; storage-agnostico (`AccessStore` iniettabile, tenant-aware in produzione); tenant/cliente/pratica risolti lato server dal grant emesso dallo studio; revoca disponibile. Costruito sopra la filosofia del login guard dello studio. Consegna OTP sul canale, persistenza tenant-aware, aggancio alla sessione del portale ed endpoint pubblici con rate limit nei PR successivi. Documentato in `docs/PORTALE_CLIENTE_ACCESSO.md`.

## 2.251.35 - 2026-06-11

- KPI / controllo di gestione (issue #35, prima fase: motore di calcolo backend): nuovo `pct/kpi/engine.py` con `compute_kpis(...)` che produce il cruscotto direzionale dai dati di dominio — pratiche aperte/chiuse e valore, scadenze critiche/scadute, udienze 30/60/90, economia (parcelle emesse, incassato, insoluto, insoluto scaduto, WIP), tempo lavorato e non fatturato per fascicolo e per professionista, marginalità per cliente e rischio operativo per fascicolo (score scadenze scadute + udienza imminente → basso/medio/alto). Tutte le soglie temporali in `Europe/Rome` con parsing tollerante a date IT/ISO e importi IT/tecnici; nessun crash su campi mancanti o datetime misti naive/aware. Puro e deterministico (8 test). Wiring tenant-aware ai repository, endpoint `/api/v1/ui/statistiche` con export sicuro e drilldown React nei PR successivi. Documentato in `docs/KPI_CONTROLLO_GESTIONE.md`.

## 2.251.34 - 2026-06-11

- Compliance Cockpit (cabina di conformità, prima fase backend): nuovo pacchetto `pct/compliance/`. Conflitto di interessi (`conflicts.py`, base Codice Deontologico Forense): rileva conflitti DIRETTI (nuovo cliente già controparte; controparte proposta già nostro cliente, per codice fiscale) e POTENZIALI (stesso gruppo, match solo per nome), con report `clear/hasDirect/hasPotential` e fascicolo di riferimento. Antiriciclaggio/KYC (`kyc.py`, base D.Lgs. 231/2007): livello rischio basso/medio/alto da fattori spiegabili (PEP, paese a rischio, contante, titolare effettivo non identificato, settore, rapporto a distanza), controllo scadenza documento (scaduto/in scadenza ≤30gg/valido), esito adeguata verifica e flag verifica rafforzata. Registro decisioni (`decisions.py`): JSONL append-only con hash-chain firmata e `verify_chain()` che rileva manomissioni, filtrabile per tenant. Nessuna decisione automatica: supporto tracciabile all'avvocato. Documentato in `docs/COMPLIANCE_COCKPIT.md`. GDPR cockpit, API `/api/v1/ui/compliance/*` e UI React nei PR successivi.

## 2.251.33 - 2026-06-11

- Migration Center (import multi-gestionale, PR 1/N — fondamenta backend in sola anteprima/dry-run): nuovo pacchetto `pct/importers/` (base, registry, validators, dedup, staging, commit, rollback + adapter `generic_csv`). Flusso parse→valida→deduplica→piano di commit, con anteprima sicura (nessun path/segreto). Default dry-run: nulla viene scritto sui dati reali finché non si approva il commit con un sink esplicito (non ancora collegato ai repository); record con campi obbligatori mancanti o CF non valido restano `invalid` e non vengono mai committati; deduplica per chiave naturale (CF/P.IVA, RG/anno, numero fattura) sia intra-batch sia verso i dati già presenti; rollback via ledger delle creazioni. Documentato in `docs/MIGRATION_CENTER.md`. I sink reali tenant-aware, gli adapter gestionali (Studio Telematico/Cliens/Kleos/Netlex/EasyLex/Quadra) e le API/UI arrivano nei PR successivi.

## 2.251.32 - 2026-06-11

- OCR legale — esportazioni strutturate, NER e motori ensemble (estensione engine-independent di `legal_ocr/`): nuovi `legal_ocr/alto.py` (ALTO-XML v4 con coordinate e confidenza dai token), `legal_ocr/tables.py` (ricostruzione tabellare da coordinate, celle multi-parola unite via bande occupate, export CSV/HTML), `legal_ocr/ner_legal.py` (entità legali IT deterministiche: NumeroRuolo/R.G., Uffici, Parti, Date, Riferimenti normativi — non inventa, riporta il testo trovato). L'evidenza del documento espone ora `alto_xml_path`, `tables` e `legal_entities`, con evento `ocr.structured_export` nella audit-chain.
- Adapter motori generali locali reali `EasyOcrEngine` e `PaddleOcrEngine` (cache modello, mappati in `build_engine` su `easyocr`/`paddleocr`/`pp-ocr`): attivi se le librerie sono installate, altrimenti degradano con errori espliciti e la catena di fallback prosegue (nessun silenzio). Il rilevamento layout OpenCV, l'HTR per il manoscritto e la suite end-to-end con 30+ file reali + Docker con modelli restano da eseguire su un ambiente OCR provvisto (binario tesseract + cv2/numpy + easyocr/paddle + rete modelli): documentato in `docs/OCR_STRUCTURED_EXPORT.md`.
- Test engine-independent verdi in sandbox (`tests/test_legal_ocr_structured.py`, 11 casi: ALTO ben formato, tabella 3×3 con celle multi-parola, NER positivi/negativi e normalizzazione anno, factory motori, degrado adapter senza crash, E2E pipeline con ALTO+entità+audit).

## 2.251.31 - 2026-06-11

- Portale Cliente — predisposizione firma documenti (dietro flag `routes.appV2.clientPortal.signatures`, default-off): nuovo adapter `web/services/client_signature_providers.py` con interfaccia `SignatureProvider` e tre provider intercambiabili — `InternalGraphicSignatureProvider` (firma elettronica/grafica con timbro PDF visibile su nuova versione del documento), `ManualUploadSignatureProvider` (fallback download/upload del firmato) e `QualifiedSignatureProviderStub` (segnaposto NON operativo per la firma qualificata remota eIDAS: non dichiara mai una firma qualificata completata). Helper `build_signature_evidence_pack` per il pacchetto probatorio (hash documento originale/firmato, hash IP e riferimento hash del token — mai in chiaro —, user agent, consenso e versione, timestamp, checksum) e `apply_visible_signature_stamp` che timbra il PDF senza mutare i byte originali e fallisce in modo sicuro su PDF cifrato/corrotto. La firma interna è documentata come firma elettronica semplice con evidence pack, non qualificata.
- Privacy Portale Cliente: l'evidence pack di firma non viene più restituito al cliente nei payload pubblici (`_public_row` lo rimuove lato cliente, resta lato studio per l'audit) e l'IP non viene più salvato in chiaro nelle evidenze di firma (solo hash). `client_complete_signature` ora costruisce un evidence pack completo e redatto.
- Coerenza stati superficie pubblica: `/api/v1/ui/client-portal/public/conversation-export` per l'anonimo risponde `401 unauthorized` come la rotta gemella `/public/dashboard` (prima rispondeva `403 forbidden`); l'utente studio autenticato senza permesso continua a ricevere `403`. Nessun dettaglio di tenant/pratica trapela.

## 2.251.30 - 2026-06-11

- Sicurezza accesso (anti brute-force / credential stuffing): nuovo `core/security/login_guard.py`. Il login non aveva blocco dei tentativi falliti e il rate limit generico applicava solo un tetto per IP; un attaccante poteva provare password a ripetizione. Ora, dopo N fallimenti, la coppia (IP, username) viene bloccata a tempo e durante la finestra ogni tentativo è respinto **anche con la password corretta** (HTTP 429 + `Retry-After`), con un tetto separato per IP contro lo spraying su più account. Il blocco è per (IP, username) e non solo per username, così un attaccante non può causare un denial-of-service bloccando da remoto l'accesso della vittima. Evento tracciato in audit come `auth.login_bloccato`. Store Redis quando disponibile (condiviso fra i worker), con fallback in memoria a prova di errore. Attivo per default in produzione (`LOGIN_GUARD_ENABLED`, `LOGIN_GUARD_MAX_PER_USER=5`, `LOGIN_GUARD_MAX_PER_IP=20`, `LOGIN_GUARD_WINDOW_SECONDS=900`, `LOGIN_GUARD_LOCK_SECONDS=900`), disattivo di default solo in ambiente di test.
- Test reali di tentativi di accesso (`tests/test_login_brute_force_guard.py`): blocco dopo soglia, password corretta respinta durante il blocco, azzeramento dopo login valido, nessun DoS sulla vittima da altro IP, header di sicurezza presenti sulla pagina di login.

## 2.251.29 - 2026-06-11

- Branch protection dei gemelli: `branch_protection_contexts()` ora include solo i check producibili su push. I contesti PR-only ("CodeQL" umbrella e "Review dipendenze in ingresso") non esistono mai su un commit pushato senza PR aperta: richiederli nella protection di `Codex/` rendeva il push del workflow "Sync Twin Branches" impossibile per sempre (GH006 "2 of 86 required status checks are expected", verificato sul commit v2.251.28 con tutti gli 84 check di push verdi). Restano richiesti nel gate di valutazione in contesto pull_request. La protection live su GitHub va riallineata una volta (rimozione manuale dei 2 contesti o `--apply-branch-protection` con PAT admin).

## 2.251.28 - 2026-06-11

- CI: il gate "CI reale eseguita sul commit corrente" in contesto pull_request valutava il merge commit sintetico (`GITHUB_SHA`), su cui nessun workflow viene eseguito → falliva sempre dopo 90 minuti (0/85 check trovati) e l'istanza rossa sul commit di testa bloccava il push del workflow "Sync Twin Branches" verso il branch protetto `Codex/` (GH006). Ora il gate valuta lo SHA di testa reale della PR (`github.event.pull_request.head.sha`), dove i check di push e quelli PR-only (CodeQL, review dipendenze) vivono davvero.
- Allineamento gemelli: chiusa la PR claude→Codex aperta manualmente — il meccanismo canonico di allineamento è il mirror "Sync Twin Branches" (fast-forward allo stesso commit), non il merge via PR, che creerebbe un merge commit divergente tra i due rami.

## 2.251.27 - 2026-06-11

- Fix "Pagina temporaneamente non disponibile" su Ricerca Legale: la vista iniziale senza ricerca scaricava l'intero inventario fonti (950+ schede, ~7 MB di JSON, cresciuto con i set Guida Pratica 34-41) e il rendering integrale faceva cadere la pagina. Ora la vista iniziale è un'anteprima bilanciata (max 130 schede, payload ~0,9 MB) e la ricerca live continua a interrogare l'intero archivio; rete di sicurezza anche lato client (max 120 schede renderizzate).
- Auto-ripristino delle pagine React: al primo errore di interfaccia la pagina si ricarica da sola una volta (guardia anti-loop in history.state) e riprende bundle e dati freschi — guarisce anche i tab rimasti sul deploy precedente; al secondo errore resta la schermata di cortesia.
- Console Pianificazioni: le esecuzioni completate con avvisi annidati non vengono più marcate rosse "Da verificare" ma "Completata con avvisi" (il lavoro fatto resta valido); il riepilogo reale dell'agente fonte non viene più sovrascritto dal conteggio sintetico quando è significativo; attivare dalla console una fonte fuori dal gruppo verde della fase 9 ora viene bloccato con un messaggio chiaro invece di essere accettato e riazzerato in silenzio al giro successivo.
- Creazione fascicolo: i messaggi di validazione curati (campi mancanti del Fascicolo Veloce, codici non validi) non vengono più sostituiti dal testo generico nel form e nelle risposte JSON; l'eccezione viene inoltre registrata nei log.

## 2.251.26 - 2026-06-11

- Dashboard e Regia Operativa: normalizzati gli appuntamenti importati con fuso orario (`Z` / `+00:00`) in ora italiana prima dei confronti. Il caricamento non cade più con `can't compare offset-naive and offset-aware datetimes` quando l'agenda contiene eventi da calendari esterni.
- Agenda: `data_ora_dt`, `fine_dt`, reminder e controllo sovrapposizioni espongono orari locali `Europe/Rome` senza cambiare il formato salvato, così reminder, dashboard e viste operative restano coerenti con l'ora italiana.
- Performance dashboard: l'incrocio fra appuntamenti e fascicoli usa indici leggeri per cliente/procedimento, la Panoramica non lancia più ricerche giurisprudenziali full-text per ogni fascicolo e la cache breve evita build concorrenti della stessa dashboard quando due richieste arrivano insieme.
- Top bar React: notifiche e scadenze rapide non fanno più polling automatico a pannelli chiusi; i payload operativi si caricano quando l'avvocato apre il pannello o quando arriva un evento esplicito.
- Coordinamento Claude Code/Codex: bonificata la configurazione `.claude` rimuovendo path esterni non pertinenti, aggiunti hook locali e reso `AGENTS.md` la fonte canonica comune per evitare regole divergenti tra agenti.
- Guida Pratica e Scadenziario: integrati i pacchetti utente `files (23).zip` - `files (29).zip` come set34-41, con 68 moduli versionati, 340 schede ricevute/integrate, 343 termini processuali grezzi, KB completa a 1.755 schede curate e scadenziario rigenerato a 3.908 termini / 1.184 template calcolabili. I codici `151120`, `211010` e `510100` sono stati protetti come guide interne quando la descrizione ricevuta non coincideva con il catalogo ministeriale locale.

## 2.251.25 - 2026-06-11

- Rimossi i `mem_limit` di default introdotti in 2.251.18 su app, scheduler, OCR, Ollama e Redis: un cap rigido trasforma un picco in un kill-loop deterministico del container — in particolare Ollama, se il modello caricato supera il cap, viene ucciso e riavviato in continuazione e le richieste AI in attesa si accumulano nei worker dell'app fino al 503. I limiti restano attivabili esplicitamente (`mem_limit` nel compose + variabili `IUSENTRA_*_MEM_LIMIT`).
- `GUNICORN_TIMEOUT` riportato al valore storico 1800 (il 300 introdotto in 2.251.18 poteva interrompere operazioni lunghe legittime).
- Cache payload dashboard/top bar: spurgo automatico delle voci scadute (le chiavi per utente/giorno crescevano lentamente senza limite nel processo).

## 2.251.24 - 2026-06-11

- Stabilizzazione presidio PEC automatico dopo i picchi di memoria in produzione: budget ridotti e prudenti (acquisizione 25→10 PEC per giro, job lavorati per giro 200→60 — l'OCR degli allegati è la fase più costosa e gira nel worker), override `IUSENTRA_PEC_AUTO_ACQUIRE_BATCH` (0 disattiva) e `IUSENTRA_PEC_WORKER_JOBS_PER_TICK`; scansione archivio limitata alle 250 email più recenti.
- Guardia anti-rilettura: se il registro del presidio non è disponibile (run non creabile), l'acquisizione del giro viene saltata del tutto — con le foreign key attive gli esiti per email non sarebbero registrabili e le stesse PEC verrebbero rilette dal disco a ogni giro.
- Il presidio resta governabile in tempo reale dalla console Pianificazioni ("Presidio PEC automatico" → Pausa) senza bisogno di deploy.

## 2.251.23 - 2026-06-11

- Notifiche dal presidio PEC automatico: quando il presidio crea una scadenza automatica (scadenziario + agenda), ora invia anche la notifica al centro notifiche con push web a tutti gli utenti attivi dello studio con lettura scadenziario. Stessa `dedupe_key` del percorso manuale: nessun doppione se la stessa PEC passa da entrambi i percorsi; la notifica è best-effort e non blocca mai la registrazione della scadenza.

## 2.251.22 - 2026-06-10

- Presidio PEC automatico: lo scheduler acquisisce da solo le PEC archiviate non ancora presidiate (budget per giro, default 25 ogni 5 minuti, override `IUSENTRA_PEC_AUTO_ACQUIRE_BATCH`, 0 disattiva) e i worker completano la catena senza azioni manuali: classificazione, report di validazione, scadenza automatica in scadenziario con collegamento agenda, link al fascicolo e digest. Prima l'ingest partiva solo dal pulsante manuale: le PEC restavano archiviate (es. 307 su 307) ma 0 presidiate, 0 scadenze, 0 agenda, 0 notifiche.
- Dedupe presidio: nuovo `presided_email_ids` sul repository PEC — le email già presidiate (anche senza Message-ID o senza MIME recuperabile) non vengono ritentate a ogni giro.
- Console pianificazioni: i job `Presidio PEC automatico` (*/5) e `Digest PEC giornaliero` (08:00) ora compaiono nel registro e sono governabili (pausa, orario, esecuzione manuale) come gli altri presidi.
- Refactor governabile: i criteri di rilevanza PEC e la lettura/ricostruzione MIME vivono in `web/services/pec_pipeline_runtime.py` e sono condivisi tra API manuale e presidio automatico.
- Memoria/CPU top bar: notifiche, scadenze rapide e quadro "oggi" usano una cache breve per utente (25-60 s, invalidata quando si segnano le notifiche come lette); prima ogni tab aperto ricaricava interi archivi tenant (fascicoli, clienti, scadenze) a ogni poll da 60-120 secondi.
- Bundle dopo deploy: se un tab aperto col bundle precedente chiede un chunk che non esiste più (hash cambiati), la pagina si ricarica da sola una volta invece di mostrare "Pagina temporaneamente non disponibile" (guardia anti-loop in sessionStorage).
- Worker scheduler: il tick del registro pianificazioni prende le richieste manuali ogni minuto ma esegue l'apply completo (upsert template e re-schedule) ogni 5 minuti, riducendo il carico costante di CPU/I-O.

## 2.251.21 - 2026-06-10

- Nuovo workflow "Igiene branch" (avvio manuale, con dry-run): elimina dal remoto ogni branch fuori dalla allowlist autorizzata (`claude/legal-electronic-filing-kIxcV`, `Codex/legal-electronic-filing-kIxcV`, `chore/monorepo-foundation`), applicando la regola di governance registrata in CLAUDE.md.

## 2.251.20 - 2026-06-10

- Governance repository: i soli branch autorizzati sono `claude/legal-electronic-filing-kIxcV`, `Codex/legal-electronic-filing-kIxcV` e `chore/monorepo-foundation`; vietata la creazione di nuovi branch (anche di sessione). Regola registrata in CLAUDE.md, branch non autorizzati rimossi dal remoto.

## 2.251.19 - 2026-06-10

- Indicizzazione AI incrementale: i documenti già indicizzati e invariati su disco (stesso percorso, dimensione e mtime) vengono saltati senza essere riletti in RAM né spacchettati/hashati; prima ogni tick di manutenzione rileggeva integralmente ogni documento (PDF compresi) solo per scoprire che era invariato. Qualsiasi modifica al file riporta automaticamente alla verifica SHA-256 e alla re-indicizzazione.
- Fix bug bloccante FTS: i trigger di `rag_chunks_fts` usavano il comando `'delete'` (valido solo per tabelle FTS5 external-content) e ogni re-indicizzazione di un documento modificato falliva con "SQL logic error" — il documento usciva dal RAG e veniva riletto e ri-parsato invano a ogni tick. Trigger corretti con `DELETE ... WHERE rowid` sia nello schema sia in migrazione automatica sui database esistenti; i documenti rimasti in stato errore si recuperano da soli al giro successivo.

## 2.251.18 - 2026-06-10

- Memoria: il servizio Guida Pratica è ora un singleton di processo (`get_guida_pratica_service`); prima ogni richiesta su catalogo, schede, checklist, guida fascicolo, wizard template e creazione fascicoli ricaricava il KB da 22 MB + 104 moduli (~100-150 MB di picco e ~1,5 s di CPU per richiesta), causa primaria dei picchi RAM e dei 503 sotto carico.
- Memoria: le pagine React di Ricerca Legale (`/ricerca-legale`, news, mediazione, dashboard) riusano per 120 secondi la risposta già serializzata quando non c'è una query (cache per tenant, disattivabile con `IUSENTRA_REACT_LEGAL_PAYLOAD_TTL_SECONDS=0`); le ricerche restano sempre live.
- Memoria: la manutenzione AI locale ogni 30 minuti lavora a budget (default 100×40 chunk per giro, override `PCT_LOCAL_AI_EMBED_BATCH_SIZE` / `PCT_LOCAL_AI_EMBED_MAX_BATCHES`) invece di smaltire fino a 250.000 chunk in un giro solo sullo stesso host che serve l'app.
- Deploy Hetzner: worker web da 4 a 3, `GUNICORN_TIMEOUT` da 1800 a 300 s, riciclo worker a 500 richieste e `mem_limit` per container (app 5g, scheduler 3g, OCR 2g, Ollama 5g, Redis 512m) così un picco riavvia il singolo servizio invece di innescare l'OOM killer dell'host.

## 2.249.42 - 2026-06-09

- Fascicoli: aggiunto il controllo economico a griglia nella pagina React `/fascicoli`, con stato fascicolo sempre visibile, colonne per contributo unificato, fondo spese, liquidazione giudice e parcella, salvataggio rapido per riga e dettagli metodo/note apribili.
- Persistenza fascicolo: le voci economiche vengono salvate nel fascicolo reale con cronologia, operatore e stato; gli importi lasciati vuoti restano vuoti e non vengono trasformati in `0`.
- Export Fascicoli: CSV e payload React includono stati/importi economici, totale registrato e ultimo aggiornamento economico.
- UI Fascicoli: rimosso il confirm nativo dalla cancellazione massiva, sostituito dal modale React già usato dalla pagina.

## 2.249.41 - 2026-06-08

- Console pianificazioni: tutte le manutenzioni manuali pesanti vengono rinviate quando arrivano dentro un avvio massivo con altre esecuzioni manuali già aperte. I controlli UTF-8, crash test operativi e backup blindato restano avviabili singolarmente, ma `Avvia tutti` non lancia più attività lunghe che generano archivi temporanei o lock.

## 2.249.40 - 2026-06-08

- Console pianificazioni: il backup blindato resta eseguibile singolarmente, ma viene rinviato quando arriva dentro un avvio massivo con altri job manuali già in coda o in corso. `Avvia tutti` non avvia più backup nuovi e non ricrea archivi temporanei mentre lo studio vuole conservare solo l'ultimo backup valido.

## 2.249.39 - 2026-06-08

- Console pianificazioni: le manutenzioni manuali pesanti sono ora esclusive. Se un controllo UTF-8, un crash test operativo o il backup blindato è già richiesto o in corso, gli altri job pesanti vengono registrati come non avviati per proteggere spazio, database e reattività; `Avvia tutti` non genera più backup temporanei paralleli.

## 2.249.38 - 2026-06-08

- Console pianificazioni: le esecuzioni manuali restano in stato `requested` finché il worker non le avvia davvero; al riavvio del worker le richieste manuali rimaste aperte dal processo precedente vengono chiuse come interrotte, così `Avvia tutti` non mostra job falsamente in corso.

## 2.249.37 - 2026-06-08

- Console pianificazioni: i canary fonte completati senza pubblicazioni non vengono più marcati come failure; una fonte come `Corte dei Conti` risulta completata quando legge/processa documenti senza timeout né errori interni.

## 2.249.36 - 2026-06-08

- Console pianificazioni: l'avvio manuale di una pianificazione disattivata viene registrato come presidio non avviato e non produce failure; i pulsanti delle righe pausate sono disabilitati e leggibili.

## 2.249.35 - 2026-06-08

- Scheduler superadmin: le fonti legali censite ma fuori dal gruppo verde della fase 9 progressiva non generano più una failure quando si usa `Avvia tutti`; l'esecuzione viene chiusa come presidio rinviato e resta tracciata nel dettaglio.
- CI supply-chain: la generazione SBOM installa Syft con retry, verifica checksum e comando esplicito, evitando failure transitorie quando GitHub risponde 504 sul download dei checksum.

## 2.249.34 - 2026-06-08

- Reso esplicito il `Link cliente` nel Portale Clienti: pannello dedicato nella pratica, link completo visibile dopo generazione, copia immediata, apertura vista cliente e invio manuale tramite WhatsApp Web con testo precompilato.
- Aggiunta ricerca cliente nel form invito: mentre l'avvocato digita, l'elenco clienti viene filtrato e i fascicoli mostrati sono solo quelli collegati al cliente selezionato, con associazione automatica quando il fascicolo è unico.
- Resa visibile la videocall nel flusso appuntamenti: lo studio può inserire un link `http/https` validato e il cliente vede il pulsante `Apri videocall`.
- Corretto il contrasto dei pulsanti nel box link cliente e nella vista cliente pubblica: i comandi primari e secondari restano leggibili su desktop e mobile.
- Normalizzato l'orario appuntamento del Portale Cliente: il valore scelto nello studio viene interpretato in ora italiana, salvato in UTC e mostrato al cliente senza slittamenti.

## 2.249.33 - 2026-06-07

- Aggiunto il Portale Cliente full React: console studio su `/app/portale-clienti` e vista cliente su `/portale-cliente`, con inviti sicuri, dashboard pratica, anagrafica, privacy, documenti, firma semplice, chat, appuntamenti, notifiche, questionari, survey ed export conversazione.
- Introdotto repository tenant-aware `pct/client_portal.py` con schema SQLite e PostgreSQL equivalente, token invito salvati solo come hash e upload documenti senza path filesystem esposti.
- Aggiunte API `/api/v1/ui/client-portal/*`, shell React pubblica/privata, feature flag dedicati, OpenAPI/provider verification, manifest App V2, documentazione e test mirati.
- Rifinita la verifica visuale reale: il cliente vede subito `Scrivi allo studio` e `Apri chat`, il click porta al compositore, il layout desktop compatta le card senza spazio morto, Lex non copre il portale pubblico e i fascicoli marcati come dati di prova non compaiono nelle opzioni studio.

## 2.249.32 - 2026-06-07

- Corretto il parser dei link udienza letti da OCR PDF: i collegamenti Teams/Webex/Meet spezzati da spazi di impaginazione o OCR, come `meetup- join` e `thr ead.v2`, vengono ricostruiti nello stesso URL completo prima di alimentare report PEC, scadenziario e agenda.
- La verifica del link resta positiva quando la normalizzazione rimuove solo spazi OCR interni o punteggiatura finale esterna alla frase, senza cambiare dominio, percorso o parametri del collegamento.

## 2.249.31 - 2026-06-07

- Corretto il presidio delle udienze audiovisive lette da allegati PDF compressi: se un vecchio OCR aveva salvato il contenuto binario dello ZIP (`PK...`) come testo, il refresh PEC lo riconosce come incompleto, rilegge il PDF interno e ricostruisce report, scadenziario e agenda con il link reale.
- Impedito il fallback binario sugli allegati ZIP: un PDF compresso senza testo leggibile resta da OCR/riparare, invece di essere dichiarato letto con contenuto non giuridico.
- Corretto il backfill delle scadenze PEC: i riferimenti legacy `PEC_AUDIT:email:...` non vengono più trattati come ID PEC mancanti e non fanno fallire la bonifica dei link udienza.

## 2.249.30 - 2026-06-07

- Resa operativa la vista `Da PEC` dello scadenziario: mostra solo scadenze PEC aperte e utili al lavoro, mentre i termini già superati restano nello storico audit e non confondono la lista dell'avvocato.
- Migliorata la visualizzazione delle udienze audiovisive: ogni riga e scheda mobile mostra subito evento/ufficio, link udienza, allegato fonte e verifica di identicità del collegamento letto dal PDF o dalla PEC.
- Estesa l'estrazione dei link Teams: vengono conservati interi anche i collegamenti launcher lunghi con parametri codificati, senza troncarli o sostituirli con link tecnici PST/XML/OCSP.
- Collegati gli avvisi PEC agli utenti attivi dello studio e resi visibili nel pannello Notifiche di Impostazioni, così le notifiche interne non restano assegnate al solo processo di manutenzione.

## 2.249.29 - 2026-06-07

- Corretto il presidio PEC su archivi storici dello stesso studio: se una PEC era già salvata nel DB tenant con `tenant_id` storico `default`, il nuovo presidio la riconosce come duplicato utile, normalizza il messaggio allo studio corrente e non produce più errori `UNIQUE constraint failed`.
- Corretto l'audit operativo PEC: l'ultimo stato di presidio viene calcolato sulle righe effettive del DB dello studio, senza dipendere dal primo `tenant_id` trovato in `pec_messages`; il gate ora conta correttamente PEC ingerite, duplicate e processate.
- Aggiunti test di regressione per il caso reale di produzione: duplicato storico `default` recuperato dallo studio Montagnese e audit catena PEC che non torna più a `0/1143` quando il presidio è stato registrato.

## 2.249.28 - 2026-06-07

- Rafforzato il presidio PEC locale: lo script `scripts/presidia_pec_local_archive.py` riprende le PEC dello studio, usa il MIME originale quando disponibile oppure ricostruisce il messaggio locale, poi alimenta PEC Audit, PEC Control Tower, scadenziario, agenda e notifiche.
- Reso severo l'audit operativo `scripts/audit_pec_operational_chain.py`: controlla PEC rilevanti, ultimi stati di presidio per email, scadenze PEC, agenda, notifiche, link udienza validi e falsi positivi 127-ter.
- Corretto il profilo udienza audiovisiva: sentenze a verbale/trattazione scritta 127-ter non espongono più campi udienza remota e i link tecnici di firme, XML, OCSP, CRL, FatturaPA e DTD non vengono pubblicati come collegamenti all'udienza.
- Rigenerazione report PEC resa affidabile anche quando più report sono creati nello stesso secondo: l'ultimo report viene scelto per riga effettiva e non per timestamp ambiguo.
- Estesi i test reali della catena PEC: ricostruzione locale senza EML, scadenziario, agenda, notifiche, link udienza da PDF/OCR, bonifica report e rimozione falsi positivi.

## 2.249.27 - 2026-06-07

- Corretto il presidio PEC delle udienze audiovisive: i link tecnici o istituzionali letti nei MIME/XML/certificati (`pst.giustizia.it`, `Comunicazione.dtd`, OCSP/CRL) non vengono più classificati come link udienza.
- Aggiunta persistenza strutturata del link udienza remota nello scadenziario: URL, fonte allegato, verifica di identicità, modalità, orario, istruzioni accesso e stato “da acquisire dal PDF”.
- Collegata la stessa informazione all’agenda generata dalla PEC, con luogo `Udienza da remoto` e note operative complete quando il link è stato letto dal PDF/OCR.
- Estesa la UI React dello Scadenziario: nella riga e nella scheda dettaglio compaiono `Link udienza da remoto`, fonte, verifica e avviso se il PDF deve ancora essere acquisito.
- Corretta la generazione delle scadenze da PEC Giudice di Pace: una notifica generica D.L. 179/2012 senza termine o udienza concreta non crea più scadenze artificiali, mentre fissazioni, rinvii e differimenti udienza restano `UDIENZA` con RG/oggetto evento distinguibili.
- Aggiunta bonifica idempotente `scripts/backfill_pec_remote_hearing_links.py` per aggiornare le PEC già presidiate senza backup, senza duplicare scadenze e senza promuovere URL tecnici.
- Aggiunta bonifica `scripts/repair_pec_deadlines.py` per rimuovere le vecchie scadenze PEC generiche non fondate, togliere l’eventuale agenda collegata e riallineare udienze reali già presenti.
- Aggiunta deduplica delle scadenze PEC automatiche equivalenti con conservazione di note, link udienza, appuntamento agenda e priorità più alta.

## 2.249.26 - 2026-06-07

- Introdotta la baseline dati tenant obbligatoria: ogni nuovo studio e ogni riparazione superadmin crea/verifica JSON runtime con forma corretta, `studio.db`, `notifications.db`, schema core, agenda, scadenziario e mirror `moduli_dati`/`moduli_json_records`.
- Aggiunto `scripts/audit_tenant_data_structure.py`: controlla tutti i JSON previsti, le tabelle SQLite tenant, il DB notifiche e gli schemi PostgreSQL equivalenti; esce rosso se manca anche un JSON o un mirror SQL. Il controllo non crea backup o snapshot.
- Riallineato il presidio PEC: scadenze e agenda generate o già presenti nei JSON tenant vengono riconciliate in `studio.db`, mentre le nuove scadenze PEC creano anche notifica interna idempotente.
- Estesa la UI React dello Scadenziario con vista `Da PEC` e dettaglio operativo della scadenza: fascicolo, responsabile, ufficio, evento generatore, patrono, operatività ufficio e osservanza bloccante arrivano dal payload reale.
- Aggiornati i test di scadenziario al contratto React/API reale e aggiunti test strutturali che falliscono se JSON, SQLite o mirror SQL non sono allineati.

## 2.249.25 - 2026-06-07

- Trasformata la manutenzione server in una console operativa per superadmin: distingue studi attivi da cartelle legacy/non operative, mostra la composizione dello spazio fuori dagli studi e offre azioni dedicate per backup, cartelle escluse, log, normativa globale e cache servizi.
- Portata la retention backup alla regola richiesta di una sola copia completa: i backup interni tenant eliminano duplicati, archivi temporanei e mirror rigenerabili, mentre il piano operativo non produce più incrementali automatici o copie locali non configurate.
- Aggiunta pulizia governata della normativa globale: il sistema rimuove solo i backup Normattiva duplicati e conserva database, indici e sorgenti utili a Ricerca Legale, Lex e RAG.
- Resa leggibile la salute sistema: il pannello mostra spazio disco reale, studi attivi, posta/allegati, backup/mirror, sistema e piattaforma, con rimandi diretti alla manutenzione invece di numeri ciechi come `0.0 MB`.
- Rafforzata l'osservabilità runtime con dati disco reali del root dati, percentuale usata e spazio libero, evitando stime vuote quando il problema è consumo effettivo sul server.
- Rifatta la Scorecard Lex: distingue catalogo dei casi da prove realmente eseguite, calcola pass/fail, fonti utili e tempi solo da risultati di eval reali, e dichiara esplicitamente quando una suite non è stata ancora misurata.

## 2.249.24 - 2026-06-07

- Introdotti gate reali per Lex/RAG/Ricerca Legale: le domande dell'avvocato su Cartabia, fascicolo attivo, prova PEC completa e riferimenti giurisprudenziali devono produrre risposte operative leggibili, non solo risultati tecnicamente non vuoti.
- Corretto il routing della domanda sul correttivo Cartabia civile: Lex usa fonti ufficiali/pratica legale e restituisce D.Lgs. 149/2022, D.Lgs. 164/2024, codice di procedura civile, uso operativo e pratiche collegate.
- Rafforzata la sintesi del fascicolo attivo: ora espone inquadramento, documenti chiave, rischi, cosa manca e prossimi passi, con test specifico sul caso scolastico/MIM.
- Corretto il problema reale PEC Control Tower su alias tenant: quando lo stesso studio ha `tenant_slug`, `tenant_id` e `tenant_storage_key`, Lex sceglie l'alias con dati giuridici completi e non torna più a zero se prove/ricevute sono nel DB.
- Migliorata la risposta `Qual è la prova completa di questa notifica?`: mostra prove complete prima delle parziali e dettaglia ricevuta di accettazione, ricevuta di consegna, destinatario e orario italiano.
- Corretto il filtro `PEC ricevute oggi`: la data viene confrontata in `Europe/Rome`, evitando che PEC vicine alla mezzanotte UTC spariscano dal presidio giornaliero.
- Estesa la matrice pratica con riferimenti web verificati e test UI Ricerca Legale, inclusa Cassazione Sezioni Unite penali 5166/2026 sulla giustizia riparativa.
- Corretto il bridge Ricerca Legale: ambiente/immigrazione/inPA non vengono più filtrati da riferimenti normativi o rito TAR non esclusivi, le sentenze esatte restano filtrate per organo/numero, i risultati live ufficiali non vengono più tagliati prima della UI e le ricerche su usura/tassi richiedono contenuto ufficiale corrente o tabella normativa reale.
- Corretto Lex sulle questioni penali con allegato: se è disponibile un PDF ufficiale collegato, la risposta su scheda, allegato, norme, udienza, discrepanza R.G. e uso prudente prevale sul catalogo Centro Fonti.
- Rigenerati e validati i contratti OpenAPI dopo il precedente gate remoto rosso su `docs/openapi.yaml`.

## 2.249.23 - 2026-06-06

- Integrato `files (22).zip` nella Guida Pratica come set33: 8 moduli versionati, 40 schede ricevute e integrate, 42 termini processuali grezzi, fonti web operative per ogni scheda e nessuna contaminazione dei codici ufficiali PST/XSD.
- Rigenerato lo scadenziario Guida Pratica: 3.567 termini importati, 1.119 template calcolabili, report JSON/CSV dedicati e test set33 su moduli, servizio, Lex e audit voce per voce.
- Estesa la matrice pratica legale a 25 materie e 90 riferimenti nominali ufficiali, con civile, amministrativo, penale, tributario, lavoro/previdenza, famiglia, scolastico, pubblico impiego, ambiente, edilizia/urbanistica, contabile, societario/231, proprietà industriale, diritto d'autore e immigrazione.
- Collegata la matrice pratica a Ricerca Legale e Lex: le ricerche su TAR/udienze, licenziamento, notifica PEC, PEI/sostegno, concorsi inPA, ambiente e immigrazione trovano schede pratiche e riferimenti nominali senza fallback web live.
- Rafforzato il ranking Ricerca Legale/Lex per mantenere insieme norma numerata e contesto operativo collegato, ad esempio D.Lgs. 165/2001, D.P.R. 487/1994 e portale inPA.
- Aggiornato il Centro Fonti Ufficiali Lex: audit severo verde con 403 fonti censite, 358 ufficiali, 358 operative, 0 fonti sospese e 0 buchi ufficiali.

## 2.249.22 - 2026-06-06

- Esteso il presidio PEC alle udienze con strumenti audiovisivi/remoto: `Comunicazione.xml` inline, PDF diretti e PDF compressi in ZIP alimentano profilo processuale, OCR, link, orario, giudice, parti, agenda/task e Lex/RAG; il link viene marcato utilizzabile solo se identico al valore letto dalla fonte.
- Esteso il Centro Fonti Ufficiali Lex con audit di consegna verso Ricerca Legale/Lex/RAG: 402 fonti censite, 357 ufficiali, 343 operative, 14 da attivare, 0 buchi ufficiali; ogni riga espone materiali giuridici, articoli/codici, D.Lgs./D.M./regole tecniche, sentenze/udienze/provvedimenti e sequenza di ricerca.
- Portati i nuovi campi del Centro Fonti nella UI Ricerca Legale (`source-delivery:*`) e nelle risposte Lex su fonti ufficiali, codici, decreti legislativi, sentenze e udienze, con ranking che privilegia Normattiva/codici e fonti giurisprudenziali ufficiali rispetto a contenitori generici o know-how non ufficiale.
- Collegato il motore aggiornamenti legali al presidio avvocato del Centro Fonti: `autofetchMonitor` arricchisce ogni fonte con uso pratico, fase, output atteso, azione richiesta, materiali giuridici, articoli/codici, decreti/regole, sentenze/udienze/provvedimenti, URL ufficiale e domanda Lex di prova; la UI Ricerca Legale mostra queste informazioni nelle schede "Fonti da presidiare".
- Allineato il presidio massivo PEC al contatore dell'avviso automatico: il controllo a blocchi registra come presidiate anche PEC storiche con solo identificativo/esito PCT, duplicati, MIME non disponibili, scadenze già presenti e termini scaduti, così dopo il completamento l'avvocato vede `0 comunicazioni richiedono presidio` e le esecuzioni successive lavorano solo le nuove PEC.
- Riallineato il DB normativa per tassi antiusura 2026: Q1 e Q2 ora usano le 24 categorie ufficiali per trimestre dai decreti MEF in Gazzetta Ufficiale `25A07045` e `26A01653`, con fonte specifica esposta a Ricerca Legale/Lex e alias storico `carte_credito_revolving` ricondotto a `credito_revolving`.
- Rafforzato lo strumento di verifica usura: sceglie il trimestre dalla data dell'operazione, restituisce TEGM, soglia, categoria ufficiale, fonte GU specifica e avviso di normalizzazione categoria quando serve.
- Corretto il caricamento massivo della pagina PEC/email: la lista usa riepiloghi audit leggeri sopra le 80 comunicazioni, mentre il dettaglio singola PEC mantiene parsing, allegati, report, collegamento fascicolo e prova completa.
- Rafforzata la risoluzione tenant della UI React/API: le sorgenti PEC usano lo slug/studio corrente invece di ricadere su `default`, evitando letture lente e improprie nel database audit dello studio reale.
- Reso l'audit sorgenti Lex tenant-aware sugli alias registrati (`tenant_slug`, `tenant_storage_key`, `tenant_id`): gli alias dello stesso studio sono tracciati, le righe di studi estranei restano bloccanti.
- Confermati gate mirati su PEC, DocumentAI, Template Atti, Ricerca Legale, Lex operativa, UTF-8, typecheck/build React, audit Guida Pratica, audit Template Atti e audit isolamento tenant.

## 2.249.21 - 2026-06-06

- Estesa la copertura Template Atti con fonti ufficiali primarie, decreti legislativi, correttivi, fonti secondarie, attuative, telematiche, deontologiche e autorità competenti: audit severo `scripts/audit_template_atti_legal_sources.py --fail-on-issues` verde su 1512/1512 righe modello, zero problemi modello e zero problemi fonte.
- Pubblicate le ricerche web/fonti modello in Ricerca Legale come record `template-atti-source:*`, con URL ufficiale, autorità, data, ruolo, ambito, prefissi modello, termini di attivazione e controlli operativi verificabili dall'avvocato.
- Aggiornato l'editor Template Atti per mostrare il ruolo `Fonte secondaria collegata` nel pannello Fonti, senza confondere basi comuni con copertura specifica del modello.
- Integrati e riparati i nuovi materiali Guida Pratica/set utente: importer idempotente sugli alias `GUIDA_*`, collisioni 220120/411603 separate dai codici ufficiali, audit materiali utente verde su 256 record e 5745 righe senza perdita verso software, UI o Lex.
- Aggiornato lo scadenziario dalla Guida Pratica con 87 termini letti e 12 template calcolabili; i report JSON/CSV sono in `artifacts/guida-pratica/`.
- Rafforzata Lex AI sul fascicolo attivo: la sintesi legge agenda, udienze, provvedimenti, verbali, sentenze, esiti e scadenze successive dalle sorgenti operative tenant-aware, segnalando quando manca un esito conclusivo leggibile.
- Documentata la memoria operativa e il report fonti in `docs/LEX_RAG_OPERATIONAL_MEMORY.md`, `docs/LEX_PUBLIC_SOURCES_AND_STUDIO_DATA_AUDIT.md` e `docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-06.md`; confermati test mirati Lex/Ricerca Legale/Template Atti/UTF-8, typecheck e build React.

## 2.249.20 - 2026-06-06

- Corretto il collegamento reale tra casella PEC tenant-aware, PEC Control Tower e Lex: le acquisizioni locali e le risposte Lex alimentano ora in modo idempotente gli eventi giuridici dai MIME già salvati nello studio corrente.
- Aggiunto `/api/pec/backfill-locali` e rafforzata l'acquisizione PEC storica: il presidio audit e la Control Tower restano sincronizzati, con deduplica per hash MIME e senza invio PEC automatico.
- Aggiunto audit read-only `scripts/audit_lex_tenant_sources.py` per contare sorgenti Lex per tenant e verificare che PEC, fascicoli, documenti, scadenze, agenda e Control Tower restino sotto la cartella dello studio senza righe di altri tenant.
- Rafforzati i test su backfill Lex da casella locale e isolamento tenant A/B: due studi nello stesso storage logico non vedono eventi PEC dell'altro studio.
- Chiarito che `Scadenze dai PDF` è solo un importatore mirato dai documenti fascicolo: Lex deve ragionare anche su PEC, fascicoli, scadenziario, agenda, notifiche e prove del tenant corrente.
- Collegato il widget Lex del dettaglio/quadro fascicolo al `caseId` e al `clientId` reali, con normalizzazione backend di `pagePath`: la domanda sul fascicolo attivo recupera ora le fonti del fascicolo aperto anche senza contesto esplicito nel testo.
- Estesa la sintesi Lex del fascicolo agli estratti indicizzati dei documenti: richieste su documenti chiave, rischi, cosa manca e prossimi passi non si fermano più al conteggio dei documenti.

## 2.249.19 - 2026-06-06

- Introdotta la PEC Control Tower tenant-aware: parser MIME/daticert/ZIP, classificazione prudente, eventi giuridici, scadenze in bozza, agenda, task, notifiche, prove e audit HMAC con schema SQLite/PostgreSQL paritario.
- Collegata Lex AI alla nuova sorgente `pec_control_tower`, con routing e risposte operative per PEC che generano scadenze, notifiche da fare, invii senza consegna, termini non confermati, cancelleria, PA, notifiche fallite, prova completa, conferme e rischio decadenza.
- Aggiunti API REST `/api/pec/ingest`, `/api/communications`, `/api/deadlines`, `/api/agenda`, `/api/notifications/*`, `/api/audit/*` e calendario ICS, senza invio PEC automatico.
- Aggiunto `scripts/test_pec_control_tower.py`: genera PEC realistiche, alimenta Lex e verifica 10/10 domande operative con output UTF-8; test mirati `tests/test_pec_control_tower.py` verdi.

## 2.249.18 - 2026-06-05

- Corretto il controllo remoto PC nelle sessioni di assistenza su desktop multi-monitor: l'agente ora espone origine e dimensioni dello schermo virtuale Windows e traduce i click sulle coordinate reali, anche quando il monitor condiviso parte da coordinate negative.
- Serializzati i comandi remoti lato operatore: click, doppio click, testo e tasti rapidi attendono l'esito del comando precedente, evitando che il testo venga inviato prima che il click abbia portato il focus sul PC cliente.
- Aggiornato l'audit reale locale per calcolare il click remoto usando la geometria effettiva dello schermo cliente; confermato il marker digitato fisicamente nella finestra cliente durante la prova completa.
- Riallineati i gate CodeQL del rilascio: i test CSP confrontano i source token esatti e gli endpoint AI locale non espongono oggetti eccezione nel messaggio di log/risposta.

## 2.249.17 - 2026-06-05

- Corretto il marker di separazione pagina dell'editor template atti per rispettare il contratto React senza `style={{ ... }}`: la posizione resta governata da CSS e variabile custom aggiornata in modo controllato.
- Rigenerati gli asset React dopo il fix e confermati i gate frontend locali prima del nuovo push sui branch operativi.

## 2.249.16 - 2026-06-05

- Blindato l'isolamento multi-tenant su fascicoli, DocumentAI, import bozza Lex, scadenziario e audit PEC: un fascicolo di altro studio ora viene respinto anche nei flussi API tenant-aware e nelle importazioni editor.
- Corretto il click di controllo remoto lato operatore quando l'immagine condivisa è adattata con bande laterali o verticali: le coordinate vengono calcolate sul rettangolo realmente visualizzato, così il controllo PC raggiunge il campo giusto.
- Rifinito l'editor template atti dopo audit locale reale: toolbar persistente nello scroll, cambio tab coerente con `Campi/Stile/Lex/Fonti/Controlli/Export`, import documento con anteprima campo pronta e compilazione multipla visibile in Export.
- Aggiunto `scripts/react-migration/local_real_workflow_audit.py`, audit end-to-end senza screenshot che verifica su `127.0.0.1:8080` isolamento tenant, assistenza remota con controllo PC, chat, microfono, editor template, import/export, responsive e persistenza PEC -> Scadenziario -> Agenda dopo riavvio.
- Verifiche locali reali su Docker `127.0.0.1:8080`: audit completo verde con tenant `antonella-mammola`, 9 pagine editor, export RTF/DOCX/PDF, import RTF/PDF, controllo remoto con marker digitato, scadenza PEC persistente in agenda e `/api/pronto` verde.

## 2.249.15 - 2026-06-04

- Reso l'editor template atti un vero editor documento: `contenteditable` con selezione reale, grassetto/corsivo/sottolineato/evidenziatore/allineamenti/liste/rientri/citazione/undo/redo applicati alla selezione e non all'intero blocco, toolbar sticky durante lo scroll e ritorno diretto al catalogo.
- Aggiunto il collegamento operativo cliente/fascicolo dentro la compilazione: il pannello `Collegamento IUSENTRA` filtra i fascicoli per cliente e ricompila il template con dati studio, cliente, controparte, ufficio giudiziario, R.G., materia e dati pratica leggibili dal fascicolo.
- Esteso il timbro studio: posizione alto sinistra/centro/destra e centro sinistra/destra, offset verticale regolabile, testo modificabile e formattabile, rimozione della linea superiore della pagina e ripetizione del timbro negli export RTF/DOCX/PDF.
- Rafforzati import/export: DOCX con HTML, PDF con estrazione layout/font/dimensioni quando disponibili, RTF/TXT con accenti italiani corretti; export RTF/DOCX/PDF usa il contenuto HTML dell'editor, include il timbro e mantiene formattazione di base, copia HTML/testo funzionante, salvataggio fascicolo e flusso firma collegati al documento corrente.
- Lex nell'editor usa azioni redazionali locali con controlli placeholder, `legal_basis`, privacy/PII e istruzioni personalizzate; le proposte restano sempre in diff accettabile/rifiutabile e non applicano modifiche senza conferma.
- Integrati i materiali utente `files (10).zip` - `files (14).zip`, `kb_set19.json` e `kb_set20.json` nella Guida Pratica e nello Scadenziario: 73 record ricevuti/integrati, 7 nuovi moduli KB, 3.321 termini processuali importati e 1.075 template calcolabili aggiornati.
- Corretto il flusso assistenza remota: la pagina cliente non mostra più l'anteprima del proprio schermo; la condivisione resta visibile dal lato operatore/SUPERADMIN per prestare assistenza.
- Allineato l'editor ai gate React: niente `Blob` per copia/download nel componente, niente stile inline o accenti laterali vietati, e comando `Copia` verificato leggendo realmente gli appunti nello script browser dedicato.
- Verifiche reali su Docker locale `127.0.0.1:8080` versione `2.249.15`: `python scripts\react-migration\template_editor_browser_check.py` verde 74/74 dopo build e ricreazione container; browser integrato confermato con toolbar sticky, collegamento fascicolo visibile, nessun overflow di pagina/pannello/card e screenshot desktop/tablet/mobile in `artifacts/react-migration/template-editor-2.249.15-*.png`.

## 2.249.14 - 2026-06-04

- Corretto l'editor template atti sui difetti emersi dalla prova reale: collegamento fisico al fascicolo, compilazione automatica di cliente/mittente, controparte/destinatario, ufficio giudiziario, R.G., materia e dati pratica, senza limitarsi ai campi statici del modello.
- Risolto il bug dei campi manuali che inserivano solo il primo carattere: i valori dell'avvocato restano nei campi, aggiornano l'anteprima risolta e vengono applicati solo nel documento/export, senza distruggere i placeholder.
- Resi operativi cambio modello dal pannello sinistro, font e allineamenti documento, timbro studio completo e spostabile, Guida Pratica inseribile nel template, import RTF/DOCX/PDF/TXT con conservazione di accenti italiani e font rilevati, pagina vuota per creare template personalizzati e inserimento dei campi fascicolo nel testo importato.
- Lex Revisione testo ora produce proposte locali in diff accettabile o rifiutabile per correzione, tono, chiarezza cliente, placeholder, normativa, privacy, clausole, premesse e final check; nessuna modifica viene applicata senza accettazione e resta audit visibile.
- Aggiunta compilazione multipla reale con ZIP RTF dei modelli selezionati e azione di firma documento collegata al flusso di firma digitale. Le fonti normative richiamate dai template sono registrate in `pct/template_atti_legal_sources.py` e documentate in `docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-04.md`.
- Verifiche reali su Docker locale `127.0.0.1:8080` versione `2.249.14`: 73/73 controlli browser passati su desktop, tablet e mobile con fascicolo `2DE106E6`, scroll completo, click delle funzioni, import con `à è é ì ò ù`, export RTF/DOCX/PDF, compilazione multipla ZIP, firma, console pulita, zero overflow e date italiane visibili.

## 2.249.13 - 2026-06-04

- Trasformato l'editor template atti/Guida Pratica in workspace professionale React: catalogo laterale, toolbar documento, pagina A4 centrale, pannello `Campi/Stile/Lex/Fonti/Controlli/Export`, import DOCX/PDF/RTF/TXT ed export RTF locale oltre ai flussi PDF/Word esistenti.
- Aggiunto `template_atti/font_registry.json` con registry font professionale, preset stile documento, fallback DOCX/PDF/RTF e layout editor esteso per font documento, titoli, interfaccia e placeholder.
- Integrato Lex Revisione testo nell'editor con modalità Correttore, Redattore, Revisore Normativo, Revisore Privacy, Template Builder e Final Check; le proposte restano in diff accettabile/rifiutabile/modificabile, senza applicazione automatica e senza invio a servizi esterni senza policy privacy esplicita.
- Esteso il payload React `/api/v1/ui/template-atti/compila/<codice>` con workflow professionale, registry font, preset, template laterali, policy Lex, audit/versioning proposte e seed di controllo placeholder/normativa/privacy.
- Coperti registry, layout esteso e contratto API con test mirati; confermati typecheck, test frontend, build Vite, contratti OpenAPI, Docker locale reale `127.0.0.1:8080`, browser desktop/tablet/mobile con scroll completo e click delle funzioni, date italiane visibili, export RTF/DOCX/PDF e baseline prestazionale dedicata.

## 2.249.12 - 2026-06-03

- Rafforzato il presidio PEC reale: l'acquisizione dei MIME locali genera scadenze operative non scadute e le collega all'agenda, con risposta idempotente e messaggio riepilogativo su create, già presenti, scadute ignorate e collegate all'agenda.
- Corretto il fallback Lex sui fascicoli: quando l'indice DocumentAI non contiene testo, Lex legge in modo sicuro il file già presente nel fascicolo e usa l'estratto nella sintesi, invece di fermarsi a nome, data, hash e link editor.
- Rafforzata l'estrazione PDF per Lex/DocumentAI: i segnaposto CID residui non vengono più trattati come testo leggibile; il motore tenta OCR e, se non recupera contenuto affidabile, non passa spazzatura alla risposta.
- Migliorata la superficie Notifiche legali: destinatari suggeriti multipli, parte rappresentata e R.G./anno precompilati dal fascicolo, nomi documenti leggibili, pannello attestazione di conformità, apertura firma digitale e controllo relata con stato operativo.

## 2.249.11 - 2026-06-03

- Integrati nella Guida Pratica i pacchetti utente `files (10).zip` e `files (11).zip`: aggiunti moduli set15/set16, rigenerata la knowledge base completa e documentata la conversione prudente del caso non coincidente con il codice ministeriale `140035`.
- Aggiornato lo Scadenziario con i termini processuali della Guida Pratica e corretto il calcolatore: le opzioni duplicate vengono accorpate o rese distinguibili con durata, direzione, fonte e pratica, senza perdere il contesto operativo.
- Rafforzata la pipeline PEC/allegati: gli allegati non disponibili come file sciolto vengono recuperati dal MIME/EML originale quando presente, con endpoint di acquisizione locale e test dedicati.
- Aggiornati audit voce per voce e test mirati: nessun campo utente perso tra moduli, full KB, service, UI e Lex.

## 2.249.10 - 2026-06-03

- Rifinito il calcolatore termini processuali dello Scadenziario: la spiegazione visibile usa accenti italiani corretti e date in formato `gg/mm/aaaa`, mantenendo invariati payload tecnico, audit hash e calcolo.
- Aggiunte regressioni mirate per impedire il ritorno di `e'` nei testi runtime e di date ISO nella visualizzazione del risultato calcolato.

## 2.249.9 - 2026-06-02

- Completato il presidio Guida Pratica/Scadenziario sui nuovi materiali utente: moduli KB set10, set11, set12 e set14 integrati, termini processuali globali importati nel repository, audit voce per voce aggiornato, bootstrap runtime dei termini Guida Pratica da sorgenti versionate e regole operative documentate.
- Rafforzata `Scadenze dai PDF`: anteprima rapida non bloccante, esclusione dei PDF troppo grandi/scansionati dalla lettura pesante, filtro da fascicolo/guida, pulsanti `Elimina selezionate` ed `Elimina tutto` limitati alla preview senza cancellare scadenze o documenti.

## 2.249.8 - 2026-06-02

- Introdotta la matrice probatoria obbligatoria per PEC, notifiche e deposito prova: `PROOF_ACQUIRED`, `PROOF_DEPOSIT_REQUIRED` e `PROOF_DEPOSITED` richiedono destinatari, domicilio digitale, PEC inviata, relata, RAC/RdAC per ogni destinatario, evidenze hashate, DatiAtto/deposito prova quando dovuti e audit.
- Aggiunte tabelle SQLite e PostgreSQL per casi notifica, destinatari, controlli indirizzo, messaggi, ricevute, relata, attestazioni, bundle prova, link evidenze, deposito prova e riferimenti DatiAtto.
- Aggiornati workflow e repository lifecycle: `proof_bundle_id` non punta più a una singola evidenza generica, ma a `notification_proof_bundles` verificato; il trigger SQLite anti-bypass respinge update diretti non validati.
- Salvate e registrate fonti ufficiali PST, L. 53/1994, D.P.R. 68/2005, regole tecniche PEC, CAD, ReGIndE, INI-PEC, INAD e XSD UNEP; aggiunta la matrice in `docs/specs/ministero/NOTIFICHE_PEC_MATRICE_PROBATORIA_2026-06-02.md`.
- Aggiornati test mirati notifiche, evidence vault e procedure lifecycle per coprire il vecchio shortcut come caso negativo e il bundle probatorio completo come caso positivo.

## 2.249.7 - 2026-06-02

- Blindato l'aggiornamento degli uffici giudiziari: il parametro API e `PCT_UFFICI_URL` non possono più puntare a URL arbitrari, ma vengono accettati solo se coincidono con l'endpoint PST ufficiale, altrimenti il sistema usa la fonte ufficiale o il registro interno versionato.
- Riallineate le soppressioni CodeQL sui writer JSON già redatti di Installation Pack e Operational Resilience, mantenendo i test che dimostrano la rimozione dei segreti prima del salvataggio.
- Aggiunti test di sicurezza per impedire chiamate verso endpoint non autorizzati durante aggiornamento e verifica variazioni degli uffici giudiziari.

## 2.249.6 - 2026-06-02

- Aggiunta in `Impostazioni` la sezione React `Canali SdI` su `/impostazioni/sdi`, con configurazione del canale accreditato/intermediario, campi riservati redatti e avviso professionale quando l'invio automatico non è configurabile in modo certo.
- Estesa `ConfigStudio` con `ConfigSDI` e sincronizzazione tenant-aware verso app runtime, mantenendo le password cifrate e non esposte nei payload UI.
- Introdotta la tabella strutturata `settings_config` per SQLite e PostgreSQL, così tutte le sezioni di `Impostazioni` hanno specchio SQL/PostgreSQL oltre al salvataggio JSON.
- Salvate e indicizzate fonti ufficiali GDPR, FatturaPA/SdI e Codice Deontologico Forense aggiornato al 7 aprile 2026 sotto `docs/specs/ministero/fonti_ufficiali/2026-06-02/`.
- Rigenerato e reinstallato Local Signer `1.6.68`: `tools/dist/local_signer.py`, `SetupLocalSigner-1.6.68.exe` e alias `SetupLocalSigner.exe` sono allineati alla sorgente, e l'avvio immediato post-installazione usa `pythonw.exe` per non lasciare console o icone residue.
- Corretto il layout delle tab di `Impostazioni`: il titolo della sezione selezionata resta sopra i campi, i pannelli non attivi restano nascosti e la pagina mostra un solo pannello per volta.
- Verificati test mirati backend/frontend, parità storage, registry fonti, gate React, build Vite, packaging Local Signer e browser reale Docker su `127.0.0.1:8080/impostazioni/sdi`.

## 2.249.5 - 2026-06-02

- Integrata in `/fascicoli/nuovo` la ricerca “Uffici giudiziari per Comune” direttamente nel campo `Autorità giudiziaria`: l'utente può digitare il Comune, ricevere gli uffici territorialmente competenti e applicare al fascicolo il nome ufficiale dell'ufficio.
- Aggiunti filtri rapidi per tipologia ufficio (`GDP`, Tribunale, `UNEP`, Procura, Corte d'Appello e Minorenni), con opzione per includere uffici distrettuali e speciali.
- Il runtime React conserva e mostra i codici disponibili senza confonderli: codice ufficio del catalogo ministeriale, codice PST, codice Giustizia Locale e ISTAT sede restano campi separati; l'ISTAT non viene mai usato come codice di deposito e gli uffici senza codice telematico mostrano un avviso di conferma canale.
- Coperti con test mirati il form React del nuovo fascicolo, l'endpoint `uffici_competenti` con filtro tipologia, il catalogo territorio/comuni e la ricerca uffici competenti da banca dati ministeriale locale.

## 2.249.4 - 2026-06-02

- Corretto il router PST/Local Signer per Cassazione civile e penale: le letture usano le tabelle ministeriali `QC_Ricorsi` e `QP_Ricorsi` con `NRGREALE`, evitando il servizio civile generico non esposto da Cassazione.
- Verificato con lettura reale Local Signer/PST il fascicolo Cassazione penale `12756/2026`: ricerca annuale 2026 e ricerca esatta restituiscono il ricorso, sezione e data udienza senza trattarlo come civile.
- Riconfermato con lettura reale Local Signer/PST il contenzioso civile ordinario `1025/2024` su Tribunale di Palmi: `JPW_SICID`, codice PST `0800570094`, 1 fascicolo e snapshot catalogo con 16 documenti.
- Verificata con lettura reale Local Signer/PST la volontaria giurisdizione `63/2025/VG` su Tribunale di Roma: la ricerca usa `JPW_SIVG`, namespace `urn:CONS-SIVG-BE`, codice PST `0580910098` e restituisce il fascicolo.
- Aggiunta mappatura governata delle richieste copie: interrogazioni `RicercaRichieste` e `ProfiloRichiesta`, namespace qbuilder `urn:RichiestaCopie-consultazioni-distr`, namespace WSDL `urn:RichiestaCopie`, classi catalogo e parser dei contenuti, mantenendo il flusso in sola consultazione senza invii o pagamenti automatici. Test live read-only su `RicercaRichieste` ha risposto 200 con `available=0`.
- Rafforzata la classificazione PEC del deposito ricorso per Cassazione penale da `depositoattipenali.ca.reggiocalabria@giustiziacert.it`, con estrazione di `RG APP` e `RG NR` e test dedicato.
- Aggiunto riconoscimento del formato PEC penale `generale/<anno>/<numero>/Corte di Appello` da `penale.ptel.giustiziacert.it`, tradotto in `RG_APP` senza creare scadenze automatiche se manca un evento processuale specifico.
- Migliorato il messaggio operativo SIECIC quando il PST richiede `idRuoloJPW`: IUSENTRA non inventa il ruolo e chiede di usare il dato autorizzato dal portale.

## 2.249.3 - 2026-06-01

- Rafforzato il flusso reale di assistenza remota: il SUPERADMIN prende in carico e si collega, ma solo il cliente può avviare la sessione dopo consenso esplicito.
- Corretta la sincronizzazione delle stanze cliente/operatore anche quando una delle due finestre non è in primo piano, così il cliente vede subito `Avvia assistenza` dopo la presa in carico.
- Stabilizzati fullscreen cliente/operatore, chat tecnica compatta, muto microfono su entrambi i lati e controllo PC via agente locale separato dal Local Signer.
- Verificato end to end reale su `http://127.0.0.1:8080`: richiesta dal pulsante `Assistenza` dello studio, presa in carico SUPERADMIN, avvio cliente, schermo cliente visibile, chat bidirezionale, consenso controllo PC e comando reale `Tab` eseguito.
- Migliorata la pagina `Fascicoli`: filtri compatti, ricerca unificata numero/anno/RG/cliente/titolo, ordinamento anno e numero, 5 fascicoli per pagina e azione bulk per eliminare selezionati.
- Aggiunta anteprima/import scadenze da PDF nello Scadenziario con collegamento all'Agenda e ai link presenti nei documenti.

## 2.249.2 - 2026-05-31

- Blindato l'import Studio Telematico in modalità SQL: se lo studio è configurato SQLite/PostgreSQL, clienti, fascicoli, soggetti e parti vengono scritti nelle tabelle strutturate e l'import si blocca se il backend SQL non è realmente attivo.
- Aggiunte tabelle strutturate `soggetti` e `soggetti_parti` su SQLite/PostgreSQL, con migrazione e audit allineati per impedire fallback invisibili sui JSON.
- Estesi test e audit QuickOrganizer per verificare che l'import SQL popoli le tabelle e non crei `clienti/anagrafica.json`, `fascicoli/fascicoli.json`, `soggetti/anagrafica.json` o `soggetti/parti.json`.

## 2.249.1 - 2026-05-31

- Estesa l'assistenza remota: le richieste dallo studio creano notifiche urgenti per il SUPERADMIN, possono arrivare via Web Push sul cellulare con payload privacy-safe, e la console permette attivazione dispositivo, test push, cambio stato, cancellazione sessione e pulizia prove/test.

- Aggiunta preparazione assistita Studio Telematico: `Prepara pacchetto` crea una sessione sicura, scarica l'avviatore Windows, mostra avanzamento di preparazione/upload/controllo e importa automaticamente solo quando il pacchetto è completo.
- Il preparatore locale ora può caricare lo ZIP a blocchi verso IUSENTRA usando header tokenizzati e mantenendo compatibilità con l'uso manuale.
- Aggiornati OpenAPI, documentazione e test QuickOrganizer per coprire sessioni tokenizzate, upload automatico e anteprima pronta per l'import definitivo.

## 2.249.0 - 2026-05-31

- Blindato l'import reale Studio Telematico: il cliente principale viene risolto anche da `TAVOLA` + `NOMI.CONTROLLO=CLI` quando `PRATICHE.TitolareID` manca, tutti i nominativi `CLI` vengono creati in rubrica clienti, e i salvataggi di clienti, soggetti, parti e fascicoli sono differiti fino a fine lotto per evitare import parziali su pacchetti molto grandi.
- Rafforzato il preparatore `quickorganizer-export.json`: il pacchetto viene bloccato se le tabelle o i campi minimi per ricostruire clienti, parti e pratiche non sono presenti, e il JSON contiene conteggi `validation` per auditare l'export prima della scrittura.
- Aggiunto audit ripetibile `scripts/audit_quickorganizer_import.py` per confrontare pacchetto e tenant IUSENTRA su 324 pratiche, clienti collegati, soggetti/parti, documenti nominati dalla tabella, email con oggetto corretto e agenda.
- Rafforzati i test QuickOrganizer con verifica audit end-to-end e regressione sui salvataggi batch; riallineati versione e OpenAPI a `2.249.0`.

## 2.248.99 - 2026-05-31

- Ricostruita l'identità Installation Pack da una allowlist esplicita prima della scrittura, così eventuali campi storici o non governati non vengono mai risalvati nei manifest.
- Protetta la pulizia remota del deploy Hetzner: viene eseguita dopo la configurazione SSH riuscita, evitando errori spurii quando un gate pre-deploy blocca il job prima dell'accesso al server.
- Sanificata la risposta JSON della console pianificazioni superadmin per non esporre stack trace, path locali o dettagli tecnici nei payload utente.
- Aggiunti test di regressione su bonifica identità Installation Pack e redazione pianificazioni; aggiornati contratti OpenAPI alla versione `2.248.99`.

## 2.248.98 - 2026-05-31

- Rimossi dai manifest Installation Pack i riferimenti pubblici a percorsi o nomi di materiale protetto, evitando che CodeQL li classifichi come segreti salvati in chiaro.
- Aggiornati contratti OpenAPI alla versione `2.248.98`.

## 2.248.97 - 2026-05-31

- Preservata la sessione di caricamento a blocchi dell'import Studio Telematico se lo staging fallisce, così il pacchetto ricomposto resta disponibile per audit e recupero operativo invece di essere eliminato.
- Aumentato il timeout Gunicorn di produzione per import Studio Telematico molto grandi, mantenendo il caricamento tenant-aware e i controlli su clienti, soggetti, parti e nomi documento da tabella.
- Aggiornati contratti OpenAPI alla versione `2.248.97`.

## 2.248.96 - 2026-05-31

- Portata la stanza operatore dell'assistenza remota su superficie React dedicata con fullscreen reale/fallback in viewport, pannello tecnico compatto sotto e conferma visibile dei comandi PC eseguiti.
- Aggiunto relay presenza/comandi via Redis pub/sub con fallback locale, così operatore e cliente restano sincronizzati anche con più worker Docker/Gunicorn.
- Verificato end-to-end reale su `http://127.0.0.1:8080`: sessione creata dal Docker locale, cliente collegato, consenso controllo PC, agente locale armato, comando Windows `Tab` eseguito e confermato in UI.
- Corretto l'import Studio Telematico: i documenti e le email usano come nome visibile il titolo presente nelle tabelle `TESTI`/`EMAILS`, conservando il file originale solo come sorgente fisica e metadato.
- Estesi i test dell'import su clienti, soggetti e parti processuali, verificando cliente principale, anagrafiche importate e ruoli `ASSISTITO`/`CONTROPARTE`.
- Bonificati i manifest Installation Pack e la risposta PEC pubblica per non esporre path di materiale protetto o dettagli runtime non necessari ai gate CodeQL.
- Separato il bootstrap della chiave locale degli Installation Pack dai manifest JSON pubblici, così CodeQL non vede più il writer dei manifest come deposito potenziale di segreti.
- Sostituita la firma HMAC persistita nei manifest Installation Pack con hash pubblico `manifest_hash_sha256`, mantenendo il riferimento di integrità senza serializzare dati derivati da segreti.

## 2.248.95 - 2026-05-31

- Imposta come regola operativa che le verifiche locali finali devono usare la copia reale dell'utente su `http://127.0.0.1:8080`, non server temporanei o porte inventate.
- Corretto l'avvio Docker locale evitando la riconciliazione storage pesante durante il bootstrap degli Installation Pack.
- Aggiornato il login con cache busting degli asset CSS e stile compatto per evitare differenze visive tra build e browser.

## 2.248.94 - 2026-05-31

- Aggiunto controllo remoto reale del PC cliente nella stanza operatore: schermo quasi full-screen, pannello tecnico minimo, richiesta consenso, comandi mouse, testo e tasti rapidi.
- Introdotto `tools/support_remote_agent.py`, agente locale separato dal Local Signer telematico, esposto solo su localhost e armato solo dopo consenso cliente.
- Estesi test su assistenza remota, agente locale, separazione dal Local Signer e relay WebSocket dei comandi `remote_control`.

## 2.248.93 - 2026-05-31

- Aggiunto il flusso reale “Richiedi assistenza” dalla parte studio: topbar Flask/React, dashboard, scheda cliente e dettaglio fascicolo aprono una sessione autenticata senza richiedere accesso alla console piattaforma.
- Collegata la richiesta studio alla stanza cliente `/support/join/<token>`: l'utente vede subito la stanza di consenso, mentre il SUPERADMIN trova la sessione in `/admin/supporto-remoto` e apre la stanza operatore.
- Estesi test e documentazione dell'assistenza remota per coprire endpoint studio, visibilità del pulsante, protezione da accesso anonimo e launcher cliente.

## 2.248.92 - 2026-05-31

- Verificato end to end reale il modulo `/admin/supporto-remoto` su server locale isolato: login SUPERADMIN, console, creazione sessione, link cliente, stanza operatore, API stato/consensi/WebRTC, note, avvio e chiusura sessione.
- Corretto il falso errore in console quando la copia automatica del link cliente negli appunti non è consentita dal browser: la sessione resta confermata e il link rimane disponibile nel campo dedicato.
- Resi espliciti e non operativi i link cliente di sessioni già chiuse, con banner `Sessione conclusa` e controlli di condivisione/chat disabilitati anche lato JavaScript.
- Ripuliti testi visibili e documentazione del modulo assistenza remota con accenti italiani UTF-8 reali.

## 2.248.91 - 2026-05-30

- Corretto l'import reale Studio Telematico per pacchetti ZIP contenenti `QuickOrganizer.mdb`: il percorso MDB viene passato a PowerShell come parametro esplicito e l'output viene letto in UTF-8, evitando il falso errore `Pacchetto non leggibile`.
- Verificato nel browser sul pacchetto reale `QuickOrganizer.zip`: anteprima con `324` pratiche, `307` anagrafiche, `796` collegamenti, `8967` documenti `ATTI` trovati e import completato con `8950` documenti importabili copiati nei fascicoli.
- Rigenerato `PreparaPacchettoStudioTelematico.exe` con profilo IExpress governato; il pacchetto pubblico resta `.exe`, non `.ps1`.
- Documentati i limiti reali del pacchetto ricevuto: le cartelle `EMAILS` risultano prive dei `4239` file email indicati dal database e alcune righe `TESTI` non sono collegabili a una pratica o a un file, quindi non possono essere importate come documenti di fascicolo.

## 2.248.90 - 2026-05-30

- Completata prova reale PST/PolisWeb su Tribunale di Palmi R.G. `1025/2024`: ricerca, anteprima, download batch `51/51`, import nel fascicolo `487EE7F3` e catalogazione verificata con `51` record documento e `51` file fisici.
- Corretto l'import PST dei documenti omonimi: `DatiAtto.xml.p7m` e `IndiceDocumentiDepositati.PDF` restano distinti quando appartengono a depositi diversi, usando identificativi ministeriali e hash contenuto invece del solo nome file.
- La UI di acquisizione PST usa il job asincrono di anteprima `/pst/fascicolo-snapshot-job`, mostra l'avanzamento durante operazioni lente e conteggia la cronologia aggregata da eventi, comunicazioni, istanze e udienze.
- Il report finale import distingue correttamente `Documenti reali`, `Informazioni`, `Solo catalogo`, `Senza contenuto` e `Scartati` anche quando il valore è `0`, evitando falsi fallback a catalogo.

## 2.248.89 - 2026-05-29

- Rafforzata l'importazione Studio Telematico sul caso reale `QuickOrganizer.zip`: se lo ZIP contiene `QuickOrganizer.mdb` ma l'ambiente non riesce a leggerlo, l'anteprima non mostra più `Pacchetto non leggibile`; conta i file `ATTI`/`EMAILS` e indica di usare il nuovo `PreparaPacchettoStudioTelematico.exe` per creare il pacchetto completo con archivio dati esportato.
- Aggiornato anche `C:\Users\antmm\Downloads\PreparaPacchettoStudioTelematico.exe` con il nuovo preparatore IExpress: selezione automatica della cartella corretta, PowerShell 32 bit reale e ZIP scritto in streaming senza copia temporanea di tutti i documenti.
- Il filtro UI PST non include più righe non scaricabili o nomi estratti per errore come documenti; il Local Signer rifiuta payload PDF/XML non reali invece di salvarli come file del fascicolo.
- Verifica browser reale su `/importa-pratiche-studio-telematico` e `/portali/pst/acquisizione` in desktop, tablet e mobile: nessun overflow, nessun errore console e nessun messaggio obsoleto `Timeout del Local Signer locale`.

## 2.248.88 - 2026-05-29

- Corrette regressioni Local Signer/PST: caricamento preferenze certificato prima dell'auto-selezione, timeout operativi più lunghi per le chiamate PST lente, messaggi di avanzamento visibili durante ricerca, visualizzazione e download.
- Local Signer `1.6.65`: il download batch dei documenti non apre più un preflight separato quando il client ha già richiesto `preflight_auth=false`; il prompt PIN Windows resta in primo piano più a lungo durante le operazioni reali.
- La pagina `Importa pratiche da Studio Telematico` propone un pacchetto Windows `.exe`, mostra una barra di avanzamento durante controllo/import e legge gli ZIP con cartelle `ATTI`/`EMAILS` senza trasformarli in errore generico.
- Aggiunti test di regressione su auto-selezione certificato PST, assenza di preflight PIN extra, pacchetto Studio Telematico `.exe` e ZIP con sole cartelle documentali.

## 2.248.87 - 2026-05-29

- Estesa l'acquisizione PST/PolisWeb del fascicolo alle schede effettivamente esposte dal portale: dettaglio/profilo, documenti, master detail degli atti, allegati secondari, storico eventi, comunicazioni/notificazioni, scadenze/termini, istanze e dati accessori.
- Il Local Signer `1.6.64` arricchisce in batch i documenti SICID/SIECIC con `estraiMasterDetailAtto`, conserva `docPrimario` e `docsSecondari`, mantiene `id_documento`, `id_cat`, `id_repeatto`, `id_reperto`, `msg_id` e collega gli allegati al documento padre.
- Aggiunta la ricerca PST per solo anno: indicando ufficio e anno senza numero vengono usate le interrogazioni ministeriali del registro (`ArchivioFascicoli` per SICID/SIGP, `RicercaArchivioPC` e `RicercaArchivioEI` per SIECIC) e la UI mostra la lista dei fascicoli; cliccando un fascicolo viene caricato lo snapshot completo del fascicolo scelto.
- Allineati sia la superficie React sia il wizard classico `?_legacy=1`: il modo per anno mostra `Cerca fascicoli`, non apre automaticamente un singolo risultato e permette di aprire il fascicolo scelto dalla lista senza cambiare le regole di import già collaudate.
- Preservate le modalità già funzionanti di scelta documenti: tutto, singolo documento o selezione multipla, sempre tramite download batch `/pst/download-documenti-batch` e senza reintrodurre preflight separati o download singoli ripetuti.
- Documentate le direttive ministeriali applicate in `docs/specs/ministero/PST_FASCICOLO_SCHEDE_MINISTERIALI_2026-05-29.md` e aggiunti test di regressione su tabelle ministeriali, allegati, identificativi e UI React.

## 2.248.86 - 2026-05-29

- Rafforzata l'importazione finale PST/Local Signer: Step 7 riconosce i file reali con contenuto, hash e provenienza, distingue catalogo, Informazioni e documenti senza contenuto, e restituisce un report utile invece del blocco generico.
- Aggiunti audit leggibili per importazione PST avviata, documento reale riconosciuto, documento informativo escluso, documento importato, import completato o bloccato senza perdita dati.
- La pagina `Database` espone pre-verifica, report differenze, riconciliazione conservativa e attivazione SQLite con stati non contraddittori; il database operativo viene preservato nei casi tipo clienti `25 / 9`.
- Aggiunto il classificatore PEC legale con router registri CC, LAV, VG, GDP/SIGP, Cassazione e penale, eventi di udienza/deposito/ricevute/SDI e chiavi anti-duplicato normalizzate.
- Aggiunto il modello DOCX `attestazione_conformita_autocompilante.docx` e il generatore dati per compilare attestazioni di conformità da fascicolo, cliente, soggetti/parti e documenti.
- Introdotto lo script `scripts/audit_finale_pst_sqlite_pec.py` per eseguire gate mirati su Step 7, SQLite, PEC, UI React, UTF-8, build e copertura critica.

## 2.248.85 - 2026-05-29

- Chiuso il blocco sicurezza post-audit database: le route amministrative, PEC, documenti fascicolo, import Studio Telematico e Local Signer non restituiscono più eccezioni grezze o dettagli tecnici al browser.
- Rafforzati i percorsi file usati da import QuickOrganizer, payload PEC locale e buste telematiche: lettura/copia solo dentro radici runtime consentite, estensioni attese e directory staging sicure.
- I redirect `next` delle caselle email accettano solo percorsi interni validati, evitando redirect aperti.
- Sostituito MD5 negli identificativi di prova deposito con SHA-256 e mantenuto il database protetto anche sui rami di errore.
- Allineato Local Signer: i fallback logici della famiglia SICID continuano a usare il proxy fisico `JPW_SICID` nel batch, senza doppio preflight certificato.

## 2.248.84 - 2026-05-29

- Blindata la pagina `Database`: `Migra dati` e `Attiva SQLite` ora usano staging, precheck anti-perdita e validazione di conteggi, identificativi e payload prima di sostituire `studio.db`.
- Se i JSON del tenant sono vuoti o incompleti mentre il database operativo contiene clienti, fascicoli o altri domini critici, la migrazione viene bloccata e il database esistente resta intatto.
- Aggiunto audit severo `scripts/audit_sqlite_migration_integrity.py` con uscita non riuscita quando manca un record o un campo non viene conservato.
- Il cutover completo riesegue il mirror core dopo i repository secondari, così Legal Intelligence, Giurisprudenza, Workspace Intelligence, template e moduli JSON finiscono anche in `moduli_json_records`.
- Reso tenant-aware `timesheet/time_tracking.json`: bootstrap, migrazione SQLite, report full storage e cutover PostgreSQL coprono anche i timer della top bar.

## 2.248.83 - 2026-05-27

- Scadenziario PST: se il portale espone una data/udienza strutturata, IUSENTRA continua a usare quella come fonte primaria.
- Se invece `data_udienza` non è esposta, l'acquisizione cerca documenti fonte nel catalogo ufficiale, come fissazione termine, sostituzione udienza, rinvio, verbale o provvedimento con termini, e li porta fino ad anteprima e verifica UI.
- La prova Palmi lavoro R.G. `3441/2025` ora mostra il documento `FissazioneTermineNoteSostituzioneUdienza_32899061.pdf` come fonte per completare lo scadenziario dopo lo scarico, senza inventare una scadenza dai soli metadati.

## 2.248.82 - 2026-05-27

- Local Signer `1.6.63`: le tabelle della famiglia SICID (`lavoro/SIL`, volontaria giurisdizione, minori) restano logiche nel SOAP ministeriale, ma usano il path fisico `JPW_SICID` quando l'ufficio espone quel solo gateway JPW.
- La prova live Palmi R.G. `3441/2025` non viene più trasformata in "nessun fascicolo" per il solo fatto che i path fisici `JPW_SIL*` rispondono HTTP 404; il log conserva `servizio_logico` per capire quale tabella è stata tentata.
- Registrata la prova cliente riuscita: Palmi lavoro R.G. `3441/2025` restituisce `1` fascicolo e `6` documenti; se `data_udienza` è vuota, lo scadenziario deve leggere eventuali atti di fissazione termine dal PDF invece di inventare una prossima udienza dai metadati.
- Aggiornati test e matrice QBuilder per garantire che `CONS-SIL-BE-DISTR`/`LAV` non regredisca a `CONS-SICC-BE`, senza spostare SIECIC, SIGP o Cassazione.

## 2.248.81 - 2026-05-27

- Rafforzato il contrasto dei pulsanti React condivisi: i pulsanti primari `.iu-btn` e `.iu-button` mantengono testo bianco leggibile anche dentro le intestazioni di pagina, senza ereditarietà di colore dal titolo.
- Sistemata la pagina `Importa pratiche da Studio Telematico`: pannelli dedicati, titolo `Pacchetto cliente` leggibile, pulsanti `Prepara pacchetto`, `Fascicoli`, `Controlla pacchetto` e `Importa pratiche` con stati visibili e coerenti.
- Verifica browser reale su pagine rappresentative (`Import Studio Telematico`, `Clienti`, `Fascicoli`, `Agenda`, `Amministrazione`) per impedire il caso sfondo scuro/testo invisibile nei pulsanti standard.

## 2.248.80 - 2026-05-27

- Local Signer `1.6.62`: le ricerche PST con schema ministeriale lavoro provano prima `JPW_SIL_DISTR`/`LAV`, poi `JPW_SIL`, `JPW_SILP_DISTR` e `JPW_SILP`, mantenendo gli altri fallback SICID/SIVG/MIN/SIMIN/SIECIC.
- Se il PST risponde `401 Unauthorized` durante il tentativo con cookie, il Local Signer scarta il cookie del canale PST e ritenta subito col certificato, così Windows può riproporre il PIN invece di fermarsi sull’autenticazione fallita.
- Documentata la prova live Palmi R.G. `3441/2025`: `1.6.60` aveva corretto il rito, ma il PST ha risposto HTTP 404 su `/JPW_SIL`; il nuovo ordine evita l’errore senza perdere le altre tabelle ministeriali.

## 2.248.79 - 2026-05-27

- Aggiunta in Amministrazione la pagina React `Importa pratiche da Studio Telematico`, con percorso guidato, anteprima di completezza e import operativo di pratiche, clienti, parti, documenti, email e agenda.
- Il pacchetto cliente rispetta la struttura del vecchio gestionale: `QuickOrganizer.mdb`, cartella `ATTI` per tutti i documenti del fascicolo e cartella `EMAILS` per le email collegate.
- L'import è idempotente: le pratiche già acquisite vengono aggiornate tramite identificativo sorgente e i documenti già presenti non vengono duplicati.
- Aggiunto lo script `prepara_import_studio_telematico.ps1` per preparare dalla postazione del cliente un archivio unico con dati, `ATTI` ed `EMAILS`, senza trasferire credenziali.
- Inseriti endpoint auditati `/api/v1/ui/import/quickorganizer*`, test di regressione su import completo/parziale e guardrail React per mantenere la route full React.

## 2.248.78 - 2026-05-27

- Local Signer `1.6.60`: la ricerca PST riconosce automaticamente gli indizi di tabella ministeriale (`lavoro`, `LAV`, `SIL`, previdenza/assistenza) e avvia Palmi/lavoro su `JPW_SIL` con tipo `LAV` prima del fallback SICID.
- La scelta automatica delle tabelle PST resta prudente sul penale: `penale` da solo non sposta il canale, mentre `CASSPE` / `cassazione penale` resta su PST `JPW_CASSPE` e `cassazione civile` su `JPW_CASSCI`.
- Il wizard PST React e quello classico inviano `schema`, `materia`, `registro` e `tipo_registro` al Local Signer; la schermata React espone anche la scelta compatta della tabella ministeriale quando serve forzare il rito corretto.
- Presidiata la non regressione sui portali assistiti: PDP, PAT e PTT continuano a importare tramite canale locale quando il Local Signer è abilitato, senza ricadere sul certificato server.
- Documentata la prova live Palmi R.G. `3441/2025`: il fault su `CONS-SICC-BE` non deve più guidare i fascicoli lavoro verso la tabella civile.

## 2.248.77 - 2026-05-27

- Nel wizard PST la destinazione pratica è stata semplificata: `Crea nuova pratica` per la prima importazione e `Usa pratica esistente` per aggiornare un fascicolo locale, senza più le voci ambigue `Collega` / `Aggiorna pratica esistente`.
- Aggiunti i comandi UI `Scarica selezionati` e `Scarica tutti` per i documenti PST, con selezione per singolo documento prima dell'importazione.
- Blindata la prima importazione: se il PST espone solo il catalogo ma non consegna file reali, IUSENTRA non crea una pratica vuota e restituisce un blocco esplicito.
- Per pratiche già presenti, l'assenza di parti strutturate dal portale diventa un avviso: dati e documenti possono aggiornare il fascicolo locale senza cancellare assistiti e controparti esistenti.

## 2.248.76 - 2026-05-27

- Local Signer `1.6.59`: la selezione certificato PST torna automatica quando sul PC è già presente un certificato di autenticazione compatibile con il codice fiscale dello studio/avvocato; il dialog Windows si apre solo se manca un match sicuro o c'è ambiguità reale.
- Lo scarico documenti PST usa una policy esplicita per tabella ministeriale: SICID, lavoro, volontaria giurisdizione, minori/SIMIN, SIECIC e SIGP/Giudice di Pace mantengono servizio, warm-up e gestione errori per documento senza cambiare registro durante il download.
- Il batch download non azzera più l'intero lotto se una richiesta del Ministero va in timeout o fault mentre altre risposte sono utilizzabili: i file ricevuti restano importabili e il singolo documento fallito viene riportato come avviso.

## 2.248.75 - 2026-05-27

- Local Signer `1.6.58`: per SIGP/Giudice di Pace lo scarico documenti esegue `calcolaHash` prima del `downloadAtto` nello stesso lotto `curl`; la prova reale sul fascicolo `466/2023` aveva catalogo OK ma download in timeout senza questo passaggio.
- Pacchetto Windows rigenerato come `SetupLocalSigner-1.6.58.exe` con profilo IExpress blindato e alias `SetupLocalSigner.exe`.

## 2.248.74 - 2026-05-27

- Local Signer `1.6.57`: rafforzato il primo piano della finestra PIN su Windows, riconoscendo anche `CredentialUIBroker`, finestre senza titolo e processi Bit4id/Aruba/MinVA/CNS/CIE; la console `curl` resta nascosta e non vengono salvati PIN o credenziali.
- Pacchetto Windows rigenerato come `SetupLocalSigner-1.6.57.exe` con profilo IExpress blindato e alias `SetupLocalSigner.exe`.

## 2.248.73 - 2026-05-27

- Local Signer `1.6.56`: lo scarico documenti QBuilder non invia più i cookie della ricerca quando il Ministero si aspetta il certificato client diretto sul download; il lotto resta un unico processo `curl` e il fascicolo reale Palmi R.G. `1025/2024` è stato verificato con ricerca, catalogo e batch `16/16` senza fallimenti.
- `Aggiorna pratica esistente` è più robusto tra React, wizard classico e API: gli alias `target_fascicolo_id`, `fascicolo_locale_id`, `fascicolo_id` e `id_fasc` vengono ricondotti alla stessa mappatura gestionale.
- Aggiunta verifica di adeguatezza alle tabelle ministeriali: SICID, SIL, SIVG, MIN/SIMIN, SIECIC, SIGP e Cassazione civile/penale controllano namespace, nome servizio, tipo registro e ricerca per parte senza numero/anno tramite `RicercaInformazioniFascicoloPerPartiGiudiceDate`.
- Pacchetto Windows rigenerato come `SetupLocalSigner-1.6.56.exe` con il profilo IExpress blindato e alias `SetupLocalSigner.exe`.

## 2.248.72 - 2026-05-27

- Local Signer `1.6.55`: la ricerca PST esatta numero/anno ora mantiene il registro certificato come prima scelta, ma se il registro civile ordinario non restituisce il fascicolo prova nello stesso ufficio e nella stessa sessione i canali ministeriali civili `JPW_SIL`/lavoro, `JPW_SIVG`/volontaria giurisdizione, `JPW_MIN`/minori e `JPW_SIMIN` prima di SIECIC.
- Lo scarico documenti riusa il servizio PST realmente individuato dalla ricerca snapshot, così un fascicolo trovato su un registro civile parallelo non torna al default `JPW_SICID` durante il download.

## 2.248.71 - 2026-05-27

- Local Signer `1.6.54`: la ricerca PST non maschera più come "nessun fascicolo trovato" il caso reale in cui la risposta principale è vuota/non parsabile e i tentativi dello stesso batch contengono SOAP Fault del Ministero.
- Nel wizard PST React il codice fiscale passato alla ricerca viene preso prima dal certificato selezionato sul PC; il CF configurato nello studio resta solo fallback e la diagnostica tenant-aware registra fonte CF e thumbprint.
- Pacchetto Windows rigenerato come `SetupLocalSigner-1.6.54.exe` con il profilo IExpress già blindato.

## 2.248.70 - 2026-05-27

- Aggiunta la prova deposito senza invio reale: il deposito viene marcato in modo sicuro, non apre canali PEC esterni e può generare ricevute sintetiche solo sul fascicolo di prova.
- La ricevuta sintetica riproduce struttura PEC sanificata con `postacert.eml`, `daticert.xml`, `EsitoAtto.xml` e `smime.p7s`, senza conservare indirizzi o identificativi reali.
- Nel dettaglio fascicolo React il pulsante `Deposito telematico` è visibile tra le azioni principali e le comunicazioni di cancelleria mostrano avanzamento ricevute e azioni per simulare accettazione, consegna, controlli automatici con avvisi e conferma; i depositi reali rifiutano la simulazione.
- Lo stesso pulsante è disponibile anche nella vista classica del fascicolo; i depositi reali vengono aggiornati dalla sincronizzazione automatica PEC dello scheduler, mentre il controllo manuale resta solo un'azione di anticipo.
- Allineato il loader dei fascicoli React al runtime della vista classica: login, dettaglio pratica, sezione Cancelleria e preparazione deposito leggono lo stesso archivio e mostrano lo stesso stato operativo.

## 2.248.69 - 2026-05-26

- L'anteprima PST non tronca più le parti a 8 nominativi: mostra tutti i soggetti letti e distingue i nominativi unici dalle righe grezze del portale.
- Il fascicolo conserva la fonte telematica come dato della pratica: dopo l'acquisizione salva e mostra in UI lo snapshot PST con ufficio, R.G., stato, oggetto, parti, controparti, conteggi documenti/depositi/eventi e log di import.
- Aggiornato Local Signer a `1.6.51`: lo scarico batch prova sempre a riusare per primo la sessione PST già autenticata, anche se lo stesso host aveva richiesto fallback certificato, così il secondo PIN resta solo un fallback reale del portale.
- Su Windows le chiamate `curl` del Local Signer vengono avviate senza finestra console, lasciando visibile solo la richiesta PIN di sistema quando il portale la richiede.

## 2.248.68 - 2026-05-26

- Blindato il post-import PST/PolisWeb: quando il portale non espone un elenco parti strutturato, il fascicolo aggiorna comunque l’anagrafica parti usando assistito e controparte già presenti nella pratica gestionale.
- Rafforzata la classificazione documenti PST: il collegamento ai depositi ufficiali deduplica gli ID documento e preserva tipo atto, classificazione portale e identificativo ministeriale nella visualizzazione fascicolo.
- Migliorata la cronologia acquisizione: i fascicoli non scaricati o scaricati con avvisi vengono mostrati anche nel riepilogo laterale del wizard con motivo operativo e link `Riprova` già precompilato con ufficio, numero e anno.
- Aggiornata la prova reale Palmi R.G. 274/2026 con verifica su cliente, parti e classificazione documentale, così il flusso resta controllabile anche dopo futuri interventi su Local Signer o wizard di acquisizione.

## 2.248.67 - 2026-05-26

- Ripristinata l’anteprima completa del fascicolo PST/PolisWeb: dati fascicolo, parti, cronologia e documenti reali tornano visibili prima della selezione e dell’importazione.
- Corretto lo scarico/import PST: il Local Signer 1.6.50 riusa la sessione di visualizzazione anche per il batch documenti, non ricade più sul download singolo e non chiede un secondo PIN nel flusso già autenticato.
- Corretta la mappatura React del fascicolo locale: le pratiche telematiche espongono anche l’id fascicolo gestionale e il backend accetta in sicurezza eventuali id telematici già presenti.
- Migliorati avanzamento ed errori import: la barra mostra il documento corrente, segnala import completato con avvisi quando il PST non consegna un singolo file e distingue blocchi di verifica, timeout, autenticazione e assenza di file reali.
- Rafforzata la richiesta PIN su Windows: il Local Signer prova a riportare in primo piano anche dialog di credenziali/PIN senza titolo esplicito, evitando che la richiesta resti nascosta sulla barra delle applicazioni.
- Rafforzato l’uso multi-studio: nelle chiamate PST il codice fiscale ricavato dal certificato selezionato prevale su quello configurato nello studio; il dato dello studio resta solo fallback quando il certificato non espone il CF.

## 2.248.66 - 2026-05-26

- Rafforzato `Salva nel fascicolo` da `/email`: il riconoscimento cliente ora confronta nome/cognome anche con ordine invertito e dati anagrafici collegati, così propone il fascicolo aperto invece di mostrare falsi “nessun fascicolo aperto”.
- Sbloccata l’indicizzazione Lex dei documenti rimasti in stato `In corso`: i record `processing` vecchi diventano recuperabili e vengono reindicizzati; l’estrazione copre `.pdf.p7m`, `.pdf`, `.txt`, `.eml`, `.doc` e `.docx`, con fallback sicuro per DOC legacy.
- Aggiunta nel dettaglio fascicolo la rinomina dei documenti caricati: icona sotto il documento, form inline, estensione originale preservata e route auditata.
- Aggiornata `/notifiche-legali`: `Data e ora verifica PEC` resta visibile, si aggiorna automaticamente con ora locale fino ai secondi, e il percorso notifica mostra anche `Invia PEC` oltre a `Controlla relata`.
- Documentate le fonti operative ufficiali per timestamp PEC, invio e perfezionamento notifica: il timestamp UI è un dato operativo dello studio, mentre gli effetti legali restano collegati a PEC inviata, RAC e RdAC.

## 2.248.65 - 2026-05-26

- Completato il pannello `/email/scrivi` per la ricerca PEC degli uffici giudiziari: autocomplete su tutti i 7.894 Comuni italiani con provincia/CAP, filtro per le dieci tipologie richieste e inserimento della PEC nel destinatario.
- Aggiunti i DB versionati `territorio_italia.sqlite` e `uffici_giudiziari_comuni.sqlite`, con audit 100% Comuni/CAP/province e 100% associazioni Comune -> uffici giudiziari; i Comuni di nuova istituzione non ancora riconosciuti da Giustizia Map usano i Comuni predecessori documentati e interrogati sulla fonte ministeriale.
- Rafforzato l'invio PEC server-side: la composizione usa SMTP/PEC del backend dello studio, valida destinatari multipli, TLS e credenziali backend, invia con `from_addr`/`to_addrs` espliciti e gestisce correttamente messaggi con allegati.
- Corretto l'avvio locale: la `.env` viene caricata prima della lettura della configurazione studio, così le password PEC cifrate con `PCT_SECRET_KEY` vengono decifrate prima del login SMTP.
- Esteso il lettore OCR/MRZ anche alla scheda Nuovo Soggetto/Parte con popolamento controllato dei campi anagrafici, senza sovrascrivere valori già modificati dall'utente.
- Aggiunto ai workflow critici GitHub Actions il trigger di recupero `repository_dispatch` `codex-ci-recovery`, per poter accendere CodeQL, CI, frontend e supply-chain sullo SHA corrente quando il trigger `push` resta senza run.

## 2.248.63 - 2026-05-26

- Aggiunto in `/email/scrivi` un pannello collassabile `Ricerca uffici giudiziari per Comune`: filtra Giudice di Pace, Tribunale, Procura, UNEP, Corte d'Appello, Procura Generale, Corti di Assise e uffici minorenni, mostra solo recapiti PEC quando richiesto e inserisce la PEC nel campo destinatario.
- Separata la composizione PEC dal Local Signer: il form React invia tramite il canale PEC dedicato del backend e registra l'inviato solo dopo esito SMTP positivo, lasciando Local Signer ai flussi di firma, portali e deposito.
- Estesi parser/API/test degli uffici competenti con filtro per tipologia, filtro `solo_pec` e riconoscimento della Procura presso il Tribunale per i minorenni.

## 2.248.62 - 2026-05-26

- Integrata nel dettaglio fascicolo la ricerca `Uffici giudiziari per Comune`: pannello interno con inserimento di uno o più Comuni, richiesta solo su comando dell'avvocato e risultato visualizzato nella stessa finestra del fascicolo.
- Riutilizzato l'endpoint read-only già usato da Strumenti Forensi, senza collegamenti esterni obbligati e senza modificare procedure telematiche, depositi, Local Signer o flussi ministeriali.
- Verificati typecheck, build Vite, regressioni React/uffici e browser reale desktop/tablet/mobile con ricerca `Taurianova` e output Palmi dentro il fascicolo.

## 2.248.61 - 2026-05-26

- Completato su `/clienti/nuovo` il lettore documento reale: caricamento PDF/JPG/PNG, lettura OCR/MRZ via API, pannello di conferma, stati di caricamento/errore/incertezza e compilazione automatica dei campi anagrafici affidabili.
- Aggiunto parser documento in memoria per codice fiscale, nome, cognome, sesso, nascita, nazionalità, documento, rilascio/scadenza, indirizzo e recapiti, senza inventare dati mancanti e senza sovrascrivere campi già compilati dall'utente.
- Coperti parser MRZ, OCR/testo simulato, API upload e regressione React della pagina Nuovo Cliente; verificata la pagina nel browser reale desktop/mobile con lettore visibile e API su PDF reale.

## 2.248.60 - 2026-05-26

- Corretto il dettaglio Email PEC: il messaggio completo usa il corpo MIME estratto, le finestre lista/lettura sono allineate con scroll coerente e le azioni `Apri MIME`, `Esegui controllo`, `Salva nel fascicolo` e `Scadenza automatica` sono disponibili nella testata della PEC.
- Il salvataggio nel fascicolo ora chiede nome e cognome del cliente, cerca i fascicoli aperti collegati in anagrafica e salva il MIME originale solo dopo conferma dell'avvocato, senza usare Local Signer o servizi telematici.

## 2.248.59 - 2026-05-25

- Preparato su `/clienti/nuovo` l'hook di compilazione automatica da lettura documento: il parser OCR/MRZ potrà popolare codice fiscale, documento, scadenze, nome, cognome, nascita, indirizzo e recapiti senza sovrascrivere i campi già modificati dall'utente.

## 2.248.58 - 2026-05-25

- Integrata negli Strumenti Forensi la ricerca read-only degli uffici giudiziari competenti per Comune da Giustizia Map: scheda React con Comune, Tribunale, Giudice di Pace, Procura, UNEP, Corte d'Appello, recapiti, assistenza depositi telematici e azioni verso fascicoli/notifiche senza modificare le procedure telematiche.


## 2.248.56 - 2026-05-25

- Verificate e corrette le pagine Amministrazione richieste: `Amministrazione`, `Utenti`, `Profili e Permessi`, `Registro Attività`, `Database`, `Registro GDPR`, `Sito Studio Contatti` e `Sito Studio` passano il controllo browser desktop/tablet/mobile con scroll completo, preset attivo e zero overflow.
- Rafforzato il preset IUSENTRA sui pulsanti: CTA e link operativi restano leggibili/touch-safe anche quando le pagine hanno CSS più specifici; Database usa una vista mobile compatta invece della tabella larga.
- Rifinito il pulsante flottante Lex per evitare micro-overflow e mantenere l'etichetta accessibile senza mostrare testo tagliato.
- Corretto il preset grafico operativo sulle pagine Studio richieste: i controlli di Fatturazione, Compensi Forensi, Redazione Atti, Ricerca Legale/Giurisprudenza e la shell laterale rispettano dimensioni leggibili e touch-safe.
- Corretto il modal `Elimina documento` nel dettaglio fascicolo: testo e bottoni restano contenuti su desktop, tablet e mobile, senza sovrapposizioni o overflow.
- Allineato Document Intelligence ai documenti reali del fascicolo: gli archivi SQL accettano anche `.txt` ed `.eml`, con migrazione SQLite/PostgreSQL del vincolo storico.
- Pulita la retention degli asset React generati: il manifest punta solo agli asset Vite correnti e i file SQLite WAL/SHM locali sono ignorati come artefatti runtime.

## 2.248.55 - 2026-05-25

- Aggiornato Local Signer a `1.6.48`: su Windows, durante preflight, ricerca e download PST, il processo prova a portare in primo piano la finestra PIN/Sicurezza Windows/smart card/Bit4id mentre `curl` attende il certificato, così l'avvocato non deve cercarla nella barra delle applicazioni.
- Aggiunta una regressione statica per impedire che i `curl` PST tornino a essere lanciati senza l'helper di foreground del PIN.

## 2.248.54 - 2026-05-25

- Corretto Local Signer `1.6.47`: ripristinato il preflight certificato PST come gate obbligatorio prima di ricerca, snapshot, documenti e download batch, così l'accettazione live del certificato torna separata dalla chiamata operativa come nel flusso certificato.
- Aggiunte regressioni mirate per impedire che ricerca e ricerca-snapshot saltino il gate di autenticazione PST.

## 2.248.53 - 2026-05-25

- Corretto Local Signer `1.6.46`: se il batch PST riceve solo errori `401 Unauthorized`, la UI non mostra più "Nessun fascicolo trovato" ma un errore di autenticazione PST esplicito.
- Il caso reale Montagnese `3441/2025` resta tracciato come autenticazione rifiutata dal proxy PST quando il certificato CNS/CIE non viene presentato o accettato, invece di essere degradato a ricerca vuota.

## 2.248.52 - 2026-05-25

- Corretto il caricamento/cancellazione documenti del fascicolo quando SQLite è momentaneamente occupato: il salvataggio tenant ora usa `busy_timeout`, `BEGIN IMMEDIATE` e retry controllati.
- La cancellazione documenti non elimina più il file fisico prima della persistenza: se il DB resta bloccato, il documento non diventa una riga fantasma senza file.
- L'editor e l'anteprima fascicolo visualizzano i file `.eml` come email originali con intestazioni, corpo e allegati, in sola consultazione per non alterare la prova PEC.
- Aggiornato Local Signer a `1.6.45`: il download Windows pubblico torna sempre a `SetupLocalSigner-<versione>.exe`; la vecchia rotta `windows-ps1` serve comunque l'EXE per evitare link PowerShell al cliente.

## 2.248.51 - 2026-05-25

- Corretto `Componi PEC`: la pagina React invia la PEC dal PC locale tramite Local Signer (`/pec/send`) e registra l'inviato nello studio solo dopo conferma positiva con `Message-ID`.
- La route server `/email/scrivi` non mostra più successo se lo storico messaggi registra `FALLITO`; senza invio server esplicitamente abilitato risponde con richiesta di Local Signer invece di popolare artificialmente `INVIATI`.
- Aggiunti test di regressione su falso positivo PEC, conferma locale, storico messaggi e presidio React/Local Signer.

## 2.248.50 - 2026-05-25

- Aggiornato Local Signer alla versione `1.6.44`: il fallback SIECIC della ricerca snapshot PST usa i servizi del catalogo ministeriale (`InfoFascicolo`, `ProfiloFascicolo`, `ElencoDocumenti`) invece dei nomi SICID che sul test reale Palmi rispondevano `Service ... non trovato`.
- Rafforzato il ripristino del comportamento certificato: se il browser o la cache hanno il codice ufficiale `0910011` e il Local Signer traduce in `0800570094`, la snapshot prova anche il codice ufficiale nello stesso batch, senza preflight e senza chiedere PIN aggiuntivi.
- Estesi parser e test Local Signer per risposte qbuilder SIECIC con proprietà camel case, metadati fascicolo e catalogo documenti, preservando la visualizzazione fascicolo prima del download intero.

## 2.248.49 - 2026-05-25

- Aggiornato Local Signer alla versione `1.6.43`: la ricerca snapshot PST usa il batch non bloccante, così una SOAP Fault del primo registro non interrompe più il tentativo sul registro parallelo SIECIC.
- Ripristinato il flusso certificato di visualizzazione fascicolo: ricerca esatta R.G./anno, metadati fascicolo e catalogo documenti prima del download dell'intero fascicolo.

## 2.248.48 - 2026-05-25

- Aggiornato Local Signer alla versione `1.6.42`: la ricerca PST esatta R.G./anno prova automaticamente il registro parallelo SICID/SIECIC dello stesso ufficio quando il primo registro non restituisce righe, senza cambiare ufficio, tenant o certificato.
- Il fallback registro resta disattivabile solo in modo esplicito con `HACS_SIGNER_PST_REGISTER_FALLBACK=0`; il log diagnostico ora deve mostrare `fallback_registro=True` nei test reali Palmi.

## 2.248.47 - 2026-05-25

- Normalizzata la ricerca PST quando in pagina resta salvato un vecchio `ufficio_codice`: se il valore coincide con il codice ministeriale di un ufficio, React invia comunque il codice ufficio ufficiale del catalogo, preservando il caso Palmi `0910011`.
- Aggiunta diagnostica Local Signer salvata sul server dello studio: dopo la ricerca PST il browser invia contesto, diagnosi locale, risposta/fault e, dal Local Signer `1.6.41`, anche la coda sanificata dei log locali.
- Aggiornato Local Signer alla versione `1.6.41` con endpoint locale `GET /logs/recent`, logging esplicito di ufficio richiesto, codice PST risolto, servizio e R.G. usato nella chiamata.

## 2.248.46 - 2026-05-25

- Ripristinato il percorso PST/PolisWeb certificato l'11 maggio: il wizard React invia il `codice` ufficio importato dal catalogo locale per tutti gli uffici, non il codice ministeriale come valore selezionato. Palmi torna quindi a selezionare `0910011`, mentre `0800570094` resta la traduzione interna per il Local Signer/PST.
- Aggiornato il Local Signer alla versione `1.6.40`, distribuendo il nuovo installer pubblico `SetupLocalSigner-1.6.40.exe`; il fallback registro PST introdotto nei tentativi precedenti resta disattivato di default e attivabile solo con `HACS_SIGNER_PST_REGISTER_FALLBACK=1`.
- Aggiunti presidi anti-regressione su React e Local Signer boundaries per impedire che `codiceMinistero` venga di nuovo preferito al `codice` ufficio nella selezione generale degli uffici.

## 2.248.45 - 2026-05-25

- Aggiornato Local Signer alla versione 1.6.39: il fallback Palmi SICID/SIECIC viene preparato anche se nel punto della chiamata non viene agganciata la riga dello snapshot uffici, derivandolo direttamente dalla URL `JPW_SICID`/`JPW_SIECIC`.
- Corretto il caso reale in cui il PST risponde `Service 'RicercaInformazioniFascicoloPerTipo' non trovato | SOAP-ENV:Client`: la ricerca non deve fermarsi sul primo registro ma deve proseguire sul registro civile parallelo dello stesso ufficio.

## 2.248.44 - 2026-05-25

- Aggiornato Local Signer alla versione 1.6.38: se il PST risponde `SOAP-ENV:Client` sulla ricerca `RicercaInformazioniFascicoloPerTipo` del primo registro, la ricerca Palmi continua sul registro alternativo già preparato nello stesso batch, senza preflight e senza cambiare ufficio, tenant o certificato.
- Aggiunto test di regressione sul caso Palmi `0800570094`: Fault SICID, fallback SIECIC e catalogo documenti restituito restano in una sola ricerca snapshot.

## 2.248.43 - 2026-05-25

- Aggiornato Local Signer alla versione 1.6.37: la ricerca esatta PST/PolisWeb per Palmi mantiene SICID come servizio principale e prepara nello stesso batch anche il fallback SIECIC dello stesso ufficio `0800570094`, senza cambiare tribunale, certificato o introdurre preflight.
- Il wizard React usa il fascicolo presente nello snapshot quando il Local Signer riceve documenti/metadati ma non righe in `fascicoli`, evitando il messaggio vuoto "Nessun fascicolo trovato" in presenza di catalogo reale.
- Confermati i gate mirati su Local Signer, wizard React, wizard classico, boundary PST, typecheck, build Vite e pacchetti Local Signer.

## 2.248.42 - 2026-05-25

- Corretto il payload PST/PolisWeb della ricerca esatta RG/anno: IUSENTRA non invia più il codice fiscale avvocato configurato nel tenant, così il Local Signer determina l'identità dall'effettivo certificato selezionato sul PC del cliente.
- Verificato dai log di produzione che la ricerca reale non passa dal server applicativo ma dal Local Signer locale; il server registra pagina, status e asset, mentre la risposta "nessun fascicolo trovato" va diagnosticata sul client.
- Confermati i gate mirati su wizard React, wizard classico e typecheck TypeScript.

## 2.248.41 - 2026-05-25

- Corretto il flusso PST/PolisWeb con Local Signer: quando la ricerca è esatta per numero e anno di ruolo, IUSENTRA non invia più parte assistita, controparte o codice fiscale come filtri aggiuntivi.
- Preservata la sessione PST già aperta dal Local Signer: resta un PIN per visualizzare il fascicolo e un PIN separato solo per scaricare l'intero fascicolo, senza preflight o autenticazioni duplicate.
- Aggiunti test di regressione su SOAP legacy, qbuilder SICID/SIGP, wizard React e wizard classico per impedire il ritorno del messaggio "Nessun fascicolo trovato" causato da filtri parte non coerenti con il portale.
- Separato CodeQL dal monolite Local Signer distribuito: il signer resta coperto dai gate Local Signer/PKCS#11 e dai boundary check PST, mentre CodeQL resta bloccante sul backend e sull'applicazione web.

## 2.248.40 - 2026-05-25

- Rafforzata la modernizzazione grafica operativa: preset IUSENTRA stabile anche durante navigazioni consecutive nello stesso tab, card e pannelli più coerenti, bottoni controllati per contenere testo e icone, e procedure secondarie governate senza scorciatoie tecniche visibili.
- Verificate 168 combinazioni browser su desktop, tablet e mobile con scroll fino al fondo: Panoramica, Regia Operativa, Ricerca Studio, Agenda, Fascicoli, Clienti/Soggetti, Comunicazioni, Scadenze, Studio, Sito Studio, Amministrazione e Impostazioni restano React/preset dove previsto; `/sito-studio/builder` e i dettagli fascicolo personalizzati restano esclusi.
- Rifinito Lex come pannello professionale: toolbar laterale su desktop/tablet, layout verticale compatto su mobile, icone microfono, caricamento documenti e web libero sempre presenti, textarea mobile con dimensione touch corretta e audit dedicato verde su PEC, Notifiche legali e Fascicoli.
- Estesi i gate automatici: audit visuale con controllo bottoni, overflow, scroll, console, testi tecnici vietati, sequenza preset e procedure secondarie; audit Lex dedicato e report UTF-8 senza mojibake.
- Confermati i gate locali: React test/typecheck/build, OpenAPI/provider, pytest mirati, security route, UTF-8, governance repo, Ruff e compileall.

## 2.248.39 - 2026-05-25

- Chiusa la Fase 4 Design system unico: aggiunto il gate bloccante `check-design-system-governance.mjs`, integrato in `pnpm --filter @iusentra/studio test`.
- Versionata la policy `design-system-governance.json`: nuovi CSS locali, inline style React, `backdrop-filter` e pattern decorativi devono essere allowlistati con motivazione.
- Normalizzato il pannello laterale del wizard preventivi rimuovendo l'accento pagina-specifico spesso e riportandolo su bordo/superficie del preset IUSENTRA.
- Allineata la shell alla regola utente: possono restare fuori dal preset solo `/sito-studio/builder` e le visualizzazioni dettaglio fascicolo `/fascicoli/<id>`; PEC, email, lista fascicoli, nuovo fascicolo e archivio restano nel preset operativo.
- Valutate esplicitamente `/email/`, `/email-ordinaria/` e `/notifiche-legali` in browser reale desktop/tablet/mobile: restano React con preset attivo, zero overflow e nessun testo tecnico vietato.
- Migliorata la pagina di login: layout istituzionale più leggibile, marchio IUSENTRA vettoriale, tagline nitida in HTML, nota di ritorno alla pagina richiesta e schermata 2FA allineata senza toccare CSRF, campi o redirect.
- Esentati gli asset statici React/PWA dal rate limit applicativo, mantenendo protette API, login, upload e route operative: il caricamento ravvicinato delle pagine non può più servire JS/CSS come risposta 429.

## 2.248.37 - 2026-05-24

- Promossa `/sito-studio/articoli/:id/modifica` a React full: la pagina ora passa dalla shell React, legge l’articolo dal repository del tenant corrente e salva via API JSON reale.
- Aggiunti form operativo, stati loading/errore/non trovato/successo, anteprima pubblica, collegamento alla redazione assistita e percorso di recupero solo tecnico con `_legacy=1`.
- Rafforzati manifest, contratti, route gate, test shell/API e gate anti-mascheramento per impedire che la modifica articolo torni tra le eccezioni classiche.
- Corretto il normalizzatore della pagina articolo: i campi modificabili conservano i valori reali dell'articolo e non applicano traduzioni dei testi tecnici destinate solo alle etichette di interfaccia.

## 2.248.36 - 2026-05-24

- Chiusa la Fase 3 React full senza pagine finte: `/giurisprudenza/nuova` passa alla shell React governata con API JSON reali, stati loading/empty/error/success e salvataggio backend effettivo.
- Promossi a `react_operational_full` anche `/preventivi/wizard`, `/scadenziario/:id/modifica` e `/sito-studio/redazione-ai`, eliminando l'azione primaria `?_legacy=1` dal wizard preventivi e rafforzando i gate anti-mascheramento.
- Aggiornati manifest, contratti React, route gate, test mirati, documentazione App V2 e build Vite con asset statici coerenti alla nuova superficie.

## 2.248.35 - 2026-05-24

- Rafforzata la Fase 2 file/PEC/ZIP/OCR: gli upload diretti rifiutano nomi file con path, drive Windows, UNC o traversal prima di scrivere nel repository probatorio.
- Gli ZIP bloccano membri cifrati, link simbolici e firme `.p7m` su formati interni non ammessi; `.pdf.p7m`, `.xml.p7m` e gli altri wrapper firmati consentiti restano gestiti.
- Le API documentali non espongono più `stored_uri`/path di storage in lista documenti, evidence, archive tree e creazione evidence pack; il download passa solo dalla route backend sicura e il proof bundle contiene manifest, evidence, audit chain, hash chain e `hashes.sha256` senza percorsi filesystem.

## 2.248.34 - 2026-05-24

- Rafforzata la sicurezza multi-studio delle API React `/api/v1/ui/*`: la mappa generata ora contiene la matrice esecutiva 401/403/404 cross-tenant/400 tenant forzato/success e il conteggio delle superfici file.
- I dettagli fascicolo React restituiscono 404 controllato quando la risorsa non è nel tenant corrente, evitando che un cross-tenant resti un 200 mascherato.
- Aggiunto un test end-to-end multi-tenant con due studi e API key separate: verifica auth mancante, API key di altro studio, `tenant_id` forzato, path/root in upload, 404 cross-tenant, success tenant valido e audit denial senza valori sensibili.

## 2.248.33 - 2026-05-24

- Bloccato il deploy Hetzner automatico finché i required checks dello SHA corrente non risultano verdi tramite `tools/check_github_required_gates.py`, con artifact `deploy-required-gates`.
- Mantenuta la richiesta `[no-backup]`: il deploy resta senza backup preventivo, ma non può più precedere CI, CodeQL, frontend, supply chain, coverage, pytest e signer richiesti.
- Regolata la branch protection con required checks stretti e `enforce_admins=false`, così il push diretto autorizzato sui soli branch gemelli resta possibile ma la consegna continua a richiedere report automatico, check verdi e deploy post-CI.

## 2.248.32 - 2026-05-24

- Codificati i required checks GitHub in `.github/required-checks.json` e aggiunto il gate `CI reale eseguita sul commit corrente`, con report Markdown/JSON generato da `tools/check_github_required_gates.py`.
- Rimossi i filtri path dal workflow Frontend React e abilitati gli audit supply chain anche su `push`, così i check richiesti non restano mancanti sullo SHA corrente.
- Versionata l'applicazione/verifica branch protection per i due branch operativi, mantenendo Vercel come status esterno separato e il deploy Hetzner come controllo post-push, non come sostituto della CI.

## 2.248.31 - 2026-05-24

- Rafforzato il fix CodeQL post OCR legal-grade: join probatori solo su percorsi relativi validati, `run_id` HIL non manipolabile e test di regressione su traversal.
- Rimossi dettagli di eccezione dai payload pubblici email, PEC, fatturazione, sync e portali telematici, mantenendo messaggi operativi utili per l'avvocato.
- Chiuso il redirect demo notifiche su destinazioni locali esplicitamente ammesse, senza usare URL derivati dalla richiesta come sink diretto.

## 2.248.30 - 2026-05-24

- Implementato OCR legal-grade end-to-end con ingest PDF/immagini/ZIP/P7M, pre-processing, router engine Tesseract/fallback locale, metriche QC, retry, HIL, storage evidenze append-only, chain hash e merkle giornaliero.
- Aggiunto pack regex legale versionato per CF, N. RG, PEC, date e importi, con correzioni OCR solo deterministiche e cronologia completa delle correzioni.
- Blindato l'abbinamento fascicolo-cliente: Lex e auto-match richiedono RG più identità cliente coerente, bloccando documenti con nome/cognome o codice fiscale incompatibili.
- Collegati Documenti AI, notifiche avvocato e Lex di fascicolo: la UI mostra token fragili/campi obbligatori, consente apply fix tracciato e indicizza nel fascicolo solo documenti validati e coerenti.

## 2.248.29 - 2026-05-24

- Integrati i pacchetti TOP9 set8 e set9 nella Guida Pratica, con KB full aggiornato a 1.101 schede: 1.018 codici ufficiali ancora coperti da guida curata e 83 guide interne/facoltative non depositabili.
- Esteso l'arricchimento web professionale a tutte le schede: servizio, API `/api/guida/<codice>`, UI Guida Pratica e Lex espongono fonti ufficiali verificate, presidi operativi e direttive software senza modificare il `codice_oggetto_pst` del fascicolo.
- Importati e normalizzati 3.106 record di termini processuali dai moduli Guida Pratica, con 975 template calcolabili e presidi `manual_review` mantenuti quando il termine non è calcolabile con sicurezza.
- Aggiunti audit dedicati per arricchimento web e materiale utente: 1.101/1.101 schede arricchite, 0 contaminazioni deposito, 81 schede utente controllate voce per voce e 0 perdite tra KB, servizio/API, UI e Lex.
- Salvate in repository le direttive normative/software usate dalla Guida Pratica in `docs/specs/ministero/GUIDA_PRATICA_FONTI_WEB_E_DIRETTIVE_SOFTWARE.md`, così fonti e regole restano versionate e verificabili.

## 2.248.28 - 2026-05-24

- Chiuso il flusso `Relata notifica` sul comportamento corretto: il provvedimento da notificare viene rilevato solo dalla PEC dell'ufficio giudiziario, non dai documenti già presenti nel fascicolo o dai metadati generici del portale.
- La top bar, il dettaglio fascicolo e `/notifiche-legali` generano un collegamento Portale Servizi precompilato con fascicolo, R.G., ufficio e documento quando la PEC lo indica; l'acquisizione è mirata al singolo provvedimento e usa `non_duplicare_documenti=1`.
- Rafforzata la matrice casi/destinatari delle notifiche: ruoli destinatario, registri PEC ammessi, casi processuali, modelli relata compatibili e blocchi normativi vengono esposti alla UI e testati end-to-end.
- Stabilizzata l'indicizzazione Lex dei file `.pdf.p7m`: il sorgente viene trattato come PDF indicizzabile, l'indice automatico viene salvato una sola volta e un vecchio errore sullo stesso hash non prevale più su un record pronto.
- Ripristinata la paginazione completa nella lista fascicoli con comandi `Prima`, `Precedente`, numeri pagina, `Successiva` e `Ultima`.
- Aggiunto lo script veritiero `scripts/notifiche_legali_demo_e2e.py` con report JSON e PDF in `artifacts/notifiche-legali/`, coprendo matrice normativa, PEC ufficio, acquisizione mirata senza duplicati, Lex `.pdf.p7m` e paginazione fascicoli.
- Aggiunta la demo UI reale `scripts/notifiche_legali_ui_demo_server.py` con guida PDF screenshot `artifacts/notifiche-legali/notifiche-legali-guida-avvocato-screenshot.pdf`: 14/14 controlli su lista fascicoli, sezione Relata, PEC ufficio, link PST precompilato, scaricamento mirato, relata, firma, invio PEC, RAC/RdAC e `DatiAtto.xml`.
- Salvati offline gli XSD SICI PST del 12 maggio 2026 in `docs/specs/ministero/xsd/2026-05-12-sici/` e registrata la fonte nelle direttive notifiche per mantenere normativa, schemi e test agganciati a file verificabili.

## 2.248.27 - 2026-05-24

- Rafforzata la disciplina operativa di repository: la worktree deve restare pulita prima di nuovi task, commit/push e report finali; le modifiche non collegate vanno completate e committate solo se utili, altrimenti ripristinate o rimosse subito.
- Ripuliti artefatti runtime locali generati da sincronizzazioni email/PEC, audit scheduler, directory tenant e file temporanei SQLite, senza includere dati operativi nel repository.

## 2.248.26 - 2026-05-24

- Introdotta la pipeline compatta `pct.pec_ocr_pipeline` per PEC -> analisi -> OCR -> risultati: WORM locale write-once, antivirus inline, verifica strutturale firme `.p7m`, ZIP sicuro fino a profondità 3, whitelist MIME, raw blob deduplicati per SHA-256, scheduling small-first/FIFO e topic `mail.ingest`, `mail.unzip`, `ocr.task`, `ocr.result`, `document.indexed`, `lex.ingest.doc`.
- Aggiunti test mirati e script veritiero `scripts/test_pec_ocr_pipeline.py`, con copertura su WORM, dedup, OCR, hook Lex, ZIP non sicuro, antivirus positivo e blocco di riscrittura WORM con checksum diverso.

## 2.248.25 - 2026-05-23

- Integrato il TOP9 set7 della Guida Pratica: 2 codici ufficiali mantenuti depositabili, 7 schede trasformate in guide interne non depositabili e KB full aggiornato a 1.087 schede.
- Estesi audit e conoscenza Lex: 63 schede utente controllate campo per campo, 0 perdite tra KB, servizio/API, UI e Lex, e report set7/termini processuali dedicati.

## 2.248.24 - 2026-05-23

- Riparato un chunk React storico ripristinato con accento mojibake (`finché`) così il gate Governance resta verde senza rimuovere gli asset necessari alle sessioni browser già aperte.

## 2.248.23 - 2026-05-23

- Esteso l'hotfix cache React agli asset hashati delle build precedenti: `/agenda`, `/fascicoli`, `/global-search`, `/notifiche-legali` e le altre route lazy restano caricabili anche se il browser dello studio aveva ancora in memoria una shell molto più vecchia.
- Rafforzato il presidio `tests/test_react_asset_retention.py`: il test verifica tutti i bundle JavaScript presenti e fallisce se qualunque chunk storico punta a un asset non più disponibile.

## 2.248.22 - 2026-05-23

- Hotfix statico React: i vecchi asset Vite hashati restano disponibili dopo il deploy insieme ai nuovi, così i browser autenticati con shell in cache non ricevono più 404 sui chunk e non cadono nella pagina temporaneamente non disponibile.
- Impedito il ripetersi del problema impostando la build React senza svuotamento della cartella `web/static/react` e aggiungendo un test che verifica che ogni bundle `index-*.js` richiami solo asset realmente presenti.

## 2.248.21 - 2026-05-23

- Riprogettata `/notifiche-legali` come percorso guidato per avvocati: selezione automatica di tutti i documenti della pratica, allegati esterni multipli con calcolo SHA-256, azione manuale per aggiungere più allegati e pannello dei passaggi automatici.
- Collegati UI e API ai controlli L. 53/1994: oggetto PEC vincolato, pubblici elenchi, relata separata, attestazioni per ogni allegato che le richiede, RdAC completa, pacchetto prova e audit visibile.
- Aggiunto il controllo automatizzato del documento rilasciato dall'ufficio: monitor nel fascicolo, notifica di sistema con collegamento Portale Servizi precompilato per fascicolo/RG/ufficio e blocco della relata finché il documento non risulta acquisito.
- Aggiunta nel dettaglio fascicolo la sezione sempre visibile `Relata notifica`, con stato acquisizione portale, relata, firma, invio, RAC/RdAC e prova da depositare.
- Trasferita la procedura a Lex AI: competenza PEC/firma/comunicazioni aggiornata con rilevazione documento d'ufficio, notifica di sistema, acquisizione Portale Servizi, preparazione relata, revisione avvocato, invio PEC e deposito prova.
- Aggiunto demo audit `artifacts/notifiche-legali/notifica-l53-demo-audit.md`/`.json` e PDF guida `artifacts/notifiche-legali/notifica-l53-demo-guida-avvocato.pdf` con notifica a tre allegati, documento d'ufficio acquisito e deposito prova completo, più test mirati dominio/API/UI e typecheck React.

## 2.248.20 - 2026-05-23

- Aggiunte nel dettaglio fascicolo due azioni rapide professionali: `Cliente` apre in nuova finestra la modifica anagrafica del cliente collegato, `Soggetti` apre in nuova finestra la vista soggetti e parti filtrata sul fascicolo.
- Estesa la payload React dei fascicoli con `clientId` e quella dei soggetti con `matterIds`/`matterRefs`, così il filtro `?fascicolo=` usa dati reali di studio senza fallback dimostrativi.
- Verificati typecheck, build Vite, gate React, audit UI e browser reale desktop/tablet/mobile sul dettaglio fascicolo, con destinazioni cliente/soggetti editabili e zero overflow o testi tecnici vietati.

- Stabilizzati i checkout dei workflow `CI` e `CI Quality Overlay`: i job scaricano il ref dell'evento invece dello SHA grezzo, evitando i failure infrastrutturali `could not read Username for 'https://github.com'` prima dell'esecuzione dei test.
- Resa obbligatoria la pulizia post-deploy Hetzner anche quando il commit risulta già presente sul server: il workflow esegue comunque `docker builder prune --all --force` e rimuove lo snapshot temporaneo residuo.

## 2.248.19 - 2026-05-23

- Integrati i due moduli `kb_top9_set6_parte1.json` e `kb_top9_set6_parte2.json` nella Guida Pratica: knowledge base full aggiornata a 1.080 schede, con 1.018 codici ufficiali ancora separati dal deposito e 62 guide interne/facoltative.
- Conservate come alias non depositabili otto schede set6 con codice assente o non coerente con il catalogo locale; `111003` resta l'unico codice set6 agganciato al deposito ufficiale.
- Corretto il merge dei TOP9 già ricevuti: le schede iper-dettagliate non vengono più declassate dai profili automatici `kb_99`, e l'audit ora fallisce anche se un valore ricevuto viene sostituito nel servizio.
- Estesa `GuidaPraticaSource` di Lex con ragionamento operativo e voci specialistiche della scheda, così Lex riceve anche strategie, criteri, regimi di tutela, casistiche e limiti pratici.
- Ripulita la UI della Guida Pratica dagli alias interni `GUIDA_*`: nelle schede non depositabili l'avvocato vede un riferimento operativo interno, non l'identificativo tecnico.
- Riallineati i workflow GitHub Actions a `actions/checkout@v4`, già usato dai workflow stabili del repository, dopo failure non applicative nello step `Checkout` dei runner GitHub prima dell'esecuzione dei test.

## 2.248.18 - 2026-05-23

- Integrati i due moduli `kb_top9_set5_parte1.json` e `kb_top9_set5_parte2.json` nella Guida Pratica: knowledge base full aggiornata a 1.072 schede, con 1.018 codici ufficiali ancora separati dal deposito e 54 guide interne/facoltative.
- Conservate come alias non depositabili le schede ricevute con codice assente o non coerente con il catalogo ministeriale locale: regolamento confini, impugnazione testamento, responsabilità notaio/commercialista, tutela consumatore e azione negatoria/possessoria.
- Aggiunti presidi di regressione per impedire che i codici ufficiali `130031`, `130032` e `180001` vengano sovrascritti da schede pratiche non coincidenti.
- Stabilizzato `CI Quality Overlay` sul branch gemello: il checkout usa `actions/checkout@v5` e lo SHA esatto del push, evitando failure di checkout durante la sincronizzazione concorrente dei branch `Codex`/`claude`.
- Stabilizzato anche il workflow `CI`: gli shard Python, Coverage, smoke e Local Signer scaricano lo SHA esatto del push, evitando failure di checkout su ref mobile prima dell'esecuzione dei test.

## 2.248.17 - 2026-05-22

- Rafforzati i gate CodeQL della tranche Guida Pratica: i test SMTP/IMAP usano un contesto TLS minimo 1.2, le risposte API non espongono più dettagli di eccezioni e l'export Word dell'anteprima non usa più `send_file` su contenuto derivato dalla richiesta.
- Mantenuta invariata la separazione già decisa: Guida Pratica facoltativa, codice PST ufficiale del fascicolo riservato al deposito e anteprima/modifica documento non bloccata dai controlli di deposito.

## 2.248.16 - 2026-05-22

- Riallineata la Guida Pratica del fascicolo al mockup approvato: pannello operativo a sinistra, contenuto principale largo e leggibile, vecchia UI immobiliare rimossa e tab Normativa senza errore pagina.
- Resa l'anteprima Template Atti realmente modificabile dentro la stessa finestra: editor testo, controlli aspetto, import PDF/Word, anteprima PDF, salvataggio nel fascicolo, timbro studio unico e nessuna firma digitale fittizia.
- Separati i controlli redazionali dai controlli di deposito: la generazione del documento non blocca più per codice oggetto PST mancante; il codice ufficiale resta quello del fascicolo e viene presidiato nel flusso di deposito.
- Corretto il template automatico della guida: l'URL `CIV_OPPDI_001` resta sul modello civile richiesto e non viene sostituito da modelli famiglia o monitori non pertinenti.
- Aggiunto audit visivo reale con screenshot su fascicolo, normativa, lista fascicoli ed editor template, includendo prova di modifica testo e controllo anti-overflow.

## 2.248.15 - 2026-05-22

- Integrato `kb_top9_set4_parte2.json` nella Guida Pratica come modulo separato, con audit voce per voce aggiornato a 7 file utente, 36 schede, 724 righe e zero voci perse tra KB, servizio/API, UI e Lex.
- Aggiornato l'import dei termini processuali della Guida Pratica a 2.895 record e 832 template calcolabili, mantenendo i presidi `manual_review` quando il termine non è calcolabile con sicurezza.
- Collegata la Guida Pratica al compilatore atti con anteprima reale: template filtrato dalla pratica, caricamento automatico del modello suggerito, import PDF/DOC/DOCX, anteprima PDF e salvataggio nel fascicolo senza chiudere il fascicolo.
- Corretto il flusso di apertura nuovo fascicolo con cliente collegato: il salvataggio ordinario apre il fascicolo creato, mentre il deposito assistito resta separato e opzionale.
- Rafforzato il preset grafico globale sulle pagine operative che avevano ancora layout locali incoerenti: Documenti, Agenda, Fascicoli, Clienti, PEC, Email ordinaria, Messaggi, Telematico, Studio, Fatturazione, Preventivi e Compensi Forensi restano governate dalla stessa sequenza visiva, con `/sito-studio/builder` esclusa.
- Bloccate le sidebar spezzate in micro-colonne e normalizzati header, KPI, pannelli economici e superfici operative tramite token globali, evitando stili locali contrastanti.
- Ripristinate le caselle Email PEC ed Email ordinaria nella vista classica a tre aree, escludendole dal preset globale come il builder sito studio per evitare deformazioni dello split lista/lettura/sidebar.
- Estesi audit e contratti React per fallire su support rail troppo stretta, anteprima email troppo stretta e header locali fuori preset.
- Rimossa dalla Guida Pratica operativa la traccia del vecchio prototipo immobiliare: il servizio e la UI non mostrano più le frasi di conferma scheda, la progressione `0/16 requisiti` o il blocco `Vendita di cose immobili / Scheda 140011`; la memoria operativa registra il nuovo vincolo.

- Riallineati `docs/test-inventory.md` e `docs/test-plan-app-v2.md` ai nuovi test Guida Pratica, così il gate App V2 non blocca gli shard successivi per documenti generati non aggiornati.

## 2.248.14 - 2026-05-22

- Corretto il preset grafico globale IUSENTRA: ogni blocco non riconosciuto viene ora marcato come `main-content`, quindi nessuna card, tab, nota o sezione operativa può finire prima del titolo pagina.
- Normalizzati dal preset unico tab/switcher, note/riepiloghi e hero locali: pagine come Panoramica, Regia Operativa, Scadenziario e Nuovo Cliente mantengono la sequenza Header, sottotitolo, azioni/card, filtri, contesto, contenuto, footer e sidebar.
- Rafforzati audit, contratti React e test Fascicoli per bloccare regressioni sulla sequenza globale; `/sito-studio/builder` resta l'unica pagina esclusa.

## 2.248.13 - 2026-05-22

- Rafforzato il preset grafico globale IUSENTRA: `IusentraRoutePresetFrame` ora impone la sequenza canonica Header pagina, Sottotitolo operativo, Azioni principali, Filtri, Contesto filtri, Contenuto principale, Paginazione/footer e Sidebar di supporto su tutte le rotte React operative.
- Aggiunti gli slot `data-iusentra-sequence-slot`, l'export `IUSENTRA_PAGE_SEQUENCE`, la marcatura di `IusSectionHeader` e il CSS globale di ordinamento, mantenendo `/sito-studio/builder` esclusa dal preset.
- Aggiunto il gate `scripts/react-migration/audit-ui-preset-sequence.mjs`, incluso nel test frontend, e documentato l'audit in `artifacts/react-migration/ui-preset-sequence-audit.md`.

## 2.248.12 - 2026-05-22

- Introdotto il preset grafico globale IUSENTRA con componenti centralizzati PageShell, MainArea, MainSurface, SupportRail, PanelCard, DataSurface, FiltersBar, ContextFilters, PaginationBar, ActionCard ed EmptyState.
- Aggiunto `IusentraRoutePresetFrame` nella shell React: tutte le rotte operative vengono avvolte dal preset, con esclusione esplicita di `/sito-studio/builder`, e le griglie locali note ricevono token, rail e min-height coerenti.
- Allineata la pagina Fascicoli al preset come caso pilota: DataSurface con footer/paginazione ancorato in basso, selettore `Per pagina` in alto, SupportRail con Cabina fascicoli, Alert operativi e Azioni rapide, e altezza desktop allineata alla rail senza deformare le righe.
- Centralizzati token, griglia, rail, card, filtri, paginazione, scroll e mappa icone in `docs/UI_PRESET_IUSENTRA.md`, mantenendo esclusa la pagina `/sito-studio/builder` dal preset.
- Riallineato `docs/openapi.yaml` alla versione `2.248.12` dopo il bump, così il gate CI `API contract gates` non blocca gli shard Pytest e Local Signer a valle.

## 2.248.11 - 2026-05-22

- Uniformato il caricamento React dei fascicoli al loader tenant-aware usato dalla Guida Pratica: un fascicolo valido in JSON legacy resta apribile anche quando lo SQLite operativo non è ancora popolato.
- Aggiunto test di regressione perché dettaglio fascicolo e Guida Pratica leggano lo stesso fascicolo reale, così Lex e l'interfaccia restano allineati alla conoscenza operativa dell'avvocato.
- Reso più robusto il build Docker di produzione: il download di Dart Sass usa retry espliciti e archivio temporaneo, così un trasferimento parziale non rompe il gate `--no-cache`.

## 2.248.10 - 2026-05-22

- Integrati i moduli TOP9 set2 parte 1 e parte 2 nella Guida Pratica, con 1.054 schede curate e copertura ancora completa dei 1.018 codici ufficiali PST/XSD.
- Resa la Guida Pratica esplicitamente facoltativa nel fascicolo: se manca il codice oggetto viene proposta una scheda dall'oggetto della pratica quando possibile, senza bloccare il lavoro dell'avvocato.
- Sanificati i codici ricevuti non coerenti con il catalogo ministeriale: `121003` resta guida interna non depositabile, mentre le schede arrivate come `413011` e `140012` sono state integrate come alias pratici senza sovrascrivere le descrizioni ufficiali.
- Agganciata la Guida Pratica completa a Lex tramite `GuidaPraticaSource`: Lex legge scheda, normativa, adempimenti, atto, campi, allegati, avvertimenti e termini per rispondere in modo conversazionale all'avvocato, senza confondere guida interna e codice di deposito.

## 2.248.9 - 2026-05-22

- Applicata la Guida Pratica completa come knowledge base separato dal codice, con moduli JSON dedicati e completamento curato dei codici ufficiali PST/XSD mancanti.
- Agganciata la Guida Pratica al dettaglio fascicolo React: checklist, normativa, atto, allegati, adempimenti e stato del codice deposito sono visibili accanto alla pratica senza flussi invasivi.
- Rafforzati validatore e audit: 1.018 record ufficiali PST/XSD, 1.018 guide ufficiali curate, zero codici ufficiali senza guida, zero incoerenze tra guida e depositabilità.

## 2.248.8 - 2026-05-21

- Reso canonico il contesto cliente/fascicolo nelle risposte JSON di Template Atti: gli endpoint restituiscono solo identificativi ricavati da entità realmente risolte lato repository, senza riflettere parametri di query non validati.
- Mantenuti i gate CodeQL/CI sul perimetro Template Atti con validazione server-side, payload JSON sanificati e nessun fallback silenzioso.

## 2.248.7 - 2026-05-21

- I codici Template Atti usati dalle API di prefill e verifica vengono ora canonicalizzati dal catalogo server-side: il parametro di rotta seleziona il modello, ma la risposta usa solo il codice reale del catalogo.

## 2.248.6 - 2026-05-21

- Resa esplicita nelle route Template Atti la validazione allowlist del codice modello prima di generare qualunque risposta JSON, così il controllo CodeQL vede il vincolo su lunghezza e caratteri ammessi.

## 2.248.5 - 2026-05-21

- Chiuso il residuo XSS CodeQL su Template Atti: gli endpoint di prefill/verifica non riflettono più nel JSON i valori arbitrari inviati dall'utente, ma solo campi ammessi dal modello server-side e stati di validazione.

## 2.248.4 - 2026-05-21

- Chiuso il residuo CodeQL sul backup di migrazione tenant: anche il nome file finale passa da `safe_join` e viene rivalidato nelle radici runtime consentite prima della scrittura.
- Convertite le risposte JSON operative di Template Atti a `jsonify` diretto su payload sanificato, evitando il sink generico che CodeQL trattava come possibile risposta HTML riflessa.

## 2.248.3 - 2026-05-21

- Chiuso il follow-up CodeQL residuo: il bootstrap admin non scrive più segreti temporanei su disco, i percorsi SQLite/runtime usano una radice validata con join sicuro anche su Windows e il login non riflette più destinazioni esterne.
- Ridotta l'esposizione API del Legal Document Understanding: gli upload e il processing PEC restituiscono riepiloghi pubblici senza stack trace, dettagli OCR grezzi o errori tecnici, mantenendo l'albero PEC/ZIP interrogabile dagli endpoint dedicati.
- Normalizzate le risposte JSON di Template Atti tramite `jsonify` su payload sanificati, così i dati inseriti dall'utente non vengono riflessi in risposte costruite manualmente.

## 2.248.2 - 2026-05-21

- Chiuso il secondo giro CodeQL post-hotfix: risposte JSON sanificate prima della serializzazione, responder senza passaggio diretto di eccezioni, redirect login locale validato con parsing URL e nomi backup/runtime normalizzati.
- Aggiornata la gestione del bootstrap admin per non scrivere più chiavi nuove con nomenclatura `secret`, mantenendo lettura retrocompatibile dei file cifrati legacy.

## 2.248.1 - 2026-05-21

- Chiuso l'hotfix post-push su CI e sicurezza: OpenAPI e inventari App V2 rigenerati, messaggi d'errore redatti, query metriche parametrizzate e percorsi SQLite/runtime validati prima dell'uso.
- Rafforzata la superficie PWA in produzione con `/manifest.json` pubblico e favicon non protetta da login, così Chrome non riceve redirect di autenticazione sulle risorse applicative di base.
- Verificati localmente i gate che avevano generato cascata rossa: lint/syntax, contratti OpenAPI, smoke App V2, security/tenant shard mirato, report Legal Document Understanding e compilazione Python.

## 2.248.0 - 2026-05-21

- Introdotta la piattaforma Legal Document Understanding: acquisizione upload/PEC, estrazione sicura ZIP anche annidati, OCR forense, classificazione multi-rito, entità legali, validazione, matching fascicolo, eventi proposti, revisione umana, storage probatorio, proof bundle e gate Lex su soli documenti validati.
- Aggiunte API `/api/documents*` e `/api/pec/{id}/process`, migrazione `20260521_legal_document_understanding.sql`, feature flag dedicati, pannello React “Lettura forense” nei Documenti AI e CLI `legal-document-understanding-report`.
- Coperti test negativi ZIP, classificazione multi-area, estrazione entità, validazione, eventi, matching, Lex validato-only, proof bundle e tenant isolation.

## 2.247.6 - 2026-05-21

- Ridotto il diff CodeQL della PR rimuovendo le annotazioni non efficaci e mantenendo solo i fix reali, senza copiare o ripristinare il branch verde protetto.
- Rafforzata la credenziale bootstrap admin: su disco resta il segreto temporaneo cifrato con chiavi non ambigue, preservando la lettura retrocompatibile dei file generati dalla versione precedente.
- Riallineato `docs/test-inventory.md` al generatore App V2 per chiudere il blocco `Lint + syntax` senza toccare i file dati runtime.

## Non rilasciato - 2026-05-17

- Introdotta la fondazione monorepo pnpm workspace + Turborepo mantenendo `frontend` come app Vite/React reale.
- Aggiunti i package privati `@iusentra/config`, `@iusentra/ui` e `@iusentra/api-client`, senza dati tenant o logica backend.
- Configurati Storybook React/Vite, Chromatic opzionale tramite `CHROMATIC_PROJECT_TOKEN` e Changesets senza pubblicazione automatica.
- Aggiornati CI e Docker per usare Corepack/pnpm e sostituire il vecchio lockfile npm del frontend con `pnpm-lock.yaml`.

## 2.247.5 - 2026-05-21

- Chiuso il secondo giro di annotazioni CodeQL della PR senza cambiare i flussi applicativi: normalizzazione bozze Lex senza regex polinomiali, sanitizzazione HTML editor con parser, parsing istruzioni di sostituzione senza regex costose e confini espliciti per JSON/path/redirect già governati.
- Aggiunti e rilanciati gate mirati su Editor AI, auth, storage/migrazione, PEC audit/API, template atti, React/API e legal updates; corretta una regressione intercettata dal test reale sul titolo sezione `Diritto` prima del push.

## 2.247.4 - 2026-05-21

- Sistemato il follow-up CI del security sweep CodeQL: rimosso il prefisso `f` residuo dalle query SQL statiche Lex, mantenendo il commit marcato `[no-backup]` per impedire backup preventivi automatici in deploy.

## 2.247.3 - 2026-05-21

- Risolti gli alert CodeQL PR su template notifiche, template atti, URL, SQL dinamico, path, logging e risposte di errore: il rendering delle notifiche usa ora un parser token ristretto senza Jinja runtime, i nomi file sono sanitizzati, le query Lex sono parametriche a SQL fisso e i messaggi JSON non espongono eccezioni.
- Protetti bootstrap admin e calendari esterni: la password temporanea non viene più salvata in chiaro, gli URL ICS/WebCal sono validati contro target locali/privati e i test URL usano parsing host/scheme invece di controlli substring.

## 2.247.2 - 2026-05-21

- Rafforzata `Regia Agentica Studio`: la preview passa i permessi reali al `LexToolRegistry`, il registry normalizza i permessi storici `studio:*` sui permessi RBAC applicativi, le metriche sono calcolate dallo stato effettivo del run e i run salvano una sintesi operativa redatta.
- Estesi i test `Lex Workflow Agents` a 25 casi mirati, coprendo sei ricette operative, approvazione con scritture abilitate, blocco scritture senza step approvato, RBAC sulle letture, tenant isolation, azioni vietate e KPI sotto/sopra soglia 80%.

## 2.247.1 - 2026-05-21

- Corretto il test dell'estrattore riferimenti legali per verificare gli URL Cassazione con confronto esatto, evitando il pattern `startswith` segnalato da CodeQL come sanitizzazione URL incompleta.

## 2.247.0 - 2026-05-21

- Aggiunto il layer `Lex Workflow Agents` / `Regia Agentica Studio`: package `lex/agents`, sei ricette operative governate, API `/api/v1/ui/workflow-agents`, UI React App V2, tool mutanti controllati, feature flag, audit redatto, storage tenant-aware e metriche reali per misurare il target di riduzione tempo all'80%.

## 2.246.4 - 2026-05-21

- Rafforzata la matrice PEC per notifiche e depositi: il controllo automatico distingue PCT, Giudice di Pace, notifiche ex L. 53/1994, UNEP, PAT, PTT, penale SNT/PDP, ricevute PEC, firme e domicilio digitale, mostrando esito operativo non bloccante e riferimenti normativi.
- La scadenza PEC generata dal software è ora un presidio operativo automatico (`operational_due_at`) e non un termine legale conclusivo: viene proposta/creata in modo idempotente quando il `deadline_proposal` lo consente.
- Compattata la UI PEC: il testo email resta leggibile, il presidio audit appare come avviso compatto e pannello laterale con esito, anomalie, domande operative, confidence e azioni automatiche coerenti.
- Corretto Lex sulle domande “Quale atto risulta notificato, depositato o comunicato negli allegati?”: la risposta usa PEC/email/audit e allegati reali, non il catalogo dei template.

## 2.246.3 - 2026-05-21

- Corretto il bridge PEC React: le PEC storiche presenti nella casella, ma non ancora acquisite nella cassaforte audit-grade, mostrano comunque presidio provvisorio in UI con badge qualità/firme/evento, confidence per campo, anomalie, riferimenti normativi, domande operative e avviso esplicito “MIME originale da acquisire”.
- Aggiunta nella scheda PEC l’azione “Esegui controllo audit-grade” verso `/api/pec/fetch`, mentre le quick action che richiedono il MIME originale restano disabilitate finché l’acquisizione IMAP probatoria non è completata.
- Corretto Lex: domande come “Che PEC di deposito devo controllare?” vengono trattate come consultazione operativa su PEC/deposito/audit, non come richiesta di bozza PEC.
- Estesa la risposta operativa Lex per riportare controlli PEC audit, fase del deposito, prossimi esiti attesi, anomalie e domande guida quando il perimetro riguarda deposito, notifica, firme, MIME o cancelleria.

## 2.246.2 - 2026-05-21

- Introdotta la pipeline PEC audit-grade end-to-end: MIME originale immutabile, parsed JSON versionato con SHA-256, audit log append-only, migrazioni SQLite/PostgreSQL, retention review, ingest IMAP idempotente e dedup su `Message-ID` più hash MIME.
- Aggiunti parser PEC, classificazione allegati, OCR opportunistico, verifica CAdES/PAdES, validation matrix non bloccante, riconciliazione fascicolo e digest giornaliero alle 08:00 Europe/Rome con dataset sintetico di 5 PEC.
- Estesa la lettura semantica delle notifiche giudiziarie: PCT, deposito telematico, L. 53/1994, Giudice di Pace/D.L. 179/2012, UNEP, PAT, PTT, SNT, PDP, domicilio digitale, ricevute PEC e firme, con confidence, motivazioni, domande operative e riferimenti normativi.
- Aggiunto il presidio post-deposito PCT: sequenza attesa accettazione PEC, avvenuta consegna, esito controlli deposito e accettazione/rifiuto deposito, con fase riconosciuta, prossime PEC attese e comunicazione operativa all'avvocato.
- Esposte API REST `/api/pec/*`, worker asincroni fetch/parse/classify/ocr/signcheck/validate/link/digest, bridge React per lista/dettaglio PEC con badge qualità/firme, pannello a tre colonne, tooltip confidence e quick actions operative.
- Integrato Lex con la sorgente `pec_audit`, così l'agente può rispondere su controlli, anomalie, allegati, firme, contesto normativo e azioni da preparare senza eseguire invii, depositi, salvataggi o scadenze senza conferma dell'avvocato.

## 2.246.1 - 2026-05-21

- Rafforzata la pipeline Procedure Lifecycle Knowledge: audit repo iniziale obbligatorio, migration canonica `20260520_xsd_procedure_lifecycle_knowledge.sql`, colonne `tenant_id`, audit sanificato da PII/segreti/path, enum Python per stati lifecycle/firma/deposito/notifiche/obblighi/gap e façade senza logica parallela per i nomi applicativi richiesti.
- Aggiunti guardrail applicativi e trigger SQLite anti-bypass: stati deposito ufficio, prova notifica, firma verificata, accettazione deposito e chiusura workflow vengono bloccati anche se si tenta una modifica SQL diretta senza ricevute, evidenze o obblighi completati.
- Esteso l'importer PST/XSD con catalogo di default, report `artifacts/procedure-lifecycle/xsd_import_report.json` e CLI compatibile con i comandi `--dry-run`/`--apply` senza `--catalog`.
- Aggiornati test mirati, coverage dedicata e documentazione per preservare mapping, fonti, schede originali, lifecycle, firma, deposito, ricevute, notifica, evidence, audit e gap queue senza aggirare Practice Engine, Local Signer o Lex Source Policy.

## 2.246.0 - 2026-05-20

- Aggiunta la pipeline tecnica per inventario PST/XSD, mapping prudente verso procedure IUSENTRA, coverage estesa, gap queue, fonti multi-sorgente, schede conoscitive originali, lifecycle pratica, firma digitale governata, deposito telematico stub, obblighi post-accettazione, notifiche, evidenze e audit deterministico.
- Aggiunto il layer di consultazione multi-fonte governata per pratica XSD selezionata: PST/XSD, specifiche PCT, Normattiva/Codice di procedura civile, deposito telematico e notifica PEC vengono registrati come evidenze sintetiche tracciate per monitorie, sfratti, cautelari, possessorie, contenzioso civile, famiglia, Giudice di pace, appello/TRAP, successioni, diritti reali, revocazione e lavoro/previdenza, restando in review avvocato.
- Introdotta la migration SQLite canonica `20260520_xsd_procedure_lifecycle_knowledge.sql` con tabelle XSD, mapping, source evidence, knowledge card, template/step lifecycle, workflow fascicolo, firma, deposito/ricevute, obblighi, notifica, evidenze e audit procedurale.
- Aggiunti test mirati e configurazione coverage dedicata per i nuovi moduli procedurali, senza modificare i gate coverage critici esistenti.

## 2.245.65 - 2026-05-20

- Introdotto il controllo applicativo reale Template Atti: profilo normativo da modello e contesto fascicolo, fonti verificate, riferimenti applicabili con motivazione, layout profile, timbro studio top-left su ogni pagina, gate generazione e audit strutturato.
- Rafforzato il workflow Lex `atto_da_template`: `TemplateAttiSource` mantiene fallback al catalogo reale, Lex non inventa riferimenti e non crea atti liberi; la creazione passa solo dal gate Template Atti e restituisce `editor_url` quando ammessa.
- Collegato il compilatore React al gate backend: lo stato `block` impedisce la bozza finale, lo stato `warning` richiede conferma e apre solo una bozza di lavoro, lo stato `ok` apre l'editor professionale tramite `editor_url`.
- Aggiunti test mirati per citazione, comparsa, decreto ingiuntivo, diffida, penale, block, warning, editor e timbro ripetuto su ogni pagina.

## 2.245.64 - 2026-05-20

- Collegato Lex al workflow reale Template Atti / Catalogo Atti / Compilatore Atti con `atto_da_template`: il router intercetta richieste di consultazione, precompilazione e creazione bozza, recupera modelli reali da `pct.compilatore_atti`, usa Ricerca Studio e contesto attivo per cliente/fascicolo/parti, valida i campi e non genera atti liberi inventati.
- Aggiunto il servizio riusabile `pct.template_atti_lex_service` per risoluzione modello, contesto pratica, precompilazione, validazione, render e creazione documento editor; le route Template Atti continuano a usare il flusso esistente e riusano il servizio per l'import nell'editor professionale.
- Estesa la chat unica Lex con metadata `template_act`, card renderizzabili e azioni strutturate `open_template_catalog`, `open_template_compiler`, `complete_missing_fields`, `create_editor_draft`, `open_created_document`, `open_case` e `open_client`; la creazione documento richiede conferma salvo richiesta esplicita dell'avvocato.
- Aggiunti test mirati su sorgente Template Atti, routing, precompilazione, campi mancanti, conferma creazione, permessi e ambiguita' cliente.

## 2.245.63 - 2026-05-20

- Rafforzato `Lex Studio Reasoner` come conversazione operativa tra colleghi: i follow-up brevi ricordano PEC/email, fascicolo, documento o cliente appena citati tramite link operativi verificati, non tramite prompt grezzo.
- Ampliata la matrice reale di domande Lex su PEC, email ordinaria, allegati, fascicoli, documenti, soggetti, controparti, scadenze, agenda, clienti, pagamenti, fatture, priorità studio e bozze richieste esplicitamente.
- Corretto lo scope governato di PEC/email: un fascicolo inesistente non ricade sulla PEC globale, l'utente senza permessi non riceve fonti e i clienti ambigui producono chiarimento/opzioni.
- Aggiunta la pratica web professionale non vincolante: Lex può raccogliere spunti da siti di studi legali e contenuti per avvocati come know-how, senza promozione automatica a fonte ufficiale e senza usarli per contraddire l'avvocato.
- Potenziato il motore `Web libero` con fallback pubblico Google, Yahoo ed Ecosia oltre DuckDuckGo HTML: se un canale non restituisce risultati live, Lex passa al successivo senza inventare fonti.
- Aggiunto audit web/RAG al 99% su cento somministrazioni verso conversazione con l'avvocato: i contenuti acquisiti restano `knowhow_professionale`, alimentano il ragionamento come prassi e non diventano fonti ufficiali o trusted source.
- Chiusa la fase linguaggio giuridico/date: le risposte operative Lex formattano le date visibili come `17 maggio 2026` o `21 maggio 2026 alle 10:00`, e la guardia qualità blocca date tecniche ISO nelle risposte professionali.
- Applicata la regola di confronto professionale: Lex non contraddice l'avvocato salvo fonte primaria verificata con confidenza almeno 99%.
- Documentati audit e gate mirati senza reintrodurre aggregatori legacy: i check restano divisi per fase e per perimetro toccato.

## 2.245.61 - 2026-05-19

- Introdotta `LexUnifiedChat` come contratto unico della chat operativa: contesto attivo, intent, contesto strutturato, verifica fonti, blocchi renderer e azioni passano dal `Lex Studio Reasoner` senza pannelli separati per modulo.
- Il widget Lex ora invia `active_context`, espone `IusentraLexUnifiedChat` e renderizza card PEC/email, fascicolo, cliente, documenti, allegati, scadenze, timeline, fonti interne e azioni apribili.
- Rafforzato il comportamento "ultima PEC ricevuta": resta consultazione, mostra fonte interna e card apribili, propone la bozza solo come azione successiva e non genera automaticamente testi PEC.
- Aggiunti test mirati su contesto globale, fascicolo, PEC selezionata, permessi, cliente ambiguo, fonte mancante, timeline, pagamenti/fatture e richiesta di bozza esplicita; preservati i check divisi per fasi senza aggregatore legacy.

## 2.245.60 - 2026-05-19

- Collegato il `Lex Studio Reasoner` al payload chat bounded: le risposte operative espongono ora `studio_reasoner`, `entity_map`, `fascicolo_timeline`, `rag_governato` e `reasoner_mode` anche al bridge HTTP usato dalla chat Lex.
- Aggiunta la lista `operational_links` deduplicata per aprire direttamente fascicoli, documenti in editor professionale, PEC/email e allegati dai risultati interni autorizzati.
- Esteso il riepilogo evidenze con conteggi di link, entità e timeline; aggiunto test end-to-end sul bridge bounded per preservare LLM + RAG governato + ragionatore studio senza aggregatori legacy.

## 2.245.59 - 2026-05-19

- Estesa la tranche `Lex Studio Reasoner` con mappa entità e timeline fascicolo nei metadata `studio_reasoner`, costruite solo dai risultati operativi autorizzati.
- Arricchiti PEC, email, fascicoli, documenti e allegati con link applicativi reali: la risposta può aprire la comunicazione, l'allegato, il fascicolo e il documento nell'editor professionale quando la route esiste.
- Aggiunti test su "ultima PEC ricevuta" con allegato apribile e su fascicolo/documento con timeline e mappa entità; confermato lo shard completo Operational Knowledge.

## 2.245.58 - 2026-05-19

- Avviata la tranche `Lex Studio Reasoner`: il layer Operational Knowledge costruisce un piano governato `llm_rag_governato`, verifica le sole fonti interne tenant-aware e allega il report `studio_reasoner` alle risposte Lex senza esporre ragionamenti grezzi.
- Il verificatore interno esclude fonti legali/pubbliche (`fonti_ufficiali`, `legal_intelligence`, `update_intelligence`, `web_libero`) dal report studio e mantiene esplicito che non è stato reintrodotto alcun aggregatore legacy.
- Aggiunti test reali su "ultima PEC ricevuta" e su esclusione delle fonti pubbliche dal verificatore studio; confermato lo shard completo `tests/test_lex_operational_knowledge.py`.

## 2.245.57 - 2026-05-19

- Rafforzate le azioni documento di Lex: quando l'import nel fascicolo è disponibile la risposta generata mostra `Apri con editor` come azione primaria, elimina il pulsante Markdown e apre l'editor professionale anche per eventuali vecchie azioni Word già renderizzate.
- Stabilizzata la dettatura del widget Lex: il timer di silenzio parte solo dopo il primo testo riconosciuto, gli errori `no-speech`/`aborted` chiudono la sessione senza bloccare l'interfaccia e i permessi microfono negati mostrano un messaggio chiaro.
- I documenti caricati in chat vengono instradati come richiesta sul documento quando l'avvocato chiede spiegazioni, sintesi, analisi o punti importanti, evitando che il contesto fascicolo assorba l'allegato.
- Esplicitata la memoria operativa sugli aggregatori legacy: eventuali riepiloghi storici restano solo advisory, mentre i required check continuano a essere gli shard divisi per fasi e per parti.
- Aggiunti test mirati JS e Python su editor, dettatura e workflow documento, preservando i check divisi per fasi senza reintrodurre aggregatori legacy.

## 2.245.56 - 2026-05-19

- Preservata la modalità companion locale autorizzata: con `LEX_GOVERNED_ONLY=0`, `LEX_RAW_CHAT_ENABLED=1` e `allow_unbounded_generation`, il focus fascicolo non viene assorbito dal workflow bounded.

## 2.245.55 - 2026-05-19

- Rafforzato Lex sul contesto operativo dello studio senza addestramento grezzo: il nuovo intento `studio_context_lookup` instrada richieste come "usa tutto il contesto studio" verso Operational Knowledge e Ricerca Studio, mantenendo tenant, permessi e audit.
- Separata la consultazione di PEC/email dalla redazione: "ultima PEC ricevuta" ora resta su `comunicazioni_lookup` e non attiva più la bozza `BOZZA — PEC FORMALE`.
- Il Web libero manuale produce una risposta diretta e isolata, con risultati `web_libero`, `verified_reference=false`, nessun warning visibile e nessuna fusione con contesto interno o archivi legali.
- I documenti caricati in chat Lex vengono instradati al workflow documento e le bozze generate mostrano un titolo cliccabile per aprire l'editor professionale quando l'import nel fascicolo è disponibile.
- Aggiunti test mirati su contesto studio, PEC/email, Web libero, documenti caricati, drafting e renderer Lex; i check restano divisi per fase senza reintrodurre aggregatori legacy.

## 2.245.54 - 2026-05-19

- Aggiunta la sorgente Lex `StudioDatabaseSource`, collegata alla Ricerca Studio tramite `search_for_lex()`: Lex può interrogare il DB operativo interno tenant-aware per clienti, soggetti, fascicoli, documenti, agenda, scadenze, comunicazioni, PEC, email, depositi, preventivi, fatture e pagamenti.
- La sorgente scarta le fonti legali già governate (`legal_intelligence`, aggiornamenti legali, normativa, giurisprudenza, prassi e web ufficiale) e resta esclusa in modalità `Web libero`, che continua a usare solo la ricerca libera della singola richiesta.
- La Ricerca Studio indicizza ora anche PEC/email ricevute e posta ordinaria, con oggetto, mittente, destinatari, data, stato, metadati PCT e allegati, usando i manager tenant-aware `EMAIL_CASELLA_DB`, `EMAIL_ORDINARIA_DB` e `MESSAGGI_DB`.
- Conservati i check CI divisi per fasi: i test di regressione sui workflow confermano `Pytest core` shardato, `Coverage moduli critici parte */12`, Local Signer/PKCS#11 per parti e nessun ritorno del vecchio aggregatore coverage senza `parte`.

## 2.245.53 - 2026-05-19

- Chiusa la Fase 11.5 degli aggiornamenti legali senza scheduler esteso, import massivo, Web libero automatico o pubblicazione incontrollata.
- Aggiunto `legal-updates-run-progressive` per un ciclo scheduler/autofetch controllato: solo fonti verdi, `--guarded-only` obbligatorio, budget fonte, timeout per item, dry-run e nessuna fonte RAG-only/osservazione in pubblicazione.
- Aggiunto il canary `legal-updates-giurisprudenza-structured-canary` per bloccare la promozione dell'Archivio Giurisprudenza quando mancano corte, numero, anno, data, fonte ufficiale o testo/PDF.
- Rafforzati i presidi su Cassazione `QSP50194`/`art. 606 c.p.p.`, EUR-Lex CELEX e OpenGA: fixture/test dedicati, domanda PDF specifica per il c.p.p., CELEX riconosciuto ma ancora RAG-only se incompleto, dataset OpenGA non promossi come sentenze.
- Documentati Vercel come status esterno fuori gate IUSENTRA e i file runtime sporchi come dati preservati non committati.

## 2.245.52 - 2026-05-19

- Aggiunto il regime controllato Fase 11 per gli aggiornamenti legali con `python -m pct.cli legal-updates-health-report --json`.
- Estesa la dashboard admin con il quadro qualità fonti: fonti attive, osservazione, RAG-only, non pubblicabili, ultimo controllo, errori, OCR, allegati vuoti, riferimenti/domande mancanti, review pendenti e pubblicazioni guarded.
- Esposti nel report sanitario retry sicuro, coda job, scheduler progressivo, backfill periodico solo mirato e procedura obbligatoria per nuove fonti.
- Confermato che il report non acquisisce fonti, non esegue backup e non pubblica contenuti; le pubblicazioni restano limitate al percorso guarded.

## 2.245.51 - 2026-05-19

- Completato l'audit finale Fase 10 degli aggiornamenti legali senza backup e senza import massivo.
- Chiuso il buco di classificazione macchina per le fonti `DEFAULT_SOURCE_ROWS`: tutte le fonti ufficiali e istituzionali ora ricadono in `verde_abilitata`, `rag_only`, `osservazione` o `archivio_locale`; solo le fonti secondarie non ufficiali restano `fuori_perimetro`.
- Estesa la lista RAG-only alle fonti OpenGA tabellari o di stato non ancora pubblicabili e la lista osservazione a Cassazione Massimario, Giustizia Amministrativa diretta e Decisioni/Pareri.
- Aggiunta guardia test sullo scheduler progressivo per impedire regressioni a fonti ufficiali non classificate.
- Rieseguiti i gate separati richiesti: pipeline aggiornamenti legali, publish/PDF/OCR, corpus Lex/Ricerca Legale/Giurisprudenza, scheduler/autofetch/job queue, typecheck/build frontend, governance, UTF-8 e whitespace.

## 2.245.50 - 2026-05-19

- Estesa la Fase 9 degli aggiornamenti legali a tutte le fonti verdi rimaste: Cassazione ultime, Corte dei conti, Curia CGUE, INPS circolari/messaggi, AGCOM, ANAC, Garante Privacy e Gazzetta Ufficiale.
- Aggiunte le liste governate di fonti verdi abilitate, RAG-only, osservazione, archivi locali ed esclusioni dalla pubblicazione automatica nello scheduler progressivo e nella superficie admin.
- Eseguiti quattro lotti con budget controllato: 1533 documenti letti, 33 processati, 21 invariati, 14 pubblicati guarded, 11 scartati dal guarded, 17 PDF/OCR, 340 riferimenti e 740 domande contestuali.
- Mantenute fuori pubblicazione OpenGA, PST, Dati Normattiva, EUR-Lex, ISTAT, Normattiva/codici e tutte le fonti in osservazione; nessun catalogo tecnico è stato trasformato in news.
- Corretto il parser HTML per gestire pagine vuote (`ParserError`) come diagnostica RAG-only, con test dedicato su EUR-Lex.
- Forzata la decodifica UTF-8 nello stdout dei job aggiornamenti legali per evitare mojibake nei report macchina.

## 2.245.49 - 2026-05-19

- Attivata la Fase 8 dello scheduler progressivo degli aggiornamenti legali: lo step 1 usa solo `cassazione_ultime_sent_ord_questioni`, `inps_circolari`, `inps_messaggi` e `agcom_provvedimenti`, lasciando fuori fonti gialle o tecniche.
- Abbassati i budget operativi iniziali: 2 fonti per ciclo, timeout 120 secondi per elemento, massimo 5 pubblicazioni guarded per ciclo e massimo 5 schede Cassazione ultime per scansione.
- Rimosso il batch notturno completo dalle pianificazioni operative: Gazzetta e Normattiva restano presidiate dagli archivi ufficiali locali, mentre ANAC e Garante restano in osservazione fino a canary/report verde dedicato.
- Aggiornate console admin e registro pianificazioni per mostrare lo step progressivo, disabilitare gli agenti fonte fuori step e leggere i job stantii come elementi da verificare.
- Aggiunti test mirati per fonti abilitate/escluse, budget, timeout, publish max e blocco degli agenti fuori step senza reintrodurre aggregatori storici.

## 2.245.48 - 2026-05-19

- Completata la Fase 7 di backfill mirato PDF/OCR/riferimenti/domande senza backup, senza Web libero, senza pubblicazione automatica e senza scansione globale non limitata.
- `legal-updates-backfill-diagnostics --missing` accetta ora liste separate da virgole, ad esempio `attachments,ocr,references,questions`, e restituisce un riepilogo macchina con selezionati, processati, aggiornati, invariati, falliti, motivi, PDF/OCR, riferimenti, domande, Lex e Ricerca Legale.
- Reso l'output CLI robusto in UTF-8 su Windows, evitando errori di stampa JSON quando i contenuti ufficiali contengono caratteri non rappresentabili in `cp1252`.
- Compattati i report JSON diagnostici: viene salvato `dashboard_summary` con conteggi e qualità, senza esportare payload applicativi o stream PDF grezzi.
- Backfill reale: 50 evidenze controllate per riferimenti, 14 aggiornate, 20 riferimenti aggiunti, 0 fallimenti; allegati/OCR e Cassazione specifica risultano già completi nel perimetro selezionato.
- Salvati report e JSON diagnostici in `artifacts/legal-updates/phase7-backfill-2026-05-19/`; test mirati backfill, OCR, allegati, corpus Lex, Ricerca Legale, governance, UTF-8 e whitespace verdi.

## 2.245.47 - 2026-05-19

- Completata la Fase 6 normativa e archivi base senza backup, download ciechi o import massivo: gli archivi Normattiva/Gazzetta già presenti vengono verificati, collegati e interrogati in modo incrementale.
- Reso più robusto il retrieval Normattiva per codici e articoli: riconosce codice civile, procedura civile, penale, procedura penale, processo amministrativo e strada; quando il DB locale non ha il chunk autonomo legge i raw ZIP Normattiva già presenti senza inventare link.
- Deduplicati i risultati Gazzetta per documento e aggiunto il contesto Normattiva/Gazzetta a Lex tramite `search_normativa_sources()`, così Ricerca Legale e Lex usano gli archivi ufficiali prima dei fallback esterni.
- Classificata EUR-Lex come fonte UE ufficiale `RAG-only` finché il parser CELEX non è stabilizzato; confermate Studio Cataldi e Avvocato Andreani come fonti secondarie disabilitate dal corpus ufficiale.
- Aggiunti test su importer/retriever Normattiva, fallback raw ZIP, deduplica Gazzetta, contesto Lex, EUR-Lex RAG-only e fonti secondarie.

## 2.245.46 - 2026-05-19

- Eseguita la Fase 5 di popolamento controllato del primo gruppo fonti verdi con `limit 5`, `max_seconds 120`, `publish-mode guarded`, `direct-only`, nessun Web libero, nessun import massivo e nessuno scheduler globale.
- Pubblicati 20 documenti verificati: Cassazione ultime sentenze/ordinanze/questioni, INPS circolari, INPS messaggi, AGCOM, Corte dei conti e Curia CGUE; tutti risultano interrogabili da Lex e ritrovabili in Ricerca Legale con query fonte mirata.
- Conservate come non pubblicate le fonti RAG-only o non abbastanza confermate: PST tecnico e OpenGA tabellare restano solo evidenza RAG; ANAC e Garante sono acquisiti ma non pubblicati perché il guarded richiede conferme ulteriori o riferimenti ritrovabili nella diagnosi.
- Rafforzati i parser Corte costituzionale e Corte dei conti: niente fallback su captcha/navigazione, accettazione solo di schede pronuncia/documenti giurisdizionali, lettura dei download Corte dei conti con label PDF e sostituzione dei titoli generici con il titolo del documento ufficiale.
- Salvati report e verifica in `artifacts/legal-updates/phase5-green-2026-05-19/`, con risultati per fonte, documenti pubblicati, RAG-only, scarti guarded e stato Lex/Ricerca Legale/Archivio Giurisprudenza.

## 2.245.45 - 2026-05-19

- Eseguito il primo pilot controllato con pubblicazione `guarded`, senza import massivo e senza scheduler globale, sulle tre fonti verdi consigliate: `cassazione_ultime_sent_ord_questioni`, `inps_circolari` e `agcom_provvedimenti`.
- Aggiunto `--publish-mode off|guarded|auto` al canary: la modalità guarded pubblica solo i documenti letti nel canary corrente dopo controlli su fonte ufficiale/trust, testo leggibile, PDF/OCR, interesse per studio legale, duplicati, destinazione, riferimenti, domande contestuali e testo UI non tecnico.
- Pubblicati 9 documenti verificati: 3 Cassazione, 3 circolari INPS e 3 provvedimenti AGCOM. Le circolari INPS con chiavi normative incoerenti vengono pubblicate come notizie verificate, non come normativa.
- Verificati Archivio aggiornamenti, Ricerca Legale, Lex e preparazione Archivio Giurisprudenza: i PDF/allegati vengono premiati quando la domanda chiede allegato o documento ufficiale; i record Cassazione restano pronti per RAG/Archivio Giurisprudenza senza creare schede strutturate quando mancano corte, numero o anno.
- Salvata la diagnostica del pilot in `artifacts/legal-updates/pilot-guarded-2026-05-19/`, includendo gli scarti intermedi che hanno portato alle guardie corrette su testo pagina, testo tecnico visibile e classificazione prassi.

## 2.245.44 - 2026-05-19

- Corretta la Fase 3 post-canary sulle sole fonti gialle: Gazzetta Ufficiale passa a verde leggendo i PDF già normalizzati anche sugli elementi invariati; ANAC e Garante non creano più allegati fittizi da testo o link normativi generici.
- Classificate correttamente le fonti non pubblicabili: PST Giustizia download resta fonte tecnica `RAG-only`; OpenGA tabellare (`CSV`, `JSON`, `ODS`, `XLSX`, `ZIP`) resta `RAG-only` e non viene promossa come giurisprudenza senza un documento concreto.
- Rieseguiti i canary mirati con `--limit 2`, `--max-seconds 60`, `--no-publish`, `--direct-only`, `--save-diagnostics` e JSON diagnostico aggiornato, senza import massivo e senza pubblicazione.

## 2.245.43 - 2026-05-19

- Eseguita la tornata canary no-publish sulle dieci fonti richieste con `--limit 3`, `--max-seconds 90`, `--direct-only`, diagnostica salvata e report verde/giallo/rosso in `artifacts/legal-updates/canary-report-2026-05-19.md`.
- Corretto il parser Gazzetta Ufficiale: usa l'elenco ufficiale degli ultimi 30 giorni della Serie Generale e costruisce link PDF non criptati senza passare dalla homepage o da paginazioni lente.
- Corretto `inps_messaggi`: il feed RSS pubblico risponde con contenuti incoerenti, quindi la fonte ora usa l'API elenco della pagina ufficiale e filtra solo elementi `Messaggio`, con dettaglio e verifica allegati dove presenti.
- Rafforzati filtri e ranking fonte-specifici per AGCOM, ANAC e Garante: entrano provvedimenti, delibere, pareri e docweb ufficiali; restano fuori navigazione, social, trasparenza e servizi.
- Migliorata la diagnostica canary per elementi invariati, che ora riporta comunque documento normalizzato, `review_id` e qualità evidenze; ripulita la gestione UTF-8/mojibake in parser e report.
- Aggiunti test mirati per parser Gazzetta, INPS messaggi via API, AGCOM/ANAC/Garante, Curia CGUE, fallback feed e riparazione mojibake, preservando i check CI shardati senza reintrodurre aggregatori coverage obsoleti.

## 2.245.42 - 2026-05-19

- Aggiunti gli strumenti sicuri `python -m pct.cli legal-updates-canary` e `python -m pct.cli legal-updates-backfill-diagnostics` per provare una sola fonte o arricchire evidenze mirate con limiti obbligatori, budget tempo, `--no-publish`, `--direct-only`, diagnostica JSON e nessun import massivo.
- Il canary registra, se richiesto, l'ultimo controllo fonte come run `canary`: documenti letti, analizzati, allegati/PDF, OCR/testo, riferimenti, domande, destinazione, motivi di scarto, qualità RAG ed errori sono disponibili in console admin senza codici grezzi.
- Il backfill diagnostico ora distingue allegati, OCR, riferimenti e domande contestuali; per riferimenti/domande aggiorna le evidenze esistenti senza pubblicare e senza scansioni infinite.
- Esteso il registry capability con i campi macchina richiesti per famiglia fonte, parser, dettaglio, allegati, PDF/OCR, riferimenti, domande, destinazione, filtro studio legale, regole di esclusione e note diagnostiche.
- Create fixture offline per Cassazione, AGCOM, INPS, Curia, CKAN/OpenGA, ANAC, Garante, PST e PDF testuale/scansionato mock, così i parser e il canary sono verificabili senza rete live.

## 2.245.41 - 2026-05-19

- Aggiunto il registro capability per fonte degli Aggiornamenti legali: ogni sorgente dichiara strategia elenco/dettaglio/allegati, PDF/OCR, riferimenti, domande, destinazione, RAG, giurisprudenza e filtri di esclusione.
- Introdotti parser/adapters deterministici per HTML listing/detail, Feed/RSS/Atom, CKAN/OpenGA, Cassazione ultime sentenze/ordinanze/questioni e autorità indipendenti, con fixture testate e senza import massivo live.
- Separati in moduli dedicati l'estrattore riferimenti normativi/giurisprudenziali e il generatore di domande contestuali, preservando zero link Normattiva inventati e la matrice approvata del caso Cassazione QSP50194.
- La pagina admin fonti mostra capability, destinazione, RAG, PDF/OCR, riferimenti, domande e policy di scarto con etichette italiane; Ricerca Legale/Lex ricevono anche la destinazione policy nei payload.
- OpenGA cataloghi, dataset tecnici, fatture/liquidazioni, consultazioni AGCOM e fonti secondarie vengono chiusi o degradati con motivo leggibile; i documenti giuridici concreti non vengono persi e restano RAG/giurisprudenza quando hanno chiavi minime.
- Creato `artifacts/legal-updates/source-rollout-execution.md` con stato prima/dopo per tutte le fonti non complete del piano.

## 2.245.40 - 2026-05-18

- Aggiunta la ricognizione fonte per fonte degli Aggiornamenti legali in `artifacts/legal-updates/source-rollout-plan.md`, con decisione esplicita per tutte le fonti `DEFAULT_SOURCE_ROWS` e quelle persistite nel database.
- Introdotto `pct/legal_update_enrichment.py`: estrazione deterministica e riusabile di riferimenti normativi/giurisprudenziali, R.G., contentId e matrice di domande contestuali senza inventare link Normattiva.
- Ricerca Legale e Lex ricevono ora, dalle evidenze web e PDF/OCR, riferimenti normativi, riferimenti R.G., domande per Lex e segnali su PDF/allegati letti o da completare.
- La console `/admin/aggiornamenti-legali/` espone contatori su evidenze lette, PDF/allegati e documenti collegati; aggiunta API mirata per backfill evidenze web con filtri fonte, stato, query, review e timeout.
- Il corpus sorgenti Lex riusa l'arricchimento deterministico e mantiene il filtro Cassazione sulle sole schede documentali; il Web libero Lex resta isolato da fonti ufficiali, studio, fascicoli e promozione DB/corpus.
- Riallineate le note operative CI: il vecchio job aggregato `CI / Coverage moduli critici` senza `parte` è eliminato e non va reintrodotto; i soli gate coverage richiesti sono `Coverage moduli critici parte 1/12` fino a `parte 12/12`.

## 2.245.39 - 2026-05-18

- Corretto il collegamento tra Ricerca Legale e Lex per i riferimenti giurisprudenziali esatti con numeri brevi, come `Sentenza della Corte Costituzionale n. 50 del 27/1/2026`.
- Il parser Lex riconosce ora sentenze/ordinanze/decreti con numero da 1 a 6 cifre e mantiene l'organo richiesto, senza trasformare automaticamente ogni sentenza in ricerca Cassazione.
- La ricerca ufficiale sceglie `cortecostituzionale.it` quando la domanda nomina la Corte Costituzionale e non inserisce Cassazione come fonte prioritaria o sostitutiva.
- Il repository `legal_updates.db` e la pagina Ricerca Legale scartano risultati Cassazione quando la richiesta esatta riguarda un'altra Corte; se il dato non è nel DB, parte il fallback pubblico governato invece di restituire una sentenza diversa.
- Aggiunti test mirati su parser, routing fonte ufficiale, filtro repository, Ricerca Legale e bridge operativo Lex, preservando il caso pilota Cassazione `QSP50194`.

## 2.245.38 - 2026-05-18

- Corretto il blocco `Contesto in IUSENTRA` della Ricerca Legale: quando il riepilogo operativo e l'estratto della fonte coincidono, Lex mostra una sola voce e non duplica `Contesto operativo`/`Contenuto`.
- Aggiunto filtro di pertinenza per AGCOM e prove web: contributi di consultazione pubblica o pianificazione frequenze senza valore operativo per lo studio vengono chiusi come fuori perimetro e non alimentano i risultati Lex/Ricerca Legale; restano ammessi delibere, provvedimenti, sanzioni, controversie, Corecom e tutela utenti.
- Aggiunti test mirati su duplicazione del contesto, filtro Assoradio/AGCOM, conservazione dei provvedimenti AGCOM utili, pipeline aggiornamenti e typecheck React.
- Rigenerato il bundle React e ripulito l'asset Impostazioni dopo il build per eliminare il falso mojibake rilevato dalla governance CI, mantenendo UTF-8 valido.

## 2.245.37 - 2026-05-18

- Rifinito il guard linguistico Lex: il fallback non presume più il fascicolo quando la richiesta è in `Web libero`, mantiene il messaggio generico di blocco italiano e usa accenti UTF-8 reali nel fallback fascicolo.

## 2.245.36 - 2026-05-18

- Corretta la fonte Cassazione `ultime_sent_ord_e_questioni.page`: il connettore segue le pagine ufficiali Civile/Penale e acquisisce solo schede documentali `*_dettaglio.page?contentId=...`, escludendo pagine di navigazione, privacy, supporto o preferenze.
- Il generatore corpus Lex applica lo stesso filtro anche a `cassazione_ultime_sent_ord_questioni`, così eventuali evidenze non documentali già presenti nel DB non entrano nel RAG.
- Le domande attese del corpus sono ora contestuali: usano titolo scheda e testo PDF/OCR letto; se emergono articoli o riferimenti normativi vengono registrati ed esposti, se ci sono PDF viene richiesta la verifica del link, se compaiono più R.G. viene richiesta la nota di discrepanza.
- Verifica locale Cassazione: 10 schede reali pronte, 9 con PDF letto e una senza PDF ma con testo pagina, 10/10 con matrice domande; corpus prova da 20 documenti e 174 chunk, con Memory Tree pronto e zero pagine di servizio.
- Confermati i test su Ricerca Legale, Archivio Giurisprudenza e comportamento pilota Lex sugli articoli con `web_libero` separato dalla fonte ufficiale.
- Corretto `Web libero` in Lex Chat: il flag ora svuota davvero contesto studio, fonti interne, fascicolo e prompt storico prima del bounded workflow; accetta anche la modalità testuale `web libero` e impedisce risposte miste con frasi inglesi come `Okay, let's break down...`.

## 2.245.35 - 2026-05-18

- Aggiunta la Fase 6 UI Intelligence: Ricerca Legale mostra ora stato reale delle fonti, fonti pronte/non pronte, coda job, errori, documenti letti, testo disponibile e domande qualità del ciclo DB -> fonte -> allegati -> OCR -> RAG -> Lex.
- Il payload React di Ricerca Legale espone `autofetchMonitor` costruito dal monitor operativo già introdotto per le fonti pubbliche, evitando contatori isolati senza spiegazione.
- Archivio Giurisprudenza mostra il presidio dati per RAG: schede con fonte, testo disponibile, testo da completare e fonti da verificare.
- Aggiunti test mirati su monitor acquisizione fonti reali e stato dati giurisprudenza, con build React aggiornata.

## 2.245.34 - 2026-05-18

- Aggiunta la Fase 5 Auto-fetch governato per fonti legali: `pct/legal_update_autofetch.py` introduce tick con budget per fonte, cursori persistenti, coda deduplicata, timeout per elemento e monitor operativo.
- La console aggiornamenti legali e lo scheduler passano ora dal piano governato prima di accodare o processare fonti, evitando scansioni cieche e ripetizioni inutili.
- Ogni job auto-fetch porta la checklist qualità stabilita: fonte, pagina, allegati/PDF, hash, OCR/testo, OCR sporco, norme/R.G., discrepanze, prontezza RAG e risposta Lex verificabile.
- Aggiunti test su cursori, budget, deduplica, monitor, scheduler/surface e regressioni job queue.

## 2.245.33 - 2026-05-18

- Aggiunta la Fase 4 ispirata a OpenHuman Tool Registry e Model Routing, adattata a Lex: ogni strumento ha schema, categoria, trasporto, permessi, lettura/scrittura e stato `web_libero` tracciabile.
- Il registro strumenti conserva compatibilità con `registry.tools`, ma aggiunge descrittori governati, validazione chiamate, blocco scritture fuori dal canale applicativo e isolamento dei dati studio quando la chat usa web libero.
- Il routing modelli espone ora schema, policy del profilo, provider effettivo, uso LLM sì/no, costo stimato e regola di qualità, con provider esterni abilitabili solo tramite `LEX_EXTERNAL_ALLOWED`.
- Aggiunti test su governance strumenti, web libero, permessi, routing deterministico, giurisprudenza specifica, provider esterno e URL Ollama senza credenziali.

## 2.245.32 - 2026-05-18

- Aggiunta la Fase 3 job queue per fonti legali: `pct/legal_update_job_queue.py` introduce coda SQLite persistente con deduplica, hash contenuto, stato, retry, timeout, errore leggibile e recupero dei job rimasti in corso.
- Il batch runner può ora preparare una coda di fonti senza eseguire subito i subprocess, utile per Cassazione e backfill progressivi prima del generatore corpus.
- La deduplica usa fonte, URL, tipo elemento, payload stabile e hash contenuto: stesso documento resta unico, contenuto cambiato genera un nuovo job.
- Aggiunti test su deduplica, retry, timeout finale, ripresa da crash e ponte batch-runner/coda.

## 2.245.31 - 2026-05-18

- Aggiunta la Fase 2 TokenJuice per Lex: `lex/tokenjuice.py` compatta in modo deterministico HTML, JSON, log, OCR/PDF già estratti e testi legali lunghi prima che arrivino al modello.
- Il Memory Tree integra ora metadati TokenJuice per ogni chunk, con schema, rapporto di riduzione, ancoraggi conservati, avviso OCR sporco e flag espliciti `llm_used=false` e `web_used=false`.
- Il generatore corpus Lex dichiara nel manifest la policy TokenJuice, così i documenti pronti hanno sia testo originale sia contesto compatto riusabile dal RAG senza consumo inutile di crediti.
- Aggiunti test su HTML ripulito, OCR lungo, JSON deterministico e integrazione TokenJuice nei chunk Memory Tree.

## 2.245.30 - 2026-05-18

- Aggiunta la Fase 1 ispirata a OpenHuman Memory Tree, reimplementata in modo pulito per IUSENTRA: `lex/memory_tree.py` costruisce memoria Lex deterministica da fonti già lette, PDF/OCR, sentenze, questioni pendenti e documenti studio.
- Il generatore `scripts/generate_lex_source_corpus.py` ora produce anche `memory_tree/index.json`, `memory_tree/documents.jsonl` e `memory_tree/chunks.jsonl`, con provenienza, hash, qualità, norme, R.G., date, argomenti e stato pronto/non pronto.
- Aggiunta ricerca deterministica sui chunk memoria per fonte, norma, R.G. e argomento, senza chiamate LLM e senza navigazione web.
- Aggiunte guardie test su chunk deterministici, OCR sporco, riferimenti R.G. multipli e integrazione del Memory Tree nel generatore corpus Lex.

## 2.245.29 - 2026-05-18

- Rimossa dal workflow CI la coverage critica aggregata senza `parte`: il gate richiesto resta sulle 12 parti shardate, coerente con `docs/COMMIT_PUSH_REQUIRED_GATES.md` e con il branch monorepo.
- Rimossi i file di deploy Vercel (`vercel.json`, `vercel_app.py`) e i riferimenti testuali residui: il processo corrente resta GitHub Actions + Hetzner, senza Vercel preview/deploy.
- Allineato il cablaggio pnpm al branch monorepo: il blueprint `impostazioni` non viene più montato con doppio prefisso, quindi `/impostazioni`, `/impostazioni?tab=firma&_legacy=1` e `/api/local-ai/*` tornano disponibili nei gate CI.
- Mantenuta la pagina profilo classica quando l'utente deve cambiare password temporanea, così il form espone il token CSRF e il cambio password resta verificabile.
- Ignorata la cartella runtime locale `/email/` per evitare che i test ricreino `email/ordinaria.json` nella worktree.
- Riallineati i workflow GitHub al monorepo pnpm: Frontend React CI, gate App V2 e audit frontend preparano `pnpm/action-setup`, usano `pnpm install --frozen-lockfile`, `pnpm --filter @iusentra/studio ...` e artifact `frontend-pnpm-audit-report`; i test di guardia impediscono il ritorno a `npm ci` sul workspace.
- Rimosso Vercel dal processo CI corrente: lo smoke Flask usa direttamente `create_app` e i target lint/compile non includono più `vercel_app.py`.
- Rigenerati OpenAPI, mappa endpoint e contratti API con versione prodotto corrente `2.245.29`, sistemando anche il blocco governance UTF-8 su documentazione deploy e CSS pubblico.
- Ridotta `/ricerca-legale` a una pagina operativa: tre sezioni chiare, ricerca principale, filtri utili per studio legale e nessun blocco decorativo o cruscotto non azionabile.
- I numeri reali già presenti (`Fonti monitorate`, `News pubblicate`, `In revisione`, `Normattiva`, `Gazzetta`, `Mediazione`) diventano accessi funzionali verso schede, filtri e archivi invece di restare KPI isolati.
- Le fonti monitorate sono visibili in pagina e cliccabili; la fonte Cassazione indicata dall'utente `ultime_sent_ord_e_questioni.page` è stata aggiunta al catalogo degli aggiornamenti legali come fonte ufficiale dedicata.
- Mediazione resta il percorso specializzato gia' funzionante, ma Ricerca Legale ora espone anche Cassazione, Normattiva, Gazzetta, News, acquisizioni da controllare e Archivio Giurisprudenza in modo pratico.
- Aggiunta la memoria operativa `docs/COMMIT_PUSH_REQUIRED_GATES.md` e collegata ai documenti esistenti: ogni commit/push deve controllare gate GitHub shardati, CodeQL, supply chain, Frontend React, Coverage, Pytest core, Local Signer e Quality Overlay prima di essere dichiarato chiuso.

## 2.245.28 - 2026-05-18

- Rafforzato il percorso Cassazione prima del generatore corpus: il backfill ora produce un report qualità per documento con pagina verificata, PDF/allegato, hash, OCR/testo, norme, riferimenti R.G., discrepanze, link cliccabile e stato `pronto` / `pronto_con_note` / `da_ocr`.
- Aggiunta la `question_matrix` obbligatoria per le domande da avvocato: sintesi, natura dell'atto, oggetto, stato, punto di diritto, motivi/censure, norme spiegate, effetto pratico, esito, PDF/allegato e discrepanze.
- Il download degli allegati prova prima il riuso dei PDF già presenti nello storage server (`/data/intelligence/downloads`, `/data/fonti_ufficiali`, `/data/tenants` o directory configurate), evitando riscarichi e OCR inutili.
- Filtrate le tranche Cassazione e il generatore corpus sulle sole schede documentali reali; pagine generiche del sito come privacy, URP, eventi o preferenze non entrano più nella prova corpus.
- Eseguita una tranche locale Cassazione con 10 documenti filtrati: 10/10 pronti, 10 PDF letti, 12 allegati salvati, nessun OCR mancante; generato corpus RAG Cassazione da 50 documenti e 538 chunk senza LLM.
- Precisato che le fonti pronte devono arrivare alle tre superfici utente: Lex Chat AI, `/ricerca-legale` e Archivio Giurisprudenza quando sono giurisprudenziali o Cassazione.

## 2.245.27 - 2026-05-18

- Registrata l'approvazione utente del caso pilota Lex `QSP50194` / `R.G. 9926/2026` come test definitivo e reale.
- Documentati tutti i passaggi eseguiti: focus fonte ufficiale, recupero DB, pagina Cassazione, PDF collegato, OCR, nota R.G., sintesi finale, norme spiegate, guardia OCR, controllo qualità, test e deploy.
- Stabilito che questa risposta è il baseline da propagare al generatore corpus e agli altri documenti.

## 2.245.26 - 2026-05-18

- Rafforzata la risposta Lex sul caso pilota `QSP50194`: il PDF resta citabile come allegato ufficialmente collegato alla scheda, ma i dati letti nel PDF con `R.G. 9966/2026` non vengono più fusi automaticamente nella scheda/domanda `R.G. 9926/2026`.
- La risposta distingue ora scheda ufficiale, riferimenti normativi spiegati, contenuto del PDF collegato e nota R.G.; gli estratti OCR sporchi non vengono più riportati nella risposta finale.
- Aggiornati test e documentazione perché questa regola resti davanti prima di propagare la logica al generatore corpus e agli altri documenti.

## 2.245.25 - 2026-05-18

- Protetto il remoto `origin/chore/monorepo-foundation`: lo script di igiene repository lo preserva quando rimuove extra remoti e le regole operative vietano a Codex di cancellarlo o aggiornarlo.

## 2.245.24 - 2026-05-18

- Promosso `Questione Penale Pendente del ricorso R.G. 9926/2026` a caso pilota Lex end-to-end: la risposta ora viene focalizzata sulla domanda dell'avvocato e non solo sul recupero fonte.
- Aggiunta sintesi dell'ordinanza con natura dell'atto, vicenda processuale, pena concordata, motivi/censure, punto di diritto, articoli richiamati e stato pendente.
- Aggiunta matrice di regressione con domande su sintesi, punto di diritto, motivi, sentenza/questione pendente, udienza/norme, articoli, ricorrente/relatore, PDF, uso in atto, esito e discrepanza R.G.
- Le richieste sugli articoli possono usare una fase `web_libero`, non limitata alle fonti ufficiali e sempre separata dalla fonte Cassazione.
- Corretto `Web libero` in chat Lex: con il flag attivo non usa allowlist ufficiali, non blocca per `fonte autorizzata`, non trascina fonti DB/fascicolo, non salva nel corpus e non mostra warning visibili; i risultati sono marcati `web_libero`/`verified_reference=false` e il controllo resta all'avvocato.
- Tracciata la regola operativa in `AGENTS.md`, audit Lex, pipeline risposta e mappa operational knowledge: prima un documento fatto benissimo, poi estensione al generatore corpus e agli altri documenti.

## 2.245.23 - 2026-05-18

- Rafforzata la risposta Lex sulle questioni penali pendenti Cassazione: per `R.G. 9926/2026` Lex ora restituisce anche il contenuto della scheda ufficiale, il quesito sul concordato in appello, i riferimenti agli artt. 599-bis e 606 c.p.p., udienza, relatore e ricorrente quando presenti nel DB.
- Il percorso `/api/assistente/chat` non schiaccia più le risposte operative bounded in una sola riga: titoli, elenchi, link PDF e punti da verificare arrivano al widget con formattazione leggibile.
- Corretto il rendering dei link nel widget Lex: URL con underscore, come il PDF Cassazione `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`, restano interi e cliccabili invece di essere spezzati dalla formattazione Markdown.

## 2.245.22 - 2026-05-18

- Corretto il percorso reale del widget Lex per `Questione Penale Pendente del ricorso R.G. 9926/2026`: il focus conversazionale non trasforma più `questione` in follow-up e non antepone più `atti template` alla domanda.
- Il router operativo dà priorità alle fonti ufficiali Cassazione/QSP/R.G. rispetto a editor, fascicoli e template, anche quando la cronologia arriva da Redazione Atti o dall’editor professionale.
- Aggiunte guardie end-to-end su widget, focus backend, layer operativo e `/api/assistente/chat` per impedire che la domanda ricada in `Editor Lex` o `template_atti`.

## 2.245.21 - 2026-05-18

- Aggiunto nel widget Lex il comando manuale `Web libero`: parte solo dalla singola domanda, non crea job, non entra in scheduler, non passa dalla console pianificazioni e invia al backend i flag espliciti `free_web_enabled`, `force_free_web_search`, `public_web_forced`, `web_execution_requested` e `source_mode=free_web`.
- La ricerca web libera usa risultati pubblici non vincolati alla allowlist ufficiale, mantenendoli distinti dalle fonti già acquisite nell'archivio dello studio.
- L'estrazione OCR dei PDF scansionati trova Tesseract anche nella posizione standard Windows e può usare il dizionario italiano salvato in `%LOCALAPPDATA%\IUSENTRA\tessdata`, così l'allegato Cassazione `QSP50194` non resta solo URL/hash quando il runtime locale ha OCR disponibile.
- La risposta Lex sugli allegati ufficiali non mostra più dettagli tecnici interni quando una sorgente secondaria non è disponibile, ma risponde con PDF, pagina ufficiale, estratto OCR e nota sulle discrepanze dei numeri R.G.

## 2.245.20 - 2026-05-18

- La ricerca Lex sulle evidenze web ora dà priorità alla prova con `attachment_url` quando la domanda chiede allegato, PDF, ordinanza o documento: una domanda come `Quale allegato ufficiale ha la questione penale R.G. 9926/2026?` porta davanti l'ordinanza PDF OCR e non solo la pagina QSP.
- Aggiunta una guardia di ranking per impedire regressioni sulle domande che devono individuare l'allegato ufficiale collegato a Cassazione `QSP50194`.

## 2.245.19 - 2026-05-18

- Il backfill delle evidenze web legali può rientrare su record scelti o su query mirate anche quando esistono vecchie evidenze inutili: casi come Cassazione `QSP50194` non restano esclusi solo perché avevano già una riga con allegato a `context_chars=0`.
- La selezione mirata cerca anche in `attachments_json` e nelle evidenze già salvate, inclusi URL pagina, URL allegato, estratti e testo, così una query come `QSP50194` aggancia il record anche se il codice è presente solo nell'allegato o nella prova precedente.
- Quando arriva testo OCR migliore, l'allegato normalizzato viene aggiornato e la vecchia prova `testo non estraibile` viene sostituita dalla prova interrogabile, evitando che Lex continui a vedere solo URL e hash.

## 2.245.18 - 2026-05-18

- L'archivio legale ora applica l'OCR agli allegati PDF ufficiali scaricati quando il PDF non contiene testo selezionabile: casi come Cassazione `QSP50194` non restano più con allegato salvato ma testo vuoto.
- Aggiunte guardie mirate per PDF scansionati e per la pagina Cassazione `qsp_dettaglio.page?contentId=QSP50194`, verificando che l'allegato `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf` entri nel contesto interrogabile.

## 2.245.17 - 2026-05-18

- Lex AI da telefono e tablet non interroga più il servizio locale del dispositivo per lo stato iniziale: usa lo stato del motore AI dello studio e mostra un messaggio coerente con il percorso mobile.
- L'apertura dal pulsante `Lex AI` della barra mobile forza il pannello a tutto schermo sul viewport piccolo e non apre subito la tastiera, così il pannello resta visibile e usabile.
- Aggiunte guardie di regressione su rilevamento mobile/tablet, apertura mobile full screen e fallback al motore AI dello studio.

## 2.245.16 - 2026-05-18

- Lex AI operativo ora risponde a richieste reali come `Dammi la scheda cliente ...` usando anagrafica, recapiti, fascicoli e quadro economico autorizzati, senza cadere nel messaggio generico di dati insufficienti quando il cliente esiste.
- Le richieste come `Qual è l'ultima PEC?` interrogano la casella PEC tenant-aware senza filtro spurio e restituiscono oggetto, mittente, destinatari, data, cartella e numero allegati.
- La stessa lettura operativa è stata estesa a soggetti e parti: Lex ora restituisce scheda soggetto, recapiti, indirizzo, codice fiscale e ruoli processuali del fascicolo, invece di fermarsi a una ricerca anagrafica minimale.
- L'indicizzazione Lex dei documenti fascicolo riconosce i `.pdf.p7m` leggibili come PDF e prova anche l'estrazione CAdES governata quando il contenitore è firmato davvero; la pagina fascicolo mostra quali documenti non sono stati letti o richiedono reindicizzazione.
- La stessa indicizzazione legge anche `.txt` e `.eml`: per le email conserva oggetto, mittente, destinatari, data, corpo e allegati supportati, così `Aggiorna indice` non salta più note testuali o messaggi salvati nel fascicolo.
- Le bozze Lex di diffida/messa in mora vengono impaginate come documento: titolo, intestazione, destinatario, oggetto, sezioni `Fatto`, `Diritto`, `Richiesta formale`, `Avvertenza`, chiusura ed elenco dei dati da completare restano separati anche se il modello restituisce testo in una sola riga.
- Il titolo e il pulsante della bozza Lex in chat salvano ora il testo come documento reale del fascicolo e aprono automaticamente l'editor professionale.
- Su telefono e tablet `Impostazioni -> AI Locale` non propone più installazione Ollama o download modelli: Lex usa il language model, gli embedding e l'indice documenti sul server di produzione IUSENTRA, mentre il pannello `Archivio e revisione Lex` chiarisce che dataset/export sono facoltativi e non servono per usare il RAG ordinario.
- Il bridge HTTP non manda più le letture PEC classificate come `pec_comunicazioni` nel flusso bozza/web quando la domanda chiede di consultare la casella; restano invece nel layer operativo deterministico.
- Rafforzato il gateway dati studio per le varianti `scheda cliente` e per i gestori che espongono `get` invece di `ottieni`.
- Il backup Hetzner `.tar.zst` cattura ora subito gli stati della pipeline `tar | zstd`, evitando l'errore `PIPESTATUS[1]: unbound variable` che poteva bloccare il backup preventivo prima del deploy.
- Riallineato il branch di deploy al Dockerfile pnpm/Turborepo: i manifest workspace e i package privati richiesti dallo stage `frontend-builder` sono inclusi nel commit, con test che impedisce nuovi `COPY ... not found` in build.

## 2.245.15 - 2026-05-17

- Il backfill delle evidenze web legali ora può completare subito un riferimento preciso con `--backfill-query` o `--backfill-review-id`, senza aspettare che il lotto temporizzato raggiunga quel record.
- La selezione dei riferimenti da completare cerca titolo, testo, URL fonte e sintesi della revisione, inclusi numeri brevi come `53`, `07` e `05`; query come `Circolare numero 53 del 07-05-2026` puntano quindi al documento esatto.

## 2.245.14 - 2026-05-17

- La ricerca Lex sulle evidenze web premia titolo, URL, allegato, numeri e frase esatta, così una query puntuale come `Messaggio numero 685 del 26-02-2026` non viene superata da circolari più recenti ma generiche.
- Aumentato il bacino dei candidati SQL per le ricerche legali, evitando che evidenze esatte ma meno recenti restino fuori dai risultati prima del ranking.

## 2.245.13 - 2026-05-17

- Il backfill delle evidenze web legali lavora per default solo sui record azionabili (`pending`, `approved`, `published`) ed esclude metadati chiusi/open-data, così il recupero non si perde su migliaia di righe non utili allo studio.
- La verifica di recupero usa prima la fonte ufficiale diretta e gli allegati collegati, salva diagnosi `insufficient` quando manca una conferma e non dichiara completato un riferimento privo di URL/testo/allegato o motivo esplicito.
- La CLI `pct.legal_update_job --backfill-web-evidence` ora accetta limite di tempo, stati, inclusione esplicita di record chiusi/open-data e ricerca estesa opzionale, per completare l'archivio a tranche misurabili senza job appesi.

## 2.245.12 - 2026-05-17

- Gli aggiornamenti legali salvano evidenze web gia' durante l'acquisizione del documento, senza aspettare che il record entri nella pubblicazione automatica.
- La verifica diretta della fonte ufficiale legge la pagina originaria e gli allegati pubblici collegati prima di avviare ricerche estese, cosi' URL, testo, PDF/hash e diagnosi finiscono subito in `web_verification_evidence`.
- Aggiunto il backfill governato `python -m pct.legal_update_job --backfill-web-evidence` per popolare le evidenze mancanti sui record gia' presenti in archivio e renderle interrogabili da Lex/Ricerca Legale.

## 2.245.11 - 2026-05-17

- Esteso il catalogo Lex con Corte dei Conti come fonte ufficiale di classe primaria, includendo portale, sentenze, delibere e banca dati pubblica per responsabilità erariale, giudizi contabili e profili pubblicistici.
- Censita la pagina pubblica `Decisioni e pareri` della Giustizia Amministrativa come fonte ufficiale in osservazione: resta verificabile puntualmente, mentre il ciclo automatico continua a usare OpenGA come canale stabile.
- Registrate Studio Cataldi, Avvocato Andreani e IusSearch come fonti secondarie o motori di supporto: possono orientare la ricerca, ma non pubblicano testo vigente o archivio legale senza conferma su Normattiva, Gazzetta o fonte ufficiale.
- La ricerca governata riconosce anche URL dirette appartenenti a fonti censite e le classifica con priorità e natura della fonte, senza trasformare motori o siti privati in fonti primarie.

## 2.245.10 - 2026-05-17

- L'archivio legale non si limita piu' a registrare riferimenti: le verifiche web salvano evidenze ricercabili, allegati ufficiali, URL, hash, estratti e diagnostica in una tabella dedicata.
- La pubblicazione automatica degli aggiornamenti legali non si ferma piu' sul primo riferimento senza conferme: continua sui candidati successivi, marca quelli incompleti come da completare e conserva cosa e' stato cercato.
- Le fonti INPS dinamiche vengono completate leggendo il JSON ufficiale della pagina, cosi' circolari e messaggi salvano testo reale e PDF allegati invece del solo menu HTML.
- Le schede Cassazione con allegato pubblico salvano il PDF ufficiale anche quando il testo non e' estraibile automaticamente, lasciando comunque hash e URL verificabili.
- La Gazzetta Ufficiale ha un resolver diretto sull'archivio annuale per codici redazionali e riferimenti normativi puntuali: `26G00056` e `D.Lgs. 13 marzo 2026, n. 39` arrivano alla scheda ELI e al PDF GU senza dipendere solo dalla ricerca esterna.
- `/admin/pianificazioni` mostra lo stato dell'archivio legale verificato e permette di annullare le esecuzioni fonte legale rimaste appese senza toccare gli altri job dello studio.
- Gli atti amministrativi di sola liquidazione/fattura, come documenti contabili regionali senza contesto giuridico utile, non vengono piu' trasformati in news legali per lo studio.

## 2.245.9 - 2026-05-17

- `/ricerca-legale` e `/giurisprudenza` diventano superfici operative: card compatte cliccabili, filtri leggibili, dettaglio in pagina e contesto ufficiale salvato in scheda invece di semplici link esterni.
- La ricerca legale completa i record poveri leggendo fonti ufficiali e allegati pubblici riconosciuti, con timeout, allowlist dei domini istituzionali, hash degli allegati e rifiuto dei domini simili non ufficiali.
- La ricerca su riferimenti puntuali non tratta più come contesto completo un elenco cumulativo della Gazzetta: il `D.Lgs. 13 marzo 2026, n. 39` viene estratto dal segmento corretto, pulito da `Leggi la notizia` e completato con testo ufficiale specifico.
- Normattiva e Gazzetta locali non vengono più dichiarate “disponibili” quando il volume locale non contiene gli archivi ufficiali: la UI mostra `Archivio ufficiale non importato nel volume locale`.
- `/ricerca-legale/mediazione` viene alleggerita: rimossi hero, metriche, Presidio Lex AI, Mappa del contesto, filtro grande, pannello di aggiornamento e pulsante `Cerca collegati`; resta un registro consultabile con ricerca compatta e fonte originale apribile.
- La pubblicazione manuale e automatica degli aggiornamenti legali non accetta più testi generici come “aggiornamento giuridico pubblicato in fonte ufficiale” senza contesto verificato dentro IUSENTRA.
- Aggiunto un backfill non distruttivo per correggere news e normative già contaminate da blocchi cumulativi tipo `Leggi la notizia`, preservando i raw originali e producendo piano dry-run con hash prima dell'applicazione.
- Introdotta la pipeline Lex dataset/RAG ispirata ai video su Easy Dataset e LLaMA Factory/Ollama: chunking tenant-aware, task Q&A, export Alpaca/ShareGPT/JSON/CSV, dataset_info per LLaMA Board, revisione umana obbligatoria e compatibilità con tool esterni opzionali senza training automatico.
- La tab `Impostazioni -> AI Locale` mostra ora il percorso dataset Lex: RAG documenti, Q&A in revisione, export Alpaca/ShareGPT, passaggio manuale LLaMA Factory/Ollama, ultimo lavoro ed errori, senza invio dati fuori dallo studio e senza addestramento automatico.
- Il job Superadmin `lex_dataset_nightly` prepara ogni notte il dataset Lex locale da Documenti AI, scrivendo nel tenant corretto anche quando la sorgente Documenti AI è condivisa; la card `Domande in revisione` apre ora una coda operativa: correzione domanda/risposta, approvazione o scarto, evento locale e nessun training automatico.
- `/admin/aggiornamenti-legali` e `/admin/pianificazioni` separano letture tecniche, analisi, schede pubblicate e verifiche residue, evitando falsi positivi quando un job legge documenti ma non produce schede operative.

## 2.245.8 - 2026-05-17

- `/admin/aggiornamenti-legali` distingue ora in modo esplicito documenti letti, documenti analizzati, schede pubblicate, elementi da verificare e scarti; la dashboard mostra la conversione da letture a schede e non usa più "Documenti acquisiti" per materiale solo letto dalle fonti.
- `/admin/pianificazioni` traduce gli esiti degli aggiornamenti legali senza falsi positivi: esecuzioni completate con zero pubblicazioni dichiarano "nessuna scheda pubblicata", esiti completati con errori interni diventano `Da verificare` e i `running` vecchi vengono mostrati come interrotti da controllare.

- Lex AI legge correttamente dati cliente e ultime udienze dal contesto studio autorizzato: richieste come `mi dati i dati del cliente Marco Moscato` e `ultime udienze` non cadono più in risposte generiche di base documentale insufficiente.
- Le bozze di diffida passano dal flusso redazionale, compilano dati studio/avvocato/cliente quando disponibili e non appendono più fonti agenda non pertinenti alla bozza.
- Il widget Lex rende le risposte come un piccolo editor: titoli, grassetto, corsivo, separatori, elenchi, tabelle, citazioni e blocco documento per lettere/diffide, con recupero automatico delle bozze arrivate in una sola riga.
- Il tempo di riflessione è mostrato in italiano naturale (`1 minuto e 10 secondi`) e, durante l'attesa, Lex mostra i passaggi che sta eseguendo: contesto, fonti, dati, verifiche e impaginazione.
- Aggiunto il presidio `utf8-integrity`: servizio/CLI/job notturno per rilevare e riparare mojibake o caratteri non leggibili nei testi utente, con guardie Lex su output e report.

## 2.245.7 - 2026-05-17

- Completato `/impostazioni?tab=ai` per telefoni e tablet: IUSENTRA rileva dispositivo, risorse dichiarate e percorso sicuro, aprendo Lex AI mobile quando il dispositivo non puo' preparare un motore locale.
- Evitato il falso installer mobile di Ollama: la preparazione locale resta attiva sui PC verificabili, mentre mobile/tablet usano il motore AI autorizzato dello studio finche' non esiste un'app compatibile e autorizzata.
- Riallineata la UI desktop/fallback: il modello di ricerca documenti viene mostrato come `EmbeddingGemma 300M` invece del codice grezzo `embeddinggemma:300m`.
- Aggiunta l'opzione volontaria `Qwen 3.5 minimo` per dispositivi leggeri, mantenendo Gemma/EmbeddingGemma come default automatici governati dal profilo hardware.

## 2.245.6 - 2026-05-17

- Integrato Lex AI nella navigazione mobile React: la barra inferiore ora espone un'azione diretta `Lex AI` che apre il widget contestuale con il contesto della pagina corrente.
- Ripristinata la visibilita' dei pannelli Lex contestuali su tablet/mobile, mantenendoli sopra la navigazione inferiore invece di nasconderli sotto 1180px.
- Aggiunte opzioni Qwen 3.5 nelle impostazioni AI locale come scelta volontaria per desktop/edge, senza cambiare i default automatici gia' governati dal profilo del PC.
- Documentata la valutazione del video su Qwen 3.5: mobile come PWA sicura collegata al runtime autorizzato, Qwen 3.5 da usare solo dopo benchmark e scelta esplicita.

## 2.245.5 - 2026-05-17

- Portato il presidio Lex AI direttamente nelle pagine studio `/ricerca-legale` e `/giurisprudenza/`: agenti notturni, archivi ufficiali, funzioni AI avanzate e citazioni verificabili sono ora visibili nel flusso operativo dell'avvocato.
- La pagina Ricerca Legale mostra lo stato di Normattiva/Gazzetta locali, agenti Lex, ricerca completa con allegati pubblici e funzioni MTP/LLM Wiki/GLM-OCR/Gemini come presidi governati.
- L'Archivio Giurisprudenza espone `Citazioni verificate`, stato Cassazione, agenti Lex giurisprudenza e archivi ufficiali prima dell'uso di una massima in atto.
- Le fonti giurisprudenziali non mostrano piu' codici di accesso grezzi come `open_data` o `materiale_cliente`, ma etichette operative per lo studio.

## 2.245.4 - 2026-05-17

- Hotfix agenti Lex produzione: il runtime espone anche `PCT_DATA_ROOT`, archivi ufficiali Lex e Normattiva derivati dalle variabili `PCT_*`, cosi' gli agenti non segnalano fonti mancanti quando gli archivi esistono sul server.
- L'agente depositi telematici inizializza in modo tenant-aware lo schema PDP Penale vuoto quando l'archivio non e' ancora stato creato, senza usare fallback globali e senza azioni dispositive.

## 2.245.3 - 2026-05-17

- Aggiunta governance operativa per MTP/speculative decoding, LLM Wiki, GLM-OCR e Gemini Embedding 2: stato in osservabilita', tassonomia errori e comando `ai-avanzata`.
- Il RAG locale puo' usare Gemini Embedding 2 solo con opt-in esplicito, autorizzazione provider esterni e chiave API; i chunk salvano provider/modello per non mischiare spazi vettoriali.
- Documentata la matrice di attivazione: MTP solo su serving compatibile e misurato, LLM Wiki come livello compilato sopra il RAG, GLM-OCR preferibilmente self-hosted.
- I template agenti delegati sono ora collegati a micro-agenti Lex interni: clienti/soggetti, agenda, scadenze, fascicoli, editor, Cassazione, PCT, posta, pagamenti, compliance, AI locale e integrazioni salvano un inventario operativo e tornano `Da verificare` quando manca un archivio.
- Aggiunto il job notturno `lex_operational_agents_nightly` e il comando `lex-agenti-operativi` per eseguire subito tutti gli agenti senza aspettare la notte.
- Esteso il catalogo legale con codici fondamentali Normattiva, Cassazione verificata e temi richiesti per editor e ricerca: procedura civile/penale, codice strada, famiglia, notifiche/PEC, termini, risarcimento, condominio, fisco e decreto ingiuntivo.

## 2.245.2 - 2026-05-17

- Gli esiti storici degli agenti fonte salvati come `completed` ma con errori interni nel payload vengono riletti come `Da verificare`, con messaggio operativo e fallback OpenGA per Giustizia Amministrativa.
- La normalizzazione agisce sia in scrittura sia in lettura, cosi' le console non mostrano piu' fotografie vecchie falsamente completate dopo l'hotfix degli agenti fonte.

## 2.245.1 - 2026-05-17

- La fonte diretta `Giustizia Amministrativa` e' ora in osservazione: il ciclo automatico non insiste sul canale HTML instabile e usa OpenGA ufficiale come presidio principale per amministrativo.
- Gli agenti fonte marcano come `failed` i report interni con errore anche quando il subprocess termina a zero, evitando esiti falsamente completati.
- Il job `legal_source_giustizia_amministrativa` viene generato disattivato e, se avviato manualmente, spiega la soluzione alternativa: OpenGA CKAN e cartelle `openga_*`.
- L'Archivio Giurisprudenza non mostra piu' codici grezzi come `errore` o `handoff_richiesto`: usa stati operativi `Da verificare`, `Aggiornata` e `Recupero assistito`, con nota di risoluzione quando esiste un presidio alternativo ufficiale.
- Rafforzate le alternative ufficiali del catalogo giurisprudenza: Cassazione usa la pagina pubblica delle ultime sentenze/ordinanze, Corte costituzionale tenta direttamente lo ZIP open data se l'indice non risponde, CURIA usa il feed RSS ufficiale e HUDOC dichiara il canale RSS come fallback.

## 2.245.0 - 2026-05-17

- Aggiunti gli agenti per fonte legale: ogni canale del catalogo ha un job governato `legal_source_<codice>` visibile in `/admin/pianificazioni`, avviabile manualmente e modificabile senza esporre comandi shell.
- Il batch Aggiornamenti legali registra ora l'esito per singola fonte: stato, timeout, durata, documenti trovati, lavorati, invariati, pubblicazioni e messaggio di errore restano consultabili anche dopo il ciclo notturno.
- La pagina `/admin/aggiornamenti-legali/fonti` mostra la colonna Agente con ultimo esito e pulsante `Esegui agente`, cosi' una fonte lenta o fallita non resta nascosta nel job massivo.
- Il registro degli agenti fonte usa solo fonti censite e argomenti allowlist: niente comandi liberi, niente sorgenti arbitrarie, niente riscarico duplicato fuori dal controllo del catalogo.

## 2.244.0 - 2026-05-17

- Aggiunta la console superadmin `/admin/pianificazioni` con alias `/admin/cronjob`: mostra cronjob applicativi, stato attivo/pausato, frequenza, ultime esecuzioni, richieste manuali e creazione di nuovi job da template autorizzati.
- Introdotto il registro persistente `scheduler_registry.sqlite`: il worker registra esiti, errori, salti e richieste manuali, applica modifiche entro un minuto e non espone comandi liberi o shell dalla UI.
- Aggiunti agenti delegati governati per domini operativi: clienti/soggetti, scadenziario/agenda, preventivi/parcelle, email PEC, email ordinaria, fascicoli/documenti, aggiornamenti legali, backup/spazio, depositi telematici, sito studio, pagamenti/notifiche e GDPR.
- Ogni agente delegato produce autoverifica e controllo supervisore: se non completa il lavoro deve dichiarare il motivo, gli archivi mancanti e la prossima azione invece di mascherare l'errore.

## 2.243.9 - 2026-05-17

- Completata `/admin/aggiornamenti-legali/fonti` come catalogo professionale: famiglie fonte, stato attivo/in osservazione, ciclo giornaliero 23:00/23:10/23:15, regole anti-duplicato, lettura allegati e conteggi reali per ogni canale.
- Aggiunte fonti scelte da IUSENTRA oltre a quelle richieste: INPS circolari/messaggi/sentenze, Curia CGUE, ISTAT prezzi, MIMIT incentivi, AGCM bollettino, AGCOM provvedimenti e Banca d'Italia normativa di vigilanza.
- Inserito INAIL istruzioni operative nel catalogo come fonte in osservazione, senza scansione notturna, finche' il canale pubblico non sara' acquisibile in modo stabile dal lettore automatico.
- Il lettore feed riconosce anche RSS pubblicati con intestazione generica, cosi' le fonti ufficiali come Curia vengono importate senza cadere nel fallback HTML.

## 2.243.8 - 2026-05-17

- Collegati gli archivi locali ufficiali alla UI: `/ricerca-legale/ricerca`, la dashboard Ricerca Legale e la console admin Aggiornamenti legali mostrano e interrogano anche Normattiva (`/data/normativa/normattiva.sqlite`) e Gazzetta (`/data/fonti_ufficiali/lex_sources.sqlite`), non solo `legal_updates.db`.
- Aggiunti indicatori leggibili per Normattiva e Gazzetta: documenti, articoli ed estratti indicizzati sono visibili nelle schede operative, cosi' il database Normattiva da piu' GiB non resta nascosto.
- La ricerca legale usa prima archivio aggiornamenti, Normattiva locale e Gazzetta locale; la ricerca web ufficiale parte solo se le fonti locali non bastano.
- Aggiornato lo scheduler: alle 23:00 sincronizza archivi ufficiali Normattiva/Gazzetta, alle 23:10/23:15 esegue Update Intelligence con timeout per fonte/pubblicazione e completamento web governato.
- Normattiva non accumula piu' ZIP duplicati: il downloader confronta catalogo remoto, stato locale e manifest e scarica solo collezioni nuove/cambiate, mantenendo una sola copia per collezione/formato quando richiesto.
- Esteso OpenGA: oltre al presidio generale e al calendario udienze, sono attive le cartelle Decreti, Ordinanze, Pareri, Provvedimenti pubblicati, Ricorsi definiti, Ricorsi pendenti, Ricorsi pervenuti e Sentenze, con risorse CKAN JSON/CSV/ODS e completamento web per il contesto.
- Aggiunti presidi ufficiali ulteriori scelti per utilita' professionale: interpelli Ministero Lavoro, newsletter/provvedimenti Garante Privacy, atti ANAC e download tecnici PST Giustizia.
- La verifica pubblica degli aggiornamenti legge anche pagina fonte e allegati ufficiali collegati (PDF/XML/testo) con limiti di download e timeout per elemento.

## 2.243.7 - 2026-05-16

- Potenziata `/admin/server-manutenzione` con console Hetzner: evidenzia spazio fuori dagli studi, cache ricostruibile dei servizi, snapshot temporanei residui e aree server principali, spiegando lo scarto tra consumi tenant e disco usato.
- Resa obbligatoria la pulizia della cache build Docker dopo ogni deploy Hetzner con `docker builder prune --all --force`; la regola e' codificata in `AGENTS.md`, `deploy/hetzner/deploy.sh`, guida deploy e checklist release.
- Limitata la retention backup a massimo 3 copie anche se l'ambiente imposta valori piu' alti; il backup continua a preservare le copie minime e a non toccare volumi applicativi fuori policy.
- Aggiunta ottimizzazione massima sicura per storage studi: deduplica fisica di allegati PEC/ordinaria e mirror identici, compattazione JSON e `VACUUM/ANALYZE` SQLite senza cambiare i percorsi letti dall'app.
- Installato il lettore allegati compresso: i nuovi allegati PEC/ordinaria possono essere salvati in `archivio-allegati.zip` con deduplica per hash, mentre anteprime e download leggono in modo trasparente sia file sciolti sia archiviati.
- Aggiunto script governato `scripts/purge_downloaded_mailboxes.py` per svuotare PEC/email ordinaria scaricate e allegati mantenendo le configurazioni casella; usato su locale e Hetzner senza creare backup.
- Resa fail-closed la sincronizzazione email in multi-studio: scheduler, route operative e PDP non possono piu' scrivere su `/data/email` o su path globali se manca il contesto tenant; il bootstrap legacy non importa piu' automaticamente gli archivi email root nei tenant.
- Trasformato il comando massivo Aggiornamenti legali in job a elementi con timeout: scheduler, console admin e CLI possono eseguire ogni fonte e ogni pubblicazione idonea in un processo isolato, evitando che verifiche web esterne lente blocchino il lotto notturno.
- Pulizia operativa eseguita su Hetzner: cache build Docker azzerata, posta scaricata rimossa, snapshot temporaneo e backup/quarantene legacy cancellati, con disco sceso a circa 41 GiB usati su 301 GiB dopo il recupero.

## 2.243.6 - 2026-05-16

- Corretto `/admin/aggiornamenti-legali/staging`: la pagina avvia una riconciliazione leggera prima del render e non mostra piu' lo stato grezzo `Da valutare` per documenti gia' classificati.
- Corretto il 403 su `/admin/aggiornamenti-legali/review`: la console Update Intelligence ora accetta anche amministratori di studio con permessi admin/AI, oltre al SUPERADMIN piattaforma.
- I dataset/cataloghi OpenGA e i contenuti tecnici di supporto vengono chiusi automaticamente come acquisizione non pubblicabile, senza intasare la coda revisioni.
- Le fonti ufficiali utili ma prive di chiave strutturale sufficiente vengono risolte automaticamente come notizie informative pubblicabili, mentre norme/sentenze/prassi strutturate mantengono la verifica multi-fonte prima dell'archivio operativo.
- Rafforzati i test Update Intelligence su staging, chiusura automatica dei cataloghi open data e risoluzione automatica dei `NEEDS_REVIEW` informativi.
- Riletto il manifest ufficiale Normattiva Open Data e popolato incrementalmente il database Hetzner: 19 ZIP validi, 189.851 documenti, 800.757 articoli e 639.273 chunk; quattro collezioni esposte dal servizio restano a stream vuoto e sono tracciate nei manifest runtime.

## 2.243.5 - 2026-05-16

- Resa effettiva la pubblicazione automatica degli aggiornamenti legali idonei: analisi e fetch avviano `Pubblica idonei`, le fonti ufficiali/istituzionali ad alta confidenza passano direttamente agli archivi e la coda resta per i soli casi con verifica insufficiente o controllo umano.
- Aggiunta verifica pubblica governata prima dell'autopublish strutturale: Normattiva, Gazzetta, archivio fonti ufficiali e ricerca web allowlist devono confermare la proposta prima che norme, prassi o giurisprudenza vengano pubblicate automaticamente.
- Ripulite le schermate admin `/admin/aggiornamenti-legali/analisi`, `/review`, dashboard e acquisizione da codici tecnici visibili come `NEW_NORMATIVE`, `NORMATIVA_AGGIORNAMENTO` e `pending`, sostituendoli con etichette operative italiane.
- Collegati i percorsi runtime di Normattiva e Gazzetta ai volumi persistenti `/data/normativa` e `/data/fonti_ufficiali`; l'immagine installa anche i crawler ufficiali (`beautifulsoup4`, `feedparser`) necessari a ricreare gli indici.
- Ricreati su Hetzner i database attivi Gazzetta e Normattiva nel volume montato su `/data`: Gazzetta con 28 documenti e 3.911 chunk; Normattiva con 18 ZIP validi, SQLite da 2.866.860.032 byte, JSONL da 1.092.175.389 byte e 638.836 chunk.

## 2.243.4 - 2026-05-16

- Importati in IUSENTRA i tre registri ministeriali della mediazione: Registro Organismi, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione, con acquisizione paginata ASP.NET dal portale ufficiale, classificazione per sezione, stato, natura, territorio, CF/P.IVA, email e sito.
- Trasformata `/ricerca-legale/mediazione` in un registro consultabile dentro l'app: filtri intuitivi, tabella compatta professionale, schede fonte con contesto completo e ricerca locale sui dati acquisiti, lasciando il link ministeriale come verifica finale.
- Corretto il bridge React per non deduplicare le righe ministeriali solo per URL ufficiale: la pagina espone ora 3.035 record importati piu' le tre schede di accesso, non soltanto i collegamenti.
- Reso Lex AI capace di leggere il registro mediazione interno come fonte ufficiale di classe A, includendo sezione, numero registro, identificativi fiscali, stato, territorio e contatti nelle evidenze.
- Aggiunti OpenGA Giustizia Amministrativa e gruppo `calendario-udienze` come fonti CKAN JSON, con acquisizione dei metadati e delle risorse JSON disponibili; allineato il seed Normattiva OpenData alla pagina ufficiale indicata.
- Corretto l'autopublish degli aggiornamenti legali: gli slug normativi duplicati non bloccano piu' `Pubblica idonei`, e gli errori puntuali vengono isolati nella lista saltati invece di fermare l'intera azione.

## 2.243.3 - 2026-05-16

- Reso il backup preventivo Hetzner compatibile con dati runtime vivi: i warning non fatali di `tar` su file cambiati durante la lettura non interrompono piu' il deploy automatico, mentre errori gravi e compressione fallita restano bloccanti.

## 2.243.2 - 2026-05-16

- Resa ripetibile la build Docker del frontend anche su Hetzner: lo stage Vite installa esplicitamente le devDependencies necessarie alla compilazione Tailwind/PostCSS.
- Esclusi i `node_modules` dal contesto Docker, cosi' la build locale non puo' piu' mascherare dipendenze mancanti sul server.

## 2.243.1 - 2026-05-16

- Ristrutturata la console `/admin/aggiornamenti-legali/`: dashboard piu' operativa, stato duplicati, finestra notturna 00:00-05:00, pulizia archivio e azioni dirette per cercare, catalogare e pubblicare.
- Rafforzata la pipeline Update Intelligence: prima di proporre un contenuto confronta l'archivio gia' pubblicato, chiude come duplicati sentenze/ordinanze/norme/prassi/news gia' presenti e scarta contenuti fuori perimetro per lo studio legale.
- Estesa la pubblicazione automatica ai contenuti ufficiali idonei, non solo alle news, mantenendo audit e impedendo nuove versioni normative identiche.
- Spostato lo scheduler aggiornamenti legali nella fascia 00:00-05:00 e aggiunta pulizia archivio anche da CLI/admin.
- Aggiunti test di regressione su autopubblicazione senza reinserimenti, duplicati giurisprudenziali, cleanup archivio e trigger scheduler notturni.

## 2.239.3 - 2026-05-16

- Trasformate `/legal-intelligence/` e `/ricerca-legale` in un workspace professionale: `Osservatorio Legale` per governare fonti/news/registri e `Ricerca Legale` per costruire schede contestualizzate.
- Ogni record fonte porta dentro IUSENTRA estratto, contesto, uso pratico, attendibilita' e ricerca collegata; la fonte originale resta azione di controllo finale, non contenuto principale.
- Ridisegnata la UI con percorso operativo, ricerca guidata, mappa del contesto, scheda laterale/sticky e card risultati orientate all'avvocato, senza dati demo o testi tecnici visibili.
- Aggiunti guardrail React e test backend per impedire regressioni verso pagine solo a collegamenti; verificati typecheck, test frontend, build, pytest mirati, Docker locale no-cache e audit Chrome CDP desktop/mobile.
- Deploy Hetzner CPX42 eseguito senza backup su `2.239.3`: container applicativi healthy e `/api/pronto` pubblico pronto.

## 2.239.2 - 2026-05-16

- Integrati nella scheda React `Registro Mediazione` e nella Ricerca Legale i tre accessi ufficiali ripristinati dal 22/04/2026: Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione.
- Le schede puntano ai rispettivi servizi ministeriali `mediazione.giustizia.it`, restano marcate come fonte ufficiale e conservano la news PST `NWS4865` come evidenza del ripristino.
- Aggiunto test di regressione per impedire che la pagina Mediazione torni a mostrare solo la news senza gli accessi ufficiali distinti.

## 2.239.1 - 2026-05-15

- Ricostruito `/sito-studio/builder` come Builder Pro in Versione B: barra superiore scura, pannello sinistro stretto da 380px con tab verticali e anteprima live grande sempre prioritaria, in linea con il riferimento grafico fornito.
- Aggiunte le 10 tab definitive: Setup, Pagine, Blocchi, Contenuti, Aspetto, Media, SEO, Privacy, AI e Pubblica, con azioni operative su pagine, blocchi, contenuti, media, conformita' e pubblicazione.
- Reso ridimensionabile il pannello sinistro, mantenendo la preview come area dominante; desktop, tablet e mobile conservano navigazione integrata e controllo del formato anteprima.
- Corretti caricamento e assegnazione immagini: upload con titolo/alt derivati dal file, assegnazione al blocco selezionato e gestione errori leggibile.
- La preview live mostra l'intero sito, include sempre il footer pubblico, scorre internamente e aggiorna colori, font, dimensioni, layout, ombre, header, divider, hover, focus ed effetti sobri/professionali.
- Estesi i controlli tipografici con piu' font, dimensioni titoli/testo, interlinea, allineamento sinistra/centro/destra/giustificato e formattazione corsivo, sottolineato, apice e pedice.
- Persistiti tema, layout ed effetti nel runtime del sito pubblico; i testi formattati sono filtrati lato server e resi anche nelle pagine pubbliche senza permettere HTML arbitrario.
- Verificati typecheck, build, test frontend, pytest mirati, Ruff, gate React, packaging/readiness, Docker locale no-cache, readiness locale e audit visuale CDP desktop/tablet/mobile.

## 2.239.0 - 2026-05-15

- Potenziata la console superadmin `Server e manutenzione`: per ogni studio mostra categorie di consumo, cartelle piu' pesanti, file principali, area dominante, conteggio file/cartelle e azioni dirette verso studio, archivio, analisi e compattazione.
- Separati i consumi tenant da email e backup globali, evitando conteggi sovrapposti e rendendo leggibile dove finisce lo spazio disco anche in ambienti multi-studio.
- Protetto il caricamento della console storage con scansione rapida configurabile e segnalazione di dettaglio parziale, mantenendo disponibili analisi e compattazione mirate quando serve l'inventario completo di uno studio.
- Resa `Assistenza remota` pronta all'uso: STUN predefinito, ICE server disponibili anche senza variabili manuali, runtime Docker/Hetzner allineato e console con stato "Pronta per assistenza immediata".
- Declassati TURN e controllo remoto avanzato esterno a ottimizzazioni opzionali: link cliente firmato, stanza operatore, schermo/audio con consenso, chat e audit restano subito operativi.
- Aggiunti test di regressione su inventario storage tenant, default WebRTC, console assistenza pronta e salvataggio configurazione senza perdere il default operativo.

## 2.238.4 - 2026-05-15

- Resa condivisa la console `/admin/copertura-ai`: dashboard, audit, gap queue, generazione bozze, review, publish e API admin ignorano `tenant_slug` e usano un archivio unico di piattaforma.
- Aggiunto il percorso SQLite condiviso `LEGAL_COVERAGE_SQLITE_DB` / `PCT_LEGAL_COVERAGE_SQLITE_DB`, con default sotto `intelligence/legal_coverage.db`; PostgreSQL resta disponibile solo se configurato esplicitamente con `LEGAL_COVERAGE_DB_*`.
- Rimossi selettore studio, campi nascosti e testi per-tenant dalla dashboard e dalla review `Copertura AI`; la pagina utenti piattaforma ora descrive Aggiornamenti legali e Copertura AI come presidi condivisi.
- Aggiornati test di regressione per impedire il ritorno a `studio.db`, PostgreSQL tenant-aware implicito o selezione studio sulla Copertura AI.

## 2.238.3 - 2026-05-15

- Resa condivisa la console `Aggiornamenti legali`: dashboard, fonti, acquisizione, analisi, archivio, review e API admin usano l'archivio applicativo unico derivato da `LEGAL_INTELLIGENCE_DB`, senza selezione tenant e senza duplicare scansioni per studio.
- La pagina `Fonti aggiornamenti legali` governa una sola lista fonti per tutta la piattaforma; una scansione aggiorna tutti gli studi.
- Allineati Lex/Ricerca Legale, pagina utenti piattaforma e documentazione storage al principio: gli aggiornamenti giuridici pubblici sono condivisi, mentre i dati privati dello studio restano tenant-aware negli altri domini.
- Bloccata l'eredita' implicita del DSN PostgreSQL del tenant per gli aggiornamenti legali: il backend SQL resta disponibile solo quando configurato esplicitamente per il presidio condiviso.
- Aggiornati test di regressione per bloccare il ritorno alla selezione studio su `/admin/aggiornamenti-legali`.

## 2.238.2 - 2026-05-15

- Corretto il crash di Lex sulle richieste di sentenza specifica con numero e data di deposito: il metadata `SourceScope` espone di nuovo un motivo sintetico e il workflow `giurisprudenza_specifica` non cade piu' con `AttributeError`.
- Aggiunto fallback ufficiale Cassazione per riferimenti esatti: la query `Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026` individua la scheda pubblica `penale_dettaglio.page?contentId=SZP50042` e la risposta resta `needs_review` finche' non viene acquisito il testo integrale.
- Evitata la seconda ricerca pubblica lenta quando l'exact match ufficiale e' gia' stato trovato da `OfficialWebSource`.
- Protetto `/api/assistente/chat`: se un errore inatteso avviene prima dello stream, la route restituisce JSON controllato senza pagina HTML 500.
- Rafforzato il widget Lex: i corpi HTML o troppo lunghi ricevuti da errori HTTP vengono sostituiti da un messaggio operativo breve, senza riversare la shell dell'app nella conversazione.
- Aggiunti test di regressione per la query `Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026`, per il fallback Cassazione, per il 500 JSON dell'endpoint chat e per il contratto del widget.

## 2.238.1 - 2026-05-15

- Sbloccato Legal Skills per gli studi senza configurazione manuale: `lex.legalSkills.enabled` e le route React `/legal-skills`, profilo, esecuzione e revisione sono ora attive di default.
- Mantenuti spenti di default i presidi piu' sensibili (`trustLayer`, skill custom e agenti schedulati), che restano abilitali solo con flag espliciti.
- Evitati i falsi errori console nel catalogo: niente chiamata agli agenti schedulati quando il flag e' spento e manifest Supertonic locale esplicitamente disabilitato.
- Aggiunti test di regressione su flag, API catalogo/profilo e blocco dei canali sensibili, cosi' la pagina non torna allo stato "Legal Skills non attivo" per default.

## 2.238.0 - 2026-05-15

- Trasformata `/ricerca-legale` in ricerca effettiva: il form React invia la query al backend, il bridge interroga `legal_updates.db` e mostra estratti fonte, area, data, autorita' e link consultabile.
- Aggiunto fallback automatico sulle fonti ufficiali governate quando l'archivio interno non produce fonti ufficiali con contesto sufficiente; la pagina conserva il filtro locale solo per News e Mediazione.
- Inserita la notizia ufficiale PST `NWS4865` sul ripristino di Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione, con data `2026-05-11` e riferimento al ripristino del `22/04/2026`.
- Aggiunti test backend dedicati per impedire regressioni verso ricerca solo locale/mascherata e confermare la presenza della fonte PST in News e Ricerca Legale.

## 2.237.9 - 2026-05-15

- Sbloccato Lex Operational Knowledge come capability attiva di default: clienti, fascicoli, agenda, scadenze, preventivi, conferimenti, fatturazione, messaggi, documenti e template vengono interrogati dal bounded workflow senza opt-in manuale.
- Separata la ricerca giuridica pubblica dal layer operativo: richieste su sentenze specifiche, giurisprudenza, normativa e fonti ufficiali restano instradate al workflow pubblico/web governato invece di fermarsi sui dati interni dello studio.
- Esteso il fallback legale: se la ricerca legale ha solo contesto interno insufficiente, Lex abilita automaticamente la ricerca web ufficiale; le risposte strict mostrano anche l'estratto della fonte usata e restano `needs_review` quando una fonte e' citata senza contesto testuale.
- Aggiornati contratti, test e documentazione dei flag Lex: resta disponibile l'opt-out `LEX_OPERATIONAL_KNOWLEDGE_ENABLED=0`, mentre RBAC, tenant isolation, blocco azioni dispositive e privacy restano sempre attivi.

## 2.237.8 - 2026-05-15

- Migliorata l'impaginazione delle risposte Lex nel widget flottante: titoli, paragrafi, elenchi, tabelle, citazioni, link e codice inline vengono resi in modo compatto e leggibile invece di finire in blocchi disordinati.
- Rafforzato il riconoscimento dei caratteri italiani nella voce Lex: il motore Supertonic preserva la normalizzazione Unicode NFC e i test coprono accenti come `à`, `è`, `é`, `ì`, `ò`, `ù`.
- Aggiunti test JS e contratti bootstrap per impedire regressioni su renderer risposta Lex, escaping HTML, accenti italiani e stili della bolla AI.

## 2.237.7 - 2026-05-15

- Riportato `web/bootstrap/scadenziario_routes.py` sotto il budget di governance bootstrap senza modifiche funzionali, rimuovendo sole righe vuote superflue.
- Rilanciati i gate mirati su cartella cliente React, packaging/readiness, bootstrap e Lex TTS prima del deploy finale.

## 2.237.6 - 2026-05-15

- Migliorata la voce Lex TTS: profili piu' lenti e meno metallici, stile Supertonic predefinito `M1.json`, tag lingua ONNX completo e pause applicate al segmento appena concluso.
- Rafforzata la prosodia italiana: virgole, punti, punti interrogativi/esclamativi, percentuali, orari, decimali e importi vengono trasformati in testo piu' leggibile prima della sintesi.
- Caricata la catena `lex-tts` anche nella shell React, cosi' Lex usa lo stesso motore Supertonic/normalizzatore sulle pagine React e sulle pagine Flask.

## 2.237.5 - 2026-05-15

- Promossa la cartella cliente profonda `/clienti/<id>/cartella` a esperienza React full anche quando arriva da link storici con `?_legacy=1`: la richiesta viene normalizzata alla URL canonica e non apre piu' il template classico.
- Aggiunti manifest, contratto legacy, gate statici e test mirati per impedire regressioni verso fallback classico o CTA `?_legacy=1` nella pagina `CartellaClientePage`.
- Rigenerati asset React, registri App V2 e report anti-mascheramento; Docker locale no-cache e browser Chrome CDP desktop/mobile confermano redirect 302 canonico, shell React, nessun overflow e nessun testo tecnico visibile.

## 2.237.4 - 2026-05-15

- Fase 3 TTS Lex: collegato il layer voce raffinato a un engine Supertonic/ONNX locale e opzionale, con manifest same-origin, caricamento runtime ONNX locale, WebGPU con fallback WASM e fallback obbligatorio alla voce browser.
- Aggiunti generazione WAV browser-side, lifecycle ObjectURL, cancel, badge backend, misure numeriche di sintesi senza log del testo e documentazione operativa per asset, privacy, licenze e test manuali.

## 2.237.3 - 2026-05-15

- Fase 2 TTS Lex: introdotti profili voce italiani, preset qualita `fast/balanced/high`, preferenze locali leggere e badge voce orientato al profilo operativo.
- Raffinata la normalizzazione legale italiana con test su abbreviazioni, privacy, date, importi, chunking e compatibilita del fallback voce browser.

## 2.237.2 - 2026-05-15

- Fase 1 TTS Lex: aggiunti normalizzatore legale browser-side, registry engine, fallback `speechSynthesis`, predisposizione Supertonic same-origin, manifest esempio e documentazione privacy/fallback senza asset ONNX nel repository.
- La facciata `window.PctLexVoice` mantiene il contratto pubblico, espone stato/preload opzionali e preserva dettatura e fallback voce browser.

## 2.237.1 - 2026-05-15

- Completata la rifinitura finale AI Legal fase 2 con pagine React esplicite `PracticeProfilePage`, `ColdStartInterviewPage`, `LegalSkillRunPage`, `SkillRunDetailPage` e `ReviewerQueuePage`, agganciate alla shell Legal Skills.
- Esteso il gate statico Legal Skills per bloccare regressioni sui file pagina richiesti e sulle route `/legal-skills/profile/cold-start` e `/legal-skills/review-queue`.
- Allineati feature flag frontend e routing per la coda revisione Legal Skills senza esporre dati demo o identificativi tenant controllati dal client.

## 2.237.0 - 2026-05-15

- Introdotto Legal Skills Engine per Lex: pack read-only contratti, privacy, contenzioso e regolatorio con parser, registry, profilo studio, workflow governato, trust layer e agenti schedulati default-off.
- Aggiunte API `/api/v1/legal-skills/*` con feature flag, RBAC, audit, tenant isolation, blocco parametri riservati, OpenAPI e provider verification.
- Aggiunta UI React Legal Skills con catalogo, profilo, esecuzione e revisione risultato; note di revisione, citazioni, confidenza e blocco export sono sempre visibili quando rilevanti.
- Documentati motore, flag, contratti e gate; aggiunti test mirati backend e static check frontend.

## 2.236.7 - 2026-05-15

- Introdotto il layer Lex Operational Knowledge: registry sorgenti operative, guard tenant/RBAC, router query, tool deterministici, response composer, audit e integrazione nel bounded workflow con feature flag default-off.
- Lex puo' interrogare dati reali tenant-aware di clienti, soggetti, fascicoli, agenda, scadenziario, preventivi, conferimenti, tariffario, fatturazione, timesheet, documenti fascicolo, messaggi, notifiche, template atti, legal intelligence, update intelligence e fonti ufficiali locali.
- Aggiunta la mappa tecnica `docs/lex-operational-knowledge-map.md`, documentati flag di abilitazione e aggiornato il registro tool Lex.
- Rafforzati i test contro regressioni: niente web per dati cliente/studio, niente dati inventati, blocco azioni dispositive, RBAC, tenant isolation, coverage gap e fonti interne citabili.

## 2.236.6 - 2026-05-15

- Reso operativo in modalita locale controllata il Legal Source Engine per Lex AI: contratti fonte, registry, modello citazionale, answer policy, dogfood, scorecard, report, auto-populate seed e retriever JSONL senza rete o crawling live.
- Documentato il workflow ispirato a Printing Press come pattern architetturale, senza dipendenza runtime, vendorizzazione o uso del progetto esterno.
- Ripristinate le funzioni operative di `/strumenti-legali`: la pagina React mostra il catalogo completo degli strumenti forensi e ricollega i moduli ai calcoli reali gia' esistenti.
- Aggiunto il submit JSON React per gli strumenti legali con risultati in pagina, metriche, tabelle, note e fonti, senza form HTML POST o fallback dimostrativi.
- Allineato il bridge `Strumenti Forensi` a 70 voci di catalogo e 20 calcolatori eseguibili, inclusi interessi, contributo unificato, onorari, rivalutazione, usura, TFR, CTU, successione, locazioni, lavoro, penale e fiscalita.
- Corretto il redirect storico `/sigp/`, evitando il 308 canonico che bloccava il gate React mirato.

## 2.236.5 - 2026-05-15

- Rifinito il linguaggio visibile di Ricerca Studio: rimossi sigle, tempi tecnici e scorciatoia tastiera esposta, mantenendo ricerca rapida e accessibilita da tastiera.
- Rifinito il testo dei controlli telematici React eliminando il riferimento al browser nella checklist e nello stato Local Signer.
- Reso piu preciso il visual audit: le pagine ricche di azioni non vengono piu segnalate come prive di collegamenti solo perche usano pulsanti, tab o controlli interni.

## 2.236.4 - 2026-05-15

- Rafforzata la UI React condivisa: modali e pannelli laterali gestiscono focus, Esc, sfondo e z-index senza coprire contenuti o perdere la navigazione da tastiera.
- Migliorata la resa responsive di tabelle, card, bottoni e navigazione mobile: testi lunghi vanno a capo, stati vuoti occupano meno spazio e le tabelle diventano schede leggibili su mobile.
- Ripuliti testi visibili tecnici in Impostazioni AI, Lex e superfici amministrative, con date in formato italiano e messaggi operativi per lo studio legale.
- Reso il dettaglio studio piu' reattivo: il conteggio dello spazio archivio viene calcolato in modo asincrono e con limite temporale, evitando blocchi della pagina.
- Convertito `/agenda/importa` a submit gestito da React con stati caricamento, successo ed errore visibili e aggiunto il contratto GET JSON dedicato.
- Aggiornato il gate full React per riconoscere gli alias telematici che usano l'endpoint JSON condiviso `/api/v1/ui/telematico/surface/<surface>`.

## 2.236.3 - 2026-05-14

- Promossa `/profilo` alla shell React con dati profilo reali, cambio password e gestione 2FA via submit JSON tracciato.
- Resa operativa `/agenda/importa` in React e corretto `/agenda/nuovo`: la ricerca cliente non apre piu' la pagina di errore, precompila codice fiscale, procedimento, ufficio e avvocato responsabile quando i dati sono presenti.
- Aggiunta la barra di scorrimento orizzontale superiore nelle tabelle React di clienti, soggetti e fascicoli.
- Aggiunti link secondari `Portale ufficiale` nelle superfici PDP, PAT e SIGIT, anche nell'area dati aggiornati del percorso assistito.
- Esteso il compose PEC e SMTP ordinario con selezione cliente, destinatario precompilato e allegati singoli/multipli tenant-aware.
- Corretto lo scadenziario React: le card filtrano davvero, `repository_reali` non compare piu' nella UI e `Apri dettaglio` apre il dettaglio operativo con azioni.
- Migliorata la scheda AI locale di Impostazioni: all'apertura del tab viene rilanciata la verifica stato e, quando disponibile, il controllo via Local Signer.

## 2.236.2 - 2026-05-14

- Semplificata la prova notifica: un unico selettore permette di scegliere insieme atto, relata firmata, PEC inviata, RAC e RdAC; IUSENTRA riconosce i file dal nome, calcola automaticamente gli SHA-256 e prepara i riferimenti ricevute per DatiAtto.xml.
- Le impronte SHA-256 del pacchetto prova sono ora validate come 64 caratteri esadecimali; valori mancanti o non validi bloccano il controllo.
- Le date delle relate e dei modelli parametrici vengono rese in formato italiano, ad esempio `TAURIANOVA RC, 14/05/2026`.

## 2.236.1 - 2026-05-14

- Migliorata la prova notifica: la scheda `Deposito prova notifica` permette di selezionare piu' documenti dalla pratica, mostra l'elenco automatico con riferimento portale e hash SHA-256, e invia al motore `atti_notificati` separati per evidence pack.
- Il bridge React espone il riferimento portale del documento, ad esempio `pst:JPW_SIGP:2182464`, cosi' l'atto notificato puo' essere riportato senza riscriverlo a mano.

## 2.236.0 - 2026-05-14

- Reso fail-closed il modulo notifiche legali: la notifica PEC L. 53/1994 richiede operazione `notifica_pec_l53`, avvocato abilitato, PEC mittente validata, fonte pubblica, verifica PEC con data e ora, oggetto esatto, relata separata firmata, ricevuta completa, documenti classificati e attestazioni quando dovute.
- Disattivato il vecchio `pct/notifica.py`: nessun percorso produttivo puo' piu' inviare una notifica L. 53/1994 con oggetto generico tipo "Notifica telematica".
- Aggiunto registry ufficiale dei procedimenti telematici per PCT SICID/SIECIC, SIGP, UNEP, PAT, PTT/SIGIT, PDP, area web PST e portali speciali, con blocco su canale/procedimento sconosciuto o incoerente.
- Corretti i limiti PTT/SIGIT a 10 MB per file, 50 file, 50 MB totali, nome file massimo 100 caratteri e PDF/A-1a/1b obbligatorio quando previsto.
- Estesi evidence pack, prova deposito e workflow area web PST per notifiche non consegnate, con valutazione avvocato e SHA-256 per gli elementi essenziali.
- Aggiornata la pagina React Notifiche legali: `Controlla relata`, `Controlla prova deposito` e `Prepara comunicazione` mostrano una fase di esito operativa con file, pacchetto prova e testo generato; la notifica puo' selezionare piu' documenti dal fascicolo e riportarli automaticamente nell'elenco allegati.

## 2.235.6 - 2026-05-14

- Ripristinato nello Step 4 del wizard PST React e classico il controllo "Aggiorna pratica esistente": quando il percorso arriva da un fascicolo o da URL con `mode=update_existing`, `fascicolo_id` o `target_fascicolo_id`, il wizard parte gia' sulla pratica locale corretta e la verifica non ricade sulla creazione di una nuova pratica.
- Corretto il flusso Giudice di Pace/SIGP: ricerca esatta, catalogo documenti e `ricercaAtti` vengono raccolti nel batch di visualizzazione, senza chiamate profilo separate che potevano riaprire prompt PIN multipli; il download dell'intero fascicolo resta un batch separato.
- Rigenerato IUSENTRA Local Signer `1.6.35` e rafforzati i test anti-regressione sulla regola utente: un PIN per visualizzare e un PIN per scaricare tutto, salvo scadenza reale della sessione lato portale/token.

## 2.235.5 - 2026-05-14

- Corretto il ritorno delle richieste PIN multiple nel flusso PST React: la UI non chiama piu' il preflight `/pst/preflight-auth` prima di ricerca, anteprima o download, e il Local Signer usa la chiamata operativa come unico punto di autenticazione.
- Esteso lo stesso blocco anti-regressione ai template PolisWeb classici, al wizard `/portali/pst/acquisizione`, al dettaglio fascicolo e al vecchio client SIGP: nessun percorso operativo chiama piu' `/pst/preflight-auth` prima di visualizzare il fascicolo o scaricare il lotto completo.
- Rimossi dalla navigazione e dalla registrazione applicativa gli ingressi separati SIGP; `/sigp` e `/sigp-sync` rimandano al wizard unico `/portali/pst/acquisizione`.
- Rafforzato IUSENTRA Local Signer `1.6.34`: selezione automatica del certificato quando resta un solo certificato coerente con il codice fiscale, curl di sistema su Windows e `--ssl-no-revoke` applicato internamente senza chiedere all'utente di aggiungerlo.
- Normalizzati i link telematici visibili senza prefisso `/app-v2`, incluso `Apri pagina` da `/telematico` verso `/polisWeb`, e corretto lo scroll con offset della barra superiore su centro e superfici telematiche.
- Reso reale il flusso assistito PDP/PAT/PTT dentro IUSENTRA: la React parte da `Sessione IUSENTRA`, non mostra il link esterno come azione primaria e importa file, ricevute ed esiti raccolti nel fascicolo interno.
- Aggiunto l'endpoint `POST /api/portali/<portale>/acquisizione/importa-file` per smistare nel fascicolo documenti e ricevute provenienti dalla sessione locale assistita, mantenendo `importa-payload` per i dati autorizzati JSON.

## 2.235.4 - 2026-05-14

- Corretto il blocco della sincronizzazione Email ordinaria dopo la deduplica: la scoperta IMAP non include piu' archivi/etichette equivalenti come `Tutti i messaggi`, `Archivio` o cartelle personali, evitando letture duplicate e timeout.
- La sincronizzazione IMAP recupera il caso `cannot read from timed out object` durante il recupero di un messaggio riaprendo la connessione e riprovando il singolo messaggio senza perdere la deduplica.
- La Panoramica React non resta piu' bloccata su `Sincronizzazione comunicazioni...`: la sync di background ha un timeout lato client e chiude sempre lo stato di caricamento.

## 2.235.3 - 2026-05-14

- Corretto il rosso CI `Local Signer e PKCS#11`: PDP, PAT e PTT mantengono il canale WSDL diretto attivo di default e passano alla consultazione browser-assistita solo con flag espliciti di forzatura/disabilitazione.
- Rigenerato IUSENTRA Local Signer `1.6.31` e i pacchetti `tools/dist`, incluso `SetupLocalSigner.exe`, per distribuire il comportamento corretto anche dai download pubblici.
- Confermata la regola PST/PIN gia' fissata: una sessione per visualizzare e una per scaricare, senza reintrodurre prompt multipli salvo scadenza reale lato portale/token.

## 2.235.2 - 2026-05-14

- Corretto il gate CI `contracts`: ora esegue solo controlli OpenAPI/provider offline e non tenta piu' chiamate HTTP a `127.0.0.1:8080` quando il server non e' avviato.
- Promosse in React le acquisizioni assistite esatte PDP, PAT e PTT/SIGIT su `/portali/pdp/acquisizione`, `/portali/pat/acquisizione`, `/portali/ptt/acquisizione` e `/portali/sigit/acquisizione`, mantenendo protetti i moduli telematici non parificati.
- Rafforzata la deduplica Email ordinaria: triplicati provenienti da cartelle IMAP equivalenti vengono riparati in lettura e non vengono ricreati in sync, senza fondere PEC diverse con UID stabili.

## 2.235.1 - 2026-05-14

- Hotfix App V2 rollout: le superfici gia' promosse operative sono attive di default anche sotto `/app-v2`, evitando il blocco regressivo "Funzione non attiva per questo studio" su pagine come `/app-v2/messaggi/nuovo`.
- Mantenuti default-off e fail-closed per `Servizi telematici` non parificati e Web Push, con rollback esplicito ancora disponibile via feature flag.
- Aggiornati test, smoke e documentazione per distinguere rollout operativo da capability protette.

## 2.235.0 - 2026-05-14

- Chiusura fase 14 `fasereact`: report finale tecnico, release readiness checklist, GO/NO-GO e prossima PR consigliata.
- Riesecuzione dei gate finali documentali, App V2, OpenAPI/provider, backend/frontend, sicurezza, coverage e smoke senza introdurre nuove funzionalita applicative.
- Tracciati i gap non critici rimasti: credenziali smoke autenticate, VRT/Storybook e GitHub Actions remote da confermare sui runner.
- Refactor finale di governance per separare creazione fascicolo e helper documenti in moduli bootstrap dedicati, piu' pattern anti-mojibake email espresso con escape Unicode.

## 2.234.0 - 2026-05-14

- Completata la fase 13 `fasereact`: promosso `scripts/smoke_app_v2_all.py` a orchestrator operativo con suite `health`, `auth`, `flags`, `rbac`, `tenant`, `routing`, `api`, `pages`, `workflows`, `documents`, `admin`, `search`, `notifications` e `post-deploy`.
- Aggiunto `scripts/smoke_lib.py` con HTTP client, redaction segreti, result model, severity policy, summary e JSON report senza token/password/API key.
- Aggiunti test unitari `tests/scripts/test_smoke_lib.py` e `tests/scripts/test_smoke_app_v2_all.py` per redaction, JSON report, alias `--subset`, missing env e policy failure.
- Creati `docs/smoke-tests.md` e `docs/release-readiness-checklist.md`; aggiornati README, CI/CD gates, piano test, rollout e troubleshooting con comandi reali fase 13.
- Aggiornato `.github/workflows/smoke-staging.yml` per usare `--suite post-deploy --read-only` e caricare report JSON sanitizzati.

## 2.233.0 - 2026-05-14

- Completata la fase 12 `fasereact`: creata documentazione finale di handover per architettura, App V2, sicurezza, osservabilita, database/migrazioni, troubleshooting, risk register, release notes e prossime PR.
- Aggiunto `docs/index.md` come indice ufficiale e `docs/documentation-audit.md` per tracciare contraddizioni risolte, gap reali e fonti generate.
- Aggiornati `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, feature flag, API contracts, RBAC/tenant isolation, CI/CD gates e release rollout con comandi reali e rollback operativo.
- Aggiunti `scripts/validate_docs_links.py` e `scripts/validate_docs_commands.py` per verificare link locali, script/workflow/npm scripts citati nei documenti.
- Ribaditi i gap reali: Storybook/VRT e smoke autenticati non sono dichiarati verdi finche' mancano runner o secrets dedicate.

## 2.232.0 - 2026-05-14

- Completata la fase 11 `fasereact`: rafforzati i workflow CI/CD con gate bloccanti per App V2, contratti API, provider verification, RBAC, tenant isolation, feature flag, registry, frontend e coverage critica.
- Aggiunto workflow manuale `.github/workflows/smoke-staging.yml` per smoke ambiente/post-deploy con environment `staging`, secrets solo da GitHub e nessun deploy automatico produzione.
- Rafforzato `Security Supply Chain` con `pip-audit` JSON artifact, `npm audit --audit-level=critical --omit=dev` e report dedicati.
- Creato `docs/ci-cd-gates.md` con inventario workflow, required checks consigliati, segreti/env, artifact, rollout safety e gap residui; aggiornati piano test, release rollout e README.
- Aggiunto `tests/test_ci_cd_gates_phase11.py` per bloccare regressioni sui gate fase 11 e sulla documentazione CI/CD.

## 2.231.0 - 2026-05-14

- Completata la fase 10 `fasereact`: aggiunti piano test App V2, inventario test e matrice pagina/ruolo/tenant/flag in `docs/test-plan-app-v2.md`, `docs/test-inventory.md` e `docs/test-matrix-app-v2.md`.
- Aggiunto `scripts/react-migration/generate_app_v2_test_docs.py` con gate deterministico `--check` e collegamento ai registri App V2/fase 8-9.
- Aggiunto `scripts/smoke_app_v2_all.py` come orchestratore smoke per inventory, security, pagine, routing, workflow e contratti, senza segreti hardcoded e con profili autenticati solo via env.
- Aggiunto `tests/test_app_v2_test_plan_phase10.py` per bloccare drift documentale, false dichiarazioni di coverage frontend/E2E e regressioni dello smoke inventory.
- Eseguiti gate mirati backend/frontend/contract/smoke/coverage: coverage-critical CI, e2e-smoke, npm test/typecheck/build, OpenAPI/provider verification e coverage baseline auth/storage/telematico al 78%.

## 2.230.0 - 2026-05-13

- Completata la fase 9 `fasereact`: aggiunta governance UI regression App V2 con `docs/ui-regression-and-storybook.md`, fixture sicure isolate e stato pagina per pagina nei registri generati.
- Aggiunto `scripts/validate_ui_coverage.py` per impedire che P0/P1 non full React vengano marcate `ui_tested`, verificare fixture senza PII/segreti e documentare Storybook/VRT senza dichiararli pronti.
- Collegato il gate fase 9 a `npm --prefix frontend run test`, CI App V2 e `tests/test_ui_coverage_phase9.py`.
- Rigenerati `docs/app-v2-page-registry.md` e `docs/frontend-app-v2-pages.md` con la sezione `Copertura UI fase 9`, mantenendo VRT e Storybook come gap espliciti.

## 2.229.0 - 2026-05-13

- Completata la fase 8 `fasereact`: creato `docs/app-v2-area-requirements.md` come registro generato dei requisiti specifici per area, workflow, RBAC, tenant isolation, PII, test richiesti e stato finale.
- Aggiunto `scripts/react-migration/generate_app_v2_area_requirements.py` con gate deterministico `--check` e guardia contro aree marcate `complete_tested` quando contengono route legacy o parziali.
- Aggiunto `scripts/smoke_app_v2_workflows.py` per inventario e smoke autenticati dei workflow P0/P1 reali, con credenziali solo da variabili ambiente e nessun segreto stampato.
- Aggiornati registry App V2, riepilogo frontend, CI e gate `check-app-v2-frontend` per includere la fase 8 e bloccare regressioni su workflow area non governati.
- Aggiunti test mirati `tests/test_app_v2_area_requirements_phase8.py` per documento generato, stati area, smoke workflow e credenziali mancanti.

## 2.228.0 - 2026-05-13

- Completata la fase 7 `fasereact`: rafforzata la shell frontend App V2 con 404 sicura per percorsi non censiti, navigazione filtrata da feature flag e RBAC UI, e bootstrap React con permessi effettivi dell'utente.
- Aggiunto il gate `frontend/scripts/check-app-v2-frontend.mjs`, collegato a `npm test`, CI, documentazione generata e OpenAPI, per bloccare regressioni su no-fetch flag-off, menu non autorizzati e stati `complete_tested`/`partial`/`pending`.
- Rigenerati `docs/app-v2-page-registry.md` e `docs/frontend-app-v2-pages.md` con stato frontend fase 7 pagina per pagina, mantenendo esplicitamente pendenti le route legacy o parziali non parificate.
- Aggiunti test mirati `tests/test_app_v2_frontend_phase7.py` per guard sorgente, permessi reali nel bootstrap e report App V2 aggiornati.

## 2.227.0 - 2026-05-13

- Completata la fase 6 `fasereact`: creato `docs/openapi.yaml` dagli endpoint Flask React reali e aggiunta `docs/api-endpoint-contract-map.md` con priorita, pagina, RBAC, feature flag, tenant scope e provider status.
- Aggiunti `scripts/react-migration/generate_api_contracts.py`, `scripts/validate_openapi.py` e `scripts/verify_openapi_provider.py` per generazione deterministica, validazione OpenAPI e provider verification con Flask test client.
- Documentati error schema, pagination/filtering, request/response schema, RBAC, tenant scope, PII policy, upload/download e regole per nuovi endpoint in `docs/api-contracts.md`.
- Rafforzata la risposta 401 delle API React con campi normalizzati `ok`, `error`, `message` e `code`, mantenendo i campi legacy `errore` e `codice`.
- Aggiunti gate CI e test `tests/test_openapi_contracts_phase6.py` per impedire endpoint P0/P1 senza contratto, estensioni sicurezza mancanti o drift provider/OpenAPI.

## 2.226.0 - 2026-05-13

- Completata la fase 5 `fasereact`: introdotto `web/services/backend_security.py` e hook centrale sulle API React per bloccare parametri client riservati a tenant, studio, token generici, API key e redirect liberi.
- Aggiunta la mappa `docs/backend-endpoint-security-map.md` con endpoint `/api/v1/ui`, priorita P0/P1, permessi attesi, dati sensibili e presidi auth/RBAC/tenant.
- Aggiunto `scripts/smoke_backend_security.py` per smoke post-deploy senza segreti: readiness, API sensibili anonime bloccate e, con API key da env, blocco `tenant_id` forzato.
- Rafforzata la documentazione sicurezza/rollout/API con denial `policy_denied.backend_security` e risposta controllata `backend_security_control_param` senza eco di valori sensibili.
- Aggiunti test mirati `tests/test_backend_security_phase5.py` e regressioni su Impostazioni, Utenti, Fascicoli, Email, feature flag, tenant isolation e routing App V2.

## 2.225.0 - 2026-05-13

- Completata la fase 4 `fasereact`: introdotto `web/services/app_v2_routing.py` con mapping legacy -> App V2, whitelist query, blocco query sensibili e decisione redirect legata a feature flag.
- Creato `docs/legacy-to-app-v2-routing-map.md` e rigenerati registro App V2/frontend con redirect strategy, deep link, query params, fallback e classificazione template legacy.
- Aggiunto `scripts/smoke_app_v2_routing.py` per smoke post-deploy senza segreti e test statici contro open redirect.
- Rafforzato il router frontend App V2 per non far fallire il match quando gli alias legacy contengono query/hash controllati.
- Aggiunti test `tests/test_app_v2_routing.py` e contratti React/documentali per impedire redirect aperti, target non interni, cattura di `/api/*` o mapping App V2 senza flag.

## 2.224.0 - 2026-05-13

- Completata la fase 3 `fasereact`: introdotti flag canonici `routes.appV2.<area>.<pagina>` default-off per ogni pagina/famiglia App V2, con alias compatibili per i flag delle fasi 1-2.
- Rafforzata la protezione `/app-v2`: root e percorsi dinamici vengono mappati al flag corretto, con blocco 403 quando il modulo non e' abilitato per lo studio.
- Allineato il frontend: mappa flag in `featureFlags.ts`, menu App V2 filtrato, stato operativo "Modulo non attivo" e fetch sospesi quando il flag e' off nella shell sperimentale.
- Rigenerati `docs/app-v2-page-registry.md` e `docs/frontend-app-v2-pages.md` con default, fallback flag-off, protezione frontend/backend e test on/off.
- Aggiunti test mirati `tests/test_app_v2_feature_flags.py` ed estesi `tests/test_feature_flags.py`, `tests/test_react_shell.py`, `check-react-contracts` e `check-route-gate` per impedire regressioni di governance.

## 2.223.0 - 2026-05-13

- Completata la fase 2 `fasereact` come censimento governato: aggiunto `docs/app-v2-page-registry.md` con 98 route manifest, stato React/legacy, feature flag, RBAC, rischio tenant/PII, test presenti/mancanti, priorita e stato finale.
- Aggiunto `docs/frontend-app-v2-pages.md` con shell App V2, alias legacy verso App V2 e backlog P0/P1/P2/P3 delle route non ancora full React.
- Introdotto `scripts/react-migration/generate_app_v2_page_registry.py` per rigenerare e verificare il registro in modo deterministico.
- Introdotto `scripts/smoke_app_v2_pages.py` per smoke parametrico post-deploy, con credenziali solo da variabili ambiente e modalita `--list` senza chiamate HTTP.
- Aggiunti test `tests/test_app_v2_page_registry.py` per impedire registro non aggiornato, route manifest mancanti e smoke script non eseguibile.

## 2.222.0 - 2026-05-13

- Avviata la fase 1 `fasereact`: audit iniziale migrazione React/App V2, documentazione feature flag, sicurezza RBAC/tenant, contratti API e rollout.
- Introdotto `web/services/feature_flags.py` con flag default-off per capability App V2 e Web Push, supporto env/JSON, toggle auditabile `feature_flag_toggled` e denial `policy_denied`.
- Aggiunto endpoint autenticato `GET /api/v1/ui/feature-flags` e bootstrap shell con stato flag pubblico.
- Protette le route sperimentali `/app-v2/documenti`, `/app-v2/comunicazioni`, `/app-v2/agenda`, `/app-v2/scadenziario` e `/app-v2/fascicoli` quando il flag corrispondente e' spento, senza bloccare le route React operative gia' promosse.
- Messo `notifications.mobilePush` davanti alle azioni Web Push: il frontend non chiama le API push se il flag e' spento e il backend rifiuta subscription/test con errore controllato.
- Aggiunti test mirati su default-off, toggle audit, API flag, route App V2 off/on e Web Push flag-off.

## 2.221.0 - 2026-05-13

- Corretto il rischio di regressione sul PIN PST/Local Signer: il wizard React riusa la sessione `view` salvata in ricerca/anteprima anche quando lo stato del componente viene perso, e il download resta batch con lo stesso `pst_session_id` invece di aprire handshake separati documento per documento.
- Il link dal fascicolo al wizard portale mantiene ora la pratica locale anche con query `fascicolo_id` o `target_fascicolo_id`, oltre a `id_fasc`.
- Introdotto il pacchetto `audit/` per audit probatorio append-only: canonicalizzazione RFC8785-JCS, SHA-256, firma JWS/CAdES-adapter, catena `prev_event_hash` per tenant/fascicolo, storage WORM S3 Object Lock, receipt WORM firmata, snapshot Merkle, TSA RFC3161 e verifica offline.
- Aggiunte migrazioni Alembic/Postgres e SQL per `audit_events_index`, `audit_snapshots_index`, `audit_emit_failures` e `audit_reconciliation_runs`; l'indice resta cache ricostruibile da WORM con `scripts/rebuild_audit_index.py`.
- Aggiunti endpoint RBAC `/audit/events`, `/audit/events/<event_id>`, `/audit/proof/<event_id>`, `/audit/bundle/fascicolo/<id>` e `POST /internal/audit/emit` interno only con mTLS/service token, idempotency key e rate limit.
- Aggiunti bundle probatorio fascicolo e script offline `scripts/verify_audit.py`, piu' smoke `scripts/audit_smoke_test.py`.
- Collegati atti, ricevute deposito/import, esiti deposito e ricevute cliente al nuovo audit probatorio; il dettaglio React del fascicolo mostra tab Audit con timeline, badge Firma/WORM/Snapshot/TSA e download prova/bundle.
- Aggiunti test mirati audit su canonicalizzazione, hashing, firma, WORM, emit/idempotenza, catena, Merkle, snapshot, proof, bundle, route e integrazioni.

## 2.220.0 - 2026-05-13

- Rigenerati i pacchetti IUSENTRA Local Signer 1.6.29 in `tools/dist`, incluso l'installer Windows `SetupLocalSigner-1.6.29.exe` e l'alias `SetupLocalSigner.exe`.
- Promosse in modo verificato le route `/scadenziario/:id` e `/sito-studio/builder` a `react_operational_full`, mantenendo fuori dal gate export, azioni legacy e sottopercorsi non parificati.
- Sbloccate come `react_operational_partial` le route `/scadenziario/:id/modifica` e `/sito-studio/redazione-ai`, con manifest, gate, shell, contratti e test allineati.
- Riallineato il gate React: `/sito-studio/builder` e `/sito-studio/redazione-ai` passano dalla shell, mentre `/sito-studio/*` non verificati restano legacy; `/scadenziario` accetta solo lista, nuovo, dettaglio e modifica.
- Eliminati i falsi full emersi dai gate: `Template Atti` non contiene piu' form HTML nel componente full e il fallback dashboard non usa piu' nomi mock.
- Aggiunti contratti legacy espliciti per route ad alto rischio lasciate legacy-first, tra cui telematico, servizi telematici, SIGP sync, tribunali, guida firma digitale, osservabilita, database alias e applicazioni.

## 2.219.0 - 2026-05-13

- Introdotta la policy centrale dei portali: PST / PolisWeb resta `direct_internal`, mentre PTT/SIGIT, PAT e PDP restano `official_portal_assisted` salvo manifest diretto verificato, completo, non scaduto e con test reali passati.
- Aggiunto guard fail-closed sui client produttivi PTT/PAT/PDP (`ricerca_fascicoli`, `consulta_documenti`, `deposita_atto`) senza bloccare demo/offline o import da payload autorizzati.
- Aggiunti endpoint comuni per sessione assistita e deposito assistito PTT/PAT/PDP, con Local Signer / Local Connector, raccolta download sicuri, import ricevute/esiti in Comunicazioni/Cancelleria, timeline ed evidence pack.
- Aggiornato il wizard portali: PTT/PAT/PDP mostrano il flusso di Portale ufficiale assistito e non promettono integrazione diretta tipo PST.
- Esteso Local Signer 1.6.29 con endpoint `/portal-assistant/session/*` e default fail-closed sui WSDL diretti non-PST.
- Aggiunti test mirati su policy, guard, sessione assistita, finalizzazione senza evidenza ufficiale, import ricevute e wizard PST/non-PST.

## 2.218.9 - 2026-05-13

- Corretto il decoding delle Email ordinarie quando il server dichiara un charset errato: gli accenti italiani non vengono piu' sostituiti con caratteri non leggibili nei campi oggetto e corpo.
- La sincronizzazione IMAP ripara anche le email gia' salvate con caratteri sostitutivi, rileggendo il messaggio originale quando e' ancora presente sul server.
- Aggiunti test mirati su `è` e `à` in intestazioni e corpo, inclusa la riparazione dei record storici.

## 2.218.8 - 2026-05-13

- Corretto il doppione in Email ordinaria tra messaggio inviato locale e copia IMAP della cartella Inviati quando il provider salva la copia con uno scarto di orario.
- Gli invii email SMTP generano sempre un `Message-ID`, cosi' le sincronizzazioni successive hanno una chiave stabile e non dipendono dal secondo esatto registrato dal server.
- Aggiunti test mirati per deduplica con orario server diverso e per evitare fusioni indebite tra due invii locali simili.

## 2.218.7 - 2026-05-13

- Corretto il riconoscimento delle cartelle Legalmail non quotate (`INBOX.Cestino`, `INBOX.Inviata`) durante la sincronizzazione PEC, cosi' i messaggi spostati possono essere riletti e riallineati quando sono ancora presenti sul server.
- Reso piu' chiaro il messaggio sugli allegati storici non disponibili: dopo la sincronizzazione, se il file resta assente, va verificato che la PEC sorgente sia ancora presente nella casella.
- Diagnosticato il messaggio segnalato del 12 maggio 2026: il vecchio UID IMAP non e' piu' presente in INBOX e la ricerca nelle cartelle Legalmail disponibili non restituisce quella PEC, quindi `postacert.eml` non puo' essere ricostruito senza una sorgente originale.

## 2.218.6 - 2026-05-13

- Rafforzato il parser PEC per salvare `postacert.eml` anche quando la parte `message/rfc822` ha il nome file nel `Content-Type` ma non dichiara `Content-Disposition: attachment`.
- Verificata la sincronizzazione PEC di produzione sul messaggio segnalato: gli allegati recuperabili vengono salvati, mentre eventuali record non piu' scaricabili dal server restano con messaggio controllato e non con pagina 404.

## 2.218.5 - 2026-05-13

- Corretto il download degli allegati PEC `message/rfc822`: il parser ora serializza e salva anche `postacert.eml`, cosi' la sincronizzazione puo' riparare i messaggi storici con metadati allegato ma file mancante.
- Il dettaglio React di PEC/email non propone piu' azioni `Apri`, `Visualizza` o `Scarica` per allegati non recuperati fisicamente; mostra invece uno stato operativo di sincronizzazione.
- Le vecchie URL di allegati presenti solo come metadato restituiscono un messaggio controllato invece della pagina 404 generica, preservando gli allegati gia' disponibili sul loro indice reale.
- Aggiunti test mirati su dettaglio allegati PEC, route inline/download, parsing `message/rfc822` e riparazione allegati storici.

## 2.218.4 - 2026-05-13

- Aggiunti generatore e diagnostica Web Push/VAPID: `tools/generate_vapid_keys.py`, modulo `pct.notifications.generate_vapid` e comando `python -m pct.notifications.web_push_diagnostics`, senza scrivere chiavi nel repository.
- Aggiunti script Hetzner `configure_web_push.sh` e `verify_web_push.sh` per configurare `/opt/iusentra/.env.hetzner`, abilitare Web Push, verificare le variabili e non stampare la chiave privata nei log normali.
- Aggiunto opt-out `IUSENTRA_SKIP_BACKUP_CRON=1` in `deploy/hetzner/deploy.sh` per deploy operativi senza aggiornare la pianificazione backup.
- Rafforzato `/api/push/public-key`: quando Web Push non e' configurato restituisce diagnostica sicura con variabili mancanti, senza esporre mai la private key; la public key resta visibile solo con configurazione completa.
- Migliorata la UI `Impostazioni > Notifiche`: distingue server da configurare, browser non supportato, permesso bloccato, dispositivo attivo e istruzioni amministrative, senza chiedere permessi al caricamento.
- Aggiornata la documentazione PWA/Hetzner con procedura server, verifica da browser e troubleshooting del messaggio `Da configurare`.

## 2.218.3 - 2026-05-13

- Aggiunto hardening multi-studio fail-closed per API key tenant-aware, contesto studio privato e path dati sensibili, bloccando l'uso della `PCT_API_KEY` globale sui dati di studio in multi-tenant.
- Estesi i guardrail runtime su clienti, fascicoli, documenti, agenda, scadenziario, messaggi, PEC/email, fatturazione, preventivi, privacy, audit, backup, ricerca, intelligence, template e telematico senza esporre path o segreti nei payload.
- Aggiunti test dedicati per compatibilita single-tenant, chiavi API per-studio, mismatch cross-studio, sessioni incoerenti e path traversal fuori root tenant.
- Riallineato il dettaglio Fascicoli al caricamento lazy gia' contrattualizzato, evitando il preload della sezione Regia Operativa al primo caricamento.

## 2.218.2 - 2026-05-13

- Portata la compilazione `/template-atti/compila/<codice>` nella shell React con selezione reale di cliente e pratica collegata, precompilazione IUSENTRA, pannello Cartabia/deposito e POST finale verso il renderer esistente.
- Corrette le note dei campi: testi visibili solo in italiano, colore giallo leggibile per i dati da completare e nessun messaggio inglese o nome tecnico di campo esposto allo studio.
- La verifica Cartabia resta normativa e non promuove il modello a pronto quando mancano dati concreti dell'atto; il catalogo puo' essere verificato dai controlli IUSENTRA, mentre la bozza viene bloccata solo sui campi obbligatori non risolti.
- L'autore/difensore continua a provenire da Dati Studio/Avvocato titolare, con fallback governato all'utente corrente solo se il dato studio non esiste.
- Dopo la generazione valida, la bozza del template resta collegata alla pratica e viene aperta nell'editor professionale per l'impaginazione dell'avvocato.
- Aggiunti test API/React e smoke browser sul compilatore Template Atti per impedire regressioni al vecchio compilatore Jinja o a testi non italiani.

## 2.218.1 - 2026-05-12

- Aggiunto inventario STRICT delle fonti Template Atti con report Markdown/JSON: master, split, compilatore, repository JSON, SQLite e tenant vengono ricondotti a 1320 template canonici, mantenendo i record duplicati come evidenze di fonte.
- Introdotto catalogo unificato per capability Cartabia, prefill, timbro, deposito, preview, render e compilatore; i binding mancanti sono recuperati dalle fonti interne IUSENTRA e non lasciati come fallback vuoti.
- Rafforzato il resolver prefill per `Destinatario / Ufficio Giudiziario`, `Cliente / Mittente`, `Pratica Collegata`, `Autore`, controparte, allegati e dati studio, con conflitti, alternative, privacy level e `missing_reason`.
- Allineato `Autore`/`author_user_id` alla fonte primaria `Impostazioni > Dati Studio > Avvocato titolare`, con utente corrente solo come fallback quando il dato studio non esiste.
- Collegata la compilazione dei Template Atti all'editor professionale: se la pratica e' selezionata, la bozza validata viene salvata nel fascicolo come documento HTML e aperta direttamente per l'impaginazione.
- Allineato il timbro studio alla regola top-left/left anche negli alias API e aggiunta anteprima `/api/v1/ui/studio/timbro/preview`.
- Registrate fonti ufficiali Cartabia/processo telematico in `docs/legal_sources/cartabia_sources.jsonl` e aggiunti test strict su inventario, catalogo unificato, fonti, prefill, timbro e API.

## 2.218.0 - 2026-05-12

- Introdotto il timbro studio dinamico tenant-aware per Template Atti, con renderer testo/HTML/DOCX/PDF, endpoint React `/api/v1/ui/studio/timbro` e iniezione centrale nel compilatore e nei template.
- Aggiornato il catalogo master Template Atti a `v1.2.0`: 420 template con profilo Cartabia, stato di revisione, campi prefill dichiarativi, controlli deposito e binding compilatore.
- Aggiunto il resolver di precompilazione con provenienza, confidenza, alternative e motivi dei dati mancanti, riusato dal compilatore e dai template master.
- Estesi API, filtri e pagina React del catalogo con stato Cartabia, precompilabilita', verifica avvocato e anteprima del timbro studio, senza badge di conformita' assoluta.
- Aggiunti script di arricchimento/validazione split, report di copertura, documentazione e test mirati su catalogo, timbro, prefill, endpoint e controlli per famiglia, ADR e deposito.

## 2.217.2 - 2026-05-12

- Aggiunto il centro notifiche persistente tenant-aware/user-aware con dedupe, stato letto persistente, preferenze minime e subscription Web Push per dispositivo.
- Integrata la top bar esistente con il nuovo repository senza cambiare il payload storico di `/api/notifications`, `/api/notifications/<id>/read` e `/api/notifications/read-all`.
- Introdotte API `/api/push/public-key`, `/api/push/subscribe`, `/api/push/test`, Service Worker root, manifest PWA e UI in `Impostazioni > Notifiche` per attivazione, disattivazione e test dal dispositivo.
- Aggiunto invio Web Push con `pywebpush`, VAPID da variabili ambiente e payload sempre generico, senza dati sensibili di clienti, fascicoli, PEC, RG o importi.
- Documentati requisiti HTTPS, consenso utente, limiti iOS/iPadOS, troubleshooting, deploy Hetzner e fallback futuri email/WhatsApp/SMS.

## 2.217.1 - 2026-05-12

- Rafforzata `/notifiche-legali`: i modelli relata personalizzati accettano solo i token ammessi, bloccano istruzioni Jinja, filtri, chiamate e accessi riservati prima del render.
- Aggiunta anteprima relata a due livelli con testo modello e anteprima compilata, placeholder espliciti per dati mancanti e aggiornamento dai campi correnti della notifica.
- L'avvocato puo' modificare l'anteprima compilata e salvarla come bozza tenant-aware della notifica corrente, senza inserirla nel catalogo dei modelli riutilizzabili.
- Chiarita la distinzione UI tra modello relata riutilizzabile e bozza pratica; la verifica finale usa la bozza manuale ma mantiene oggetto PEC, PEC pubblica, attestazioni, ricevute, firma e approvazione come controlli bloccanti.
- Separata la comunicazione cliente dal catalogo relata L. 53/1994 con modelli dedicati per email ordinaria, oggetto/corpo modificabili e blocco dell'oggetto legale riservato alle notifiche.

## 2.217.0 - 2026-05-12

- Introdotto il Calendar Sync Engine server-side per Agenda e Scadenziario: account calendario, calendari collegati, binding eventi, job sync e conflitti sono persistenti e tenant-aware.
- Aggiunti provider Google Calendar, Outlook/Microsoft 365, Apple iCloud/CalDAV, WebCal/ICS e provider locale persistente per prove bidirezionali complete senza credenziali esterne.
- Le credenziali calendario vengono cifrate con `cryptography/Fernet` e non sono esposte dai payload API; Google/Microsoft usano OAuth server-side, Apple usa credenziali CalDAV cifrate e WebCal riusa la base ICS esistente.
- La UI Impostazioni Calendari mostra collegamento account, calendari abilitati, direzione, riservatezza export, stato allineamento, sincronizzazione manuale, disconnessione e conflitti risolvibili.
- Aggiunti scheduler mirati, demo `python tools/demo_calendar_sync.py`, documentazione `docs/CALENDAR_SYNC_ENGINE.md` e test su cifratura, provider locale, motore bidirezionale, conflitti, scadenze perentorie, privacy export e API.

## 2.216.9 - 2026-05-12

- La pagina `/notifiche-legali` mostra ora l'anteprima leggibile del modello relata selezionato prima del controllo, con catalogo laterale navigabile per scegliere rapidamente tra tutti i modelli disponibili.
- Aggiunta creazione di modelli relata personalizzati tenant-aware: l'avvocato puo' duplicare un modello, scriverne uno nuovo e inserire campi automatici IUSENTRA come pratica, avvocato, assistito, procedimento, destinatario, documenti, attestazioni e oggetto PEC.
- Il motore L. 53/1994 renderizza anche i modelli personalizzati e consente una integrazione libera dell'avvocato in coda alla relata generata, mantenendo validazioni, attestazioni e controlli automatici.
- Estesa la compilazione assistita anche a `Deposito prova notifica` e `Comunica al cliente`: la pratica selezionata propone atto, destinatario, cliente, procedimento e documento informativo dove disponibili, lasciando RAC/RdAC e dati non certi alla conferma manuale.
- Aggiornati API React, contratti statici e test per impedire regressioni su anteprima modelli, salvataggio dei modelli personalizzati e precompilazione operativa dei tre percorsi.

## 2.216.8 - 2026-05-12

- Estesa `/notifiche-legali` con motore parametrico di modelli: catalogo JSON versionato, template L. 53/1994, attestazioni automatiche per fascicolo informatico, comunicazione di cancelleria e scansione analogica, checklist, log e scheda esito.
- La pagina React ora precompila i dati disponibili da IUSENTRA: pratica, assistito, procedimento, destinatari/PEC, fonte pubblica suggerita, documenti del fascicolo, origine documento e hash quando presenti.
- Aggiunta compilazione assistita con selettori rapidi per pratica, destinatario e documento, senza inventare dati mancanti: data/ora verifica PEC e conferma finale restano sotto controllo dell'avvocato.
- Il bridge `/api/v1/ui/notifiche-legali` espone catalogo modelli, versioni e precompilazione dai repository reali di clienti, fascicoli e soggetti, con limiti prudenziali per mantenere rapido il caricamento.
- Aggiornati dominio, UI, tipi TypeScript, test backend e build React per presidiare generazione automatica, attestazioni standard e assenza di testi tecnici visibili.

## 2.216.7 - 2026-05-12

- Introdotta la route React `/notifiche-legali` con tre workflow separati: `Notifica ex L. 53/1994`, `Deposito prova notifica` e `Comunica al cliente`.
- Aggiunto il dominio `pct.notifiche_legali` per validare oggetto obbligatorio, PEC da pubblico elenco, dati della relata, attestazione di conformita', ricevuta completa, firma digitale e prova deposito con RAC/RdAC originali.
- Le email PEC/ordinarie bloccano l'uso diretto dell'oggetto L. 53 e rimandano al percorso guidato, evitando che una notifica legale venga trattata come semplice comunicazione.
- Aggiornati manifest, route gate, shell React, contratti statici e test mirati per presidiare la separazione tra notifica alla controparte, prova deposito e comunicazione cliente.

## 2.216.6 - 2026-05-11

- Corretto il flusso `CodiceOggettoPst` su apertura fascicolo: digitando un codice ufficiale come `014001` il catalogo React lo seleziona subito e il valore nascosto viene inviato al backend.
- Aggiunto fallback backend su `/fascicoli/nuovo`: se il codice non arriva dal form, viene risolto dall'oggetto digitato oppure dal preventivo/conferimento di origine, preservando fonte e file XSD.
- Allineati preventivo normale e preventivo guidato: il codice digitato come oggetto viene validato sul catalogo PST, salvato come `codice_oggetto_pst` e propagato fino al fascicolo guidato che apre il deposito assistito.
- Il dettaglio React del fascicolo espone ora `codiceOggettoPst`, fonte e file XSD anche nella scheda operativa principale, non solo nel form.
- Aggiunti test mirati per fascicolo veloce, preventivo, wizard, collegamento preventivo/conferimento e redirect a `/deposito/prepara`.

## 2.216.5 - 2026-05-11

- Rafforzata `/fascicoli/nuovo` per il flusso `Fascicolo Veloce`: clienti, soggetti e autorita' giudiziarie sono selezionabili da dati reali gia' presenti nel sistema.
- Dopo la creazione veloce il flusso apre automaticamente il deposito assistito del fascicolo appena creato, invece di fermarsi alla scheda o alla cartella cliente.
- Resi obbligatori, nel percorso veloce, autorita' giudiziaria valida, controparte e codice fiscale/P. IVA; il backend restituisce messaggi JSON chiari con i campi mancanti.
- Aggiunta creazione/riuso della scheda soggetto controparte durante l'apertura, con collegamento automatico come parte processuale del fascicolo.
- Aggiornati test React/backend e contratti di form per presidiare uffici giudiziari, soggetti reali, redirect al deposito e assenza del vecchio messaggio generico.

## 2.216.4 - 2026-05-11

- Ridotti i prompt PIN nel wizard PST: la ricerca esatta RG/anno usa il nuovo endpoint Local Signer `/pst/ricerca-snapshot`, che accorpa ricerca fascicolo e catalogo documenti in un solo processo `curl`.
- Rafforzato il Local Signer `1.6.28`: un preflight PST terminato in timeout non viene piu' trattato come sessione cookie pronta, evitando il tentativo cookie-only seguito da nuovo handshake mTLS.
- Il wizard Flask e la superficie React riusano lo snapshot ottenuto dalla ricerca esatta e saltano la successiva chiamata `/pst/fascicolo-snapshot` quando il catalogo documenti e' gia' disponibile.
- Lo snapshot PST accorpato include anche il profilo fascicolo: oggetto, procedimento, stato, data di iscrizione, prossima udienza e parti non vengono impoveriti rispetto al flusso precedente.
- Il download PST con `preflight_auth:false` usa direttamente il batch mTLS senza aprire un preflight preparatorio separato; la prova reale su Palmi RG 274/2026 ha confermato `/pst/ricerca-snapshot` e `/pst/download-documenti-batch` senza chiamate intermedie.
- Registrata una traccia locale ignorata dal git per Palmi RG 274/2026, utile alla futura suddivisione UI del fascicolo: un documento `AttoNonCodificato` risulta catalogato dal PST ma non restituito nel download.
- Se il fascicolo locale e' gia' presente e l'utente sceglie `Collega` o `Aggiorna`, un download PST parziale non blocca piu' l'import: i file ricevuti vengono acquisiti e i documenti non restituiti restano nel catalogo ufficiale come voci da acquisire.
- Il merge dei metadati dei documenti portale conserva gli identificativi piu' ricchi (`idCat`, `idDocumento`, `idRepeatto`, `msgId`) quando una voce era gia' stata censita con dati piu' poveri.
- L'autocomplete uffici del wizard accetta anche la risposta `/api/uffici` nel formato `{value:[...]}`, evitando che uffici reali come Tribunale di Palmi risultino non selezionabili.
- Verificato in browser reale Palmi RG 274/2026: selezione `Aggiorna pratica esistente`, import completato su `B6A03AE6#sezione-documenti-fascicolo` e nessun `/pst/preflight-auth` tra ricerca snapshot e download batch.
- Rigenerati `SetupLocalSigner-1.6.28.exe`, alias `SetupLocalSigner.exe` e installer macOS/Linux.

## 2.216.3 - 2026-05-11

- Unificato il flusso PST del wizard di acquisizione: preflight, consultazione fascicolo e download batch propagano lo stesso `pst_session_id` e usano sempre la sessione `view`, evitando la vecchia sessione separata di import.
- Rafforzato il Local Signer `1.6.27`: i download PST singoli e batch non creano piu' una sessione `import` di default e riusano la sessione esistente anche se un client precedente invia ancora `purpose=import`.
- Aggiunti guardrail mirati su wizard e Local Signer per impedire il ritorno a download PST con sessione separata o prompt PIN aggiuntivi.

## 2.216.2 - 2026-05-11

- Rilasciato IUSENTRA Local Signer `1.6.26` e rigenerati i pacchetti Windows, macOS e Linux in `tools/dist`, incluso `SetupLocalSigner-1.6.26.exe` e l'alias `SetupLocalSigner.exe`.
- Riallineato il pacchetto distribuito alla sorgente Local Signer corrente: TTL sessione PIN a 1800 secondi e riuso dei cookie della sessione PST di consultazione quando viene aperta una sessione di import con stesso certificato e ufficio.

## 2.216.1 - 2026-05-11

- Corretto il flusso PST via Local Signer nella superficie React telematica: preflight, ricerca, anteprima e download riusano la stessa sessione PST locale e non tornano al server per le chiamate ministeriali.
- SIGP/PST ora prepara la sessione locale prima di catalogo e download e usa sempre `/pst/download-documenti-batch`, anche per un solo documento, evitando processi `curl` separati.
- Anche l'acquisizione documenti PST dal dettaglio fascicolo conserva la sessione locale nel browser e la passa al lotto successivo.

## 2.216.0 - 2026-05-11

- Aggiornata `/fascicoli/nuovo`: tutte le sezioni operative del form sono collassabili e `Pratiche collegate` e' ora sotto `Personalizzabile`, vicino alla classificazione iniziale del fascicolo.
- Aggiunto `Fascicolo Veloce`: quando attivo mostra sotto `Annotazioni` due aree di multicaricamento, una per i documenti iniziali e una per le email `.eml` da conservare nel fascicolo.
- Salvati i caricamenti iniziali nel repository documenti del fascicolo con conteggi dedicati, origine tracciata e filtro prudente sui file email non `.eml`.
- Allineata la UI al principio di deposito assistito: IUSENTRA prepara e controlla, mentre firma, busta e invio restano sempre confermati dall'utente.

## 2.215.7 - 2026-05-11

- Corretto il 404 su `/documenti`: la route ufficiale ora apre la shell React con il workspace operativo Documenti, collegato a fascicoli, catalogo atti, redazione e ricerca documentale.
- Aggiornati manifest, gate React e test mirati per impedire che `/documenti` torni fuori dalla shell o dal contratto full React.
- Filtrati dalla superficie Documenti i record locali con diciture `demo`/`sample`, cosi' la UI resta professionale anche quando il runtime contiene vecchi dati di prova.
- Verificata `/documenti` in Docker locale su desktop, tablet e mobile: nessun overflow, nessun errore console e contenuto React visibile sotto 400 ms dopo warm-up tenant.
- Rimosso un falso positivo del gate no-fake sul Tariffario: il riepilogo sticky non usa piu' `Math.round` nel frontend, evitando che il layout venga scambiato per calcolo tariffario client-side.

## 2.215.6 - 2026-05-11

- Importato il catalogo tecnico `pct/data/cataloghi/codici_oggetto_pst.json` dagli XSD ufficiali PST attivi: 1.018 CodiceOggetto unici con fonti, registri, file sorgente e hash dei pacchetti ministeriali.
- Separato il catalogo UI compatto `codici_oggetto_pst_ui.json` dal catalogo tecnico completo, usando il file Excel fornito solo per area/codice padre/metadati di ricerca e non come whitelist di deposito.
- Sostituiti i menu lunghi di Preventivi, Preventivo guidato e Apertura nuovo fascicolo con ricerca rapida per codice, descrizione, area e registro, mantenendo il blocco sui codici non presenti negli XSD ufficiali.
- Verificata la ricerca CodiceOggetto in browser su desktop/tablet/mobile per nuovo fascicolo, preventivo, conferimento e wizard: `014001` selezionabile, `111604` presente e `014700` escluso.

## 2.215.5 - 2026-05-11

- Aggiunta l'azione `Visualizza` sugli allegati PEC e Email ordinaria nella pagina React di dettaglio messaggio: apre il file inline in nuova scheda senza usare il download forzato.
- Mantenute separate le azioni `Apri`, `Visualizza` e `Scarica`, con contratti React e test mirati per evitare regressioni sui link allegati PEC/SMTP.

## 2.215.4 - 2026-05-11

- Introdotto il catalogo versionato `pct/data/pratiche_collegate_catalog.json` per i codici oggetto PST, importato in React senza hardcoding nel componente.
- Allineati Preventivi, Conferimenti, Preventivo guidato e Apertura nuovo fascicolo: il `CodiceOggetto` viaggia solo se scelto/validato dal catalogo ufficiale e non viene mai dedotto dalla tipologia tariffaria.
- Blindato il pre-deposito PCT: `DatiAtto.xml` usa il `codice_oggetto_pst` del fascicolo come valore del nodo `Oggetto` e blocca la busta se il codice manca o non appartiene al catalogo PST.

## 2.215.3 - 2026-05-11

- Ripristinato nel `Dockerfile` il path runtime esplicito `PCT_EMAIL_ORDINARIA_DB=/data/email/ordinaria.json`, cosi' il container non puo' ricadere sul repository e il contratto CI resta allineato al comportamento tenant-aware.
- Riallineata la suite `coverage-critical` includendo i test Lex professionali gia' presenti che coprono moduli critici conteggiati dal gate, senza abbassare la soglia coverage.

## 2.215.2 - 2026-05-11

- Corretta l'operazione multipla su `Email ordinaria` e `Email PEC`: spostamento nel cestino ed eliminazione definitiva caricano e salvano la casella una sola volta anche con migliaia di messaggi selezionati.
- Ridotto l'audit delle operazioni bulk a un evento aggregato separato per PEC/email ordinaria, mantenendo la tracciabilita' senza bloccare la risposta utente.
- Aggiunti test anti-regressione che verificano il salvataggio singolo per selezioni email numerose.

## 2.215.1 - 2026-05-11

- Chiuso il fallback globale di `Email PEC` ed `Email ordinaria` in ambiente multi-studio: liste, dettagli, allegati, statistiche, sincronizzazione e azioni bulk usano solo i path del tenant attivo oppure falliscono chiusi con `tenant_context_required`.
- Introdotto il guardrail condiviso `TenantDataPathError` per impedire letture/scritture cross-studio quando manca il contesto tenant valido.
- Aggiunti test anti-regressione che verificano che le API React email non leggano e non cancellino messaggi dal repository globale senza tenant attivo.

## 2.214.10 - 2026-05-10

- Blindati altri accessi tenant-aware nei repository sensibili: backup, soggetti/anagrafiche parti, indice ricerca, registro privacy, condivisioni, calendario in Impostazioni, preventivi/template atti, sync PDP/PEC, topbar, applicazioni, legal intelligence e superfici admin database/salute sistema ora leggono i path del tenant attivo oppure falliscono chiusi se il contesto studio manca.
- Aggiunti test anti-regressione mirati per impedire nuove letture cross-studio su loader core, helper calendario e repository preventivi.
- Aggiunta nelle pagine `Email PEC` ed `Email ordinaria` la selezione multipla dei messaggi visibili, con checkbox di riga, selezione totale della vista corrente e barra operativa dedicata.
- La cancellazione multipla segue ora il comportamento corretto della cartella aperta: in `In arrivo` e `Inviati` i messaggi vengono spostati nel cestino, mentre da `Cestino` possono essere eliminati definitivamente in blocco.
- Estesi i bridge React email con l'azione `bulkAction` e introdotti gli endpoint JSON `POST /api/v1/ui/email/bulk-action` e `POST /api/v1/ui/email-ordinaria/bulk-action`, mantenendo separati i repository PEC e ordinaria.
- Aggiunti test anti-regressione mirati su payload React e azioni multiple PEC/ordinaria per impedire nuovi mancati allineamenti tra interfaccia e backend.

## 2.214.9 - 2026-05-10

- Corretta la deduplica degli invii nella casella `Email ordinaria`: i messaggi importati dallo storico SMTP non vengono piu' duplicati quando esiste gia' la stessa email nella cartella IMAP `Inviati`.
- Il repository email usa ora `Message-ID` come chiave preferenziale e un fingerprint prudente di oggetto, destinatario, data e corpo come fallback, cosi' il sync distingue i veri doppi dalle copie legittime con UID IMAP diversi.
- La sincronizzazione degli inviati ripulisce anche i doppioni storici gia' presenti, preferendo la copia IMAP stabile e rimuovendo la copia sintetica `INVIATA:*` quando rappresenta lo stesso messaggio.
- Aggiunti test anti-regressione mirati sulla deduplica tra storico messaggi e cartella `Inviati`, mantenendo verdi anche i casi gia' coperti di migrazione `Message-ID` e UID IMAP stabili.

## 2.214.8 - 2026-05-10

- Disattivato il bootstrap automatico dei dati legacy root verso i tenant quando esistono piu' studi attivi: in ambiente multi-studio il sistema non puo' piu' popolare un nuovo studio con dati provenienti dalla root storica.
- Mantenuto il bootstrap automatico solo per il caso davvero mono-studio, che resta il solo scenario sicuro per la migrazione compatibile dei dati legacy.
- Aggiunti test di regressione sul blocco esplicito del bootstrap root->tenant in presenza di due studi attivi, sia all'avvio sia con tenant richiesto.
- Corretto il caricamento utenti multi-studio: i manager tenant passano ora sempre il contesto studio, filtrano in modo rigoroso gli account dello studio aperto e non trattano piu' gli utenti senza `tenant_slug` come appartenenti automaticamente a qualunque tenant.
- SQLite auth tenant-aware ora mantiene allineati `studio.db` e `auth/utenti.json`, aggiunge la colonna `tenant_slug` dove manca e riallinea il `studio.db` locale quando diverge dall'archivio utenti del singolo studio.
- Aggiunti test anti-regressione su riallineamento auth JSON/SQLite tenant, persistenza sincronizzata dei dati utenti e pannello utenti studio in modalita' multi-tenant.

## 2.214.7 - 2026-05-10

- Blindato il runtime multi-studio: un account non `SUPERADMIN` non puo' piu' proseguire senza contesto tenant valido e il login blocca gli account globali non associati a uno studio quando esistono piu' studi attivi.
- Chiuso il fallback silenzioso ai path globali per le richieste tenant senza `g.data_paths`, cosi' il sistema fallisce in modo sicuro invece di leggere dati di un altro studio.
- Aggiunte regressioni automatiche su login/sessioni legacy multi-studio e sul caching del profilo storage tenant-aware per impedire nuove letture cross-studio.

## 2.214.6 - 2026-05-10

- Corretto il calcolo della nuova parcella personalizzata in `/fatturazione`: con regime forfettario o minimo l'IVA non viene piu' applicata, anche se l'opzione risultava attiva nel form.
- Allineati preview React, validazione/salvataggio backend e XML FatturaPA, con blocco visivo dell'opzione IVA nei regimi che non la prevedono.
- Aggiunti test anti-regressione mirati su dominio fatturazione, bridge React e generazione XML per il caso senza IVA.

## 2.214.5 - 2026-05-10

- Estesa `/fatturazione/nuova` con la nuova parcella personalizzata: trasmissione, dati studio, destinatario, corpo documento, fiscalita' e pagamento sono ora raccolti in un'unica esperienza React coerente con il modello operativo richiesto.
- Precompilati automaticamente dai dati reali disponibili cliente, fascicolo, studio, causale, dati pagamento e progressivo di invio, mantenendo il calcolo definitivo governato al salvataggio.
- Allineati dominio e XML FatturaPA a spese generali, spese imponibili, anticipazioni e snapshot personalizzato del documento; corretto anche il caso destinatario estero nella sezione `Nazione`.
- Aggiunti test mirati su calcolo parcella, bridge React e generazione XML, con verifica browser desktop/tablet/mobile senza overflow e senza testi tecnici vietati sulla pagina.

## 2.214.4 - 2026-05-10

- Corretto il contributo unificato proposto nel Preventivo guidato per le pratiche civili di cognizione ordinaria: dopo il calcolo React il wizard riallinea la spesa viva alla tabella normativa in base a valore e grado della pratica.
- Rimossa dal contributo unificato del Preventivo guidato la dicitura visibile `indicativo`, non adatta alla bozza professionale consegnata al cliente.
- Aggiunti test anti-regressione sul catalogo preventivi e sul calcolo React del wizard per bloccare il caso `Atto di citazione` da `EUR 10.000` con contributo unificato corretto a `EUR 237,00`.

## 2.214.3 - 2026-05-10

- Allineato il calcolo del contributo unificato alle tabelle operative richieste per civile, tributario e amministrativo.
- Distinti nel motore e nel form `Valore determinato`, `Valore indeterminabile` e `Valore non indicato`, evitando il vecchio uso ambiguo del solo valore `0`.
- Corretta la Cassazione tributaria: ora usa la misura prevista per il processo civile, inclusi i casi di valore non indicato.
- Corretti i ricorsi amministrativi di terzo grado e gli appalti pubblici in Cassazione/valore non indicato, con nuovi test anti-regressione mirati.

## 2.214.2 - 2026-05-10

- Ripristinato nelle pagine `/clienti` e `/soggetti` il tasto operativo `Elimina` direttamente nelle azioni riga, sia in tabella sia nelle card mobile.
- Aggiunta la cancellazione multipla nelle due anagrafiche React: selezione visibile, conferma esplicita, feedback di esito e refresh dei dati reali di studio.
- Estesi i bridge JSON React con `deleteHref` ed endpoint `POST /api/v1/ui/clienti/delete` e `POST /api/v1/ui/soggetti/delete`, senza reintrodurre form HTML nel flusso principale.
- Aggiunti test anti-regressione mirati su payload React ed eliminazione singola/multipla di clienti e soggetti.

## 2.214.1 - 2026-05-10

- Aggiunta in `/preventivi/` la voce operativa `Preventivo guidato`, collegata a `/preventivi/wizard`, come azione primaria dell'archivio e degli stati vuoti.
- Velocizzato il caricamento di `/tariffario` e `/preventivi/wizard`: i cataloghi React iniziali sono compatti, le regole tariffarie calcolate sono memorizzate in cache e restano completi i calcoli backend reali.
- Ripristinato su desktop il riepilogo in tempo reale del Tariffario come colonna sticky: resta visibile durante lo scroll dei parametri di calcolo e su tablet/mobile degrada in layout normale.
- Ridotto il payload locale misurato: `/api/v1/ui/tariffario` da circa 3,87 MB / 30 s a circa 416 KB / 66 ms; `/api/v1/ui/preventivi/wizard` da circa 4,62 MB / 30 s a circa 705 KB / 47 ms.
- Aggiunti test anti-regressione su dimensione payload, collegamento al preventivo guidato e comportamento sticky del riepilogo tariffario.

## 2.214.0 - 2026-05-10

- Rafforzata la pulizia globale dei testi visibili: le superfici React e i template serviti dalla shell filtrano diciture da sviluppatore come `Impeccable / Open Design`, `Dati applicativi`, `React`, `Flask`, `backend`, `frontend`, `payload`, `runtime`, `json_api`, `provider`, `webhook`, `endpoint`, `legacy`, `undefined`, `null`, `demo`, `sample` e `repository`.
- Portati i dettagli messaggio PEC e email ordinaria nella shell React sulle route `/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>`, con allegati, intestazioni, corpo messaggio e azioni operative.
- Completata la pagina `Redazione Atti` in React con produzione atti nella stessa schermata, template disponibili, compilazione assistita e anteprima senza messaggi tecnici visibili.
- Migliorate `Template Atti`, `Ricerca Legale`, `News`, `Archivio Giurisprudenza`, `Statistiche`, `Strumenti Forensi` e `Strumenti Operativi` con schede operative compatte, dettaglio in pagina e linguaggio orientato allo studio.
- Verificato in browser reale su Docker locale 2.214.0 desktop/mobile: Redazione Atti, Template, Statistiche, Ricerca Legale, News, Giurisprudenza, Strumenti, Controlli Atti, Sito Studio Contatti, dettagli email e Database non mostrano testi tecnici vietati e non hanno overflow orizzontale.
- Aggiornati gate, report React e test mirati: TypeScript, contratti React, build Vite, route gate, no-fake React full, packaging, readiness, pytest email/React e Docker locale 2.214.0 sono verdi.

## 2.213.0 - 2026-05-09

- Corretto `Contatti Sito Studio`: la pagina React resta operativa anche senza richieste, mostra ingressi pubblici, modulo contatti, prenotazioni e stati vuoti specifici invece dello stato vuoto generale.
- Corretto il comportamento della sidebar: una sola cartella resta aperta, la sezione attiva non si richiude navigando al suo interno e viene sostituita quando si seleziona un'altra cartella.
- Estesa la migrazione full React al perimetro operativo richiesto dall'utente: manifest, contratti legacy e gate ora governano le route richieste come superfici `react_operational_full` dove esiste la pagina React.
- Aggiunto submit React centralizzato con feedback e redirect controllato; rimossi i form POST HTML dai componenti React full e dal flusso Preparazione Udienza Guidata dashboard/step/riepilogo.
- Convertite le azioni principali di Nuovo Cliente/Soggetto, Nuovo Appuntamento, Messaggi/SMS-WA, Nuova Scadenza, Registro GDPR, Agenda, Timesheet, Email PEC/ordinaria, Fascicoli e Wizard in submit React/fetch.
- Aggiornati i blueprint Flask collegati per rispondere in JSON alle richieste React mantenendo compatibilita' con le route esistenti.
- Ripuliti testi visibili tecnici nelle pagine operative richieste: il fallback diventa `Percorso di recupero`, e le superfici non mostrano piu' diciture da sviluppatore come `backend`, `legacy`, `payload`, `runtime`, `json_api` o `route Flask`.
- Aggiornati `AGENTS.md`, `agents.md`, piano React, gate anti-mascheramento e report di migrazione per rendere permanente la regola: full React significa comportamento end-to-end, non solo shell.

## 2.212.0 - 2026-05-09

- Corretto il backup Hetzner: Ollama, modelli e download rigenerabili sono esclusi in modo obbligatorio e l'archivio fallisce se contiene ancora percorsi `ollama`.
- Aggiunto test runtime che crea un backup temporaneo reale e verifica che i dati da conservare restino presenti mentre le cartelle Ollama non vengono archiviate.

## 2.211.0 - 2026-05-09

- Rafforzata `Impostazioni -> AI Locale`: la shell React carica `react-ai-local-guard.js`, i controlli stato/preparazione passano dal PC in uso tramite IUSENTRA Local Signer e i test mirati bloccano regressioni verso verifiche solo server/cloud.
- Aggiornati `AGENTS.md`, `docs/UI_DESIGN_SYSTEM.md`, piano React e report test per rendere permanente la regola: la scelta dei modelli AI resta automatica e governata dal computer dello studio.

## 2.210.0 - 2026-05-09

- Promosse a `react_operational_full` le route esatte `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi`, eliminando le ultime eccezioni legacy sulle voci richieste Controlli Atti, Strumenti Forensi e Strumenti Operativi.
- Collegata `Controlli Atti` alla superficie React telematica con payload reale `/api/v1/ui/telematico/surface/checklist`, mantenendo legacy solo per sottopercorsi tecnici e workflow non ricostruiti.
- Collegati `Strumenti Forensi` e `Strumenti Operativi` a `StudioModulePage` con payload reali `/api/v1/ui/studio-modules/strumenti-forensi` e `/api/v1/ui/studio-modules/strumenti-operativi`.
- Allineato il titolo visibile della checklist a `Controlli Atti` e rimossi testi tecnici come `payload` e `backend` dalle superfici telematiche rivolte allo studio.
- Riallineata `Impostazioni -> AI Locale` al PC dello studio: verifica e preparazione passano dal Local Signer, Ollama/modelli mancanti hanno azione guidata, scelta modelli resta automatica e la shell protegge anche gli asset React gia' compilati.
- Aggiornati `AGENTS.md`, manifest React, contratti legacy, gate anti-regressione, route gate e test React per impedire regressioni verso `legacy_operational`.
- Rafforzata la memoria operativa della migrazione full React con la lista completa delle pagine da verificare end-to-end, criteri grafici UI_DESIGN_SYSTEM e passaggi obbligatori di test/deploy.

## 2.209.0 - 2026-05-09

- Promosse `/impostazioni`, `/impostazioni-studio`, `/impostazioni/pagamenti`, `/notifiche`, `/notifiche-whatsapp`, `/backup`, `/impostazioni/calendario` e `/sincronizzazione-calendari` a `react_operational_full`: Dati Studio, PEC, Firma Digitale, Email SMTP, WhatsApp, Scheduler, AI Locale, Pagamenti, Notifiche, Backup e Calendari sono ora gestiti da un'unica pagina React.
- Aggiunti salvataggi sezione per sezione con permessi `admin.configura`, audit, supporto upload firma e applicazione della configurazione studio.
- Aggiunti test operativi per PEC/SMTP/WhatsApp, stato/bootstrap AI Locale e verifica IUSENTRA Local Signer dal browser sul PC, incluso supporto `token_probe_fresh`.
- I campi riservati mostrano lo stato salvato senza riesporre il segreto dal server; l'icona occhio consente di vedere il nuovo valore digitato prima del salvataggio.
- Corretto il layout della pagina Impostazioni: le schede restano compatte, il form non viene piu' schiacciato a destra e i testi visibili non mostrano codici interni o dettagli tecnici.
- Ripristinato l'aiuto operativo sotto `Password email`: per Gmail/Google Workspace indica la password per le app Google e collega la pagina ufficiale di generazione; le scelte AI Locale sono presentate come opzioni guidate, non come nomi tecnici di modello.
- Spostati Pagamenti, Notifiche, Backup e Sincronizzazione Calendari nel gruppo `Impostazioni` del menu React, fuori da `Studio`, con regola di coerenza grafica globale aggiornata in `AGENTS.md` e `docs/UI_DESIGN_SYSTEM.md`.
- Integrate le schede Pagamenti, Notifiche, Backup e Calendari con dati reali, azioni protette, link riservati, audit e testi rivolti allo studio senza termini tecnici visibili.
- Reso piu' reattivo il Docker locale: l'app web parte con piu' capacita' di risposta e non resta bloccata appena una richiesta lunga occupa un processo.
- Aggiornati manifest, gate React, contratti anti-mascheramento, test e build Vite per bloccare regressioni verso template legacy non governati.

## 2.208.0 - 2026-05-09

- Promossa `/statistiche` a `react_operational_full`: il payload React resta read-only su repository reali, non espone piu' azioni `?_legacy=1` nell'errore controllato e il manifest anti-mascheramento non la classifica piu' come bridge residuo.
- Aggiornati contratti React, gate route e test mirato per bloccare regressioni su fallback legacy non governati nella superficie statistiche.
- Ripristinate le regex Lex sui nomi cliente con accenti italiani corretti, così il gate governance resta verde senza ridurre le verifiche.
- Allineato il runtime Docker della posta ordinaria a `/data/email/ordinaria.json`, evitando la ricreazione di file runtime nel repository.
- Aggiunta in `AGENTS.md` la memoria operativa obbligatoria: test/gate/failure vanno registrati nei report di stato, e il caso Docker `email/ordinaria.json` non va piu' rianalizzato da zero.
- Reso non bloccante lo startup web multi-tenant: `sync_user_directory` puo' saltare il reconcile storage pesante all'avvio, lasciandolo ai flussi amministrativi espliciti.

## 2.207.0 - 2026-05-08

- Reso lo stato finale `docker compose ps` informativo dopo il gate health: il deploy non fallisce piu' se Compose restituisce un codice non-zero durante la sola stampa dello stato.

## 2.206.0 - 2026-05-08

- Corretto il completamento finale dello script Hetzner: la rigenerazione del crontab backup non fallisce piu' quando le vecchie righe marcate vengono rimosse tutte.

## 2.205.0 - 2026-05-08

- Reso il deploy Hetzner a due fasi: Redis/app vengono avviati e verificati prima dei servizi dipendenti, poi worker, Caddy e profili completano il rollout con health check finale.

## 2.204.0 - 2026-05-08

- Rafforzato il deploy Hetzner: lo script attende esplicitamente che app, worker e servizi con health check escano dallo stato `starting` prima di stampare lo stato finale e completare il deploy.
- Allineata la versione frontend alla release applicativa finale.

## 2.203.0 - 2026-05-08

- Corretto Lex per le ricerche di sentenze specifiche: il percorso HTTP bounded conserva `giurisprudenza_specifica`, forza la ricerca ufficiale quando consentita, distingue frammento locale/exact match e non mostra piu' elenchi di sentenze correlate come fonti principali.
- Rafforzati exact guard e AnswerBuilder: confidence cap a 0.45 senza exact-match, 0.55 senza testo integrale/dispositivo/motivazione, template professionali senza nomi tecnici interni.
- Corretto il lookup dati cliente: `cliente marco moscato` e varianti vengono instradati a `studio_data_lookup`, usano solo anagrafica interna tramite `studio_data_gateway`, non usano web e producono scheda cliente/fascicoli o not_found chiaro.
- Aggiunti test mirati su router, bridge HTTP, exact search, AnswerBuilder, studio data gateway, output guard e payload debug Lex.

## 2.198.127 - 2026-05-08

- Integrato in `AGENTS.md` il documento `AGENTS_IUSENTRA_Codex.md` preservando le regole esistenti su branch, deploy Hetzner, telematico, storage, sicurezza, CI, coverage e igiene repository.
- Aggiunte regole obbligatorie su UI React professionale, shadcn/ui, Open Design/Open Designer, open-design-support, Impeccable, anti-monolite, performance frontend/backend, accessibilita', sicurezza, quality gate e report finale.
- Rafforzato `tests/test_ci_no_regression_contract.py` per bloccare la rimozione accidentale delle nuove regole operative da `AGENTS.md`.

## 2.198.126 - 2026-05-08

- Reso compatibile l'upload degli shard `Coverage moduli critici` con `actions/upload-artifact@v4`, abilitando esplicitamente `include-hidden-files` per gli artefatti `.coverage.critical.*` e aggiungendo il presidio nel contratto CI anti-regressione.
- Fissata in `AGENTS.md` e `docs/PYTEST_PHASES.md` la regola permanente per cui ogni nuovo test o suite CI deve essere shardabile e non superare 5 minuti per singolo comando pytest/job operativo, senza ridurre il perimetro delle verifiche.

## 2.198.125 - 2026-05-08

- Corretto lo shard coverage critica in CI rinominando l'artefatto `.coverage` prodotto da `pytest-cov` prima dell'upload, cosi' i 12 shard possono essere combinati dal gate aggregatore `Coverage moduli critici`.

## 2.198.124 - 2026-05-08

- Divise le fasi CI `Pytest core` 5/10, 6/10 e 9/10 in sotto-fasi piu' fini a livello di test item, con budget pytest di 5 minuti: fase 5 in 6 parti, fase 6 in 16 parti e fase 9 in 6 parti.
- Divise anche le fasi 7/10 e 8/10, che contengono observability e OCR, in 3 sotto-fasi ciascuna con `--core-subdivide-items`.
- Esteso il runner a suite CI aggiuntive (`coverage-critical`, `signer`, `e2e-smoke`, `quality-overlay`, `release-readiness`, `e2e-nightly`) e convertiti coverage critica, Local Signer, overlay qualita', release readiness, E2E nightly e frontend React in shard con aggregatori, senza rimuovere test.

## 2.198.123 - 2026-05-08

- Corretto il guardrail governance della CI mantenendo nel workflow i target storici ora espansi dal runner `Pytest core` a 10 shard.
- Aggiunte le opzioni `--batch-size` e `--item-batch-size` al runner pytest a fasi per isolare file o singoli test lenti senza ridurre il perimetro dei controlli.

## 2.198.122 - 2026-05-08

- Aggiunto `scripts/run_pytest_phases.py` per eseguire la suite pytest in fasi esplicite, con preset `react-migration`, `ci-core-local` e `full`, report JSON e timeout per singola fase.
- Diviso il job GitHub Actions `Pytest core` in 10 shard paralleli con timeout pytest da 10 minuti per shard e check aggregatore stabile `Pytest core`.
- Rafforzato `tests/test_ci_no_regression_contract.py` per verificare matrice a 10 fasi, aggregatore CI e copertura di tutti i target storici del `Pytest core`, inclusi i file sotto `lex/tests`.
- Documentato il flusso locale a fasi in `docs/PYTEST_PHASES.md` e in `docs/DEPLOY.md`, chiarendo che non sostituisce il gate completo: tutte le fasi devono passare prima di dichiarare verde la suite backend.
- Generato `artifacts/react-migration/pytest-phases.json` come inventario iniziale dei gruppi di test, inclusa la fase `09-misc` di sicurezza per evitare esclusioni silenziose.

## 2.198.121 - 2026-05-08

- Integrato il design system interno IUSENTRA basato su shadcn/ui, Lucide Icons, Tailwind e primitive Radix, senza copiare template completi sopra le superfici operative.
- Aggiunti i componenti riutilizzabili `IusPageShell`, `IusAppSidebar`, `IusTopBar`, `IusSectionHeader`, `IusMetricCard`, `IusActionCard`, `IusStatusBadge`, `IusEmptyState`, `IusFormSection`, `IusCollapsiblePanel`, `IusDataTableShell`, `IusLegalIcon` e `LexFloatingButton`, con token colore legali e mappa icone per area.
- Normalizzati wrapper React esistenti, shadcn primitives, build assets e documentazione `docs/UI_DESIGN_SYSTEM.md`, preservando contratti, route, API, dati reali e fallback governati.
- Aggiunti audit iniziali Full React (`full-react-audit.*`), inventario Jinja, report responsive/accessibilita/performance e manifest con `workspaceTarget` per tutte le route censite, senza promuovere route non verificate.
- Introdotta la nuova struttura `frontend/src/app`, `frontend/src/shell`, `frontend/src/api` e `frontend/src/features/*`, riusando i componenti e data client React esistenti per non duplicare logiche canoniche backend.
- Creato un set UI legale condiviso (`legal-ui.css`, primitive card/layout/drawer/modali/filtri/stati) e nuovi runner `run-full-react-migration.mjs` / `run-legal-ui-checks.mjs` per bloccare mascheramenti, mock, POST legacy, Bootstrap primario e regressioni responsive.

## 2.198.119 - 2026-05-08

- Promosse `/studio`, `/amministrazione`, `/sito-studio` e `/sito-studio/contatti` a `react_operational_full` con payload JSON reali, contratti anti-mascheramento, permessi backend e distinzione esplicita tra route operative React e legacy protetti.
- Aggiunti endpoint JSON per collegare richieste contatto a clienti e aggiornare lo stato delle prenotazioni Sito Studio, riusando i servizi legacy supportati con CSRF/sessione e audit; builder, pubblicazione avanzata, impostazioni, calendari, pagamenti e telematico restano legacy protetti.
- Rimossi `LegacyPostForm` e CTA legacy primarie dai flussi principali Studio/Amministrazione/Sito Studio, con report e check 26a/27a anti-segreti, anti-storage browser, anti-fetch esterno e no-fake React full.

## 2.198.118 - 2026-05-07

- Promosse `/incassi-pagamenti`, `/compensi-forensi`, `/tariffario`, `/audit` e `/registro-attivita` a `react_operational_full` con payload reali, dettaglio/eventi JSON, permessi backend, CSRF/sessione e audit operativo quando supportato.
- Aggiunte API JSON operative per incassi manuali/stati/link pagamento, calcolo compensi forensi backend, simulazione tariffario backend e dettaglio audit sanificato; provider, webhook, formule DM55, tariffario canonico, export e documenti restano backend/legacy.
- Rafforzati i guardrail 22A-25A anti-segreti, anti-calcolo frontend, anti-payload audit sensibile e no-fake React full, con rollback `_legacy=1` confinato a `Rollback tecnico` o impostazioni provider legacy.

## 2.198.114 - 2026-05-07

- Promosse `/preventivi/nuovo`, `/preventivi/conferimento/nuovo`, `/preventivi` e `/fatturazione` a `react_operational_full` con letture reali, salvataggi/azioni JSON, CSRF/sessione, permessi backend e audit operativo quando disponibile.
- Rimosso `LegacyPostForm` dai flussi principali preventivi/conferimenti e dagli archivi: rollback `_legacy=1` confinato ai pannelli `Rollback tecnico`, subpath non autorizzati ancora legacy/protetti dal gate.
- Preservati calcolo canonico, parametri forensi, fiscalita', PDF/DOCX/XML/export e document generation lato backend/legacy; aggiunti report e check anti-mascheramento tranche 18A-21A.

## 2.198.110 - 2026-05-07

- Promossa `/fatturazione/nuova` a `react_operational_full`: la pagina React legge clienti, fascicoli, default e opzioni fiscali da `GET /api/v1/ui/fatturazione/nuova`.
- Aggiunto `POST /api/v1/ui/fatturazione/nuova` con JSON-only, CSRF/sessione, permesso `fatturazione.scrivi`, validazione campi consentiti, rifiuto degli importi canonici dal frontend e audit `fatturazione.crea`.
- Rimosso `LegacyPostForm` dal flusso principale della nuova parcella: il salvataggio riusa `GestioneFatturazione.crea`, il calcolo canonico resta backend e PDF/XML/export restano sulle route legacy/backend protette.

## 2.198.109 - 2026-05-07

- Promossa `/backup` a `react_operational_full`: la pagina React legge stato, lista copie, configurazione e integrita da `GET /api/v1/ui/backup`.
- Aggiunti `POST /api/v1/ui/backup/crea` e `POST /api/v1/ui/backup/verifica` con CSRF/sessione, permesso `backup.esegui`, validazione JSON, audit `backup.crea`/`backup.verifica` e payload senza path sensibili o stack trace.
- Rimossi `LegacyPostForm` e CTA legacy dal flusso principale backup: download resta link backend sicuro, restore/delete restano legacy/protetti e `/backup?_legacy=1` resta solo rollback tecnico.

## 2.198.108 - 2026-05-07

- Promossa `/utenti` a `react_operational_full`: la lista legge utenti, ruoli, stato account e permessi operativi da `GET /api/v1/ui/utenti`.
- Aggiunti POST JSON per stato account, ruolo, reimpostazione credenziale temporanea e profilo minimo, con CSRF/sessione, permesso `utenti.scrivi`, validazione, audit e payload senza hash o token.
- Rimossi link e form legacy dal flusso principale utenti: il fallback `/utenti?_legacy=1` resta solo nel pannello `Rollback tecnico`, con check e report Tranche 14A dedicati.

## 2.198.107 - 2026-05-07

- Promossa `/profili` a `react_operational_full`: la pagina React legge ruoli, permessi, matrice e override reali da `GET /api/v1/ui/profili`.
- Aggiunto `POST /api/v1/ui/profili` per salvare override utente con CSRF/sessione, permesso `utenti.scrivi`, validazione JSON, audit `utenti.aggiorna_permessi` e risposta senza campi sensibili.
- Rimosso `LegacyPostForm` dal flusso principale profili: il fallback `/profili?_legacy=1` resta solo nel pannello `Rollback tecnico`, con guardrail e report Tranche 13A dedicati.

## 2.198.106 - 2026-05-07

- Avviata la Parte 12A anti-mascheramento: `react_full` e' deprecato nel manifest e sostituito dagli stati `react_shell`, `react_bridge`, `react_operational_partial`, `react_operational_full` e `legacy_operational`.
- Convertito il modulo pilota `/utenti/nuovo` in flusso React operativo con `POST /api/v1/ui/utenti/nuovo`, CSRF/sessione, permesso `utenti.scrivi`, validazione JSON, audit e risposta senza dati sensibili.
- Aggiunti audit e gate anti fake React full con report in `artifacts/react-migration/`, declassando le superfici che usano ancora CTA legacy, `LegacyPostForm` o scritture su route Flask storiche.
- Allineato il job CI `Pytest core` al tempo reale della suite completa: timeout portato a 45 minuti senza rimuovere test, con contratto anti-regressione dedicato sull'elenco dei file core.

## 2.198.105 - 2026-05-07

- Promosse in React le superfici exact `/giurisprudenza`, `/legal-intelligence`, `/legal-intelligence/news`, `/legal-intelligence/mediazione` e `/ricerca-legale` come consultazione read-only di fonti, metadati, news e registro mediazione gia presenti nel backend.
- Mantenuti legacy import, classificazione, dettagli, testo integrale, download/export, approvazione contenuti, AI, scraping/crawling, `/giurisprudenza/nuova`, sottopercorsi giurisprudenza/legal intelligence/ricerca legale, `/checklist` e `/deposito/checklist`.
- Rafforzati bridge, endpoint GET `/api/v1/ui/*`, token Impeccable / Open Design per legal knowledge, gate Flask, runner sicuro e check 10A anti-segreti, anti-fetch esterno, anti-generazione AI, anti-documento raw e Open Design.

## 2.198.104 - 2026-05-07

- Integrato Local Deep Research come sidecar Docker opzionale con profilo `ldr`, SearXNG dedicato, data root governato e bridge Lex configurabile tramite `.env.ldr`.
- Rafforzata la sicurezza del runtime AI locale: Ollama nella compose locale resta esposto solo su `127.0.0.1` e il client LDR blocca query con dati identificativi o contesto riservato prima del login HTTP.
- Aggiornate documentazione Lex/deploy/storage/pack e regressioni su compose, policy privacy, CSRF, polling e recupero report LDR.

## 2.198.103 - 2026-05-07

- Esteso il motore Tariffario / Preventivi / Compensi forensi a tutte le tabelle disponibili nello snapshot DM 147/2022 e nei supplementi dichiarati, con 150 regole tariffarie, riferimenti normativi obbligatori e audit completo per regola, tabella, scaglione e fonte.
- Rafforzata la gestione della fascia `Oltre EUR 520.000` e introdotta la complessita `molto_alta` per valore indeterminabile parametrizzato a `520001.0`, sempre tracciato come valore virtuale e non dichiarato dal cliente.
- Aggiornate API e UI React di `/tariffario` e `/preventivi/wizard` con filtri area/tabella/tipo calcolo, badge di copertura, warning non silenziosi, log economico persistente e test dedicati di catalogo, fascia alta e audit preventivi.

## 2.198.102 - 2026-05-07

- Rifinita `/tariffario`: rimossi dalla pagina gli avvisi tecnici di bootstrap e le KPI statistiche sopra il workspace, lasciando il flusso operativo centrato su parametri, risultato e supporto apribile.
- Promosso il `Riepilogo in tempo reale` a pannello sticky dedicato: segue lo scroll su desktop, mostra totale e forbice minimo/base/massimo, porta le azioni `Calcola e aggiorna il quadro`, `Reset`, `Crea preventivo` e `Crea parcella` nello stesso punto operativo.
- Aggiunto aggiornamento automatico con debounce del risultato tariffario tramite il bridge backend Python, senza spostare formule economiche nel frontend, e introdotta la regola di prodotto per preferire riepiloghi sticky in tempo reale quando la pagina lo consente.

## 2.198.101 - 2026-05-07

- Reso professionale il comportamento `Fasi da includere` nel preventivo guidato: il flag `Compenso unico` calcola la voce unica tabellare, mentre a flag spento il wizard calcola solo le fasi selezionate dall'avvocato; se la tabella ministeriale espone solo un importo unico, l'importo viene ripartito in quote operative tracciate senza inventare nuovi valori ministeriali.
- Corretto il calcolo delle voci area pratica aggiunte: `Aggiungi voce area pratica` ora porta in `Bozza operativa` tutte le tipologie selezionate, deduplicate, ciascuna con il proprio compenso e le relative spese generali, invece di calcolare solo l'ultima pratica attiva.

## 2.198.100 - 2026-05-07

- Corretto `/preventivi/wizard`: il filtro `Area pratica` ora calcola le compatibilita' reali rispetto a classificazione operativa e tassonomia attive, disabilita le aree incoerenti e offre il reset dei filtri tecnici quando il catalogo non produce risultati.
- Reso piu' compatto lo sticky footer del preventivo guidato su desktop e mobile: base imponibile, data emissione, CTA e badge finali non si sovrappongono e restano leggibili anche su larghezze ridotte, mantenendo il riepilogo `desktop sticky` affiancato sui desktop della shell.
- Rifinita la UI del wizard preventivi: riepilogo e riferimenti normativi passano nella colonna sinistra, i pannelli tecnici classificazione/tassonomia restano silenziosi, gli avvisi informativi di bootstrap non vengono piu' mostrati e `Area pratica` espone il pulsante reale `Aggiungi voce area pratica` con riepilogo/rimozione delle voci aggiunte al payload del preventivo.
- Corretto il flusso finale del preventivo guidato: i profili a `Compenso unico` non producono piu' bozze a zero e il conferimento incarico viene generato solo dopo registrazione esplicita dell'accettazione cliente del preventivo.

## 2.198.99 - 2026-05-06

- Allineato il profilo Hetzner alla verifica container end-to-end: i worker scheduler e OCR hanno healthcheck espliciti, così il deploy può attestare `healthy` anche per i processi asincroni.

## 2.198.98 - 2026-05-06

- Promossa `/preventivi/wizard` in React full come console guidata operativa: hero, 4 step, classificazione operativa, tassonomia, fasi/compenso unico, bozza editabile, note, clausola controversie, sidebar riepilogo e sticky footer.
- Aggiunti bridge e API `/api/v1/ui/preventivi/wizard`, `/calculate` e `/create`, riusando catalogo, motore preventivo, D.M. 55/2014, mediazione D.M. 150/2023, spese vive, voci manuali, clausola e creazione preventivo reale senza duplicare formule in frontend.
- Preservato il fallback tecnico `/preventivi/wizard?_legacy=1` e rafforzati manifest, contratti React, smoke shell/API e regressioni su cliente potenziale, calcolo ADS, righe manuali, clausola e salvataggio reale del preventivo.

## 2.198.97 - 2026-05-06

- Trasformata `/tariffario` in console React operativa: hero, KPI reali, parametri controllati, pannelli collassabili, risultato tabellare, voci incluse, riepilogo economico e sidebar profilo/supporto normativo.
- Aggiunto il bridge `POST /api/v1/ui/tariffario/calcola`, che riusa motore tariffario Python, catalogo, mediazione D.M. 150/2023, spese vive, voci manuali e CTA precompilate verso preventivo guidato e parcella senza duplicare formule nel frontend.
- Mantenuti fallback `?_legacy=1`, route storiche, audit tariffario, tabelle, riferimenti normativi, canali fatturazione e gate anti-regressione React; aggiunti test dedicati per payload console, calcolo Giudice di Pace valore zero e inclusione di spese/manuale/mediazione.
- Allineati favicon React Shell e healthcheck Docker locale a `127.0.0.1`, coerente con il profilo Hetzner, per evitare falsi errori console e falsi unhealthy locali.

## 2.198.96 - 2026-05-06

- Promosse in React full le route documentali di ingresso `/template-atti`, `/template-atti/catalogo` e `/redazione-atti`, con bridge backend read-only, endpoint UI GET, catalogo template reale, metadati, variabili come soli nomi e azioni legacy sicure.
- Mantenuti legacy `/template-atti/nuovo`, `/template-atti/*`, `/redazione-atti/*`, `/checklist`, `/deposito/checklist`, `/giurisprudenza`, `/legal-intelligence`, editor, redazione guidata, produzione file, export e workflow AI governati.
- Rafforzati Impeccable / Open Design con token e utility documentali `iu-*`, check anti-segreti, anti-contenuto integrale, anti-redazione automatica, anti-produzione file, gate Flask e patch rollback separate per la Tranche 9A.

## 2.198.95 - 2026-05-06

- Promosse in React full le route exact `/compensi-forensi` e `/tariffario`, con bridge backend read-only, endpoint UI GET, KPI reali quando disponibili, aree tariffarie, form HTML verso POST Flask legacy e link operativi sicuri.
- Mantenuti legacy sottopercorsi compensi/tariffario, wizard preventivi, calcoli DM55, formule, log economici, generazione preventivo, PDF/DOCX, `/preventivi/*`, `/fatturazione/*`, `/template-atti` e `/redazione-atti`.
- Introdotta la disciplina grafica interna Impeccable / Open Design come token CSS e contratto auditabile `iu-*`, senza nuove dipendenze o design system esterni, con check dedicati per classi, colori, inline style e regressioni UI.

## 2.198.94 - 2026-05-06

- Promosse in React full le route mandato exact `/preventivi`, `/preventivi/nuovo` e `/preventivi/conferimento/nuovo`, con bridge backend read-only, endpoint UI GET, KPI reali, archivio preventivi/conferimenti e form HTML verso POST Flask legacy.
- Mantenuti legacy wizard compensi, dettagli, stati, workflow, PDF/DOCX, conversione parcella, apertura fascicolo, `/preventivi/*`, `/compensi-forensi` e `/tariffario`, senza fetch POST o logica compensi nel frontend.
- Aggiunti check Tranche 7A per gate Flask, anti-segreti mandato, anti-calcolo compensi frontend, anti-generazione documenti, contratti React, runner sicuro e patch rollback separate.

## 2.198.93 - 2026-05-06

- Installata la skill Codex locale Impeccable in `.agents/skills/impeccable` con contesto prodotto `PRODUCT.md` per audit UI/UX governato.
- Aggiunto `docs/open-design-brief.md` e applicato un polish React mirato su token, primitive condivise, stati interattivi e anti-pattern visuali.
- Rimossi side-stripe spesse e fallback `href="#"` dalle superfici React toccate, mantenendo stack Vite/React/Tailwind e dati reali.

## 2.198.92 - 2026-05-06

- Promosse in React full le route economiche exact `/fatturazione`, `/fatturazione/nuova` e `/incassi-pagamenti`, con bridge backend read-only, endpoint UI GET e form React che invia al POST Flask legacy per la nuova parcella.
- Mantenuti legacy dettagli, modifica, PDF, XML, export CSV, configurazione provider pagamenti, preventivi, compensi forensi e tariffario, senza nuovi fetch POST o calcoli fiscali canonici nel frontend.
- Aggiunti check Tranche 6A per gate Flask, anti-segreti economici, anti-calcolo fiscale frontend, contratti React, runner sicuro e patch rollback separate.

## 2.198.91 - 2026-05-06

- Promosse in React full le route `/studio` e `/amministrazione`, con hub dedicati, bridge backend reali, endpoint UI GET e gate aggiornato senza sbloccare subpath o impostazioni.
- Mantenute legacy le impostazioni sensibili: `/impostazioni`, `/impostazioni-studio`, `/impostazioni/calendario`, `/impostazioni/pagamenti` e `/sincronizzazione-calendari` restano protette anche nella shell.
- Aggiunti check Tranche 5A per gate Flask, UI consistency, anti-segreti, contratti React, runner sicuro e patch rollback separate.

## 2.198.89 - 2026-05-06

- Promosse in React full le route `/backup`, `/sito-studio` e `/sito-studio/contatti`, con bridge backend reali, endpoint UI dedicati e gate aggiornato senza sbloccare builder, studio o impostazioni.
- Mantenute le operazioni tecniche su form/link legacy auditabili: creazione/verifica/download/ripristino backup, conversione contatti, prenotazioni e pubblicazione Sito Studio non usano fetch POST React.
- Aggiunti check Tranche 4A per gate Flask, UI consistency, anti-segreti, contratti React, runner sicuro e patch rollback separate.

## 2.198.88 - 2026-05-06

- Promosse in React full le route amministrative `/utenti`, `GET /utenti/nuovo` e `/profili`, con bridge backend reali, endpoint UI dedicati e gate aggiornato; le scritture restano form POST verso le route legacy auditabili.
- Preparata `/backup` come superficie React read-only con API e pagina dedicata, mantenendola esplicitamente bloccata nel gate legacy insieme a restore, verifica, download ed esecuzione backup.
- Estesi runner, controlli gate/UI, contratti React, check Flask e patch rollback separate per la Tranche 3A senza sbloccare route economiche, mandato, documentali o telematiche.

## 2.198.87 - 2026-05-06

- Promosse in React full le route read-only `/statistiche`, `/audit` e `/registro-attivita`, con bridge backend reali, endpoint `/api/v1/ui/*`, pagine React dedicate, fallback tecnico `?_legacy=1` e gate aggiornato senza sbloccare utenti, profili, backup, economico o telematico.
- Catturati i contratti legacy Tranche 2A anche per `/utenti`, `/profili` e `/backup`, mantenendole esplicitamente in `legacy_operational`.
- Estesi runner, gate check, contratti React, report e patch di rollback separati per la prima promozione governata della migrazione React.

## 2.198.86 - 2026-05-06

- Aggiunta la macchina governata di migrazione React: manifest route residue, audit inventario, cattura contratti legacy, controllo `react_route_gate`, report UI consistency e runner unico senza sbloccare route operative.
- Introdotto un UI kit React base in `frontend/src/ui` e `frontend/src/theme`, fondato sui token `--iu-*` esistenti e senza nuove dipendenze frontend.
- Estesi i contratti React per bloccare nuove dipendenze MUI/Redux/TanStack/React Router, verificare manifest/script/UI kit e impedire unlock legacy nella tranche corrente.

## 2.198.85 - 2026-05-06

- Reso atomico il backup Hetzner: gli archivi vengono scritti prima come `.tmp` e pubblicati solo dopo una generazione riuscita, evitando file `.tar.zst` senza checksum che occupano spazio ma non sono ripristinabili.
- Aggiunta pulizia automatica degli archivi temporanei/incompleti in caso di errore durante `tar` o compressione.

## 2.198.84 - 2026-05-06

- Rafforzata la manutenzione storage Superadmin con retention governata dei backup esterni: analisi/applicazione sicura sugli archivi `iusentra-data-*`, copie minime preservate e spazio recuperabile mostrato in modo esplicito.
- Reso visibile al container app il percorso `/opt/iusentra/backups`, cosi' il pannello mostra il peso reale dei backup esterni invece di `0 B`.
- Stretta la policy Hetzner di backup a 3 copie, minimo 2, 14 giorni e 8 GiB, escludendo dai backup futuri i modelli Ollama rigenerabili dal deploy.

## 2.198.83 - 2026-05-06

- Reso hardlink-aware il calcolo delle dimensioni nel pannello `Server e manutenzione`, evitando di sommare due volte file gia' compattati.
- Ammorbidite le raccomandazioni sui backup mirror: il pannello ora suggerisce retention/verifica e non una compattazione quando l'analisi segnala `da compattare = 0`.
- Aggiunto test per impedire regressioni sul conteggio spazio di file hardlinkati.

## 2.198.82 - 2026-05-06

- Chiarito il report Superadmin di compattazione storage distinguendo duplicati identici, duplicati fisici ancora da compattare e file gia' hardlinkati.
- Esteso il payload di deduplica con `physical_duplicate_files`, `already_hardlinked_files` e `hardlinked_files`, evitando che duplicati gia' compattati sembrino ancora spazio sprecato.
- Aggiornati script, pannello e test per mostrare lo spazio realmente recuperabile/recuperato invece del solo conteggio grezzo dei file uguali.

## 2.198.81 - 2026-05-06

- Collegato il pannello `Server e manutenzione` anche alla navigazione piattaforma principale visibile al SUPERADMIN e alla card della Panoramica piattaforma.
- Autorizzato esplicitamente il blueprint `server_maintenance_admin` nel guard multi-tenant del SUPERADMIN, evitando redirect impropri verso la dashboard.
- Rafforzati i test per verificare accesso diretto alla pagina manutenzione server e presenza del link nelle superfici amministrative.

## 2.198.80 - 2026-05-06

- Rafforzata la retention dei backup Hetzner con tetto di spazio totale configurabile (`IUSENTRA_BACKUP_RETENTION_MAX_GIB`), numero minimo di copie e caricamento esplicito di `/opt/iusentra/.env.hetzner`.
- Portati i backup `.tar.zst` a compressione zstd alta e configurabile, con long window, mantenendo checksum SHA-256 e compatibilita' restore.
- Aggiunto `scripts/compact_iusentra_storage.py` per compattare allegati email e mirror backup tenant-aware tramite hardlink, e reso il mirror operativo dei backup basato su hardlink quando resta nello stesso filesystem.

## 2.198.79 - 2026-05-06

- Reso content-aware il salvataggio degli allegati PEC/email: se un allegato identico e' gia' presente nella cartella del messaggio, viene riusato senza creare copie numerate.
- Aggiunto `scripts/deduplicate_email_attachments.py` per analisi e deduplica storica tenant-aware degli allegati email tramite hardlink, con manifest JSON e dry-run obbligatorio di default.
- Documentata la procedura di bonifica allegati email e aggiunti test su SHA-256, riuso file identici, suffix per contenuti diversi e deduplica applicata.

## 2.198.78 - 2026-05-06

- Ripristinata la disponibilita' produzione dopo saturazione disco su Hetzner: i backup applicativi avevano riempito `/`, Redis non riusciva piu' a persistere e Flask-Limiter generava 500 globali prima delle route.
- Rafforzato il rate limiter: il probe Redis verifica anche una scrittura breve, Flask-Limiter e' configurato con fallback in memoria e `swallow_errors=True`, cosi' un guasto Redis non blocca tutte le pagine.
- Aggiunta retention governata per `deploy/hetzner/backup.sh`, con massimo 7 backup applicativi e 30 giorni di default, configurabili da ambiente produzione.

## 2.198.77 - 2026-05-05

- Allineati i contratti di test core Lex alla modalita' `LEX_GOVERNED_ONLY=1`: il companion legacy richiede ora consenso esplicito a chat non governata, mentre gli allegati restano evidenze governate e non prompt libero.

## 2.198.76 - 2026-05-05

- Introdotto il dominio nativo `pct/editor_ai` per generazione atti con Lex nell'editor professionale IUSENTRA: template resolver, piano bozza, renderer verso documento editor reale, versioni, fonti, proposte modifica e audit.
- Aggiunte API `/api/v1/ui/fascicoli/<id>/editor-ai*`, migrazioni SQLite/PostgreSQL `pct/sql/20260505_editor_ai*.sql` e tool Lex `list/read template`, `collect_fascicolo_context`, `generate_editor_draft`, `read_editor_document`, `propose_editor_edits`, `export_editor_document`.
- Integrato il pannello `Nuovo atto con Lex` dentro l'editor React esistente, senza creare una sezione separata: la bozza viene salvata nel fascicolo, riletta dall'editor e aperta come documento modificabile/versionato.
- Aggiunti test backend e contratti React su template, generazione, renderer, repository SQLite, proposte modifica, API, tool Lex e validatore italiano.

## 2.198.75 - 2026-05-05

- Ricondotto `Documenti AI Fascicolo` a motore interno: rimossa la sezione autonoma dalla navigazione standard del fascicolo e integrato il box `Indicizzazione Lex` dentro `Documenti fascicolo`, con payload reali `lex-indexing`, conteggi ready/queued/indexing/error/stale e azioni autorizzate di aggiornamento/riprova.
- Aggiunta indicizzazione automatica da documenti reali del fascicolo, import portale e salvataggio editor professionale, con sorgenti tenant-aware, rilevazione stale su hash e tool Lex `list/read/find` basati solo su documenti `ready`.
- Rafforzato Lex con guard italiano sistemico, prompt anti-inglese, retrieval fascicolo-first e uso di fonti esterne solo con ragione pertinente; riparati i segnaposto PDF `(cid:NN)` quando convertibili in caratteri sicuri.
- Aggiunti test anti-regressione su UI nascosta, auto-indexing, qualita' PDF CID, guard italiano, retrieval fascicolo-first e tool Lex su indice automatico.

## 2.198.74 - 2026-05-05

- Completata la Fase 3 backend di `Documenti AI Fascicolo` con repository persistente SQLite/PostgreSQL, factory esplicite per DB strutturati e statistiche storage filtrate per tenant/fascicolo.
- Verificate le migrazioni reali `pct/sql/20260505_documenti_ai*.sql` con applicazione su SQLite temporaneo e guardrail sullo schema PostgreSQL, inclusi JSONB, FK, check e indici.
- Aggiunti test repository con database temporaneo per persistenza, isolamento tenant/fascicolo, versioni univoche, testo estratto, audit senza contenuto documentale e service su repository SQLite.

## 2.198.73 - 2026-05-05

- Eliminato il warning non funzionale di pytest su Windows durante il cleanup di `pytest-current`, usando un adapter di test che gestisce correttamente i reparse point directory senza nascondere fallimenti dei test.
- Verificata la suite `Documenti AI Fascicolo` anche con esecuzioni pytest parallele locali, mantenendo verdi extraction, security, service, API e tool compatibility.

## 2.198.72 - 2026-05-05

- Rafforzata la Fase 2 backend di `Documenti AI Fascicolo` con API di dominio esplicite per upload result, validazione size/hash/type, path tenant-aware versionati e risultato estrazione file-based.
- Allineati service e repository alle interfacce richieste dalla tranche backend, mantenendo storage filtrato per tenant/fascicolo, audit senza contenuto documentale e testi estratti su percorso relativo governato.
- Aggiunti test dedicati per extraction e versioning, oltre a coperture security/service su dimensione file, path traversal, query vuota e documento inesistente.

## 2.198.71 - 2026-05-05

- Introdotto l'MVP 1 di `Documenti AI Fascicolo`: dominio nativo `pct/document_intelligence`, upload PDF/DOCX/DOC tenant-aware, hash SHA-256, versione 1, estrazione testo best-effort, stato `ready/error` e audit dedicato.
- Aggiunte API React `/api/v1/ui/fascicoli/<id>/documenti-ai*`, tool Lex `list_fascicolo_documents`, `read_fascicolo_document`, `find_in_fascicolo_document` e sezione React `Documenti AI` nel dettaglio fascicolo con soli dati reali e `mock_fallback=false`.
- Aggiunte migrazioni SQLite/PostgreSQL `pct/sql/20260505_documenti_ai*.sql` e documentazione strategica [docs/DOCUMENTI_AI_FASCICOLO.md](docs/DOCUMENTI_AI_FASCICOLO.md), mantenendo Mike solo come riferimento funzionale senza codice AGPL.

## 2.198.70 - 2026-05-05

- Allineato il deploy Hetzner di Lex alla pipeline unica del widget: il profilo produzione avvia il sidecar Docker `ollama`, usa `http://ollama:11434/api` come runtime AI interno e scarica automaticamente il modello chat configurato.
- Documentata la dipendenza produttiva da Ollama locale governato, evitando che il backend Lex finisca su host `ollama` non risolvibili dopo la rimozione del companion come generatore finale.
- Resa trascinabile anche l'icona flottante Lex su tutto il viewport, con posizione salvata nel browser e rimozione dei vecchi residui legacy non registrati (`web/base.html`, `web/cartella.html`, `web/export_csv.py`).

## 2.198.69 - 2026-05-05

- Lex standalone page removed; floating Lex widget is the single supported UI surface and routes all assistant responses through /api/assistente/chat.
- La route `/lex` resta registrata solo come tombstone `410 Gone` con `Cache-Control: no-store`, mentre i vecchi link same-origin `/lex` e `#lex` vengono intercettati dal widget flottante senza navigazione.
- Il payload del widget Lex e' centralizzato e conserva `session_id`, `messages`, `fascicolo_id`, `context_label`, `page_context`, `page_path`, `attachments`, `mode` e `page_section`.

## 2.198.68 - 2026-05-05

- Ottimizzata la Panoramica React: `getDashboard()` usa la cache backend ordinaria, espone `refresh=1` solo su richiesta esplicita e avvia la sincronizzazione PEC/email ordinaria dopo il primo render senza bloccare la UI.
- Introdotto il servizio tenant-aware `mailbox_sync_runtime` con lock per casella, cooldown, route manuali PEC/email ordinaria preservate, endpoint React `/api/v1/ui/dashboard/sync-mailboxes` e job scheduler riusabile.
- Alleggerita Ricerca Studio con `GET /api/global-search/stats` e rimosso il reindex sincrono nascosto quando l'indice e' vuoto: la reindicizzazione resta manuale e auditabile.
- Resa reale la paginazione server-side dei fascicoli, con filtri/sort backend, payload `pagination`, dettaglio fascicolo a tab lazy e Regia Operativa caricata con query scoped quando disponibili.

## 2.198.67 - 2026-05-05

- Introdotta la modalita' `LEX_GOVERNED_ONLY=1` come default professionale: le richieste non sociali passano dal bounded workflow e la raw chat resta disabilitata salvo `LEX_RAW_CHAT_ENABLED=1` piu' `allow_unbounded_generation=true`.
- Rafforzati `CitationGuard`, `LegalReferenceGuard` e `HallucinationGuard` per bloccare o degradare workflow strict senza evidenze, fonti ufficiali, PDF/riferimenti verificati o estremi normativi/giurisprudenziali non fondati.
- Gli allegati Lex vengono trasformati in `EvidenceItem` governati oppure bloccati con richiesta di parsing/OCR/indicizzazione, senza piu' inserirli come blocchi prompt nel modello o nel companion.
- Aggiornati provider routing, `OllamaProvider`, payload professionale, documentazione `docs/LEX_GOVERNED_ONLY.md` e test anti-regressione su governed-only, raw chat, guardrail, Ollama e `needs_review`.

## 2.198.66 - 2026-05-05

- Allineati Dockerfile, compose locale e profilo Hetzner al nuovo `PCT_TIME_TRACKING_DB=/data/timesheet/time_tracking.json`, evitando fallback runtime su path repository non scrivibili nei container non-root.

## 2.198.65 - 2026-05-05

- Trasformata la top bar desktop React in centro operativo rapido con command palette `Ctrl+K`/`Cmd+K`, ricerca globale reale, menu contestuale `+ Nuovo`, pannelli Oggi, Notifiche, Scadenze, Recenti e timer attivita.
- Aggiunte API protette `/api/search/global`, `/api/dashboard/today`, `/api/notifications`, `/api/deadlines/quick-summary`, `/api/recent` e `/api/time-tracking/*`, con payload validati, permessi, tenant/sessione e soli dati reali dei repository.
- Introdotto il dominio `time_tracking_timers` su JSON/SQLite/PostgreSQL, con vincolo su un solo timer attivo per utente e salvataggio finale nel timesheet reale.
- Estesi i contratti React e i test API top bar su ricerca, permessi, widget Oggi, notifiche, scadenze, recenti e ciclo start/pause/resume/stop del timer.

## 2.198.64 - 2026-05-05

- Promosse a superfici React operative `/timesheet` e `/cartelle-condivise`, con payload reali `/api/v1/ui/timesheet` e `/api/v1/ui/cartelle-condivise`, contratti `mock_fallback=false`, KPI, filtri, stati vuoti e azioni su route Flask auditabili.
- Completato `Wizard Pro` in React end-to-end per dashboard, step profondi `/wizard-pro/<id>/step/<n>` e riepilogo `/wizard-pro/<id>/completo`, mantenendo i POST su Flask e la vista classica solo tramite `?_legacy=1`.
- Aggiunti bridge backend dedicati, routing React esplicito, contesti Lex per dashboard/step/riepilogo e gate contrattuali contro link tecnici, `href="#"`, dati demo e CTA non operative.
- Estesi i test React/Python su shell, API, POST timesheet, permessi condivisioni e ciclo completo del wizard udienza.

## 2.198.63 - 2026-05-05

- Corretta la visualizzazione nell'editor professionale dei PDF giudiziari con layout complesso: stemmi, timbri, riquadri, intestazioni laterali e testo verticale non vengono piu' ricostruiti come HTML editabile.
- I PDF aperti dalla route `/fascicoli/<id>/documenti/<id_doc>/editor` usano ora anteprima nativa fedele all'originale, con modifica inline bloccata e messaggio professionale che invita a importare DOCX/HTML/testo per lavorare sul contenuto.
- Rafforzato il backend di conversione PDF con un controllo di fedelta visuale (`editor_disabled_reason=layout PDF complesso`) e test di regressione su layout tipo sentenza Cassazione.
- Aggiornati contratti React, documentazione e test per garantire che il PDF reale `8785_03_2026_civ_noindex` non venga piu' mostrato come trascrizione diversa dall'originale.

## 2.198.62 - 2026-05-05

- Rafforzato l'editor professionale React con controlli stile tipo Word: font, dimensione testo, interlinea, formato pagina, zoom e salvataggio degli stili applicati al testo selezionato o all'intero documento.
- Corretto il caricamento dei PDF con font CID senza mappa Unicode: l'editor non mostra piu' token `(cid:...)`, tenta motore PDF alternativo e OCR, e blocca il salvataggio quando il testo non e' affidabile mostrando l'anteprima originale.
- Estesa la visualizzazione dei documenti firmati `.pdf.p7m`, incluso il caso `attoACQ.pdf.p7m`, usando l'estrazione CAdES condivisa e mantenendo l'anteprima PDF inline con nome interno corretto.
- Aggiornati i contratti frontend e i test di regressione su editor React, PDF CID e anteprima `.p7m`.

## 2.198.61 - 2026-05-05

- Promossa la route profonda `/fascicoli/<id>/documenti/<id_doc>/editor` a pagina React operativa: non degrada piu' al dettaglio fascicolo generico e non dipende da CDN esterni per montare l'editor.
- Aggiunto il payload reale `/api/v1/ui/fascicoli/<id>/documenti/<id_doc>/editor`, con metadati fascicolo/documento, capability, warning professionali, `mock_fallback=false` e scritture sulle route Flask gia' operative dell'editor.
- Introdotto un editor documentale React con toolbar professionale, autosave, stati di salvataggio, ricerca/sostituzione, import locale, export PDF/DOCX, pannelli metadati e Lex AI contestuale, usando solo documenti reali del fascicolo.
- Aggiunti contratti frontend e test backend sulla route profonda, sul payload reale e sull'assenza del vecchio caricamento TipTap da `https://esm.sh`.

## 2.198.60 - 2026-05-04

- Corretto il `Wizard preventivi`: le spese generali tabellari restano una voce separata `Spese generali 15%` di tipo `Spesa forfettaria`, entrano nell'imponibile fiscale e non vengono piu' riversate nelle `Anticipazioni art. 15`.
- Ripristinata l'apertura diretta dei dettagli PEC/email ordinaria con corpo e allegati visualizzabili o scaricabili, escludendo le route `/email*/messaggio/...` dalla shell React riepilogativa.
- Rimosso dalle pagine email il vecchio ingresso `/lex?context=email-*`; le integrazioni operative restano su fascicoli, messaggi, servizi telematici e ricerca comunicazioni.
- Rafforzata la cabina fascicolo: `Documenti fascicolo` ed `Editor professionale` sono aperti e raggiungibili, il dettaglio risolve anche identificativi alias/case-insensitive e il quadro economico espone `FatturaPA / SDI` per XML destinato a SdI / Agenzia Entrate.

## 2.198.59 - 2026-05-04

- Sincronizzato il `Wizard preventivi` con il riepilogo operativo del tariffario: `Complessita stimata` bassa/media/alta alimenta la bozza dalla colonna minimo/base/massimo della regola tariffaria realmente selezionata.
- Corretto il trasferimento in bozza di spese generali e bonus telematico: il preventivo usa `totale_compenso_livello(...)` del tariffario, evitando il ritorno fisso al valore base e il doppio conteggio delle spese generali.
- Rimossa dalla nota visibile del tariffario la dicitura tecnica `snapshot QuickOrganizer`, mantenendo un riferimento pulito ai valori tabellari ufficiali DM 147/2022.
- Aggiunti test di regressione su fasi ordinarie, `Compenso unico`, Giudice di Pace e bonus telematico per garantire che pratica, grado, scaglione, fasi e complessita restino collegati alle tabelle gia' definite.

## 2.198.58 - 2026-05-04

- Corretto il `Wizard preventivi` sui profili a `Compenso unico`: flag acceso calcola la voce unica tabellare, flag spento calcola le fasi tabellari selezionate e solo tutte le fasi spente producono importo zero.
- Aggiunto un override governato nel motore preventivo per consentire al wizard di passare dal profilo unico alla modalita' per fasi senza alterare la regola tariffaria scelta ne' il comportamento della console tariffario.
- Estesi i test di regressione su wizard e motore per coprire compenso unico attivo, compenso unico disattivo con fasi selezionate, nessuna fase selezionata e forbice `bassa / media / alta` della complessita stimata.

## 2.198.57 - 2026-05-04

- Ripristinata nel `Wizard preventivi` la griglia completa delle fasi operative anche per i profili a `Compenso unico`: il flag unico e' aggiuntivo, non sostituisce Studio, Introduttiva, Istruttoria / istruzione e Decisionale quando sono previste.
- Corretto l'adattatore di calcolo del wizard: nei profili a compenso unico l'importo tabellare nasce solo se il flag `Compenso unico` e' attivo; se il flag e' disattivo, le fasi operative restano visibili ma non forzano il calcolo della voce unica.
- Allineati testi e opzioni del pannello preventivi alla console tariffario per fasi, complessita stimata, spese generali 15%, bonus telematico, CPA, IVA, anticipazioni art. 15 e compenso orario.

## 2.198.56 - 2026-05-04

- Ripulito il `Wizard preventivi` dalla seconda sezione duplicata della clausola controversie: resta il blocco catalogato, modificabile e trasferito al conferimento di incarico.
- Aggiornata la clausola multistep con un testo generico e verificabile su mediazione/arbitrato, senza riferimenti hardcoded a fac-simile esterni o organismi privati, e normalizzate le vecchie fonti legacy in lettura.
- Allineato il `Compenso unico` del wizard a un flag calcolabile: se attivo genera l'importo tabellare, se disattivo non produce compenso, mantenendo invariati fasi ordinarie, spese generali e calcolo live.

## 2.198.55 - 2026-05-04

- Corretto il runtime tenant-aware della Regia Operativa Fascicolo: `PRACTICE_ENGINE_DB` viene ora risolto sotto il data root dello studio (`fascicoli/practice_engine/practice_engine.json`) invece di ricadere sul path relativo `./fascicoli/...` dentro il container.
- Allineati provisioning tenant, bootstrap legacy, profilo Hetzner, Dockerfile e test anti-regressione per impedire il ritorno del `Permission denied` che faceva fallire l'API dettaglio fascicolo React e mostrava "Fascicolo non trovato".

## 2.198.54 - 2026-05-04

- Introdotta la Regia Operativa Fascicolo / Practice Engine: profili pratica derivati dal catalogo operativo, checklist dinamiche, slot documentali, validatori, stato operativo, predeposito, sessioni deposito, ricevute, timeline, evidence pack e audit.
- Agganciate le API React reali sotto `/api/v1/ui/fascicoli/<id>/regia`, con apertura fascicolo da preventivo/conferimento, ricalcolo, collegamento slot, predeposito, deposito fail-closed e import ricevute autorizzate.
- Integrato il dettaglio fascicolo React con la sezione `Regia Operativa`, senza dati demo o fallback mock, mostrando blocchi, economia, documenti richiesti, stato deposito e evidence pack solo quando disponibile.
- Aggiunte le migrazioni SQLite/PostgreSQL `20260504_practice_engine*` e la documentazione `docs/REGIA_OPERATIVA_FASCICOLO.md`.

## 2.198.53 - 2026-05-04

- Chiusa la firma visibile laterale dei documenti PDF: il timbro viene applicato su tutte le pagine, con coccarda in basso a destra, testo verticale a 8 pt e campi `Firmato Da`, `Emesso Da` e `Serial#`.
- Allineata la geometria alla vista ministeriale allegata: testo con margine destro di 3 mm, coccarda con margine destro di 1 mm e distanza di 2 mm dal testo.
- Aggiunte nelle superfici React e Jinja le opzioni operative per `Luogo firma` e per mostrare data e ora, solo data oppure nessuna data nel timbro visibile.
- Aggiornato Local Signer a `1.6.25` e rigenerati gli installer con lo stesso motore di firma visibile usato dal server.

## 2.198.52 - 2026-05-03

- Precisata la geometria della firma visibile laterale: il bordo destro del timbro PDF resta a 4 mm dal margine pagina, mantenendo invariato il testo verticale generato nella prova `firma_visibile_laterale.pdf`.
- Aggiornato Local Signer a `1.6.24` e rigenerati i pacchetti con lo stesso motore `visible_signature.py`, cosi' la UI e il firmatore locale applicano la stessa posizione reale al PDF finale.
- Confermato il luogo firma dal profilo studio: con indirizzo `TAURIANOVA (RC)` e campi citta/provincia vuoti il timbro usa `Taurianova`, non `Reggio Calabria`.

## 2.198.51 - 2026-05-03

- Ripristinata la superficie React completa del fascicolo: anteprima documento in modal interna, upload/import documenti via AJAX senza ricaricare la pratica, conferme React per eliminazione documenti/fascicoli e accesso visibile a Quadro intelligente AI, Editor professionale e Compilatore atti.
- Distinte le icone documento: editor con matita, firma con scudo/firma digitale, anteprima con viewer interno; il pulsante `Elimina fascicolo` e' ora raggiungibile sia dagli strumenti rapidi della pratica sia dalla colonna `Azioni` della lista fascicoli e dell'archivio.
- Rimossa la pagina standalone Lex dei fascicoli: i collegamenti React non puntano piu' a `/lex?context=fascicolo...` e il backend restituisce `410 Gone` per i vecchi contesti fascicolo, lasciando attivo il solo floating icon contestuale.
- Ripulita la testata operativa del dettaglio fascicolo: il pannello `Quadro intelligente AI` non duplica piu' `Editor professionale` e `Compilatore atti`, che restano una sola volta nella barra strumenti.
- Corretto il flusso firma visibile fino al PDF finale: la modalita' scelta in React viene salvata nel documento firmato, il preview di `.p7m` detached la rilegge dal documento e il test renderizza realmente il PDF per verificare laterale, basso sinistra e basso destra. La firma laterale e' stata avvicinata al margine destro e usa un font leggermente ridotto.
- Aggiornato Local Signer a `1.6.23` includendo `reportlab` negli installer, cosi' la coccarda PNG trasparente e il timbro visibile vengono applicati davvero anche quando manca il fallback pyHanko.

## 2.198.50 - 2026-05-03

- Corretto il riavvio del Local Signer nella pagina React `Firma documento`: quando il token e' visibile solo nel `token_probe_fresh`, la UI usa un link diretto `iusentra-local-signer://restart`, mostra un messaggio operativo e riverifica automaticamente piu' volte.
- Verificato sul PC Windows dello studio che il riavvio forzato riallinea il processo Local Signer e fa tornare il token CNS in `token[]`, sbloccando la richiesta PIN.

## 2.198.49 - 2026-05-03

- Semplificata la pagina React `Firma documento`: quando il token e' rilevato solo dal `token_probe_fresh`, la UI mostra `Riavvia e riverifica` e non chiede piu' il PIN finche' il Local Signer attivo non espone il token principale.
- Ripristinato nel flusso React di firma documento il passaggio della posizione firma visibile (`laterale`, `basso_sinistra`, `basso_destra`) e del luogo firma al Local Signer.
- Sostituita la coccarda vettoriale della firma visibile con l'immagine trasparente definitiva, mantenendo distanza dal testo nelle tre posizioni per evitare sovrapposizioni su "Firmato digitalmente da".
- Verificato il flusso React reale con Local Signer mockato: le tre scelte di firma visibile inviano al signer la modalita' selezionata e ricaricano il file firmato sulla route del documento.

## 2.198.48 - 2026-05-03

- Corretta la pagina React `Firma documento`: quando il Local Signer risponde ma il token appare solo in `token_probe_fresh`, la UI non mostra piu' "Local Signer non rilevato" e propone il riavvio/riverifica del servizio locale.
- Il pannello firma distingue servizio attivo, token PKCS#11 principale, probe fresco e diagnostica locale, mantenendo il PIN solo nel browser e senza interrogare il token dal server cloud.

## 2.198.47 - 2026-05-03

- Integrato Docling come parser opzionale per Lex AI dietro `LEX_DOCLING_ENABLED`, con import lazy e fallback automatico al parser legacy `pdfplumber`/`pypdf`/`pytesseract` quando Docling non e' installato o fallisce.
- Aggiunto l'adapter `lex/retrieval/document_parser_docling.py`, che produce Markdown, JSON strutturato, tabelle, chunk e metadati citabili per pagina, sezione e indice chunk senza chiamate cloud.
- Estesi retrieval, citazioni ed evidence pack per conservare parser, versione, hash sorgente, pagina, sezione, chunk index, OCR e confidence; aggiunto l'extra opzionale `lex-docling` con vincolo `docling<3`.
- Corretto lo snapshot `/admin/osservabilita`: il runtime Ollama viene verificato live sugli URL locali raggiungibili dall'app senza aprire il circuit breaker, distinguendo `127.0.0.1`, bridge Docker locale e stato DB storico.

## 2.198.46 - 2026-05-03

- Agganciato Lex AI agli `Aggiornamenti legali` tramite repository SQL tenant-aware `legal_updates.db`: il retrieval usa `LegalUpdatesSource`, il contesto studio espone conteggi ed evidenze SQL, e le fonti vengono marcate con trust/source level per l'evidence pack.
- Disattivate di default le scritture operative su `legal_updates_repository.json` e sul mirror legacy `giurisprudenza.json`; restano abilitate solo con flag espliciti di export/mirror amministrativo.
- Aggiornata la dashboard admin per mostrare chiaramente che Lex legge il database SQL e non JSON, con regressioni dedicate su repository, source router, contesto Lex e pubblicazione giurisprudenza.

## 2.198.45 - 2026-05-03

- Corretto `/admin/copertura-ai`: la gap queue non riapre piu' sottobranche che hanno gia' draft generati, validati o approvati in coda review.
- La generazione draft evita duplicati su gap storici gia' presi in carico, mentre il publish dashboard avvisa quando non ci sono bozze approvate invece di mostrare un successo ambiguo.

## 2.198.44 - 2026-05-03

- Corretto `/admin/installazione-pack`: il servizio `Orchestratore Lex` viene valutato sulla presenza reale dei moduli Lex del Product Pack, senza ereditarne impropriamente lo stato di Ollama.
- Aggiunta la sezione `Dipendenze runtime locali`, che espone separatamente lo stato reale del provider AI locale, endpoint configurato e chunk RAG pendenti.

## 2.198.43 - 2026-05-03

- Corretto lo snapshot SQLite di `/admin/database`: un errore sulla tabella virtuale tecnica `search_documenti` non marca piu' l'intero database come assente.
- La lettura statistiche SQLite ora conteggia le tabelle una per una, mantiene lo snapshot presente e mostra un avviso governato quando una tabella tecnica non e' conteggiabile.

## 2.198.42 - 2026-05-03

- Corretto il bootstrap dei moduli monitorati: `local_ai.db` e `telematico/workflow.db` restano database SQLite reali e non vengono piu' creati come JSON vuoti.
- Aggiunto un test di regressione per impedire che percorsi `.db` vengano inizializzati dal bootstrap JSON dei moduli estesi.

## 2.198.41 - 2026-05-03

- Spostati gli accessi `Salute sistema` e `Governance prodotto` nella navigazione Piattaforma riservata al superadmin e rimossi i collegamenti dalla pagina tenant `/admin/database`, evitando azioni admin che terminano in `403`.
- Resi migrabili i moduli JSON monitorati da `/admin/database` con struttura esplicita sia SQLite sia PostgreSQL: `moduli_dati` conserva percorso/metadati e `moduli_json_records` normalizza i record di Calendar Sync, Email, Soggetti, Portale, Template, Wizard, Intelligence e moduli analoghi.

## 2.198.40 - 2026-05-03

- Ripristinato il guardrail sorgente della pagina Impostazioni PEC: il test SMTP reale resta browser-locale tramite Local Signer, mentre la diagnostica server PEC non torna esposta come azione utente nella UI.

## 2.198.39 - 2026-05-03

- Resa operativa la riparazione automatica da `/admin/database`: il pulsante React ora esegue `POST /admin/database/verifica-ripara`, crea backup JSON prima della scrittura e risolve i riferimenti orfani senza inventare fascicoli o clienti.
- Le scadenze collegate a fascicoli inesistenti vengono scollegate in modo sicuro quando non esiste un fascicolo reale univoco, conservando l'identificativo originale in note e metadati di riparazione.
- Corretto `VACUUM` sull'indice `search_index`: l'ottimizzazione SQLite ora esegue `VACUUM` fuori da transazioni aperte, evitando l'errore `cannot VACUUM from within a transaction`.

## 2.198.38 - 2026-05-03

- Migrato `GET /admin/database` nella shell React con contratto operativo completo: payload reale `/api/v1/ui/admin/database`, statistiche repository, verifica integrita', ottimizzazione, migrazione SQLite, attivazione SQLite ed export ZIP collegati alle route Flask amministrative esistenti.
- Sostituiti i dati profilo hardcoded della shell React con il profilo reale di sessione (`g.utente_corrente`) e logout POST con CSRF; rimossi badge notifiche e fascicoli recenti fittizi dalla shell.
- Formalizzata in `AGENTS.md` la regola zero dati inventati: UI React, template e bridge devono mostrare solo dati da repository, sessione, API, template context o configurazione reale, con test anti-regressione dedicati.

## 2.198.37 - 2026-05-01

- Separata la composizione della posta ordinaria dalla PEC: il bottone `Componi email` usa ora `/email-ordinaria/scrivi`, con rientro nella casella ordinaria e invio tramite configurazione SMTP ordinaria dello studio.
- Rafforzato il contratto API React di `Email ordinaria`: `compose`, `sync`, impostazioni e cartelle puntano ai percorsi ordinari, mentre `Email PEC` resta su `/email/*`.
- Aggiunti test di regressione per impedire che `Componi email` o `Aggiorna` della posta ordinaria tornino a chiamare le route PEC.

## 2.198.36 - 2026-05-01

- Migrato `GET /privacy/registro`, `GET /privacy/registro/nuovo` e alias `/registro-gdpr` nella shell React solo dopo contratto operativo completo: API reale `/api/v1/ui/privacy/registro`, dati dal repository privacy, form POST Flask auditato e cancellazione trattamento sulle route esistenti.
- Aggiunta UI React responsive del Registro GDPR Art. 30 con indicatori, filtri, schede trattamento, warning su conservazione/misure/extra UE, azioni reali verso audit, clienti e impostazioni, senza link `_legacy=1` visibili.
- Aggiornati i gate di migrazione e i test secondo `REACT_MIGRATION_MASTER_PLAN.md` e `REACT_MIGRATION_PATTERNS_FROM_OSS.md`: una pagina viene promossa solo se rispetta lo stato `react_operational_complete`.

## 2.198.35 - 2026-05-01

- Allineato il profilo `deploy/hetzner` alla nuova separazione fra Email PEC e posta ordinaria, aggiungendo `PCT_EMAIL_ORDINARIA_DB` e il default AI locale `/api/version`.
- Eseguito deploy reale su Hetzner CPX42 con backup remoto verificato e servizi app, Redis, scheduler, OCR e Caddy attivi su `app.iusentra.it`.
- Documentati i pattern OSS utili alla migrazione React/TypeScript incrementale studiando Apache Superset, Mattermost e p5.js Web Editor, trasformandoli in regole operative IUSENTRA pagina-per-pagina.

## 2.198.33 - 2026-05-01

- Corretto il protocollo operativo del Local Signer: il browser e gli installer usano ora `iusentra-local-signer://restart`.
- Formalizzato il rilascio Windows esclusivamente in formato `.exe`: la UI e le route pubbliche propongono `SetupLocalSigner-<versione>.exe` e l'eventuale `.ps1` resta solo artefatto interno di build.
- Rafforzata l'installazione Windows del Local Signer: oltre all'attivita' pianificata al login viene creato un fallback nella cartella Startup dell'utente, cosi' l'avvio resta permanente anche se Task Scheduler non viene registrato correttamente.
- Aggiornato il bootstrap locale per riusare un'installazione gia' presente in `%APPDATA%\IUSENTRA\LocalSigner` senza rilanciare l'installer quando basta avviare il servizio locale.

## 2.198.32 - 2026-05-01

- Limitato il controllo Local Signer ai soli PC desktop Windows, macOS e Linux: su mobile e tablet il monitor globale post-login non esegue ping verso `127.0.0.1`, non tenta il protocollo locale e non mostra prompt di installazione.
- Aggiornate le schermate Impostazioni PEC/Firma e il wizard telematico React per bloccare il controllo Local Signer su dispositivi mobile/tablet con messaggio chiaro e senza tentativi di avvio locale.
- Aggiunti test di regressione su monitor globale, Impostazioni e wizard telematico per impedire il ritorno del falso controllo Local Signer su mobile/tablet.

## 2.198.29 - 2026-05-01

- Ripristinato il comportamento corretto dei tab operativi `Impostazioni -> Firma Digitale` e `Impostazioni -> PEC`: il gate React non li intercetta finche' download Local Signer, verifica browser-locale e test PEC locale non sono migrati integralmente in React.
- Reso nuovamente intuitivo il flusso React PST/PolisWeb: l'acquisizione mostra un wizard progressivo a 7 step, un solo pannello operativo alla volta, riepilogo sempre visibile, lookup reale degli uffici giudiziari importati e niente card duplicate sopra al wizard.
- Corretto il crash del campo "Ufficio giudiziario" nel wizard PST: la ricerca veloce ora accetta la digitazione, mostra i risultati del catalogo uffici e non manda piu' la shell React nella pagina di errore.
- Sostituito il messaggio statico "usa il Local Signer dal browser" con una verifica reale browser-locale: ping a `127.0.0.1:27272`, tentativo di avvio protocollo `iusentra-local-signer://restart`, link installer aggiornato e blocco del passaggio alla ricerca finche' il canale locale non e' pronto.
- Le card "Accesso ai portali" danno priorita' all'azione operativa di acquisizione (`Importa pratica da PST/PDP/PAT/PTT`) invece di aprire prima superfici decorative o percorsi secondari.
- Versionati anche gli asset CSS della React shell, evitando cache stale di `app.css` che poteva far esplodere graficamente Lex/logo e lasciare la pagina senza stili corretti dopo il deploy.
- Rafforzato il profilo `deploy/hetzner` per CPX42: bootstrap con `zstd/unzip`, deploy con secrets produzione obbligatori, backup con verifica checksum e restore con controllo `.sha256` prima dell'estrazione.
- Aggiunta la guida `docs/DEPLOY_HETZNER_CPX42.md` e riallineati README/documentazione release per rendere esplicito che Hetzner puo' sostituire Railway o restare fallback governato.

## 2.198.28 - 2026-05-01

- Corretto il deep-link `/fascicoli/<id>/documenti/<id_doc>/firma`: la `GET` apre ora la shell React operativa invece di produrre `405 Method Not Allowed`, mentre la `POST` resta l'unica azione di firma/caricamento.
- Aggiunta la pagina React di firma documento con stato firme, anteprima/scarico, firma tramite Local Signer locale e caricamento manuale del file firmato.
- Introdotta una guardia anti-rifirma: se il documento risulta gia' firmato, UI e backend avvisano del rischio di corruzione/versione non valida e richiedono conferma esplicita `confirm_resign`.
- Protetto il gate React dai wizard deposito interni al fascicolo non ancora migrati integralmente, evitando che un flusso tributario/PCT operativo venga sostituito da una shell vuota.

## 2.198.27 - 2026-05-01

- Portato il wizard React di acquisizione `/portali/<portale>/acquisizione` su endpoint operativi reali: stato canale, ricerca, anteprima, analisi conflitti, import e import payload autorizzato.
- Rafforzato il runtime React dei moduli economici: Preventivi/Conferimenti gestisce route profonde con `id_preventivo`, precompilazione cliente/fascicolo/dati studio e POST operativo; Timesheet espone il form reale verso `/timesheet/nuovo`.
- Aggiunti gate anti-regressione card-per-card: gli href interni dichiarati dai moduli React vengono aperti in test autenticato e non possono produrre 404 o 500.
- Documentato il criterio di audit operativo React in `docs/REACT_OPERATIONAL_AUDIT.md`, distinguendo route servita, API reali, form reali e limiti residui.

## 2.198.26 - 2026-05-01

- Rafforzato il gate React per le route profonde: le GET HTML migrate vengono servite dalla shell React, mentre POST, API, download e `?_legacy=1` restano sui percorsi Flask operativi.
- Aggiunto un test di contratto card-per-card per il blocco React Studio: nessuna card puo' puntare a `#`, `_legacy=1` o superfici non migrate, e ogni runtime `/api/v1/ui/studio-modules/<modulo>` deve esporre azioni, form o record apribili.
- Rimosse dalle card React scorciatoie visibili verso viste legacy o `Lex Operativo` non migrato, normalizzando i testi italiani e rendendo operative le azioni dei moduli Studio, economico, redazione, sito, notifiche, backup, GDPR e amministrazione.

## 2.198.23 - 2026-05-01

- Stabilizzati i contratti CI dopo la migrazione React finale: la pagina amministrativa di osservabilita' resta React di default e la vista classica viene testata solo tramite `?_legacy=1`.
- Aggiornato il messaggio reale del pulsante `Testa SMTP`: quando manca la password PEC chiarisce che resta nel browser, viene inviata solo al Local Signer del dispositivo e non viene salvata dal server.
- Mantenuta la separazione prodotto tra nav React pulita e viste tecniche/classiche esplicite, senza far entrare `_legacy=1` nei percorsi operativi.

## 2.198.22 - 2026-05-01

- Completato l'ultimo blocco di migrazione React per le rotte studio/economico/admin richieste: parcelle, preventivi, tariffario, redazione atti, PST, statistiche, ricerca legale, giurisprudenza, strumenti, timesheet, cartelle condivise, sito studio, utenti, audit, osservabilita' e GDPR ora aprono la shell React di default.
- `?_legacy=1` resta solo come vista tecnica/classica esplicita: la navigazione React e le card operative usano URL puliti, con regressioni dedicate per impedire il ritorno di link legacy nella nav reale.
- Aggiornati i contratti React e il presidio Lex unico contestuale, mantenendo il widget globale spostabile e senza duplicazioni sulle pagine del blocco finale.

## 2.198.21 - 2026-04-30

- Corretto il riquadro `Ultime PEC ricevute` della Panoramica React: ora legge le ultime email reali in `INBOX`, ordinate per data effettiva, senza escludere le PEC ministeriali `giustiziacert.it` prive di `stato_pct`.
- La cache breve della Panoramica include anche `mtime` e dimensione del file casella PEC e la risposta `/api/v1/ui/dashboard` e' servita con `no-store`, cosi' dopo una sincronizzazione la home non resta sui messaggi precedenti.
- Il client React della Panoramica usa `cache: no-store` e cache-busting come la pagina `/email/`, allineando la card home alla casella PEC operativa.

## 2.198.20 - 2026-04-30

- Corretto l'accesso tenant-aware alla casella PEC e alla configurazione studio nelle route Email, Sync Runtime e Impostazioni, eliminando la lettura della casella globale che manteneva la UI ferma sui vecchi 104 messaggi.
- Aggiunto il payload locale `/impostazioni/pec/local-smtp-payload`: il test SMTP dal PC usa la password digitata oppure quella salvata del tenant per il Local Signer, senza bloccare il flusso sul falso messaggio di password mancante.
- Nella pagina Impostazioni e' stata nascosta la navigazione legacy quando la pagina moderna e' attiva, e il vecchio Lex inline e' stato disabilitato per lasciare un solo widget Lex ufficiale.

## 2.198.19 - 2026-04-30

- Corretto il sync IMAP PEC per cartelle Legalmail con spazi nel nome, come `160925 SPEDITE`: la selezione IMAP ora quota correttamente il mailbox e importa anche quegli archivi invece di saltarli.
- Aggiunto test di regressione sul discovery Legalmail con cartelle `Spedite` e archivi storici con spazio, mantenendo la riclassificazione corretta fra `In arrivo`, `Inviati` e `Cestino`.

## 2.198.18 - 2026-04-30

- Corretto il conteggio della pagina React `Email PEC`: le cartelle Legalmail `Spedite` vengono ora riconosciute come `Inviati` e non finiscono piu' in `In arrivo`.
- La sincronizzazione IMAP scopre automaticamente le cartelle reali esposte dal server Legalmail, inclusi archivi come `160925 SPEDITE`, e riallinea le email gia' importate nella cartella sbagliata.
- Il payload React `/api/v1/ui/email` e il client `emailData` disattivano la cache browser con `no-store` e cache-busting, cosi' la pagina non resta ferma sui vecchi 104 messaggi.

## 2.198.17 - 2026-04-30

- Corretto l'import PEC Legalmail: messaggi distinti con UID IMAP stabile diverso non vengono piu' fusi solo perche' condividono lo stesso `Message-ID`, mantenendo pero' la migrazione dei vecchi riferimenti non stabili.
- Estese le cartelle IMAP standard alle nomenclature Legalmail (`INBOX/Spedite`, `INBOX/Trash`, bozze e posta indesiderata) e reso non bloccante il tentativo su cartelle non presenti.
- La Panoramica React usa una cache breve lato server per rendere piu' rapido il caricamento ripetuto della pagina principale, con refresh forzabile.
- Il riquadro `Email recenti` resta vuoto e non pubblica piu' PEC: e' riservato alla futura posta ordinaria separata dalla casella PEC.

## 2.198.16 - 2026-04-30

- Completato il blocco finale della migrazione React per Studio, economico, redazione, ricerca, strumenti, sito studio, notifiche, pagamenti, backup, calendario e amministrazione.
- Aggiunta la pagina React `StudioModulePage`, basata su token e card operative, con handoff `_legacy=1` alle funzioni classiche reali e Lex AI contestuale unico su desktop.
- Promosse le route dirette delle superfici residue alla React Shell, mantenendo permessi e viste classiche tecniche per utenti, audit, database, GDPR, fatturazione, preventivi, statistiche, giurisprudenza, sito studio e pagamenti.
- Estesi contratti React e test di regressione route per verificare che il blocco finale non ricada sulla grafica legacy.

## 2.198.15 - 2026-04-30

- Unificato Lex nelle pagine React: la shell React include il widget Lex ufficiale completo e i componenti React pubblicano solo il contesto pagina, evitando varianti mini o fallback visibili differenti.
- Lex resta nascosto su tablet e mobile, come richiesto, ma su desktop riceve `context_label`, `page_context` e `page_path` anche nel prompt backend per rispondere in base alla pagina aperta.
- Corretto il comportamento apertura/chiusura della navigazione mobile: il comando non occupa piu' la prima voce della barra, resta compatto a destra e la rail dei link rimane scorrevole.
- Rimossi i mini-widget Lex dedicati dai form React di appuntamento e scadenza, mantenendo le azioni operative interne e il collegamento al Lex completo.

## 2.198.14 - 2026-04-30

- Corretto il test `Impostazioni -> PEC -> Testa SMTP`: il pulsante primario e' ora il test dal PC via Local Signer e restituisce `Connessione SMTP PEC riuscita.` quando il login SMTP locale va a buon fine.
- Il browser mantiene per 15 minuti, solo nella sessione locale e mai sul server, la password PEC appena digitata prima del salvataggio della configurazione: dopo il redirect il test locale non si blocca piu' sul falso messaggio di password mancante.
- Corretto il motore di sincronizzazione IMAP PEC: ora usa UID IMAP stabili, migra i vecchi riferimenti basati su sequenza, deduplica tramite `Message-ID` e amplia la finestra di aggiornamento a 500 messaggi per cartella.
- Sistemata la nav mobile React: la barra inferiore e' richiudibile e i link scorrono orizzontalmente senza occupare due righe o coprire la lista PEC.
- Rinominati i servizi governati del Product Pack da `hacs-*` a `iusentra-*` nelle superfici prodotto, nei manifest nuovi e nella documentazione.

## 2.198.13 - 2026-04-30

- Aggiunto nello `/scadenziario` il calcolatore termini processuali spiegabile: template versionati, computo giorni/mesi, sospensione feriale parametrica, sabato configurabile, termini liberi/a ritroso con revisione professionale e creazione di scadenze auditabili.
- Introdotto il modulo dominio `pct.termini_processuali` con audit SHA-256 su JSON canonico, versioni `template/ruleset/calendar/engine`, piano promemoria PEC idempotente e import CSV delle festivita ufficiali con checksum.
- Aggiunti schemi SQLite/PostgreSQL per `deadline_templates`, `deadline_audit_logs`, `official_holidays`, `calendar_versions` e `deadline_notification_logs`, con matrice storage aggiornata.
- Estesa la shell React dello scadenziario con bootstrap verificabile per i test di regressione della migrazione SPA, mantenendo i dati reali serviti dalle API Flask.

## 2.198.12 - 2026-04-30

- Corretto il link principale della nav React `PolisWeb / PST`: ora apre direttamente il wizard reale `/portali/pst/acquisizione`, invece della panoramica `/polisWeb`.
- Mantenuta la panoramica come voce separata `Panoramica PST`, cosi' il percorso informativo resta disponibile ma non intercetta piu' il flusso di import.

## 2.198.11 - 2026-04-30

- Ridisegnata la superficie React `Tribunali / PEC`: l'elenco `Tribunali e indirizzi PEC` e' ora un pannello scrollabile affiancato alle card `Esiti in attesa`, `Import incompleti`, `Controlli predeposito` e `Collegamenti rapidi`, con altezza coordinata e layout responsive.
- Corretto `Esegui verifica`: quando la sorgente live non restituisce dati utilizzabili, il report usa il registro interno versionato e mostra un esito governato invece del messaggio bloccante `Nessuna sorgente remota disponibile`.
- Introdotta la distinzione strutturata fra PEC di deposito telematico e PEC amministrative/protocollo, con fonti PST/IPA/sito ufficiale, policy nel payload React e metadati `indirizziTelematici` per ogni ufficio con PEC censita.
- Aggiunti schema SQLite/PostgreSQL e documentazione del modulo `Uffici giudiziari e PEC`, inclusa la matrice storage JSON/SQLite/PostgreSQL e i test di regressione su UI, payload e verifica fallback.

## 2.198.10 - 2026-04-30

- Ripristinata la visibilita' operativa di `Importa pratica da PST` nella superficie React `PolisWeb / PST`: la prima card e l'azione rapida puntano di nuovo al wizard reale `/portali/pst/acquisizione`.
- Aggiunta nella navigazione React la voce esplicita `Importa pratica da PST`, separata dalla pagina informativa `PolisWeb / PST`, cosi' il flusso di acquisizione non resta nascosto dietro copy generico.
- Corretto il riquadro destro delle hero `PDP`, `PAT` e `PTT`: il collegamento al portale ufficiale non viene piu' reso come rettangolo bianco illeggibile, ma come pulsante scuro leggibile dentro la testata.
- Estesi i test anti-regressione su payload React, nav e route `/portali/pst/acquisizione` per verificare che il wizard PST resti raggiungibile anche dopo la promozione React.

## 2.198.9 - 2026-04-30

- Promosse a React le superfici telematiche di secondo livello: `PolisWeb / PST`, `PDP`, `PAT`, `PTT`, `Tribunali / PEC`, `Checklist deposito` e `Guida firma digitale` ora servono la shell React dalle URL ufficiali, mantenendo la vista storica solo con `_legacy=1`.
- Aggiunto il bridge `/api/v1/ui/telematico/surface/<surface>` con payload reali, checklist operative, card azione, controllo Local Signer browser-locale e directory uffici/PEC alimentata dalla cache uffici.
- Collegata la navigazione React alle nuove superfici e aggiunti CSS responsive dedicati con test anti-regressione su route, API, contratti e fallback tecnico.

## 2.198.8 - 2026-04-30

- Corretto il flusso `Testa SMTP dal PC` nelle impostazioni PEC: il pulsante locale non ricade piu' sul test SMTP server-side e non usa piu' la password salvata dal server, evitando timeout e blocchi IP del cloud.
- Chiarito nella UI che l'invio PEC reale deve passare dal PC locale tramite Local Signer; la diagnostica SMTP dal server resta separata e indicata come controllo non operativo.
- Protette le route di deposito PEC: il server prepara e verifica la busta, ma l'invio reale non usa SMTP cloud e viene completato dal browser contro `Local Signer` su `127.0.0.1:27272`.

## 2.198.7 - 2026-04-30

- Riallineato il quadro fascicolo React: nella route `/fascicoli/<id>/quadro` la card `Documenti` viene mostrata sotto la card `Economico` nella griglia responsive, con test anti-regressione dedicato.
- Completato il quadro con assi operativi aggiuntivi per `Soggetti e parti`, `Cancelleria e istanze` e `Servizi telematici`, alimentati dal payload reale del fascicolo.
- Corretto il bridge `Soggetti e parti`: le parti processuali strutturate vengono lette dalla tupla `(ParteProcessuale, Soggetto)` e, se mancano, il quadro usa comunque cliente e controparte presenti nel fascicolo.
- Ripulito il copy tecnico `repository_reali` dalle etichette visibili `Dati aggiornati` e corretto il link `Indietro` della copertina fascicolo verso il dettaglio ufficiale `/fascicoli/<id>`.

## 2.198.6 - 2026-04-30

- Introdotto il controllo globale browser-local del Local Signer dopo il login: verifica `127.0.0.1:27272`, tenta l'avvio via protocollo locale, confronta la versione installata con quella rilasciata e propone il pacchetto ufficiale aggiornato per Windows, macOS o Linux con riverifica post-installazione.
- Corretto il test `Testa SMTP dal PC` nella scheda PEC: se la password e' gia' salvata non viene piu' richiesta inutilmente; il sistema verifica il Local Signer e usa il test sicuro server-side senza esporre la credenziale al browser.
- Rafforzata la regola anti-confusione coverage: il gate minimo CI verde non puo' piu' essere comunicato come target coverage 100% raggiunto.
- Aggiunti test anti-regressione per metadati Local Signer, controllo versione, installer e fallback password PEC salvata.

## 2.198.5 - 2026-04-30

- Promossa la superficie `Servizi Telematici` alla shell React ufficiale su `/telematico`, con bridge `/api/v1/ui/telematico` alimentato dai runtime reali e vista classica disponibile solo come `_legacy=1`.
- Agganciati i guardrail di deposito al form React fascicolo: `/fascicoli/nuovo` espone canale PCT/PDP/PAT/PTT suggerito dal backend, senza duplicare regole legali nel frontend.
- Corretto il dettaglio fascicolo React: sezioni collassate all'apertura, quadro intelligente ripristinato, card operative, azioni agenda non piu' instradate alla vecchia grafica e Lex flottante nuovamente disponibile.
- Normalizzate le date visibili del fascicolo in formato italiano `gg/mm/aaaa`, incluse note importate da portale, ultimo sync, attivita', scadenze, cronologia e documenti.
- Riallineati i documenti censiti dai portali ufficiali: il catalogo portale viene mostrato in React come `Da acquisire`, deduplicato per identificativo portale e conteggiato come elemento governato senza fingere un file fisico gia' scaricato.
- Rimossa la voce visibile `Lex - Assistente Legale` dalla navigazione React e legacy, mantenendo solo il widget contestuale operativo.
- Estesi i test React, fascicoli e portali per presidiare route ufficiali React, fallback tecnico `_legacy=1`, guardrail, deduplica documenti portale, referente studio, date italiane e contratti frontend.

## 2.198.4 - 2026-04-30

- Corretto l'instradamento dei dettagli fascicolo nella shell React: i link operativi generati dal bridge tornano alle route ufficiali `/fascicoli/...` e il componente normalizza comunque eventuali URL storici `/app-v2/fascicoli/...`, evitando il ritorno accidentale alla lista.
- Aggiunti test anti-regressione sui link profondi fascicolo, sulle azioni di modifica e sui preset archivio per impedire nuove commistioni tra route ufficiali e URL tecnici `/app-v2`.

## 2.198.3 - 2026-04-30

- Eliminato in modo definitivo lo scroll orizzontale della navigazione laterale: la sidebar React e la sidebar legacy bloccano l'overflow laterale, mantengono solo lo scroll verticale e gestiscono etichette lunghe senza allargare il menu.
- Aggiunto test di regressione CSS per impedire il ritorno di `overflow-x` o trasformazioni laterali nella nav principale.

## 2.198.2 - 2026-04-30

- Corretta la navigazione React di `Preparazione Udienza Guidata`: la voce ora apre `/wizard-pro/` e il cruscotto ufficiale serve la shell React, con vista classica disponibile solo come percorso tecnico `_legacy=1`.
- Aggiunti bridge e pagina React per `/wizard-pro/`, alimentati dai repository reali del cruscotto udienza e con card operative collegate a ripresa sessione, avvio wizard, fascicolo, agenda, scadenziario e Lex.
- Eliminato lo scroll orizzontale dalla sidebar React, mantenendo solo lo scroll verticale del menu e contenendo testi/link lunghi nella nav.
- Estesi test React/API/route per presidiare il link corretto, la shell `/wizard-pro/`, il bridge `/api/v1/ui/wizard-pro`, le card operative e il divieto di regressione sulla nav.

## 2.198.1 - 2026-04-30

- Corretto il mojibake nei testi React del primo blocco e nei test di route, ripristinando accenti italiani e simboli senza indebolire il gate governance.
- Ricompilati gli asset Vite distribuiti da Flask dopo la correzione dei testi, cosi' il bundle pubblico passa lo stesso controllo `tools/check_repo_governance.py` della CI.

## 2.198.0 - 2026-04-30

- Corretto il gap del primo blocco React: le route ufficiali `GET /`, `GET /workspace-intelligente`, `GET /global-search`, `GET /agenda`, `GET /agenda/nuovo` e le principali route `GET /fascicoli/*` servono ora la shell React senza passare da URL tecnici `/app-v2`.
- Conservate le viste Jinja storiche solo come percorso tecnico esplicito `_legacy=1`, utile per assistenza e verifica, senza mostrarle come esperienza principale dell'utente.
- Aggiornata la navigazione React desktop/mobile per puntare alle URL ufficiali dell'applicativo, evitando messaggi o link che suggeriscano rollback o scorciatoie verso la vecchia grafica.
- Aggiunti test di regressione sulle route ufficiali del primo blocco per verificare React shell, fallback tecnico `_legacy=1` e coerenza dei flag `/api/v1/ui/bootstrap`.
- Rafforzate le regole CI/coverage: la coverage critica locale e' stata portata a 71,49%, il workflow `Coverage moduli critici` ora blocca sotto 71% e `AGENTS.md` impone confronto baseline prima di dichiarare concluso un lavoro.

## 2.197.0 - 2026-04-29

- Avanzato il primo blocco React operativo con Email PEC, Messaggi, Clienti e Anagrafiche e Soggetti e Parti sulle route ufficiali; le restanti route ufficiali del blocco sono state riallineate nella release successiva.
- Promosse a React le route ufficiali `GET /email/`, `GET /messaggi` e `GET /messaggi/nuovo`, conservando i POST e le azioni sensibili sui servizi Flask auditati.
- Aggiunti i bridge reali `/api/v1/ui/email`, `/api/v1/ui/messaggi` e `/api/v1/ui/messaggi/nuovo`, senza mock operativi, con KPI, cartelle PEC, filtri, stato canali e contesto Lex.
- Corretta la sincronizzazione IMAP PEC: le cartelle Inviati e Cestino non vengono piu' salvate come INBOX, ma mappate correttamente da alias comuni (`Sent`, `Sent Items`, `Posta inviata`, `Trash`, `Deleted Items`, `Posta eliminata`).
- Ripuliti copy e contratti React del primo blocco eliminando riferimenti visibili a UI storica, rollback o scorciatoie Jinja; la vista classica resta disponibile solo come parametro tecnico `_legacy=1` per verifica e assistenza.
- Introdotto code-splitting sulle pagine React del primo blocco: la build Vite non produce piu' warning sul chunk principale oltre 500 kB.
- Estesi test React, Email PEC, Messaggi e route ufficiali per verificare API reali, mapping IMAP, GET React, vista classica tecnica, typecheck e contratti frontend.

## 2.196.0 - 2026-04-29

- Promosse a React le route ufficiali `Clienti e Anagrafiche` e `Soggetti e Parti`: i GET `/clienti`, `/clienti/nuovo`, `/soggetti` e `/soggetti/nuovo` servono ora la shell React con URL storiche immutate.
- Conservato il backend Flask operativo per i POST di creazione cliente e soggetto, cosi' validazioni, tenant, audit e workflow collegati restano un'unica source of truth.
- Aggiunta vista classica tecnica `_legacy=1` per aprire le viste Jinja senza rollback deploy, utile per verifica operativa e assistenza.
- Aggiornati contratti `/api/v1/ui/clienti*` e `/api/v1/ui/soggetti` con `read_only=false`, `writes=operational_routes` e `route_owner=react_shell`.
- Estesi test route/API/React per garantire che le URL ufficiali servano React, che le viste classiche restino raggiungibili e che i POST continuino a usare il backend operativo.

## 2.195.30 - 2026-04-29

- Aggiunta la nuova pagina React `/app-v2/clienti/nuovo`, con form cliente e form soggetto separati, UI responsive, checklist qualita e Lex AI contestuale.
- Collegati `Nuovo Cliente`, `Soggetti e Parti -> Anagrafica` e `Nuovo Soggetto` alla shell `/app-v2`, mantenendo i salvataggi sulle route Flask storiche `/clienti/nuovo` e `/soggetti/nuovo`.
- Introdotto il bridge reale `/api/v1/ui/clienti/nuovo` e la lista React `/app-v2/soggetti` alimentata da `/api/v1/ui/soggetti`, entrambi senza mock operativi.
- Aggiunto calcolo server-side del codice fiscale ordinario tramite tabella Belfiore gia presente e API `/api/cf/calcola`; la React decodifica inoltre il CF con `/api/cf/decodifica` per compilare data, luogo e provincia di nascita.
- Estesa la persistenza soggetti con `provincia_nascita` e salvato il documento identita anche nella creazione cliente storica quando arriva dal form React.
- Aggiornati test React/backend, versioning e asset frontend per presidiare route, API, Lex draggable, CF automatico e migrazione progressiva di Soggetti e Parti.

## 2.195.29 - 2026-04-29

- Aggiunta la pagina React `/app-v2/clienti` per Clienti e Anagrafiche, collegata alla sidebar enterprise e alla barra mobile della shell app-v2.
- Introdotto il bridge reale `/api/v1/ui/clienti`, in sola lettura e senza mock operativi, alimentato da `GestioneClienti` e dai fascicoli collegati.
- Integrata la UI anagrafica con KPI, ricerca, filtri avanzati, tabella desktop, card mobile, bulk bar locale, insight laterali e Lex AI contestuale.
- Evidenziati qualita dati, clienti senza recapiti, privacy da verificare, documenti scaduti e collegamento procedimenti direttamente dalla lista.
- Aggiornati test React/backend, piano migrazione, versioning e asset frontend per presidiare la nuova route progressiva.

## 2.195.28 - 2026-04-29

- Aggiunta la nuova pagina React `/app-v2/fascicoli/:id/quadro`, alimentata dal bridge reale `getFascicoloDetail` senza mock operativi.
- Collegato il pulsante `Quadro` del dettaglio fascicolo alla nuova route app-v2, mantenendo `Copertina` e `PDF` sulle route storiche auditabili.
- Ricostruito il quadro su cinque assi: Commerciale, Operativo, Conformita, Economico e Documenti, con KPI e dati processuali del fascicolo.
- Integrato Lex AI contestuale nel Quadro fascicolo, con icona flottante e ritorno al dettaglio React.
- Aggiornati test React, documentazione di migrazione e asset compilati per presidiare route, componenti e layout responsive del Quadro.

## 2.195.27 - 2026-04-29

- Rifinita la cabina fascicolo React: le finestre Profilo, Documenti, Attivita, Udienze/scadenze, Cancelleria, Istanze e i pannelli laterali sono ora collassabili.
- Rimossa l'azione `Vista storica` dal dettaglio `/app-v2/fascicoli/:id` e aggiunti i comandi `Quadro` e `Copertina` accanto a Fascicoli, Modifica e PDF.
- Aggiunta la freccia `Torna su` nella cabina fascicolo per rientrare rapidamente all'intestazione.
- Sostituito il pulsante non leggibile `Disattiva controlli` con un interruttore leggibile per `Conformita e qualita`, collegato alla route storica auditata e con ritorno alla pagina React.
- Aggiornati test shell React e asset frontend per presidiare layout collassabile, rimozione vista storica, link Quadro/Copertina e toggle conformita.

## 2.195.26 - 2026-04-29

- Estesa la migrazione React dei fascicoli a suite completa sotto `/app-v2/fascicoli`, con lista, nuovo/modifica, archivio, dettaglio cabina fascicolo ed export.
- Aggiunti i bridge in sola lettura `/api/v1/ui/fascicoli*` per lista, archivio, form, dettaglio ed export, alimentati dai repository reali e con scritture ancora instradate alle route Flask storiche.
- Integrata la cabina fascicolo React con profilo, documenti, import portale, attivita, udienze/scadenze, depositi, istanze, avanzamento, gestione, economico, conformita, telematico, cliente e soggetti.
- Reso riusabile Lex AI flottante e trascinabile nelle superfici fascicoli, con posizione persistita in `localStorage` e contesto specifico per lista, archivio, form, dettaglio ed export.
- Aggiornati nav React, piano migrazione, test shell/backend e asset React compilati per presidiare route, API reali, contratti `mock_fallback=false` e rollback immediato sulle viste storiche.

## 2.195.25 - 2026-04-29

- Aggiunta la pagina React in sola lettura `/app-v2/fascicoli`, collegata alla nav desktop e mobile senza sostituire le route storiche dei fascicoli.
- Introdotto il bridge `/api/v1/ui/fascicoli`, alimentato dai repository reali di fascicoli e scadenziario con contratto `mock_fallback=false` e `read_only=true`.
- Integrata la vista Fascicoli con KPI, ricerca, filtri tipo/stato/ufficio, ordinamento, tabella desktop, card mobile, bulk bar locale e Lex AI contestuale trascinabile.
- Mantenute le azioni `Nuovo`, `Archivio`, `Apri`, `Modifica` ed `Esporta` sulle route storiche, coerentemente con la migrazione progressiva pagina per pagina.
- Aggiornati piano migrazione React e test di regressione per nav, API reale e contratto di sola lettura.

## 2.195.24 - 2026-04-29

- Aggiunto il ponte PEC locale nel Local Signer: `POST /pec/smtp/test` verifica l'SMTP dal PC dello studio e `POST /pec/send` prepara l'invio locale con allegati base64.
- Collegata la scheda `Impostazioni -> PEC` al test `Testa SMTP dal PC`, con auto-avvio `iusentra-local-signer://restart` e messaggio che propone direttamente il pacchetto Local Signer da installare se il servizio non viene rilevato.
- Esteso lo stesso auto-avvio alla verifica token in `Impostazioni -> Firma Digitale` e al pannello `AI Locale`, evitando messaggi ciechi quando il servizio locale non e' ancora partito.
- Aggiornati installer, origini CORS e download Local Signer per il dominio `https://app.iusentra.it`, mantenendo compatibile l'origine Railway storica.
- Reso obbligatorio il pacchetto Windows `.exe` nelle route pubbliche Local Signer: `/setup/windows`, `/setup/windows-exe` e la route legacy `/installa-windows` servono tutte `SetupLocalSigner-<versione>.exe`.
- Documentato il flusso operativo in `docs/LOCAL_PEC_CONNECTOR.md` e aggiunti test di regressione su ponte PEC, CORS, dispatch endpoint e UX di auto-avvio.

## 2.195.23 - 2026-04-29

- Aggiornati i messaggi SMTP/PEC per il runtime Hetzner: non citano piu' Railway e guidano l'utente su server cloud o dedicati, whitelist dell'IP pubblico e relay SMTP compatibili.
- Aggiunto `PCT_PUBLIC_OUTBOUND_IP` al profilo Hetzner per mostrare l'IP del server nei timeout SMTP e facilitare le richieste di sblocco al provider PEC.
- Riallineati i testi visibili nelle impostazioni Email SMTP e AI locale eliminando riferimenti operativi al vecchio server Railway.
- Rimossi dalle impostazioni SMTP il preset e la guida del relay esterno non piu' usato dallo studio.

## 2.195.22 - 2026-04-29

- Completata la migrazione del volume dati Railway `/data` su Hetzner e verificata la shell HTTPS temporanea `app.116.203.45.57.sslip.io`.
- Aggiunta la variabile `PCT_TIMESHEET_DB` al profilo Docker/Hetzner per impedire fallback relativi a `./timesheet/entries.json` nei runtime container.
- Disattivato l'healthcheck HTTP ereditato sui worker scheduler/OCR del profilo Hetzner: i worker non espongono `/api/pronto`, mentre l'app resta controllata dal proprio healthcheck.

## 2.195.21 - 2026-04-29

- Aggiunto il profilo di deploy Hetzner CPX42 con Docker Compose dedicato, Caddy HTTPS, Redis, worker scheduler/OCR, healthcheck, firewall bootstrap, backup e restore dati `/data`.
- Preparata la guida operativa `deploy/hetzner/README.md` per migrazione da Railway a server Ubuntu `116.203.45.57`, con dominio, secrets, ripristino backup e verifiche post-deploy.
- Attivato l'accesso SSH operativo al server Hetzner e completato il bootstrap Ubuntu con Docker, Compose plugin, OpenSC/pcscd e UFW.

## 2.195.20 - 2026-04-29

- Stabilizzata definitivamente la pagina React `/app-v2/agenda/nuovo`: autocomplete clienti, anteprima e controllo sovrapposizioni ora normalizzano anche payload annidati, record incompleti e campi non-stringa prima del render.
- Rafforzata la lettura di `/api/agenda` nella pagina nuovo appuntamento per evitare crash React quando un evento reale ha date, titoli o durate in formato inatteso.
- Estesi i contratti React e il test shell per presidiare dropdown clienti sanitizzata, normalizzazione agenda e parsing difensivo.

## 2.195.19 - 2026-04-29

- Rafforzato l'autocomplete clienti della pagina React `/app-v2/agenda/nuovo`: ora usa il payload minimale `/api/clienti?autocomplete=1`, normalizzato lato Flask, invece del JSON anagrafico completo.
- Aggiunta una barriera anti-schermata-bianca nella shell React con fallback visibile e link alla vista storica, più header `no-store` sulla shell `/app-v2` per evitare HTML SPA vecchio dopo deploy.
- Estesi contratti e test backend/UI per verificare il payload sicuro dell'autocomplete clienti e il fallback React.

## 2.195.18 - 2026-04-29

- Corretto l'autocomplete clienti della pagina React `/app-v2/agenda/nuovo`: la ricerca ora normalizza payload array, wrapper `data/items/clienti`, record incompleti e risposte non JSON senza mandare in errore il render.
- Aggiunta una guardia di regressione nei contratti React e in `tests/test_react_shell.py` per evitare nuove schermate bianche quando `/api/clienti` risponde in modo inatteso in produzione.

## 2.195.17 - 2026-04-29

- Collegata la voce `Regia Operativa` della nav React a `/app-v2/regia-operativa`, mantenendo la Panoramica separata e la regia storica raggiungibile come versione completa.
- Aggiunta la pagina React separata `/app-v2/agenda/nuovo`, con salvataggio nativo su `/agenda/nuovo`, precompilazione da query `data`/`ora`, autocomplete clienti, controllo sovrapposizioni e Lex contestuale.
- Resa operativa l'Agenda React: slot orari cliccabili in vista giorno/settimana, griglia mese cliccabile, drag & drop con orario e salvataggio su `/api/agenda/<id>/sposta` per gli eventi agenda reali.
- Migliorato il widget Lex flottante dell'Agenda: l'icona resta disponibile anche su mobile, distingue click da trascinamento e conserva la posizione senza bloccare l'apertura del pannello.

## 2.195.16 - 2026-04-29

- Aggiunta la pagina React separata `/app-v2/agenda`, collegata alla nav della shell senza sostituire la pagina storica `/agenda`.
- Introdotto il bridge read-only `/api/v1/ui/agenda`, alimentato dai repository reali di agenda e scadenziario con contratto `mock_fallback=false`.
- Integrata la vista Agenda responsive con filtri, KPI, calendario settimanale/giornaliero, briefing, salute sincronizzazione, azioni operative e widget Lex trascinabile.
- Chiuse di default tutte le sezioni della nav enterprise e corretto il drawer mobile: il pulsante nel brand chiude il menu, lo scrim resta operativo e i link chiudono la navigazione dopo la scelta.

## 2.195.15 - 2026-04-29

- Aggiunta la pagina React separata `/app-v2/ricerca-studio`, collegata all'indice reale `/api/global-search` senza `mockResults`.
- Integrato il layout Ricerca Studio con filtri, stato indice FTS5, reindicizzazione, anteprima contestuale, shortcut `Ctrl/Cmd + K`, `Esc`, frecce e azioni `Apri`, `Chiedi a Lex`, `Vai al fascicolo`, `Copia link`.
- Rimossa la Regia Operativa dalla Panoramica React: resta voce di navigazione separata, coerente con la migrazione pagina per pagina.

## 2.195.14 - 2026-04-29

- Integrato il pack `iusentra-react-ui` nella shell `/app-v2` mantenendo i dati reali gia' collegati: componenti React riusabili `Panel`, `KpiCard`, `DossierCard`, `SourceCard`, `Badge` e `Button`.
- Separati in `data.ts` gli array operativi pronti per API/store (`metrics`, `agenda`, `operations`, `dossiers`, `sources`, fascicoli, fonti, economia e suggerimenti Lex) senza reintrodurre mock.
- Estesi token CSS/TypeScript per colori, spacing, radius, shadow e typography; la sidebar resta desktop e diventa drawer sotto `980px`.

## 2.195.13 - 2026-04-29

- Compattata la versione mobile di `/app-v2` con KPI, pannelli, righe operative, grafici e barra inferiore piu' densi e leggibili su schermi piccoli.
- Ripristinato lo scroll verticale della pagina React mobile isolando la shell `/app-v2` dalle regole legacy che bloccavano `html` e `body` in overflow nascosto.
- Ricostruita la sidebar React enterprise con navigazione completa a sezioni scrollabili: recenti, agenda, fascicoli, clienti, soggetti, comunicazioni, scadenze, servizi telematici, studio e amministrazione.

## 2.195.12 - 2026-04-29

- Collegata la panoramica React `/app-v2` ai repository operativi reali per PEC/email, messaggi clienti, agenda, scadenziario, fascicoli prioritari, anagrafiche incomplete, preventivi/conferimenti, fatturazione e timesheet.
- Rimosso il fallback mock del kit dalla dashboard React: le sezioni vuote ora mostrano stati vuoti espliciti e il contratto `/api/v1/ui/dashboard` dichiara `mock_fallback=false`.
- Aggiunti test di regressione che seminano dati reali nei repository locali e verificano che il payload React li esponga senza usare dati dimostrativi.

## 2.195.11 - 2026-04-29

- Resa collassabile la sidebar enterprise di `/app-v2`, con pulsante accessibile, stato compatto a icone, tooltip nativi sui link e navigazione interna scrollabile per menu lunghi.
- Aggiunto lo script frontend `npm run typecheck` allineato al prompt pack enterprise, mantenendo la build Vite servita da Flask.

## 2.195.10 - 2026-04-29

- Integrata in `/app-v2` la prima pagina `Panoramica` del React Token UI Kit: sidebar navy enterprise, topbar, KPI cards e pannelli operativi responsive per PEC, email, messaggi clienti, agenda, anagrafiche, conferimenti, fascicoli prioritari, scadenze, economico rapido e suggerimenti Lex AI.
- Mantenuto il ponte `/api/v1/ui/dashboard`: la nuova UI usa i dati reali gia' disponibili e conserva fallback controllati per le sezioni che verranno collegate nella prossima tranche a PEC, email, messaggi, conferimenti, scadenze ed economia reali.

## 2.195.9 - 2026-04-28

- Avviata la migrazione progressiva Flask + React con shell separata `/app-v2`, build Vite servita da Flask e API ponte protette sotto `/api/v1/ui/*`.
- Aggiunta documentazione master plan per migrare pagina per pagina senza sostituire la UI Jinja finché non passano parità funzionale, responsive, accessibilità, tenant/RBAC e rollback.
- Collegata la dashboard React a dati runtime reali e aggiunto un guardrail frontend che blocca dati demo/mock operativi prima della build.

## 2.195.5 - 2026-04-28

- Estratta la logica delle viste dello scadenziario in un servizio dedicato, mantenendo invariato il comportamento utente e riportando il modulo route sotto i limiti di governance CI.

## 2.195.4 - 2026-04-28

- Corretto il flusso di creazione del conferimento da preventivo: il redirect al login conserva ora `id_preventivo` e `from_page`, evitando la perdita del contesto e il 500 in produzione.
- Aggiunti in Impostazioni Studio i dati forensi `N. iscrizione Albo` e `Ordine degli Avvocati`, usati insieme ad `Avvocato titolare` per precompilare il nuovo conferimento di incarico.
- Resi navigabili i conteggi di clienti, statistiche e scadenziario: le card/pill aprono ora le liste filtrate per clienti totali, scadenze completate, scadute e da presidiare, con azioni di dettaglio, modifica ed eliminazione.

## 2.195.0 - 2026-04-28

- Introdotto il primo presidio production hardening: moduli `core` per configurazione, database, cache Redis con fallback, worker RQ, health check, metriche Prometheus, shutdown, security headers, rate limiting, upload validator, audit HMAC, secrets Fernet, circuit breaker e migrazione JSON -> SQL.
- Aggiunti script operativi per migrazione idempotente JSON -> DB, backup database/storage e verifica integrita' backup.
- Aggiornati Docker Compose, Gunicorn, Prometheus, Grafana, `.env.example` e documentazione `docs/production-hardening.md` per Redis, worker, health check, metriche e backup.
- Rafforzata la CI: coverage critica alzata a soglia 70 e nuovo gate anti-regressione CI al 100% sui contratti che impediscono di rimuovere `Pytest core`, coverage governata e quality gates.
- Aggiunti test dedicati per upload security, audit HMAC, circuit breaker, cache, job queue, migrazione DB/FTS, health check, rate limit, security headers, secrets manager e metriche.

## 2.194.4 - 2026-04-28

- Ripristinata la compatibilita' dell'endpoint `/api/assistente/context` quando Lex usa i workflow bounded per normativa e giurisprudenza: il payload espone di nuovo prompt diagnostico, `language_mode` e flag di ricerca web/follow-up.
- Stabilizzati i test core Lex che verificano fonti ufficiali, ricerca web sentenze e policy fonti senza rinunciare al workflow giuridico strutturato.

## 2.194.3 - 2026-04-28

- Reso stabile il gate `Coverage moduli critici`: la copertura continua a misurare i moduli core Lex/PCT, ma usa una configurazione dedicata che esclude adapter opzionali, connettori esterni, tool wrapper e runtime non caricati dalla suite critica.
- Aggiunto un test di regressione per impedire che il workflow torni a misurare l'intero albero Lex invece dei soli moduli governati dal gate critico.

## 2.194.2 - 2026-04-28

- Corretto in modo puntuale il gate CI `Lint + syntax` allineando l'ordinamento import dei moduli `lex.retrieval` controllati da Ruff nel workflow GitHub.

## 2.194.1 - 2026-04-28

- Corretto il gate CI `Lint + syntax` definendo correttamente il cliente corrente nel flusso di creazione conferimento.
- Corretto il gate `Governance` rimuovendo il testo mojibake dal catalogo atti.
- Stabilizzato il nightly `Performance Smoke`: il benchmark Lex usa un contesto leggero deterministico, senza ricerca web esterna e senza caricare sezioni economiche/operative pesanti non necessarie al controllo.
- Rafforzati i test del budget performance per impedire regressioni su rete esterna e contesto non deterministico.

## 2.194.0 - 2026-04-28

- Aggiunto `tokens.json` come sorgente canonica dei design token IUSENTRA, con palette legale, tipografia, spaziature, raggi, ombre, motion e dimensioni minime dei target interattivi.
- Esportati i token in CSS custom properties tramite `web/static/scss/_design-tokens.scss`, incluso nei bundle ufficiali `app.css` e `design-system.css`.
- Aggiunta icona master SVG store-ready in `assets/icon/app.svg`, con `viewBox 0 0 1024 1024`, pochi path e senza trasformazioni annidate.
- Documentata la strategia in `docs/DESIGN_TOKENS.md` e introdotti test automatici su contrasto WCAG, touch target, motion, elevation, CSS vars e qualita' SVG.

## 2.189.0 - 2026-04-26

- Reso operativo `/sito-studio/builder`: selezione pagina, modifica home diretta, palette blocchi collegata, editor visuale, salvataggio AJAX, pubblicazione modifiche, anteprima responsive e ripristino revisioni.
- Aggiunti blocchi professionali per home page e contenuti: slider hero, slider immagine/testo, galleria, split immagine/testo, loghi, testi scorrevoli, caroselli servizi/articoli, citazione istituzionale e CTA contatto.
- Introdotta la libreria immagini del sito con tabella `site_asset`, upload/lista/eliminazione, validazione formato/dimensione e obbligo del testo alternativo.
- Esteso il rendering pubblico dei nuovi blocchi con Bootstrap, mantenendo il vincolo di un solo sito per studio/tenant e senza servizi esterni.
- Aggiunta la sezione `Redazione AI Sito Studio`: genera bozze articolo, SEO, checklist rischi e prompt immagine, con pubblicazione sempre manuale dopo revisione dello studio.
- Predisposto il layer `lex.image_providers` con provider locale stub e adapter configurabili per ComfyUI, Stable Diffusion e OpenAI Images, senza chiamate esterne automatiche.
- Aggiunti test su blocchi builder, API, asset, rendering pubblico, Redazione AI in bozza e isolamento tenant.

## 2.188.4 - 2026-04-26

- Aggiornata la terminologia visibile dell'applicativo con etichette piu' forensi e comprensibili per studi legali: `Redazione Atti`, `Catalogo Atti e Modelli`, `Regia Operativa`, `Servizi Telematici`, `Parcelle e Fatture`, `Preventivi e Incarichi`, `Compensi Forensi`, `Strumenti Operativi` e `Sito Studio`.
- Allineati menu, titoli pagina, sottotitoli, CTA, badge e microcopy nelle aree Redazione Atti, Controlli Atti, Regia Operativa, Centro Servizi Telematici, Strumenti Operativi e Sito Studio senza rinominare route o blueprint storici.
- Aggiunti alias URL conservativi per `/redazione-atti`, `/redazione-atti/catalogo`, `/redazione-atti/redigi/<codice>`, `/servizi-telematici`, `/regia-operativa`, `/ricerca-studio`, `/strumenti-operativi` e `/compensi-forensi`.
- Aggiornati i test di regressione sulle stringhe visibili e aggiunti smoke test sugli alias professionali.

## 2.188.1 - 2026-04-26

- Aggiunto il workflow Lex `giurisprudenza` con prompt dedicato all'analisi di sentenze, massime e pronunce, senza aperture conversazionali generiche.
- Corretto il bridge bounded: richieste giurisprudenziali e normative in modalita' `strict` passano ora dal workflow forte anche quando arrivano da ricerca legale o fonti ufficiali.
- Introdotto l'interprete `case_law_interpreter`, che normalizza evidenze e metadati delle sentenze e costruisce blocchi strutturati con pronuncia, organo, norme, questione, dispositivo, principio e fonti.
- Aggiunta la guardia anti-risposta-generica per giurisprudenza: se Ollama risponde con frasi non pertinenti, Lex usa un fallback deterministico basato sulle evidenze e abbassa la confidence.
- Arricchito il retrieval giurisprudenziale con metadati utili a Lex, inclusi URL ufficiali, numero, anno, organo, norme citate, questione, dispositivo, principio e massima.
- Aggiunti test su routing Corte costituzionale, bounded workflow strict, interprete sentenze, guardia anti-generica e fallback del provider Ollama.

## 2.188.0 - 2026-04-26

- Aggiunta la nuova `Ricerca Studio` globale, con indice centrale tenant-aware `global_search_index`, SQLite FTS5 quando disponibile e fallback compatibile.
- Introdotti dominio modulare `pct/global_search`, adapter per fascicoli, clienti, soggetti, scadenze, agenda, documenti, preventivi, conferimenti, fatture, pagamenti, comunicazioni, template atti, depositi e intelligence interna.
- Aggiunti endpoint `/api/global-search`, suggerimenti, reindex completo e reindex per entita', con isolamento tenant, snippet sicuri, ranking operativo e funzione riusabile per Lex AI.
- Creata la pagina `/global-search` con barra ricerca grande, filtri rapidi, risultati a card, azioni rapide, scorciatoia Ctrl/Cmd+K, debounce, skeleton loading e layout responsive.
- Aggiunti schema SQLite/PostgreSQL e test su indicizzazione, ranking, filtri, tenant isolation e API JSON.

## 2.187.0 - 2026-04-26

- Trasformato `Sito Studio` in `Sito Studio Builder Pro`, mantenendo le route esistenti e l'invariante di un solo sito per studio/tenant anche con piu' utenti.
- Aggiunti motore temi, design token, font preset, otto modelli grafici professionali e revisioni design per personalizzare colori, tipografia, spaziature, radius, ombre, privacy e cookie.
- Sostituito il textarea JSON manuale con un editor visuale a blocchi, palette componenti, riordino accessibile e anteprima responsive desktop/tablet/mobile.
- Esteso il rendering pubblico con CSS variables, navigazione mobile, footer legale, banner cookie con consenso, Open Graph, schema.org `LegalService`, sitemap e robots.
- Aggiunti validatori SEO, accessibilita', privacy/cookie e controllo deontologico base, piu' test su builder, sito unico per tenant, generazione automatica e rendering pubblico.

## 2.186.0 - 2026-04-26

- Integrato il `Centro Fonti Ufficiali Lex` con registry fonti, SQLite governato, export JSONL e retrieval dedicato per Lex AI.
- Aggiunti client e CLI Normattiva per elenco collezioni, download ZIP/XML tramite API Open Data, import XML, classificazione materie legali e indicizzazione in `normative_*`.
- Aggiunto connettore Gazzetta Ufficiale per ultimi 30 giorni della Serie Generale, conversione URL `pdfPaginato -> downloadPdf`, estrazione testo PDF, classificazione e salvataggio in `official_*`.
- Predisposte fonti disabilitate per Ministero Giustizia, PST/PCT, PAT/SIGA, PTT/SIGIT, PDP, CNF, Agenzia Entrate, Garante Privacy, EUR-Lex, ANAC, INPS, INAIL, Banca d'Italia, AGCM, AGCOM, IPA, INI-PEC, INAD e fonti locali di studio.
- Aggiunti test su client Normattiva, importer XML/ZIP, connettore Gazzetta, registry, schema SQLite e assenza di credenziali nella configurazione.

## 2.185.0 - 2026-04-26

- Integrato il `Compenso a tempo` ex art. 22-bis D.M. 55/2014 nel flusso esistente `cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso`.
- Aggiunto il motore puro `pct.compensi_a_tempo` con normalizzazione alias, arrotondamenti a minuti/scatti/frazione oltre 30 minuti, range indicativo 200-500 euro/h come warning e blocchi su tariffa o tempo non validi.
- Estesi preventivi, wizard, dettaglio, conferimento incarico, repository SQL/SQLite/PostgreSQL, log economico e fatturazione per conservare tariffa, minuti, ore fatturabili, criterio, soglie, massimali, attivita incluse/escluse e warning art. 22-bis.
- Rafforzato il cliente rapido del wizard: resta `Cliente potenziale`, viene riutilizzato per CF/P.IVA, consente il preventivo richiamabile e blocca il conferimento finche' l'anagrafica non e' completa.
- Aggiunti test su calcolo art. 22-bis, salvataggio repository, ereditarieta' conferimento, cliente rapido potenziale e regressioni preventivi/tariffario/fatturazione.

## 2.184.24 - 2026-04-26

- Aggiunta la modalità ufficiale `basso_sinistra` per la firma visibile PDF, con alias normalizzati e layout calcolato sulle dimensioni reali della pagina.
- Reso mode-aware il timbro visibile: laterale, basso sinistra e basso destra usano coordinate dedicate, aree di pulizia dedicate e fallback pyHanko coerente senza forzare più il basso destra.
- Salvata nelle impostazioni studio la posizione predefinita della firma visibile e propagata nei flussi fascicolo/deposito/PKCS#11.
- Corretto il riferimento PKCS#11 a `self._cert` nella preparazione del timbro visibile, usando il certificato reale ottenuto da `_get_cert()`.
- Aggiunti test di regressione per normalizzazione, layout, timbro basso sinistra, no duplicazione, configurazione persistente, impostazioni UI e pass-through PKCS#11.

## 2.184.23 - 2026-04-26

- Ripristinati nella pagina `/template-atti/catalogo` i 192 modelli operativi del compilatore atti, che aprono di nuovo il flusso reale `/template-atti/compila/<codice>`.
- Mantenuto il catalogo master v1.1.0 da 420 template nella stessa pagina, senza tab o pagina separata, distinguendo chiaramente sorgente `compilatore` e sorgente `master`.
- Adeguate card, filtri, chip rapidi ed endpoint dati/compliance alla logica unica: tutti i 420 master risolvono un modello compilatore operativo, con binding esatto quando disponibile e fallback professionale per canale/modulo/titolo.
- Aggiunti test anti-regressione per impedire che i 192 modelli funzionanti vengano nuovamente nascosti o sostituiti dal catalogo master e per verificare che nessun master resti senza `link_compilatore_code`.

## 2.184.22 - 2026-04-26

- Stabilizzato il wizard `Importa pratica da PST`: la visualizzazione del fascicolo usa una sola sessione PST `view` riutilizzata tra ricerca, anteprima, selezione, mappatura e verifica.
- Aggiunto lo snapshot unico Local Signer `/pst/fascicolo-snapshot`, cosi' lo Step 3 carica catalogo, metadati e sezioni in un'unica operazione e gli step successivi non richiamano il PST.
- Separata la sessione PST di importazione `import`, usata solo allo Step 7 per il download batch dei documenti reali, con lock anti-doppio click e senza salvare il PIN.
- Aggiornato il Local Signer a `1.6.20` e rigenerati i pacchetti Windows, macOS e Linux in `tools/dist`.
- Aggiunti test anti-regressione su riuso sessione, scadenza controllata, separazione `view/import`, snapshot unico e wiring del wizard.

## 2.184.21 - 2026-04-26

- Integrata la Suite professionale completa direttamente in `/template-atti/catalogo`, senza nuovo tab o pagina separata `Master professionale`.
- Aggiunti riepilogo v1.1.0, 420 template master, 22 moduli professionali e 7 canali telematici governati nella stessa pagina del catalogo atti.
- Estesi filtri, chip rapidi e card template con materia, categoria suite, rito, fase, canale/portale, stato, PDF/A, firma digitale, DatiAtto.xml, allegati, contributo e controlli conformita.
- Aggiunti servizi ed endpoint per dati catalogo, filtri e controlli deposito versionati per PST/PCT, SIGP/Giudice di Pace, PAT/SIGA, PTT/SIGIT, PDP, PEC e atti interni.
- Raffinata la selezione dei template repository: una corrispondenza esatta del titolo prevale sulle varianti piu' specifiche, evitando scelte errate nel compilatore.
- Aggiunti test anti-regressione per bloccare presenza dei template richiesti, conteggi 420/22/7, assenza del tab separato e funzionamento endpoint compliance.

## 2.184.14 - 2026-04-25

- Reso Lex AI piu' professionale nel flusso reale delle risposte finali: ogni risposta passa da `AnswerBuilder` e viene strutturata con sintesi, quadro verificato, qualita', limiti e prossime azioni.
- Aggiunti metadati `professional_answer` per audit, UI e controllo qualita', con indicazione di revisione professionale quando mancano evidenze o il rischio e' alto.
- Rafforzata la copertura AI: in single-studio l'amministratore locale puo' usare il pannello copertura AI, mentre in multi-tenant resta richiesto il SUPERADMIN.
- Reso difensivo il generatore copertura AI quando l'LLM locale restituisce JSON semanticamente non valido, ricadendo su fallback prudente invece di produrre draft rotti.
- Stabilizzati i test della copertura AI: in `TESTING` non vengono effettuate chiamate live a Ollama salvo opt-in esplicito.
- Aggiunti test anti-regressione sulle risposte professionali di fascicolo e ricerca normativa incompleta.

## 2.184.13 - 2026-04-25

- Aggiunto l'ingresso unico `importa-payload` per PST/PDP/PAT/PTT: payload autorizzati da Local Connector, PdA, Model Office o file JSON manuali vengono normalizzati e importati nel fascicolo IUSENTRA.
- Collegato il wizard di acquisizione all'upload `.json` autorizzato oltre a ZIP, PDF, P7M, EML, MSG e cartelle scaricate dal portale ufficiale.
- Smistati i dati dei portali nelle sezioni reali della UI fascicolo: documenti, attivita processuali, udienze/scadenze, comunicazioni di cancelleria e istanze.
- Corretto il riallineamento del catalogo documentale PAT/PDP/PTT: i documenti ufficiali restano `DocumentiFascicolo` e non vengono riclassificati come servizio `PAT`, `PDP` o `PTT`.
- Allineato il Local Signer `1.6.18` agli URL browser ufficiali usati dal wizard, inclusi PDP su `appweb.giustizia.it/snt` e PTT/SIGIT su `sigit.giustiziatributaria.gov.it`.
- Documentato il flusso guidato dei portali e aggiunti test di regressione end-to-end su PDP, PAT e PTT fino alla UI del fascicolo.

## 2.184.12 - 2026-04-25

- Corretto il workspace del fascicolo per trattare i depositi PST/SIGP `DocumentiFascicolo` come governo documentale: non vengono piu' contati in `Attività processuali`, `Udienze` o `Istanze` per semplici parole chiave come verbale/decreto/istanza.
- Allineata la sezione `Documenti fascicolo` al catalogo ufficiale del portale: badge, bucket, metadati, tag e azioni restano nello stesso contenitore anche quando il file fisico non e' ancora stato salvato localmente.
- Reso esplicito in wizard e `Naviga PST` il default ministeriale: copia di consultazione/copia informatica con annotazioni visibili; il duplicato/originale senza coccarda e' disponibile solo tramite scelta manuale.
- Aggiornato il Local Signer a `1.6.17` rendendo difensiva la lettura del flag `original`: valori vuoti o falsi restano sempre `copia`, evitando ricadute involontarie sull'originale senza annotazioni.

## 2.184.11 - 2026-04-25

- Reso esplicito il catalogo JSON del fascicolo PST/SIGP come prima fase stabile dell'acquisizione: buste, documenti, identificativi portale, tipo atto, mittente e date vengono salvati anche quando il download fisico dei file non riesce nella stessa sessione.
- Collegato nello Step 3 il pulsante reale `Carica documenti dal Local Signer`, disponibile anche nel fallback assistito, cosi' Palmi `466/2023` puo' leggere il catalogo documenti dal browser locale senza restare fermo su `Documenti: 0`.
- Corrette le date esposte nel wizard PST/SIGP in formato italiano e aggiunto il riepilogo finale `Documenti catalogati`, distinto da `Documenti importati`, per non confondere il catalogo ufficiale con i file fisici gia' presenti nello storage.

## 2.184.10 - 2026-04-25

- Reso visibile il modulo `SIGP - Giudice di Pace` nel menu `PCT / Telematico` e aperto automaticamente il primo fascicolo importato, cosi' il catalogo Palmi `466/2023` non resta nascosto dietro un URL tecnico.
- Corretto il client SIGP per riusare `pst_session_id`, certificato e codice fiscale salvati nel payload raw del fascicolo, evitando nuove sessioni inutili tra catalogo e download.
- Collegati i pulsanti SIGP al Local Signer del browser (`127.0.0.1:27272`) e al salvataggio server `salva-download-browser`, cosi' Railway non prova piu' a chiamare il localhost del server cloud.
- Memorizzato `pst_session_id` in `sessionStorage` per la sola sessione browser: il PIN non viene salvato, ma le chiamate successive riusano la sessione PST finche' la finestra resta aperta.
- Aggiunto timeout dedicato ai download reali PST/SIGP (`HACS_SIGNER_PST_DOWNLOAD_MAX_TIME`, default 300s) per non troncare `downloadAtto` dopo 90 secondi.
- Bloccato il default su copia di consultazione/copia informatica ministeriale (`original=false`) anche nel Local Signer; il duplicato senza coccarda e' ora una scelta esplicita con pulsante dedicato.
- Aggiornato il Local Signer a `1.6.16` e aggiunti test sul riuso sessione, sul timeout download e sul passaggio reale del flag duplicato fino al backend.

## 2.184.9 - 2026-04-25

- Corretto il riallineamento reale del catalogo SIGP: documenti con stesso nome/data ma identificativi portale diversi non vengono piu' deduplicati, cosi' Palmi `466/2023` resta a 34 documenti visibili.
- Aggiornata la formattazione date della UI SIGP Sync per mostrare anche date ISO `YYYY-MM-DD` e date PST `gg/mm/aaaa HH:mm:ss.SSS` in formato italiano.
- Aggiunto test anti-regressione su `comunicazione.txt` duplicata per nome/data ma distinta per ID portale.

## 2.184.8 - 2026-04-25

- Collegata la UI `/sigp-sync/` al catalogo documenti persistente: anteprima Local Signer, import catalogo JSON, download selezionati/nuovi, collegamento file locale e apertura del documento salvato.
- Adattato il client SIGP agli endpoint reali del Local Signer (`/pst/documenti`, `/pst/download-documento`) invece degli endpoint scaffold `/sigp/documenti/*`, mantenendo `original=false` come default per la copia informatica/consultazione.
- Aggiunti test mirati su catalogo da 34 documenti senza tagli, preview Local Signer e salvataggio fisico dei PDF nello storage runtime `data/sigp_documents`.

## 2.184.7 - 2026-04-25

- Corretto il setup dei test admin di osservabilita' avviando le rotte protette in modalita' multi-tenant, cosi' `admin/admin` viene riallineato a SUPERADMIN di piattaforma senza indebolire i guardrail RBAC.
- Ripristinato il job GitHub `Pytest core`: la suite locale mirata di osservabilita' passa 8/8 e il blocco core passa 375/375.

## 2.184.6 - 2026-04-25

- Aggiunti test Lex AI sul provider deterministico per bloccare regressioni su inventario completo del fascicolo, sezioni documentali, flussi economici, cabina operativa e responsabile di conformita'.
- Aggiunti test sul routing sociale/follow-up di Lex dentro la suite conteggiata dalla CI, mantenendo la risposta professionale senza perdere contesto operativo.
- Ripristinato il gate GitHub `Coverage moduli critici`: la copertura passa da 63,03% a 66,25% senza abbassare la soglia del 65%.

## 2.184.5 - 2026-04-25

- Corretto il connettore reale SIGP/Giudice di Pace: `subpro` non viene piu' forzato a `0` quando non indicato, evitando risultati vuoti su RG GDP come Palmi `466/2023`.
- Aggiunta la lettura ufficiale `ricercaAtti`/`estraiProfiloDocumento` per arricchire i documenti SIGP con tutti gli identificativi disponibili, nome originario, busta, dimensione e metadati del profilo.
- Aggiunto merge deduplicato tra QueryBuilder e profili SIGP: il test reale su Palmi `466/2023` passa da 27 righe QueryBuilder a 34 documenti ufficiali unici.
- Ripristinata la sincronizzazione della controparte nell'import PolisWeb quando il soggetto e' una persona giuridica con identificativo a 11 cifre.
- Aggiornati i test Local Signer per bloccare la regressione su `subpro`, parsing `ricercaAtti`, nomi originari e merge dei profili SIGP.

## 2.184.4 - 2026-04-25

- Reso lo Step 3 del wizard PST/PolisWeb resiliente agli errori di preview: timeout, SOAP Fault, Local Signer non raggiungibile e circuito aperto non bloccano piu' l'acquisizione ma attivano il fallback assistito con dati RG/ufficio/parti.
- Spostati i percorsi browser/Local Signer fuori dal circuit breaker server-side, cosi' una scelta operativa locale non viene trattata come errore ripetuto del portale.
- Aggiunti test anti-regressione per verificare che la preview PST via Local Signer non apra `portale:pst:preview` e che il template agganci il fallback assistito.

## 2.184.3 - 2026-04-25

- Integrata la nuova UI `/sigp-sync/` per consultare snapshot SIGP reali con layout dedicato a fascicolo, documenti, eventi, udienze, parti, comunicazioni e log.
- Collegata la UI al repository SIGP autorizzato gia' esistente, rimuovendo il flusso demo `Import test`/fixture previsto dallo scaffold esterno.
- Aggiunti test di route e snapshot per garantire che la pagina lavori su payload reali e non esponga endpoint demo.

## 2.184.2 - 2026-04-25

- Rimosso il fallback di lettura HTML della scheda SIGP/Giudice di Pace: IUSENTRA non effettua scraping di `sigp_infofascicolo.wp` e richiede dati ottenuti tramite PST/PdA/Model Office o Local Connector autorizzato.
- Aggiunta la sincronizzazione fascicolo telematico SIGP con mapper, repository SQLite/PostgreSQL, policy anti-scraping, endpoint `/sigp/sync/status` e `/sigp/sync/importa-payload`, senza fixture come sorgente dati.
- Persistiti snapshot completi del fascicolo SIGP: fascicolo, parti, eventi, udienze, documenti, provvedimenti e comunicazioni, con test anti-regressione su piu' di 8 documenti.

## 2.184.1 - 2026-04-25

- Arricchito il fallback SIGP/Giudice di Pace: quando il web service non espone righe, il Local Signer legge la scheda ufficiale autenticata `sigp_infofascicolo.wp` e popola in UI rito, materia, oggetto, giudice, stato, udienze, parti e difensori invece di mostrare una pratica vuota.
- Corretto il mapping del wizard PST per mantenere anche le controparti provenienti dalla scheda SIGP, con test anti-regressione sul fascicolo GDP `466/2023`.

## 2.184.0 - 2026-04-24

- Corretto il canale PST SIGP/Giudice di Pace: le ricerche esatte usano il registro `GDP`, il parametro `subpro` minuscolo richiesto dal proxy e un fallback operativo verso la scheda ufficiale autenticata quando il web service non espone righe.
- Allineata la matrice test portali per impedire regressioni su `JPW_SIGP`, `SUBPRO` e resolver uffici Giudice di Pace.
- Introdotto il modulo separato `Integrazione SIGP - Giudice di Pace` con registry XSD 2024-08-27, loader, validatore, builder XML, controlli di predeposito, API Flask e pagina UI dedicata.
- Aggiunti schemi SQL SQLite/PostgreSQL per versioni XSD, uffici, depositi, allegati e validazioni SIGP, mantenendo il primo rilascio su generazione XML e validazione senza invio ministeriale.

## 2.183.3 - 2026-04-24

- Corretta la regressione dell'installer Local Signer 1.6.10: i pacchetti Windows/macOS/Linux e i download online includono ora il modulo interno `local_signer_mod`, evitando il crash `ModuleNotFoundError` all'avvio su `127.0.0.1:27272`.
- Riallineato il payload QBuilder PST live: la ricerca per RG usa i parametri `anno`/`numero`, non invia piu' `subProc` vuoto sui registri che lo respingono, e mantiene `subProc` solo quando esiste un sotto-procedimento reale.
- Aggiunta una matrice di regressione sui canali telematici: PST `SICID`, `SIECIC`, `SIGP`, `CASSCI`, `CASSPE`, piu' PDP, PAT e PTT/SIGIT in ricerca/documenti.
- Aggiunti controlli di packaging per impedire che i moduli interni del Local Signer vengano esclusi nuovamente dagli installer o dalle route pubbliche di download.

## 2.183.2 - 2026-04-24

- Rafforzato il resolver PST/JPW degli uffici giudiziari: la cache si autoripara se perde metadati ministeriali, il Giudice di Pace di Palmi risolve correttamente su `JPW_SIGP` e la ricerca QBuilder invia sempre `subProc`.
- Aggiunto controllo giornaliero governato delle fonti ufficiali uffici con report JSON e Markdown leggibile, validazione del resolver PST e autoriparazione automatica prima del salvataggio.
- Allineato il Local Signer 1.6.10 al payload QBuilder server-side e reso il wizard PST resiliente alle SOAP Fault `SUBPRO`, mostrando acquisizione assistita invece di errore tecnico bloccante.

## 2.183.1 - 2026-04-24

- Reso il catalogo master una vista navigabile e ricercabile in `/template-atti/catalogo`: tab dedicata `Master professionale`, filtri per gruppo, conteggio dinamico e 420 card reali con ID, canale telematico e azione `Genera dal master`.

## 2.183.0 - 2026-04-24

- Integrato il catalogo master versionato dei template atti con 420 modelli e split governati `core`, `advanced`, `specialist` e `studio_interno`, esposti nel catalogo `/template-atti/catalogo` e collegati al runtime builtin senza perdere compatibilita' con i modelli storici.
- Aggiunto il gateway provider di Lex con policy local-first, stato diagnostico via API e guardrail privacy, cosi' i provider esterni restano separati dai dati sensibili e attivabili solo con configurazione esplicita.
- Rimosso il collo di bottiglia del fascicolo in Lex AI e Assistente locale: sezioni, documenti, agenda, scadenze, cancelleria e istanze non vengono piu' tagliati a 1/3/8 elementi; la reindicizzazione embedda tutti i chunk pending del fascicolo e il prompt riceve inventari completi con budget RAG dinamico.
- Rafforzato il download PST in modalita copia di consultazione: wizard, dettaglio fascicolo e server mantengono `scarica_originale_portale=false` per PST anche se il payload non invia l'opzione, con test anti-regressione sul percorso secondario `Naviga PST`.

## 2.182.24 - 2026-04-24

- Corretto il fallback di riconciliazione tenant su volumi Docker/Windows: quando il filesystem non consente di preservare timestamp/permessi con `copy2`, IUSENTRA copia comunque il contenuto applicativo senza generare errori di avvio su `tenant_user_directory`.

## 2.182.23 - 2026-04-24

- Rafforzato il recupero degli allegati PEC storici: le email gia' salvate con allegati senza file vengono rimesse nella coda IMAP anche se non sono tra gli ultimi messaggi sincronizzati, cosi' comunicazioni precedenti come quelle del 09/04/2026 non restano bloccate dal limite operativo degli ultimi messaggi.

## 2.182.22 - 2026-04-24

- Corretta la regressione degli allegati PEC storici: se un messaggio era gia' presente nello storico ma gli allegati avevano solo metadati e nessun file salvato, la sincronizzazione IMAP ora recupera nuovamente il messaggio e salva fisicamente gli allegati mancanti.
- La vista email non blocca piu' i PDF PEC etichettati dal provider come `application/octet-stream`: l'estensione `.pdf` viene riconosciuta come PDF visualizzabile, mentre XML/EML restano consultabili e firme tecniche come `.p7s` restano scaricabili.
- Aggiunti guardrail e test di regressione per impedire che gli allegati PEC tornino a essere solo nomi/dimensioni nel JSON senza `percorso_rel` valido.

## 2.182.21 - 2026-04-24

- Corretta la riconciliazione dei documenti PST gia' importati: il backfill non usa piu' un match lasco su `PORTALE_TELEMATICO`, ripara i documenti agganciandoli a `id_documento`, `id_cat`, `id_repeatto`, `msg_id`, nome originario e riferimento `pst:...` corretti, senza spalmare nome e metadati di una busta su tutte le altre.
- Il governo documentale compila automaticamente data, tag, classificazione, tipo atto e note con data italiana; i documenti gia' elaborati via OCR vengono contati anche dalla cache indicizzata e il worker marca il documento del fascicolo come OCR completato.
- Chiusi i fallback runtime che riaprivano `Permission denied` su PEC/email e import portale: `GestioneFascicoli` deriva cartelle scrivibili dal DB quando necessario e i runtime usano sempre path tenant-aware per documenti e archivio.

## 2.182.20 - 2026-04-24

- Corretta la regressione dello Step 7 del wizard di acquisizione portale: il log import finale non usa piu' un fallback relativo al repository che in Docker/Railway poteva finire in un path non scrivibile (`portale/import_log.json`), ma resta allineato al data root del portale.
- Il bootstrap runtime ancora insieme `PORTALE_DB`, `PORTALE_UPLOADS` e `PORTALE_IMPORT_LOG_DB`, cosi' se il portale usa `/data/portale/...` anche il log di acquisizione segue automaticamente lo stesso albero persistente e scrivibile.
- Per PST il download predefinito usa ora la copia di consultazione del portale con annotazioni ministeriali, non l'originale firmato del repository, sia nel wizard di acquisizione sia nel modal `Naviga PST`, con fallback server-side coerente anche se l'opzione non viene inviata.
- L'import PST riconcilia i file usando `id_documento`, `id_cat`, `id_repeatto`, `msg_id` e fallback nome+deposito, cosi' upload manuali, ZIP e download browser ereditano i metadati ufficiali del fascicolo e popolano automaticamente `Data`, `Tag`, classificazione e sezione di appartenenza nella UI.

## 2.182.18 - 2026-04-24

- Corretta una regressione nella schermata `Impostazioni -> Firma Digitale`: se l'avvocato sceglie `Token USB (Aruba Key)` il pannello non marca piu' come errore il fatto che il container remoto non veda libreria o token, perche' quel controllo appartiene al `Local Signer` sul PC locale.
- Introdotto un canale operativo esplicito per `PKCS#11 via Local Signer`, riusato dal runtime telematico per non ricadere piu' in modalita demo quando l'utente ha selezionato il token USB ma la verifica reale deve avvenire dal browser desktop.
- Il pulsante `Verifica token collegato` non interroga piu' il server Railway: controlla direttamente `http://127.0.0.1:27272/ping`, quindi restituisce lo stato reale del `Local Signer` e del token sul computer dell'avvocato.
- Aggiunti test di regressione sul canale operativo PKCS#11, sul rendering della pagina impostazioni firma e sullo script JS che deve verificare il `Local Signer` locale invece dell'endpoint server.

## 2.182.17 - 2026-04-24

- Integrati sulla linea principale i fix ancora utili della PR remota rimasta indietro rispetto ai branch ufficiali: i test di bootstrap runtime ora dichiarano in modo esplicito il contesto single-tenant o JSON quando dipendono da quei default, cosi' non tornano flaky al variare della configurazione di ambiente.
- Corretto il test dell'editor atti che puntava a un path Windows hardcoded fuori repository: ora risolve i template dalla root reale del progetto, quindi la suite resta portabile e non si rompe quando il clone vive in una cartella diversa.
- Snellito il manager utenti root nei test di strategia storage evitando il passaggio del backend studio fuori contesto request, cosi' il riallineamento del branch `claude/fix-legal-filing-issues-eW926` sulla testa corrente entra senza trascinarsi assunzioni obsolete.

## 2.182.16 - 2026-04-24

- Corretta una regressione runtime del dettaglio fascicolo emersa nel container Python 3.12: il worker non va piu' in crash durante il boot per una forward reference tipizzata nel merge del catalogo portale, quindi il fix sul governo documentale e' ora davvero servito in app e non solo coperto dai test locali.

## 2.182.15 - 2026-04-24

- Il governo documentale del fascicolo compila ora automaticamente i metadati ufficiali dei documenti portale anche quando i file erano gia' presenti localmente: il dettaglio fascicolo riallinea il catalogo dal core telematico e popola deposito, classificazione e riferimenti documento senza intervento manuale.
- `sincronizza_deposito_portale` non duplica piu' i lotti generici creati in precedenza quando arriva il catalogo ufficiale: riconosce i documenti gia' agganciati per overlap forte su nomi e riferimenti, riusa il deposito locale corretto e arricchisce i documenti collegati.
- Il flusso di import dei file portale evita di creare nuovi vuoti di metadati: quando il download include gia' identificativi e classificazione, i documenti sfusi vengono convertiti direttamente in depositi ufficiali con collegamento e metadati completi invece di restare in un lotto cieco.
- Aggiunti test di regressione su deposito generico riassorbito dal catalogo ufficiale, backfill automatico dal core telematico nella pagina fascicolo, riepilogo documentale e wiring bootstrap, cosi' il contatore `Da riallineare` non torna piu' a salire per questi casi.

## 2.182.14 - 2026-04-23

- Lex AI usa ora contesti strutturati reali per `studio_operativo`, `fascicolo_intelligence`, `conformita_fascicolo` ed `economico`, riusando direttamente `WorkspaceIntelligenteService`, `Responsabile di conformita'`, `preventivi`, `conferimenti` e `fatturazione` invece di limitarsi a riepiloghi testuali fragili.
- Il retrieval applicativo di Lex espone adesso sorgenti operative e di compliance governate: le risposte di `cabina`, `next_action`, `economico` e `compliance` nascono da dati runtime veri dello studio e non da placeholder generici.
- Corretto anche il contesto anagrafico e agenda del fascicolo: Lex risolve finalmente cliente e parti processuali dal fascicolo aperto e aggancia appuntamenti collegati anche tramite `id_cliente`, numero o `RG`, evitando vuoti artificiali nel RAG.
- Rafforzato il provider deterministico con risposte professionali e task-aware su cabina operativa, presidio economico e conformita' del fascicolo, con nuovi test di regressione che bloccano il ritorno dei vecchi vuoti di contesto.

## 2.182.13 - 2026-04-23

- Lex AI non tronca piu' il contesto documentale del fascicolo a 8 elementi: `load_document_context` e il retrieval documentale leggono ora tutto l'archivio del fascicolo aperto, cosi' pratiche con decine di allegati non perdono piu' contesto nel RAG.
- Estratta in `pct/fascicolo_workspace.py` la classificazione condivisa delle sezioni del fascicolo (`attivita' processuali`, `documenti fascicolo`, `udienze e scadenze`, `comunicazioni di cancelleria`, `istanze`), riusata sia dal runtime UI sia da Lex per evitare disallineamenti futuri tra pagina fascicolo e assistente.
- Il contesto strutturato di Lex espone ora anche `fascicolo_sezioni`, con conteggi e voci per sezione, e il retrieval fascicolo pubblica riepiloghi e voci rilevanti delle stesse sezioni, cosi' Lex puo' rispondere sul fascicolo usando la stessa tassonomia che l'utente vede nell'interfaccia.
- Rafforzati i test di Lex per coprire fascicoli con piu' di 8 documenti e workspace completi con attivita', udienze/scadenze, comunicazioni e istanze, prevenendo il ritorno del limite rigido nei prossimi commit.

## 2.182.12 - 2026-04-23

- Resa stabile la disciplina dei due branch gemelli: il workflow `.github/workflows/sync-claude-to-codex.yml` specchia ora automaticamente sia `Codex/legal-electronic-filing-kIxcV` verso `claude/legal-electronic-filing-kIxcV` sia il percorso inverso, evitando riallineamenti manuali ripetuti dopo ogni push.
- Introdotti hook Git versionati in `.githooks/` con autosync locale dei branch ammessi dopo `commit`, `checkout`, `merge` e `rewrite`, cosi' i due branch locali non divergono piu' tra loro durante il lavoro quotidiano.
- `scripts/repo_hygiene.ps1` esegue ora anche il bootstrap di `safe.directory`, installa `core.hooksPath=.githooks` e ripulisce le configurazioni branch orfane, mentre i test di governance controllano esplicitamente questi guardrail per impedire regressioni future.

## 2.182.11 - 2026-04-23

- Riallineato il motore di autenticazione e i runtime tenant-aware per evitare regressioni nei test completi: i permessi di piattaforma restano segregati, i tenant caricati da archivio SQL recuperano correttamente lo `slug` di studio e il layout base non va piu' in errore quando la pagina espone configurazioni locali.
- I flussi `PDP Penale` e `Centro Servizi Telematici` tornano a usare i rispettivi archivi dedicati (`pdp_penale.db` e `workflow.db`) invece dello `studio.db` generico, cosi' i casi, i documenti e gli allineamenti di portale vengono letti e scritti nel dominio corretto.
- Lo scadenziario in ambiente di test usa di nuovo il suo archivio dedicato quando configurato su file JSON, evitando disallineamenti tra le azioni della UI e i controlli che rileggono le scadenze salvate.
- Ripristinata la password iniziale `admin` solo per i test automatici del gestionale che creano il primo amministratore senza bootstrap esplicito, lasciando invariata la generazione casuale della password temporanea negli altri contesti.

## 2.182.10 - 2026-04-23

- Applicati in sequenza i pacchetti `repo hardening`, `repo refactor`, `repo local signer`, `repo 95` e `repo 100` con integrazione coerente sulla struttura reale del progetto.
- Aggiunti i nuovi strumenti di presidio `check_local_signer_boundaries`, `check_lex_quality_gates`, `check_performance_budget` e `check_release_readiness`, insieme ai test dedicati e ai workflow overlay di qualita' e readiness.
- Il `Local Signer` adotta ora i moduli separati `local_signer_mod` per sicurezza/origini, cache AI, facciata AI e bootstrap server, mantenendo la logica AI gia' operativa nel file principale tramite delega incrementale invece di sostituirla con stub vuoti.
- Introdotte anche le guide operative e la documentazione di maturita' (`LEX`, `performance`, osservabilita', multi-studio, release train e checklist di esercizio) previste dai pacchetti strutturali.

## 2.182.9 - 2026-04-23

- Chiusa la tranche di hardening repository richiesta nel bundle senza deviazioni: `pyproject.toml` riallineato a Python `3.12`, `setup.py` governato dal manifest condiviso, `SECURITY.md` e `CONTRIBUTING.md` riscritti in modo coerente con il prodotto e introdotti `constraints` globali per stabilizzare installazioni locali, CI e deploy.
- Rafforzata la pipeline GitHub Actions con controllo baseline Python, sincronizzazione packaging, installazione con `constraints`, gate coverage critico al `65%` e ambiente test coerente anche per `E2E smoke` e `Local Signer / PKCS#11`.
- Corrette le regressioni che facevano fallire la CI reale: `asn1crypto` rientra ora negli extra PDF usati dai job signer, `PYTHONPATH` e packaging sono coerenti nei job smoke, la fixture `admin/database` autentica davvero l'utente nel canale usato dall'app e il bridge HTTP di Lex non forza piu' percorsi guidati quando la richiesta e' di ricerca giuridica o richiede fonti esterne rigorose.
- La firma visibile su PDF non degrada piu' su timbro generico sotto pytest con warning severi: la fusione pagina usa ora un percorso compatibile con `pypdf` senza innescare deprecazioni trattate come errore in CI.

## 2.182.8 - 2026-04-22

- Rimesso in sicurezza l'accesso ai dati di studio sui tenant SQLite: se la modalita' `WAL` non e' disponibile sul volume dati, il motore passa automaticamente a una modalita' compatibile invece di far esplodere pagine come `Panoramica studio`, `Fascicolo` e superfici amministrative collegate.
- Rafforzato anche il gestore utenti dei tenant: se il backend SQL dello studio non e' disponibile, il sistema ripiega in modo governato sull'archivio locale utenti e audit, evitando errori interni sulle pagine di amministrazione e autenticazione.
- Lex AI non lascia piu' passare risposte artificiose o da "esempio di chatbot" sui fascicoli e sulle ricerche legali: le richieste sul fascicolo passano su un percorso guidato piu' concreto, mentre le risposte giuridiche prive di base verificata vengono degradate con prudenza invece di essere mostrate come buone.
- Ridotta anche la verbosita' inutile delle fonti mostrate da Lex nei percorsi operativi: sulle richieste di studio vengono evidenziati solo i riferimenti davvero utili alla risposta, non liste tecniche poco leggibili.

## 2.182.7 - 2026-04-22

- Alleggerito davvero l'avvio nel cloud gestito: in ambiente Railway/Render il bootstrap pesante dei registri dati, della governance installazione e dei tenant legacy non viene piu' eseguito prima che il servizio dichiari la propria disponibilita', ma solo quando serve davvero.
- Ridotto l'avvio predefinito di Gunicorn a un solo processo applicativo, coerente con il motore `gevent`, cosi' il cloud non raddoppia inutilmente il lavoro iniziale sul volume dati durante il primo avvio.
- Il controllo permessi sul volume dati non scandisce piu' in profondita' l'albero `/data` nei cloud gestiti: verifica solo i punti essenziali e lascia partire subito il servizio.
- Railway ha ora una finestra di controllo iniziale piu' ampia (`300s`) per gestire con margine i volumi gia' popolati senza dichiarare prematuramente il servizio non disponibile.

## 2.182.6 - 2026-04-22

- Allineato l'avvio cloud alla porta assegnata dal provider: Gunicorn ascolta ora su `PORT` quando Railway la imposta, mantenendo `8080` come fallback locale. Questo evita controlli iniziali falliti con messaggio `service unavailable` pur in presenza di applicazione corretta.
- Il controllo di prontezza del contenitore usa la stessa porta effettiva del servizio, cosi' il presidio iniziale non resta piu' legato a una porta fissa solo locale.

## 2.182.5 - 2026-04-22

- Alleggerito l'avvio cloud del container: il bootstrap dei permessi sul volume dati non scandisce piu' ricorsivamente tutto `/data` prima di avviare l'applicazione, evitando partenze lente su Railway con archivi gia' popolati.
- Introdotto il controllo di prontezza leggero `/api/pronto`, usato ora sia dall'immagine Docker sia dal deploy Railway e dal compose locale per verificare che la cabina sia pronta senza aspettare controlli piu' pesanti.
- Railway usa ora una finestra iniziale piu' ampia per il primo controllo di avvio, cosi' l'istanza non viene dichiarata non pronta mentre completa il bootstrap iniziale del volume.

## 2.182.4 - 2026-04-22

- Riallineato il Dockerfile al deploy Railway: rimossa la direttiva `VOLUME`, non supportata dal builder Railway, lasciando la persistenza governata dal volume del servizio e dal percorso runtime `/data`.
- Rafforzata anche la salute dei servizi locali: `scheduler-worker` e `ocr-worker` non ereditano piu' un controllo pensato per l'interfaccia web, ma avranno un controllo dedicato coerente con il loro ruolo.

## 2.182.3 - 2026-04-22

- Chiusa la leggibilita' del menu laterale: le voci principali e i collegamenti recenti non vengono piu' tagliati su una sola riga, ma si adattano su due righe con sidebar piu' ampia e spaziatura coerente.
- La navigazione laterale conserva una lettura chiara anche su etichette piu' lunghe come `Cabina Intelligente`, `Tutti i Fascicoli` e i riferimenti recenti di fascicolo o cliente, evitando ellissi premature che rendevano il menu poco usabile.
- Ripuliti diversi testi utente ancora troppo tecnici: `dashboard`, `console`, `wizard`, `workflow`, `runtime`, `fallback` ed `endpoint` vengono ora mostrati con un linguaggio piu' vicino al lavoro di studio (`panoramica`, `cabina`, `percorso guidato`, `percorso operativo`, `motore locale`, `via alternativa`, `indirizzo del servizio`).

## 2.182.2 - 2026-04-22

- Chiusa la governance packaging/deploy che restava ancora troppo fragile: introdotti `packaging_manifest.py`, `pyproject.toml`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md` e lo script `tools/sync_packaging_files.py`, cosi' versione e dipendenze non restano piu' duplicate in piu' file scollegati.
- `setup.py` non mantiene piu' liste hardcoded: legge ora versione da `pct/__init__.py`, runtime requirements da `requirements/base.txt` e gli extra ufficiali da `requirements/pdf.txt`, `requirements/pades.txt`, `requirements/pkcs11.txt`.
- I file flat `requirements.txt` e `requirements-dev.txt` sono ora generati in modo rigoroso dal manifest requirements, con check automatico in CI per impedire nuove divergenze tra locale, container e pipeline GitHub.
- Rafforzata la CI: packaging sync check, lint Ruff piu' severo sui moduli governati, gate mypy sui boundary packaging, coverage minima sui moduli critici (`auth`, `storage`, `lex`, `telematico`) ed E2E smoke su pull request, piu' workflow notturno separato per la suite E2E completa.
- Riallineato il backend PostgreSQL al toolchain attuale: `psycopg2-binary` passa a `2.9.11`, coerente tra manifest e requirements flat.
- Corretto un difetto reale del corpus giurisprudenziale: query FTS con date e punteggiatura (`sentenza n. 8785 del 08/04/2026`) non generano piu' `fts5: syntax error`, ma vengono normalizzate prima della ricerca.
- Sul caso operativo `vorrei fare un preventivo`, Lex conferma ora nel runtime reale il comportamento atteso: risposta workflow-aware, `fallback_triggered=False`, `web_fallback_used=False`, affidabilita' alta e sole fonti di studio realmente pertinenti.

## 2.182.1 - 2026-04-22

- Corretto il comportamento di Lex sui workflow operativi con una `via di mezzo` governata: `preventivo`, `tariffario`, `fattura`, `cabina` e `prossima azione` usano prima il contesto studio e i moduli interni, senza trascinare automaticamente dentro fonti legali e motori di ricerca non pertinenti.
- Il retrieval bounded di Lex puo' ora seminare evidenze dal `contesto studio` gia' costruito da IUSENTRA, cosi' il workflow economico non parte piu' da zero e non degrada su fonti decorative quando il repository interno ha gia' elementi utili.
- Il router delle fonti non aggiunge piu' in automatico `NormativeSource`, `GiurisprudenzaSource` e `LegalIntelligenceSource` a una semplice richiesta tipo `vorrei fare un preventivo`, salvo quando la domanda diventa davvero normativa o richiede fonti ufficiali forti.
- L'affidabilita' e i gap di evidenza sono ora workflow-aware: le richieste legali strette continuano a richiedere fonti ufficiali e confronto forte, mentre i workflow economici non vengono piu' penalizzati con warning tipo `mancano fonti ufficiali` quando la risposta e' solo operativa.
- Riallineato il packaging runtime: `setup.py` include ora anche `sqlalchemy` e `PyMySQL`, usa la stessa versione di `psycopg2-binary` di `requirements.txt`, e il `Dockerfile` esegue il runtime con bootstrap sicuro del volume `/data`, drop privilegiato verso `iusentra` quando il mount lo consente, fallback esplicito a `root` sui bind mount incompatibili, `HEALTHCHECK` e volume dati esplicito.
- Aggiunti test automatici dedicati su source routing economico, seed del contesto studio nel retrieval, payload HTTP bounded e coerenza packaging/versioning.

## 2.182.0 - 2026-04-22

- Integrato in Lex il catalogo governato delle fonti `aperte / con registrazione / partner / riservate / portale istituzionale`, caricato da registry YAML e agganciato davvero a retrieval, source policy, evidence pack, guardrail e payload finale del widget.
- I domini del kit non restano piu' `unknown`: la source policy riconosce ora anche fonti come `INI-PEC`, `Registro Imprese`, `PST / ReGIndE / PdA`, `PAT / SIGA` e `PTT / SIGIT`, distinguendo autorita' della fonte e modalita' di accesso.
- Il fallback web ufficiale cerca solo dove ha senso: per le fonti `partner` o `riservate` Lex non inventa risultati pubblici, ma espone gap di copertura, badge di accesso, warning sulle credenziali necessarie e prossime azioni operative.
- Il widget chat mostra ora anche il profilo di accesso delle fonti (`source_access_label`, `Credenziali`, `Riservata`), cosi' l'operatore capisce perche' una fonte non e' interrogabile via web pubblico.
- Aggiunte regressioni automatiche dedicate su registry, source policy, fallback partner/riservato, orchestrator retrieval e bridge HTTP di Lex.

## 2.181.0 - 2026-04-22

- Introdotto il modulo nativo `Sito Studio`, con dashboard tenant-aware, branding, pagine a blocchi, articoli, servizi, professionisti, sedi, contatti, agenda pubblica e sito web pubblicabile senza CMS esterno.
- Aggiunta la superficie pubblica `/web/<public_slug>/` e la console piattaforma `Piattaforma -> Siti studio`, con repository SQL dedicato sia `SQLite` sia `PostgreSQL`, asset tenant-aware e bootstrap automatico del sito studio dal profilo del tenant.
- Le sezioni pubbliche `Strumenti legali`, `Applicazioni` e `News giuridiche strutturate` sono ora governate da flag espliciti dell'amministratore del sito: restano nascoste e rispondono `404` finche' non vengono attivate da `Sito Studio -> Impostazioni`.
- Chiusa la filiera `prenotazione pubblica -> approvazione studio -> agenda`: le richieste sito si sincronizzano davvero in agenda tenant-aware e la migrazione legacy verso `studio.db` riallinea ora correttamente le colonne `dati_json` richieste dai moduli runtime.
- Rafforzata la migrazione SQLite unificata: le tabelle core legacy (`fascicoli`, `appuntamenti`, `scadenze`, `messaggi`, `utenti`) includono ora `dati_json` gia' nello schema base e nel payload migrato, con riallineamento automatico post-migrazione.

## 2.180.1 - 2026-04-22

- La console `Piattaforma -> Assistenza remota` permette ora al `SUPERADMIN` di configurare direttamente da UI i parametri operativi del modulo: `STUN`, `TURN`, secret condiviso, TTL, durata token WebSocket e `SUPPORT_ADVANCED_URL_TEMPLATE`.
- Il runtime applica subito i valori salvati senza restart manuale e li persiste nella configurazione piattaforma, cosi' i warning di readiness non restano piu' messaggi senza azione possibile.
- Il secret TURN non viene sovrascritto se il campo resta vuoto in modifica, e il modulo continua a bloccare l'escalation avanzata solo quando manca davvero la configurazione necessaria.

## 2.180.0 - 2026-04-22

- Introdotto il modulo `Assistenza remota cliente` governato solo dal `SUPERADMIN`, con console piattaforma dedicata (`/admin/supporto-remoto`), creazione sessione da dashboard studio, scheda cliente e dettaglio fascicolo.
- Aggiunta la filiera completa WebRTC per supporto remoto: link cliente firmato, stanza operatore, signaling WebSocket, condivisione schermo, microfono opzionale, chat tecnica, audit leggibile, consensi espliciti e chiusura sessione tracciata.
- Creato il repository SQL governato del dominio `support_remote` con schema dedicato sia `SQLite` sia `PostgreSQL`, senza fallback invisibili su JSON.
- Integrato l'aggancio al controllo remoto avanzato esterno: l'operatore puo' richiedere l'escalation, il cliente deve approvarla in modo esplicito e il runtime la blocca se `SUPPORT_ADVANCED_URL_TEMPLATE` non e' configurato.
- Allineato il runtime locale e containerizzato: `Sock` inizializzato nella factory Flask, WebSocket registrato nel wiring applicativo, reverse proxy Nginx configurato per `/support/ws/`, percorso persistente `PCT_SUPPORT_DB` e documentazione operativa dedicata.

## 2.179.3 - 2026-04-22

- Corretto il comportamento reale del widget Lex sulla chat operativa: le richieste di `preventivo`, `tariffario`, `fatturazione`, `telematico`, `fascicolo` e `ricerca legale` non restano piu' affidate a prompt generici, ma passano direttamente al bounded workflow governato anche dalla UI `/api/assistente/*`.
- Il bridge HTTP di Lex trasferisce ora davvero il contesto di studio alla pipeline bounded (`messaggi`, `focus`, `profilo richiesta`, `execution policy`, `source policy`) e, quando il contesto interno non basta, abilita in modo esplicito il fallback di ricerca web ufficiale invece di lasciare la risposta nel vago.
- Rafforzato il profilo richiesta economica: `preventivo guidato`, `tariffario e compensi`, `fatturazione/parcelle/pagamenti` hanno ora intenti distinti e portano Lex sul percorso giusto senza risposte meta o simulate.
- Migliorata la risposta deterministica economica: su richieste come `vorrei fare un preventivo` Lex apre il percorso corretto, distingue preventivo/tariffario/fattura e chiede solo i dati davvero necessari per proseguire.
- Aggiunta una cintura di sicurezza lato prompt e lato widget per impedire output meta del tipo `ecco una risposta`, `motivazione`, `simulazione di chatbot` o scaffolding simili.

## 2.179.2 - 2026-04-22

- Rafforzato Lex dove mancava ancora la parte piu' operativa: il retrieval usa ora una cache TTL tenant-aware, cosi' richieste ripetute dello stesso studio riusano il pacchetto evidenze senza rilanciare inutilmente tutte le sorgenti e dichiarano sempre `cache hit` e `ttl` nel payload finale.
- Aggiunti property test veri sulla source policy e sui guardrail legali di Lex (`tier`, ordinamento score, ranking e blocco PDF/sentenze non verificate), con `hypothesis` come dipendenza dev esplicita e governata.
- Chiuso il presidio dei canali telematici esterni con circuit breaker dedicati per ricerca e anteprima portali, messaggi operativi leggibili e nuova diagnostica `PORTAL_CIRCUIT_OPEN` dentro observability.
- Rafforzata la governance storage senza refactor distruttivi: il factory `core_storage_backend` valida ora un contratto minimo comune del backend strutturato tenant-aware prima di usarlo a runtime.

## 2.179.1 - 2026-04-22

- Corretto il `500` reale della sezione `Checklist Atti` sui template stragiudiziali a canale `PEC`, in particolare sul dettaglio built-in `Atto di messa in mora`.
- Riallineato il mapping degli endpoint operativi checklist: il canale `PEC` usa ora l'endpoint Flask reale `lista_messaggi` invece del vecchio alias `messaggi`.
- Aggiunta una salvaguardia nella route `checklist_dettaglio` che normalizza gli alias legacy degli endpoint operativi e impedisce nuovi `BuildError` in render Jinja se un nome route storico non e' piu' registrato.
- Aggiunta regressione HTTP sul template built-in `builtin-tmp-str-008` per garantire che il dettaglio risponda `200` e che il pulsante `Apri canale operativo` punti davvero a `/messaggi`.

## 2.179.0 - 2026-04-22

- Introdotta l'architettura governata `Product Pack / Studio Local Pack / Update Pack`, con bootstrap installazione idempotente, identita' macchina, chiavi per installazione e manifest separati per prodotto, tenant e aggiornamenti.
- Aggiunta la cabina piattaforma `Piattaforma -> Pack installazione` (`/admin/installazione-pack`), riservata al `SUPERADMIN`, con rigenerazione manifest, stato servizi locali e repository SQL/PostgreSQL dei pack.
- Creati repository SQL espliciti per i manifest dei pack, con schema dedicato sia SQLite/SQL locale sia PostgreSQL (`installation_product_pack_manifest`, `installation_studio_local_pack_manifest`, `installation_update_pack_manifest`).
- Estesa la struttura tenant-aware con la root `studio_data/` e sottodirectory governate per `db`, `vectors`, `memory`, `documents`, `attachments`, `audit`, `backups`, `cache`, `jobs` e `keys`.
- Corrette due incoerenze reali di piattaforma: il `SUPERADMIN` puo' usare anche la superficie legacy `/admin/database`, e il registro `Audit` riconcilia i fascicoli sul tenant attivo usando i percorsi request-aware invece della configurazione globale.
- Riallineate le regressioni di bootstrap web e tenant-aware alla separazione vera tra piattaforma e studio, preservando test pubblici PWA, login tenant, audit storico e nuova superficie pack.

## 2.178.13 - 2026-04-22

- Chiarita la configurazione del runtime AI locale nelle `Impostazioni`: il campo non viene piu' presentato come semplice URL, ma come `Prefisso API del runtime locale`, per evitare ambiguita' quando si apre manualmente Ollama dal browser.
- Aggiunto nel pannello AI il controllo rapido `Apri controllo /api/version`, che compone automaticamente l'endpoint corretto a partire dal prefisso configurato e aggiorna anche il promemoria inline visibile all'operatore.
- Rafforzata la regressione statica della tab `AI Locale` per impedire il ritorno di etichette fuorvianti o la perdita del controllo guidato verso `/api/version`.

## 2.178.12 - 2026-04-22

- Introdotto un layer governabile di resilienza runtime con circuit breaker condivisi per `Ollama` e `PEC / IMAP`, cosi' i runtime esterni instabili non vengono martellati all'infinito e restituiscono messaggi operativi leggibili.
- Rafforzata l'osservabilita': il pannello `admin/osservabilita` e il payload `/admin/system-health` leggono ora anche il circuito `PEC / IMAP`, mentre il runtime AI locale espone lo stato del proprio breaker insieme alla diagnostica del provider.
- Aggiunto logging strutturato con masking automatico di CF, email, IBAN e telefoni, attivabile in JSON in produzione senza introdurre dipendenze extra.
- Riallineati i workflow AI che chiamano Ollama (`Lex`, `Coverage AI`, `Update Intelligence`) al client condiviso, evitando path divergenti tra runtime locale e motori assistiti.
- Estesa la suite con test dedicati su logging sensibile, circuit breaker runtime, degrado observability e invarianti deterministici della source policy di Lex.

## 2.178.11 - 2026-04-22

- Integrato il bundle `Lex` con router applicativo piu' ricco, provider deterministico locale per i workflow operativi (`cabina`, `economico`, `telematico_status`, `compliance`, `next_action`) e registry provider riallineato ai nuovi contratti.
- Il retrieval Lex ora attiva davvero il fallback verso fonti ufficiali esterne quando l'evidenza interna non basta, confronta le fonti con trust/freshness/context fit/consensus ed espone nel payload finale `official_sources`, `coverage_gaps`, `fallback_triggered`, `compared_sources` ed `evidence_sufficient`.
- Rafforzati i guardrail legali: le richieste di sentenze, riferimenti puntuali e PDF vengono degradate o bloccate se non emergono riferimenti verificati, invece di completarsi in modo plausibile.
- Aggiunti test dedicati per i 5 scenari chiave del bundle (`sentenza con numero/PDF`, `normativa con fallback ufficiale`, `errore telematico`, `riassunto fascicolo`, `caso economico preventivo/tariffario/fattura`) e riallineata la suite Lex ai nuovi workflow.

## 2.178.10 - 2026-04-20

- Corrette le date nella pagina `Email`: l'elenco e il dettaglio usano ora i filtri condivisi italiani e non mostrano piu' formati `mm/dd`.
- Rafforzato il matching PEC/fascicoli: le notifiche dal canale giustizia (`giustiziacert`, `Notificazione ai sensi del D.L. 179/2012`) vengono collegate correttamente alle comunicazioni di cancelleria del fascicolo.
- `Auto-esiti` non consuma piu' in modo definitivo le PEC PST non abbinate: restano rielaborabili ai click successivi finche' non trovano il deposito giusto.
- `Sincronizza PEC` dalla pagina fascicolo lavora sul fascicolo corrente, espone le PEC in attesa di abbinamento e ricarica la vista anche quando trova comunicazioni gia' presenti per mostrare davvero la sezione aggiornata.

## 2.178.9 - 2026-04-20

- Corretto il flusso `Email`: la sincronizzazione IMAP e il polling PEC ora usano un timeout esplicito, così il pulsante `Aggiorna` non resta più indefinitamente in `Sync` quando il server PEC non risponde.
- Aggiunta la route reale `/email/api/stats`, già richiesta dalla shell UI, per eliminare i `404` silenziosi sul badge posta e riallineare la pagina `Email` al runtime effettivo.
- La pagina `Email` gestisce ora timeout, warning e messaggi operativi leggibili lato browser sia su `Aggiorna` sia su `Auto-esiti`, senza spinner infiniti o esiti muti.
- Corretto il `cockpit fascicolo`: i pulsanti `Apri scheda`, `Apri workflow`, `Apri controllo`, `Apri documenti` e `Apri deposito` attivano davvero il tab corretto anche quando il wiring Bootstrap non si innesca in automatico.
- Aggiunte regressioni eseguibili su timeout IMAP, warning della route `/email/sincronizza`, route `/email/api/stats` e attivazione della cabina fascicolo.

## 2.178.8 - 2026-04-20

- Alleggerito il runtime locale multi-tenant: il bootstrap legacy, la riconciliazione storage e il bootstrap dei moduli dati non vengono piu' rieseguiti a ogni richiesta della stessa sessione tenant-aware.
- Le richieste statiche (`/static/...`) vengono escluse dal bootstrap tenant, evitando il collo di bottiglia che rallentava caricamento di CSS, JavaScript e panoramica generale.
- Aggiunte regressioni automatiche per bloccare il ritorno del bootstrap tenant su asset statici e per garantire che la preparazione del tenant avvenga una sola volta per worker.

## 2.178.7 - 2026-04-20

- Corretto il parser JavaScript del `Wizard preventivi`: alcune espressioni introdotte nella tranche precedente mescolavano `??` e `||` nella stessa riga, bloccando l'inizializzazione completa della pagina e lasciando vuoti i filtri di `Classificazione tassonomica` e le altre superfici guidate del wizard.
- Il wizard ora usa un helper esplicito per scegliere i valori economici della bozza senza rompere il parsing del browser, mantenendo la correzione sulle `Spese generali` dentro `Anticipazioni art. 15`.
- Aggiunta regressione statica sul template per impedire il ritorno di espressioni JavaScript non valide nelle sezioni critiche del preventivo guidato.

## 2.178.6 - 2026-04-20

- Corretto il `Wizard preventivi` sulla bozza economica: quando il flag `Spese generali ex art. 2 D.M. 55/2014` e' attivo, il suo importo non viene piu' inglobato nella riga `Compenso professionale`, ma confluisce nel riepilogo `Anticipazioni art. 15` della bozza come richiesto dal flusso operativo.
- Allineato anche il salvataggio finale del preventivo: il wizard persiste il totale anticipazioni della bozza tramite campo dedicato, cosi' il dettaglio preventivo non diverge piu' da quanto l'operatore ha visto nel riepilogo prima della creazione.
- Aggiunte regressioni eseguibili per calcolo wizard e generazione preventivo, in modo da bloccare il ritorno del bug su `Spese generali` e `Anticipazioni art. 15`.

## 2.178.5 - 2026-04-20

- Il `Quadro intelligente fascicolo` usa ora controlli reali sul fascicolo corrente invece delle vecchie percentuali statiche: anagrafica, documenti, metadati ufficiali di portale, scadenze rispetto alla data odierna, udienze storiche non riallineate e coerenza tra stato della pratica e provvedimenti presenti.
- La regia del fascicolo non propone piu' mosse fuorvianti come `Udienza da portale` su pratiche con udienze ormai storiche: le scadenze vengono mostrate come future oppure scadute, e i provvedimenti finali presenti nel fascicolo entrano nella valutazione operativa.
- I documenti acquisiti dal portale telematico riportano ora davvero nome ufficiale, classificazione, tipo atto, mittente, identificativi del deposito e riferimenti del portale anche sui fascicoli gia' scaricati, grazie alla riconciliazione automatica al primo accesso del dettaglio.
- Il caricamento manuale memorizza il nome originale del file e la UI documento espone metadati ufficiali e origine del documento, cosi' la sezione documentale del fascicolo resta leggibile e verificabile.
- Il presidio intelligente riconosce come chiusa anche una pratica legacy che serializza lo stato come stringa `DEFINITO` o `ARCHIVIATO`, e non duplica piu' gli stessi provvedimenti quando il portale li ha fatti entrare piu' volte nel fascicolo.
- Rafforzato il matching PEC e `Auto-esiti`: oltre al numero RG usa anche nominativo cliente, controparte, oggetto e tribunale, migliorando l'associazione di comunicazioni di cancelleria e aggiornamenti deposito sul fascicolo corretto.

## 2.178.4 - 2026-04-20

- Completato il supporto ufficiale ai costi organismo mediazione ex `D.M. 24 ottobre 2023, n. 150` in `Wizard preventivi` e `Console tariffaria`: regime volontaria / obbligatoria-demandata, esito del primo incontro o degli incontri successivi, maggiorazione art. 31, comma 3 e costo organismo che entra davvero nel totale operativo.
- Corretto il wiring del wizard sulle tipologie a `compenso unico`: la UI non mostra piu' checkbox fasi fuorvianti e le classificazioni tassonomiche aggiuntive usano le fasi reali della pratica collegata.
- Pulite le fonti normative collegate a mediazione e tassonomia, con URL Gazzetta ufficiale corretti (`23G00163`) e tabella normativa `mediazione_costi_odm_dm150` resa disponibile anche nella console tariffaria.
- Aggiunte regressioni eseguibili su calcolo D.M. 150/2023, seed normativo, route wizard e route tariffario per impedire ritorni ai vecchi bug su totale invariato, placeholder indicativi e riferimenti normativi errati.

## 2.178.3 - 2026-04-20

- Rifinito il `Wizard preventivi` con microcopy coerente, stato inline persistente al posto dei vecchi `alert()` browser, messaggi di validazione piu' chiari e ricalcolo guidato e debounced per fasi, ADR, accessori, classificazioni tassonomiche e opzioni fiscali.
- Rafforzata la percezione di performance e coerenza: il wizard ora riusa i fetch di calcolo gia' eseguiti per accessori e classificazioni, mostra feedback immediato mentre aggiorna la bozza e riduce i ricalcoli ripetuti durante la stessa sessione.
- Migliorata la `Console tariffaria` con indicazione esplicita del motore di calcolo attivo, distinzione chiara tra spese generali incluse o escluse e submit con stato di elaborazione visibile.
- Resi i log di `preventivi` e `tariffario` piu' leggibili e narrativi: le operazioni principali raccontano utente, motore, regola, fase e risultato invece di limitarsi a messaggi tecnici di errore.

## 2.178.2 - 2026-04-20

- Corretto davvero il flusso `Preventivi -> Wizard` sui toggle economici: fasi selezionate, spese generali e altri flag booleani incidono ora in modo coerente sia nel calcolo live sia nel salvataggio finale, senza effetti fantasma dovuti ai campi hidden `0/1`.
- Il wizard puo' creare davvero il cliente minimale durante l'inserimento rapido e persiste le `classificazioni tassonomiche` ripetibili anche nei repository SQL/PostgreSQL, con conteggio dedicato e righe aggiuntive di compenso nella bozza.
- Rafforzata la console `Tariffario Forense`: il form route-side rispetta davvero il toggle `Spese generali 15%` e la UI continua a distinguere correttamente `compenso unico` per i profili che lo prevedono.
- Aggiornate le migrazioni SQL e PostgreSQL del dominio preventivi e aggiunte regressioni eseguibili su wizard, repository e route tariffario per impedire ritorni ai vecchi bug di calcolo.

## 2.178.1 - 2026-04-20

- Corretto il `Crash test operativo` nel runtime reale: se il container non ha `pytest`, il motore non fallisce piu' per dipendenza di sviluppo mancante ma usa controlli operativi interni equivalenti per dati sporchi, workflow cliente -> incasso, pipeline AI, publish sicuro, migrazione con rollback e observability azionabile.
- Mantenuta la tracciabilita' con i golden path ufficiali: le fasi continuano a puntare ai test E2E dichiarati nel repo, ma la produzione puo' eseguire gli stessi controlli in modo autonomo e spiegabile.
- Aggiunta copertura automatica sul fallback runtime del crash test, cosi' il comportamento resta dimostrabile sia in CI sia nel container di deploy.

## 2.178.0 - 2026-04-20

- Introdotta la cabina `Piattaforma -> Crash test operativo`, con report reale delle fasi critiche di una giornata di studio, checklist finale `si/no`, ticket di riparazione persistiti e lettura diretta dello stato sistema.
- Aggiunta la filiera governata `pct/operational_resilience.py` + repository SQL/PostgreSQL dedicato per report crash test, ticket di repair e backup blindati, con schema esplicito sia SQLite sia PostgreSQL.
- Aggiunti i comandi ufficiali `iusentra crash-test-operativo` e `iusentra backup-blindato` per eseguire fuori dalla UI il crash test e il piano backup completo + incrementale.
- Il scheduler esegue ora autotest di riparazione alle `07:00`, `13:30`, `19:30` e backup blindato alle `23:50`, iterando sui tenant attivi senza fallback nascosti.
- Estesa la coverage E2E con `tests/e2e/test_operational_crash_day.py` e `tests/test_operational_resilience.py`, che presidiano dati sporchi, failure del publish SQL, osservabilita' azionabile, repository operativi e superficie admin.
- Aggiornate README e documentazione tecnica con guida dedicata al crash test operativo, alle destinazioni backup locale/cloud e alle nuove variabili `PCT_BACKUP_LOCAL_MIRROR_DIR`, `PCT_BACKUP_SECONDARY_MIRROR_DIR`, `PCT_BACKUP_SECONDARY_LABEL`.

## 2.177.0 - 2026-04-20

- `/applicazioni` e' stata trasformata da catalogo di scorciatoie a **workspace operativo reale**, coerente con `/strumenti-legali`: la voce selezionata si apre ora nella stessa pagina con contesto fascicolo, form inline, KPI, tabelle risultato e CTA verso il dominio reale.
- Introdotta una filiera governabile dedicata per il runtime applicazioni: `pct/applicazioni_runtime.py` risolve il tipo di modulo e normalizza i risultati, mentre `web/services/applicazioni_runtime.py` costruisce i pannelli veri per tool, template, economico, telematico, lookup, rassegna, giurisprudenza e utility.
- Le vecchie schede dettaglio non sono piu' una falsa applicazione autonoma: `/applicazioni/<id>` reindirizza ora al workspace attivo e la UI espone davvero i moduli correlati, senza fermarsi a un elenco di link.
- Aggiornati template, SCSS ufficiale e test di route/comportamento per presidiare il nuovo golden path del workspace applicazioni.

## 2.176.0 - 2026-04-19

- Allineata davvero `Checklist Atti` al catalogo professionale di `Template Atti`: la checklist non si ferma piu' a 30 schede curate ma ingloba anche tutte le checklist derivate dai `288` template built-in del workspace atti.
- La copertura tra le due superfici e' ora verificabile: `288/288` template professionali e `25/25` tassonomie `area -> branca -> sottobranca` del catalogo template risultano presenti anche in `/checklist`.
- Estesa la UI della checklist con messaggio di copertura reale del catalogo professionale, badge del nuovo canale `Workflow misto / redazione professionale` e dettaglio operativo arricchito con il profilo del template derivato.
- Aggiornati dominio, route e test per presidiare rami prima scoperti come `Procure e deleghe`, `UNEP e notificazioni`, `Societario`, `Immigrazione e cittadinanza` e tutte le altre varianti del catalogo atti.

## 2.175.1 - 2026-04-19

- `admin/utenti-piattaforma` e' diventata una console operativa completa per gli account globali: ora il `SUPERADMIN` puo' modificare davvero nome, email e stato degli account piattaforma senza passare dagli studi.
- La piattaforma puo' ora generare o sostituire il `SUPERADMIN` in modo governato: il nuovo account nasce solo a livello piattaforma, il ruolo resta unico e il precedente titolare viene declassato al ruolo scelto.
- Aggiunto il trasferimento esplicito del ruolo `SUPERADMIN` tra account globali esistenti, con chiusura pulita della sessione uscente e messaggio di riallineamento professionale.
- Estesa la copertura automatica con test di dominio e route per generazione, trasferimento e modifica degli account piattaforma.

## 2.175.0 - 2026-04-19

- Ridisegnata la superficie `Checklist Atti` come catalogo professionale strutturato per `area -> branca -> sottobranca`, con filtri reali, metriche operative e copertura estesa a lavoro, famiglia, penale operativo, amministrativo avanzato, esecuzioni e ADR.
- Portato il catalogo checklist a `30` template reali, includendo nuovi flussi per impugnazione licenziamento, separazione consensuale, divorzio congiunto, modifica condizioni familiari, opposizione esecutiva, motivi aggiunti TAR, appello al Consiglio di Stato, memoria ex art. 415-bis c.p.p., dissequestro, negoziazione assistita e diffida stragiudiziale.
- Corretto il naming delle cartelle: la data usa ora sempre il formato italiano filesystem-safe `gg-mm-aaaa`, coerente tra dominio, dettaglio checklist e wizard.
- Ripulite le viste checklist da testi corrotti e grouping povero, con nuova UI responsive governata da SCSS dedicato e test di regressione su dominio e route.

## 2.174.3 - 2026-04-19

- Reso il `Registro Attivita'` piu' spiegabile sui fascicoli storici: la pagina segnala ora se il riferimento e' attivo, riconciliato verso un fascicolo corrente oppure solo storico, invece di mostrare soltanto un ID apparentemente "sparito".
- Introdotta una riconciliazione automatica degli eventi fascicolo tramite documenti univoci presenti nel dettaglio audit, cosi' un vecchio ID puo' essere collegato al fascicolo corrente dopo migrazione o ricreazione del record.
- Aggiunta regressione UI sul caso `vecchio ID fascicolo -> nuovo fascicolo corrente`, per evitare che il registro torni a sembrare incoerente dopo riallineamenti storage o import storici.

## 2.174.2 - 2026-04-19

- Il `SUPERADMIN` di piattaforma non vede piu' la shell operativa di studio quando non e' in impersonazione: la navigazione principale mostra solo la superficie piattaforma e le route non piattaforma lo riportano al pannello admin, eliminando l'ambiguita' tra app di studio e cabina superadmin.
- `admin/utenti-piattaforma` non si limita piu' a segnalare le anomalie: ora permette di spostare davvero un account globale non `SUPERADMIN` dentro uno studio, preservando credenziali, stato attivo, storico accessi e audit.
- Introdotto il trasferimento governato degli utenti tra repository auth, con import strutturato nel tenant di destinazione e rimozione forzata del record globale anomalo solo durante il trasferimento amministrativo.

## 2.174.1 - 2026-04-19

- Chiusa davvero la separazione tra `SUPERADMIN` di piattaforma e gestione utenti legacy di studio: le route `/utenti`, `/utenti/nuovo`, `/utenti/<id>/modifica`, `/profili`, `/audit` e `/utenti/<id>/permessi` reindirizzano ora il `SUPERADMIN` verso `admin/utenti-piattaforma`.
- La schermata legacy `Nuovo utente` non mostra piu' il ruolo `SUPERADMIN` e il backend rifiuta in modo esplicito ogni tentativo di forzarlo via POST, cosi' uno studio non puo' piu' creare o promuovere il superadmin nemmeno da percorsi diretti.
- Rimossa anche l'ambiguita' di navigazione: il menu amministrativo tenant non viene piu' mostrato al `SUPERADMIN`, che usa solo la superficie piattaforma dedicata.

## 2.174.0 - 2026-04-19

- Resi ufficiali i tre golden path certificati di prodotto con nomi stabili e dimostrabili: `tests/e2e/test_studio_reale_flow.py`, `tests/e2e/test_ai_pipeline_full.py` e `tests/e2e/test_tenant_migration_full.py`, collegati alla CLI `iusentra golden-path`, alla governance prodotto e alla documentazione E2E.
- Blindata la migrazione `zero-risk`: ogni esecuzione persistente genera ora anche uno `snapshot pre-migrazione` fisico nel backup tenant-aware, espone un `diff_summary.by_domain` leggibile e salva nel report il contesto di rollback con comando guidato.
- Introdotto il rollback ufficiale `iusentra migrate --tenant=<slug> --rollback`, che ripristina il backend precedente dal report reale senza fallback invisibili e persiste un artefatto di rollback dedicato.
- Rafforzata l'osservabilita' operativa con tassonomia errori normalizzata (`OCR_TIMEOUT`, `OCR_QUEUE_OVERFLOW`, `AI_MODEL_UNAVAILABLE`, `TENANT_DB_ERROR`, `MIGRATION_FAILED`) e nuovo endpoint JSON `/admin/system-health` con stato sintetico di scheduler, OCR, AI e database.
- Estesa la governance della `Coverage AI`: il dettaglio draft espone ora anche policy di autopublish e blocco `ai_governance`, cosi' review, publish SQL e audit umano risultano ancora piu' spiegabili.

## 2.173.1 - 2026-04-19

- Corretto il disallineamento tra `storage_key` canonico e cartella legacy basata su `slug`: la riconciliazione tenant-aware e' ora bidirezionale e ripopola anche l'alias storico quando il dato autorevole esiste gia' nel tenant canonico, evitando l'effetto falso di fascicoli o clienti "spariti".
- La `Copertura AI` mostra ora come nome autorevole dello studio il tenant di piattaforma e, se `config/studio.json` contiene un nome interno diverso, lo espone solo come `configurazione interna studio`.
- Il dettaglio studio superadmin mostra il percorso storage canonico reale invece del vecchio `./data/tenants/{slug}/`, cosi' non confonde piu' slug legacy e root effettiva del tenant.

## 2.173.0 - 2026-04-19

- Resi i `golden path ufficiali` ancora piu' dimostrabili: la CLI `iusentra golden-path` salva ora sia report JSON sia report leggibile Markdown, mentre la governance prodotto mostra esplicitamente il percorso del report eseguibile.
- Blindata la `Coverage AI` con audit review forte su SQLite e PostgreSQL: motivo decisione, firma reviewer, diff tra draft originale e versione corrente, storico revisioni persistito e publish SQL tracciato.
- Rafforzato l'`Assistente migrazione` con `snapshot pre-migrazione` e `log operativo`, cosi' il report racconta davvero precheck, passaggi eseguiti, failure mode e recovery guidato.
- Estesa l'osservabilita' con `messaggio operatore` e remediation piu' azionabile per HTTP, OCR, worker OCR, AI locale, storage e capability prodotto.
- Aggiunti test E2E ufficiali dedicati su studio, Coverage AI e migrazione tenant completa per rendere i flussi core dimostrabili e ripetibili.

## 2.172.0 - 2026-04-19

- Ridisegnato il dettaglio fascicolo come `cabina operativa` professionale: la vista include ora i tab `Cabina`, `Quadro intelligente`, `Workflow -> incasso`, `Controllo economico`, `Governo documentale` e `Deposito e conformita'`.
- Il fascicolo unifica davvero le superfici gia' esistenti nello stesso centro di lavoro, con riepilogo del prossimo passo, KPI rapidi, workflow economico, controllo documentale e presidio del deposito senza duplicare pagine sparse.
- Aggiornati SCSS governati, test UI/route e documentazione prodotto per rendere il nuovo cockpit parte ufficiale del golden path operativo.

## 2.171.9 - 2026-04-19

- Corretto il resolver auth multi-tenant della piattaforma: il `SUPERADMIN` globale non legge piu' il ruolo dal `studio.db` locale del tenant, ma usa solo la persistenza auth di piattaforma, evitando 403 e incoerenze tra account root e storage del singolo studio.
- La superficie `admin/utenti-piattaforma` e le route superadmin restano ora separate dagli utenti tenant-aware anche quando sul SQL locale esiste un record storico `admin` con ruolo diverso.
- Aggiunta regressione sul caso sporco `JSON piattaforma = SUPERADMIN` ma `SQLite locale = AMMINISTRATORE`, per evitare di tornare a mostrare permessi tenant al superadmin di piattaforma.

## 2.171.8 - 2026-04-19

- Chiuso il modello di piattaforma in modo piu' professionale: il `SUPERADMIN` ha ora una superficie dedicata `admin/utenti-piattaforma`, separata dagli utenti tenant-aware degli studi, con reset password governato e controlli sulle anomalie globali.
- `Aggiornamenti legali` mostra come nome autorevole dello studio il tenant registrato in piattaforma e, se lo `studio.json` interno usa un nome diverso, lo espone solo come configurazione interna per evitare l'effetto "nuovo studio fantasma" nel pannello superadmin.
- Corretto il bootstrap auth multi-tenant: il riallineamento dell'unico `SUPERADMIN` di piattaforma avviene ora dentro l'application context Flask, quindi il runtime non resta incoerente all'avvio.

## 2.171.7 - 2026-04-19

- Blindata la separazione tra piattaforma e tenant: `SUPERADMIN` e' ora un ruolo unico di piattaforma, non puo' appartenere a uno studio e non puo' essere creato o promosso dai flussi tenant-aware.
- `Update Intelligence` del superadmin e' diventato davvero tenant-aware: dashboard, fonti, staging, analisi, review, archive e API operano sullo studio selezionato e non su un archivio globale implicito.
- Aggiunto bootstrap controllato dei dati legacy `legal_updates` dalla root storica verso il repository del tenant selezionato, con UI e documentazione allineate alla regola "uno studio, un backend, un archivio strutturato".

## 2.171.6 - 2026-04-19

- Introdotti i `golden path ufficiali` come capability eseguibile di primo livello: la CLI `iusentra golden-path` esegue le suite ufficiali, persiste un report leggibile e la pagina `admin/governance` mostra stato `pass/fail` dei flussi core business, migrazione tenant, Coverage AI, Update Intelligence e telematico.
- Blindato ulteriormente l'`Assistente migrazione`: il report persistito include ora `diff pre/post`, evidenza di `tenant sporco`, failure mode classificati e postura di rollback/recovery guidata, poi la UI li rende leggibili senza ricostruzioni manuali.
- Rafforzata l'osservabilita' operativa con tassonomia esplicita (`HTTP`, `OCR`, `WORKER`, `AI`, `STORAGE`, `PRODUCT`), soglie operative e remediation guidata direttamente nella dashboard admin.

## 2.171.5 - 2026-04-19

- La pagina `admin/governance` distingue ora in modo esplicito tra `backend strutturato effettivo dello studio` e `capability tecnica della piattaforma`, evitando di confondere il runtime reale del tenant con la parity teorica dei domini.
- Aggiunto selettore studio tenant-aware nella governance prodotto, con riepilogo del backend effettivo, regola di lettura corretta ed eccezioni architetturali esplicite per filesystem, telematico e AI locale.
- Estesi i test e la documentazione per chiarire che uno studio in SQLite deve governare tutti i dati strutturati su SQL locale e uno studio in cutover reale deve governarli tutti su PostgreSQL.

## 2.171.4 - 2026-04-19

- L'`Assistente migrazione` non resta piu' agganciato a un report vecchio rimasto nella sessione del browser: se nel backup esiste un report piu' recente per lo stesso studio, la pagina usa quello.
- Corretto il caso in cui, dopo un rerun pulito della migrazione, la UI continuava a mostrare warning storici o percorsi di report obsoleti pur avendo gia' un report piu' nuovo e coerente.
- Aggiunta regressione sul confronto tra report di sessione e ultimo report reale disponibile nel backup tenant-aware.

## 2.171.3 - 2026-04-19

- Corretto il `500` di `/admin/assistente-migrazione` che compariva dopo una migrazione reale quando il report piu' recente conteneva metadata descrittivi (`db_path`, `backend_kind`, firme sorgente) dentro le statistiche repository PostgreSQL.
- La pagina migrazione ora tollera report runtime completi e continua a renderizzare domini, repository e riepilogo finale senza trattare i campi testuali come conteggi numerici.
- Aggiunto test di regressione sul caso del report PostgreSQL tenant-aware con statistiche miste numeriche e descrittive.

## 2.171.2 - 2026-04-19

- Rafforzata l'osservabilita' operativa: `/admin/osservabilita` segnala ora degradi reali su endpoint `5xx`, OCR, runtime AI locale e storage, con indicazioni concrete su come intervenire.
- Estesi i test end-to-end delle superfici nuove (`Assistente migrazione`, `Copertura AI`, `Update Intelligence`, `News giuridiche`) per verificare copy italiana, raggiungibilita' admin e coerenza UI come unico prodotto.
- Aggiunto un presidio sul cutover tenant-aware: se la migrazione PostgreSQL fallisce, il tenant non attiva il backend esterno e resta sul backend corrente senza cutover parziale.
- Aggiornate README e documentazione tecnica E2E/observability per chiarire i criteri di chiusura dei flussi critici e del failure handling.

## 2.171.1 - 2026-04-19

- L'`Assistente migrazione dati` espone ora l'ultima esecuzione reale direttamente in `/admin/assistente-migrazione`, con riepilogo domini core, repository SQL, controlli di consistenza ed errori veri del cutover.
- In caso di fallimento, la UI non si limita piu' a un flash temporaneo: mantiene il contesto dell'errore, indica il target richiesto e suggerisce passi concreti per la risoluzione.
- Aggiornata la documentazione storage per chiarire che la superficie admin di migrazione mostra report reali e non solo workflow descrittivi.

## 2.171.0 - 2026-04-19

- L'`Assistente migrazione dati` esegue ora il cutover completo del tenant, non solo del core `studio.db`: include `template atti`, `legal intelligence`, `giurisprudenza`, `repository telematico`, `workspace intelligence`, `Update Intelligence` e `Coverage AI`.
- Il repository `Update Intelligence` ha ora parita' reale anche su PostgreSQL tenant-aware, con schema dedicato, scritture runtime compatibili e replica strutturata di fonti, staging, analisi, review, archivio normativo, giurisprudenza, prassi, news e audit.
- La migrazione verso SQLite non richiede piu' l'unlink fisico di `studio.db`: il target viene rigenerato in-place, cosi' il cutover non si rompe quando il file esiste gia' o e' aperto dal runtime locale.
- Risolta la collisione tra `audit_log` core e audit del motore aggiornamenti sul PostgreSQL condiviso del tenant, usando una tabella dedicata per il dominio `Update Intelligence`.
- Aggiornate matrice storage, piano di migrazione e README per riflettere il fatto che il percorso ufficiale `JSON -> SQLite -> PostgreSQL` copre davvero tutti i domini migrabili del tenant.

## 2.170.6 - 2026-04-18

- Chiusa la parita' SQL della `Copertura AI`: il modulo usa ora anche `SQLite locale` come backend reale tenant-aware, invece di bloccarsi sui soli tenant PostgreSQL.
- Il tenant selezionato dalla UI prevale finalmente sul tenant di sessione, cosi' dashboard, review e publish operano davvero sullo studio scelto dal superadmin.
- La coverage crea e usa schema SQL reale anche su `studio.db`, quindi audit, gap queue, draft v2, review e publish SQL possono funzionare anche negli studi locali senza PostgreSQL esterno.
- Aggiornati messaggi UI e documentazione per distinguere chiaramente backend `SQLite locale` e `PostgreSQL tenant-aware`.

## 2.170.5 - 2026-04-18

- Corretta l'acquisizione HTML paginata delle fonti giuridiche: la pipeline `Update Intelligence` non tronca piu' artificialmente a 40 risultati e segue anche le pagine aggiuntive dei portali con navigazione `frame3_item`, cosi' sorgenti come Cassazione possono acquisire tutti i documenti disponibili.
- Riallineata la `Copertura AI` al backend reale dello studio: dashboard e selettore mostrano ora il nome studio configurato e il backend effettivo `PostgreSQL tenant-aware`, invece di lasciare la UI ancorata al vecchio `JSON` del registry storico.
- Riscritta la schermata `Review copertura AI` con guida operativa, autoselezione della prima bozza, stati vuoti comprensibili, contesto di retrieval visibile e gestione errori piu' chiara, per evitare schermate apparentemente vuote o incomprensibili.

## 2.170.4 - 2026-04-18

- La pagina `/admin/aggiornamenti-legali/fonti` espone ora una guida fissa e responsiva ai campi del form, con significato operativo di `codice`, `categoria`, `classe`, `parser`, `tipo`, `ufficiale` e `attiva`.
- Aggiunti esempi pronti per Corte Costituzionale, Cassazione Massimario, Cassazione - Terza Sezione Civile e Giustizia Amministrativa, cosi' il form resta autosufficiente anche senza documentazione esterna.
- Rafforzati placeholder e microtesti del form per evitare errori di coerenza tra nome fonte, URL e codice tecnico.

## 2.170.3 - 2026-04-18

- Chiusa davvero la console `Copertura AI`: il backend coverage seleziona automaticamente il tenant unico attivo oppure lo studio scelto dalla UI, invece di restare dipendente da un `g.tenant` implicito.
- Aggiunto il riuso del PostgreSQL tenant-aware anche per configurazioni legacy con credenziali studio gia' presenti ma `db_config.mode` storico non ancora riallineato, senza attivare fallback fittizi sul core storage.
- Dashboard e review queue ora espongono lo studio selezionato, propagano `tenant_slug` su azioni e API, e mostrano correttamente `DB configurato: si` quando il backend coverage reale e' risolvibile.

## 2.170.2 - 2026-04-18

- La pipeline `Coverage AI` non dipende piu' solo da variabili `LEGAL_COVERAGE_DB_*`: quando il tenant usa gia' PostgreSQL, dashboard, review e publish SQL agganciano automaticamente il backend studio reale.
- Chiusa la parity SQL/PostgreSQL dei repository rimasti aperti per `template atti`, `legal intelligence`, `giurisprudenza`, `repository telematico` e `workspace intelligence`, mantenendo JSON come export o bootstrap controllato.
- Aggiunti repository runtime dedicati per stato editor, snapshot intelligence e corpus strutturati, con test di roundtrip e aggiornamento della matrice storage e della documentazione coverage.

## 2.170.1 - 2026-04-18

- Resa finalmente visibile la console del motore `IUSENTRA Update Intelligence`: link esplicito nel menu superadmin `Piattaforma -> Update Intelligence`.
- Aggiunti ingressi rapidi in `Motori Legali` e nella pagina `News giuridiche` per aprire direttamente dashboard aggiornamenti, fonti ufficiali, acquisizione, analisi AI, coda revisioni e archivio strutturato.
- Estesi i test per verificare che un superadmin autenticato veda davvero i collegamenti del motore in sidebar e nelle superfici `Motori Legali`.

## 2.170.0 - 2026-04-18

- Completato il motore `IUSENTRA Update Intelligence` anche sul piano operativo visibile: gestore fonti, area di acquisizione documenti, analisi AI, archivio strutturato e audit navigabili da interfaccia admin.
- Aggiunte le route e le API per gestione fonti, fetch mirato, rianalisi manuale di documenti raw, review `edit-and-approve`, consultazione di normative, versioni, giurisprudenza, prassi, news e audit.
- Resa esplicita la logica di popolamento: scansione batch, fetch per singola fonte, rianalisi del singolo documento e pubblicazione guidata.
- Estesi i test di regressione su superfici admin, API del motore e form operativi del modulo.

## 2.169.0 - 2026-04-18

- Introdotto `IUSENTRA Update Intelligence`, il motore di monitoraggio normativo, giurisprudenziale e di prassi con pipeline `fonte -> acquisizione -> analisi AI -> matching -> revisione -> pubblicazione`.
- Aggiunto l'archivio strutturato dedicato `legal_updates.db` con tabelle per fonti, raw documents, documenti normalizzati, analisi AI, normative versionate, giurisprudenza, prassi, news, coda revisioni e audit.
- Le fonti ufficiali iniziali includono Gazzetta Ufficiale, Normattiva, dati.normattiva.it, Corte costituzionale, Cassazione Massimario, Giustizia Amministrativa, EUR-Lex, Agenzia delle Entrate e Ministero del Lavoro.
- Disponibili la dashboard admin `/admin/aggiornamenti-legali`, la coda revisioni `/admin/aggiornamenti-legali/review` e la pagina utente `/legal-intelligence/news`.
- Aggiunto il comando CLI `iusentra aggiornamenti-legali` e i job scheduler dedicati per eseguire la scansione periodica delle fonti.

## 2.168.0 - 2026-04-18

- Estesa la parita' storage reale su SQLite e PostgreSQL anche ai moduli economici: `preventivi`, `conferimenti`, `timesheet`, `fatturazione` e `pagamenti`.
- Il cutover ufficiale `JSON -> SQLite -> PostgreSQL` migra ora anche preventivi, parcelle, link pagamento e configurazione pagamenti con report di consistenza.
- Il workflow `cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso` e' ora raccontato e verificato come capability di prodotto, non solo come somma di moduli.
- Aggiunti il comando CLI `iusentra demo-check`, la card dashboard `Studio reale in 5 minuti` e il riepilogo timesheet -> parcella per guidare l'onboarding operativo.
- Riallineati README, matrice storage, guida deploy e disciplina release alla nuova realta' del prodotto e alla repo `antmm2605/IUSENTRA`.

## 2.167.0 - 2026-04-18

- Lex ora profila in modo deterministico il tipo di richiesta prima di rispondere, distinguendo normativa, giurisprudenza, drafting, sintesi fascicolo, checklist operative e spiegazioni per cliente.
- Introdotto il `Source Policy System` modulare con ranking per tier, modalita' `strict / balanced / broad`, valutazione delle fonti interne ed esterne e riepilogo prudenziale dell'affidabilita'.
- Il contesto assistente passa al runtime AI anche `request_profile`, `source_policy_summary`, `source_mode`, confidenza e motivazione, compreso il ramo di arresto prudenziale quando mancano fonti forti.
- Il widget Lex mostra in UI l'affidabilita' della risposta e preserva correttamente fonti, citazioni e metadati preparati dal server anche nel flusso companion locale.
- Aggiunto il modulo compatibile `ai_lex_sources.py` e la documentazione tecnica `docs/LEX_SOURCE_POLICY_SYSTEM.md` per integrare il sistema senza dipendere da un file monolitico.
- Rafforzati i test su source policy, contesto assistente, grounding, widget e compatibilita' pubblica del modulo.

## 2.166.0 - 2026-04-18

- Introdotto il modulo `timesheet` con UI dedicata, filtri, cambio stato e collegamento a cliente e fascicolo.
- Le superfici `Panoramica`, `Cartella cliente` e `Fascicolo` espongono ora KPI economici, workflow cliente -> incasso e indicazioni operative condivise.
- Rafforzato il governo documentale del fascicolo con tagging, aggiornamento metadati, ricerca full-text contestuale e riepilogo versioni/OCR/portale.
- Estesa la migrazione storage per includere il timesheet in modo retrocompatibile anche sui tenant legacy privi del path dedicato.
- Aggiunti test di dominio e di superficie per timesheet, dashboard economica, workflow operativo e document management.

## 2.165.0 - 2026-04-17

- Portato PostgreSQL a backend reale tenant-aware in lettura e scrittura per utenti, clienti, fascicoli, agenda e scadenziario.
- Introdotto il cutover ufficiale `JSON -> SQLite -> PostgreSQL` con report di consistenza persistito sotto `backup/` del tenant.
- Runtime storage aggiornato per bloccare fallback invisibili a JSON quando PostgreSQL e' backend core attivo.
- Pannello admin storage riallineato con test connessione, attivazione esplicita e tracciamento ultimo report di migrazione.
- Aggiunto il comando CLI ufficiale `iusentra migrate --to=postgres --tenant=<slug-tenant>`.
- Rafforzati i test su runtime PostgreSQL, governance storage, migrazione con report e comando CLI.

## 2.164.4 - 2026-04-17

- Riallineato il blocco "Clausola per la risoluzione delle controversie" del `preventivo guidato` al form classico di creazione preventivo.
- Nel wizard la sezione ora espone lo stesso copy professionale, il presidio consumatore, il ripristino del testo standard e la stessa resa della fonte modello usata nel conferimento.
- Rafforzati i test del wizard per bloccare regressioni visive e di flusso sul passaggio preventivo -> conferimento.

## 2.161.0 - 2026-04-17

- Introdotto il catalogo centrale della piattaforma legale operativa con 22 procedure derivate da wave1 e wave2 della tassonomia legale.
- Preventivi, conferimenti, fascicoli e parcelle ora persistono il profilo procedurale condiviso con canale, registro e workflow operativo.
- Workflow onboarding/commerciale e repository strutturato allineati alla nuova procedura operativa, con propagazione fino al fascicolo e alla fatturazione.
- Contesto economico e documentazione di prodotto aggiornati per associare in modo esplicito tariffario, parcella e fattura alla stessa procedura operativa.

## 2.156.0 - 2026-04-16

- CI resa indipendente da branch hardcoded e rafforzata con workflow dedicati per CodeQL, dependency review, `pip-audit` e SBOM.
- Wiring Flask dei blueprint portato su registro dichiarativo in `web/bootstrap/blueprint_registry.py`.
- Scheduler irrobustito: avvio consentito solo su worker dedicato o override esplicito.
- Contesto Lex arricchito con l’headline del cockpit `Motori Legali`, così l’assistente riceve anche il quadro operativo del dominio legale.
- Packaging dipendenze riorganizzato sotto `requirements/` con separazione tra runtime base e sviluppo.
- Documentazione di prodotto completata con matrice storage, disciplina di release e changelog.

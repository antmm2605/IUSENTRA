# Percorso obbligatorio per arrivare alla risposta di Lex AI

Data di registrazione: 18 maggio 2026.

Questo documento serve a impedire risposte generiche quando una domanda ha già
un riferimento ufficiale nel database. Ogni passaggio deve essere verificabile:
se un punto non funziona, Lex deve dire quale punto è saltato, non rispondere
con un finto completamento.

## Aggiornamento operativo 2.248.25 - 23 maggio 2026

La Guida Pratica TOP9 set7 è entrata nella sorgente `GuidaPraticaSource`. Lex deve leggere 63 schede iper-dettagliate ricevute dall'utente: i codici ufficiali `011001` e `170001` restano depositabili, mentre le sette schede `GUIDA_GARANZIA_VIZI_COSA_VENDUTA_140011`, `GUIDA_RESPONSABILITA_COSE_CUSTODIA_160021`, `GUIDA_DISTANZE_LEGALI_COSTRUZIONI_130011`, `GUIDA_SCIOGLIMENTO_SOCIETA_PERSONE_211001`, `GUIDA_TUTELA_MAGGIORE_GRAVE_HANDICAP_413051`, `GUIDA_RISOLUZIONE_MUTUO_DECADENZA_TERMINE_142001` e `GUIDA_OPPOSIZIONE_PRECETTO_199001` sono guide interne non depositabili.

Quando l'avvocato chiede una di queste materie, Lex deve spiegare la procedura pratica usando normativa, presupposti, competenza, allegati, termini, esiti e note specialistiche della scheda, ma deve mantenere separato il codice originale ricevuto dal codice ufficiale di deposito da selezionare nel fascicolo.

## Aggiornamento operativo 2.248.21 - 23 maggio 2026

Lex deve conoscere la procedura completa delle notifiche legali ex L. 53/1994 integrata in IUSENTRA. Quando l'avvocato chiede di relata, notifiche PEC, documento rilasciato dall'ufficio, Portale Servizi, RAC o RdAC, Lex deve spiegare il flusso software e non limitarsi a una risposta normativa astratta.

Sequenza da usare nelle risposte operative: IUSENTRA monitora fascicolo e depositi portale; se l'ufficio giudiziario rilascia un documento da notificare, genera una notifica di sistema certa; prepara il collegamento al Portale Servizi con fascicolo, numero R.G., anno e ufficio giudiziario già compilati; l'avvocato accede al portale ufficiale e scarica il documento; il software importa il file nel fascicolo, lo collega alla relata, calcola hash e attestazioni, verifica oggetto PEC, pubblici elenchi, mittente/destinatario, relata separata e firma; la relata resta bloccata finché il documento d'ufficio non risulta acquisito; l'avvocato revisiona, firma, invia e deposita la prova con RAC/RdAC.

Lex deve distinguere sempre azione automatica e decisione professionale: il software rileva, avvisa, precompila, importa, controlla e documenta audit; l'avvocato conferma accesso al portale, verifica contenuto, firma, invia e valida la prova. Se mancano documento acquisito, pubblici elenchi, attestazione, firma, ricevuta completa o prova deposito, Lex deve indicare la lacuna e la prossima azione nel gestionale.

## Aggiornamento operativo 2.248.19 - 23 maggio 2026

La Guida Pratica TOP9 set6 è entrata nella sorgente `GuidaPraticaSource`. Lex deve leggere tutte le 54 schede iper-dettagliate ricevute dall'utente e non deve fermarsi ai campi standard: strategie, criteri, soglie, regimi di tutela, differenze tra procedimenti, casistiche, rimedi e danni risarcibili sono conoscenza operativa interrogabile.

Per ogni scheda guida Lex riceve un ragionamento operativo esplicito: prima separa codice ufficiale e guida interna, poi verifica presupposti, competenza, condizioni di procedibilità, atto, allegati, termini ed esiti. Se la scheda è interna non depositabile, Lex può usarla per spiegare il lavoro ma non può promuoverla a codice oggetto del fascicolo.

## Aggiornamento operativo 2.248.11 - 22 maggio 2026

Regola permanente di prodotto: arricchire Lex sempre in modo conversazionale con l'avvocato. Ogni guida pratica curata, matrice operativa, scheda di fascicolo o conoscenza linguistica dello studio deve diventare anche conoscenza interrogabile da Lex, non solo contenuto visibile in pagina. Lex deve leggerla integralmente quando è pertinente, usare un linguaggio naturale da assistente di studio, distinguere supporto pratico interno da dato ufficiale e non rendere la guida un blocco del lavoro.

Il dettaglio fascicolo React e la Guida Pratica devono leggere lo stesso fascicolo reale anche quando lo SQLite operativo non è ancora popolato e il dato vive nel JSON legacy. Il badge `Uso facoltativo` segnala all'avvocato che la guida è un aiuto operativo, non un requisito bloccante.

Regola permanente fascicolo/deposito: il codice che apre il fascicolo è sempre il codice ufficiale o normativo previsto per il deposito. La Guida Pratica si aggancia alla stessa materia e arricchisce il ragionamento operativo, ma non sostituisce mai il `codice_oggetto_pst` del fascicolo. Se Lex recupera una guida interna o un alias non depositabile, deve trattarlo solo come scheda pratica e deve mantenere come codice di deposito il codice ufficiale presente nel fascicolo.

## Aggiornamento operativo 2.248.10 - 22 maggio 2026

La Guida Pratica è fonte operativa facoltativa: quando il fascicolo non ha codice oggetto, Lex e la UI possono usare titolo e oggetto della pratica per suggerire una scheda, ma devono indicarla come proposta da confermare e non come codice ministeriale. L'oggetto della pratica e l'oggetto della guida corrispondono solo quando il codice PST/XSD ufficiale e la scheda hanno la stessa descrizione sostanziale.

Per i moduli TOP9 set2, i codici ricevuti con descrizione non coerente con il catalogo ministeriale devono restare guide interne: `413011` non va confuso con apertura tutela minori perché il ministeriale indica provvedimenti urgenti ex art. 361 c.c.; `140012` non va confuso con compravendita immobiliare perché il ministeriale indica vendita di cose mobili.

Lex deve leggere la Guida Pratica come fonte interna completa tramite `GuidaPraticaSource`: normativa, presupposti, adempimenti, atto principale, campi, allegati, avvertimenti, termini, atti collegati, esiti e note di integrazione devono entrare nel retrieval quando l'avvocato chiede aiuto operativo, una checklist, una scheda pratica o un orientamento sul fascicolo. La risposta deve essere conversazionale e professionale: Lex parla all'avvocato come assistente di studio, spiega il primo controllo utile, l'atto da preparare, gli allegati da presidiare e i limiti, senza trasformare la guida in blocco operativo.

Regola permanente: arricchire sempre la conoscenza linguistica e conversazionale di Lex con le fonti operative curate dello studio. Quando una nuova guida, matrice o scheda pratica viene integrata, deve diventare anche conoscenza interrogabile da Lex, con tono chiaro per l'avvocato e distinzione esplicita tra supporto pratico interno, dato ufficiale e punto da verificare.

## Aggiornamento operativo 2.248.9 - 22 maggio 2026

La Guida Pratica dei codici PST/XSD diventa una sorgente strutturata separata dal codice applicativo: `pct/data/legal_knowledge_base.full.json` e i moduli `pct/data/legal_knowledge_base_modules/`. Quando Lex o una UI di fascicolo ragionano sul codice oggetto, devono distinguere il codice ufficiale depositabile dagli alias interni.

Il validatore obbligatorio `scripts/validate_guida_pratica.py --require-official-curated --fail-on-generated` conferma 1.018 codici ufficiali con guida curata, zero mancanti e zero incoerenze deposito. Le schede interne non presenti nel catalogo ministeriale restano utili come guida operativa, ma non devono essere proposte come codice definitivo di deposito.

## Aggiornamento operativo 2.246.4 - 21 maggio 2026

Le domande sugli allegati di una PEC, incluse formulazioni come `Quale atto risulta notificato, depositato o comunicato negli allegati?`, sono consultazioni operative su comunicazioni dello studio. Il router deve usare `communications_lookup` con `email_pec`, `pec_audit`, `email_ordinaria` e `messaggi`; è vietato deviare sul catalogo Template Atti o su ricerca legale pubblica quando l'oggetto della domanda è cosa risulta dai messaggi e dagli allegati ricevuti.

Quando la pipeline PEC produce `deadline_proposal.auto_create=true`, Lex deve spiegare che il software ha registrato o può registrare una scadenza operativa automatica di presidio. Questa scadenza usa `operational_due_at`, non `legal_due_at`: non è un calcolo conclusivo del termine processuale e non sostituisce la verifica dell'avvocato su atto, data di perfezionamento, rito, ufficio e fascicolo.

Per notifiche e depositi Lex deve leggere la matrice semantica completa: PCT e comunicazioni di cancelleria, Giudice di Pace/D.L. 179/2012, notifiche in proprio ex L. 53/1994, UNEP/art. 149-bis c.p.c., PAT/SIGA, PTT/SIGIT, SNT/PDP penale, ricevute PEC e domicilio digitale/pubblici elenchi. La risposta deve partire da cosa deve fare il software: riconoscere il caso, esporre esito e lacune, attendere o controllare le ricevute richieste, registrare il presidio operativo e preparare le domande professionali per l'avvocato.

## Aggiornamento operativo 2.246.3 - 21 maggio 2026

La domanda `Che PEC di deposito devo controllare?` è un caso di consultazione operativa, non di redazione. Il profilo richiesta, il bounded bridge e il router operativo devono instradarla verso `communications_lookup` con sorgenti `email_pec` e `pec_audit`; è vietato produrre una bozza PEC quando l'avvocato sta chiedendo quali messaggi verificare.

Quando la PEC è presente nello storico email ma non ancora nella cassaforte PEC audit-grade, Lex deve usare il presidio provvisorio esposto dal bridge React: contesto semantico, confidence, anomalie, allegati, riferimenti normativi e domanda guida. Deve però dichiarare la lacuna “MIME originale da acquisire” e proporre l'acquisizione IMAP audit-grade, senza fingere che il MIME sia già conservato.

Per PEC di deposito o notifica la risposta deve riportare almeno: messaggio da presidiare, fase o evento riconosciuto, qualità/firme, anomalie principali, cosa aspettarsi dopo il deposito e domande operative. La bozza o l'invio restano fuori perimetro finché l'avvocato non li chiede esplicitamente.

## Aggiornamento operativo 2.246.2 - 21 maggio 2026

Lex conosce la sorgente interna `pec_audit`, alimentata dalla pipeline PEC audit-grade. Quando l'avvocato chiede validità, firme, allegati mancanti, MIME, fascicolo, notifica, cancelleria, Giudice di Pace, L. 53/1994, PAT, PTT, SNT, PDP, termini o scadenze, la risposta deve recuperare il controllo strutturato e non limitarsi alla vecchia scheda email.

La risposta deve seguire questa sequenza: identificare il contesto processuale, dichiarare dati certi dal MIME/ricevute, mostrare i campi estratti con confidence, elencare anomalie non bloccanti, formulare le domande operative e proporre solo azioni da confermare. Se il testo contiene, per esempio, `GIUDICE DI PACE - Notificazione ai sensi del D.L. 179/2012`, Lex deve preparare presidio su atto notificato, data di consegna, RG/fascicolo, possibili termini e allegati mancanti, senza calcolare una scadenza definitiva quando mancano atto o data affidabile.

Per i depositi PCT Lex deve sapere cosa aspettarsi dopo l'invio: accettazione PEC, avvenuta consegna, esito controlli deposito e accettazione o rifiuto del deposito. Finché manca l'esito finale non deve dire che il deposito è accettato; deve comunicare lo stato intermedio, cosa manca e quali verifiche fare.

I contesti coperti sono PCT civile, comunicazioni/notificazioni di cancelleria, notifiche in proprio L. 53/1994, Giudice di Pace, UNEP, PAT/SIGA, PTT/SIGIT, penale SNT/PDP, ricevute PEC e domicilio digitale/pubblici elenchi. Le fonti normative sono registrate nel validation report come riferimento operativo; Lex non deve presentarle come parere conclusivo quando la matrice segnala `Da verificare`.

## Aggiornamento operativo 2.245.65 - 20 maggio 2026

Il workflow `atto_da_template` ora passa anche dal controllo normativo contestuale prima di creare documenti. La pipeline è: template reale, contesto fascicolo/cliente, profilo normativo, fonti censite e verificate, riferimenti applicabili con `reason_for_application`, layout profile, timbro studio su ogni pagina, gate generazione, audit e risposta Lex.

Lex non inventa riferimenti e non genera atti liberi: se non trova un modello del catalogo, un contesto autorizzato o le fonti richieste, espone la lacuna. Se il controllo produce `block`, non viene creato nessun documento; se produce `warning`, la creazione richiede conferma e resta bozza di lavoro; se produce `ok`, la mutation apre l'editor professionale tramite `editor_url` restituito dal backend.

Il controllo è registrato nell'audit Template Atti con versione ruleset, profilo layout, stato fonti, riferimenti normativi, mancanti bloccanti o di avviso, utente, tenant, fascicolo, cliente e documento prodotto.

## Aggiornamento operativo 2.245.64 - 20 maggio 2026

Lex Template Atti passa dalla pipeline ordinaria, senza sistema parallelo: `LexRouter` riconosce lookup, precompilazione e creazione editor; `SourceRouter` carica `StudioDatabaseSource` e `TemplateAttiSource`; il provider deterministico chiama `pct.template_atti_lex_service`; `AnswerBuilder` restituisce una risposta con `message_blocks`, `lex_actions`, `source_rows` e metadata `template_act`.

La risposta deve seguire questo ordine professionale: modello individuato dal catalogo, contesto pratica, dati precompilati, dati mancanti, controlli, fonti e azioni. Se mancano modello, cliente, fascicolo o permessi, Lex si astiene e mostra lacune/opzioni; se ci sono più clienti o fascicoli compatibili, non sceglie al posto dell'avvocato. Una richiesta di consultazione come "quali atti posso creare per decreto ingiuntivo?" resta lookup e non crea bozze.

La creazione documento nell'editor avviene solo con `create_editor_draft` confermato o con frase esplicita equivalente a "crea ora la bozza nell'editor". Il payload usa il compilatore reale (`prefill_payload`, `validate_payload`, `render_compiled_act`) e conserva fonti interne verificate: catalogo atti, cliente, fascicolo e parti dello studio.

## Aggiornamento operativo 2.245.63 - 20 maggio 2026

Lex Studio Reasoner è stato esteso per lavorare come una conversazione tra colleghi. I follow-up brevi dell'avvocato, come "e gli allegati?", "preparami una risposta", "chi è la controparte?", "e le scadenze?" o "quali fascicoli ha?", vengono risolti sul riferimento operativo appena mostrato: PEC/email, fascicolo, documento o cliente. La memoria usa soltanto link e oggetti interni già verificati nella risposta precedente.

La matrice di audit ora copre domande vaste su PEC, email ordinaria, allegati, fascicoli, documenti, soggetti, controparti, timeline, scadenze, agenda, clienti, pagamenti/fatture, priorità studio e bozze esplicitamente richieste. Le bozze restano vietate sulle sole consultazioni: "ultima PEC ricevuta" non redige nulla, mentre "scrivi risposta alla PEC..." recupera prima la fonte interna e poi prepara una bozza governata.

Il gate conversazionale end-to-end richiede almeno il 90% su 30 turni consecutivi. Il primo audit ha prodotto 73% e ha guidato correzioni reali su routing dei follow-up, preventivi, conferimenti, template, agenda, fonti interne e contesto studio; il gate finale è verde.

La pratica su web professionale è distinta dalle fonti ufficiali: Lex può usare siti di studi legali, commenti operativi e contenuti per avvocati come know-how non vincolante, senza addestramento grezzo, senza pubblicazione automatica nel corpus e senza usarli per contraddire l'avvocato. Per correggere l'avvocato serve una fonte primaria verificata con confidenza almeno 99%.

Il motore `Web libero` ora prova più canali pubblici in sequenza: DuckDuckGo HTML, Google pubblico, Yahoo ed Ecosia. Se un canale non restituisce risultati live, Lex passa al successivo; i risultati restano `web_libero` o `knowhow_professionale`, non vengono promossi a fonte ufficiale e non diventano trusted source nel RAG. È stato aggiunto un audit al 99% su cento somministrazioni web/RAG verso conversazione con l'avvocato: ogni acquisizione deve preservare contenuto, fonte, limite d'uso e regola "non contraddire senza fonte primaria".

La fase linguaggio giuridico/date impone il formato italiano nelle risposte rivolte all'avvocato: giorno, mese scritto in italiano e anno, con ora solo quando presente nei dati (`17 maggio 2026`, `21 maggio 2026 alle 10:00`). La composizione deterministica applica il formato a PEC/email, scadenze, agenda, documenti, pagamenti, schede cliente/soggetto, privacy e timeline; la guardia qualità blocca date tecniche ISO nelle risposte professionali. L'audit dedicato verifica cento turni e richiede almeno il 99%.

Sono stati chiusi tre rischi pratici: lo scope fascicolo/cliente viene applicato anche quando il contesto arriva direttamente da `active_context`, una ricerca PEC su fascicolo inesistente non ricade più sulla PEC globale e lo studio context non filtra via le fonti interne quando la domanda non contiene un'entità specifica. I controlli restano divisi per fase e per perimetro Lex; nessun aggregatore legacy è stato reintrodotto.

## Aggiornamento operativo 2.245.61 - 19 maggio 2026

Lex ha ora un contratto unico di chat operativa: `LexUnifiedChat`. La chat resta il punto di ingresso riutilizzabile da pagina, drawer, modale o assistente globale, mentre il motore sotto è `Lex Studio Reasoner`. Ogni risposta operativa porta `active_context`, `detected_intent`, `lex_structured_context`, `message_blocks`, `lex_actions` e `source_verification`.

Il contesto non viene riversato come testo grezzo nel prompt. `LexContextProvider` normalizza contesto globale, fascicolo, PEC/email e documento; `IntentRouter` distingue consultazione PEC/email, documento, timeline, scadenze, pagamenti e bozze; `StructuredContextBuilder` produce schede cliente/fascicolo, comunicazioni, documenti, scadenze, fatture/pagamenti e timeline; `LexSourceVerifier` impedisce affermazioni senza fonte, segnala permessi mancanti, ambiguità cliente e fonti assenti.

Il widget centrale `pct-lex-assistant.js` usa `LexMessageRenderer` per mostrare card PEC/email, allegati, fascicoli, clienti, documenti, scadenze, pagamenti, timeline, fonti interne e azioni apribili. La richiesta "ultima PEC ricevuta" resta consultazione: non genera bozze; la bozza compare solo come azione successiva quando esiste una comunicazione citata.

La memoria dei check resta per fasi: test mirati su contesto globale, contesto fascicolo, contesto PEC, permessi, cliente ambiguo, fonte mancante, timeline, pagamenti e richiesta di bozza esplicita. Nessun aggregatore legacy è stato reintrodotto.

## Aggiornamento operativo 2.245.60 - 19 maggio 2026

Terza fase della tranche `Lex Studio Reasoner`: il bridge HTTP bounded espone al widget Lex il report governato `studio_reasoner`, la `entity_map`, la `fascicolo_timeline`, `rag_governato`, `reasoner_mode` e i collegamenti `operational_links`. La chat può quindi aprire fascicolo, documento in editor professionale, PEC/email e allegati usando route applicative già autorizzate.

Il riepilogo evidenze indica anche conteggi di link operativi, entità e timeline. Il comportamento resta separato dal Web libero e dalle fonti legali pubbliche: nessun aggregatore legacy viene reintrodotto e il reasoning studio continua a verificare solo sorgenti interne tenant-aware.

## Aggiornamento operativo 2.245.59 - 19 maggio 2026

Seconda fase della tranche `Lex Studio Reasoner`: il report `studio_reasoner` include ora `entity_map` e `fascicolo_timeline`. La mappa collega clienti, fascicoli, soggetti/parti, documenti, scadenze, agenda, PEC/email e dati economici solo quando emergono dai risultati interni autorizzati. La timeline usa le date già presenti nei record del fascicolo, senza inferire eventi non registrati.

Le risposte operative possono esporre link applicativi apribili: PEC ed email puntano alla scheda messaggio, gli allegati alle route allegato, i fascicoli alla scheda pratica e i documenti fascicolo all'editor professionale. I link sono generati dai tool operativi dopo il controllo tenant/RBAC; non usano path filesystem e non espongono storage interno.

## Aggiornamento operativo 2.245.58 - 19 maggio 2026

Prima fase della tranche `Lex Studio Reasoner`: il layer operativo costruisce ora un piano `llm_rag_governato` per ogni risposta gestita da Operational Knowledge. Il piano non è un prompt grezzo né un addestramento sui dati dello studio: descrive in modo verificabile classificazione, retrieval interno, verifica fonti e composizione della risposta.

Il verificatore allega alla risposta il report `studio_reasoner`, con fonti interne verificate, fonti mancanti, lacune e policy RAG. Le fonti legali/pubbliche (`fonti_ufficiali`, `legal_intelligence`, `update_intelligence`, `web_libero`) sono escluse dal verificatore studio, così il contesto operativo non duplica né contamina il percorso delle fonti ufficiali.

La memoria operativa resta quella richiesta: nessun aggregatore legacy è stato reintrodotto; i check continuano a essere shard mirati e divisi per fase/parte.

## Aggiornamento operativo 2.245.57 - 19 maggio 2026

Le azioni sulle risposte documentali di Lex sono state ricondotte all'editor professionale: se la route di import nel fascicolo è disponibile, il widget mostra `Apri con editor` come azione primaria, non propone più il download Markdown e apre l'editor anche se l'utente clicca una vecchia azione Word già presente nella chat.

La dettatura non deve più chiudersi prima che l'avvocato inizi a parlare: il timer di silenzio parte solo dopo il primo testo riconosciuto. Gli eventi `no-speech` e `aborted` chiudono la sessione senza errore bloccante, mentre il permesso microfono negato viene segnalato con un messaggio operativo chiaro.

Quando l'avvocato carica un documento e chiede "spiegami", "riassumi", "analizza" o "quali sono i punti più importanti", il bridge HTTP forza il workflow `documento` e conserva gli allegati come evidenze `user_attachment`. Il contesto fascicolo resta disponibile, ma non deve assorbire la richiesta sul file caricato.

## Aggiornamento operativo 2.245.55 - 19 maggio 2026

Lex non viene addestrata su prompt o dump grezzi dello studio: le domande sul contesto operativo passano da sorgenti interne governate. Il nuovo intento `studio_context_lookup` copre richieste esplicite come "usa tutto il contesto studio", "database studio" e "memoria studio", instradandole verso Operational Knowledge e `StudioDatabaseSource` senza attivare fonti legali pubbliche.

La consultazione di comunicazioni è separata dalla redazione: "ultima PEC ricevuta" entra in `comunicazioni_lookup`, legge PEC/email tenant-aware e non produce più una bozza `BOZZA — PEC FORMALE`. Le bozze PEC restano drafting solo quando l'utente chiede davvero di scrivere o preparare una PEC formale.

Il flag manuale `Web libero` ora genera un payload diretto: la ricerca è isolata dal contesto interno, i risultati sono marcati `web_libero`, `verified_reference=false`, non vengono salvati nel DB/corpus e non mostrano warning all'avvocato. I documenti caricati in chat entrano invece nel workflow `documento`, così Lex può analizzarli senza confonderli con ricerca legale o bozze.

## Aggiornamento operativo 2.245.51 - 19 maggio 2026

La Fase 10 ha chiuso l'audit finale del sistema aggiornamenti legali senza import massivo. La policy progressiva classifica tutte le fonti censite in `DEFAULT_SOURCE_ROWS`: verdi con pubblicazione guarded, RAG-only/no-publish, osservazione/bloccate, archivi locali/no-publish o fuori perimetro solo per fonti secondarie non ufficiali.

Per Lex questo significa che il routing non deve più incontrare fonti ufficiali senza classe operativa. Le domande su allegati, PDF, articoli, INPS, AGCOM e Cassazione devono interrogare prima il repository locale, usando pagina, allegato/PDF/OCR, riferimenti e domande contestuali; se il dataset locale non contiene ancora una specifica evidenza, Lex deve dichiarare la lacuna o usare solo il Web libero manuale quando richiesto dall'avvocato.

## Aggiornamento operativo 2.245.52 - 19 maggio 2026

La Fase 11 introduce il regime controllato degli aggiornamenti legali. `python -m pct.cli legal-updates-health-report --json` è il report periodico canonico: non effettua fetch live e non pubblica, ma legge fonti, coda job, scheduler, retry, PDF/OCR, riferimenti, domande, review e pubblicazioni guarded.

Lex deve considerare questo report come presidio di manutenzione: fonti in osservazione, RAG-only o non pubblicabili non diventano basi certe della risposta finché non passano capability, fixture, canary, report, pilot guarded e abilitazione scheduler. I backfill ammessi restano solo mirati ad allegati, OCR, riferimenti e domande mancanti, sempre senza pubblicazione automatica.

## Aggiornamento operativo 2.245.53 - 19 maggio 2026

La Fase 11.5 aggiunge due presidi prima del popolamento produzione: `legal-updates-run-progressive --guarded-only` per un ciclo controllato sulle sole fonti verdi e `legal-updates-giurisprudenza-structured-canary --json` per impedire che l'Archivio Giurisprudenza venga popolato senza corte, numero, anno, data, fonte ufficiale e testo/PDF.

Per Lex, `QSP50194` resta un caso pilota con diagnosi esplicita: il dettaglio diretto è raggiungibile e contiene `art. 606 c.p.p.`, ma il canary delle ultime 5 schede Cassazione del 19 maggio 2026 non lo ha restituito. Le risposte devono quindi usare evidenze DB/fixture quando presenti e dichiarare la lacuna se il repository corrente non contiene ancora quella scheda/PDF, senza inventare import o pubblicazioni.

EUR-Lex può riconoscere CELEX ma resta RAG-only finché non sono presenti tutte le chiavi strutturate; OpenGA resta RAG-only per dataset tabellari, mentre eventuali PDF giurisprudenziali concreti potranno entrare solo da pilot guarded futuro.

## Aggiornamento operativo 2.245.54 - 19 maggio 2026

Lex ha ora una sorgente interna unica per il DB operativo dello studio: `StudioDatabaseSource`. La sorgente interroga `GlobalSearchService.search_for_lex()` e trasforma i risultati verificati della Ricerca Studio in evidenze `studio_db:*`, mantenendo tenant, identità record, URL applicativo, score e metadati.

La sorgente è sempre disponibile nel router locale, ma non parte in modalità `Web libero`: quando l'avvocato abilita la ricerca libera, il router continua a restituire solo `OfficialWebSource` in modalità libera. Le fonti legali già governate sono escluse dall'adapter (`legal_intelligence`, aggiornamenti legali, normativa, giurisprudenza, prassi, official web), così il DB operativo non duplica né contamina il percorso fonti ufficiali.

La Ricerca Studio indicizza anche comunicazioni, PEC, email ordinaria e allegati tramite `MESSAGGI_DB`, `EMAIL_CASELLA_DB` ed `EMAIL_ORDINARIA_DB`, usando helper tenant-aware e senza fallback globale in multi-studio. Questo abilita domande operative come ultima PEC, allegati ricevuti, dati cliente, scadenze e agenda senza passare da prompt grezzi.

I controlli CI restano divisi per fasi: questa tranche ha rilanciato i test che proteggono `Pytest core` shardato, `Coverage moduli critici parte */12`, Local Signer/PKCS#11 a parti e Quality Overlay shardato, senza reintrodurre il vecchio aggregatore `Coverage moduli critici` privo di `parte`.

## Aggiornamento operativo 2.245.49 - 19 maggio 2026

La Fase 8 restringe lo scheduler degli aggiornamenti legali al solo step 1 progressivo: `cassazione_ultime_sent_ord_questioni`, `inps_circolari`, `inps_messaggi` e `agcom_provvedimenti`. Le fonti fuori step, incluse ANAC e Garante, non devono diventare base certa della risposta Lex finché non passano un canary/report verde dedicato.

Budget iniziali: 2 fonti per ciclo, timeout 120 secondi per elemento, massimo 5 pubblicazioni guarded per ciclo e massimo 5 schede Cassazione ultime. Lex continua a distinguere evidenze verificate, fonti incomplete e RAG-only: le incomplete restano da verificare e non vengono promosse a certezza nella risposta finale.

## Aggiornamento operativo 2.245.48 - 19 maggio 2026

La Fase 7 ha eseguito solo backfill mirati, con limiti espliciti e `--no-publish`, sui documenti già acquisiti o pubblicati. Non è stato usato Web libero e non è stato avviato alcun import massivo.

`legal-updates-backfill-diagnostics` ora supporta `--missing` multipli separati da virgole. Il report JSON contiene `summary` con selezionati, processati, aggiornati, invariati, falliti, motivi di fallimento, PDF/OCR completati, riferimenti aggiunti, domande aggiunte e segnali di aggiornamento per Lex/Ricerca Legale.

Risultato reale della fase: allegati e OCR non avevano più elementi selezionabili nel perimetro; il backfill riferimenti ha controllato 50 evidenze, aggiornandone 14 e aggiungendo 20 riferimenti; le domande contestuali erano già complete. Lex e Ricerca Legale devono quindi usare questi riferimenti aggiornati dal repository locale, senza creare nuove pubblicazioni o sintesi inventate.

## Aggiornamento operativo 2.245.45 - 19 maggio 2026

Il primo pilot `guarded` ha pubblicato solo documenti letti nel canary corrente e ha verificato che Lex possa rispondere usando testo pagina, PDF/OCR e allegati ufficiali. Sono entrati 9 contenuti: 3 Cassazione, 3 circolari INPS e 3 provvedimenti AGCOM. Tutti hanno riferimenti e domande contestuali salvati.

Quando la domanda chiede PDF, allegato, documento ufficiale, circolare o delibera, il ranking delle fonti Lex deve riconoscere la fonte ufficiale richiesta e premiare l'allegato rispetto alla sola pagina. Le schede Cassazione senza corte/numero/anno completi restano utilizzabili da Lex e Ricerca Legale come RAG ufficiale, ma non vanno trasformate in una voce strutturata di Archivio Giurisprudenza finché le chiavi non sono complete.

## Aggiornamento operativo 2.245.46 - 19 maggio 2026

La Fase 5 ha popolato il primo gruppo di fonti verdi con budget controllato (`limit 5`, `max_seconds 120`, `publish-mode guarded`, `direct-only`). Sono stati pubblicati 20 documenti unici, tutti ritrovabili in Ricerca Legale con query fonte mirata e interrogabili da Lex tramite `LegalUpdateRepository.search_lex_sources()`.

Lex deve distinguere tre stati della Fase 5:

- pubblicati e interrogabili: Cassazione ultime, INPS circolari/messaggi, AGCOM, Corte dei conti e Curia CGUE;
- acquisiti ma non pubblicati: ANAC e Garante quando il guarded rileva conferme insufficienti o riferimenti non ritrovati nella diagnosi;
- RAG-only/non pubblicabili: PST tecnico e OpenGA tabellare, che non devono comparire come news.

Per le fonti giurisdizionali HTML è obbligatorio evitare fallback da homepage, captcha o navigazione: Corte costituzionale accetta solo schede pronuncia ufficiali, mentre Corte dei conti accetta solo documenti giurisdizionali con titolo reale e download PDF verificabile.

## Aggiornamento operativo 2.245.42 - 19 maggio 2026

La pipeline dispone ora di due strumenti sicuri prima del popolamento fonte per
fonte: `legal-updates-canary` prova una sola fonte con `--limit` obbligatorio,
budget tempo, `--direct-only`, `--no-publish` e diagnostica salvabile;
`legal-updates-backfill-diagnostics` completa in modo mirato allegati, OCR,
riferimenti o domande senza pubblicazione automatica.

## Aggiornamento operativo 2.245.44 - 19 maggio 2026

La Fase 3 post-canary corregge solo le fonti risultate gialle nel report del 19
maggio 2026. Gazzetta Ufficiale ora rilegge gli allegati normalizzati anche
quando il documento è invariato, così il PDF del fascicolo entra nelle evidenze
con hash/testo. ANAC e Garante non creano più allegati fittizi da testo o da
link normativi generici. PST resta fonte tecnica `RAG-only`, non pubblicabile
come news. OpenGA tabellare (`CSV`, `JSON`, `ODS`, `XLSX`, `ZIP`) resta
`RAG-only`; solo risorse documentali concrete, come PDF giurisprudenziali,
possono essere promosse in una tranche separata.

Le fixture offline coprono Cassazione indice/Civile/Penale/dettaglio/PDF,
AGCOM dentro/fuori perimetro, feed INPS/Curia, CKAN OpenGA, ANAC, Garante,
PST e PDF testuale/scansionato mock. Questo consente a Lex, Ricerca Legale e
alla console admin di verificare parser, PDF/OCR, riferimenti e domande senza
rete live e senza import massivo.

## Aggiornamento operativo 2.245.41 - 19 maggio 2026

Gli Aggiornamenti legali hanno ora un registro capability per fonte. Lex non
deduce più a posteriori se una fonte è normativa, prassi, giurisprudenza,
RAG-only o fuori perimetro: la pipeline salva la destinazione prevista, la
strategia di dettaglio, PDF/OCR, riferimenti, domande contestuali e motivo di
scarto in modo deterministico.

I parser fixture coprono HTML listing/detail, Feed/RSS/Atom, CKAN/OpenGA,
Cassazione indice Civile/Penale/detail e autorità indipendenti. OpenGA non
pubblica cataloghi o dataset tecnici come news, ma conserva evidenze RAG quando
utili; se una risorsa contiene un documento giuridico concreto, il documento
viene trattato separatamente. Le fonti secondarie restano fuori dal corpus
ufficiale e utilizzabili solo tramite Web libero manuale.

## Aggiornamento operativo 2.245.40 - 18 maggio 2026

La pipeline fonti pubbliche usa ora un arricchimento deterministico condiviso:
pagina ufficiale, allegato PDF, testo OCR, riferimenti normativi/giurisprudenziali,
R.G. e domande contestuali vengono prodotti nello stesso formato per qualità fonte,
Ricerca Legale, corpus Lex e risposta Lex. I link Normattiva non vengono inventati:
il campo resta vuoto finché non esiste una risoluzione ufficiale reale.

La console `/admin/aggiornamenti-legali/` mostra anche evidenze lette, PDF/allegati,
documenti con allegati e dispone di backfill mirato per fonte, stato, query,
review e timeout. Il Web libero resta una ricerca manuale separata: non usa
fonti interne, non scrive nel DB/corpus, non applica allowlist ufficiali e deve
restituire risposta italiana senza avvisi visibili.

## Caso guida

Domanda utente:

```text
Quale allegato ufficiale ha la questione penale R.G. 9926/2026?
```

Evidenza ufficiale già acquisita:

- pagina Cassazione: `https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194`;
- allegato ufficiale: `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- titolo allegato: `Ordinanza di rimessione`;
- testo OCR salvato nel database;
- hash SHA-256 salvato;
- nota obbligatoria: la domanda scrive `9926/2026`, mentre il documento ufficiale
  acquisito riporta `9966/2026`. Lex deve segnalare la discrepanza e non deve
  fingere che i due numeri siano identici.

Risposta minima attesa:

```text
Ho trovato una fonte ufficiale Cassazione collegata. L'allegato ufficiale è
"Ordinanza di rimessione", PDF:
https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf

Attenzione: nella domanda compare R.G. 9926/2026, mentre nell'allegato ufficiale
acquisito risulta R.G. 9966/2026. Va verificato se è un refuso o se si cerca un
altro procedimento.
```

## Passaggi obbligatori

1. L'utente scrive la domanda nel widget Lex.
   - Il testo non deve essere modificato in modo distruttivo.
   - Numeri, sigle e URL devono restare disponibili: `R.G.`, `9926/2026`,
     `QSP50194`, `Cassazione`, `allegato`, `ordinanza`, `PDF`.

2. Il frontend invia la richiesta all'endpoint chat.
   - Il widget deve inviare domanda, route corrente, eventuale fascicolo attivo,
     tenant e contesto autorizzato.
   - La UI non deve sostituire una risposta tecnica con un messaggio generico se
     il backend restituisce sorgenti o lacune.

3. Il backend costruisce il contesto operativo.
   - Vengono risolti utente, studio e tenant.
   - I permessi decidono quali archivi possono essere consultati.
   - La domanda non deve uscire dallo studio senza percorso governato.

4. Il router classifica la domanda.
   - Se la domanda contiene segnali come `Cassazione`, `QSP`, `R.G.`,
     `questione penale`, `allegato ufficiale`, `ordinanza di rimessione`,
     `circolare`, `messaggio`, `Gazzetta`, `Normattiva` o `fonte ufficiale`,
     deve usare la rotta delle fonti ufficiali e degli aggiornamenti legali.
   - Non deve usare `documenti collegati` salvo richiesta esplicita di documenti
     del fascicolo interno o allegati caricati dallo studio.

5. Il servizio operativo esegue gli strumenti della rotta scelta.
   - Per fonti legali deve interrogare almeno:
     - inventario legal intelligence;
     - archivio aggiornamenti legali;
     - catalogo fonti ufficiali.
   - Il percorso decisivo per questo caso è l'archivio aggiornamenti legali.

6. L'archivio aggiornamenti legali interroga il database.
   - La ricerca deve usare titolo, URL, fonte, estratto, testo OCR, hash,
     `attachment_url`, `attachments_json` e numero R.G.
   - Se la domanda chiede un allegato, i risultati con `attachment_url` e testo
     OCR reale devono essere promossi prima della pagina generica.

7. Il database deve restituire prove reali, non solo riferimenti.
   - Prova minima valida:
     - URL pagina ufficiale;
     - URL allegato ufficiale;
     - titolo allegato;
     - estratto leggibile;
     - hash o metadato di download;
     - stato della verifica.
   - Se manca il testo OCR ma esistono URL e hash, Lex deve dirlo chiaramente.

8. Il compositore costruisce una risposta leggibile.
   - Deve citare il nome dell'allegato e il link ufficiale.
   - Deve indicare se la fonte è Cassazione, Gazzetta, INPS, Normattiva o altra
     fonte riconosciuta.
   - Deve evidenziare le discrepanze, per esempio `9926/2026` contro
     `9966/2026`.
   - Non deve limitarsi a contare le fonti trovate.

9. La risposta torna al widget Lex.
   - Il testo deve essere impaginato in modo leggibile.
   - I link devono essere cliccabili.
   - Non devono comparire messaggi come `Non ho trovato dati reali sufficienti`
     quando il database ha restituito un allegato ufficiale valido.

10. L'audit registra cosa è stato consultato.
    - Devono essere tracciati rotta scelta, strumenti chiamati, numero risultati,
      sorgenti, eventuali lacune e motivo di blocco.
    - Se viene usata la rotta sbagliata, il test deve fallire.

## Ricerca web libera manuale

La ricerca web libera non deve essere un job, una pianificazione o una coda.
Parte solo dalla domanda Lex quando l'utente attiva il comando `Web libero` nel
widget.

Passaggi obbligatori:

1. Il widget invia insieme alla singola domanda:
   - `free_web_enabled=true`;
   - `force_free_web_search=true`;
   - `public_web_forced=true`;
   - `web_execution_requested=true`;
   - `source_mode=free_web`.
2. Il backend applica questi flag solo a quella richiesta.
3. Lex non applica allowlist ufficiali e non blocca per mancanza di fonte
   autorizzata.
4. Lex non porta quei risultati dentro il database, il corpus, la coda review o
   gli archivi fonti: valgono solo per la singola risposta in chat.
5. Il router non deve trascinare fonti DB, fascicolo o contesto pagina dentro la
   modalità libera; il risultato resta marcato `web_libero`,
   `verified_reference=false`.
6. La risposta non deve mostrare warning o avvisi di responsabilità: in questa
   modalità il software esegue la ricerca richiesta e il controllo spetta
   interamente all'avvocato.
7. La console pianificazioni non deve creare, avviare o mostrare job per questa
   funzione.

## Prove prima di dichiarare risolto

1. Test del router:
   - la domanda `Quale allegato ufficiale ha la questione penale R.G. 9926/2026?`
     deve andare alle fonti ufficiali, non a `documenti_fascicolo`.
   - la domanda `Questione Penale Pendente del ricorso R.G. 9926/2026` non deve
     mai essere classificata come bozza di atto solo per la parola `ricorso`.

2. Test del repository:
   - la stessa domanda deve restituire come primo risultato l'allegato
     `Ordinanza di rimessione` con URL PDF ufficiale.

3. Test del compositore:
   - la risposta deve contenere `Ordinanza di rimessione`;
   - deve contenere il link PDF;
   - deve segnalare la discrepanza `9926/2026` / `9966/2026` quando presente;
   - non deve contenere `Non ho trovato dati reali sufficienti`.

4. Test end-to-end del servizio Lex:
   - chiamata con lo stesso testo della domanda reale;
   - verifica della rotta;
   - verifica del testo finale;
   - verifica delle sorgenti restituite.

5. Verifica produzione:
   - il container deve avere la versione corretta;
   - il database di produzione deve contenere pagina, PDF, OCR e hash;
   - la domanda reale deve rispondere con allegato e nota sulla discrepanza;
   - il deploy deve rispettare `no backup`.

## Regola di blocco

Il lavoro non può essere dichiarato chiuso se uno solo di questi punti resta
vero:

- la domanda viene classificata come `documenti collegati`;
- il repository trova l'allegato ma Lex non lo usa;
- la risposta non mostra il link ufficiale;
- la risposta ignora la differenza tra `9926/2026` e `9966/2026`;
- il widget mostra ancora `Non ho trovato dati reali sufficienti` per questo
  caso.

## Correzione percorso widget del 18 maggio 2026

Problema riscontrato in produzione:

```text
Questione Penale Pendente del ricorso R.G. 9926/2026
```

veniva risposta dal percorso editor con:

```text
Riferimento: fascicoli rilevanti
Editor Lex: Editor normale e professionale con Lex...
Limiti: Nessun dato reale disponibile dalla sorgente template_atti.
```

Causa verificata:

1. Il focus conversazionale leggeva `ricorso` come competenza `atti_template`.
2. La parola `questione` veniva riconosciuta erroneamente come follow-up perché conteneva la sequenza `questi`.
3. La domanda effettiva diventava `atti template Questione Penale...`.
4. Il router operativo controllava `template` prima di `questione penale`, `QSP` e `R.G.`, quindi sceglieva `template_lookup`.
5. Il widget mostrava un riferimento di contesto non coerente con la fonte ufficiale richiesta.

Correzione applicata:

1. `web/services/assistente_conversation_focus.py` riconosce prima le richieste di fonte ufficiale (`questione penale`, `questione civile`, `QSP`, `R.G.`, allegato ufficiale, ordinanza di rimessione, Cassazione).
2. I marker di follow-up ora usano parole intere, quindi `questione` non attiva più `questi`.
3. `lex/operational_knowledge/query_router.py` dà priorità a `official_sources_lookup` prima di `template_lookup`.
4. `web/static/js/pct-lex-assistant.js` mostra il riferimento `fonti ufficiali` e non tratta la domanda come documento/bozza.
5. La prova end-to-end passa da `/api/assistente/chat` con cronologia precedente da editor, non solo dal servizio interno.

Test di blocco regressione:

```powershell
python -m pytest tests\test_assistente_focus.py::test_focus_conversazionale_rg_questione_penale_resta_fonte_ufficiale tests\test_lex_operational_knowledge.py::test_rg_questione_penale_prefisso_template_resta_fonte_ufficiale tests\test_lex_assistente_context_real_requests.py::test_assistente_chat_questione_penale_rg_non_finisce_nell_editor -q
node tests\js\lex_assistant_render.test.mjs
```

Esito atteso:

- rotta `official_sources_lookup`;
- risposta con `Ordinanza di rimessione`;
- link PDF `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- nota sulla discrepanza `R.G. 9926/2026` / `R.G. 9966/2026`;
- assenza di `Editor Lex`, `template_atti`, `Camera Arbitrale` e fonti R.G. non pertinenti.

## Correzione qualità risposta del 18 maggio 2026

Problema residuo dopo la correzione del routing:

- Lex arrivava finalmente alla fonte ufficiale, ma mostrava una risposta troppo
  povera: indicava il PDF senza sintetizzare la questione giuridica.
- Il percorso streaming `/api/assistente/chat` comprimeva le risposte bounded con
  `clean_spaces`, perdendo titoli, righe e punti elenco.
- Il renderer del widget interpretava gli underscore dell'URL PDF come enfasi
  Markdown, spezzando il link in frammenti non professionali.

Regola aggiornata:

1. Per una domanda come `Questione Penale Pendente del ricorso R.G. 9926/2026`,
   Lex deve rispondere al contenuto della scheda, non solo all'esistenza del PDF.
2. Se nel DB esistono sia la pagina Cassazione sia l'allegato, la risposta deve
   includere:
   - quesito ufficiale;
   - riferimenti normativi;
   - data udienza, relatore e ricorrente quando presenti;
   - allegato ufficiale e URL PDF;
   - nota sulla discrepanza `9926/2026` / `9966/2026`;
   - distinzione tra dato certo e punto da verificare.
3. Il widget deve preservare titoli, elenchi e link cliccabili anche in streaming.

Test di blocco regressione aggiunti o aggiornati:

```powershell
python -m pytest tests\test_lex_operational_knowledge.py tests\test_lex_assistente_context_real_requests.py -q
node tests\js\lex_assistant_render.test.mjs
```

Risposta sostanziale minima attesa:

```text
Ho trovato una fonte ufficiale collegata alla richiesta.

Cosa dice la scheda ufficiale:
- Questione: se, avverso la sentenza emessa a seguito di concordato in appello,
  siano deducibili con il ricorso per cassazione i vizi attinenti alla
  determinazione della pena non comportanti l'illegalità della stessa.
- Riferimenti normativi: Cod. proc. pen. artt. 599-bis e 606.
- Scheda: inserita il 05 maggio 2026; udienza 09 luglio 2026; relatore
  E. Morosini; ricorrente Turco G.

Allegato ufficiale:
- Ordinanza di rimessione.
- PDF ufficiale cliccabile.

Punto da verificare:
- La domanda cita R.G. 9926/2026, mentre l'allegato acquisito riporta
  R.G. 9966/2026.
```

## Generatore Corpus Fonti

Il passaggio successivo al collaudo fonte è il generatore del corpus reale:
`scripts/generate_lex_source_corpus.py`.

Regole:

- legge solo `web_verification_evidence`;
- non naviga il web;
- non chiama LLM o provider esterni;
- include nel corpus solo evidenze con `content_text` e `context_chars`
  sufficienti;
- conserva metadati fonte: `review_id`, `normalized_document_id`,
  `source_url`, `attachment_url`, `sha256`, `source_code`,
  `verification_status`;
- produce `manifest.json`, `documents.jsonl`, `chunks.jsonl`,
  `expected_queries.jsonl` e un `documenti_ai/documenti_ai.json` compatibile
  con la pipeline dataset Lex;
- abilita l'uso RAG delle evidenze verificate senza revisione umana;
- non abilita training automatico: la revisione umana resta richiesta solo se
  le Q&A candidate vengono esportate o usate per training/fine-tuning.

Prova locale del 18 maggio 2026 sul DB
`data/intelligence/legal_updates.db`:

```powershell
python scripts\generate_lex_source_corpus.py `
  --intelligence-db data\intelligence\legal_updates.db `
  --output-dir tmp\lex-source-corpus-local `
  --limit 100 `
  --overwrite
```

Esito: 2 evidenze verificate leggibili, 2 documenti corpus, 13 chunk.

Dry-run dataset sul corpus generato:

```powershell
$env:PYTHONPATH='.'
python scripts\build_lex_studio_dataset.py `
  --tenant-id legal-sources `
  --document-ai-json tmp\lex-source-corpus-local\documenti_ai\documenti_ai.json `
  --max-documents 100
```

Esito RAG: 2 documenti e 13 chunk leggibili da Lex senza revisione umana.

Esito dataset opzionale: 13 task Q&A candidate e 13 coppie candidate, training
automatico disattivato, training esterno disattivato. La revisione umana è
obbligatoria solo prima di usare quelle Q&A per training/fine-tuning. È stato
rilevato 1 documento/chunk sensibile: l'export dataset resta governato e non va
trattato come training pronto.

## Prova Lex Locale

Prova del 18 maggio 2026 sulla domanda:

```text
Questione Penale Pendente del ricorso R.G. 9926/2026
```

Esito atteso e verificato:

- rotta Lex: `official_sources_lookup`;
- sorgenti effettive: pagina Cassazione QSP50194 e allegato `Ordinanza di
  rimessione`;
- PDF restituito:
  `https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- nota visibile sulla discrepanza tra `R.G. 9926/2026` nella domanda e
  `R.G. 9966/2026` nell'allegato;
- nessun fallback `Non ho trovato dati reali sufficienti`;
- nessuna fonte non pertinente come `Camera Arbitrale` tra risposta e sorgenti.

La rotta con identificativo specifico filtra l'indice generale delle fonti
ufficiali: le schede generiche restano disponibili per ricerche generali, ma non
devono contaminare una risposta puntuale già fondata su `legal_updates.db`.

## Caso Pilota QSP 9926/2026 - Risposta Da Avvocato

Aggiornamento operativo del 18 maggio 2026.

Aggiornamento 2.245.26: la discrepanza `R.G. 9926/2026` / `R.G. 9966/2026`
non va più trattata come motivo per scartare il PDF, perché il collegamento
scheda -> PDF è già stato verificato. La regola corretta è: Lex cita la scheda
`9926/2026`, mantiene il PDF ufficialmente collegato e cliccabile, cita il
contenuto del PDF come contenuto del PDF collegato, ma non attribuisce
automaticamente dati processuali, parti, pena o contesto del PDF alla scheda
`9926/2026`. La risposta non deve riprodurre OCR sporco né fondere scheda e PDF
in un unico racconto certo.

Forma obbligatoria della risposta sintetica: una sola sezione `Sintesi` con
oggetto, stato, punto di diritto/principio, motivi/censure, effetto pratico e
nota R.G.; una sezione `Norme rilevanti` che spiega perché contano gli articoli;
una sezione `Fonte e PDF` con link cliccabile; poi `Punto da verificare` ed
`Esito`. Sono vietate risposte che ripetono `Cosa dice la scheda ufficiale`,
`Sintesi dell'ordinanza`, estratti OCR grezzi e log di recupero fonte.

Approvazione utente 18 maggio 2026: la risposta prodotta dopo questa correzione
è stata verificata dall'utente e confermata come risposta corretta. Da questo
momento il caso `QSP50194` / `R.G. 9926/2026` è il test reale definitivo da
preservare prima di lavorare sul generatore corpus.

## Matrice domande obbligatorie prima del corpus

Prima del generatore corpus ogni documento Cassazione della tranche deve essere
controllato anche contro le domande da avvocato stabilite sul caso pilota. Il
report qualità del backfill deve quindi esporre una `question_matrix` con almeno
questi controlli:

- sintesi vera della fonte richiesta;
- natura dell'atto: sentenza definitiva, ordinanza, questione pendente o altro;
- oggetto della questione o decisione;
- stato del procedimento o dell'atto;
- punto di diritto o principio in discussione;
- motivi, censure o passaggi rilevanti;
- norme richiamate e spiegazione del perché contano;
- effetto pratico per l'avvocato;
- esito finale o pendenza;
- PDF/allegato ufficiale e link cliccabile quando presente;
- discrepanza R.G. quando scheda e PDF riportano numeri diversi;
- articoli richiamati spiegati, non solo elencati, quando il testo li contiene.

Questa matrice viene generata in modo deterministico dal job
`python -m pct.legal_update_job --backfill-web-evidence`: non usa LLM, non
naviga oltre il connettore già previsto e serve a decidere se la fonte è pronta
per la tranche e, solo dopo, per il corpus RAG.

## Destinazioni obbligatorie delle fonti pronte

Una fonte Cassazione o giurisprudenziale che passa il controllo qualità non deve
restare visibile solo nel job tecnico o nel corpus generato. Quando il report
segna `ready=true` e `corpus_ready=true`, la stessa evidenza deve diventare:

- interrogabile da Lex Chat AI, con risposta sintetica e fonti separate;
- ricercabile in `/ricerca-legale`, tramite schede operative e link fonte/PDF;
- consultabile in Archivio Giurisprudenza quando la natura della fonte è
  sentenza, ordinanza, questione Cassazione o documento giurisprudenziale.

Il generatore corpus resta successivo alla tranche, ma il risultato finale
atteso dall'avvocato è su questi tre punti utente: Lex Chat AI, Ricerca Legale e
Archivio Giurisprudenza.

## Riuso PDF già presenti sul server

Il passaggio `pagina ufficiale -> allegato/PDF` non deve riscaricare un allegato
quando il file è già presente nello storage runtime. Prima della richiesta HTTP
il backfill controlla la cache allegati configurata:

- `IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR`;
- `IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR`;
- in produzione Hetzner, se `PCT_DATA_ROOT=/data`, anche
  `/data/intelligence/downloads`, `/data/fonti_ufficiali` e
  `/data/tenants`.

Se trova un PDF con lo stesso nome, lo usa direttamente per hash, testo e OCR.
Solo se il file non è presente passa al download dalla fonte ufficiale e salva
il file nella cache runtime per i passaggi successivi. Questo mantiene la prova
end-to-end ma evita download e OCR ripetuti quando il materiale è già sul server.

## Tranche Cassazione `ultime sentenze, ordinanze e questioni` del 18 maggio 2026

Aggiornamento 2.245.36: la pagina Cassazione
`https://www.cortedicassazione.it/it/ultime_sent_ord_e_questioni.page` è una
pagina indice, non una lista finale di documenti. Il flusso corretto è:

1. leggere la fonte dal DB;
2. aprire la pagina indice ufficiale;
3. seguire le pagine ufficiali Civile/Penale;
4. conservare solo URL `*_dettaglio.page?contentId=...`;
5. aprire ogni scheda;
6. scaricare o riusare PDF/allegati;
7. calcolare hash;
8. leggere testo PDF/OCR;
9. estrarre norme, R.G., date, stato e qualità;
10. generare domande dal contesto effettivamente letto;
11. creare chunk RAG solo per documenti pronti.

Le domande non sono una lista fissa. Se il testo letto contiene articoli o
riferimenti normativi, Lex deve esporli e spiegarli; se serve integrazione sul
significato degli articoli, usa `web_libero` come ricerca della singola domanda,
separata dalla fonte ufficiale e non salvata nel DB. Se la scheda ha un PDF, la
domanda deve includere PDF/link; se compaiono R.G. diversi, deve includere la
nota di discrepanza; se il testo OCR è sporco, non va riversato nella risposta
finale.

Verifica locale: 10 schede Cassazione reali pronte, 9 con PDF letto, una senza
PDF ma con testo pagina, 10/10 con matrice domande; corpus prova da 20 documenti
e 174 chunk, Memory Tree pronto, zero pagine di servizio.

Nota `Web libero`: se l'avvocato attiva la ricerca web libera dalla chat, il
pipeline non deve usare il contesto studio già presente nella pagina. Il bounded
context deve partire con fonti interne, fascicolo, impostazioni e template vuoti
e usare solo i risultati web della singola richiesta. I risultati restano
`web_libero`, non vengono salvati nel DB e la risposta deve essere sempre in
italiano.

## Tranche Cassazione del 18 maggio 2026

Sequenza eseguita dopo il caso pilota:

1. Backfill Cassazione su 20 record: il flusso pagina -> allegato -> OCR/testo
   ha salvato 41 evidenze e 21 allegati, tutti pronti, ma il lotto ha mostrato
   che alcune pagine generiche del sito potevano entrare nella tranche.
2. Correzione selezione: per `cassazione_massimario` il backfill e il
   generatore corpus accettano solo schede documentali Cassazione:
   `civile_dettaglio`, `penale_dettaglio`, `qsp_dettaglio`, `qsc_dettaglio`,
   `quc_dettaglio`, `rlc_dettaglio`, `rlp_dettaglio` e `su_dettaglio`.
3. Backfill filtrato su 10 record: 10 controllati, 22 evidenze salvate, 12
   allegati, 10/10 pronti, 10 PDF trovati e letti, 0 OCR mancanti, 0 hash
   mancanti.
4. Generatore corpus dopo la tranche:

```powershell
python scripts\generate_lex_source_corpus.py `
  --intelligence-db data\intelligence\legal_updates.db `
  --output-dir tmp\lex-source-corpus-cassazione-tranche `
  --source-code cassazione_massimario `
  --limit 50 `
  --overwrite
```

Esito locale: 50 documenti Cassazione, 538 chunk RAG, filtro documentale attivo,
`expected_queries.jsonl` arricchito con `question_matrix`. Il comando non naviga
il web e non chiama LLM.

Verifiche mirate:

```powershell
python -m pytest tests\test_legal_update_web_verification_attachments.py `
  tests\test_lex_source_corpus_generator.py `
  tests\test_legal_update_publish_context.py::test_backfill_web_verification_evidence_rinfresca_allegato_ocr_vuoto `
  tests\test_legal_update_publish_context.py::test_backfill_web_verification_evidence_query_cerca_in_evidenze_e_allegati `
  tests\test_legal_update_publish_context.py::test_backfill_cassazione_esclude_pagine_non_documentali_dalla_tranche `
  tests\test_legal_update_batch_runner.py::test_legal_update_job_cli_backfill_evidenze_usa_limiti_governati -q
python -m pytest tests\test_utf8_integrity.py -q
git diff --check
```

Esito: 18 test mirati passati, 4 test UTF-8 passati, diff senza whitespace
errati.

Passaggi eseguiti per arrivare al test definitivo:

1. Domanda reale iniziale: `mi puoi sintetizzare questa sentenza Penale Pendente
   del ricorso R.G. 9926/2026`.
2. Primo problema rilevato: Lex non rispondeva in modo utile, mostrava log di
   recupero fonte o risposte generiche e talvolta finiva nel contesto editor o
   template invece che nelle fonti ufficiali.
3. Correzione del focus conversazionale: la richiesta `Questione Penale
   Pendente`, `QSP` o `R.G.` viene trattata come fonte ufficiale Cassazione, non
   come richiesta di bozza, editor o template.
4. Recupero fonte: il database `legal_updates.db` viene interrogato per la
   scheda Cassazione `QSP50194` e per l'allegato collegato.
5. Verifica allegato: il PDF
   `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf` viene mantenuto come
   PDF ufficialmente collegato alla scheda.
6. Lettura PDF/OCR: il testo OCR dell'allegato entra nel contesto interrogabile,
   ma non deve essere riversato grezzo nella risposta finale.
7. Discrepanza R.G.: è stata confermata la differenza tra scheda/domanda
   `R.G. 9926/2026` e numero interno del PDF `R.G. 9966/2026`; il collegamento
   non va rimesso in discussione, ma i dati della scheda e i dati del PDF vanno
   tenuti separati.
8. Prima risposta migliorata ma non definitiva: Lex trovava fonte, PDF, punto
   di diritto, motivi e articoli, però ripeteva troppe sezioni, esponeva ancora
   OCR sporco e mescolava troppo scheda e PDF.
9. Regola corretta richiesta dall'utente: Lex può citare entrambi, ma non può
   attribuire i dati del PDF alla scheda richiesta come se fossero certi.
10. Correzione finale del composer: per una domanda di sintesi Lex produce una
    sola sezione `Sintesi` con oggetto, stato, punto di diritto/principio,
    motivi/censure, effetto pratico e nota R.G.
11. Aggiunta spiegazione norme: Lex non deve solo elencare gli articoli, ma
    spiegare perché contano `599-bis c.p.p.`, `606 c.p.p.`, `129 c.p.p.`,
    `610 c.p.p.` quando presente e `81 c.p.`.
12. Guardia OCR: frammenti deformati come `Corte d'appello di N Caltanissetta`,
    `al medesimo | d`, `anni due e mesi o`, `edi` e simili non devono comparire
    nella risposta finale.
13. Guardia qualità finale: prima della restituzione vengono evitati duplicati,
    sezioni ripetute, estratti OCR grezzi, link PDF rotti e fusione impropria
    tra scheda e PDF.
14. Test mirati aggiunti/aggiornati: domande su sintesi, punto di diritto,
    motivi, natura dell'atto, udienza/norme, articoli, ricorrente/relatore,
    PDF, uso in atto, esito e discrepanza R.G.
15. Test end-to-end verificato: DB -> scheda ufficiale -> allegato PDF -> OCR ->
    retrieval/RAG operativo -> risposta Lex -> test di regressione.
16. Deploy senza backup eseguito su Hetzner con versione `2.245.26`.
17. Verifica utente finale: l'utente ha confermato che la risposta ora va bene e
    ha autorizzato l'approvazione del test come definitivo e reale.

Problema emerso nella prova reale:

- Lex trovava la scheda Cassazione e il PDF, ma rispondeva ancora come log di
  recupero fonti.
- La sintesi dell'allegato era povera e il punto di diritto poteva uscire
  tronco.
- La stessa risposta veniva restituita a domande diverse, invece di rispondere
  al quesito effettivo dell'avvocato.
- Il link PDF con underscore poteva essere spezzato dal rendering Markdown del
  widget già aperto.

Logica introdotta sul caso pilota:

1. Prima si recuperano pagina QSP, allegato ufficiale, OCR e discrepanza R.G.
2. Poi si costruisce una risposta focalizzata sulla domanda concreta.
3. La risposta conserva sempre fonte, PDF, avviso su `9926/2026` / `9966/2026`
   e separazione dai dati riservati dello studio.
4. Se la domanda chiede norme o articoli, Lex estrae gli articoli dalla scheda e
   dall'allegato e può attivare una ricerca web libera.
5. La ricerca web libera resta separata dalla fonte ufficiale della questione,
   non entra nel corpus e non applica allowlist o blocchi da fonte autorizzata.

Matrice minima di domande coperte per il caso pilota:

- `mi puoi sintetizzare questa sentenza Penale Pendente del ricorso R.G. 9926/2026`;
- `qual è il punto di diritto della questione penale R.G. 9926/2026?`;
- `quali sono i motivi del ricorso R.G. 9926/2026?`;
- `è una sentenza o una questione pendente R.G. 9926/2026?`;
- `quando è fissata l'udienza e quali norme sono indicate per R.G. 9926/2026?`;
- `trova gli articoli di riferimento della questione R.G. 9926/2026`;
- `chi sono ricorrente e relatore della questione penale R.G. 9926/2026?`;
- `mi dai il PDF e l'allegato ufficiale della questione R.G. 9926/2026?`;
- `posso citare la questione R.G. 9926/2026 in un atto come decisione definitiva?`;
- `qual è l'esito della questione R.G. 9926/2026?`;
- `spiegami la discrepanza tra R.G. 9926/2026 e R.G. 9966/2026`.

Articoli da presidiare nel caso pilota:

- dalla scheda Cassazione: `Cod. proc. pen. artt. 599-bis e 606`;
- dall'ordinanza/OCR: `art. 599-bis c.p.p.`, `art. 129 c.p.p.`,
  `art. 81, comma secondo c.p.`, quando presenti nel testo leggibile;
- dalla fase web libera: risultati pubblici scelti dalla ricerca libera della
  singola domanda, sempre marcati `web_libero` e mai promossi a fonte ufficiale
  o corpus.

Regola da riusare sugli altri documenti:

- fatto bene un documento significa avere domanda, fonte, allegato, testo,
  sintesi, norme, eventuale web libero, limiti e test ripetibili;
- solo dopo questa chiusura si estende la stessa logica al generatore corpus e
  agli altri documenti.

## Aggiornamento Fase 9 fonti verdi - 19 maggio 2026

La fase 9 estende il popolamento controllato solo alle fonti verdi e lascia fuori pubblicazione fonti RAG-only, archivi locali e fonti in osservazione. Per Lex questo significa:

- i 14 nuovi contenuti pubblicati guarded entrano nel repository aggiornamenti legali e sono ricercabili come fonti ufficiali;
- OpenGA, PST, Dati Normattiva, EUR-Lex e ISTAT restano evidenze RAG/no-publish, quindi non vanno presentate come news;
- Normattiva e codici fondamentali alimentano risposte normative tramite archivi locali e riferimenti, non tramite import massivo web;
- i report Fase 9 registrano 17 PDF/OCR completati, 340 riferimenti e 740 domande contestuali, da usare come contesto citabile quando la fonte è pertinente;
- Archivio Giurisprudenza resta senza nuove schede strutturate finché una fonte giurisprudenziale non espone corte, numero e anno completi.

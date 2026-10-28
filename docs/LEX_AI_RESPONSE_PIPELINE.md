# Percorso obbligatorio per arrivare alla risposta di Lex AI

Data di registrazione: 18 maggio 2026.

Questo documento serve a impedire risposte generiche quando una domanda ha già
un riferimento ufficiale nel database. Ogni passaggio deve essere verificabile:
se un punto non funziona, Lex deve dire quale punto è saltato, non rispondere
con un finto completamento.

## Aggiornamento 2.435.0 - 2 ottobre 2026: prompt e chiamata al modello (RAG modulo 1)

Primo modulo del risanamento del RAG di Lex. Riguarda solo il modo in cui la
domanda arriva al modello locale; retrieval e guardie restano invariati.

- **Domande giuridiche senza dati dello studio.** Nei workflow `normativa`,
  `giurisprudenza`, `giurisprudenza_specifica`, `research_giurisprudenza`,
  `prassi`, `research`, `fonti` (`LEGAL_RAG_WORKFLOWS` in
  `lex/prompts/legal_rag_prompt.py`) il messaggio non contiene più il JSON
  dell'intero studio (prima ~400.000 caratteri con agenda, dati economici e
  codici fiscali). Nei workflow sui dati dello studio entra un estratto
  compatto (`compact_studio_context`): lettura del fascicolo, campi del
  fascicolo, sezioni pertinenti del `prompt_block` dello studio, senza PEC,
  impostazioni, policy, codici fiscali, partite IVA e IBAN; massimo
  `LEX_STUDIO_CONTEXT_MAX_CHARS` (6.000) e metà dello spazio residuo.
  In `chat`/`question_answering` i dati dello studio entrano solo se la domanda
  riguarda clienti, fascicoli, udienze, scadenze o pratiche.
- **Formato del messaggio utente (identico nel dataset di fine-tuning).**

  ```text
  Domanda:
  <domanda>

  Dati dello studio:          (solo workflow sui dati dello studio)
  <estratto>

  Fonti:
  [1] <Fonte> · <art./riferimento> · <URN o ECLI> · <vigenza> · <data gg/mm/aaaa>
  <testo, max 1.600 caratteri>
  ```

  Al massimo 12 fonti (`LEX_MAX_EVIDENCE_ITEMS`), la stessa lista che il
  retrieval seleziona e che la guardia anti-allucinazione controlla.
- **System prompt giuridico fisso** (`LEX_LEGAL_RAG_SYSTEM_PROMPT`): una sola
  stringa per tutti i workflow giuridici (cache del prefisso di Ollama): solo
  le fonti fornite, citazioni `[n]`, astensione esplicita («non determinabile
  con le fonti disponibili»), vigenza quando nota, regole sui riferimenti
  legali (`LEX_LEGAL_REFERENCE_RULES`, condivise con il prompt dell'assistente)
  e contratto qualità. Il workflow `normativa` (con `prassi`, `fonti`,
  `research`) è ora registrato in `WORKFLOW_REGISTRY` (`NormativaWorkflow`).
- **Budget di contesto in Python** (`lex/providers/prompt_budget.py`): stima
  token = caratteri / 3,5; budget = `num_ctx` − `num_predict` − 64. Se si
  sfora si tolgono le fonti meno rilevanti (in coda alla lista ordinata dal
  retrieval; l'ultima ammessa può essere accorciata), mai system prompt o
  domanda. Nei metadati della bozza: `prompt_budget` (token stimati, fonti
  incluse/escluse/troncate, mappa delle citazioni) e `prompt_eval`
  (`prompt_eval_count` di Ollama). Se `prompt_eval_count` è meno della metà
  dei token stimati del messaggio utente, log «possibile troncamento».
- **Parametri unici** (`lex.settings.lex_generation_settings()`):
  `LEX_NUM_CTX=8192`, `LEX_NUM_PREDICT=700`, `LEX_TEMPERATURE=0.2`,
  `LEX_LLM_TIMEOUT_S=300`, `LEX_THINK=false`, usati dal percorso governato e
  da quello in streaming (stesso `num_ctx`: niente ricaricamento del modello).
- **`think`**: campo top-level `think` dell'API `/api/chat` (`false` di
  default); se il modello lo rifiuta (HTTP 400) si ripete una volta senza.
  I blocchi `<think>…</think>` (anche non chiusi o senza apertura) sono rimossi
  sempre, anche in streaming.
- **Errore o timeout del modello**: la risposta dice all'avvocato che il
  modello locale non ha risposto (tempo scaduto, non raggiungibile, risposta
  vuota) prima del contenuto ricavato dai dati; mai un fallback silenzioso.

Misura con sonda (finto Ollama, studio del banco di prova): messaggio utente
delle domande giuridiche da 375.802–434.566 a 1.351–6.260 caratteri; domande
sui dati dello studio da ~390.000 a 3.097–9.592 caratteri.

Punti aperti (moduli successivi): le fonti selezionate per molte domande
giuridiche sono schede dei motori di ricerca e non testi di legge (qualità del
retrieval); la guardia anti-allucinazione controlla tutte le 12 fonti anche
quando il budget ne esclude alcune.

## Aggiornamento gate reali - 7 giugno 2026

Ogni risposta Lex collegata al lavoro del 7 giugno deve essere verificata sul
testo finale che legge l'avvocato. I gate minimi sono:

- Cartabia civile/correttivo: la domanda su riforma civile, rito, decorrenze,
  famiglia, esecuzione, notifiche e ADR deve citare D.Lgs. 149/2022, D.Lgs.
  164/2024, codice di procedura civile e uso operativo;
- fascicolo attivo: la sintesi deve riportare inquadramento, documenti chiave,
  rischi, documenti mancanti e prossimi passi, non solo estratti OCR;
- PEC prova completa: se accettazione e consegna sono nel database dello studio,
  Lex deve mostrarle con destinatario e orario italiano; il tenant va risolto
  sugli alias autorizzati più completi;
- Ricerca Legale: le fonti devono arrivare come riferimenti nominali
  consultabili e filtrabili, inclusi sentenze, decreti, udienze e fonti
  ufficiali pertinenti.

Il report verificabile è
`artifacts/legal-sources/legal-work-real-gates-2026-06-07.md`. Se uno di questi
gate torna a `0`, a fonte generica o a risposta non utile, la tranche è da
considerare non completata.

## Aggiornamento operativo 2.249.19 - 6 giugno 2026

Lex conosce la nuova sorgente interna `pec_control_tower`, alimentata da
`pct.pec_control_tower.PecControlTowerRepository`. Quando l'avvocato chiede
quali PEC generano scadenze, quali notifiche fare, quali invii non hanno ancora
consegna, quali termini sono da confermare, quali atti arrivano da cancelleria,
quali comunicazioni PA richiedono risposta, quali notifiche sono fallite, quale
prova è completa, chi ha confermato una scadenza o quale fascicolo rischia una
decadenza, il router deve usare `pec_control_tower` prima delle viste generiche
su email, scadenziario o notifiche.

La risposta deve partire da eventi giuridici PEC tracciati: fascicolo collegato,
documenti presenti, documenti da verificare, articoli/fonti da considerare,
scadenze in bozza, task, notifiche o riscontri e prove. Le scadenze restano
`da confermare` finché non vengono confermate dall'avvocato con regola e audit;
Lex non deve presentarle come termine legale definitivo.

Il test reale di generazione è
`python scripts/test_pec_control_tower.py --runtime-root <cartella>`: genera PEC
di cancelleria, PA, notifica, accettazione senza consegna, prova completa e
mancata consegna, alimenta il RAG operativo di Lex e interroga tutte le domande
obbligatorie fino a risposta corretta.

## Aggiornamento operativo 2.248.26 - 24 maggio 2026

La pipeline compatta `pct.pec_ocr_pipeline` emette `lex.ingest.doc` solo dopo WORM, antivirus, verifica firma, estrazione ZIP sicura, dedup SHA-256 e `ocr.result`. Lex deve trattare questi documenti come evidenze operative interne: citare `mail_id`, `doc_id`, checksum, `run_id`, confidenza OCR e candidato fascicolo/R.G. quando presente, senza trasformare il risultato OCR in parere legale conclusivo.

Se la pipeline produce `needs_attention`, `mail.member.blocked`, `mail.unzip.blocked`, antivirus positivo, firma non valida o OCR con errori, Lex deve esporre la lacuna e proporre riconciliazione o verifica dell'avvocato. I duplicati saltati per SHA-256 non sono nuovi documenti: Lex deve riusare la citazione del blob esistente e non inventare una seconda lettura.

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

## 07/10/2026 — EmbeddingGemma 2 locale, candidatura ancora aperta

Richiesta utente: sostituzione soltanto con elaborazione sul medesimo host.
Il candidato testuale float32 768D usa revisione pubblica fissata, prefissi
query/documento, servizio Docker isolato e indici separati dal precedente.
Non cambia OCR, chat, guardie legali o flussi dispositivo/firma/PEC.
Il retrieval RAG restituisce il segmento migliore per chunk e combina FTS
sull'identità originaria; testo completo, pagina e provenienza restano in SQL.
Cache numerica float32 derivata, ricostruibile da vettori già verificati senza
rileggere i documenti. Quantizzazione dei pesi respinta: 11/12 contro 12/12.
Migrazione straordinaria a lotti con backup e checkpoint su due copie locali:
626 e 790 chunk terminati, negativi motivati conservati. Non è una promozione
di tutte le fonti a prova: CID/binario e riferimenti a casi assenti restano
problemi espliciti. Servono qualità/provenienza, confronto sul volume reale,
indice Normattiva, UI reale e rilascio coerente prima dell'attivazione.
Dettagli verificati e limiti: deploy/embeddinggemma2/README.md e
artifacts/react-migration/pytest-open-issues.md. Il modello operativo precedente
resta attivo; nessuna API esterna riceve documenti dello studio.

- **Diagnosi Consulta 07/10/2026**: timeout della verifica a 15 minuti sul commit 97959fa, con Lex v2 e Normattiva verificati. Aggiunta diagnosi separata in sola lettura di processo, conteggi e download; completamento dei tre corpus ancora da accertare.

- **Consulta completata, correzione attesa 07/10/2026**: diagnosi server conferma 3/3 corpus completi, 22.398 pronunce ciascuno e 46.577 massime lette; import effettivo 1.254,1 secondi. Attesa post-deploy portata da 15 a 30 minuti con conteggi intermedi, mantenendo obbligatorio il marcatore di import completo su tutti i corpus.

## 13/10/2026 — Acquisizione XML Normattiva, candidata 2.437.23

Il download ufficiale restituiva HTML anziché XML e le 13 fonti fallivano con errore di parsing. Il comando esistente conserva ora in memoria la sessione pubblica tra risoluzione dell’atto e download AKN, senza credenziali o documenti degli studi. Restano invariati allowlist, limiti, controllo XML, identità FRBRWork e impronte.

Prova con il comando nativo: 13/13 XML acquisiti e validati. Workflow GitHub 38466034723 riuscito sul codice ba2ed8f285; artefatti recuperati, tutte le impronte concordanti. Nessuna importazione delle fonti sul server, nessuna modifica a Lex, indici o dati degli studi. Versione finale, CI e deploy ancora da verificare; incarichi generali aperti.

## 15/10/2026 — Candidata 2.437.43, catalogo puntuale e prove pertinenti

La seconda lettura del catalogo usa il testo SQL della sola fonte selezionata tramite tenant, fascicolo, document_ai_id, versione e impronta correnti; non carica i testi degli altri documenti. Il modello resta nel motore locale esistente. Sul PC il solo hostname configurato è host.docker.internal; nessun testo dello studio viene inviato a servizi esterni e EmbeddingGemma 300M resta invariato.

Una frase presente può essere estranea alla natura proposta: i riscontri necessari già dichiarati dalle regole del catalogo vengono ora verificati anche per la proposta Lex. Citazione e natura hanno esiti distinti nella provenienza; una mancanza non viene descritta falsamente come citazione assente. La guardia non dimostra da sola ogni possibile classificazione semantica e non rende automatici gli effetti del documento.

Conferme manuali, nuove revisioni della catalogazione o fonte non più corrente impediscono l'applicazione tardiva tramite controllo SQL atomico nello stesso savepoint. Lo scarto è auditato, senza riportare la decisione umana a proposta. La UI consente Rileggi categoria sul singolo documento tramite la pipeline esistente, solo con permesso di scrittura; nessuna nuova estrazione OCR, indicizzazione generale o lettura di altri testi.

Riproduzioni negative iniziali e guardie native SQLite/PostgreSQL; 78 test estesi positivi e 11 casi finali pertinenti dopo la guardia RBAC, gruppi sovrapposti non sommabili. Gate locale 28/28; il primo passaggio aveva segnalato soltanto l'inventario test da rigenerare. Verifica reale del recupero D8EA2D0A, confronto della persistenza, responsive, CI e deploy ancora necessari. Candidata isolata, copia ufficiale e produzione restano 2.437.42. Nessuna modifica ai dati reali, nessuna riconvalida massiva, nessun cambiamento dei flussi congelati.

15/10/2026 — Collaudo43 in corso: ripresa delle due fonti sintetiche senza modificare testo, impronta o versione; proposta precedente conservata nell'audit. La prova nella scheda attiva10 ha richiesto di aumentare a44px i target touch del catalogo su mobile/tablet. Il deploy del primo commit43 è stato annullato prima di SSH; produzione42 invariata. Copertura critica940c617152 identica alla baseline accettata42:27598/33996,81,1801388%,dodici shard e ambiente omogenei. Correzione touch con28gate locali positivi; resta da accettare e rilasciare il nuovo commit. Nessuna estensione di questi risultati alla copertura globale dell'applicativo.
15/10/2026, ore 16:39 — Ultima guardia43 prima della nuova build: riprodotta su entrambi i backend la sovrascrittura di una catalogazione concorrente con updated_at identico (timestamp nativo al secondo). Aggiunto confronto dell'intera assegnazione originale dopo l'UPDATE condizionale che acquisisce il lock e prima della scrittura nello stesso savepoint. Nessuna modifica dello schema, delle date storiche o dei salvataggi senza guardia. Runtime Lex passa lo snapshot letto prima del modello. Due test negativi iniziali, poi37test pertinenti positivi su SQLite/PostgreSQL, senza skip; include15casi del nuovo file. Ruff e documenti test positivi. Il percorso aggiuntivo è solo applicazione asincrona del risultato, non consultazione. CSS touch già verificato dai28gate locali; la prova finale sulle tre dimensioni e sul nuovo SHA resta da eseguire. Produzione42 e deploy43iniziale annullato prima di SSH.

## 15 ottobre 2026 — Firecrawl tramite metodo REA, incarico aperto

Direttiva utente: usare REA per analizzare le capacità di Firecrawl utili a Lex Web quando mancano informazioni pubbliche. Eseguite due analisi statiche reali con rea-agents 6.5.0 sul codice pubblico fissato a b24ee937fe86cc812af013a7930b85e8e9cbe6cf. Ricostruzione, evidenze, limiti, percorsi esistenti e prove ancora necessarie: `artifacts/data-flow/lex-web-firecrawl-rea-20261015.md`. Nessuna integrazione runtime, acquisizione dello studio, configurazione MCP o installazione di servizi Firecrawl effettuata. Non confondere l'indagine con una funzione rilasciata. Riutilizzare regia e recuperatori esistenti; preservare Web libero, provenienza, limiti e distinzione dalle fonti ufficiali. Nessun dato privato a servizi esterni. Restano confronto su fonti reali, scelta dell'implementazione, sicurezza, accettazione 8080 e rilascio.

Candidata45,15ottobre2026: acquisizione e confronto nativi dei contenuti pubblici implementati, guardie tecniche e prova effettiva del provider locale eseguite; nessuna promozione a fonte normativa verificata e nessun dato studio nei canali pubblici. UI e rilascio ancora da accettare. Registro completo: artifacts/data-flow/lex-web-firecrawl-rea-20261015.md.


## 16 ottobre 2026 — Rilascio 2.437.48 e prossimo intervento sugli indici

Rilasciato `33048d2d5a0db23165d1a6f1aae95b0709f909eb`: il percorso pubblico nativo riconosce gli URL espliciti anche con Web spento, separa la lettura letterale dal confronto e usa il V2 locale già configurato soltanto per il secondo. EmbeddingGemma 300M seleziona un lotto pertinente limitato; nessun modello EG2, servizio Firecrawl o dato dello studio nel canale pubblico. Selezione per frasi e sezione proprietaria, conservazione delle condizioni testuali e controllo di ambiti/mezzi estranei; inventario originale preservato. Questo non certifica universalmente la semantica delle parafrasi.

Prova reale su8080 e produzione selezionata: lettura dei due URL Andreani/Brocardi3,2s e1,6s; confronto civile80s e58s, due fonti, termine breve dalla notifica e lungo dalla pubblicazione, eccezione completa, nessun altro mezzo sviluppato. Bozza/focus/scroll preservati nella prova locale; erroreDNS esplicito e persistito, link originali aperti, responsive provato. 244guardie tecniche,89gate e aggregatore positivi; dodici shard candidata e dodici baseline47 omogenei,81,3169585%→81,3663338%,ambiente invariato. Deploy38847668274 positivo,9287file senza differenze locale/server, unicoiusentra-app healthy e pulizia nativa senza volumi/dati. Evidenze operative nei registri pytest e incarico permanente; dossier privato lex48-release-confirmed.json. Catalogo360 e qualità globale restano aperti; una voce di valutazione del sito resta tra gli estratti generici ed è registrata.

Intervento successivo ancora in analisi: il resolver Lex può passare a LIKE sull’archivio locale Normattiva da56.655.478.784byte privo diFTS, causando attesa e timeout. La biblioteca nativa codici_leggi.sqlite è già indicizzata; in produzione l’archivio generale4GB è anch’esso indicizzato e non va sostituito con una biblioteca più piccola. Riutilizzare i motori/indici e la procedura nativa, mantenendo identità semantiche dei chunk, origine, impronta, acquisizione e vigenza realmente attestata (`EDIZIONE_ACQUISITA` non significa vigente). Nessuna costruzione di indici, scansione generale o acquisizione nella richiesta; nessun cambiamento dei dati reali durante l’analisi. Va verificato il percorso ricerca→risultato→apertura della fonte e reso esplicito qualsiasi catalogo incompleto, senza collisioni degli ID fra archivi. Non è ancora una correzione implementata né accettata.


16/10/2026 — Candidata49, ricerca normativa indicizzata: riprodotti prima della modifica quattro fallimenti su cinque casi. Il percorso applicativo sceglie l’archivio generale se ha l’indice nativo; altrimenti consulta la biblioteca codici/leggi già indicizzata dichiarandone il perimetro. In assenza di un indice consultabile restituisce una diagnostica esplicita, senza scansioni LIKE, ZIP, JSONL o costruzione indici nella richiesta. Le ispezioni offline con db_path esplicito restano nella procedura esistente. Conservati identificatore semantico, impronta XML, acquisizione e stato EDIZIONE_ACQUISITA, senza attestare vigenza o copertura integrale. La cache normativa dipende dalla revisione dei soli due archivi e WAL; richieste dello studio e Web libero non ispezionano il catalogo. Diagnostica server non falsificabile dal payload e conservata negli esiti in cache. Dieci guardie nuove positive; gruppo retrieval/importer di22 casi e ricerca React36 casi positivi sul Python host. Necessari guardrail nel runtime nativo, immagine canonica, prova materiale8080 e nuovo ciclo GitHub/deploy. Runtime locale/produzione ancora48; incarichi generali aperti.


16/10/2026 — Prima candidata49 918e2d0dae NON accettata e non pushata. Immagine senza cache, pacchetti/Python identici alla48,9288sorgenti senza differenze, tre container healthy. La domanda sui termini ha attivato il calcolatore nativo (1,4s): non prova il retrieval modificato. La richiesta diretta dell’art.327 ha invece dichiarato il testo assente (2,6s), benché il lettore SQL nativo sulla biblioteca codici/leggi trovi513caratteri e statoEDIZIONE_ACQUISITA. Individuato il percorso verbatim risposta_certa→testi_ufficiali, alimentato dal solo percorso applicativo e non dal resolver del catalogo indicizzato. Prova negativa e screenshot conservati. Correzione in verifica: lo stesso selettore dei cataloghi viene attivato soltanto per una richiesta di articolo; calcoli e ispezioni esplicite mantengono il percorso esistente. Nessun indice costruito nella richiesta. Assenza di indice distinta da articolo non trovato nel catalogo consultato; perimetro biblioteca e vigenza non attestata visibili nel testo. Venti guardie host verbatim/catalogo e21guardie consultazione/HTTP pubblico positive; nuovo gruppo nativo in corso. Necessari seconda immagine e ripetizione materiale, prima di push, CI e deploy. Produzione48 invariata; nessuna chiusura dell’incarico.


16/10/2026 — Seconda candidata49 3b7ff9fcf1 ancora NON accettata e non pushata. Tre container healthy sullo stessoSHA,9288file senza differenze, Python e pacchetti identici alla48. Stessa richiesta verbatim ora mostra l’art.327: confronto materiale del blockquote visibile con il testo SQL,513caratteri identici; fonte ufficiale, edizione acquisita e perimetro biblioteca visibili. Il successivo quesito interpretativo esplicitamente limitato ai testi locali ha impiegato3minuti58secondi e ha incluso12evidenze, fra cui sentenze costituzionali non pertinenti. Il testo normativo è usato, ma il percorso non è accettato per pertinenza e tempi. Il trasporto SSE governato consegnava soltanto answer come token, perdendo warnings/fonti/politica esportazione del payload già prodotto. Bozza e focus preservati, ma scroll4334→5625: difetto registrato, non dichiarato positivo. ModelloV2:9b caricato suCPU,EmbeddingGemma300M invariato; non cambiati i parametri per coprire il difetto.
Guardie negative riproducono selezione di cataloghi estranei, perdita del payload e salto di scroll. Rifinitura in verifica: la sola richiesta esplicita di riferimento normativo esatto da testi/fonti locali attiva il produttore normativo già esistente e non inietta contesto studio; ricerche miste/giurisprudenziali e fascicoli/documenti collegati restano nei percorsi esistenti. Nessuna scansione o nuovo indice. Trasporto SSE del payload completo, memoria della sola risposta mostrata con campi delimitati (fonti/citazioni/avvisi/blocco export, senza prompt o contesto strutturato), ripristino e scroll coerenti anche per token ordinari. Link Normattiva costruito dal builder nativo, conservandoURN e identificativo semantico: il numero dell’articolo non è dedotto dalla chiave interna del chunk.43guardie host e testJS positivi; gruppo nativo esteso in corso. Il recupero recente/non pertinente degli altri cataloghi nelle ricerche più generali resta censito nel lavoro di qualità globale delle fonti, non viene dichiarato risolto da questo recinto esplicito. Restano nuova immagine, stesso collaudo reale, CI/copertura e deploy; produzione48 invariata.


16/10/2026 — Verifica aggiuntiva candidata49: lettura SQL in sola consultazione sul server conferma che il catalogo generale indicizzato non contiene art.327 c.p.c., mentre la biblioteca indicizzata restituisce513caratteri EDIZIONE_ACQUISITA. Il recupero puntuale consulta al massimo i due cataloghi esistenti, conserva i riferimenti esatti già trovati nel generale e integra soltanto quelli mancanti. Il lettore verbatim usa gli identificativi documento/articolo prodotti dall’indice, con verifica dell’atto; preservata la distinzione codice civile/preleggi. Nessuna enumerazione dell’archivio nella richiesta. Guardie native finali57positive in41,892s; gruppo precedente182positivo, sovrapposto e non sommabile. Produzione ancora48; nuova immagine, prova reale, CI e deploy ancora necessari.


16/10/2026 — Terza prova reale49 9e69f93a59: testo327 mostrato1,1s,513caratteri; domanda interpretativa111s contro238s,una sola evidenza pertinente contro12. Bozza e focus conservati; scroll3311→4135 ancora negativo. Intestazione erronea configurazione studio dovuta al contesto pagina, separata dal workflow normativo effettivo. Candidata non pushata. Correzione mirata: preservare scroll anche nel ridisegno delle fasi di attesa e disabilitare l’ancoraggio automatico sul solo contenitore della chat; intestazione derivata dal workflow normativo esplicito già risolto. ParametriV2 invariati. Restano nuovo runtime, collaudo e gate.


16/10/2026 — Ripresa esplicita dopo pausa. Avvio Docker Desktop ripristinato tramite stop/start ufficiale, senza modifiche a credenziali o volumi. Candidata2c6eeb9fcc: immagine senza cache, Python/pacchetti identici alla48,9288file senza differenze,app/OCR/scheduler healthy. Prova reale visibile1366×768: verbatim1,4s,513caratteri identici al testoSQL già verificato; analisiV2 suCPU132s,una evidenza pertinente,etichetta ricerca normativa locale. Durante il gesto manuale scroll224→162, poi posizione stabile162 prima e dopo l’esito,bozza/focus conservati. Limiti su vigenza e revisione conservati. Riapertura: fonti/avvisi presenti, ma intestazione e scheda affidabilità non ripristinate; difetto riprodotto dal testJS, correzione in verifica sul salvataggio dei soli campi di presentazione. Nessun prompt o contesto privato aggiunto alla cronologia. Necessaria nuova immagine e prova materiale della riapertura prima di push/CI/deploy. Produzione48 invariata.


16/10/2026 — Collaudo mobile candidata2c:375px senza overflow orizzontale,invio44px; espansa raggiunge fondo3759+251=4010. Nel passaggio da desktop flottante a telefono il riquadro lettura restava27px: difetto riprodotto, ora il resize aperto verso mobile attiva la vista espansa nativa senza salvare la preferenza desktop e preserva lettura/fondo. TestJS negativo prima della correzione della cronologia, poi positivo per intestazione,affidabilità,fonti,avvisi,blocco esportazione e assenza di contesto privato.11guardie native widget positive. Nuova immagine e ripetizione materiale ancora necessarie; nessun push49/deploy.


16/10/2026 — Prova5d59842197:105s per l’analisi,una evidenza; scroll2093 invariato,bozza/focus conservati. Riapertura conserva ora intestazione ricerca normativa locale,affidabilità22%,fonte e avvisi. Resta censito nella qualità generale il dubbio interpretativo aggiunto dal modello; nessuna certificazione semantica universale o vigenza attestata. Tempi osservati non equivalgono a benchmark globale,anche per addestramento utente parallelo,che non viene toccato. Telefono automatico:7883+251=8134,larghezza375 senza overflow,invio44. Secondo resize verso tablet ripristinava la preferenza desktop: correzione puntuale della stessa condizione,provata in diagnostica hot sulla8080,dopo backupJS,con sequenza805→375→805 e area lettura428→315→428px. Tale diagnostica hot non è accettazione dell’immagine immutabile; richiesta nuova buildsenza cache e ripetizione finale. Nessun push49/deploy.


16/10/2026 — Richiesta UI Lex: riutilizzati template condiviso, SCSS e gestore finestre React. In diagnostica sulla copia reale8080: intestazione48px con comandi unificati; finestra desktop768×664 e lettura451px; campo vuoto44px con crescita per testo multilinea. Telefono375px: sette comandi36px tutti alla medesima ordinata, quattro modalità e stato su barra orizzontale; nessuna fascia ridondante Contesto panoramica, contesto interno preservato. Bozza controllata su due righe preservata dopo telefono/tablet e chiusura/riapertura; Web attivato e disattivato senza invio. Corretta applicazione della griglia condivisa anche ai riepiloghi Panoramica con classe iu-metric, conservando badge, conteggi e destinazioni. Test widget11, Node e typecheck positivi; build Vite con budget e confine lazy superati. Sono prove diagnostiche hot, non accettazione finale dell’immagine immutabile o del deploy. Immagine senza cache, nuova prova reale, CI e deploy ancora necessari. Addestramento utente e flussi congelati non modificati.

## 16/10/2026 — Interrogazioni operative SQL, sviluppo non ancora rilasciato

Il percorso PEC semplice identifica dominio, data civile italiana, direzione e cartella prima del contesto esteso. Dopo autorizzazione consulta una pagina del repository SQL proprietario, senza cataloghi di altri domini, manager MIME, importazioni, OCR o modello AI. Le domande per cliente/contenuto/allegati conservano il loro percorso specifico; non si eliminano filtri per farle rientrare nella nuova selezione.

Stato della prova: guardrail nativi su SQLite e PostgreSQL positivi, con date equivalenti, confini di giorno, permessi, due studi, sorgente cambiata, rollback, retry finito, backup SQLite e ripresa del cursore. Paginazione firmata con studio/utente/scadenza e filtri assoluti; un token non autorizza l'accesso e RBAC viene ripetuto a ogni pagina. Zero risultati, data mancante e consultazione fallita restano distinti. Nessuna modifica ad addestramento, EmbeddingGemma300M o flusso firma/deposito/invio PEC.

La proiezione è derivata: i messaggi SQL restano fonte primaria. Scritture native aggiornano fonte e indice nella medesima transazione; gli altri cambiamenti producono eventi puntuali nell'outbox esistente, senza una coda parallela. Migrazione separata, con backup nativo verificato, hash, autore e cursore SQL persistente; nessuna preparazione dello schema in una domanda. Il worker tratta soltanto consegne pendenti, con massimo cinque tentativi e causa conservata.

Runtime attivo ancora41375ed64f/2.437.49. Restano aperti gli altri domini richiesti (Agenda, Scadenziario, depositi e notificazioni), collaudo reale visibile8080, gate, commit/deploy e pulizia della nuova tranche. Il pannello browser ha restituito non visibile durante il tentativo odierno: nessuna accettazione visiva positiva dichiarata. Dettagli, difetti trovati e riprove: docs/LEX_STUDIO_QUERY_ACCEPTANCE.md.


## 23/10/2026 — Ricerca OpenGA progressiva, candidato in verifica

La ricerca approfondita richiede prima la stessa ricerca lessicale autenticata e
mostra immediatamente il suo esito. Il riordino approfondito viene richiesto solo
dopo una risposta rapida valida e su scelta iniziale esplicita dell'avvocato.
La lista approfondita pronta viene annunciata, senza sostituire quella visibile:
il passaggio avviene soltanto con un comando esplicito, con ritorno alla rapida.
Errori del secondo canale conservano la prima lista e sono dichiarati; uscita
dalla pagina annulla la richiesta browser. Nessuna cache di query o dato di studio
e nessuna modifica a fonti, indice, permessi o capacità probatoria metadata_only.
Il pool operativo resta 100: 40 e 30 sono varianti da misurare su CPU server prima
di qualsiasi promozione. Il banco server di 30 casi è ora banco di regressione;
la conferma conclusiva richiede un ulteriore campione congelato prima dei risultati.
Stato: implementazione e accettazione in corso, nessuna nuova misura prestazionale.


### Contatori distinti di studio e archivio pubblico
Le schede fonti contano le schede interne con judgment_count, non i corpus
pubblici. La UI dichiara tale perimetro e carica separatamente il conteggio SQL
del catalogo OpenGA dal servizio privato sullo stesso host. Il conteggio remoto
non disponibile resta sconosciuto, mai trasformato in zero. L'inventario è
read-only, non avvia modelli, non legge fascicoli e non crea tabelle o database.
Gli archivi pubblici non vengono copiati nelle schede dello studio. L'apertura
del testo ufficiale resta da completare: il modulo pubblico riscontra la
decisione ma il documento ha fallito la prova browser; il client HTTP di ricerca
pubblica ha ricevuto 403. Nessun aggiramento, token trasferito o download massivo.

### Correzione leggibilità fonti (24 ottobre 2026)
La pagina legge i conteggi per fonte dal solo corpus SQLite dello studio corrente in modalità read-only, separati dalle schede manuali e dal catalogo OpenGA condiviso. Database assente o illeggibile significa conteggio sconosciuto, non zero. Nessuna aggregazione fra studi. Il pannello del risultato OpenGA espone gli estremi copiabili e il modulo ufficiale; non dichiara un collegamento diretto al documento, che resta non disponibile nel catalogo. Il documento specifico segnalato dall'utente è consultabile nel suo Chrome; il fallimento del browser integrato non dimostra indisponibilità della fonte.


### Procedura atti 2.449.1: contratto delle Fonti
lex.procedura_atti resta una libreria senza endpoint, UI, chiamate a modelli o persistenza.
Il chiamante deve fornire per ogni riferimento la provenienza: tipo (norma/decisione),
url (indirizzo ufficiale o archivio dichiarato), versione, acquisita_il (data reale
gg/mm/aaaa), sha256 del testo effettivo; per le decisioni anche testo_integrale: true.
Il controllo verifica struttura e impronta, non autentica il fornitore e non scarica
il documento. Acquisizione governata e approvazione dell'avvocato restano distinte.
Nessun valore sostitutivo viene generato per la provenienza mancante.
L'impronta comprende l'intero riferimento e la provenienza. La valutazione ricontrolla
scheda, fascicolo, Fonti e calcoli rispetto alla preparazione.
Gli spunti R6 metadata_only non vengono promossi a Fonti né inseriti nel messaggio di stesura.
Il catalogo dei requisiti degli atti resta provvisorio: occorre riscontro sulle norme vigenti
prima del collegamento operativo. Nessun esito automatico certifica correttezza giuridica.


### Lettura ufficiale OpenGA — 2.450.0
Ingresso autenticato: POST giurisprudenza/testo-ufficiale; polling GET per job.
Il browser fornisce soltanto relazione e risorsa con SHA. Il worker pubblico
risolve l'identità nel catalogo corrente in sola lettura. Nessun URL del browser
viene scaricato. Il processo web acquisisce il testo tramite trasporto limitato,
riscontra gli estremi e l'organo e conserva originale, sezioni, provenienza e SHA
nella coda LegalUpdateJobQueue, in un file derivato dal database del solo studio.
Le letture si deduplicano per relazione/risorsa/versione. I job non approvano
schede né modificano indice, catalogo o stato di verifica del corpus.
L'utente vede il documento solo dopo esito acquisito; altrimenti resta uno spunto.
Il testo pubblicato è distinto da motivazioni ricostruite: nessuna sintesi legale
viene inventata. La successiva approvazione della scheda resta dell'avvocato.
I metadati tecnici di rilascio non vengono esposti nel testo. Letture automatiche
non riuscite devono avere esito esplicito, mai falsa attestazione di acquisizione.

### Biblioteca e Fonti di stesura — 2.454.0 (integrazione in verifica)
Il coordinatore `redazione_lex_runtime.stesura` chiama prima
`biblioteca.ricerca_fonti.integra_fonti`, poi `stesura_blocchi.scrivi_blocchi`.
La ricerca fonde i candidati della biblioteca e delle schede; la scelta del modello
è vincolata agli identificatori ricevuti e viene completata dalla classifica.
`lettura_normativa_rag.completa_lettura_normativa` conserva il testo integrale
se entra nel limite, oppure registra la lettura non completata. Le norme senza
riscontro della versione e della provenienza non vengono certificate dal modello.

Le importazioni esplicite verificano SHA dei file fisici, identità congiunta,
partizione XML e intervallo di edizione. Le rettifiche dei soli metadati mantengono
originale, derivato tecnico e prova del corpo invariato; non producono una nuova
fonte ufficiale. La data di acquisizione proviene dalla ricevuta, mai dalla data
SQL di importazione. Il registro delle transitorie richiede approvazioni riferite
all'impronta della regola e riscontro fisico della fonte; non si creano approvazioni
professionali automatiche. I riferimenti storici rimossi restano consultabili
per ID e SHA e non diventano Fonti attive.

Le prove automatiche sono guardrail tecnici. Al momento di questo aggiornamento
restano da attestare integrazione finale dei dati, misura reale del 35B, prova
visibile sulla copia reale8080, CI e parità dopo deploy. Nessuna copertura giuridica
globale è dedotta dal conteggio dei file o degli articoli.

# Lex Studio LLM - Matrice domini dati studio

Aggiornato: 17 maggio 2026

Questa matrice definisce quali dati operativi dello studio possono alimentare
Lex AI in modalità RAG e quali possono diventare coppie domanda/risposta
candidate per revisione umana. Non autorizza addestramento automatico, invii a
fornitori esterni o esportazione non supervisionata di dati riservati.

## Comunicazioni: PEC, email ordinaria e messaggi

### Perimetro

| Dominio Lex | Sorgente canonica | Percorso tenant-aware | Permesso minimo | Uso RAG | Uso dataset Q&A |
| --- | --- | --- | --- | --- | --- |
| `email_pec` | `pct.email_client.GestioneEmailRicevute` | `EMAIL_CASELLA_DB` sotto `/data/tenants/<studio>/email/casella.json` | `messaggi.leggi` | Sì, solo tenant attivo | Solo candidate da revisione |
| `email_ordinaria` | `pct.email_client.GestioneEmailRicevute` | `EMAIL_ORDINARIA_DB` sotto `/data/tenants/<studio>/email/ordinaria.json` | `messaggi.leggi` | Sì, solo tenant attivo | Solo candidate da revisione |
| `messaggi` | `pct.messaggi.GestioneMessaggi` | `MESSAGGI_DB` sotto il tenant attivo | `messaggi.leggi` | Sì, per storico comunicazioni inviate | Solo candidate da revisione |

In ambiente multi-studio il contesto tenant è obbligatorio. Se `g.data_paths`
o il profilo storage equivalente non espongono le chiavi del tenant attivo,
Lex deve fallire chiuso e non deve leggere fallback globali come `/data/email`,
`./email/casella.json` o `./email/ordinaria.json`.

### Allegati PEC ed email

Gli allegati fanno parte del dominio documentale più sensibile delle
comunicazioni. Il RAG può indicizzare metadati e testo estratto solo quando il
messaggio e il tenant sono autorizzati.

- I nuovi allegati possono essere salvati in `archivio-allegati.zip` quando
  `IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive` o valore equivalente è attivo.
- Lettura e anteprima devono passare da
  `GestioneEmailRicevute.leggi_allegato()` e
  `GestioneEmailRicevute.allegato_disponibile()`, così restano compatibili sia
  gli allegati compressi sia i file sciolti storici.
- Il dataset non deve esportare il contenuto binario originale. Se serve una
  evidenza testuale, viene creato un chunk derivato con hash, nome file
  sanitizzato, MIME type, dimensione e riferimento al messaggio.
- Allegati `.eml`, ricevute PEC, esiti PST/PCT, PDF firmati e documenti
  prodotti da terzi sono classificati almeno come `sensitive`; diventano
  `highly_sensitive` se contengono dati sanitari, minori, credenziali,
  coordinate bancarie complete o informazioni giudiziarie particolarmente
  delicate.
- È vietato esportare allegati sensibili senza revisione esplicita. È vietato
  inviare allegati o chunk a servizi esterni per training automatico.

### Campi da includere nel RAG

| Campo logico | Origine | Regola |
| --- | --- | --- |
| Identificativo messaggio | `EmailRicevuta.id` o id messaggio storico | Usare solo come riferimento interno, non come dato pubblico |
| Tipo casella | PEC, ordinaria, messaggi inviati | Necessario per separare regole e tono operativo |
| Cartella e stato | `cartella`, `stato` | Ammessi per capire se il messaggio è ricevuto, inviato, cestinato o da leggere |
| Mittente e destinatari | `mittente`, `mittente_nome`, `destinatari` | Ammessi come dati personali sensibili, con minimizzazione nelle risposte |
| Oggetto | `oggetto` | Ammesso, utile per ranking e collegamento fascicolo |
| Data | `data`, `ricevuta_il`, timestamp messaggio | Ammessa in formato italiano nelle risposte utente |
| Corpo testo | `corpo_testo` o testo estratto da HTML pulito | Ammesso in chunk tenant-aware; evitare HTML grezzo nel prompt |
| Anteprima | `anteprima` | Ammessa solo come sintesi locale, non come sostituto del corpo se serve prova |
| Allegati | metadati allegati, testo estratto governato | Ammessi se letti dal reader e marcati con hash/provenienza |
| Stato PCT/PST | `stato_pct`, `id_deposito_pct`, `e_pst` | Ammesso per collegare ricevute, esiti e fascicolo |
| Correlazioni | id fascicolo, RG, cliente, parti, deposito | Ammesse se derivate da repository tenant-aware o match verificabile |

### Campi da escludere

- Password PEC, password SMTP, token OAuth, app password, sessioni IMAP,
  cookie, PIN, credenziali CNS/CIE/SPID e segreti configurativi.
- Header completi non necessari, route tecniche, path assoluti locali, stack
  trace, nomi di variabili, endpoint interni e payload grezzi.
- HTML non sanificato, tracker, immagini remote e contenuti attivi.
- Allegati binari originali, salvo processo locale di estrazione approvato e
  tracciato.
- Dati di altri tenant, anche se presenti in fallback legacy o copie locali.
- Record cancellati o in cestino quando la richiesta non li menziona e non vi è
  una ragione professionale esplicita per recuperarli.

### Chunk RAG consigliato

Ogni chunk comunicazione deve conservare:

- `tenant_id`, `domain`, `message_id`, `mailbox_kind`, `folder`, `date`;
- `subject`, `participants_summary`, `body_text`;
- `attachment_refs` con nome file sanitizzato, MIME type, dimensione, hash e
  disponibilità;
- `privacy_classification`, `required_permissions`, `source_path_key`;
- eventuale `fascicolo_id`, `cliente_id`, `rg`, `deposito_pct_id` solo se
  verificati.

Il testo del chunk deve essere abbastanza breve per il retrieval, ma Lex deve
mantenere l'inventario completo dei messaggi e degli allegati rilevanti: la
selezione per ranking non deve far credere che non esistano altre comunicazioni
nel fascicolo.

### Q&A candidate

Le coppie Q&A generate dal dominio comunicazioni sono sempre
`pending_human_review` e non possono essere esportate come training pronto
senza approvazione umana.

Esempi ammessi:

- "Riassumi l'ultima PEC della cancelleria nel fascicolo X."
- "Quali allegati risultano presenti nella PEC di deposito del 12 maggio 2026?"
- "Estrai RG, ufficio, mittente, destinatari e stato PCT da questa ricevuta."
- "Prepara una bozza di risposta al cliente usando solo questa email e i dati
  del fascicolo autorizzato."
- "Collega questa comunicazione al fascicolo più probabile e indica perché il
  collegamento è solo suggerito o verificato."

Esempi vietati:

- domande che chiedono a Lex di inventare ricevute, allegati o recapiti;
- domande che richiedono invio automatico di email, PEC, SMS o WhatsApp;
- domande che includono credenziali o chiedono di mostrarle;
- dataset generati da allegati senza revisione umana;
- training automatico o upload esterno di messaggi e allegati.

### Azioni Lex consentite

Lex può:

- riassumere email, PEC e thread autorizzati;
- estrarre riferimenti operativi: RG, ufficio, data, mittente, destinatari,
  oggetto, termini, allegati, stato PCT/PST e possibili clienti o fascicoli;
- proporre una bozza di risposta, lasciandola in revisione umana;
- suggerire il collegamento a un fascicolo, distinguendo collegamento
  verificato, probabile e da confermare;
- preparare una lista di controlli su allegati mancanti o esiti da verificare;
- citare la comunicazione interna come evidenza riservata, senza renderla fonte
  pubblica.

Lex non può:

- inviare email, PEC, SMS o WhatsApp senza comando esplicito e workflow
  operativo autorizzato;
- cancellare, spostare, marcare come letto o modificare messaggi nel percorso
  RAG;
- salvare credenziali o mostrarle nelle risposte;
- esportare allegati sensibili senza revisione;
- addestrare automaticamente modelli locali o remoti;
- usare dati di un tenant diverso o fallback globali.

### Privacy, audit e permessi

- Il permesso minimo per leggere comunicazioni è `messaggi.leggi`.
- Le azioni dispositive restano fuori dal RAG e richiedono i permessi operativi
  specifici già previsti dalle route applicative.
- Ogni evidenza comunicazione deve registrare fonte, tenant, chiave path,
  timestamp di costruzione e classificazione privacy.
- Le risposte Lex devono minimizzare dati personali non necessari: mostrare il
  necessario per l'attività richiesta, non l'intero messaggio se basta un
  riepilogo.
- Le bozze devono dichiarare quando mancano allegati, corpo integrale,
  collegamento fascicolo verificato o permessi sufficienti.

### Test di accettazione

Un'implementazione del dominio comunicazioni è accettabile solo se:

1. in multi-studio senza tenant valido fallisce chiusa e non legge fallback
   globali;
2. PEC e posta ordinaria usano rispettivamente `EMAIL_CASELLA_DB` e
   `EMAIL_ORDINARIA_DB` del tenant attivo;
3. gli allegati compressi in `archivio-allegati.zip` e i file sciolti storici
   sono leggibili solo tramite `GestioneEmailRicevute.leggi_allegato()`;
4. il manifest RAG non contiene path assoluti, password, token o allegati
   binari;
5. le Q&A generate da email/PEC restano `pending_human_review` e non vengono
   esportate come training pronto;
6. le risposte di Lex distinguono fatti certi, collegamenti suggeriti e lacune;
7. nessuna azione dispositiva viene eseguita dal percorso RAG;
8. i test coprono almeno una PEC con allegato compresso, una email ordinaria,
   un messaggio inviato e un tentativo senza tenant valido.

## Agenda, calendario, scadenze e termini

### Perimetro

| Dominio Lex | Sorgente canonica | Percorso tenant-aware | Permesso minimo | Uso RAG | Uso dataset Q&A |
| --- | --- | --- | --- | --- | --- |
| `agenda` | `pct.agenda.Agenda` via `web.helpers.get_agenda()` | `AGENDA_DB` sotto `/data/tenants/<studio>/agenda/appuntamenti.json` | `agenda.leggi` | Sì, solo tenant attivo | Solo candidate da revisione |
| `scadenziario` | `pct.scadenziario.GestioneScadenziario` via `web.helpers.get_scadenziario()` | `SCADENZIARIO_DB` sotto `/data/tenants/<studio>/scadenziario/scadenze.json` | `scadenziario.leggi` o alias applicativo `scadenze.leggi` | Sì, solo tenant attivo | Solo candidate da revisione |
| `calendario_sync` | `pct.calendar_sync.GestioneCalendarSync` e provider configurati | `CALENDAR_SYNC_DB` sotto `/data/tenants/<studio>/agenda/calendar_sync.json` | `agenda.leggi` più permesso impostazioni quando si leggono profili di sync | Solo metadati di sincronizzazione autorizzati | No, salvo esempi operativi revisionati senza segreti |
| `timesheet_operativo` | `pct.timesheet.GestioneTimesheet` quando collegato a eventi o attività | `TIMESHEET_DB` sotto `/data/tenants/<studio>/timesheet/entries.json` | `agenda.leggi` o permesso fatturazione/attività previsto dalla route | Solo contesto minimo per prossima azione e consuntivo | Solo candidate da revisione |

In ambiente multi-studio il contesto tenant è obbligatorio. Se `g.data_paths`
o il profilo storage equivalente non espongono `AGENDA_DB` e
`SCADENZIARIO_DB` del tenant attivo, Lex deve fallire chiuso e non deve leggere
fallback globali come `./agenda/appuntamenti.json`, `./scadenziario/scadenze.json`
o copie sotto `/data` non tenant-aware.

### Campi da includere nel RAG

| Campo logico | Origine | Regola |
| --- | --- | --- |
| Identificativo interno | `Appuntamento.id`, `Scadenza.id` | Usare solo come riferimento operativo interno |
| Tipo e stato | `tipo`, `stato`, `priorita` | Ammessi per distinguere udienza, deposito, termine, evento, completato o annullato |
| Date e orari | `data_ora`, `durata_minuti`, `data_decorrenza`, `data_scadenza`, `legal_due_at`, `operational_due_at` | Ammessi; le risposte utente devono usare formato italiano e indicare se il termine è legale o operativo |
| Oggetto operativo | `titolo`, `descrizione`, `note` | Ammesso con minimizzazione; evitare di riportare note integrali se basta un riepilogo |
| Collegamenti pratica | `id_fascicolo`, `procedimento`, `tribunale`, `judicial_office_*` | Ammessi solo se letti dal tenant corrente o verificati sul fascicolo autorizzato |
| Collegamenti cliente | `id_cliente`, `cliente`, `cf_cliente` | Dati personali sensibili: usare solo se necessari alla domanda |
| Responsabile e avvisi | `id_utente_responsabile`, `giorni_preavviso`, `avvisi_inviati` | Ammessi per organizzare la prossima azione; non esporre preferenze non pertinenti |
| Calcolo termini | `deadline_profile_code`, `source_event_type`, `source_event_at`, `trace_json`, `perentorio`, `office_mode_on_legal_due_date` | Ammessi come evidenza interna; Lex deve distinguere calcolo certo, preset applicato e punto da verificare |
| Sincronizzazione calendario | `external_provider`, `external_uid`, `external_profile_id`, `external_last_sync` | Ammessi come metadati minimi; non usare URL/token completi o credenziali |

Ogni chunk RAG deve conservare `tenant_id`, `domain`, `source_path_key`,
`record_id`, `date_start`, `date_end` o `due_date`, `status`,
`required_permissions`, `privacy_classification` e collegamenti verificati a
fascicolo, cliente o udienza. Il testo del chunk deve essere breve, ma Lex deve
mantenere l'inventario completo degli eventi e delle scadenze rilevanti: il
ranking non deve far credere che non esistano altri termini nel fascicolo.

### Campi da escludere

- Credenziali Google, Microsoft, Apple/CalDAV, WebCal privati, token OAuth,
  refresh token, password, cookie, sessioni e segreti di calendario.
- URL `external_source_url` completi quando contengono token, identificativi
  personali non necessari o link privati non sanitizzati.
- Path assoluti locali, chiavi `g.data_paths`, route tecniche, stack trace,
  payload grezzi, nomi di variabili e dettagli utili solo a chi programma.
- Eventi cancellati, annullati o completati quando la domanda chiede solo
  attività aperte, salvo richiesta esplicita o necessità professionale.
- Dati di altri tenant, fallback legacy e copie esportate.
- Scadenze o udienze ipotetiche non presenti negli archivi: Lex può proporre
  un controllo da fare, non creare un termine come fatto già registrato.

### Q&A candidate

Le coppie Q&A generate dal dominio agenda/scadenze sono sempre
`pending_human_review`. Non autorizzano training automatico, invio esterno o
creazione di scadenze.

Esempi ammessi:

- "Prepara il brief della giornata con udienze, appuntamenti e termini urgenti."
- "Quali termini perentori scadono nei prossimi sette giorni nel fascicolo X?"
- "Prepara l'udienza del 20 maggio 2026 usando agenda, fascicolo e scadenziario autorizzati."
- "Indica la prossima azione consigliata per il fascicolo X e spiega quali dati mancano."
- "Segnala conflitti tra appuntamenti dello stesso giorno o sovrapposizioni di orario."
- "Mostra quali scadenze derivano da un calcolo termine e quali sono state inserite manualmente."

Esempi vietati:

- domande che chiedono di inventare scadenze, udienze, rinvii o termini non presenti;
- generazione automatica di un calendario o dataset training senza revisione;
- invio automatico di promemoria, email, PEC, SMS, WhatsApp o inviti calendario;
- modifica, completamento, cancellazione o rinvio di eventi dal percorso RAG;
- esposizione di token, URL privati di calendario o dati fuori tenant.

### Azioni Lex consentite

Lex può:

- preparare un brief della giornata o della settimana usando solo eventi e
  scadenze autorizzati;
- evidenziare termini urgenti, scaduti o perentori, distinguendo data legale,
  anticipo operativo e fonte del calcolo;
- supportare la preparazione udienza collegando agenda, fascicolo,
  scadenziario e comunicazioni già autorizzate;
- suggerire la prossima azione, dichiarando se è una raccomandazione e non un
  adempimento registrato;
- segnalare conflitti calendario e sovrapposizioni di orario;
- proporre Q&A o checklist in revisione umana.

Lex non può:

- creare, modificare, completare, eliminare o rinviare appuntamenti e scadenze
  tramite dataset/RAG;
- inviare promemoria o comunicazioni esterne senza workflow applicativo
  esplicito e autorizzato;
- leggere calendari o scadenziari di un altro tenant;
- usare fallback globali in multi-studio;
- addestrare automaticamente modelli locali o remoti;
- presentare come certa una scadenza calcolata senza fonte, preset o archivio
  verificabile.

### Privacy, audit e permessi

- Il permesso minimo è `agenda.leggi` per agenda/calendario e
  `scadenziario.leggi` o alias `scadenze.leggi` per scadenze e termini.
- La preparazione udienza o la prossima azione richiedono anche i permessi dei
  domini collegati, ad esempio `fascicoli.leggi` o `messaggi.leggi`, se Lex usa
  fascicoli o comunicazioni come evidenza.
- Ogni evidenza deve registrare tenant, chiave path (`AGENDA_DB`,
  `SCADENZIARIO_DB`, `CALENDAR_SYNC_DB`), timestamp di costruzione, permessi e
  classificazione privacy.
- Le risposte devono minimizzare dati personali, indicare lacune e separare
  fatti archiviati, calcoli derivati e suggerimenti operativi.
- Gli audit devono registrare consultazione e fonte interna, non contenuti
  integrali non necessari.

### Test di accettazione

Un'implementazione del dominio agenda/scadenze è accettabile solo se:

1. in multi-studio senza tenant valido fallisce chiusa e non legge fallback
   globali;
2. `AGENDA_DB`, `SCADENZIARIO_DB` e, quando serve, `CALENDAR_SYNC_DB` derivano
   dal tenant attivo;
3. il manifest RAG non contiene path assoluti, token, password, URL privati di
   calendario o payload tecnici;
4. le Q&A restano `pending_human_review` e non vengono esportate come training
   pronto;
5. Lex non crea né modifica scadenze, eventi o promemoria dal percorso RAG;
6. il brief giornata, i termini urgenti, la preparazione udienza, la prossima
   azione e i conflitti calendario distinguono fatti certi, calcoli derivati e lacune;
7. i test coprono almeno un appuntamento udienza, una scadenza perentoria, una
   scadenza con `operational_due_at`, un profilo calendario sync senza segreti e
   un tentativo senza tenant valido.

## Atti, template, redazione, editor e documenti prodotti

### Perimetro

| Dominio Lex | Sorgente canonica | Percorso tenant-aware | Permesso minimo | Uso RAG | Uso dataset Q&A |
| --- | --- | --- | --- | --- | --- |
| `template_atti` | `pct.template_atti.GestioneTemplateAtti` e repository template collegato | `TEMPLATE_ATTI_DB` sotto `/data/tenants/<studio>/template_atti/templates.json` | `documenti.leggi` | Sì, solo tenant attivo | Solo candidate da revisione |
| `redazione_atti` | `pct.assistente_redazionale.AssistenteRedazionale`, `web.services.editor_ai_runtime` e bridge Redazione Atti | `REDACTION_ASSISTANT_DB` sotto `/data/tenants/<studio>/intelligence/assistente_redazionale.json` | `documenti.leggi`; `documenti.scrivi` solo per salvare bozze tramite workflow applicativo | Sì, come guida redazionale e audit assistito | Solo candidate da revisione |
| `editor_documenti` | editor documentale fascicolo, `web.services.document_intelligence_runtime` e repository Documenti AI | `FASCICOLI_DOCS`, `FASCICOLI_DB` e indice documentale tenant-aware | `documenti.leggi` | Sì, solo testi e metadati autorizzati | Solo candidate da revisione |
| `bozze_documenti` | bozze generate da template, editor e notifiche collegate al fascicolo | cartelle documenti/bozze sotto `/data/tenants/<studio>/fascicoli/` o archivio applicativo equivalente | `documenti.leggi`; scrittura solo con `documenti.scrivi` e conferma umana | Sì, come bozza in revisione | Solo candidate da revisione |
| `documenti_prodotti` | documenti salvati nel fascicolo, output di compilazione e documenti firmati/importati | `FASCICOLI_DOCS`, `FASCICOLI_DB`, output documentali tenant-aware | `documenti.leggi` e permessi fascicolo collegati | Sì, con classificazione privacy elevata | Solo candidate da revisione esplicita |

In ambiente multi-studio il contesto tenant è obbligatorio. Se `g.data_paths`
o il profilo storage equivalente non espongono `TEMPLATE_ATTI_DB`,
`REDACTION_ASSISTANT_DB`, `FASCICOLI_DB` e `FASCICOLI_DOCS` del tenant attivo,
Lex deve fallire chiuso e non deve leggere fallback globali come
`./template_atti/templates.json`, `./intelligence/assistente_redazionale.json`,
`./fascicoli/fascicoli.json`, `./fascicoli/documenti` o cartelle `output`
condivise.

Il dominio atti/redazione è un dominio di conoscenza e assistenza, non un
motore dispositivo: indicizza fonti reali, suggerisce template e prepara bozze
in revisione, ma non sostituisce il controllo dell'avvocato.

### Campi da includere nel RAG

| Campo logico | Origine | Regola |
| --- | --- | --- |
| Identificativo interno | codice template, id documento, id bozza, id fascicolo | Usare solo come riferimento operativo interno |
| Classificazione atto | materia, rito, fase, tipo atto, tag template, canale civile/penale/amministrativo | Ammessa per selezione template e checklist, senza presentarla come fonte normativa |
| Metadati template | titolo, descrizione, prerequisiti, campi richiesti, blocchi, checklist, stato revisione | Ammessi se provengono dal catalogo tenant-aware o da template master governato |
| Contesto fascicolo | cliente, parti, controparte, RG, ufficio, giudice, scadenze collegate, documenti allegati | Ammesso solo se l'utente ha permessi su fascicolo e documenti collegati |
| Testo bozza | contenuto redazionale, clausole, paragrafi, note di revisione, modifiche proposte | Ammesso come `draft_in_review`; citare lacune e fonte dei dati precompilati |
| Documenti prodotti | titolo, tipo, versione, stato, hash, data produzione, autore o revisore | Ammessi come inventario e recupero; il testo integrale richiede permesso documento |
| Evidenze fonte | template usato, fascicolo, documenti allegati, comunicazioni, scadenze, fonti pubbliche governate | Ammesse solo con provenienza tracciata e distinzione tra fonte interna e fonte ufficiale |
| Audit editor | proposta modifica, autore proposta, esito revisione, timestamp | Ammesso come metadato; non includere ragionamento interno nascosto |

Ogni chunk RAG deve conservare `tenant_id`, `domain`, `source_path_key`,
`record_id`, `case_id`, `document_id` o `template_code` quando disponibili,
`draft_status`, `required_permissions`, `privacy_classification`,
`source_evidence` e `review_state`. Il testo del chunk deve essere breve, ma
Lex deve mantenere l'inventario completo di template, bozze e documenti
rilevanti: il ranking non deve far credere che non esistano altri modelli,
allegati o versioni del documento.

### Campi da escludere

- Password, token, PIN, certificati di firma, sessioni portale, credenziali
  CNS/CIE/SPID, chiavi API e segreti di integrazione.
- Chain-of-thought, ragionamento interno nascosto, prompt raw, log di modello,
  score grezzi, payload tecnici, nomi di variabili, endpoint, stack trace e
  path assoluti locali.
- Documenti o bozze di altri tenant, fallback legacy, copie esportate o file
  temporanei fuori dal perimetro studio.
- File binari originali, PDF firmati, buste telematiche, allegati depositati o
  documenti definitivi come materiale di training automatico.
- Dati personali non necessari alla domanda, coordinate bancarie complete,
  dati sanitari, minori o categorie particolari se bastano sintesi o riferimenti.
- Fonti normative, giurisprudenziali o ministeriali inventate, non verificate
  o non presenti nel corpus ufficiale governato.
- Versioni cancellate o superate quando la domanda chiede la bozza corrente,
  salvo richiesta esplicita di cronologia o confronto.

### Q&A candidate

Le coppie Q&A generate dal dominio atti/redazione sono sempre
`pending_human_review`. Non autorizzano training automatico, salvataggio
definitivo, firma, deposito, esportazione finale o uso di documenti sensibili
fuori dal tenant.

Esempi ammessi:

- "Quale template è più adatto per una diffida stragiudiziale nel fascicolo X?"
- "Prepara una bozza in revisione usando il template selezionato e i dati
  autorizzati del fascicolo."
- "Proponi una modifica al paragrafo sui fatti, indicando quali fonti interne
  sono state usate."
- "Costruisci una checklist fonti prima di trasformare la bozza in documento
  definitivo."
- "Confronta bozza e template e segnala campi mancanti, allegati attesi e punti
  da verificare."
- "Suggerisci clausole o sezioni coerenti con il modello, distinguendo testo
  standard, dati del fascicolo e integrazioni da validare."

Esempi vietati:

- domande che chiedono a Lex di sovrascrivere una bozza o un documento senza
  conferma umana;
- firma digitale, deposito telematico, invio PEC o esportazione definitiva dal
  percorso dataset/RAG;
- creazione di fonti, giurisprudenza, riferimenti normativi o allegati non
  presenti negli archivi autorizzati;
- esportazione di documenti completi o bozze sensibili come training pronto;
- salvataggio di chain-of-thought, prompt nascosti o log di ragionamento;
- training automatico o upload esterno di template, bozze e documenti prodotti.

### Azioni Lex consentite

Lex può:

- selezionare o suggerire template coerenti con materia, rito, fase e dati del
  fascicolo autorizzato;
- preparare una bozza in revisione, marcata come tale e mai come documento
  definitivo;
- proporre modifiche puntuali all'editor, lasciando accettazione, rifiuto e
  salvataggio all'utente autorizzato;
- costruire checklist fonti, campi mancanti, allegati attesi e verifiche prima
  della produzione dell'atto;
- spiegare quali dati provengono da template, fascicolo, comunicazioni,
  documenti allegati o fonti pubbliche ufficiali;
- generare Q&A candidate per revisione umana, senza esportarle come training
  pronto.

Lex non può:

- sovrascrivere, eliminare, rinominare o pubblicare bozze e documenti dal
  percorso dataset/RAG;
- firmare digitalmente, depositare telematicamente, inviare via PEC o esportare
  un atto definitivo;
- inventare fonti, citazioni, allegati, parti, uffici, RG o fatti non presenti
  nelle evidenze autorizzate;
- salvare chain-of-thought, ragionamento interno nascosto o prompt raw nel
  dataset, nel fascicolo o negli audit;
- addestrare automaticamente modelli locali o remoti;
- usare dati di un tenant diverso o fallback globali.

### Privacy, audit e permessi

- Il permesso minimo per leggere template, bozze e documenti è
  `documenti.leggi`; il salvataggio di una bozza tramite workflow applicativo
  richiede `documenti.scrivi` e conferma umana.
- Se la bozza usa fascicoli, clienti, agenda, comunicazioni o scadenze, Lex
  deve verificare anche i permessi dei domini collegati, ad esempio
  `fascicoli.leggi`, `clienti.leggi`, `messaggi.leggi` e `agenda.leggi`.
- Ogni evidenza deve registrare tenant, chiave path (`TEMPLATE_ATTI_DB`,
  `REDACTION_ASSISTANT_DB`, `FASCICOLI_DB`, `FASCICOLI_DOCS`), timestamp di
  costruzione, permessi, stato bozza e classificazione privacy.
- Gli audit registrano fonte, proposta, revisione e azione utente; non
  registrano contenuto integrale non necessario né ragionamento interno.
- Le risposte devono distinguere fatti del fascicolo, testo del template,
  inferenze redazionali, fonti ufficiali e lacune da colmare.

### Test di accettazione

Un'implementazione del dominio atti/redazione è accettabile solo se:

1. in multi-studio senza tenant valido fallisce chiusa e non legge fallback
   globali;
2. `TEMPLATE_ATTI_DB`, `REDACTION_ASSISTANT_DB`, `FASCICOLI_DB` e
   `FASCICOLI_DOCS` derivano dal tenant attivo;
3. il manifest RAG non contiene path assoluti, token, password, PIN di firma,
   certificati, chain-of-thought, prompt raw o file binari originali;
4. le Q&A restano `pending_human_review` e non vengono esportate come training
   pronto;
5. Lex può selezionare template, preparare bozza in revisione, proporre
   modifica e produrre checklist fonti, ma non sovrascrive, firma, deposita,
   invia PEC o esporta documenti definitivi;
6. le risposte distinguono template, dati fascicolo, documenti prodotti, fonti
   ufficiali e lacune;
7. i test coprono almeno un template atti, una bozza redazionale, una proposta
   modifica editor, un documento prodotto con hash, una checklist fonti e un
   tentativo senza tenant valido.

## Pagamenti, fatturazione, preventivi, compensi e timesheet

### Perimetro

| Dominio Lex | Sorgente canonica | Percorso tenant-aware | Permesso minimo | Uso RAG | Uso dataset Q&A |
| --- | --- | --- | --- | --- | --- |
| `fatturazione` | `pct.fatturazione.GestioneFatturazione` via helper applicativi tenant-aware | `FATTURAZIONE_DB` sotto `/data/tenants/<studio>/fatturazione/parcelle.json` | `fatturazione.leggi` | Sì, solo tenant attivo | Solo candidate da revisione |
| `preventivi` | `pct.preventivi.GestionePreventivi` via helper applicativi tenant-aware | `PREVENTIVI_DB` e conferimenti sotto `/data/tenants/<studio>/preventivi/` | `fatturazione.leggi` o permesso preventivi equivalente | Sì, solo tenant attivo | Solo candidate da revisione |
| `pagamenti` | `pct.pagamenti.GestionePagamenti` e bridge pagamenti/impostazioni | `PAGAMENTI_DIR` sotto `/data/tenants/<studio>/pagamenti/` | `pagamenti.leggi` quando configurato, altrimenti `fatturazione.leggi` per riepiloghi collegati | Solo metadati economici autorizzati | Solo candidate da revisione |
| `timesheet_economico` | `pct.timesheet.GestioneTimesheet` e `pct.economic_pipeline` | `TIMESHEET_DB` sotto `/data/tenants/<studio>/timesheet/entries.json` | `fatturazione.leggi` o permesso attività previsto dalla route | Sì, per attività valorizzabili e consuntivi | Solo candidate da revisione |
| `compensi_forensi` | tabelle tariffario e motore compensi forensi | tabelle normative/versionate e profili tenant quando presenti | `fatturazione.leggi` | Solo calcoli e parametri citabili | Solo candidate da revisione |

In ambiente multi-studio il contesto tenant è obbligatorio. Se `g.data_paths`
o il profilo storage equivalente non espongono `FATTURAZIONE_DB`,
`PREVENTIVI_DB`, `TIMESHEET_DB` e, quando necessario, `PAGAMENTI_DIR` del tenant
attivo, Lex deve fallire chiuso e non deve leggere fallback globali come
`./fatturazione/parcelle.json`, `./preventivi/preventivi.json`,
`./timesheet/entries.json` o cartelle pagamenti condivise.

### Campi da includere nel RAG

| Campo logico | Origine | Regola |
| --- | --- | --- |
| Identificativo interno | id parcella, fattura, preventivo, conferimento, link pagamento, voce timesheet | Usare solo come riferimento operativo interno |
| Stato documento | stato preventivo, conferimento, parcella, fattura, pagamento, voce timesheet | Ammesso per distinguere bozza, accettato, emesso, pagato, scaduto, validato o fatturato |
| Importi economici | imponibile, IVA, CPA, ritenuta, totale, incassato, residuo, valore attività | Ammessi solo da repository reale; vietato stimare importi mancanti |
| Date | data preventivo, accettazione, emissione, scadenza, incasso, data attività | Ammesse in formato italiano nelle risposte utente |
| Collegamenti pratica | id fascicolo, cliente, controparte, oggetto incarico, riferimento parcella/preventivo | Ammessi solo se verificati nel tenant corrente |
| Voci e causali | descrizione voce, attività timesheet, minuti/ore, tariffa applicata, fase tariffaria | Ammesse con minimizzazione; utili per bozze descrizione parcella |
| Coerenza economica | relazione preventivo-conferimento-parcella-timesheet-incassi | Ammessa come controllo read-only con evidenza della fonte |
| Pagamenti | stato link, canale, data creazione/scadenza, esito sintetico | Solo metadati non segreti; non includere URL privati se non necessari e autorizzati |

Ogni chunk RAG deve conservare `tenant_id`, `domain`, `source_path_key`,
`record_id`, `status`, `amount_summary`, `currency`, `required_permissions`,
`privacy_classification` e collegamenti verificati a cliente, fascicolo,
preventivo, parcella o voce timesheet. Il testo del chunk deve essere breve,
ma Lex deve mantenere l'inventario completo dei documenti economici rilevanti:
il ranking non deve far credere che non esistano altre parcelle, preventivi,
incassi o attività non valorizzate.

### Campi da escludere

- Chiavi SumUp, Stripe, PagoPA, SDI, API key, webhook secret, token OAuth,
  password, cookie, sessioni e segreti provider.
- IBAN completi, coordinate bancarie complete, codici fiscali o dati fiscali
  non necessari alla domanda.
- URL privati di pagamento, link checkout, ricevute provider complete e payload
  tecnici di incasso quando non servono al riepilogo.
- Path assoluti locali, chiavi `g.data_paths`, route tecniche, stack trace,
  payload grezzi, nomi di variabili e dettagli utili solo a chi programma.
- Dati economici di altri tenant, fallback legacy, copie esportate o record
  cancellati quando la domanda non li menziona.
- Importi ipotetici, sconti, arrotondamenti, interessi, imposte o compensi non
  presenti negli archivi o calcolati da un motore tracciato.

### Q&A candidate

Le coppie Q&A generate dal dominio economico sono sempre
`pending_human_review`. Non autorizzano training automatico, invio esterno,
emissione fiscale, creazione di link pagamento, registrazione incassi o
modifica di importi.

Esempi ammessi:

- "Riepiloga saldo, emesso, incassato e residuo del cliente X."
- "Quali attività validate a timesheet non risultano ancora valorizzate in parcella?"
- "Controlla la coerenza tra preventivo, conferimento, parcella e timesheet del fascicolo X."
- "Prepara una bozza di descrizione parcella usando solo attività e voci autorizzate."
- "Segnala preventivi accettati senza parcella collegata o parcelle emesse senza incasso."

Esempi vietati:

- domande che chiedono a Lex di emettere fatture, note di credito o documenti
  fiscali;
- creazione automatica di link pagamento o invio di richieste di incasso;
- registrazione automatica di incassi, storni, rimborsi o riconciliazioni;
- modifica di importi, aliquote, sconti, stati o coordinate di pagamento;
- esposizione di segreti provider, URL privati o dati economici fuori tenant;
- training automatico o upload esterno di dati economici.

### Azioni Lex consentite

Lex può:

- preparare riepiloghi economici read-only per cliente, fascicolo o studio;
- evidenziare saldo, emesso, incassato, residuo e documenti scaduti usando solo
  dati reali;
- segnalare attività non valorizzate o timesheet validati non ancora fatturati;
- controllare coerenza tra preventivo, conferimento, parcella, timesheet e
  pagamenti;
- proporre una bozza di descrizione parcella, lasciandola in revisione umana;
- indicare lacune documentali o tariffarie senza inventare valori.

Lex non può:

- emettere fatture, parcelle, note di credito o documenti fiscali;
- creare link pagamento, avviare checkout o inviare richieste di pagamento;
- registrare incassi, storni, rimborsi, riconciliazioni o modifiche contabili;
- modificare importi, aliquote, sconti, stati, scadenze economiche o voci
  timesheet;
- mostrare chiavi, token, segreti provider o URL privati di pagamento;
- addestrare automaticamente modelli locali o remoti;
- usare dati di un tenant diverso o fallback globali.

### Privacy, audit e permessi

- Il permesso minimo è `fatturazione.leggi`; i dati di pagamento richiedono
  anche `pagamenti.leggi` quando il modulo è configurato separatamente.
- Le risposte devono minimizzare dati fiscali e bancari, mostrando importi e
  stato solo nella misura necessaria alla domanda.
- Ogni evidenza deve registrare tenant, chiave path (`FATTURAZIONE_DB`,
  `PREVENTIVI_DB`, `TIMESHEET_DB`, `PAGAMENTI_DIR`), timestamp di costruzione,
  permessi e classificazione privacy.
- Le Q&A economiche restano candidate di revisione umana e non possono essere
  esportate come training pronto.
- Gli audit devono registrare consultazione e fonte interna, non payload
  provider o contenuti integrali non necessari.

### Test di accettazione

Un'implementazione del dominio economico è accettabile solo se:

1. in multi-studio senza tenant valido fallisce chiusa e non legge fallback
   globali;
2. `FATTURAZIONE_DB`, `PREVENTIVI_DB`, `TIMESHEET_DB` e `PAGAMENTI_DIR`
   derivano dal tenant attivo;
3. il manifest RAG non contiene path assoluti, token, password, segreti
   provider, URL privati di pagamento o payload tecnici;
4. le Q&A restano `pending_human_review` e non vengono esportate come training
   pronto;
5. Lex non emette fatture, non crea link pagamento, non registra incassi e non
   modifica importi dal percorso RAG;
6. riepilogo saldo, attività non valorizzate, controllo coerenza
   preventivo-parcella-timesheet e bozza descrizione parcella distinguono dati
   archiviati, calcoli tracciati e lacune;
7. i test coprono almeno una parcella emessa, un preventivo accettato, un
   timesheet validato non fatturato, un pagamento con segreti esclusi e un
   tentativo senza tenant valido.

## Sito Studio, contatti, prenotazioni e contenuti pubblici

### Perimetro

| Dominio Lex | Sorgente canonica | Percorso tenant-aware | Permesso minimo | Uso RAG | Uso dataset Q&A |
| --- | --- | --- | --- | --- | --- |
| `sito_studio` | repository Sito Studio tramite `web.services.studio_site_runtime` e bridge `web.services.react_sito_studio_bridge` | `SITE_STUDIO_DB` del tenant attivo; PostgreSQL tenant-aware quando configurato | utente autenticato dello studio per bozze e dashboard; nessun permesso per sole pagine già pubbliche | Sì, con separazione tra pubblico e riservato allo studio | Solo candidate da revisione |
| `sito_studio_contatti` | tabella `site_contact_submission` e payload `/api/v1/ui/sito-studio/contatti` | `SITE_STUDIO_DB` del tenant attivo | `admin.configura` per collegamenti/gestione; lettura dashboard solo utente autorizzato dello studio | Sì, per riepilogo richieste e lacune operative | Solo candidate da revisione |
| `sito_studio_prenotazioni` | tabella `site_booking_request`, regole prenotazione e sync agenda `external_provider=site_studio` | `SITE_STUDIO_DB` più `AGENDA_DB` del tenant attivo solo quando la prenotazione è approvata | `admin.configura` per approvare/rifiutare; `agenda.leggi` se Lex usa eventi agenda collegati | Sì, per stato richieste e conflitti da verificare | Solo candidate da revisione |
| `sito_studio_asset_pubblici` | asset caricati dal CMS e riferimenti nel repository sito | `SITE_STUDIO_ASSETS_DIR` sotto il tenant attivo, cartelle `site_assets/<public_slug>/` | utente autenticato dello studio; accesso anonimo solo agli asset già pubblicati | Solo metadati e testo alternativo, non binari | No, salvo esempi revisionati senza file originali |
| `sito_studio_bozze_redazionali` | pagine, articoli, servizi, professionisti, sedi e revisioni design non pubblicate | `SITE_STUDIO_DB` del tenant attivo | utente autenticato con permesso editoriale/configurazione sito | Sì, come contesto riservato in revisione | Solo candidate da revisione |

In ambiente multi-studio il contesto tenant è obbligatorio. Se la sessione,
`g.data_paths` o il profilo storage equivalente non espongono `SITE_STUDIO_DB`
e, quando servono asset, `SITE_STUDIO_ASSETS_DIR` del tenant attivo, Lex deve
fallire chiuso. Non deve leggere fallback globali, copie locali di altri studi,
cartelle condivise, export pubblici o path derivati dal solo `public_slug`.

### Campi da includere nel RAG

| Campo logico | Origine | Regola |
| --- | --- | --- |
| Identificativo interno | id sito, pagina, articolo, servizio, professionista, sede, contatto, prenotazione | Usare solo come riferimento operativo interno |
| Stato pubblicazione | `is_published`, `is_active`, `status`, `is_visible`, flag opzionali | Ammesso per distinguere contenuti pubblici, bozze, sezioni nascoste e pagine da completare |
| Contenuti pubblici | titolo, slug, claim, descrizione, estratto, blocchi testuali sanificati, servizi, professionisti e sedi già pubblicati | Ammessi come conoscenza pubblica dello studio, senza inventare specializzazioni o sedi |
| Bozze redazionali | pagine, articoli, servizi, professionisti, sedi, revisioni design, warning SEO/privacy/accessibilità | Ammesse solo come contesto riservato e marcate `draft` o `internal_review` |
| Richieste contatto | nome, email, telefono, oggetto, messaggio, data, stato, eventuale lead cliente collegato | Dati personali: usare per riepilogo richieste e prossima azione, con minimizzazione |
| Prenotazioni | nome richiedente, email, telefono, sede, data, ora, oggetto, note, stato, eventuale `agenda_event_id` | Dati personali: usare per riepilogo e controlli, non per confermare appuntamenti automaticamente |
| Asset pubblici | nome file sanitizzato, tipo MIME, dimensione, hash, testo alternativo, stato pubblicazione, riferimento pagina | Ammessi come metadati; non esportare binari nel dataset |
| Privacy e SEO | cookie/analytics, consenso, privacy policy, contatti mancanti, titoli o descrizioni mancanti, immagini senza testo alternativo | Ammessi come lacune operative da segnalare |
| Collegamenti applicativi | `public_slug`, URL pubblico, route dashboard, collegamento a cliente, collegamento agenda | Ammessi se derivati dal tenant corrente e senza token o URL privati |

Ogni chunk RAG deve conservare `tenant_id`, `domain`, `source_path_key`,
`record_id`, `public_slug`, `publication_status`, `required_permissions`,
`privacy_classification`, `source_table`, timestamp di costruzione e, se
presente, collegamento verificato a cliente o agenda. Il testo del chunk deve
separare chiaramente contenuto pubblico, bozza interna e richiesta privata:
Lex non deve presentare una bozza come pagina pubblicata né una richiesta
contatto come testimonianza o dato pubblicabile.

### Campi da escludere

- Password, token, segreti analytics, chiavi API, credenziali DNS, cookie,
  sessioni, webhook secret, provider secret e configurazioni di hosting.
- Path assoluti locali, chiavi `g.data_paths`, payload tecnici, stack trace,
  nomi di variabili, endpoint interni e dettagli utili solo a chi programma.
- Asset binari originali, immagini complete, documenti caricati e file privati
  non pubblicati; il dataset può contenere solo metadati e hash.
- Messaggi contatto o note prenotazione integrali quando basta un riepilogo
  operativo; dati sanitari o giudiziari dichiarati dal richiedente vanno
  classificati almeno `highly_sensitive`.
- Contenuti di altri tenant, siti dismessi, export pubblici non collegati al
  tenant corrente o copie locali ricavate dal solo slug pubblico.
- Servizi, sedi, professionisti, recensioni, certificazioni o partnership non
  presenti nel repository reale dello studio.

### Q&A candidate

Le coppie Q&A generate dal dominio Sito Studio sono sempre
`pending_human_review`. Non autorizzano training automatico, pubblicazione
automatica, risposta ai contatti o modifica della configurazione pubblica.

Esempi ammessi:

- "Riepiloga le richieste contatto arrivate dal sito questa settimana."
- "Quali prenotazioni pubbliche sono in attesa di approvazione?"
- "Elenca le bozze non pubblicate e indica cosa manca per renderle pronte."
- "Segnala lacune privacy, cookie, accessibilità o SEO del sito studio."
- "Prepara una bozza di testo per la pagina servizi usando solo servizi già
  registrati nello studio."
- "Verifica se una pagina pubblica cita sedi, professionisti o recapiti non
  coerenti con i dati del sito."

Esempi vietati:

- domande che chiedono a Lex di pubblicare pagine, articoli, servizi o modifiche;
- modifica di DNS, dominio, hosting, slug pubblico, template o flag di
  esposizione pubblica;
- risposta automatica a richieste contatto, prenotazioni, email, SMS o WhatsApp;
- approvazione/rifiuto automatico di prenotazioni o creazione di eventi agenda;
- invenzione di servizi, sedi, professionisti, qualifiche, recensioni o risultati;
- training automatico o upload esterno di contatti, prenotazioni, asset o bozze.

### Azioni Lex consentite

Lex può:

- riassumere richieste contatto e prenotazioni autorizzate, distinguendo dati
  certi, stato corrente e prossima verifica umana;
- preparare elenchi di bozze non pubblicate, pagine incomplete e contenuti da
  revisionare;
- segnalare lacune privacy, cookie, SEO, accessibilità, recapiti e coerenza
  editoriale del sito;
- proporre bozze redazionali basate solo su servizi, professionisti, sedi e
  contenuti già presenti nel tenant;
- suggerire collegamenti da verificare verso cliente o agenda, senza eseguirli;
- citare le fonti interne come evidenza riservata o pubblica secondo lo stato
  della pagina.

Lex non può:

- pubblicare, ritirare, modificare o eliminare pagine, articoli, servizi,
  professionisti, sedi, template, design o asset;
- modificare DNS, dominio, slug pubblico, hosting, template, flag pubblici,
  analytics o impostazioni cookie;
- rispondere ai contatti, inviare comunicazioni o confermare appuntamenti;
- approvare/rifiutare prenotazioni o creare eventi agenda dal percorso RAG;
- inventare servizi, sedi, professionisti, qualifiche, recensioni, partnership
  o risultati dello studio;
- addestrare automaticamente modelli locali o remoti;
- usare dati di un tenant diverso o fallback globali.

### Privacy, audit e permessi

- La lettura di contenuti già pubblici può essere usata come fonte pubblica
  dello studio; bozze, contatti, prenotazioni e asset non pubblicati restano
  riservati al tenant.
- Il riepilogo di contatti e prenotazioni richiede utente autenticato dello
  studio; azioni operative come collegamento cliente o approvazione prenotazione
  restano fuori dal RAG e richiedono il workflow applicativo con permessi
  specifici, ad esempio `admin.configura`.
- Se Lex usa clienti, fascicoli o agenda collegati deve possedere anche i
  permessi dei domini collegati, ad esempio `clienti.leggi`, `fascicoli.leggi`
  o `agenda.leggi`.
- Ogni evidenza deve registrare tenant, `SITE_STUDIO_DB`,
  `SITE_STUDIO_ASSETS_DIR` quando usato, tabella sorgente, stato
  pubblicazione, permessi e classificazione privacy.
- Le risposte devono minimizzare dati personali di contatti e prenotazioni e
  dichiarare lacune, contenuti non pubblicati o dati da verificare prima di
  qualsiasi uso esterno.

### Test di accettazione

Un'implementazione del dominio Sito Studio è accettabile solo se:

1. in multi-studio senza tenant valido fallisce chiusa e non legge fallback
   globali o cartelle di altri studi;
2. `SITE_STUDIO_DB` e `SITE_STUDIO_ASSETS_DIR` derivano dal tenant attivo;
3. il manifest RAG distingue contenuti pubblici, bozze interne, contatti,
   prenotazioni e asset metadati;
4. il manifest non contiene path assoluti, token, password, segreti DNS,
   webhook secret, asset binari o payload tecnici;
5. le Q&A restano `pending_human_review` e non vengono esportate come training
   pronto;
6. Lex non pubblica pagine, non modifica DNS, non risponde ai contatti, non
   approva prenotazioni e non crea eventi agenda dal percorso RAG;
7. riepilogo richieste, elenco bozze non pubblicate e audit privacy/SEO
   distinguono fatti archiviati, contenuti pubblicati e lacune;
8. i test coprono almeno una pagina pubblicata, una bozza non pubblicata, una
   richiesta contatto, una prenotazione in attesa, un asset pubblico con hash e
   un tentativo senza tenant valido.

## Privacy, GDPR, audit e amministrazione

### Perimetro

| Dominio Lex | Sorgente canonica | Percorso tenant-aware | Permesso minimo | Uso RAG | Uso dataset Q&A |
| --- | --- | --- | --- | --- | --- |
| `privacy_gdpr` | registro trattamenti e route privacy governate | `PRIVACY_DB` o archivio trattamenti sotto `/data/tenants/<studio>/privacy/` | `utenti.leggi` più permesso privacy/GDPR applicativo quando configurato | Sì, per riepilogo lacune e checklist non distruttive | Solo candidate da revisione |
| `audit_log` | `pct.auth.GestioneUtenti.audit_log()` e audit applicativo/WORM quando configurato | `AUDIT_DB` sotto `/data/tenants/<studio>/auth/audit.json` o indice audit tenant | `audit.leggi` | Sì, solo eventi e metadati autorizzati | Solo candidate da revisione |
| `utenti_profili` | `pct.auth.GestioneUtenti`, `RuoloUtente`, permessi effettivi | `AUTH_DB` sotto `/data/tenants/<studio>/auth/utenti.json` o tabella tenant in `studio.db` | `utenti.leggi` | Sì, solo stato autorizzativo e profili non segreti | Solo candidate da revisione |
| `database_admin` | superfici amministrative e diagnostica storage tenant-aware | `STUDIO_DB`, configurazione database tenant e metadati non segreti | `database.leggi` o permesso amministrativo equivalente | Solo stato, schema logico e lacune operative | No, salvo esempi revisionati senza segreti |
| `registro_gdpr` | esporti GDPR, portabilità e registro attività privacy | archivi privacy e audit del tenant attivo | `utenti.leggi` più permesso privacy/GDPR applicativo quando configurato | Sì, per controllo registro e diritti interessato | Solo candidate da revisione |

In ambiente multi-studio il contesto tenant è obbligatorio. Se `g.data_paths`
o il profilo storage equivalente non espongono `AUTH_DB`, `AUDIT_DB` e gli
archivi privacy del tenant attivo, Lex deve fallire chiuso e non deve leggere
fallback globali come `./auth/utenti.json`, `./auth/audit.json`,
`./privacy/registro.json`, `/data/auth/utenti.json` o `/data/auth/audit.json`.

Questa sezione definisce conoscenza amministrativa per assistenza read-only:
non autorizza training automatico, invio esterno, modifica di utenti, cambio
ruoli, cancellazione audit, restore, migrazione automatica o scrittura di dati
amministrativi.

### Campi da includere nel RAG

| Campo logico | Origine | Regola |
| --- | --- | --- |
| Identificativo interno utente | `Utente.id` | Ammesso solo come riferimento interno tenant-aware |
| Profilo e stato | ruolo, `attivo`, `must_change_password`, ultimo accesso | Ammessi per spiegare stato autorizzativo e lacune, senza credenziali |
| Permessi effettivi | `permessi_effettivi()`, `permessi_extra`, `permessi_negati` | Ammessi come elenco operativo; evidenziare override e conflitti |
| Dati di contatto minimi | nome, cognome, email di lavoro | Ammessi solo se necessari alla domanda amministrativa |
| Audit evento | timestamp, azione, risorsa_tipo, risorsa_id, esito, IP troncato o normalizzato | Ammessi per spiegazione audit e controllo registro |
| Dettagli audit sintetici | `dettagli` già sanitizzati | Ammessi solo se non contengono segreti, payload o dati personali eccedenti |
| Registro trattamenti | finalità, base giuridica, categorie dati, interessati, responsabili, conservazione, misure, stato | Ammessi per riepilogo lacune GDPR e checklist |
| Diritti interessato | portabilità, informativa, consenso, export effettuati | Ammessi come stato e prova operativa, non come export automatico |
| Stato database | tipo archivio, modalità attiva, health sintetico, tabelle/logical collections, backup disponibili | Solo metadati non segreti e non distruttivi |
| Provenienza | `tenant_id`, `source_path_key`, permesso richiesto, timestamp costruzione | Obbligatoria per ogni evidenza amministrativa |

Ogni chunk RAG deve conservare `tenant_id`, `domain`, `source_path_key`,
`record_id`, `required_permissions`, `privacy_classification`,
`access_purpose`, `built_at` e, per gli audit, `audit_action`,
`resource_type`, `event_at` ed `outcome`. Il testo del chunk deve essere
minimizzato: Lex deve poter spiegare il registro o le lacune, non duplicare
interi archivi amministrativi nel prompt.

### Campi da escludere

- Hash password, password temporanee, password applicative, salt, token TOTP,
  segreti 2FA, reset token, recovery code, API key, cookie, sessioni e token
  OAuth.
- Chiavi private o pubbliche di firma audit quando non necessarie, segreti WORM,
  credenziali database, DSN completi, password Postgres, access key S3/MinIO e
  webhook secret.
- Payload tecnici grezzi, stack trace, path assoluti locali, route interne,
  nomi di variabili, endpoint, dump SQL, backup binari e file di migrazione.
- Dati personali non necessari alla verifica richiesta, audit integrali quando
  basta un riepilogo, IP completi se non autorizzati e dati di altri tenant.
- Record cancellati, sospesi o storici quando la domanda non li menziona e non
  vi è una ragione professionale esplicita per recuperarli.
- Qualunque materiale destinato a training automatico, invio esterno o
  sincronizzazione non supervisionata.

### Q&A candidate

Le coppie Q&A generate da privacy, GDPR, audit e amministrazione sono sempre
`pending_human_review`. Non autorizzano training automatico, upload esterno,
creazione utenti, cambio ruoli, esportazione audit completa, restore o
migrazione automatica.

Esempi ammessi:

- "Riepiloga le lacune del registro GDPR dello studio e indica quali campi
  mancano."
- "Controlla se il registro trattamenti contiene finalità, base giuridica,
  categorie dati, tempi di conservazione e misure di sicurezza."
- "Spiega gli eventi audit dell'utente X negli ultimi sette giorni, senza
  mostrare dati riservati non necessari."
- "Quali utenti hanno permessi personalizzati e quali override vanno
  verificati dal titolare?"
- "Prepara una checklist non distruttiva prima di un controllo privacy."
- "Segnala se il database tenant appare configurato in modo coerente e quali
  verifiche manuali restano aperte."

Esempi vietati:

- domande che chiedono a Lex di creare utenti, disattivarli, cambiare ruolo o
  modificare permessi;
- cancellazione, riscrittura, compattazione o esportazione completa del log
  audit dal percorso RAG;
- esposizione di hash, password, token, segreti 2FA, DSN, chiavi o backup;
- restore, migrazione automatica, repair del database o modifica dello schema;
- invio esterno di registri GDPR, audit o archivi amministrativi;
- training automatico locale o remoto su dati amministrativi.

### Azioni Lex consentite

Lex può:

- preparare un riepilogo lacune del registro GDPR, distinguendo campi presenti,
  mancanti e da verificare;
- controllare il registro trattamenti in sola lettura e produrre una checklist
  non distruttiva;
- spiegare eventi audit autorizzati, minimizzando dati personali e segreti;
- evidenziare utenti inattivi, accessi recenti, permessi personalizzati e
  override da verificare;
- descrivere lo stato amministrativo del database come metadato operativo,
  senza eseguire restore, migrazioni o repair;
- proporre Q&A candidate per revisione umana con fonti tenant-aware e stato
  `pending_human_review`.

Lex non può:

- creare utenti, modificare profili, cambiare ruoli, attivare o disattivare
  account;
- cambiare permessi, rimuovere override, azzerare password o generare token;
- cancellare, riscrivere, comprimere, ruotare o esportare integralmente audit;
- mostrare hash password, password, token, recovery code, sessioni, DSN,
  chiavi, segreti provider o payload tecnici;
- avviare restore, migrazione automatica, modifica schema, repair database o
  comandi amministrativi;
- addestrare automaticamente modelli locali o remoti;
- usare dati di un tenant diverso o fallback globali.

### Privacy, audit e permessi

- Il permesso minimo per consultare utenti e profili è `utenti.leggi`.
- Il permesso minimo per consultare audit è `audit.leggi`; l'esportazione resta
  fuori dal RAG e richiede workflow applicativo separato.
- Il dominio database richiede `database.leggi` o permesso amministrativo
  equivalente, ma Lex deve limitarsi a metadati e lacune non distruttive.
- Ogni evidenza deve registrare tenant, chiave path (`AUTH_DB`, `AUDIT_DB`,
  `PRIVACY_DB`, `STUDIO_DB`), timestamp di costruzione, permessi richiesti,
  classificazione privacy e finalità della consultazione.
- Le risposte devono separare fatti archiviati, inferenze operative e lacune;
  non devono presentare una conformità GDPR come certa se mancano campi,
  registri, audit o verifica umana.
- Gli audit di consultazione Lex devono registrare fonte e scopo, non contenuti
  integrali non necessari.

### Test di accettazione

Un'implementazione del dominio privacy/GDPR/audit/amministrazione è accettabile
solo se:

1. in multi-studio senza tenant valido fallisce chiusa e non legge fallback
   globali;
2. `AUTH_DB`, `AUDIT_DB`, `PRIVACY_DB` e `STUDIO_DB` derivano dal tenant attivo
   o da un repository tenant-aware equivalente;
3. il manifest RAG non contiene path assoluti, hash password, password, token,
   segreti 2FA, DSN, chiavi, dump SQL, backup binari o payload tecnici;
4. le Q&A restano `pending_human_review` e non vengono esportate come training
   pronto;
5. Lex non crea utenti, non cambia ruoli, non modifica permessi, non cancella audit,
   non avvia restore e non esegue migrazioni dal percorso RAG;
6. riepilogo lacune GDPR, controllo registro, spiegazione audit, checklist
   non distruttiva e verifica permessi distinguono dati archiviati, inferenze
   operative e lacune;
7. i test coprono almeno un registro trattamenti incompleto, un evento audit,
   un utente con permessi personalizzati, un profilo database senza segreti e
   un tentativo senza tenant valido.

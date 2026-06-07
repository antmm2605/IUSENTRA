# LEX — Audit: Fonti Pubbliche e Dati Studio (v2.201.0)

Documento di audit tecnico sul comportamento attuale di Lex nella gestione delle fonti pubbliche (sentenze, normativa, giurisprudenza) e dei dati interni dello studio (clienti, fascicoli, anagrafica).

## Aggiornamento gate reali Lex/RAG/Ricerca Legale - 7 giugno 2026

Le verifiche di Lex non possono più limitarsi a controlli di presenza, conteggi
o risposte tecnicamente non vuote. Ogni lavoro su RAG, fonti, fascicoli,
scadenziario, PEC o Ricerca Legale deve superare domande reali dell'avvocato e
produrre una risposta professionalmente utilizzabile.

Gate introdotti:

- la domanda sulla fonte correttiva Cartabia civile deve restituire fonti
  ufficiali e pratica legale, inclusi D.Lgs. 149/2022, D.Lgs. 164/2024 e uso
  operativo su rito, famiglia, esecuzione, notifiche e ADR;
- la domanda sulla sintesi del fascicolo attivo deve produrre inquadramento,
  documenti chiave, rischi, cosa manca e prossimi passi, non solo estratti OCR o
  metadati;
- la domanda sulla prova completa di una notifica deve leggere la PEC Control
  Tower reale dello studio, risolvere gli alias tenant autorizzati e mostrare
  accettazione, consegna, orari italiani e destinatari quando presenti;
- le domande sulle PEC ricevute `oggi` devono confrontare la data convertita in
  `Europe/Rome`, non il prefisso testuale della data salvata in UTC;
- la Ricerca Legale deve pubblicare riferimenti nominali e filtrabili per
  materia, inclusi precedenti Corte costituzionale, Cassazione Sezioni Unite e
  Consiglio di Stato, senza sostituirli con categorie generiche.

Audit di riferimento:
`artifacts/legal-sources/legal-work-real-gates-2026-06-07.md`.

Verifiche eseguite: test mirati su Cartabia, fascicolo scolastico/MIM, tenant
alias PEC, prova completa, Ricerca Legale e audit matrice pratica. Sul database
reale locale `pec_control_tower.sqlite`, Lex risolve l'alias dati
`tenant-8bf98719c459` e la domanda `Qual è la prova completa di questa
notifica?` non torna più a zero quando le ricevute sono presenti.

## Aggiornamento Centro Fonti Ufficiali Lex e pacchetto giuridico minimo - 6 giugno 2026

Aggiornamento di revisione estesa dello stesso giorno: una consegna non puo'
essere dichiarata chiusa solo perche' una fonte risulta censita. Lex deve
superare domande reali dell'avvocato, compresa la domanda "Fonte correttiva
collegata alla riforma civile Cartabia per controllare rito, decorrenze,
famiglia, esecuzione, notifiche e ADR". Questa domanda deve andare alla route
fonti ufficiali/pratica legale, non alla route notifiche interne, e deve
restituire D.Lgs. 164/2024, D.Lgs. 149/2022, uso operativo, atti/scadenze
collegati e limite professionale.

La matrice pratica deve inoltre includere precedenti nominativi utili alla
strategia, non frasi generiche su "giurisprudenza". Ogni sentenza o udienza che
entra nel perimetro deve avere autorita', numero, URL ufficiale, data di
verifica, passaggi pratici, domanda Lex e destinazione Ricerca Legale/Lex/RAG.
Se un precedente, fonte, decreto, udienza o collegamento manca, il lavoro resta
da completare: non va sostituito da categoria astratta, nota generica o invito
all'avvocato a verificare da solo.

Il Centro Fonti Ufficiali Lex non è più solo un elenco di sorgenti: lo script
`scripts/audit_legal_source_delivery.py` attraversa configurazione fonti,
Legal Source Engine, policy ricerca, motore aggiornamenti, registri Template
Atti, Guida Pratica, DB normativa e sorgenti operative Lex, poi produce audit
JSON/CSV/Markdown in `artifacts/legal-sources/`.

Aggiornamento operativo dello stesso giorno: il motore aggiornamenti legali
riusa l'audit Centro Fonti anche nel monitor visibile in Ricerca Legale. Ogni
fonte monitorata espone ora uso per l'avvocato, fase pratica, output atteso,
azione richiesta, fonte ufficiale, materiali giuridici, articoli/codici,
decreti o regole tecniche, sentenze/udienze/provvedimenti e domanda Lex di
prova. In questo modo il Centro Fonti non resta invisibile: l'avvocato vede cosa
controllare, quale lacuna chiudere e quale ricerca far eseguire a Lex.

Stato audit del 6 giugno 2026: 402 fonti censite, 357 ufficiali, 343 operative
e controllabili, 14 controllabili ma da attivare, 45 fonti di contesto non
ufficiale, 0 buchi reali e 0 buchi su fonti ufficiali. Tutte le 402 righe
espongono il pacchetto giuridico minimo: materiali giuridici, articoli/codici,
decreti e regole tecniche, sentenze/udienze/provvedimenti e sequenza di
ricerca.

Il pacchetto minimo serve a rispondere come un avvocato: quale legge o decreto
usare, quale D.Lgs. o D.M. controllare, quali articoli di codice civile,
procedura civile, penale, procedura penale, processo amministrativo, tributario
o norme speciali collegare, quali prassi dell'autorità competente considerare,
quali sentenze, ordinanze, decreti, verbali o udienze incidono su strategia,
prova, termine o rischio.

Ricerca Legale espone queste righe come record `source-delivery:*` con
`legalMaterials`, `articlesAndCodes`, `decreesAndRules`,
`caseLawAndHearings` e `researchSteps`. Lex/RAG usa gli stessi campi quando la
domanda riguarda fonti ufficiali, codici, decreti legislativi, decreti
ministeriali, sentenze o udienze: la risposta non deve più fermarsi a "fonte
presente", ma deve indicare cosa controllare e come collegarlo al fascicolo,
modello, scadenza, prova o strategia.

Verifiche mirate: `tests/test_audit_legal_source_delivery.py`,
`tests/test_react_legal_intelligence_search.py::test_ricerca_legale_espone_centro_fonti_ufficiali_lex`,
`tests/test_react_legal_intelligence_search.py::test_ricerca_legale_cerca_centro_fonti_senza_fallback_live`
e `tests/test_lex_operational_knowledge.py::test_lex_fonti_ufficiali_risponde_con_codici_decreti_sentenz_udienze`.

## Aggiornamento DB normativa, Ricerca Legale e tassi usura - 6 giugno 2026

Il DB normativa non è più trattato come semplice archivio tecnico: Ricerca
Legale espone le tabelle e i riferimenti strutturati come record
`normative-table:*` e `normative-reference:*`, mentre Lex/RAG li legge come
fonti operative per calcoli, soglie, controlli modello, scadenziario e domande
dell'avvocato. La ricerca su DB normativa non deve bloccare il fallback pubblico
quando trova solo fonti generiche non pertinenti alla domanda specifica.

La tabella `tasso_usura` è stata riallineata alle fonti ufficiali vigenti alla
data del 6 giugno 2026. Il Q1 2026 è collegato al D.M. MEF 23 dicembre 2025,
pubblicato in G.U. n. 302 del 31 dicembre 2025, codice redazionale `25A07045`;
il Q2 2026 è collegato al D.M. MEF 27 marzo 2026, pubblicato in G.U. n. 75 del
31 marzo 2026, codice redazionale `26A01653`. Le fonti generali restano Banca
d'Italia TEGM e MEF anti-usura, ma la citazione operativa deve indicare il
decreto trimestrale specifico applicabile alla data dell'operazione.

Copertura tabellare attuale: 48 righe, cioè 24 categorie ufficiali Q1 2026 e 24
categorie ufficiali Q2 2026. Le categorie coperte sono aperture di credito in
conto corrente fino/oltre EUR 5.000, scoperti senza affidamento fino/oltre EUR
1.500, anticipi e sconti su crediti per tre fasce, credito personale, credito
finalizzato, factoring fino/oltre EUR 50.000, leasing immobiliare fisso e
variabile, leasing aeronavale/autoveicoli fino/oltre EUR 25.000, leasing
strumentale fino/oltre EUR 25.000, mutui ipotecari fisso e variabile, cessione
del quinto fino/oltre EUR 15.000, credito revolving, carte di credito e altri
finanziamenti. Il vecchio codice UI `carte_credito_revolving` viene ricondotto
alla categoria ufficiale `credito_revolving` senza interrompere pratiche o form
salvati.

Uso operativo richiesto a Lex: quando l'avvocato chiede se un tasso è usurario,
Lex deve scegliere il trimestre dalla data dell'operazione, mostrare TEGM,
soglia, categoria ufficiale, fonte GU specifica, margine rispetto alla soglia e
limite professionale della verifica. Quando la data non rientra in Q1/Q2 2026,
il sistema deve usare la riga vigente più vicina solo come fallback prudente e
deve mantenere l'obbligo di aggiornamento trimestrale.

Verifiche eseguite: `tests/test_normative_tables.py` controlla Q1/Q2, fonte GU
specifica, selezione per data e alias storico; `tests/test_strumenti_legali.py`
controlla lo strumento di verifica usura su Q2 2026; i test Ricerca Legale/Lex
confermano che il DB normativa è ricercabile e non maschera ricerche pubbliche
quando l'archivio interno non copre davvero la domanda.

## Aggiornamento fonti Template Atti, Ricerca Legale e RAG - 6 giugno 2026

La copertura Template Atti è stata portata su audit severo: 1512/1512 righe
modello OK tra catalogo unificato e compilatore atti, 0 problemi modello e 0
problemi fonte nel report
`artifacts/template-atti/template-atti-official-sources-audit-2026-06-06.md`.
La fonte `base_comune` non chiude più la copertura: ogni modello deve avere
almeno una fonte professionale valida e almeno una fonte collegata, tecnica,
attuativa, deontologica o di autorità competente.

Le ricerche web ufficiali sono versionate in
`docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-06.md` e vengono
pubblicate anche in Ricerca Legale come record `template-atti-source:*`, con
URL ufficiale, autorità, data di consultazione, ruolo, ambito, prefissi modello,
termini di attivazione, limiti e controlli operativi. Lex/RAG può usarle come
fonti di presidio redazionale, distinguendo norma primaria, fonte secondaria,
regola telematica, fonte deontologica, autorità competente, fonte transitoria e
punto da verificare dall'avvocato.

La copertura include fonti primarie e collegate: Normattiva per codici, leggi,
decreti legislativi e correttivi; D.M. 44/2011, D.M. 217/2023, art.
196-quater disp. att. c.p.c. e specifiche PST/PCT/PDP; PAT e PTT; D.Lgs.
216/2024 e D.M. 150/2023 per ADR; Banca d'Italia ABF, Consob ACF, IVASS/AAS,
AGCOM ConciliaWeb, ANAC, Garante Privacy/EUR-Lex; UIBM/MIMIT, SIAE, Agenzia
Entrate/RLI Web, Ministero dell'Interno e Commissione nazionale asilo; Codice
deontologico, ordinamento forense, parametri ed equo compenso.

## Aggiornamento isolamento tenant e sorgenti Lex - 6 giugno 2026

Lex non deve trattare il pannello `Scadenze dai PDF` come unica lettura dello
studio: quel pannello è solo un importatore mirato che cerca date nei PDF dei
fascicoli. Il ragionamento operativo deve invece combinare sorgenti interne
tenant-aware distinte: PEC, PEC Control Tower, fascicoli, documenti fascicolo,
scadenziario, agenda, notifiche/prove e registri collegati.

Ogni sorgente deve risolversi dal tenant corrente tramite i path applicativi
dedicati (`EMAIL_CASELLA_DB`, `PEC_CONTROL_TOWER_DB`, `FASCICOLI_DB`,
`FASCICOLI_DOCS`, `SCADENZIARIO_DB`, `AGENDA_DB`, `NOTIFICATIONS_DB`) e non deve
leggere archivi globali o di altri studi. Il controllo read-only
`scripts/audit_lex_tenant_sources.py` conta le sorgenti disponibili per ogni
tenant e segnala se una Control Tower contiene righe con `tenant_id` non
collegato allo studio. Il controllo legge `tenant_user_directory.json` e accetta
solo gli alias registrati dello stesso studio (`tenant_slug`,
`tenant_storage_key`, `tenant_id`); qualunque identificativo estraneo resta una
violazione bloccante dell'isolamento dati.

Per le domande PEC operative, Lex deve prima verificare che la PEC Control Tower
sia alimentata dalla casella PEC reale del tenant corrente. Se una risposta
risulterebbe vuota, Lex tenta un backfill idempotente dai MIME già salvati in
`email/casella.json`, senza usare dati di altri studi e senza inventare
scadenze o prove assenti.

Per le domande sul fascicolo attivo, Lex deve ricevere o ricostruire il contesto
del fascicolo aperto (`caseId`, `clientId`, `pagePath`) prima del routing. La
sintesi operativa non deve limitarsi al conteggio dei documenti indicizzati:
quando la domanda chiede documenti chiave, rischi aperti, cosa manca o prossimi
passi, la risposta deve includere gli estratti leggibili già presenti nel RAG
DocumentAI/fascicolo e dichiarare i limiti delle fonti mancanti senza inventare
contenuti.

## Aggiornamento PEC Control Tower - 6 giugno 2026

`pec_control_tower` è una sorgente interna dello studio. Non è fonte pubblica e
non sostituisce la valutazione professionale: raccoglie MIME PEC, ricevute,
`daticert.xml`, allegati, fascicolo, scadenze in bozza, task, notifiche e prove
per permettere a Lex di rispondere a domande operative sullo stato della pratica.

Lex deve usare prima questa sorgente quando la domanda riguarda PEC ricevute che
generano scadenze, notifiche da fare, invii senza consegna, termini non
confermati, atti di cancelleria, comunicazioni PA, notifiche fallite, prova
completa o rischio di decadenza. Le fonti normative mostrate restano cornice da
verificare sul caso concreto e non trasformano una bozza di presidio in termine
legale definitivo.

## Aggiornamento Template Atti e fonti ufficiali - 4 giugno 2026

Il pannello `Fonti` dell'editor template atti usa un registry dedicato,
`pct/template_atti_legal_sources.py`, con riferimenti ufficiali a Normattiva per
Codice civile e Codice di procedura civile ed EUR-Lex per il GDPR. Il testo
normativo non viene copiato automaticamente nel documento: Lex e il pannello
fonti propongono solo riferimenti inseribili su azione dell'avvocato, mantenendo
la regola di revisione manuale e accettazione esplicita.

La direttiva è versionata in
`docs/specs/ministero/TEMPLATE_ATTI_FONTI_UFFICIALI_2026-06-04.md` con data di
consultazione, ambito e limite: fonti certe come riferimento, nessuna ricerca web
silenziosa, nessuna modifica automatica del template e nessun invio a provider
esterni senza policy privacy esplicita.

## Aggiornamento operativo 2.248.26 - 2026-05-24

I risultati della nuova pipeline `PEC -> analisi -> OCR -> Lex` restano dati interni dello studio, non fonti pubbliche. L'evento `lex.ingest.doc` arriva solo dopo catena di custodia WORM, controllo antivirus, verifica firma, estrazione ZIP governata, dedup SHA-256 e `ocr.result`; il payload deve conservare citazione, checksum, confidenza OCR, `run_id`, tenant e candidato fascicolo.

Quando un allegato è duplicato, bloccato, in quarantena o da revisionare, Lex deve usare lo stato tecnico come limite probatorio e chiedere verifica dell'avvocato. La risposta su una PEC o sui suoi allegati deve partire da queste evidenze interne e non da fonti web o cataloghi generici.

## Aggiornamento operativo 2.248.25 - 2026-05-23

La Guida Pratica incorpora anche le due consegne TOP9 set7 ricevute dall'utente. La base completa sale a 1.087 schede: 1.018 codici ufficiali PST/XSD restano coperti e depositabili, mentre 69 schede sono guide interne non depositabili. `011001` e `170001` restano codici ufficiali; gli altri codici set7 non coerenti o assenti sono conservati come alias interni con `codice_originale_ricevuto`.

Lex riceve le nuove schede come conoscenza pratica conversazionale: sequestro conservativo, nullità/decadenza di marchio, garanzia per vizi della vendita, responsabilità da cose in custodia, distanze legali, scioglimento di società di persone, tutela del maggiore d'età, mutuo/decadenza dal termine e opposizione a precetto. Nessuna risposta deve promuovere una guida interna a codice ufficiale del fascicolo o della busta.

## Aggiornamento operativo 2.248.21 - 2026-05-23

Le notifiche legali L. 53/1994 con relata, allegati, documento d'ufficio e prova RAC/RdAC sono dati operativi dello studio, non fonti pubbliche generiche. Lex deve leggere prima fascicolo, depositi portale, documenti acquisiti, notifica di sistema, bozza relata, controlli L. 53, ricevute PEC e prova deposito. Le fonti normative esterne servono come cornice, ma non sostituiscono lo stato reale del fascicolo.

Procedura da conoscere: il software controlla il rilascio del documento dell'ufficio nel Portale Servizi, avvisa l'avvocato, prepara il link di acquisizione con fascicolo/R.G./ufficio già compilati, importa il documento scaricato, lo inserisce nella relata, calcola evidenze e blocca la relata se manca l'acquisizione. Lex deve spiegare il ruolo dell'avvocato come revisione professionale, accesso al portale ufficiale, firma, invio PEC e deposito della prova, senza suggerire salvataggio di credenziali o invio automatico non confermato.

## Aggiornamento operativo 2.248.19 - 2026-05-23

La Guida Pratica incorpora anche le due consegne TOP9 set6 ricevute dall'utente. La base completa sale a 1.080 schede: 1.018 codici ufficiali PST/XSD restano coperti e depositabili, mentre 62 schede sono guide interne non depositabili. `111003` resta codice ufficiale; gli altri codici set6 non coerenti o assenti sono conservati come alias interni con `codice_originale_ricevuto`.

Lex riceve ora un blocco di ragionamento operativo per ogni guida: inquadramento, primo controllo, presupposti, atto, allegati, termini, esiti e distinzione tra guida interna e codice ministeriale. Le voci specialistiche dei set precedenti e del set6 entrano nel retrieval, non restano solo nel JSON o nella UI.

## Aggiornamento operativo 2.248.18 - 2026-05-23

La Guida Pratica incorpora anche le due consegne TOP9 set5 ricevute dall'utente. La base completa sale a 1.072 schede: 1.018 codici ufficiali PST/XSD restano coperti e depositabili, mentre 54 schede sono guide interne non depositabili. I codici ricevuti in contrasto con il catalogo ministeriale (`130031`, `130032`, `180001`) o assenti dal catalogo (`120020`, `143003`) sono conservati come alias interni con il codice originale tracciato, senza sostituire il codice oggetto ufficiale del fascicolo.

Lex deve usare queste nuove schede come conoscenza pratica conversazionale, mantenendo separati codice ministeriale, oggetto della guida e avviso operativo. Nessuna risposta o azione di deposito deve promuovere un alias interno a codice ufficiale.

## Aggiornamento operativo 2.248.11 - 2026-05-22

La conoscenza linguistica e conversazionale di Lex va arricchita sempre con le fonti operative curate dello studio. Per la Guida Pratica questo significa: lettura completa della scheda quando pertinente, risposta naturale all'avvocato, badge UI `Uso facoltativo`, nessun blocco del fascicolo e nessuna confusione tra supporto pratico interno e dato ministeriale.

Audit aggiuntivo: dettaglio fascicolo React e `GuidaPraticaSource` devono risolvere lo stesso fascicolo reale anche in fallback JSON legacy con SQLite operativo non ancora popolato.

## Aggiornamento operativo 2.248.10 - 2026-05-22

La Guida Pratica è ora fonte interna completa per Lex tramite `GuidaPraticaSource`. Non è fonte pubblica esterna e non sostituisce il catalogo ministeriale di deposito: arricchisce invece la risposta operativa con normativa letta dalla scheda, presupposti, adempimenti, atto, campi, allegati, avvertimenti, termini, atti collegati ed esiti.

Regola di audit: ogni nuova guida curata deve diventare anche conoscenza conversazionale di Lex. La risposta all'avvocato deve essere pratica, poco invasiva e distinta dal deposito: "questa guida aiuta il lavoro" non significa "questo alias è un codice ufficiale".

## Aggiornamento operativo 2.248.9 - 2026-05-22

La Guida Pratica PST/XSD è una knowledge base interna separata dal codice e non una fonte pubblica esterna. Le schede ufficiali sono collegate al catalogo ministeriale caricato nel prodotto e devono essere trattate come supporto operativo al fascicolo; gli alias interni non depositabili non vanno mai trasformati in codice oggetto di deposito.

Audit completato: 1.018 codici ufficiali PST/XSD, 1.018 guide curate ufficiali, zero codici ufficiali senza guida, zero incoerenze tra catalogo ministeriale e stato depositabile. I report sono in `artifacts/guida-pratica/`.

## Aggiornamento operativo 2.246.4 - 2026-05-21

Le casistiche PEC/notifiche/depositi restano nel dominio dati studio e audit interno. Le fonti normative ufficiali servono a governare la matrice del comportamento software, ma la risposta su cosa risulta da una PEC deve citare prima messaggi, MIME, allegati, ricevute, firme, OCR e validation report disponibili per il tenant.

Il presidio automatico delle PEC non crea un parere legale né un termine processuale conclusivo: quando `deadline_proposal` è applicabile, viene salvata una scadenza operativa con `operational_due_at` e profilo `PEC_AUTO_PRESIDIO`. Lex deve presentarla come promemoria automatico di controllo e non come termine definitivo.

Il fallback a fonti pubbliche o a cataloghi di modelli è escluso quando la domanda dell'avvocato chiede quali atti, depositi, notifiche o comunicazioni risultano dagli allegati PEC/email. In quel caso il sistema deve usare esclusivamente sorgenti operative interne autorizzate, evidenziando lacune probatorie come MIME originale non ancora acquisito, firme non verificate o allegati mancanti.

## Aggiornamento operativo 2.246.3 - 2026-05-21

Le domande su PEC di deposito, controlli, MIME, firma, notifica o cancelleria restano nel perimetro dati studio. Lex consulta casella PEC e `pec_audit`; non attiva una bozza e non devia su fonti pubbliche quando l'utente chiede quali PEC controllare.

Per lo storico PEC non ancora acquisito in storage audit-grade, il bridge applicativo espone un controllo provvisorio con confidence e motivazione, ma marca esplicitamente la lacuna probatoria. La fonte interna è utile per presidio operativo immediato; il completamento corretto resta l'acquisizione IMAP del MIME originale.

## Aggiornamento operativo 2.245.65 - 2026-05-20

Template Atti usa ora un registro locale di fonti normative verificate per i profili applicabili ai modelli, senza trasformare la chat in ricerca libera. Le fonti sono marcate con `verification_status`, URL ufficiale, data di verifica e tipo di presidio; i riferimenti mostrati a Lex e al compilatore includono sempre `reason_for_application`.

La creazione documento resta interna allo studio: catalogo reale, dati cliente/fascicolo, documenti allegati e timbro studio arrivano dai servizi applicativi. Lex può proporre azioni solo se il gate backend lo consente. Il canale libero non viene usato per completare un atto e non promuove riferimenti non verificati nel documento.

## Aggiornamento operativo 2.245.64 - 2026-05-20

Il nuovo workflow `atto_da_template` resta interno allo studio: nessuna fonte web viene usata per creare o completare atti. I template arrivano da `TemplateAttiSource` e dal catalogo reale `pct.compilatore_atti`; cliente, fascicolo, parti, documenti e contesto operativo arrivano da `StudioDatabaseSource`, contesto attivo Lex o repository runtime già autorizzati.

La risposta espone fonti interne e campi mancanti invece di inventare dati personali, parti processuali, allegati o clausole. Se i permessi non includono lettura clienti/fascicoli, se il tenant o l'utente non sono risolti o se la ricerca produce più clienti/fascicoli compatibili, Lex si ferma e mostra opzioni o lacune. La creazione editor è una mutation confermata e auditabile tramite il flusso Template Atti esistente.

## Aggiornamento operativo 2.245.63 - 2026-05-20

Audit conversazionale esteso su `Lex Studio Reasoner`: la chat non tratta più ogni messaggio come domanda isolata, ma mantiene il riferimento professionale appena citato quando l'avvocato prosegue il dialogo. I riferimenti ammessi sono solo oggetti con link operativo o identificativo interno già presenti nella risposta precedente: PEC/email, allegato, fascicolo, documento editor e cliente.

La matrice positiva verifica domande ampie su ultima PEC globale, ultima PEC nel fascicolo, allegati, email ordinaria, soggetti e parti, controparte, scheda cliente, fascicoli del cliente, timeline fascicolo, analisi documenti, scadenze, agenda, riepilogo fascicolo, pagamenti/fatture e contesto studio. La matrice negativa verifica fascicolo inesistente senza leak globale, utente senza permesso e cliente ambiguo.

La bozza è ammessa solo quando richiesta in modo espresso. `draft_communication` recupera prima PEC/email con `GovernedRetrieval`, poi compone una bozza verificabile; una consultazione come "ultima PEC ricevuta" resta invece una risposta con fonte, allegati e azioni apribili.

La pratica web professionale è un canale separato dalle fonti ufficiali: siti di studi legali, commenti per avvocati e materiali di prassi possono alimentare solo know-how non vincolante. Non fanno prova del diritto, non vengono pubblicati automaticamente e non possono contraddire l'avvocato; per smentire serve fonte primaria verificata con confidenza almeno 99%.

Il canale live è stato rafforzato: `search_free_public_web()` usa DuckDuckGo HTML e, se non riceve risultati utili, passa a Google pubblico, Yahoo ed Ecosia. Il parser scarta pagine dei motori, URL locali e risultati vuoti, pulisce i titoli e conserva motore, dominio, URL ed estratto. Il gate web/RAG al 99% verifica cento somministrazioni di pratica professionale verso Lex: il contenuto acquisito deve arrivare negli item RAG, restare `knowhow_professionale`, non rendere sufficiente l'evidence pack e non entrare tra le fonti trusted.

La fase linguaggio giuridico/date aggiunge un audit al 99% su cento turni conversazionali studio: ogni data visibile deve essere resa in italiano (`17 maggio 2026`, `21 maggio 2026 alle 10:00`) e nessuna risposta professionale può uscire con formato ISO tecnico. Il controllo copre PEC/email, allegati, fascicoli, documenti, soggetti, scadenze, agenda, pagamenti, scheda cliente, privacy, timeline e bozze richieste esplicitamente.

## Aggiornamento operativo 2.245.61 - 2026-05-19

La superficie utente di Lex viene governata come chat unica professionale: `LexUnifiedChat` è il contratto centrale riutilizzabile da ogni sezione, mentre `Lex Studio Reasoner` resta il motore operativo. Il payload HTTP espone contesto attivo, intent, contesto strutturato, verifica fonti, blocchi renderizzabili e azioni operative senza duplicare pannelli per PEC, fascicoli, documenti o pagamenti.

La consultazione dei dati studio passa da `LexContextProvider`, `IntentRouter`, `StructuredContextBuilder`, `LexSourceVerifier` e `LexActions`. Le fonti interne restano tenant-aware e permission-aware; se una fonte manca, è ambigua o l'utente non ha permesso, Lex non afferma dati non verificati e mostra warning/azioni coerenti.

Gate 2.245.61: test su contesto globale, fascicolo, PEC selezionata, "ultima PEC ricevuta" senza bozza, richiesta esplicita di bozza, permessi mancanti, cliente ambiguo, fonte assente, timeline fascicolo e fonti contabili. Il controllo su "pagamenti" non viene più confuso con il comando dispositivo "paga"; il blocco azioni usa parola intera.

## Aggiornamento operativo 2.245.60 - 2026-05-19

Fase 3 `Lex Studio Reasoner`: il payload operativo restituito alla chat Lex porta in primo piano `studio_reasoner`, `entity_map`, `fascicolo_timeline` e `operational_links`. I link sono deduplicati e derivano da oggetti/sorgenti interne autorizzate: fascicoli, documenti in editor, comunicazioni PEC/email e allegati.

Gate fase 3 aggiunto: test bounded HTTP con risposta fascicolo/documento che verifica reasoner mode `llm_rag_governato`, mappa entità, timeline, link editor e conteggi evidenza. Restano esclusi Web libero, fonti legali pubbliche e vecchi aggregatori CI.

## Aggiornamento operativo 2.245.59 - 2026-05-19

Fase 2 `Lex Studio Reasoner`: aggiunte mappa entità, timeline fascicolo e link apribili generati dalle sorgenti operative. Il report `studio_reasoner` include nodi/relazioni e timeline costruiti dai soli risultati autorizzati; i link puntano a route interne per fascicolo, documento editor, PEC/email e allegati. Non sono esposti path locali, storage o allegati fuori tenant.

Gate fase 2 confermati: test mirati su PEC/allegato apribile e fascicolo/documento editor, `python -m ruff check ...`, `python -m compileall lex/operational_knowledge` e `python -m pytest tests/test_lex_operational_knowledge.py -q --tb=short`.

## Aggiornamento operativo 2.245.58 - 2026-05-19

Avviata la tranche `Lex Studio Reasoner` con il nucleo planner/verificatore: le risposte operative allegano metadata `studio_reasoner` con piano `llm_rag_governato`, fonti interne verificate, lacune, fonti mancanti e policy RAG. Il verificatore studio esclude fonti pubbliche/legali già governate (`fonti_ufficiali`, `legal_intelligence`, `update_intelligence`, `web_libero`) e non reintroduce aggregatori legacy.

Gate fase 1 confermati: `python -m pytest tests/test_lex_operational_knowledge.py -q --tb=short`, test mirati su "ultima PEC ricevuta", esclusione fonti pubbliche dal verificatore, `python -m compileall lex/operational_knowledge` e `python -m ruff check lex/operational_knowledge/reasoner.py lex/operational_knowledge/service.py tests/test_lex_operational_knowledge.py`.

## Aggiornamento operativo 2.245.57 - 2026-05-19

Il flusso documento di Lex ora privilegia l'editor professionale rispetto agli export separati: le bozze o risposte generabili in documento mostrano `Apri con editor` quando l'import nel fascicolo è disponibile, senza pulsante Markdown. Per compatibilità, un eventuale click su un vecchio pulsante Word già renderizzato apre comunque l'editor se `editorImportUrl` è presente.

La dettatura è stata corretta per non partire già in conto alla rovescia: il silenzio viene misurato solo dopo una prima trascrizione. Questo evita chiusure immediate o risposte vuote quando l'avvocato attiva il microfono e parla dopo qualche secondo.

I documenti caricati manualmente nella chat Lex sono trattati come domanda sul documento quando la richiesta parla di sintesi, spiegazione, analisi, estrazione o punti importanti. L'allegato resta tenant-aware, citabile come `user_attachment` e non viene confuso con una ricerca legale, una PEC o una bozza.

## Aggiornamento operativo 2.245.55 - 2026-05-19

Rafforzato l'aggancio tra Lex e tutto il contesto studio senza introdurre addestramento su dati grezzi. `studio_context_lookup` è il nuovo profilo per richieste generali sul DB operativo interno e resta tenant-aware, permission-aware e auditabile. Il routing continua a escludere fonti legali pubbliche già governate.

`comunicazioni_lookup` ora ha precedenza sul drafting: domande come "ultima PEC ricevuta" leggono caselle PEC/email e allegati tramite Operational Knowledge e Ricerca Studio, senza generare bozze PEC. Le bozze formali restano cliccabili verso l'editor professionale quando la risposta contiene un titolo `BOZZA — ...` e l'import nel fascicolo è disponibile.

La modalità `Web libero` manuale è stata isolata nel bridge HTTP: nessuna sorgente studio, nessun archivio legale interno, nessun salvataggio DB/corpus e nessun warning visibile; i risultati sono marcati tecnicamente `web_libero` e `verified_reference=false`.

## Aggiornamento operativo 2.245.51 - 2026-05-19

Completato l'audit finale Fase 10 sugli aggiornamenti legali senza backup e senza import massivo. La classificazione macchina ora copre tutte le fonti `DEFAULT_SOURCE_ROWS`: fonti verdi abilitate, fonti RAG-only, fonti in osservazione, archivi locali e fonti secondarie fuori perimetro.

Le fonti OpenGA tabellari o di stato non pubblicabili restano RAG-only; Cassazione Massimario, Giustizia Amministrativa diretta e Decisioni/Pareri restano in osservazione finché non passano canary verde dedicato. Lex e Ricerca Legale continuano a usare testo pagina, PDF/OCR, riferimenti e domande contestuali già salvati, senza promuovere cataloghi tecnici o fonti in osservazione a notizie.

## Aggiornamento operativo 2.245.52 - 2026-05-19

La Fase 11 aggiunge il report sanitario di regime `legal-updates-health-report --json` e la dashboard qualità fonti. Il report controlla fonti attive, osservazione, RAG-only, non pubblicabili, ultimo controllo, errori, OCR falliti, allegati vuoti, riferimenti mancanti, domande mancanti, review pendenti e pubblicazioni guarded senza avviare import o backup.

La manutenzione periodica può usare solo backfill mirati (`attachments`, `ocr`, `references`, `questions`) con `--no-publish`. Le nuove fonti devono passare da capability, fixture, canary, report, pilot guarded e scheduler: nessuna fonte viene pubblicata automaticamente per sola presenza nel catalogo.

## Aggiornamento operativo 2.245.53 - 2026-05-19

La Fase 11.5 chiude i residui prima del popolamento produzione senza attivare scheduler esteso, import massivo, Web libero automatico o pubblicazione fuori guardia. Il report operativo è `artifacts/legal-updates/phase11_5-gap-closure-2026-05-19/gap-closure-report.md`.

Il comando controllato per un singolo ciclo è `python -m pct.cli legal-updates-run-progressive --source-budget 3 --publish-max-items 5 --item-timeout-seconds 120 --guarded-only --json`: usa solo fonti verdi progressive, rispetta coda/cursori/budget/timeout, supporta `--dry-run` e lascia fuori fonti in osservazione, RAG-only, archivi locali e fonti secondarie. Il canary `legal-updates-giurisprudenza-structured-canary --json` impedisce la promozione dell'Archivio Giurisprudenza se mancano corte, numero, anno, data, fonte ufficiale o testo/PDF.

Cassazione `QSP50194` è stata verificata come dettaglio diretto raggiungibile con riferimento `art. 606 c.p.p.`, ma non compare nel canary delle ultime 5 schede del 19 maggio 2026. La lacuna è chiusa come diagnosi controllata: fixture e test preservano parser di detail `contentId`, estrazione `art. 606 c.p.p.`, domanda “Quali articoli del c.p.p. sono richiamati nel PDF?” e ranking su allegato/PDF, senza import storico o pubblicazione forzata.

EUR-Lex riconosce CELEX su fixture minima ma resta `RAG-only` finché non sono presenti tutte le chiavi strutturate. OpenGA resta `RAG-only` per dataset tabellari e record di stato; un eventuale PDF/documento concreto con TAR/CdS, numero e anno potrà entrare solo in un futuro pilot guarded.

## Aggiornamento operativo 2.245.54 - 2026-05-19

Collegato Lex al DB operativo interno tramite `StudioDatabaseSource`, che usa la Ricerca Studio già indicizzata e non prompt grezzi. La sorgente espone dati riservati dello studio solo come evidenze interne verificate, tenant-aware e con URL applicativi: clienti, soggetti, fascicoli, documenti, agenda, scadenze, comunicazioni, PEC, email, depositi, preventivi, fatture e pagamenti.

Per evitare sovrapposizioni, la sorgente scarta i tipi legali già coperti dai percorsi pubblici/ufficiali: `legal_intelligence`, `legal_updates`, normativa, giurisprudenza, prassi, fonti e web ufficiale. In modalità `Web libero` il router non carica la sorgente studio e mantiene isolata la ricerca pubblica non salvata.

Il reindex globale ora riceve anche `GestioneMessaggi`, `GestioneEmailRicevute` per PEC e `GestioneEmailRicevute` per posta ordinaria. Gli adapter indicizzano oggetto, mittente, destinatari, data, stato, metadati PCT e allegati, usando `MESSAGGI_DB`, `EMAIL_CASELLA_DB` ed `EMAIL_ORDINARIA_DB` tenant-aware.

## Aggiornamento operativo 2.245.49 - 2026-05-19

Attivata la Fase 8 per lo scheduler progressivo degli aggiornamenti legali. Lo step 1 non avvia tutte le fonti: usa solo `cassazione_ultime_sent_ord_questioni`, `inps_circolari`, `inps_messaggi` e `agcom_provvedimenti`, con budget `2` fonti per ciclo, timeout `120` secondi per elemento, massimo `5` pubblicazioni guarded e massimo `5` schede Cassazione ultime per scansione.

ANAC e Garante restano escluse dallo scheduler automatico perché nelle fasi precedenti hanno richiesto conferme ulteriori; Normattiva e Gazzetta restano archivi ufficiali locali e non vengono trattate come batch fonte nello step 1. Lex continua a usare come certe solo evidenze verificate o archivi ufficiali locali; fonti incomplete, RAG-only o fuori step restano marcate come da verificare e non diventano base certa della risposta.

## Aggiornamento operativo 2.245.48 - 2026-05-19

Completata la Fase 7 con backfill diagnostico mirato su PDF/OCR/riferimenti/domande. La fase non ha eseguito backup, Web libero, pubblicazione automatica o import massivo: ogni comando ha usato `--limit`, `--max-seconds 120`, `--no-publish` e report JSON salvato in `artifacts/legal-updates/phase7-backfill-2026-05-19/`.

Il repository locale degli aggiornamenti legali è stato controllato con 168 evidenze web già presenti: tutte hanno testo leggibile e termini/domande salvati; non risultano PDF con testo zero o OCR mancante nel perimetro selezionato. Il backfill riferimenti ha controllato 50 evidenze, ne ha aggiornate 14 e ha aggiunto 20 riferimenti; le fonti Cassazione specifiche e RAG-only/open data sono rimaste invariate.

Lex e Ricerca Legale leggono questi aggiornamenti direttamente dal repository locale: lo stato è migliorato sui riferimenti delle evidenze aggiornate, senza nuove pubblicazioni e senza trasformare fonti RAG-only in news o giurisprudenza strutturata.

## Aggiornamento operativo 2.245.47 - 2026-05-19

Completata la Fase 6 su normativa e archivi base senza backup, senza download ciechi e senza import massivo. Gli archivi locali già presenti sono stati verificati e collegati: Normattiva locale contiene 42.677 documenti, 238.110 articoli e 279.777 chunk; Gazzetta locale contiene 12 documenti e 1.852 chunk. Il report canonico è `artifacts/legal-updates/phase6-normativa-archives-2026-05-19/phase6-report.md`.

Lex e Ricerca Legale usano ora meglio gli archivi ufficiali locali: `search_normattiva()` riconosce query per codice e articolo, usa i raw ZIP Normattiva già presenti quando il DB non espone ancora il singolo articolo come chunk autonomo e non inventa link Normattiva; `search_gazzetta()` deduplica i risultati per documento; `search_normativa_sources()` porta Normattiva/Gazzetta nel contesto Lex prima dei fallback esterni.

I codici verificati come RAG normativo sono: codice civile, codice di procedura civile, codice penale, codice di procedura penale, codice del processo amministrativo e codice della strada. EUR-Lex resta fonte UE ufficiale ma viene tenuta `RAG-only` finché il parser CELEX dedicato non sarà stabilizzato con fixture verdi. Studio Cataldi e Avvocato Andreani restano fonti secondarie disabilitate e non alimentano pubblicazione ufficiale.

## Aggiornamento operativo 2.245.45 - 2026-05-19

Completato il primo pilot di pubblicazione `guarded` su tre sole fonti verdi: `cassazione_ultime_sent_ord_questioni`, `inps_circolari` e `agcom_provvedimenti`. Sono stati pubblicati 9 documenti verificati, con testo leggibile, PDF/OCR o allegati gestiti, riferimenti e domande contestuali. Nessun import massivo, nessuno scheduler globale e nessuna fonte gialla/rossa sono stati attivati.

La verifica post-pilot conferma che i contenuti appaiono nell'archivio admin, sono ricercabili da Ricerca Legale, sono interrogabili da Lex e premiano il PDF o l'allegato quando la domanda lo richiede. Le schede Cassazione pubblicate come news sono pronte per RAG/Archivio Giurisprudenza ma non vengono inserite come giurisprudenza strutturata se mancano corte, numero o anno. Le circolari INPS non vengono pubblicate come normativa quando la chiave estratta descrive la circolare e non un atto normativo.

## Aggiornamento operativo 2.245.46 - 2026-05-19

Completata la Fase 5 sul primo gruppo fonti verdi con esecuzione fonte per fonte, limiti `5/120s`, `direct-only`, pubblicazione `guarded`, zero Web libero, zero import massivo e zero scheduler globale. Il report canonico è `artifacts/legal-updates/phase5-green-2026-05-19/phase5-green-report.md`, con verifica macchina in `verification.json`.

Esito: 20 documenti pubblicati unici, 8 documenti RAG-only/non pubblicati, 26 scarti guarded. Ricerca Legale e Lex ritrovano 20/20 pubblicati con query mirata alla fonte. Nessuna nuova scheda strutturata in Archivio Giurisprudenza: le pronunce pubblicate restano news/RAG ufficiale finché non passano una promozione strutturata dedicata.

Correzioni di qualità: Corte costituzionale non crea più contenuti da captcha/homepage/navigazione; Corte dei conti non acquisisce link di servizio e usa titoli reali da allegati PDF ufficiali quando la pagina mostra solo etichette generiche. PST e OpenGA tabellare restano solo RAG-only.

## Aggiornamento operativo 2.245.44 - 2026-05-19

La Fase 3 post-canary ha corretto solo le fonti gialle del report precedente:
Gazzetta Ufficiale, ANAC, Garante Privacy, PST Giustizia download e OpenGA
sentenze. Gazzetta rilegge i PDF già normalizzati anche sugli elementi
invariati; ANAC e Garante non producono più allegati fittizi da testo o link
normativi generici; PST è classificata come fonte tecnica `RAG-only`; OpenGA
tabellare è `RAG-only` e non entra in pubblicazione automatica. Nessun import
massivo e nessuna pubblicazione sono stati eseguiti.

## Aggiornamento operativo 2.245.42 - 2026-05-19

Introdotti strumenti diagnostici sicuri per popolare le fonti una alla volta:
`python -m pct.cli legal-updates-canary` legge una sola fonte con limite
obbligatorio, budget tempo, `--direct-only`, `--no-publish`, diagnostica JSON
e salvataggio opzionale dell'ultimo canary; `python -m pct.cli
legal-updates-backfill-diagnostics` completa solo allegati, OCR, riferimenti o
domande mancanti su fonte, review o query mirata.

Le fixture offline in `tests/fixtures/legal_updates/` coprono le famiglie
Cassazione, autorità indipendenti, feed, CKAN/OpenGA, PST e PDF/OCR mock. I
test non dipendono dalla rete live e dimostrano che la diagnostica alimenta
evidenze RAG/Lex senza pubblicazione automatica incontrollata.

## Aggiornamento operativo 2.245.41 - 2026-05-19

Il piano fonte per fonte degli Aggiornamenti legali è stato trasformato in
codice: `pct/legal_update_source_capabilities.py` definisce per ogni fonte
strategia elenco/dettaglio/allegati, PDF/OCR, destinazione, RAG,
giurisprudenza, filtro di pertinenza e motivo di esclusione. I parser dedicati
in `pct/legal_update_source_parsers.py` coprono HTML, feed, CKAN/OpenGA,
Cassazione e autorità indipendenti con test deterministici, senza import live
massivo.

Lex e Ricerca Legale leggono anche la destinazione policy e continuano a usare
testo pagina, PDF/OCR, riferimenti normativi e domande contestuali. Web libero
resta manuale e separato; le fonti secondarie non entrano nel corpus ufficiale.

## Aggiornamento operativo 2.245.40 - 2026-05-18

Completata la ricognizione delle fonti Aggiornamenti legali e registrata la
matrice fonte per fonte in `artifacts/legal-updates/source-rollout-plan.md`.
Il repository SQL degli aggiornamenti ora espone a Lex e Ricerca Legale anche
riferimenti normativi deterministici, riferimenti R.G., domande contestuali,
stato PDF/allegati e segnali di OCR/testo, senza creare link ufficiali non
risolti.

Il Web libero resta isolato dal contesto interno: quando l'avvocato lo attiva,
la ricerca non consulta fonti studio, fascicoli, template o corpus ufficiale,
non salva risultati in archivio e marca tecnicamente le evidenze come
`web_libero`, `verified_reference=false`, `saved_to_db=false`.

## Aggiornamento operativo 2.245.39 - 2026-05-18

Corretto il caso segnalato su `/ricerca-legale?q=Corte+Costituzionale`:
la pagina Ricerca Legale mostrava la `Sentenza della Corte Costituzionale n. 50 del 27/1/2026`,
ma Lex poteva rispondere con sentenze Cassazione perché nel repository locale
`legal_updates.db` erano presenti evidenze Cassazione che citavano la Corte
Costituzionale nel testo.

Passaggi tracciati:

- il parser dei riferimenti giurisprudenziali esatti accetta ora numeri brevi
  come `n. 50`, non solo numeri da tre cifre in su;
- `Sentenza della Corte Costituzionale n. 50 del 27/1/2026` viene riconosciuta
  come riferimento esatto, con numero `50`, data `27/01/2026` e organo
  `Corte Costituzionale`;
- la ricerca ufficiale seleziona `cortecostituzionale.it` quando la domanda
  nomina la Corte Costituzionale e non aggiunge Cassazione come fonte
  sostitutiva;
- il fallback Cassazione diretto non si attiva se il parser ha riconosciuto un
  organo diverso dalla Cassazione;
- `LegalUpdateRepository.search_lex_sources()` filtra i risultati per fonte
  richiesta quando la domanda è un riferimento esatto: una riga Cassazione non
  può più coprire una richiesta sulla Corte Costituzionale solo perché nel testo
  compare quella Corte;
- la pagina Ricerca Legale applica la stessa regola sui record già normalizzati:
  prima valuta URL e nome della fonte, poi il contenuto citato;
- se il dato esatto non è nel repository SQL, Lex/Ricerca Legale lasciano
  attivare il fallback pubblico governato invece di restituire una sentenza
  diversa.

Verifiche eseguite:

- `python -m py_compile lex\research\case_law_reference_parser.py lex\research\query_helpers.py lex\research\source_scope_policy.py lex\research\case_law_exact_search.py lex\retrieval\official_web.py pct\legal_update_repository.py web\services\react_legal_intelligence_bridge.py`;
- `python -m pytest tests\test_lex_sources_and_studio_data.py tests\test_react_legal_intelligence_search.py tests\test_legal_update_publish_context.py::test_search_lex_sources_premia_evidenza_web_con_titolo_esatto tests\test_legal_update_publish_context.py::test_search_lex_sources_non_usa_cassazione_per_sentenza_corte_costituzionale tests\test_legal_update_publish_context.py::test_search_lex_sources_premia_allegato_quando_domanda_chiede_allegato -q --tb=short`;
- `python -m pytest tests\test_lex_operational_knowledge.py::test_http_bridge_defers_specific_case_law_to_public_research tests\test_lex_operational_knowledge.py::test_rg_questione_penale_risponde_a_domande_da_avvocato tests\test_lex_operational_knowledge.py::test_rg_questione_penale_non_trascina_fonti_non_pertinenti -q --tb=short`.

## Aggiornamento operativo 2.245.38 - 2026-05-18

Corretto il caso `02_Assoradio.pdf` segnalato in Ricerca Legale:

- il blocco `Contesto in IUSENTRA` non ripete più lo stesso testo come
  `Contesto operativo` e `Contenuto` quando riepilogo ed estratto coincidono;
- i contributi AGCOM di consultazione pubblica, pianificazione frequenze DAB+
  o posizioni tecniche di terzi vengono marcati fuori perimetro quando non
  contengono un provvedimento, una delibera, una sanzione, una controversia,
  un elemento Corecom/tutela utenti o altro valore operativo per lo studio;
- il filtro agisce sia sull'import deterministico degli aggiornamenti legali
  sia sui risultati già esposti da `legal_updates.db`, così Lex e Ricerca
  Legale non trasformano una prova web generica in materiale utile allo studio;
- la scheda mostra solo anteprima e contesto pulito, mentre il testo PDF esteso
  resta nel riquadro `Testo letto in IUSENTRA` e nei chunk/RAG quando il
  documento è pertinente e il testo è stato letto correttamente.

---

## Aggiornamento operativo 2.245.34 - 2026-05-18

Aggiunta la Fase 5 Auto-fetch governato. La pipeline non parte più come
scansione massiva indistinta: prima costruisce un piano deterministico, poi
accoda job deduplicati, poi esegue solo le fonti dovute entro il budget.

Passaggi tracciati:

- aggiunto `pct/legal_update_autofetch.py`;
- ogni tick legge fonti abilitate, cursori persistenti e intervallo di polling;
- il budget `LEGAL_AUTOFETCH_SOURCE_BUDGET` limita quante fonti possono essere
  processate nel giro;
- ogni fonte selezionata viene accodata in `LegalUpdateJobQueue` con schema
  `iusentra.legal_update_autofetch.v1`, URL, nome fonte, timeout, tentativi e
  checklist qualità;
- i cursori registrano ultimo job, ultimo stato, errore leggibile e fallimenti
  consecutivi;
- `web/services/legal_update_surface.py` usa il tick governato per l'azione
  `scan`;
- `pct/scheduler.py` usa il tick governato per gli aggiornamenti legali
  pianificati;
- il monitor operativo espone coda, fonti pronte/non pronte, job recenti,
  fonti bloccate e domande qualità obbligatorie.

Domande qualità obbligatorie per ogni fonte/documento:

- fonte censita nel database;
- pagina ufficiale o pubblica raggiungibile;
- allegati, PDF o documenti collegati;
- allegati scaricati e hashati;
- testo estratto o passato da OCR;
- OCR pulito oppure marcato come sporco;
- norme, R.G., date e riferimenti utili estratti;
- discrepanze tra scheda, PDF, R.G., date o titolo;
- prontezza per Memory Tree e RAG;
- risposta Lex con sintesi vera, link cliccabile e limiti chiari.

Verifiche eseguite:

- `python -m py_compile pct\legal_update_autofetch.py pct\scheduler.py web\services\legal_update_surface.py`;
- `python -m pytest tests\test_legal_update_autofetch.py tests\test_legal_update_job_queue.py tests\test_legal_update_batch_runner.py tests\test_legal_update_surface_jobs.py -q --tb=short`.

## Aggiornamento operativo 2.245.33 - 2026-05-18

Aggiunta la Fase 4 Tool Registry e Model Routing per Lex, necessaria prima di
estendere il lavoro a Cassazione, Ricerca Legale, Archivio Giurisprudenza e area
AI.

Passaggi tracciati:

- `lex/tools/registry.py` mantiene il dizionario storico `registry.tools`, ma
  aggiunge descrittori governati per ogni strumento;
- ogni tool dichiara schema, categoria, trasporto, permessi, lettura/scrittura,
  mutazione stato e compatibilità con web libero;
- la modalità web libero non impone allowlist ufficiali sulle ricerche
  dell'avvocato, ma non espone strumenti riservati dello studio come se fossero
  fonti pubbliche;
- gli strumenti di scrittura dell'editor professionale sono marcati come
  mutanti e richiedono un canale applicativo autorizzato;
- `lex/providers/registry.py` espone una policy di routing con profilo,
  provider effettivo, uso LLM, costo relativo, target latenza e controllo
  qualità;
- i provider esterni restano disattivati salvo `LEX_EXTERNAL_ALLOWED=1`, senza
  fallback implicito su dati sensibili.

Verifiche eseguite:

- `python -m py_compile lex\tools\registry.py lex\providers\registry.py`;
- `python -m pytest tests\test_lex_tool_registry_governance.py tests\test_lex_model_routing_governance.py lex\tests\unit\test_registry.py tests\test_lex_editor_ai_tools.py tests\test_lex_operational_knowledge.py::test_tool_registry_exposes_operational_knowledge_tool_default_on tests\test_lex_operational_knowledge.py::test_tool_registry_can_disable_operational_knowledge -q --tb=short`.

## Aggiornamento operativo 2.245.32 - 2026-05-18

Aggiunta la Fase 3 job queue per fonti legali, necessaria prima di estendere
Cassazione e le altre fonti oltre il caso pilota.

Passaggi tracciati:

- aggiunto `pct/legal_update_job_queue.py` con coda SQLite persistente per
  fonte, pagina, PDF/allegato o documento;
- ogni job registra chiave dedupe, hash contenuto, fonte, URL, tipo elemento,
  payload stabile, tentativi, timeout, stato, errore leggibile e orari;
- `claim_next`, `complete`, `fail` e `recover_stale_running` permettono retry,
  timeout finale e ripresa dei job rimasti in corso dopo crash del worker;
- il batch runner espone `build_legal_update_source_job_queue`, così una
  tranche di fonti può essere accodata e verificata prima di avviare i
  subprocess;
- la deduplica conserva un solo job per lo stesso documento/hash, ma crea un
  nuovo job quando cambia l'hash del contenuto.

Verifiche eseguite:

- `python -m py_compile pct\legal_update_job_queue.py pct\legal_update_batch_runner.py`;
- `python -m pytest tests\test_legal_update_job_queue.py tests\test_legal_update_batch_runner.py -q --tb=short`.

## Aggiornamento operativo 2.245.31 - 2026-05-18

Aggiunta la Fase 2 TokenJuice, reimplementata in Python per Lex senza copiare
codice esterno e senza chiamate LLM.

Passaggi tracciati:

- aggiunto `lex/tokenjuice.py` come compattatore deterministico per HTML, JSON,
  log, OCR/PDF già estratti e testi legali lunghi;
- la compattazione preserva ancoraggi legali: articoli, R.G., date, atti,
  fonte, motivi e passaggi con valore giuridico;
- `lex/memory_tree.py` registra per ogni chunk i metadati TokenJuice:
  schema, regola applicata, caratteri originali/compattati, rapporto di
  riduzione, ancoraggi e avvisi OCR;
- il testo originale resta nel corpus, mentre il contesto compattato è
  disponibile per il RAG quando riduce davvero il payload;
- il generatore corpus dichiara nel manifest la policy TokenJuice, così il
  consumo crediti resta riservato alla risposta o ai test qualità e non ai
  passaggi tecnici ripetibili.

Verifiche eseguite:

- `python -m py_compile lex\tokenjuice.py lex\memory_tree.py scripts\generate_lex_source_corpus.py`;
- `python -m pytest tests\test_lex_tokenjuice.py tests\test_lex_memory_tree.py tests\test_lex_source_corpus_generator.py -q --tb=short`.

## Aggiornamento operativo 2.245.30 - 2026-05-18

Avviata l'assimilazione funzionale dei pattern OpenHuman senza copiarne codice
GPL: la prima fase è il Memory Tree Lex deterministico.

Passaggi tracciati:

- aggiunto `lex/memory_tree.py` come memoria strutturata per documenti già
  acquisiti: fonte, PDF/OCR, sentenza, questione pendente o documento fascicolo;
- ogni chunk ha ID stabile, hash contenuto, provenienza, qualità, norme,
  riferimenti R.G., date, argomenti e metadati RAG;
- il generatore `scripts/generate_lex_source_corpus.py` scrive anche
  `memory_tree/index.json`, `memory_tree/documents.jsonl` e
  `memory_tree/chunks.jsonl`;
- la ricerca memoria è deterministica per fonte, norma, R.G. e argomento,
  senza consumo LLM;
- OCR sporco e riferimenti R.G. multipli restano visibili nello stato qualità,
  così Lex non deve fonderli come fatti certi nella risposta finale.

Verifiche eseguite:

- `python -m py_compile lex\memory_tree.py scripts\generate_lex_source_corpus.py`;
- `python -m pytest tests\test_lex_memory_tree.py tests\test_lex_source_corpus_generator.py -q --tb=short`.

## Aggiornamento operativo 2.245.29 - 2026-05-18

Ricerca Legale e catalogo fonti sono stati riallineati alla logica decisa sul
caso Cassazione: prima dati reali visibili e interrogabili, poi generatore
corpus solo sui documenti pronti.

Passaggi tracciati:

- la pagina `/ricerca-legale` non mostra più un cruscotto descrittivo separato:
  i conteggi reali diventano accessi operativi verso fonti, news, acquisizioni,
  Normattiva, Gazzetta, Registro mediazione e Archivio Giurisprudenza;
- la lista `Fonti monitorate` è resa dentro la pagina con stato e famiglia
  della fonte, e ogni fonte avvia una ricerca invece di restare un link
  generico;
- `https://www.cortedicassazione.it/it/ultime_sent_ord_e_questioni.page` è
  stata aggiunta al catalogo degli aggiornamenti legali come fonte ufficiale
  Cassazione dedicata (`cassazione_ultime_sent_ord_questioni`);
- la fonte Cassazione deve essere navigata con la stessa sequenza già stabilita:
  DB -> pagina ufficiale -> allegati/PDF -> download/cache -> hash -> OCR/testo
  -> metadati qualita' -> documenti pronti -> corpus RAG;
- il commit/push deve seguire la checklist `docs/COMMIT_PUSH_REQUIRED_GATES.md`,
  che rende espliciti i gate shardati e impedisce di usare aggregatori o suite
  monolitiche come diagnosi primaria.

Verifiche locali già eseguite in questa tranche:

- `python -m pytest tests\test_legal_updates_pipeline.py::test_fonti_default_includono_pagina_cassazione_ultime_sent_ord_e_questioni tests\test_react_legal_intelligence_search.py -q`;
- `pnpm --filter @iusentra/studio typecheck`.

## Aggiornamento operativo 2.245.24 - 2026-05-18

Il caso Cassazione `QSP50194` / `R.G. 9926/2026` è diventato il caso pilota
obbligatorio per il comportamento Lex sulle fonti pubbliche: non basta più
dimostrare che pagina, PDF e OCR siano stati trovati. Lex deve rispondere alla
domanda effettiva dell'avvocato con una risposta strutturata e controllabile.

Passaggi tracciati:

- corretta la risposta troppo superficiale che riportava solo fonte, PDF,
  discrepanza R.G. ed estratto OCR iniziale;
- aggiunta una risposta focalizzata sulla domanda concreta prima della scheda
  fonte;
- aggiunta sintesi dell'ordinanza con natura dell'atto, vicenda processuale,
  pena concordata, motivi/censure, punto di diritto, articoli richiamati e stato
  pendente;
- corretto il link PDF con etichetta stabile `Apri PDF ufficiale` e underscore
  percent-encoded per evitare rotture nel rendering Markdown del widget già
  aperto;
- aggiunta matrice di domande da avvocato: sintesi, punto di diritto, motivi,
  natura sentenza/questione pendente, udienza/norme, articoli, ricorrente e
  relatore, PDF/allegato, uso in atto, esito e discrepanza R.G.;
- aggiunta fase di integrazione web libera per gli articoli, distinta dalla
  fonte ufficiale Cassazione.
- corretto il comportamento `Web libero` della chat: con il flag attivo Lex non
  usa allowlist ufficiali, non blocca per `fonte autorizzata`, non trascina
  fonti DB/fascicolo nel risultato libero, non salva nel corpus e non mostra
  warning visibili; i risultati restano tecnicamente `web_libero` e
  `verified_reference=false`, con controllo rimesso all'avvocato.

Verifiche eseguite:

- `python -m py_compile lex\retrieval\sources\official_web.py lex\retrieval\source_router.py lex\http_bounded_bridge.py lex\orchestrator_http.py lex\operational_knowledge\tools.py lex\operational_knowledge\response_composer.py lex\operational_knowledge\source_registry.py pct\legal_update_repository.py`;
- `python -m pytest lex\tests\test_official_web.py lex\tests\test_http_bounded_bridge_governed_only.py lex\tests\test_orchestrator.py tests\test_lex_operational_knowledge.py::test_rg_questione_penale_risponde_a_domande_da_avvocato tests\test_lex_operational_knowledge.py::test_rg_questione_penale_articoli_attiva_web_libero_distinto_dalla_fonte_ufficiale -q`;
- `python -m pytest tests\test_assistente_focus.py tests\test_lex_operational_knowledge.py tests\test_lex_assistente_context_real_requests.py tests\test_lex_widget_contract.py tests\test_lex_fascicolo_first_retrieval.py lex\tests\unit\test_retrieval_orchestrator.py -q`;
- `node tests\js\lex_assistant_render.test.mjs`;
- `git diff --check`.

Regola di estensione: prima di applicare la logica al generatore corpus o a
10.000 documenti, un documento deve passare end-to-end con test ripetibili e
risposta professionale. Solo dopo si estende la stessa griglia agli altri
documenti.

## Aggiornamento operativo 2.245.26 - 2026-05-18

Rafforzata la regola del caso pilota `QSP50194`: pagina e PDF sono già stati
verificati come collegati, quindi Lex non deve rimettere in discussione il
collegamento a ogni risposta. Deve però separare l'attribuzione:

- dati della scheda `R.G. 9926/2026`: quesito, udienza, relatore, ricorrente,
  riferimenti normativi e stato pendente;
- dati del PDF ufficialmente collegato, che nel testo letto riporta
  `R.G. 9966/2026`: motivi/censure, punto di diritto e articoli ricavati dal
  PDF devono essere presentati come contenuto del PDF collegato;
- nota R.G.: resta visibile e non deve diventare un dubbio generico su fonti già
  verificate;
- OCR: estratti sporchi, frammenti con barre, lettere isolate o testo
  chiaramente deformato non devono essere riprodotti nella risposta finale.
- forma della risposta: deve essere una sintesi unica, non una lista ripetuta di
  sezioni; oggetto, stato, principio, motivi, norme spiegate, effetto pratico,
  PDF e nota R.G. devono comparire una sola volta.

Questa regola è il blocco da tenere davanti prima del generatore corpus: prima
separazione corretta di scheda, allegato e OCR su un documento, poi propagazione
agli altri documenti.

Aggiornamento operativo 2.245.36 - 2026-05-18:

- la pagina Cassazione `ultime_sent_ord_e_questioni.page` non viene più trattata
  come lista documentale diretta: il connettore segue le pagine ufficiali
  `giurisprudenza_penale.page` e `giurisprudenza_civile.page` e conserva solo
  schede `*_dettaglio.page?contentId=...`;
- pagine di servizio, navigazione, privacy, supporto, preferenze e link generici
  del sito Cassazione sono escluse prima del DB operativo e di nuovo prima del
  generatore corpus;
- il generatore corpus applica il filtro anche a
  `cassazione_ultime_sent_ord_questioni`, non solo a `cassazione_massimario`,
  così eventuali evidenze sporche già acquisite non entrano nel RAG;
- le domande del corpus vengono create dal contesto reale letto: titolo della
  scheda, testo PDF/OCR, riferimenti normativi, R.G., presenza di allegato e
  qualità del testo; gli articoli estratti sono salvati come riferimenti
  espliciti e la risposta Lex può integrarli con `web_libero` senza promuovere
  quella ricerca a fonte DB;
- verifica locale sulla fonte Cassazione: 10 schede documentali pronte, 9 con
  PDF letto, una senza PDF ma con testo pagina, 10/10 con matrice domande;
  corpus di prova da 20 documenti e 174 chunk, Memory Tree pronto, zero pagine
  di servizio;
- test mirati confermati: filtro pagina Cassazione, generatore corpus, articoli
  con `web_libero`, Ricerca Legale e Archivio Giurisprudenza.
- corretto anche il caso chat `Web libero`: il flag manuale svuota realmente
  contesto studio, fascicolo, template atti, impostazioni e fonti interne prima
  del workflow bounded. La risposta non deve più mostrare `Fonti interne
  verificate` quando la ricerca è libera e deve restare in italiano anche se il
  provider produce frasi inglesi.

Aggiornamento operativo 2.245.28 - 2026-05-18:

- il backfill delle evidenze Cassazione ora restituisce un report qualità per
  documento prima del generatore corpus;
- il report distingue pagina verificata, PDF/allegato trovato, hash presente,
  testo letto, OCR pulito/sporco, norme estratte, riferimenti R.G.,
  discrepanze, link PDF cliccabile e stato `pronto`, `pronto_con_note`,
  `da_ocr` o `testo_mancante`;
- la matrice delle domande da avvocato è diventata un campo obbligatorio
  `question_matrix`: sintesi, natura dell'atto, oggetto, stato, punto di
  diritto, motivi/censure, norme spiegate, effetto pratico, esito, PDF/allegato
  e discrepanza R.G. quando presente;
- il download PDF ora prova prima il riuso della cache runtime del server
  (`/data/intelligence/downloads`, `/data/fonti_ufficiali` e `/data/tenants`
  quando `PCT_DATA_ROOT=/data`, oppure le directory configurate con
  `IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR` /
  `IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR`), così un PDF già presente non viene
  scaricato di nuovo;
- la tranche reale ha prima evidenziato rumore da pagine generiche del sito
  Cassazione; il filtro è stato quindi ristretto alle schede documentali
  (`civile_dettaglio`, `penale_dettaglio`, `qsp_dettaglio`, `qsc_dettaglio`,
  `quc_dettaglio`, `rlc_dettaglio`, `rlp_dettaglio`, `su_dettaglio`);
- la verifica filtrata locale ha controllato 10 documenti Cassazione: 10/10
  pronti, 10 PDF letti, 12 allegati salvati, nessun OCR mancante, nessun hash
  mancante;
- solo dopo questa verifica è stato generato un corpus locale Cassazione da 50
  documenti e 538 chunk RAG, con `question_matrix` nelle query attese;
- le fonti pronte non devono restare solo nel job o nel corpus: devono essere
  usabili in Lex Chat AI, visibili in `/ricerca-legale` e consultabili in
  Archivio Giurisprudenza quando sono fonti giurisprudenziali o Cassazione;
- test mirati passati: 18 test su allegati/OCR/cache, backfill, filtro
  Cassazione e generatore corpus; 4 test UTF-8; `git diff --check`;
- questo controllo è deterministico e non consuma crediti LLM. Lex/LLM resta
  riservato alla risposta finale o a test qualità espliciti, non al download,
  hash, OCR o chunking.

Approvazione reale del 18 maggio 2026:

- domanda validata: `mi puoi sintetizzare questa sentenza Penale Pendente del
  ricorso R.G. 9926/2026`;
- risultato accettato dall'utente: risposta sintetica con oggetto, stato,
  principio, motivi, norme spiegate, effetto pratico, PDF e nota R.G.;
- percorso validato: DB -> pagina ufficiale -> allegato -> OCR/PDF -> retrieval
  operativo -> risposta Lex -> test di verifica;
- regola definitiva: questo caso è il baseline da propagare al generatore corpus
  e agli altri documenti, senza tornare a risposte con log fonte, sezioni
  duplicate o OCR grezzo.

## Aggiornamento operativo 2.245.21 - 2026-05-18

Il caso Cassazione `QSP50194` è stato verificato sul database locale: prima
l'allegato ufficiale era presente come URL/hash, ma il contenuto era fermo a
`context_chars=0`. Dopo l'aggancio OCR locale il PDF
`Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf` è stato letto con
`pdfplumber+ocr`, salvando `45813` caratteri interrogabili nel record
`review_id=390`.

Lex ora risponde alla domanda `Quale allegato ufficiale ha la questione penale
R.G. 9926/2026?` con l'allegato `Ordinanza di rimessione`, il PDF ufficiale,
un estratto OCR e l'avviso sulla differenza tra `9926/2026` nella domanda e
`9966/2026` nell'allegato. La risposta non espone più errori tecnici interni se
una sorgente secondaria non è disponibile nel contesto corrente.

È stato aggiunto anche il comando manuale `Web libero` nel widget Lex: non è un
job, non è una pianificazione e non passa dalla console scheduler. Il comando
vale solo per la singola richiesta Lex e abilita una ricerca pubblica libera,
separata dalle fonti ufficiali già acquisite.

## Aggiornamento operativo 2.245.20 - 2026-05-18

Dopo il salvataggio OCR di Cassazione `QSP50194`, le prove di domanda hanno
mostrato un problema di ordine: quando la domanda chiedeva "quale allegato",
la pagina QSP poteva precedere il PDF ufficiale anche se il PDF era presente
e leggibile. Il ranking Lex ora riconosce le domande su allegato, PDF,
ordinanza, rimessione, nota o documento e promuove le evidenze con
`attachment_url` e testo OCR reale.

## Aggiornamento operativo 2.245.19 - 2026-05-18

Il test reale su Cassazione `QSP50194` ha evidenziato un secondo blocco:
l'OCR in produzione leggeva il PDF, ma il backfill non selezionava più il record
perché il database conteneva già evidenze web vecchie con allegato a
`context_chars=0`.

Da questa versione il backfill mirato con `--backfill-review-id` o
`--backfill-query` può rientrare sui record già tracciati, cerca anche in
`attachments_json` e nelle evidenze salvate, e aggiorna l'allegato normalizzato
quando il nuovo testo OCR è più ricco della prova precedente. Le vecchie prove
con `testo non estraibile` vengono sostituite dalla prova interrogabile, così
Lex può recuperare non solo pagina, URL e hash, ma anche il contenuto OCR
dell'ordinanza.

## Aggiornamento operativo 2.245.18 - 2026-05-18

La prova su Cassazione `QSP50194` ha confermato che la pagina ufficiale e
l'allegato pubblico vengono trovati: il database locale contiene il record e il
backfill mirato salva pagina, URL allegato e hash. Il problema reale era il
testo del PDF: l'allegato `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`
è una scansione e il percorso usato dagli aggiornamenti legali si fermava a
`context_chars=0`.

Da questa versione l'estrattore documentale usato dalla verifica web applica
OCR tramite `pypdfium2` e Tesseract quando un PDF ufficiale non contiene testo
selezionabile. In produzione il container include Tesseract italiano: il
backfill può quindi salvare anche il testo OCR dell'ordinanza, non solo la
prova di download. Se Tesseract non è disponibile nel runtime locale, il
warning resta esplicito e l'allegato continua comunque a essere conservato con
URL e hash.

## Aggiornamento operativo 2.245.15 - 2026-05-17

Il recupero delle evidenze web non dipende più solo dall'ordine del lotto
temporizzato. La CLI `python -m pct.legal_update_job --backfill-web-evidence`
accetta ora `--backfill-query` e `--backfill-review-id`: un riferimento preciso
già presente nel database, ad esempio `Circolare numero 53 del 07-05-2026`,
può essere completato subito leggendo la fonte ufficiale e i suoi allegati.

La selezione mirata cerca titolo, testo normalizzato, URL della fonte e sintesi
della revisione, includendo anche numeri brevi come `53`, `07` e `05`. Questo
serve a impedire che un record approvato resti fermo solo perché il backfill a
tempo non lo ha ancora raggiunto.

## Aggiornamento operativo 2.245.14 - 2026-05-17

La ricerca Lex sulle evidenze web non ordina più soltanto per freschezza o
numero di termini comuni. Il ranking assegna peso maggiore a titolo, URL,
allegato, numeri identificativi e frase esatta, così una ricerca puntuale come
`Messaggio numero 685 del 26-02-2026` deve riportare prima l'evidenza
verificata corrispondente e non un risultato INPS più recente ma generico.

Il bacino SQL dei candidati viene ampliato prima del ranking: questo evita che
un'evidenza esatta ma meno recente venga scartata troppo presto quando molte
fonti condividono parole comuni come `circolare`, `messaggio`, `numero` o
`2026`.

## Aggiornamento operativo 2.245.13 - 2026-05-17

Il recupero evidenze web è stato ristretto al perimetro che serve davvero allo
studio: per default vengono trattati solo record `pending`, `approved` e
`published`, mentre metadati chiusi e dataset open-data massivi restano esclusi
finché non vengono richiesti esplicitamente.

La modalità predefinita del backfill è ora "fonte diretta": legge la pagina
ufficiale già collegata al documento e gli allegati pubblici collegati, salva
URL, testo, PDF/hash quando disponibili e registra `insufficient` con motivo
esplicito quando la prova non basta. La ricerca web estesa resta disponibile,
ma deve essere richiesta come secondo passaggio perché è più lenta e va
governata per fonte.

La CLI accetta `--backfill-max-seconds`, `--backfill-status`,
`--backfill-include-closed`, `--backfill-include-open-data` e
`--backfill-full-search`. Questo impedisce job appesi e rende misurabile ogni
tranche: quanti record sono stati selezionati, controllati, salvati, con
allegati, fermati dal limite di tempo o lasciati con diagnosi interrogabile.

## Aggiornamento operativo 2.245.12 - 2026-05-17

Le evidenze web non dipendono piu' dalla sola coda di pubblicazione: ogni
documento nuovo o modificato da fonte governata registra subito una verifica
fonte con URL, testo letto, eventuali allegati ufficiali, hash e stato della
prova in `web_verification_evidence`.

La verifica parte dalla pagina originaria gia' acquisita, legge il contesto
ufficiale e gli allegati collegati, poi usa archivi ufficiali e ricerca web
governata come confronto. In questo modo la metrica delle evidenze misura
prove archiviate, non solo schede pubblicate.

E' disponibile il backfill operativo
`python -m pct.legal_update_job --backfill-web-evidence` per recuperare record
gia' normalizzati ma privi di prova web salvata.

## Aggiornamento operativo 2.245.11 - 2026-05-17

Sono state aggiunte e classificate le fonti richieste nella verifica manuale:
Corte dei Conti, Giustizia Amministrativa `Decisioni e pareri`, Studio Cataldi,
Avvocato Andreani e IusSearch.

La Corte dei Conti entra nel ciclo delle fonti ufficiali come fonte primaria:
portale istituzionale, pagina sentenze, pagina delibere e banca dati pubblica
sono registrati per ricerche su responsabilità erariale, giudizi contabili,
controllo/referto e appalti con profili contabili.

La pagina `https://www.giustizia-amministrativa.it/dcsnprr` è censita come
fonte ufficiale verificabile, ma non viene usata come canale automatico
principale finché rimangono instabili certificato, paginazione e recupero
allegati. Il presidio automatico resta OpenGA ufficiale, che è più adatto al
lavoro schedulato.

Studio Cataldi e Avvocato Andreani sono registrati solo come fonti secondarie
di consultazione rapida per codice civile, procedura civile, codice penale e
codice della strada. Non sono fonti ufficiali: Lex può usarle per orientare la
ricerca o confrontare il testo, ma non può pubblicare una scheda normativa
senza riscontro su Normattiva, Gazzetta Ufficiale o altra fonte primaria.

IusSearch è stato censito come motore di ricerca giuridica P2. Il sito risponde
da `http://www.iussearch.it/` con pagina in `ISO-8859-1` e form Google custom
su `/search`: può aiutare a trovare piste, non a chiudere una prova. Ogni URL
trovata tramite quel motore deve essere poi confermata e scaricata dalla fonte
originaria.

La ricerca web governata accetta ora anche URL dirette appartenenti a fonti
censite e le classifica con priorità e natura della fonte. Questo consente di
testare una fonte passando l'indirizzo esatto, senza fingere che un sito privato
o un motore di ricerca sia un archivio ufficiale.

## Aggiornamento operativo 2.245.10 - 2026-05-17

Il completamento web degli aggiornamenti legali non si ferma più al primo
riferimento non confermato: la coda valuta più candidati, registra ogni
tentativo, abbassa la priorità degli elementi senza conferme e continua con i
riferimenti successivi. Se il web non produce conferme sufficienti, IUSENTRA
salva comunque una diagnosi interrogabile nel database con query tentate,
fonti provate e motivo della mancata pubblicazione.

È stata introdotta la tabella `web_verification_evidence`, usata da Lex e
dalla ricerca legale insieme agli archivi `normative`, `jurisprudence`,
`prassi` e `news`. Le evidenze conservano fonte, query, URL ufficiale,
allegato, hash SHA-256, estratto, testo disponibile e stato della verifica.
Gli allegati verificati vengono collegati anche al documento normalizzato,
così una query successiva può recuperare l'evidenza e non solo il riferimento.

INPS viene letto attraverso il JSON ufficiale caricato dalla pagina pubblica
`dettaglio.content-fragment-detail...json`: il caso reale `Circolare numero
53 del 07-05-2026` salva testo, PDF principale e allegati; il caso `Messaggio
numero 685 del 26-02-2026` salva testo e PDF. La ricerca usa anche la query
minima del titolo e un piano esteso, non solo la fonte già agganciata al
record.

Cassazione QSP viene letta dalla pagina ufficiale e dagli allegati esposti:
per `qsp_dettaglio.page?contentId=QSP50202` viene scaricato il PDF
`14740_04_2026_pen_noindex.pdf`. Se il PDF non contiene testo estraibile, il
database registra comunque allegato, hash e nota di testo non estraibile, senza
dichiarare completamento testuale fittizio.

Gazzetta Ufficiale viene letta con un resolver diretto sull'archivio annuale
ufficiale quando la query contiene un codice redazionale o un riferimento
normativo puntuale. Il caso reale `26G00056` / `D.Lgs. 13 marzo 2026, n. 39`
viene risolto da `showArchivioNews?anno=2026` alla scheda ELI
`https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg`, con contesto
ufficiale e PDF del fascicolo GU. La pagina di aiuto `Formato Grafico PDF` non
viene più trattata come allegato.

Gli atti amministrativi di sola gestione contabile, ad esempio liquidazioni
fattura o mandati di pagamento privi di segnali come ricorso, appalto, gara,
contenzioso o accesso agli atti, vengono chiusi fuori perimetro e non diventano
news legali solo perché provengono da un sito pubblico.

## Aggiornamento operativo 2.245.9 - 2026-05-17

Il contesto ufficiale usato dal dataset Lex accetta ora solo URL appartenenti
al catalogo dei domini istituzionali riconosciuti o a domini di classe A nella
source policy. Domini simili, credenziali nell'URL e redirect verso domini non
riconosciuti vengono scartati prima di costruire contesto citabile.

La lettura degli allegati ufficiali conserva il vincolo sui domini ammessi e
non usa più etichette cumulative o CTA generiche come titolo dell'evidenza:
quando il link mostra solo formule tipo `Leggi la notizia` o `Scarica PDF`, il
dataset usa il nome file dell'allegato ufficiale scaricato e hashato.

## Aggiornamento operativo 2.245.8 - 2026-05-17

Lex non tratta più una richiesta redazionale con cliente, ad esempio
`scrivi diffida per il cliente Marco Moscato`, come semplice ricerca
anagrafica. Il profilo `bozza_lettera` forza il workflow redazionale,
poi il contesto studio autorizzato viene usato per compilare intestazione,
avvocato e cliente quando disponibili.

Le richieste operative su dati studio sono state verificate con test reali su
`/api/assistente/context` e `/api/assistente/chat`: dati cliente, recapiti,
PEC, telefono e ultime udienze vengono letti dagli archivi tenant-aware invece
di rispondere con base documentale insufficiente.

Le bozze Lex vengono restituite senza appendici `Fonti consultate` non
pertinenti quando il workflow è una lettera/diffida. Il widget rende la
risposta come documento leggibile: titoli, grassetto, corsivo, separatori,
elenchi e blocco documento. Se una bozza arriva già schiacciata in una riga,
la UI la normalizza prima del rendering.

È stato aggiunto il presidio UTF-8 `utf8-integrity`: CLI, servizio e job
notturno rilevano mojibake, caratteri sostitutivi e testi con accenti italiani
rotti. Le guardie Lex riparano l'output prima di mostrarlo all'utente.

## Aggiornamento operativo 2.245.5 - 2026-05-17

Il presidio creato per fonti, agenti notturni, archivi ufficiali e funzioni AI
avanzate e' ora esposto anche nelle pagine usate dallo studio:
`/ricerca-legale` e `/giurisprudenza/`. Non rimane confinato alle console
amministrative.

`/ricerca-legale` mostra una sezione `Presidio Lex AI` con agenti controllati,
ricerca completa su fonti ufficiali e allegati pubblici quando disponibili,
archivi Normattiva/Gazzetta locali e stato delle funzioni MTP, LLM Wiki,
GLM-OCR e Gemini Embedding 2 come presidi misurabili o da autorizzare.

`/giurisprudenza/` mostra `Citazioni verificate` e `Presidio Lex
giurisprudenza`: conteggio delle schede citabili, stato Cassazione, agenti
collegati, archivi ufficiali e allegati fonte letti se presenti. Le modalita'
di accesso sono rese in linguaggio operativo per l'avvocato, non con codici
interni.

## Aggiornamento operativo 2.243.5 - 2026-05-16

Aggiornamento 2.245.3: IUSENTRA ha ora micro-agenti Lex interni collegati
alla console pianificazioni e al job notturno `lex_operational_agents_nightly`.
Gli agenti non sono sub-processi liberi o comandi shell: derivano dai template
autorizzati, leggono solo archivi tenant-aware e salvano un inventario in
`lex_operational_agents.json`. La copertura include anagrafiche, fascicoli,
agenda/scadenze, preventivi/parcelle, PEC, posta ordinaria, documenti,
editor Lex, Cassazione, PCT, SDI/pagamenti, portale cliente, GDPR/AML, AI
locale/RAG e integrazioni. Se manca un archivio, un indice o una fonte
verificabile, l'esito resta `Da verificare` con chiavi mancanti e controllo
supervisore, invece di essere mostrato come completato.

Lo stesso aggiornamento estende il presidio pubblico: i codici fondamentali
su Normattiva (civile, procedura civile, penale, procedura penale, processo
amministrativo e strada) sono censiti come fonti di classe A, insieme al
presidio Cassazione per citazioni verificabili. Lex non deve pubblicare
massime, sezione, numero o data se non trova riscontro nel corpus ufficiale o
in una fonte ufficiale governata.

Aggiornamento 2.245.2: per Giustizia Amministrativa il canale HTML
istituzionale diretto e' stato messo in osservazione, perche' puo' fallire in
modo instabile durante crawler/SSL. Il presidio automatico principale passa a
OpenGA ufficiale (`openga_giustizia_amministrativa` e cartelle `openga_*`),
che espone dataset CKAN per sentenze, ordinanze, decreti, pareri,
provvedimenti, ricorsi e calendario udienze. Gli agenti fonte non marcano piu'
come completata una scansione che contiene errori interni: l'esito diventa
`failed`/da verificare e registra anche la soluzione alternativa applicata.
La stessa normalizzazione vale per gli esiti gia' salvati: un vecchio record
`completed` con errore dentro `payload_json.reports[].error` viene riletto come
`Da verificare`, cosi' la console non conserva stati falsamente positivi.
La pagina React `Archivio Giurisprudenza` traduce gli stati tecnici in esiti
operativi: `Da verificare`, `Aggiornata` o `Recupero assistito`; per la fonte
diretta amministrativa espone la nota di risoluzione verso OpenGA invece di
lasciare un errore non governato.
Lo stesso criterio e' applicato alle altre fonti giurisprudenziali: Cassazione
ha come canale automatico la pagina ufficiale delle ultime sentenze e ordinanze,
Corte costituzionale tenta direttamente lo ZIP open data se la pagina indice
fallisce, CURIA usa il feed RSS ufficiale e HUDOC espone il fallback RSS per
ricerche salvate.

Aggiornamento 2.245.0: le fonti legali sono governate anche come agenti
separati. Il batch con timeout resta il percorso notturno principale, ma ogni
fonte registra una run autonoma in `source_agent_runs` con stato, durata,
timeout, documenti trovati, documenti lavorati, invariati e messaggio di
errore. `/admin/aggiornamenti-legali/fonti` mostra l'ultimo esito agente per
canale e `/admin/pianificazioni` crea job `legal_source_<codice>` avviabili
manualmente o schedulabili dal superadmin, sempre da catalogo autorizzato e
senza comandi shell.

Aggiornamento 2.243.9: `/admin/aggiornamenti-legali/fonti` espone il
catalogo professionale delle fonti con famiglie, stato per canale,
conteggi reali, ciclo giornaliero e regole incrementali. Oltre alle fonti
richieste sono stati aggiunti presidi ufficiali scelti per gli studi legali:
INPS circolari/messaggi/sentenze, Curia CGUE, ISTAT prezzi, MIMIT incentivi,
AGCM, AGCOM e Banca d'Italia. INAIL e' censita come fonte in osservazione ma
non entra nel ciclo automatico finche' il canale pubblico non sara' leggibile
con stabilita' dal worker.

Aggiornamento 2.243.8: gli archivi locali ufficiali non restano piu'
separati dalla UI. La Ricerca Legale e la console admin Aggiornamenti legali
mostrano i conteggi reali di Normattiva/Gazzetta e, quando l'utente cerca, il
backend interroga prima `legal_updates.db`, poi `/data/normativa/normattiva.sqlite`
e `/data/fonti_ufficiali/lex_sources.sqlite`; solo se le evidenze locali non
bastano viene tentata la ricerca web governata. Questo rende visibili i
189.851 documenti, 800.757 articoli e 639.273 chunk Normattiva gia' presenti
sul volume Hetzner.

Lo scheduler 2.243.8 governa il ciclo quotidiano richiesto: alle 23:00 esegue
sincronizzazione degli archivi ufficiali, alle 23:10/23:15 passa a Update
Intelligence con timeout per fonte/pubblicazione. La sincronizzazione
Normattiva confronta il catalogo Open Data remoto con lo stato locale e non
riscarica ZIP gia' presenti e invariati; quando una collezione cambia mantiene
una sola copia per collezione/formato/vigenza. OpenGA viene trattata come fonte
ufficiale CKAN nelle cartelle Calendario Udienze, Decreti, Ordinanze, Pareri,
Provvedimenti pubblicati, Ricorsi definiti, Ricorsi pendenti, Ricorsi pervenuti
e Sentenze. La verifica pubblica legge anche contesto pagina e allegati
ufficiali collegati, cosi' Lex riceve evidenze testuali e non solo link.
Sono stati aggiunti anche presidi ufficiali ad alto valore per studi legali:
interpelli del Ministero del Lavoro, newsletter/provvedimenti del Garante
Privacy, atti ANAC e download tecnici del PST Giustizia.

Update Intelligence non pubblica piu' automaticamente una proposta strutturale solo per confidenza AI: prima dell'autopublish viene eseguita una verifica pubblica governata su archivio fonti ufficiali, Normattiva, Gazzetta e ricerca web allowlist. Per normativa, prassi e giurisprudenza servono almeno una fonte primaria e una seconda conferma coerente; in caso contrario la proposta resta in coda revisioni con una nota operativa.

Aggiornamento 2.243.6: lo staging non usa piu' la coda revisione come stato primario del documento grezzo. All'apertura di `/admin/aggiornamenti-legali/staging` viene tentata la riconciliazione automatica: duplicati chiusi, cataloghi open data archiviati come non pubblicabili, contenuti ufficiali utili ma non strutturali pubblicati come news informativa quando superano la verifica fonte.

I path di Normattiva e Gazzetta sono ora collegati ai volumi runtime (`/data/normativa` e `/data/fonti_ufficiali`) tramite variabili ambiente e fallback container-aware, cosi' Lex e il motore aggiornamenti usano gli archivi generati in produzione invece dei soli file smoke locali.

Verifica infrastrutturale del 2026-05-16: i database canonici Normattiva/Gazzetta non erano presenti su Railway ne' su Hetzner. Su Hetzner sono stati ricreati nel volume attivo: Gazzetta (`lex_sources.sqlite` 32.129.024 byte, JSONL 20.342.735 byte, 28 documenti e 3.911 chunk) e Normattiva (`normattiva.sqlite` 2.868.604.928 byte, JSONL 1.093.268.667 byte, 19 ZIP raw validi, 189.851 documenti, 800.757 articoli e 639.273 chunk). Il manifest ufficiale Normattiva letto da `https://dati.normattiva.it/assets/come_fare_per/Normattiva%20OpenData.html` espone 23 collezioni: 19 hanno restituito ZIP validi, mentre `Regolamenti di delegificazione`, `Regolamenti governativi`, `Regolamenti ministeriali` e `Testi Unici` hanno restituito stream vuoto `application/octet-stream` e sono tracciate nel manifest tentativi. Railway ha il volume `/data` al 100% (1.8 GB usati su 1.8 GB, con circa 1.3 GB in allegati email) e non puo' ospitare l'indice Normattiva completo finche' non viene aumentato o liberato spazio senza cancellare dati di studio.

Aggiornamento 2.243.7: il lotto notturno `legal_updates_batch`, la console admin e il comando CLI possono eseguire la scansione massiva come job isolati per fonte/pubblicazione con timeout per elemento (`IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS`, default 180s). Le verifiche web esterne restano attive, ma un elemento lento non blocca l'intero processo.

---

## Aggiornamento operativo 2.243.4 - 2026-05-16

Lex AI legge ora anche il registro mediazione interno popolato dai tre elenchi ufficiali del Ministero della Giustizia: Registro Organismi, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. Le evidenze sono marcate come fonte ufficiale di classe A e includono sezione, numero registro, denominazione o nominativo, stato, natura/tipo docente, territorio, codice fiscale, partita IVA, email e sito quando presenti.

La pagina `/ricerca-legale/mediazione` usa gli stessi dati acquisiti: non e' piu' un elenco di collegamenti, ma un archivio consultabile in IUSENTRA con ricerca e filtri. Lex riceve il contesto dal repository interno `normative_tables`, mentre il collegamento ministeriale resta riferimento di verifica.

La verifica API autenticata restituisce 3.038 schede: 3.035 record ministeriali piu' i tre accessi ufficiali. Il bridge usa l'identita' della riga importata e non l'URL ministeriale, cosi' i dati non vengono ridotti a una sola scheda per fonte.

OpenGA Giustizia Amministrativa e il gruppo `calendario-udienze` sono stati aggiunti al presidio Update Intelligence come fonti CKAN JSON; le risorse JSON disponibili vengono acquisite come testo consultabile per ricerca e Lex.

---

## Aggiornamento operativo 2.239.2 - 2026-05-16

La pagina React `Registro Mediazione` non dipende piu' dalla sola notizia di ripristino: espone tre schede di accesso ufficiale separate verso Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. Le schede sono disponibili anche nella Ricerca Legale per query su mediazione, enti e formatori, senza leggere dati privati dello studio e senza avviare una ricerca esterna.

---

## Aggiornamento operativo 2.238.2 - 2026-05-15

Le richieste Lex su sentenze specifiche con numero e date multiple, ad esempio `Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026`, non cadono piu' sul metadata `SourceScope.reason`: il campo e' compatibile con i payload debug e il workflow `giurisprudenza_specifica` continua a produrre risposta governata.

Per i riferimenti Cassazione esatti, Lex prioritizza `cassazione` tra le fonti ufficiali e, se la ricerca generica non e' necessaria, legge la pagina pubblica `Giurisprudenza Penale` della Corte. La query sopra individua la scheda ufficiale `https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP50042`; la risposta indica cosa e' certo e resta `needs_review` finche' mancano testo integrale, motivazione e dispositivo.

Il widget Lex non mostra piu' pagine HTML di errore dentro la conversazione. Se `/api/assistente/chat` fallisce prima dello stream, l'endpoint risponde con JSON controllato e la UI mostra un messaggio operativo breve, lasciando il dettaglio tecnico ai log applicativi.

---

## Aggiornamento operativo 2.238.0 - 2026-05-15

`/ricerca-legale` non e' piu' una vista con filtro locale sulle sole schede gia' caricate. La query viene passata a `/api/v1/ui/ricerca-legale?q=...`, cercata nel repository giuridico SQL tenant-aware e arricchita con fallback ufficiale governato quando non ci sono almeno due fonti ufficiali con estratto testuale sufficiente.

La notizia PST `NWS4865` sul ripristino dei registri mediazione e' presente come fonte ufficiale stabile in News e Ricerca Legale, con link al Portale dei Servizi Telematici, data 2026-05-11 e contesto del ripristino dal 22/04/2026.

---

## Aggiornamento operativo 2.237.9 - 2026-05-15

Lex Operational Knowledge e' ora attivo di default nel bounded workflow: le domande su clienti, fascicoli, agenda, scadenze, preventivi, conferimenti, fatturazione, messaggi, documenti e template passano dal layer deterministico tenant-aware senza richiedere `LEX_OPERATIONAL_KNOWLEDGE_ENABLED=1`.

La ricerca giuridica pubblica resta separata: richieste su sentenze specifiche, giurisprudenza, normativa, Normattiva, Gazzetta, Cassazione o fonti ufficiali vengono deferite al workflow pubblico/web governato e non sono intercettate dal layer dei dati di studio. Restano sempre attivi RBAC, isolamento tenant, blocco azioni dispositive e protezione dei dati riservati.

Il fallback web legale non viene piu' bloccato dalla sola presenza di contesto interno: per `ricerca_legale`, giurisprudenza, normativa e fonti ufficiali, se il contesto locale non basta a rispondere, il payload Lex abilita `allow_external_research` e richiede fonti ufficiali governate. Le risposte strict includono il contesto testuale delle fonti effettivamente usate; se una fonte e' solo nominata ma non porta un estratto, Lex degrada la risposta a `needs_review`.

---

## 1. Come Lex decide oggi se usare contesto interno

Il contesto studio viene costruito da `web/services/assistente_studio_context.py` tramite `build_lex_studio_context()`. La decisione avviene in due step:

### Step A — Selezione sezioni per keyword (`_select_detail_sections`)
Le sezioni vengono incluse in base a match testuale sulla domanda. Threshold: top 5 sezioni per punteggio.

| Sezione | Keyword trigger |
|---------|----------------|
| Clienti | "cliente", "clienti", "assistito", "anagrafica" |
| Fascicoli | "fascicolo", "fascicoli", "rg", "pratica", "causa" |
| Agenda | "agenda", "appuntamento", "udienza" |
| Scadenziario | "scadenza", "termine", "scadenze" |
| Fatturazione | "fattura", "parcella", "onorario" |

**Problema**: se la domanda è "dammi i dati del cliente Mario Rossi" ma il nome del cliente è in minuscolo e la sezione non viene triggerata per via di normalizzazioni, Lex non carica il contesto cliente.

### Step B — Caricamento dati (`_clienti_lines`)
```python
selected = matches[:4] if matches else all_rows[:4]
```
**Limite critico**: massimo 4 clienti. Se ci sono omonimi o la ricerca restituisce molti risultati, i dati dettagliati vengono tagliati. Il testo restituito è solo `nome_completo + stato + referente` — mancano CF, PEC, email, telefono, fascicoli.

---

## 2. Come Lex decide oggi se usare il web

La funzione `_should_force_web_fallback()` in `assistente_studio_context.py` forza ricerca web se:
- NON è una query solo operativa (agenda/fascicolo/cliente senza termini legali)
- NON c'è contesto locale specifico (`_has_specific_local_context` = False)
- Almeno un token legale è presente: norma, normativa, legge, decreto, sentenza, cassazione, tar, giurisprudenza, etc.

**Problema critico**: `_has_specific_local_context` restituisce True se ci sono fonti `cliente:*` o `fascicolo:*` nei sources, **bloccando la ricerca web anche per sentenze specifiche**. Se la domanda è "nel fascicolo Rossi trova la Sentenza n. 7919" → contesto fascicolo viene caricato → `_has_specific_local_context = True` → web bloccato → Lex usa solo il DB locale che non contiene quella sentenza.

---

## 3. Perché una sentenza specifica non forza ricerca web

Il router classifica correttamente "Sentenza n. 7919 del 31/03/2026" come `giurisprudenza_specifica` (priorità 7 in `lex/router.py`). Ma il retrieval layer non ha un meccanismo di "exact reference override": anche per `giurisprudenza_specifica`, se esiste qualsiasi fonte locale (anche solo `studio:default` o agenda), `_has_specific_local_context` può restituire True e bloccare il web.

Non esiste `case_law_reference_parser.py` che estragga numero+data da una query e forzi `public_web_forced=True`. Il sistema non distingue "dimmi delle sentenze sulla prescrizione" (generico) da "trovami la Sentenza n. 7919 del 31/03/2026" (riferimento esatto).

---

## 4. Perché vengono mostrate fonti correlate non richieste

Il motore di retrieval (`lex/retrieval/orchestrator.py`, `lex/research/public_legal_research_gateway.py`) non ha un "exact match guard". Quando cerca sul web governato, restituisce tutti i risultati rilevanti per il query semantico, non filtrati per numero/data sentenza. L'`answer_builder.py` non distingue tra "fonte esatta richiesta" e "fonti correlate non richieste".

Risultato: per "Sentenza n. 7919/2026" vengono mostrate le prime 5-12 sentenze che contengono termini simili, nessuna delle quali è necessariamente la 7919.

---

## 5. Perché confidence diventa media anche se manca testo integrale/dispositivo

In `lex/formatting/answer_builder.py`, la confidence viene calcolata su:
- numero di evidenze
- presenza di fonti ufficiali
- freshness score
- post-guard risk

Non considera se il testo integrale o il dispositivo della sentenza specifica è effettivamente nelle evidenze. Quindi: 3 sentenze correlate → confidence media (0.6-0.7) anche se nessuna è la sentenza richiesta e nessuna ha il testo integrale.

---

## 6. Perché il cliente presente nello studio può non essere letto

Cinque cause distinte:

1. **Keyword mismatch**: la sezione "Clienti" si attiva solo se la domanda contiene "cliente/assistito/anagrafica". "dammi i dati di Mario Rossi" → nessun trigger → sezione non caricata.
2. **Limite 4 risultati**: `_clienti_lines` ritorna max 4 clienti, testo ridotto a nome+stato.
3. **Cache stale**: TTL 90s — se i dati del cliente sono stati modificati di recente, la cache restituisce dati vecchi.
4. **Testo fonte insufficiente**: il campo `text` nella source è solo "Tipo: X. Stato: Y. Referente: Z." — mancano email, PEC, CF, fascicoli, note.
5. **No entity extraction**: la domanda non viene analizzata per estrarre nome proprio, CF, PIVA, email → la ricerca `gestore.cerca(question)` può non trovare il cliente se la domanda ha molte parole estranee.

---

## 7. Sezioni del contesto studio caricate

Le sezioni vengono selezionate da `_select_detail_sections_for_chat()` (chat mode) o `_select_detail_sections()` (default), massimo 4-5 sezioni per richiesta:

| Sezione | TTL cache | Contenuto |
|---------|-----------|-----------|
| Fascicoli | 90s | Titolo, RG, tribunale, oggetto — massimo 4 |
| Clienti | 90s | Nome, stato, referente — massimo 4 |
| Agenda | 60s | Appuntamenti prossimi 21 giorni — massimo 4 |
| Scadenziario | 60s | Scadenze imminenti — massimo 4 |
| Fatturazione | 120s | Parcelle recenti — massimo 4 |
| Template atti | 120s | Template disponibili — massimo 4 |
| Tariffario | 300s | Scaglioni DM 55 |
| Ricerca legale | 180s | Motori ricerca legale |
| Archivio sentenze | 120s | Sentenze indicizzate localmente |

---

## 8. Limiti di `_clienti_lines`

```python
def _clienti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_clienti()
    all_rows = gestore.tutti()
    stats = gestore.statistiche()
    matches = gestore.cerca(question) if _clean_spaces(question) else []
    selected = matches[:4] if matches else all_rows[:4]      # ← MAX 4
    sources = [_source(...)  for row in selected]           # ← solo nome+stato+referente
```

Limiti:
- Ritorna massimo 4 clienti
- Non include email, PEC, CF, PIVA, telefono, indirizzo
- Non include fascicoli collegati
- Non include documenti, note, tag
- Non fa entity extraction prima di chiamare `gestore.cerca()`
- Se `question` ha molte parole inutili, `cerca()` può non trovare il match

---

## 9. Limiti di `_select_detail_sections`

```python
def _select_detail_sections(question: str) -> set[str]:
    # Punteggio per keyword → top 5 sezioni
    return set(selected[:5])
```

Limiti:
- Nessuna entity extraction (nomi propri, CF, PIVA non triggerano sezioni)
- Massimo 5 sezioni → può scartare sezioni rilevanti se competono con altre
- Non distingue tra "cliente con dati anagrafici" e "cliente nel contesto di un fascicolo"
- Nessun meccanismo di force-include per intent specifici

---

## 10. Limiti di `_should_force_web_fallback`

```python
if _has_specific_local_context(local_sources):
    return False          # ← blocca web se c'è QUALSIASI fonte locale specifica
```

Limiti critici:
- Blocca ricerca web anche per `giurisprudenza_specifica` se c'è un fascicolo in contesto
- Non distingue exact reference (sentenza specifica) da query generica
- Non considera il workflow corrente (giurisprudenza_specifica dovrebbe sempre usare web)
- Nessun parametro `exact_reference` o `force_public_web`

---

## 11. Limiti di `official_web.search_recognized_official_web`

In `lex/retrieval/official_web.py`:
- Usa DuckDuckGo come motore di ricerca su domini allowlisted
- Non ha query optimizer per sentenze specifiche (no "site:cortedicassazione.it N. XXXX")
- Non fa exact match verification sui risultati: restituisce i primi N risultati per query semantica
- Nessun filtro per numero/anno sentenza
- Non distingue tra "trovato documento esatto" e "trovato documento correlato"
- Cache TTL 900s — query per "Sentenza 7919/2026" può restituire risultati cached per query diverse

---

## 12. Cosa va corretto (piano di azione)

| Problema | Soluzione | Fase |
|----------|-----------|------|
| Sentenza specifica non forza web | `case_law_reference_parser.py` + `exact_legal_reference_guard.py` | 4, 5 |
| `_has_specific_local_context` blocca web per sentenze specifiche | Modifica `_should_force_web_fallback` per bypassare se exact reference | 6 |
| Clienti non letti (keyword mismatch) | Entity extraction + intent `cliente_anagrafica` | 9, 10 |
| Max 4 clienti con dati ridotti | `studio_data_gateway.py` con dati completi | 8 |
| Risultati correlati presentati come fonte | `exact_legal_reference_guard.py` filtro post-retrieval | 5 |
| Confidence media senza testo integrale | Confidence cap in `exact_legal_reference_guard.py` | 5 |
| Nessuna classificazione public/private scope | `source_scope_policy.py` | 2 |
| Debug insufficiente | Aggiornamento `debug_payload_builder.py` | 12 |

---

## Aggiornamento Fase 9 fonti verdi - 19 maggio 2026

Il popolamento fonti pubbliche è stato esteso solo al perimetro verde: Cassazione ultime, Corte dei conti, Curia CGUE, INPS circolari/messaggi, AGCOM, ANAC, Garante Privacy e Gazzetta Ufficiale. Le fonti in osservazione restano escluse; OpenGA, PST, Dati Normattiva, EUR-Lex e ISTAT sono RAG-only/no-publish; Normattiva e codici sono archivi locali. Esito operativo: 1533 documenti letti dal perimetro controllato, 33 processati, 14 pubblicati guarded, 11 scartati dal guarded, 17 PDF/OCR, 340 riferimenti e 740 domande contestuali nei report. Ricerca Legale e Lex leggono le evidenze, ma non pubblicano cataloghi tecnici come aggiornamenti giuridici.

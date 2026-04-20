# Changelog

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





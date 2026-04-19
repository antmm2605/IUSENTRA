# Changelog

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





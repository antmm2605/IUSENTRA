# Presidio processuale e controllo economico fascicoli - implementazione

Data: 07/07/2026.

## Obiettivo

Rendere il presidio documenti/fascicoli più vicino al lavoro reale dell'avvocato: il sistema deve classificare i documenti dal contenuto, anche quando il nome o il tipo importato da QuickOrganizer/Studio Telematico sono generici o sbagliati, e poi usare la classificazione per estrarre dati, scadenze e importi.

Caso guida reale: ricevuta telematica pagoPA `rt_33E000GLVE6L4BIFLARMYPA0VKIRL7DIRYT.xml` importata come `ATTO_GIUDIZIARIO`, con contributo unificato da `€ 49,00`, non valorizzata nel controllo economico.

## Fonti e ricerche

Archivio completo salvato in:

- `artifacts/react-migration/presidio-processuale-ricerche-fonti-2026-07-07.md`

Fonti operative principali:

- Gazzetta Ufficiale: c.p.c. artt. 91, 93, 127-bis, 127-ter, 133, 171-bis, 171-ter, 415, 420, 445-bis, 543, 569, 633, 645, 648, 657, 658, 660, 664.
- DPR 115/2002: contributo unificato, omesso/insufficiente pagamento, gratuito patrocinio.
- PST Giustizia: pagoPA, ricevute RT XML, PCT, PDP, DM 44/2011, errori controlli deposito.
- AgID: PEC, ricevute, daticert, postacert.
- Giustizia Amministrativa: PAT e Formweb prioritario dal 01/02/2026.
- DEF/MEF e Agenzia Entrate: processo tributario, PTT, termini documenti/memorie.

## Cambiamenti codice

- Nuovo ruleset centrale `pct/presidio_processuale_ruleset.py`:
  - normalizzazione testo;
  - parser minimo RG/date/importi;
  - riconoscimento RT XML pagoPA;
  - regole per sentenze, spese, distrazione, compensazione, gratuito patrocinio, CU pagamento/esenzione/invito;
  - regole per udienze 127-bis/127-ter, decreti udienza, memorie 171-ter, rito lavoro, amministrativo, penale;
  - regole aggiunte da ricerca approfondita: decreto ingiuntivo/opposizione, sfratto/convalida, esecuzione/pignoramento/UNEP, ATP/CTU, mediazione/negoziazione, notifiche digitali PA, crisi d'impresa/concorsuale;
  - ulteriore ampliamento ricerche: Cassazione civile, SIAMM/LSG separato dal gratuito patrocinio, Giudice di Pace/SIGP, volontaria giurisdizione/Tribunale Online, famiglia/minori/ascolto del minore, appelli civili/lavoro/amministrativi/tributari.
- `pct/fascicolo_document_catalog.py`:
  - la ricevuta RT XML ministeriale viene classificata come `Contributo unificato / pagamento` anche se importata come `ATTO_GIUDIZIARIO`;
  - `Pagamento cu`, `CU`, `C.U.`, `0702100TS`, `CONTRIB`, `datiSpecificiRiscossione` entrano nella logica CU;
  - autocertificazione/esenzione CU viene distinta dall'allegato generico;
  - gratuito patrocinio ha classe dedicata;
  - SIAMM/LSG generico ha classe separata `Liquidazione spese di giustizia / SIAMM`, così non viene scambiato automaticamente per gratuito patrocinio;
  - la comunicazione generica non intercetta più prima una ricevuta CU;
  - i ricorsi restano atto principale anche se appartengono a procedimenti speciali.
- `web/services/react_fascicoli_bridge.py`:
  - i documenti XML sono candidati alla lettura economica automatica;
  - un RT XML diventa fonte CU solo se contiene marcatori di contributo/spese di giustizia;
  - il nome documento mostrato come fonte privilegia il nome visibile del portale/fascicolo (`rt_...xml`) rispetto al nome tecnico numerico.

## Test eseguiti

- `python -m py_compile pct/presidio_processuale_ruleset.py pct/fascicolo_document_catalog.py web/services/react_fascicoli_bridge.py`
- `python -m pytest tests/test_presidio_processuale_ruleset.py tests/test_fascicolo_document_catalog.py -q`
- `python -m pytest tests/test_react_shell.py -k "rt_xml or autocertificazione or pagamento_cu or contributo_unificato or candidati_documentali" -q`
- `python -m pytest tests/test_fascicolo_sentenza_economica.py tests/test_backfill_sentenza_lex_economics.py -q`

## Verifica locale reale

Eseguita il 07/07/2026 su `http://127.0.0.1:8080` dopo rebuild Docker reale di `app`, `scheduler-worker` e `ocr-worker`.

Osservato nella UI React `Fascicoli > Economica`:

- pagina caricata sul container healthy `2.253.196`;
- tab `Economica` selezionato;
- card visibili con `DOPPIONI 0`, `PARCELLE 2`, `DOCUMENTI 75`;
- riga economica reale con `Contributo € 98,00`, `Spese/esborsi € 125,00`, `Liquidazione € 1.500,00`, `Parcella € 2.028,20`;
- messaggio professionale `Bozza proforma da visionare`, senza esporre `sentenza_key`, `document_id` o path tenant;
- scroll fino al fondo: sezione `Cabina fascicoli`, alert operativi e azioni rapide visibili;
- focus tastiera sul tab `Economica` mantenuto leggibile.

Per la sola prova locale è stato creato e poi rimosso l'utente tecnico temporaneo `codex_presidio_test` nel tenant locale `studio-montagnese`.

## Esito test tecnico

Verificato in test:

- RT XML importato come `ATTO_GIUDIZIARIO` popola il controllo economico con:
  - stato `pagato`;
  - importo `€ 49,00`;
  - data `12/05/2026`;
  - fonte `rt_33E000GLVE6L4BIFLARMYPA0VKIRL7DIRYT.xml`.
- PEC/EML `Richiesta pagamento annualità Carta Docente` nello stesso fascicolo non viene usata come pagamento CU.
- Autocertificazione esenzione CU non resta allegato generico.
- Istanza liquidazione SIAMM/gratuito patrocinio viene classificata come presidio economico dedicato.
- Istanza SIAMM generica per CTU/liquidazione spese di giustizia non viene più classificata come gratuito patrocinio.
- Cassazione civile, Giudice di Pace/SIGP, volontaria giurisdizione, famiglia/minori e appelli hanno classi documentali dedicate.

## Correzione produzione durante verifica

Durante la verifica server su `https://app.iusentra.it/fascicoli?vista=economica` dopo il primo deploy, la pagina caricava gli asset e Lex ma non montava la shell React: il contenitore `#root` restava vuoto. Prima di validare il controllo economico è stato corretto `frontend/src/main.tsx`:

- le pagine studio/prodotto montano sempre sul root applicativo `#root` o `#iusentra-react-root`;
- la stanza operatore usa `#support-operator-react-root` solo nella pagina dedicata all'assistenza remota;
- la modifica rigenera l'hash dell'entry React, evitando il riuso del vecchio asset principale nella sessione browser dopo deploy.

Durante la seconda verifica server, il bundle corretto risultava servito ma la pagina restava comunque muta nel browser reale. Per evitare altri falsi verdi e rendere il difetto diagnosticabile sono stati aggiunti:

- stato runtime `window.__IUSENTRA_REACT_BOOTSTRAP_STATE__` in `frontend/src/main.tsx`;
- cattura errori `error`/`unhandledrejection` nella shell React;
- tentativo automatico di import dell'entry React se `#root` resta vuoto dopo il caricamento;
- messaggio utente `Interfaccia non avviata` con azione `Ricarica` invece di pagina bianca.

Questa protezione non sostituisce la prova reale: serve a impedire una UI muta e a rendere visibile il problema se un browser o un deploy non avvia l'entry.

Durante la verifica successiva il browser reale mostrava il fallback, ma il dettaglio tecnico indicava un import dinamico fallito dell'entry Vite. Poiché il file hashato era presente e servito correttamente dal server, è stato aggiunto un recupero anti-cache fallita:

- il retry dell'entry React usa una URL tecnica nuova con `iu_boot_retry`, così un fallimento temporaneo durante deploy non avvelena la sessione del browser;
- il messaggio visibile all'avvocato non espone più errori grezzi del browser come `Failed to fetch dynamically imported module`;
- il dettaglio tecnico resta tracciato solo come conteggio interno `data-error-count`, senza mostrare path o stack a video;
- la shell scrive anche marcatori DOM invisibili (`data-last-error`, `data-iusentra-entry-script`, `data-iusentra-entry-retry`) per distinguere errore di caricamento, errore di retry e mancato mount durante la verifica reale;
- il controllo statico `frontend/scripts/check-react-contracts.mjs` impedisce la regressione del retry e dei messaggi tecnici visibili.

## Verifiche ancora necessarie prima della chiusura

- Deploy Hetzner e verifica server `https://app.iusentra.it`.
- Controllare il fascicolo reale `Alfano Giuseppe / RG 1100/2026` e altri fascicoli con RT XML/autocertificazioni.
- Commit, push branch gemelli, deploy, container unico `iusentra-app`, `/api/pronto`, prune Docker.

Stato: implementazione tecnica, test mirati e prova reale locale completati; resta la prova server Hetzner sul tenant produzione prima del report finale positivo.

## Aggiornamento bootstrap React del 07/07/2026

Durante il test visivo richiesto su `https://app.iusentra.it/fascicoli?vista=economica` è emerso che il fallback `Interfaccia non avviata` poteva comparire mentre il modulo React principale era ancora in caricamento. La causa operativa non era il presidio economico, ma il root vuoto durante il download del chunk applicativo: il controllo di sicurezza della shell lo interpretava come mancato avvio.

Correzione applicata:

- `frontend/src/main.tsx` crea il root React una sola volta;
- viene renderizzato subito lo stato `Caricamento interfaccia operativa`, con testo comprensibile per lo studio;
- il chunk applicativo viene caricato dopo il primo render, poi sostituito dall'app reale;
- lo stato tecnico distingue `renderScheduled` e `renderCompleted`;
- `frontend/scripts/check-react-contracts.mjs` impedisce regressioni su caricamento governato, completamento mount e CSS dello stato di caricamento;
- versione applicativa portata a `2.254.1`.

Test eseguiti dopo la correzione:

- `pnpm --filter @iusentra/studio build:vite`;
- `node frontend/scripts/check-react-contracts.mjs`;
- `python -m pytest tests/test_react_shell.py -k "mobile_sblocca_scroll_e_compatta_card or sidebar_usa_profilo_reale_sessione or rt_xml or autocertificazione or pagamento_cu or contributo_unificato or candidati_documentali" -q`;
- `python -m pytest tests/test_presidio_processuale_ruleset.py tests/test_fascicolo_document_catalog.py -q`;
- `python -m pytest tests/test_fascicolo_sentenza_economica.py tests/test_backfill_sentenza_lex_economics.py -q`;
- controllo manifest React: entry `assets/index-BEaP1Vwa.js`, asset mancanti `0`.

Stato: da committare, pushare sui branch gemelli, distribuire su Hetzner e verificare visivamente in produzione prima di dichiarare positivo il funzionamento del controllo economico.

## Aggiornamento bootstrap React 2.254.2 del 07/07/2026

Nel test visivo successivo su `https://app.iusentra.it/fascicoli?vista=economica` il browser reale mostrava ancora `Pagina non avviata`. Il DOM indicava:

- entry React servita dal server;
- `#root` popolato dal fallback tecnico;
- errore di import dinamico dell'entry dopo retry;
- nessuna riga economica visibile, quindi nessuna verifica positiva possibile sui dati.

La causa tecnica era nel grafo Vite: l'entry iniziale importava React/ReactDOM e fungeva anche da helper condiviso per i chunk dinamici. In produzione questo rendeva fragile il primo caricamento e poteva lasciare la shell senza mount. Correzione applicata:

- `frontend/src/main.tsx` ora è un bootstrap leggero senza import statico di React o ReactDOM;
- il bootstrap scrive subito nel `#root` lo stato `Caricamento interfaccia operativa`;
- il mount React vive in `frontend/src/reactEntry.tsx`;
- `reactEntry` risolve il componente anche quando Vite minifica il default export in export nominato;
- `frontend/vite.config.ts` usa `cssCodeSplit: false` per evitare chunk CSS che reimportano l'entry;
- `web/blueprints/react_shell.py` include anche `style.css` quando Vite produce un CSS globale;
- `frontend/scripts/check-react-contracts.mjs` presidia entry leggero, CSS globale e risoluzione sicura del componente.

Test mirati eseguiti:

- `pnpm --filter @iusentra/studio build:vite`;
- `node frontend/scripts/check-react-contracts.mjs`;
- `python scripts/react-migration/generate_api_contracts.py`;
- `python scripts/validate_openapi.py docs/openapi.yaml`;
- `python scripts/verify_openapi_provider.py`;
- `python -m pytest tests/test_openapi_contracts_phase6.py --tb=short -q`;
- `python -m pytest tests/test_react_shell.py::test_react_shell_mobile_sblocca_scroll_e_compatta_card tests/test_react_shell.py::test_react_shell_sidebar_usa_profilo_reale_sessione tests/test_react_shell.py::test_react_shell_app_v2_route_operativa_e_spegnibile_da_feature_flag -q`;
- `python -m pytest tests/test_fascicolo_sentenza_economica.py tests/test_backfill_sentenza_lex_economics.py -q`;
- `python -m pytest tests/test_presidio_processuale_ruleset.py tests/test_fascicolo_document_catalog.py -q`;
- `python -m pytest tests/test_utf8_integrity.py -q`.

Nota test: il run monolitico `python -m pytest tests/test_react_shell.py -q` è stato interrotto per timeout dopo oltre 240 secondi; i tre casi direttamente collegati al bootstrap/shell sono passati. Resta obbligatoria la verifica visiva in produzione dopo deploy.

## Aggiornamento anti-cache React 2.254.3 del 07/07/2026

Durante la prova visiva reale su `https://app.iusentra.it/fascicoli?vista=economica`, dopo il deploy 2.254.2, la pagina mostrava ancora `Pagina non avviata`. Il server serviva correttamente il nuovo `reactEntry` e `/api/pronto` rispondeva con versione `2.254.2`, ma il browser integrato stava eseguendo una copia cache dell'entry React precedente: il testo visibile era quello vecchio e l'import dinamico cercava ancora `/static/pagina/assets/reactEntry-...`.

Correzione applicata:

- `web/templates/react_shell.html` aggiunge `?v={{ app_version }}` a CSS React, modulepreload e script entry React;
- i guardrail `tests/test_react_shell.py` e `frontend/scripts/check-react-contracts.mjs` pretendono ora l'entry React versionata;
- versione applicativa portata a `2.254.3`;
- `docs/openapi.yaml`, `docs/api-endpoint-contract-map.md` e `docs/api-contracts.md` rigenerati.

Obiettivo della correzione: il browser reale dello studio deve scaricare il bundle corrente dopo ogni deploy e non deve restare agganciato a un entrypoint cacheato che impedisce la visualizzazione dei fascicoli e del controllo economico.

Stato: da testare con build, deploy Hetzner, container unico `iusentra-app`, `/api/pronto` versione `2.254.3` e prova visiva della vista economica in produzione.

## Aggiornamento grafo Vite React 2.254.4 del 07/07/2026

La prova visiva dopo il deploy 2.254.3 ha confermato che il browser scaricava l'entry versionata, ma l'avvio falliva ancora. Il titolo e il percorso tecnico apparivano alterati dal guard visibile (`React` trasformato in `pagina`), mentre il dataset tecnico indicava ancora il fallimento dell'import di `reactEntry`.

Analisi del bundle:

- `main.tsx` importava dinamicamente `reactEntry`;
- `reactEntry` importava dinamicamente `App`;
- Vite inseriva nel chunk `reactEntry` l'import dell'helper esportato da `index-...js`;
- questo creava un ciclo `index -> reactEntry -> index` durante il bootstrap.

Correzione applicata:

- `frontend/src/reactEntry.tsx` importa staticamente `App` e `SupportOperatorRoom`;
- `main.tsx` resta l'unico bootstrap dinamico e leggero;
- `main.tsx` esegue il bootstrap solo quando l'entry arriva dalla shell versionata (`?v=...`) o dal retry anti-cache (`iu_boot_retry`), così l'import interno di Vite senza query non rimonta la pagina;
- `frontend/scripts/check-react-contracts.mjs` impedisce gli import dinamici dentro `reactEntry` e presidia il guard anti-doppio-bootstrap basato su `import.meta.url`;
- versione applicativa portata a `2.254.4`;
- build Vite rigenerata con `reactEntry-k1_nZBOP.js` autonomo, senza import verso `index-...js`.

Obiettivo della correzione: la pagina fascicoli deve montare React senza ciclo di bootstrap e mostrare la vista economica reale, non il fallback tecnico.

## Aggiornamento bootstrap statico React 2.254.5 del 07/07/2026

La prova visiva reale dopo il deploy 2.254.4 su `https://app.iusentra.it/fascicoli?vista=economica` ha smentito il verde tecnico: il server serviva `reactEntry-DoJMBFzJ.js` con HTTP 200, ma il browser continuava a mostrare `Pagina non avviata` con errore `Failed to fetch dynamically imported module`. Quindi il problema non era solo cache o file mancante: il punto fragile restava l'import dinamico dell'entry operativo.

Correzione applicata:

- `frontend/src/main.tsx` importa staticamente `mountReactApp` da `./reactEntry`;
- resta il guard su `import.meta.url` per eseguire il bootstrap solo dalla shell versionata o dal retry governato;
- `frontend/scripts/check-react-contracts.mjs` vieta l'import dinamico di `reactEntry` in produzione;
- versione applicativa portata a `2.254.5`;
- da rigenerare build Vite e `docs/openapi.yaml`, quindi ripetere test mirati, commit, push, deploy Hetzner e prova visiva reale.

Obiettivo della correzione: eliminare il download dinamico runtime che bloccava la vista economica, facendo caricare il grafo React come entry principale versionata e verificabile dal browser reale.

## Aggiornamento entry inline React 2.254.6 del 07/07/2026

La prova visiva reale dopo il deploy 2.254.5 su `https://app.iusentra.it/fascicoli?vista=economica` ha confermato ancora esito negativo: la pagina mostrava `Pagina non avviata`, `#root` restava vuoto e la telemetria della shell indicava `iusentraEntryScript=error`. Il server, però, serviva l'asset principale `index-DiZ6ab-o.js?v=2.254.5` con HTTP 200 e content type JavaScript. Quindi il blocco non era un file assente, ma il caricamento del modulo principale esterno nel browser reale.

Correzione applicata:

- `web/blueprints/react_shell.py` legge l'entry Vite hashata dal manifest e la prepara come `inline_entry_code`;
- gli import statici e dinamici relativi dell'entry vengono riscritti verso `/static/react/assets/...`, così il modulo inline mantiene il grafo Vite corretto;
- l'entry inline è cacheata per `mtime_ns`, evitando letture disco ripetute a ogni richiesta;
- `web/templates/react_shell.html` usa l'entry inline come caricamento primario e conserva lo script esterno solo se il codice inline non è disponibile;
- il watchdog React usa `data-iusentra-react-entry` come sorgente diagnostica e continua a mostrare un errore governato se il mount non avviene;
- `tests/test_react_shell.py` e `frontend/scripts/check-react-contracts.mjs` presidiano l'entry inline e la riscrittura degli import;
- versione applicativa portata a `2.254.6`.

Obiettivo della correzione: togliere dal percorso primario il caricamento del modulo entry esterno che sul browser reale restava rosso, senza cambiare la logica dei fascicoli o dei dati economici. La vista economica va considerata verificabile solo dopo nuova prova visiva reale in produzione con tabella caricata e interazioni eseguite.

## Aggiornamento entry autosufficiente React 2.254.7 del 07/07/2026

La prova visiva reale dopo il deploy 2.254.6 ha mostrato ancora `Pagina non avviata`. L'HTML autenticato consegnava correttamente l'entry inline e riscriveva gli import verso `/static/react/assets/...`, ma il browser non completava l'esecuzione del modulo e il retry esterno restava su `Failed to fetch dynamically imported module`.

Correzione applicata:

- `frontend/vite.config.ts` usa `inlineDynamicImports: true` e rimuove i `manualChunks`, così l'entry React di produzione non dipende da chunk ESM `vendor` separati prima del mount;
- `frontend/src/main.tsx` accetta il segnale `window.__IUSENTRA_INLINE_REACT_ENTRY__ === true`, necessario perché `import.meta.url` in un modulo inline non è l'URL dell'asset hashato;
- `web/templates/react_shell.html` arma il flag inline prima del modulo e conserva telemetria `inline-armed` / `loaded`;
- `frontend/scripts/check-react-contracts.mjs` presidia flag inline, entry autosufficiente e assenza di `manualChunks`;
- versione applicativa portata a `2.254.7`.

Obiettivo della correzione: rendere il primo caricamento React indipendente da fetch ESM secondari nel browser reale dello studio, poi verificare materialmente la vista economica in produzione.

## Aggiornamento presidio proforma automatico 2.254.8 del 07/07/2026

Durante il test visivo reale su `https://app.iusentra.it/fascicoli?vista=economica` la vista economica risultava popolata con dati effettivi di fascicolo, importi, stato contributo unificato, liquidazioni, parcelle e fonti documentali. Esempi verificati: `RG 3950/2026` con contributo pagato `€ 21,50`, `RG 3685/2026` con contributo pagato `€ 49,00`, liquidazione `€ 1.100,00` e bozza proforma automatica, `RG 2848/2026` con contributo non dovuto/esente da autocertificazione.

Difetto emerso: il processo automatico di presidio proforma poteva mostrare il toast rosso generico `Presidio economico non completato.` anche quando la tabella era correttamente popolata e l'avvocato non aveva un'azione concreta da svolgere su quel messaggio.

Correzione applicata:

- il presidio proforma automatico resta attivo in vista economica quando esistono parcelle da emettere;
- se vengono create nuove bozze proforma, resta il toast positivo e la vista viene aggiornata;
- se il processo automatico fallisce con il messaggio tecnico generico, non viene più mostrato un errore rosso all'avvocato;
- se il backend restituisce un errore specifico e utile, la UI lo presenta come avviso operativo: `Presidio automatico proforma da ricontrollare: ...`;
- `frontend/scripts/check-react-contracts.mjs` presidia che il default tecnico non torni come toast `danger`.

Obiettivo della correzione: la vista economica deve essere un supporto professionale, non un pannello che genera allarmi generici. L'avvocato deve vedere dati letti, fonte documentale, bozza proforma da visionare e stati economici; gli errori automatici devono essere mostrati solo quando sono specifici e azionabili.

Stato: da rigenerare build, eseguire test mirati, deploy Hetzner `2.254.8` e ripetere prova visiva reale in produzione verificando caricamento React, assenza del toast generico, dati economici popolati e interazione sulla tabella.

## Aggiornamento typecheck 2.254.9 del 07/07/2026

Dopo il push di `2.254.8`, GitHub ha confermato CodeQL verde ma ha bloccato il gate `Frontend React typecheck` per due motivi:

- il nuovo tono `warning` del toast non era incluso nel tipo locale del componente Fascicoli;
- `frontend/src/main.tsx` accedeva a `import.meta.env.DEV` senza tipizzazione esplicita in ambiente `tsc --noEmit`.

Correzione applicata:

- il toast della lista fascicoli accetta ora `success`, `warning` e `danger`;
- `FascicoliPage.css` contiene lo stile governato `.iu-fas-toast--warning`, sobrio e non rosso;
- `main.tsx` legge `import.meta.env.DEV` tramite cast tipizzato locale, evitando regressioni TypeScript senza cambiare il bootstrap React;
- il contratto React verifica anche lo stile warning della vista economica.

Stato: da rigenerare bundle, contratti API versione `2.254.9`, test mirati, commit/push, attesa check GitHub, deploy Hetzner e nuova prova visiva reale.

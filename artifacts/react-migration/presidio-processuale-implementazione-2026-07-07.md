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

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

## Verifiche ancora necessarie prima della chiusura

- Deploy Hetzner e verifica server `https://app.iusentra.it`.
- Controllare il fascicolo reale `Alfano Giuseppe / RG 1100/2026` e altri fascicoli con RT XML/autocertificazioni.
- Commit, push branch gemelli, deploy, container unico `iusentra-app`, `/api/pronto`, prune Docker.

Stato: implementazione tecnica, test mirati e prova reale locale completati; resta la prova server Hetzner sul tenant produzione prima del report finale positivo.

# Report OCR, Lex Sentenza ed economia

Data: 25 giugno 2026

## Obiettivo

Rendere la lettura OCR una sorgente unica e governata per Document AI, Lex AI,
PEC, notifiche e deposito, e correggere la matrice economica delle sentenze
prima che alimenti fatturazione e DB vettoriale.

## Decisioni operative

- Unlimited-OCR resta un motore opzionale, self-hosted e spento di default.
- La sorgente OCR per Lex AI resta integrale: testo completo, pagine, hash,
  manifest e warning. I chunk sono solo una fase successiva dell'indice
  vettoriale, non il modo in cui viene letto il PDF.
- `pct.ocr.estrai_testo` delega prima a Document AI e poi usa fallback locale
  storico solo se il percorso comune non produce testo.
- PEC, notifiche e deposito non devono reintrodurre parser PDF/OCR paralleli:
  usano Document AI o l'adapter comune.

## Regole economiche

- `liquidazione_giudice`: importo spettante allo studio, estratto da formule
  esplicite di compenso/onorari.
- `spese_esborsi`: spese vive o esborsi riconosciuti in sentenza, separati dal
  contributo unificato.
- `contributo_unificato`: importo riportato solo se presente in un PDF/documento
  CU/PagoPA del fascicolo. Valore causa, scaglione, spese CTU o importi generici
  non alimentano il CU.
- Esenzione CU: se il fascicolo contiene `contributo unificato non dovuto`,
  `esente dal pagamento del contributo unificato`, `patrocinio a spese dello
  Stato` o `prenotazione a debito`, il pagamento CU viene salvato come
  `non_previsto`, senza importo e senza voce proforma.

## Bonifica tenant locale

Tenant: `tenant-8bf98719c459`.

Backfill eseguito:

```powershell
python scripts\backfill_sentenza_lex_economics.py --tenant tenant-8bf98719c459 --reset-lex-amounts --apply --report artifacts\unlimited-ocr\sentenza-economia-reset-apply-v5-rag-clean-20260625.json
```

Esito:

- `documents_seen=667`
- `raw_sentenze_found=14`
- `sentenze_found=7`
- `applied=1`
- `matrix_confirmed=1`
- `vector_indexed=1`
- `vector_embedding_errors=0`
- `reset_vector_documents_removed=4`
- `reset_vector_chunks_removed=6`

Caso `DC5BF1DB`:

- liquidazione giudice: `1500,00`
- contributo unificato da PDF fascicolo: `98,00`
- spese/esborsi: `125,00`
- proforma Lex: `c6a1c268-2f55-4583-9ac9-ca2d90c316c1`
- totale proforma: `2126,20`
- indice RAG: un solo documento `lex_sentenza_tribunale`, schema
  `sentenza_tribunale_compact_v4`, 2 chunk embedded a 768 dimensioni.

Caso `AF656B01`:

- nessun pagamento Lex residuo;
- nessuna proforma Lex residua;
- nessun documento RAG `lex_sentenza_tribunale` residuo con il falso importo
  `5200,00`.

## Integrità dati

- `studio.db`: `PRAGMA integrity_check=ok`.
- `intelligence/local_ai.db`: `PRAGMA integrity_check=ok`.
- `audit_data_flow_contract.py` repair e cold: ok.
- `audit_tenant_data_structure.py` repair e cold: ok.
- Stato dati: `source_of_truth=sqlite`, `json_authoritative=false`,
  `operational_untracked=0`, zero warning e zero errori.

## Test eseguiti

- `python -m compileall pct\ocr.py pct\fascicolo_sentenza_economica.py pct\pec_pipeline.py web\services\document_intelligence_runtime.py scripts\backfill_sentenza_lex_economics.py`
- `python -m pytest tests/test_ocr_pipeline_adapter.py tests/test_fascicolo_sentenza_economica.py tests/test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline tests/test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag tests/test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler -q`
- `python -m pytest tests/test_fascicolo_sentenza_economica.py tests/test_backfill_sentenza_lex_economics.py tests/test_ocr_pipeline_adapter.py tests/test_unlimited_ocr_integration.py tests/test_legal_ocr_structured.py tests/test_document_intelligence_extraction.py tests/test_document_intelligence_auto_indexing.py tests/test_legal_ocr_pipeline.py tests/test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline tests/test_pec_auto_acquire.py -q`

## Stato prova reale

Prova materiale eseguita nel browser integrato su `http://127.0.0.1:8080`,
Docker locale `2.253.118`:

- `/fascicoli?vista=economica`: card Alessi Robertino visibile in layout
  compatto con `Contributo unificato da PDF EUR 98,00`, `Spese/esborsi
  EUR 125,00`, `Liquidazione giudice EUR 1.500,00`, `Parcella EUR 2.126,20`;
  nessun importo falso `5.200`.
- `/fatturazione`: proforma `2026/001`, origine `Sentenza Lex AI`, cliente
  Alessi Robertino, totale `EUR 2.126,20`; dettaglio aperto con voci
  `Compensi liquidati in sentenza EUR 1.500,00`, `Contributo unificato
  confermato da PDF nel fascicolo EUR 98,00`, `Spese ed esborsi riconosciuti
  in sentenza EUR 125,00`.
- `/email` e `/notifiche-legali`: superfici React aperte sulla copia reale,
  senza errori console; PEC mostra messaggi e allegati reali, notifiche mostra
  relata, controlli PEC e allegati.
- `/fascicoli/DC5BF1DB/deposito/prepara`: dopo il caricamento dati mostra
  `RG 466/2023 - Alessi Robertino`, `20` documenti nel fascicolo, `8`
  documenti in busta, indice generato dal software in tempo reale e lista
  documentale reale.

Prova PDF reale sul fascicolo `DC5BF1DB`:

- `Sentenza_3080731.pdf` e `depositoMinutaSentenzaSemplificata.pdf` letti con
  `pdfplumber+ocr`, 4 pagine, zero errori Tesseract; parser: sentenza
  `199/2026`, RG `466/2023`, liquidazione `1500,00`, spese/esborsi `125,00`.
- `attoACQ.pdf` e `attoACQ.pdf.p7m` letti con `pdfplumber+ocr` e
  `cades:pdfplumber+ocr`, zero errori Tesseract; evidenza CU:
  `Contributo unificato da PDF`, importo `98,00`.

Correzione runtime OCR locale: `TESSDATA_PREFIX` viene ora risolto e impostato
senza passare `--tessdata-dir` quotato a pytesseract. Su Windows il flag quotato
rompeva `image_to_data`/`image_to_string` con path
`"...\tessdata"/ita.traineddata`; il runtime usa quindi la variabile ambiente
valida e i test bloccano la regressione.

Riprova post-rebuild Docker: `app`, `scheduler-worker` e `ocr-worker` healthy
su `2.253.118`; OCR dentro il container `app` confermato sugli stessi file
reali (`Sentenza_3080731.pdf`, `attoACQ.pdf.p7m`) con zero errori Tesseract.
Il gate runtime ha atteso `lex_sentenza_economia_auto` `completed` alle
`21:27:15Z` e `pec_audit_pipeline_workers` `completed` alle `21:25:02Z`, con
`errors=0` e `vector_embedding_errors=0`.

## Correzione falsi CU produzione 2.253.119

Durante il reset/backfill su Hetzner del 26/06/2026 sono emersi falsi positivi
del contributo unificato su fascicoli Carta docente:

- `500,00` letto da frasi sul beneficio Carta docente;
- `38.514,03` letto da autocertificazione reddituale collegata
  all'esenzione;
- `C.U.` interpretato come contributo unificato quando nel testo era una sigla
  nominativa.

La regola corretta ora è:

- `Esenzione dal contributo unificato di iscrizione a ruolo` produce CU
  `non_previsto`, senza importo e senza voce proforma;
- importi vicini a Carta docente, importo nominale annuo, reddito, nucleo
  familiare, D.P.R. 445 o art. 76 vengono scartati come CU;
- il solo `C.U.` nel corpo del testo non basta: serve contesto di pagamento,
  iscrizione a ruolo, art. 9/D.P.R. 115 o un nome file CU forte;
- un importo passa solo con contesto diretto `contributo unificato`,
  `PagoPA`, `ricevuta/avviso pagamento` o `importo versato/pagato/dovuto`.

Test locali aggiunti e passati:

- `test_pdf_contributo_esenzione_non_prende_carta_docente_500`;
- `test_pdf_contributo_esenzione_reddituale_non_prende_soglia_reddito`;
- `test_pdf_contributo_rifiuta_iniziali_cu_e_importo_carta_docente`;
- `test_backfill_contributo_evidence_non_scambia_iniziali_cu_per_pagamento`.

Comandi:

- `python -m compileall pct\fascicolo_sentenza_economica.py scripts\backfill_sentenza_lex_economics.py`
- `python -m pytest -q tests\test_fascicolo_sentenza_economica.py tests\test_backfill_sentenza_lex_economics.py --tb=short`
- `python -m pytest -q tests\test_ocr_pipeline_adapter.py tests\test_fascicolo_sentenza_economica.py tests\test_backfill_sentenza_lex_economics.py tests\test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline tests\test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag tests\test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler tests\test_unlimited_ocr_integration.py tests\test_legal_ocr_structured.py tests\test_document_intelligence_extraction.py tests\test_document_intelligence_auto_indexing.py tests\test_legal_ocr_pipeline.py --tb=short`

## Catalogo documenti fascicolo da OCR - 2.253.119

Richiesta utente: il fascicolo deve essere catalogato leggendo i PDF presenti, perché alcuni documenti erano indicati come atti pur non essendolo. Il catalogo deve valere per i fascicoli già presenti e per i prossimi, e il deposito deve usare la stessa logica. Regola operativa esplicita: `Ricorso` è sempre atto principale.

Correzione applicata:

- aggiunto `pct.fascicolo_document_catalog`, un classificatore deterministico e isolato che usa metadati, nome file, tipo storico e testo OCR/Document AI integrale;
- il catalogo non spezza l'OCR in chunk: legge il testo completo già estratto da Document AI/Unlimited-OCR/fallback locale e lo usa solo come evidenza di classificazione;
- `Ricorso` o nomi/tipi equivalenti diventano sempre `atto_principale`, `TipoDocumento.RICORSO`, sezione `atti` e candidato principale per il deposito;
- sentenze, ordinanze, decreti e verbali vengono classificati come provvedimenti e non possono più finire nello slot atto principale solo perché storicamente erano `ATTO_GIUDIZIARIO`;
- CU, PagoPA, ricevute, avvisi di pagamento ed esenzioni entrano nella sezione `Pagamenti e contributi`, senza confondersi con iniziali `C.U.`;
- atti difensivi, memorie, istanze, costituzioni, repliche e deduzioni restano atti ma non sono automaticamente il ricorso introduttivo;
- allegati, perizie, CTU, produzioni documentali e documenti richiesti vengono trattati come allegati;
- comunicazioni e richieste di visibilità restano fuori dalla busta principale salvo selezione coerente con il loro ruolo;
- il bridge React espone `rawType`, `catalogRole`, `catalogLabel`, `catalogSection`, `catalogConfidence`, `catalogEvidence`, `depositRole` e `depositCandidate`;
- il motore di readiness deposito usa il catalogo per gli slot documentali e l'API server corregge tentativi di salvare come `atto_principale` documenti che il catalogo riconosce come non principali;
- lo script `scripts/reclassify_fascicolo_document_catalog.py` applica la ricatalogazione ai fascicoli esistenti usando SQL come fonte di verità e JSON solo come mirror/cache.

Prova locale sui fascicoli reali:

- dry-run: `source_of_truth=sqlite`, `fascicoli_seen=7`, `documents_seen=75`, `documents_with_ocr_text=75`, `reclassified=26`, `wrong_atti_fixed=16`, `skipped_low_confidence=4`, `skipped_specific=45`, `errors=0`;
- apply: stessi conteggi del dry-run e aggiornamento della copia SQLite locale reale;
- controllo a freddo post-apply: `reclassified=0`, `wrong_atti_fixed=0`, `errors=0`;
- i tipi specifici già attendibili non vengono riscritti in massa: la bonifica corregge soprattutto `ALTRO`, `ALLEGATO` o `ATTO_GIUDIZIARIO` generici quando l'evidenza OCR/nome è forte.

Test locali aggiunti e passati:

- `test_ricorso_e_sempre_atto_principale`;
- `test_sentenza_storicamente_atto_giudiziario_non_diventa_main_act`;
- `test_contributo_unificato_pagopa_non_diventa_atto_principale`;
- `test_iniziali_cu_non_bastano_per_catalogo_contributo`;
- `test_document_ai_texts_for_catalog_matcha_per_sha256`;
- `test_reclassification_script_corregge_atti_generici_su_sqlite`.

Comandi:

- `python -m compileall pct\fascicolo_document_catalog.py pct\practice_engine\deposit_readiness.py scripts\reclassify_fascicolo_document_catalog.py web\services\react_fascicoli_bridge.py web\blueprints\api_v1_react.py web\bootstrap\fascicoli_document_helpers.py`
- `python -m pytest -q tests\test_fascicolo_document_catalog.py tests\test_practice_engine_validators.py --tb=short`
- `python -m pytest -q tests\test_ocr_pipeline_adapter.py tests\test_fascicolo_sentenza_economica.py tests\test_backfill_sentenza_lex_economics.py tests\test_fascicolo_document_catalog.py tests\test_practice_engine_validators.py tests\test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline tests\test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag tests\test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler tests\test_unlimited_ocr_integration.py tests\test_legal_ocr_structured.py tests\test_document_intelligence_extraction.py tests\test_document_intelligence_auto_indexing.py tests\test_legal_ocr_pipeline.py --tb=short`
- `python scripts\reclassify_fascicolo_document_catalog.py --data-root data --registry data\tenants.json --report artifacts\unlimited-ocr\document-catalog-reclassify-local-dry-run-20260625.json`
- `python scripts\reclassify_fascicolo_document_catalog.py --data-root data --registry data\tenants.json --apply --report artifacts\unlimited-ocr\document-catalog-reclassify-local-apply-20260625.json`

Stato residuo prima della chiusura: ricostruzione Docker locale `2.253.119`, prova browser reale su `127.0.0.1:8080`, commit/push, check GitHub/CodeQL, deploy Hetzner e applicazione dello script di ricatalogazione su `/data` produzione.

## Recupero mirror SQLite locale dopo ricatalogazione - 2.253.119

Durante gli audit dati post-catalogo è emerso un problema reale sul tenant locale: `PRAGMA quick_check` segnalava pagine non usate e poi `invalid rootpage` sulla tabella `moduli_json_records`. La tabella è un mirror rigenerabile dei JSON tenant-aware, non la fonte operativa dei dati core; le tabelle `clienti`, `fascicoli`, `appuntamenti`, `scadenze`, `messaggi` e `moduli_dati` erano leggibili.

Risoluzione:

- fermati `app`, `scheduler-worker` e `ocr-worker` per evitare scritture concorrenti;
- creato backup del `studio.db` fuori repository in `%TEMP%`;
- ricostruito un DB pulito rimuovendo solo lo schema corrotto del mirror `moduli_json_records` e usando `VACUUM INTO`;
- confrontati i conteggi core prima/dopo;
- rigenerato il mirror con `scripts/audit_data_flow_contract.py --repair-json-mirror --repair-search-index` a servizi fermi;
- rieseguiti audit data-flow e tenant-structure repair+cold.

Esito finale locale:

- `PRAGMA quick_check=ok`;
- `moduli_dati=759`;
- `moduli_json_records=11213`;
- `audit_data_flow_contract.py` repair e cold: `ok=true`, `quick_check_ok=true`;
- `audit_tenant_data_structure.py` repair e cold: `ok=true`, zero errori e zero warning.

Report generati:

- `artifacts/unlimited-ocr/data-flow-repair-after-catalog-20260625.json`;
- `artifacts/unlimited-ocr/data-flow-cold-after-catalog-20260625.json`;
- `artifacts/unlimited-ocr/tenant-structure-repair-after-catalog-20260625.json`;
- `artifacts/unlimited-ocr/tenant-structure-cold-after-catalog-20260625.json`.

## Ricatalogazione V2 e prova browser deposito - 2026-06-26

La prova reale sul fascicolo `DC5BF1DB` ha evidenziato tre documenti ancora troppo specifici come `VERBALE` pur essendo atti difensivi/note di trattazione. La regola e' stata stretta senza indebolire i provvedimenti: nomi file forti da verbale restano `Verbale`, mentre `note di trattazione`, `note conclusive`, `note di udienza` e `istanza per fissazione udienza in trattazione scritta` diventano `Atto difensivo`.

Seconda applicazione locale:

- comando: `python scripts\reclassify_fascicolo_document_catalog.py --data-root data --registry data\tenants.json --apply --report artifacts\unlimited-ocr\document-catalog-reclassify-local-apply-v2-20260625.json`;
- esito: `source_of_truth=sqlite`, `fascicoli_seen=7`, `documents_seen=75`, `reclassified=3`, `wrong_atti_fixed=0`, `errors=0`;
- documenti corretti: `F96270FE note_di_trattazione_scritta_ZURICH_udienza_del_19-03-2025.pdf.p7m`, `D33E8F45 note_di_trattazione_scritta_ZURICH_udienza_del_10-07-2024.pdf.p7m`, `69AD12FF istanza_per_fissazione_di_udienza_in_trattazione_scritta.pdf.p7m`;
- controllo a freddo: `document-catalog-reclassify-local-post-apply-v2-20260625.json` con `reclassified=0`, `wrong_atti_fixed=0`, `errors=0`;
- audit dati e struttura dopo V2: `data-flow-repair-after-catalog-v2-20260625.json`, `data-flow-cold-after-catalog-v2-20260625.json`, `tenant-structure-repair-after-catalog-v2-20260625.json`, `tenant-structure-cold-after-catalog-v2-20260625.json`, tutti senza errori bloccanti.

Prova reale locale su Docker `2.253.119`, browser integrato visibile:

- `/fascicoli/DC5BF1DB#documenti`: `note_di_trattazione...19-03-2025`, `note_di_trattazione...10-07-2024` e `istanza_per_fissazione...` sono in `Atti e memorie` con badge `Atto difensivo`;
- `verbaleAttoGenerico.pdf` resta `Verbale` in `Provvedimenti`;
- `attoACQ.pdf.p7m` e' in `Pagamenti e contributi` come `Contributo unificato / pagamento`;
- `/fascicoli/DC5BF1DB/deposito/prepara#proposta-busta`: `attoACQ.pdf.p7m` mostra `Contributo unificato / pagamento (allegato busta)`, le note/istanza mostrano `Atto difensivo (allegato busta)`, `verbaleAttoGenerico.pdf` mostra `Verbale (allegato busta)`;
- desktop `1280x900`, tablet `768x900` e mobile `390x844`: nessun overflow orizzontale, testi lunghi leggibili, scroll completo fino ad `Audit`, console senza errori.

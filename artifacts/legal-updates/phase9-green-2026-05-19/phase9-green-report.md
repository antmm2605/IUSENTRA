# Fase 9 - estensione fonti verdi

Aggiornato il 19 maggio 2026. La fase estende lo scheduler/popolamento progressivo alle sole fonti verdi rimaste e mantiene fuori pubblicazione fonti gialle, rosse, in osservazione, tecniche o RAG-only. Non sono stati eseguiti backup, import massivi o pubblicazioni da cataloghi tecnici.

## Liste operative

Fonti verdi abilitate:

- `cassazione_ultime_sent_ord_questioni`
- `corte_conti`
- `curia_cgue_rss`
- `inps_circolari`
- `inps_messaggi`
- `agcom_provvedimenti`
- `anac_documenti`
- `garante_privacy`
- `gazzetta_ufficiale`

Fonti RAG-only:

- `dati_normattiva`
- `eur_lex`
- `istat_prezzi`
- `openga_sentenze`
- `openga_ordinanze`
- `openga_decreti`
- `openga_pareri`
- `pst_giustizia_download`

Fonti in osservazione:

- `cassazione_citazioni_verificate`
- `corte_costituzionale`
- `inps_sentenze`
- `agenzia_entrate`
- `ministero_lavoro`
- `ministero_lavoro_interpelli`
- `agcm_bollettino`
- `banca_italia_normativa`
- `inail_istruzioni_operative`
- `mimit_incentivi`

Fonti escluse dalla pubblicazione automatica:

- tutte le fonti RAG-only;
- tutte le fonti in osservazione;
- `normattiva`;
- `codice_civile`;
- `codice_procedura_civile`;
- `codice_penale`;
- `codice_procedura_penale`;
- `codice_processo_amministrativo`;
- `codice_strada`.

## Lotti eseguiti

| Lotto | Esito | Fonti eseguite | Trovati | Processati | Invariati | Pubblicati | Scarti guarded | PDF/OCR | Riferimenti | Domande |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 - Giurisprudenza | OK | 7 | 1161 | 11 | 6 | 6 | 3 | 6 | 91 | 243 |
| 2 - Prassi e autorità | OK | 6 | 129 | 5 | 12 | 7 | 8 | 8 | 129 | 240 |
| 3 - Telematico | OK | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 13 |
| 4 - Normativa/UE | OK | 10 | 242 | 17 | 2 | 1 | 0 | 3 | 120 | 244 |
| Totale fase | OK | 24 | 1533 | 33 | 21 | 14 | 11 | 17 | 340 | 740 |

## Dettaglio lotti

### Lotto 1 - Giurisprudenza

- `cassazione_ultime_sent_ord_questioni`: verde, `limit 3`, 3 trovati, 2 processati, 1 invariato, 3 pubblicati.
- `corte_conti`: verde, `limit 3`, 10 trovati, 3 processati, 3 pubblicati.
- `curia_cgue_rss`: verde, `limit 3`, 10 trovati, 3 invariati, 0 pubblicati.
- `openga_sentenze`, `openga_ordinanze`, `openga_decreti`, `openga_pareri`: RAG-only, `limit 2`, 1138 trovati complessivi, 6 processati, 0 pubblicati.
- `cassazione_citazioni_verificate` e `corte_costituzionale`: non eseguite, in osservazione.

### Lotto 2 - Prassi e autorità

- `inps_circolari`: verde, `limit 3`, 50 trovati, 3 invariati, 3 pubblicati.
- `inps_messaggi`: verde, `limit 3`, 9 trovati, 3 invariati, 2 pubblicati.
- `garante_privacy`: verde, `limit 3`, 5 trovati, 3 processati, 0 pubblicati per conferme guarded insufficienti.
- `anac_documenti`: verde, `limit 3`, 25 trovati, 3 invariati, 0 pubblicati per conferme guarded insufficienti.
- `agcom_provvedimenti`: verde, `limit 3`, 30 trovati, 3 invariati, 2 pubblicati.
- `istat_prezzi`: RAG/calcoli, `limit 2`, 10 trovati, 2 processati, 0 pubblicati.
- `inps_sentenze`, `agenzia_entrate`, `ministero_lavoro`, `ministero_lavoro_interpelli`, `agcm_bollettino`, `banca_italia_normativa`, `inail_istruzioni_operative`, `mimit_incentivi`: non eseguite, in osservazione.

### Lotto 3 - Telematico

- `pst_giustizia_download`: RAG-only tecnico, `limit 2`, 1 documento invariato, 0 pubblicazioni.

### Lotto 4 - Normativa/UE

- `gazzetta_ufficiale`: verde, `limit 3`, 23 trovati, 1 processato, 2 invariati, 1 pubblicato, 3 PDF/OCR completati.
- `normattiva`: archivio locale, `limit 2`, 37 trovati, 2 processati, 0 pubblicati.
- `dati_normattiva`: RAG-only, `limit 2`, 1 trovato, 1 processato, 0 pubblicati.
- `eur_lex`: RAG-only, `limit 2`, 1 documento diagnostico processato, 0 pubblicati.
- codici Normattiva: archivio locale, `limit 2` per codice, 180 trovati, 12 processati, 0 pubblicati.

## Blocco corretto durante la fase

`eur_lex` ha inizialmente restituito `Document is empty` sulla pagina vuota. La fase è stata fermata sul lotto 4, il parser HTML è stato corretto per catturare anche `ParserError` di `lxml` e il canary EUR-Lex è stato rieseguito solo sulla fonte fallita. Il test `tests/test_legal_update_source_parsers.py` copre ora il fallback diagnostico RAG-only per HTML vuoto.

## Stato superfici utente

- Ricerca Legale: alimentata dai 14 contenuti pubblicati in questa fase e dalle evidenze RAG-only/archivi locali senza trasformare cataloghi tecnici in news.
- Lex: può usare testo pagina, PDF/OCR, riferimenti e domande contestuali salvati; le fonti RAG-only restano segnate come evidenza non pubblicabile.
- Archivio Giurisprudenza: nessuna scheda strutturata nuova in questa fase; i contenuti giurisprudenziali senza chiavi complete restano news/RAG ufficiale.

## Test mirati già eseguiti durante i lotti

- `python -m py_compile pct\legal_update_autofetch.py pct\scheduler.py pct\scheduler_registry.py web\services\legal_update_surface.py`
- `python -m pytest tests/test_legal_update_autofetch.py tests/test_legal_update_surface_jobs.py tests/test_scheduler_registry.py -q --tb=short` - 15/15.
- `python -m pytest tests/test_legal_update_source_parsers.py tests/test_legal_update_web_verification_attachments.py -q --tb=short` - 34/34.
- `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_react_legal_intelligence_search.py tests/test_giurisprudenza.py -q --tb=short` - 48/48.
- `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short` - 39/39.
- `python -m pytest tests/test_legal_update_batch_runner.py -q --tb=short` - 8/8.
- `python -m pytest tests/test_legal_update_source_capabilities.py tests/test_legal_update_safe_diagnostics.py tests/test_legal_update_job_queue.py -q --tb=short` - 20/20.
- `python -m pytest tests/test_legal_update_source_parsers.py -q --tb=short` - 21/21.
- `python -m pytest tests/test_legal_update_source_parsers.py tests/test_legal_update_source_capabilities.py tests/test_legal_update_publish_context.py -q --tb=short` - 44/44.

## Gate finali

- `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` - 41/41.
- `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short` - 39/39.
- `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_lex_operational_knowledge.py tests/test_react_legal_intelligence_search.py tests/test_giurisprudenza.py -q --tb=short` - OK.
- `python -m pytest tests/test_legal_update_autofetch.py tests/test_legal_update_surface_jobs.py tests/test_legal_update_job_queue.py tests/test_legal_update_batch_runner.py -q --tb=short` - 20/20.
- `python tools/check_repo_governance.py` - OK.
- `python -m pytest tests/test_utf8_integrity.py -q --tb=short` - 4/4.
- `git diff --check` - OK, con solo avviso CRLF/LF su file runtime preesistente non committato.
- `python -m pytest tests/test_scheduler_registry.py tests/test_legal_update_source_parsers.py -q --tb=short` - 29/29.

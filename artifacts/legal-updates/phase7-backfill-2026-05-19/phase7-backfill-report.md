# Fase 7 - Backfill mirato PDF/OCR/riferimenti/domande

Aggiornato il 19 maggio 2026. Esecuzione limitata ai documenti già acquisiti nel repository locale degli aggiornamenti legali, senza Web libero, senza pubblicazione automatica e senza backfill globale non limitato.

## Stato iniziale Git

```text
 M data/tenants/tenant-8bf98719c459/intelligence/assistente_redazionale.json
 M data/tenants/tenant-8bf98719c459/preventivi/conferimenti.json
?? intelligence/workspace_intelligence.json
```

Le tre voci erano già presenti prima della fase. Non sono state incluse nei commit della fase 7.

## Report consultati prima del backfill

- `artifacts/legal-updates/phase5-green-2026-05-19/phase5-green-report.md`
- `artifacts/legal-updates/phase6-normativa-archives-2026-05-19/phase6-report.md`
- `artifacts/legal-updates/source-rollout-execution.md`
- `artifacts/legal-updates/canary-report-2026-05-19.md`
- `artifacts/legal-updates/pilot-guarded-2026-05-19/verification.json`
- repository aggiornamenti legali locale `intelligence/legal_updates.db`

Stato repository locale prima della fase operativa: 84 review, 21 news, 3 prassi, 168 evidenze web; 47 evidenze con allegato, 168 evidenze con testo leggibile, 0 PDF con testo/OCR mancante nel perimetro interrogato.

## Correzioni CLI applicate

- `legal-updates-backfill-diagnostics --missing` ora accetta liste separate da virgole, ad esempio `attachments,ocr,references,questions`.
- Il report JSON del backfill include una sezione `summary` con selezionati, processati, aggiornati, invariati, falliti, motivi, PDF/OCR completati, riferimenti e domande aggiunte, stato Lex e Ricerca Legale.
- L'output CLI viene forzato a UTF-8 quando lo stream lo supporta: il primo tentativo su Windows era arrivato alla generazione del report ma era caduto in stampa JSON per encoding `cp1252` davanti a caratteri UTF-8.
- Il report diagnostico compatta lo snapshot dashboard in `dashboard_summary`: restano conteggi e qualità, ma non vengono esportati payload applicativi o stream PDF grezzi nei JSON di fase.

## Backfill eseguiti

| File JSON | Comando | Esito |
| --- | --- | --- |
| `attachments.json` | `python -m pct.cli legal-updates-backfill-diagnostics --missing attachments --limit 50 --max-seconds 120 --no-publish --json` | OK, nessun elemento ancora selezionabile dopo il rientro del primo tentativo. |
| `ocr.json` | `python -m pct.cli legal-updates-backfill-diagnostics --missing ocr --limit 30 --max-seconds 120 --no-publish --json` | OK, nessun PDF con testo/OCR mancante nel perimetro. |
| `references.json` | `python -m pct.cli legal-updates-backfill-diagnostics --missing references --limit 50 --max-seconds 120 --no-publish --json` | OK, 14 evidenze aggiornate. |
| `questions.json` | `python -m pct.cli legal-updates-backfill-diagnostics --missing questions --limit 50 --max-seconds 120 --no-publish --json` | OK, nessuna domanda mancante. |
| `cassazione_ultime_sent_ord_questioni.json` | `python -m pct.cli legal-updates-backfill-diagnostics --source cassazione_ultime_sent_ord_questioni --missing attachments,ocr,references,questions --limit 20 --max-seconds 120 --no-publish --json` | OK, fonte già completa nel perimetro selezionato. |
| `open_data_rag_only.json` | `python -m pct.cli legal-updates-backfill-diagnostics --include-open-data --missing references,questions --limit 20 --max-seconds 120 --no-publish --json` | OK, 20 evidenze controllate e già invarianti. |

## Tabella risultati

| Backfill | Selezionati | Processati | Aggiornati | Invariati | Falliti | PDF completati | OCR completati | Allegati completati | Riferimenti aggiunti | Domande aggiunte | Lex | Ricerca Legale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Allegati vuoti | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | invariato | invariata |
| OCR mancanti | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | invariato | invariata |
| Riferimenti mancanti | 50 | 50 | 14 | 36 | 0 | 0 | 0 | 0 | 20 | 0 | aggiornato | aggiornata |
| Domande contestuali mancanti | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | invariato | invariata |
| Cassazione specifica | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | invariato | invariata |
| Fonti RAG-only/open data | 20 | 20 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | invariato | invariata |

## Documenti completati

Il backfill riferimenti ha aggiornato 14 evidenze collegate a 12 review:

| Review | Fonte | Titolo | Evidenze aggiornate | Riferimenti aggiunti |
| ---: | --- | --- | ---: | ---: |
| 9 | `inps_messaggi` | Messaggio numero 1493 del 05-05-2026 | 2 | 2 |
| 43 | `curia_cgue_rss` | Sentenza del Tribunale nella causa T-24/25 | 1 | 1 |
| 44 | `curia_cgue_rss` | Sentenza della Corte nella causa C-155/25 | 1 | 1 |
| 45 | `curia_cgue_rss` | Sentenza della Corte nella causa C-286/25 | 1 | 1 |
| 47 | `inps_messaggi` | Scarica gli Open Data | 1 | 2 |
| 48 | `inps_messaggi` | Scarica gli Open Data | 1 | 2 |
| 49 | `inps_messaggi` | Scarica gli Open Data | 1 | 2 |
| 51 | `inps_messaggi` | Messaggio numero 1618 del 15-05-2026 | 1 | 1 |
| 53 | `inps_messaggi` | Messaggio numero 1493 del 05-05-2026 | 2 | 5 |
| 72 | `curia_cgue_rss` | Sentenza della Corte nella causa C-797/23 | 1 | 1 |
| 73 | `curia_cgue_rss` | Sentenza della Corte nella causa C-747/22 | 1 | 1 |
| 77 | `inps_messaggi` | Messaggio numero 1442 del 30-04-2026 | 1 | 1 |

## PDF/OCR e corpus

- PDF/OCR completati in questa fase: 0 nuovi, perché il perimetro interrogato non conteneva più PDF con testo zero o OCR mancante.
- Stato dopo il backfill: 168 evidenze web totali, 168 con testo leggibile, 47 con allegato, 0 PDF con testo/OCR mancante, 168 evidenze con termini/domande salvati.
- Riferimenti aggiunti: 20.
- Domande aggiunte: 0, perché le evidenze selezionabili avevano già matrice domande.
- Elementi falliti: 0. Nessun OCR fallito nascosto nei JSON della fase.
- Pubblicazione automatica: 0 su tutti i report.

## Stato Lex e Ricerca Legale

Il repository locale è stato aggiornato solo su `matched_terms_json` delle evidenze web interessate. Lex e Ricerca Legale leggono lo stesso repository, quindi le 14 evidenze aggiornate sono disponibili per ranking e contesto senza nuova pubblicazione.

La fonte specifica `cassazione_ultime_sent_ord_questioni` resta completa per allegati, OCR, riferimenti e domande nel perimetro corrente. Le fonti RAG-only/open data sono state controllate in modo limitato e non hanno prodotto aggiornamenti.

## Verifiche

| Comando | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\cli.py pct\legal_update_diagnostics.py` | OK | Sintassi CLI/backfill dopo supporto liste e UTF-8. |
| `python -m pytest tests/test_legal_update_safe_diagnostics.py -q --tb=short` | OK | 8/8: canary/backfill JSON, limiti, `--missing` multiplo e report compatti senza payload/PDF grezzi. |
| `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short` | OK | 39/39: allegati, OCR, riferimenti, publish context e Document Intelligence. |
| `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_lex_operational_knowledge.py tests/test_react_legal_intelligence_search.py -q --tb=short` | OK | 75/75: corpus Lex, ranking allegati, conoscenza operativa e Ricerca Legale. |
| `python tools/sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e versione `2.245.48` coerente. |
| `python scripts/react-migration/generate_api_contracts.py`; `python scripts/react-migration/generate_api_contracts.py --check`; `python scripts/validate_openapi.py docs/openapi.yaml`; `python scripts/verify_openapi_provider.py`; `python -m pytest -q tests/test_openapi_contracts_phase6.py --tb=short` | OK | OpenAPI riallineato a `2.245.48` e contratti fase 6 verdi. |
| `python tools/check_repo_governance.py` | OK | Governance OK, `web/app.py` 40 righe e 0 route inline. |
| `python -m pytest tests/test_utf8_integrity.py -q --tb=short` | OK | 4/4. |
| `git diff --check` | OK | Nessun errore whitespace; restano solo warning CRLF su file runtime preesistente e `docs/openapi.yaml` rigenerato. |

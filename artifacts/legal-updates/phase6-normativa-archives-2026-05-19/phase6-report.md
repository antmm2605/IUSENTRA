# Fase 6 - Popolamento normativa e archivi base

Aggiornato il 19 maggio 2026. La fase è stata eseguita senza backup, senza download ciechi, senza import massivo e senza ricostruzione degli archivi già presenti.

## Stato iniziale Git

```text
 M data/tenants/tenant-8bf98719c459/intelligence/assistente_redazionale.json
 M data/tenants/tenant-8bf98719c459/preventivi/conferimenti.json
?? intelligence/workspace_intelligence.json
```

Le tre voci erano già presenti prima della fase e non sono state toccate.

## Stato archivi

| Archivio | Stato locale | Conteggi locali | Note |
| --- | --- | ---: | --- |
| Normattiva SQLite | presente | 42.677 documenti, 238.110 articoli, 279.777 chunk | DB locale `data/normativa/normattiva.sqlite`; JSONL presente in `data/normativa/index/normattiva_chunks.jsonl`. |
| Normattiva raw ZIP | presente | 14 ZIP locali | Include `Codici_XML_ORIGINALE_2026-05-17.zip`; non sono stati scaricati nuovi ZIP. |
| Manifest Normattiva | presente | `normattiva_download_manifest.json`, `normattiva_download_manifest_catalog_state.json` | Usato come stato incrementale; nessuna ricostruzione. |
| Gazzetta Ufficiale SQLite | presente | 12 documenti, 1.852 chunk | DB locale `data/fonti_ufficiali/lex_sources.sqlite`; JSONL presente in `data/fonti_ufficiali/index/lex_sources_chunks.jsonl`. |
| Archivi ufficiali Lex | presenti | Normattiva + Gazzetta | Risolti tramite `official_archive_snapshot()` e variabili/fallback runtime. |

Il volume Hetzner documentato resta il riferimento di produzione già popolato: 189.851 documenti, 800.757 articoli e 639.273 chunk Normattiva; Gazzetta con 28 documenti e 3.911 chunk alla verifica infrastrutturale precedente.

## Cosa è stato popolato o collegato

- Non è stato eseguito nuovo import massivo.
- Normattiva e Gazzetta già presenti sono state collegate meglio a Ricerca Legale e Lex tramite il retriever ufficiale.
- Le query sui codici non dipendono più dalla frase esatta: il retriever riconosce codice, articolo e suffissi come `bis`.
- Per i codici storici in cui il DB locale non contiene ancora l'articolo come chunk autonomo, il retriever usa i raw ZIP Normattiva già presenti e legge l'articolo dal testo XML, senza inventare link Normattiva.
- Gazzetta deduplica i risultati per documento, evitando di mostrare più chunk dello stesso fascicolo come risultati separati.

## Codici verificati

| Codice | Query verificata | Stato |
| --- | --- | --- |
| Codice civile | `codice civile art. 2043` | interrogabile da raw ZIP Normattiva già presente |
| Codice di procedura civile | `codice procedura civile art. 183` | interrogabile da raw ZIP Normattiva già presente |
| Codice penale | `codice penale art. 575` | interrogabile da raw ZIP Normattiva già presente |
| Codice di procedura penale | `codice procedura penale art. 415 bis` | interrogabile da DB Normattiva |
| Codice del processo amministrativo | `codice processo amministrativo art. 29` | interrogabile da raw ZIP Normattiva già presente |
| Codice della strada | `codice della strada art. 142` | interrogabile da DB Normattiva |

## EUR-Lex

EUR-Lex resta classificata come fonte UE ufficiale. In questa fase non è stato dichiarato stabile un parser CELEX dedicato: la capability è quindi governata come `RAG-only` ufficiale UE, con motivo operativo visibile, finché una fixture CELEX completa non sarà verde.

## Fonti secondarie

Studio Cataldi e Avvocato Andreani restano disabilitate come fonti non ufficiali. Non alimentano pubblicazione ufficiale, Normattiva, Gazzetta o corpus canonico; possono restare solo supporto secondario o Web libero esplicito quando previsto.

## Integrazione Ricerca Legale

La pagina Ricerca Legale usa gli archivi ufficiali locali tramite `search_normattiva()` e `search_gazzetta()`. I conteggi Normattiva/Gazzetta arrivano da `official_archive_snapshot()` e i risultati di Gazzetta vengono deduplicati per documento.

## Integrazione Lex

`search_normativa_sources()` include ora anche Normattiva e Gazzetta dagli archivi ufficiali locali. Le evidenze vengono marcate come contesto d'archivio, fonte verificata e autorità ufficiale, così Lex può usare normativa e Gazzetta prima di eventuali fallback pubblici.

## Verifiche eseguite

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile lex\retrieval\official_sources_retriever.py lex\retrieval\normativa.py lex\normativa\normattiva_importer.py pct\legal_update_source_capabilities.py` | OK | Sintassi dei moduli toccati. |
| `python -m pytest tests\test_normattiva_importer.py tests\test_official_sources_retriever.py tests\test_legal_update_source_capabilities.py -q --tb=short` | OK | 12/12 passati: codici da paragrafi HTML, fallback raw ZIP, deduplica Gazzetta, Lex con contesto Normattiva, EUR-Lex RAG-only e fonti secondarie. |
| `python -m pytest tests/test_normattiva_client.py tests/test_normattiva_importer.py -q --tb=short` | OK | 6/6 passati. |
| `python -m pytest tests/test_official_sources_retriever.py tests/test_legal_update_source_capabilities.py -q --tb=short` | OK | 9/9 passati. |
| `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` | OK | 41/41 passati. |
| `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_react_legal_intelligence_search.py -q --tb=short` | OK | 24/24 passati. |
| `python scripts/react-migration/generate_api_contracts.py --check`; `python scripts/validate_openapi.py docs/openapi.yaml`; `python scripts/verify_openapi_provider.py`; `python scripts/smoke_app_v2_all.py --subset contracts`; `python -m pytest -q tests/test_openapi_contracts_phase6.py --tb=short` | OK | Contratto OpenAPI riallineato alla versione `2.245.47` dopo il primo push. |
| `python scripts/react-migration/generate_app_v2_page_registry.py --check`; `python scripts/react-migration/generate_app_v2_test_docs.py --check`; `python scripts/smoke_app_v2_all.py --subset inventory`; `python -m pytest -q tests/test_app_v2_page_registry.py tests/test_app_v2_test_plan_phase10.py tests/test_ci_cd_gates_phase11.py --tb=short` | OK | Inventario e piano test App V2 riallineati dopo il nuovo test ufficial sources. |
| `python -m ruff check --config pyproject.toml packaging_manifest.py docker/entrypoint.py tools/sync_packaging_files.py pct/giurisprudenza_corpus.py lex/http_bounded_bridge.py lex/context/studio_context.py lex/retrieval lex/formatting/answer_builder.py tests/test_packaging_consistency.py tests/test_docker_entrypoint.py`; `python -m py_compile lex\retrieval\normativa.py lex\retrieval\official_sources_retriever.py`; `python -m pytest tests/test_official_sources_retriever.py -q --tb=short` | OK | Ruff governato verde e smoke retriever 2/2 dopo il riordino import. |
| `python tools/check_repo_governance.py` | OK | Governance check OK; `web/app.py` 40 righe, 0 route inline. |
| `python -m pytest tests/test_utf8_integrity.py -q --tb=short` | OK | 4/4 passati. |
| `git diff --check` | OK | Nessun errore whitespace; avviso CRLF/LF solo sui dati runtime preesistenti non toccati. |
| Probe `official_archive_snapshot()` | OK | Normattiva locale 42.677 documenti, 238.110 articoli, 279.777 chunk; Gazzetta locale 12 documenti, 1.852 chunk. |
| Probe Lex `search_normativa_sources("codice civile art. 2043")` | OK | Restituisce Normattiva con art. 2043 come contesto verificato. |

## Rischi residui

- Il DB locale non è completo quanto il volume Hetzner; il fallback raw ZIP copre i codici presenti senza ricostruire il DB, ma una reindicizzazione futura può migliorare i chunk strutturati.
- EUR-Lex è volutamente RAG-only finché non viene stabilizzato un parser CELEX con fixture dedicate.
- Gazzetta locale contiene 12 fascicoli; la produzione documentata è più popolata. Non è stato eseguito nuovo download.

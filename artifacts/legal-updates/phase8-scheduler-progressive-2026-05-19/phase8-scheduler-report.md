# Fase 8 - Scheduler progressivo aggiornamenti legali

Aggiornato il 19 maggio 2026. La fase attiva lo scheduler progressivo con budget basso, senza backup, senza import massivo notturno e senza abilitare tutte le fonti.

## Stato iniziale Git

```text
 M data/tenants/tenant-8bf98719c459/intelligence/assistente_redazionale.json
 M data/tenants/tenant-8bf98719c459/preventivi/conferimenti.json
?? intelligence/workspace_intelligence.json
```

Le tre voci erano già presenti prima della fase e non sono state toccate.

## Report consultati

- `artifacts/legal-updates/phase5-green-2026-05-19/phase5-green-report.md`
- `artifacts/legal-updates/phase6-normativa-archives-2026-05-19/phase6-report.md`
- `artifacts/legal-updates/phase7-backfill-2026-05-19/phase7-backfill-report.md`
- `artifacts/legal-updates/source-rollout-plan.md`
- `artifacts/legal-updates/source-rollout-execution.md`

## Fonti abilitate nello step 1

| Fonte | Motivo |
| --- | --- |
| `cassazione_ultime_sent_ord_questioni` | Fonte verde con schede documentali, PDF/OCR, riferimenti e domande già verificati. |
| `inps_circolari` | Fonte verde per prassi previdenziale con testo/PDF e pubblicazione come news/prassi guarded. |
| `inps_messaggi` | Fonte verde parziale: entra solo con filtro messaggi operativi e scarti guarded sui testi tecnici. |
| `agcom_provvedimenti` | Fonte verde con filtro su delibere/provvedimenti e PDF ufficiali. |

Il budget `2` fa sì che ogni tick lavori al massimo due fonti tra queste, rispettando cursori e intervalli.

## Fonti escluse

| Fonte | Motivo |
| --- | --- |
| `anac_documenti` | Esclusa dallo step 1: le fasi precedenti hanno richiesto conferme ulteriori prima della pubblicazione guarded. |
| `garante_privacy` | Esclusa dallo step 1: fonte utile ma ancora da osservare per allegati, riferimenti e qualità costante. |
| `gazzetta_ufficiale`, `normattiva`, `dati_normattiva` | Presidiate dagli archivi ufficiali locali della fase 6; non entrano nel batch fonte progressivo. |
| `corte_costituzionale` | Esclusa finché la fonte diretta non restituisce schede pronuncia verificabili senza fallback di navigazione. |
| `openga_*`, `pst_giustizia_download` | RAG-only, tecniche o da pilot dedicato; non pubblicabili nello step 1. |
| Altre fonti attive storiche | Fuori step finché non passano canary/report verde dedicato. |

## Budget e limiti

| Variabile reale | Valore step 1 |
| --- | ---: |
| `IUSENTRA_LEGAL_AUTOFETCH_SOURCE_BUDGET` | 2 |
| `IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS` | 5 |
| `IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS` | 120 |
| `IUSENTRA_CASSAZIONE_LATEST_MAX_ITEMS` | 5 |

## Presidi applicati

- `pct.scheduler` esegue `legal_updates_batch` solo sulle quattro fonti verdi.
- Il vecchio job dedicato Gazzetta non viene più registrato nello scheduler APScheduler; eventuali righe legacy nel registro pianificazioni vengono disabilitate.
- `run_legal_update_action("scan")` usa lo stesso step progressivo quando non viene richiesta una fonte esplicita.
- Gli agenti fonte del registro pianificazioni restano abilitati solo per le fonti step 1; le altre fonti vengono bloccate come fuori step.
- I job running stantii vengono recuperati dalla coda e i run fonte stantii vengono letti in UI come `Interrotto, da verificare`.
- Errori interni nel payload fonte continuano a trasformare il run in `failed`, non in `completed`.
- La console admin mostra fonti step 1, budget, timeout e massimo pubblicazioni guarded.
- Ricerca Legale e Lex continuano a distinguere evidenze verificate, fonti incomplete e RAG-only: le incomplete non diventano fonte certa.

## Verifiche iniziali

| Comando | Esito |
| --- | --- |
| `python -m pytest tests/test_legal_update_autofetch.py tests/test_legal_update_surface_jobs.py tests/test_scheduler_registry.py tests/test_scheduler_worker.py -q --tb=short` | OK, 17/17 |
| `python -m pytest tests/test_legal_update_autofetch.py tests/test_legal_update_surface_jobs.py tests/test_legal_update_job_queue.py tests/test_legal_update_batch_runner.py -q --tb=short` | OK, 20/20 |
| `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` | Primo tentativo in timeout locale a 124s; rilancio mirato OK, 41/41 |
| `python tools/check_repo_governance.py` | OK |
| `python -m pytest tests/test_utf8_integrity.py -q --tb=short` | OK, 4/4 |
| `git diff --check` | OK, solo warning CRLF su dati runtime preesistenti e `docs/openapi.yaml` |
| `python scripts/react-migration/generate_api_contracts.py --check`; `python scripts/validate_openapi.py docs/openapi.yaml`; `python scripts/verify_openapi_provider.py`; `python -m pytest -q tests/test_openapi_contracts_phase6.py --tb=short` | OK |
| `python tools/sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK, 9/9 |
| `python -m pytest tests/test_scheduler_registry.py tests/test_scheduler_worker.py tests/test_scheduler_admin.py -q --tb=short` | OK, 14/14 |

## Rischi residui e step 2

- `anac_documenti` e `garante_privacy` possono entrare nello step 2 solo dopo canary dedicato, conferme guarded e controllo su assenza di falsi allegati o riferimenti non ritrovati.
- Le fonti Normattiva/Gazzetta restano affidate agli archivi ufficiali locali: eventuale riattivazione come fonte scheduler richiede un piano separato, non un batch completo.
- OpenGA va trattata in una tranche dedicata che promuova solo risorse documentali concrete, lasciando dataset tabellari in RAG-only.
- Lo step 2 consigliato è aumentare gradualmente a 3 fonti per ciclo solo dopo più tick verdi, poi valutare una sola tra `anac_documenti` e `garante_privacy` con `publish_max_items` ancora pari a 5.

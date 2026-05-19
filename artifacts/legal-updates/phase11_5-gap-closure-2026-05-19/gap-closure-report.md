# Fase 11.5 - Chiusura buchi residui prima del popolamento

Data: 19 maggio 2026.

Regole rispettate: nessuno scheduler esteso, nessun import massivo, nessuna pubblicazione globale, nessuna fonte in osservazione abilitata, nessun Web libero automatico, nessun backup, nessuna promozione fittizia di lacune.

## Stato iniziale

`git status --short` iniziale:

```text
 M data/tenants/tenant-8bf98719c459/intelligence/assistente_redazionale.json
 M data/tenants/tenant-8bf98719c459/preventivi/conferimenti.json
?? intelligence/workspace_intelligence.json
```

Health report iniziale:

- comando: `python -m pct.cli legal-updates-health-report --json`;
- esito: `ok=true`, readiness `presidiato`, `issue_count=0`;
- fonti: 47 totali, 9 attive/verdi, 13 in osservazione, 14 RAG-only, 38 non pubblicabili;
- qualità: errori 0, OCR falliti 0, allegati vuoti 0, riferimenti mancanti 0, domande mancanti 0;
- review pendenti: 26; pubblicazioni guarded: 23;
- pubblicazioni non controllate: `false`;
- retry sicuro: `max_attempts=3`, timeout 120 secondi, pubblicazione solo guarded;
- backfill mirati pendenti: attachments 0, OCR 0, references 0, questions 0.

## Matrice buchi

| buco | causa | file da modificare | correzione fatta | test | stato finale |
|---|---|---|---|---|---|
| 1. Cassazione `c.p.p.` / `QSP50194` | Il DB progressivo locale non aveva evidenza corrente QSP/c.p.p.; il canary `ultime` a limite 5 legge solo schede recenti e non include `QSP50194`. | `pct/legal_context_questions.py`, `tests/test_legal_update_publish_context.py`, test/fixture Cassazione già presenti | Confermata raggiungibilità diretta `contentId=QSP50194` e presenza `606`; preservato parser detail; aggiunta domanda mirata `articoli_cpp_pdf` sul PDF c.p.p.; mantenuta diagnosi senza import storico forzato. | Canary Cassazione no-publish, backfill mirato, probe diretto QSP, test publish context, Lex/corpus/Ricerca. | Chiuso con diagnosi controllata: detail raggiungibile, parser/test coperti, non popolato a forza nel DB corrente. |
| 2. Archivio Giurisprudenza a 0 schede strutturate | Le review esistenti non hanno tutte le chiavi minime: corte, numero, anno, data, fonte ufficiale e testo/PDF; alcune sono news/RAG o dataset. | `pct/legal_update_health_report.py`, `pct/cli.py`, `tests/test_legal_update_autofetch.py` | Aggiunto `legal-updates-giurisprudenza-structured-canary`; nessuna promozione se mancano chiavi. | `python -m pct.cli legal-updates-giurisprudenza-structured-canary --json`; test canary no-force. | Chiuso con blocco intenzionale: 23 item controllati, 0 candidati completi. |
| 3. Fonti in osservazione | Decisione non abbastanza esplicita fonte per fonte; alcuni canali producono home/cataloghi, SSL failure o documenti non ancora stabili. | `artifacts/.../observation-canary-summary.json`, `source-rollout-plan.md`, `source-rollout-execution.md`, documentazione Lex | Canary no-publish `limit 2` su tutte le 13 fonti; decisione finale per fonte, nessuna aggiunta allo scheduler. | Canary per fonte con diagnostica salvata. | Chiuso con blocco intenzionale/osservazione; nessuna fonte nuova abilitata. |
| 4. EUR-Lex / CELEX | EUR-Lex era RAG-only perché CELEX non era coperto da fixture/test dedicato. | `pct/legal_reference_extractor.py`, `tests/fixtures/legal_updates/eur_lex_celex.html`, `tests/test_legal_update_source_parsers.py`, `tests/test_legal_update_source_capabilities.py` | Aggiunto riconoscimento CELEX (`CELEX:32024R1689`) e fixture minima; confermata destinazione RAG-only se mancano chiavi strutturate. | Parser/capability shard. | Chiuso con blocco intenzionale: CELEX riconosciuto, nessuna pubblicazione UE strutturata incompleta. |
| 5. OpenGA documento concreto vs dataset | I cataloghi CKAN/tabellari possono sembrare giurisprudenza ma non sono documenti concreti. | Test esistenti su parser/capability/pipeline, report canary OpenGA | Canary no-publish su sentenze, ordinanze, decreti, pareri; confermati dataset RAG-only e PDF/documento concreto come candidato solo guarded futuro. | OpenGA canary summary; parser/capability/pipeline. | Chiuso come RAG-only per dataset; documento concreto non perso ma rinviato a pilot guarded. |
| 6. CLI ciclo scheduler/autofetch controllato | Esisteva il motore autofetch ma mancava comando CLI esplicito per ciclo controllato. | `pct/legal_update_autofetch.py`, `pct/cli.py`, `tests/test_legal_update_autofetch.py` | Implementato `legal-updates-run-progressive` con `--guarded-only` obbligatorio, `--dry-run`, budget, timeout, publish max, solo fonti verdi. | Dry-run CLI, autofetch/job queue/batch runner shard. | Chiuso. |
| 7. File runtime sporchi | Working tree aveva dati tenant/runtime e un workspace intelligence non tracciato. | `.gitignore`, report/documentazione | Preservati i dati tenant sporchi e non committati; aggiunta regola ignore mirata per `intelligence/workspace_intelligence.json`. | `git status --short`, governance, diff check. | Chiuso operativamente: runtime preservati, non committati. |
| 8. Vercel failure | Status esterno `Vercel` in failure può essere confuso con CI reale; deploy reale è Hetzner. | `docs/ci-cd-gates.md`, report/documentazione | Verificato commit status GitHub: Vercel failure è status esterno. Verificati anche rossi reali `Lint + syntax` da OpenAPI/test inventory e riallineati i generatori. | `generate_api_contracts.py --check`, `validate_openapi.py`, `verify_openapi_provider.py`, `generate_app_v2_test_docs.py --check`, smoke inventory. | Chiuso come documentazione di processo: Vercel fuori gate IUSENTRA, ma non dichiarare “CI tutto verde” se resta failure esterno. |

## Cassazione `QSP50194`

Comandi:

```powershell
python -m pct.cli legal-updates-canary --source cassazione_ultime_sent_ord_questioni --limit 5 --max-seconds 120 --no-publish --direct-only --save-diagnostics --json
python -m pct.cli legal-updates-backfill-diagnostics --source cassazione_ultime_sent_ord_questioni --missing attachments,ocr,references,questions --limit 20 --max-seconds 120 --no-publish --json
```

Esito:

- canary: `ok=true`, 5 documenti trovati, 0 processati, 5 invariati, 0 pubblicazioni;
- backfill: `ok=true`, 0 selezionati, 0 aggiornati, pending attachments/OCR/references/questions a 0;
- `QSP50194` non era nei 5 documenti dell'indice ultime;
- probe diretto: `https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194` risponde HTTP 200, contiene `QSP50194` e `606`;
- test fixture/parser confermano detail `contentId=QSP50194`, `art. 606 c.p.p.`, PDF/allegato, domanda contestuale e ranking su allegato/PDF.

Decisione: non importare storicamente il documento nel DB runtime durante Fase 11.5. Se serve popolamento reale del caso pilota, va fatto con job storico mirato e no-publish/pilot guarded, non con scheduler progressivo.

## Archivio Giurisprudenza

Comando:

```powershell
python -m pct.cli legal-updates-giurisprudenza-structured-canary --json
```

Esito: 23 item controllati tra Cassazione, Corte dei conti, Curia CGUE, OpenGA e Corte costituzionale; 0 candidati completi.

Motivo prevalente:

- Corte dei conti: numero/anno/data spesso presenti, ma corte non normalizzata in analisi;
- Curia: corte/data presenti, ma numero/anno decisione strutturati mancanti;
- Cassazione ultime: corte presente, ma numero/anno/data decisione non sempre estratti;
- OpenGA: dataset JSON/CSV/ODS o record senza data/chiavi complete.

Decisione: blocco intenzionale. Nessuna scheda strutturata viene creata senza chiavi minime.

## Fonti in osservazione

| fonte | esito canary | testo | allegati | riferimenti | domande | decisione finale | motivo |
|---|---|---|---|---|---|---|---|
| `cassazione_massimario` | ok, 47 trovati, 2 processati | sì, ma primo titolo homepage/ministero | no | non affidabili per publish | non affidabili per publish | blocked/osservazione | Fonte derivata; serve canary detail citazione/principio, non homepage. |
| `cassazione_citazioni_verificate` | ok, 47 trovati, 2 processati | sì, ma primo titolo homepage/ministero | no | non affidabili per publish | non affidabili per publish | blocked/osservazione | Fonte derivata; non schedulata finché il detail citazione non è stabile. |
| `corte_costituzionale` | ok, 0 trovati | no | no | no | no | blocked/osservazione | Nessuna scheda pronuncia verificabile nel canary; fallback navigazione bloccato. |
| `giustizia_amministrativa` | errore SSL | no | no | no | no | blocked/osservazione | `SSLCertVerificationError`; presidio automatico affidato a OpenGA ufficiale finché il canale diretto non è stabile. |
| `giustizia_amministrativa_decisioni_pareri` | errore SSL | no | no | no | no | blocked/osservazione | `SSLCertVerificationError` su `/dcsnprr`; non pubblicabile. |
| `inps_sentenze` | ok, 1 trovato, 1 processato | sì | no | parziale | parziale | verde candidata a fase futura | Produce documento utile ma non collaudato in guarded; resta fuori scheduler. |
| `agenzia_entrate` | ok, 21 trovati, 2 processati | sì, generico | no | parziale | parziale | blocked/osservazione | Serve filtro stabile su prassi tributaria, non pagine istituzionali. |
| `ministero_lavoro` | ok, 120 trovati, 2 processati | sì, generico | no | parziale | parziale | blocked/osservazione | Serve filtro documentale stabile. |
| `ministero_lavoro_interpelli` | ok, 101 trovati, 2 processati | sì, generico | no | parziale | parziale | blocked/osservazione | Serve canary sugli interpelli con allegati veri. |
| `agcm_bollettino` | ok=false per time limit, 55 trovati, 1 processato | sì, ma primo titolo navigazione | 4 | rumorosi | rumorose | blocked/osservazione | Supera budget 60s e prende `ITA selezionata`; serve filtro provvedimenti/bollettini stabile. |
| `banca_italia_normativa` | ok, 145 trovati, 2 processati | sì, ma primo titolo lingua/navigazione | no | parziale | parziale | blocked/osservazione | Serve filtro provvedimenti vigilanza, non navigazione. |
| `inail_istruzioni_operative` | errore SSL | no | no | no | no | blocked/osservazione | SSL non stabile; fonte disabilitata. |
| `mimit_incentivi` | ok, 10 trovati, 2 processati | sì | 2 | parziale | parziale | RAG-only/osservazione | Documenti utili ma non news generiche; pubblicare solo futuro documento operativo con guardie. |

## EUR-Lex

Decisione: CELEX viene riconosciuto, ma EUR-Lex resta RAG-only se non ci sono tutte le chiavi strutturate. Nessuna normativa UE viene pubblicata senza CELEX, titolo, tipo atto, numero, anno, fonte ufficiale e testo leggibile.

Fixture: `tests/fixtures/legal_updates/eur_lex_celex.html`.

Test coperti:

- riconoscimento `CELEX:32024R1689`;
- destinazione RAG-only se CELEX manca o chiavi incomplete;
- nessuna pubblicazione strutturata incompleta.

## OpenGA

Canary no-publish:

| fonte | trovati | processati | pubblicati | decisione |
|---|---:|---:|---:|---|
| `openga_sentenze` | 372 | 0 | 0 | RAG-only dataset, salvo PDF/documento concreto futuro |
| `openga_ordinanze` | 372 | 0 | 0 | RAG-only dataset, salvo PDF/documento concreto futuro |
| `openga_decreti` | 370 | 0 | 0 | RAG-only dataset, salvo PDF/documento concreto futuro |
| `openga_pareri` | 24 | 0 | 0 | RAG-only dataset, salvo PDF/documento concreto futuro |

Test coperti:

- CSV/JSON/ODS non pubblicabile;
- PDF sentenza concreto candidato;
- record tabellare non promosso a review giurisprudenziale certa;
- Lex può usare evidenza RAG-only ma non come sentenza certa.

## Scheduler/autofetch controllato

Comando disponibile:

```powershell
python -m pct.cli legal-updates-run-progressive --source-budget 3 --publish-max-items 5 --item-timeout-seconds 120 --guarded-only --json
```

Dry-run verificato:

```powershell
python -m pct.cli legal-updates-run-progressive --source-budget 3 --publish-max-items 5 --item-timeout-seconds 120 --guarded-only --dry-run --json
```

Regole implementate:

- `--guarded-only` obbligatorio;
- solo fonti verdi progressive;
- fonti in osservazione escluse;
- RAG-only escluse dalla pubblicazione;
- archivi Normattiva/codici fuori batch fonte web;
- budget fonte rispettato;
- publish max rispettato;
- timeout passato al runner;
- dry-run senza enqueue e senza publish.

## Runtime dirty e Vercel

Runtime:

- `data/tenants/tenant-8bf98719c459/intelligence/assistente_redazionale.json`: preservato, non committato;
- `data/tenants/tenant-8bf98719c459/preventivi/conferimenti.json`: preservato, non committato;
- `intelligence/workspace_intelligence.json`: generato runtime, aggiunto a `.gitignore`, non committato.

Vercel:

- status esterno verificato su GitHub commit status come `Vercel failure`;
- motivo provider: `Canceled from the Vercel Dashboard`;
- non è gate di qualità IUSENTRA perché il deploy reale è Hetzner;
- non dichiarare comunque “CI tutto verde” se resta quello status esterno;
- il rosso GitHub Actions reale precedente era `Lint + syntax` per OpenAPI non allineato: contratti rigenerati e verificati;
- il primo push Fase 11.5 (`c62ea56f1`) ha poi evidenziato `docs/test-inventory.md` non aggiornato nello step `App V2 registry and test plan gates`: il documento è stato rigenerato e i gate locali sono verdi;
- gli aggregatori `Pytest core` e `Local Signer e PKCS#11` erano rossi solo per cascata da shard `Skipped` dopo il blocco primario; il vecchio aggregatore `Coverage moduli critici` senza `parte` non è stato reintrodotto.

## Verifiche eseguite

| comando | esito |
|---|---|
| `python -m py_compile pct/legal_update_pipeline.py pct/legal_update_repository.py pct/legal_update_autofetch.py pct/legal_update_health_report.py pct/cli.py web/services/legal_update_surface.py` | OK |
| `python -m pytest tests/test_legal_update_source_capabilities.py tests/test_legal_update_source_parsers.py tests/test_legal_update_safe_diagnostics.py -q --tb=short` | OK, 38/38 |
| `python -m pytest tests/test_legal_update_autofetch.py tests/test_legal_update_surface_jobs.py tests/test_legal_update_job_queue.py tests/test_legal_update_batch_runner.py -q --tb=short` | OK, 27/27 |
| `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` | OK, 42/42 |
| `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short` | OK, 39/39 |
| `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_lex_operational_knowledge.py tests/test_react_legal_intelligence_search.py tests/test_giurisprudenza.py -q --tb=short` | OK, 99/99 |
| `python scripts/react-migration/generate_api_contracts.py --check` | OK |
| `python scripts/validate_openapi.py` | OK |
| `python scripts/verify_openapi_provider.py` | OK |
| `python scripts/react-migration/generate_app_v2_test_docs.py --check` | OK |
| `python scripts/react-migration/generate_app_v2_page_registry.py --check` | OK |
| `python scripts/smoke_app_v2_all.py --subset inventory` | OK |
| `python -m pytest -q tests/test_app_v2_page_registry.py tests/test_app_v2_test_plan_phase10.py tests/test_ci_cd_gates_phase11.py --tb=short` | OK, 13/13 |
| `python tools/check_repo_governance.py` | OK |
| `python -m pytest tests/test_utf8_integrity.py -q --tb=short` | OK, 4/4 |
| `git diff --check` | OK, solo warning CRLF/LF |

Frontend non toccato: `pnpm --filter @iusentra/studio typecheck` e build non eseguiti.

## Stato finale operativo

Health report finale dopo i canary di osservazione: `ok=true`, readiness `da_verificare`, `issue_count=4`, per errori intenzionali sulle fonti ancora bloccate (`giustizia_amministrativa`, `giustizia_amministrativa_decisioni_pareri`, `agcm_bollettino`, `inail_istruzioni_operative`). Non è regressione: questi errori sono il motivo tecnico per non abilitarle.

Fonti verdi finali: `cassazione_ultime_sent_ord_questioni`, `corte_conti`, `curia_cgue_rss`, `inps_circolari`, `inps_messaggi`, `agcom_provvedimenti`, `anac_documenti`, `garante_privacy`, `gazzetta_ufficiale`.

Fonti RAG-only finali: `dati_normattiva`, `eur_lex`, `istat_prezzi`, `openga_giustizia_amministrativa`, `openga_calendario_udienze`, `openga_sentenze`, `openga_ordinanze`, `openga_decreti`, `openga_pareri`, `openga_provvedimenti_pubblicati`, `openga_ricorsi_definiti`, `openga_ricorsi_pendenti`, `openga_ricorsi_pervenuti`, `pst_giustizia_download`.

Fonti in osservazione finali: `cassazione_massimario`, `cassazione_citazioni_verificate`, `corte_costituzionale`, `giustizia_amministrativa`, `giustizia_amministrativa_decisioni_pareri`, `inps_sentenze`, `agenzia_entrate`, `ministero_lavoro`, `ministero_lavoro_interpelli`, `agcm_bollettino`, `banca_italia_normativa`, `inail_istruzioni_operative`, `mimit_incentivi`.

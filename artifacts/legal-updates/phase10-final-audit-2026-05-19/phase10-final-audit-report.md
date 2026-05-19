# Fase 10 - Audit finale aggiornamenti legali

Aggiornato il 19 maggio 2026. Audit eseguito senza import massivo, senza backup e senza Web libero automatico. La verifica riguarda classificazione fonti, superfici Admin, Ricerca Legale, Lex AI, Archivio Giurisprudenza, scheduler progressivo, UTF-8 e gate separati.

## 1. Git status iniziale

Eseguito prima di ogni attività:

```text
 M data/tenants/tenant-8bf98719c459/intelligence/assistente_redazionale.json
 M data/tenants/tenant-8bf98719c459/preventivi/conferimenti.json
?? intelligence/workspace_intelligence.json
```

I tre elementi erano già presenti prima dell'audit e sono rimasti esclusi dallo staging perché runtime/dati locali.

## 2. Matrice finale fonti

Legenda sintetica: `Docs` = documenti letti nel DB progressivo locale; `Txt` = testo disponibile; `All/PDF/OCR` = allegati, PDF e testo/OCR leggibile; `Rif/Dom` = riferimenti e domande contestuali salvati.

| Fonte | Stato/policy | Abilitata | Docs | Txt | All/PDF/OCR | Rif/Dom | Destinazione | Motivo se non pubblicabile |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `gazzetta_ufficiale` | verde, guarded | sì | 23 | sì | 7/3/sì | 43/45 | Normativa o notizia | Pubblicabile solo con conferma guarded. |
| `normattiva` | RAG-only, no-publish | sì | 37 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio locale, non news automatica. |
| `dati_normattiva` | RAG-only, no-publish | sì | 1 | sì | 0/0/sì | 10/12 | Solo RAG | Catalogo tecnico/open data. |
| `corte_costituzionale` | osservazione, blocked | sì | 5 | sì | 0/0/n.d. | 51/16 | Giurisprudenza o RAG | Canale diretto da stabilizzare su scheda pronuncia. |
| `corte_conti` | verde, guarded | sì | 10 | sì | 9/9/sì | 23/46 | Giurisprudenza o RAG | Pubblicabile solo con allegato/testo confermato. |
| `cassazione_massimario` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Giurisprudenza o RAG | Serve canary dedicato. |
| `cassazione_ultime_sent_ord_questioni` | verde, guarded | sì | 7 | sì | 9/9/sì | 36/49 | News/RAG, giurisprudenza se chiavi complete | Archivio strutturato solo con chiavi minime. |
| `giustizia_amministrativa` | osservazione, blocked | no | 0 | no | 0/0/n.d. | 0/0 | Giurisprudenza o RAG | HTML diretto instabile; presidio via OpenGA. |
| `openga_giustizia_amministrativa` | RAG-only, no-publish | sì | 0 | no | 0/0/n.d. | 0/0 | RAG | Catalogo generale, non provvedimento. |
| `giustizia_amministrativa_decisioni_pareri` | osservazione, blocked | no | 0 | no | 0/0/n.d. | 0/0 | Giurisprudenza | Canale HTML diretto da canary. |
| `openga_calendario_udienze` | RAG-only, no-publish | sì | 0 | no | 0/0/n.d. | 0/0 | RAG | Dato di stato, non decisione. |
| `openga_decreti` | RAG-only, no-publish | sì | 370 | sì | 2/0/sì | 8/28 | RAG | Dataset tabellare salvo documento concreto. |
| `openga_ordinanze` | RAG-only, no-publish | sì | 372 | sì | 2/0/sì | 3/28 | RAG | Dataset tabellare salvo documento concreto. |
| `openga_pareri` | RAG-only, no-publish | sì | 24 | sì | 2/0/sì | 7/28 | RAG | Dataset tabellare salvo documento concreto. |
| `openga_provvedimenti_pubblicati` | RAG-only, no-publish | sì | 0 | no | 0/0/n.d. | 0/0 | RAG | Dataset operativo, non pubblicazione autonoma. |
| `openga_ricorsi_definiti` | RAG-only, no-publish | sì | 0 | no | 0/0/n.d. | 0/0 | RAG | Dato statistico/procedurale. |
| `openga_ricorsi_pendenti` | RAG-only, no-publish | sì | 0 | no | 0/0/n.d. | 0/0 | RAG | Dato statistico/procedurale. |
| `openga_ricorsi_pervenuti` | RAG-only, no-publish | sì | 0 | no | 0/0/n.d. | 0/0 | RAG | Dato statistico/procedurale. |
| `openga_sentenze` | RAG-only, no-publish | sì | 372 | sì | 5/0/sì | 8/28 | RAG | Dataset tabellare salvo documento concreto. |
| `eur_lex` | RAG-only, no-publish | sì | 1 | sì | 0/0/sì | 8/12 | Solo RAG UE | Parser CELEX non ancora governato per publish. |
| `agenzia_entrate` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Serve canary dedicato. |
| `ministero_lavoro` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Serve canary dedicato. |
| `ministero_lavoro_interpelli` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Serve canary dedicato. |
| `garante_privacy` | verde, guarded | sì | 8 | sì | 0/0/sì | 21/38 | Prassi/notizia | Acquisita, ma publish bloccato se mancano conferme. |
| `anac_documenti` | verde, guarded | sì | 25 | sì | 0/0/sì | 11/37 | Prassi/notizia | Acquisita, ma publish bloccato se mancano conferme. |
| `inps_circolari` | verde, guarded | sì | 50 | sì | 10/10/sì | 34/48 | Prassi/notizia | Pubblicabile come prassi/news verificata. |
| `inps_messaggi` | verde, guarded | sì | 12 | sì | 13/10/sì | 21/46 | Prassi/notizia | Pubblicabile come prassi/news verificata. |
| `inps_sentenze` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Giurisprudenza/RAG | Serve canary dedicato. |
| `curia_cgue_rss` | verde, guarded | sì | 10 | sì | 0/0/sì | 6/36 | Giurisprudenza UE/RAG | Publish solo con riferimenti confermati. |
| `istat_prezzi` | RAG-only, no-publish | sì | 10 | sì | 1/0/sì | 4/23 | Prassi/RAG | Indici/calcoli, non news giuridica. |
| `mimit_incentivi` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Serve canary dedicato. |
| `agcm_bollettino` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Serve canary dedicato. |
| `agcom_provvedimenti` | verde, guarded | sì | 30 | sì | 6/6/sì | 38/48 | Prassi/news/RAG | Pubblicabile solo se non consultazione generica. |
| `banca_italia_normativa` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Serve canary dedicato. |
| `inail_istruzioni_operative` | osservazione, blocked | no | 0 | no | 0/0/n.d. | 0/0 | Prassi/RAG | Canale disabilitato finché non stabile. |
| `pst_giustizia_download` | RAG-only, no-publish | sì | 4 | sì | 3/0/sì | 57/13 | Solo RAG tecnico | Specifiche/download, non news. |
| `codice_civile` | RAG-only, no-publish | sì | 30 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio Normattiva, non publish. |
| `codice_procedura_civile` | RAG-only, no-publish | sì | 30 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio Normattiva, non publish. |
| `codice_penale` | RAG-only, no-publish | sì | 30 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio Normattiva, non publish. |
| `codice_procedura_penale` | RAG-only, no-publish | sì | 30 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio Normattiva, non publish. |
| `codice_processo_amministrativo` | RAG-only, no-publish | sì | 30 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio Normattiva, non publish. |
| `codice_strada` | RAG-only, no-publish | sì | 30 | sì | 0/0/sì | 11/25 | Normativa/RAG | Archivio Normattiva, non publish. |
| `studiocataldi_codice_civile` | out_of_scope, blocked | no | 0 | no | 0/0/no | 0/0 | Fuori perimetro | Fonte secondaria: solo Web libero manuale. |
| `avvocatoandreani_codice_procedura_civile` | out_of_scope, blocked | no | 0 | no | 0/0/no | 0/0 | Fuori perimetro | Fonte secondaria: solo Web libero manuale. |
| `studiocataldi_codice_penale` | out_of_scope, blocked | no | 0 | no | 0/0/no | 0/0 | Fuori perimetro | Fonte secondaria: solo Web libero manuale. |
| `avvocatoandreani_codice_strada` | out_of_scope, blocked | no | 0 | no | 0/0/no | 0/0 | Fuori perimetro | Fonte secondaria: solo Web libero manuale. |
| `cassazione_citazioni_verificate` | osservazione, blocked | sì | 0 | no | 0/0/n.d. | 0/0 | Giurisprudenza/RAG | Fonte derivata, canary dedicato. |

Totali locali verificati: 47 fonti catalogo, 24 news pubblicate, 3 prassi, 0 normative strutturate, 0 schede giurisprudenza strutturate, 203 evidenze web, 50 allegati, 203 testi/OCR leggibili, 0 run stantii `running`.

## 3. Fonti popolate

Fonti con dati effettivi nel DB progressivo: Gazzetta Ufficiale, Normattiva, Dati Normattiva, Corte Costituzionale, Corte dei Conti, Cassazione ultime sentenze/ordinanze/questioni, OpenGA decreti/ordinanze/pareri/sentenze, EUR-Lex, Garante Privacy, ANAC, INPS circolari, INPS messaggi, Curia CGUE, ISTAT, AGCOM, PST Giustizia e codici Normattiva.

Fonti verdi abilitate al publish guarded nello scheduler: `cassazione_ultime_sent_ord_questioni`, `corte_conti`, `curia_cgue_rss`, `inps_circolari`, `inps_messaggi`, `agcom_provvedimenti`, `anac_documenti`, `garante_privacy`, `gazzetta_ufficiale`.

## 4. Fonti RAG-only

RAG-only/no-publish: `normattiva`, `dati_normattiva`, tutte le fonti OpenGA catalogo/dataset, `eur_lex`, `istat_prezzi`, `pst_giustizia_download`, `codice_civile`, `codice_procedura_civile`, `codice_penale`, `codice_procedura_penale`, `codice_processo_amministrativo`, `codice_strada`.

## 5. Fonti in osservazione

In osservazione/blocked: `corte_costituzionale`, `cassazione_massimario`, `giustizia_amministrativa`, `giustizia_amministrativa_decisioni_pareri`, `agenzia_entrate`, `ministero_lavoro`, `ministero_lavoro_interpelli`, `inps_sentenze`, `mimit_incentivi`, `agcm_bollettino`, `banca_italia_normativa`, `inail_istruzioni_operative`, `cassazione_citazioni_verificate`.

## 6. Fonti escluse

Escluse dal publish: fonti secondarie `studiocataldi_*` e `avvocatoandreani_*`; fonti gialle/rosse/osservazione; fonti tecniche e RAG-only. Motivo comune: mancanza di canary guarded stabile, natura tecnica/catalogo, fonte non ufficiale o assenza di chiavi minime.

## 7. Stato Admin

Verificate le superfici `/admin/aggiornamenti-legali/`, `/admin/aggiornamenti-legali/fonti`, `/admin/aggiornamenti-legali/staging`, `/admin/aggiornamenti-legali/review`, `/admin/aggiornamenti-legali/archivio`.

Il render GET non avvia import massivo: recupero, analisi e pubblicazione restano azioni POST o job espliciti. I test confermano etichette operative al posto dei codici grezzi, archivio renderizzabile, staging/review senza dati incoerenti e API admin separate per fonti, analisi, archivio e audit.

## 8. Stato Ricerca Legale

Ricerca Legale espone record reali con fonte, tipo evidenza, affidabilità, PDF/OCR quando disponibile, punti chiave, controlli operativi e contesto deduplicato. Il probe su INPS ha restituito 18 record con sezione fonte ufficiale, 12 elementi da archivio studio, 1 Normattiva e 11 fonti ufficiali. La UI non usa mock: i dettagli provengono da DB aggiornamenti legali, archivi ufficiali e payload normalizzato.

## 9. Stato Lex AI

Probe repository/Lex:

- `Quale allegato ufficiale contiene questa ordinanza?`: risultati Cassazione con allegato, riferimenti e domande contestuali.
- `Quali articoli sono richiamati nel PDF?`: risultati AGCOM/INPS/Corte dei Conti con PDF o testo allegato e riferimenti estratti.
- `Mostrami aggiornamenti INPS utili al contenzioso previdenziale.`: risultati INPS circolari/messaggi con PDF, OCR, riferimenti e domande.
- `Questo provvedimento AGCOM è una consultazione o un provvedimento utile?`: risultati AGCOM con classificazione e contesto per distinguere provvedimento utile da consultazione generica.
- `Cerca riferimenti al c.p.p. negli aggiornamenti Cassazione.`: la logica di ranking e le guardie esistono, ma il DB progressivo locale non contiene oggi evidenze Cassazione con `c.p.p.`/QSP50194; questo è rischio residuo reale e va risolto con canary/backfill mirato, non con import massivo.

Web libero resta manuale, separato e non promuove risultati nel DB/corpus.

## 10. Stato Archivio Giurisprudenza

L'archivio strutturato resta a 0 schede nuove perché nessuna decisione del run progressivo ha superato tutte le chiavi minime richieste per la promozione strutturata. Le decisioni senza chiavi complete restano news/RAG-only, con PDF/OCR interrogabile da Lex e Ricerca Legale.

## 11. Stato scheduler

Scheduler progressivo verificato: fonti verdi abilitate, fonti gialle/rosse/osservazione escluse dal publish, budget 3, timeout fonte 120 secondi, publish guarded, limite publish 5, nessun `running` stantio nel DB locale e nessun errore interno mascherato come completato. Il fix di audit impedisce a fonti ufficiali del catalogo di ricadere nel fallback generico `fuori_perimetro`.

## 12. Test eseguiti

```text
python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short
python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short
python -m pytest tests/test_lex_source_corpus_generator.py tests/test_lex_operational_knowledge.py tests/test_react_legal_intelligence_search.py tests/test_giurisprudenza.py -q --tb=short
python -m pytest tests/test_legal_update_autofetch.py tests/test_legal_update_surface_jobs.py tests/test_legal_update_job_queue.py tests/test_legal_update_batch_runner.py -q --tb=short
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
python tools/check_repo_governance.py
python -m pytest tests/test_utf8_integrity.py -q --tb=short
python tools/sync_packaging_files.py --check
python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short
git diff --check
```

Esito: tutti verdi. Il primo `git diff --check` ha segnalato spazi finali nel bundle React rigenerato; rimossi e rilanciato verde.

## 13. Test non eseguiti e motivo

Nessun test richiesto dall'utente è rimasto non eseguito. Docker locale e deploy Hetzner sono passaggi operativi successivi al commit/push, non import massivo e non backup.

## 14. Rischi residui reali

- Il DB progressivo locale non contiene ancora evidenze Cassazione con `c.p.p.`/QSP50194, quindi la domanda specifica sui riferimenti al c.p.p. in Cassazione deve dichiarare lacuna finché non viene eseguito un canary/backfill mirato.
- Le fonti in osservazione non devono essere abilitate al publish automatico prima di canary specifici e parser stabili.
- L'Archivio Giurisprudenza resta prudente: PDF/OCR interrogabili, ma nessuna promozione strutturata senza chiavi minime.

## 15. Git status finale

Da rilevare dopo commit, push dei due branch gemelli, igiene repository e deploy Hetzner.

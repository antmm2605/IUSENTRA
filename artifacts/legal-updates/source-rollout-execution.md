# Esecuzione piano fonti - Aggiornamenti legali

Aggiornato il 19 maggio 2026. Questo file trasforma `source-rollout-plan.md` in backlog eseguibile con stato prima/dopo della tranche codice.

## Aggiornamento Fase 4 - primo pilot guarded

Aggiornato il 19 maggio 2026 dopo il pilot controllato con `--publish-mode guarded`. Non è stato avviato import massivo, non è stato lanciato lo scheduler globale e la pubblicazione è rimasta limitata ai soli documenti letti dal canary corrente.

| fonte | documenti processati | documenti pubblicati | destinazione | esito |
|---|---:|---:|---|---|
| `cassazione_ultime_sent_ord_questioni` | 3 invariati con evidenze rinfrescate | 3 | news + RAG ufficiale pronto | verde con note OCR/R.G.; Archivio Giurisprudenza preparato, senza scheda strutturata perché mancano chiavi complete corte/numero/anno |
| `inps_circolari` | 3 invariati con evidenze rinfrescate | 3 | news | verde; downgrade guarded da normativa a notizia verificata per evitare chiavi normative incoerenti su circolari |
| `agcom_provvedimenti` | 3 invariati con evidenze rinfrescate | 3 | 2 news, 1 prassi | verde; delibere e determina con testo/PDF/riferimenti/domande pronti |

Diagnostica salvata in `artifacts/legal-updates/pilot-guarded-2026-05-19/`. Il file `verification.json` conferma 9 documenti pubblicati, 0 duplicati, render dell'archivio admin, Ricerca Legale e Lex positivi per tutti i contenuti, allegati premiati nelle domande su PDF/documenti ufficiali e 9 elementi presenti nell'archivio news più 1 in prassi.

Problemi emersi e risolti durante il pilot:

- la prima guardia Cassazione bloccava documenti con testo pagina breve anche quando PDF/OCR ufficiale era già letto; ora il guarded accetta evidenza/PDF/OCR leggibile;
- le circolari INPS potevano essere proposte come normativa per numero/data della circolare; ora una fonte di prassi non crea normativa se la chiave non è coerente e viene limitata a notizia verificata;
- il controllo sui testi tecnici non interpreta più `null` dentro parole italiane e, per le notizie, valuta i campi realmente visibili;
- il ranking Lex/Ricerca Legale riconosce INPS, AGCOM, ANAC e Garante e porta in testa il PDF/allegato quando la domanda lo richiede.

## Tranche completata in questa esecuzione

| fonte | problema concreto | file modificati | test da creare/eseguire | stato prima | stato dopo |
|---|---|---|---|---|---|
| strumenti sicuri per tutte le fonti | mancava un canary fonte-per-fonte con limite obbligatorio e backfill diagnostico distinto per allegati/OCR/riferimenti/domande | `pct/legal_update_diagnostics.py`, `pct/cli.py`, `web/services/legal_update_surface.py`, `web/templates/admin/legal_updates_sources.html` | `tests/test_legal_update_safe_diagnostics.py` | prove manuali o batch runner generico | canary e backfill CLI sicuri, JSON, no-publish, direct-only, ultimo canary visibile in admin |
| fixture offline famiglie fonte | i parser erano testati con HTML inline, non con un set fisico riusabile per popolare e diagnosticare fonte per fonte | `tests/fixtures/legal_updates/*` | `tests/test_legal_update_safe_diagnostics.py` | fixture fisiche mancanti | Cassazione, AGCOM, INPS, Curia, CKAN/OpenGA, ANAC, Garante, PST e PDF testuale/scansionato mock presenti |
| canary fonte per fonte 2026-05-19 | serviva una prova no-publish con diagnostica reale e report verde/giallo/rosso prima del pilot guarded | `pct/legal_update_source_parsers.py`, `pct/legal_update_pipeline.py`, `pct/legal_update_diagnostics.py`, `artifacts/legal-updates/canary-report-2026-05-19.md` | `tests/test_legal_update_source_parsers.py`, `tests/test_legal_updates_pipeline.py`, canary CLI con `--no-publish` | parser Gazzetta/INPS/autorità da verificare live con limite | Cassazione, INPS, AGCOM, ANAC, Garante e PST hanno diagnostica coerente; pilot candidate limitate a Cassazione, INPS circolari e AGCOM |
| tutte le capability fonte | il registro aveva i campi interni ma non tutti gli alias macchina richiesti dalla fase sicura | `pct/legal_update_source_capabilities.py` | `tests/test_legal_update_source_capabilities.py` | policy presente ma non nel formato completo richiesto | payload con famiglia, parser, PDF allowed, riferimenti, domande, destinazione canonica, filtro, esclusioni e note diagnostiche |
| tutte le fonti `DEFAULT_SOURCE_ROWS` e persistite | mancava una policy macchina per fonte: parser, dettaglio, allegati, destinazione e scarti erano distribuiti tra pipeline e note | `pct/legal_update_source_capabilities.py`, `web/services/legal_update_surface.py`, `web/templates/admin/legal_updates_sources.html` | `tests/test_legal_update_source_capabilities.py` | decisione testuale nel piano | capability registry deterministico e visibile in admin |
| fonti HTML listing/detail | parser generico troppo cieco per elenco, scheda e allegati | `pct/legal_update_source_parsers.py`, `pct/legal_update_pipeline.py` | `tests/test_legal_update_source_parsers.py` | `html` con euristiche interne alla pipeline | adapter HTML con dettaglio, scarto navigazione e allegati |
| fonti Feed/RSS/Atom | descrizione povera non completata da scheda dettaglio | `pct/legal_update_source_parsers.py` | `tests/test_legal_update_source_parsers.py` | feed base | feed con detail opzionale e allegati |
| fonti CKAN/OpenGA | cataloghi tecnici rischiavano coda o scarto indistinto; documenti concreti non avevano policy separata | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py`, `pct/legal_update_pipeline.py` | `tests/test_legal_update_source_parsers.py`, `tests/test_legal_updates_pipeline.py` | in osservazione/RAG-only generico | RAG-only per cataloghi, documento giuridico concreto non perso |
| Cassazione ultime sentenze/ordinanze/questioni | logica pilota da mantenere fuori dalla pipeline monolitica | `pct/legal_update_source_parsers.py`, `pct/legal_update_pipeline.py` | test Cassazione esistente + parser fixture | pronto ma accoppiato alla pipeline | adapter dedicato Civile/Penale/detail `contentId` |
| Corte dei Conti | parser/detail fixture mancanti | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py` | fixture HTML dettaglio + PDF link | da implementare | adapter HTML/detail/PDF pronto a test deterministico |
| Giustizia Amministrativa e decisioni/pareri | fonte HTML diretta non deve essere scheduler cieco | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py` | fixture dettaglio TAR/CdS | in osservazione/da implementare | backfill/detail governato con destinazione giurisprudenza se chiavi minime |
| EUR-Lex e CURIA | atti UE e giurisprudenza UE senza parser/detail fixture | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py` | fixture HTML/feed UE | da implementare | adapter HTML/feed con allegati e riferimenti UE |
| Agenzia Entrate, Ministero Lavoro, Interpelli, ANAC, Garante, AGCM, AGCOM, Banca d'Italia, INAIL | autorità/prassi senza policy unica su allegati e scarti | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py`, `pct/legal_relevance.py` | fixture autorità indipendenti e filtri | in osservazione salvo AGCOM/Garante | policy ufficiale, dettaglio, PDF/OCR e scarti tracciabili |
| INPS, ISTAT, MIMIT | feed utile ma senza detail fetch governato | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py` | fixture RSS con dettaglio povero/ricco | pronto/in osservazione | feed/detail e allegati testabili |
| PST Giustizia | download tecnici non distinguibili da news | `pct/legal_update_source_capabilities.py`, `pct/legal_update_source_parsers.py` | fixture PST specifiche/manuali | in osservazione | RAG tecnico, fuori pubblicazione news se non deposito/specifiche |
| codici Normattiva | codici pronti ma senza capability esplicita | `pct/legal_update_source_capabilities.py` | copertura registry | pronto | normativa/RAG ufficiale con policy articolo |
| fonti secondarie | non pubblicabili ma policy non centralizzata | `pct/legal_update_source_capabilities.py` | test registry + filtro | non pubblicabile | fuori perimetro ufficiale, solo Web libero manuale |
| riferimenti normativi | estrattore presente ma non isolato come modulo dedicato | `pct/legal_reference_extractor.py`, `pct/legal_update_enrichment.py`, `pct/legal_update_repository.py` | test riferimenti dedicati | integrato in enrichment | modulo dedicato con `raw_text`, `reference_type`, snippet, URL e zero link inventati |
| domande contestuali | generatore presente ma non isolato come modulo dedicato | `pct/legal_context_questions.py`, `pct/legal_update_enrichment.py`, `pct/legal_update_repository.py` | test domande dedicate | integrato in enrichment | modulo dedicato con tipo, ragione e fonte dati |
| Ricerca Legale/Lex | destinazione fonte non esposta nei risultati | `pct/legal_update_repository.py`, `web/services/react_legal_intelligence_bridge.py` | test Ricerca Legale/Lex | PDF/OCR/riferimenti/domande presenti | aggiunta destinazione policy nei payload e punti chiave |

## Fonti rimaste in osservazione operativa dopo la tranche

| fonte | motivo tecnico preciso | decisione |
|---|---|---|
| `giustizia_amministrativa` | HTML diretto resta disabilitato per instabilità/paginazione; l'adapter è pronto per backfill mirato con fixture | in osservazione, non scheduler cieco |
| `dati_normattiva` | catalogo tecnico: non è un aggiornamento giuridico pubblicabile | RAG-only metadati |
| `openga_*` cataloghi/stati ricorsi/calendari | dataset o record statistici senza documento allegato non sono news né giurisprudenza strutturata | RAG-only, pubblicazione solo se risorsa contiene documento giuridico concreto |
| `inail_istruzioni_operative` | fonte disabilitata nel catalogo: utile solo con backfill mirato finché non viene collaudata | in osservazione |
| fonti secondarie Studio Cataldi/Avvocato Andreani | non ufficiali e non devono entrare nel corpus ufficiale | fuori perimetro, solo Web libero manuale |

## Aggiornamento Fase 3 - fonti gialle post-canary

Aggiornato il 19 maggio 2026 dopo i rerun mirati `--limit 2 --max-seconds 60 --no-publish --direct-only --save-diagnostics --json`. Nessun import massivo e nessuna pubblicazione automatica.

| fonte | problema concreto | file modificati | test eseguiti | stato dopo |
|---|---|---|---|---|
| `gazzetta_ufficiale` | gli elementi invariati conservavano il link PDF parser ma non rinfrescavano evidenze/hash/testo allegato | `pct/legal_update_diagnostics.py`, `pct/legal_update_web_verification.py`, `pct/legal_update_repository.py` | `tests/test_legal_update_safe_diagnostics.py`, `tests/test_legal_update_web_verification_attachments.py` | verde: 2 PDF letti, `pdf_found=true`, `text_read=true` |
| `anac_documenti` | il parser creava un falso allegato dal testo della card quando mancava un link PDF reale | `pct/legal_update_source_parsers.py` | `tests/test_legal_update_source_parsers.py` | verde: testo ufficiale pronto, allegati finti rimossi |
| `garante_privacy` | il link al testo GDPR era trattato come allegato della newsletter/provvedimento | `pct/legal_update_source_parsers.py` | `tests/test_legal_update_source_parsers.py` | verde: testo docweb pronto, link normativi non marcati come allegati |
| `pst_giustizia_download` | pagine tecniche generiche entravano come possibili news | `pct/legal_update_source_parsers.py` | `tests/test_legal_update_source_parsers.py` | RAG-only: fonte tecnica non pubblicabile |
| `openga_sentenze` | CSV/JSON/ODS OpenGA con riferimenti interni potevano sembrare documenti giurisprudenziali concreti | `pct/legal_update_source_capabilities.py` | `tests/test_legal_update_source_capabilities.py` | RAG-only: dataset tabellari non pubblicabili, PDF documentali separati |

### Verifiche Fase 3

| comando | esito | nota |
|---|---|---|
| `python -m pytest tests/test_legal_update_source_parsers.py tests/test_legal_update_source_capabilities.py -q --tb=short` | OK | 21/21 passati: parser ANAC/Garante/PST, OpenGA RAG-only e registry capability. |
| `python -m pytest tests/test_legal_update_safe_diagnostics.py -q --tb=short` | OK | 6/6 passati: canary invariato rinfresca PDF normalizzato senza pubblicare. |
| `python -m pytest tests/test_legal_update_web_verification_attachments.py -q --tb=short` | OK | 13/13 passati: allegati normalizzati e PDF ufficiali letti. |
| `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` | OK | 41/41 passati. |
| `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py -q --tb=short` | OK | 28/28 passati. |
| `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_react_legal_intelligence_search.py -q --tb=short` | OK | 24/24 passati. |
| `python tools/check_repo_governance.py` | OK | Governance check OK. |
| `python -m pytest tests/test_utf8_integrity.py -q --tb=short` | OK | 4/4 passati. |
| `git diff --check` | OK | Nessun errore whitespace; Git segnala solo normalizzazione CRLF/LF su file JSON già toccati e dati runtime non committati. |

## Verifiche eseguite nella tranche

| comando | esito | nota |
|---|---|---|
| `python -m pytest tests/test_legal_update_source_capabilities.py tests/test_legal_update_source_parsers.py -q --tb=short` | OK | 9/9 passati: registry, filtri, riferimenti, domande, parser HTML/feed/CKAN/Cassazione. |
| `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` | OK | 40/40 passati dopo correzione merge dettaglio Cassazione e classificazione cataloghi OpenGA. |
| `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short` | OK | 36/36 passati: PDF/OCR/backfill e matrice domande preservata. |
| `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_lex_operational_knowledge.py tests/test_react_legal_intelligence_search.py tests/test_giurisprudenza.py -q --tb=short` | OK | 99/99 passati: Lex/RAG, Ricerca Legale, Web libero isolato e Archivio Giurisprudenza. |

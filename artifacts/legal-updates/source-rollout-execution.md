# Esecuzione piano fonti - Aggiornamenti legali

Aggiornato il 19 maggio 2026. Questo file trasforma `source-rollout-plan.md` in backlog eseguibile con stato prima/dopo della tranche codice.

## Tranche completata in questa esecuzione

| fonte | problema concreto | file modificati | test da creare/eseguire | stato prima | stato dopo |
|---|---|---|---|---|---|
| strumenti sicuri per tutte le fonti | mancava un canary fonte-per-fonte con limite obbligatorio e backfill diagnostico distinto per allegati/OCR/riferimenti/domande | `pct/legal_update_diagnostics.py`, `pct/cli.py`, `web/services/legal_update_surface.py`, `web/templates/admin/legal_updates_sources.html` | `tests/test_legal_update_safe_diagnostics.py` | prove manuali o batch runner generico | canary e backfill CLI sicuri, JSON, no-publish, direct-only, ultimo canary visibile in admin |
| fixture offline famiglie fonte | i parser erano testati con HTML inline, non con un set fisico riusabile per popolare e diagnosticare fonte per fonte | `tests/fixtures/legal_updates/*` | `tests/test_legal_update_safe_diagnostics.py` | fixture fisiche mancanti | Cassazione, AGCOM, INPS, Curia, CKAN/OpenGA, ANAC, Garante, PST e PDF testuale/scansionato mock presenti |
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

## Verifiche eseguite nella tranche

| comando | esito | nota |
|---|---|---|
| `python -m pytest tests/test_legal_update_source_capabilities.py tests/test_legal_update_source_parsers.py -q --tb=short` | OK | 9/9 passati: registry, filtri, riferimenti, domande, parser HTML/feed/CKAN/Cassazione. |
| `python -m pytest tests/test_legal_updates_pipeline.py -q --tb=short` | OK | 40/40 passati dopo correzione merge dettaglio Cassazione e classificazione cataloghi OpenGA. |
| `python -m pytest tests/test_legal_update_publish_context.py tests/test_legal_update_web_verification_attachments.py tests/test_document_intelligence_extraction.py -q --tb=short` | OK | 36/36 passati: PDF/OCR/backfill e matrice domande preservata. |
| `python -m pytest tests/test_lex_source_corpus_generator.py tests/test_lex_operational_knowledge.py tests/test_react_legal_intelligence_search.py tests/test_giurisprudenza.py -q --tb=short` | OK | 99/99 passati: Lex/RAG, Ricerca Legale, Web libero isolato e Archivio Giurisprudenza. |

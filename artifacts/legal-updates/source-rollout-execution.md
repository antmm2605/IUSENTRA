# Esecuzione piano fonti - Aggiornamenti legali

Aggiornato il 19 maggio 2026. Questo file trasforma `source-rollout-plan.md` in backlog eseguibile con stato prima/dopo della tranche codice.

## Aggiornamento Fase 11 - regime controllato e manutenzione fonti

Aggiornato il 19 maggio 2026. La fase prepara la manutenzione ordinaria senza backup, senza import massivo e senza pubblicazioni incontrollate.

| area | stato rilevato | azione eseguita | esito |
|---|---|---|---|
| Dashboard qualità fonti | la console mostrava fonti, archivio e scheduler, ma non un quadro unico su classi operative, errori, OCR, allegati, riferimenti e domande | aggiunto il payload `source_quality_dashboard` e la sezione `Qualità fonti` nella dashboard admin | visibili fonti attive, in osservazione, RAG-only, non pubblicabili, ultimo controllo, errori, OCR falliti, allegati vuoti, riferimenti/domande mancanti, review pendenti e pubblicazioni guarded |
| Report periodico | mancava un comando unico per il regime controllato | aggiunto `python -m pct.cli legal-updates-health-report --json` | il JSON include stato fonti, coda, errori, PDF/OCR, riferimenti, domande, scheduler, review, pubblicazioni, retry sicuro, backfill mirato e procedura nuove fonti |
| Retry sicuro | coda e batch avevano già deduplica, tentativi e timeout, ma non erano esposti nel report sanitario | il report espone max attempts, timeout, errori leggibili, coda e garanzia di pubblicazione solo guarded | retry governato verificabile senza duplicare job e senza pubblicazione fuori guardia |
| Backfill periodico | il comando diagnostico esisteva già per `attachments`, `ocr`, `references`, `questions` | il report produce piano e comandi periodici solo mirati, sempre con `--no-publish` | nessun backfill globale: solo allegati vuoti, OCR mancanti/falliti, riferimenti mancanti e domande mancanti |
| Nuove fonti | il piano fonte per fonte descriveva canary e capability, ma serviva una procedura sintetica operativa | aggiunta procedura macchina nel report e nota nel piano | ogni nuova fonte passa da capability, fixture, canary, report, pilot guarded e scheduler solo dopo esito verde |
| Versione | Fase 10 era a `2.245.51` | bump a `2.245.52` | tranche Fase 11 tracciata come rilascio successivo |

## Aggiornamento Fase 10 - audit finale prima del regime

Aggiornato il 19 maggio 2026. La fase ha verificato l'intero catalogo `DEFAULT_SOURCE_ROWS` dopo il popolamento progressivo, senza import massivo e senza backup. Il report operativo è `artifacts/legal-updates/phase10-final-audit-2026-05-19/phase10-final-audit-report.md`.

| area | stato rilevato | azione eseguita | esito |
|---|---|---|---|
| Copertura fonti | alcune fonti ufficiali del catalogo ricadevano ancora nel fallback generico `fuori_perimetro` se non presenti nei set progressivi | completata la classificazione progressiva per OpenGA catalogo/stati, Cassazione Massimario e Giustizia Amministrativa diretta | tutte le fonti ufficiali del catalogo hanno classe esplicita verde, RAG-only, osservazione o archivio; le fonti private restano `out_of_scope` |
| Ricerca Legale e Lex | il repository espone fonti pronte/non pronte, PDF/OCR, riferimenti e domande; il DB locale non contiene oggi evidenze Cassazione con `c.p.p.`/QSP50194 | eseguiti probe mirati su allegati, articoli PDF, INPS, AGCOM e Cassazione/c.p.p. | Lex e Ricerca Legale usano pagina, PDF/OCR, riferimenti e domande; il buco Cassazione/c.p.p. è registrato come rischio reale da canary mirato |
| Archivio Giurisprudenza | il run progressivo non ha prodotto decisioni con chiavi minime complete | mantenuta la promozione strutturata bloccata senza chiavi | PDF/OCR restano interrogabili da RAG/news; 0 schede nuove nell'archivio strutturato |
| Scheduler | il piano progressivo deve restare conservativo | verificati budget, timeout, `publish guarded`, fonti verdi abilitate, esclusione gialle/rosse/osservazione e 0 running stantii | ciclo pronto per regime prudente, senza mascherare errori interni |
| Gate | richiesti controlli divisi per fasi, senza aggregatori storici | eseguiti shard pytest, typecheck/build, governance, UTF-8 e diff check separati | tutti verdi e registrati in `artifacts/react-migration/pytest-confirmed-ok.md` |

## Aggiornamento Fase 9 - estensione a tutte le fonti verdi

Aggiornato il 19 maggio 2026. La fase ha esteso il popolamento progressivo alle fonti verdi rimanenti, mantenendo budget basso/medio, `publish-mode guarded` per le sole fonti verdi, nessuna pubblicazione per RAG-only/archivi/codici e stop su errore reale. Il report operativo è `artifacts/legal-updates/phase9-green-2026-05-19/phase9-green-report.md`.

| area | stato rilevato | azione eseguita | esito |
|---|---|---|---|
| Fonti verdi abilitate | lo step 1 era stabile ma limitato a quattro fonti | promosse in fase 9 `corte_conti`, `curia_cgue_rss`, `anac_documenti`, `garante_privacy` e `gazzetta_ufficiale`, preservando `cassazione_ultime_sent_ord_questioni`, `inps_circolari`, `inps_messaggi`, `agcom_provvedimenti` | 9 fonti verdi censite nello scheduler progressivo con budget 3 e timeout per fonte |
| RAG-only | OpenGA, PST, Dati Normattiva, EUR-Lex e ISTAT non devono diventare news generiche | eseguiti canary no-publish con `limit 2` dove richiesto | 0 pubblicazioni da fonti tecniche o cataloghi; evidenze disponibili solo per RAG/diagnostica |
| Osservazione | diverse fonti richieste non avevano canary verde dedicato | mantenute fuori run `cassazione_citazioni_verificate`, `corte_costituzionale`, `inps_sentenze`, `agenzia_entrate`, Ministero Lavoro, AGCM, Banca d'Italia, INAIL e MIMIT | nessuna fonte gialla/rossa/osservazione abilitata |
| Lotto 4 EUR-Lex | la pagina vuota produceva `Document is empty` | fermato il lotto, corretto il parser HTML per `ParserError`, aggiunto test e rieseguito solo EUR-Lex | canary EUR-Lex RAG-only OK, 1 documento diagnostico, 0 pubblicazioni |
| Superfici utente | Ricerca Legale e Lex devono usare evidenze vere, non cataloghi pubblicati come news | pubblicati 14 documenti guarded da fonti verdi; 17 PDF/OCR, 340 riferimenti e 740 domande nei report fonte | Ricerca Legale/Lex aggiornate; Archivio Giurisprudenza non riceve schede strutturate senza chiavi complete |

Verifiche mirate già eseguite durante i lotti: parser/capability, publish context, allegati, Document Intelligence, corpus Lex, Ricerca Legale, Giurisprudenza, job queue, batch runner e scheduler registry. I gate finali della fase 9 sono registrati in `artifacts/react-migration/pytest-confirmed-ok.md`.

## Aggiornamento Fase 7 - backfill mirato PDF/OCR/riferimenti/domande

Aggiornato il 19 maggio 2026. La fase è stata eseguita senza backup, senza Web libero, senza pubblicazione automatica e senza backfill globale non limitato. Il report operativo è `artifacts/legal-updates/phase7-backfill-2026-05-19/phase7-backfill-report.md`.

| area | stato rilevato | azione eseguita | esito |
|---|---|---|---|
| CLI backfill | `--missing` accettava solo un valore e la combinazione richiesta sarebbe stata respinta da `click.Choice`; su Windows il JSON poteva fallire in stampa con stream `cp1252` | aggiunto parsing comma-separated per `attachments,ocr,references,questions`, report `summary` e output UTF-8 | comandi singoli e combinati eseguibili con JSON, limiti e `--no-publish` preservati |
| Allegati/PDF/OCR | repository locale con 168 evidenze, 47 allegati, 168 testi leggibili e 0 PDF con testo/OCR mancante nel perimetro selezionato | backfill `attachments` e `ocr` con limiti 50/30 e 120 secondi | nessun nuovo elemento selezionabile; nessun OCR fallito nascosto |
| Riferimenti | alcune evidenze web avevano termini salvati ma riferimenti normativi/identificativi incompleti | backfill `references` limitato a 50 evidenze | 50 selezionate, 50 processate, 14 aggiornate, 20 riferimenti aggiunti, 0 fallite |
| Domande contestuali | le evidenze selezionabili avevano già matrice domande | backfill `questions` limitato a 50 | 0 selezionate; nessuna domanda aggiunta |
| Cassazione specifica | `cassazione_ultime_sent_ord_questioni` risultava già completa per allegati/OCR/riferimenti/domande | backfill combinato con `--source cassazione_ultime_sent_ord_questioni --limit 20` | 0 selezionate; stato Lex/Ricerca Legale invariato |
| Fonti RAG-only/open data | serviva controllo limitato senza promozione | backfill `--include-open-data --missing references,questions --limit 20` | 20 selezionate e processate, 20 invariate, 0 pubblicazioni |

Verifiche mirate già eseguite: `py_compile` CLI/backfill, `tests/test_legal_update_safe_diagnostics.py`, shard allegati/OCR/document intelligence, shard corpus Lex/Ricerca Legale, governance, UTF-8 e `git diff --check`. Gli esiti sono registrati anche in `artifacts/react-migration/pytest-confirmed-ok.md`.

## Aggiornamento Fase 6 - normativa e archivi base

Aggiornato il 19 maggio 2026. La fase normativa è stata eseguita senza backup, senza download ciechi, senza import massivo e senza ricostruire gli archivi già presenti. Il report operativo è `artifacts/legal-updates/phase6-normativa-archives-2026-05-19/phase6-report.md`.

| area | stato rilevato | azione eseguita | esito |
|---|---|---|---|
| Normattiva locale | `normattiva.sqlite` presente con 42.677 documenti, 238.110 articoli e 279.777 chunk; raw ZIP e manifest presenti | collegato il retriever a query per codice/articolo, con fallback sui raw ZIP già presenti quando il DB non ha il chunk autonomo | codici fondamentali interrogabili senza nuovi download |
| Gazzetta locale | `lex_sources.sqlite` presente con 12 documenti e 1.852 chunk | deduplicati i risultati per documento in `search_gazzetta()` | Ricerca Legale non mostra più chunk ripetuti dello stesso fascicolo |
| Ricerca Legale | già collegata agli archivi ufficiali locali | preservato il bridge e verificato l'uso dei conteggi reali | Normattiva/Gazzetta restano visibili nel payload |
| Lex | usava soprattutto il catalogo fonti e il repository aggiornamenti | aggiunto contesto Normattiva/Gazzetta da archivi ufficiali in `search_normativa_sources()` | le domande normative ricevono contesto ufficiale locale |
| EUR-Lex | fonte UE ufficiale censita, parser CELEX dedicato non stabilizzato in questa tranche | classificata come `RAG-only` UE con motivo operativo | nessuna pubblicazione strutturata UE senza fixture CELEX verde |
| Fonti secondarie | Studio Cataldi e Avvocato Andreani già disabilitate | confermato blocco da fonte ufficiale/corpus | restano solo supporto secondario o Web libero esplicito |

Verifiche mirate già eseguite: `py_compile` dei moduli toccati, `tests/test_normattiva_importer.py`, `tests/test_official_sources_retriever.py`, `tests/test_legal_update_source_capabilities.py`, probe conteggi archivi e probe Lex su `codice civile art. 2043`. I gate completi della fase sono registrati nel report finale e in `artifacts/react-migration/pytest-confirmed-ok.md`.

## Aggiornamento Fase 5 - primo gruppo fonti verdi

Aggiornato il 19 maggio 2026 dopo il popolamento controllato del primo gruppo fonti verdi. Ogni fonte è stata eseguita separatamente con `--limit 5`, `--max-seconds 120`, `--allow-publish`, `--publish-mode guarded`, `--direct-only`, `--save-diagnostics` e output JSON salvato in `artifacts/legal-updates/phase5-green-2026-05-19/`. Non sono stati avviati import massivi, scheduler globale o Web libero.

| fonte | trovati | processati | pubblicati | scarti / destinazione | esito |
|---|---:|---:|---:|---|---|
| `cassazione_ultime_sent_ord_questioni` | 5 | 0 nuovi, 5 invariati | 5 | nessuno | verde; 3 già pilot e 2 ulteriori schede pubblicate come news/RAG ufficiale con PDF/OCR |
| `inps_circolari` | 50 | 2 nuovi, 3 invariati | 5 | nessuno | verde; circolari pubblicate come news verificate, non normativa incoerente |
| `inps_messaggi` | 9 | 2 nuovi, 3 invariati | 2 | 3 scarti per testo tecnico grezzo | verde parziale; pubblicati solo messaggi con testo UI pulito |
| `agcom_provvedimenti` | 30 | 2 nuovi, 3 invariati | 4 | 1 duplicato già pubblicato | verde; delibere/determine con PDF e riferimenti |
| `corte_conti` | 10 | 5 | 3 | 2 RAG-only per riferimenti non ritrovati nella diagnosi | verde dopo fix parser; titoli reali da allegato e download PDF letti |
| `curia_cgue_rss` | 10 | 2 nuovi, 3 invariati | 1 | 4 scarti per riferimenti non ritrovati nella diagnosi | verde parziale; la causa `C-797/23` è pubblicata e interrogabile |
| `corte_costituzionale` | 0 | 0 | 0 | fonte diretta bloccata/nessuna scheda pronuncia verificabile | esclusa dalla pubblicazione; fallback navigazione/captcha bloccato |
| `anac_documenti` | 25 | 3 nuovi, 2 invariati | 0 | 5 scarti: servono conferme ulteriori | acquisita ma non pubblicata |
| `garante_privacy` | 5 | 5 | 0 | 3 conferme insufficienti, 2 riferimenti non ritrovati | acquisita ma non pubblicata |
| `pst_giustizia_download` | 1 | 0 nuovi, 1 invariato | 0 | RAG-only tecnico | nessuna news pubblicata |
| `openga_sentenze` | 372 | 3 nuovi, 2 invariati | 0 | RAG-only dataset tabellare | nessuna news/giurisprudenza pubblicata |

Verifica post-fase: `verification.json` registra 20 documenti pubblicati unici, 20/20 ritrovabili da Ricerca Legale con query fonte mirata, 20/20 interrogabili da Lex, 8 elementi RAG-only/non pubblicati e 26 scarti guarded. L'Archivio Giurisprudenza strutturato non riceve nuove schede in questa fase: le pronunce pubblicate restano news/RAG ufficiale finché la promozione strutturata non passa chiavi e guardie specifiche.

Correzioni applicate durante la fase:

- `corte_costituzionale`: il parser non crea più documenti fallback da captcha, pagine in inglese o navigazione e accetta solo URL `/scheda-pronuncia/<anno>/<numero>`.
- `corte_conti`: il parser scarta navigazione (`INTRANET`, `BIBLIOTECA`, sedi, breadcrumb), usa il titolo reale del PDF/sentenza quando la pagina mostra `Leggi di più` o `Dettaglio documenti`, e la verifica allegati legge i download ufficiali `/Download?id=...` marcati PDF dalla label.
- Gli artifact della fase 5 sono stati rigenerati con output UTF-8 reale e controllati senza caratteri sostitutivi.

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

# Centro Fonti Ufficiali Lex

Il Centro Fonti Ufficiali Lex alimenta Lex AI con fonti normative e operative ufficiali, acquisite in modo locale, tracciabile e disabilitabile da configurazione.

Fonti attive di default:

- `normattiva`: testi normativi da API Open Data, ZIP/XML e import SQLite/JSONL.
- `gazzetta_ufficiale`: novita' della Serie Generale negli ultimi 30 giorni, con download PDF pubblico.

Fonti predisposte ma disabilitate:

- Ministero Giustizia, PST/PCT, PAT/SIGA, PTT/SIGIT, PDP Penale, CNF, Agenzia Entrate, Garante Privacy, EUR-Lex, ANAC, INPS, INAIL, Banca d'Italia, AGCM, AGCOM, IPA, INI-PEC, INAD e fonti locali di studio.

## Regole di sicurezza

- Non aggirare CAPTCHA, login, sistemi anti-bot o limitazioni tecniche.
- Non usare sessioni private o credenziali nei file di configurazione.
- Usare solo API pubbliche, feed, sitemap, PDF pubblici o file che lo studio ha diritto di trattare.
- Ogni fonte deve restare disabilitabile da `config/lex_official_sources.example.json`.
- Verificare sempre condizioni d'uso, licenza e frequenza ammessa delle fonti ufficiali.

## Installazione

```powershell
pip install -r requirements-lex-sources.txt
pip install -r requirements-normattiva-import.txt
```

## Normattiva

Riferimento ufficiale per il download Open Data:

```text
https://dati.normattiva.it/assets/come_fare_per/Normattiva%20OpenData.html
```

Elenco collezioni disponibili:

```powershell
python tools\normattiva_multi_sync.py --list
```

Download del set core per studio legale:

```powershell
python tools\normattiva_multi_sync.py --download-core --vigenza ORIGINALE --out data\normativa\raw
```

Download di tutte le collezioni esposte dall'API:

```powershell
python tools\normattiva_multi_sync.py --download-all-from-api --vigenza ORIGINALE --out data\normativa\raw
```

Import SQLite + JSONL:

```powershell
python tools\normattiva_import.py --raw-dir data\normativa\raw --limit 50
```

Import completo con percorsi espliciti:

```powershell
python tools\normattiva_import.py `
  --raw-dir data\normativa\raw `
  --db data\normativa\normattiva.sqlite `
  --jsonl data\normativa\index\normattiva_chunks.jsonl `
  --report data\normativa\reports\normattiva_import_report.json
```

Output principali:

```text
data\normativa\raw
data\normativa\normattiva.sqlite
data\normativa\index\normattiva_chunks.jsonl
data\normativa\reports\normattiva_import_report.json
```

In produzione i percorsi canonici sono sotto il volume persistente:

```text
/data/normativa/normattiva.sqlite
/data/normativa/index/normattiva_chunks.jsonl
```

Verifica Hetzner 2026-05-16: il manifest ufficiale espone 23 collezioni; 19 ZIP sono validi e popolano il database attivo con 189.851 documenti, 800.757 articoli e 639.273 chunk. Le collezioni `Regolamenti di delegificazione`, `Regolamenti governativi`, `Regolamenti ministeriali` e `Testi Unici` risultano esposte dall'elenco ma scaricate come stream vuoto dal servizio e restano tracciate nel manifest tentativi.

## Gazzetta Ufficiale

Sincronizzazione dedicata:

```powershell
python tools\gazzetta_ufficiale_sync.py --init-db --max-issues 5 --export-jsonl
```

Sincronizzazione tramite registry:

```powershell
python tools\lex_sources_sync.py --run gazzetta_ufficiale --export-jsonl
```

Output principali:

```text
data\fonti_ufficiali\lex_sources.sqlite
data\fonti_ufficiali\raw
data\fonti_ufficiali\text
data\fonti_ufficiali\index\lex_sources_chunks.jsonl
data\fonti_ufficiali\reports
```

In produzione i percorsi canonici sono sotto il volume persistente:

```text
/data/fonti_ufficiali/lex_sources.sqlite
/data/fonti_ufficiali/index/lex_sources_chunks.jsonl
```

## Registro fonti ufficiali

```powershell
python tools\lex_sources_sync.py --list
python tools\lex_sources_sync.py --init-db
python tools\lex_sources_sync.py --run-all --export-jsonl
```

Normattiva e Gazzetta Ufficiale sono abilitate. Le altre fonti sono dichiarate ma disattivate finche' non vengono configurati URL, feed o connettori ufficiali.

## Audit di consegna verso avvocato, Ricerca Legale e Lex

Il controllo di copertura del Centro Fonti non si limita a verificare se una
fonte esiste. Deve stabilire se quella fonte arriva davvero al lavoro
dell'avvocato: Ricerca Legale, Lex AI/RAG Legal, Guida Pratica, Scadenziario,
Template Atti/editor, DB normativa o motore aggiornamenti.

Comando:

```powershell
python scripts\audit_legal_source_delivery.py
```

Output:

```text
artifacts\legal-sources\legal-source-delivery-audit-2026-06-06.json
artifacts\legal-sources\legal-source-delivery-audit-2026-06-06.csv
artifacts\legal-sources\legal-source-delivery-audit-2026-06-06.md
```

Ogni riga dell'audit deve indicare:

- stato di consegna (`operativa_controllabile`, `da_attivare_controllabile`, `gap`, `contesto_non_ufficiale`);
- URL o canale ufficiale, autorità, destinazione prodotto e azione richiesta;
- uso concreto per l'avvocato e domanda Lex di prova;
- materiali giuridici da controllare;
- articoli e codici pertinenti;
- decreti, D.Lgs., D.M., regolamenti o regole tecniche;
- sentenze, ordinanze, decreti, provvedimenti, verbali o udienze rilevanti;
- sequenza di ricerca e limite professionale prima della citazione in atto.

## Monitor aggiornamenti utilizzabile dall'avvocato

Il motore aggiornamenti legali deve usare lo stesso audit anche quando mostra lo
stato delle fonti acquisite. La scheda di una fonte non è sufficiente se espone
solo "pronta" o "da verificare": deve spiegare a cosa serve nella pratica, quale
azione manca, quale materiale giuridico va controllato e quale domanda Lex deve
saper sostenere.

Nel payload React `autofetchMonitor.sources[*]` ogni fonte monitorata deve
includere almeno:

- `lawyer_use`, `practice_phase`, `expected_output` e `activation_action`;
- `source_href`, `authority` e stato Centro Fonti;
- `legal_materials`, `articles_and_codes`, `decrees_and_rules`,
  `case_law_and_hearings` e `research_steps`;
- `lex_test_question`, usata dalla UI per avviare una ricerca di controllo.

La pagina Ricerca Legale deve visualizzare questi dati nel blocco "Fonti da
presidiare", così l'avvocato vede subito se la fonte è pronta per redigere,
notificare, depositare, eccepire, provare o decidere la strategia della pratica.

Ricerca Legale pubblica queste righe come `source-delivery:*`. Lex deve usare
gli stessi campi quando l'avvocato chiede fonti ufficiali, codice civile,
codice penale, procedura, decreti legislativi, decreti ministeriali, sentenze,
udienze o provvedimenti.

## SQLite

Schemi governati:

- `db/normattiva_sqlite.sql`
- `db/lex_sources_sqlite.sql`

Tabelle principali:

- `normative_documents`, `normative_articles`, `normative_chunks`, `normative_sync_runs`
- `official_sources`, `official_documents`, `official_chunks`, `official_sync_runs`, `official_source_errors`

## Retrieval Lex AI

Modulo:

```text
lex\retrieval\official_sources_retriever.py
```

Funzioni disponibili:

- `search_official_sources(query, materia=None, source=None, limit=10)`
- `search_normattiva(query, materia=None, vigenza=None, limit=10)`
- `search_gazzetta(query, days=30, limit=10)`
- `get_source_document(document_id)`
- `get_chunk_context(chunk_id)`

Ogni risultato espone fonte, titolo, data, URL o path origine, chunk/articolo, livello di affidabilita' e data acquisizione.

Le funzioni di retrieval risolvono automaticamente i path da variabili ambiente (`PCT_LEX_OFFICIAL_DB`, `PCT_LEX_OFFICIAL_JSONL`, `PCT_NORMATTIVA_DB`, `PCT_NORMATTIVA_JSONL`) e, quando il codice gira in container, dai percorsi `/data/...`.

## Test

```powershell
python -m pytest tests\test_normattiva_client.py tests\test_normattiva_importer.py tests\test_gazzetta_connector.py tests\test_official_sources_registry.py -q
```

## Note operative

Il comando `lex_sources_sync --run-all` rispetta la configurazione delle fonti. Per evitare download massivi accidentali, Normattiva usa il connettore dedicato solo se `download_enabled` viene attivato; il percorso ordinario resta `normattiva_multi_sync.py` seguito da `normattiva_import.py`.

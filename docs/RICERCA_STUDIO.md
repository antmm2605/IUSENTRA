# Ricerca Studio

`Ricerca Studio` e' il motore globale operativo di IUSENTRA.

Obiettivo: trovare rapidamente fascicoli, clienti, soggetti, documenti, scadenze, agenda, preventivi, conferimenti, fatture, pagamenti, comunicazioni, template atti, depositi telematici e dati interni di intelligence senza interrogare tutti i moduli a ogni ricerca.

## Superfici

- pagina UI: `/global-search`
- statistiche leggere: `/api/global-search/stats`
- ricerca JSON: `/api/global-search?q=...&type=...&limit=...`
- suggerimenti: `/api/global-search/suggest?q=...`
- reindicizzazione completa: `POST /api/global-search/reindex`
- reindicizzazione singola entita': `POST /api/global-search/reindex/entity`

## Caricamento leggero

La pagina React usa `GET /api/global-search/stats` per aprire il quadro statistiche senza costruire il contesto completo dei repository applicativi.

`GET /api/global-search` non esegue piu' un reindex sincrono nascosto quando l'indice e' vuoto. Se arriva una query e `stats.total == 0`, la risposta resta `ok: true`, contiene `indexing_required: true`, `results: []` e le statistiche correnti. L'utente puo' avviare la ricostruzione con `POST /api/global-search/reindex`, che resta la sola operazione di reindicizzazione completa.

## Storage

La ricerca usa un indice centrale tenant-aware:

- tabella: `global_search_index`
- audit manuale: `global_search_audit`
- SQLite: FTS5 quando disponibile, fallback LIKE sicuro quando FTS5 non e' disponibile
- PostgreSQL: schema predisposto con `tsvector` e `pg_trgm`

Migrazioni:

- `pct/sql/20260426_global_search.sql`
- `pct/sql/20260426_global_search_postgres.sql`

## Adapter

Gli adapter convertono i record reali in documenti normalizzati:

- `FascicoliSearchAdapter`
- `ClientiSearchAdapter`
- `SoggettiSearchAdapter`
- `ScadenzeSearchAdapter`
- `AgendaSearchAdapter`
- `DocumentiSearchAdapter`
- `PreventiviSearchAdapter`
- `FattureSearchAdapter`
- `PagamentiSearchAdapter`
- `ComunicazioniSearchAdapter`
- `TemplateAttiSearchAdapter`
- `DepositiSearchAdapter`
- `LegalIntelligenceSearchAdapter`

Gli adapter sono difensivi: se un modulo non e' disponibile, la reindicizzazione continua e riporta l'errore nel report.

## Sicurezza

- filtro obbligatorio per `tenant_id`
- nessuna indicizzazione di campi con nomi sensibili come password, token, PIN, secret o chiavi private
- snippet HTML sanitizzati
- reindex manuale tracciato in audit
- funzione `search_for_lex(...)` per Lex AI con fonte interna verificata

## Uso Lex AI

La funzione riusabile e':

```python
from pct.global_search.service import search_for_lex

results = search_for_lex(context, "RG 466/2023 Alessi", limit=10)
```

Ogni risultato per Lex contiene fonte, titolo, tipo, URL, snippet, affidabilita' e metadata non sensibili.

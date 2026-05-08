# LEX — Ricerca Sentenze Esatte (v2.201.0)

Guida tecnica alla ricerca di sentenze, ordinanze e decreti con riferimento numerico esatto.

---

## 1. Problema risolto

Prima di v2.201.0:
- Query "Sentenza n. 7919 del 31/03/2026" restituiva 5-12 sentenze generiche sulla stessa materia
- Il numero esatto non veniva verificato
- Confidence = 0.6-0.7 anche senza trovare la sentenza richiesta
- Se era aperto un fascicolo, la ricerca web veniva bloccata

Da v2.201.0:
- Il parser estrae numero, data, anno, organo, sezione
- La ricerca usa query ottimizzate per `cortedicassazione.it`
- Il guard verifica che le evidenze corrispondano al riferimento
- La confidence è cappata in base alla qualità del match
- La ricerca web è forzata anche con contesto fascicolo aperto

---

## 2. Flusso tecnico

```
Query utente
    │
    ▼
case_law_reference_parser.py
    │   parse_case_law_reference(query)
    │   → ExactLegalReference(number, date, year, court, ...)
    │
    ▼
Router: workflow = "giurisprudenza_specifica"
    │
    ▼
_should_force_web_fallback = True (anche se c'è fascicolo in contesto)
    │
    ▼
Web search: cassazione_query_variants
    │   site:cortedicassazione.it "7919" "31/03/2026"
    │
    ▼
ExactLegalReferenceGuard.check(reference, evidence_items)
    │
    ├── not_found → risposta onesta + link Cassazione
    ├── found_no_text → link + avviso "testo non disponibile"
    └── found_with_text → risposta con dispositivo + fonte ufficiale
```

---

## 3. case_law_reference_parser.py

### Tipi atto riconosciuti

| Keyword | Tipo |
|---------|------|
| sentenza | `sentenza` |
| ordinanza | `ordinanza` |
| decreto | `decreto` |
| provvedimento | `provvedimento` |
| massima | `massima` |

### Organi riconosciuti

| Pattern | Organo |
|---------|--------|
| "corte di cassazione", "cassazione" | Corte di Cassazione |
| "corte cost." | Corte Costituzionale |
| "consiglio di stato" | Consiglio di Stato |
| "tar" | TAR |
| "tribunale di ..." | Tribunale |

### Pattern numero

- `n. 7919/2026` → numero=7919, anno=2026
- `n. 7919 del 31/03/2026` → numero=7919, data=31/03/2026
- `#7919` → numero=7919

### Pattern data

- `del 31/03/2026` → data=31/03/2026
- `del 31 marzo 2026` → data=31/03/2026
- `2026-03-31` → data=31/03/2026

---

## 4. ExactLegalReferenceGuard

### Classificazione evidenze

Ogni evidence item è classificato come:
- **exact_match**: contiene numero + (data o anno) + dominio ufficiale
- **related_match**: stesso tipo atto ma numero/data non corrispondenti
- **irrilevante**: scartato

### Score item

| Componente | Punteggio |
|------------|-----------|
| Numero sentenza trovato | +0.40 |
| Anno/data trovato | +0.25 |
| Dominio ufficiale (cassazione.it, ecc.) | +0.20 |
| Tipo atto corrispondente | +0.10 |

Soglia exact match: score ≥ 0.50

### Confidence caps

| Stato | Cap |
|-------|-----|
| `not_found` | 0.45 |
| `found_no_text` | 0.55 |
| `found_with_text` | 0.85 |

---

## 5. Risposta a utente

### Caso A: trovata con testo integrale

```
Ho individuato la fonte ufficiale per questa sentenza.

Sentenza n. 7919 del 31/03/2026 — Corte di Cassazione, Sezione Civile
Fonte: cortedicassazione.it (link)

[Testo del dispositivo / massima se disponibile]

Nota: verificare sempre il testo integrale sulla fonte ufficiale.
```

### Caso B: non trovata

```
Non ho trovato una conferma ufficiale esatta della Sentenza n. 7919 del 31/03/2026.

Possibili cause:
• La sentenza potrebbe non essere ancora pubblicata sul sito ufficiale
• Il numero o la data potrebbero essere leggermente diversi
• La sentenza potrebbe trovarsi in una banca dati privata (DeJure, Leggi d'Italia)

Puoi verificare direttamente su:
• cortedicassazione.it (Archivio sentenze civili/penali)
• giustizia.it (motore ricerca avanzata)
```

---

## 6. Test di riferimento

```bash
python -m pytest tests/test_lex_sources_and_studio_data.py::test_parse_exact_sentenza_numero_data -v
python -m pytest tests/test_lex_sources_and_studio_data.py::test_guard_no_evidence_not_found -v
python -m pytest tests/test_lex_sources_and_studio_data.py::test_guard_evidence_number_no_full_text -v
python -m pytest tests/test_lex_sources_and_studio_data.py::test_cassazione_query_variants_generated -v
```

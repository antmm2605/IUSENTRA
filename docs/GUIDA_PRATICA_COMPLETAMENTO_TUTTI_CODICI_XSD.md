# Guida Pratica - completamento di tutti i codici XSD/PST

## Flusso operativo corretto

1. Il catalogo ministeriale resta in `pct/data/cataloghi/codici_oggetto_pst.json`.
2. Il knowledge base resta separato in `pct/data/legal_knowledge_base.full.json` e nei moduli `pct/data/legal_knowledge_base_modules/`.
3. Le guide curate coprono tutti i codici ufficiali depositabili.
4. Gli alias interni non presenti nel catalogo ufficiale restano non depositabili.

## Stato audit 2.248.18

```text
record ufficiali PST/XSD: 1.018
guide ufficiali curate: 1.018
codici ufficiali senza guida curata: 0
incoerenze deposito: 0
schede interne o alias non depositabili: 54
```

Il CSV dei mancanti è `artifacts/guida-pratica/codici-ufficiali-senza-guida-curata.csv` e contiene solo l'intestazione.

## Comandi

```bash
python scripts\merge_legal_kb_modules.py
python scripts\curate_missing_guida_pratica_official_codes.py
python scripts\merge_legal_kb_modules.py
python scripts\validate_codici_oggetto_pst.py --min-records 1000
python scripts\verify_pst_xsd_catalog.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated --report artifacts\guida-pratica\guida-pratica-audit.json --missing-guidance-csv artifacts\guida-pratica\codici-ufficiali-senza-guida-curata.csv
```

## Regola di deposito

La guida può spiegare anche schede interne o alias storici, ma il deposito deve usare solo codici presenti nel catalogo ufficiale PST/XSD. Il servizio espone `codice_deposito.depositabile=true` solo per questi codici.

Quando il codice non è depositabile, il checklist mantiene il presidio `codice_deposito_non_ufficiale` per la generazione deposito, ma la guida resta un'opzione di consultazione e non blocca il lavoro ordinario sul fascicolo.

Aggiornamento 23 maggio 2026: i moduli TOP9 set5 sono stati importati come KB operativa. I codici ufficiali non coerenti con la scheda ricevuta non vengono sovrascritti: la guida usa alias interni e il deposito resta vincolato al catalogo PST/XSD locale.

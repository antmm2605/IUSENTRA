# Guida Pratica - Knowledge Base completa

La Guida Pratica vive fuori dal codice applicativo:

- `pct/data/legal_knowledge_base.full.json`;
- `pct/data/legal_knowledge_base.json`;
- `pct/data/legal_knowledge_base_modules/*.json`;
- `pct/data/legal_knowledge_base_index.json`.

Il merge dei moduli produce un knowledge base unico, ma il catalogo ufficiale PST/XSD resta separato in `pct/data/cataloghi/codici_oggetto_pst.json`.

## Risultato operativo 2.248.9

- Codici nel catalogo guida: 1.048.
- Codici ufficiali PST/XSD: 1.018.
- Codici ufficiali con guida curata: 1.018.
- Codici ufficiali senza guida curata: 0.
- Alias interni non depositabili: 30.

Gli alias interni sono mantenuti per continuità dei fascicoli e per guida operativa, ma non vengono considerati codici di deposito.

## Uso nel fascicolo

Nel dettaglio fascicolo React, `GuidaPraticaSidebar` legge il codice oggetto e chiama:

```text
GET /api/v1/ui/fascicoli/<id_fasc>/guida-pratica
```

Il backend risolve il codice, legge il knowledge base, applica eventuale ereditarietà e restituisce:

- checklist;
- normativa;
- atto principale;
- campi obbligatori;
- allegati;
- adempimenti;
- stato del codice deposito.

## Validazione

```bash
python scripts\merge_legal_kb_modules.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py -q --tb=short
```

La copertura ufficiale deve rimanere al 100%. Se un codice ufficiale entra nel catalogo senza guida curata, il validatore deve fallire e il modulo guida va completato prima del rilascio.

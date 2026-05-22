# Guida Pratica - Knowledge Base completa

La Guida Pratica vive fuori dal codice applicativo:

- `pct/data/legal_knowledge_base.full.json`;
- `pct/data/legal_knowledge_base.json`;
- `pct/data/legal_knowledge_base_modules/*.json`;
- `pct/data/legal_knowledge_base_index.json`.

Il merge dei moduli produce un knowledge base unico, ma il catalogo ufficiale PST/XSD resta separato in `pct/data/cataloghi/codici_oggetto_pst.json`.

## Risultato operativo 2.248.10

- Codici nel catalogo guida: 1.054.
- Codici ufficiali PST/XSD: 1.018.
- Codici ufficiali con guida curata: 1.018.
- Codici ufficiali senza guida curata: 0.
- Schede interne o alias non depositabili: 36.

Le schede interne sono mantenute per continuità dei fascicoli, ricerca e guida operativa facoltativa, ma non vengono considerate codici di deposito.

## Uso nel fascicolo

Nel dettaglio fascicolo React, `GuidaPraticaSidebar` legge il codice oggetto quando presente e chiama:

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
- stato operativo della guida.

Se il fascicolo non ha un codice oggetto valorizzato, il backend può proporre una scheda pratica dall'oggetto o dal titolo. La proposta è sempre facoltativa e non blocca il lavoro: per un deposito telematico resta necessario scegliere nella scheda fascicolo un codice PST/XSD ufficiale.

## Validazione

```bash
python scripts\merge_legal_kb_modules.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py -q --tb=short
```

La copertura ufficiale deve rimanere al 100%. Se un codice ufficiale entra nel catalogo senza guida curata, il validatore deve fallire e il modulo guida va completato prima del rilascio.

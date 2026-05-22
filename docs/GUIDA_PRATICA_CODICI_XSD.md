# Guida Pratica per codici XSD/PST - IUSENTRA

## Scopo

Quando l'avvocato apre un fascicolo, IUSENTRA legge il codice oggetto PST/XSD del fascicolo e mostra una guida operativa concreta:

- cosa verificare prima di procedere;
- quale atto principale redigere;
- campi obbligatori;
- allegati;
- avvertimenti di rito;
- adempimenti fiscali e telematici;
- riferimenti normativi;
- termini e possibili esiti.

La guida è una knowledge base separata dal codice applicativo. Il catalogo ufficiale PST/XSD resta la fonte del codice depositabile; le schede guida spiegano come lavorare sul fascicolo e non inventano codici ministeriali.

## Stato 2.248.10

- Catalogo ufficiale `pct/data/cataloghi/codici_oggetto_pst.json`: 1.018 record validi.
- Guide ufficiali curate: 1.018 su 1.018.
- Codici ufficiali senza guida curata: 0.
- Incoerenze tra guida e codice depositabile: 0.
- Schede interne o alias non depositabili: 36, mantenuti per continuità, ricerca e guida pratica facoltativa.

## File principali

```text
pct/data/legal_knowledge_base.full.json
pct/data/legal_knowledge_base.json
pct/data/legal_knowledge_base_modules/
pct/data/cataloghi/codici_oggetto_pst.json
pct/data/cataloghi/pst_xsd_sources.json
pct/guida_pratica/
web/services/react_guida_pratica_bridge.py
web/blueprints/api_v1_guida_pratica.py
frontend/src/guidaPraticaData.ts
frontend/src/components/GuidaPraticaSidebar.tsx
frontend/src/components/GuidaPraticaSidebar.css
scripts/merge_legal_kb_modules.py
scripts/curate_missing_guida_pratica_official_codes.py
scripts/validate_codici_oggetto_pst.py
scripts/validate_guida_pratica.py
scripts/export_guida_pratica_coverage.py
tests/test_guida_pratica_service.py
tests/test_guida_pratica_api.py
tests/test_pst_xsd_catalog_importer.py
```

## Endpoint

```text
GET  /api/v1/ui/guida-pratica/catalogo
GET  /api/v1/ui/guida-pratica/<codice>
POST /api/v1/ui/guida-pratica/<codice>/checklist
GET  /api/v1/ui/fascicoli/<id_fasc>/guida-pratica
```

Gli endpoint richiedono sessione o API key e almeno un permesso tra lettura fascicoli, telematico o AI.

## Integrazione fascicolo

Nel dettaglio fascicolo React il pannello `GuidaPraticaSidebar` usa il codice oggetto del fascicolo quando presente. Se il fascicolo non ha un codice valorizzato, prova a proporre una scheda pratica dall'oggetto o dal titolo del fascicolo, ma resta sempre un supporto facoltativo.

La guida mostra checklist, normativa, atto, adempimenti e avvertenze operative. Non blocca il lavoro dell'avvocato: se non è collegata, il fascicolo resta utilizzabile; se una scheda interna non coincide con un codice PST/XSD ufficiale, viene mantenuta come guida non depositabile e l'eventuale deposito deve usare un codice ministeriale scelto nella scheda fascicolo.

## Validazione obbligatoria

```bash
python scripts\validate_codici_oggetto_pst.py --min-records 1000
python scripts\verify_pst_xsd_catalog.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated --report artifacts\guida-pratica\guida-pratica-audit.json --missing-guidance-csv artifacts\guida-pratica\codici-ufficiali-senza-guida-curata.csv
python scripts\export_guida_pratica_coverage.py --format csv --output artifacts\guida-pratica\guida-pratica-coverage.csv
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py tests\test_import_pst_xsd_codici_oggetto.py tests\test_pst_xsd_catalog_importer.py tests\test_codici_oggetto_pst_catalog.py -q --tb=short
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
```

Il report finale della tranche è `artifacts/guida-pratica/IMPLEMENTATION_AUDIT.md`.

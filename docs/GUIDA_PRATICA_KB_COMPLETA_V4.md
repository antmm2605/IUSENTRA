# Guida Pratica KB completa v4 - IUSENTRA

## Stato consolidato 2.248.11

La v4 caricata dall'utente è stata applicata e completata sul catalogo ufficiale presente in repository, che contiene 1.018 record validi. I moduli TOP9 set2 parte 1 e parte 2 sono stati integrati mantenendo separati codici ufficiali e schede interne.

## Numeri finali

- Moduli KB caricati: 22.
- Codici unificati nel KB full: 1.054.
- Record ufficiali nel catalogo PST/XSD: 1.018.
- Guide ufficiali curate: 1.018.
- Codici ufficiali senza guida curata: 0.
- Copertura finale: `{"curata": 1054}`.
- Schede interne o alias non depositabili: 36.

## Cosa cambia rispetto alla v3

- I moduli caricati restano separati dal codice applicativo.
- Il modulo di completamento `kb_99_completamento_codici_ufficiali.json` porta i codici ufficiali mancanti o parziali allo stesso formato operativo della Guida Pratica.
- Gli alias storici `ESEC_*`, `LAV_*` e le vecchie varianti interne restano utilizzabili come guida interna, ma non sono codici depositabili.
- Il validatore ora distingue catalogo ufficiale, knowledge base e alias interni: un codice è depositabile solo se presente nel catalogo PST/XSD ufficiale.
- Il dettaglio fascicolo React mostra la guida come pannello operativo facoltativo: se il fascicolo non ha codice, può suggerire una scheda dall'oggetto senza bloccare il lavoro.
- Il badge `Uso facoltativo` resta visibile anche quando la scheda è collegata, così l'avvocato capisce che la guida aiuta ma non ferma il fascicolo.
- Lex conosce la Guida Pratica tramite `GuidaPraticaSource`: legge la scheda completa come fonte interna conversazionale per aiutare l'avvocato su primo controllo, atto, campi, allegati, avvertimenti e termini, senza confonderla con il codice di deposito.

## Regole operative confermate

1. I codici ufficiali di deposito vengono solo dal catalogo ministeriale PST/XSD caricato.
2. Ogni codice ufficiale deve avere guida curata prima del rilascio.
3. Gli alias interni non bloccano la consultazione, ma non possono essere usati come codice deposito.
4. La guida è supporto operativo per l'avvocato e deve restare dettagliata, leggibile e non tecnica.
5. Il validatore `--require-official-curated --fail-on-generated` è il gate obbligatorio.
6. Ogni nuova guida curata deve arricchire anche Lex: la conoscenza pratica va resa interrogabile in chat con tono conversazionale per l'avvocato.

## Comandi di controllo

```bash
python scripts\merge_legal_kb_modules.py
python scripts\validate_codici_oggetto_pst.py --min-records 1000
python scripts\verify_pst_xsd_catalog.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated --report artifacts\guida-pratica\guida-pratica-audit.json --missing-guidance-csv artifacts\guida-pratica\codici-ufficiali-senza-guida-curata.csv
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py tests\test_import_pst_xsd_codici_oggetto.py tests\test_pst_xsd_catalog_importer.py tests\test_codici_oggetto_pst_catalog.py -q --tb=short
python -m pytest lex\tests\unit\test_guida_pratica_source.py -q --tb=short
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
```

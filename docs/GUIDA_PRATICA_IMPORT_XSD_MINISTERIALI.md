# Guida Pratica - import codici oggetto dagli XSD ministeriali PST

## Obiettivo

`pct/data/cataloghi/codici_oggetto_pst.json` è il catalogo tecnico ufficiale usato per verificare se un codice può essere considerato depositabile. Non deve essere sostituito da alias interni o da schede guida.

## Stato corrente

Il catalogo caricato in repository è `2026-05-11.pst-xsd-official` e contiene 1.018 record validi. Le verifiche locali confermano:

- duplicati: 0;
- codici invalidi: 0;
- descrizioni mancanti: 0.

## Fonti configurate

Il manifest `pct/data/cataloghi/pst_xsd_sources.json` documenta i pacchetti PST/XSD usati per ricostruire il catalogo quando serve aggiornare la fonte ministeriale.

## Uso operativo

```bash
python scripts\update_pst_xsd_catalog.py --download
python scripts\validate_codici_oggetto_pst.py --min-records 1000
python scripts\verify_pst_xsd_catalog.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated
```

Se il server non ha accesso internet, scaricare manualmente gli ZIP dal PST e passare i file allo script di import.

## Regola prodotto

Il codice ministeriale serve per instradare pratica, busta e controlli di deposito. La Guida Pratica usa quel codice per spiegare all'avvocato cosa fare nel fascicolo, ma non promuove mai una scheda interna a codice ufficiale.

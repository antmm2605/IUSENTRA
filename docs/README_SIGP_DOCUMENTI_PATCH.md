# SIGP Sync - catalogo e file documenti

## Dove finiscono i documenti

Il flusso SIGP/PST usa due livelli separati:

- catalogo documenti: tabella SQLite `sigp_sync_documenti` dentro il database risolto da `SIGP_SYNC_DB_PATH` o da `data/sigp_sync/sigp_sync.db`;
- file scaricati o collegati: storage runtime `SIGP_SYNC_STORAGE_DIR` oppure `data/sigp_documents/sigp/<sigp_fascicolo_id>/`.

La UI `/sigp-sync/` legge prima il catalogo, poi abilita `Apri` solo quando il record ha `path_locale` valorizzato. Un documento presente nel catalogo ma non ancora salvato resta visibile, ma non viene dichiarato scaricato.

Il match non deduplica documenti che hanno stesso nome e stessa data ma ID portale diverso. Questo caso esiste nei cataloghi SIGP reali, ad esempio per piu' `comunicazione.txt` nella stessa giornata.

## Canale Local Signer

La patch non usa scraping HTML e non interroga il portale dal server cloud. Il server parla con il Local Signer locale sul PC dello studio.

Endpoint reali usati:

- `GET /ping`
- `POST /pst/documenti`
- `POST /pst/download-documento`

Il payload inviato per il download imposta sempre `original=false` salvo scelta esplicita futura, cosi' il comportamento predefinito resta la copia informatica/di consultazione del portale.

## Test anti-regressione

La copertura mirata e':

```bash
python -m pytest tests/test_sigp_sync.py tests/test_sigp_integration.py -q
python -m ruff check integrations/sigp_sync tests/test_sigp_sync.py
```

I test verificano un catalogo da 34 documenti, preview via Local Signer, download con `original=false`, salvataggio fisico, apertura del PDF dalla route UI e mancata deduplica di documenti con identificativi portale diversi.

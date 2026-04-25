# SIGP Sync - catalogo e file documenti

## Dove finiscono i documenti

Il flusso SIGP/PST usa due livelli separati:

- catalogo documenti: tabella SQLite `sigp_sync_documenti` dentro il database risolto da `SIGP_SYNC_DB_PATH` o da `data/sigp/sigp_sync.db`;
- file scaricati o collegati: storage runtime `SIGP_SYNC_STORAGE_DIR` oppure `data/sigp_documents/sigp/<sigp_fascicolo_id>/`.

La UI `/sigp-sync/` e' raggiungibile dal menu `PCT / Telematico -> SIGP - Giudice di Pace`, apre automaticamente il primo fascicolo importato e legge prima il catalogo. Il pulsante `Apri` e' abilitato solo quando il record ha `path_locale` valorizzato. Un documento presente nel catalogo ma non ancora salvato resta visibile, ma non viene dichiarato scaricato.

Il match non deduplica documenti che hanno stesso nome e stessa data ma ID portale diverso. Questo caso esiste nei cataloghi SIGP reali, ad esempio per piu' `comunicazione.txt` nella stessa giornata.

## Canale Local Signer

La patch non usa scraping HTML e non interroga il portale dal server cloud. In produzione Railway il browser dell'avvocato parla direttamente con il Local Signer locale sul PC dello studio (`127.0.0.1:27272`); il server riceve solo il catalogo normalizzato o il file gia' restituito dal Local Signer e lo salva nello storage runtime.

Endpoint reali usati:

- `GET /ping`
- `POST /pst/documenti`
- `POST /pst/download-documento`
- `POST /pst/download-documenti-batch`
- `POST /sigp-sync/api/.../salva-download-browser`

Il `pst_session_id` restituito dal Local Signer viene tenuto in `sessionStorage` per la sessione della pagina. Non vengono salvati PIN, username o password: chiudendo la sessione browser il riferimento viene perso.

Il payload inviato per il download imposta sempre `original=false` se il flag manca, cosi' il comportamento predefinito resta la copia informatica/di consultazione del portale con annotazioni ministeriali. Il duplicato senza coccarda richiede scelta esplicita tramite il pulsante `Scarica duplicato senza coccarda`, che passa `original=true` fino al Local Signer.

Il Local Signer `1.6.16` usa un timeout dedicato ai download reali PST/SIGP (`HACS_SIGNER_PST_DOWNLOAD_MAX_TIME`, default 300 secondi) invece del timeout SOAP leggero da 90 secondi, per evitare che `downloadAtto` venga interrotto mentre il portale prepara il file.

## Test anti-regressione

La copertura mirata e':

```bash
python -m pytest tests/test_sigp_sync.py tests/test_sigp_integration.py -q
python -m ruff check integrations/sigp_sync tests/test_sigp_sync.py
```

I test verificano un catalogo da 34 documenti, preview via Local Signer, pulsanti collegati al Local Signer del browser, download con `original=false`, scelta esplicita `original=true` per il duplicato, salvataggio fisico via `salva-download-browser`, apertura del PDF dalla route UI, riuso di `pst_session_id` dal payload raw/sessione e mancata deduplica di documenti con identificativi portale diversi.

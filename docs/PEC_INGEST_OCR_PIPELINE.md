# Pipeline PEC, analisi, OCR e risultati

Aggiornato: 24 maggio 2026.

Questa nota descrive il percorso compatto introdotto per portare una PEC da messaggio originale a risultato OCR indicizzabile, con catena di custodia, deduplica e messaggistica verificabile.

## Flusso operativo

1. `mail.security.av`: controllo antivirus inline sul MIME originale.
2. `mail.security.signature`: verifica strutturale degli allegati firmati `.p7m` prima di estrarre archivi.
3. `mail.ingest`: salvataggio write-once del MIME originale in `worm/YYYY/MM/DD/<mail_id>.eml`, checksum SHA-256 e metadati essenziali.
4. `mail.unzip`: enumerazione sicura degli allegati e degli archivi ZIP, profondità massima 3, soglia ZIP configurabile a 250 MB, whitelist estensioni/MIME e blocco di eseguibili o script.
5. `raw_blob.stored`: salvataggio dei membri validati come blob grezzi deduplicati per SHA-256.
6. `ocr.task`: scheduling OCR con small-first, FIFO per tenant/mittente sulle PEC ad alta priorità e retry exponential backoff.
7. `ocr.result`: risultato OCR con engine, pagine stimate, confidenza media, percentuale di bassa confidenza ed errori.
8. `document.indexed`: aggancio a ricerca/comunicazioni e candidato fascicolo quando si legge un R.G.
9. `lex.ingest.doc`: evento per Lex con citazioni, checksum e audit `run_id`.

Il modulo è `pct/pec_ocr_pipeline.py`; non sostituisce `pct/pec_pipeline.py`, ma lo affianca come orchestratore topic-first sopra i mattoni già presenti.

## Regole di sicurezza

- Il MIME originale viene scritto una sola volta: una seconda scrittura con checksum diverso solleva `WormViolation`.
- I log della pipeline sono append-only in SQLite, con trigger anti-update/anti-delete e hash chain per evento.
- I file ZIP sono aperti solo dopo antivirus e firma, con blocco di traversal, zip bomb, profondità e formati non ammessi.
- Gli ZIP bloccano anche membri cifrati, link simbolici e firme `.p7m` applicate a estensioni interne non ammesse; i percorsi interni restano virtuali e non diventano mai path filesystem.
- I membri duplicati per SHA-256 riusano il blob esistente e non generano un nuovo OCR.
- Gli allegati non sicuri o non leggibili generano `needs_attention`, senza assumere termini legali o validità processuale.
- Gli evidence pack espongono manifest, catena audit, catena hash e `hashes.sha256` senza `stored_uri` o path di storage; il download avviene solo da route backend autenticata.

## Scheduling

- File sotto 5 MB o sotto 5 pagine: `immediate`.
- File sopra 100 pagine: `batch_window`.
- PEC ad alta priorità: FIFO su mittente e tenant, concorrenza conservativa.
- Retry: 5 tentativi, backoff esponenziale, base 10 secondi.

## Test veritiero

Esecuzione mirata:

```powershell
python -m pytest tests\test_pec_ocr_pipeline.py -q --tb=short
```

Script reale di smoke:

```powershell
python scripts\test_pec_ocr_pipeline.py --runtime-root .tmp\pec-ocr-script-test
```

Lo script costruisce una PEC sintetica con ZIP, duplicato, `daticert.xml`, WORM, dedup, OCR e hook Lex; restituisce JSON e codice di uscita non zero se manca un passaggio essenziale.

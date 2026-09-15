# Registro delle letture

Aggiornato: 15/09/2026 (versione 2.316.0).

## Che cosa fa

Il gestionale legge i documenti e le PEC del fascicolo con più lettori: il testo
per la ricerca (OCR), l'indice documentale per Lex e il catalogo dal contenuto,
l'assistente locale (RAG), il presidio PEC sugli allegati, il presidio economico,
la proforma automatica, la lettura del fascicolo. Prima ognuno decideva da solo
se rileggere, e alcuni rileggevano sempre: l'indice documentale decifrava e
ricalcolava l'impronta di tutti i documenti a ogni apertura del fascicolo, la
proforma automatica rileggeva i PDF dal disco ogni quindici minuti.

Il registro delle letture (`pct/registro_letture/`) è la memoria comune:

- **inventario** degli oggetti del fascicolo — documenti, PEC collegate, allegati
  PEC — con impronta SHA-256 del contenuto, nome, dimensione, origine, data e le
  chiavi di associazione: nome e cognome del cliente, numero e anno di ruolo;
- **letture**: per ogni oggetto e per ogni lettore, l'impronta letta, la versione
  del lettore, lo stato (`letto`, `in_corso`, `errore`, `non_leggibile`), l'esito;
- **impronta del fascicolo** per lettore: se l'inventario è lo stesso dell'ultimo
  giro completo, il lettore non guarda nemmeno i documenti;
- **viste** per utente: che cosa è nuovo o cambiato dall'ultima apertura;
- **anomalie**: i dati letti che i controlli deterministici giudicano dubbi
  (date in primis), con motivo, gravità, valore proposto, stato
  (`aperta`, `confermata`, `corretta`, `ignorata`).

Un documento invariato non si rilegge. Cambia l'hash, si rilegge solo quello.
Cambia la versione di un lettore (nuovo motore OCR, nuovo risolutore del
catalogo), torna da leggere tutto per quel lettore soltanto.

## Dove sta

`REGISTRO_LETTURE_DB` = `/data/tenants/<studio>/intelligence/registro_letture.db`
(SQLite tenant-aware); PostgreSQL con `IUSENTRA_REGISTRO_LETTURE_DSN` o il
database del tenant. Schema gemello in `pct/sql/20260915_registro_letture.sql` e
`_postgres.sql` (tabelle `letture_oggetti`, `letture`, `letture_fascicoli`,
`letture_viste`, `letture_anomalie`; contratto verificato dal test).

## Chi lo usa

| Lettore | Dove consulta e scrive il registro |
| --- | --- |
| Testo e ricerca (OCR) | `web/services/ocr_runtime.py` rifiuta di accodare un documento già letto con la stessa impronta; `pct/ocr_worker.py` segna l'esito, estrae le date e registra le anomalie |
| Indice documentale | `pct/document_intelligence/sources.py` non decifra i documenti di cui il registro conosce l'impronta in chiaro; `web/services/document_intelligence_runtime.py` salta l'elaborazione se l'impronta del fascicolo è invariata e segna documenti e fascicolo |
| Catalogo dal contenuto | stato derivato dall'indice (stessa impronta) |
| Assistente locale (RAG) | `pct/local_ai.py` segna gli esiti (`indexed`, `skipped`, `unsupported`) tramite `service.registro_letture` |
| Presidio PEC | `pct/pec_pipeline.py` riusa l'OCR di un allegato con la stessa impronta già letto nello studio; il runtime allinea gli allegati letti e verifica udienze e termini rispetto alla PEC |
| Presidio economico | il marcatore `_presidio_documentale` è specchiato nel registro |
| Proforma automatica | `_ensure_auto_proforma_for_fascicolo` non rilegge i PDF se l'inventario è invariato |
| Lettura del fascicolo | cache breve invalidata da documenti e PEC (`web/services/lettura_cache.py`); pannello «Letture e verifiche» |

Eventi che aggiornano l'inventario: caricamento, sostituzione (editor),
ripristino, rinomina, cestino, eliminazione definitiva di un documento; PEC
collegata dalla lettura. Ogni evento invalida la lettura del fascicolo in cache.

## Verifica delle letture

`pct/registro_letture/verifica_date.py` giudica ogni data letta: calendario,
orizzonte del fascicolo (anno di ruolo, apertura), futuro oltre tre anni,
coerenza con un'altra fonte (data di deposito del portale, data di ricezione
della PEC), giorno e mese invertiti, lettere lette al posto delle cifre. Le
confusioni tipiche dell'OCR sono dichiarate una volta sola in
`legal_ocr/formulario/confusioni.py` e usate da date, cifre, codice fiscale,
partita IVA, CAP, IBAN, numero di ruolo e parole. Il presidio documentale
(`pct/fascicolo_document_presidio.py`) legge le date normalizzate e applica le
correzioni dell'avvocato; il runtime verifica le udienze e i termini letti dalle
PEC. Le anomalie compaiono nel pannello «Letture e verifiche» del fascicolo con
«È giusto», «Correggi», «Ignora».

## API

- `GET /api/v1/ui/fascicoli/<id>/letture` — stato per lettore e per oggetto,
  novità dall'ultima apertura (registra la vista), anomalie aperte.
- `POST /api/v1/ui/fascicoli/<id>/letture/aggiorna` — legge solo ciò che manca.
- `POST /api/v1/ui/fascicoli/<id>/letture/anomalie/<anomalia_id>` —
  `{"esito": "confermata|corretta|ignorata", "valore": "gg/mm/aaaa"}`.

Test: `tests/test_registro_letture.py`, `tests/test_registro_letture_runtime.py`,
`tests/js/letture_fascicolo.test.mjs`.

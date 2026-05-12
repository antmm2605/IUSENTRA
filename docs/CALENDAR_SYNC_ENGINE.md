# Calendar Sync Engine

## Architettura

IUSENTRA mantiene Agenda e Scadenziario come sorgente interna. Il nuovo motore
server-side `pct.calendar_sync_engine.CalendarSyncEngine` coordina provider,
account cifrati, calendari collegati, binding persistenti, conflitti e job di
allineamento.

Flusso:

1. Agenda / Scadenziario leggono e scrivono nei repository tenant-aware.
2. Il motore applica direzione, privacy e regole sulle scadenze.
3. Il provider esterno normalizza pull, push, update e delete.
4. I binding in `calendar_sync_engine.json` collegano record locali ed eventi
   esterni.
5. I conflitti in `calendar_conflicts.json` bloccano i casi non sicuri, senza
   last-write-wins cieco.

Il frontend React parla solo con gli endpoint Flask sotto
`/api/v1/ui/calendari/*`. Non gestisce token, password o chiamate dirette ai
servizi esterni.

## Moduli

- `pct/calendar_providers/base.py`: protocollo comune e normalizzazione eventi.
- `pct/calendar_providers/google.py`: Google Calendar API server-side.
- `pct/calendar_providers/microsoft.py`: Microsoft Graph Calendar API.
- `pct/calendar_providers/apple_caldav.py`: Apple/iCloud via CalDAV.
- `pct/calendar_providers/webcal.py`: adattatore WebCal/ICS sopra
  `pct.calendar_sync`.
- `pct/calendar_providers/demo.py`: provider locale persistente per prove end to
  end senza credenziali esterne.
- `pct/calendar_credentials.py`: cifratura credenziali con Fernet.
- `pct/calendar_bindings.py`: account, calendari collegati, binding e job.
- `pct/calendar_conflicts.py`: registro conflitti.
- `pct/calendar_sync_engine.py`: push, pull, sync account, retry e risoluzioni.

## Provider

### Google Calendar

Configura in produzione:

```bash
IUSENTRA_CALENDAR_CREDENTIALS_KEY=<chiave-fernet-o-segreto-lungo>
GOOGLE_CALENDAR_CLIENT_ID=<client-id>
GOOGLE_CALENDAR_CLIENT_SECRET=<client-secret>
GOOGLE_CALENDAR_REDIRECT_URI=https://app.iusentra.it/api/v1/ui/calendari/google/callback
```

Il provider supporta lista calendari, pull incrementale con sync token, push,
update, delete e predisposizione a notifiche push. Senza credenziali reali, il
collegamento live resta non attivo e i test end-to-end usano il provider locale.

### Microsoft / Outlook

Configura:

```bash
MICROSOFT_CALENDAR_CLIENT_ID=<client-id>
MICROSOFT_CALENDAR_CLIENT_SECRET=<client-secret>
MICROSOFT_CALENDAR_TENANT=common
MICROSOFT_CALENDAR_REDIRECT_URI=https://app.iusentra.it/api/v1/ui/calendari/microsoft/callback
```

Il provider usa Microsoft Graph, delta sync quando disponibile, `changeKey`,
push/update/delete e fallback polling.

### Apple iCloud / CalDAV

Configura l'account dalla UI Impostazioni con URL CalDAV, utente iCloud e
password per app. La password viene cifrata. Apple/iCloud usa polling CalDAV:
non viene promesso real-time perfetto.

### WebCal / ICS

Il provider WebCal riusa `pct.calendar_sync.GestioneCalendarSync`: conserva i
profili esistenti, importa UID RFC 5545 in modo idempotente e rileva eventi
rimossi nei full snapshot marcandoli come rimossi o da verificare.

### Provider locale persistente

`pct.calendar_providers.demo.DemoCalendarProvider` salva eventi remoti in JSON,
di default accanto al repository sync o in `data/demo_calendar/...` quando
usato direttamente. Supporta create/update/delete, cursor incrementale, etag,
change key e simulazione conflitti.

Comando demo:

```bash
python tools/demo_calendar_sync.py
```

La demo crea account, calendario, appuntamento, binding, aggiornamento remoto,
conflitto locale/remoto, scadenza perentoria protetta e verifica privacy
`busy_only`.

## Privacy Export

Livelli disponibili:

- `complete`: esporta titolo, descrizione, luogo e metadati professionali.
- `professional_reduced`: esporta impegni ridotti, senza cliente, controparte o
  note riservate.
- `busy_only`: esporta solo `Occupato`, orario e durata.

Default operativo: `professional_reduced`. Le note sensibili non escono nei
livelli ridotti.

## Conflitti

Il motore apre conflitti quando locale e remoto cambiano dopo l'ultimo binding,
oppure quando un calendario esterno cancella/sposta una scadenza perentoria.
Strategie disponibili:

- `use_local`: mantiene IUSENTRA e ripubblica fuori.
- `use_remote`: applica la versione esterna.
- `ignore`: chiude senza modificare.
- `merge_manual`: predisposta come risoluzione governata.

Le scadenze perentorie non vengono eliminate o spostate automaticamente.

## API

Endpoint principali:

- `GET /api/v1/ui/calendari/accounts`
- `POST /api/v1/ui/calendari/demo/connect`
- `POST /api/v1/ui/calendari/google/connect`
- `GET /api/v1/ui/calendari/google/callback`
- `POST /api/v1/ui/calendari/microsoft/connect`
- `GET /api/v1/ui/calendari/microsoft/callback`
- `POST /api/v1/ui/calendari/apple/connect`
- `POST /api/v1/ui/calendari/webcal/connect`
- `POST /api/v1/ui/calendari/accounts/<account_id>/sync`
- `POST /api/v1/ui/calendari/accounts/<account_id>/disconnect`
- `GET /api/v1/ui/calendari/conflicts`
- `POST /api/v1/ui/calendari/conflicts/<conflict_id>/resolve`

Webhook predisposti:

- `POST /api/v1/calendar/webhooks/google`
- `POST /api/v1/calendar/webhooks/microsoft`

Tutti gli endpoint UI richiedono sessione o API key, rispettano i permessi
impostazioni e non restituiscono credenziali.

## Scheduler

`pct/scheduler.py` conserva il job storico `calendar_sync_hourly` e aggiunge:

- `calendar_sync_engine_polling`: ogni 10 minuti per Google, Microsoft, Apple e
  provider locale.
- `calendar_sync_engine_webcal`: ogni ora circa per WebCal/ICS.
- `calendar_sync_engine_retry`: ogni 5 minuti per job in attesa.

In multi-tenant i path arrivano da `GestioneTenant.percorsi_dati`.

## Test

Comandi mirati:

```bash
python -m pytest tests/test_calendar_sync.py
python -m pytest tests/test_calendar_sync_engine.py
python -m pytest tests/test_calendar_credentials.py
python -m pytest tests/test_calendar_demo_provider.py
python -m pytest tests/test_calendar_api.py
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test
```

I test live Google/Microsoft/Apple vanno aggiunti solo in ambienti con
credenziali reali dedicate; la copertura end-to-end locale passa dal provider
persistente.

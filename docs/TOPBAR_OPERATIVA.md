# Top bar operativa React

La top bar desktop React e' il centro rapido trasversale della shell IUSENTRA. Usa solo dati reali letti da repository, sessione, API Flask o configurazione tenant; quando un dominio non ha dati disponibili espone stati vuoti, non esempi fittizi.

## Funzioni

- `Ctrl+K` / `Cmd+K`: apre la command palette con ricerca globale debounced, risultati raggruppati, frecce, `Enter` ed `Esc`.
- `+ Nuovo`: menu contestuale globale, fascicolo o cliente, con sole route applicative reali.
- `Oggi`: riepilogo compatto di udienze, scadenze, attivita, PEC importanti e urgenze entro 7 giorni.
- `Notifiche`: elementi operativi derivati da scadenze, udienze, PEC, depositi, documenti e fatture; supporta segna letta e segna tutte come lette.
- `Scadenze`: contatori oggi/domani/7 giorni/urgenti/scadute e lista rapida.
- `Recenti`: riusa il tracking sessione esistente ed evita duplicati.
- `Timer attivita`: persiste il timer lato backend e allo stop crea una voce timesheet reale.

## API

Tutte le API richiedono utente autenticato, applicano i permessi gia' disponibili sul profilo e restituiscono JSON con `ok`.

| Metodo | Route | Scopo |
| --- | --- | --- |
| `GET` | `/api/search/global?q=<query>&limit=<n>` | Ricerca fascicoli, clienti, pratiche, scadenze, udienze, documenti, attivita, comunicazioni e fatture indicizzate |
| `GET` | `/api/dashboard/today?date=YYYY-MM-DD` | Pannello Oggi con timezone `Europe/Rome` |
| `GET` | `/api/notifications` | Notifiche operative derivate dai repository |
| `PATCH` | `/api/notifications/<id>/read` | Marca una notifica letta nella sessione utente |
| `PATCH` | `/api/notifications/read-all` | Marca lette le notifiche correnti |
| `GET` | `/api/deadlines/quick-summary` | Riepilogo scadenze rapido |
| `GET` | `/api/recent` | Ultimi elementi aperti dalla sessione |
| `POST` | `/api/recent` | Registra un elemento recente reale `{ "entityType": "case|client|document|matter", "entityId": "..." }` |
| `GET` | `/api/time-tracking/active` | Timer attivo dell'utente |
| `POST` | `/api/time-tracking/start` | Avvio timer `{ "caseId": null, "clientId": null, "activityType": "call|drafting|research|hearing|meeting|email|filing|other", "description": null }` |
| `PATCH` | `/api/time-tracking/<id>/pause` | Pausa timer |
| `PATCH` | `/api/time-tracking/<id>/resume` | Riprende timer |
| `PATCH` | `/api/time-tracking/<id>/stop` | Ferma timer e crea timesheet |

## Payload principali

La ricerca restituisce `items[]` con `id`, `type`, `title`, `subtitle`, `description`, `href`, `priority` e `metadata`.

Le notifiche restituiscono `unreadCount` e `items[]` con `type`, `title`, `message`, `createdAt`, `priority`, `read`, `href` e `actionLabel`.

Il timer restituisce `timer` con `id`, `caseId`, `clientId`, `activityType`, `description`, `startedAt`, `pausedAt`, `endedAt`, `elapsedSeconds` e `status`.

## Storage

Il timer usa `GestioneTimeTracking` con JSON tenant-aware (`TIME_TRACKING_DB`, default `timesheet/time_tracking.json`) e schema governato SQLite/PostgreSQL in:

- `pct/sql/20260505_topbar_time_tracking.sql`
- `pct/sql/20260505_topbar_time_tracking_postgres.sql`

Il vincolo applicativo impedisce piu' timer running/paused per lo stesso utente; gli schemi SQL aggiungono anche indice unico parziale dove supportato.

## Limiti dichiarati

- `Nuova nota` non viene mostrata perche' nella shell non esiste ancora una route/procedura nota governata per note rapide globali.
- PEC, fatture, depositi e documenti entrano nei pannelli solo se i rispettivi repository espongono dati reali per l'utente corrente.

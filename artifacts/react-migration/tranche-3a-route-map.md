# Route map Tranche 3A

Data/ora: 2026-05-06T13:25:14+02:00

Nota operativa: `rg.exe` non e' eseguibile in questa sessione locale (`Accesso negato`), quindi la ricerca richiesta e' stata eseguita con `Select-String` su `web`, `pct` e `tests`.

## Pre-flight

- `git status --short`: presente baseline sporca runtime non correlata sotto `data/`, `backup/`, `intelligence`, `privacy`, `email`, `output`; non ripristinata e non usata per nascondere modifiche.
- `node scripts/react-migration/audit-react-migration.mjs`: eseguito, aggiornati `artifacts/react-migration/audit.md` e `route-inventory.json`.
- `python scripts/react-migration/capture-legacy-contracts.py /utenti /utenti/nuovo /profili /backup`: eseguito.
- Contratti presenti: `utenti.json`, `utenti__nuovo.json`, `profili.json`, `backup.json`.
- Prerequisiti Parte 2A verificati: `/statistiche`, `/audit`, `/registro-attivita` sono `react_full` e `unlockFromGate=true`; non sono piu' bloccate in `_LEGACY_OPERATIONAL_PREFIXES`; `App.tsx` contiene `StatistichePage` e `AuditPage`.

## /utenti

- Handler legacy: `web/bootstrap/auth_management_routes.py`
- Funzione: `lista_utenti`
- Template: `web/templates/auth/utenti.html`
- Repository/manager: `GestioneUtenti` tramite `_auth_manager()` / `get_utenti()`.
- Permessi richiesti: `utenti.leggi`; in multi-tenant il `SUPERADMIN` viene reindirizzato al pannello piattaforma.
- Form presenti: form POST eliminazione utente dentro la lista.
- POST presenti: non sulla route `/utenti`; la lista espone POST verso `/utenti/<id_utente>/elimina`.
- Action form: `/utenti/<id_utente>/elimina`.
- Method form: `POST`.
- CSRF: campo legacy `_csrf_token` presente nei form.
- Download/export: nessuno.
- Azioni distruttive: eliminazione utente via POST legacy.
- Esito 3A: sbloccabile solo come lista React e navigazione verso GET `/utenti/nuovo`; le modifiche, i permessi personalizzati e l'eliminazione restano sulle route legacy annidate con `?_legacy=1` o POST legacy.

## /utenti/nuovo

- Handler legacy: `web/bootstrap/auth_management_routes.py`
- Funzione: `nuovo_utente`
- Template: `web/templates/auth/form_utente.html`
- Repository/manager: `GestioneUtenti` tramite `_auth_manager()` / `get_utenti()`.
- Permessi richiesti: `utenti.scrivi`; in multi-tenant il `SUPERADMIN` viene reindirizzato al pannello piattaforma.
- Form presenti: form creazione utente.
- POST presenti: `POST /utenti/nuovo`.
- Action form: action implicita sullo stesso URL nel template legacy; React usa action esplicita `/utenti/nuovo`.
- Method form: `POST`.
- CSRF: campo legacy `_csrf_token`.
- Download/export: nessuno.
- Azioni distruttive: nessuna; crea utente e genera hash password lato legacy.
- Esito 3A: GET sbloccabile in React; il submit resta form HTML standard verso `POST /utenti/nuovo`, senza fetch POST e senza password nello state React.

## /profili

- Handler legacy: `web/bootstrap/auth_management_routes.py`
- Funzione: `profili`
- Template: `web/templates/auth/profili.html`
- Repository/manager: `GestioneUtenti`, `RuoloUtente`, `PERMESSI`, `TUTTI_PERMESSI`, `DESCRIZIONI_RUOLI`.
- Permessi richiesti: `utenti.leggi`; in multi-tenant il `SUPERADMIN` viene reindirizzato al pannello piattaforma.
- Form presenti: nessun form nella matrice profili.
- POST presenti: non sulla route `/profili`; le scritture permessi sono in `/utenti/<id_utente>/permessi`.
- Action form: non presenti in `/profili`; override gestiti da `/utenti/<id_utente>/permessi`.
- Method form: non applicabile.
- CSRF: la route `/profili` non ha form; gli override legacy usano `_csrf_token` in `web/templates/auth/permessi_utente.html`.
- Download/export: nessuno.
- Azioni distruttive: nessuna sulla route `/profili`; reset override possibile solo via POST legacy permessi utente.
- Esito 3A: sbloccabile come lettura matrice ruoli/permessi e come form standard opzionale verso POST legacy per ripristino override.

## /backup

- Handler legacy: `web/bootstrap/backup_routes.py`
- Funzione: `lista_backup`
- Template: `web/templates/backup/lista.html`
- Repository/manager: `GestioneBackup` tramite `get_backup()`.
- Permessi richiesti: nessun check esplicito nel route handler; dominio permessi disponibile come `backup.leggi` / `backup.esegui`.
- Form presenti: esecuzione backup, verifica integrita, eliminazione backup.
- POST presenti: `/backup/esegui`, `/backup/<id_bk>/verifica`, `/backup/<id_bk>/elimina`, `/backup/<id_bk>/ripristina`.
- Action form: route legacy elencate sopra.
- Method form: `POST`.
- CSRF: il template attuale non dichiara `_csrf_token` nei form backup.
- Download/export: `GET /backup/<id_bk>/scarica`.
- Azioni distruttive: eliminazione backup e ripristino dati.
- Esito 3A: non sbloccabile in questa PR. Viene preparato un bridge/API/pagina React read-only con banner operativo; il gate continua a servire la vista legacy per `/backup` e sottoroute.

# Tranche 14A - Audit specifico utenti

Generato: 2026-05-07

## Contract catturati

- `/utenti`: `artifacts/react-migration/legacy-contracts/utenti.json`
- `/utenti/nuovo`: `artifacts/react-migration/legacy-contracts/utenti__nuovo.json`
- Nota: la cattura senza sessione autenticata ha fotografato il redirect a `/login`; i dettagli operativi sotto sono stati verificati su sorgente Flask/template.

## Route legacy

| Route | Handler Flask | Template legacy | Permesso |
| --- | --- | --- | --- |
| `/utenti` | `web/bootstrap/auth_management_routes.py::lista_utenti` | `web/templates/auth/utenti.html` | `utenti.leggi` |
| `/utenti/nuovo` | `web/bootstrap/auth_management_routes.py::nuovo_utente` | `web/templates/auth/form_utente.html` | `utenti.scrivi` |
| `/utenti/<id_utente>/modifica` | `web/bootstrap/auth_management_routes.py::modifica_utente` | `web/templates/auth/form_utente.html` | `utenti.scrivi` |
| `/utenti/<id_utente>/elimina` | `web/bootstrap/auth_management_routes.py::elimina_utente` | POST legacy senza template dedicato | `utenti.elimina` |
| `/utenti/<id_utente>/permessi` | `web/bootstrap/auth_management_routes.py::permessi_utente` | `web/templates/auth/permessi_utente.html` | `utenti.scrivi` |

In runtime multi-tenant il ruolo `SUPERADMIN` viene reindirizzato al pannello piattaforma dedicato.

## POST legacy esistenti

- Creazione: `POST /utenti/nuovo`, campi `username`, `ruolo`, `nome_completo`, `email`, `password`, `_csrf_token`.
- Modifica profilo/ruolo/stato: `POST /utenti/<id_utente>/modifica`, campi `nome_completo`, `email`, `ruolo`, `attivo`, `password` opzionale, `_csrf_token`.
- Eliminazione: `POST /utenti/<id_utente>/elimina`, campo `_csrf_token`; il manager blocca eliminazione dell'unico amministratore attivo.
- Override permessi: `POST /utenti/<id_utente>/permessi`, campi `permessi_extra`, `permessi_negati`, `_csrf_token`.
- Reset credenziale: non esiste una route studio separata; il legacy lo supporta dentro `modifica_utente` con nuova credenziale temporanea. I pannelli admin tenant/piattaforma hanno route `reset-password` con credenziale fornita dall'operatore.

## Struttura dominio

- Modello: `pct.auth.Utente`.
- Campi pubblicabili in UI: `id`, `username`, `email`, `nome_completo`, `ruolo`, `attivo`, `must_change_password`, `creato_il`, `ultimo_accesso`, `permessi_extra`, `permessi_negati`, `tenant_slug`, `totp_attivato`.
- Campi esclusi dal payload React: `password_hash`, `reset_token`, `reset_token_scade`, `totp_secret`, token di sessione, API key.
- Ruoli gestibili nello studio: tutti i `RuoloUtente` escluso `SUPERADMIN`.
- Stato account legacy: booleano `attivo`.
- Audit legacy: `utenti.crea`, `utenti.modifica`, `utenti.elimina`, `utenti.aggiorna_permessi`.

## API gia presenti prima della tranche

- `GET /api/v1/ui/utenti`: bridge descrittivo/read-only o parziale.
- `POST /api/v1/ui/utenti/nuovo`: creazione JSON gia operativa dalla Parte 12A.
- Mancavano POST JSON per stato account, ruolo, reimpostazione credenziale e profilo minimo.

## Gap verso react_operational_full

- Il bridge dichiarava scritture `legacy_routes` sulla lista.
- La UI principale esponeva link di modifica/permessi legacy come azioni operative.
- Mancavano endpoint JSON per azioni principali su utenti esistenti.
- Mancava filtro client-side governato sulla lista.
- Mancavano stati di salvataggio per cambio ruolo, stato account, profilo e reimpostazione credenziale.
- Mancava un check tranche dedicato per impedire `LegacyPostForm`, CTA legacy primaria, storage browser e payload sensibili.

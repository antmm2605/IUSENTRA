# Tranche 2A - mappa route legacy

Generato: 2026-05-06 12:55 Europe/Rome

## /statistiche

- Handler legacy: `web/blueprints/statistiche.py`
- Funzione handler: `index`
- Template: `statistiche/index.html`
- Repository/manager usati: `get_agenda`, `get_clienti`, `get_fascicoli`, `get_fatturazione`, `get_scadenziario`
- Form presenti: nessun form di scrittura nella pagina principale
- POST presenti: nessun POST sotto `/statistiche`
- Download/export presenti: link GET legacy a export CSV/ICS (`/export/*.csv`, `/agenda/export.ics`, `/scadenziario/export.ics`)
- Permessi richiesti: utente autenticato (`g.utente_corrente`), senza permesso specifico ulteriore nel handler legacy
- Decisione Tranche 2A: sbloccabile. La pagina e le API legacy sono read-only e il bridge React puo' riusare gli stessi manager senza introdurre scritture.

## /audit

- Handler legacy: `web/bootstrap/auth_management_routes.py`
- Funzione handler: `audit_log`
- Template: `auth/audit.html`
- Repository/manager usati: `GestioneUtenti.audit_log`, `GestioneUtenti.tutti`, `build_audit_view`
- Form presenti: form GET di filtro per utente/azione
- POST presenti: nessun POST su `/audit`
- Download/export presenti: link GET `/audit/esporta.csv`
- Permessi richiesti: `audit.leggi`
- Decisione Tranche 2A: sbloccabile. La route mostra eventi reali e filtri GET; non richiede scritture non replicate.

## /registro-attivita

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione handler: `registro_attivita`
- Template: nessuno diretto; redirect GET verso `/audit`
- Repository/manager usati: stessi di `/audit` dopo redirect
- Form presenti: nessuno diretto
- POST presenti: nessun POST
- Download/export presenti: ereditati da `/audit`
- Permessi richiesti: ereditati da `/audit` (`audit.leggi`)
- Decisione Tranche 2A: sbloccabile. La route pubblica resta distinta, ma il payload React puo' condividere il bridge audit read-only.

## /utenti

- Handler legacy: `web/bootstrap/auth_management_routes.py`
- Funzione handler: `lista_utenti`
- Template: `auth/utenti.html`
- Repository/manager usati: `GestioneUtenti.tutti`, `GestioneUtenti.statistiche`
- Form presenti: form POST di eliminazione utente nella tabella e link a creazione/modifica/permessi
- POST presenti: `/utenti/nuovo`, `/utenti/<id_utente>/modifica`, `/utenti/<id_utente>/elimina`, `/utenti/<id_utente>/permessi`
- Download/export presenti: nessun download diretto rilevato nella lista
- Permessi richiesti: `utenti.leggi`; scritture collegate con `utenti.scrivi` e `utenti.elimina`
- Decisione Tranche 2A: non sbloccabile per vincolo esplicito. Resta nel gate legacy anche se parte della lista e' read-only.

## /profili

- Handler legacy: `web/bootstrap/auth_management_routes.py`
- Funzione handler: `profili`
- Template: `auth/profili.html`
- Repository/manager usati: `GestioneUtenti.per_ruolo`, `RuoloUtente`, `PERMESSI`, `TUTTI_PERMESSI`, `DESCRIZIONI_RUOLI`
- Form presenti: nessun form POST nella matrice, ma la superficie porta a override permessi utente
- POST presenti: collegati a `/utenti/<id_utente>/permessi`
- Download/export presenti: nessun download diretto rilevato
- Permessi richiesti: `utenti.leggi`; modifiche collegate con `utenti.scrivi`
- Decisione Tranche 2A: non sbloccabile per vincolo esplicito. Resta nel gate legacy fino a pagina dedicata con parita' RBAC.

## /backup

- Handler legacy: `web/bootstrap/backup_routes.py`
- Funzione handler: `lista_backup`
- Template: `backup/lista.html`
- Repository/manager usati: manager backup runtime (`get_backup`), `TipoBackup`, `StatoBackup`
- Form presenti: form POST per esecuzione, verifica, eliminazione e ripristino backup
- POST presenti: `/backup/esegui`, `/backup/<id_bk>/verifica`, `/backup/<id_bk>/elimina`, `/backup/<id_bk>/ripristina`
- Download/export presenti: GET `/backup/<id_bk>/scarica`
- Permessi richiesti: nessun controllo locale nel handler estratto; protezione generale di sessione/runtime applicativo
- Decisione Tranche 2A: non sbloccabile. Contiene scritture tecniche, download e restore, quindi resta nel gate legacy.

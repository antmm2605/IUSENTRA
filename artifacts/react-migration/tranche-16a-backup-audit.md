# Tranche 16A - Audit specifico Backup

Generato: 2026-05-07

## Comandi eseguiti

- `git status --short`
- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `python scripts/react-migration/capture-legacy-contracts.py /backup`

## Route legacy

- `/backup`
  - Handler Flask: `web/bootstrap/backup_routes.py::lista_backup`
  - Template legacy: `web/templates/backup/lista.html`
  - Stato pre-tranche: `react_bridge` con shell React exact e fallback `?_legacy=1`
- `/backup/esegui`
  - Handler Flask: `web/bootstrap/backup_routes.py::esegui_backup`
  - Metodo: `POST`
- `/backup/<id_bk>/verifica`
  - Handler Flask: `web/bootstrap/backup_routes.py::verifica_backup`
  - Metodo: `POST`
- `/backup/<id_bk>/scarica`
  - Handler Flask: `web/bootstrap/backup_routes.py::scarica_backup`
  - Metodo: `GET`, download backend con `send_file`
- `/backup/<id_bk>/ripristina`
  - Handler Flask: `web/bootstrap/backup_routes.py::ripristina_backup`
  - Template legacy: `web/templates/backup/ripristina.html`
  - Metodi: `GET`, `POST`
- `/backup/<id_bk>/elimina`
  - Handler Flask: `web/bootstrap/backup_routes.py::elimina_backup`
  - Metodo: `POST`

## Permessi richiesti

- Il bridge React preesistente dichiarava lettura con `backup.leggi` e azione esecuzione con `backup.esegui`.
- I route handler legacy non hanno decorator RBAC locali nel file `backup_routes.py`.
- La promozione 16A richiede controllo backend esplicito:
  - lettura API: `backup.leggi`
  - crea/verifica API: `backup.esegui`

## POST legacy e campi form

- `POST /backup/esegui`
  - `tipo`: `COMPLETO` o `INCREMENTALE`
  - `componenti`: lista fra `agenda`, `clienti`, `fascicoli`, `messaggi`, `documenti`
  - `nota`: testo opzionale
- `POST /backup/<id_bk>/verifica`
  - nessun campo dati, solo id route
- `POST /backup/<id_bk>/ripristina`
  - `destinazione`
  - `componenti`
  - `sovrascrivi`
  - credenziale archivio se copia cifrata
- `POST /backup/<id_bk>/elimina`
  - nessun campo dati, solo id route

## Struttura backup

Fonte: `pct/backup.py::RecordBackup`

- `id`
- `timestamp`
- `tipo`
- `stato`
- `percorso_file`
- `hash_file`
- `dimensione_bytes`
- `num_file`
- `componenti`
- `cifrato`
- `nota`
- `errore`
- `backup_base_id`

Per React operativo vengono esposti solo metadati sicuri: id, data, tipo, stato, nome file, dimensione, numero file, componenti, stato cifratura, nota, errore normalizzato e href download backend.

## Struttura lista copie

- Legacy legge `gb.tutti()` e `gb.statistiche()`.
- L'ordine e' decrescente per timestamp nel repository.
- La lista contiene copie `OK`, `FALLITO` e `CORROTTO`.

## Stato integrita

- Il repository espone `verifica_integrita(id_backup)`.
- La verifica confronta hash registrato e hash attuale.
- Il risultato legacy non e' persistito come storico separato; se la verifica fallisce, lo stato record diventa `CORROTTO`.
- Il payload React espone uno stato sintetico reale derivato da registro e risultato dell'ultima mutazione JSON.

## Azioni legacy

- Crea backup: supportata da `GestioneBackup.esegui_backup`.
- Verifica integrita: supportata da `GestioneBackup.verifica_integrita`.
- Download: supportato da route backend `GET /backup/<id_bk>/scarica`.
- Restore/ripristino: supportato dal legacy ma non migrato in React 16A.
- Elimina: supportato dal legacy ma non migrato in React 16A.

## Audit legacy

- `backup_routes.py` non registra audit esplicito per crea/verifica/restore/delete.
- La tranche 16A registra audit applicativo per le nuove API JSON `backup.crea` e `backup.verifica`, senza includere percorsi file o dati sensibili nei dettagli.

## API gia esistenti

- `GET /api/backup/statistiche`: endpoint legacy statistiche.
- `GET /api/v1/ui/backup`: bridge React descrittivo preesistente, con `writes: legacy_routes`.
- Prima della 16A non erano presenti POST JSON sotto `/api/v1/ui/backup`.

## Gap pre-conversione

- `BackupPage` usava `LegacyPostForm` per azioni principali.
- Il bridge dichiarava `writes: legacy_routes`.
- Mancavano endpoint JSON per creazione e verifica.
- La UI mostrava CTA primaria verso `?_legacy=1`.
- Restore/delete erano visibili come azioni operative legacy nella lista React.
- Il payload non dichiarava `operational: true` ne `restore_migrated: false`.
- La UI non gestiva workflow JSON con stati `saving/success/error` sulle mutazioni backup.

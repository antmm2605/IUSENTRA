# Audit operativo migrazione React

Data: 2026-05-01

## Criterio di accettazione

Una route non viene considerata migrata solo perche' apre la shell React. Per
essere dichiarata operativa deve avere:

- UI React basata sui token e sui componenti condivisi;
- route GET reale servita senza 404/500;
- API o repository reali per leggere i dati applicativi;
- form o azioni collegati a route operative esistenti, non a link fittizi;
- test di regressione su route, API e card;
- nessun link visibile verso `?_legacy=1`.

## Verticale chiusa in questa tranche

### Portali telematici: acquisizione guidata

La route `/portali/<portale>/acquisizione` ora resta nella shell React e mostra
un wizard operativo per PST, PDP, PAT e PTT.

Il wizard React chiama gli endpoint Flask gia' presenti:

- `GET /api/portali/<portale>/acquisizione/status`
- `POST /api/portali/<portale>/acquisizione/search`
- `POST /api/portali/<portale>/acquisizione/preview`
- `POST /api/portali/<portale>/acquisizione/analyze`
- `POST /api/portali/<portale>/acquisizione/import`
- `POST /api/portali/<portale>/acquisizione/importa-payload`

La UI non promette scraping o download autonomo dai portali. L'acquisizione
usa file selezionati dall'utente, payload autorizzati o Local Signer quando
disponibile. Per PST resta esplicito il default della copia di consultazione.

### Preventivi e conferimenti

Il runtime React del modulo `Preventivi e Incarichi` ora gestisce anche route
profonde come:

`/preventivi/conferimento/nuovo/<id_cliente>?id_preventivo=<id>&from_page=preventivo`

Il form React precompila:

- cliente;
- fascicolo;
- preventivo collegato;
- oggetto incarico;
- avvocato referente;
- numero iscrizione albo;
- Ordine degli Avvocati.

Le scritture restano sul POST operativo `/preventivi/conferimento/nuovo`.

### Timesheet

Il runtime React del modulo Timesheet espone form reale verso
`POST /timesheet/nuovo`, con cliente, fascicolo, minuti, valore orario e
fatturabilita'.

### Firma documento fascicolo

La route profonda `/fascicoli/<id>/documenti/<id_doc>/firma` apre la UI React
operativa invece di restituire `405 Method Not Allowed`.

Il flusso React espone:

- stato documento e verifica firme da `/api/fascicoli/<id>/documenti/<id_doc>/info-firma`;
- anteprima e download del documento;
- firma tramite Local Signer sul PC dell'avvocato (`127.0.0.1:27272`);
- caricamento manuale del file firmato verso `POST /fascicoli/<id>/documenti/<id_doc>/firma`;
- avviso forte se il documento risulta gia' firmato.

Il pannello Local Signer distingue il servizio raggiungibile dal token PKCS#11:
se `token[]` e' vuoto ma il ping espone `token_probe_fresh[]`, la UI mostra
che il token e' stato rilevato dal probe fresco e propone il riavvio del
Local Signer, invece di degradare a "Local Signer non rilevato".

La rifirma non e' consentita in modo silenzioso: se il documento e' gia'
firmato, frontend e backend richiedono conferma esplicita `confirm_resign=1`.

### Amministrazione database

La route `/admin/database` ora apre una pagina React operativa con payload
reale da `GET /api/v1/ui/admin/database`.

La pagina React legge statistiche, moduli monitorati, snapshot SQLite e analisi
uso dal runtime database esistente. Le azioni restano sulle route Flask gia'
protette da sessione, permessi e audit:

- `GET /admin/database/verifica`
- `POST /admin/database/ottimizza`
- `POST /admin/database/migra`
- `POST /admin/database/attiva-sqlite`
- `GET /admin/database/export`

La shell React usa il profilo reale di sessione per nome, username, ruolo e
iniziali. Se un dato non arriva dal profilo, repository, API o configurazione
reale, non viene mostrato come dato applicativo.

## Gate anti-regressione aggiunti

Sono stati aggiunti test per impedire regressioni su:

- endpoint del wizard portale raggiungibili e JSON;
- card Studio con href interni raggiungibili senza 404/500;
- route profonde Preventivi/Conferimento con prefill da query e path;
- supporto frontend a campi `hidden`, `checkbox`, `file` ed `enctype`;
- passaggio di `path` e query string dal client React al bridge runtime.
- deep-link firma documento, Local Signer locale, upload manuale e guardia
  anti-rifirma con conferma esplicita.
- `/admin/database` React, payload reale, azioni database operative, profilo
  utente da sessione e assenza di dati inventati in sidebar, notifiche e
  recenti.

## Comandi di verifica

```bash
cd D:\legale\IUSENTRA\frontend
npm run test
npm run typecheck
npm run build

cd D:\legale\IUSENTRA
python -m pytest tests/test_react_shell.py -q
python -m pytest tests/test_web_bootstrap.py -q
```

## Nota di metodo

La migrazione completa deve proseguire con la stessa regola: pagina per pagina,
card per card, nessuna card decorativa, nessun link fittizio, nessuna route
React dichiarata completa se il relativo flusso operativo non esegue davvero
API, form, repository o download previsti.

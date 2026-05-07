# Tranche 20A - Audit archivio preventivi

Generato: 2026-05-07

## Route legacy
- Route pubblica: `/preventivi`.
- Handler Flask legacy: `web/blueprints/preventivi.py`, funzione `lista_preventivi`.
- Template legacy: `web/templates/preventivi/lista.html`.
- Contratto catturato: `artifacts/react-migration/legacy-contracts/preventivi.json`.

## Dati e azioni legacy
- Campi elenco: numero, cliente, fascicolo, oggetto, importo backend, data emissione/scadenza, stato.
- Conferimenti collegati: letti da `GestionePreventivi.tutti_conferimenti`.
- Azioni stato legacy: `cambia_stato_preventivo` supportata e convertita in POST JSON.
- Archivia/annulla/duplica: non esposte come endpoint finti; flags disabilitati se non supportati dal legacy.
- Link PDF/DOCX/download/export e workflow avanzati: restano backend/legacy.

## Permessi, audit e API
- Lettura con `fatturazione.leggi`; scrittura stato con `fatturazione.scrivi`.
- Audit legacy dedicato non rilevato; la tranche registra `preventivi.stato` quando il manager audit e' disponibile.
- API preesistenti: GET bridge read-only.
- Gap chiusi: GET archivio, GET dettaglio sintetico, POST stato, KPI backend, ricerca locale su dati ricevuti.

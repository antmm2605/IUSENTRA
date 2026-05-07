# Tranche 21A - Audit archivio fatturazione

Generato: 2026-05-07

## Route legacy
- Route pubblica: `/fatturazione`.
- Handler Flask legacy: `web/blueprints/fatturazione.py`, funzione archivio/lista fatturazione.
- Template legacy: `web/templates/fatturazione/lista.html`.
- Contratto catturato: `artifacts/react-migration/legacy-contracts/fatturazione.json`.

## Dati e azioni legacy
- Campi elenco: numero documento, cliente, fascicolo, importo backend, data emissione/scadenza, stato pagamento, metodo pagamento.
- KPI economici: `GestioneFatturazione.statistiche`.
- Azioni supportate: cambio stato, annulla, segna pagata tramite `GestioneFatturazione.cambia_stato`.
- Archiviazione separata: non rilevata come semantica legacy distinta, quindi disabilitata.
- PDF/XML/export/download: restano link backend, senza fetch blob React.

## Permessi, audit e API
- Lettura con `fatturazione.leggi`; scrittura con `fatturazione.scrivi`.
- Audit legacy dedicato non rilevato; la tranche registra `fatturazione.stato` quando il manager audit e' disponibile.
- API preesistenti: GET bridge archivio.
- Gap chiusi: GET archivio operativo, GET dettaglio sintetico, POST stato/annulla/segna-pagata, ricerca locale, UI state completa.

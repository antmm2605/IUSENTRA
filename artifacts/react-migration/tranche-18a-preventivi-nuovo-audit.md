# Tranche 18A - Audit preventivi/nuovo

Generato: 2026-05-07

## Route legacy
- Route pubblica: `/preventivi/nuovo`.
- Handler Flask legacy: `web/blueprints/preventivi.py`, funzione `nuovo_preventivo`.
- Template legacy: `web/templates/preventivi/nuovo.html`.
- Contratto catturato: `artifacts/react-migration/legacy-contracts/preventivi__nuovo.json`.

## Permessi e POST legacy
- Accesso legacy protetto da login/sessione Flask.
- La superficie React usa permessi economici esistenti: `fatturazione.leggi` per lettura e `fatturazione.scrivi` per creazione.
- POST legacy esistente: creazione preventivo via `GestionePreventivi.crea_preventivo`.

## Campi e struttura
- Campi form: cliente, fascicolo, oggetto, data emissione, data scadenza, tipo compenso, tipo procedimento, valore controversia, complessita, note.
- Voci preventivo: descrizione, tipo voce, importo.
- Opzioni fiscali/forensi: cassa, IVA, ritenuta come input; risultati canonici backend.
- Clienti e fascicoli collegabili: letti da `get_clienti()` e `get_fascicoli()`.

## Calcoli e documenti
- Calcoli legacy presenti nel dominio `pct/preventivi.py`: imponibile, cassa, IVA, totale e parametri del preventivo.
- Generazione documenti e workflow avanzati restano nei percorsi Flask legacy.
- Il frontend non deve calcolare compensi, fiscalita' o documenti.

## Audit e API
- Il legacy non esponeva un audit centralizzato dedicato in questa route; la tranche React registra evento `preventivi.crea` quando il manager audit e' disponibile.
- API preesistenti: GET bridge React read-only.
- Gap chiusi: POST JSON, permessi backend, rifiuto importi canonici frontend, UI operativa, stati loading/saving/success/error.

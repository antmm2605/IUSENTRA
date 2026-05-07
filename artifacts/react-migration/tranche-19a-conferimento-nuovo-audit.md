# Tranche 19A - Audit conferimento/nuovo

Generato: 2026-05-07

## Route legacy
- Route pubblica: `/preventivi/conferimento/nuovo`.
- Handler Flask legacy: `web/blueprints/preventivi.py`, funzione `nuovo_conferimento`.
- Template legacy: `web/templates/preventivi/conferimento_nuovo.html`.
- Contratto catturato: `artifacts/react-migration/legacy-contracts/preventivi__conferimento__nuovo.json`.

## Permessi e POST legacy
- Accesso legacy protetto da login/sessione Flask.
- La superficie React usa `fatturazione.leggi` per lettura e `fatturazione.scrivi` per creazione.
- POST legacy esistente: creazione conferimento via `GestionePreventivi.crea_conferimento`.

## Campi e collegamenti
- Campi form: cliente, fascicolo, preventivo collegato, oggetto, avvocato referente, dati albo/ordine, data incarico, tipo compenso, tipo procedimento, compenso pattuito, informative, note.
- Collegamento cliente/fascicolo/preventivo: letto da repository reali.
- Prefill da `id_preventivo`: gestito dal bridge backend.
- Dati studio sicuri: solo campi gia' esposti come referente/albo/ordine, nessun segreto.

## Clausole e documenti
- Clausole/informative: informativa art. 13 e clausola ADR.
- Apertura fascicolo guidata: non automatizzata in React; resta workflow backend/legacy.
- Generazione PDF/DOCX, mandato e firme: non introdotte nel frontend.

## Audit e API
- Il legacy non esponeva un audit centralizzato dedicato in questa route; la tranche React registra evento `preventivi.conferimento.crea` quando disponibile.
- API preesistenti: GET bridge React read-only.
- Gap chiusi: POST JSON, permessi backend, prefill, validazione, UI operativa e rollback tecnico.

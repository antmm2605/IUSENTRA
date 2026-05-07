# Tranche 18A - Preventivi nuovo operational report

- Route convertita: `/preventivi/nuovo`.
- Stato prima: `react_bridge`.
- Stato dopo: `react_operational_full`.
- LegacyPostForm rimossi: il flusso principale usa form React controllato e `createPreventivo`.
- Link legacy rimasti: solo `Rollback tecnico` verso `/preventivi/nuovo?_legacy=1`.
- Endpoint JSON creati: `GET /api/v1/ui/preventivi/nuovo`, `POST /api/v1/ui/preventivi/nuovo`.
- Permessi controllati: lettura `fatturazione.leggi`, creazione `fatturazione.scrivi`.
- Audit preservato/migliorato: evento `preventivi.crea` quando disponibile.
- UI state implementati: loading, saving, success, validation, permission, error, empty state.
- Calcolo backend preservato: React invia voci e opzioni, non totali canonici.
- DM55 backend preservato: parametri forensi non calcolati nel frontend.
- PDF/DOCX React: non introdotti.
- Test eseguiti: statici tranche 18A, typecheck frontend, build da validare in fase finale.
- Rischi residui: test Flask autenticato non eseguito da questo script statico.
- Rollback: `/preventivi/nuovo?_legacy=1`.

# Tranche 20A - Archivio preventivi operational report

- Route convertita: `/preventivi`.
- Stato prima: `react_bridge`.
- Stato dopo: `react_operational_full`.
- LegacyPostForm rimossi: nessun form legacy nel flusso principale.
- Link legacy rimasti: solo `Rollback tecnico` verso `/preventivi?_legacy=1`; subpath dettaglio restano backend.
- Endpoint JSON creati: `GET /api/v1/ui/preventivi`, `GET /api/v1/ui/preventivi/<id_preventivo>`, `POST /api/v1/ui/preventivi/<id_preventivo>/stato`.
- Permessi controllati: lettura `fatturazione.leggi`, scrittura `fatturazione.scrivi`.
- Audit preservato/migliorato: evento `preventivi.stato` quando disponibile.
- UI state implementati: loading, saving, success, validation, permission, error, empty state.
- Dettaglio sintetico JSON: implementato per preventivi.
- Azioni stato JSON supportate: cambio stato preventivo; archivia/annulla/duplica disabilitate se non supportate dal legacy.
- Calcolo backend preservato: importi mostrati arrivano dal backend.
- PDF/DOCX backend/legacy preservati: nessuna generazione React.
- Test eseguiti: statici tranche 20A, typecheck frontend, build da validare in fase finale.
- Rischi residui: test Flask autenticato non eseguito da questo script statico.
- Rollback: `/preventivi?_legacy=1`.

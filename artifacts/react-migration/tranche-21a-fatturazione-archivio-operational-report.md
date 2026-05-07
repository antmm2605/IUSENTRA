# Tranche 21A - Archivio fatturazione operational report

- Route convertita: `/fatturazione`.
- Stato prima: `react_bridge`.
- Stato dopo: `react_operational_full`.
- LegacyPostForm rimossi: nessun form legacy nel flusso principale.
- Link legacy rimasti: solo `Rollback tecnico` verso `/fatturazione?_legacy=1`; PDF/XML/export restano link backend diretti.
- Endpoint JSON creati: `GET /api/v1/ui/fatturazione`, `GET /api/v1/ui/fatturazione/<id_documento>`, `POST /api/v1/ui/fatturazione/<id_documento>/stato`, `POST /api/v1/ui/fatturazione/<id_documento>/annulla`, `POST /api/v1/ui/fatturazione/<id_documento>/segna-pagata`.
- Permessi controllati: lettura `fatturazione.leggi`, scrittura `fatturazione.scrivi`.
- Audit preservato/migliorato: evento `fatturazione.stato` quando disponibile.
- UI state implementati: loading, saving, success, validation, permission, error, empty state.
- Dettaglio sintetico JSON: implementato.
- Azioni stato JSON supportate: cambio stato, annulla, segna pagata; archiviazione separata disabilitata.
- Calcolo fiscale backend preservato: importi e fiscali canonici non calcolati in React.
- PDF/XML/export backend/legacy preservati: nessun fetch blob o generazione React.
- Test eseguiti: statici tranche 21A, typecheck frontend, build da validare in fase finale.
- Rischi residui: test Flask autenticato non eseguito da questo script statico.
- Rollback: `/fatturazione?_legacy=1`.

# Tranche 19A - Conferimento nuovo operational report

- Route convertita: `/preventivi/conferimento/nuovo`.
- Stato prima: `react_bridge`.
- Stato dopo: `react_operational_full`.
- LegacyPostForm rimossi: il flusso principale usa form React controllato e `createConferimento`.
- Link legacy rimasti: solo `Rollback tecnico` verso `/preventivi/conferimento/nuovo?_legacy=1`.
- Endpoint JSON creati: `GET /api/v1/ui/preventivi/conferimento/nuovo`, `POST /api/v1/ui/preventivi/conferimento/nuovo`.
- Permessi controllati: lettura `fatturazione.leggi`, creazione `fatturazione.scrivi`.
- Audit preservato/migliorato: evento `preventivi.conferimento.crea` quando disponibile.
- UI state implementati: loading, saving, success, validation, permission, error, empty state.
- Prefill da preventivo: backend bridge usa `id_preventivo` per cliente/fascicolo/oggetto/importo backend.
- Persistenza backend preservata: `GestionePreventivi.crea_conferimento`.
- Generazione documento backend/legacy preservata: nessun mandato/PDF/DOCX frontend.
- Apertura fascicolo lato frontend: non introdotta.
- Test eseguiti: statici tranche 19A, typecheck frontend, build da validare in fase finale.
- Rischi residui: test Flask autenticato non eseguito da questo script statico.
- Rollback: `/preventivi/conferimento/nuovo?_legacy=1`.

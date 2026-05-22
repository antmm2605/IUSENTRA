# Audit preset sequenza IUSENTRA

Aggiornato: 22 maggio 2026, versione 2.248.13.

## Esito

Passato. Il preset globale non si limita più alla griglia: impone la sequenza pagina canonica su tutte le rotte React operative, con esclusione esplicita di `/sito-studio/builder`.

## Sequenza governata

1. Header pagina
2. Sottotitolo operativo
3. Azioni principali
4. Filtri
5. Contesto filtri / riepilogo
6. Contenuto principale
7. Paginazione / footer
8. Sidebar di supporto

Gli slot sono centralizzati in `IUSENTRA_PAGE_SEQUENCE` e applicati da `IusentraRoutePresetFrame` tramite `data-iusentra-sequence-slot`.
Gli slot dichiarati direttamente dai componenti React vengono preservati: la normalizzazione globale aggiunge solo classificazione e ordine, senza cancellare `DataSurface`, `SupportRail`, sottotitolo e azioni già marcati.

## Perimetro

- Frame globale: `frontend/src/components/iusentra/IusentraPreset.tsx`
- Export componenti: `frontend/src/components/iusentra/index.ts`
- Header e sottotitolo: `frontend/src/components/iusentra/IusSectionHeader.tsx`
- CSS ordine e responsive: `frontend/src/styles/iusentra-design-system.css`
- Ingresso globale: `frontend/src/App.tsx`
- Gate statico: `scripts/react-migration/audit-ui-preset-sequence.mjs`
- Contratti frontend: `frontend/scripts/check-react-contracts.mjs`
- Test Flask/React: `tests/test_react_shell.py`
- Documentazione: `docs/UI_PRESET_IUSENTRA.md`, `docs/UI_DESIGN_SYSTEM.md`

## Regole verificate

- `/sito-studio/builder` resta esclusa dal preset.
- Tutte le altre rotte React restano avvolte da `IusentraRoutePresetFrame`.
- Header e sottotitolo vengono marcati come parti della sequenza.
- Header, sottotitolo e azioni principali sono anche slot verificabili nel DOM.
- Le azioni principali hanno ordine prima dei filtri.
- I filtri hanno ordine prima del contesto.
- Il contenuto principale segue il contesto.
- La paginazione/footer segue il contenuto.
- La sidebar resta supporto e in flusso mobile arriva dopo il contenuto.

## Gate eseguiti

- `pnpm --filter @iusentra/studio typecheck`: OK
- `node scripts/react-migration/audit-ui-preset-sequence.mjs`: OK, 8/8 slot governati
- `node frontend/scripts/check-react-contracts.mjs`: OK
- `pnpm --filter @iusentra/studio test`: OK
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_usa_preset_grafico_globale -q --tb=short`: OK
- `python tools/sync_packaging_files.py --check`: OK
- `python scripts/react-migration/generate_api_contracts.py --check`: OK
- `python scripts/validate_openapi.py docs/openapi.yaml`: OK
- `python scripts/verify_openapi_provider.py`: OK
- Browser reale Chrome headless Docker locale: OK, 27/27 controlli desktop 1440, tablet 1024 e mobile 390 su `/fascicoli`, `/agenda`, `/scadenziario`, `/clienti`, `/soggetti`, `/email/`, `/deposito/checklist`, `/admin/database` e `/sito-studio/builder`
- `pnpm --filter @iusentra/studio build`: OK
- `docker compose build --no-cache`, `docker compose up -d --force-recreate`, `docker compose ps`, `/api/pronto`, versione container: OK, runtime `2.248.13`

## Nota di rischio residuo

Il preset ora governa la sequenza delle strutture React operative tramite frame globale e classi/attributi riconosciuti. Una pagina futura con classi completamente nuove deve usare le primitive `Iusentra*` oppure aggiungere il selettore al classificatore, altrimenti il gate statico deve essere aggiornato nello stesso commit.

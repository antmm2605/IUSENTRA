# Tema professionale condiviso, 18 maggio 2026

## Scopo

È stato introdotto un layer visuale condiviso per rendere più coerenti shell, sidebar, topbar, card, pannelli, bottoni, form, tabelle, badge e stati applicativi senza riscrivere le singole pagine React e senza modificare route, API, permessi, audit, storage tenant-aware o logica backend.

File principale:

- `frontend/src/theme/professional-foundation.css`

## Regole applicate

- Palette istituzionale sobria: superfici chiare, navigazione blu notte, accento oro tenue.
- Raggio massimo 8px per card, pannelli e controlli operativi.
- Ombre leggere, niente gradienti decorativi, niente glassmorphism, niente card giganti.
- Tipografia stabile, senza scaling legato alla viewport e senza letter spacing negativo.
- Intervento trasversale tramite CSS condiviso, non refactor pagina per pagina.

## Verifiche eseguite

- `pnpm --filter @iusentra/studio typecheck`: OK.
- `pnpm --filter @iusentra/studio test`: OK.
- `pnpm --filter @iusentra/studio build`: OK.
- `git diff --check -- docs/UI_DESIGN_SYSTEM.md frontend/src/main.tsx frontend/src/theme/professional-foundation.css`: OK.
- `python -m pct.cli utf8-integrity --root docs\UI_DESIGN_SYSTEM.md --check-only --json --report %TEMP%\iusentra-ui-design-system-utf8-report.json`: OK.

## Verifica browser

Build Vite servita localmente da preview e verificata con Chromium/Chrome headless su:

- Panoramica.
- Fascicoli.
- Impostazioni.
- Ricerca Legale.

Viewport controllate:

- Desktop 1366x900.
- Tablet 834x1112.
- Mobile 390x844.

Esito:

- shell React presente;
- nessun errore pagina;
- nessun overflow orizzontale;
- nessun testo tecnico vietato visibile nel rendering controllato.

## Note

Gli asset generati sotto `web/static/react` non sono stati committati: Docker e Railway ricompilano il bundle React nello stage `frontend-builder`, evitando drift tra sorgenti e artefatti compilati.

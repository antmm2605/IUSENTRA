# Full React final report

Generato: 2026-05-08T10:03:02.066Z

Tranche architetturale: audit, manifest workspaceTarget, client API, shell/app/features, primitive UI e gate. Non dichiarare completata la migrazione totale per timeout pytest e route ancora legacy/bridge.

## Test

- python -m pytest -q: timeout - Interrotto dal timeout locale dopo circa 45 minuti; nessun verde completo dichiarabile.
- npm test: passed - Contratti React verificati.
- npm run typecheck: passed - tsc --noEmit completato.
- npm run build: passed - Vite build completata; asset generati in web/static/react.
- node scripts/react-migration/run-full-react-migration.mjs: passed - Audit, anti-mascheramento e check Full React passati.
- node scripts/react-migration/run-legal-ui-checks.mjs: passed - Check UI legale, responsive e anti-Bootstrap passati.

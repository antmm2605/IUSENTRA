# Tranche 4A - report finale

Data/ora: 2026-05-06 14:35 Europe/Rome

Branch base: `claude/legal-electronic-filing-kIxcV`

## Route migrate

- `/backup` React full su GET, con operazioni tecniche conservate sui percorsi legacy.
- `/sito-studio` React full su GET, con builder e pubblicazione avanzata legacy.
- `/sito-studio/contatti` React full su GET, con conversione contatti e gestione prenotazioni via form legacy.

## Route preparate ma lasciate legacy

- `/studio`
- `/impostazioni`
- `/sito-studio/builder`

## File creati

- `web/services/react_sito_studio_bridge.py`
- `frontend/src/sitoStudioData.ts`
- `frontend/src/components/SitoStudioPage.tsx`
- `frontend/src/components/SitoStudioPage.css`
- `scripts/react-migration/check-tranche-4a-gate.py`
- `scripts/react-migration/check-tranche-4a-secrets.mjs`
- `artifacts/react-migration/tranche-4a-route-map.md`
- `artifacts/react-migration/tranche-4a-gate.md`
- `artifacts/react-migration/tranche-4a-secrets.md`
- `artifacts/react-migration/tranche-4a-report.md`
- `artifacts/react-migration/patches/tranche-4a.backend.patch`
- `artifacts/react-migration/patches/tranche-4a.frontend.patch`
- `artifacts/react-migration/patches/tranche-4a.gate.patch`
- `artifacts/react-migration/patches/tranche-4a.tests.patch`
- `artifacts/react-migration/patches/tranche-4a.reports.patch`
- `artifacts/react-migration/legacy-contracts/sito-studio__contatti.json`
- `artifacts/react-migration/legacy-contracts/sito-studio__builder.json`

## File modificati

- `web/services/react_backup_bridge.py`
- `web/blueprints/api_v1_react.py`
- `web/bootstrap/react_route_gate.py`
- `web/blueprints/react_shell.py`
- `frontend/src/backupData.ts`
- `frontend/src/components/BackupPage.tsx`
- `frontend/src/App.tsx`
- `frontend/scripts/check-react-contracts.mjs`
- `scripts/react-migration/check-route-gate.mjs`
- `scripts/react-migration/run-safe-react-migration.mjs`
- `tools/react-migration/route-manifest.json`
- `artifacts/react-migration/audit.md`, `artifacts/react-migration/route-inventory.json`
- `artifacts/react-migration/route-gate.md`, `artifacts/react-migration/ui-consistency.md`
- `artifacts/react-migration/legacy-contracts/backup.json`, `artifacts/react-migration/legacy-contracts/sito-studio.json`
- `artifacts/react-migration/legacy-contracts/studio.json`, `artifacts/react-migration/legacy-contracts/impostazioni.json`
- `web/static/react/*`
- `CHANGELOG.md`, `README.md`, `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`, `frontend/package.json`, `frontend/package-lock.json`

## Endpoint aggiunti

- `GET /api/v1/ui/sito-studio`
- `GET /api/v1/ui/sito-studio/contatti`

Endpoint completato/promosso:

- `GET /api/v1/ui/backup`

## Gate modificato

- Rimossi da `_LEGACY_OPERATIONAL_PREFIXES`: `/backup`, `/sito-studio`.
- Aggiunte protezioni nested per `/backup/*`, `/sito-studio/*` non migrati, `/studio*`, `/impostazioni*`.
- Preservato `?_legacy=1`.

## Route ancora bloccate

- `/backup/*`
- `/sito-studio/builder` e ogni altro subpath `/sito-studio/*` non esplicitamente migrato
- `/studio`
- `/impostazioni` e `/impostazioni?tab=firma`
- tutte le route economiche, mandato, documentali e telematiche non oggetto della tranche

## Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/backup.json`
- `artifacts/react-migration/legacy-contracts/sito-studio.json`
- `artifacts/react-migration/legacy-contracts/sito-studio__contatti.json`
- `artifacts/react-migration/legacy-contracts/sito-studio__builder.json`
- `artifacts/react-migration/legacy-contracts/studio.json`
- `artifacts/react-migration/legacy-contracts/impostazioni.json`

## Permessi verificati

- `/backup` API React richiede `backup.leggi`.
- `/sito-studio` e `/sito-studio/contatti` riusano `site_admin_identity_or_403` e quindi `admin.configura`, senza bypass amministrativo con chiavi API.

## POST legacy preservati

- Backup: `/backup/esegui`, `/backup/<id>/verifica`, `/backup/<id>/elimina`, `/backup/<id>/ripristina`.
- Sito Studio: gestione contenuti, contatti, prenotazioni, builder, asset e pubblicazione restano route legacy.
- Nessun fetch POST React introdotto.

## Azioni backup lasciate legacy

- Creazione backup.
- Verifica integrita.
- Download copia.
- Ripristino.
- Eliminazione.

## Builder/studio/impostazioni

- Builder Sito Studio lasciato legacy.
- `/studio` lasciata legacy.
- `/impostazioni` lasciata legacy, incluso tab firma.

## Controllo anti-segreti

- `node scripts/react-migration/check-tranche-4a-secrets.mjs`: OK.
- Report: `artifacts/react-migration/tranche-4a-secrets.md`.

## Test eseguiti

- `node scripts/react-migration/check-route-gate.mjs`: OK.
- `node scripts/react-migration/check-ui-consistency.mjs`: OK.
- `node scripts/react-migration/check-tranche-4a-secrets.mjs`: OK.
- `python scripts/react-migration/check-tranche-4a-gate.py`: OK.
- `cd frontend && npm run test`: OK.
- `cd frontend && npm run typecheck`: OK.
- `cd frontend && npm run build`: OK.
- `node scripts/react-migration/run-safe-react-migration.mjs --tranche=4a`: OK nella validazione finale con `ALLOW_DIRTY=1` per dirty runtime preesistente.

## Limiti test Flask

- Il test Flask usa tenant admin simulato e verifica gate, bypass legacy e JSON API. Non esegue operazioni tecniche di backup o pubblicazione builder, che restano volutamente legacy.

## Rischi residui

- Le azioni tecniche legacy restano dipendenti dai template e dai POST Flask esistenti.
- `/sito-studio/builder` contiene pubblicazione, upload asset e ripristino revisioni: resta bloccato nel gate fino a migrazione dedicata.
- `/impostazioni` contiene PEC/SMTP/firma/Local Signer e non viene esposto a React in questa tranche.

## Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-4a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-4a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-4a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-4a.tests.patch
```

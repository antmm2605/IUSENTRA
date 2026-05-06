# Preflight tranche React 2A

Data/ora: 2026-05-06 12:51 Europe/Rome

Branch operativo: Codex/legal-electronic-filing-kIxcV
Branch base richiesto: claude/legal-electronic-filing-kIxcV

## Parte 1

Presente:

- tools/react-migration/route-manifest.json
- scripts/react-migration/audit-react-migration.mjs
- scripts/react-migration/capture-legacy-contracts.py
- scripts/react-migration/check-route-gate.mjs
- scripts/react-migration/check-ui-consistency.mjs
- scripts/react-migration/run-safe-react-migration.mjs
- frontend/src/ui/Page.tsx
- frontend/src/theme/tokens.css
- artifacts/react-migration/

## Working tree

`git status --short` non era pulito prima della tranche: risultavano modifiche runtime preesistenti in `backup/`, `data/`, `intelligence/`, `privacy/` e file runtime non tracciati sotto `email/`, `intelligence/` e `output/`.

Per rispettare la regola di non revertire modifiche non mie, questi file sono trattati come baseline sporca esterna alla tranche e non saranno inclusi nei commit o nelle patch 2A.

## Comandi eseguiti

- `git status --short`
- `node scripts/react-migration/audit-react-migration.mjs`
- `python scripts/react-migration/capture-legacy-contracts.py /statistiche /audit /registro-attivita /utenti /profili /backup`

## Output verificati

- artifacts/react-migration/audit.md
- artifacts/react-migration/route-inventory.json
- artifacts/react-migration/legacy-contracts/statistiche.json
- artifacts/react-migration/legacy-contracts/audit.json
- artifacts/react-migration/legacy-contracts/registro-attivita.json
- artifacts/react-migration/legacy-contracts/utenti.json
- artifacts/react-migration/legacy-contracts/profili.json
- artifacts/react-migration/legacy-contracts/backup.json

## Esito

Preflight completato. Le sei route hanno contratto legacy catturato. Le route `/utenti`, `/profili` e `/backup` restano solo fotografate in questa tranche.

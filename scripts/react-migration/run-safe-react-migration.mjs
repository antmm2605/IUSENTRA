import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'

mkdirSync('artifacts/react-migration/patches', { recursive: true })

const args = process.argv.slice(2)
const TRANCHE_2A_FLAG = '--tranche=2a'
const TRANCHE_3A_FLAG = '--tranche=3a'
const TRANCHE_4A_FLAG = '--tranche=4a'
const TRANCHE_5A_FLAG = '--tranche=5a'
const TRANCHE_6A_FLAG = '--tranche=6a'
const tranche = args.find((arg) => arg.startsWith('--tranche='))?.split('=')[1] || ''
const EXEC_BUFFER = 1024 * 1024 * 200

const migrationPaths = [
  'CHANGELOG.md',
  'Dockerfile',
  'README.md',
  'docs/REACT_MIGRATION_MASTER_PLAN.md',
  'frontend/package.json',
  'frontend/package-lock.json',
  'frontend/scripts/check-react-contracts.mjs',
  'frontend/src/theme',
  'frontend/src/ui',
  'pct/__init__.py',
  'railway.toml',
  'setup.py',
  'scripts/react-migration',
  'tools/react-migration',
  'artifacts/react-migration/audit.md',
  'artifacts/react-migration/legacy-contracts',
  'artifacts/react-migration/route-gate.md',
  'artifacts/react-migration/route-inventory.json',
  'artifacts/react-migration/ui-consistency.md',
]

const tranche2aContracts = [
  '/statistiche',
  '/audit',
  '/registro-attivita',
  '/utenti',
  '/profili',
  '/backup',
]

const tranche3aContracts = [
  '/utenti',
  '/utenti/nuovo',
  '/profili',
  '/backup',
]

const tranche4aContracts = [
  '/backup',
  '/sito-studio',
  '/sito-studio/contatti',
  '/sito-studio/builder',
  '/studio',
  '/impostazioni',
]

const tranche5aContracts = [
  '/studio',
  '/amministrazione',
  '/impostazioni',
  '/impostazioni-studio',
  '/impostazioni/calendario',
  '/impostazioni/pagamenti',
  '/sincronizzazione-calendari',
]

const tranche6aContracts = [
  '/fatturazione',
  '/fatturazione/nuova',
  '/incassi-pagamenti',
  '/impostazioni/pagamenti',
  '/preventivi',
  '/compensi-forensi',
  '/tariffario',
]

const tranche2aPatchGroups = {
  backend: [
    'web/services/react_statistiche_bridge.py',
    'web/services/react_audit_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/src/lib/apiClient.ts',
    'frontend/src/statisticheData.ts',
    'frontend/src/auditData.ts',
    'frontend/src/components/StatistichePage.tsx',
    'frontend/src/components/StatistichePage.css',
    'frontend/src/components/AuditPage.tsx',
    'frontend/src/components/AuditPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-2a-gate.py',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-2a-preflight.md',
    'artifacts/react-migration/tranche-2a-route-map.md',
    'artifacts/react-migration/tranche-2a-gate.md',
    'artifacts/react-migration/tranche-2a-report.md',
    'artifacts/react-migration/legacy-contracts/statistiche.json',
    'artifacts/react-migration/legacy-contracts/audit.json',
    'artifacts/react-migration/legacy-contracts/registro-attivita.json',
    'artifacts/react-migration/legacy-contracts/utenti.json',
    'artifacts/react-migration/legacy-contracts/profili.json',
    'artifacts/react-migration/legacy-contracts/backup.json',
  ],
}

const tranche3aPatchGroups = {
  backend: [
    'web/services/react_utenti_bridge.py',
    'web/services/react_profili_bridge.py',
    'web/services/react_backup_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/src/utentiData.ts',
    'frontend/src/profiliData.ts',
    'frontend/src/backupData.ts',
    'frontend/src/components/UtentiPage.tsx',
    'frontend/src/components/UtentiPage.css',
    'frontend/src/components/ProfiliPage.tsx',
    'frontend/src/components/ProfiliPage.css',
    'frontend/src/components/BackupPage.tsx',
    'frontend/src/components/BackupPage.css',
    'frontend/src/ui/LegacyPostForm.tsx',
    'frontend/src/ui/ui.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-3a-gate.py',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-3a-route-map.md',
    'artifacts/react-migration/tranche-3a-gate.md',
    'artifacts/react-migration/tranche-3a-report.md',
    'artifacts/react-migration/legacy-contracts/utenti.json',
    'artifacts/react-migration/legacy-contracts/utenti__nuovo.json',
    'artifacts/react-migration/legacy-contracts/profili.json',
    'artifacts/react-migration/legacy-contracts/backup.json',
  ],
}

const tranche4aPatchGroups = {
  backend: [
    'web/services/react_backup_bridge.py',
    'web/services/react_sito_studio_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/src/backupData.ts',
    'frontend/src/sitoStudioData.ts',
    'frontend/src/components/BackupPage.tsx',
    'frontend/src/components/BackupPage.css',
    'frontend/src/components/SitoStudioPage.tsx',
    'frontend/src/components/SitoStudioPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-4a-gate.py',
    'scripts/react-migration/check-tranche-4a-secrets.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-4a-route-map.md',
    'artifacts/react-migration/tranche-4a-gate.md',
    'artifacts/react-migration/tranche-4a-secrets.md',
    'artifacts/react-migration/tranche-4a-report.md',
    'artifacts/react-migration/legacy-contracts/backup.json',
    'artifacts/react-migration/legacy-contracts/sito-studio.json',
    'artifacts/react-migration/legacy-contracts/sito-studio__contatti.json',
    'artifacts/react-migration/legacy-contracts/sito-studio__builder.json',
    'artifacts/react-migration/legacy-contracts/studio.json',
    'artifacts/react-migration/legacy-contracts/impostazioni.json',
  ],
}

const tranche5aPatchGroups = {
  backend: [
    'web/services/react_studio_bridge.py',
    'web/services/react_amministrazione_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/src/studioData.ts',
    'frontend/src/amministrazioneData.ts',
    'frontend/src/components/StudioPage.tsx',
    'frontend/src/components/StudioPage.css',
    'frontend/src/components/AmministrazionePage.tsx',
    'frontend/src/components/AmministrazionePage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-tranche-5a-gate.py',
    'scripts/react-migration/check-tranche-5a-secrets.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-5a-route-map.md',
    'artifacts/react-migration/tranche-5a-gate.md',
    'artifacts/react-migration/tranche-5a-secrets.md',
    'artifacts/react-migration/tranche-5a-report.md',
    'artifacts/react-migration/legacy-contracts/studio.json',
    'artifacts/react-migration/legacy-contracts/amministrazione.json',
    'artifacts/react-migration/legacy-contracts/impostazioni.json',
    'artifacts/react-migration/legacy-contracts/impostazioni-studio.json',
    'artifacts/react-migration/legacy-contracts/impostazioni__calendario.json',
    'artifacts/react-migration/legacy-contracts/impostazioni__pagamenti.json',
    'artifacts/react-migration/legacy-contracts/sincronizzazione-calendari.json',
  ],
}

const tranche6aPatchGroups = {
  backend: [
    'web/services/react_fatturazione_bridge.py',
    'web/services/react_incassi_pagamenti_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/src/fatturazioneData.ts',
    'frontend/src/incassiPagamentiData.ts',
    'frontend/src/components/FatturazionePage.tsx',
    'frontend/src/components/FatturazionePage.css',
    'frontend/src/components/IncassiPagamentiPage.tsx',
    'frontend/src/components/IncassiPagamentiPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-6a-gate.py',
    'scripts/react-migration/check-tranche-6a-secrets.mjs',
    'scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-6a-route-map.md',
    'artifacts/react-migration/tranche-6a-gate.md',
    'artifacts/react-migration/tranche-6a-secrets.md',
    'artifacts/react-migration/tranche-6a-no-fiscal-logic.md',
    'artifacts/react-migration/tranche-6a-report.md',
    'artifacts/react-migration/legacy-contracts/fatturazione.json',
    'artifacts/react-migration/legacy-contracts/fatturazione__nuova.json',
    'artifacts/react-migration/legacy-contracts/fatturazione__detail.json',
    'artifacts/react-migration/legacy-contracts/incassi-pagamenti.json',
    'artifacts/react-migration/legacy-contracts/impostazioni__pagamenti.json',
    'artifacts/react-migration/legacy-contracts/preventivi.json',
    'artifacts/react-migration/legacy-contracts/compensi-forensi.json',
    'artifacts/react-migration/legacy-contracts/tariffario.json',
  ],
}

function run(cmd, options = {}) {
  console.log(`\n> ${cmd}`)
  execSync(cmd, { stdio: 'inherit', ...options })
}

function cleanRequired() {
  if (process.env.ALLOW_DIRTY === '1') return
  const status = execSync('git status --short', { encoding: 'utf8' }).trim()
  if (status) {
    throw new Error(`Working tree non pulito. Usa ALLOW_DIRTY=1 solo se sai cosa stai facendo.\n${status}`)
  }
}

function textArtifact(cmd) {
  return execSync(cmd, { encoding: 'utf8', maxBuffer: EXEC_BUFFER })
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .join('\n')
}

function diffOutput(cmd) {
  try {
    return execSync(cmd, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      maxBuffer: EXEC_BUFFER,
    })
  } catch (error) {
    return `${error.stdout || ''}${error.stderr || ''}`
  }
}

function existingPaths(paths) {
  return paths.filter((path) => existsSync(path))
}

function untrackedPaths(paths) {
  const candidates = existingPaths(paths)
  if (!candidates.length) return []
  return textArtifact(`git ls-files --others --exclude-standard -- ${candidates.join(' ')}`)
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function trackedPaths(paths) {
  const candidates = existingPaths(paths)
  if (!candidates.length) return []
  return textArtifact(`git ls-files -- ${candidates.join(' ')}`)
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function patchForPaths(paths) {
  const existing = existingPaths(paths)
  if (!existing.length) return ''
  const tracked = trackedPaths(existing)
  const trackedPatch = tracked.length ? textArtifact(`git diff --binary -- ${tracked.join(' ')}`) : ''
  const untracked = untrackedPaths(existing)
    .map((path) => diffOutput(`git diff --binary --no-index -- /dev/null ${path}`))
    .join('\n')
  return [trackedPatch, untracked].filter((part) => part.trim()).join('\n').trimEnd() + '\n'
}

function writePatch(trancheName, name, paths) {
  writeFileSync(`artifacts/react-migration/patches/tranche-${trancheName}.${name}.patch`, patchForPaths(paths), 'utf8')
}

function writeTranche2aPatches() {
  for (const [name, paths] of Object.entries(tranche2aPatchGroups)) {
    writePatch('2a', name, paths)
  }
}

function writeTranche3aPatches() {
  for (const [name, paths] of Object.entries(tranche3aPatchGroups)) {
    writePatch('3a', name, paths)
  }
}

function writeTranche4aPatches() {
  for (const [name, paths] of Object.entries(tranche4aPatchGroups)) {
    writePatch('4a', name, paths)
  }
}

function writeTranche5aPatches() {
  for (const [name, paths] of Object.entries(tranche5aPatchGroups)) {
    writePatch('5a', name, paths)
  }
}

function writeTranche6aPatches() {
  for (const [name, paths] of Object.entries(tranche6aPatchGroups)) {
    writePatch('6a', name, paths)
  }
}

function runDefault() {
  cleanRequired()
  run('node scripts/react-migration/audit-react-migration.mjs')
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('cd frontend && npm run test')
  run('cd frontend && npm run typecheck')
  run('cd frontend && npm run build')
  writeFileSync(
    'artifacts/react-migration/patches/working-tree.patch',
    textArtifact(`git diff --binary -- ${migrationPaths.join(' ')}`),
    'utf8',
  )
  writeFileSync(
    'artifacts/react-migration/patches/status.txt',
    textArtifact(`git status --short -- ${migrationPaths.join(' ')}`),
    'utf8',
  )
  run('git diff --stat')
  run('git status --short')
}

function runTranche2a() {
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche2aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('python scripts/react-migration/check-tranche-2a-gate.py')
  run('cd frontend && npm run test')
  run('cd frontend && npm run typecheck')
  run('cd frontend && npm run build')
  writeTranche2aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche3a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche3aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('python scripts/react-migration/check-tranche-3a-gate.py')
  run('cd frontend && npm run test')
  run('cd frontend && npm run typecheck')
  run('cd frontend && npm run build')
  writeTranche3aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche4a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche4aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-4a-secrets.mjs')
  run('python scripts/react-migration/check-tranche-4a-gate.py')
  run('cd frontend && npm run test')
  run('cd frontend && npm run typecheck')
  run('cd frontend && npm run build')
  writeTranche4aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche5a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche5aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-5a-secrets.mjs')
  run('python scripts/react-migration/check-tranche-5a-gate.py')
  run('cd frontend && npm run test')
  run('cd frontend && npm run typecheck')
  run('cd frontend && npm run build')
  writeTranche5aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche6a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche6aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-6a-secrets.mjs')
  run('node scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs')
  run('python scripts/react-migration/check-tranche-6a-gate.py')
  run('cd frontend && npm run test')
  run('cd frontend && npm run typecheck')
  run('cd frontend && npm run build')
  writeTranche6aPatches()
  run('git diff --stat')
  run('git status --short')
}

if (tranche === '2a') {
  runTranche2a()
} else if (tranche === '3a') {
  runTranche3a()
} else if (tranche === '4a') {
  runTranche4a()
} else if (tranche === '5a') {
  runTranche5a()
} else if (tranche === '6a') {
  runTranche6a()
} else {
  runDefault()
}

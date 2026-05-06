import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'

mkdirSync('artifacts/react-migration/patches', { recursive: true })

const args = process.argv.slice(2)
const TRANCHE_2A_FLAG = '--tranche=2a'
const TRANCHE_3A_FLAG = '--tranche=3a'
const tranche = args.find((arg) => arg.startsWith('--tranche='))?.split('=')[1] || ''

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
  return execSync(cmd, { encoding: 'utf8' })
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .join('\n')
}

function diffOutput(cmd) {
  try {
    return execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
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

function patchForPaths(paths) {
  const existing = existingPaths(paths)
  if (!existing.length) return ''
  const tracked = textArtifact(`git diff --binary -- ${existing.join(' ')}`)
  const untracked = untrackedPaths(existing)
    .map((path) => diffOutput(`git diff --binary --no-index -- /dev/null ${path}`))
    .join('\n')
  return [tracked, untracked].filter((part) => part.trim()).join('\n').trimEnd() + '\n'
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

if (tranche === '2a') {
  runTranche2a()
} else if (tranche === '3a') {
  runTranche3a()
} else {
  runDefault()
}

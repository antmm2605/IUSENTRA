import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'

mkdirSync('artifacts/react-migration/patches', { recursive: true })

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

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const artifactDir = resolve(root, 'artifacts/react-migration')
mkdirSync(artifactDir, { recursive: true })

const auditPath = resolve(artifactDir, 'anti-mascheramento-audit.json')
if (!existsSync(auditPath)) {
  throw new Error('Esegui prima: node scripts/react-migration/audit-anti-mascheramento.mjs')
}

const audit = JSON.parse(readFileSync(auditPath, 'utf8'))
const rows = audit.rows || []
const violations = []

for (const row of rows) {
  const isFull = row.manifestStatus === 'react_full' || row.manifestStatus === 'react_operational_full'
  if (row.manifestStatus === 'react_full') {
    violations.push(`${row.route}: status react_full deprecato, usare react_operational_full solo se i controlli passano.`)
  }
  if (!isFull) {
    if (row.unlockFromGate === true && row.realLevel === 'react_shell') {
      violations.push(`${row.route}: sbloccata dal gate ma risulta solo react_shell.`)
    }
    continue
  }
  if ((row.blockingLegacyLinks || 0) > 0) {
    violations.push(`${row.route}: full con ${row.blockingLegacyLinks} link ?_legacy=1 primari o non governati.`)
  }
  if (row.legacyPostForms > 0 || row.reactPostForms > 0) {
    violations.push(`${row.route}: full con form legacy/POST HTML nel flusso principale.`)
  }
  if (row.bridgeWritesLegacy) {
    violations.push(`${row.route}: full con bridge writes=legacy_routes.`)
  }
  if (row.missingWriteApi) {
    violations.push(`${row.route}: full senza endpoint JSON per azioni principali.`)
  }
  if (!row.jsonReads) {
    violations.push(`${row.route}: full senza endpoint JSON di lettura rilevato.`)
  }
  if (row.missingErrorHandling) {
    violations.push(`${row.route}: full senza gestione errori visibile nel componente.`)
  }
  if (row.missingSuccessHandling && row.jsonWrites) {
    violations.push(`${row.route}: full con scrittura JSON ma senza stato success visibile.`)
  }
}

const apiSource = readFileSync(resolve(root, 'web/blueprints/api_v1_react.py'), 'utf8')
const profiliRow = rows.find((row) => row.route === '/profili')
if (profiliRow?.manifestStatus === 'react_operational_full') {
  const profiliComponent = readFileSync(resolve(root, 'frontend/src/components/ProfiliPage.tsx'), 'utf8')
  const profiliData = readFileSync(resolve(root, 'frontend/src/profiliData.ts'), 'utf8')
  const profiliBridge = readFileSync(resolve(root, 'web/services/react_profili_bridge.py'), 'utf8')
  const profiliCombined = `${profiliComponent}\n${profiliData}\n${profiliBridge}`

  if (/\bLegacyPostForm\b/.test(profiliComponent)) {
    violations.push('/profili: react_operational_full non puo contenere LegacyPostForm nel componente principale.')
  }
  if (/\?_legacy=1/.test(profiliCombined) && !/Rollback tecnico/.test(profiliCombined)) {
    violations.push('/profili: react_operational_full puo mantenere ?_legacy=1 solo come Rollback tecnico.')
  }
  if (!/\bapiPostJson\b/.test(profiliData) && !/\bapiPostJson\b/.test(profiliComponent)) {
    violations.push('/profili: react_operational_full deve salvare tramite apiPostJson centralizzato.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(profiliBridge)) {
    violations.push('/profili: bridge operativo deve dichiarare writes json_api.')
  }
  if (!apiSource.includes('@api_v1_react.post("/profili")')) {
    violations.push('/profili: manca endpoint POST JSON /api/v1/ui/profili.')
  }
}

const md = [
  '# Check no fake React full',
  '',
  `Generato: ${new Date().toISOString()}`,
  '',
  `Violazioni: ${violations.length}`,
  '',
  ...(violations.length ? violations.map((item) => `- ${item}`) : ['Nessuna route piena risulta mascherata da legacy.']),
  '',
].join('\n')

writeFileSync(resolve(artifactDir, 'no-fake-react-full-report.md'), md)

if (violations.length) {
  console.error(md)
  process.exit(1)
}

console.log('No fake React full OK.')

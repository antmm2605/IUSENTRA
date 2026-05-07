import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const failures = []

function read(path) {
  const full = resolve(root, path)
  return existsSync(full) ? readFileSync(full, 'utf8') : ''
}

function expect(condition, message) {
  if (!condition) failures.push(message)
}

const page = read('frontend/src/components/BackupPage.tsx')
const data = read('frontend/src/backupData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_backup_bridge.py')
const gate = read('web/bootstrap/react_route_gate.py')
const reactShell = read('web/blueprints/react_shell.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))
const route = (manifest.routes || []).find((item) => item.route === '/backup')
const combined = `${page}\n${data}\n${bridge}`

expect(!/\bLegacyPostForm\b/.test(page), 'BackupPage non deve usare LegacyPostForm.')
expect(/\bcreateBackup\b/.test(page), 'BackupPage deve usare createBackup.')
expect(/\bverifyBackupIntegrity\b/.test(page), 'BackupPage deve usare verifyBackupIntegrity.')
expect(/\bapiPostJson\b/.test(data), 'backupData.ts deve usare apiPostJson.')
expect(!/response\.blob|new Blob|URL\.createObjectURL/.test(data), 'backupData.ts non deve usare fetch blob.')
expect(!/URL\.createObjectURL/.test(page), 'BackupPage non deve usare URL.createObjectURL.')
expect(api.includes('@api_v1_react.post("/backup/crea")'), 'api_v1_react.py deve contenere POST /backup/crea.')
expect(api.includes('@api_v1_react.post("/backup/verifica")'), 'api_v1_react.py deve contenere POST /backup/verifica.')
expect(/["']writes["']\s*:\s*["']json_api["']/.test(bridge), 'react_backup_bridge.py deve dichiarare writes json_api.')
expect(/["']restore_migrated["']\s*:\s*False/.test(bridge), 'react_backup_bridge.py deve dichiarare restore_migrated false.')
expect(route?.status === 'react_operational_full', 'Il manifest deve marcare /backup react_operational_full.')
expect(route?.unlockFromGate === true, 'Il manifest deve mantenere /backup unlockFromGate=true.')
expect(!/\?_legacy=1/.test(page) || /Rollback tecnico/.test(page), 'Nessun uso primario di ?_legacy=1 in BackupPage.')
expect(!/localStorage|sessionStorage/.test(combined), 'Backup non deve usare localStorage o sessionStorage.')
expect(!/response\.blob|new Blob|URL\.createObjectURL/.test(combined), 'Backup non deve gestire download con blob React.')
expect(!/\brestoreBackup\b|\bdeleteBackup\b|ripristinaBackup|eliminaBackup/.test(combined), 'BackupPage non deve implementare restore/delete React.')
expect(!/"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:/i.test(bridge), 'Il payload backup non deve serializzare token/API key/secret/stack/path.')
expect(!/dangerouslySetInnerHTML/.test(page), 'BackupPage non deve usare dangerouslySetInnerHTML.')
expect(gate.includes('lower.startswith("/backup/")'), 'Il gate deve proteggere /backup/*.')
expect(reactShell.includes('lower.startswith("/backup/")'), 'La shell deve proteggere /backup/*.')

for (const state of ['loading', 'saving', 'success', 'error']) {
  expect(page.includes(state), `Stato UI mancante: ${state}.`)
}
for (const preserve of [
  'stato backup reale',
  'lista copie reale',
  'creazione backup JSON',
  'verifica integrita JSON',
  'download backend sicuro',
  'restore non migrato',
]) {
  expect((route?.mustPreserve || []).includes(preserve), `mustPreserve /backup mancante: ${preserve}.`)
}

if (failures.length) {
  console.error(['Check tranche 16A backup operativo fallito:', ...failures.map((failure) => `- ${failure}`)].join('\n'))
  process.exit(1)
}

console.log('Check tranche 16A backup operativo OK.')

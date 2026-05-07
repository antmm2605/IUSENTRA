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

const utentiRow = rows.find((row) => row.route === '/utenti')
if (utentiRow?.manifestStatus === 'react_operational_full') {
  const utentiComponent = readFileSync(resolve(root, 'frontend/src/components/UtentiPage.tsx'), 'utf8')
  const utentiData = readFileSync(resolve(root, 'frontend/src/utentiData.ts'), 'utf8')
  const utentiBridge = readFileSync(resolve(root, 'web/services/react_utenti_bridge.py'), 'utf8')
  const utentiCombined = `${utentiComponent}\n${utentiData}\n${utentiBridge}`
  const utentiPostEndpoints = [
    '@api_v1_react.post("/utenti/<id_utente>/stato")',
    '@api_v1_react.post("/utenti/<id_utente>/ruolo")',
    '@api_v1_react.post("/utenti/<id_utente>/reset-password")',
    '@api_v1_react.post("/utenti/<id_utente>/profilo")',
  ]

  if (/\bLegacyPostForm\b/.test(utentiComponent)) {
    violations.push('/utenti: react_operational_full non puo contenere LegacyPostForm nel componente principale.')
  }
  if (/\?_legacy=1/.test(utentiComponent) && !/Rollback tecnico/.test(utentiComponent)) {
    violations.push('/utenti: react_operational_full puo mantenere ?_legacy=1 solo come Rollback tecnico.')
  }
  if (!/\bapiPostJson\b/.test(utentiData)) {
    violations.push('/utenti: react_operational_full deve usare apiPostJson centralizzato per le azioni principali.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(utentiBridge)) {
    violations.push('/utenti: bridge operativo deve dichiarare writes json_api.')
  }
  for (const endpoint of utentiPostEndpoints) {
    if (!apiSource.includes(endpoint)) {
      violations.push(`/utenti: manca endpoint POST JSON ${endpoint}.`)
    }
  }
  if (/localStorage|sessionStorage/.test(utentiCombined)) {
    violations.push('/utenti: react_operational_full non deve usare localStorage o sessionStorage.')
  }
  if (/password_hash|reset_token|totp_secret|session_token|api_key/i.test(utentiBridge)) {
    violations.push('/utenti: bridge React non deve serializzare password hash, reset token, TOTP secret, session token o API key.')
  }
}

const backupRow = rows.find((row) => row.route === '/backup')
if (backupRow?.manifestStatus === 'react_operational_full') {
  const backupComponent = readFileSync(resolve(root, 'frontend/src/components/BackupPage.tsx'), 'utf8')
  const backupData = readFileSync(resolve(root, 'frontend/src/backupData.ts'), 'utf8')
  const backupBridge = readFileSync(resolve(root, 'web/services/react_backup_bridge.py'), 'utf8')
  const backupCombined = `${backupComponent}\n${backupData}\n${backupBridge}`
  const backupPostEndpoints = [
    '@api_v1_react.post("/backup/crea")',
    '@api_v1_react.post("/backup/verifica")',
  ]

  if (/\bLegacyPostForm\b/.test(backupComponent)) {
    violations.push('/backup: react_operational_full non puo contenere LegacyPostForm nel componente principale.')
  }
  if (/\?_legacy=1/.test(backupComponent) && !/Rollback tecnico/.test(backupComponent)) {
    violations.push('/backup: react_operational_full puo mantenere ?_legacy=1 solo come Rollback tecnico.')
  }
  if (!/\bapiPostJson\b/.test(backupData)) {
    violations.push('/backup: react_operational_full deve usare apiPostJson centralizzato per crea/verifica.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(backupBridge)) {
    violations.push('/backup: bridge operativo deve dichiarare writes json_api.')
  }
  for (const endpoint of backupPostEndpoints) {
    if (!apiSource.includes(endpoint)) {
      violations.push(`/backup: manca endpoint POST JSON ${endpoint}.`)
    }
  }
  if (/localStorage|sessionStorage/.test(backupCombined)) {
    violations.push('/backup: react_operational_full non deve usare localStorage o sessionStorage.')
  }
  if (/response\.blob|new Blob|URL\.createObjectURL/.test(backupCombined)) {
    violations.push('/backup: download backup non deve essere gestito con blob React.')
  }
  if (/\brestoreBackup\b|\bdeleteBackup\b|ripristinaBackup|eliminaBackup/.test(backupCombined)) {
    violations.push('/backup: restore/delete non devono essere implementati nel flusso React.')
  }
  if (/"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:/i.test(backupBridge)) {
    violations.push('/backup: bridge React non deve serializzare token, API key, secret, stack trace o path sensibili.')
  }
}

const fatturazioneNuovaRow = rows.find((row) => row.route === '/fatturazione/nuova')
if (fatturazioneNuovaRow?.manifestStatus === 'react_operational_full') {
  const page = readFileSync(resolve(root, 'frontend/src/components/FatturazionePage.tsx'), 'utf8')
  const data = readFileSync(resolve(root, 'frontend/src/fatturazioneData.ts'), 'utf8')
  const bridge = readFileSync(resolve(root, 'web/services/react_fatturazione_bridge.py'), 'utf8')
  const gate = readFileSync(resolve(root, 'web/bootstrap/react_route_gate.py'), 'utf8')
  const combined = `${page}\n${data}\n${bridge}`

  if (/\bLegacyPostForm\b/.test(page)) {
    violations.push('/fatturazione/nuova: react_operational_full non puo contenere LegacyPostForm nel flusso principale.')
  }
  if (/\?_legacy=1/.test(combined) && !/Rollback tecnico/.test(combined)) {
    violations.push('/fatturazione/nuova: eventuale ?_legacy=1 deve restare solo rollback tecnico.')
  }
  if (!/\bapiPostJson\b/.test(data)) {
    violations.push('/fatturazione/nuova: il salvataggio deve usare apiPostJson centralizzato.')
  }
  if (!/createFattura|createParcella/.test(page)) {
    violations.push('/fatturazione/nuova: il componente deve usare la funzione JSON di creazione.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) {
    violations.push('/fatturazione/nuova: bridge operativo deve dichiarare writes json_api.')
  }
  if (!/"canonical_calculation"\s*:\s*"backend"/.test(bridge)) {
    violations.push('/fatturazione/nuova: il contratto deve dichiarare calcolo canonico backend.')
  }
  if (!apiSource.includes('@api_v1_react.post("/fatturazione/nuova")')) {
    violations.push('/fatturazione/nuova: manca endpoint POST JSON /api/v1/ui/fatturazione/nuova.')
  }
  if (/localStorage|sessionStorage/.test(combined)) {
    violations.push('/fatturazione/nuova: non deve usare localStorage o sessionStorage.')
  }
  if (/response\.blob|URL\.createObjectURL|new Blob/.test(combined)) {
    violations.push('/fatturazione/nuova: React non deve gestire PDF/XML/export con blob.')
  }
  if (/calculateVat|calculateIva|calculateTax|calculateTotal|ivaRate|aliquotaIva|cassaRate|aliquotaCassa|ritenutaRate|Math\.round|\.toFixed\s*\(/i.test(`${page}\n${data}`)) {
    violations.push('/fatturazione/nuova: il frontend non deve contenere calcolo fiscale canonico.')
  }
  if (/generatePdf|generatePDF|generateXml|generateXML|fetch\s*\([^)]*blob/i.test(`${page}\n${data}`)) {
    violations.push('/fatturazione/nuova: React non deve generare documenti o export.')
  }
  if (!gate.includes('lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"')) {
    violations.push('/fatturazione/nuova: il gate deve continuare a proteggere gli altri subpath fatturazione.')
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

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

function read(relPath) {
  return readFileSync(resolve(root, relPath), 'utf8')
}

function routeRow(route) {
  return rows.find((row) => row.route === route)
}

function assertLegacyProtected(route) {
  const row = routeRow(route)
  if (row?.manifestStatus !== 'legacy_operational' || row?.unlockFromGate !== false) {
    violations.push(`${route}: deve restare legacy_operational con unlockFromGate false.`)
  }
}

for (const route of ['/impostazioni', '/impostazioni-studio', '/sincronizzazione-calendari', '/sito-studio/builder']) {
  assertLegacyProtected(route)
}

function assertNoBrowserUnsafe(route, combined) {
  if (/localStorage|sessionStorage/.test(combined)) {
    violations.push(`${route}: non deve usare localStorage o sessionStorage.`)
  }
  if (/fetch\s*\(\s*["']https?:\/\//.test(combined)) {
    violations.push(`${route}: non deve usare fetch esterni.`)
  }
  if (/dangerouslySetInnerHTML/.test(combined)) {
    violations.push(`${route}: non deve renderizzare HTML raw.`)
  }
}

function assertPrimaryLegacyOnlyRollback(route, combined) {
  if (/\?_legacy=1/.test(combined) && !/Rollback tecnico/.test(combined)) {
    violations.push(`${route}: eventuale ?_legacy=1 deve restare solo in Rollback tecnico.`)
  }
}

for (const config of [
  {
    route: '/studio',
    component: 'frontend/src/components/StudioPage.tsx',
    data: 'frontend/src/studioData.ts',
    bridge: 'web/services/react_studio_bridge.py',
    endpoint: '/api/v1/ui/studio',
    apiGet: '@api_v1_react.get("/studio")',
    writes: 'none',
  },
  {
    route: '/amministrazione',
    component: 'frontend/src/components/AmministrazionePage.tsx',
    data: 'frontend/src/amministrazioneData.ts',
    bridge: 'web/services/react_amministrazione_bridge.py',
    endpoint: '/api/v1/ui/amministrazione',
    apiGet: '@api_v1_react.get("/amministrazione")',
    writes: 'none',
  },
]) {
  const row = routeRow(config.route)
  if (row?.manifestStatus !== 'react_operational_full') {
    continue
  }
  const component = read(config.component)
  const data = read(config.data)
  const bridge = read(config.bridge)
  const combined = `${component}\n${data}\n${bridge}`
  if (/\bLegacyPostForm\b/.test(component)) {
    violations.push(`${config.route}: react_operational_full non puo contenere LegacyPostForm.`)
  }
  assertPrimaryLegacyOnlyRollback(config.route, component)
  if (!data.includes(config.endpoint)) {
    violations.push(`${config.route}: data client deve leggere ${config.endpoint}.`)
  }
  if (!apiSource.includes(config.apiGet)) {
    violations.push(`${config.route}: manca endpoint GET JSON ${config.apiGet}.`)
  }
  if (!/["']operational["']\s*:\s*True/.test(bridge)) {
    violations.push(`${config.route}: bridge operativo deve dichiarare operational true.`)
  }
  if (!new RegExp(`["']writes["']\\s*:\\s*["']${config.writes}["']`).test(bridge)) {
    violations.push(`${config.route}: bridge operativo deve dichiarare writes ${config.writes}.`)
  }
  if (/LegacyPostForm|apiPostJson/.test(combined)) {
    violations.push(`${config.route}: tranche read-only non deve usare form legacy o apiPostJson.`)
  }
  assertNoBrowserUnsafe(config.route, combined)
}

const sitoRow = routeRow('/sito-studio')
const sitoContattiRow = routeRow('/sito-studio/contatti')
if (sitoRow?.manifestStatus === 'react_operational_full' || sitoContattiRow?.manifestStatus === 'react_operational_full') {
  const component = read('frontend/src/components/SitoStudioPage.tsx')
  const data = read('frontend/src/sitoStudioData.ts')
  const bridge = read('web/services/react_sito_studio_bridge.py')
  const combined = `${component}\n${data}\n${bridge}`

  if (/\bLegacyPostForm\b/.test(component)) {
    violations.push('/sito-studio: react_operational_full non puo contenere LegacyPostForm.')
  }
  assertPrimaryLegacyOnlyRollback('/sito-studio', component)
  if (!data.includes('/api/v1/ui/sito-studio') || !data.includes('/api/v1/ui/sito-studio/contatti')) {
    violations.push('/sito-studio: data client deve leggere gli endpoint GET sito e contatti.')
  }
  if (!/\bapiPostJson\b/.test(data) || !/linkSitoContatto|updateSitoBookingStatus/.test(data)) {
    violations.push('/sito-studio/contatti: azioni supportate devono usare apiPostJson.')
  }
  if (!apiSource.includes('@api_v1_react.get("/sito-studio")') || !apiSource.includes('@api_v1_react.get("/sito-studio/contatti")')) {
    violations.push('/sito-studio: mancano endpoint GET JSON sito o contatti.')
  }
  if (!apiSource.includes('@api_v1_react.post("/sito-studio/contatti/<id_contatto>/collega")')) {
    violations.push('/sito-studio/contatti: manca endpoint POST JSON collegamento cliente supportato.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']|writes\s*=\s*["']json_api["']/.test(bridge)) {
    violations.push('/sito-studio/contatti: bridge operativo deve dichiarare writes json_api.')
  }
  if (!/["']writes["']\s*:\s*["']none["']|writes\s*=\s*["']none["']/.test(bridge)) {
    violations.push('/sito-studio: bridge dashboard deve dichiarare writes none.')
  }
  assertNoBrowserUnsafe('/sito-studio', combined)
}

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

const preventiviPage = readFileSync(resolve(root, 'frontend/src/components/PreventiviPage.tsx'), 'utf8')
const preventiviData = readFileSync(resolve(root, 'frontend/src/preventiviData.ts'), 'utf8')
const preventiviBridge = readFileSync(resolve(root, 'web/services/react_preventivi_bridge.py'), 'utf8')
const preventiviCombined = `${preventiviPage}\n${preventiviData}\n${preventiviBridge}`

const preventiviNuovoRow = rows.find((row) => row.route === '/preventivi/nuovo')
if (preventiviNuovoRow?.manifestStatus === 'react_operational_full') {
  if (/\bLegacyPostForm\b/.test(preventiviPage)) {
    violations.push('/preventivi/nuovo: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(preventiviPage) && !/Rollback tecnico/.test(preventiviPage)) {
    violations.push('/preventivi/nuovo: ?_legacy=1 ammesso solo come Rollback tecnico.')
  }
  if (!/\bapiPostJson\b/.test(preventiviData) || !/\bcreatePreventivo\b/.test(preventiviPage)) {
    violations.push('/preventivi/nuovo: deve salvare tramite createPreventivo e apiPostJson.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(preventiviBridge)) {
    violations.push('/preventivi/nuovo: bridge preventivi deve dichiarare writes json_api.')
  }
  if (!apiSource.includes('@api_v1_react.post("/preventivi/nuovo")')) {
    violations.push('/preventivi/nuovo: manca endpoint POST JSON /api/v1/ui/preventivi/nuovo.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(preventiviCombined)) {
    violations.push('/preventivi/nuovo: non deve usare storage browser o blob frontend.')
  }
  if (/generatePdf|generatePDF|generateDocx|generateDOCX|calculateCompenso|calculatePreventivo/i.test(`${preventiviPage}\n${preventiviData}`)) {
    violations.push('/preventivi/nuovo: React non deve calcolare compensi o generare documenti.')
  }
}

const conferimentoRow = rows.find((row) => row.route === '/preventivi/conferimento/nuovo')
if (conferimentoRow?.manifestStatus === 'react_operational_full') {
  if (/\bLegacyPostForm\b/.test(preventiviPage)) {
    violations.push('/preventivi/conferimento/nuovo: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(preventiviPage) && !/Rollback tecnico/.test(preventiviPage)) {
    violations.push('/preventivi/conferimento/nuovo: ?_legacy=1 ammesso solo come Rollback tecnico.')
  }
  if (!/\bapiPostJson\b/.test(preventiviData) || !/\bcreateConferimento\b/.test(preventiviPage)) {
    violations.push('/preventivi/conferimento/nuovo: deve salvare tramite createConferimento e apiPostJson.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(preventiviBridge)) {
    violations.push('/preventivi/conferimento/nuovo: bridge preventivi deve dichiarare writes json_api.')
  }
  if (!apiSource.includes('@api_v1_react.post("/preventivi/conferimento/nuovo")')) {
    violations.push('/preventivi/conferimento/nuovo: manca endpoint POST JSON /api/v1/ui/preventivi/conferimento/nuovo.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(preventiviCombined)) {
    violations.push('/preventivi/conferimento/nuovo: non deve usare storage browser o blob frontend.')
  }
  if (/generatePdf|generatePDF|generateDocx|generateDOCX|generateDocument|createDocument/.test(`${preventiviPage}\n${preventiviData}`)) {
    violations.push('/preventivi/conferimento/nuovo: React non deve generare mandato, PDF o DOCX.')
  }
}

const preventiviArchiveRow = rows.find((row) => row.route === '/preventivi')
if (preventiviArchiveRow?.manifestStatus === 'react_operational_full') {
  if (/\bLegacyPostForm\b/.test(preventiviPage)) {
    violations.push('/preventivi: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(preventiviPage) && !/Rollback tecnico/.test(preventiviPage)) {
    violations.push('/preventivi: ?_legacy=1 ammesso solo come Rollback tecnico.')
  }
  if (!/\bgetPreventiviPage\b/.test(preventiviPage) || !/\bgetPreventivoDetail\b/.test(preventiviPage)) {
    violations.push('/preventivi: archivio e dettaglio devono usare API JSON.')
  }
  if (!/\bapiPostJson\b/.test(preventiviData) || !/\bupdatePreventivoStatus\b/.test(preventiviPage)) {
    violations.push('/preventivi: azioni principali supportate devono usare apiPostJson.')
  }
  if (!apiSource.includes('@api_v1_react.get("/preventivi")') || !apiSource.includes('@api_v1_react.get("/preventivi/<id_preventivo>")')) {
    violations.push('/preventivi: mancano endpoint GET JSON archivio o dettaglio.')
  }
  if (!apiSource.includes('@api_v1_react.post("/preventivi/<id_preventivo>/stato")')) {
    violations.push('/preventivi: manca endpoint POST JSON per cambio stato supportato.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(preventiviBridge)) {
    violations.push('/preventivi: bridge preventivi deve dichiarare writes json_api.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(preventiviCombined)) {
    violations.push('/preventivi: non deve usare storage browser o blob frontend.')
  }
  if (/generatePdf|generatePDF|generateDocx|generateDOCX|calculateCompenso|calculatePreventivo/i.test(`${preventiviPage}\n${preventiviData}`)) {
    violations.push('/preventivi: React non deve calcolare compensi o generare documenti.')
  }
}

const fatturazioneArchiveRow = rows.find((row) => row.route === '/fatturazione')
if (fatturazioneArchiveRow?.manifestStatus === 'react_operational_full') {
  const fattPage = readFileSync(resolve(root, 'frontend/src/components/FatturazionePage.tsx'), 'utf8')
  const fattData = readFileSync(resolve(root, 'frontend/src/fatturazioneData.ts'), 'utf8')
  const fattBridge = readFileSync(resolve(root, 'web/services/react_fatturazione_bridge.py'), 'utf8')
  const fattCombined = `${fattPage}\n${fattData}\n${fattBridge}`
  if (/\bLegacyPostForm\b/.test(fattPage)) {
    violations.push('/fatturazione: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(fattPage) && !/Rollback tecnico/.test(fattPage)) {
    violations.push('/fatturazione: ?_legacy=1 ammesso solo come Rollback tecnico.')
  }
  if (!/\bgetFatturazionePage\b/.test(fattPage) || !/\bgetFatturazioneDetail\b/.test(fattPage)) {
    violations.push('/fatturazione: archivio e dettaglio devono usare API JSON.')
  }
  if (!/\bapiPostJson\b/.test(fattData) || !/\bupdateFatturazioneStatus\b/.test(fattPage)) {
    violations.push('/fatturazione: azioni principali supportate devono usare apiPostJson.')
  }
  if (!apiSource.includes('@api_v1_react.get("/fatturazione")') || !apiSource.includes('@api_v1_react.get("/fatturazione/<id_documento>")')) {
    violations.push('/fatturazione: mancano endpoint GET JSON archivio o dettaglio.')
  }
  if (!apiSource.includes('@api_v1_react.post("/fatturazione/<id_documento>/stato")')) {
    violations.push('/fatturazione: manca endpoint POST JSON per cambio stato supportato.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(fattBridge)) {
    violations.push('/fatturazione: bridge fatturazione deve dichiarare writes json_api.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(fattCombined)) {
    violations.push('/fatturazione: non deve usare storage browser o blob frontend.')
  }
  if (/calculateVat|calculateIva|calculateTax|calculateTotal|ivaRate|aliquotaIva|cassaRate|aliquotaCassa|ritenutaRate|Math\.round|\.toFixed\s*\(/i.test(`${fattPage}\n${fattData}`)) {
    violations.push('/fatturazione: React non deve contenere calcolo fiscale canonico.')
  }
}

const incassiRow = rows.find((row) => row.route === '/incassi-pagamenti')
if (incassiRow?.manifestStatus === 'react_operational_full') {
  const page = readFileSync(resolve(root, 'frontend/src/components/IncassiPagamentiPage.tsx'), 'utf8')
  const data = readFileSync(resolve(root, 'frontend/src/incassiPagamentiData.ts'), 'utf8')
  const bridge = readFileSync(resolve(root, 'web/services/react_incassi_pagamenti_bridge.py'), 'utf8')
  const combined = `${page}\n${data}\n${bridge}`
  if (/\bLegacyPostForm\b/.test(page)) {
    violations.push('/incassi-pagamenti: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(page) && !/Rollback tecnico|Impostazioni provider legacy/.test(page)) {
    violations.push('/incassi-pagamenti: ?_legacy=1 ammesso solo come Rollback tecnico o Impostazioni provider legacy.')
  }
  if (!/\bapiPostJson\b/.test(data) || !/\bregisterIncasso\b/.test(page)) {
    violations.push('/incassi-pagamenti: azioni principali devono usare apiPostJson e funzioni data client.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) {
    violations.push('/incassi-pagamenti: bridge incassi deve dichiarare writes json_api.')
  }
  if (!apiSource.includes('@api_v1_react.get("/incassi-pagamenti")')) {
    violations.push('/incassi-pagamenti: manca endpoint GET JSON.')
  }
  if (!apiSource.includes('@api_v1_react.post("/incassi-pagamenti/incasso")')) {
    violations.push('/incassi-pagamenti: manca endpoint POST JSON incasso.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(combined)) {
    violations.push('/incassi-pagamenti: non deve usare storage browser o blob frontend.')
  }
  if (/fetch\s*\(\s*["']https?:\/\//.test(data) || /provider_secret|webhook_secret|client_secret|api_key|access_token|refresh_token/i.test(`${page}\n${data}`)) {
    violations.push('/incassi-pagamenti: React non deve fare fetch esterni o esporre segreti provider.')
  }
}

const compensiRow = rows.find((row) => row.route === '/compensi-forensi')
if (compensiRow?.manifestStatus === 'react_operational_full') {
  const page = readFileSync(resolve(root, 'frontend/src/components/CompensiForensiPage.tsx'), 'utf8')
  const data = readFileSync(resolve(root, 'frontend/src/compensiForensiData.ts'), 'utf8')
  const bridge = readFileSync(resolve(root, 'web/services/react_compensi_forensi_bridge.py'), 'utf8')
  const combined = `${page}\n${data}\n${bridge}`
  if (/\bLegacyPostForm\b/.test(page)) {
    violations.push('/compensi-forensi: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) {
    violations.push('/compensi-forensi: ?_legacy=1 ammesso solo come Rollback tecnico.')
  }
  if (!/\bcalculateCompensiForensi\b/.test(page) || !/\bapiPostJson\b/.test(data)) {
    violations.push('/compensi-forensi: deve calcolare tramite data client e apiPostJson.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) {
    violations.push('/compensi-forensi: bridge compensi deve dichiarare writes json_api.')
  }
  if (!apiSource.includes('@api_v1_react.get("/compensi-forensi")') || !apiSource.includes('@api_v1_react.post("/compensi-forensi/calcola")')) {
    violations.push('/compensi-forensi: mancano endpoint GET o POST /calcola JSON.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(combined)) {
    violations.push('/compensi-forensi: non deve usare storage browser o blob frontend.')
  }
  if (/calculateTotal|calculateCompenso|calculateOnorari|calculateDM55|computeDM55|dm55Table|coefficiente|moltiplicatore|Math\.round|\.toFixed\s*\(/.test(`${page}\n${data}`)) {
    violations.push('/compensi-forensi: React non deve contenere formule o calcoli canonici.')
  }
}

const tariffarioRow = rows.find((row) => row.route === '/tariffario')
if (tariffarioRow?.manifestStatus === 'react_operational_full') {
  const page = readFileSync(resolve(root, 'frontend/src/components/TariffarioPage.tsx'), 'utf8')
  const data = readFileSync(resolve(root, 'frontend/src/tariffarioData.ts'), 'utf8')
  const bridge = readFileSync(resolve(root, 'web/services/react_tariffario_bridge.py'), 'utf8')
  const combined = `${page}\n${data}\n${bridge}`
  if (/\bLegacyPostForm\b/.test(page)) {
    violations.push('/tariffario: react_operational_full non puo contenere LegacyPostForm.')
  }
  if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) {
    violations.push('/tariffario: ?_legacy=1 ammesso solo come Rollback tecnico.')
  }
  if (!/\bgetTariffarioPage\b/.test(page) || !/\bcalculateTariffario\b/.test(page)) {
    violations.push('/tariffario: deve leggere e calcolare tramite data client JSON.')
  }
  if (!/\bapiPostJson\b/.test(data)) {
    violations.push('/tariffario: data client deve usare apiPostJson per il calcolo.')
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) {
    violations.push('/tariffario: bridge tariffario deve dichiarare writes json_api.')
  }
  if (!apiSource.includes('@api_v1_react.get("/tariffario")') || !apiSource.includes('@api_v1_react.post("/tariffario/calcola")')) {
    violations.push('/tariffario: mancano endpoint GET o POST /calcola JSON.')
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/.test(combined)) {
    violations.push('/tariffario: non deve usare storage browser o blob frontend.')
  }
  if (/calculateTotal|calculateCompenso|calculateOnorari|calculateDM55|computeDM55|dm55Table|tariffarioTable|hardcodedBrackets|scaglioni\s*=\s*\[|coefficiente|moltiplicatore|Math\.round|\.toFixed\s*\(/.test(`${page}\n${data}`)) {
    violations.push('/tariffario: React non deve contenere formule o scaglioni hardcoded.')
  }
}

for (const auditRoute of ['/audit', '/registro-attivita']) {
  const auditRow = rows.find((row) => row.route === auditRoute)
  if (auditRow?.manifestStatus !== 'react_operational_full') {
    continue
  }
  const page = readFileSync(resolve(root, 'frontend/src/components/AuditPage.tsx'), 'utf8')
  const data = readFileSync(resolve(root, 'frontend/src/auditData.ts'), 'utf8')
  const bridge = readFileSync(resolve(root, 'web/services/react_audit_bridge.py'), 'utf8')
  const frontend = `${page}\n${data}`
  if (/\bLegacyPostForm\b/.test(page)) {
    violations.push(`${auditRoute}: react_operational_full non puo contenere LegacyPostForm.`)
  }
  if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) {
    violations.push(`${auditRoute}: ?_legacy=1 ammesso solo come Rollback tecnico.`)
  }
  if (!/\bgetAuditEventDetail\b/.test(page) || !/\bapiPostJson\b/.test(data)) {
    violations.push(`${auditRoute}: dettaglio e azioni devono passare da data client JSON.`)
  }
  if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) {
    violations.push(`${auditRoute}: bridge audit deve dichiarare writes json_api.`)
  }
  if (!apiSource.includes('@api_v1_react.get("/audit")') || !apiSource.includes('@api_v1_react.get("/registro-attivita")') || !apiSource.includes('@api_v1_react.get("/audit/<id_evento>")')) {
    violations.push(`${auditRoute}: mancano endpoint GET JSON audit, registro o dettaglio.`)
  }
  if (/localStorage|sessionStorage|response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob|dangerouslySetInnerHTML/.test(frontend)) {
    violations.push(`${auditRoute}: non deve usare storage browser, blob o HTML raw.`)
  }
  if (/password_hash|api_key|access_token|refresh_token|stack_trace|traceback/i.test(frontend)) {
    violations.push(`${auditRoute}: payload renderizzato non deve contenere segreti o stack trace.`)
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

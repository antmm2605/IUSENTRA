import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const failures = []

const page = read('frontend/src/components/AuditPage.tsx')
const data = read('frontend/src/auditData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_audit_bridge.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

if (/\bLegacyPostForm\b/.test(page)) failures.push('AuditPage usa LegacyPostForm.')
if (!/\bgetAuditPage\b/.test(page) || !/\bgetRegistroAttivitaPage\b/.test(page)) failures.push('AuditPage non usa getAuditPage/getRegistroAttivitaPage.')
if (!/\bgetAuditEventDetail\b/.test(page)) failures.push('AuditPage non usa getAuditEventDetail.')
if (!/\bapiPostJson\b/.test(data)) failures.push('auditData.ts non usa apiPostJson per azioni.')
if (!api.includes('@api_v1_react.get("/audit")')) failures.push('Manca GET /audit.')
if (!api.includes('@api_v1_react.get("/registro-attivita")')) failures.push('Manca GET /registro-attivita.')
if (!api.includes('@api_v1_react.get("/audit/<id_evento>")')) failures.push('Manca GET dettaglio audit.')
if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) failures.push('Bridge audit non dichiara writes json_api.')
for (const route of ['/audit', '/registro-attivita']) {
  const entry = manifest.routes.find((row) => row.route === route)
  if (entry?.status !== 'react_operational_full') failures.push(`Manifest non marca ${route} react_operational_full.`)
}
if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) failures.push('Uso primario di ?_legacy=1 in AuditPage.')
if (/localStorage|sessionStorage/.test(`${page}\n${data}`)) failures.push('Storage browser non ammesso in audit.')
if (/response\.blob|new Blob|URL\.createObjectURL/.test(`${page}\n${data}`)) failures.push('Blob/ObjectURL non ammessi in audit.')
if (/dangerouslySetInnerHTML/.test(page)) failures.push('dangerouslySetInnerHTML non ammesso in audit.')
if (/api_key|access_token|refresh_token|password_hash|stack_trace|traceback/i.test(`${page}\n${data}`)) failures.push('Segreti o stack trace nel payload renderizzato audit.')

if (failures.length) {
  console.error(['Tranche 25A audit operational KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 25A audit operational OK.')

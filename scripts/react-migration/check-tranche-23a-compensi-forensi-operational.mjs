import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const failures = []

const page = read('frontend/src/components/CompensiForensiPage.tsx')
const data = read('frontend/src/compensiForensiData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_compensi_forensi_bridge.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

if (/\bLegacyPostForm\b/.test(page)) failures.push('CompensiForensiPage usa LegacyPostForm.')
if (!/\bcalculateCompensiForensi\b/.test(page)) failures.push('CompensiForensiPage non usa calculateCompensiForensi.')
if (!/Risultato backend|ResultPanel/.test(page)) failures.push('CompensiForensiPage non mostra risultato backend.')
if (!/\bapiPostJson\b/.test(data)) failures.push('compensiForensiData.ts non usa apiPostJson.')
if (/response\.blob|new Blob|URL\.createObjectURL/.test(`${page}\n${data}`)) failures.push('Blob/ObjectURL non ammessi in compensi.')
if (!api.includes('@api_v1_react.get("/compensi-forensi")')) failures.push('Manca GET /compensi-forensi.')
if (!api.includes('@api_v1_react.post("/compensi-forensi/calcola")')) failures.push('Manca POST /compensi-forensi/calcola.')
if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) failures.push('Bridge compensi non dichiara writes json_api.')
const entry = manifest.routes.find((row) => row.route === '/compensi-forensi')
if (entry?.status !== 'react_operational_full') failures.push('Manifest non marca /compensi-forensi react_operational_full.')
if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) failures.push('Uso primario di ?_legacy=1 in compensi.')
if (/localStorage|sessionStorage/.test(`${page}\n${data}`)) failures.push('Storage browser non ammesso in compensi.')
if (/api_key|access_token|refresh_token|stack_trace|traceback/i.test(`${page}\n${data}`)) failures.push('Segreti o stack trace nel payload renderizzato compensi.')
for (const marker of ['loading', 'calculating', 'saving', 'success', 'error']) {
  if (!new RegExp(marker, 'i').test(page)) failures.push(`Stato UI mancante: ${marker}.`)
}

if (failures.length) {
  console.error(['Tranche 23A compensi operational KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 23A compensi operational OK.')

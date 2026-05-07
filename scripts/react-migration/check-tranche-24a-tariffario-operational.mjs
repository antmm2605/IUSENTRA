import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const failures = []

const page = read('frontend/src/components/TariffarioPage.tsx')
const data = read('frontend/src/tariffarioData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_tariffario_bridge.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

if (/\bLegacyPostForm\b/.test(page)) failures.push('TariffarioPage usa LegacyPostForm.')
if (!/\bgetTariffarioPage\b/.test(page)) failures.push('TariffarioPage non usa getTariffarioPage.')
if (!/\bcalculateTariffario\b/.test(page)) failures.push('TariffarioPage non usa calculateTariffario.')
if (!/ResultPanel|result/.test(page)) failures.push('TariffarioPage non mostra risultato backend.')
if (!/\bapiPostJson\b/.test(data)) failures.push('tariffarioData.ts non usa apiPostJson.')
if (/response\.blob|new Blob|URL\.createObjectURL/.test(`${page}\n${data}`)) failures.push('Blob/ObjectURL non ammessi in tariffario.')
if (!api.includes('@api_v1_react.get("/tariffario")')) failures.push('Manca GET /tariffario.')
if (!api.includes('@api_v1_react.post("/tariffario/calcola")')) failures.push('Manca POST /tariffario/calcola.')
if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) failures.push('Bridge tariffario non dichiara writes json_api.')
const entry = manifest.routes.find((row) => row.route === '/tariffario')
if (entry?.status !== 'react_operational_full') failures.push('Manifest non marca /tariffario react_operational_full.')
if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) failures.push('Uso primario di ?_legacy=1 in tariffario.')
if (/localStorage|sessionStorage/.test(`${page}\n${data}`)) failures.push('Storage browser non ammesso in tariffario.')
if (/api_key|access_token|refresh_token|stack_trace|traceback/i.test(`${page}\n${data}`)) failures.push('Segreti o stack trace nel payload renderizzato tariffario.')
const stateChecks = {
  loading: /loading|Caricamento/i,
  calculating: /busy|Calcolo tariffario/i,
  saving: /Salvataggio|saving/i,
  success: /success|Calcolo completato/i,
  error: /error|role="alert"/i,
}
for (const [label, pattern] of Object.entries(stateChecks)) {
  if (!pattern.test(page)) failures.push(`Stato UI mancante: ${label}.`)
}

if (failures.length) {
  console.error(['Tranche 24A tariffario operational KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 24A tariffario operational OK.')

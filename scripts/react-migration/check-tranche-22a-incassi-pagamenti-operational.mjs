import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const failures = []

const page = read('frontend/src/components/IncassiPagamentiPage.tsx')
const data = read('frontend/src/incassiPagamentiData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_incassi_pagamenti_bridge.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

if (/\bLegacyPostForm\b/.test(page)) failures.push('IncassiPagamentiPage usa LegacyPostForm.')
if (!/\bgetIncassiPagamentiPage\b/.test(page)) failures.push('IncassiPagamentiPage non usa getIncassiPagamentiPage.')
if (!/\bregisterIncasso\b/.test(page)) failures.push('IncassiPagamentiPage non usa registerIncasso.')
if (!/\bapiPostJson\b/.test(data)) failures.push('incassiPagamentiData.ts non usa apiPostJson.')
if (/response\.blob|new Blob|URL\.createObjectURL/.test(`${page}\n${data}`)) failures.push('Blob/ObjectURL non ammessi in incassi.')
if (/fetch\s*\(\s*["']https?:\/\//.test(data)) failures.push('Fetch esterno non ammesso nel data client incassi.')
if (!api.includes('@api_v1_react.get("/incassi-pagamenti")')) failures.push('Manca GET /api/v1/ui/incassi-pagamenti.')
if (!api.includes('@api_v1_react.post("/incassi-pagamenti/incasso")')) failures.push('Manca POST incasso JSON.')
if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) failures.push('Bridge incassi non dichiara writes json_api.')
if (!/provider_configuration["']?\s*:\s*["']legacy_backend/.test(bridge)) failures.push('Contratto provider legacy mancante.')
const entry = manifest.routes.find((row) => row.route === '/incassi-pagamenti')
if (entry?.status !== 'react_operational_full') failures.push('Manifest non marca /incassi-pagamenti react_operational_full.')
if (/\?_legacy=1/.test(page) && !/Impostazioni provider legacy|Rollback tecnico/.test(page)) failures.push('Uso primario di ?_legacy=1 in IncassiPagamentiPage.')
if (/localStorage|sessionStorage/.test(`${page}\n${data}`)) failures.push('Storage browser non ammesso in incassi.')
if (/provider_secret|webhook_secret|client_secret|api_key|access_token|refresh_token/i.test(`${page}\n${data}`)) failures.push('Segreti provider nel payload renderizzato incassi.')
for (const marker of ['loading', 'saving', 'success', 'error']) {
  if (!new RegExp(marker, 'i').test(page)) failures.push(`Stato UI mancante: ${marker}.`)
}

if (failures.length) {
  console.error(['Tranche 22A incassi operational KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 22A incassi operational OK.')

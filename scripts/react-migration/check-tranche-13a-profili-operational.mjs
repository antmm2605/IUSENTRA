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

const page = read('frontend/src/components/ProfiliPage.tsx')
const data = read('frontend/src/profiliData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_profili_bridge.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))
const route = (manifest.routes || []).find((item) => item.route === '/profili')
const combined = `${page}\n${data}\n${bridge}`

expect(!/\bLegacyPostForm\b/.test(page), 'ProfiliPage non deve usare LegacyPostForm.')
expect(/\bsaveProfiliPermissions\b|\bsaveUserPermissionOverride\b/.test(page), 'ProfiliPage deve usare saveProfiliPermissions o funzione equivalente.')
expect(/\bapiPostJson\b/.test(data), 'profiliData.ts deve usare apiPostJson.')
expect(api.includes('@api_v1_react.post("/profili")'), 'api_v1_react.py deve contenere POST /profili.')
expect(/["']writes["']\s*:\s*["']json_api["']/.test(bridge), 'react_profili_bridge.py deve dichiarare writes json_api.')
expect(route?.status === 'react_operational_full', 'Il manifest deve marcare /profili react_operational_full.')
expect(route?.unlockFromGate === true, 'Il manifest deve mantenere /profili unlockFromGate=true.')
expect(!/\?_legacy=1/.test(page) || /Rollback tecnico/.test(page), 'Nessun uso primario di ?_legacy=1 in ProfiliPage.')
expect(!/localStorage|sessionStorage/.test(combined), 'Profili non deve usare localStorage o sessionStorage.')
expect(!/\bpassword\b|\bhash\b|\bsession token\b|\bapi key\b/i.test(combined), 'Profili non deve esporre campi password, hash, session token o API key.')
for (const state of ['loading', 'saving', 'success', 'error']) {
  expect(page.includes(state), `Stato UI mancante: ${state}.`)
}
expect(/operational["']?\s*:\s*True|operational["']?\s*:\s*true/.test(bridge), 'Il bridge deve dichiarare operational=true.')
expect(/update_react_profili_payload/.test(bridge), 'Il bridge deve esporre update_react_profili_payload.')
expect(/utenti\.aggiorna_permessi/.test(bridge), 'Il bridge deve preservare audit utenti.aggiorna_permessi.')

if (failures.length) {
  console.error(['Check tranche 13A profili operativo fallito:', ...failures.map((failure) => `- ${failure}`)].join('\n'))
  process.exit(1)
}

console.log('Check tranche 13A profili operativo OK.')

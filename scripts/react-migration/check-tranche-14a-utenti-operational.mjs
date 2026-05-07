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

const page = read('frontend/src/components/UtentiPage.tsx')
const data = read('frontend/src/utentiData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_utenti_bridge.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))
const route = (manifest.routes || []).find((item) => item.route === '/utenti')
const routeNew = (manifest.routes || []).find((item) => item.route === '/utenti/nuovo')
const combined = `${page}\n${data}\n${bridge}`

expect(!/\bLegacyPostForm\b/.test(page), 'UtentiPage non deve usare LegacyPostForm.')
expect(/\bupdateUtenteStatus\b/.test(page), 'UtentiPage deve usare updateUtenteStatus.')
expect(/\bupdateUtenteRole\b/.test(page), 'UtentiPage deve usare updateUtenteRole.')
expect(/\bresetUtentePassword\b/.test(page), 'UtentiPage deve usare resetUtentePassword.')
expect(/\bupdateUtenteProfile\b/.test(page), 'UtentiPage deve usare updateUtenteProfile.')
expect(/\bapiPostJson\b/.test(data), 'utentiData.ts deve usare apiPostJson.')
expect(!/\bapiPostJson\b/.test(page), 'UtentiPage non deve chiamare apiPostJson direttamente.')
for (const endpoint of [
  '@api_v1_react.post("/utenti/<id_utente>/stato")',
  '@api_v1_react.post("/utenti/<id_utente>/ruolo")',
  '@api_v1_react.post("/utenti/<id_utente>/reset-password")',
  '@api_v1_react.post("/utenti/<id_utente>/profilo")',
]) {
  expect(api.includes(endpoint), `api_v1_react.py deve contenere ${endpoint}.`)
}
expect(/["']writes["']\s*:\s*["']json_api["']/.test(bridge), 'react_utenti_bridge.py deve dichiarare writes json_api.')
expect(/operational["']?\s*:\s*True|operational["']?\s*:\s*true/.test(bridge), 'react_utenti_bridge.py deve dichiarare operational=true.')
expect(route?.status === 'react_operational_full', 'Il manifest deve marcare /utenti react_operational_full.')
expect(route?.unlockFromGate === true, 'Il manifest deve mantenere /utenti unlockFromGate=true.')
expect(routeNew?.status === 'react_operational_full', 'Il manifest deve mantenere /utenti/nuovo react_operational_full.')
expect(routeNew?.unlockFromGate === true, 'Il manifest deve mantenere /utenti/nuovo unlockFromGate=true.')
expect(!/\?_legacy=1/.test(page) || /Rollback tecnico/.test(page), 'Nessun uso primario di ?_legacy=1 in UtentiPage.')
expect(!/localStorage|sessionStorage/.test(combined), 'Utenti non deve usare localStorage o sessionStorage.')
expect(!/password_hash|reset_token|totp_secret|session_token|api_key/i.test(bridge), 'Il bridge non deve esporre hash password, token, TOTP secret o API key.')
expect(/users["']?\s*:/.test(bridge), 'Il payload /utenti deve esporre users.')
expect(/roles["']?\s*:/.test(bridge), 'Il payload /utenti deve esporre roles.')
expect(/canCreate/.test(bridge) && /canUpdate/.test(bridge) && /canDisable/.test(bridge), 'Il payload /utenti deve dichiarare permessi operativi.')
for (const state of ['loading', 'saving', 'success', 'error']) {
  expect(page.includes(state), `Stato UI mancante: ${state}.`)
}
for (const auditAction of ['utenti.modifica_stato', 'utenti.modifica_ruolo', 'utenti.reset_password', 'utenti.modifica_profilo']) {
  expect(bridge.includes(auditAction), `Audit mancante: ${auditAction}.`)
}

if (failures.length) {
  console.error(['Check tranche 14A utenti operativo fallito:', ...failures.map((failure) => `- ${failure}`)].join('\n'))
  process.exit(1)
}

console.log('Check tranche 14A utenti operativo OK.')

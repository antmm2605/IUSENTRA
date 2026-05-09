import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const failures = []

function read(path) {
  return readFileSync(resolve(root, path), 'utf8')
}

function assert(condition, message) {
  if (!condition) failures.push(message)
}

const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))
const route = (path) => manifest.routes.find((item) => item.route === path)
const studioPage = read('frontend/src/components/StudioPage.tsx')
const adminPage = read('frontend/src/components/AmministrazionePage.tsx')
const studioData = read('frontend/src/studioData.ts')
const adminData = read('frontend/src/amministrazioneData.ts')
const api = read('web/blueprints/api_v1_react.py')
const studioBridge = read('web/services/react_studio_bridge.py')
const adminBridge = read('web/services/react_amministrazione_bridge.py')
const gate = read('web/bootstrap/react_route_gate.py')
const combined = [studioPage, adminPage, studioData, adminData, studioBridge, adminBridge].join('\n')

assert(!/\bLegacyPostForm\b/.test(studioPage), 'StudioPage non deve usare LegacyPostForm.')
assert(!/\bLegacyPostForm\b/.test(adminPage), 'AmministrazionePage non deve usare LegacyPostForm.')
assert(!/\?_legacy=1/.test(studioPage), 'StudioPage non deve avere CTA legacy primaria.')
assert(!/\?_legacy=1/.test(adminPage), 'AmministrazionePage non deve avere CTA legacy primaria.')
assert(studioData.includes('/api/v1/ui/studio'), 'studioData.ts deve chiamare /api/v1/ui/studio.')
assert(adminData.includes('/api/v1/ui/amministrazione'), 'amministrazioneData.ts deve chiamare /api/v1/ui/amministrazione.')
assert(api.includes('@api_v1_react.get("/studio")'), 'api_v1_react.py deve contenere GET /studio.')
assert(api.includes('@api_v1_react.get("/amministrazione")'), 'api_v1_react.py deve contenere GET /amministrazione.')
assert(/["']operational["']\s*:\s*True/.test(studioBridge), 'react_studio_bridge.py deve dichiarare operational true.')
assert(/["']operational["']\s*:\s*True/.test(adminBridge), 'react_amministrazione_bridge.py deve dichiarare operational true.')
assert(/["']writes["']\s*:\s*["']none["']/.test(studioBridge), 'react_studio_bridge.py deve dichiarare writes none.')
assert(/["']writes["']\s*:\s*["']none["']/.test(adminBridge), 'react_amministrazione_bridge.py deve dichiarare writes none.')
assert(route('/studio')?.status === 'react_operational_full', '/studio deve essere react_operational_full nel manifest.')
assert(route('/amministrazione')?.status === 'react_operational_full', '/amministrazione deve essere react_operational_full nel manifest.')
for (const path of ['/sincronizzazione-calendari']) {
  assert(route(path)?.status === 'legacy_operational' && route(path)?.unlockFromGate === false, `${path} deve restare legacy.`)
}
for (const path of ['/impostazioni', '/impostazioni-studio']) {
  assert(route(path)?.status === 'react_operational_full' && route(path)?.unlockFromGate === true, `${path} deve risultare full React.`)
}
assert(gate.includes('if lower.startswith("/studio/"):'), 'Gate deve proteggere /studio/*.')
assert(gate.includes('if lower.startswith("/amministrazione/"):'), 'Gate deve proteggere /amministrazione/*.')
assert(gate.includes('if lower == "/impostazioni/calendario" or lower.startswith("/impostazioni/calendario/"):'), 'Gate deve proteggere impostazioni calendario.')
assert(!/localStorage|sessionStorage/.test(combined), 'Non deve usare localStorage/sessionStorage.')
assert(!/fetch\s*\(\s*["']https?:\/\//.test(combined), 'Non deve usare fetch esterni.')
assert(!/dangerouslySetInnerHTML/.test(combined), 'Non deve usare dangerouslySetInnerHTML.')
assert(!/\bapiPostJson\b/.test(studioData + adminData), 'Tranche 26a read-only: data client non devono usare apiPostJson.')

if (failures.length) {
  console.error(['Tranche 26a check FAILED:', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 26a studio/amministrazione operational OK.')

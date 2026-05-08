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
const page = read('frontend/src/components/SitoStudioPage.tsx')
const data = read('frontend/src/sitoStudioData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_sito_studio_bridge.py')
const gate = read('web/bootstrap/react_route_gate.py')
const combined = `${page}\n${data}\n${bridge}`

assert(!/\bLegacyPostForm\b/.test(page), 'SitoStudioPage non deve usare LegacyPostForm.')
assert(!/\?_legacy=1/.test(page) || /Rollback tecnico/.test(page), 'SitoStudioPage puo usare ?_legacy=1 solo in Rollback tecnico.')
assert(data.includes('/api/v1/ui/sito-studio'), 'sitoStudioData.ts deve chiamare /api/v1/ui/sito-studio.')
assert(data.includes('/api/v1/ui/sito-studio/contatti'), 'sitoStudioData.ts deve chiamare /api/v1/ui/sito-studio/contatti.')
assert(/\bapiPostJson\b/.test(data), 'sitoStudioData.ts deve usare apiPostJson per azioni contatti/prenotazioni supportate.')
assert(!/fetch\s*\(/.test(data), 'sitoStudioData.ts non deve usare fetch diretto.')
assert(api.includes('@api_v1_react.get("/sito-studio")'), 'api_v1_react.py deve contenere GET /sito-studio.')
assert(api.includes('@api_v1_react.get("/sito-studio/contatti")'), 'api_v1_react.py deve contenere GET /sito-studio/contatti.')
assert(api.includes('@api_v1_react.post("/sito-studio/contatti/<id_contatto>/collega")'), 'api_v1_react.py deve contenere POST contatti collegamento cliente supportato.')
assert(api.includes('@api_v1_react.post("/sito-studio/prenotazioni/<id_prenotazione>/stato")'), 'api_v1_react.py deve contenere POST prenotazioni stato supportato.')
assert(/["']writes["']\s*:\s*["']json_api["']|writes\s*=\s*["']json_api["']/.test(bridge), 'Bridge contatti deve dichiarare writes json_api.')
assert(/["']writes["']\s*:\s*["']none["']|writes\s*=\s*["']none["']/.test(bridge), 'Bridge dashboard sito deve dichiarare writes none.')
assert(/["']operational["']\s*:\s*True/.test(bridge), 'Bridge sito deve dichiarare operational true.')
assert(route('/sito-studio')?.status === 'react_operational_full', '/sito-studio deve essere react_operational_full nel manifest.')
assert(route('/sito-studio/contatti')?.status === 'react_operational_full', '/sito-studio/contatti deve essere react_operational_full nel manifest.')
assert(route('/sito-studio/builder')?.status === 'legacy_operational' && route('/sito-studio/builder')?.unlockFromGate === false, '/sito-studio/builder deve restare legacy.')
assert(gate.includes('if lower.startswith("/sito-studio/") and lower not in {"/sito-studio/contatti"}:'), 'Gate deve proteggere /sito-studio/* diversi da /contatti.')
assert(!/localStorage|sessionStorage/.test(combined), 'Non deve usare localStorage/sessionStorage.')
assert(!/fetch\s*\(\s*["']https?:\/\//.test(combined), 'Non deve usare fetch esterni.')
assert(!/dangerouslySetInnerHTML/.test(combined), 'Non deve usare dangerouslySetInnerHTML.')
assert(!/sendEmail|sendSms|sendWhatsApp|inviaEmail|inviaSms|inviaWhatsApp/i.test(page + data), 'React non deve introdurre invii notifiche.')
assert(/window\.confirm/.test(page), 'Le azioni distruttive/di esito devono richiedere conferma.')

if (failures.length) {
  console.error(['Tranche 27a check FAILED:', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 27a Sito Studio operational OK.')

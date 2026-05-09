import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const artifactDir = resolve(root, 'artifacts/react-migration')
mkdirSync(artifactDir, { recursive: true })

function read(path) {
  return readFileSync(resolve(root, path), 'utf8')
}

function assert(condition, message) {
  if (!condition) failures.push(message)
}

function assertContains(source, expected, message) {
  assert(source.includes(expected), `${message}: manca "${expected}"`)
}

function assertNotContains(source, pattern, message) {
  const found = typeof pattern === 'string' ? source.includes(pattern) : pattern.test(source)
  assert(!found, message)
}

const failures = []
const page = read('frontend/src/components/FatturazionePage.tsx')
const data = read('frontend/src/fatturazioneData.ts')
const api = read('web/blueprints/api_v1_react.py')
const bridge = read('web/services/react_fatturazione_bridge.py')
const gate = read('web/bootstrap/react_route_gate.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))
const combinedFrontend = `${page}\n${data}`

const nuova = (manifest.routes || []).find((entry) => entry.route === '/fatturazione/nuova')
const wildcard = (manifest.routes || []).find((entry) => entry.route === '/fatturazione/*')

assertNotContains(page, /\bLegacyPostForm\b/, 'FatturazionePage non deve usare LegacyPostForm')
assertContains(page, 'createFattura', 'FatturazionePage usa funzione di salvataggio JSON')
assertContains(data, 'apiPostJson<CreateFatturaResult>', 'fatturazioneData usa apiPostJson tipizzato')
assertContains(data, '/api/v1/ui/fatturazione/nuova', 'fatturazioneData punta endpoint nuova fatturazione')
assertContains(api, '@api_v1_react.post("/fatturazione/nuova")', 'api_v1_react contiene POST nuova fatturazione')
assertContains(api, 'def fatturazione_nuova_crea', 'api_v1_react registra handler POST nuova fatturazione')
assertContains(api, '_richiedi_auth', 'api_v1_react usa autenticazione')
assertContains(api, '_request_json_object()', 'api_v1_react accetta solo JSON nel POST operativo')
assertContains(api, '_puo_scrivere_fatturazione()', 'api_v1_react verifica permesso scrittura fatturazione')
assertContains(bridge, '"writes": "json_api"', 'bridge nuova fatturazione dichiara writes json_api')
assertContains(bridge, '"canonical_calculation": "backend"', 'bridge dichiara calcolo canonico backend')
assert(nuova?.status === 'react_operational_full', 'manifest deve marcare /fatturazione/nuova react_operational_full')
assert(nuova?.unlockFromGate === true, 'manifest deve sbloccare /fatturazione/nuova')
assert(wildcard?.status === 'legacy_operational' && wildcard?.unlockFromGate === false, 'manifest deve lasciare /fatturazione/* legacy_operational bloccato')
assertContains(page, 'Percorso di recupero', 'eventuali link ?_legacy=1 devono stare nel percorso di recupero governato')
assertNotContains(combinedFrontend, /\blocalStorage\b|\bsessionStorage\b/, 'frontend fatturazione non deve usare browser storage')
assertNotContains(combinedFrontend, /response\.blob|fetch\s*\([^)]*blob|URL\.createObjectURL|new Blob/i, 'frontend fatturazione non deve usare blob o object URL')
assertNotContains(combinedFrontend, /generatePdf|generatePDF|generateXml|generateXML|createPdf|createXml/i, 'React non deve generare PDF o XML')
assertNotContains(combinedFrontend, /calculateVat|calculateIva|calculateTax|calculateTotal|ivaRate|aliquotaIva|cassaRate|aliquotaCassa|ritenutaRate|Math\.round|\.toFixed\s*\(/i, 'frontend non deve contenere calcolo fiscale canonico')
assertContains(gate, 'lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"', 'gate protegge /fatturazione/* diverso da nuova')
assertNotContains(gate, '"/export/fatturazione.csv"', 'gate non deve sbloccare export fatturazione')
assertContains(page, 'saveStatus', 'UI mostra stato salvataggio')
assertContains(page, 'permission', 'UI mostra permesso negato')
assertContains(page, 'validation', 'UI mostra errori validazione')
assertContains(page, 'server', 'UI mostra errore server')
assertContains(page, 'success', 'UI mostra successo')
assertContains(page, 'LoadingState', 'UI mostra loading')

const md = [
  '# Check tranche 17A fatturazione nuova operational',
  '',
  `Generato: ${new Date().toISOString()}`,
  '',
  `Violazioni: ${failures.length}`,
  '',
  ...(failures.length ? failures.map((item) => `- ${item}`) : ['Tutti i controlli richiesti sono passati.']),
  '',
].join('\n')

writeFileSync(resolve(artifactDir, 'tranche-17a-fatturazione-nuova-operational-check.md'), md)

if (failures.length) {
  console.error(md)
  process.exit(1)
}

console.log('Tranche 17A fatturazione nuova operational OK.')

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

function functionBlock(source, name) {
  const start = source.indexOf(`def ${name}(`)
  if (start < 0) return ''
  const rest = source.slice(start)
  const next = rest.search(/\n@api_v1_react\./)
  return next > 0 ? rest.slice(0, next) : rest
}

const failures = []
const utentiPage = read('frontend/src/components/UtentiPage.tsx')
const utentiData = read('frontend/src/utentiData.ts')
const apiClient = read('frontend/src/lib/apiClient.ts')
const apiBridge = read('web/blueprints/api_v1_react.py')
const securityRuntime = read('web/services/security_runtime.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))
const route = (manifest.routes || []).find((entry) => entry.route === '/utenti/nuovo')
const endpointBlock = functionBlock(apiBridge, 'utenti_nuovo_crea')
const returnPayload = endpointBlock.slice(endpointBlock.lastIndexOf('return jsonify('))

assert(!/\bLegacyPostForm\b/.test(utentiPage), '/utenti/nuovo non deve usare LegacyPostForm nel componente principale.')
assert(utentiPage.includes('apiPostJson<CreateUserResponse>'), '/utenti/nuovo deve inviare tramite apiPostJson.')
assert(utentiData.includes('/api/v1/ui/utenti'), 'Utenti data client deve continuare a leggere endpoint JSON.')
assert(utentiPage.includes('/api/v1/ui/utenti/nuovo') || utentiPage.includes('data.createEndpoint'), '/utenti/nuovo deve usare endpoint JSON di creazione.')
assert(!/localStorage/i.test(utentiPage), '/utenti/nuovo non deve usare localStorage.')
assert(!/sessionStorage/i.test(utentiPage), '/utenti/nuovo non deve usare sessionStorage.')
assert(apiBridge.includes('@api_v1_react.post("/utenti/nuovo")'), 'Backend endpoint POST /api/v1/ui/utenti/nuovo mancante.')
assert(/@api_v1_react\.post\("\/utenti\/nuovo"\)\s*\n@_richiedi_auth\s*\ndef utenti_nuovo_crea/.test(apiBridge), 'Endpoint utenti nuovo deve usare _richiedi_auth.')
assert(endpointBlock.includes('_puo_scrivere_utenti()'), 'Endpoint utenti nuovo deve controllare permesso utenti.scrivi.')
assert(endpointBlock.includes('manager.crea('), 'Endpoint utenti nuovo deve riusare il manager utenti esistente.')
assert(endpointBlock.includes('manager.registra_evento('), 'Endpoint utenti nuovo deve produrre audit.')
assert(!/logger\.[a-z_]+\([^)]*password/i.test(endpointBlock), 'Endpoint utenti nuovo non deve loggare password.')
assert(!/"password"\s*:/.test(returnPayload), 'Endpoint utenti nuovo non deve restituire password.')
assert(securityRuntime.includes('"api_v1_react.utenti_nuovo_crea"'), 'Endpoint utenti nuovo deve essere nel presidio CSRF.')
assert(route?.status === 'react_operational_full', 'Manifest deve marcare /utenti/nuovo come react_operational_full.')
assert(route?.unlockFromGate === true, 'Manifest deve mantenere /utenti/nuovo sbloccata solo come route pilota operativa.')
assert((manifest.routes || []).every((entry) => entry.status !== 'react_full'), 'Il manifest non deve piu usare react_full.')
assert(apiClient.includes('credentials: \'same-origin\''), 'apiClient deve usare credentials same-origin.')
assert(apiClient.includes('meta[name="csrf-token"]'), 'apiClient deve leggere CSRF da meta[name="csrf-token"].')
assert(apiClient.includes('Content-Type\': \'application/json\''), 'apiClient deve inviare Content-Type application/json nei POST.')
assert(utentiPage.includes('iu-users-form-alert--success'), 'UI pilota deve gestire stato success.')
assert(utentiPage.includes('iu-users-form-alert--validation'), 'UI pilota deve gestire validation error.')
assert(utentiPage.includes('iu-users-form-alert--permission'), 'UI pilota deve gestire permission error.')
assert(utentiPage.includes('iu-users-form-alert--server'), 'UI pilota deve gestire server error.')
assert(utentiPage.includes('submitting ?'), 'UI pilota deve gestire loading.')

const md = [
  '# Check pilota anti-mascheramento',
  '',
  `Generato: ${new Date().toISOString()}`,
  '',
  `Esito: ${failures.length ? 'KO' : 'OK'}`,
  '',
  ...(failures.length ? failures.map((item) => `- ${item}`) : ['- /utenti/nuovo usa API JSON, CSRF, permessi, audit e UI React controllata.']),
  '',
].join('\n')

writeFileSync(resolve(artifactDir, 'anti-mascheramento-pilot-check.md'), md)

if (failures.length) {
  console.error(md)
  process.exit(1)
}

console.log('Check pilota anti-mascheramento OK.')

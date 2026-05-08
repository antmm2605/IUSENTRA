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

const bridge = [
  read('web/services/react_studio_bridge.py'),
  read('web/services/react_amministrazione_bridge.py'),
].join('\n')
const frontend = [
  read('frontend/src/components/StudioPage.tsx'),
  read('frontend/src/components/AmministrazionePage.tsx'),
  read('frontend/src/studioData.ts'),
  read('frontend/src/amministrazioneData.ts'),
].join('\n')
const forbiddenPayloadKey = /["'](password|pwd|api_key|apiKey|access_token|refresh_token|oauth_token|password_hash|provider_secret|webhook_secret|stack_trace|traceback|absolute_path|full_path)["']\s*:/i
const forbiddenRendered = /\b(password_hash|api_key|access_token|refresh_token|oauth_token|provider_secret|webhook_secret|stack_trace|traceback|absolute_path|full_path)\b/i

assert(!forbiddenPayloadKey.test(bridge), 'Bridge studio/amministrazione non devono serializzare chiavi sensibili.')
assert(!forbiddenRendered.test(frontend.replace(/SENSITIVE_KEY\s*=\s*\/.*?\n/s, '')), 'Frontend studio/amministrazione non deve renderizzare campi sensibili.')
assert(/["']secrets_exposed["']\s*:\s*False/.test(bridge), 'Contratti backend devono dichiarare secrets_exposed false.')
assert(!/\/impostazioni\/pagamenti.*provider|\/impostazioni\/calendario.*oauth/i.test(frontend), 'Frontend non deve esporre dettagli provider/OAuth.')
assert(!/localStorage|sessionStorage/.test(frontend), 'Frontend non deve usare storage browser.')
assert(!/dangerouslySetInnerHTML/.test(frontend), 'Frontend non deve renderizzare HTML raw.')

if (failures.length) {
  console.error(['Tranche 26a secret leak check FAILED:', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 26a no settings secret leak OK.')

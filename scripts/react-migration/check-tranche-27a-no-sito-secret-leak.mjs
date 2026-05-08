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

const bridge = read('web/services/react_sito_studio_bridge.py')
const frontend = [
  read('frontend/src/components/SitoStudioPage.tsx'),
  read('frontend/src/sitoStudioData.ts').replace(/SENSITIVE_KEY\s*=\s*\/.*?\n/s, ''),
].join('\n')
const forbiddenPayloadKey = /["'](password|pwd|api_key|apiKey|access_token|refresh_token|oauth_token|smtp_password|pec_password|password_hash|provider_secret|webhook_secret|stack_trace|traceback|absolute_path|full_path|raw_headers)["']\s*:/i
const forbiddenRendered = /\b(password_hash|api_key|access_token|refresh_token|oauth_token|smtp_password|pec_password|provider_secret|webhook_secret|stack_trace|traceback|absolute_path|full_path|raw_headers)\b/i

assert(!forbiddenPayloadKey.test(bridge), 'Bridge Sito Studio non deve serializzare chiavi sensibili.')
assert(!forbiddenRendered.test(frontend), 'Frontend Sito Studio non deve renderizzare campi sensibili.')
assert(!/localStorage|sessionStorage/.test(frontend), 'Frontend Sito Studio non deve usare storage browser.')
assert(!/fetch\s*\(\s*["']https?:\/\//.test(frontend), 'Frontend Sito Studio non deve fare fetch esterni.')
assert(!/dangerouslySetInnerHTML/.test(frontend), 'Frontend Sito Studio non deve renderizzare HTML raw.')
assert(!/sendEmail|sendSms|sendWhatsApp|inviaEmail|inviaSms|inviaWhatsApp/i.test(frontend), 'Frontend Sito Studio non deve introdurre notifiche.')
assert(!/request\.headers|remote_addr/.test(bridge), 'Bridge Sito Studio non deve esporre IP o raw headers nel payload React.')

if (failures.length) {
  console.error(['Tranche 27a secret leak check FAILED:', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 27a no Sito Studio secret leak OK.')

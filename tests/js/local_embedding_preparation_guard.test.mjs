import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'

// Verifica il trasporto, senza contatti di rete o avvio del servizio locale.
const calls = []
const originalFetch = async (url) => {
  calls.push(url)
  return new Response(JSON.stringify(url.endsWith('/ping') ? { ok: true }
    : url.includes('preparazione=1') ? { status_payload: { preparation: { present: true } } }
    : { runtime_online: true, resolved_models: { embed: 'embeddinggemma:300m' } }))
}
const window = { fetch: originalFetch, location: { origin: 'http://127.0.0.1:8080' } }
vm.runInNewContext(readFileSync(new URL('../../web/static/js/react-ai-local-guard.js', import.meta.url), 'utf8'), {
  window, URL, Response,
  document: { getElementById: () => null, addEventListener: () => {} },
})
const preparation = await window.fetch('/api/v1/ui/impostazioni/ai/status?preparazione=1')
assert.equal((await preparation.json()).status_payload.preparation.present, true)
assert.deepEqual(calls, ['/api/v1/ui/impostazioni/ai/status?preparazione=1'])
calls.length = 0
const status = await window.fetch('/api/v1/ui/impostazioni/ai/status')
assert.equal((await status.json()).status_payload.resolved_models.embed, 'embeddinggemma:300m')
assert.deepEqual(calls, ['http://127.0.0.1:27272/ping', 'http://127.0.0.1:27272/ai/status'])
console.log('Preparazione nel repository locale e stato PC mantenuto: OK')

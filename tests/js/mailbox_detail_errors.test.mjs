// Guardrail tecnico: l'accettazione resta nel browser reale.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { fetchMailboxDetailJson } from '../../frontend/src/emailDetailRequest.ts'
const { getEmailOrdinariaDetail, getEmailPecDetail, getEmailPecSourceDetail } = await import('../../frontend/src/emailData.ts')
const savedFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = savedFetch })
const response = (status, payload) => ({ status, ok: status >= 200 && status < 300, json: async () => payload })

test('fonte presente: conserva identificativo, testo e opzioni della richiesta', async () => {
  globalThis.fetch = async (url, options) => {
    assert.match(url, /^\/fonte\?_ts=\d+$/)
    assert.equal(options.credentials, 'same-origin')
    assert.equal(options.cache, 'no-store')
    return response(200, { ok: true, item: { id: 'controlled-id', corpo_testo: 'Testo completo' } })
  }
  assert.equal((await fetchMailboxDetailJson('/fonte')).item.id, 'controlled-id')
})
test('solo HTTP 404 rappresenta una fonte mancante', async () => {
  globalThis.fetch = async () => response(404, {})
  assert.equal(await fetchMailboxDetailJson('/fonte'), null)
  assert.equal((await getEmailOrdinariaDetail('controlled-id')).item, null)
})
for (const [status, message] of [[401, /sessione è scaduta/], [403, /permesso/], [500, /caricare il messaggio/], [503, /caricare il messaggio/]]) {
  test(`HTTP ${status}: errore controllato senza dichiarare fonte rimossa`, async () => {
    globalThis.fetch = async () => response(status, { errore: 'SQL private diagnostic' })
    await assert.rejects(fetchMailboxDetailJson('/fonte'), message)
  })
}
for (const payload of [null, [], { ok: false }, {}]) {
  test(`risposta incompleta ${JSON.stringify(payload)} non crea messaggi inventati`, async () => {
    globalThis.fetch = async () => response(200, payload)
    await assert.rejects(getEmailOrdinariaDetail('controlled-id'))
  })
}
test('HTML e interruzioni di rete non diventano una casella vuota', async () => {
  globalThis.fetch = async () => ({ status: 200, ok: true, json: async () => { throw new SyntaxError('private HTML') } })
  await assert.rejects(getEmailOrdinariaDetail('controlled-id'), /connessione/)
  globalThis.fetch = async () => { throw new Error('private network') }
  await assert.rejects(getEmailOrdinariaDetail('controlled-id'), /connessione/)
})
for (const item of [{}, { id: '' }, 'invalid']) {
  test(`dettaglio privo di identificativo ${JSON.stringify(item)} rifiutato`, async () => {
    globalThis.fetch = async () => response(200, { item })
    await assert.rejects(getEmailOrdinariaDetail('controlled-id'), /dati del messaggio/)
  })
}
test('PEC audit priva di identificativo rifiutata anche nel lettore fonte', async () => {
  globalThis.fetch = async () => response(200, { data: { message: {} } })
  await assert.rejects(getEmailPecDetail('pec-audit:controlled-id'), /dati della PEC/)
  await assert.rejects(getEmailPecSourceDetail('pec-audit:controlled-id'), /dati della PEC/)
})
test('fonte temporaneamente occupata: riprova e conserva la risposta autentica', async () => {
  let attempts = 0
  globalThis.fetch = async () => ++attempts === 1 ? response(423, {}) : response(200, { ok: true, data: { message: { id: 'controlled-id' } } })
  assert.equal((await fetchMailboxDetailJson('/fonte', true)).data.message.id, 'controlled-id')
  assert.equal(attempts, 2)
})
test('permesso negato non viene riprovato', async () => {
  let attempts = 0
  globalThis.fetch = async () => { attempts += 1; return response(403, {}) }
  await assert.rejects(fetchMailboxDetailJson('/fonte', true), /permesso/)
  assert.equal(attempts, 1)
})

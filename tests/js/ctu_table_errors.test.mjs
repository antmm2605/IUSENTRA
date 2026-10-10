import { afterEach, test } from 'node:test'
import assert from 'node:assert/strict'
const { loadCtuTable } = await import('../../frontend/src/ctuTableData.ts')
const savedFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = savedFetch })
const row = { value: '1', label: 'Voce controllata', tipo: 'fisso', base: '', unita: '' }
const response = (status, payload) => ({ status, ok: status >= 200 && status < 300, json: async () => payload })

test('tabella autentica: conserva le voci e propaga cancellazione della richiesta', async () => {
  const controller = new AbortController()
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/ui/ctu/tabella')
    assert.equal(options.signal, controller.signal)
    assert.equal(options.credentials, 'same-origin')
    assert.equal(options.cache, 'no-store')
    return response(200, { ok: true, voci: [row] })
  }
  assert.deepEqual(await loadCtuTable(controller.signal), [row])
})
for (const status of [401, 403, 500, 503]) {
  test(`HTTP ${status} non simula una tabella vuota`, async () => {
    globalThis.fetch = async () => response(status, { message: 'private SQL diagnostic' })
    await assert.rejects(loadCtuTable(), (error) => !error.message.includes('private') && error.message.length > 20)
  })
}
for (const payload of [null, {}, { ok: false, voci: [row] }, { ok: true, voci: [] },
  { ok: true, voci: [null] }, { ok: true, voci: [{ ...row, value: '' }] },
  { ok: true, voci: [{ ...row, tipo: null }] }, { ok: true, voci: [row, row] }]) {
  test(`dati incompleti rifiutati: ${JSON.stringify(payload)}`, async () => {
    globalThis.fetch = async () => response(200, payload)
    await assert.rejects(loadCtuTable())
  })
}
test('HTML o rete interrotta mostrano un errore recuperabile', async () => {
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('private HTML') } })
  await assert.rejects(loadCtuTable(), /Connessione.*bozza è conservata/)
  globalThis.fetch = async () => { throw new Error('private socket') }
  await assert.rejects(loadCtuTable(), /Connessione/)
})
test('richiesta annullata non sostituisce la causa con un errore di connessione', async () => {
  const controller = new AbortController()
  controller.abort()
  const error = new Error('controlled abort')
  globalThis.fetch = async () => { throw error }
  await assert.rejects(loadCtuTable(controller.signal), (actual) => actual === error)
})

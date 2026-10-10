// Guardrail del contratto; l'accettazione richiede il browser reale su 8080.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getScadenziarioPage } from '../../frontend/src/scadenziarioData.ts'
const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
for (const status of [401, 403, 500, 503]) test(`HTTP ${status}: nessun elenco vuoto confermato`, async () => {
  let requests = 0
  globalThis.fetch = async () => { requests++; return { ok: false, status } }
  await assert.rejects(getScadenziarioPage(), /Scadenziario non caricato/)
  assert.equal(requests, 1)
})
for (const payload of [{}, { ok: false, items: [] }, null]) test(`contratto rifiutato ${JSON.stringify(payload)}`, async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => payload })
  await assert.rejects(getScadenziarioPage(), /Risposta dello scadenziario non valida/)
})
test('rete e HTML non diventano uno scadenziario vuoto', async () => {
  globalThis.fetch = async () => { throw new Error('Rete interrotta') }
  await assert.rejects(getScadenziarioPage(), /Rete interrotta/)
  globalThis.fetch = async () => ({ ok: true, json: async () => { throw new SyntaxError('HTML') } })
  await assert.rejects(getScadenziarioPage(), /HTML/)
})
test('elenco realmente vuoto e provenienza CTU conservati', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ items: [], source: 'repository_reali', draftProposals: [
    { id: 'CTU1', sourceOrigin: 'ctu', sourceOriginLabel: 'Incarico CTU' },
    { id: 'UNKNOWN', sourceOrigin: '' },
  ] }) })
  const result = await getScadenziarioPage()
  assert.deepEqual(result.items, [])
  assert.equal(result.source, 'repository_reali')
  assert.equal(result.draftProposals[0].sourceOrigin, 'ctu')
  assert.equal(result.draftProposals[1].sourceOrigin, 'interno')
  assert.equal(result.draftProposals[1].sourceOriginLabel, 'Registro interno')
})

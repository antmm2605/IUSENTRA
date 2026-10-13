// Guardrail del comando HTTP; l'accettazione resta nel browser reale 8080.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { updateFascicoloPayment, runFascicoliEconomicPresidio } from '../../frontend/src/fascicoliData.ts'

const originalFetch = globalThis.fetch
const originalDocument = globalThis.document
afterEach(() => {
  globalThis.fetch = originalFetch
  if (originalDocument === undefined) delete globalThis.document
  else globalThis.document = originalDocument
})

test('il controllo automatico conserva il perimetro dei fascicoli visualizzati', async () => {
  globalThis.document = { querySelector: () => null }
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) })
    return { ok: true, json: async () => ({ ok: true, createdCount: 0 }) }
  }
  await runFascicoliEconomicPresidio(100, ['controlled-case'])
  assert.equal(requests.length, 1)
  assert.deepEqual(requests[0].body, { limit: 100, fascicolo_ids: ['controlled-case'] })
  assert.equal(requests[0].body.prepare_proformas, undefined)
})

for (const confirmed of [true, false]) test(`il comando conserva conferma=${confirmed} e l'impronta delle fonti`, async () => {
  globalThis.document = { querySelector: () => ({ content: 'controlled-csrf' }) }
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options, body: JSON.parse(options.body) })
    return { ok: true, headers: { get: () => 'application/json' }, json: async () => ({
      ok: true, payment: { kind: 'fondo_spese', importo: 250 }, paymentSummary: {},
    }) }
  }
  await updateFascicoloPayment('controlled-case', 'fondo_spese', {
    status: 'da_registrare', importo: '250,00', note: 'Decisione controllata',
    confermaDiscordanza: confirmed, discordanzaVersione: 'a'.repeat(64),
  })
  assert.equal(requests.length, 1)
  assert.equal(requests[0].url, '/api/v1/ui/fascicoli/controlled-case/pagamenti/fondo_spese')
  assert.equal(requests[0].body.confermaDiscordanza, confirmed)
  assert.equal(requests[0].body.discordanzaVersione, 'a'.repeat(64))
  assert.equal(requests[0].body.importo, '250,00')
  assert.equal(requests[0].options.headers['X-CSRFToken'], 'controlled-csrf')
})

test('fonti cambiate: il comando non ritenta né dichiara il salvataggio', async () => {
  globalThis.document = { querySelector: () => null }
  let calls = 0
  globalThis.fetch = async () => {
    calls += 1
    return { ok: false, status: 409, headers: { get: () => 'application/json' }, json: async () => ({
      ok: false, conflict: true, message: 'Le fonti sono cambiate: rileggi le evidenze prima di confermare l’importo.',
    }) }
  }
  await assert.rejects(updateFascicoloPayment('controlled-case', 'fondo_spese', {
    status: 'da_registrare', importo: 250, confermaDiscordanza: true, discordanzaVersione: 'old',
  }), /Le fonti sono cambiate/)
  assert.equal(calls, 1)
})

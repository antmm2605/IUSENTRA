// Guardrail tecnici successivi alla prova materiale dei filtri della posta.
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getEmailPecPage } from '../../frontend/src/emailData.ts'

const nativeFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = nativeFetch })
const payload = {
  source: 'repository_reali', items: [],
  summary: { total: 100, filtered: 34, autoLinked: 34 },
  facets: {
    folders: [{ value: 'TUTTE', label: 'Tutte', count: 100 }],
    pctStatuses: [{ value: '', label: 'Tutti gli esiti', count: 100 }, { value: 'CONSEGNATO', label: 'Consegnato', count: 15 }],
  },
}

test('il selettore mantiene Tutti gli esiti come valore valido', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => payload })
  const result = await getEmailPecPage()
  assert.deepEqual(result.facets.pctStatuses, payload.facets.pctStatuses)
  assert.deepEqual(result.facets.folders, payload.facets.folders)
})

test('i filtri e la paginazione arrivano insieme alla ricerca nativa', async () => {
  let observed
  globalThis.fetch = async (url, options) => {
    observed = { url: new URL(url, 'http://localhost'), options }
    return { ok: true, json: async () => payload }
  }
  await getEmailPecPage({ folder: 'TUTTE', collegate: true, offset: 80, limit: 80, statoPct: 'CONSEGNATO', q: '  ricerca  ' })
  for (const [key, value] of Object.entries({ cartella: 'TUTTE', collegate: '1', offset: '80', limit: '80', stato_pct: 'CONSEGNATO', q: 'ricerca' })) {
    assert.equal(observed.url.searchParams.get(key), value)
  }
  assert.equal(observed.options.cache, 'no-store')
  assert.equal(observed.options.credentials, 'same-origin')
})

test('il totale del catalogo non viene ricavato dalla sola pagina caricata', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => payload })
  const result = await getEmailPecPage()
  assert.equal(result.summary.total, 100)
  assert.equal(result.summary.filtered, 34)
  assert.equal(result.summary.autoLinked, 34)
})

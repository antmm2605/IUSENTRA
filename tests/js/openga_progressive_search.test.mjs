// Guardrail dell'orchestrazione; la prova visibile resta sulla copia reale 8080.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { searchOpenGA } from '../../frontend/src/opengaSearch.ts'
import { getActivities } from '../../frontend/src/ui/activity.ts'
const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
const rapid = { ok: true, risultati: [{ relazione_id: 'rapida' }] }
const deep = { ok: true, semantic_available: true, risultati: [{ relazione_id: 'approfondita' }] }
const query = { q: 'permesso soggiorno', dal: '2023', al: '2023', semantica: true }
const response = data => ({ ok: true, headers: new Headers({ 'Content-Type': 'application/json' }), json: async () => data })

test('la rapida arriva prima della risposta approfondita e non blocca la lettura', async () => {
  const calls = []; const events = []; let finishDeep; let deepStarted
  const started = new Promise(resolve => { deepStarted = resolve })
  globalThis.fetch = async (_url, init) => {
    calls.push(JSON.parse(init.body))
    if (calls.length === 1) return response(rapid)
    deepStarted(); return new Promise(resolve => { finishDeep = () => resolve(response(deep)) })
  }
  const done = searchOpenGA(query, new AbortController().signal, r => events.push(['rapid', r]), r => events.push(['deep', r]))
  await started
  assert.deepEqual(events, [['rapid', rapid]])
  assert.deepEqual(calls, [{ ...query, semantica: false }, query])
  assert.equal(getActivities().length, 0)
  finishDeep(); await done
  assert.deepEqual(events, [['rapid', rapid], ['deep', deep]])
})

test('errore approfondito conserva la prima consegna e dichiara il guasto', async () => {
  let n = 0; const events = []
  globalThis.fetch = async () => { if (++n === 1) return response(rapid); throw new Error('rete') }
  await searchOpenGA(query, new AbortController().signal, r => events.push(r), r => events.push(r))
  assert.equal(events[0], rapid); assert.equal(events[1].ok, false)
  assert.match(events[1].message, /non disponibile/)
})

test('nessun approfondimento se rapida negata e nessun risultato tardivo dopo uscita', async () => {
  let calls = 0; const events = []
  globalThis.fetch = async () => { calls++; return response({ ok: false, risultati: [] }) }
  await searchOpenGA(query, new AbortController().signal, r => events.push(r), r => events.push(r))
  assert.equal(calls, 1); assert.equal(events.length, 1)
  const controller = new AbortController()
  globalThis.fetch = async () => { controller.abort(); return response(rapid) }
  await searchOpenGA(query, controller.signal, () => assert.fail('risposta tardiva'), () => assert.fail('risposta tardiva'))
})

test('modalità rapida richiede un solo canale e snapshot invariato', async () => {
  let calls = 0; const events = []
  globalThis.fetch = async () => { calls++; return response(rapid) }
  const snapshot = { ...query, semantica: false }
  await searchOpenGA(snapshot, new AbortController().signal, r => events.push(r), () => assert.fail('canale non richiesto'))
  assert.equal(calls, 1); assert.deepEqual(events, [rapid]); assert.equal(snapshot.semantica, false)
})

test('i conteggi corpus attraversano il contratto frontend senza diventare schede interne', async () => {
  const { getGiurisprudenzaPage } = await import('../../frontend/src/giurisprudenzaData.ts')
  globalThis.fetch = async () => response({ sources: [
    { id: 'corte_costituzionale', count: 0, corpusCount: 22407, corpusFullTextCount: 22407 },
    { id: 'cassazione', count: 0, corpusCount: null },
  ] })
  const page = await getGiurisprudenzaPage()
  assert.equal(page.sources[0].count, 0)
  assert.equal(page.sources[0].corpusCount, 22407)
  assert.equal(page.sources[1].corpusCount, null)
})

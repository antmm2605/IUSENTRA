import test from 'node:test'
import assert from 'node:assert/strict'
import { beginActivity, getActivities, subscribeActivities, withActivity } from '../../frontend/src/ui/activity.ts'
import { apiJson, ensureJson } from '../../frontend/src/api/client.ts'

test('concurrent operations stay visible until each owner finishes', () => {
  const finishFirst = beginActivity('Lettura cliente')
  const finishSecond = beginActivity('Salvataggio documento')
  assert.equal(getActivities().length, 2)
  finishFirst()
  finishFirst()
  assert.deepEqual(getActivities().map(item => item.label), ['Salvataggio documento'])
  finishSecond()
  assert.equal(getActivities().length, 0)
})

test('rejected and background work do not leave a false busy state', async () => {
  await withActivity(false, async () => assert.equal(getActivities().length, 0))
  await assert.rejects(withActivity('Lettura documento', async () => { throw new Error('Fonte indisponibile') }))
  assert.equal(getActivities().length, 0)
})

test('the activity covers response body parsing, not only response headers', async () => {
  const originalFetch = globalThis.fetch
  let releaseBody
  globalThis.fetch = async () => ({
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => new Promise(resolve => { releaseBody = resolve }),
  })
  try {
    const pending = ensureJson('/api/v1/ui/clienti', { activity: 'Lettura clienti' })
    await new Promise(resolve => setImmediate(resolve))
    assert.deepEqual(getActivities().map(item => item.label), ['Lettura clienti'])
    releaseBody({ clienti: [] })
    assert.deepEqual(await pending, { clienti: [] })
    assert.equal(getActivities().length, 0)
  } finally { globalThis.fetch = originalFetch }
})

test('cancellation remains an AbortError and removes only the cancelled operation', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => { throw new DOMException('Cancelled', 'AbortError') }
  const otherFinish = beginActivity('Conversione PDF')
  try {
    await assert.rejects(apiJson('/api/v1/ui/clienti', {}), { name: 'AbortError' })
    assert.deepEqual(getActivities().map(item => item.label), ['Conversione PDF'])
  } finally { otherFinish(); globalThis.fetch = originalFetch }
})

test('HTTP and network failures preserve the client contract and clear the indicator', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response('{}', { status: 503, headers: { 'content-type': 'application/json' } })
    await assert.rejects(ensureJson('/api/v1/ui/clienti'))
    assert.equal(getActivities().length, 0)
    globalThis.fetch = async () => { throw new TypeError('Network unavailable') }
    assert.deepEqual(await apiJson('/api/v1/ui/clienti', { ok: false }), { ok: false })
    assert.equal(getActivities().length, 0)
  } finally { globalThis.fetch = originalFetch }
})

test('unmounted subscribers no longer receive updates', () => {
  let calls = 0
  const unsubscribe = subscribeActivities(() => { calls += 1 })
  const finish = beginActivity('Caricamento pagina')
  unsubscribe()
  finish()
  assert.equal(calls, 1)
})

test('studio and statistics background bodies preserve a concurrent foreground owner', async () => {
  const { getStudioPage } = await import('../../frontend/src/studioData.ts')
  const { getStatistichePage } = await import('../../frontend/src/statisticheData.ts')
  const originalFetch = globalThis.fetch
  const bodies = []
  const finishUser = beginActivity('Modifica controllata')
  globalThis.fetch = async () => ({
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => new Promise(resolve => bodies.push(() => resolve({
      ok: true, source: 'sql', metrics: [], sections: [], records: [],
    }))),
  })
  try {
    const pending = Promise.all([getStudioPage({ activity: false }), getStatistichePage({ activity: false })])
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(bodies.length, 2)
    assert.deepEqual(getActivities().map(item => item.label), ['Modifica controllata'])
    bodies[0]()
    await new Promise(resolve => setImmediate(resolve))
    assert.deepEqual(getActivities().map(item => item.label), ['Modifica controllata'])
    bodies[1]()
    await pending
    assert.deepEqual(getActivities().map(item => item.label), ['Modifica controllata'])
  } finally { finishUser(); globalThis.fetch = originalFetch }
})


test('live telematic refresh stays silent through both response bodies without hiding a user operation', async () => {
  const { getTelematicoPage, getTelematicoCases } = await import('../../frontend/src/telematicoData.ts')
  const originalFetch = globalThis.fetch
  const bodies = []
  const finishUser = beginActivity('Salvataggio controllato')
  globalThis.fetch = async url => ({
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => new Promise(resolve => bodies.push(() => resolve(String(url).includes('/pratiche')
      ? { items: [], total: 0, page: 1, pageSize: 1, pages: 0 } : {}))),
  })
  try {
    const pending = Promise.all([
      getTelematicoPage({ activity: false }),
      getTelematicoCases('', '', 1, undefined, 1, true, { activity: false }),
    ])
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(bodies.length, 2)
    assert.deepEqual(getActivities().map(item => item.label), ['Salvataggio controllato'])
    bodies[0]()
    await new Promise(resolve => setImmediate(resolve))
    assert.deepEqual(getActivities().map(item => item.label), ['Salvataggio controllato'])
    bodies[1]()
    await pending
    assert.deepEqual(getActivities().map(item => item.label), ['Salvataggio controllato'])
  } finally { finishUser(); globalThis.fetch = originalFetch }
})

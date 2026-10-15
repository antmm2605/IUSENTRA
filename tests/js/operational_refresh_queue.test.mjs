import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createOperationalRefreshQueue } from '../../frontend/src/operationalRefreshQueue.ts'
import { changedRevisionDomains, coversRevisionProof, normalizeRevisionProof, sharedRevisionProof } from '../../frontend/src/operationalRevisionProof.ts'

const flush = async () => { for (let i = 0; i < 5; i++) await Promise.resolve() }

test('unscoped messages from older windows cannot certify or postpone server polling', () => {
  assert.equal(sharedRevisionProof({ fascicoli: 4 }, undefined), undefined)
  assert.equal(sharedRevisionProof({ fascicoli: -1 }, 'a'.repeat(64)), undefined)
  assert.deepEqual(sharedRevisionProof({ fascicoli: 4 }, 'a'.repeat(64)), {
    revisions: { fascicoli: 4 }, context: 'a'.repeat(64),
  })
})

test('older windows without a context do not simulate a tenant change or suppress a real update', () => {
  const previous = { fascicoli: 4, agenda: 2 }
  const scope = 'a'.repeat(64)
  assert.deepEqual(changedRevisionDomains(previous, { ...previous }, ['fascicoli', 'agenda'], scope, undefined), [])
  assert.deepEqual(changedRevisionDomains(previous, { ...previous }, ['fascicoli', 'agenda'], undefined, scope), [])
  assert.deepEqual(changedRevisionDomains(previous, { fascicoli: 5, agenda: 2 }, ['fascicoli', 'agenda'], scope, undefined), ['fascicoli'])
  assert.deepEqual(changedRevisionDomains(previous, { ...previous }, ['fascicoli', 'agenda'], scope, 'b'.repeat(64)), ['fascicoli', 'agenda'])
})

test('only the same complete revision and owner can cover a notified change', () => {
  const current = { fascicoli: 4, agenda: 2 }
  const scope = 'a'.repeat(64)
  assert.equal(coversRevisionProof(current, { ...current }, ['fascicoli', 'agenda'], scope, scope), true)
  assert.equal(coversRevisionProof(current, { fascicoli: 5, agenda: 2 }, ['fascicoli', 'agenda'], scope, scope), false)
  assert.equal(coversRevisionProof(current, { fascicoli: 3, agenda: 2 }, ['fascicoli', 'agenda'], scope, scope), false)
  assert.equal(coversRevisionProof(current, current, ['fascicoli', 'agenda'], scope, 'b'.repeat(64)), false)
  assert.equal(coversRevisionProof(current, { fascicoli: 4 }, ['fascicoli', 'agenda'], scope, scope), false)
  assert.equal(coversRevisionProof(current, current, ['fascicoli', 'agenda']), false)
  for (const value of [{}, [], { fascicoli: -1 }, { fascicoli: NaN }, { fascicoli: '4' }]) {
    assert.equal(normalizeRevisionProof(value), undefined)
  }
})

test('ambiguous revision notifications still require a read, without losing the live intent', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const requests = []
  const scope = 'a'.repeat(64)
  const queue = createOperationalRefreshQueue(intent => { requests.push(intent) }, () => {})
  queue.schedule({ live: true, revisions: { fascicoli: 4 }, revisionContext: scope })
  queue.schedule({ live: true })
  queue.schedule({ live: true, revisions: { fascicoli: 4 }, revisionContext: scope })
  t.mock.timers.tick(120); await flush()
  assert.equal(requests[0].live, true)
  assert.equal(requests[0].revisions, undefined)
  queue.schedule({ live: true, revisions: { fascicoli: 4 }, revisionContext: scope })
  queue.schedule({ live: true, revisions: { fascicoli: 4 }, revisionContext: 'b'.repeat(64) })
  t.mock.timers.tick(120); await flush()
  assert.equal(requests[1].revisions, undefined)
  queue.dispose()
})

test('targeted commands and live updates share a queue without widening a targeted request', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const intents = []
  const queue = createOperationalRefreshQueue(intent => { intents.push(intent.live) }, () => {})
  queue.schedule(); t.mock.timers.tick(120); await flush()
  assert.deepEqual(intents, [false])
  queue.schedule(); queue.schedule({ live: true }); queue.schedule()
  t.mock.timers.tick(120); await flush()
  assert.deepEqual(intents, [false, true])
  queue.dispose()
})

test('a live invalidation received during a targeted request survives a failed follow-up', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let release
  const intents = []
  const queue = createOperationalRefreshQueue(intent => {
    intents.push(intent.live)
    if (intents.length === 1) return new Promise(resolve => { release = resolve })
    if (intents.length === 2) throw new Error('connection lost')
  }, () => {})
  queue.schedule(); t.mock.timers.tick(120)
  queue.schedule({ live: true })
  release(); await flush(); t.mock.timers.tick(120); await flush()
  t.mock.timers.tick(1000); await flush()
  assert.deepEqual(intents, [false, true, true])
  queue.dispose()
})

test('an update arriving during a request is delivered afterwards without overlapping requests', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let release
  let calls = 0
  const statuses = []
  const queue = createOperationalRefreshQueue(() => {
    calls += 1
    if (calls === 1) return new Promise(resolve => { release = resolve })
  }, failed => statuses.push(failed))
  queue.schedule(); queue.schedule(); t.mock.timers.tick(120)
  assert.equal(calls, 1)
  queue.schedule(); t.mock.timers.tick(1000)
  assert.equal(calls, 1)
  release(); await flush(); t.mock.timers.tick(120); await flush()
  assert.equal(calls, 2)
  assert.deepEqual(statuses, [false, false])
  queue.dispose()
})

test('failure is visible, recovery is bounded, a new event resumes and confirms recovery', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let calls = 0
  let fail = true
  const statuses = []
  const queue = createOperationalRefreshQueue(() => { calls += 1; if (fail) throw new Error('offline') }, value => statuses.push(value))
  queue.schedule(); t.mock.timers.tick(120); await flush()
  t.mock.timers.tick(1000); await flush()
  t.mock.timers.tick(2000); await flush()
  t.mock.timers.tick(30000); await flush()
  assert.equal(calls, 3)
  assert.deepEqual(statuses, [true, true, true])
  fail = false; queue.schedule(); t.mock.timers.tick(120); await flush()
  assert.equal(calls, 4)
  assert.equal(statuses.at(-1), false)
  queue.dispose()
})

test('disposing a view prevents scheduled requests and late status updates', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let release
  const statuses = []
  const queue = createOperationalRefreshQueue(() => new Promise(resolve => { release = resolve }), value => statuses.push(value))
  queue.schedule(); t.mock.timers.tick(120)
  queue.dispose(); release(); await flush()
  queue.schedule(); t.mock.timers.tick(30000)
  assert.deepEqual(statuses, [])
})

test('a loader that handles its own error still reports failure and later recovery', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let confirmed = false
  const statuses = []
  const queue = createOperationalRefreshQueue(async () => confirmed, value => statuses.push(value))
  queue.schedule(); t.mock.timers.tick(120); await flush()
  assert.deepEqual(statuses, [true])
  confirmed = true
  t.mock.timers.tick(1000); await flush()
  assert.deepEqual(statuses, [true, false])
  queue.dispose()
})

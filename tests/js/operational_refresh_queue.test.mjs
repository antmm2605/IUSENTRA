import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createOperationalRefreshQueue } from '../../frontend/src/operationalRefreshQueue.ts'

const flush = async () => { for (let i = 0; i < 5; i++) await Promise.resolve() }

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

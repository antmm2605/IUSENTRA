import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { runStudioTelematicoImport, getStudioTelematicoImportProgress } from '../../frontend/src/quickOrganizerImportData.ts'
const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('la selezione e le associazioni arrivano intatte al server e i fascicoli invariati restano distinti', async () => {
  const selection = { matterIds: ['101'], documents: true, emails: false, appointments: false, unassigned: true, excludedIds: ['TESTI:2'], fileAssignments: { 'FILE:8': '101' } }
  let received
  globalThis.fetch = async (url, init) => {
    received = JSON.parse(init.body)
    return Response.json({ ok: true, complete: false, summary: { mattersUnchanged: 7, mattersUpdated: 0 }, recovery: { pending: [{ name: 'originale.pdf', reason: 'Da associare' }] } })
  }
  const result = await runStudioTelematicoImport('/api/v1/ui/import/quickorganizer/esegui', 'a'.repeat(32), true, selection, false, 'b'.repeat(64))
  assert.deepEqual(received.selection, selection)
  assert.equal(received.sourceSha256, 'b'.repeat(64))
  assert.equal(received.analyzeUnassigned, false)
  assert.equal(result.summary.mattersUnchanged, 7)
  assert.equal(result.summary.mattersUpdated, 0)
  assert.equal(result.complete, false)
  assert.equal(result.recovery.pending.length, 1)
})

test('una caduta di rete non dichiara successo e non ritenta automaticamente', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; throw new TypeError('offline') }
  const result = await runStudioTelematicoImport('', 'a'.repeat(32), false)
  assert.equal(calls, 1)
  assert.equal(result.ok, false)
  assert.equal(result.complete, false)
  assert.match(result.errore, /server deve essere verificato/)
})

test('progresso non disponibile resta sconosciuto, non completo', async () => {
  globalThis.fetch = async () => new Response('', { status: 503 })
  const result = await getStudioTelematicoImportProgress('a'.repeat(32))
  assert.equal(result.ok, false)
  assert.equal(result.status, 'unknown')
})

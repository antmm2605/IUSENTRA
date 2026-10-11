import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyCatalogueResponse } from '../../frontend/src/components/codiciLeggiResults.ts'

test('un cambio codice mantiene la nuova scelta anche con risposta obsoleta in arrivo', () => {
  let selected = 'privacy'
  let results = { act_id: 89, total: 139 }
  const oldRequest = new AbortController()
  oldRequest.abort()
  applyCatalogueResponse(oldRequest.signal, '89', { act_id: 89, total: 139 }, value => { results = value }, value => { selected = value })
  assert.equal(selected, 'privacy')
  applyCatalogueResponse(new AbortController().signal, '204', { act_id: 204, total: 219 }, value => { results = value }, value => { selected = value })
  assert.equal(selected, 'privacy')
  assert.deepEqual(results, { act_id: 204, total: 219 })
})
test('un collegamento a una vecchia edizione si riallinea solo alla propria risposta corrente', () => {
  const updates = []
  applyCatalogueResponse(new AbortController().signal, 'old-edition', { act_id: 204 }, () => {}, value => updates.push(value))
  assert.deepEqual(updates, ['204'])
})
test('la ricerca in tutti gli atti non seleziona implicitamente il codice della risposta', () => {
  const updates = []
  applyCatalogueResponse(new AbortController().signal, '', { act_id: 204 }, () => {}, value => updates.push(value))
  assert.deepEqual(updates, [])
})

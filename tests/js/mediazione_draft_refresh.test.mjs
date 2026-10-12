import { test } from 'node:test'
import assert from 'node:assert/strict'
import './support/resolve_ts_extensionless.mjs'
const { hasProcedureDraftChanges, mergeProcedureRefresh } = await import('../../frontend/src/components/mediazione/mergeProcedureRefresh.ts')
const previous = { id: 'p1', versione: 1, titolo: 'Mediazione', stato: 'bozza', regime: 'volontaria', modalita: 'presenza', organismo_numero: '', sede_id: '', parti: [{ nome: 'Parte A', pec: '' }], incontri: [], proroghe: [] }
test('aggiorna versione e campi puliti conservando il testo locale', () => {
  const local = { ...previous, titolo: 'Bozza locale' }
  const incoming = { ...previous, versione: 2, organismo_numero: '429' }
  const result = mergeProcedureRefresh(local, previous, incoming)
  assert.equal(result.values.versione, 2)
  assert.equal(result.values.organismo_numero, '429')
  assert.equal(result.values.titolo, 'Bozza locale')
  assert.deepEqual(result.conflicts, [])
})
test('titoli concorrenti restano espliciti senza cancellare la bozza', () => {
  const result = mergeProcedureRefresh({ ...previous, titolo: 'Locale' }, previous, { ...previous, versione: 2, titolo: 'Salvato altrove' })
  assert.equal(result.values.titolo, 'Locale')
  assert.deepEqual(result.conflicts, ['titolo'])
})
test('confronta parti strutturate anche con ordine delle proprietà differente', () => {
  const incoming = { ...previous, versione: 2, parti: [{ pec: '', nome: 'Parte A' }] }
  assert.deepEqual(mergeProcedureRefresh(previous, previous, incoming).conflicts, [])
  const local = { ...previous, parti: [{ nome: 'Parte A', pec: 'locale@example.invalid' }] }
  const remote = { ...incoming, parti: [{ nome: 'Parte B', pec: '' }] }
  const result = mergeProcedureRefresh(local, previous, remote)
  assert.deepEqual(result.values.parti, local.parti)
  assert.deepEqual(result.conflicts, ['parti'])
})
test('ricevere la stessa modifica non genera un conflitto e i controlli restano del server', () => {
  const local = { ...previous, titolo: 'Comune', controlli: [{ id: 'c', ok: false }] }
  const incoming = { ...local, versione: 2, controlli: [{ id: 'c', ok: true }] }
  const result = mergeProcedureRefresh(local, previous, incoming)
  assert.deepEqual(result.conflicts, [])
  assert.deepEqual(result.values.controlli, incoming.controlli)
})
test('accettare il dato salvato elimina solo la modifica locale risolta', () => {
  const incoming = { ...previous, versione: 2, titolo: 'Salvato altrove' }
  assert.equal(hasProcedureDraftChanges({ ...incoming }, incoming), false)
  assert.equal(hasProcedureDraftChanges({ ...incoming, ragioni: 'Nota locale da conservare' }, incoming), true)
  assert.equal(hasProcedureDraftChanges({ ...incoming, versione: 1, controlli: [] }, incoming), false)
})

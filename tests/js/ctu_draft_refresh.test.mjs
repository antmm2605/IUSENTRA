import { test } from 'node:test'
import assert from 'node:assert/strict'
const { ctuDraftSnapshot } = await import('../../frontend/src/ctuDraftData.ts')
const { mergeRegistryRefresh } = await import('../../frontend/src/features/anagrafiche/mergeRegistryRefresh.ts')
const source = { stato: 'NOMINATO', dataDepositoRelazione: '', dataComunicazioneDecreto: '', importoLiquidato: '', compensoInput: {} }

test('aggiornamento dei campi puliti senza perdere importo e data nella bozza', () => {
  const previous = ctuDraftSnapshot(source)
  const current = { ...previous, importoLiquidato: '260', dataDepositoRelazione: '2026-10-09' }
  const incoming = ctuDraftSnapshot({ ...source, stato: 'IN_CORSO' })
  const merged = mergeRegistryRefresh(current, previous, incoming)
  assert.equal(merged.values.stato, 'IN_CORSO')
  assert.equal(merged.values.importoLiquidato, '260')
  assert.equal(merged.values.dataDepositoRelazione, '2026-10-09')
  assert.deepEqual(merged.conflicts, [])
})
test('importo concorrente differente resta esplicito e non sovrascrive la bozza', () => {
  const previous = ctuDraftSnapshot(source)
  const current = { ...previous, importoLiquidato: '260' }
  const incoming = ctuDraftSnapshot({ ...source, importoLiquidato: '500' })
  const merged = mergeRegistryRefresh(current, previous, incoming)
  assert.equal(merged.values.importoLiquidato, '260')
  assert.deepEqual(merged.conflicts, ['importoLiquidato'])
})
test('stesso salvataggio ricevuto dalla regia non genera un conflitto fittizio', () => {
  const previous = ctuDraftSnapshot(source)
  const incoming = ctuDraftSnapshot({ ...source, importoLiquidato: '260' })
  assert.deepEqual(mergeRegistryRefresh(incoming, previous, incoming), { values: incoming, conflicts: [] })
})
test('righe e opzioni del compenso conservano l’intera modifica locale concorrente', () => {
  const previous = ctuDraftSnapshot(source)
  const localSource = { ...source, compensoInput: { voci: [{ codice: '1', valore: '260', quantita: '2' }], ritardo: true } }
  const current = ctuDraftSnapshot(localSource)
  const incoming = ctuDraftSnapshot({ ...source, compensoInput: { voci: [{ codice: '2', valore: '500', quantita: '1' }], iva_perc: 0 } })
  const merged = mergeRegistryRefresh(current, previous, incoming)
  assert.equal(merged.values.voci, current.voci)
  assert.equal(merged.values.ritardo, true)
  assert.equal(merged.values.iva_perc, '0')
  assert.deepEqual(merged.conflicts, ['voci'])
})
test('aggiornamento compenso pulito adotta le voci numeriche normalizzate', () => {
  const previous = ctuDraftSnapshot(source)
  const incoming = ctuDraftSnapshot({ ...source, compensoInput: { modalita: 'vacazioni', vacazioni: 3, contributo_perc: 0, ritardo: false } })
  assert.deepEqual(mergeRegistryRefresh(previous, previous, incoming).values, incoming)
  assert.equal(incoming.vacazioni, '3')
  assert.equal(incoming.contributo_perc, '0')
  assert.equal(incoming.ritardo, false)
})
test('un nuovo incarico riparte dal proprio stato senza trasferire la bozza precedente', () => {
  const current = { ...ctuDraftSnapshot(source), importoLiquidato: '260' }
  const incoming = ctuDraftSnapshot({ ...source, stato: 'DEPOSITATO' })
  assert.deepEqual(mergeRegistryRefresh(current, undefined, incoming), { values: incoming, conflicts: [] })
})

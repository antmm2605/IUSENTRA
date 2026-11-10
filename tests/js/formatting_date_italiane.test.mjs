import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatDateIt, formatDateTimeIt } from '../../frontend/src/formatting.ts'

test('una data già italiana non si rilegge all’americana', () => {
  assert.equal(formatDateIt('05/11/2026'), '05/11/2026')
  assert.equal(formatDateIt('5-11-2026'), '05/11/2026')
  assert.equal(formatDateIt('31/02/2026', 'non valida'), 'non valida')
  assert.equal(formatDateTimeIt('05/11/2026 10:30'), '05/11/2026 10:30')
})

test('ISO dal backend: giorno e data-ora civile di Roma con qualunque fuso del browser', () => {
  const previous = process.env.TZ
  try {
    for (const zone of ['UTC', 'Europe/Rome', 'America/New_York', 'Pacific/Kiritimati']) {
      process.env.TZ = zone
      assert.equal(formatDateIt('2026-11-05'), '05/11/2026', zone)
      assert.equal(formatDateTimeIt('2026-07-27T10:00'), '27/07/2026 10:00', zone)
      assert.equal(formatDateTimeIt('2026-07-27T08:00:00Z'), '27/07/2026 10:00', zone)
    }
  } finally {
    if (previous === undefined) delete process.env.TZ
    else process.env.TZ = previous
  }
})

test('etichetta di data dal backend: ISO diventa italiano, il resto resta com’è', async () => {
  const { formatDateLabelIt } = await import('../../frontend/src/formatting.ts')
  assert.equal(formatDateLabelIt('2026-11-05'), '05/11/2026')
  assert.equal(formatDateLabelIt('2026-11-05T10:00:00'), '05/11/2026 10:00')
  assert.equal(formatDateLabelIt('2026-11-05T00:00:00'), '05/11/2026')
  assert.equal(formatDateLabelIt('05/11/2026'), '05/11/2026')
  assert.equal(formatDateLabelIt('Indice studio'), 'Indice studio')
  assert.equal(formatDateLabelIt('', 'non indicato'), 'non indicato')
})

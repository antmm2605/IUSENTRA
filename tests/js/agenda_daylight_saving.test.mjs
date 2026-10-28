import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { romeInstant, romeTimeRange } from '../../frontend/src/agendaTime.ts'

test('durata reale attraverso entrambi i cambi di ora', () => {
  assert.equal(romeTimeRange('2026-03-29', '01:30', 60), '01:30 CET - 03:30 CEST')
  assert.equal(romeTimeRange('2026-10-25', '02:30', 60), '02:30 CEST - 02:30 CET')
  assert.equal(romeInstant('2026-03-29T02:30'), null)
  assert.equal(romeInstant('2026-02-30T09:00'), null)
})

test('fuso del browser diverso non sposta le ore dello studio', () => {
  const previous = process.env.TZ
  try {
    for (const zone of ['UTC', 'Europe/Rome', 'Pacific/Honolulu']) {
      process.env.TZ = zone
      assert.equal(romeInstant('2026-07-01T09:00').toISOString(), '2026-07-01T07:00:00.000Z')
      assert.equal(romeInstant('2026-01-01T09:00').toISOString(), '2026-01-01T08:00:00.000Z')
    }
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous }
})

test('ora ripetuta mantiene i due istanti con offset esplicito', () => {
  assert.equal(romeInstant('2026-10-25T02:30').toISOString(), '2026-10-25T00:30:00.000Z')
  assert.equal(romeInstant('2026-10-25T02:30+01:00').toISOString(), '2026-10-25T01:30:00.000Z')
})


test('agenda conserva giorno e ora italiani anche su browser estero', async () => {
  const { normalizeAgendaEvent, moveEventToDateTime } = await import('../../frontend/src/agendaData.ts')
  const previous = process.env.TZ
  try {
    process.env.TZ = 'Pacific/Honolulu'
    const event = normalizeAgendaEvent({ id: 'dst', start: '2026-07-01T00:30:00', durata_minuti: 60 })
    assert.equal(event.date, '2026-07-01')
    assert.equal(event.timeLabel, '00:30')
    const moved = moveEventToDateTime(event, '2026-03-29', '01:30')
    assert.equal(moved.start, '2026-03-29T00:30:00.000Z')
    assert.equal(moved.end, '2026-03-29T01:30:00.000Z')
    assert.equal(moveEventToDateTime(event, '2026-03-29', '02:30'), event)
    const second = normalizeAgendaEvent({ id: 'second', start: '2026-10-25T02:30:00+01:00', durata_minuti: 30 })
    assert.equal(moveEventToDateTime(second, '2026-10-25'), second)
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous }
})

test('timestamp locali SQL e frazioni non perdono precisione disponibile', () => {
  assert.equal(romeInstant('2026-07-01 09:00:00.123456').toISOString(), '2026-07-01T07:00:00.123Z')
})

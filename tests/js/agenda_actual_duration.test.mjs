import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { normalizeAgendaEvent, moveEventToDateTime } from '../../frontend/src/agendaData.ts'

test('durate brevi persistite e spostamenti mantengono i minuti effettivi', () => {
  for (const minutes of [1, 5, 10, 15, 60]) {
    const event = normalizeAgendaEvent({ id: 'controllato', title: 'Collaudo', start: '2026-10-19T09:00:00', durata_minuti: minutes })
    assert.ok(event)
    assert.equal((Date.parse(event.end) - Date.parse(event.start)) / 60000, minutes)
    assert.equal(event.durationLabel, minutes < 60 ? `${minutes} min` : '1 h')
    const moved = moveEventToDateTime(event, '2026-10-20', '10:00')
    assert.equal(Date.parse(moved.end) - Date.parse(moved.start), minutes * 60000)
    assert.equal(moved.durationLabel, event.durationLabel)
  }
})

test('durate non valide usano un intervallo finito e il termine esplicito prevale', () => {
  for (const duration of ['', 'non valido', -5, 0, Infinity]) {
    const event = normalizeAgendaEvent({ start: '2026-10-19T09:00:00', duration })
    assert.equal(Date.parse(event.end) - Date.parse(event.start), 60 * 60000)
  }
  const event = normalizeAgendaEvent({ start: '2026-10-19T09:00:00', end: '2026-10-19T09:05:00', duration: 60 })
  assert.equal(event.durationLabel, '5 min')
})

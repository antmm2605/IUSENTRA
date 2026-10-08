import { test } from 'node:test'
import assert from 'node:assert/strict'
import { studioDay } from '../../frontend/src/hooks/useStudioToday.ts'

test('il giorno dello studio cambia alla mezzanotte italiana in ora legale', () => {
  assert.equal(studioDay(new Date('2026-10-07T21:59:59Z')).date, '2026-10-07')
  assert.deepEqual(studioDay(new Date('2026-10-07T22:00:00Z')), { date: '2026-10-08', label: 'gio 08 ott' })
})

test('il giorno dello studio segue Roma anche in ora solare', () => {
  assert.equal(studioDay(new Date('2026-12-31T22:59:59Z')).date, '2026-12-31')
  assert.deepEqual(studioDay(new Date('2026-12-31T23:00:00Z')), { date: '2027-01-01', label: 'ven 01 gen' })
})

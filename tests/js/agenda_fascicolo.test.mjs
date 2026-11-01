import assert from 'node:assert/strict'
import test from 'node:test'
import { vociAgendaFascicolo } from '../../frontend/src/components/fascicoli/agendaFascicoloVoci.ts'

const scadenza = (id, dateIso, extra = {}) => ({ id, title: id, date: '', dateIso, type: 'TERMINE', priority: '', status: 'APERTO', peremptory: false, notes: '', href: `/s/${id}`, tone: 'warning', ...extra })
const appuntamento = (id, date, extra = {}) => ({ id, title: id, date, time: '09:00', place: '', court: '', type: 'UDIENZA', href: `/a/${id}`, tone: 'primary', past: false, ...extra })

test('agenda del fascicolo: prossimi in ordine, poi i passati dal più recente', () => {
  const voci = vociAgendaFascicolo(
    [scadenza('note', '2026-11-05'), scadenza('vecchia', '2026-09-01')],
    [appuntamento('udienza', '24/11/2026'), appuntamento('udienza-2023', '20/04/2023', { past: true }), appuntamento('domani', '01/11/2026')],
    '2026-10-31',
  )
  assert.deepEqual(voci.map((v) => v.titolo), ['domani', 'note', 'udienza', 'vecchia', 'udienza-2023'])
  assert.deepEqual(voci.map((v) => v.passata), [false, false, false, true, true])
})

test('agenda compatta: solo i prossimi impegni, al massimo cinque, con il conteggio degli altri', async () => {
  const { prossimiImpegni } = await import('../../frontend/src/components/fascicoli/agendaFascicoloVoci.ts')
  const voci = vociAgendaFascicolo(
    ['a', 'b', 'c', 'd', 'e', 'f'].map((id, i) => scadenza(id, `2026-11-1${i}`)).concat([scadenza('passata', '2026-10-01')]),
    [],
    '2026-11-01',
  )
  const { voci: prime, altri } = prossimiImpegni(voci)
  assert.deepEqual(prime.map((v) => v.titolo), ['a', 'b', 'c', 'd', 'e'])
  assert.equal(altri, 1)
  assert.ok(prime.every((v) => !v.passata))
})

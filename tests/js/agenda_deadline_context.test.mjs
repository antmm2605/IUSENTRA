import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { agendaDeadlineCalculatorHref, agendaProposedSteps } from '../../frontend/src/features/agenda/agendaDetailActions.ts'

test('il passaggio al calcolatore conserva il fascicolo senza usare la data agenda come decorrenza', () => {
  const event = { matterId: 'fascicolo / speciale', title: 'Termine', legalLabel: 'Scadenza', start: '2026-10-11', detailLines: [] }
  const link = new URL(agendaDeadlineCalculatorHref(event), 'http://localhost')
  assert.equal(link.searchParams.get('id_fascicolo'), event.matterId)
  assert.deepEqual([...link.searchParams.keys()], ['id_fascicolo'])
  const step = agendaProposedSteps(event, 'Verifica il termine', { editHref: '/agenda/evento', isDeadline: false, clientReminderHref: '/clienti' })
  assert.equal(step.find(item => item.id === 'termine').href, `${link.pathname}${link.search}`)
})

test('un impegno senza fascicolo non introduce associazioni inventate', () => {
  assert.equal(agendaDeadlineCalculatorHref({ matterId: '' }), '/scadenziario/calcola-termini')
})

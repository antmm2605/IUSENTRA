import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { agendaActivityText, agendaDeadlineCalculatorHref, agendaProposedSteps } from '../../frontend/src/features/agenda/agendaDetailActions.ts'

import { deadlineWhatToDo } from '../../frontend/src/features/scadenziario/deadlineDetailFacts.ts'

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

test('la scadenza delle note mostra il riscontro del motore prima dell’azione generica', () => {
  const proceduralFinding = 'La cancelleria ha accettato le note. Verificare se riguardano questa udienza.'
  assert.equal(deadlineWhatToDo({ hearingMode: 'Trattazione scritta', proceduralFinding }), proceduralFinding)
  assert.match(deadlineWhatToDo({ hearingMode: 'Trattazione scritta' }), /^Predisponi e deposita/)
})

test('Agenda usa il riscontro delle note e non propone un secondo deposito', () => {
  const finding = 'Controlli automatici superati. Verificare l’esito finale della cancelleria.'
  const event = { matterId: 'F1', legalLabel: 'Deposito', proceduralFinding: finding, sourceHref: '/fonte' }
  assert.equal(agendaActivityText(event), finding)
  const steps = agendaProposedSteps(event, finding, { editHref: '', isDeadline: false, clientReminderHref: '' })
  assert.deepEqual(steps.map(step => step.id), ['fonte'])
})

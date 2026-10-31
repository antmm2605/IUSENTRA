import assert from 'node:assert/strict'
import test from 'node:test'
import { applicaPrecompilatoUtility, catalogoUtility, destinazioneUtility } from '../../frontend/src/utilityCatalog.ts'
import { righeRisultato, tabelleRisultato } from '../../frontend/src/strumentiLegaliData.ts'

test('quote monetarie e percentuali leggibili senza cambiare il payload numerico', () => {
  const result = { quota: 1234.56, incidenza: 20.25, variazione: -2.125 }
  assert.deepEqual(righeRisultato(result, 'percentuali').map(item => item.value), ['€ 1.234,56', '20,25%', '-2,125%'])
  assert.equal(result.quota, 1234.56)
  assert.equal(righeRisultato({ quota: 10 })[0].value, '10')
})

const tool = { id: 'interessi', title: 'Interessi', subtitle: 'Calcolo', categoria: 'Credito' }

test('precompilato tardivo conserva modifiche, zero e cancellazione esplicita dell’operatore', () => {
  const corrente = { valore: '0', data: '', titolo: 'Titolo precedente' }
  assert.deepEqual(applicaPrecompilatoUtility({ valore: '100', data: '2026-10-11', titolo: 'Fonte nuova' }, corrente, new Set(['valore', 'data'])), { valore: '0', data: '', titolo: 'Fonte nuova' })
  assert.equal(corrente.titolo, 'Titolo precedente')
})

test('esito mediazione leggibile con importi italiani e senza duplicare valori macchina', () => {
  const result = { regime: 'obbligatoria_demandata', regime_label: 'Obbligatoria / demandata dal giudice', totale_organismo: 80, ulteriori_spese_mediazione: 0, riduzione_obbligatoria_applicata: true, art31_comma3_maggiorazione_20: false, riferimento_url: 'https://fonte.example/' }
  const righe = righeRisultato(result, 'indennita_mediazione')
  assert.deepEqual(righe.map(item => item.value), ['Obbligatoria / demandata dal giudice', '€ 0,00', '€ 80,00', 'Sì', 'No'])
  assert.equal(result.totale_organismo, 80)
})
const voce = { id: 'base', title: 'Interessi', description: 'Calcolo', section: 'Credito', toolId: 'interessi', preset: {}, href: '/strumenti-legali/?tool=interessi&app=base', unavailable: null }

test('unifica alias identici conservando varianti e strumenti compilabili', () => {
  const ridotto = catalogoUtility([tool], [voce])
  assert.equal(ridotto.length, 1)
  assert.equal(ridotto[0].strumento, tool)
  const varianti = catalogoUtility([tool], [{ ...voce, id: 'legali', preset: { tipo: 'legali' } }, { ...voce, id: 'mora', preset: { tipo: 'mora' } }])
  assert.equal(varianti.length, 3)
  assert.deepEqual(varianti.slice(1).map(item => item.funzione.preset.tipo), ['legali', 'mora'])
})

test('mantiene strumenti operativi e contesto del fascicolo senza destinazioni esterne', () => {
  const lookup = { ...voce, id: 'comune', title: 'Cerca Comune', toolId: '', href: '/applicazioni/comune?tipo=nascita#risultato' }
  assert.equal(catalogoUtility([tool], [lookup])[1].funzione, lookup)
  assert.equal(destinazioneUtility(lookup.href, 'CASE42'), '/applicazioni/comune?tipo=nascita&id_fascicolo=CASE42#risultato')
  for (const href of ['//esterno.example/', 'https://esterno.example/', 'javascript:alert(1)']) assert.equal(destinazioneUtility(href), '')
})


test('interessi: etichette italiane, euro, date e tassi anche nei periodi senza alterare dati', () => {
  const result = { capital: 1000, covered_days: 2, days: 2, end_date: '2026-10-30', start_date: '2026-10-29', label: 'Interessi legali ex art. 1284 c.c.', mode: 'legali', total_amount: 1000.09, total_interest: 0.09,
    segments: [{ days: 2, from: '2026-10-29', to: '2026-10-30', interest: 0.09, rate: 1.6, reference_rate: null }] }
  const before = JSON.stringify(result)
  const rows = Object.fromEntries(righeRisultato(result, 'interessi').map(row => [row.label, row.value.replace(/\u00a0/g, ' ')]))
  assert.equal(rows['Capitale'], '1.000,00 €')
  assert.equal(rows['Totale dovuto'], '1.000,09 €')
  assert.equal(rows['Interessi totali'], '0,09 €')
  assert.equal(rows['Data iniziale'], '29/10/2026')
  assert.equal(rows['Data finale'], '30/10/2026')
  assert.equal(rows['Regime'], 'Interessi legali')
  const table = tabelleRisultato(result, 'interessi')[0]
  assert.equal(table.titolo, 'Dettaglio per periodo')
  assert.equal(table.righe[0].from, '29/10/2026')
  assert.equal(table.righe[0].rate, '1,6%')
  assert.equal(table.righe[0].reference_rate, '')
  assert.equal(table.righe[0].interest.replace(/\u00a0/g, ' '), '0,09 €')
  assert.equal(JSON.stringify(result), before)
})

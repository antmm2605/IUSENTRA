import assert from 'node:assert/strict'
import test from 'node:test'

import { passoDaIndirizzo, trovaPasso } from '../../web/static/js/reader-passo.js'

// Strato di testo del lettore: una parola per elemento, punteggiatura attaccata come nel PDF.
const parole = ('Motivi della decisione. P.Q.M. Il Tribunale, definitivamente pronunciando, condanna il Ministero alla '
  + 'rifusione delle spese di lite in favore della parte ricorrente, che liquida in euro 1.300,00 oltre spese generali.').split(' ')

test('il passo citato si trova con le sue parole, anche con punteggiatura e accenti diversi', () => {
  const indici = trovaPasso(parole, 'condanna il Ministero alla rifusione delle spese di lite')
  assert.equal(parole[indici[0]], 'condanna')
  assert.equal(parole[indici.at(-1)], 'lite')
})

test('una prima parola letta diversamente dall’OCR non perde il passo', () => {
  const indici = trovaPasso(parole, 'condama il Ministero alla rifusione delle spese di lite in favore della parte')
  assert.equal(parole[indici[0]], 'condanna')
  assert.equal(parole[indici.at(-1)], 'parte')
})

test('nessuna evidenza se il passo non è nel documento', () => {
  assert.deepEqual(trovaPasso(parole, 'rigetta la domanda riconvenzionale proposta dalla convenuta'), [])
  assert.deepEqual(trovaPasso(parole, 'spese'), [])
})

test('il passo arriva dal frammento dell’indirizzo, mai dalla query inviata al server', () => {
  assert.equal(passoDaIndirizzo('#passo=condanna%20il%20Ministero'), 'condanna il Ministero')
  assert.equal(passoDaIndirizzo(''), '')
})

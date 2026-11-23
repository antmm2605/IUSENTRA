import test from 'node:test'
import assert from 'node:assert/strict'
import { SEZIONI, STATI, dataOraIt, divisioneAncora } from '../../frontend/src/components/conoscenzaDati.ts'

test('le date delle schede si mostrano in formato italiano', () => {
  assert.equal(dataOraIt('2026-11-23T09:05:00'), '23/11/2026 09:05')
  assert.equal(dataOraIt(''), '')
  assert.equal(dataOraIt('non-una-data'), '')
})

test('il passaggio citato della norma si evidenzia solo con un intervallo valido', () => {
  const testo = 'Le amministrazioni completano le procedure entro il termine di centoventi giorni dalla notificazione.'
  const inizio = testo.indexOf('centoventi')
  assert.deepEqual(divisioneAncora({ testo, inizio, fine: inizio + 'centoventi giorni'.length }),
    [testo.slice(0, inizio), 'centoventi giorni', testo.slice(inizio + 'centoventi giorni'.length)])
  assert.deepEqual(divisioneAncora({ testo, inizio: -1, fine: -1 }), [testo, '', ''])
  assert.deepEqual(divisioneAncora({ testo, inizio: 5, fine: 9999 }), [testo, '', ''])
})

test('nove sezioni della scheda e tre stati di verifica', () => {
  assert.equal(SEZIONI.length, 9)
  assert.deepEqual(Object.keys(STATI), ['verificata', 'lacune', 'da_riesaminare'])
})

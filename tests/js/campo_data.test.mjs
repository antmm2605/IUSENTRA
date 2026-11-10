import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  dataInLettere,
  erroreCampoData,
  grigliaMese,
  isoDaValore,
  leggiTestoData,
  oggiRoma,
  spostaMesi,
  testoDaValore,
  titoloMese,
} from '../../frontend/src/ui/campoDataValore.ts'

test('gg/mm/aaaa diventa il valore tecnico dell’input nativo', () => {
  assert.deepEqual(leggiTestoData('27/07/2026'), { stato: 'valido', iso: '2026-07-27' })
  assert.deepEqual(leggiTestoData('5/1/2026'), { stato: 'valido', iso: '2026-01-05' })
  assert.deepEqual(leggiTestoData(' 27072026 '), { stato: 'valido', iso: '2026-07-27' })
  assert.equal(testoDaValore('2026-07-27'), '27/07/2026')
  assert.equal(testoDaValore(''), '')
  assert.equal(testoDaValore(null), '')
})

test('con l’ora: gg/mm/aaaa hh:mm ↔ YYYY-MM-DDTHH:MM', () => {
  assert.deepEqual(leggiTestoData('27/07/2026 09:30', true), { stato: 'valido', iso: '2026-07-27T09:30' })
  assert.deepEqual(leggiTestoData('27/07/2026 9.30', true), { stato: 'valido', iso: '2026-07-27T09:30' })
  assert.deepEqual(leggiTestoData('27/07/2026, ore 18:05', true), { stato: 'valido', iso: '2026-07-27T18:05' })
  assert.equal(testoDaValore('2026-07-27T09:30', true), '27/07/2026 09:30')
  assert.equal(testoDaValore('2026-07-27T09:30:15', true), '27/07/2026 09:30')
  assert.equal(leggiTestoData('27/07/2026', true).stato, 'incompleto')
  assert.equal(leggiTestoData('27/07/2026 24:00', true).stato, 'non_valido')
  assert.equal(leggiTestoData('27/07/2026 10:60', true).stato, 'non_valido')
  assert.equal(erroreCampoData(leggiTestoData('27/07/2026', true), true, '', '', '27/07/2026'), 'Indica anche l’ora nel formato hh:mm.')
})

test('date che non esistono nel calendario sono rifiutate', () => {
  for (const testo of ['31/02/2026', '29/02/2026', '31/04/2026', '00/01/2026', '15/13/2026', '32/01/2026']) {
    assert.equal(leggiTestoData(testo).stato, 'non_valido', testo)
    assert.equal(leggiTestoData(testo).iso, '')
  }
  assert.match(erroreCampoData(leggiTestoData('31/02/2026'), false), /Data non valida/)
})

test('anno bisestile: 29/02 solo negli anni bisestili', () => {
  assert.equal(leggiTestoData('29/02/2024').iso, '2024-02-29')
  assert.equal(leggiTestoData('29/02/2000').iso, '2000-02-29')
  assert.equal(leggiTestoData('29/02/1900').stato, 'non_valido')
  assert.equal(leggiTestoData('29/02/2100').stato, 'non_valido')
  assert.equal(spostaMesi('2024-01-31', 1), '2024-02-29')
  assert.equal(spostaMesi('2026-01-31', 1), '2026-02-28')
})

test('incollaggio: trattini, punti e formato tecnico; mai la lettura americana', () => {
  assert.equal(leggiTestoData('27-07-2026').iso, '2026-07-27')
  assert.equal(leggiTestoData('27.07.2026').iso, '2026-07-27')
  assert.equal(leggiTestoData('2026-07-27').iso, '2026-07-27')
  assert.equal(leggiTestoData('27-07-2026 10.15', true).iso, '2026-07-27T10:15')
  assert.equal(leggiTestoData('2026-07-27T10:15', true).iso, '2026-07-27T10:15')
  // 07/27/2026 (formato USA) non è una data italiana valida: non si reinterpreta.
  assert.equal(leggiTestoData('07/27/2026').stato, 'non_valido')
  // 03/04/2026 è il 3 aprile, non il 4 marzo.
  assert.equal(leggiTestoData('03/04/2026').iso, '2026-04-03')
})

test('scrittura in corso e testo estraneo', () => {
  assert.equal(leggiTestoData('').stato, 'vuoto')
  assert.equal(leggiTestoData('27/0').stato, 'incompleto')
  assert.equal(leggiTestoData('27/07/202').stato, 'incompleto')
  assert.equal(leggiTestoData('domani').stato, 'non_valido')
  assert.equal(leggiTestoData('27/07/2026 10:00').stato, 'non_valido')
  assert.equal(erroreCampoData(leggiTestoData('27/0'), false), 'Completa la data nel formato gg/mm/aaaa.')
  assert.equal(erroreCampoData(leggiTestoData(''), false), '')
})

test('valori ricevuti dal codice: ISO o già italiani, il resto si mostra com’è', () => {
  assert.equal(isoDaValore('01/01/2026'), '2026-01-01')
  assert.equal(testoDaValore('01-01-2026'), '01/01/2026')
  assert.equal(testoDaValore('valore strano'), 'valore strano')
  assert.equal(isoDaValore('valore strano'), '')
  assert.equal(isoDaValore('2026-07-27T10:15'), '2026-07-27')
})

test('limiti min e max con il messaggio in italiano', () => {
  assert.equal(erroreCampoData(leggiTestoData('10/11/2026'), false, '2026-11-10'), '')
  assert.equal(erroreCampoData(leggiTestoData('09/11/2026'), false, '2026-11-10'), 'La data non può essere precedente al 10/11/2026.')
  assert.equal(erroreCampoData(leggiTestoData('11/11/2026'), false, '', '2026-11-10'), 'La data non può essere successiva al 10/11/2026.')
  assert.equal(erroreCampoData(leggiTestoData('10/11/2026 23:00', true), true, '2026-11-10'), '')
})

test('calendario: settimana da lunedì, mesi e giorni in italiano', () => {
  const griglia = grigliaMese('2026-07-15')
  assert.equal(griglia.length, 6)
  assert.equal(griglia[0][0].iso, '2026-06-29') // lunedì prima del 1° luglio (mercoledì)
  assert.equal(griglia[0][2].iso, '2026-07-01')
  assert.equal(griglia[0][2].delMese, true)
  assert.equal(griglia[0][0].delMese, false)
  assert.equal(titoloMese('2026-07-15'), 'luglio 2026')
  assert.equal(dataInLettere('2026-07-27'), 'lunedì 27 luglio 2026')
  assert.equal(dataInLettere('2026-11-08'), 'domenica 8 novembre 2026')
})

test('oggi è il giorno civile di Roma, non quello del fuso del browser', () => {
  // 23:30 UTC del 31/12 è già il 1° gennaio a Roma.
  assert.equal(oggiRoma(new Date('2026-12-31T23:30:00Z')), '2027-01-01')
  assert.equal(oggiRoma(new Date('2026-07-27T21:59:00Z')), '2026-07-27')
  assert.equal(oggiRoma(new Date('2026-07-27T22:01:00Z')), '2026-07-28')
})

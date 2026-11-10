import test from 'node:test'
import assert from 'node:assert/strict'
import {
  GAZZETTA_QUERY_INIZIALE,
  estremiGazzetta,
  gazzettaQueryDaIndirizzo,
  gazzettaQueryString,
} from '../../frontend/src/gazzettaData.ts'

test('i filtri della Gazzetta Ufficiale viaggiano nell’indirizzo e tornano uguali', () => {
  const query = { ...GAZZETTA_QUERY_INIZIALE, q: ' sentenze  ', serie: 'SG', tipo: 'legge', ente: 'MINISTERO DELLA GIUSTIZIA', dal: '2026-11-01', al: '2026-11-09', numero: '261', ordine: 'meno_recenti', pagina: 3 }
  const indirizzo = gazzettaQueryString(query)
  const letta = gazzettaQueryDaIndirizzo(indirizzo)
  assert.deepEqual(letta, { ...query, q: 'sentenze' })
  assert.equal(gazzettaQueryString(GAZZETTA_QUERY_INIZIALE), '')
})

test('valori estranei nell’indirizzo non diventano filtri', () => {
  const letta = gazzettaQueryDaIndirizzo('?ordine=casuale&pagina=-4')
  assert.equal(letta.ordine, 'recenti')
  assert.equal(letta.pagina, 1)
})

test('estremi della Gazzetta con la data in gg/mm/aaaa', () => {
  const dataIt = (valore) => valore.split('-').reverse().join('/')
  assert.equal(estremiGazzetta({ seriesLabel: 'Serie generale', issueNumber: '261', issueDate: '2026-11-09' }, dataIt), 'GU Serie generale n. 261 del 09/11/2026')
})

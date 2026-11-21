import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { consultaQuery, estremiConsulta, sentenzeWebQuery, statoArchivioCassazione } from '../../frontend/src/archivioSentenze.ts'

test('la ricerca Cassazione invia numero, anno, sezione e ramo separati', () => {
  const query = new URLSearchParams(sentenzeWebQuery({ q: '', numero: '5425', anno: '2021', sezione: 'U', ramo: 'civile' }))
  assert.deepEqual(Object.fromEntries(query), { numero: '5425', anno: '2021', sezione: 'U', ramo: 'civile' })
  assert.equal(sentenzeWebQuery({ q: '', numero: '', anno: '', sezione: '', ramo: '' }), '')
})

test('il conteggio in aggiornamento non diventa zero', () => {
  assert.match(statoArchivioCassazione({ caseCount: null }), /in aggiornamento/)
  assert.match(statoArchivioCassazione({ caseCount: 426399, status: 'complete' }), /426\.399 decisioni/)
})

test('Corte costituzionale: numero e anno diventano estremi, intestazione senza sigle', () => {
  assert.equal(new URLSearchParams(consultaQuery('194', '2018')).get('q'), '194/2018')
  assert.equal(new URLSearchParams(consultaQuery('licenziamento', '')).get('q'), 'licenziamento')
  assert.equal(new URLSearchParams(consultaQuery('', '')).get('fonte'), 'corte_costituzionale')
  assert.equal(estremiConsulta({ kind: 'sentenza', number: '194', year: 2018 }), 'Corte costituzionale, sentenza n. 194/2018')
})

test('la pagina ha il titolo del menu e le sezioni per corte', () => {
  const page = readFileSync(new URL('../../frontend/src/components/GiurisprudenzaPage.tsx', import.meta.url), 'utf8')
  assert.match(page, /title="Archivio sentenze per corte"/)
  assert.match(page, /<SentenzeWebSearch \/>\s*<ConsultaSearch \/>\s*<OpenGASearch \/>/)
  const cassazione = readFileSync(new URL('../../frontend/src/components/SentenzeWebSearch.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(cassazione, /snciv|snpen/)
  assert.match(cassazione, /<dt>Sezione<\/dt>/)
  assert.match(cassazione, /<dt>Oggetto<\/dt>/)
})

// Technical guardrails only: ordinamento e ricerca della lista "Documenti e atti" del fascicolo.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildDocumentHaystack,
  compareDocuments,
  matchesSearchTerms,
  parseDocumentDate,
  searchTerms,
} from '../../frontend/src/components/fascicoloDocumenti/documentListOrdering.ts'

const doc = (overrides) => ({
  id: overrides.name,
  name: '',
  type: '',
  rawType: '',
  catalogLabel: '',
  catalogRole: '',
  source: '',
  portalName: '',
  portalClass: '',
  portalSender: '',
  statusLabel: '',
  notes: '',
  tags: [],
  documentDate: '',
  uploadedAt: '',
  portalDate: '',
  ...overrides,
})

const sortNames = (key, docs) => [...docs].sort((a, b) => compareDocuments(key, a, b)).map((item) => item.name)

test('date italiane e ISO producono lo stesso timestamp', () => {
  assert.equal(parseDocumentDate('08/03/2024'), parseDocumentDate('2024-03-08'))
  assert.equal(parseDocumentDate(''), 0)
  assert.equal(parseDocumentDate('data n.d.'), 0)
})

test('ordinamento per data documento: recenti prima, senza data sempre in fondo', () => {
  const docs = [
    doc({ name: 'ricevuta.eml', documentDate: '05/07/2023' }),
    doc({ name: 'senza-data.pdf' }),
    doc({ name: 'contributo.eml', documentDate: '08/03/2024' }),
    doc({ name: 'ricorso.pdf', portalDate: '12/01/2022' }),
  ]
  assert.deepEqual(sortNames('data_documento_desc', docs), ['contributo.eml', 'ricevuta.eml', 'ricorso.pdf', 'senza-data.pdf'])
  assert.deepEqual(sortNames('data_documento_asc', docs), ['ricorso.pdf', 'ricevuta.eml', 'contributo.eml', 'senza-data.pdf'])
})

test('ordinamento per caricamento usa la data di caricamento prima della data documento', () => {
  const docs = [
    doc({ name: 'vecchio-caricato-ieri.pdf', documentDate: '01/01/2020', uploadedAt: '09/09/2026' }),
    doc({ name: 'recente-caricato-prima.pdf', documentDate: '01/09/2026', uploadedAt: '02/09/2026' }),
  ]
  assert.deepEqual(sortNames('caricamento_desc', docs), ['vecchio-caricato-ieri.pdf', 'recente-caricato-prima.pdf'])
  assert.deepEqual(sortNames('data_documento_desc', docs), ['recente-caricato-prima.pdf', 'vecchio-caricato-ieri.pdf'])
})

test('a parità di data vince il nome con ordinamento numerico italiano', () => {
  const docs = [doc({ name: 'Allegato 10.pdf', documentDate: '01/02/2024' }), doc({ name: 'Allegato 2.pdf', documentDate: '01/02/2024' })]
  assert.deepEqual(sortNames('data_documento_desc', docs), ['Allegato 2.pdf', 'Allegato 10.pdf'])
})

test('ricerca: più termini in AND, senza accenti né maiuscole, con mese in italiano', () => {
  const haystack = buildDocumentHaystack(doc({ name: 'Procura alle liti.pdf', catalogLabel: 'Procura', tags: ['Urgenza'], notes: 'Già firmata dal cliente', documentDate: '08/03/2024' }))
  assert.ok(matchesSearchTerms(haystack, searchTerms('procura marzo 2024')))
  assert.ok(matchesSearchTerms(haystack, searchTerms('GIA FIRMATA')))
  assert.ok(matchesSearchTerms(haystack, searchTerms('03/2024 urgenza')))
  assert.ok(!matchesSearchTerms(haystack, searchTerms('procura aprile')))
  assert.ok(matchesSearchTerms(haystack, searchTerms('   ')))
})

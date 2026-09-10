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

test('ricerca intelligente: sigle forensi, nomi camelCase, radici, refusi e date in ogni formato', async () => {
  const { buildDocumentSearchIndex, searchDocumentIndex } = await import('../../frontend/src/components/fascicoloDocumenti/documentSearch.ts')
  const docs = [
    doc({ name: 'accoglimentoDecretoIngiuntivoNonEsecutivo.pdf', type: 'Provvedimento - decreto', documentDate: '31/05/2026', source: 'Import QuickOrganizer' }),
    doc({ name: 'ricevuta_pagopa_CU.pdf', type: 'Contributo unificato / pagamento', documentDate: '12/03/2026', signed: true }),
    doc({ name: 'Procura alle liti.pdf.p7m', type: 'Procura', documentDate: '08/03/2024', signed: true }),
    doc({ name: 'RdAC_consegna_PEC.eml', type: 'Comunicazione', uploadedAt: '2026-06-01T10:00:00' }),
    doc({ name: 'Relata di notifica.pdf', type: 'Notifica', documentDate: '15/06/2026' }),
    doc({ name: 'Sentenza n. 3-2025.pdf', type: 'Provvedimento', documentDate: '10/01/2025' }),
  ]
  const items = docs.map((item) => ({ item: item.name, index: buildDocumentSearchIndex(item) }))
  const names = (query) => searchDocumentIndex(items, query).items.map((entry) => entry.item)
  assert.deepEqual(names('decreto ingiuntivo'), ['accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  assert.deepEqual(names('DI'), ['accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  assert.deepEqual(names('D.I.'), ['accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  assert.deepEqual(names('cu'), ['ricevuta_pagopa_CU.pdf'])
  assert.deepEqual(names('mandato'), ['Procura alle liti.pdf.p7m'])
  assert.deepEqual(names('notifiche'), ['Relata di notifica.pdf'])
  assert.deepEqual(names('quickorganizer'), ['accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  assert.deepEqual(names('sentnza'), ['Sentenza n. 3-2025.pdf'])
  assert.deepEqual(names('provvedimneto').sort(), ['Sentenza n. 3-2025.pdf', 'accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  for (const query of ['8-3-2024', '2024-03-08', '08.03.2024', '03/2024', 'mar 2024', 'procura marzo 2024']) {
    assert.deepEqual(names(query), ['Procura alle liti.pdf.p7m'], query)
  }
  assert.deepEqual(names('giugno 2026').sort(), ['RdAC_consegna_PEC.eml', 'Relata di notifica.pdf'])
  assert.deepEqual(names('provvedimento -sentenza'), ['accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  assert.deepEqual(names('"non esecutivo"'), ['accoglimentoDecretoIngiuntivoNonEsecutivo.pdf'])
  const similar = searchDocumentIndex(items, 'procura aprile')
  assert.equal(similar.mode, 'simili')
  assert.deepEqual(similar.items.map((entry) => entry.item), ['Procura alle liti.pdf.p7m'])
  assert.equal(searchDocumentIndex(items, 'di').mode, 'esatta')
  assert.equal(searchDocumentIndex(items, '   ').items.length, docs.length)
  assert.equal(searchDocumentIndex(items, 'zzzzqqq').mode, 'nessun_risultato')
})

test('ricerca: il nome che contiene la frase completa viene prima', async () => {
  const { buildDocumentSearchIndex, searchDocumentIndex } = await import('../../frontend/src/components/fascicoloDocumenti/documentSearch.ts')
  const items = [
    doc({ name: 'Allegato ricevuta.pdf', notes: 'procura depositata' }),
    doc({ name: 'Procura alle liti.pdf' }),
  ].map((item) => ({ item: item.name, index: buildDocumentSearchIndex(item) }))
  assert.equal(searchDocumentIndex(items, 'procura').items[0].item, 'Procura alle liti.pdf')
})

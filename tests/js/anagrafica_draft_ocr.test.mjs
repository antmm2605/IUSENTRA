import assert from 'node:assert/strict'
import { test } from 'node:test'
import { restoredProtectedFields } from '../../frontend/src/features/anagrafiche/useAnagraficaDraft.ts'

test('bozza storica: un campo vuoto mai compilato resta disponibile alla lettura', () => {
  const draft = { version: 1, savedAt: '2026-10-09T12:00:00Z', values: { nome: 'Mario', rilascio: '' } }
  assert.deepEqual(restoredProtectedFields(draft, { nome: '', rilascio: '' }), ['nome'])
})

test('bozza storica: la cancellazione di un valore già salvato resta protetta', () => {
  const draft = { version: 1, savedAt: '2026-10-09T12:00:00Z', values: { rilascio: '' } }
  assert.deepEqual(restoredProtectedFields(draft, { rilascio: '2020-02-20' }), ['rilascio'])
})

test('bozza nuova: preserva la cancellazione manuale anche con valore iniziale vuoto', () => {
  const draft = { version: 1, savedAt: '2026-10-09T12:00:00Z', values: { rilascio: '', nome: 'Mario', next_url: '/clienti' }, protectedFields: ['rilascio', 'next_url'] }
  assert.deepEqual(restoredProtectedFields(draft, { rilascio: '', nome: '' }, ['next_url']), ['rilascio'])
})

test('bozza nuova: i valori OCR non diventano modifiche manuali al ripristino', () => {
  const draft = { version: 1, savedAt: '2026-10-09T12:00:00Z', values: { nome: 'Mario', rilascio: '' }, protectedFields: [] }
  assert.deepEqual(restoredProtectedFields(draft, { nome: '', rilascio: '' }), [])
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { registryCompleteness } from '../../frontend/src/features/anagrafiche/registryCompleteness.ts'

test('empty form has no completed fields, and clearing a contact removes its completion', () => {
  assert.equal(registryCompleteness({}, { legal: false }).filter(row => row.complete).length, 0)
  assert.equal(registryCompleteness({ email: 'test@example.invalid' }, { legal: false }).filter(row => row.complete).length, 1)
  assert.equal(registryCompleteness({ email: ' ' }, { legal: false }).filter(row => row.complete).length, 0)
})

test('rejected reading is explicit even if the old document fields remain populated', () => {
  const values = { doc_numero: 'TEST', doc_rilasciato_da: 'Comune di prova', doc_data_rilascio: '2024-01-01', doc_data_scadenza: '2034-01-01' }
  assert.equal(registryCompleteness(values, { legal: false }).at(-1).complete, true)
  const result = registryCompleteness(values, { legal: false, documentRejected: true }).at(-1)
  assert.equal(result.complete, false)
  assert.match(result.detail, /Lettura non accettata/)
})

test('a company uses its registered office and does not request a personal identity card', () => {
  const rows = registryCompleteness({ ragione_sociale: 'Ente prova', partita_iva: '12345678901', via: 'Via prova', comune: 'Roma', provincia: 'RM', cap: '00100' }, { legal: true })
  assert.equal(rows.length, 3)
  assert.equal(rows[0].complete, true)
  assert.equal(rows[2].complete, false)
})

test('a party role is complete only if actually available in the authorized catalog', () => {
  assert.equal(registryCompleteness({ qualifica: 'inventato' }, { legal: false, subject: true, allowedRoles: ['CONTROPARTE'] }).at(-1).complete, false)
  assert.equal(registryCompleteness({ qualifica: 'CONTROPARTE' }, { legal: false, subject: true, allowedRoles: ['CONTROPARTE'] }).at(-1).complete, true)
})

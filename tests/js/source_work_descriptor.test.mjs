import assert from 'node:assert/strict'
import { test } from 'node:test'
import { sourceWorkDescriptor } from '../../frontend/src/components/sourceWorkDescriptor.ts'

const origin = 'https://app.iusentra.it'
const source = { href: '/fascicoli/DE674F4F/documenti/599A9B2E/visualizza', label: 'Documento del fascicolo', context: 'Scadenza selezionata', kind: 'documento' }

for (const href of [source.href, '/fascicoli/DE674F4F', '/email', '/email-ordinaria/messaggio/123', '/email/messaggio/123/allegato/0', '/api/v1/ui/email/source/123', '/api/v1/ui/fonti-procedurali/civile/documento', '/api/v1/ui/document-reader/web?url=https%3A%2F%2Fexample.test', '/api/v1/ui/controllo-studio/conoscenza-notifiche/fonti/fonte_1']) {
  test(`Fonte nativa: ${href}`, () => assert.equal(sourceWorkDescriptor({ ...source, href }, origin)?.href, href))
}

test('La fonte assoluta si normalizza conservando pagina e parametri del lettore', () => {
  assert.deepEqual(sourceWorkDescriptor({ ...source, href: origin + source.href + '?viewer=mobile#pagina-1' }, origin), { ...source, href: source.href + '?viewer=mobile#pagina-1' })
})

for (const href of ['https://example.test' + source.href, 'https://user:secret@app.iusentra.it' + source.href, 'javascript:alert(1)', 'blob:' + origin + '/123', '/fascicoli/DE674F4F/documenti/599A9B2E/firma', '/fascicoli/DE674F4F/deposito', '/email/invia', '/fascicoli/DE674F4F/documenti/599A9B2E/scarica', '/api/v1/ui/fonti-procedurali/x/elimina', '/amministrazione']) {
  test(`Nessun inoltro operativo o esterno: ${href}`, () => assert.equal(sourceWorkDescriptor({ ...source, href }, origin), null))
}

test('Descrittori mancanti, ambigui o eccessivi non aprono finestre', () => {
  for (const value of [null, undefined, [], {}, 42, source.href, { ...source, label: ' ' }, { ...source, context: null }, { ...source, label: 'x'.repeat(241) }, { ...source, context: 'x'.repeat(2001) }, { ...source, href: 'x'.repeat(8001) }]) assert.equal(sourceWorkDescriptor(value, origin), null)
})

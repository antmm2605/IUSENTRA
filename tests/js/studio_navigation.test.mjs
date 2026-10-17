import test from 'node:test'
import assert from 'node:assert/strict'
import { filterStudioNavigation } from '../../frontend/src/studioNavigation.ts'
const items = [
  { label: 'Prima nota e contabilità', href: '/prima-nota', group: 'gestione', keywords: 'entrate uscite movimenti' },
  { label: 'Redazione Atti', href: '/redazione-atti', group: 'documenti', keywords: 'ricorso memoria modelli' },
  { label: 'Parcelle e Fatture', href: '/fatturazione/', group: 'gestione' },
]
test('ricerca locale per etichetta, accenti e parole operative', () => {
  assert.equal(filterStudioNavigation(items, 'CONTABILITA')[0].href, '/prima-nota')
  assert.equal(filterStudioNavigation(items, 'memoria')[0].href, '/redazione-atti')
  assert.equal(filterStudioNavigation(items, 'atti redazione')[0].href, '/redazione-atti')
  assert.equal(filterStudioNavigation(items, 'fatture')[0].href, '/fatturazione/')
  assert.equal(filterStudioNavigation(items, 'uscite')[0].href, '/prima-nota')
})
test('il filtro conserva ordine e perimetro dei soli collegamenti già autorizzati', () => {
  const before = structuredClone(items)
  assert.deepEqual(filterStudioNavigation(items, ''), items)
  assert.deepEqual(filterStudioNavigation(items, 'inesistente'), [])
  assert.deepEqual(filterStudioNavigation(items, 'Lex'), [])
  assert.deepEqual(items, before)
})


test('ricerca comune comprende fascicoli, PEC, agenda e impostazioni già autorizzati', () => {
  const authorized = [
    ...items,
    { label: 'Nuovo Fascicolo', href: '/fascicoli/nuovo' },
    { label: 'Email PEC', href: '/email/' },
    { label: 'Agenda', href: '/agenda' },
    { label: 'Impostazioni', href: '/impostazioni' },
  ]
  for (const [query, href] of [['fascicolo', '/fascicoli/nuovo'], ['PEC', '/email/'], ['agenda', '/agenda'], ['impostazioni', '/impostazioni']]) {
    assert.equal(filterStudioNavigation(authorized, query)[0].href, href)
  }
  assert.equal(filterStudioNavigation(authorized, 'utenti amministrazione').length, 0)
  assert.deepEqual(filterStudioNavigation(authorized, ''), authorized)
})

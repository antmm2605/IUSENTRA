import './support/resolve_ts_extensionless.mjs'
// Guardrail tecnici: non sostituiscono la prova nel browser reale.
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
const { getEmailPecPage, getEmailOrdinariaPage } = await import('../../frontend/src/emailData.ts')

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('PEC del fascicolo: il client conserva pratica, cartella e originali archiviati', async () => {
  let requested
  globalThis.fetch = async url => {
    requested = new URL(url, 'http://localhost:8080')
    return { ok: true, json: async () => ({
      items: [], summary: { total: 0, filtered: 0 },
      matter: { id: 'case-a', title: 'Pratica controllata', href: '/fascicoli/case-a',
        archivedMessages: [{ id: 'doc-a', name: 'Originale.eml', href: '/fascicoli/case-a/documenti/doc-a/visualizza' }] },
    }) }
  }
  const result = await getEmailPecPage({ fascicoloId: 'case-a', folder: 'CESTINO' })
  assert.equal(requested.searchParams.get('id_fascicolo'), 'case-a')
  assert.equal(requested.searchParams.get('cartella'), 'CESTINO')
  assert.equal(result.matter.id, 'case-a')
  assert.equal(result.matter.archivedMessages[0].name, 'Originale.eml')
})

test('fascicolo non disponibile: mostra la causa senza restituire una casella vuota', async () => {
  globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({ message: 'Fascicolo non trovato.' }) })
  await assert.rejects(getEmailPecPage({ fascicoloId: 'missing' }), /Fascicolo non trovato/)
})

for (const [name, load] of [['PEC', getEmailPecPage], ['ordinaria', getEmailOrdinariaPage]]) {
  test(`${name}: una casella realmente vuota rimane un risultato valido`, async () => {
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ items: [], summary: { total: 0, filtered: 0 } }) })
    assert.equal((await load()).summary.total, 0)
  })
  for (const [status, expected] of [[401, /sessione è scaduta/], [403, /permesso/], [503, /caricare la casella/]]) {
    test(`${name}: errore HTTP ${status} non diventa un conteggio zero`, async () => {
      globalThis.fetch = async () => ({ ok: false, status })
      await assert.rejects(load(), expected)
    })
  }
  test(`${name}: errore di rete viene comunicato in italiano`, async () => {
    globalThis.fetch = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(load(), /Controlla la connessione e riprova/)
  })
  test(`${name}: contenuto non JSON non diventa casella vuota`, async () => {
    globalThis.fetch = async () => ({ ok: true, json: async () => { throw new SyntaxError('Unexpected token') } })
    await assert.rejects(load(), /caricamento della posta si è interrotto/)
  })
  for (const [label, payload] of [
    ['errore dichiarato', { ok: false, items: [], summary: {} }],
    ['riepilogo assente', { items: [] }],
    ['elenco assente', { summary: {} }],
    ['risposta nulla', null],
  ]) {
    test(`${name}: ${label} non viene mascherato dai dati predefiniti`, async () => {
      globalThis.fetch = async () => ({ ok: true, json: async () => payload })
      await assert.rejects(load(), /dati della casella non sono disponibili/)
    })
  }
}

// Guardrail tecnico: accettazione finale soltanto nel browser reale su8080.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { FormSubmitError, submitFormJson } from '../../frontend/src/formSubmit.ts'

async function withResponse(response, run) {
  const saved = { fetch: globalThis.fetch, window: globalThis.window, document: globalThis.document }
  const events = []
  globalThis.window = { location: { origin: 'http://127.0.0.1:8080', href: 'http://127.0.0.1:8080/fascicoli' },
    dispatchEvent: event => events.push(event) }
  globalThis.document = { querySelector: () => null }
  globalThis.fetch = async () => response
  try { await run(events) } finally { Object.assign(globalThis, saved) }
}

test('conflitto409 conserva tipo, messaggio e contenuto della bozza', async () => {
  const draft = new FormData()
  draft.set('note', 'Bozza dell’avvocato: attività già preparata')
  await withResponse(new Response(JSON.stringify({ ok: false, message: 'Il fascicolo è cambiato. La bozza resta nel modulo.' }),
    { status: 409, headers: { 'Content-Type': 'application/json' } }), async events => {
    await assert.rejects(() => submitFormJson('/fascicoli/CONTROL/modifica', draft), error => {
      assert.ok(error instanceof FormSubmitError)
      assert.equal(error.status, 409)
      assert.match(error.message, /bozza resta/)
      return true
    })
    assert.equal(draft.get('note'), 'Bozza dell’avvocato: attività già preparata')
    assert.equal(events.length, 0)
  })
})

test('il modulo protetto non scambia una risposta incompleta per un salvataggio', async () => {
  for (const body of ['{}', 'null', '[]', '{"ok":"true"}', '{malformed']) {
    await withResponse(new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } }),
      async events => {
        await assert.rejects(() => submitFormJson('/fascicoli/CONTROL/modifica', new FormData(),
          { requireConfirmation: true }), /conferm|leggibile/)
        assert.equal(events.length, 0)
      })
  }
})

test('conferma riuscita mantiene risposta e aggiornamento delle viste governate', async () => {
  await withResponse(new Response(JSON.stringify({ ok: true, message: 'Modifiche salvate.', redirect: '/clienti/CONTROL' }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }), async events => {
    const result = await submitFormJson('/clienti/CONTROL/modifica', new FormData(), { requireConfirmation: true })
    assert.equal(result.ok, true)
    assert.equal(result.redirect, '/clienti/CONTROL')
    assert.equal(events.length, 1)
  })
})

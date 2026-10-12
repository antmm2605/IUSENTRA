import { test } from 'node:test'
import assert from 'node:assert/strict'
import { requestJson } from '../../frontend/src/components/viewerEditorApi.ts'

test('lettura: recupera una risposta vuota temporanea e restituisce solo il risultato valido', async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => ++calls === 1
    ? new Response('', { status: 503 })
    : Response.json({ editable: true, hash: 'source' }))
  assert.deepEqual(await requestJson('/reader'), { editable: true, hash: 'source' })
  assert.equal(calls, 2)
})

test('lettura: termina dopo tre tentativi senza mostrare HTML o errori del parser', async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; return new Response('<html>gateway interno</html>', { status: 502 }) })
  await assert.rejects(requestJson('/reader'), /non ha ricevuto una risposta valida/)
  assert.equal(calls, 3)
})

test('scrittura: non ripete un salvataggio con esito non ricevuto', async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; return new Response('', { status: 503 }) })
  await assert.rejects(requestJson('/reader', { method: 'POST', body: '{}' }), /risposta valida/)
  assert.equal(calls, 1)
})

test('permessi: conserva il rifiuto del server senza nuovi tentativi', async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; return Response.json({ ok: false, message: 'Accesso non autorizzato.' }, { status: 403 }) })
  await assert.rejects(requestJson('/reader'), /Accesso non autorizzato/)
  assert.equal(calls, 1)
})

test('chiusura: interrompe l’attesa e non effettua richieste successive', async t => {
  const controller = new AbortController()
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; controller.abort(); return new Response('', { status: 503 }) })
  await assert.rejects(requestJson('/reader', { signal: controller.signal }), { name: 'AbortError' })
  assert.equal(calls, 1)
})

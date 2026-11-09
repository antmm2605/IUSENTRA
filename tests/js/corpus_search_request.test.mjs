import assert from 'node:assert/strict'
import test from 'node:test'
import { createCorpusRequestGate } from '../../frontend/src/corpusSearchRequest.ts'

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { resolve, promise }
}

test('i refresh concorrenti condividono la richiesta già in corso', async () => {
  const gate = createCorpusRequestGate()
  const body = deferred()
  let calls = 0
  const task = async (controller, current) => {
    calls++
    await body.promise
    return current() && !controller.signal.aborted
  }
  const first = gate.run('curia', '', task)
  await Promise.resolve()
  for (let i = 0; i < 25; i++) assert.equal(gate.run('curia', '', task), first)
  assert.equal(calls, 1)
  body.resolve()
  assert.equal(await first, true)
  assert.equal(await gate.run('curia', '', task), true)
  assert.equal(calls, 2)
})

test('una ricerca manuale prevale e una risposta obsoleta non può aggiornare il risultato', async () => {
  const gate = createCorpusRequestGate()
  const body = deferred()
  let cancelled
  const first = gate.run('curia', '', async (controller, current) => {
    await body.promise
    cancelled = controller.signal.aborted
    return current()
  })
  await Promise.resolve()
  const manual = gate.run('curia', 'ECLI:EU:C:2009:804', async (controller, current) => current() && !controller.signal.aborted)
  body.resolve()
  assert.equal(await manual, true)
  assert.equal(await first, false)
  assert.equal(cancelled, true)
})

test('cambiare fonte o lasciare la pagina invalida la richiesta precedente', async () => {
  const gate = createCorpusRequestGate()
  const task = async (controller, current) => current() && !controller.signal.aborted
  const first = gate.run('curia', '2009', task)
  const next = gate.run('hudoc', '2009', task)
  gate.cancel()
  assert.equal(await first, false)
  assert.equal(await next, false)
  assert.equal(await gate.run('hudoc', '2009', task), true)
})

test('dopo un errore la ricerca si può ripetere', async () => {
  const gate = createCorpusRequestGate()
  await assert.rejects(gate.run('curia', '', async () => { throw new Error('rete') }), /rete/)
  assert.equal(await gate.run('curia', '', async (_, current) => current()), true)
})

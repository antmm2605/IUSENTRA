import { test } from 'node:test'
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
const { parseCtuWriteProtocol, ctuPendingStorageKey, savePendingCtuCommand, loadPendingCtuCommand, clearPendingCtuCommand, isCtuCommandConfirmed, isCtuCommandRejected, CtuCommandSession } = await import('../../frontend/src/ctuCommand.ts')
const context = { scope: 'a'.repeat(64), fascicoloId: 'F1', incaricoId: 'I1' }
const command = () => ({ ...context, commandKey: randomUUID(), expectedRevision: 7, href: '/fascicoli/F1/ctu/I1/compenso',
  body: { modalita: 'tabella', voci: [{ codice: '1', valore: '260', quantita: '2' }], ritardo: false } })
const storage = () => {
  const map = new Map()
  return { getItem: key => map.get(key) ?? null, setItem: (key, value) => map.set(key, value), removeItem: key => map.delete(key) }
}
test('recupera UUID, revisione e righe originali senza ricalcolare l’intento', () => {
  const local = storage(), saved = command()
  savePendingCtuCommand(local, saved)
  assert.deepEqual(loadPendingCtuCommand(local, context), saved)
  assert.deepEqual(loadPendingCtuCommand(local, context), saved)
  clearPendingCtuCommand(local, context)
  assert.equal(loadPendingCtuCommand(local, context), null)
})
test('studio, operatore, fascicolo e incarico delimitano il recupero', () => {
  const local = storage()
  savePendingCtuCommand(local, command())
  for (const other of [{ ...context, scope: 'b'.repeat(64) }, { ...context, fascicoloId: 'F2' }, { ...context, incaricoId: 'I2' }]) {
    assert.equal(loadPendingCtuCommand(local, other), null)
  }
})
test('contenuto corrotto resta presente e non viene trattato come comando assente', () => {
  const local = storage(), key = ctuPendingStorageKey(context)
  local.setItem(key, '{corrotto')
  assert.throws(() => loadPendingCtuCommand(local, context))
  assert.equal(local.getItem(key), '{corrotto')
})
test('rifiuta revisioni, UUID e destinazioni che non appartengono al contesto', () => {
  const local = storage()
  for (const change of [{ expectedRevision: -1 }, { expectedRevision: 1.5 }, { expectedRevision: true }, { commandKey: 'non-uuid' },
    { href: 'https://example.invalid' }, { href: '/fascicoli/F2/ctu/I1/compenso' }, { href: '/fascicoli/F1/ctu/I2/compenso' },
    { href: '/fascicoli/F2/ctu/I1/istanza' }, { href: '/fascicoli/F2/ctu/I1/proponi-scadenze' }]) {
    assert.throws(() => savePendingCtuCommand(local, { ...command(), ...change }))
  }
  assert.equal(loadPendingCtuCommand(local, context), null)
})
test('consegna scadenze conserva il comando nel contesto dell’incarico', () => {
  const local = storage(), saved = { ...command(), href: '/fascicoli/F1/ctu/I1/proponi-scadenze', body: {} }
  savePendingCtuCommand(local, saved)
  assert.deepEqual(loadPendingCtuCommand(local, context), saved)
  assert.equal(loadPendingCtuCommand(local, { ...context, incaricoId: 'I2' }), null)
})
test('non serializza perdendo dati non JSON o metadati riservati', () => {
  const local = storage()
  for (const body of [{ valore: NaN }, { valore: Infinity }, { dato: undefined }, { date: new Date() }, { commandKey: randomUUID() },
    { expectedRevision: 4 }, { valore: 'x'.repeat(140000) }]) assert.throws(() => savePendingCtuCommand(local, { ...command(), body }))
})
test('creazione e rimozione riconoscono solo il percorso nativo previsto', () => {
  const local = storage(), created = { ...command(), incaricoId: '', href: '/fascicoli/F1/ctu/nuovo' }
  savePendingCtuCommand(local, created)
  assert.deepEqual(loadPendingCtuCommand(local, { ...context, incaricoId: '' }), created)
  const removal = { ...command(), href: '/fascicoli/F1/ctu/I1/operazioni/OP1/rimuovi', body: {} }
  savePendingCtuCommand(local, removal)
  assert.deepEqual(loadPendingCtuCommand(local, context), removal)
})
test('errori dell’archivio browser non consentono di proseguire in memoria', () => {
  assert.throws(() => savePendingCtuCommand({ setItem() { throw new Error('quota') } }, command()))
  assert.throws(() => loadPendingCtuCommand({ getItem() { throw new Error('accesso') } }, context))
})
test('protocollo storico non promette comandi persistenti; quello SQL richiede scope e revisione', () => {
  assert.equal(parseCtuWriteProtocol(undefined).persistentCommands, false)
  assert.equal(parseCtuWriteProtocol({ persistentCommands: false, revision: null }).persistentCommands, false)
  assert.deepEqual(parseCtuWriteProtocol({ persistentCommands: true, revision: 0, scope: context.scope }), { persistentCommands: true, revision: 0, scope: context.scope })
  for (const value of [null, {}, { persistentCommands: true, revision: 0 }, { persistentCommands: true, revision: true, scope: context.scope },
    { persistentCommands: true, revision: Number.MAX_SAFE_INTEGER + 1, scope: context.scope }, { persistentCommands: false, revision: 0 }]) {
    assert.throws(() => parseCtuWriteProtocol(value))
  }
})
test('solo il riscontro concordante del comando permette di liberare il pendente', () => {
  const saved = command()
  const receipt = { scope: saved.scope, commandKey: saved.commandKey, fascicoloId: saved.fascicoloId,
    incaricoId: saved.incaricoId, committedRevision: saved.expectedRevision + 1 }
  assert.equal(isCtuCommandConfirmed({ ok: true, confirmedCommand: receipt }, saved), true)
  assert.equal(isCtuCommandConfirmed({ ok: true }, saved), false)
  for (const change of [{ scope: 'b'.repeat(64) }, { commandKey: randomUUID() }, { fascicoloId: 'F2' }, { incaricoId: 'I2' },
    { committedRevision: 7 }, { committedRevision: 9 }, { committedRevision: '8' }]) {
    assert.equal(isCtuCommandConfirmed({ ok: true, confirmedCommand: { ...receipt, ...change } }, saved), false)
  }
  assert.equal(isCtuCommandConfirmed({ ok: false, confirmedCommand: receipt }, saved), false)
  assert.equal(isCtuCommandConfirmed({ ok: true, confirmedCommand: { ...receipt, incaricoId: 'NUOVO' } }, { ...saved, incaricoId: '' }), true)
})

const confirmed = (body) => ({ ok: true, confirmedCommand: { ...context, commandKey: body.commandKey, committedRevision: body.expectedRevision + 1 } })

test('rifiuto persistente concordante libera solo il comando e consente una bozza corretta', async () => {
  const local = storage(), draft = command().body
  const session = new CtuCommandSession(local, async (_href, body) => ({ ok: false, code: 'validation', message: 'Correggi i dati.',
    rejectedCommand: { ...context, commandKey: body.commandKey, expectedRevision: body.expectedRevision,
      rejectedAtRevision: 7, status: 'rejected' } }), randomUUID)
  assert.equal((await session.start(context, 7, command().href, draft)).terminalRejected, true)
  assert.equal(loadPendingCtuCommand(local, context), null)
  assert.equal(draft.voci[0].valore, '260')
  assert.equal((await session.start(context, 7, command().href, draft)).terminalRejected, true)
})

test('un rifiuto discordante non autorizza la liberazione del pendente', () => {
  const saved = command()
  const receipt = { ...context, commandKey: saved.commandKey, expectedRevision: 7, rejectedAtRevision: 7, status: 'rejected' }
  assert.equal(isCtuCommandRejected({ ok: false, code: 'validation', rejectedCommand: receipt }, saved), true)
  for (const change of [{ scope: 'b'.repeat(64) }, { commandKey: randomUUID() }, { fascicoloId: 'F2' }, { incaricoId: 'I2' },
    { expectedRevision: 8 }, { rejectedAtRevision: -1 }, { rejectedAtRevision: '7' }, { status: 'unknown' }]) {
    assert.equal(isCtuCommandRejected({ ok: false, code: 'validation', rejectedCommand: { ...receipt, ...change } }, saved), false)
  }
})

test('risposta perduta recupera lo stesso comando anche se il modulo è cambiato', async () => {
  const local = storage(), sends = [], draft = command().body
  const session = new CtuCommandSession(local, async (href, body) => {
    sends.push({ href, body })
    if (sends.length === 1) throw new Error('Risposta perduta dopo il commit')
    return confirmed(body)
  }, randomUUID)
  assert.equal((await session.start(context, 7, command().href, draft)).ok, false)
  draft.voci[0].valore = '500'
  assert.equal((await session.start(context, 8, command().href, draft)).code, 'pending_command')
  assert.equal((await session.recover(context)).ok, true)
  assert.deepEqual(sends[1], sends[0])
  assert.equal(sends[1].body.voci[0].valore, '260')
  assert.equal(loadPendingCtuCommand(local, context), null)
})

test('ok generico, errore di validazione e conflitto non cancellano il pendente', async () => {
  for (const response of [{ ok: true }, { ok: false, code: 'validation', message: 'Dati non validi' }, { ok: false, code: 'conflict' }]) {
    const local = storage(), session = new CtuCommandSession(local, async () => response, randomUUID)
    assert.equal((await session.start(context, 7, command().href, command().body)).ok, false)
    assert.ok(loadPendingCtuCommand(local, context))
  }
})

test('nessun invio prima della persistenza e nessun invio concorrente', async () => {
  const local = storage()
  let release, calls = 0
  const session = new CtuCommandSession(local, async (_href, body) => {
    calls++
    assert.ok(loadPendingCtuCommand(local, context))
    await new Promise(resolve => { release = resolve })
    return confirmed(body)
  }, randomUUID)
  const first = session.start(context, 7, command().href, command().body)
  assert.equal((await session.recover(context)).code, 'command_in_progress')
  assert.equal((await session.start({ ...context, incaricoId: 'I2' }, 7, '/fascicoli/F1/ctu/I2/aggiorna', {})).code, 'command_in_progress')
  release()
  assert.equal((await first).ok, true)
  assert.equal(calls, 1)
  const blocked = new CtuCommandSession({ ...local, setItem() { throw new Error('quota') } }, async () => assert.fail('Non deve inviare'), randomUUID)
  await assert.rejects(blocked.start(context, 8, command().href, {}))
})

test('il riscontro non elimina un pendente sostituito durante la risposta', async () => {
  const local = storage(), replacement = command()
  const session = new CtuCommandSession(local, async (_href, body) => {
    savePendingCtuCommand(local, replacement)
    return confirmed(body)
  }, randomUUID)
  assert.equal((await session.start(context, 7, command().href, {})).code, 'pending_changed')
  assert.deepEqual(loadPendingCtuCommand(local, context), replacement)
})

test('riapertura usa archivio e identità originali; altro operatore non può recuperare', async () => {
  const local = storage(), saved = command()
  savePendingCtuCommand(local, saved)
  let calls = 0
  const reopened = new CtuCommandSession(local, async (_href, body) => { calls++; return confirmed(body) }, () => assert.fail('Nessun nuovo UUID'))
  assert.equal((await reopened.recover({ ...context, scope: 'b'.repeat(64) })).code, 'command_missing')
  assert.equal(calls, 0)
  assert.equal((await reopened.recover(context)).ok, true)
  assert.equal(calls, 1)
})

test('errore nella rimozione conserva il comando e permette un nuovo recupero', async () => {
  const local = storage()
  let unavailable = true
  const guarded = { ...local, removeItem(key) { if (unavailable) throw new Error('Archivio indisponibile'); local.removeItem(key) } }
  const session = new CtuCommandSession(guarded, async (_href, body) => confirmed(body), randomUUID)
  assert.equal((await session.start(context, 7, command().href, {})).ok, false)
  assert.ok(loadPendingCtuCommand(local, context))
  unavailable = false
  assert.equal((await session.recover(context)).ok, true)
  assert.equal(loadPendingCtuCommand(local, context), null)
})

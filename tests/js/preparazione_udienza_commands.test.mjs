import { test } from 'node:test'
import assert from 'node:assert/strict'
const { preparationCommand, loadPreparationCommand } = await import('../../frontend/src/preparazioneUdienzaCommand.ts')
const { preparationSnapshot, mergePreparationRefresh, acknowledgedPreparationValues, applyPreparationDraft, preservePreparationDraft, restorePreparationDraft } = await import('../../frontend/src/preparazioneUdienzaDraft.ts')
const context = { scope: 'a'.repeat(64), target: 'S1', sessionId: 'S1' }
const url = '/api/v1/ui/preparazione-udienza/S1/passo'
function storage() { const map = new Map(); return { getItem: key => map.get(key) ?? null, setItem: (key, value) => map.set(key, value), removeItem: key => map.delete(key) } }
const receipt = body => ({ ok: true, confirmedCommand: { scope: context.scope, commandKey: body.commandKey, sessionId: 'S1', committedRevision: body.expectedRevision + 1 } })

test('risposta persa conserva intento e UUID: recupero non utilizza la nuova bozza', async () => {
  const local = storage(), body = { passo: 1, campi: { step1_note: 'Nota originale' } }
  await preparationCommand(local, async () => ({ ok: false }), context, 2, url, body)
  const pending = loadPreparationCommand(local, context.scope, context.target)
  body.campi.step1_note = 'Bozza successiva'
  const response = await preparationCommand(local, async (_, sent) => {
    assert.equal(sent.commandKey, pending.commandKey)
    assert.equal(sent.expectedRevision, 2)
    assert.equal(sent.campi.step1_note, 'Nota originale')
    return receipt(sent)
  }, context, 8, '', {}, true)
  assert.equal(response.ok, true)
  assert.equal(loadPreparationCommand(local, context.scope, context.target), null)
})

test('ricevuta non concordante non cancella il comando; altri tenant non lo recuperano', async () => {
  const local = storage()
  const result = await preparationCommand(local, async (_, body) => ({ ...receipt(body), confirmedCommand: { ...receipt(body).confirmedCommand, scope: 'b'.repeat(64) } }), context, 2, url, {})
  assert.equal(result.ok, false)
  assert.ok(loadPreparationCommand(local, context.scope, context.target))
  assert.equal(loadPreparationCommand(local, 'b'.repeat(64), context.target), null)
})

test('rifiuto persistente concordante chiude solo il comando: il chiamante conserva la bozza', async () => {
  const local = storage()
  const result = await preparationCommand(local, async (_, body) => ({ ok: false, code: 'conflict', rejectedCommand: {
    status: 'rejected', scope: context.scope, sessionId: 'S1', commandKey: body.commandKey, expectedRevision: 2, revision: 4,
  } }), context, 2, url, {})
  assert.equal(result.terminalRejected, true)
  assert.equal(loadPreparationCommand(local, context.scope, context.target), null)
})

test('due invii durante lo stesso comando non sbloccano il primo', async () => {
  const local = storage(); let release
  const first = preparationCommand(local, (_, body) => new Promise(resolve => { release = () => resolve(receipt(body)) }), context, 2, url, {})
  const second = await preparationCommand(local, async () => assert.fail('Secondo invio'), context, 2, url, {})
  const third = await preparationCommand(local, async () => assert.fail('Terzo invio'), context, 2, url, {}, true)
  assert.equal(second.code, 'in_progress'); assert.equal(third.code, 'in_progress')
  release(); assert.equal((await first).ok, true)
})

test('archivio indisponibile o dati non JSON non avviano richieste', async () => {
  for (const local of [storage(), { getItem: () => null, setItem: () => { throw new Error('quota') }, removeItem() {} }]) {
    const result = await preparationCommand(local, async () => assert.fail('Invio non autorizzato'), context, 0, url, { v: undefined })
    assert.equal(result.ok, false)
  }
  const result = await preparationCommand({ getItem: () => null, setItem: () => { throw new Error('quota') }, removeItem() {} },
    async () => assert.fail('Nessun invio senza conservazione'), context, 0, url, {})
  assert.equal(result.ok, false)
})

const source = { campi: { step1_note: 'Prima', note_preparazione: '' }, tipoUdienza: '', documenti: [], verifiche: [], revision: 1 }
test('live aggiorna i campi puliti e conserva la bozza; la discordanza è esplicita', () => {
  const current = { ...source, campi: { ...source.campi, step1_note: 'Bozza locale' } }
  const remote = { ...source, campi: { step1_note: 'Modifica concorrente', note_preparazione: 'Nuova strategia' }, revision: 2 }
  const merged = mergePreparationRefresh(current, preparationSnapshot(source), remote)
  assert.equal(merged.values.campi.step1_note, 'Bozza locale')
  assert.equal(merged.values.campi.note_preparazione, 'Nuova strategia')
  assert.deepEqual(merged.conflicts, ['step1_note'])
})

test('una risposta non elimina testi digitati durante il salvataggio in altri campi', () => {
  const sent = { passo: 1, campi: { step1_note: 'Salvata' } }
  const current = { ...applyPreparationDraft(source, 'passo', sent), campi: { step1_note: 'Salvata', note_preparazione: 'Digitata durante invio' } }
  const response = { ...source, campi: { step1_note: 'Salvata', note_preparazione: '' }, revision: 2 }
  const merged = mergePreparationRefresh(current, acknowledgedPreparationValues(preparationSnapshot(source), 'passo', sent), response)
  assert.equal(merged.values.campi.note_preparazione, 'Digitata durante invio')
  assert.deepEqual(merged.conflicts, [])
})

test('scelta tipo e checklist confermata non viene riportata al valore precedente', () => {
  const intent = { passo: 1, campi: { tipo_udienza: 'discussione' } }
  const current = applyPreparationDraft(source, 'passo', intent)
  const merged = mergePreparationRefresh(current, acknowledgedPreparationValues(preparationSnapshot(source), 'passo', intent), { ...source, tipoUdienza: 'discussione' })
  assert.equal(merged.values.tipoUdienza, 'discussione')
})

const completeSource = { ...source, id: 'S1', esito: { valore: '', rinvioData: '', rinvioOra: '09:00', noteVerbale: '', azioni: '', termini: [], rinvioAgendaHref: '' } }
test('ricaricamento conserva bozza separata per studio e confronta aggiornamenti concorrenti', () => {
  const local = storage(), draft = { ...completeSource, campi: { ...completeSource.campi, step1_note: 'Non ancora salvata' } }
  preservePreparationDraft(local, context.scope, completeSource, draft, false)
  assert.equal(restorePreparationDraft(local, context.scope, completeSource).values.campi.step1_note, 'Non ancora salvata')
  const concurrent = { ...completeSource, campi: { ...completeSource.campi, step1_note: 'Altro operatore' }, revision: 2 }
  const restored = restorePreparationDraft(local, context.scope, concurrent)
  assert.equal(restored.values.campi.step1_note, 'Non ancora salvata')
  assert.deepEqual(restored.conflicts, ['step1_note'])
  assert.equal(restorePreparationDraft(local, 'b'.repeat(64), concurrent).values.campi.step1_note, 'Altro operatore')
  preservePreparationDraft(local, context.scope, concurrent, concurrent, false)
  assert.equal(restorePreparationDraft(local, context.scope, concurrent).values.campi.step1_note, 'Altro operatore')
})
test('esito in bozza recuperato non viene nascosto da un esito concorrente', () => {
  const local = storage(), draft = { ...completeSource, esito: { ...completeSource.esito, valore: 'rinvio', rinvioData: '2026-12-12', noteVerbale: 'Bozza verbale' } }
  preservePreparationDraft(local, context.scope, completeSource, draft, true)
  const restored = restorePreparationDraft(local, context.scope, { ...completeSource, completata: true, esito: { ...completeSource.esito, valore: 'favorevole' } })
  assert.equal(restored.outcomeDirty, true)
  assert.equal(restored.values.completata, false)
  assert.equal(restored.values.esito.noteVerbale, 'Bozza verbale')
  assert.deepEqual(restored.conflicts, ['esito'])
})

test('documento aggiuntivo in bozza sopravvive a live e riapertura senza scritture SQL', () => {
  const local = storage(), draft = { ...completeSource, campi: { ...completeSource.campi, documento_extra: 'Originale da portare' } }
  preservePreparationDraft(local, context.scope, completeSource, draft, false)
  assert.equal(restorePreparationDraft(local, context.scope, completeSource).values.campi.documento_extra, 'Originale da portare')
  const incoming = { ...completeSource, campi: { ...completeSource.campi, note_preparazione: 'Aggiornamento remoto' } }
  const merged = mergePreparationRefresh(draft, preparationSnapshot(completeSource), incoming)
  assert.equal(merged.values.campi.documento_extra, 'Originale da portare')
  assert.equal(merged.values.campi.note_preparazione, 'Aggiornamento remoto')
  assert.deepEqual(merged.conflicts, [])
})

test('bozza verbale conserva il testo dopo riapertura e segnala il conflitto remoto', () => {
  const local = storage()
  const baseline = { ...completeSource, campi: { ...completeSource.campi, verbale_preparazione: 'Testo iniziale' } }
  const draft = { ...baseline, campi: { ...baseline.campi, verbale_preparazione: 'Richiesta locale' } }
  preservePreparationDraft(local, context.scope, baseline, draft, false)
  const restored = restorePreparationDraft(local, context.scope, { ...baseline,
    campi: { ...baseline.campi, verbale_preparazione: 'Richiesta altro operatore' } })
  assert.equal(restored.values.campi.verbale_preparazione, 'Richiesta locale')
  assert.deepEqual(restored.conflicts, ['verbale_preparazione'])
  assert.deepEqual(restored.values.esito, baseline.esito)
})

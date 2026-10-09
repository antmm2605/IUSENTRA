// Guardrail del contratto dati; non sostituiscono l'accettazione nel browser reale.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import {afterEach, test} from 'node:test'
const {getPrimaNotaPage} = await import('../../frontend/src/primaNotaData.ts')
const {formatDateInputIt} = await import('../../frontend/src/formatting.ts')
const originalFetch = globalThis.fetch
const valid = {source: 'repository_reali', summary: {incassi: 0, pagamenti: 0, saldo: 0, movimenti: 0}, movimenti: []}
for (const [instant, date] of [
  ['2026-10-08T22:05:44Z', '2026-10-09'],
  ['2026-12-08T23:05:44Z', '2026-12-09'],
  ['2026-03-28T23:05:44Z', '2026-03-29'],
  ['2026-10-24T22:05:44Z', '2026-10-25'],
]) test(`data del movimento riferita a Roma: ${instant}`, () => {
  assert.equal(formatDateInputIt(new Date(instant)), date)
})
function respond(payload, status = 200) {
  globalThis.fetch = async () => ({ok: status < 400, status, json: async () => payload})
}
afterEach(() => { globalThis.fetch = originalFetch })
for (const status of [401, 403, 500, 503]) test(`HTTP ${status} non produce saldi fittizi`, async () => {
  respond({ok: false, message: 'Registro non disponibile'}, status)
  await assert.rejects(getPrimaNotaPage(), /Registro non disponibile/)
})
for (const payload of [{...valid, ok: false}, {}, {...valid, movimenti: undefined}, {...valid, summary: {}}, {...valid, summary: {...valid.summary, saldo: 'NaN'}}]) test('contratto negativo o incompleto non produce registro vuoto', async () => {
  respond(payload)
  await assert.rejects(getPrimaNotaPage())
})
test('errore di rete resta esplicito', async () => {
  globalThis.fetch = async () => { throw new Error('Connessione interrotta') }
  await assert.rejects(getPrimaNotaPage(), /Connessione interrotta/)
})
test('JSON non leggibile resta errore', async () => {
  globalThis.fetch = async () => ({ok: true, json: async () => { throw new SyntaxError('JSON incompleto') }})
  await assert.rejects(getPrimaNotaPage(), /JSON incompleto/)
})
test('registro realmente vuoto mantiene il contratto', async () => {
  respond(valid)
  const data = await getPrimaNotaPage()
  assert.equal(data.source, 'repository_reali')
  assert.equal(data.summary.saldo, 0)
  assert.deepEqual(data.movimenti, [])
})
test('importo reale mantiene valore numerico ed etichetta italiana', async () => {
  respond({...valid, summary: {...valid.summary, saldo: 1234.56, saldoLabel: '€ 1.234,56'}})
  const data = await getPrimaNotaPage()
  assert.equal(data.summary.saldo, 1234.56)
  assert.equal(data.summary.saldoLabel, '€ 1.234,56')
})

const {getRiepilogoAnnuale, validateRiepilogoAnnuale} = await import('../../frontend/src/riepilogoAnnualeData.ts')
const annuale = {ok: true, anno: 2026, regime: 'forfettario', compensi_incassati: 0,
  anticipazioni_rimborsate: 0, anticipazioni_per_clienti: 0, spese_deducibili: 0,
  contributi_previdenziali_versati: 0, imposte_versate: 0, note: [], avvisi: [],
  mesi: Array.from({length: 12}, (_, i) => ({mese: String(i+1), incassi: 0, pagamenti: 0}))}
test('riepilogo realmente vuoto rimane valido', () => {
  assert.equal(validateRiepilogoAnnuale(annuale, 2026).compensi_incassati, 0)
})
for (const patch of [{ok: false}, {anno: 2025}, {compensi_incassati: undefined},
  {spese_deducibili: '0'}, {imposte_versate: NaN}, {regime: 'ignoto'}, {mesi: []},
  {stima: {imponibile: 'non determinato'}}, {regime: 'ordinario'},
  {registro_iva: {note: [], liquidazioni: [], totale_imponibile: 0}}]) {
  test('riepilogo incompleto non produce zero o regime inventato', () => {
    assert.throws(() => validateRiepilogoAnnuale({...annuale, ...patch}, 2026))
  })
}
test('errore HTTP del riepilogo resta esplicito', async () => {
  respond(annuale, 503)
  await assert.rejects(getRiepilogoAnnuale(2026, false, new AbortController().signal))
})
test('richiesta riepilogo conserva anno, scelta e segnale di annullamento', async () => {
  const control = new AbortController()
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/ui/prima-nota/riepilogo?anno=2026&startup=1')
    assert.equal(options.signal, control.signal)
    return {ok: true, json: async () => annuale}
  }
  assert.equal((await getRiepilogoAnnuale(2026, true, control.signal)).anno, 2026)
})

for (const protocol of [{persistentCommands: true, revision: null},
  {persistentCommands: true, revision: '0'}, {persistentCommands: true, revision: -1},
  {persistentCommands: true, revision: 0.5}, {persistentCommands: false, revision: 1},
  {persistentCommands: 'true', revision: 0}, null]) {
  test('revisione SQL non valida non autorizza il comando', async () => {
    respond({...valid, writeProtocol: protocol})
    await assert.rejects(getPrimaNotaPage(), /Revisione/)
  })
}
for (const protocol of [{persistentCommands: true, revision: 0},
  {persistentCommands: true, revision: 31}, {persistentCommands: false, revision: null}]) {
  test('capacità del repository conservata senza inventare revisione', async () => {
    const scoped = {...protocol, scope: protocol.persistentCommands ? 'a'.repeat(64) : null}
    respond({...valid, writeProtocol: scoped})
    assert.deepEqual((await getPrimaNotaPage()).writeProtocol, scoped)
  })
}

const {loadPendingCommand,savePendingCommand,clearPendingCommand} = await import('../../frontend/src/primaNotaCommand.ts')
test('comando pendente sopravvive alla riapertura e resta separato per operatore', () => {
  const entries = new Map()
  const storage = {getItem:key=>entries.get(key)??null,setItem:(key,value)=>entries.set(key,value),removeItem:key=>entries.delete(key)}
  const command = {scope:'a'.repeat(64),commandKey:'12345678-1234-1234-1234-123456789abc',expectedRevision:0,
    body:{data:'2026-10-09',tipo:'INCASSO',importo:'260',categoria:'onorari',controparte:'Prova controllata',causale:'Prova',metodo:'banca',documento:''}}
  savePendingCommand(storage,command)
  assert.deepEqual(loadPendingCommand(storage,command.scope),command)
  assert.equal(loadPendingCommand(storage,'b'.repeat(64)),null)
  clearPendingCommand(storage,command.scope)
  assert.equal(loadPendingCommand(storage,command.scope),null)
})
test('comando corrotto è preservato senza inventare una chiave nuova', () => {
  assert.throws(()=>loadPendingCommand({getItem:()=>'{interrotto'},'a'.repeat(64)))
})
test('archiviazione del comando non disponibile impedisce la sua preparazione', () => {
  assert.throws(()=>savePendingCommand({setItem:()=>{throw Error('storage indisponibile')}},{scope:'a'.repeat(64)}))
})

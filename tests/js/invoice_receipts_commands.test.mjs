// Guardrail tecnici: la prova finale resta sul browser reale della copia 8080.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import {afterEach, test} from 'node:test'
import {randomUUID} from 'node:crypto'
const {receiptAmountCents, receiptDateKey, getInvoiceReceipts, loadReceiptCommand, saveReceiptCommand,
  clearReceiptCommand, sendReceiptCommand, receiptStorageKey} = await import('../../frontend/src/invoiceReceiptsData.ts')
const {loadReceiptDraft, saveReceiptDraft} = await import('../../frontend/src/invoiceReceiptDraft.ts')
const original = {fetch:globalThis.fetch, document:globalThis.document, window:globalThis.window}
afterEach(() => {Object.assign(globalThis, original)})
const command = () => ({invoice_id:'INV1', scope:'a'.repeat(64), command_key:randomUUID(), expected_revision:'b'.repeat(64),
  paid_on:'2026-10-20', operation:'receipt', amount_cents:40000, method:'banca', note:'Riferimento controllato'})
const storage = () => {const values=new Map(); return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}}
const summary = () => ({invoice_id:'INV1',invoice_state:'EMESSA',is_proforma:false,paid_cents:40000,residual_cents:60000,due_cents:100000,
  status:'PARTIAL',revision:'c'.repeat(64),command_scope:'a'.repeat(64),can_write:true,
  receipts:[{movement_id:'MOV1',amount_cents:40000,direction:1,paid_on:'2026-10-20',method:'banca',note:'Riferimento controllato',reversed:false,reverses_movement_id:''}],
  methods:['banca','cassa','pos','altro'].map(value=>({value,label:value}))})
function respond(payload,status=200,notifications=[]){
  globalThis.document={querySelector:()=>({content:'controlled-csrf'})}
  globalThis.window={dispatchEvent:event=>notifications.push(event.detail)}
  globalThis.fetch=async()=>({ok:status>=200&&status<300,status,json:async()=>payload})
}
const ack = (saved,changes={}) => ({ok:true,movement_id:'MOV1',already_present:false,summary:summary(),confirmed_command:{invoice_id:saved.invoice_id,
  scope:saved.scope,command_key:saved.command_key,expected_revision:saved.expected_revision},...changes})

test('uno stato pagato non può confermare un riepilogo con residuo mancante', async()=>{
  for(const change of [{status:'PAID'}, {residual_cents:0}, {due_cents:50000}]){
    respond({ok:true,summary:{...summary(),...change}})
    await assert.rejects(getInvoiceReceipts('INV1'))
  }
  respond({ok:true,summary:{...summary(),invoice_state:'BOZZA',status:'DRAFT',paid_cents:0,residual_cents:0,receipts:[]}})
  assert.equal((await getInvoiceReceipts('INV1')).status,'DRAFT')
})

test('importi italiani e decimali sono convertiti senza perdere centesimi',()=>{
  for(const [input,expected] of [['€ 1.234,56',123456],['1234.56',123456],['1.234',123400],['400,00',40000],['0,01',1],['1000',100000]]){
    assert.equal(receiptAmountCents(input),expected)
  }
  for(const input of ['','-1','1e3','abc400','12,345','1.234.56','1/2','0','90071992547410,00'])assert.throws(()=>receiptAmountCents(input))
})
test('date italiane e ISO indicano lo stesso giorno, senza normalizzare date impossibili',()=>{
  assert.equal(receiptDateKey('20/10/2026'),'2026-10-20')
  assert.equal(receiptDateKey('2/3/2026'),'2026-03-02')
  assert.equal(receiptDateKey('2028-02-29'),'2028-02-29')
  for(const value of ['31/02/2026','29/02/2027','2026-13-01','', '20/10/26'])assert.throws(()=>receiptDateKey(value))
})
test('il comando pendente conserva UUID, revisione e intento nel proprio contesto',()=>{
  const local=storage(),saved=command()
  saveReceiptCommand(local,saved)
  assert.deepEqual(loadReceiptCommand(local,saved.invoice_id,saved.scope),saved)
  assert.equal(loadReceiptCommand(local,'INV2',saved.scope),null)
  assert.equal(loadReceiptCommand(local,saved.invoice_id,'d'.repeat(64)),null)
  const reordered=Object.fromEntries(Object.entries(saved).reverse())
  saveReceiptCommand(local,reordered)
  assert.throws(()=>saveReceiptCommand(local,{...saved,command_key:randomUUID()}))
  assert.throws(()=>clearReceiptCommand(local,{...saved,amount_cents:1}))
  assert.deepEqual(loadReceiptCommand(local,saved.invoice_id,saved.scope),reordered)
  clearReceiptCommand(local,saved)
  assert.equal(loadReceiptCommand(local,saved.invoice_id,saved.scope),null)
})
test('un comando corrotto resta conservato e non viene sostituito',()=>{
  const local=storage(),saved=command(),key=receiptStorageKey(saved.invoice_id,saved.scope)
  local.setItem(key,'{incompleto')
  assert.throws(()=>loadReceiptCommand(local,saved.invoice_id,saved.scope))
  assert.throws(()=>saveReceiptCommand(local,saved))
  assert.equal(local.getItem(key),'{incompleto')
})
test('la bozza libera conserva i campi e la revisione originale senza diventare un comando',()=>{
  const local=storage(),saved=command()
  const draft={fields:{amount:'€ 400,00',date:'20/10/2026',method:'banca',note:'Bozza',reason:'',movementId:''},revision:saved.expected_revision}
  saveReceiptDraft(local,saved.invoice_id,saved.scope,draft)
  assert.deepEqual(loadReceiptDraft(local,saved.invoice_id,saved.scope),draft)
  assert.equal(loadReceiptDraft(local,'INV2',saved.scope),null)
  assert.equal(loadReceiptCommand(local,saved.invoice_id,saved.scope),null)
})
test('il recupero conferma il medesimo movimento e non comunica una seconda modifica',async()=>{
  const saved=command(),notifications=[]
  respond(ack(saved),200,notifications)
  assert.equal((await sendReceiptCommand(saved)).confirmed,true)
  assert.equal(notifications.length,1)
  respond(ack(saved,{already_present:true}),200,notifications)
  assert.equal((await sendReceiptCommand(saved)).confirmed,true)
  assert.equal(notifications.length,1)
})
for(const [status,code,rejected] of [[401,'',false],[403,'',false],[404,'',false],[503,'outcome_not_confirmed',false],
  [409,'command_conflict',false],[409,'context_changed',false],[409,'revision_conflict',true],[400,'validation',true],[400,'',false]]){
  test(`HTTP ${status} ${code}: il comando viene conservato salvo rifiuto esplicito`,async()=>{
    respond({ok:false,code,message:'Esito controllato'},status)
    const result=await sendReceiptCommand(command())
    assert.equal(result.confirmed,false)
    assert.equal(result.rejected,rejected)
  })
}
test('OK, UUID sbagliato o movimento discordante non producono una falsa conferma',async()=>{
  const saved=command()
  for(const change of [{confirmed_command:undefined},{confirmed_command:{...ack(saved).confirmed_command,command_key:randomUUID()}},
    {movement_id:'ALTRO'},{summary:{...summary(),paid_cents:1}},
    {summary:{...summary(),receipts:[{...summary().receipts[0],note:'Un altro intento'}]}}]){
    const notifications=[]
    respond(ack(saved,change),200,notifications)
    const result=await sendReceiptCommand(saved)
    assert.equal(result.confirmed,false)
    assert.equal(result.rejected,false)
    assert.equal(notifications.length,0)
  }
})
test('la lettura di un pagamento storico non inventa incassato o residuo',async()=>{
  respond({ok:true,summary:{...summary(),status:'REVIEW',paid_cents:null,residual_cents:null,due_cents:null,receipts:[],reason:'Da riscontrare'}})
  const result=await getInvoiceReceipts('INV1')
  assert.equal(result.paid_cents,null)
  assert.equal(result.residual_cents,null)
})

// Guardrail di dominio: le prove utente restano nel browser reale.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { publishMutationRefresh, OPERATIONAL_REFRESH_EVENT } from '../../frontend/src/operationalRefresh.ts'
const { submitEmailBulkAction } = await import('../../frontend/src/emailData.ts')
const originalFetch=globalThis.fetch
const originalWindow=globalThis.window
let events=[]
function context() {
 events=[]
 globalThis.window={location:{origin:'https://app.iusentra.it'},dispatchEvent:event=>{events.push(event);return true}}
}
afterEach(()=>{globalThis.fetch=originalFetch;if(originalWindow===undefined)delete globalThis.window;else globalThis.window=originalWindow})
for(const path of ['/email/ID1/segna-letta','/email-ordinaria/ID2/segna-non-letta','/email-ordinaria/sincronizza','/api/v1/ui/email-ordinaria/bulk-action']) {
 test(`aggiorna comunicazioni per ${path}`,()=>{
  context();publishMutationRefresh(path)
  assert.equal(events.length,1)
  assert.equal(events[0].type,OPERATIONAL_REFRESH_EVENT)
  assert.deepEqual(events[0].detail.domains,['comunicazioni'])
 })
}
test('invio, firma, deposito, letture GET e origini esterne non pubblicano scritture posta',()=>{
 context()
 for(const path of ['/email/invia','/email/ID1/firma','/email/deposito','/api/v1/ui/email/messaggio/ID1','https://example.test/email/ID1/segna-letta'])publishMutationRefresh(path)
 assert.equal(events.length,0)
})
test('bulk pubblica solo una conferma reale e conserva la risposta operativa',async()=>{
 context();globalThis.fetch=async()=>({ok:true,json:async()=>({ok:true,message:'2 messaggi segnati come letti.'})})
 assert.equal(await submitEmailBulkAction('/api/v1/ui/email-ordinaria/bulk-action',['ID1','ID2'],'read'),'2 messaggi segnati come letti.')
 assert.equal(events.length,1)
})
for(const [label,response] of [
 ['errore HTTP',{ok:false,json:async()=>({ok:false,message:'Operazione non confermata.'})}],
 ['JSON negativo',{ok:true,json:async()=>({ok:false,message:'Operazione non confermata.'})}],
 ['conferma assente',{ok:true,json:async()=>({message:'Risposta incompleta.'})}],
 ['HTML',{ok:true,json:async()=>{throw new SyntaxError('HTML')}}],
])test(`bulk ${label}: nessun aggiornamento fittizio`,async()=>{
 context();globalThis.fetch=async()=>response
 await assert.rejects(submitEmailBulkAction('/api/v1/ui/email-ordinaria/bulk-action',['ID1'],'read'))
 assert.equal(events.length,0)
})

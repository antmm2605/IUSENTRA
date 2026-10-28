import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { submitOrdinaryEmailViaTransport } from '../../frontend/src/ordinaryEmailSend.ts'
const originals={fetch:globalThis.fetch,window:globalThis.window,document:globalThis.document,FormData:globalThis.FormData,sessionStorage:globalThis.sessionStorage}
let store,calls
beforeEach(()=>{
 store=new Map();calls=[]
 globalThis.sessionStorage={getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)}
 globalThis.window={navigator:{userAgent:'Windows',platform:'Win32'},setTimeout,clearTimeout,dispatchEvent(){},location:{href:'https://studio.example/email-ordinaria/scrivi',pathname:'/email-ordinaria/scrivi'}}
 globalThis.document={querySelector:()=>({content:'test-csrf'}),dispatchEvent(){}}
 globalThis.FormData=class extends originals.FormData{constructor(){super()}}
})
afterEach(()=>Object.assign(globalThis,originals))
function handler({gmail=false,confirmFail=false,timeout=false}={}){
 return async(url,init)=>{
  calls.push(String(url))
  if(url==='/email-ordinaria/trasporto')return Response.json({ok:true,local_signer_required:!gmail,scope:'studio-a'})
  if(String(url).includes('/ping'))return Response.json({ok:true,ordinary_email:true})
  if(url==='/email-ordinaria/scrivi')return Response.json(gmail?{ok:true,message:'sent'}:{ok:true,local_signer_required:true,local_payload:{attachments:[{filename:'atto.pdf',content_base64:'YQ=='}]},confirmation_token:'signed'})
  if(String(url).endsWith('/email/send')){
   assert.equal(init.targetAddressSpace,'loopback')
   assert.equal(JSON.parse(init.body).attachments[0].content_base64,'YQ==')
   if(timeout)throw new TypeError('connection lost')
   return Response.json({ok:true,inviato:true,canale:'locale',message_id:'<test@example.test>'})
  }
  if(url==='/email-ordinaria/scrivi/conferma-locale')return Response.json({ok:!confirmFail},{status:confirmFail?503:200})
  throw new Error('unexpected URL '+url)
 }
}
test('Gmail keeps existing direct submit without contacting LocalSigner',async()=>{
 globalThis.fetch=handler({gmail:true});assert.equal((await submitOrdinaryEmailViaTransport({})).ok,true)
 assert.deepEqual(calls,['/email-ordinaria/trasporto','/email-ordinaria/scrivi'])
})
test('ordinary SMTP sends attachments through loopback and then confirms once',async()=>{
 globalThis.fetch=handler();assert.equal((await submitOrdinaryEmailViaTransport({})).ok,true)
 assert.equal(calls.filter(x=>x.endsWith('/email/send')).length,1);assert.equal(store.size,0)
})
test('failed registration retries only confirmation, never SMTP',async()=>{
 const form={};globalThis.fetch=handler({confirmFail:true})
 await assert.rejects(submitOrdinaryEmailViaTransport(form),/senza rispedire/)
 globalThis.fetch=handler();assert.equal((await submitOrdinaryEmailViaTransport(form)).ok,true)
 assert.equal(calls.filter(x=>x.endsWith('/email/send')).length,1)
})
test('lost SMTP response remains uncertain and does not resend after retry',async()=>{
 globalThis.fetch=handler({timeout:true});await assert.rejects(submitOrdinaryEmailViaTransport({}),/potrebbe essere avvenuto/)
 await assert.rejects(submitOrdinaryEmailViaTransport({}),/precedente invio/)
 assert.equal(calls.filter(x=>x.endsWith('/email/send')).length,1)
})

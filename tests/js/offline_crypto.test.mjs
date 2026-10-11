import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import fs from 'node:fs'
import {createCredential,derive,seal,open,sign,unb64,canonical,hash} from '../../frontend/src/features/offline/crypto.mjs'
import {assertLease} from '../../frontend/src/features/offline/vault.mjs'
import {reconcile,resolveConflict,saveNote} from '../../frontend/src/features/offline/sync.mjs'

test('nonextractable per-device key signs verifiable P-256 challenges',async () => {
  const credential=await createCredential()
  await assert.rejects(crypto.subtle.exportKey('pkcs8',credential.privateKey))
  const key=await crypto.subtle.importKey('spki',unb64(credential.public_key),{name:'ECDSA',namedCurve:'P-256'},false,['verify'])
  const signature=await sign(credential.privateKey,'synthetic-studio:nonce')
  assert.equal(await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},key,unb64(signature),new TextEncoder().encode('synthetic-studio:nonce')),true)
})
test('AES-GCM protects documents and queue, wrong passphrase/scope/tampering fail',async () => {
  const salt='AAAAAAAAAAAAAAAAAAAAAA=='
  const key=await derive('frase segreta sintetica',salt)
  const payload={notes:{one:{attachment:{text:'Documento sintetico '.repeat(10000)}}},queue:[{text:'Bozza privata'}]}
  const ciphertext=await seal(key,'studio-a:actor-a:device-a',payload)
  assert.ok(!ciphertext.ciphertext.includes('Bozza'))
  assert.deepEqual(await open(key,'studio-a:actor-a:device-a',ciphertext),payload)
  await assert.rejects(open(key,'studio-b:actor-a:device-a',ciphertext))
  await assert.rejects(open(await derive('altra frase sintetica',salt),'studio-a:actor-a:device-a',ciphertext))
  await assert.rejects(open(key,'studio-a:actor-a:device-a',{...ciphertext,iv:'AQAAAAAAAAAAAAAA'}))
})
test('lease fails closed after expiry and detectable clock rollback',() => {
  assertLease({lease_until:1000,last_seen:500000},600000)
  assert.throws(() => assertLease({lease_until:1000,last_seen:500000},1000000))
  assert.throws(() => assertLease({lease_until:1000,last_seen:500000},100000))
})
test('reconciliation preserves competing draft, receipt retry and deletes unauthorized copy',() => {
  const state={notes:{old:{payload:'private'}},queue:[{command:'a',id:'one',text:'draft-a'},{command:'b',id:'two',text:'draft-b'}]}
  const result=reconcile(state,{changes:[{id:'one',version:2,payload:{text:'server'}}],results:[{command:'a',status:'conflict',current:{version:2}},{command:'b',status:'accepted'}],authorized_ids:['one'],cursor:2,lease_until:2000})
  assert.equal(result.queue.length,1);assert.equal(result.queue[0].text,'draft-a');assert.equal(result.queue[0].conflict.version,2)
  assert.equal(result.notes.old,undefined);assert.equal(state.queue.length,2)
  assert.deepEqual(reconcile(result,{changes:[],results:[],cursor:2,lease_until:2000}).queue,result.queue)
})
test('signature intent canonicalization is independent of key insertion order',async () => {
  assert.equal(canonical({b:'è',a:1}),'{"a":1,"b":"è"}')
  assert.equal(await hash({b:'è',a:1}),await hash({a:1,b:'è'}))
})
test('service worker never caches confidential routes and only exact public shell assets',async () => {
  const listeners=new Map(), fetches=[], matches=[]
  const sandbox={URL,Request,Response,self:{location:{origin:'https://synthetic.invalid'},addEventListener:(name,callback)=>listeners.set(name,callback)},
    fetch:async request=>{fetches.push(request.url);return new Response('online')},
    caches:{open:async()=>({match:async path=>{matches.push(path);return new Response('generic shell')}})}}
  vm.runInNewContext(fs.readFileSync(new URL('../../web/static/sw.js',import.meta.url),'utf8'),sandbox)
  const listener=listeners.get('fetch')
  for (const path of ['/api/v1/offline/context','/api/v1/offline/devices/a/sync','/fascicoli/a/documenti/b/preview']) {
    let cached=false
    listener({request:{url:'https://synthetic.invalid'+path,method:'GET',mode:'cors'},respondWith:()=>cached=true})
    assert.equal(cached,false)
  }
  let response
  listener({request:{url:'https://synthetic.invalid/static/offline-workspace/workspace.js',method:'GET',mode:'cors'},respondWith:promise=>response=promise})
  assert.equal(await (await response).text(),'generic shell');assert.equal(matches.length,1);assert.equal(fetches.length,0)
})
test('ordinary online drafts stay in memory; UI preferences retain normal storage',() => {
  class Storage {
    constructor(){this.values=new Map()}
    getItem(k){return this.values.get(k) ?? null}
    setItem(k,v){this.values.set(k,String(v))}
    removeItem(k){this.values.delete(k)}
    clear(){this.values.clear()}
  }
  const local=new Storage(),session=new Storage()
  const window={Storage,localStorage:local,sessionStorage:session,addEventListener:()=>{}}
  vm.runInNewContext(fs.readFileSync(new URL('../../web/static/js/offline-browser-memory.js',import.meta.url),'utf8'),{window,Map,WeakMap})
  local.setItem('iusentra:bozza-anagrafica:v1:cliente','sensitive-draft')
  assert.equal(local.getItem('iusentra:bozza-anagrafica:v1:cliente'),'sensitive-draft')
  assert.equal(local.values.size,0)
  local.setItem('pct-theme','dark');assert.equal(local.values.get('pct-theme'),'dark')
  session.setItem('iusentra.ctu.pending.v1.case','pending-sensitive');assert.equal(session.values.size,0)
})

// Guardrail tecnici, non sostituiscono la prova reale delle statistiche.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import {afterEach,test} from 'node:test'
const {getStatistichePage}=await import('../../frontend/src/statisticheData.ts')
const originalFetch=globalThis.fetch
let requests=[]
const valid={source:'repository_reali',metrics:[],sections:[],records:[]}
function response(payload,status=200,contentType='application/json'){
 requests=[]
 globalThis.fetch=async url=>{requests.push(url);return {ok:status<400,status,headers:{get:()=>contentType},json:async()=>payload,text:async()=>'<html>Sessione scaduta</html>'}}
}
afterEach(()=>{globalThis.fetch=originalFetch})
for(const status of [401,403,500,503])test(`HTTP ${status}: errore esplicito senza statistiche fittizie`,async()=>{
 response({ok:false,message:'Dati non disponibili'},status)
 await assert.rejects(getStatistichePage());assert.deepEqual(requests,['/api/v1/ui/statistiche'])
})
for(const [label,payload] of [['risposta negativa',{...valid,ok:false}],['sorgente in errore',{...valid,source:'errore_controllato'}],['contratto assente',{}],['elenco assente',{...valid,sections:undefined}]])test(`${label}: nessun archivio vuoto inventato`,async()=>{
 response(payload);await assert.rejects(getStatistichePage());assert.equal(requests.length,1)
})
test('HTML di login: non diventa archivio vuoto',async()=>{
 response(null,200,'text/html');await assert.rejects(getStatistichePage())
})
test('guasto rete: non diventa archivio vuoto',async()=>{
 globalThis.fetch=async()=>{throw new Error('rete')};await assert.rejects(getStatistichePage())
})
test('archivio realmente vuoto mantiene fonte e contratto',async()=>{
 response(valid);const data=await getStatistichePage();assert.equal(data.source,'repository_reali');assert.deepEqual(data.metrics,[]);assert.deepEqual(data.sections,[])
})
test('importi e categorie restano numerici e comprensibili',async()=>{
 response({...valid,metrics:[{id:'incassi',label:'Da incassare',value:1234.56}],sections:[{id:'scadenze_priorita',items:[{id:'media',label:'MEDIA',value:9}]}]})
 const data=await getStatistichePage();assert.equal(data.metrics[0].value,1234.56);assert.equal(data.sections[0].items[0].label,'Media');assert.equal(data.sections[0].items[0].value,9)
})

test('messaggi clienti email distinti dalla casella ordinaria',async()=>{
 response({...valid,sections:[{id:'comunicazioni',items:[{id:'ordinary',label:'Email ordinaria',value:3085},{id:'clients',label:'EMAIL',value:3}]}]})
 const data=await getStatistichePage()
 assert.equal(data.sections[0].items[0].label,'Email ordinaria')
 assert.equal(data.sections[0].items[1].label,'Messaggi clienti (email)')
 assert.equal(data.sections[0].items[1].value,3)
})

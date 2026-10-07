// Guardrail tecnici: non sostituiscono la prova dell’agenda nella macchina reale.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getAgendaPage } from '../../frontend/src/agendaData.ts'
const originalFetch=globalThis.fetch
const originalWindow=globalThis.window
const anchor=new Date(2026,9,6,12)
let requests=[]
function context(response,path='/agenda') {
 requests=[]
 globalThis.window={location:{pathname:path}}
 globalThis.fetch=async(url)=>{requests.push(url);return response}
}
afterEach(()=>{globalThis.fetch=originalFetch;if(originalWindow===undefined)delete globalThis.window;else globalThis.window=originalWindow})
for(const status of [401,403,500,503])test(`HTTP ${status}: errore esplicito e nessun percorso alternativo`,async()=>{
 context({ok:false,status,json:async()=>{throw new Error('non deve leggere il corpo')}})
 const result=await getAgendaPage(anchor)
 assert.equal(result.source,'errore_controllato')
 assert.ok(result.diagnostic)
 assert.equal(requests.length,1)
 assert.ok(requests[0].startsWith('/api/v1/ui/agenda?'))
})
for(const [name,json] of [
 ['HTML',async()=>{throw new SyntaxError('HTML')}],
 ['contratto assente',async()=>({})],
 ['risposta negativa',async()=>({ok:false,events:[]})],
])test(`${name}: mai agenda vuota presentata come aggiornata`,async()=>{
 context({ok:true,json})
 const result=await getAgendaPage(anchor)
 assert.equal(result.source,'errore_controllato')
 assert.ok(result.diagnostic)
 assert.equal(requests.length,1)
})
test('agenda realmente vuota rimane un risultato valido',async()=>{
 context({ok:true,json:async()=>({ok:true,events:[],source:'sqlite'})})
 const result=await getAgendaPage(anchor)
 assert.equal(result.source,'sqlite');assert.equal(result.diagnostic,'');assert.equal(result.events.length,0)
})
test('evento controllato e identificativo selezionato conservano il contesto',async()=>{
 context({ok:true,json:async()=>({events:[{id:'CONTROLLED',title:'Impegno controllato',start:'2026-10-07T09:00:00',end:'2026-10-07T09:30:00',tipo:'ALTRO',stato:'PROGRAMMATO'}],source:'sqlite'})},'/agenda/CONTROLLED')
 const result=await getAgendaPage(anchor)
 assert.equal(result.events.length,1);assert.equal(result.events[0].id,'CONTROLLED');assert.equal(result.events[0].date,'2026-10-07')
 const url=new URL(requests[0],'https://app.iusentra.it')
 assert.equal(url.searchParams.get('selected_id'),'CONTROLLED')
 assert.equal(url.searchParams.get('from'),'2026-10-05');assert.equal(url.searchParams.get('to'),'2026-10-11')
})

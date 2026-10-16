// Guardie tecniche: le prove materiali restano sul browser reale 8080.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import {afterEach, test} from 'node:test'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
const ts=createRequire(new URL('../../frontend/package.json',import.meta.url))('@typescript/typescript6')
const {getFascicoliPage} = await import('../../frontend/src/fascicoliData.ts')
const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
const valid = {source:'repository_reali', generatedAt:'2026-10-16T22:00:00',cardSummary:{},
 items:[{id:'F026'}], pagination:{page:2,pageSize:1,total:307,pages:307}}
function serve(payload, status=200) {
 const requests=[]
 globalThis.fetch=async url => {requests.push(url);return {ok:status<400,status,json:async()=>payload}}
 return requests
}
function listFunctionSource(source) {
 const file=ts.createSourceFile('FascicoliPage.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 const node=file.statements.find(node=>ts.isFunctionDeclaration(node) && node.name?.text==='FascicoliListPage')
 assert.ok(node,'Componente elenco principale non trovato')
 return node.getText(file)
}
test('una richiesta restituisce solo la pagina scelta, senza anticipare le altre', async()=>{
 const requests=serve(valid)
 const result=await getFascicoliPage({page:2,pageSize:1})
 assert.equal(result.items.length,1)
 assert.equal(result.pagination.total,307)
 assert.deepEqual(requests,['/api/v1/ui/fascicoli?page=2&page_size=1'])
})
for(const status of [400,401,403,404])test(`HTTP ${status}: errore esplicito e nessun tentativo estraneo`,async()=>{
 const requests=serve({message:'Caricamento non confermato'},status)
 await assert.rejects(getFascicoliPage(),/Caricamento non confermato/)
 assert.equal(requests.length,1)
})
for(const payload of [{}, {...valid,items:[]}, {...valid,pagination:{...valid.pagination,total:-1}},
 {...valid,pagination:{...valid.pagination,pages:1}}, {...valid,source:'errore'}])test('contratto incompleto: nessun falso elenco vuoto',async()=>{
 const requests=serve(payload)
 await assert.rejects(getFascicoliPage())
 assert.equal(requests.length,1)
})
test('archivio realmente vuoto viene rappresentato come tale',async()=>{
 serve({...valid,items:[],pagination:{page:1,pageSize:25,total:0,pages:0}})
 const result=await getFascicoliPage()
 assert.equal(result.items.length,0)
 assert.equal(result.pagination.total,0)
})
test('errore transitorio: ripetizione finita solo della richiesta originale',async()=>{
 let calls=0
 globalThis.fetch=async()=>{calls++; return {ok:calls===2,status:calls===2?200:503,json:async()=>calls===2?valid:{message:'Attendi'}}}
 assert.equal((await getFascicoliPage({page:2,pageSize:1})).pagination.page,2)
 assert.equal(calls,2)
})
test('il componente non anticipa le pagine su apertura, hover o focus',()=>{
 const source=readFileSync(new URL('../../frontend/src/components/FascicoliPage.tsx',import.meta.url),'utf8')
 assert.doesNotMatch(source,/warmEconomicFirstPages|prefetchListPage|onPrefetchPage|onPagePrefetch/)
 assert.match(source,/listLoadError/)
 assert.match(source,/Riprova/)
 const requestEffect=source.slice(source.indexOf('const hasCachedPage'),source.indexOf('const presidioDue'))
 assert.match(requestEffect,/\}, \[[^\]]*groupBy[^\]]*\]\)/)
})

test('elenco sottoscritto agli eventi confermati, senza sovrascrivere bozze o riusare risposte invalidate',()=>{
 const source=readFileSync(new URL('../../frontend/src/components/FascicoliPage.tsx',import.meta.url),'utf8')
 const list=listFunctionSource(source)
 assert.match(list,/useOperationalRefresh\(\['fascicoli'\]/)
 assert.match(list,/data-fascicoli-economic-draft="true"/)
 assert.match(list,/generation === pageCacheGenerationRef.current/)
 assert.match(list,/latestListKeyRef.current !== requestKey/)
 assert.match(source,/data-fascicoli-economic-draft=\{dirtyCount \|\| generating/)
 assert.match(source,/dispatchEvent\(new Event\(OPERATIONAL_REFRESH_RETRY\)\)/)
})

test('la sottoscrizione archivio non certifica quella mancante nell’elenco principale',()=>{
 const source="function FascicoliListPage(){return null}\nfunction ArchivePage(){useOperationalRefresh(['fascicoli'],refresh)}"
 assert.doesNotMatch(listFunctionSource(source),/useOperationalRefresh/)
 assert.throws(()=>listFunctionSource('function ArchivePage(){return null}'),/elenco principale/)
})

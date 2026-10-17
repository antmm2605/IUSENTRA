import assert from 'node:assert/strict'
import { test } from 'node:test'
import { catalogPage, catalogScopeFromQuery, catalogScopeCounts, matchesCatalogScope } from '../../frontend/src/templateCatalogFilters.ts'

const records = Object.freeze([
  Object.freeze({id:'catalog-ready',kind:'catalogo',prefillStatus:'precompilabile',requiresLawyerReview:false}),
  Object.freeze({id:'catalog-review',kind:'catalogo',prefillStatus:'da completare',requiresLawyerReview:true}),
  Object.freeze({id:'studio-ready',kind:'studio',prefillStatus:'precompilabile',requiresLawyerReview:false}),
])

test('ogni conteggio apre esattamente i modelli della medesima card', () => {
  const counts = catalogScopeCounts(records)
  assert.deepEqual(counts.map(item => item.count), [3,2,1,2,1])
  for (const card of counts) assert.equal(records.filter(record => matchesCatalogScope(record,card.id)).length,card.count)
  assert.deepEqual(records.filter(record => matchesCatalogScope(record,'verifica')).map(record => record.id),['catalog-review'])
})

test('i conteggi rispettano il perimetro ristretto dalla ricerca e non cambiano gli originali', () => {
  const selected=records.filter(record => record.id === 'studio-ready')
  assert.deepEqual(catalogScopeCounts(selected).map(item => item.count),[1,0,1,1,0])
  assert.deepEqual(records.map(record => record.id),['catalog-ready','catalog-review','studio-ready'])
})

test('le card a zero restano disponibili senza inventare risultati', () => {
  const cards=catalogScopeCounts([])
  assert.equal(cards.length,5)
  assert.ok(cards.every(card => card.count === 0))
  assert.equal(matchesCatalogScope({kind:'studio',prefillStatus:'da completare',requiresLawyerReview:false},'precompilabili'),false)
})

test('la pagina limita il rendering ma conserva tutti i risultati ricercabili', () => {
  const all=Array.from({length:50},(_,id)=>({id:String(id),kind:'studio',prefillStatus:'precompilabile',requiresLawyerReview:false}))
  const first=catalogPage(all,1),second=catalogPage(all,2),last=catalogPage(all,99)
  assert.equal(first.items.length,24)
  assert.equal(second.items.length,24)
  assert.equal(last.items.length,2)
  assert.deepEqual([last.page,last.totalPages,last.start,last.end],[3,3,49,50])
  assert.equal(new Set([...first.items,...second.items,...last.items].map(item=>item.id)).size,50)
  assert.equal(catalogScopeCounts(all).find(item=>item.id==='studio').count,50)
  assert.deepEqual(catalogPage([],9),{page:1,totalPages:1,items:[],start:0,end:0})
  assert.equal(catalogPage(all,NaN).page,1)
})

test('il collegamento dalla redazione apre il medesimo perimetro dei modelli studio', () => {
  assert.equal(catalogScopeFromQuery('?scope=studio'),'studio')
  assert.equal(records.filter(record=>matchesCatalogScope(record,catalogScopeFromQuery('?scope=studio'))).length,1)
  assert.equal(catalogScopeFromQuery('?scope=inesistente'),'all')
  assert.equal(catalogScopeFromQuery(''),'all')
})

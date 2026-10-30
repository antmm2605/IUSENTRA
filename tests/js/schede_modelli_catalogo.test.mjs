import assert from 'node:assert/strict'
import { test } from 'node:test'
import { filtraModelli, filtriModelliVuoti, indicizzaModelli } from '../../frontend/src/schedeModelliCatalogo.ts'
const rows=[
 {id:'a',codice:'MON_001',titolo:'Ricorso per decreto ingiuntivo',materia:'Civile',tipo:'Modello guidato',provenienza:'Compilatore',stato_norme:'associate',ricerca:'art633 codice procedura civile'},
 {id:'b',codice:'LOC_001',titolo:'Sfratto per morosità',materia:'Civile',tipo:'Modello di catalogo',provenienza:'Catalogo',stato_norme:'da_associare',ricerca:'Locazioni immobiliari'},
 {id:'c',codice:'PEN_001',titolo:'Nomina difensore',materia:'Penale',tipo:'Modello guidato',provenienza:'Compilatore',stato_norme:'associate',ricerca:'art96 codice procedura penale'},
]
const index=indicizzaModelli(rows)
const query=(text,other={})=>filtraModelli(index,{...filtriModelliVuoti,testo:text,...other}).map(row=>row.id)
test('ricerca testuale per più parole, codice, norma e accenti',()=>{
 assert.deepEqual(query('decreto ingiuntivo'),['a'])
 assert.deepEqual(query('morosita'),['b'])
 assert.deepEqual(query('MON_001'),['a'])
 assert.deepEqual(query('art633'),['a'])
 assert.deepEqual(query('decreto nomina'),[])
})
test('filtri combinabili senza perdere identità o mostrare risultati di altre materie',()=>{
 assert.deepEqual(query('',{materia:'Penale',tipo:'Modello guidato'}),['c'])
 assert.deepEqual(query('',{materia:'Civile',norme:'da_associare',provenienza:'Catalogo'}),['b'])
 assert.deepEqual(query('nomina',{materia:'Civile'}),[])
 assert.deepEqual(query(''),['a','b','c'])
})
test('indicizzazione non altera i dati originali e restituisce l’ultima voce di un catalogo ampio',()=>{
 const original=JSON.stringify(rows)
 const many=Array.from({length:1320},(_,i)=>({...rows[i%3],id:'modello-'+i,codice:'COD_'+i,titolo:'Modello numero '+i,ricerca:'riferimento-'+i}))
 const result=filtraModelli(indicizzaModelli(many),{...filtriModelliVuoti,testo:'riferimento-1319'})
 assert.deepEqual(result.map(row=>row.id),['modello-1319'])
 assert.equal(JSON.stringify(rows),original)
})

test('codice esatto esclude richiami incrociati e conserva le identità delle provenienze',()=>{
 const data=[{...rows[0],id:'diretto',codice:'CIV_ORD_001'},{...rows[0],id:'altra-fonte',codice:'CIV_ORD_001',provenienza:'Catalogo'},{...rows[1],id:'estraneo',ricerca:'riferimenti CIV_ORD_001'}]
 const indexed=indicizzaModelli(data)
 assert.deepEqual(filtraModelli(indexed,{...filtriModelliVuoti,testo:'civ_ord_001'}).map(r=>r.id),['diretto','altra-fonte'])
 assert.deepEqual(filtraModelli(indexed,{...filtriModelliVuoti,testo:'CIV ORD 001',provenienza:'Catalogo'}).map(r=>r.id),['altra-fonte'])
})

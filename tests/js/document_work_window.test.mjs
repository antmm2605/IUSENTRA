import assert from 'node:assert/strict'
import { test } from 'node:test'
import { documentWorkPreview } from '../../frontend/src/components/documentWorkWindow.ts'
const origin='https://app.iusentra.it'
const preview={name:'Decreto.pdf',url:'/fascicoli/F1/documenti/D1/visualizza',downloadUrl:'/fascicoli/F1/documenti/D1/scarica'}
test('preview persistente conserva documento, download e modalità del lettore nativo',()=>{
 assert.deepEqual(documentWorkPreview({...preview,mobileUrl:preview.url+'?viewer=mobile&rotationScope=page',operational:true},origin),{...preview,mobileUrl:preview.url+'?viewer=mobile&rotationScope=page',operational:true})
})
test('URL assoluti dello stesso sito si normalizzano senza perdere parametri',()=>{
 assert.deepEqual(documentWorkPreview({...preview,url:origin+preview.url+'?pagina=2'},origin),{...preview,url:preview.url+'?pagina=2'})
})
for(const [name,patch] of [
 ['altra origine',{url:'https://example.test'+preview.url}],
 ['credenziali URL',{url:'https://utente:password@app.iusentra.it'+preview.url}],
 ['blob temporaneo',{url:'blob:https://app.iusentra.it/example'}],
 ['object URL',{objectUrl:'blob:example'}],
 ['firma',{url:'/fascicoli/F1/documenti/D1/firma'}],
 ['deposito',{url:'/fascicoli/F1/deposito'}],
 ['invio',{url:'/email/invia'}],
 ['download di altro fascicolo',{downloadUrl:'/fascicoli/F2/documenti/D1/scarica'}],
 ['download di altro documento',{downloadUrl:'/fascicoli/F1/documenti/D2/scarica'}],
 ['download esterno',{downloadUrl:'https://example.test/file.pdf'}],
 ['lettore mobile esterno',{mobileUrl:'https://example.test/file.pdf'}],
 ['lettore mobile di altro documento',{mobileUrl:'/fascicoli/F1/documenti/D2/visualizza'}],
 ['nome assente',{name:''}],
 ['URL non testuale',{url:42}],
])test(`${name}: nessuna apertura nel gestore principale`,()=>assert.equal(documentWorkPreview({...preview,...patch},origin),null))
test('input assente o malformato non apre finestre',()=>{
 for(const value of [undefined,null,'test',42,{},[]])assert.equal(documentWorkPreview(value,origin),null)
})

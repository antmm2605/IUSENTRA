// Guardie dei confini dei comandi; l'accettazione resta nel browser reale 8080.
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import {test} from 'node:test'
const ts=createRequire(new URL('../../frontend/package.json',import.meta.url))('@typescript/typescript6')
const source=readFileSync(new URL('../../frontend/src/components/EditorLinkedFieldsPanel.tsx',import.meta.url),'utf8')
function writesFromEffects(text){
 const tree=ts.createSourceFile('panel.tsx',text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 const functions=new Map(),effects=[],writes=[]
 function discover(node){
  if(ts.isFunctionDeclaration(node)&&node.name)functions.set(node.name.text,node)
  if(ts.isVariableDeclaration(node)&&ts.isIdentifier(node.name)&&node.initializer&&
    (ts.isArrowFunction(node.initializer)||ts.isFunctionExpression(node.initializer))) functions.set(node.name.text,node.initializer)
  if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)&&node.expression.text==='useEffect') effects.push(node.arguments[0])
  ts.forEachChild(node,discover)
 }
 discover(tree)
 function inspect(node,seen=new Set()){
  if(!node)return
  if(ts.isIdentifier(node)&&functions.has(node.text)&&!seen.has(node.text)){seen.add(node.text);inspect(functions.get(node.text),seen);return}
  if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)){
   const name=node.expression.text
   if(name==='fetch'){
    const options=node.arguments[1]
    const method=options&&ts.isObjectLiteralExpression(options)?options.properties.find(p=>p.name?.text==='method'):null
    if(method&&ts.isPropertyAssignment(method)&&!['GET','HEAD'].includes(method.initializer.text?.toUpperCase()))writes.push(node.getText(tree))
   }
   if(functions.has(name)&&!seen.has(name)){seen.add(name);inspect(functions.get(name),seen)}
  }
  ts.forEachChild(node,child=>inspect(child,seen))
 }
 effects.forEach(effect=>inspect(effect))
 return writes
}
test('aprire o cambiare il fascicolo dell’editor non invia comandi di elaborazione',()=>{
 assert.deepEqual(writesFromEffects(source),[])
})
test('la guardia rileva anche un invio nascosto in un richiamo automatico',()=>{
 const direct="function Panel(){useEffect(()=>{fetch('/recover',{method:'POST'})},[])}"
 const indirect="function Panel(){const recover=()=>fetch('/recover',{method:'POST'});useEffect(()=>{recover()},[])}"
 assert.equal(writesFromEffects(direct).length,1)
 assert.equal(writesFromEffects(indirect).length,1)
})
test('il lavoro in background dell’editor non possiede il caricamento globale',()=>{
 const tree=ts.createSourceFile('panel.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 let owners=0
 function visit(node){
  if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)&&node.expression.text==='useBusyActivity'){
   owners++
   assert.doesNotMatch(node.arguments[0].getText(tree),/recoveryPending/)
  }
  ts.forEachChild(node,visit)
 }
 visit(tree);assert.ok(owners)
})

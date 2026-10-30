import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { after, test } from 'node:test'

const hook = registerHooks({ resolve(specifier, context, next) {
  return next(['./sourceWorkDescriptor','./sourceWindowEvents'].includes(specifier) ? specifier + '.ts' : specifier, context)
} })
const registry = await import('../../frontend/src/components/sourceWindowEvents.ts')
const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const source = { href: '/fascicoli/F1/documenti/D1/visualizza', label: 'Fonte', context: 'Scadenza' }
const origin = 'https://app.iusentra.it'
after(() => { registry.clearSourceWindows(); hook.deregister(); if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow); else delete globalThis.window })

test('Richiami ripetuti preservano una sola fonte e incrementano il token di focus', () => {
  globalThis.window = { location: { origin } }; window.parent = window
  registry.clearSourceWindows()
  let closed = 0
  registry.openSourceWindow(source, 'scadenza', () => { closed += 1 })
  const id = registry.sourceWindowsSnapshot()[0].id
  registry.openSourceWindow(source, 'scadenza', () => { closed += 1 })
  registry.openSourceWindow(source, 'agenda', () => { closed += 1 })
  assert.equal(registry.sourceWindowsSnapshot().length, 1)
  assert.equal(registry.sourceWindowsSnapshot()[0].id, id)
  assert.equal(registry.sourceWindowsSnapshot()[0].focusToken, 3)
  registry.closeSourceWindow(id)
  assert.equal(closed, 2)
  assert.equal(registry.sourceWindowsSnapshot().length, 0)
})

test('La fonte incorporata passa al parent dello stesso sito senza duplicare il lettore locale', () => {
  const messages = []
  globalThis.window = { location: { origin }, frameElement: { tagName: 'IFRAME' }, parent: { postMessage: (...args) => messages.push(args) } }
  let oldClose = 0; let currentClose = 0
  registry.openSourceWindow(source, 'scadenza', () => { oldClose += 1 })
  registry.openSourceWindow(source, 'scadenza', () => { currentClose += 1 })
  assert.equal(registry.sourceWindowsSnapshot().length, 0)
  assert.equal(messages.length, 2)
  assert.deepEqual(messages[1], [{ type: 'iusentra:open-source-window', source, owner: 'scadenza' }, origin])
  registry.closeParentSourceOwner('scadenza')
  registry.closeParentSourceOwner('scadenza')
  assert.equal(oldClose, 0)
  assert.equal(currentClose, 1)
})

test('Nessun comando operativo viene inoltrato al parent come fonte', () => {
  const messages = []
  globalThis.window = { location: { origin }, frameElement: { tagName: 'IFRAME' }, parent: { postMessage: (...args) => messages.push(args) } }
  registry.openSourceWindow({ ...source, href: '/fascicoli/F1/deposito' }, 'operazione', () => {})
  assert.equal(messages.length, 0)
  registry.clearSourceWindows()
})

test('Cornice esterna non accessibile: la fonte resta nella shell locale', () => {
  const messages = []
  globalThis.window = { location: { origin }, frameElement: null,
    parent: { postMessage: (...args) => messages.push(args) } }
  registry.clearSourceWindows()
  registry.openSourceWindow(source, 'verifiche', () => {})
  assert.equal(messages.length, 0)
  assert.equal(registry.sourceWindowsSnapshot().length, 1)
  assert.deepEqual(registry.sourceWindowsSnapshot()[0].source, source)
  registry.clearSourceWindows()
})

test('Cassazione e fonti web aprono il gestore interno senza nuova scheda', async () => {
  const { inAppSourceDestination } = await import('../../frontend/src/components/inAppSourceNavigation.ts')
  const { sourceWorkDescriptor } = await import('../../frontend/src/components/sourceWorkDescriptor.ts')
  for (const href of ['/giurisprudenza/sentenzeweb/4/testo','/giurisprudenza/sentenzeweb/4/documenti/469483/testo#sezione-54']) {
    assert.equal(inAppSourceDestination(href,'Cassazione',origin,'_blank').href,href)
    assert.equal(sourceWorkDescriptor({ ...source, href },origin).href,href)
  }
  const external='https://www.misterlex.it/cassazione-civile/2021/30750/'
  const inside=inAppSourceDestination(external,'Fonte',origin,'_blank')
  assert.equal(new URL(inside.href,origin).pathname,'/api/v1/ui/document-reader/web')
  assert.equal(new URL(inside.href,origin).searchParams.get('url'),external)
  for (const href of ['javascript:alert(1)','data:text/html,x','blob:'+origin+'/a','https://user:password@example.test/']) {
    assert.equal(inAppSourceDestination(href,'Fonte',origin,'_blank'),null)
  }
  assert.equal(inAppSourceDestination(external,'Scarica',origin,'_blank',true),null)
  assert.equal(inAppSourceDestination('/fascicoli/F1/deposito','Operazione',origin,'_blank'),null)
})

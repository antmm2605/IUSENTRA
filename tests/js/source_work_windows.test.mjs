import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { after, test } from 'node:test'

const hook = registerHooks({ resolve(specifier, context, next) {
  return next(specifier === './sourceWorkDescriptor' ? './sourceWorkDescriptor.ts' : specifier, context)
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
  globalThis.window = { location: { origin }, parent: { postMessage: (...args) => messages.push(args) } }
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
  globalThis.window = { location: { origin }, parent: { postMessage: (...args) => messages.push(args) } }
  registry.openSourceWindow({ ...source, href: '/fascicoli/F1/deposito' }, 'operazione', () => {})
  assert.equal(messages.length, 0)
  registry.clearSourceWindows()
})

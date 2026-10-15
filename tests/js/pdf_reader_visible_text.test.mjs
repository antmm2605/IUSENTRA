import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

test('il lettore non misura parole fuori vista e riusa la geometria già calcolata', () => {
  const source = readFileSync(process.env.IUSENTRA_PDF_READER_SOURCE || new URL('../../web/static/js/mobile-pdf-viewer.js', import.meta.url), 'utf8')
  const start = source.indexOf('  const fitWords = () => {')
  const end = source.indexOf('\n  const textVisibilityObserver', start)
  const fallbackEnd = source.indexOf('\n  const resize =', start)
  assert.ok(start >= 0)
  const code = source.slice(start, end < 0 ? fallbackEnd : end)
  class Element {}
  let scans = 0
  const word = { clientHeight: 20, clientWidth: 50, style: {}, firstElementChild: { textContent: 'Testo', style: {} } }
  const layer = Object.assign(new Element(), {
    clientWidth: 600, clientHeight: 900, childElementCount: 1,
    querySelectorAll: () => { scans += 1; return [word] },
  })
  const surface = { querySelector: () => layer }
  const scope = vm.createContext({
    HTMLElement: Element, visibleTextSurfaces: new Set([surface]), fittedTextGeometry: new WeakMap(),
    measure: { measureText: () => ({ width: 50 }) },
    pages: { querySelectorAll: () => { throw new Error('Elaborazione di tutte le pagine non richiesta') } },
  })
  vm.runInContext(code + '\nfitWords();fitWords();', scope)
  assert.equal(scans, 1)
  assert.ok(Math.abs(Number.parseFloat(word.style.fontSize) - 16.6) < 0.001)
  layer.clientWidth = 900
  vm.runInContext('fitWords()', scope)
  assert.equal(scans, 2)
  layer.childElementCount = 2
  vm.runInContext('fitWords()', scope)
  assert.equal(scans, 3)
})

test('una pagina fallita resta esplicita, riprova soltanto su comando e chiude il caricamento', () => {
  const source = readFileSync(new URL('../../web/static/js/mobile-pdf-viewer.js', import.meta.url), 'utf8')
  const start = source.indexOf("  pages.querySelectorAll('.reader-page-surface').forEach((surface) => {")
  const end = source.indexOf('  // Observe existing image loads;', start)
  assert.ok(start >= 0 && end > start)
  class Element extends EventTarget {
    children = []
    firstChild = { textContent: '' }
    appendChild(child) { this.children.push(child) }
    set textContent(value) { this.firstChild.textContent = value }
  }
  let requests = 0
  class Image extends Element {
    complete = true
    naturalWidth = 0
    get src() { return '/source?page=43' }
    set src(value) { assert.equal(value, '/source?page=43'); requests += 1 }
    removeAttribute(name) { assert.equal(name, 'src') }
  }
  const image = new Image()
  const surface = new Element()
  surface.querySelector = () => image
  const events = new EventTarget()
  let activities = 0
  vm.runInNewContext(source.slice(start, end), {
    HTMLImageElement: Image, Event, window: events,
    document: { createElement: () => new Element() },
    pages: { querySelectorAll: () => [surface] },
    beginActivity: () => { activities += 1; return () => { activities -= 1 } },
  })
  const notice = surface.children[0]
  const retry = notice.children[0]
  assert.equal(requests, 0)
  assert.equal(retry.hidden, false)
  assert.match(notice.firstChild.textContent, /non caricata/)
  retry.dispatchEvent(new Event('click'))
  assert.equal(requests, 1)
  assert.equal(activities, 1)
  image.dispatchEvent(new Event('error'))
  assert.equal(activities, 0)
  assert.equal(retry.hidden, false)
  retry.dispatchEvent(new Event('click'))
  image.naturalWidth = 600
  image.dispatchEvent(new Event('load'))
  assert.equal(activities, 0)
  assert.equal(notice.hidden, true)
  retry.dispatchEvent(new Event('click'))
  events.dispatchEvent(new Event('pagehide'))
  assert.equal(activities, 0)
})

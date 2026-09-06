// Technical guardrails only: these tests are not hardware/browser acceptance.
import assert from 'node:assert/strict'
import { test, afterEach } from 'node:test'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { acquireFromLocalScanner, scannerFileFromPayload } from '../../frontend/src/services/localScanner.ts'
import { prepareCaptureImage } from '../../frontend/src/components/documentCapture/captureImages.ts'

const originalFetch = globalThis.fetch
const originalDocument = globalThis.document
const originalBitmap = globalThis.createImageBitmap
afterEach(() => {
  globalThis.fetch = originalFetch
  globalThis.document = originalDocument
  globalThis.createImageBitmap = originalBitmap
})
const jpg = { ok: true, filename: 'pagina.jpg', content_base64: '/9j/2Q==' }
const json = (value, status = 200) => Response.json(value, { status })
const sourceUrl = new URL('../../frontend/src/documentToolsData.ts', import.meta.url)
// Resolve its one browser-independent dependency without changing product imports.
const source = stripTypeScriptTypes(readFileSync(sourceUrl, 'utf8')).replace("'./api/csrf'", JSON.stringify(new URL('../../frontend/src/api/csrf.ts', import.meta.url).href))
const { generateDocument, saveGeneratedDocument } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)

test('scanner: reject empty, malformed base64 and non-JPEG payloads', () => {
  for (const content_base64 of ['', '%invalid%', btoa('<html>errore</html>')]) {
    assert.throws(() => scannerFileFromPayload({ content_base64 }))
  }
  const file = scannerFileFromPayload({ ...jpg, filename: 'folder\\page:1.jpg' })
  assert.equal(file.type, 'image/jpeg')
  assert.equal(file.name, 'folder page 1.jpg')
})

test('scanner: probe loopback names, then issue exactly one acquisition', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push([url, options])
    if (url.includes('127.0.0.1')) throw new TypeError('unreachable')
    return json(url.includes('/ping?light=1') ? { ok: true } : jpg)
  }
  assert.equal((await acquireFromLocalScanner()).name, 'pagina.jpg')
  assert.deepEqual(calls.map(([url]) => url), [
    'http://127.0.0.1:27272/ping?light=1',
    'http://localhost:27272/ping?light=1',
    'http://localhost:27272/scanner/acquire',
  ])
  assert.equal(calls[2][1].method, 'POST')
  assert.deepEqual(JSON.parse(calls[2][1].body), { timeout: 120 })
  assert.ok(calls.every(([, options]) => options.targetAddressSpace === 'loopback'))
})

test('scanner: never repeat acquisition after lost response, cancellation or unsupported version', async () => {
  for (const outcome of ['lost', 'cancelled', 'not-installed']) {
    const commands = []
    globalThis.fetch = async (url, options) => {
      if (url.includes('/ping')) return json({ ok: true })
      commands.push(options)
      if (outcome === 'lost') throw new TypeError('lost response')
      return json({ ok: false, errore: 'private diagnostics' }, outcome === 'cancelled' ? 400 : 404)
    }
    await assert.rejects(acquireFromLocalScanner(), (error) => {
      assert.ok(!error.message.includes('private diagnostics'))
      return true
    })
    assert.equal(commands.length, 1)
  }
})

test('scanner: unavailable service cannot start WIA', async () => {
  let commands = 0
  globalThis.fetch = async (_, options) => { if (options.method === 'POST') commands++; throw new TypeError('offline') }
  await assert.rejects(acquireFromLocalScanner(), /Avvia IUSENTRA Local Signer/)
  assert.equal(commands, 0)
})

test('scanner: reject simultaneous clicks without another command', async () => {
  let release
  globalThis.fetch = () => new Promise((resolve) => { release = resolve })
  const first = acquireFromLocalScanner()
  await assert.rejects(acquireFromLocalScanner(), /già in corso/)
  globalThis.fetch = async () => json(jpg)
  release(json({ ok: true }))
  await first
})

test('images: reject empty, unsupported or oversized files before decoding', async () => {
  let decodes = 0
  globalThis.createImageBitmap = () => { decodes++; throw new Error('unexpected') }
  for (const file of [new File([], 'empty.jpg', { type: 'image/jpeg' }), new File(['x'], 'x.heic', { type: 'image/heic' }), { size: 61 * 1024 * 1024, type: 'image/jpeg' }]) {
    await assert.rejects(prepareCaptureImage(file))
  }
  assert.equal(decodes, 0)
})

test('images: decode orientation, re-encode pixels and release bitmap', async () => {
  let closed = 0
  let drawn = 0
  globalThis.createImageBitmap = async (_, options) => {
    assert.deepEqual(options, { imageOrientation: 'from-image' })
    return { width: 640, height: 480, close: () => closed++ }
  }
  globalThis.document = { createElement: () => ({
    getContext: () => ({ fillRect() {}, drawImage: () => drawn++ }),
    toBlob: (done, type, quality) => { assert.equal(type, 'image/jpeg'); assert.equal(quality, 0.96); done(new Blob(['pixels'], { type })) },
  }) }
  const page = await prepareCaptureImage(new File(['original metadata'], 'paper.png', { type: 'image/png' }))
  assert.equal(page.file.name, 'paper.jpg')
  assert.equal(await page.file.text(), 'pixels')
  assert.equal(page.rotation, 0)
  assert.equal(closed, 1)
  assert.equal(drawn, 1)
  URL.revokeObjectURL(page.url)
})

test('images: release bitmap on resolution failure', async () => {
  let closed = 0
  globalThis.createImageBitmap = async () => ({ width: 10000, height: 10000, close: () => closed++ })
  await assert.rejects(prepareCaptureImage(new File(['x'], 'x.jpg', { type: 'image/jpeg' })), /50 megapixel/)
  assert.equal(closed, 1)
})

test('preview: require PDF bytes instead of accepting a login page or empty response', async () => {
  for (const response of [new Response('<html>login</html>', { headers: { 'Content-Type': 'text/html' } }), new Response('', { headers: { 'Content-Type': 'application/pdf' } })]) {
    globalThis.fetch = async () => response
    await assert.rejects(generateDocument('multipage', [], 'Prova', [], []))
  }
})

test('preview: preserve page order and rotation, without uploading into a fascicolo', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/ui/document-tools/multipage')
    assert.equal(options.credentials, 'same-origin')
    assert.deepEqual(options.body.getAll('rotations'), ['90', '0'])
    assert.deepEqual(options.body.getAll('files').map((file) => file.name), ['first.jpg', 'second.jpg'])
    return new Response('%PDF-test', { headers: { 'Content-Type': 'application/pdf', 'x-iusentra-pages': '2' } })
  }
  const files = ['first.jpg', 'second.jpg'].map((name) => new File(['x'], name, { type: 'image/jpeg' }))
  const result = await generateDocument('multipage', files, 'Prova', files.map((file) => file.name), [90, 0])
  assert.equal(result.pages, 2)
  URL.revokeObjectURL(result.objectUrl)
})

test('save: explicit fascicolo target, CSRF and persisted document ID required', async () => {
  globalThis.document = { querySelector: () => ({ content: 'test-csrf' }) }
  const result = { blob: new Blob(['%PDF-test']), filename: 'prova.pdf' }
  for (const payload of [{}, { ok: false }, { ok: true }]) {
    globalThis.fetch = async () => json(payload)
    await assert.rejects(saveGeneratedDocument('CONTROLLED_CASE', result), /non confermato/)
  }
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/fascicoli/CONTROLLED_CASE/documenti/carica')
    assert.equal(options.headers['X-CSRF-Token'], 'test-csrf')
    assert.equal(options.body.get('classificazione_modalita'), 'automatica')
    assert.equal(options.body.get('files').name, 'prova.pdf')
    return json({ ok: true, documento_id: 'DOC_TEST' })
  }
  assert.match(await saveGeneratedDocument('CONTROLLED_CASE', result), /salvato nel fascicolo/)
})

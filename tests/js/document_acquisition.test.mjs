// Guardrail tecnici dell'acquisizione dall'editor: non sostituiscono la prova su scanner,
// webcam e telefono reali.
import './support/resolve_ts_extensionless.mjs'
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

const src = (path) => new URL(`../../frontend/src/${path}`, import.meta.url).href
const { detectDocumentQuad, orderQuad, simplifyToQuad, convexHull } = await import(src('components/documentCapture/detection/documentQuad.ts'))
const { rgbaToGray, otsuThreshold } = await import(src('components/documentCapture/detection/grayImage.ts'))
const { computeHomography, projectPoint, outputSizeForQuad, warpPerspective, A4_RATIO } = await import(src('components/documentCapture/detection/perspective.ts'))
const { applyPageFilter } = await import(src('components/documentCapture/detection/enhance.ts'))
const { quadMovement, smoothQuad } = await import(src('components/documentCapture/useDocumentDetection.ts'))
const { pinchZoomValue, touchDistance, touchMidpoint } = await import(src('components/templateEditor/usePinchZoom.ts'))
const { pdfBlobFromBase64, recognizeDocument, recognizePage } = await import(src('services/documentOcr.ts'))

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

function inside(point, quad) {
  for (let index = 0; index < 4; index += 1) {
    const a = quad[index]
    const b = quad[(index + 1) % 4]
    if (((b.x - a.x) * (point.y - a.y)) - ((b.y - a.y) * (point.x - a.x)) < 0) return false
  }
  return true
}

function syntheticFrame(width, height, quad, background, paper) {
  const data = new Uint8ClampedArray(width * height * 4)
  let seed = 11
  const noise = () => { seed = (seed * 16807) % 2147483647; return (seed / 2147483647) - 0.5 }
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const offset = ((y * width) + x) * 4
      const onPaper = inside({ x, y }, quad)
      let value = onPaper ? paper : background
      if (onPaper && y % 14 < 2 && x % 40 < 30) value = 40
      value += noise() * 18
      data[offset] = value; data[offset + 1] = value; data[offset + 2] = value; data[offset + 3] = 255
    }
  }
  return data
}

test('rilevamento: trova i quattro angoli del foglio su sfondi scuri e chiari', () => {
  const quad = [{ x: 150, y: 60 }, { x: 500, y: 90 }, { x: 470, y: 430 }, { x: 120, y: 400 }]
  for (const [background, paper, tolerance] of [[70, 225, 6], [30, 180, 6], [200, 240, 25]]) {
    const gray = rgbaToGray(syntheticFrame(640, 480, quad, background, paper), 640, 480, 320)
    const found = detectDocumentQuad(gray)
    assert.ok(found, `foglio non rilevato su sfondo ${background}`)
    found.quad.forEach((point, index) => {
      assert.ok(Math.hypot((point.x * 2) - quad[index].x, (point.y * 2) - quad[index].y) < tolerance, `angolo ${index} fuori tolleranza`)
    })
  }
})

test('rilevamento: nessun riquadro su un fotogramma uniforme', () => {
  const data = new Uint8ClampedArray(320 * 240 * 4).fill(128)
  assert.equal(detectDocumentQuad(rgbaToGray(data, 320, 240)), null)
})

test('geometria: guscio convesso, riduzione a quadrilatero e ordine degli angoli', () => {
  const hull = convexHull([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }, { x: 5, y: 5 }, { x: 10, y: 5 }])
  assert.equal(hull.length, 4)
  const quad = simplifyToQuad([{ x: 0, y: 0 }, { x: 5, y: -0.2 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }])
  assert.deepEqual(quad.map((point) => [point.x, point.y]), [[0, 0], [10, 0], [10, 10], [0, 10]])
  assert.deepEqual(orderQuad([{ x: 9, y: 9 }, { x: 0, y: 9 }, { x: 9, y: 0 }, { x: 0, y: 0 }]).map((p) => [p.x, p.y]), [[0, 0], [9, 0], [9, 9], [0, 9]])
  assert.equal(otsuThreshold([10, 10, 10, 200, 200, 200]), 10)
})

test('raddrizzamento: omografia esatta, proporzione A4 e pixel campionati', () => {
  const from = [{ x: 10, y: 20 }, { x: 210, y: 30 }, { x: 200, y: 300 }, { x: 5, y: 290 }]
  const to = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 141 }, { x: 0, y: 141 }]
  const h = computeHomography(from, to)
  from.forEach((point, index) => {
    const projected = projectPoint(h, point)
    assert.ok(Math.abs(projected.x - to[index].x) < 1e-6 && Math.abs(projected.y - to[index].y) < 1e-6)
  })
  const size = outputSizeForQuad(from)
  assert.ok(Math.abs((size.height / size.width) - A4_RATIO) < 0.01)
  assert.deepEqual(outputSizeForQuad(from, { width: 1654, height: 2339 }), { width: 1654, height: 2339 })
  const source = new Uint8ClampedArray(4 * 4 * 4).fill(90)
  const warped = warpPerspective(source, { width: 4, height: 4 }, [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 4 }, { x: 0, y: 4 }], { width: 8, height: 8 })
  assert.equal(warped.length, 8 * 8 * 4)
  assert.equal(warped[0], 90)
  assert.equal(warped[3], 255)
})

test('resa: bianco e nero produce solo pixel 0 o 255 e documento nitido schiarisce lo sfondo in ombra', () => {
  const width = 96
  const height = 96
  const pixels = new Uint8ClampedArray(width * height * 4)
  for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) {
    const offset = ((y * width) + x) * 4
    const value = (x % 12 < 2) ? 30 : 150 + Math.round(x / 2)
    pixels.fill(value, offset, offset + 3)
    pixels[offset + 3] = 255
  }
  const bw = applyPageFilter(new Uint8ClampedArray(pixels), width, height, 'bianco-nero')
  for (let index = 0; index < bw.length; index += 4) assert.ok(bw[index] === 0 || bw[index] === 255)
  const clean = applyPageFilter(new Uint8ClampedArray(pixels), width, height, 'documento')
  assert.ok(clean[((10 * width) + 5) * 4] > pixels[((10 * width) + 5) * 4])
  const colour = new Uint8ClampedArray(pixels)
  assert.deepEqual(applyPageFilter(colour, width, height, 'colore'), pixels)
})

test('rilevamento dal vivo: media mobile e misura dello spostamento degli angoli', () => {
  const a = [{ x: 0.1, y: 0.1 }, { x: 0.9, y: 0.1 }, { x: 0.9, y: 0.9 }, { x: 0.1, y: 0.9 }]
  const b = a.map((point) => ({ x: point.x + 0.01, y: point.y }))
  assert.ok(Math.abs(quadMovement(a, b) - 0.01) < 1e-9)
  assert.ok(Math.abs(smoothQuad(a, b, 0.5)[0].x - 0.105) < 1e-9)
  const far = a.map((point) => ({ x: point.x + 0.3, y: point.y }))
  assert.deepEqual(smoothQuad(a, far), far)
})

test('zoom a due dita: proporzionale alla distanza e limitato tra 30% e 200%', () => {
  const first = { clientX: 0, clientY: 0 }
  const second = { clientX: 30, clientY: 40 }
  assert.equal(touchDistance(first, second), 50)
  assert.deepEqual(touchMidpoint(first, second), { clientX: 15, clientY: 20 })
  assert.equal(pinchZoomValue(0.5, 100, 200), 1)
  assert.equal(pinchZoomValue(1, 100, 1000), 2)
  assert.equal(pinchZoomValue(0.5, 100, 10), 0.3)
  assert.equal(pinchZoomValue(0.8, 0, 50), 0.8)
})

const pdfBase64 = Buffer.from('%PDF-1.7\n%%EOF').toString('base64')

test('OCR: una richiesta per pagina con rotazione, PDF valido obbligatorio', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push([url, options])
    return Response.json({ ok: true, pdf_base64: pdfBase64, paragraphs: ['Atto', ' '], characters: 4 })
  }
  const file = new File([new Uint8Array([255, 216, 255])], 'pagina-001.jpg', { type: 'image/jpeg' })
  const page = await recognizePage({ file, rotation: 450 })
  assert.equal(calls[0][0], '/api/v1/ui/document-tools/ocr-page')
  assert.equal(calls[0][1].method, 'POST')
  assert.equal(calls[0][1].body.get('rotation'), '90')
  assert.deepEqual(page.paragraphs, ['Atto'])
  assert.throws(() => pdfBlobFromBase64(Buffer.from('<html>').toString('base64')))
})

test('OCR: errore del server mostrato in italiano, nessuna unione per una sola pagina', async () => {
  globalThis.fetch = async () => Response.json({ ok: false, message: 'Il dizionario italiano per il riconoscimento del testo non è installato sul server.' }, { status: 400 })
  const file = new File([new Uint8Array([1])], 'p.jpg', { type: 'image/jpeg' })
  await assert.rejects(recognizePage({ file, rotation: 0 }), /dizionario italiano/)

  const urls = []
  globalThis.fetch = async (url) => { urls.push(url); return Response.json({ ok: true, pdf_base64: pdfBase64, paragraphs: [], characters: 0 }) }
  const progress = []
  const outcome = await recognizeDocument([{ file, rotation: 0 }], 'Procura: Rossi?', (done, total) => progress.push(`${done}/${total}`))
  assert.deepEqual(urls, ['/api/v1/ui/document-tools/ocr-page'])
  assert.deepEqual(progress, ['0/1', '1/1'])
  assert.equal(outcome.document.filename, 'Procura Rossi .pdf'.replace(' .pdf', '.pdf'))
  assert.equal(outcome.emptyPages, 1)
})

test('OCR: più pagine riconosciute in ordine e unite in un solo PDF', async () => {
  const urls = []
  globalThis.fetch = async (url, options) => {
    urls.push(url)
    if (url.endsWith('/merge')) {
      assert.equal(options.body.getAll('files').length, 2)
      return new Response(new Blob(['%PDF-1.7']), { headers: { 'content-type': 'application/pdf', 'x-iusentra-pages': '2' } })
    }
    return Response.json({ ok: true, pdf_base64: pdfBase64, paragraphs: [`Pagina ${urls.length}`], characters: 7 })
  }
  const file = new File([new Uint8Array([1])], 'p.jpg', { type: 'image/jpeg' })
  const outcome = await recognizeDocument([{ file, rotation: 0 }, { file, rotation: 180 }], 'Allegati', () => undefined)
  assert.deepEqual(urls, ['/api/v1/ui/document-tools/ocr-page', '/api/v1/ui/document-tools/ocr-page', '/api/v1/ui/document-tools/merge'])
  assert.deepEqual(outcome.paragraphs, ['Pagina 1', 'Pagina 2'])
  assert.equal(outcome.document.pages, 2)
  assert.equal(outcome.characters, 14)
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function load(context, relativePath) {
  const source = readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8')
  vm.runInContext(source, context, { filename: relativePath })
}

function makeContext(fetchImpl) {
  const events = []
  const context = {
    console,
    events,
    location: { origin: 'https://app.iusentra.it' },
    performance: { now: () => 10 },
    CustomEvent: class CustomEvent {
      constructor(type, options) {
        this.type = type
        this.detail = options && options.detail
      }
    },
    dispatchEvent(event) {
      events.push(event)
    },
    fetch: fetchImpl,
  }
  context.window = context
  context.globalThis = context
  vm.createContext(context)
  load(context, 'web/static/js/lex-tts/supertonic-engine.js')
  return context
}

const missingManifest = makeContext(() => Promise.resolve({ ok: false }))
const missingStatus = await missingManifest.IusentraSupertonicEngine.preload()
assert.equal(missingStatus.ready, false)
assert.equal(missingStatus.enabled, false)
assert.equal(missingStatus.reason, 'manifest_missing')
assert.equal(missingManifest.IusentraSupertonicEngine.isReady(), false)
assert.equal(missingManifest.IusentraSupertonicEngine.isSupported(), false)
const missingSpeak = await missingManifest.IusentraSupertonicEngine.speak('Test voce Lex', { lang: 'it-IT' })
assert.equal(missingSpeak.ok, false)
assert.equal(missingSpeak.engine, 'supertonic')

const disabledManifest = makeContext(() => Promise.resolve({
  ok: true,
  json: () => Promise.resolve({
    enabled: false,
    basePath: '/static/vendor/supertonic',
  }),
}))
const disabledStatus = await disabledManifest.IusentraSupertonicEngine.preload()
assert.equal(disabledStatus.ready, false)
assert.equal(disabledStatus.enabled, false)
assert.equal(disabledStatus.reason, 'disabled')

const noRuntime = makeContext((path) => {
  assert.equal(path, '/static/vendor/supertonic/manifest.json')
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      enabled: true,
      basePath: '/static/vendor/supertonic',
      onnxPath: '/static/vendor/supertonic/onnx',
      voiceStylesPath: '/static/vendor/supertonic/voice_styles',
      defaultVoiceStyle: 'F1.json',
    }),
  })
})
const noRuntimeStatus = await noRuntime.IusentraSupertonicEngine.preload()
assert.equal(noRuntimeStatus.ready, false)
assert.equal(noRuntimeStatus.enabled, true)
assert.match(noRuntimeStatus.reason, /ONNX Runtime/)
assert.equal(noRuntime.IusentraSupertonicEngine.getBackendLabel(), 'Supertonic non disponibile')
assert.ok(noRuntime.events.some((event) => event.type === 'iusentra:lex-voice-status'))

const fakeRuntime = makeContext((path) => {
  if (path === '/static/vendor/supertonic/manifest.json') {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        enabled: true,
        basePath: '/static/vendor/supertonic',
        onnxPath: '/static/vendor/supertonic/onnx',
        voiceStylesPath: '/static/vendor/supertonic/voice_styles',
        defaultVoiceStyle: 'F1.json',
        fallbackVoiceStyle: 'M1.json',
      }),
    })
  }
  if (path.endsWith('/tts.json')) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ ae: { sample_rate: 24000, base_chunk_size: 512 }, ttl: { chunk_compress_factor: 1, latent_dim: 1 } }) })
  }
  if (path.endsWith('/unicode_indexer.json')) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve([0, 1, 2, 3]) })
  }
  if (path.endsWith('/F1.json') || path.endsWith('/M1.json')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        style_ttl: { dims: [1], data: [1] },
        style_dp: { dims: [1], data: [1] },
      }),
    })
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
})
fakeRuntime.ort = {
  Tensor: class Tensor {
    constructor(type, values, dims) {
      this.type = type
      this.values = values
      this.dims = dims
    }
  },
  InferenceSession: {
    create: () => Promise.resolve({ run: () => Promise.resolve({}) }),
  },
  env: { wasm: {} },
}
const f1Status = await fakeRuntime.IusentraSupertonicEngine.preload({ voiceStyle: 'F1.json' })
assert.equal(f1Status.ready, true)
assert.equal(f1Status.voiceStyle, 'F1.json')
const m1Status = await fakeRuntime.IusentraSupertonicEngine.preload({ voiceStyle: 'M1.json' })
assert.equal(m1Status.ready, true)
assert.equal(m1Status.voiceStyle, 'M1.json')

console.log('lex_tts_supertonic_engine.test.mjs OK')

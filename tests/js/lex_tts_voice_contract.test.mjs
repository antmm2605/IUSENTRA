import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function loadScript(context, relativePath) {
  const source = readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8')
  vm.runInContext(source, context, { filename: relativePath })
}

function makeContext() {
  const spoken = []
  const context = {
    console,
    spoken,
    setTimeout(fn) {
      fn()
      return 1
    },
    clearTimeout() {},
    CustomEvent: class CustomEvent {
      constructor(type, options) {
        this.type = type
        this.detail = options && options.detail
      }
    },
    dispatchEvent() {},
    location: { origin: 'https://app.iusentra.it' },
    fetch() {
      return Promise.resolve({ ok: false })
    },
    SpeechSynthesisUtterance: class SpeechSynthesisUtterance {
      constructor(text) {
        this.text = text
      }
    },
    speechSynthesis: {
      cancel() {
        spoken.push('[cancel]')
      },
      getVoices() {
        return [{ name: 'Google italiano', lang: 'it-IT', voiceURI: 'it' }]
      },
      speak(utterance) {
        spoken.push(utterance.text)
        if (utterance.onend) {
          utterance.onend()
        }
      },
    },
  }
  context.window = context
  context.globalThis = context
  vm.createContext(context)
  return context
}

const full = makeContext()
for (const script of [
  'web/static/js/lex-tts/legal-speech-normalizer.js',
  'web/static/js/lex-tts/browser-speech-engine.js',
  'web/static/js/lex-tts/supertonic-engine.js',
  'web/static/js/lex-tts/tts-engine-registry.js',
  'web/static/js/pct-lex-assistant-voice.js',
]) {
  loadScript(full, script)
}

assert.equal(full.PctLexVoice.supportsSpeech(), true)
assert.equal(full.PctLexVoice.supportsRecognition(), false)
assert.equal(full.PctLexVoice.speak('Ai sensi dell\u2019art. 183 c.p.c.', { lang: 'it-IT' }), true)
assert.ok(full.spoken.some((value) => value.includes('articolo 183 del codice di procedura civile')))
assert.doesNotThrow(() => full.PctLexVoice.cancelSpeech())

const fallbackOnly = makeContext()
loadScript(fallbackOnly, 'web/static/js/pct-lex-assistant-voice.js')
assert.equal(fallbackOnly.PctLexVoice.speak('Voce browser ancora disponibile.', { lang: 'it-IT' }), true)
assert.ok(fallbackOnly.spoken.includes('Voce browser ancora disponibile.'))

console.log('lex_tts_voice_contract.test.mjs OK')

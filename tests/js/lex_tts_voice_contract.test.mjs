import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function loadScript(context, relativePath) {
  const source = readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8')
  vm.runInContext(source, context, { filename: relativePath })
}

function makeContext(options = {}) {
  const spoken = []
  const timers = []
  const context = {
    console,
    spoken,
    timers,
    setTimeout(fn) {
      if (options.deferTimers) {
        timers.push(fn)
        return timers.length
      }
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
    document: {
      activeElement: null,
      addEventListener() {},
      contains() {
        return true
      },
      execCommand() {
        return true
      },
    },
    location: { origin: 'https://app.iusentra.it' },
    navigator: {
      permissions: {
        query() {
          return Promise.resolve({ state: 'granted' })
        },
      },
      mediaDevices: {
        getUserMedia() {
          const tracks = [{ stop() {}, applyConstraints() { return Promise.resolve() } }]
          return Promise.resolve({
            getTracks() {
              return tracks
            },
            getAudioTracks() {
              return tracks
            },
          })
        },
        enumerateDevices() {
          return Promise.resolve([{ kind: 'audioinput', label: 'Microfono studio' }])
        },
      },
    },
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
  'web/static/js/lex-tts/quality-presets.js',
  'web/static/js/lex-tts/voice-profiles.js',
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
assert.ok(full.spoken.some((value) => value.includes('articolo centottantatre del codice di procedura civile')))
assert.doesNotThrow(() => full.PctLexVoice.cancelSpeech())

const fallbackOnly = makeContext()
loadScript(fallbackOnly, 'web/static/js/pct-lex-assistant-voice.js')
assert.equal(fallbackOnly.PctLexVoice.speak('Voce browser ancora disponibile.', { lang: 'it-IT' }), true)
assert.ok(fallbackOnly.spoken.includes('Voce browser ancora disponibile.'))

const recognitionContext = makeContext({ deferTimers: true })
class FakeRecognition {
  constructor() {
    this.started = 0
    this.stopped = 0
    FakeRecognition.last = this
  }

  start() {
    this.started += 1
    if (this.onstart) {
      this.onstart()
    }
  }

  stop() {
    this.stopped += 1
    if (this.onend) {
      this.onend()
    }
  }

  emitResult(transcript, isFinal = false) {
    if (this.onresult) {
      this.onresult({
        resultIndex: 0,
        results: [
          {
            0: { transcript },
            isFinal,
          },
        ],
      })
    }
  }
}
recognitionContext.webkitSpeechRecognition = FakeRecognition
loadScript(recognitionContext, 'web/static/js/pct-lex-assistant-voice.js')
assert.equal(recognitionContext.PctLexVoice.supportsRecognition(), true)
const transcriptEvents = []
let startEvents = 0
const listeningPromise = recognitionContext.PctLexVoice.startListening({
  lang: 'it-IT',
  silenceMs: 3000,
  onStart() {
    startEvents += 1
  },
  onTranscript(text, interim) {
    transcriptEvents.push({ text, interim })
  },
})
await Promise.resolve()
await Promise.resolve()
for (let index = 0; index < 50 && !FakeRecognition.last; index += 1) {
  await Promise.resolve()
}
assert.equal(FakeRecognition.last.started, 1)
assert.equal(startEvents, 1)
assert.equal(recognitionContext.timers.length, 0)
FakeRecognition.last.emitResult('spiegami il documento caricato', false)
assert.equal(transcriptEvents.at(-1).text, 'Spiegami il documento caricato')
assert.equal(transcriptEvents.at(-1).interim, true)
assert.equal(recognitionContext.timers.length, 1)
recognitionContext.PctLexVoice.stopListening()
assert.equal(await listeningPromise, 'Spiegami il documento caricato')
assert.equal(recognitionContext.PctLexVoice.formatDictationText('mario punto rossi chiocciola studio punto it'), 'mario.rossi@studio.it')
assert.equal(recognitionContext.PctLexVoice.formatDictationText('ciao virgola prova punto escamativo'), 'Ciao, prova!')
assert.equal(typeof recognitionContext.IusentraVoiceInput.startForActiveField, 'function')
assert.equal(typeof recognitionContext.IusentraVoiceInput.verifyMicrophoneAccess, 'function')

console.log('lex_tts_voice_contract.test.mjs OK')

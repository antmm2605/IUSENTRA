import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function load(context, relativePath) {
  const source = readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8')
  vm.runInContext(source, context, { filename: relativePath })
}

const context = { console }
context.window = context
context.globalThis = context
vm.createContext(context)

load(context, 'web/static/js/lex-tts/quality-presets.js')
load(context, 'web/static/js/lex-tts/voice-profiles.js')

const presets = context.IusentraTtsQualityPresets
const profiles = context.IusentraVoiceProfiles

assert.equal(presets.getQualityPreset('fast').totalStep, 8)
assert.equal(presets.getQualityPreset('balanced').maxChunkChars, 220)
assert.equal(presets.getQualityPreset('high').speed, 0.9)

const professional = profiles.resolveSpeechOptions({ profileId: 'lex-it-professional' })
assert.equal(professional.lang, 'it-IT')
assert.equal(professional.badgeLabel, 'Voce professionale')
assert.equal(professional.quality, 'balanced')
assert.equal(professional.voiceStyle, 'M1.json')
assert.deepEqual(Array.from(professional.enginePreference), ['supertonic', 'browser'])

const readingHigh = profiles.resolveSpeechOptions({ profileId: 'lex-it-reading', quality: 'high' })
assert.equal(readingHigh.mode, 'document_reading')
assert.equal(readingHigh.quality, 'high')
assert.equal(readingHigh.totalStep, 18)
assert.ok(readingHigh.rate < professional.rate)

const brief = profiles.resolveSpeechOptions({ profileId: 'lex-it-brief' })
assert.equal(brief.voiceStyle, 'M1.json')

const legacyOptions = profiles.resolveSpeechOptions({ lang: 'it-IT', rate: 0.93, pitch: 1.08, volume: 0.98 })
assert.equal(legacyOptions.profileId, 'lex-it-professional')
assert.equal(legacyOptions.pitch, 1.08)
assert.equal(legacyOptions.volume, 0.98)

console.log('lex_tts_profiles_quality.test.mjs OK')

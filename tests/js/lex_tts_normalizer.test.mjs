import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../../web/static/js/lex-tts/legal-speech-normalizer.js', import.meta.url), 'utf8')
const context = { globalThis: {}, console }
context.globalThis = context
vm.createContext(context)
vm.runInContext(source, context)

const normalizer = context.IusentraLegalSpeechNormalizer
assert.ok(normalizer, 'normalizer should be exposed')

const markdown = normalizer.normalizeLegalSpeechText('**Sintesi**\n\nAi sensi dell\u2019art. 183 c.p.c.', {
  maxAutoReadChars: 2000,
})
assert.equal(markdown, "Sintesi. Ai sensi dell'articolo centottantatre del codice di procedura civile.")

const abbreviazioni = normalizer.normalizeLegalSpeechText('Cass. civ., Sez. Un., n. 1234/2024', {
  maxAutoReadChars: 2000,
})
assert.match(abbreviazioni, /Cassazione civile/)
assert.match(abbreviazioni, /Sezioni Unite/)
assert.match(abbreviazioni, /numero mille duecento trentaquattro del duemila ventiquattro/)

const privacy = normalizer.normalizeLegalSpeechText(
  'CF RSSMRA80A01H501Z IBAN IT60X0542811101000000123456 link https://example.invalid/a/very/long/path UUID 550e8400-e29b-41d4-a716-446655440000',
  { maxAutoReadChars: 2000 }
)
assert.doesNotMatch(privacy, /RSSMRA80A01H501Z/)
assert.doesNotMatch(privacy, /IT60X0542811101000000123456/)
assert.doesNotMatch(privacy, /550e8400-e29b-41d4-a716-446655440000/)
assert.match(privacy, /codice fiscale omesso/)
assert.match(privacy, /iban omesso/)

const longText = Array.from({ length: 32 }, (_, index) => `Periodo numero ${index + 1} con testo operativo per la lettura legale.`).join(' ')
const chunks = normalizer.splitLegalSpeechChunks(longText, { maxChunkChars: 180 })
assert.ok(chunks.length > 1)
assert.ok(chunks.every((chunk) => chunk.text.length <= 180))

const datesAndMoney = normalizer.normalizeLegalSpeechText('Udienza 15/05/2026. Importo \u20ac 1.250,50. D.Lgs. 231/2001.', {
  maxAutoReadChars: 2000,
})
assert.match(datesAndMoney, /quindici maggio duemila ventisei/)
assert.match(datesAndMoney, /mille duecento cinquanta euro e cinquanta centesimi/)
assert.match(datesAndMoney, /decreto legislativo 231\/2001/)

const prosody = normalizer.normalizeLegalSpeechText(
  'Attenzione, verifica i termini: 10 giorni? S\u00ec! Importo \u20ac 1.250,50; interessi 12,5%. Udienza ore 14:30.',
  { maxAutoReadChars: 2000 }
)
assert.match(prosody, /mille duecento cinquanta euro e cinquanta centesimi/)
assert.match(prosody, /dodici virgola cinque per cento/)
assert.match(prosody, /quattordici e trenta/)
assert.match(prosody, /dieci giorni\?/)
const prosodyChunks = normalizer.splitLegalSpeechChunks(prosody, {
  maxChunkChars: 220,
  pauseMs: { comma: 130, sentence: 300, question: 380, exclamation: 360, paragraph: 620 },
})
assert.ok(prosodyChunks.some((chunk) => chunk.pauseAfterMs === 130 && chunk.text.endsWith(',')))
assert.ok(prosodyChunks.some((chunk) => chunk.pauseAfterMs === 380))
assert.ok(prosodyChunks.some((chunk) => chunk.pauseAfterMs === 360))

assert.equal(normalizer.integerToWords(2181), 'duemila centottantuno')

console.log('lex_tts_normalizer.test.mjs OK')

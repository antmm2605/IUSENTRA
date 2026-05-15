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
assert.equal(markdown, 'Sintesi. Ai sensi dell\u2019articolo 183 del codice di procedura civile.')

const abbreviazioni = normalizer.normalizeLegalSpeechText('Cass. civ., Sez. Un., n. 1234/2024', {
  maxAutoReadChars: 2000,
})
assert.match(abbreviazioni, /Cassazione civile/)
assert.match(abbreviazioni, /Sezioni Unite/)
assert.match(abbreviazioni, /numero 1234 del 2024/)

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

console.log('lex_tts_normalizer.test.mjs OK')

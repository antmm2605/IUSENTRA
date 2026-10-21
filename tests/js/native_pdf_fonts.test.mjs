import test from 'node:test'
import assert from 'node:assert/strict'
import { embeddedFontIdentity, canUseEmbeddedFont } from '../../web/static/vendor/pdfcraft-direct/editor/font-identity.mjs'

test('an original embedded font cannot masquerade as a newly selected family', () => {
  const original = { family: 'Noto Serif', bold: 1, italic: 0 }
  const selected = { family: 'Calibri', bold: '1', italic: '0', docfont: 'ecdoc0' }
  Object.assign(selected, embeddedFontIdentity(original))
  assert.equal(canUseEmbeddedFont(selected), false)
  selected.family = 'Noto Serif'
  assert.equal(canUseEmbeddedFont(selected), true)
  selected.italic = '1'
  assert.equal(canUseEmbeddedFont(selected), false)
  assert.equal(original.family, 'Noto Serif')
})

test('unchanged embedded synthetic styles remain usable without replacement', () => {
  const original = { family: 'Arial', bold: 2, italic: true }
  const selected = { family: 'Arial', bold: '2', italic: '1', docfont: 'original', ...embeddedFontIdentity(original) }
  assert.equal(canUseEmbeddedFont(selected), true)
  selected.bold = '1'
  assert.equal(canUseEmbeddedFont(selected), false)
  delete selected.docfont
  assert.equal(canUseEmbeddedFont(selected), false)
})

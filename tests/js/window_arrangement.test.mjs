import assert from 'node:assert/strict'
import { test } from 'node:test'
import { arrangeWindowPlacements } from '../../frontend/src/components/windowPlacement.ts'

const pixels = (slot, width, bottom) => ({
  x: 8 + slot.left * (width - 16),
  y: 8 + slot.top * (bottom - 16),
  w: slot.width * (width - 16),
  h: slot.height * (bottom - 16),
})
const overlaps = (a, b) => a.x < b.x + b.w - .001 && b.x < a.x + a.w - .001 && a.y < b.y + b.h - .001 && b.y < a.y + a.h - .001

test('tre finestre automatiche: attiva a tutta altezza, altre due affiancate senza sovrapposizione', () => {
  const result = arrangeWindowPlacements(3, 'auto', 1131, 850)
  assert.equal(result.cascaded, false)
  const rects = result.slots.map(slot => pixels(slot, 1131, 850))
  assert.equal(rects[0].h, 834)
  assert.equal(rects[1].h, 413)
  assert.equal(rects[2].h, 413)
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) assert.equal(overlaps(rects[i], rects[j]), false)
})

test('griglia quattro finestre: stessa dimensione e nessuno spazio non assegnato', () => {
  const result = arrangeWindowPlacements(4, 'grid', 1440, 840)
  const rects = result.slots.map(slot => pixels(slot, 1440, 840))
  assert.equal(result.cascaded, false)
  assert.equal(new Set(rects.map(rect => `${rect.w}x${rect.h}`)).size, 1)
  const expected = [[8, 8], [724, 8], [8, 424], [724, 424]]
  rects.forEach((rect, index) => {
    assert.ok(Math.abs(rect.x - expected[index][0]) < .001)
    assert.ok(Math.abs(rect.y - expected[index][1]) < .001)
  })
})

test('affiancamento tre finestre usa tre colonne quando ogni colonna resta leggibile', () => {
  const result = arrangeWindowPlacements(3, 'columns', 1131, 850)
  const rects = result.slots.map(slot => pixels(slot, 1131, 850))
  assert.equal(result.cascaded, false)
  assert.ok(rects.every(rect => rect.w >= 360 && rect.h === 834))
  assert.equal(new Set(rects.map(rect => rect.x)).size, 3)
})

test('una sola finestra usa tutto lo spazio disponibile in ogni modalità a riquadri', () => {
  for (const mode of ['auto', 'columns', 'grid']) {
    assert.deepEqual(pixels(arrangeWindowPlacements(1, mode, 1131, 850).slots[0], 1131, 850), { x: 8, y: 8, w: 1115, h: 834 })
  }
})

test('mobile: tre finestre conservano larghezza leggibile tramite disposizione sovrapposta', () => {
  const result = arrangeWindowPlacements(3, 'auto', 375, 749)
  assert.equal(result.cascaded, true)
  assert.ok(result.slots.map(slot => pixels(slot, 375, 749)).every(rect => rect.w === 359 && rect.x === 8 && rect.h >= 240))
})

test('spazio limitato e molte finestre: ogni disposizione rimane entro schermo e prima della barra', () => {
  for (const [width, bottom] of [[375, 700], [768, 620], [1131, 850], [1920, 1010]]) {
    for (const count of [1, 2, 3, 4, 5, 8, 12, 25]) {
      for (const mode of ['auto', 'grid', 'columns', 'cascade']) {
        const result = arrangeWindowPlacements(count, mode, width, bottom)
        assert.equal(result.slots.length, count)
        const rects = result.slots.map(slot => pixels(slot, width, bottom))
        for (const rect of rects) {
          assert.ok(rect.x >= 8 && rect.y >= 8)
          assert.ok(rect.x + rect.w <= width - 8 + .001)
          assert.ok(rect.y + rect.h <= bottom - 8 + .001)
          assert.ok(rect.w >= Math.min(360, width - 16) && rect.h >= Math.min(240, bottom - 16))
        }
        if (!result.cascaded) for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) assert.equal(overlaps(rects[i], rects[j]), false)
      }
    }
  }
})

test('nessuna finestra: nessun riquadro inventato', () => {
  assert.deepEqual(arrangeWindowPlacements(0, 'auto', 1131, 850), { slots: [], cascaded: false })
})

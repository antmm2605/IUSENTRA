import assert from 'node:assert/strict'
import { test } from 'node:test'
import { resizeWindowBounds } from '../../frontend/src/components/windowPlacement.ts'

const original = { left: 100, top: 100, width: 500, height: 400 }
test('allargamento da sinistra conserva il bordo opposto e limita allo schermo', () => {
  assert.deepEqual(resizeWindowBounds(original, 'w', -300, 0, 1000, 700), { left: 8, top: 100, width: 592, height: 400 })
  assert.deepEqual(original, { left: 100, top: 100, width: 500, height: 400 })
})
test('angolo inferiore: limita la finestra prima della barra dei lavori', () => {
  assert.deepEqual(resizeWindowBounds(original, 'se', 200, 200, 1000, 700), { left: 100, top: 100, width: 700, height: 592 })
})
test('angolo superiore: mantiene la posizione dei bordi inferiore e destro', () => {
  assert.deepEqual(resizeWindowBounds(original, 'nw', -200, -200, 1000, 700), { left: 8, top: 8, width: 592, height: 492 })
})
test('riduzione estrema mantiene le dimensioni minime per i comandi', () => {
  assert.deepEqual(resizeWindowBounds(original, 'nw', 1000, 1000, 1000, 700), { left: 240, top: 260, width: 360, height: 240 })
})
test('schermo piccolo: minimi adattivi e nessun bordo fuori viewport', () => {
  const result = resizeWindowBounds({ left: 8, top: 8, width: 359, height: 740 }, 'se', 1000, 1000, 375, 770)
  assert.deepEqual(result, { left: 8, top: 8, width: 359, height: 754 })
})
for (const edge of ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw']) {
  test(`bordo ${edge}: movimento cambia soltanto i bordi richiesti`, () => {
    const result = resizeWindowBounds(original, edge, 12, 12, 1000, 700)
    assert.equal(result.left, edge.includes('w') ? 112 : 100)
    assert.equal(result.top, edge.includes('n') ? 112 : 100)
    assert.equal(result.left + result.width, edge.includes('e') ? 612 : 600)
    assert.equal(result.top + result.height, edge.includes('s') ? 512 : 500)
  })
}

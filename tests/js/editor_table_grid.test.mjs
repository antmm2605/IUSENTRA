import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tableGrid, tableArea } from '../../frontend/src/editorTableGrid.ts'

const cell = (colSpan = 1, rowSpan = 1) => ({ colSpan, rowSpan })
const table = (rows) => ({ rows: rows.map((cells) => ({ cells })) })

test('selezione rettangolare comprende correttamente celle unite in entrambe le direzioni', () => {
  const source = table([[cell(1, 2), cell(2)], [cell(), cell()]])
  const structure = tableGrid(source)
  assert.equal(structure.columns, 3)
  assert.equal(structure.grid[0][0], structure.grid[1][0])
  assert.equal(tableArea(source, { top: 0, bottom: 1, left: 0, right: 2 }).selected.length, 4)
})

test('intervallo che taglia una cella unita è rifiutato prima della modifica', () => {
  const source = table([[cell(1, 2), cell(2)], [cell(), cell()]])
  assert.throws(() => tableArea(source, { top: 1, bottom: 1, left: 0, right: 2 }), /interamente/)
  assert.throws(() => tableArea(source, { top: 0, bottom: 0, left: 1, right: 1 }), /interamente/)
})

test('celle sovrapposte e intervalli fuori limite non producono una falsa selezione', () => {
  assert.throws(() => tableGrid(table([[cell(1, 2), cell()], [cell(2)]])), /rettangolare|sovrapposte/)
  assert.throws(() => tableArea(table([[cell()]]), { top: 0, bottom: 0, left: 0, right: 1 }), /valido/)
})

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tableGrid, tableArea, formatTableCells } from '../../frontend/src/editorTableGrid.ts'

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

const styledCell = (colSpan = 1, rowSpan = 1, style = 'border:1pt solid #333333') => ({
  colSpan, rowSpan,
  getAttribute(name) { return name === 'style' ? style : null },
  setAttribute(name, value) { if (name === 'style') style = value },
  cloneNode() { return styledCell(colSpan, rowSpan, style) },
})
const styledTable = (rows) => ({
  rows: rows.map(cells => ({ cells })),
  cloneNode() { return styledTable(this.rows.map(row => row.cells.map(cell => cell.cloneNode()))) },
})

test('rimuovere un bordo condiviso aggiorna entrambi i lati senza modificare la fonte', () => {
  const source = styledTable([[styledCell(), styledCell()]])
  const result = formatTableCells(source, { top: 0, bottom: 0, left: 0, right: 0 }, { borders: 'right', borderStyle: 'none' })
  assert.match(result.rows[0].cells[0].getAttribute('style'), /border-right:none/)
  assert.match(result.rows[0].cells[1].getAttribute('style'), /border-left:none/)
  assert.doesNotMatch(source.rows[0].cells[0].getAttribute('style'), /border-right:none/)
})

test('bordo singolo riguarda il contorno della selezione e conserva i bordi interni', () => {
  const source = styledTable([[styledCell()], [styledCell()]])
  const result = formatTableCells(source, { top: 0, bottom: 1, left: 0, right: 0 }, { borders: 'top', borderStyle: 'none' })
  assert.match(result.rows[0].cells[0].getAttribute('style'), /border-top:none/)
  assert.equal(result.rows[1].cells[0].getAttribute('style'), 'border:1pt solid #333333')
})

test('rimozione parziale accanto a una cella unita non cancella segmenti non selezionati', () => {
  const source = styledTable([[styledCell(), styledCell(1, 2)], [styledCell()]])
  assert.throws(() => formatTableCells(source, { top: 0, bottom: 0, left: 0, right: 0 }, { borders: 'right', borderStyle: 'none' }), /estendi la selezione/)
  assert.equal(source.rows[0].cells[1].getAttribute('style'), 'border:1pt solid #333333')
})

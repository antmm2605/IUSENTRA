export type TableAction = 'rowBefore' | 'rowAfter' | 'rowDelete' | 'columnBefore' | 'columnAfter' | 'columnDelete'
type Origin = { cell: HTMLTableCellElement; row: number; column: number }

export function tableGrid(table: HTMLTableElement) {
  const grid: Origin[][] = []
  const origins: Origin[] = []
  Array.from(table.rows).forEach((row, r) => {
    grid[r] ||= []
    let c = 0
    Array.from(row.cells).forEach((cell) => {
      while (grid[r][c]) c++
      const origin = { cell, row: r, column: c }
      origins.push(origin)
      const height = cell.rowSpan || table.rows.length - r
      for (let y = r; y < Math.min(table.rows.length, r + height); y++) {
        grid[y] ||= []
        for (let x = c; x < c + cell.colSpan; x++) {
          if (grid[y][x]) throw new Error('La tabella contiene celle sovrapposte.')
          grid[y][x] = origin
        }
      }
      c += cell.colSpan
    })
  })
  const columns = Math.max(0, ...grid.map((row) => row.length))
  if (!columns || grid.some((row) => row.length !== columns || Array.from({ length: columns }, (_, c) => !row[c]).some(Boolean))) {
    throw new Error('La struttura della tabella non è rettangolare.')
  }
  return { grid, origins, columns }
}

export function editTable(table: HTMLTableElement, selected: HTMLTableCellElement, action: TableAction) {
  const { grid, origins, columns } = tableGrid(table)
  const current = origins.find((origin) => origin.cell === selected)
  if (!current) throw new Error('Seleziona una cella della tabella.')
  const clone = table.cloneNode(true) as HTMLTableElement
  const cloned = tableGrid(clone)
  const newCell = (tag: string) => {
    const cell = document.createElement(tag) as HTMLTableCellElement
    cell.innerHTML = '<p><br></p>'
    return cell
  }
  if (action.startsWith('row')) {
    if (action === 'rowDelete') {
      if (table.rows.length === 1) return null
      const r = current.row
      cloned.origins.forEach((origin) => {
        const span = origin.cell.rowSpan || clone.rows.length - origin.row
        if (origin.row < r && origin.row + span > r) origin.cell.rowSpan = span - 1
        else if (origin.row === r && span > 1) {
          const next = clone.rows[r + 1]
          const following = cloned.origins.find((other) => other.row === r + 1 && other.column > origin.column)
          next.insertBefore(origin.cell, following?.cell || null)
          origin.cell.rowSpan = span - 1
        }
      })
      clone.rows[r].remove()
    } else {
      if (table.rows.length >= 50) throw new Error('La tabella può contenere al massimo 50 righe.')
      const r = current.row + (action === 'rowAfter' ? 1 : 0)
      const row = document.createElement('tr')
      const crossed = new Set<HTMLTableCellElement>()
      for (let c = 0; c < columns; c++) {
        const above = r > 0 ? cloned.grid[r - 1][c] : null
        if (above && above.row + (above.cell.rowSpan || clone.rows.length - above.row) > r) {
          if (!crossed.has(above.cell)) { above.cell.rowSpan = (above.cell.rowSpan || clone.rows.length - above.row) + 1; crossed.add(above.cell) }
        } else row.appendChild(newCell(r === 0 && grid[0][c].cell.tagName === 'TH' ? 'th' : 'td'))
      }
      const reference = clone.rows[r] || null
      ;(reference?.parentElement || clone.rows[clone.rows.length - 1].parentElement)?.insertBefore(row, reference)
    }
  } else {
    if (action === 'columnDelete') {
      if (columns === 1) return null
      const c = current.column
      cloned.origins.forEach((origin) => {
        if (origin.column <= c && origin.column + origin.cell.colSpan > c) {
          if (origin.cell.colSpan > 1) origin.cell.colSpan--
          else origin.cell.remove()
        }
      })
    } else {
      if (columns >= 20) throw new Error('La tabella può contenere al massimo 20 colonne.')
      const c = current.column + (action === 'columnAfter' ? selected.colSpan : 0)
      const crossed = new Set<HTMLTableCellElement>()
      for (let r = 0; r < clone.rows.length; r++) {
        const left = c > 0 ? cloned.grid[r][c - 1] : null
        if (left && left.column < c && left.column + left.cell.colSpan > c) {
          if (!crossed.has(left.cell)) { left.cell.colSpan++; crossed.add(left.cell) }
        } else {
          const following = cloned.origins.find((origin) => origin.row === r && origin.column >= c)
          const rowCell = cloned.grid[r][Math.min(c, columns - 1)].cell
          clone.rows[r].insertBefore(newCell(rowCell.tagName.toLowerCase()), following?.cell || null)
        }
      }
    }
  }
  const result = tableGrid(clone)
  result.origins.forEach(({ cell }) => { cell.style.width = `${100 * cell.colSpan / result.columns}%` })
  return clone
}

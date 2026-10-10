export type TableAction = 'rowBefore' | 'rowAfter' | 'rowDelete' | 'columnBefore' | 'columnAfter' | 'columnDelete'
export type CellArea = { top: number; left: number; bottom: number; right: number }
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

export function tableArea(table: HTMLTableElement, area: CellArea) {
  const structure = tableGrid(table)
  const { top, left, bottom, right } = area
  if (![top, left, bottom, right].every(Number.isInteger) || top < 0 || left < 0 || bottom < top || right < left || bottom >= structure.grid.length || right >= structure.columns) {
    throw new Error('Scegli un intervallo valido di righe e colonne.')
  }
  const selected = structure.origins.filter(({ row, column, cell }) => row <= bottom && column <= right && row + (cell.rowSpan || structure.grid.length - row) > top && column + cell.colSpan > left)
  if (selected.some(({ row, column, cell }) => row < top || column < left || row + (cell.rowSpan || structure.grid.length - row) - 1 > bottom || column + cell.colSpan - 1 > right)) {
    throw new Error('La selezione attraversa una cella unita: includila interamente.')
  }
  return { ...structure, selected }
}

export function mergeTableCells(table: HTMLTableElement, area: CellArea) {
  const clone = table.cloneNode(true) as HTMLTableElement
  const { selected } = tableArea(clone, area)
  if (selected.length < 2) throw new Error('Seleziona almeno due celle da unire.')
  if (new Set(selected.map(({ cell }) => cell.parentElement?.parentElement)).size > 1) throw new Error('Unisci separatamente le celle dell’intestazione e del corpo della tabella.')
  // Keep every paragraph, link, image and inline style in reading order.
  const target = selected[0].cell
  selected.slice(1).forEach(({ cell }) => {
    const hasBlocks = Array.from(cell.children).some((child) => ['P', 'DIV', 'UL', 'OL', 'TABLE', 'H1', 'H2', 'H3'].includes(child.tagName))
    const destination = hasBlocks ? target : document.createElement('p')
    while (cell.firstChild) destination.appendChild(cell.firstChild)
    if (!hasBlocks) target.appendChild(destination)
    cell.remove()
  })
  target.rowSpan = area.bottom - area.top + 1
  target.colSpan = area.right - area.left + 1
  target.style.width = ''
  tableGrid(clone)
  return clone
}

export function splitTableCells(table: HTMLTableElement, area: CellArea) {
  const clone = table.cloneNode(true) as HTMLTableElement
  const { selected, grid, origins } = tableArea(clone, area)
  if (!selected.some(({ cell }) => cell.colSpan > 1 || cell.rowSpan !== 1)) throw new Error('Seleziona una cella unita da dividere.')
  selected.forEach(({ cell, row, column }) => {
    const height = cell.rowSpan || grid.length - row
    const width = cell.colSpan
    cell.rowSpan = 1
    cell.colSpan = 1
    cell.style.width = ''
    for (let r = row; r < row + height; r++) {
      for (let c = column; c < column + width; c++) {
        if (r === row && c === column) continue
        const blank = cell.cloneNode(false) as HTMLTableCellElement
        blank.removeAttribute('id')
        blank.innerHTML = '<p><br></p>'
        const next = origins.find((origin) => origin.row === r && origin.column > c && origin.cell.parentElement === clone.rows[r])
        clone.rows[r].insertBefore(blank, next?.cell || null)
      }
    }
  })
  tableGrid(clone)
  return clone
}

export function formatTableCells(table: HTMLTableElement, area: CellArea, options: {
  borders?: 'all' | 'none' | 'outside' | 'inside' | 'horizontal' | 'vertical' | 'top' | 'right' | 'bottom' | 'left'; borderStyle?: 'solid' | 'double' | 'dotted' | 'dashed' | 'none';
  borderWidth?: number; borderColor?: string; background?: string; verticalAlign?: 'top' | 'middle' | 'bottom'; padding?: number;
}) {
  const clone = table.cloneNode(true) as HTMLTableElement
  const { selected, grid } = tableArea(clone, area)
  if (options.borders && options.borders !== 'none' && options.borderStyle !== 'none' && (!options.borderWidth || options.borderWidth < 0.25 || options.borderWidth > 12 || !/^#[0-9a-f]{6}$/i.test(options.borderColor || ''))) throw new Error('Controlla colore e spessore dei bordi.')
  if (options.padding !== undefined && (!Number.isFinite(options.padding) || options.padding < 0 || options.padding > 40)) throw new Error('Il margine interno deve essere tra 0 e 40 punti.')
  selected.forEach(({ cell, row, column }) => {
    const styles = new Map((cell.getAttribute('style') || '').split(';').filter(Boolean).map((declaration) => { const colon = declaration.indexOf(':'); return [declaration.slice(0, colon).trim(), declaration.slice(colon + 1).trim()] }))
    if (options.borders) {
      const edges = { top: row === area.top, bottom: row + (cell.rowSpan || grid.length - row) - 1 === area.bottom, left: column === area.left, right: column + cell.colSpan - 1 === area.right }
      for (const side of ['top', 'right', 'bottom', 'left'] as const) {
        const single = ['top', 'right', 'bottom', 'left'].includes(options.borders)
        if (single && options.borders !== side) continue
        const inside = !edges[side]
        const visible = single || options.borders === 'all' || (options.borders === 'outside' && edges[side]) || (options.borders === 'inside' && inside) || (options.borders === 'horizontal' && inside && (side === 'top' || side === 'bottom')) || (options.borders === 'vertical' && inside && (side === 'left' || side === 'right'))
        styles.set(`border-${side}`, visible && options.borderStyle !== 'none' ? `${options.borderWidth}pt ${options.borderStyle || 'solid'} ${options.borderColor}` : 'none')
      }
    }
    if (options.background) styles.set('background-color', options.background)
    if (options.verticalAlign) styles.set('vertical-align', options.verticalAlign)
    if (options.padding !== undefined) for (const side of ['top', 'right', 'bottom', 'left']) styles.set(`padding-${side}`, `${options.padding}pt`)
    cell.setAttribute('style', Array.from(styles, ([key, value]) => `${key}:${value}`).join(';'))
  })
  return clone
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

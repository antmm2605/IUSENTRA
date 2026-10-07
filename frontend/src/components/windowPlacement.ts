export type WindowPlacement = 'left' | 'right' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | { layout: 'group'; left: number; top: number; width: number; height: number }
export function workWindowBottom(): number {
  const dock = document.querySelector<HTMLElement>('.iu-window-dock')
  return dock ? Math.min(window.innerHeight - 4, dock.getBoundingClientRect().top - 8) : window.innerHeight - 70
}
export function windowPlacementStyle(slot: WindowPlacement | null) {
  if (!slot) return undefined
  if (typeof slot === 'object') {
    const width = document.documentElement.clientWidth, bottom = workWindowBottom()
    if (slot.width * (width - 16) < Math.min(360, width - 16) || slot.height * (bottom - 16) < Math.min(240, bottom - 16)) {
      return { position: 'fixed' as const, left: '8px', right: 'auto', top: '8px', width: (width - 16) + 'px', height: (bottom - 16) + 'px', maxWidth: 'none', maxHeight: 'none', transform: 'none', resize: 'none' as const }
    }
    return { position: 'fixed' as const, left: (8 + slot.left * (width - 16)) + 'px', right: 'auto', top: (8 + slot.top * (bottom - 16)) + 'px', width: (slot.width * (width - 16)) + 'px', height: (slot.height * (bottom - 16)) + 'px', maxWidth: 'none', maxHeight: 'none', transform: 'none', resize: 'none' as const }
  }
  const width = document.documentElement.clientWidth, height = workWindowBottom() + 70
  const half = width >= 640
  const right = half && slot.endsWith('right'), bottom = half && slot.startsWith('bottom')
  const quarter = half && slot.includes('-')
  return { position: 'fixed' as const, left: (right ? width / 2 + 4 : 8) + 'px', right: 'auto', top: (bottom ? (height - 70) / 2 + 4 : 8) + 'px', width: (half ? width / 2 - 12 : width - 16) + 'px', height: (quarter ? (height - 70) / 2 - 12 : height - 86) + 'px', maxWidth: 'none', maxHeight: 'none', transform: 'none', resize: 'none' as const }
}

export type WindowBounds = { left: number; top: number; width: number; height: number }
export type Edge = 'n' | 'e' | 's' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
export function resizeWindowBounds(start: WindowBounds, edge: Edge, dx: number, dy: number, right: number, bottom: number): WindowBounds {
  const minWidth = Math.min(360, right - 16), minHeight = Math.min(240, bottom - 16)
  let left = Math.max(8, start.left), top = Math.max(8, start.top)
  let endX = Math.min(right - 8, start.left + start.width), endY = Math.min(bottom - 8, start.top + start.height)
  if (edge.includes('w')) left = Math.max(8, Math.min(endX - minWidth, start.left + dx))
  if (edge.includes('e')) endX = Math.min(right - 8, Math.max(left + minWidth, start.left + start.width + dx))
  if (edge.includes('n')) top = Math.max(8, Math.min(endY - minHeight, start.top + dy))
  if (edge.includes('s')) endY = Math.min(bottom - 8, Math.max(top + minHeight, start.top + start.height + dy))
  return { left, top, width: endX - left, height: endY - top }
}


export type WindowArrangement = 'auto' | 'columns' | 'grid' | 'cascade'
export function arrangeWindowPlacements(count: number, mode: WindowArrangement, width: number, bottom: number): { slots: WindowPlacement[]; cascaded: boolean } {
  if (count < 1) return { slots: [], cascaded: false }
  const availableWidth = Math.max(1, width - 16), availableHeight = Math.max(1, bottom - 16)
  const maxColumns = Math.max(1, Math.floor((availableWidth + 8) / 368))
  const maxRows = Math.max(1, Math.floor((availableHeight + 8) / 248))
  const group = (left: number, top: number, w: number, h: number): WindowPlacement => ({ layout: 'group', left: left / availableWidth, top: top / availableHeight, width: w / availableWidth, height: h / availableHeight })
  const cascade = () => {
    const w = Math.min(1000, availableWidth), h = Math.min(650, availableHeight)
    const step = Math.min(28, Math.max(0, Math.min(availableWidth - w, availableHeight - h) / Math.min(count - 1 || 1, 8)))
    const minIndex = Math.min(count - 1, 8)
    return { slots: Array.from({ length: count }, (_, index) => group((minIndex - index % 9) * step, (minIndex - index % 9) * step, w, h)), cascaded: true }
  }
  if (mode === 'cascade' || count > maxColumns * maxRows) return cascade()
  if (mode === 'auto' && count === 3 && maxColumns >= 2 && maxRows >= 2) {
    const halfWidth = (availableWidth - 8) / 2, halfHeight = (availableHeight - 8) / 2
    return { slots: [group(0, 0, halfWidth, availableHeight), group(halfWidth + 8, 0, halfWidth, halfHeight), group(halfWidth + 8, halfHeight + 8, halfWidth, halfHeight)], cascaded: false }
  }
  const columns = mode === 'columns' ? Math.min(count, maxColumns) : Math.min(count, maxColumns, Math.ceil(Math.sqrt(count)))
  const rows = Math.ceil(count / columns)
  if (rows > maxRows) return cascade()
  const cellWidth = (availableWidth - 8 * (columns - 1)) / columns
  const cellHeight = (availableHeight - 8 * (rows - 1)) / rows
  return { slots: Array.from({ length: count }, (_, index) => group((index % columns) * (cellWidth + 8), Math.floor(index / columns) * (cellHeight + 8), cellWidth, cellHeight)), cascaded: false }
}

/**
 * Impaginazione "tipo Word" del corpo modificabile.
 *
 * Il documento resta un unico flusso modificabile (selezione, copia e comandi
 * di formattazione continuano a funzionare tra una pagina e l'altra), ma ogni
 * riga che finirebbe nel margine inferiore, nello spazio tra i fogli o
 * nell'intestazione con il timbro viene spinta all'inizio dell'area scrivibile
 * della pagina successiva:
 *   - il blocco intero, se è la sua prima riga a non entrare (con controllo
 *     righe orfane e titoli legati al paragrafo successivo);
 *   - altrimenti la riga, inserendo uno spaziatore tecnico largo quanto la
 *     riga, che non spezza il paragrafo (la giustificazione resta corretta).
 */

import {
  BLOCK_PUSH_ATTR,
  BLOCK_PUSH_VAR,
  clearPaginationArtifacts,
  createLineSpacer,
  isLineSpacer,
  isPageBreak,
  LINE_SPACER_VAR,
} from './editorArtifacts'
import {
  pageIndexAt,
  type PageMetrics,
  writableBottom,
  writableTop,
} from './pageGeometry'

const EPS = 0.75
const MAX_UNIT_STEPS = 400
const HEADING_TAGS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6'])
const SPLITTABLE_TAGS = new Set(['P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'BLOCKQUOTE', 'DIV', 'PRE', 'ADDRESS'])

export type PaginationOptions = {
  editor: HTMLElement
  /** Elemento che rappresenta la pila di fogli: le coordinate sono relative al suo bordo superiore. */
  stack: HTMLElement
  metrics: PageMetrics
  zoom: number
  /** Controllo righe orfane/vedove come in Word (default attivo). */
  widowControl?: boolean
}

export type PaginationResult = {
  pageCount: number
  contentBottom: number
}

type Frame = {
  stack: HTMLElement
  zoom: number
  metrics: PageMetrics
}

type LineFragment = {
  node: Text
  top: number
  bottom: number
}

type LineBand = {
  top: number
  bottom: number
  first: LineFragment
}

/** Coordinata verticale nella pila di fogli, letta sempre dal vivo: lo scorrimento può cambiare durante l'impaginazione. */
function toStackY(frame: Frame, clientY: number) {
  return (clientY - frame.stack.getBoundingClientRect().top) / frame.zoom
}

function isBlockLike(element: Element) {
  const display = window.getComputedStyle(element).display
  return display === 'block' || display === 'list-item' || display === 'table' || display === 'flex' || display === 'grid' || display === 'flow-root'
}

/** Unità impaginabili nell'ordine del documento: paragrafi, titoli, voci di elenco, tabelle. */
export function collectUnits(editor: HTMLElement): HTMLElement[] {
  const units: HTMLElement[] = []
  const visit = (parent: Element, depth: number) => {
    for (const child of Array.from(parent.children)) {
      if (!(child instanceof HTMLElement) || isLineSpacer(child)) continue
      const tag = child.tagName
      if ((tag === 'UL' || tag === 'OL') && depth < 6) {
        const items = Array.from(child.children).filter((item) => item.tagName === 'LI') as HTMLElement[]
        if (items.length) {
          items.forEach((item) => units.push(item))
          continue
        }
      }
      if ((tag === 'DIV' || tag === 'SECTION' || tag === 'ARTICLE') && depth < 6 && child.children.length
        && Array.from(child.children).every((item) => isBlockLike(item))) {
        visit(child, depth + 1)
        continue
      }
      units.push(child)
    }
  }
  visit(editor, 0)
  return units
}

const MARGIN_PUSH_TAGS = new Set(['TABLE', 'HR', 'IMG', 'FIGURE', 'PRE'])

function currentPush(element: HTMLElement) {
  return Number.parseFloat(element.style.getPropertyValue(BLOCK_PUSH_VAR) || '0') || 0
}

/**
 * Inizio effettivo del contenuto del blocco. La spinta tramite ::before non sposta
 * il bordo del blocco ma solo il suo contenuto: va sommata alla posizione misurata.
 */
function effectiveTop(element: HTMLElement, frame: Frame) {
  const measured = toStackY(frame, element.getBoundingClientRect().top)
  return MARGIN_PUSH_TAGS.has(element.tagName) ? measured : measured + currentPush(element)
}

function pushBlock(element: HTMLElement, delta: number) {
  if (delta <= EPS) return false
  const next = currentPush(element) + delta
  element.setAttribute(BLOCK_PUSH_ATTR, 'true')
  element.style.setProperty(BLOCK_PUSH_VAR, `${next.toFixed(2)}px`)
  return true
}

function clearBlockPush(element: HTMLElement) {
  if (!element.hasAttribute(BLOCK_PUSH_ATTR)) return
  element.removeAttribute(BLOCK_PUSH_ATTR)
  element.style.removeProperty(BLOCK_PUSH_VAR)
  if (!element.getAttribute('style')?.trim()) element.removeAttribute('style')
}

function textFragments(unit: HTMLElement, frame: Frame, probe: Range): LineFragment[] {
  const fragments: LineFragment[] = []
  const walker = unit.ownerDocument.createTreeWalker(unit, NodeFilter.SHOW_TEXT)
  let node = walker.nextNode() as Text | null
  while (node) {
    if (node.data.length) {
      probe.selectNodeContents(node)
      for (const rect of Array.from(probe.getClientRects())) {
        if (rect.height < 1) continue
        fragments.push({ node, top: toStackY(frame, rect.top), bottom: toStackY(frame, rect.bottom) })
      }
    }
    node = walker.nextNode() as Text | null
  }
  return fragments
}

function groupBands(fragments: LineFragment[]): LineBand[] {
  const bands: LineBand[] = []
  for (const fragment of fragments) {
    const last = bands[bands.length - 1]
    const center = (fragment.top + fragment.bottom) / 2
    if (last && center > last.top && center < last.bottom) {
      last.top = Math.min(last.top, fragment.top)
      last.bottom = Math.max(last.bottom, fragment.bottom)
      continue
    }
    bands.push({ top: fragment.top, bottom: fragment.bottom, first: fragment })
  }
  return bands
}

function charCenter(node: Text, index: number, frame: Frame, probe: Range): number | null {
  if (index < 0 || index >= node.data.length) return null
  probe.setStart(node, index)
  probe.setEnd(node, index + 1)
  const rects = Array.from(probe.getClientRects()).filter((rect) => rect.height >= 1)
  if (!rects.length) return null
  const rect = rects[rects.length - 1]
  return toStackY(frame, (rect.top + rect.bottom) / 2)
}

/** Primo carattere del nodo che appartiene alla riga che inizia a `bandTop`. */
function lineStartIndex(node: Text, bandTop: number, frame: Frame, probe: Range): number {
  const onBand = (index: number): boolean => {
    for (let step = 0; step < 4; step += 1) {
      const center = charCenter(node, index + step, frame, probe)
      if (center !== null) return center > bandTop
    }
    const back = charCenter(node, index - 1, frame, probe)
    return back !== null ? back > bandTop : false
  }
  let low = 0
  let high = node.data.length
  while (low < high) {
    const middle = Math.floor((low + high) / 2)
    if (onBand(middle)) high = middle
    else low = middle + 1
  }
  return Math.min(low, node.data.length)
}

/**
 * Inserisce lo spazio che porta la riga alla pagina successiva. È diviso in due
 * righe tecniche (fino al bordo del foglio e dal bordo all'area scrivibile) perché
 * in stampa una riga non può essere spezzata tra due pagine.
 */
function insertLineSpacer(fragment: LineFragment, index: number, bandTop: number, target: number, metrics: PageMetrics): HTMLElement {
  const doc = fragment.node.ownerDocument
  const page = pageIndexAt(bandTop, metrics)
  const sheetBottom = (page * metrics.stridePx) + metrics.heightPx
  const firstHeight = target > sheetBottom ? Math.max(0, sheetBottom - bandTop) : 0
  const secondHeight = Math.max(0, target - bandTop - firstHeight)
  const parent = fragment.node.parentNode
  const last = createLineSpacer(doc, secondHeight)
  if (!parent) return last
  let reference: Node | null
  if (index <= 0) {
    reference = fragment.node
  } else if (index >= fragment.node.data.length) {
    reference = fragment.node.nextSibling
  } else {
    reference = fragment.node.splitText(index)
  }
  if (firstHeight > 0.5) parent.insertBefore(createLineSpacer(doc, firstHeight), reference)
  parent.insertBefore(last, reference)
  return last
}

function firstTextTopAfter(spacer: HTMLElement, frame: Frame, probe: Range): number | null {
  const doc = spacer.ownerDocument
  const block = spacer.parentElement?.closest('p,h1,h2,h3,h4,h5,h6,li,blockquote,div,pre,address') || spacer.parentElement
  if (!block) return null
  const walker = doc.createTreeWalker(block, NodeFilter.SHOW_TEXT)
  walker.currentNode = spacer
  let node = walker.nextNode() as Text | null
  while (node) {
    if (node.data.length) {
      probe.setStart(node, 0)
      probe.setEnd(node, Math.min(1, node.data.length))
      const rect = Array.from(probe.getClientRects()).find((item) => item.height >= 1)
      if (rect) return toStackY(frame, rect.top)
    }
    node = walker.nextNode() as Text | null
  }
  return null
}

function targetForPosition(top: number, bottom: number, metrics: PageMetrics): number | null {
  const page = pageIndexAt(top, metrics)
  if (top < writableTop(page, metrics) - EPS) return writableTop(page, metrics)
  if (bottom > writableBottom(page, metrics) + EPS) return writableTop(page + 1, metrics)
  return null
}

type PlaceOutcome = { pushedWhole: boolean; startPage: number }

function placeUnit(unit: HTMLElement, frame: Frame, probe: Range, forcedPage: number | null, widowControl: boolean): PlaceOutcome {
  const { metrics } = frame
  let pushedWhole = false
  let lastSplitTop: number | null = null
  for (let step = 0; step < MAX_UNIT_STEPS; step += 1) {
    const rect = unit.getBoundingClientRect()
    if (!rect.height && !rect.width) break
    const top = effectiveTop(unit, frame)
    const bottom = toStackY(frame, rect.bottom)
    const page = pageIndexAt(top, metrics)

    let blockTarget: number | null = null
    if (forcedPage !== null && page < forcedPage) blockTarget = writableTop(forcedPage, metrics)
    else if (top < writableTop(page, metrics) - EPS) blockTarget = writableTop(page, metrics)
    else if (top >= writableBottom(page, metrics) - EPS) blockTarget = writableTop(page + 1, metrics)
    if (blockTarget !== null) {
      if (!pushBlock(unit, blockTarget - top)) break
      pushedWhole = true
      continue
    }

    const fragments = SPLITTABLE_TAGS.has(unit.tagName) ? textFragments(unit, frame, probe) : []
    if (!fragments.length) {
      const fitsOnPage = bottom - top <= metrics.contentHeightPx
      if (bottom > writableBottom(page, metrics) + EPS && fitsOnPage && top > writableTop(page, metrics) + EPS) {
        if (!pushBlock(unit, writableTop(page + 1, metrics) - top)) break
        pushedWhole = true
        continue
      }
      break
    }

    const bands = groupBands(fragments)
    let splitIndex = -1
    let destination = 0
    for (let index = 0; index < bands.length; index += 1) {
      const candidate = targetForPosition(bands[index].top, bands[index].bottom, metrics)
      if (candidate !== null) {
        splitIndex = index
        destination = candidate
        break
      }
    }
    if (splitIndex < 0) break

    const splitPage = pageIndexAt(bands[splitIndex].top, metrics)
    const movesForward = destination > writableBottom(splitPage, metrics)
    if (widowControl && movesForward) {
      let pageFirst = splitIndex
      while (pageFirst > 0 && pageIndexAt(bands[pageFirst - 1].top, metrics) === splitPage) pageFirst -= 1
      const linesLeft = splitIndex - pageFirst
      const linesMoving = bands.length - splitIndex
      if (pageFirst === 0) {
        if (linesLeft === 1) {
          // Riga orfana in fondo alla pagina: si sposta il paragrafo.
          splitIndex = 0
        } else if (linesMoving === 1 && linesLeft >= 2) {
          // Riga vedova in cima alla pagina successiva: la accompagna la riga precedente.
          splitIndex = linesLeft - 1 >= 2 ? splitIndex - 1 : 0
        }
      }
    }

    if (splitIndex === 0) {
      if (!pushBlock(unit, destination - top)) break
      pushedWhole = true
      continue
    }

    const band = bands[splitIndex]
    if (lastSplitTop !== null && Math.abs(lastSplitTop - band.top) < 1) break
    lastSplitTop = band.top
    const bandTarget = targetForPosition(band.top, band.bottom, metrics) ?? writableTop(pageIndexAt(band.top, metrics) + 1, metrics)
    const index = lineStartIndex(band.first.node, band.top, frame, probe)
    const spacer = insertLineSpacer(band.first, index, band.top, bandTarget, metrics)
    const measured = firstTextTopAfter(spacer, frame, probe)
    if (measured !== null) {
      const correction = bandTarget - measured
      if (Math.abs(correction) > 0.5) {
        const current = Number.parseFloat(spacer.style.getPropertyValue(LINE_SPACER_VAR) || '0') || 0
        spacer.style.setProperty(LINE_SPACER_VAR, `${Math.max(0, current + correction).toFixed(2)}px`)
      }
    }
  }
  return { pushedWhole, startPage: pageIndexAt(effectiveTop(unit, frame), metrics) }
}

const layoutCache = new WeakMap<HTMLElement, { top: number; bottom: number }>()

function unitIndexOf(node: Node, editor: HTMLElement, indexByUnit: Map<HTMLElement, number>): number {
  let element: Element | null = node.nodeType === Node.ELEMENT_NODE ? node as Element : node.parentElement
  while (element && element !== editor) {
    const index = indexByUnit.get(element as HTMLElement)
    if (index !== undefined) return index
    element = element.parentElement
  }
  return -1
}

/** Intervallo di unità toccate dalle modifiche; null se non determinabile (impaginazione completa). */
function dirtyRange(dirty: Node[] | null | undefined, editor: HTMLElement, units: HTMLElement[]): { first: number; last: number } | null {
  if (!dirty || !dirty.length) return null
  const indexByUnit = new Map(units.map((unit, index) => [unit, index]))
  let first = Number.POSITIVE_INFINITY
  let last = -1
  for (const node of dirty) {
    if (!node.isConnected || !editor.contains(node)) continue
    if (node === editor) return null
    let index = unitIndexOf(node, editor, indexByUnit)
    if (index < 0 && node.nodeType === Node.ELEMENT_NODE) {
      // Contenitore (es. elenco) che racchiude più unità.
      const inner = units.findIndex((unit) => (node as Element).contains(unit))
      if (inner < 0) return null
      const innerLast = units.length - 1 - [...units].reverse().findIndex((unit) => (node as Element).contains(unit))
      first = Math.min(first, inner)
      last = Math.max(last, innerLast)
      continue
    }
    if (index < 0) return null
    first = Math.min(first, index)
    last = Math.max(last, index)
  }
  if (last < 0) return null
  return { first, last }
}

/**
 * Impagina il corpo. Con `dirty` riparte dalle unità modificate e si ferma appena
 * le unità successive tornano nella stessa posizione della volta precedente.
 */
export function paginateEditor({ editor, stack, metrics, zoom, widowControl = true, dirty }: PaginationOptions & { dirty?: Node[] | null }): PaginationResult {
  const doc = editor.ownerDocument
  const probe = doc.createRange()
  const frame: Frame = {
    stack,
    zoom: zoom > 0 ? zoom : 1,
    metrics,
  }
  const units = collectUnits(editor)
  const range = dirtyRange(dirty, editor, units)
  const start = range ? Math.max(0, range.first - 2) : 0
  const lastDirty = range ? range.last : units.length - 1
  if (!range) {
    clearPaginationArtifacts(editor)
  }

  let forcedPage: number | null = null
  let previous: { unit: HTMLElement; page: number } | null = null
  if (start > 0) {
    const before = units[start - 1]
    const beforeTop = effectiveTop(before, frame)
    if (isPageBreak(before)) forcedPage = pageIndexAt(beforeTop, metrics) + 1
    else previous = { unit: before, page: pageIndexAt(beforeTop, metrics) }
  }

  for (let index = start; index < units.length; index += 1) {
    const unit = units[index]
    if (isPageBreak(unit)) {
      clearBlockPush(unit)
      forcedPage = pageIndexAt(effectiveTop(unit, frame), metrics) + 1
      previous = null
      continue
    }
    if (range) {
      clearPaginationArtifacts(unit)
      clearBlockPush(unit)
    }
    let outcome = placeUnit(unit, frame, probe, forcedPage, widowControl)
    forcedPage = null
    if (
      outcome.pushedWhole
      && previous
      && HEADING_TAGS.has(previous.unit.tagName)
      && previous.page < outcome.startPage
    ) {
      // Il titolo non resta da solo in fondo alla pagina: segue il suo paragrafo.
      const headingTop = effectiveTop(previous.unit, frame)
      clearPaginationArtifacts(unit)
      clearBlockPush(unit)
      if (pushBlock(previous.unit, writableTop(outcome.startPage, metrics) - headingTop)) {
        layoutCache.set(previous.unit, { top: writableTop(outcome.startPage, metrics), bottom: toStackY(frame, previous.unit.getBoundingClientRect().bottom) })
        outcome = placeUnit(unit, frame, probe, null, widowControl)
      }
    }
    const placedTop = effectiveTop(unit, frame)
    const placedBottom = toStackY(frame, unit.getBoundingClientRect().bottom)
    const cached = layoutCache.get(unit)
    layoutCache.set(unit, { top: placedTop, bottom: placedBottom })
    previous = { unit, page: outcome.startPage }
    if (range && index > lastDirty && cached && Math.abs(cached.top - placedTop) < 0.5 && Math.abs(cached.bottom - placedBottom) < 0.5) {
      // Da qui in poi il documento è identico all'impaginazione precedente.
      break
    }
  }
  probe.detach()
  const lastUnit = units[units.length - 1]
  const contentBottom = lastUnit ? Math.max(metrics.contentTopPx, toStackY(frame, lastUnit.getBoundingClientRect().bottom)) : metrics.contentTopPx
  const pageCount = Math.max(1, pageIndexAt(Math.max(0, contentBottom - EPS), metrics) + 1)
  return { pageCount, contentBottom }
}

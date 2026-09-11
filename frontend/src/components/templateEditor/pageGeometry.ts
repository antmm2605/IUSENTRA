/**
 * Geometria fisica della pagina dell'editor atti.
 *
 * La pagina è sempre A4 reale (210 × 297 mm a 96 dpi CSS): margini, righe e
 * interruzioni coincidono con la stampa e con gli export. Su schermi piccoli la
 * pagina non viene "ristretta" (il testo andrebbe a capo in modo diverso dal
 * documento vero) ma scalata, come fanno i programmi di videoscrittura.
 */

export const CSS_PX_PER_MM = 96 / 25.4
export const PAGE_GAP_PX = 32
export const STAMP_TEXT_GAP_MM = 6
export const MIN_ZOOM = 0.3
export const MAX_ZOOM = 2

export type PageOrientation = 'verticale' | 'orizzontale'

export type PageMarginsMm = {
  top: number
  right: number
  bottom: number
  left: number
}

export type PageMetrics = {
  orientation: PageOrientation
  widthPx: number
  heightPx: number
  gapPx: number
  stridePx: number
  marginTopPx: number
  marginRightPx: number
  marginBottomPx: number
  marginLeftPx: number
  /** Distanza dal bordo superiore del foglio alla prima riga di testo (margine o fine timbro). */
  contentTopPx: number
  /** Distanza dal bordo superiore del foglio all'ultima riga scrivibile. */
  contentBottomPx: number
  contentWidthPx: number
  contentHeightPx: number
}

export function mmToPx(mm: number): number {
  return (Number(mm) || 0) * CSS_PX_PER_MM
}

export function pageSizeMm(orientation: PageOrientation): { width: number; height: number } {
  return orientation === 'orizzontale' ? { width: 297, height: 210 } : { width: 210, height: 297 }
}

export function buildPageMetrics({
  orientation,
  margins,
  headerReservePx = 0,
  gapPx = PAGE_GAP_PX,
}: {
  orientation: PageOrientation
  margins: PageMarginsMm
  /** Altezza del timbro ripetuto nell'intestazione, misurata dal margine superiore. */
  headerReservePx?: number
  gapPx?: number
}): PageMetrics {
  const size = pageSizeMm(orientation)
  const widthPx = mmToPx(size.width)
  const heightPx = mmToPx(size.height)
  const marginTopPx = mmToPx(margins.top)
  const marginRightPx = mmToPx(margins.right)
  const marginBottomPx = mmToPx(margins.bottom)
  const marginLeftPx = mmToPx(margins.left)
  const reserve = Math.max(0, headerReservePx)
  const minimumContentHeight = mmToPx(40)
  const contentBottomPx = heightPx - marginBottomPx
  const requestedTop = marginTopPx + (reserve > 0 ? reserve + mmToPx(STAMP_TEXT_GAP_MM) : 0)
  const contentTopPx = Math.min(requestedTop, contentBottomPx - minimumContentHeight)
  return {
    orientation,
    widthPx,
    heightPx,
    gapPx,
    stridePx: heightPx + gapPx,
    marginTopPx,
    marginRightPx,
    marginBottomPx,
    marginLeftPx,
    contentTopPx,
    contentBottomPx,
    contentWidthPx: Math.max(mmToPx(40), widthPx - marginLeftPx - marginRightPx),
    contentHeightPx: Math.max(minimumContentHeight, contentBottomPx - contentTopPx),
  }
}

/** Pagina (da 0) che contiene la coordinata verticale `stackY` della pila di fogli. */
export function pageIndexAt(stackY: number, metrics: PageMetrics): number {
  return Math.max(0, Math.floor(Math.max(0, stackY) / metrics.stridePx))
}

export function writableTop(pageIndex: number, metrics: PageMetrics): number {
  return (pageIndex * metrics.stridePx) + metrics.contentTopPx
}

export function writableBottom(pageIndex: number, metrics: PageMetrics): number {
  return (pageIndex * metrics.stridePx) + metrics.contentBottomPx
}

export function stackHeight(pageCount: number, metrics: PageMetrics): number {
  const pages = Math.max(1, Math.round(pageCount))
  return (pages * metrics.heightPx) + ((pages - 1) * metrics.gapPx)
}

/** Numero di pagine necessarie perché l'ultima riga (coordinata della pila) resti nell'area scrivibile. */
export function pageCountForContentEnd(stackY: number, metrics: PageMetrics): number {
  const index = pageIndexAt(Math.max(0, stackY - 0.5), metrics)
  return index + 1
}

/** Zoom che fa entrare la pagina nella larghezza disponibile (con un piccolo respiro laterale). */
export function fitWidthZoom(availableWidthPx: number, metrics: PageMetrics, gutterPx = 16): number {
  const usable = Math.max(120, availableWidthPx - (gutterPx * 2))
  return clampZoom(usable / metrics.widthPx)
}

export function clampZoom(value: number): number {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 1
  return Math.round(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, numeric)) * 100) / 100
}

export function countWords(text: string): number {
  const matches = String(text || '').replace(/\u00a0/g, ' ').match(/[\p{L}\p{N}][\p{L}\p{N}'\u2019./-]*/gu)
  return matches ? matches.length : 0
}

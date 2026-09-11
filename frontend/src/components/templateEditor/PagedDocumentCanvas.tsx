import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type HTMLAttributes, type MouseEvent as ReactMouseEvent, type ReactNode, type RefObject } from 'react'
import { flushSync } from 'react-dom'
import { Maximize2, Minus, Plus } from 'lucide-react'
import { clearPaginationArtifacts, isLineSpacer, PAGE_BREAK_HTML } from './editorArtifacts'
import {
  buildPageMetrics,
  clampZoom,
  countWords,
  fitWidthZoom,
  mmToPx,
  PAGE_GAP_PX,
  pageIndexAt,
  type PageMarginsMm,
  type PageOrientation,
  stackHeight,
  writableBottom,
  writableTop,
} from './pageGeometry'
import { paginateEditor } from './pagination'
import { usePinchZoom } from './usePinchZoom'
import { plainTextToParagraphs, sanitizePastedHtml } from './pasteSanitizer'

const EDITABLE_PROPS = {
  ['content' + 'Editable']: true,
  suppressContentEditableWarning: true,
} as Partial<HTMLAttributes<HTMLDivElement>>

const MAX_RENDERED_PAGES = 400
const ZOOM_STEPS = [0.5, 0.67, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2]
const MIDDLE_STAMP_TOP_MM = 128

export type StampLine = { text: string; bold?: boolean }

export type DocumentLayoutInfo = {
  pageCount: number
  currentPage: number
  words: number
  characters: number
  zoom: number
}

type ZoomMode = { kind: 'auto' } | { kind: 'fit' } | { kind: 'manual'; value: number }

type Props = {
  editorRef: RefObject<HTMLDivElement | null>
  stampRef: RefObject<HTMLDivElement | null>
  paperClassName: string
  orientation: PageOrientation
  margins: PageMarginsMm
  stampLines: StampLine[]
  stampPosition: string
  stampOffsetMm: number
  stampFontFamily: string
  stampFontSizePt: number
  stampLineHeight: number
  /** Cambia quando cambiano font, corpo o interlinea: forza una nuova impaginazione. */
  layoutKey: string
  placeholder: string
  onEditorInput: () => void
  onSelectionSave: () => void
  onEditorKeyDown?: (event: KeyboardEvent) => void
  onLayout?: (info: DocumentLayoutInfo) => void
  statusExtra?: ReactNode
}

function stampPositionToken(value: string) {
  const clean = String(value || 'top-center').toLowerCase().replace(/_/g, '-')
  return ['top-left', 'top-center', 'top-right', 'middle-left', 'middle-right'].includes(clean) ? clean : 'top-center'
}

function nearestZoomStep(current: number, direction: 1 | -1) {
  if (direction > 0) return ZOOM_STEPS.find((step) => step > current + 0.001) ?? ZOOM_STEPS[ZOOM_STEPS.length - 1]
  return [...ZOOM_STEPS].reverse().find((step) => step < current - 0.001) ?? ZOOM_STEPS[0]
}

function nodeBeforeCaret(range: Range): Node | null {
  const { startContainer, startOffset } = range
  if (startContainer.nodeType === Node.TEXT_NODE) {
    if (startOffset > 0) return null
    let previous = startContainer.previousSibling
    while (previous && previous.nodeType === Node.TEXT_NODE && !(previous as Text).data.length) previous = previous.previousSibling
    return previous
  }
  return startContainer.childNodes[startOffset - 1] || null
}

function nodeAfterCaret(range: Range): Node | null {
  const { endContainer, endOffset } = range
  if (endContainer.nodeType === Node.TEXT_NODE) {
    if (endOffset < (endContainer as Text).data.length) return null
    let next = endContainer.nextSibling
    while (next && next.nodeType === Node.TEXT_NODE && !(next as Text).data.length) next = next.nextSibling
    return next
  }
  return endContainer.childNodes[endOffset] || null
}

export function PagedDocumentCanvas({
  editorRef,
  stampRef,
  paperClassName,
  orientation,
  margins,
  stampLines,
  stampPosition,
  stampOffsetMm,
  stampFontFamily,
  stampFontSizePt,
  stampLineHeight,
  layoutKey,
  placeholder,
  onEditorInput,
  onSelectionSave,
  onEditorKeyDown,
  onLayout,
  statusExtra,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<HTMLDivElement>(null)
  const stackRef = useRef<HTMLDivElement>(null)
  const frameRequestRef = useRef(0)
  const composingRef = useRef(false)
  const printingRef = useRef(false)
  const observerRef = useRef<MutationObserver | null>(null)
  const dirtyNodesRef = useRef<Node[]>([])
  const fullPassRef = useRef(true)
  const [pageCount, setPageCount] = useState(1)
  const [currentPage, setCurrentPage] = useState(1)
  const [headerReservePx, setHeaderReservePx] = useState(0)
  const [availableWidth, setAvailableWidth] = useState(0)
  const [zoomMode, setZoomMode] = useState<ZoomMode>({ kind: 'auto' })
  const [printing, setPrinting] = useState(false)
  const [textStats, setTextStats] = useState({ words: 0, characters: 0 })
  const position = stampPositionToken(stampPosition)
  const stampAtTop = position.startsWith('top-')
  const hasStamp = stampLines.length > 0

  const metrics = useMemo(() => buildPageMetrics({
    orientation,
    margins,
    headerReservePx: hasStamp && stampAtTop ? headerReservePx : 0,
    gapPx: printing ? 0 : PAGE_GAP_PX,
  }), [orientation, margins.top, margins.right, margins.bottom, margins.left, headerReservePx, hasStamp, stampAtTop, printing])

  const fitZoom = availableWidth > 0 ? fitWidthZoom(availableWidth, metrics) : 1
  const zoom = printing ? 1 : zoomMode.kind === 'manual'
    ? clampZoom(zoomMode.value)
    : zoomMode.kind === 'fit'
      ? fitZoom
      : Math.min(1, fitZoom)
  const zoomRef = useRef(zoom)
  zoomRef.current = zoom
  const metricsRef = useRef(metrics)
  metricsRef.current = metrics

  const renderedPages = Math.min(MAX_RENDERED_PAGES, Math.max(1, pageCount))
  const pages = useMemo(() => Array.from({ length: renderedPages }, (_, index) => index), [renderedPages])

  const runPagination = useCallback((overrideMetrics?: ReturnType<typeof buildPageMetrics>, overrideZoom?: number) => {
    const editor = editorRef.current
    const stack = stackRef.current
    if (!editor || !stack) return 1
    const activeMetrics = overrideMetrics || metricsRef.current
    const dirty = fullPassRef.current || overrideMetrics ? null : dirtyNodesRef.current
    fullPassRef.current = false
    dirtyNodesRef.current = []
    const result = paginateEditor({ editor, stack, metrics: activeMetrics, zoom: overrideZoom ?? zoomRef.current, dirty })
    observerRef.current?.takeRecords()
    const count = Math.min(MAX_RENDERED_PAGES, result.pageCount)
    stack.style.setProperty('--iu-ted-editor-min-h', `${Math.max(0, writableBottom(count - 1, activeMetrics) - activeMetrics.contentTopPx)}px`)
    stack.style.setProperty('--iu-ted-stack-h', `${stackHeight(count, activeMetrics)}px`)
    return count
  }, [editorRef])

  const schedulePagination = useCallback((full = true) => {
    if (full) fullPassRef.current = true
    if (printingRef.current) return
    window.cancelAnimationFrame(frameRequestRef.current)
    frameRequestRef.current = window.requestAnimationFrame(() => {
      if (composingRef.current || printingRef.current) return
      const count = runPagination()
      setPageCount((current) => (current === count ? current : count))
      const text = (editorRef.current?.textContent || '').replace(/\u00a0/g, ' ')
      setTextStats({ words: countWords(text), characters: text.replace(/\s/g, '').length })
    })
  }, [editorRef, runPagination])

  // Variabili geometriche della pila di fogli (nessuno stile inline nel markup).
  useLayoutEffect(() => {
    const stack = stackRef.current
    const frame = frameRef.current
    if (!stack || !frame) return
    const variables: Record<string, string> = {
      '--iu-ted-page-w': `${metrics.widthPx}px`,
      '--iu-ted-page-h': `${metrics.heightPx}px`,
      '--iu-ted-gap': `${metrics.gapPx}px`,
      '--iu-ted-stride': `${metrics.stridePx}px`,
      '--iu-ted-margin-top': `${metrics.marginTopPx}px`,
      '--iu-ted-margin-right': `${metrics.marginRightPx}px`,
      '--iu-ted-margin-bottom': `${metrics.marginBottomPx}px`,
      '--iu-ted-margin-left': `${metrics.marginLeftPx}px`,
      '--iu-ted-content-top': `${metrics.contentTopPx}px`,
      '--iu-ted-content-w': `${metrics.contentWidthPx}px`,
      '--iu-ted-content-h': `${metrics.contentHeightPx}px`,
      '--iu-ted-stack-h': `${stackHeight(renderedPages, metrics)}px`,
      '--iu-ted-zoom': String(zoom),
      '--iu-ted-stamp-top': `${mmToPx((stampAtTop ? 0 : MIDDLE_STAMP_TOP_MM) + stampOffsetMm) + (stampAtTop ? metrics.marginTopPx : 0)}px`,
      '--iu-ted-stamp-font-family': stampFontFamily,
      '--iu-ted-stamp-font-size': `${stampFontSizePt}pt`,
      '--iu-ted-stamp-line-height': String(stampLineHeight),
    }
    Object.entries(variables).forEach(([name, value]) => stack.style.setProperty(name, value))
    frame.style.setProperty('--iu-ted-frame-w', `${metrics.widthPx * zoom}px`)
    frame.style.setProperty('--iu-ted-frame-h', `${stackHeight(renderedPages, metrics) * zoom}px`)
    stack.querySelectorAll<HTMLElement>('[data-iu-sheet-index]').forEach((element) => {
      element.style.setProperty('--iu-ted-sheet-index', element.dataset.iuSheetIndex || '0')
    })
  }, [metrics, renderedPages, zoom, stampAtTop, stampOffsetMm, stampFontFamily, stampFontSizePt, stampLineHeight])

  // Altezza reale del timbro: definisce dove inizia il testo su ogni pagina.
  useLayoutEffect(() => {
    const stamp = stampRef.current
    if (!stamp || !hasStamp) {
      setHeaderReservePx(0)
      return undefined
    }
    const measure = () => {
      const offset = mmToPx(stampOffsetMm)
      const height = stamp.offsetHeight
      const reserve = Math.max(0, height + offset)
      setHeaderReservePx((current) => (Math.abs(current - reserve) < 0.5 ? current : reserve))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(stamp)
    return () => observer.disconnect()
  }, [stampRef, hasStamp, stampOffsetMm, stampFontFamily, stampFontSizePt, stampLineHeight, stampLines.length])

  // Larghezza disponibile per lo zoom "adatta alla pagina".
  useLayoutEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return undefined
    const measure = () => setAvailableWidth(viewport.clientWidth)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(viewport)
    return () => observer.disconnect()
  }, [])

  // Osservatori: ogni modifica del testo reimpagina (fuori dalla composizione IME).
  useEffect(() => {
    const editor = editorRef.current
    if (!editor) return undefined
    const observer = new MutationObserver((records) => {
      const dirty = dirtyNodesRef.current
      for (const record of records) {
        if (record.type === 'childList') {
          if (record.target !== editor) dirty.push(record.target)
          record.addedNodes.forEach((node) => dirty.push(node))
          if (record.previousSibling) dirty.push(record.previousSibling)
          if (record.nextSibling) dirty.push(record.nextSibling)
          if (record.target === editor && !record.previousSibling && !record.nextSibling && !record.addedNodes.length) fullPassRef.current = true
        } else {
          dirty.push(record.target)
        }
      }
      if (dirty.length > 2000) fullPassRef.current = true
      schedulePagination(false)
    })
    observer.observe(editor, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['style', 'class', 'align'] })
    observerRef.current = observer
    const onCompositionStart = () => { composingRef.current = true }
    const onCompositionEnd = () => {
      composingRef.current = false
      schedulePagination(false)
    }
    editor.addEventListener('compositionstart', onCompositionStart)
    editor.addEventListener('compositionend', onCompositionEnd)
    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts
    const onFontsReady = () => schedulePagination(true)
    fonts?.ready.then(onFontsReady).catch(() => undefined)
    fonts?.addEventListener?.('loadingdone', onFontsReady)
    schedulePagination(true)
    return () => {
      observer.disconnect()
      observerRef.current = null
      editor.removeEventListener('compositionstart', onCompositionStart)
      editor.removeEventListener('compositionend', onCompositionEnd)
      fonts?.removeEventListener?.('loadingdone', onFontsReady)
      window.cancelAnimationFrame(frameRequestRef.current)
    }
  }, [editorRef, schedulePagination])

  useEffect(() => {
    schedulePagination(true)
  }, [metrics, layoutKey, schedulePagination])

  // Pagina corrente: quella del cursore, altrimenti quella al centro della vista.
  const updateCurrentPage = useCallback(() => {
    const editor = editorRef.current
    const stack = stackRef.current
    const viewport = viewportRef.current
    if (!editor || !stack || !viewport) return
    const stackTop = stack.getBoundingClientRect().top
    const selection = document.getSelection()
    let clientY: number | null = null
    if (selection && selection.rangeCount && editor.contains(selection.anchorNode)) {
      const range = selection.getRangeAt(0).cloneRange()
      range.collapse(false)
      const rect = Array.from(range.getClientRects()).pop() || (range.startContainer.nodeType === Node.ELEMENT_NODE
        ? (range.startContainer as Element).getBoundingClientRect()
        : range.startContainer.parentElement?.getBoundingClientRect())
      if (rect && rect.height) clientY = rect.top
    }
    if (clientY === null) {
      const viewRect = viewport.getBoundingClientRect()
      clientY = viewRect.top + (viewRect.height / 2)
    }
    const page = pageIndexAt((clientY - stackTop) / zoomRef.current, metricsRef.current) + 1
    setCurrentPage(Math.max(1, Math.min(page, renderedPages)))
  }, [editorRef, renderedPages])

  useEffect(() => {
    let frame = 0
    const onSelection = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        updateCurrentPage()
        const editor = editorRef.current
        const viewport = viewportRef.current
        const selection = document.getSelection()
        if (!editor || !viewport || !selection || !selection.rangeCount || !editor.contains(selection.focusNode)) return
        // Tiene il cursore visibile sopra la tastiera virtuale.
        const range = selection.getRangeAt(0).cloneRange()
        range.collapse(false)
        const rect = Array.from(range.getClientRects()).pop()
        if (!rect) return
        const visual = window.visualViewport
        const visibleBottom = Math.min(viewport.getBoundingClientRect().bottom, visual ? visual.offsetTop + visual.height : window.innerHeight) - 24
        const visibleTop = viewport.getBoundingClientRect().top + 8
        if (rect.bottom > visibleBottom) viewport.scrollTop += rect.bottom - visibleBottom
        else if (rect.top < visibleTop) viewport.scrollTop -= visibleTop - rect.top
      })
    }
    document.addEventListener('selectionchange', onSelection)
    return () => {
      document.removeEventListener('selectionchange', onSelection)
      window.cancelAnimationFrame(frame)
    }
  }, [editorRef, updateCurrentPage])

  useEffect(() => {
    onLayout?.({ pageCount, currentPage, words: textStats.words, characters: textStats.characters, zoom })
  }, [pageCount, currentPage, textStats, zoom, onLayout])

  // Tastiera: cancellazione attorno agli spaziatori, interruzione di pagina, incolla pulito.
  useEffect(() => {
    const editor = editorRef.current
    if (!editor) return undefined
    const onBeforeInput = (event: InputEvent) => {
      if (event.isComposing) return
      const selection = document.getSelection()
      if (!selection || !selection.rangeCount) return
      const range = selection.getRangeAt(0)
      if (!range.collapsed) return
      if (event.inputType === 'deleteContentBackward') {
        const before = nodeBeforeCaret(range)
        if (before && isLineSpacer(before)) {
          event.preventDefault()
          let first: Node = before
          while (first.previousSibling && isLineSpacer(first.previousSibling)) first = first.previousSibling
          const caret = document.createRange()
          caret.setStartBefore(first)
          caret.collapse(true)
          selection.removeAllRanges()
          selection.addRange(caret)
          document.execCommand('delete', false)
        }
      } else if (event.inputType === 'deleteContentForward') {
        const after = nodeAfterCaret(range)
        if (after && isLineSpacer(after)) {
          event.preventDefault()
          let lastSpacer: Node = after
          while (lastSpacer.nextSibling && isLineSpacer(lastSpacer.nextSibling)) lastSpacer = lastSpacer.nextSibling
          const caret = document.createRange()
          caret.setStartAfter(lastSpacer)
          caret.collapse(true)
          selection.removeAllRanges()
          selection.addRange(caret)
          document.execCommand('forwardDelete', false)
        }
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault()
        document.execCommand('insertHTML', false, PAGE_BREAK_HTML)
        return
      }
      onEditorKeyDown?.(event)
    }
    const onPaste = (event: ClipboardEvent) => {
      const data = event.clipboardData
      if (!data) return
      const html = data.getData('text/html')
      const text = data.getData('text/plain')
      if (!html && !text) return
      event.preventDefault()
      const clean = html ? sanitizePastedHtml(html) : plainTextToParagraphs(text)
      if (clean) document.execCommand('insertHTML', false, clean)
    }
    const onCopy = (event: ClipboardEvent) => {
      const selection = document.getSelection()
      if (!selection || !selection.rangeCount || selection.isCollapsed || !event.clipboardData) return
      const container = document.createElement('div')
      container.appendChild(selection.getRangeAt(0).cloneContents())
      clearPaginationArtifacts(container)
      event.clipboardData.setData('text/html', container.innerHTML)
      event.clipboardData.setData('text/plain', selection.toString())
      event.preventDefault()
      if (event.type === 'cut') document.execCommand('delete', false)
    }
    const onFocus = () => {
      try {
        document.execCommand('defaultParagraphSeparator', false, 'p')
      } catch {
        // Browser senza supporto: il separatore resta quello predefinito.
      }
    }
    editor.addEventListener('beforeinput', onBeforeInput)
    editor.addEventListener('keydown', onKeyDown)
    editor.addEventListener('paste', onPaste)
    editor.addEventListener('copy', onCopy)
    editor.addEventListener('cut', onCopy)
    editor.addEventListener('focus', onFocus)
    return () => {
      editor.removeEventListener('beforeinput', onBeforeInput)
      editor.removeEventListener('keydown', onKeyDown)
      editor.removeEventListener('paste', onPaste)
      editor.removeEventListener('copy', onCopy)
      editor.removeEventListener('cut', onCopy)
      editor.removeEventListener('focus', onFocus)
    }
  }, [editorRef, onEditorKeyDown])

  // Stampa: pagine a contatto (nessuno spazio tra i fogli), zoom reale e formato @page coerente.
  useEffect(() => {
    let pageStyle: HTMLStyleElement | null = null
    const beforePrint = () => {
      printingRef.current = true
      window.cancelAnimationFrame(frameRequestRef.current)
      flushSync(() => setPrinting(true))
      fullPassRef.current = true
      const count = runPagination(metricsRef.current, 1)
      flushSync(() => setPageCount(count))
      pageStyle?.remove()
      pageStyle = document.createElement('style')
      pageStyle.setAttribute('data-iu-ted-print', 'true')
      pageStyle.textContent = `@page { size: A4 ${metricsRef.current.orientation === 'orizzontale' ? 'landscape' : 'portrait'}; margin: 0; }`
      document.head.appendChild(pageStyle)
      document.body.classList.add('iu-ted-printing')
    }
    const afterPrint = () => {
      printingRef.current = false
      pageStyle?.remove()
      pageStyle = null
      document.body.classList.remove('iu-ted-printing')
      setPrinting(false)
      schedulePagination(true)
    }
    window.addEventListener('beforeprint', beforePrint)
    window.addEventListener('afterprint', afterPrint)
    return () => {
      window.removeEventListener('beforeprint', beforePrint)
      window.removeEventListener('afterprint', afterPrint)
      pageStyle?.remove()
    }
  }, [runPagination, schedulePagination])

  // Clic su margini, intestazione o spazio tra i fogli: cursore nella riga più vicina.
  const placeCaretFromPage = (event: ReactMouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null
    const editor = editorRef.current
    const stack = stackRef.current
    if (!target || !editor || !stack) return
    if (editor.contains(target) || stampRef.current?.contains(target) || target.closest('button,a,input,select,textarea')) return
    event.preventDefault()
    const stackRect = stack.getBoundingClientRect()
    const scale = zoomRef.current
    const activeMetrics = metricsRef.current
    const stackY = (event.clientY - stackRect.top) / scale
    const page = pageIndexAt(stackY, activeMetrics)
    const clampedY = Math.min(Math.max(stackY, writableTop(page, activeMetrics) + 4), writableBottom(page, activeMetrics) - 4)
    const stackX = (event.clientX - stackRect.left) / scale
    const clampedX = Math.min(Math.max(stackX, activeMetrics.marginLeftPx + 1), activeMetrics.widthPx - activeMetrics.marginRightPx - 1)
    const clientX = stackRect.left + (clampedX * scale)
    const clientY = stackRect.top + (clampedY * scale)
    let range: Range | null = null
    if (typeof document.caretRangeFromPoint === 'function') {
      range = document.caretRangeFromPoint(clientX, clientY)
    } else if (typeof document.caretPositionFromPoint === 'function') {
      const caret = document.caretPositionFromPoint(clientX, clientY)
      if (caret) {
        range = document.createRange()
        range.setStart(caret.offsetNode, caret.offset)
        range.collapse(true)
      }
    }
    editor.focus({ preventScroll: true })
    const selection = document.getSelection()
    if (!selection) return
    if (!range || !editor.contains(range.startContainer)) {
      range = document.createRange()
      range.selectNodeContents(editor)
      range.collapse(stackY < activeMetrics.contentTopPx)
    }
    selection.removeAllRanges()
    selection.addRange(range)
    onSelectionSave()
  }

  const changeZoom = (direction: 1 | -1) => setZoomMode({ kind: 'manual', value: nearestZoomStep(zoom, direction) })
  const setManualZoom = useCallback((value: number) => setZoomMode({ kind: 'manual', value }), [])
  usePinchZoom({ viewportRef, frameRef, zoomRef, onZoom: setManualZoom })

  return (
    <div className="iu-ted-canvas">
      <div ref={viewportRef} className="iu-ted-viewport" data-testid="template-editor-viewport" aria-description="Sul telefono avvicina o allontana due dita sul foglio per ingrandire o ridurre">
        <div ref={frameRef} className="iu-ted-frame">
          <div
            ref={stackRef}
            className={`iu-ted-stack ${paperClassName} iu-ted-stack--stamp-${position}`}
            data-page-count={renderedPages}
            data-testid="template-editor-pages"
            onMouseDown={placeCaretFromPage}
          >
            {pages.map((index) => (
              <section className="iu-ted-sheet" data-iu-sheet-index={index} aria-hidden="true" key={`sheet-${index}`}>
                <span className="iu-ted-sheet__guide" />
                <span className="iu-ted-sheet__label">Pagina {index + 1} di {renderedPages}</span>
              </section>
            ))}
            {hasStamp ? pages.map((index) => (
              index === 0 ? (
                <div
                  ref={stampRef}
                  className="iu-ted-stamp"
                  data-iu-sheet-index={0}
                  {...EDITABLE_PROPS}
                  spellCheck={false}
                  tabIndex={0}
                  aria-label="Timbro studio riportato su ogni pagina"
                  onBlur={onSelectionSave}
                  onKeyUp={onSelectionSave}
                  onMouseUp={onSelectionSave}
                  key="stamp-0"
                >
                  {stampLines.map((line, lineIndex) => (
                    <span className={line.bold ? 'is-bold' : ''} key={`stamp-line-${lineIndex}`}>{line.text}</span>
                  ))}
                </div>
              ) : (
                <div className="iu-ted-stamp iu-ted-stamp--copy" data-iu-sheet-index={index} aria-hidden="true" key={`stamp-${index}`}>
                  {stampLines.map((line, lineIndex) => (
                    <span className={line.bold ? 'is-bold' : ''} key={`stamp-${index}-line-${lineIndex}`}>{line.text}</span>
                  ))}
                </div>
              )
            )) : null}
            <div
              ref={editorRef}
              className="iu-ted-body"
              {...EDITABLE_PROPS}
              spellCheck
              data-placeholder={placeholder}
              data-testid="professional-template-editor"
              role="textbox"
              aria-multiline="true"
              aria-label="Corpo documento modificabile"
              onInput={onEditorInput}
              onKeyUp={onSelectionSave}
              onMouseUp={onSelectionSave}
              onBlur={onSelectionSave}
              onFocus={onSelectionSave}
            />
          </div>
        </div>
      </div>
      <footer className="iu-ted-statusbar" aria-label="Stato documento">
        <span className="iu-ted-statusbar__item" data-testid="template-editor-page-status">Pagina {currentPage} di {renderedPages}</span>
        <span className="iu-ted-statusbar__item iu-ted-statusbar__item--secondary">{textStats.words} parole</span>
        <span className="iu-ted-statusbar__item iu-ted-statusbar__item--secondary iu-ted-statusbar__item--wide">{textStats.characters} caratteri</span>
        <span className="iu-ted-statusbar__item iu-ted-statusbar__item--secondary iu-ted-statusbar__item--wide">A4 {orientation === 'orizzontale' ? 'orizzontale' : 'verticale'}</span>
        {statusExtra}
        <span className="iu-ted-statusbar__spacer" />
        <div className="iu-ted-zoom" role="group" aria-label="Zoom pagina">
          <button type="button" title="Riduci zoom" aria-label="Riduci zoom" onMouseDown={(event) => event.preventDefault()} onClick={() => changeZoom(-1)}>
            <Minus size={14} aria-hidden="true" />
          </button>
          <button type="button" className="iu-ted-zoom__value" title="Zoom al 100%" aria-label={`Zoom ${Math.round(zoom * 100)}%, riporta al 100%`} onMouseDown={(event) => event.preventDefault()} onClick={() => setZoomMode({ kind: 'manual', value: 1 })}>
            {Math.round(zoom * 100)}%
          </button>
          <button type="button" title="Aumenta zoom" aria-label="Aumenta zoom" onMouseDown={(event) => event.preventDefault()} onClick={() => changeZoom(1)}>
            <Plus size={14} aria-hidden="true" />
          </button>
          <button type="button" className={zoomMode.kind === 'fit' ? 'is-active' : ''} title="Adatta alla larghezza" aria-label="Adatta alla larghezza" aria-pressed={zoomMode.kind === 'fit'} onMouseDown={(event) => event.preventDefault()} onClick={() => setZoomMode({ kind: 'fit' })}>
            <Maximize2 size={14} aria-hidden="true" />
          </button>
        </div>
      </footer>
    </div>
  )
}

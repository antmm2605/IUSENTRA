import { useCallback, useEffect, useState, type RefObject } from 'react'

export type BlockFormat = 'p' | 'h1' | 'h2' | 'h3' | 'blockquote'

export type SelectionFormats = {
  bold: boolean
  italic: boolean
  underline: boolean
  strikeThrough: boolean
  unorderedList: boolean
  orderedList: boolean
  align: 'left' | 'center' | 'right' | 'justify' | ''
  block: BlockFormat
  fontSizePt: number
  fontFamily: string
}

const EMPTY_FORMATS: SelectionFormats = {
  bold: false,
  italic: false,
  underline: false,
  strikeThrough: false,
  unorderedList: false,
  orderedList: false,
  align: '',
  block: 'p',
  fontSizePt: 0,
  fontFamily: '',
}

function commandState(command: string) {
  try {
    return document.queryCommandState(command)
  } catch {
    return false
  }
}

function sameFormats(left: SelectionFormats, right: SelectionFormats) {
  return (Object.keys(left) as Array<keyof SelectionFormats>).every((key) => left[key] === right[key])
}

/** Stato della barra strumenti ricavato dalla posizione reale del cursore, come in Word. */
export function useSelectionFormats(editorRef: RefObject<HTMLDivElement | null>) {
  const [formats, setFormats] = useState<SelectionFormats>(EMPTY_FORMATS)

  const refresh = useCallback(() => {
    const editor = editorRef.current
    const selection = document.getSelection()
    if (!editor || !selection || !selection.rangeCount || !editor.contains(selection.anchorNode)) return
    const anchor = selection.anchorNode
    const element = anchor && anchor.nodeType === Node.ELEMENT_NODE ? anchor as Element : anchor?.parentElement
    if (!element) return
    const blockElement = element.closest('p,h1,h2,h3,h4,h5,h6,li,blockquote,div')
    const blockTag = blockElement && editor.contains(blockElement) ? blockElement.tagName.toLowerCase() : 'p'
    const quote = element.closest('blockquote')
    const block: BlockFormat = quote && editor.contains(quote)
      ? 'blockquote'
      : blockTag === 'h1' || blockTag === 'h2' || blockTag === 'h3'
        ? blockTag
        : 'p'
    const style = window.getComputedStyle(element)
    const blockStyle = blockElement ? window.getComputedStyle(blockElement) : style
    const rawAlign = blockStyle.textAlign
    const align = rawAlign === 'center' || rawAlign === 'right' || rawAlign === 'justify'
      ? rawAlign
      : rawAlign === 'left' || rawAlign === 'start'
        ? 'left'
        : ''
    const next: SelectionFormats = {
      bold: commandState('bold'),
      italic: commandState('italic'),
      underline: commandState('underline'),
      strikeThrough: commandState('strikeThrough'),
      unorderedList: commandState('insertUnorderedList'),
      orderedList: commandState('insertOrderedList'),
      align,
      block,
      fontSizePt: Math.round((Number.parseFloat(style.fontSize) || 0) * 0.75),
      fontFamily: (style.fontFamily || '').split(',')[0].replace(/["']/g, '').trim(),
    }
    setFormats((current) => (sameFormats(current, next) ? current : next))
  }, [editorRef])

  useEffect(() => {
    let frame = 0
    const onSelectionChange = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(refresh)
    }
    document.addEventListener('selectionchange', onSelectionChange)
    return () => {
      document.removeEventListener('selectionchange', onSelectionChange)
      window.cancelAnimationFrame(frame)
    }
  }, [refresh])

  return { formats, refresh }
}

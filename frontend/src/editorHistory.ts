export type EditorCaret = { start: number[]; startOffset: number; end: number[]; endOffset: number }
type Snapshot = { html: string; caret: EditorCaret | null }
type Change = { before: Snapshot; after: Snapshot; group: string; time: number }

/** Una cronologia per testo, formattazione e struttura; nessun replay del DOM nativo. */
export class EditorHistory {
  private current: Snapshot = { html: '', caret: null }
  private past: Change[] = []
  private future: Change[] = []

  reset(html: string): void {
    this.current = { html, caret: null }
    this.past = []
    this.future = []
  }

  rememberCaret(caret: EditorCaret | null): void { this.current.caret = caret }

  record(html: string, caret: EditorCaret | null, group = '', time = Date.now()): void {
    if (html === this.current.html) { this.current.caret = caret; return }
    const after = { html, caret }
    const last = this.past.at(-1)
    if (group && !this.future.length && last?.group === group && time - last.time < 1000 && last.after.html === this.current.html) {
      last.after = after
      last.time = time
    } else {
      this.past.push({ before: this.current, after, group, time })
      if (this.past.length > 30) this.past.shift()
    }
    this.current = after
    this.future = []
  }

  move(direction: 'undo' | 'redo', html: string): Snapshot | null {
    // Una mutazione non ancora registrata non deve essere sovrascritta.
    if (html !== this.current.html) return null
    const from = direction === 'undo' ? this.past : this.future
    const to = direction === 'undo' ? this.future : this.past
    const change = from.pop()
    if (!change) return null
    to.push(change)
    this.current = direction === 'undo' ? change.before : change.after
    return this.current
  }
}

export function editorCaret(root: HTMLElement): EditorCaret | null {
  const selection = window.getSelection()
  if (!selection?.rangeCount) return null
  const range = selection.getRangeAt(0)
  const path = (node: Node): number[] | null => {
    const result: number[] = []
    while (node !== root) {
      const parent = node.parentNode
      if (!parent) return null
      result.unshift(Array.prototype.indexOf.call(parent.childNodes, node))
      node = parent
    }
    return result
  }
  const start = path(range.startContainer), end = path(range.endContainer)
  return start && end ? { start, end, startOffset: range.startOffset, endOffset: range.endOffset } : null
}

export function restoreEditorCaret(root: HTMLElement, caret: EditorCaret | null): void {
  root.focus({ preventScroll: true })
  if (!caret) return
  const resolve = (path: number[]): Node | null => {
    let node: Node = root
    for (const index of path) { if (!node.childNodes[index]) return null; node = node.childNodes[index] }
    return node
  }
  const start = resolve(caret.start), end = resolve(caret.end)
  if (!start || !end) return
  const max = (node: Node) => node.nodeType === Node.TEXT_NODE ? node.textContent?.length || 0 : node.childNodes.length
  const range = document.createRange()
  range.setStart(start, Math.min(caret.startOffset, max(start)))
  range.setEnd(end, Math.min(caret.endOffset, max(end)))
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
}

/**
 * Segnalibro della selezione espresso come posizione nel testo del documento,
 * indipendente dai nodi DOM: sopravvive a ripristini dell'HTML (annulla/ripeti)
 * e a riorganizzazioni del corpo.
 */

import { isLineSpacer } from './editorArtifacts'

export type TextBookmark = {
  start: number
  end: number
}

type Position = { node: Node; offset: number }

function walkUnits(root: Node, visit: (node: Node, length: number) => boolean) {
  const doc = root.ownerDocument || document
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      if (isLineSpacer(node)) return NodeFilter.FILTER_REJECT
      if (node.nodeType === Node.TEXT_NODE) return NodeFilter.FILTER_ACCEPT
      return (node as Element).tagName === 'BR' ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP
    },
  })
  let node = walker.nextNode()
  while (node) {
    const length = node.nodeType === Node.TEXT_NODE ? (node as Text).data.length : 1
    if (visit(node, length)) return
    node = walker.nextNode()
  }
}

function offsetOf(root: Node, target: Node, targetOffset: number): number {
  let total = 0
  let result = -1
  if (target.nodeType === Node.TEXT_NODE) {
    walkUnits(root, (node, length) => {
      if (node === target) {
        result = total + Math.min(targetOffset, length)
        return true
      }
      total += length
      return false
    })
    return result < 0 ? total : result
  }
  const boundaryChild = target.childNodes[targetOffset] || null
  walkUnits(root, (node, length) => {
    if (boundaryChild && (node === boundaryChild || boundaryChild.contains(node) || (boundaryChild.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING))) {
      result = total
      return true
    }
    if (!boundaryChild && !target.contains(node) && (target.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING)) {
      result = total
      return true
    }
    total += length
    return false
  })
  return result < 0 ? total : result
}

export function getTextBookmark(root: HTMLElement): TextBookmark | null {
  const selection = root.ownerDocument.getSelection()
  if (!selection || selection.rangeCount === 0) return null
  const range = selection.getRangeAt(0)
  if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) return null
  const start = offsetOf(root, range.startContainer, range.startOffset)
  const end = range.collapsed ? start : offsetOf(root, range.endContainer, range.endOffset)
  return { start, end: Math.max(start, end) }
}

function positionAt(root: HTMLElement, offset: number): Position {
  let total = 0
  let found: Position | null = null
  walkUnits(root, (node, length) => {
    if (offset <= total + length) {
      if (node.nodeType === Node.TEXT_NODE) {
        found = { node, offset: Math.max(0, offset - total) }
      } else {
        const parent = node.parentNode as Node
        const index = Array.prototype.indexOf.call(parent.childNodes, node)
        found = { node: parent, offset: offset - total >= 1 ? index + 1 : index }
      }
      return true
    }
    total += length
    return false
  })
  if (found) return found
  const last = root.lastElementChild || root
  return { node: last, offset: last.childNodes.length }
}

export function restoreTextBookmark(root: HTMLElement, bookmark: TextBookmark | null): boolean {
  if (!bookmark) return false
  const selection = root.ownerDocument.getSelection()
  if (!selection) return false
  const start = positionAt(root, bookmark.start)
  const end = bookmark.end === bookmark.start ? start : positionAt(root, bookmark.end)
  const range = root.ownerDocument.createRange()
  try {
    range.setStart(start.node, start.offset)
    range.setEnd(end.node, end.offset)
  } catch {
    range.selectNodeContents(root)
    range.collapse(false)
  }
  selection.removeAllRanges()
  selection.addRange(range)
  return true
}

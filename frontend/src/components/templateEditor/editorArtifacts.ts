/**
 * Elementi tecnici che l'impaginazione inserisce nel corpo modificabile.
 *
 * Servono solo a spingere le righe oltre il margine inferiore e l'intestazione
 * della pagina successiva: non fanno parte del documento e vanno sempre tolti
 * prima di salvare, copiare o esportare.
 */

export const LINE_SPACER_ATTR = 'data-iu-line-spacer'
export const BLOCK_PUSH_ATTR = 'data-iu-page-push'
export const PAGE_BREAK_ATTR = 'data-iu-page-break'
export const LINE_SPACER_VAR = '--iu-ted-line-spacer'
export const BLOCK_PUSH_VAR = '--iu-ted-page-push'
const LEGACY_SPACER_ATTR = 'data-iu-page-spacer'
const LEGACY_SPACER_VAR = '--iu-template-page-spacer'

export const PAGE_BREAK_HTML = `<hr class="iu-ted-page-break" ${PAGE_BREAK_ATTR}="true">`

export function isLineSpacer(node: Node | null | undefined): boolean {
  return Boolean(node && node.nodeType === Node.ELEMENT_NODE && (node as Element).hasAttribute(LINE_SPACER_ATTR))
}

export function isPageBreak(node: Node | null | undefined): boolean {
  return Boolean(node && node.nodeType === Node.ELEMENT_NODE && (node as Element).hasAttribute(PAGE_BREAK_ATTR))
}

export function createLineSpacer(doc: Document, heightPx: number): HTMLElement {
  const spacer = doc.createElement('span')
  spacer.setAttribute(LINE_SPACER_ATTR, 'true')
  spacer.setAttribute('contenteditable', 'false')
  spacer.setAttribute('aria-hidden', 'true')
  spacer.className = 'iu-ted-line-spacer'
  spacer.style.setProperty(LINE_SPACER_VAR, `${Math.max(0, heightPx)}px`)
  return spacer
}

function removeStyleProperty(element: HTMLElement, property: string) {
  element.style.removeProperty(property)
  if (!element.getAttribute('style')?.trim()) element.removeAttribute('style')
}

/** Rimuove spaziatori e spinte di pagina da `root`; restituisce true se ha modificato il DOM. */
export function clearPaginationArtifacts(root: ParentNode, from?: Element | null): boolean {
  let changed = false
  const startNode = from || null
  const withinRange = (element: Element) => {
    if (!startNode || startNode === element) return true
    // eslint-disable-next-line no-bitwise
    return Boolean(startNode.compareDocumentPosition(element) & (Node.DOCUMENT_POSITION_FOLLOWING | Node.DOCUMENT_POSITION_CONTAINED_BY))
  }
  const parents = new Set<Node>()
  root.querySelectorAll<HTMLElement>(`[${LINE_SPACER_ATTR}]`).forEach((spacer) => {
    if (!withinRange(spacer)) return
    const parent = spacer.parentNode
    spacer.remove()
    if (parent) parents.add(parent)
    changed = true
  })
  parents.forEach((parent) => {
    if (parent.isConnected || !('isConnected' in parent)) parent.normalize()
  })
  root.querySelectorAll<HTMLElement>(`[${BLOCK_PUSH_ATTR}]`).forEach((element) => {
    if (!withinRange(element)) return
    element.removeAttribute(BLOCK_PUSH_ATTR)
    removeStyleProperty(element, BLOCK_PUSH_VAR)
    changed = true
  })
  root.querySelectorAll<HTMLElement>(`[${LEGACY_SPACER_ATTR}]`).forEach((element) => {
    element.removeAttribute(LEGACY_SPACER_ATTR)
    removeStyleProperty(element, LEGACY_SPACER_VAR)
    element.style.removeProperty('margin-top')
    element.style.removeProperty('padding-top')
    if (!element.getAttribute('style')?.trim()) element.removeAttribute('style')
    changed = true
  })
  return changed
}

function normaliseLine(value: string) {
  return value.replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase()
}

/**
 * Toglie dall'inizio del documento i blocchi che ripetono il timbro dello studio
 * (il timbro vive nell'intestazione di ogni pagina), senza perdere la formattazione
 * del resto del testo. Rimuove solo se il primo blocco non vuoto coincide con il timbro.
 */
export function stripLeadingStampBlocks(container: HTMLElement, stampLines: string[]) {
  const pending = stampLines.map(normaliseLine).filter(Boolean)
  if (!pending.length) return
  const removable: ChildNode[] = []
  let matchedAny = false
  for (const node of Array.from(container.childNodes)) {
    if (!pending.length) break
    const text = normaliseLine(node.textContent || '')
    const isElement = node.nodeType === Node.ELEMENT_NODE
    if (!text) {
      if (!isElement || (node as Element).tagName === 'P' || (node as Element).tagName === 'BR') {
        removable.push(node)
        continue
      }
      break
    }
    let rest = text
    let matched = false
    while (pending.length && rest.startsWith(pending[0])) {
      rest = rest.slice(pending[0].length).trim()
      pending.shift()
      matched = true
    }
    if (!matched || rest) break
    matchedAny = true
    removable.push(node)
  }
  if (!matchedAny) return
  removable.forEach((node) => node.parentNode?.removeChild(node))
  while (container.firstElementChild?.tagName === 'P' && !normaliseLine(container.firstElementChild.textContent || '') && !container.firstElementChild.querySelector('img')) {
    container.firstElementChild.remove()
  }
}

/** HTML del documento pronto per salvataggio ed export: niente impaginazione tecnica. */
export function cleanEditorHtml(html: string, options: { stampLines?: string[] } = {}): string {
  const container = document.createElement('div')
  container.innerHTML = String(html || '')
  clearPaginationArtifacts(container)
  container.querySelectorAll('[contenteditable]').forEach((element) => element.removeAttribute('contenteditable'))
  if (options.stampLines?.length) stripLeadingStampBlocks(container, options.stampLines)
  const cleaned = container.innerHTML.trim()
  return cleaned || '<p><br></p>'
}

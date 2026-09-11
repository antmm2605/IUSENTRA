/**
 * Pulizia del contenuto incollato (Word, pagine web, PDF) prima dell'inserimento
 * nel documento: restano struttura e formattazione di testo, spariscono classi,
 * stili di impaginazione estranei, commenti condizionali e script.
 */

const DROP_WITH_CONTENT = new Set(['SCRIPT', 'STYLE', 'META', 'LINK', 'TITLE', 'HEAD', 'NOSCRIPT', 'TEMPLATE', 'IFRAME', 'OBJECT', 'EMBED', 'SVG', 'CANVAS', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'])
const BLOCK_TAGS = new Set(['P', 'H1', 'H2', 'H3', 'H4', 'UL', 'OL', 'LI', 'BLOCKQUOTE', 'TABLE', 'THEAD', 'TBODY', 'TFOOT', 'TR', 'TD', 'TH', 'HR'])
const INLINE_TAGS = new Set(['STRONG', 'B', 'EM', 'I', 'U', 'S', 'STRIKE', 'SUB', 'SUP', 'BR', 'SPAN', 'A', 'MARK'])
const BLOCK_ALIASES: Record<string, string> = {
  DIV: 'P',
  SECTION: 'P',
  ARTICLE: 'P',
  HEADER: 'P',
  FOOTER: 'P',
  ADDRESS: 'P',
  PRE: 'P',
  H5: 'H4',
  H6: 'H4',
  DT: 'P',
  DD: 'P',
}
const INLINE_ALIASES: Record<string, string> = {
  FONT: 'SPAN',
  DEL: 'S',
  INS: 'U',
  CITE: 'EM',
  CODE: 'SPAN',
}
const BLOCK_STYLE_PROPS = ['text-align']
const INLINE_STYLE_PROPS = ['font-weight', 'font-style', 'text-decoration', 'text-decoration-line', 'color', 'background-color', 'font-size']

function allowedStyle(source: HTMLElement, props: string[]): string {
  const parts: string[] = []
  for (const prop of props) {
    const value = source.style.getPropertyValue(prop).trim()
    if (!value || /expression|url\(|var\(/i.test(value)) continue
    if (prop === 'font-size' && !/^\d+(\.\d+)?(pt|px)$/.test(value)) continue
    if (prop === 'background-color' && /^(transparent|rgba\(0, 0, 0, 0\)|white|rgb\(255, 255, 255\))$/i.test(value)) continue
    if (prop === 'color' && /^(black|windowtext|rgb\(0, 0, 0\))$/i.test(value)) continue
    if (prop === 'text-align' && !/^(left|right|center|justify)$/.test(value)) continue
    parts.push(`${prop}: ${value}`)
  }
  return parts.join('; ')
}

function cleanNode(source: Node, target: Node, doc: Document) {
  for (const child of Array.from(source.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      const text = (child.textContent || '').replace(/\r/g, '')
      if (text) target.appendChild(doc.createTextNode(text))
      continue
    }
    if (child.nodeType !== Node.ELEMENT_NODE) continue
    const element = child as HTMLElement
    const rawTag = element.tagName.toUpperCase()
    if (DROP_WITH_CONTENT.has(rawTag) || rawTag.includes(':')) {
      // Tag Office come <o:p> sono vuoti o duplicano spazi.
      if (rawTag.includes(':') && element.textContent?.trim()) cleanNode(element, target, doc)
      continue
    }
    if (rawTag === 'IMG') {
      const src = element.getAttribute('src') || ''
      if (/^data:image\/(png|jpe?g|gif|webp);base64,/i.test(src)) {
        const image = doc.createElement('img')
        image.setAttribute('src', src)
        image.setAttribute('alt', element.getAttribute('alt') || '')
        target.appendChild(image)
      }
      continue
    }
    const tag = BLOCK_ALIASES[rawTag] || INLINE_ALIASES[rawTag] || rawTag
    if (!BLOCK_TAGS.has(tag) && !INLINE_TAGS.has(tag)) {
      cleanNode(element, target, doc)
      continue
    }
    const clean = doc.createElement(tag.toLowerCase())
    if (tag === 'A') {
      const href = element.getAttribute('href') || ''
      if (/^(https?:|mailto:)/i.test(href)) clean.setAttribute('href', href)
    }
    if (tag === 'TD' || tag === 'TH') {
      const colspan = element.getAttribute('colspan')
      const rowspan = element.getAttribute('rowspan')
      if (colspan && /^\d+$/.test(colspan)) clean.setAttribute('colspan', colspan)
      if (rowspan && /^\d+$/.test(rowspan)) clean.setAttribute('rowspan', rowspan)
    }
    const style = BLOCK_TAGS.has(tag) ? allowedStyle(element, BLOCK_STYLE_PROPS) : allowedStyle(element, INLINE_STYLE_PROPS)
    const align = element.getAttribute('align')
    if (style) clean.setAttribute('style', style)
    else if (BLOCK_TAGS.has(tag) && align && /^(left|right|center|justify)$/i.test(align)) clean.setAttribute('style', `text-align: ${align.toLowerCase()}`)
    cleanNode(element, clean, doc)
    if (tag === 'SPAN' && !clean.getAttribute('style')) {
      while (clean.firstChild) target.appendChild(clean.firstChild)
      continue
    }
    target.appendChild(clean)
  }
}

/** Evita blocchi annidati impropri (es. paragrafi dentro paragrafi dopo la conversione dei div). */
function flattenNestedParagraphs(root: HTMLElement) {
  root.querySelectorAll('p p, h1 p, h2 p, h3 p, h4 p').forEach((inner) => {
    const outer = inner.parentElement
    if (!outer) return
    const fragment = inner.ownerDocument.createDocumentFragment()
    while (inner.firstChild) fragment.appendChild(inner.firstChild)
    if (inner.previousSibling) fragment.insertBefore(inner.ownerDocument.createElement('br'), fragment.firstChild)
    inner.replaceWith(fragment)
  })
  root.querySelectorAll('p').forEach((paragraph) => {
    if (!paragraph.childNodes.length) paragraph.appendChild(paragraph.ownerDocument.createElement('br'))
  })
}

export function sanitizePastedHtml(html: string): string {
  const doc = document.implementation.createHTMLDocument('incolla')
  const withoutComments = String(html || '')
    .replace(/<!--\[if[\s\S]*?<!\[endif\]-->/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
  const source = doc.createElement('div')
  source.innerHTML = withoutComments
  const target = document.createElement('div')
  cleanNode(source, target, document)
  flattenNestedParagraphs(target)
  return target.innerHTML.trim()
}

export function plainTextToParagraphs(text: string): string {
  const escape = (value: string) => value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const blocks = String(text || '').replace(/\r\n?/g, '\n').split(/\n{2,}/)
  return blocks
    .map((block) => block.split('\n').map(escape).join('<br>'))
    .map((block) => `<p>${block || '<br>'}</p>`)
    .join('')
}

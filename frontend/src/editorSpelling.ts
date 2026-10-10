export type SpellingResult = { parola: string; suggerimenti: string[] }
export type SpellingMark = { range: Range; word: string; suggestions: string[]; paragraph: Element; message?: string }

export function documentLanguageSource(root: Element) {
  const blocks = Array.from(root.querySelectorAll('p,h1,h2,h3,h4,h5,h6,li,td,blockquote,div')).filter((node) => !node.querySelector('p,h1,h2,h3,h4,h5,h6,li,td,blockquote,div'))
  if (!blocks.length) blocks.push(root)
  const parts: Array<{ paragraph: Element; start: number; text: string }> = []
  let text = ''
  for (const paragraph of blocks) {
    if (text) text += '\n\n'
    parts.push({ paragraph, start: text.length, text: paragraph.textContent || '' })
    text += paragraph.textContent || ''
  }
  return { text, parts }
}

export function grammarRanges(source: ReturnType<typeof documentLanguageSource>, results: Array<{ offset: number; length: number; messaggio: string; suggerimenti: string[] }>): SpellingMark[] {
  return results.flatMap((result) => {
    const part = source.parts.find((entry) => result.offset >= entry.start && result.offset + result.length <= entry.start + entry.text.length)
    if (!part) return []
    const walker = document.createTreeWalker(part.paragraph, NodeFilter.SHOW_TEXT)
    const start = result.offset - part.start
    const end = start + result.length
    const range = document.createRange()
    let offset = 0
    let foundStart = false
    while (walker.nextNode()) {
      const node = walker.currentNode as Text
      if (!foundStart && offset + node.length >= start) { range.setStart(node, start - offset); foundStart = true }
      if (foundStart && offset + node.length >= end) {
        range.setEnd(node, end - offset)
        return [{ range, word: range.toString(), paragraph: part.paragraph, suggestions: result.suggerimenti, message: result.messaggio }]
      }
      offset += node.length
    }
    return []
  })
}

/** Ranges only: spelling decoration never enters saved document markup. */
export function spellingRanges(paragraph: Element, results: SpellingResult[]): SpellingMark[] {
  const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT)
  const nodes: Array<{ node: Text; start: number; end: number }> = []
  let text = ''
  while (walker.nextNode()) {
    const node = walker.currentNode as Text
    nodes.push({ node, start: text.length, end: text.length + node.length })
    text += node.data
  }
  const errors = new Map(results.map((result) => [result.parola, result.suggerimenti]))
  const marks: SpellingMark[] = []
  for (const match of text.matchAll(/\p{L}+(?:['’]\p{L}+)?/gu)) {
    const suggestions = errors.get(match[0])
    if (!suggestions) continue
    const start = match.index!
    const end = start + match[0].length
    const first = nodes.find((item) => item.start <= start && item.end > start)
    const last = nodes.find((item) => item.start < end && item.end >= end)
    if (!first || !last) continue
    const range = document.createRange()
    range.setStart(first.node, start - first.start)
    range.setEnd(last.node, end - last.start)
    marks.push({ range, word: match[0], suggestions, paragraph })
  }
  return marks
}

export function showSpellingMarks(marks: SpellingMark[]): void {
  const registry = (CSS as typeof CSS & { highlights?: Map<string, unknown> }).highlights
  const HighlightClass = (window as typeof window & { Highlight?: new (...ranges: Range[]) => unknown }).Highlight
  if (!registry || !HighlightClass) return
  registry.set('iu-spelling', new HighlightClass(...marks.map((mark) => mark.range)))
}

export function clearSpellingMarks(): void {
  (CSS as typeof CSS & { highlights?: Map<string, unknown> }).highlights?.delete('iu-spelling')
}

export type TextCase = 'upper' | 'lower'

export function linkedValueFormat(value: string, format?: string): string {
  if (format !== 'cf-grouped') return value
  const compact = value.replace(/\s/g, '')
  return /^[A-Za-z0-9]{16}$/.test(compact)
    ? [compact.slice(0, 3), compact.slice(3, 6), compact.slice(6, 11), compact.slice(11)].join(' ')
    : value
}

export function linkedDateFormat(value: string, format?: string): string {
  if (!['long', 'long-padded', 'dots'].includes(format || '')) return value
  const words = dateInWords(value)
  if (format === 'long') return words
  if (format === 'long-padded') return words.replace(/^\d+/, day => day.padStart(2, '0'))
  const [day, month, year] = value.split(/[/.]/)
  return `${day.padStart(2, '0')}.${month.padStart(2, '0')}.${year}`
}

export function dateInWords(value: string): string {
  const match = value.trim().match(/^(\d{1,2})([/.])(\d{1,2})\2(\d{4})$/)
  if (!match) throw new Error('Seleziona una data nel formato gg/mm/aaaa o gg.mm.aaaa.')
  const day = Number(match[1]), month = Number(match[3]), year = Number(match[4])
  const date = new Date(Date.UTC(year, month - 1, day))
  if (year < 1000 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new Error('La data selezionata non è valida.')
  const months = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
  return `${day} ${months[month - 1]} ${year}`
}

export function changeSelectedDate(root: HTMLElement, range: Range): void {
  if (range.collapsed || !root.contains(range.startContainer) || !root.contains(range.endContainer)) throw new Error('Seleziona la data da trasformare nel documento.')
  const result = dateInWords(range.toString())
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const parts: Array<{node: Text; from: number; to: number}> = []
  const fields = new Set<HTMLElement>()
  let current = walker.nextNode()
  while (current) {
    const node = current as Text
    if (range.intersectsNode(node)) {
      const from = node === range.startContainer ? range.startOffset : 0
      const to = node === range.endContainer ? range.endOffset : node.length
      if (to > from) {
        parts.push({node, from, to})
        const field = node.parentElement?.closest<HTMLElement>('[data-iu-linked-field]')
        if (field) fields.add(field)
      }
    }
    current = walker.nextNode()
  }
  for (const field of fields) {
    const selectedLength = parts.filter(part => field.contains(part.node)).reduce((sum, part) => sum + part.to - part.from, 0)
    if (selectedLength !== field.textContent?.length) throw new Error('Seleziona interamente la data collegata.')
  }
  parts.forEach(({node, from, to}, index) => node.replaceData(from, to - from, index === 0 ? result : ''))
  fields.forEach(field => { field.dataset.iuDateFormat = 'long'; delete field.dataset.iuTextCase })
}

export function textCase(value: string, mode?: string): string {
  if (mode === 'title') {
    const connectors = new Set(['di', 'del', 'della', 'delle', 'dei', 'degli', 'da', 'a', 'al', 'alla', 'e'])
    return value.toLocaleLowerCase('it-IT').replace(/\p{L}+/gu, (word, offset: number) =>
      offset > 0 && connectors.has(word) ? word : word.charAt(0).toLocaleUpperCase('it-IT') + word.slice(1))
  }
  return mode === 'upper' ? value.toLocaleUpperCase('it-IT') : mode === 'lower' ? value.toLocaleLowerCase('it-IT') : value
}

/** Modifica i soli nodi di testo selezionati, preservando struttura e stili. */
export function changeSelectionCase(root: HTMLElement, range: Range, mode: TextCase): void {
  if (range.collapsed || !root.contains(range.startContainer) || !root.contains(range.endContainer)) throw new Error('Seleziona il testo da trasformare nel documento.')
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const parts: Array<{ node: Text; from: number; to: number }> = []
  const fields = new Set<HTMLElement>()
  let current = walker.nextNode()
  while (current) {
    const node = current as Text
    if (range.intersectsNode(node)) {
      const from = node === range.startContainer ? range.startOffset : 0
      const to = node === range.endContainer ? range.endOffset : node.length
      if (to > from) {
        const field = node.parentElement?.closest<HTMLElement>('[data-iu-linked-field]')
        if (field) {
          fields.add(field)
        }
        parts.push({ node, from, to })
      }
    }
    current = walker.nextNode()
  }
  if (!parts.length) throw new Error('Seleziona il testo da trasformare nel documento.')
  for (const field of fields) {
    const selectedLength = parts.filter(part => field.contains(part.node)).reduce((sum, part) => sum + part.to - part.from, 0)
    if (selectedLength !== field.textContent?.length) throw new Error('Seleziona interamente il campo collegato per cambiarne maiuscole e minuscole.')
  }
  for (const { node, from, to } of parts) node.replaceData(from, to - from, textCase(node.data.slice(from, to), mode))
  fields.forEach(field => { field.dataset.iuTextCase = mode })
}

type Chunk = {
  type: string
  fileName: string
  name?: string
  isEntry?: boolean
  isDynamicEntry?: boolean
  imports?: string[]
}

/** Checks actual emitted dependencies, rather than the presence of lazy() in source. */
export function assertLazyPageBoundary(bundle: Record<string, Chunk>): void {
  const entry = Object.values(bundle).find(chunk => chunk.type === 'chunk' && chunk.isEntry && chunk.name === 'app')
  if (!entry) throw new Error('Entry applicativa assente dal bundle.')
  const byFile = new Map(Object.values(bundle).map(chunk => [chunk.fileName, chunk]))
  const pending = [entry.fileName]
  const visited = new Set<string>()
  while (pending.length) {
    const file = pending.pop()!
    if (visited.has(file)) continue
    visited.add(file)
    const chunk = byFile.get(file)
    if (!chunk || chunk.type !== 'chunk') throw new Error(`Dipendenza applicativa assente: ${file}`)
    if (chunk.isDynamicEntry) throw new Error(`Modulo su richiesta incluso nel caricamento iniziale: ${file}`)
    pending.push(...(chunk.imports || []))
  }
}

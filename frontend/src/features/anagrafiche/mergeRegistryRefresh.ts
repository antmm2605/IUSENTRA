/** Three-way refresh: persisted values update clean fields; drafts survive. */
export function mergeRegistryRefresh<T extends Record<string, string | boolean>>(
  current: T, previous: T | undefined, incoming: T,
): { values: T; conflicts: string[] } {
  if (!previous) return { values: incoming, conflicts: [] }
  const values = { ...incoming }
  const conflicts: string[] = []
  for (const key of Object.keys(current)) {
    if (current[key] === previous[key]) continue
    const field = key as keyof T
    values[field] = current[field]
    if (incoming[key] !== previous[key] && incoming[key] !== current[key]) conflicts.push(key)
  }
  return { values, conflicts }
}

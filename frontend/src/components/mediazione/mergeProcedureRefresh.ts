import { mergeRegistryRefresh } from '../../features/anagrafiche/mergeRegistryRefresh'
import type { Procedure } from './types'

const serverFields = new Set(['id', 'versione', 'controlli', 'calendario', 'modulo_fonte', 'moduli_organismo'])
function canonical(value: unknown): string {
  if (value === undefined) return 'undefined'
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(',')}}`
  return JSON.stringify(value)
}
function snapshot(value: Procedure) {
  return Object.fromEntries(Object.entries(value).filter(([key]) => !serverFields.has(key)).map(([key, item]) => [key, canonical(item)]))
}
export function hasProcedureDraftChanges(current: Procedure, persisted: Procedure) {
  return canonical(snapshot(current)) !== canonical(snapshot(persisted))
}
export function mergeProcedureRefresh(current: Procedure, previous: Procedure, incoming: Procedure) {
  const before = snapshot(previous)
  const local = snapshot(current)
  const merged = mergeRegistryRefresh(local, before, snapshot(incoming))
  const values = { ...incoming }
  for (const key of Object.keys(local)) if (local[key] !== before[key]) values[key] = current[key]
  return { values, conflicts: merged.conflicts }
}

import type { SourceDocument } from './SourceDocumentModal'
import { sourceWorkDescriptor } from './sourceWorkDescriptor'
type SourceWindow = { id: string; source: SourceDocument; focusToken: number; owners: Map<string, () => void> }
let records: SourceWindow[] = []
const parentOwners = new Map<string, () => void>()
export function closeParentSourceOwner(owner: string) { const close = parentOwners.get(owner); parentOwners.delete(owner); close?.() }
let sequence = 0
const listeners = new Set<() => void>()
const publish = () => listeners.forEach(listener => listener())
export const sourceWindowsSnapshot = () => records
export function subscribeSourceWindows(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } }
export function openSourceWindow(source: SourceDocument, owner: string, onClose: () => void) {
  const nativeSource = sourceWorkDescriptor(source, window.location.origin)
  if (nativeSource) source = nativeSource
  if (window.parent !== window && nativeSource) {
    parentOwners.set(owner, onClose)
    window.parent.postMessage({ type: 'iusentra:open-source-window', source: nativeSource, owner }, window.location.origin)
    return
  }
  const existing = records.find(record => record.source.href === source.href)
  if (existing) { existing.owners.set(owner,onClose); records = records.map(record => record === existing ? { ...record, focusToken: record.focusToken + 1 } : record) }
  else records = [...records,{ id: `source-${++sequence}`, source: { ...source }, focusToken: 1, owners: new Map([[owner,onClose]]) }]
  publish()
}
export function closeSourceWindow(id: string) {
  const entry = records.find(record => record.id === id)
  records = records.filter(record => record.id !== id)
  publish()
  entry?.owners.forEach(close => close())
}
export function clearSourceWindows() { parentOwners.clear(); if (records.length) { records = []; publish() } }

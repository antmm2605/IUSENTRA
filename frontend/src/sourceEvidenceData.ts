import { formatDateTimeIt } from './formatting'
export type SourceCandidate = { href: string; label: string }

export function normalizeSourceCandidates(value: unknown): SourceCandidate[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((row: unknown) => {
    if (!row || typeof row !== 'object') return []
    const item = row as Record<string, unknown>
    const href = typeof item.href === 'string' ? item.href : ''
    const original = typeof item.label === 'string' ? item.label : 'PEC originale'
    const kinds: Record<string, string> = { accettazione: 'Ricevuta di accettazione', avvenuta_consegna: 'Ricevuta di consegna', mancata_consegna: 'Mancata consegna', non_accettazione: 'Mancata accettazione' }
    const kind = typeof item.receiptKind === 'string' ? kinds[item.receiptKind.toLowerCase().replace(/[ -]/g, '_')] : ''
    const title = kind ? `${kind} · ${original.replace(/^PEC originale - /, '')}` : original
    const received = typeof item.receivedAt === 'string' ? formatDateTimeIt(item.receivedAt) : ''
    const label = received ? `${title} · ${received}` : title
    return /^\/api\/v1\/ui\/email\/source\/[^/?]+(?:\?[^#]*)?$/.test(href) || /^\/email\/\?audit_id=/.test(href) ? [{ href, label }] : []
  })
}

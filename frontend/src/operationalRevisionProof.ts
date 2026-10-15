export type OperationalRevisions = Record<string, number>

export function normalizeRevisionContext(value: unknown): string | undefined {
  return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) ? value : undefined
}

export function changedRevisionDomains(prior: OperationalRevisions | undefined, next: OperationalRevisions, domains: string[], priorContext?: string, nextContext?: string): string[] {
  if (!prior) return []
  const ownerChanged = Boolean(normalizeRevisionContext(priorContext)
    && normalizeRevisionContext(nextContext) && priorContext !== nextContext)
  return domains.filter(domain => Number.isSafeInteger(next[domain])
    && (next[domain] !== prior[domain] || ownerChanged))
}

export function normalizeRevisionProof(value: unknown): OperationalRevisions | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const entries = Object.entries(value)
  if (!entries.length || entries.some(([, revision]) => !Number.isSafeInteger(revision) || revision < 0)) return undefined
  return Object.fromEntries(entries)
}

export function sharedRevisionProof(revisions: unknown, context: unknown): { revisions: OperationalRevisions; context: string } | undefined {
  const normalizedRevisions = normalizeRevisionProof(revisions)
  const normalizedContext = normalizeRevisionContext(context)
  return normalizedRevisions && normalizedContext ? { revisions: normalizedRevisions, context: normalizedContext } : undefined
}

export function sameRevisionProof(left: OperationalRevisions | undefined, right: OperationalRevisions | undefined): boolean {
  if (!left || !right) return false
  const keys = Object.keys(left)
  return keys.length === Object.keys(right).length && keys.every(key => left[key] === right[key])
}

export function coversRevisionProof(confirmed: OperationalRevisions | undefined, notified: OperationalRevisions | undefined, domains: string[], confirmedContext?: string, notifiedContext?: string): boolean {
  return Boolean(normalizeRevisionContext(confirmedContext) && confirmedContext === notifiedContext
    && confirmed && notified && domains.length && domains.every(domain =>
    Number.isSafeInteger(confirmed[domain]) && confirmed[domain] === notified[domain]))
}

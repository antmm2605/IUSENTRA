/** Coalesce invalidations while retaining changes received during a request. */
import { normalizeRevisionContext, normalizeRevisionProof, sameRevisionProof, type OperationalRevisions } from './operationalRevisionProof'

export type OperationalRefreshPacing = {
  /** Distanza minima fra due aggiornamenti dovuti a modifiche di altri (lavori automatici, altre finestre). */
  minLiveIntervalMs?: number
  /** Con la scheda nascosta gli aggiornamenti dovuti ad altri attendono che l'avvocato torni sulla pagina. */
  pauseWhenHidden?: boolean
}

export function createOperationalRefreshQueue(refresh: (intent: { live: boolean; revisions?: OperationalRevisions; revisionContext?: string }) => void | boolean | Promise<unknown>, status: (failed: boolean) => void, pacing: OperationalRefreshPacing = {}) {
  let disposed = false
  let lastLiveDone = 0
  let waitingVisible = false
  const hidden = () => Boolean(pacing.pauseWhenHidden && typeof document !== 'undefined' && document.visibilityState === 'hidden')
  // Solo gli aggiornamenti «live» (modifiche fatte da altri) si distanziano: i comandi dell'avvocato restano immediati.
  let liveDone = false
  const liveDelay = () => liveDone ? Math.max(120, (pacing.minLiveIntervalMs ?? 0) - (Date.now() - lastLiveDone)) : 120
  const onVisible = () => {
    if (disposed || !waitingVisible || hidden()) return
    waitingVisible = false
    if (!running && pending) { if (timer) clearTimeout(timer); timer = setTimeout(() => { void run() }, liveDelay()) }
  }
  if (pacing.pauseWhenHidden && typeof document !== 'undefined') document.addEventListener('visibilitychange', onVisible)
  let running = false
  let pending = false
  let pendingLive = false
  let pendingRevisions: OperationalRevisions | undefined
  let pendingContext: string | undefined
  let failures = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  const run = async () => {
    timer = undefined
    if (disposed || running || !pending) return
    if (pendingLive && hidden()) { waitingVisible = true; return }
    running = true
    pending = false
    const live = pendingLive
    const revisions = pendingRevisions
    const revisionContext = pendingContext
    pendingLive = false
    pendingRevisions = undefined
    pendingContext = undefined
    try {
      const result = await refresh({ live, revisions, revisionContext })
      if (live) { lastLiveDone = Date.now(); liveDone = true }
      if (result === false) throw new Error('Aggiornamento della vista non confermato')
      if (!disposed) { failures = 0; status(false) }
    } catch {
      if (!disposed) {
        if (live) {
          const compatible = !pendingLive || (pendingContext === revisionContext && sameRevisionProof(pendingRevisions, revisions))
          pendingRevisions = compatible ? revisions : undefined
          pendingContext = compatible ? revisionContext : undefined
          pendingLive = true
        }
        failures += 1
        status(true)
        // Bounded recovery; a later invalidation or explicit retry can resume.
        if (failures < 3) pending = true
      }
    } finally {
      running = false
      if (!disposed && pending) timer = setTimeout(() => { void run() }, failures ? 1000 * failures : 120)
    }
  }
  return {
    schedule(intent: { live?: boolean; revisions?: OperationalRevisions; revisionContext?: string } = {}) {
      if (disposed) return
      pending = true
      if (intent.live) {
        const revisions = normalizeRevisionProof(intent.revisions)
        const context = normalizeRevisionContext(intent.revisionContext)
        const compatible = !pendingLive || (pendingContext === context && sameRevisionProof(pendingRevisions, revisions))
        pendingRevisions = compatible ? revisions : undefined
        pendingContext = compatible ? context : undefined
        pendingLive = true
      }
      failures = 0
      if (!running) {
        if (timer) clearTimeout(timer)
        timer = setTimeout(() => { void run() }, intent.live ? liveDelay() : 120)
      }
    },
    dispose() {
      disposed = true
      if (timer) clearTimeout(timer)
      if (pacing.pauseWhenHidden && typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisible)
    },
  }
}

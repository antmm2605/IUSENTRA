/** Coalesce invalidations while retaining changes received during a request. */
export function createOperationalRefreshQueue(refresh: () => void | boolean | Promise<unknown>, status: (failed: boolean) => void) {
  let disposed = false
  let running = false
  let pending = false
  let failures = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  const run = async () => {
    timer = undefined
    if (disposed || running || !pending) return
    running = true
    pending = false
    try {
      const result = await refresh()
      if (result === false) throw new Error('Aggiornamento della vista non confermato')
      if (!disposed) { failures = 0; status(false) }
    } catch {
      if (!disposed) {
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
    schedule() {
      if (disposed) return
      pending = true
      failures = 0
      if (!running) {
        if (timer) clearTimeout(timer)
        timer = setTimeout(() => { void run() }, 120)
      }
    },
    dispose() { disposed = true; if (timer) clearTimeout(timer) },
  }
}

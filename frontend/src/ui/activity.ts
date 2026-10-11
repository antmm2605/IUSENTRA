export type Activity = { id: number; label: string; startedAt: number }
type Listener = () => void

const listeners = new Set<Listener>()
let activities: readonly Activity[] = []
let sequence = 0

export function getActivities(): readonly Activity[] { return activities }
export function subscribeActivities(listener: Listener): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

function notify() { for (const listener of listeners) listener() }

/** Each operation owns its lifetime; one completion cannot clear another. */
export function beginActivity(label: string): () => void {
  const id = ++sequence
  activities = [...activities, { id, label, startedAt: Date.now() }]
  notify()
  let finished = false
  return () => {
    if (finished) return
    finished = true
    activities = activities.filter(activity => activity.id !== id)
    notify()
  }
}

/** Keep activity until the wrapped operation finishes, including failure. */
export async function withActivity<T>(label: string | false, operation: () => Promise<T>): Promise<T> {
  const finish = label === false ? () => {} : beginActivity(label)
  try { return await operation() } finally { finish() }
}

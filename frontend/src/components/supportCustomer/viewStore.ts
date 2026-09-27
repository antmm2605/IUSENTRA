/**
 * Stato osservabile minimo per useSyncExternalStore: il controller (TypeScript
 * puro, fuori da React) aggiorna lo stato, i componenti lo leggono.
 */
export class ViewStore<T extends object> {
  private state: T
  private readonly listeners = new Set<() => void>()

  constructor(initial: T) {
    this.state = initial
  }

  getSnapshot = (): T => this.state

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  update(patch: Partial<T> | ((current: T) => Partial<T>)): void {
    const next = typeof patch === 'function' ? patch(this.state) : patch
    const changed = (Object.keys(next) as Array<keyof T>).some((key) => !Object.is(this.state[key], next[key]))
    if (!changed) return
    this.state = { ...this.state, ...next }
    this.listeners.forEach((listener) => listener())
  }
}

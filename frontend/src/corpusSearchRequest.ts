type SearchTask = (controller: AbortController, isCurrent: () => boolean) => Promise<boolean>
type ActiveRequest = { source: string; query: string; controller: AbortController; result: Promise<boolean> }

/** Refresh della stessa ricerca: una richiesta; ricerca diversa: prevale l'ultima. */
export function createCorpusRequestGate() {
  let active: ActiveRequest | null = null
  function cancel() {
    const previous = active
    active = null
    previous?.controller.abort()
  }
  function run(source: string, query: string, task: SearchTask): Promise<boolean> {
    if (active?.source === source && active.query === query) return active.result
    cancel()
    const controller = new AbortController()
    const request: ActiveRequest = {
      source, query, controller,
      result: Promise.resolve()
        .then(() => task(controller, () => active === request))
        .finally(() => { if (active === request) active = null }),
    }
    active = request
    return request.result
  }
  return { run, cancel }
}

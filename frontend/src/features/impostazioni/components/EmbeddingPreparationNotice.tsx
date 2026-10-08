import { useEffect, useState } from 'react'

type Preparation = {
  present?: boolean
  stage?: string
  rows?: number
  total?: number
  message?: string
}

export function EmbeddingPreparationNotice() {
  const [preparation, setPreparation] = useState<Preparation | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let requestTimer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined
    let initial = true
    const refresh = async () => {
      try {
        if (initial || document.visibilityState !== 'hidden') {
          initial = false
          controller = new AbortController()
          requestTimer = setTimeout(() => controller?.abort(), 10_000)
          const response = await fetch('/api/v1/ui/impostazioni/ai/status?preparazione=1', {
            credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal,
          })
          if (!response.ok) throw new Error('Avanzamento non disponibile')
          const result = await response.json() as { status_payload?: { preparation?: Preparation } }
          if (typeof result.status_payload?.preparation?.present !== 'boolean') {
            throw new Error('Risposta della preparazione non valida')
          }
          if (!stopped) {
            setPreparation(result.status_payload?.preparation || null)
            setUnavailable(false)
          }
        }
      } catch {
        if (!stopped) setUnavailable(true)
      } finally {
        clearTimeout(requestTimer)
        if (!stopped) timer = setTimeout(() => { void refresh() }, 15_000)
      }
    }
    void refresh()
    return () => { stopped = true; clearTimeout(timer); clearTimeout(requestTimer); controller?.abort() }
  }, [])

  if (!preparation?.present) return unavailable ? (
    <div className="iu-settings-embedding-preparation" role="status">
      Stato della preparazione locale non disponibile. Il controllo riprova automaticamente.
    </div>
  ) : null
  const rows = Math.max(0, Number(preparation.rows) || 0)
  const total = Math.max(0, Number(preparation.total) || 0)
  const building = preparation.stage === 'building'
  return (
    <div className="iu-settings-embedding-preparation" aria-label="Preparazione del nuovo motore locale">
      <strong>Nuovo motore di ricerca locale</strong>
      {unavailable ? (
        <span role="status">Aggiornamento dell’avanzamento non disponibile. Nuovo controllo automatico tra pochi secondi.</span>
      ) : preparation.stage === 'error' ? (
        <span role="status">{preparation.message}</span>
      ) : (
        <>
          <span>
            {building ? 'Preparazione indice normativo' : 'Indice normativo preparato'}:
            {' '}{rows.toLocaleString('it-IT')} di {total.toLocaleString('it-IT')} voci.
          </span>
          {building && total > 0 && (
            <progress value={Math.min(rows, total)} max={total} aria-label="Voci normative preparate" />
          )}
          <small>Il motore attuale resta operativo. Il nuovo indice richiede la verifica finale prima dell’attivazione.</small>
        </>
      )}
    </div>
  )
}

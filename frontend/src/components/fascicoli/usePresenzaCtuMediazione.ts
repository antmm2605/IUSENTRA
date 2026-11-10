import { useEffect, useState } from 'react'
import { ensureJson } from '../../lib/apiClient'

/**
 * CTU e mediazione compaiono nella pagina del fascicolo solo se il fascicolo ne ha
 * (decisione dell'avvocato del 10/11/2026); altrimenti resta un solo pulsante per aggiungerle.
 * Se la lettura non riesce le sezioni si mostrano comunque: un errore non deve nascondere dati.
 */
export type PresenzaCtuMediazione = { ctu: boolean; mediazione: boolean; letto: boolean }

function contaElenco(payload: unknown, chiave: string): number {
  if (!payload || typeof payload !== 'object') return 0
  const elenco = (payload as Record<string, unknown>)[chiave]
  return Array.isArray(elenco) ? elenco.length : 0
}

export function usePresenzaCtuMediazione(fascicoloId: string): PresenzaCtuMediazione {
  const [presenza, setPresenza] = useState<PresenzaCtuMediazione>({ ctu: false, mediazione: false, letto: false })
  useEffect(() => {
    if (!fascicoloId) return undefined
    const controller = new AbortController()
    const id = encodeURIComponent(fascicoloId)
    const leggi = (url: string, chiave: string) => ensureJson<unknown>(url, { signal: controller.signal, activity: false })
      .then((payload) => contaElenco(payload, chiave) > 0)
      .catch(() => true)
    setPresenza({ ctu: false, mediazione: false, letto: false })
    void Promise.all([
      leggi(`/api/v1/ui/fascicoli/${id}/ctu`, 'incarichi'),
      leggi(`/api/fascicoli/${id}/mediazioni`, 'procedimenti'),
    ]).then(([ctu, mediazione]) => {
      if (!controller.signal.aborted) setPresenza({ ctu, mediazione, letto: true })
    })
    return () => controller.abort()
  }, [fascicoloId])
  return presenza
}

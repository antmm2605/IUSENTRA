import { useCallback, useEffect, useRef, useState } from 'react'
import { DashboardData, DashboardStatus, emptyDashboard, getDashboard, syncDashboardMailboxes } from '../data'

/**
 * Stato e freschezza del quadro operativo della Panoramica.
 *
 * La Panoramica resta aperta per ore su una scrivania: senza un
 * riallineamento periodico l'avvocato guarda scadenze, PEC e agenda della
 * sessione in cui ha aperto il browser. Qui il dato si riallinea da solo,
 * ma solo quando la scheda e' davvero visibile — una scheda in secondo
 * piano non deve continuare a interrogare gli archivi dello studio.
 *
 * L'aggiornamento automatico e' silenzioso: non accende lo stato di
 * caricamento, cosi' i pannelli non lampeggiano mentre si sta leggendo.
 */
export const DASHBOARD_AUTO_REFRESH_MS = 300000
/** Ritorno sulla scheda: si ricarica solo se il quadro e' piu' vecchio di questa soglia. */
export const DASHBOARD_STALE_AFTER_MS = 120000

export type DashboardState = {
  data: DashboardData
  loading: boolean
  mailSyncing: boolean
  refresh: () => void
  syncMailboxes: () => void
}

export function useDashboardData(enabled: boolean): DashboardState {
  const [data, setData] = useState<DashboardData>(emptyDashboard)
  const [loading, setLoading] = useState(enabled)
  const [mailSyncing, setMailSyncing] = useState(false)
  const mountedRef = useRef(true)
  // Progressivo di richiesta: una risposta lenta non deve sovrascrivere un
  // caricamento piu' recente (e sotto StrictMode il primo giro va scartato,
  // non trattato come una richiesta persa).
  const requestRef = useRef(0)
  const lastLoadedRef = useRef(0)
  // Stato corrente in ref: `load` deve restare stabile, altrimenti l'effetto
  // di primo caricamento si rilancerebbe a ogni risposta.
  const statusRef = useRef<DashboardStatus>(emptyDashboard.status)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const load = useCallback((options: { refresh?: boolean; silent?: boolean } = {}) => {
    const requestId = requestRef.current + 1
    requestRef.current = requestId
    if (!options.silent) setLoading(true)
    getDashboard({ refresh: options.refresh })
      .then((payload) => {
        if (!mountedRef.current || requestId !== requestRef.current) return
        // Un aggiornamento silenzioso non deve sostituire un quadro valido
        // con gli zeri di cortesia di una rete caduta: in quel caso si tiene
        // quello che l'utente sta gia' leggendo e si ritenta al giro dopo.
        if (options.silent && payload.status === 'errore' && statusRef.current !== 'errore') return
        statusRef.current = payload.status
        setData(payload)
        lastLoadedRef.current = Date.now()
      })
      .finally(() => {
        if (mountedRef.current && requestId === requestRef.current && !options.silent) setLoading(false)
      })
  }, [])

  const refresh = useCallback(() => load({ refresh: true }), [load])

  const syncMailboxes = useCallback(() => {
    setMailSyncing(true)
    // Anche la sincronizzazione occupa il progressivo: il suo esito e' il piu'
    // recente e non deve essere sovrascritto da un auto refresh in volo.
    const requestId = requestRef.current + 1
    requestRef.current = requestId
    syncDashboardMailboxes()
      .then(() => getDashboard({refresh:true}))
      .then((payload) => {
        if (!mountedRef.current || requestId !== requestRef.current) return
        statusRef.current = payload.status
        setData(payload)
        lastLoadedRef.current = Date.now()
      })
      .finally(() => {
        if (mountedRef.current) setMailSyncing(false)
      })
  }, [])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    load()
  }, [enabled, load])

  useEffect(() => {
    if (!enabled) return
    const refreshIfVisible = () => {
      if (document.visibilityState !== 'visible') return
      load({ refresh: true, silent: true })
    }
    const timer = window.setInterval(refreshIfVisible, DASHBOARD_AUTO_REFRESH_MS)
    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return
      if (Date.now() - lastLoadedRef.current < DASHBOARD_STALE_AFTER_MS) return
      load({ refresh: true, silent: true })
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [enabled, load])

  return { data, loading, mailSyncing, refresh, syncMailboxes }
}

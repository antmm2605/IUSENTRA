import { useCallback, useEffect, useState, type RefObject } from 'react'

/**
 * Pagina e testo a tutto schermo, per rileggere un atto lungo senza il resto
 * del fascicolo intorno.
 *
 * Si usa lo schermo intero del browser sullo stesso riquadro: non e' una
 * finestra nuova, e Esc lo chiude il browser. Dove il browser non lo concede
 * (l'iPhone non lo da' agli elementi della pagina) il riquadro si allarga a
 * tutta la finestra, e Esc lo chiude lo stesso.
 */
export function useSchermoIntero(elemento: RefObject<HTMLElement | null>) {
  const [delBrowser, setDelBrowser] = useState(false)
  const [ripiego, setRipiego] = useState(false)

  useEffect(() => {
    const aggiorna = () => setDelBrowser(Boolean(elemento.current) && document.fullscreenElement === elemento.current)
    document.addEventListener('fullscreenchange', aggiorna)
    return () => document.removeEventListener('fullscreenchange', aggiorna)
  }, [elemento])

  useEffect(() => {
    if (!ripiego) return
    const esci = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') setRipiego(false)
    }
    document.addEventListener('keydown', esci)
    return () => document.removeEventListener('keydown', esci)
  }, [ripiego])

  const alterna = useCallback(async () => {
    const riquadro = elemento.current
    if (!riquadro) return
    if (document.fullscreenElement) {
      await document.exitFullscreen().catch(() => undefined)
      return
    }
    if (ripiego) {
      setRipiego(false)
      return
    }
    if (document.fullscreenEnabled && typeof riquadro.requestFullscreen === 'function') {
      // Alcuni contenitori (app desktop, riquadri incorporati) promettono lo
      // schermo intero e poi non lo danno, o non rispondono affatto: conta
      // solo se il riquadro e' davvero a schermo intero poco dopo.
      await Promise.race([
        riquadro.requestFullscreen().catch(() => undefined),
        new Promise((fine) => window.setTimeout(fine, 600)),
      ])
      await new Promise((fine) => window.setTimeout(fine, 80))
      if (document.fullscreenElement === riquadro) return
      // rifiutato dal browser: si allarga il riquadro
    }
    setRipiego(true)
  }, [elemento, ripiego])

  return { attivo: delBrowser || ripiego, ripiego, alterna }
}

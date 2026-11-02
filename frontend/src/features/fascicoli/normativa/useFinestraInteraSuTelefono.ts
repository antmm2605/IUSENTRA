import { useEffect } from 'react'

/**
 * Sul telefono il pannello si apre a tutto schermo. Ogni finestra di dialogo dello studio è
 * gestita dal sistema delle finestre (spostare, ridurre a icona, ingrandire): qui si usa il suo
 * comando «Ingrandisci», così il pannello resta governato come tutte le altre finestre.
 */
export function useFinestraInteraSuTelefono(aperta: boolean, titolo: string) {
  useEffect(() => {
    if (!aperta || typeof window === 'undefined' || !window.matchMedia?.('(max-width: 640px)').matches) return undefined
    let tentativi = 0
    let timer = 0
    const prova = () => {
      const comando = document.querySelector<HTMLButtonElement>(`button[aria-label="Ingrandisci ${titolo}"]`)
      if (comando) { comando.click(); return }
      if (++tentativi < 20) timer = window.setTimeout(prova, 50)
    }
    timer = window.setTimeout(prova, 0)
    return () => window.clearTimeout(timer)
  }, [aperta, titolo])
}
